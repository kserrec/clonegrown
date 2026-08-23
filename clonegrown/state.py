"""Durable state: the workspace record, the worker record, and the worker state machine.

A workspace is a directory holding a ``.cws/`` control tree plus numbered
worker slots. The canonical repository carries a marker file under its Git
directory binding it to each workspace. Every record is validated before it
may select a path or a Git ref.
"""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import re
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .core import (
    PROTOCOL_NAME, ClonegrownError, atomic_json, file_lock, git_common_dir, git_dir, lexical_abs, load_json,
    object_format, pid_fingerprint, validate_primary_repo,
)

SCHEMA = 3
RESERVED_SOURCE_PREFIX = f"{PROTOCOL_NAME}-source"
WORKER_MODES = frozenset({"clone", "worktree"})

_HEX = r"[0-9a-f]+"


# --- the worker state machine ------------------------------------------------

class WorkerStatus:
    """Every status a worker record can hold, and the groups the lifecycle reasons about.

    Spawn:   allocated -> cloning -> configuring -> publishing -> ready   (or spawn_failed)
    Collect: ready -> collecting -> collected
    Discard: ready|collected -> discarding -> discarded | abandoned
    Any status whose on-disk worker no longer authenticates becomes ``broken``.
    """
    ALLOCATED = "allocated"
    CLONING = "cloning"
    CONFIGURING = "configuring"
    PUBLISHING = "publishing"
    READY = "ready"
    COLLECTING = "collecting"
    COLLECTED = "collected"
    DISCARDING = "discarding"
    DISCARDED = "discarded"
    ABANDONED = "abandoned"
    SPAWN_FAILED = "spawn_failed"
    BROKEN = "broken"

    ALL = frozenset({ALLOCATED, CLONING, CONFIGURING, PUBLISHING, READY, COLLECTING, COLLECTED,
                     DISCARDING, DISCARDED, ABANDONED, SPAWN_FAILED, BROKEN})
    SPAWNING = frozenset({ALLOCATED, CLONING, CONFIGURING, PUBLISHING})
    ACTIVE = SPAWNING | {COLLECTING, DISCARDING}           # an owning process may be mid-operation
    SETTLED = frozenset({READY, COLLECTED, DISCARDED, ABANDONED})  # what a waiting spawn may return
    RETRYABLE = frozenset({SPAWN_FAILED, ABANDONED})       # a request id may be reused after these
    GONE = frozenset({DISCARDED, ABANDONED})               # the worker directory has been deleted
    TOMBSTONE = GONE | {SPAWN_FAILED}                      # nothing on disk should remain


# --- workspace layout --------------------------------------------------------

def ws_paths(ws: Path) -> dict[str, Path]:
    ctl = ws / f".{PROTOCOL_NAME}"
    return {
        "ctl": ctl,
        "state": ctl / "state.json",
        "lock": ctl / "lock",
        "workers": ctl / "workers",
        "requests": ctl / "requests",
        "locks": ctl / "locks",
        "staging": ctl / "staging",
    }


def worker_lock_path(ws: Path, worker_id: int) -> Path:
    return ws_paths(ws)["locks"] / f"{worker_id}.lock"


def worker_record_path(ws: Path, worker_id: int) -> Path:
    return ws_paths(ws)["workers"] / f"{worker_id}.json"


def request_path(ws: Path, request_id: str) -> Path:
    key = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
    return ws_paths(ws)["requests"] / f"{key}.json"


def worker_slot(ws: Path, worker_id: int) -> Path:
    """The numbered directory that holds one worker's repository."""
    return ws / str(worker_id)


def staging_root(ws: Path, worker_id: int, token: str) -> Path:
    return ws_paths(ws)["staging"] / f"{worker_id}-{token}"


def canonical_marker_path(canonical: Path, workspace_id: str) -> Path:
    return git_common_dir(canonical) / PROTOCOL_NAME / f"{workspace_id}.json"


def worker_marker_path(repo: Path) -> Path:
    # The per-repository Git directory: .git itself for a clone, the private
    # .git/worktrees/<name> admin directory for a linked worktree.
    return git_dir(repo) / f"{PROTOCOL_NAME}-worker.json"


def validate_control_dir(ws: Path, require_state: bool = False) -> None:
    paths = ws_paths(ws)
    ctl = paths["ctl"]
    try:
        mode = os.lstat(ctl).st_mode
    except FileNotFoundError:
        raise ClonegrownError(f"workspace control directory is missing: {ctl}")
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ClonegrownError("workspace control directory is not a real directory")
    for key in ("workers", "requests", "locks", "staging"):
        p = paths[key]
        try:
            mode = os.lstat(p).st_mode
        except FileNotFoundError:
            raise ClonegrownError(f"workspace control subdirectory is missing: {p.name}")
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise ClonegrownError(f"workspace control subdirectory is unsafe: {p.name}")
    if paths["state"].exists() or require_state:
        try:
            mode = os.lstat(paths["state"]).st_mode
        except FileNotFoundError:
            raise ClonegrownError("workspace state file is missing")
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise ClonegrownError("workspace state file is unsafe")


@contextlib.contextmanager
def workspace_lock(ws: Path) -> Iterator[None]:
    validate_control_dir(ws)
    with file_lock(ws_paths(ws)["lock"]) as acquired:
        if not acquired:
            raise ClonegrownError("could not acquire workspace lock")
        yield


# --- small helpers shared by both records ------------------------------------

def sanitize_task(task: str) -> str:
    s = task.strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"[-_.]{2,}", "-", s).strip("-._")
    return (s or "task")[:48]


def params_hash(base: str, task: str, strong: bool, mode: str = "clone") -> str:
    """Digest of a spawn request, used to detect a request id reused with different parameters."""
    params: dict[str, Any] = {"base": base, "task": task, "strong": bool(strong)}
    if mode != "clone":
        params["mode"] = mode  # omitted for clones so records written before worktree mode still verify
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _from_json(cls: type, data: dict[str, Any]) -> Any:
    """Build a record from JSON, keeping unknown keys in ``extra`` so they round-trip."""
    names = {f.name for f in dataclasses.fields(cls)} - {"extra"}
    known = {k: v for k, v in data.items() if k in names}
    extra = {k: v for k, v in data.items() if k not in names}
    return cls(**known, extra=extra)


def _to_json(record: Any, always: frozenset[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in dataclasses.fields(record):
        if f.name == "extra":
            continue
        value = getattr(record, f.name)
        if value is not None or f.name in always:
            out[f.name] = value
    out.update(record.extra)
    return out


# --- the workspace record ----------------------------------------------------

@dataclass
class WorkspaceState:
    """``.cws/state.json``: the workspace's identity and its binding to one canonical repository."""
    schema: int | None = None
    status: str | None = None                 # "initializing" until the canonical marker is written, then "ready"
    workspace_id: str | None = None           # 16 hex chars; names this workspace's refs and branches
    canonical_token: str | None = None        # 48 hex chars; shared secret with the canonical marker file
    workspace: str | None = None
    canonical: str | None = None
    canonical_git_dir: str | None = None
    object_format: str | None = None          # "sha1" or "sha256"
    repo_name: str | None = None              # basename of canonical; each worker's repo dir is named the same
    next_id: int | None = None
    created: float | None = None
    canonical_slot: int | None = None         # set when canonical itself lives in a numbered slot of this workspace
    extra: dict[str, Any] = field(default_factory=dict)

    _ALWAYS = frozenset({"schema", "status", "workspace_id", "canonical_token", "workspace", "canonical",
                         "canonical_git_dir", "object_format", "repo_name", "next_id", "created"})

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "WorkspaceState":
        return _from_json(cls, data)

    def to_json(self) -> dict[str, Any]:
        return _to_json(self, self._ALWAYS)

    @classmethod
    def load(cls, ws: Path, require_ready: bool = True) -> "WorkspaceState":
        validate_control_dir(ws, require_state=True)
        state = cls.from_json(load_json(ws_paths(ws)["state"]))
        state.validate(ws, require_ready=require_ready)
        return state

    def save(self, ws: Path) -> None:
        atomic_json(ws_paths(ws)["state"], self.to_json())

    # ref and name conventions inside the canonical repository
    @property
    def ref_prefix(self) -> str:
        return f"refs/{PROTOCOL_NAME}/{self.workspace_id}"

    def base_ref(self, worker_id: int) -> str:
        """Pins a worker's base commit against GC until the spawn is published."""
        return f"{self.ref_prefix}/bases/{worker_id}"

    def summary_ref(self, worker_id: int) -> str:
        """Mutable pointer to a worker's most recently collected result."""
        return f"{self.ref_prefix}/workers/{worker_id}/result"

    def result_ref(self, worker_id: int, sha: str) -> str:
        """Immutable copy of one collected result."""
        return f"{self.ref_prefix}/workers/{worker_id}/results/{sha}"

    def worker_branch(self, worker_id: int, task: str) -> str:
        return f"agent/{self.workspace_id}/{worker_id}-{sanitize_task(task)}"

    def worker_repo(self, ws: Path, worker_id: int) -> Path:
        return lexical_abs(worker_slot(ws, worker_id) / str(self.repo_name))

    def validate(self, ws: Path, require_ready: bool = True) -> None:
        if self.schema != SCHEMA:
            raise ClonegrownError("unsupported workspace metadata schema")
        if require_ready and self.status != "ready":
            raise ClonegrownError(f"workspace is not ready: {self.status}")
        if self.status not in {"initializing", "ready"}:
            raise ClonegrownError(f"unknown workspace state: {self.status!r}")
        if not isinstance(self.workspace_id, str) or not re.fullmatch(r"[0-9a-f]{16}", self.workspace_id):
            raise ClonegrownError("workspace ID is malformed")
        if not isinstance(self.canonical_token, str) or not re.fullmatch(r"[0-9a-f]{48}", self.canonical_token):
            raise ClonegrownError("canonical identity token is malformed")
        if lexical_abs(self.workspace or "") != lexical_abs(ws):
            raise ClonegrownError("workspace path identity changed")
        name = self.repo_name
        if (not isinstance(name, str) or not name or name in {".", ".."}
                or Path(name).is_absolute() or Path(name).name != name or "/" in name or "\\" in name):
            raise ClonegrownError("repository name in workspace state is unsafe")
        if self.object_format not in {"sha1", "sha256"}:
            raise ClonegrownError("unsupported object format in workspace state")
        if type(self.next_id) is not int or self.next_id < 1:
            raise ClonegrownError("workspace next worker ID is malformed")
        if not isinstance(self.canonical, str) or lexical_abs(self.canonical) != Path(self.canonical):
            raise ClonegrownError("canonical path in workspace state is not normalized")
        if (not isinstance(self.canonical_git_dir, str)
                or lexical_abs(self.canonical_git_dir) != Path(self.canonical_git_dir)):
            raise ClonegrownError("canonical Git path in workspace state is not normalized")
        if self.canonical_slot is not None and (type(self.canonical_slot) is not int or self.canonical_slot < 1):
            raise ClonegrownError("canonical slot metadata is malformed")

    def verify_canonical(self) -> Path:
        """Confirm the canonical repository is still the one this workspace was bound to."""
        canonical = validate_primary_repo(Path(str(self.canonical)))
        if str(canonical) != str(Path(str(self.canonical)).resolve()):
            raise ClonegrownError("canonical root changed")
        if git_common_dir(canonical) != Path(str(self.canonical_git_dir)).resolve():
            raise ClonegrownError("canonical Git directory identity changed")
        if object_format(canonical) != self.object_format:
            raise ClonegrownError("canonical object format changed")
        marker = load_json(canonical_marker_path(canonical, str(self.workspace_id)))
        if (marker.get("token") != self.canonical_token
                or marker.get("workspace_id") != self.workspace_id
                or lexical_abs(marker.get("canonical", "")) != lexical_abs(canonical)):
            raise ClonegrownError("canonical repository identity marker mismatch")
        return canonical


# --- the worker record -------------------------------------------------------

@dataclass
class WorkerRecord:
    """``.cws/workers/<id>.json``: everything known about one worker, written before every irreversible step."""
    # identity (written at allocation, never changed)
    schema: int | None = None
    id: int | None = None
    workspace_id: str | None = None
    canonical_token: str | None = None
    worker_token: str | None = None           # 32 hex chars; also written into the worker's marker file
    path: str | None = None                   # the worker repository, inside its numbered slot
    stage_root: str | None = None             # where the worker is built before the atomic publish
    branch: str | None = None
    base: str | None = None                   # what the caller asked for
    base_sha: str | None = None               # what it resolved to
    strong: bool | None = None                # clone without object sharing
    mode: str = "clone"                       # "clone" or "worktree"; records from before worktree mode have none
    task: str | None = None
    request_id: str | None = None
    params_hash: str | None = None
    created: float | None = None
    # lifecycle
    status: str | None = None
    error: str | None = None
    # ownership of an in-flight operation
    owner_pid: int | None = None
    owner_start: str | None = None
    heartbeat: float | None = None
    # spawn
    worktree_admin: str | None = None         # .git/worktrees/<name>; cleared once the directory is removed
    worktree_admin_left: str | None = None
    pending_spawn_details: dict[str, Any] | None = None
    ready: float | None = None
    failed: float | None = None
    interrupted_error: str | None = None
    source_remote: str | None = None
    alternates_detached: bool | None = None
    copied_local_config: list[str] | None = None
    copied_sparse_checkout: bool | None = None
    copied_auxiliary_refs: dict[str, int] | None = None
    compatibility_warnings: list[str] | None = None
    # collect
    candidate_sha: str | None = None
    candidate_ref: str | None = None
    allow_rewrite: bool | None = None
    collect_started: float | None = None
    result_sha: str | None = None
    result_ref: str | None = None
    collected: float | None = None
    collected_snapshot: dict[str, Any] | None = None
    collection_error: str | None = None
    collection_failed: float | None = None
    collection_race: dict[str, Any] | None = None
    collection_recovered: float | None = None
    # discard
    discard_intent: str | None = None         # "discarded" or "abandoned"
    discard_previous: str | None = None
    discard_started: float | None = None
    discarded: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    _ALWAYS = frozenset({"schema", "id", "workspace_id", "canonical_token", "worker_token", "status", "path",
                         "stage_root", "branch", "base", "base_sha", "strong", "mode", "task", "request_id",
                         "params_hash", "created"})

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "WorkerRecord":
        return _from_json(cls, data)

    _SPAWN_DETAILS = frozenset({"source_remote", "alternates_detached", "copied_local_config",
                                "copied_sparse_checkout", "copied_auxiliary_refs", "compatibility_warnings"})

    def to_json(self) -> dict[str, Any]:
        # Spawn details are part of the ready contract: present (possibly null) once the worker was published.
        always = self._ALWAYS | self._SPAWN_DETAILS if self.ready is not None else self._ALWAYS
        return _to_json(self, always)

    @classmethod
    def load(cls, ws: Path, worker_id: int) -> "WorkerRecord":
        return cls.from_json(load_json(worker_record_path(ws, worker_id)))

    def save(self, ws: Path) -> None:
        atomic_json(worker_record_path(ws, int(self.id)), self.to_json())

    @property
    def repo(self) -> Path:
        return Path(str(self.path))

    @property
    def is_worktree(self) -> bool:
        return self.mode == "worktree"

    def take_ownership(self, status: str) -> None:
        """Record this process as the live owner of an operation on the worker."""
        self.status = status
        self.owner_pid = os.getpid()
        self.owner_start = pid_fingerprint(os.getpid())
        self.heartbeat = time.time()

    def release_ownership(self) -> None:
        self.owner_pid = None
        self.owner_start = None

    def clear_candidate(self) -> None:
        self.candidate_sha = None
        self.candidate_ref = None

    def validate(self, ws: Path, state: WorkspaceState, worker_id: int) -> None:
        """Validate durable metadata before it selects a path or a Git ref."""
        if self.schema != SCHEMA:
            raise ClonegrownError("worker metadata schema mismatch")
        if type(self.id) is not int or self.id != worker_id:
            raise ClonegrownError("worker metadata ID does not match its filename")
        if self.workspace_id != state.workspace_id:
            raise ClonegrownError("worker metadata belongs to a different workspace")
        if self.canonical_token != state.canonical_token:
            raise ClonegrownError("worker metadata canonical identity mismatch")
        token = self.worker_token
        if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
            raise ClonegrownError("worker metadata token is malformed")
        if self.status not in WorkerStatus.ALL:
            raise ClonegrownError(f"unknown worker status: {self.status!r}")
        if not isinstance(self.task, str) or not isinstance(self.base, str):
            raise ClonegrownError("worker task/base metadata is malformed")
        if self.branch != state.worker_branch(worker_id, self.task):
            raise ClonegrownError("worker branch does not match deterministic assignment")
        if self.mode not in WORKER_MODES:
            raise ClonegrownError(f"unknown worker mode: {self.mode!r}")
        if self.is_worktree and self.strong:
            raise ClonegrownError("worktree worker cannot be strong")
        if self.params_hash != params_hash(self.base, self.task, bool(self.strong), self.mode):
            raise ClonegrownError("worker parameter digest mismatch")
        if self.worktree_admin is not None:
            if not self.is_worktree or not isinstance(self.worktree_admin, str):
                raise ClonegrownError("worktree admin path is malformed")
            admin = lexical_abs(self.worktree_admin)
            if admin.parent != lexical_abs(str(state.canonical_git_dir)) / "worktrees" or admin.name in {"", ".", ".."}:
                raise ClonegrownError("worktree admin path is outside the canonical worktrees directory")
        if lexical_abs(self.path or "") != state.worker_repo(ws, worker_id):
            raise ClonegrownError("worker metadata path does not match its allocated slot")
        if lexical_abs(self.stage_root or "") != lexical_abs(staging_root(ws, worker_id, token)):
            raise ClonegrownError("worker staging path does not match its allocation token")
        sha = self.base_sha
        expected_len = 64 if state.object_format == "sha256" else 40
        if not isinstance(sha, str) or len(sha) != expected_len or not re.fullmatch(_HEX, sha):
            raise ClonegrownError("worker base commit ID is malformed")
