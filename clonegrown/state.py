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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

from .core import (
    PROTOCOL_NAME, ClonegrownError, atomic_json, file_lock, git_common_dir, git_dir, lexical_abs, load_json,
    object_format, pid_fingerprint, validate_primary_repo,
)

SCHEMA = 3
RESERVED_SOURCE_PREFIX = f"{PROTOCOL_NAME}-source"
WORKER_MODES = frozenset({"clone", "worktree"})
LEASE_STATES = frozenset({"active", "released"})

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
        "quarantine": ctl / "quarantine",
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


def base_pin_ref(workspace_id: str, worker_id: int) -> str:
    """The ref that pins a worker's base commit against GC until it is ready or gone."""
    return f"refs/{PROTOCOL_NAME}/{workspace_id}/bases/{worker_id}"


def branch_owner_ref(workspace_id: str, worker_id: int) -> str:
    """The private ref that proves a worktree worker created its task branch; created with it, deleted with it."""
    return f"refs/{PROTOCOL_NAME}/{workspace_id}/workers/{worker_id}/branch-owner"


def quarantine_root(ws: Path, worker_id: int, token: str) -> Path:
    """Where a worker slot is parked before its final deletion; derived from identity, never stored raw."""
    return ws_paths(ws)["quarantine"] / f"{worker_id}-{token}"


def canonical_marker_path(canonical: Path, workspace_id: str) -> Path:
    return git_common_dir(canonical) / PROTOCOL_NAME / f"{workspace_id}.json"


def worker_marker_path(repo: Path) -> Path:
    # The per-repository Git directory: .git itself for a clone, the private
    # .git/worktrees/<name> admin directory for a linked worktree.
    return git_dir(repo) / f"{PROTOCOL_NAME}-worker.json"


def ensure_real_directory(path: Path, label: str, *, create: bool = False,
                          parents: bool = False) -> Path:
    """Create if requested, then prove ``path`` itself is a real directory.

    ``mkdir(exist_ok=True)`` can accept a symlink to a directory, so the
    non-following ``lstat`` is mandatory before any caller creates children or
    reads/writes through this parent.
    """
    if create:
        try:
            path.mkdir(parents=parents, exist_ok=True)
        except OSError as exc:
            raise ClonegrownError(f"{label} cannot be created: {exc}") from exc
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        raise ClonegrownError(f"{label} is missing: {path}")
    except OSError as exc:
        raise ClonegrownError(f"{label} cannot be inspected: {exc}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ClonegrownError(f"{label} is not a real directory: {path}")
    return path


def load_canonical_marker(path: Path) -> dict[str, Any]:
    """Read a canonical identity marker only below a real directory and from a real file."""
    ensure_real_directory(path.parent, "canonical marker directory")
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        raise ClonegrownError(f"canonical identity marker is missing: {path}")
    except OSError as exc:
        raise ClonegrownError(f"canonical identity marker cannot be inspected: {exc}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise ClonegrownError("canonical identity marker is not a real file")
    return load_json(path)


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
    try:
        mode = os.lstat(paths["quarantine"]).st_mode
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise ClonegrownError("workspace quarantine directory is unsafe: it is not a real directory")
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
        return base_pin_ref(str(self.workspace_id), worker_id)

    def summary_ref(self, worker_id: int) -> str:
        """Mutable pointer to a worker's most recently collected result."""
        return f"{self.ref_prefix}/workers/{worker_id}/result"

    def result_ref(self, worker_id: int, sha: str) -> str:
        """Immutable copy of one collected result."""
        return f"{self.ref_prefix}/workers/{worker_id}/results/{sha}"

    def worker_branch(self, worker_id: int, task: str) -> str:
        return f"agent/{self.workspace_id}/{worker_id}-{sanitize_task(task)}"

    def branch_owner_ref(self, worker_id: int) -> str:
        return branch_owner_ref(str(self.workspace_id), worker_id)

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
        marker = load_canonical_marker(canonical_marker_path(canonical, str(self.workspace_id)))
        if (marker.get("token") != self.canonical_token
                or marker.get("workspace_id") != self.workspace_id
                or lexical_abs(marker.get("canonical", "")) != lexical_abs(canonical)):
            raise ClonegrownError("canonical repository identity marker mismatch")
        return canonical


def _directory_identity(path: Path, label: str) -> tuple[int, int]:
    """A directory identity stable across renames, for one verify-to-lock interval."""
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise ClonegrownError(f"{label} is unavailable after canonical verification: {exc}") from exc
    if not stat.S_ISDIR(metadata.st_mode):
        raise ClonegrownError(f"{label} is no longer a real directory after canonical verification")
    return metadata.st_dev, metadata.st_ino


@dataclass(frozen=True)
class VerifiedWorkspace:
    """Canonical proof prepared outside a lock and checked against locked state before use.

    The workspace counter is intentionally excluded from the identity comparison: a
    concurrent allocation owns that change. Every other state value, both repository
    directories, and the canonical token marker must still match before a caller may
    mutate while holding ``workspace_lock``.
    """

    state: WorkspaceState
    canonical: Path
    canonical_git_dir: Path
    canonical_identity: tuple[int, int]
    canonical_git_dir_identity: tuple[int, int]

    @classmethod
    def load(cls, ws: Path) -> "VerifiedWorkspace":
        state = WorkspaceState.load(ws)
        canonical = state.verify_canonical()
        canonical_git_dir = Path(str(state.canonical_git_dir)).resolve()
        return cls(
            state=state,
            canonical=canonical,
            canonical_git_dir=canonical_git_dir,
            canonical_identity=_directory_identity(canonical, "canonical root"),
            canonical_git_dir_identity=_directory_identity(canonical_git_dir, "canonical Git directory"),
        )

    @contextlib.contextmanager
    def open_canonical_git_dir(self) -> Iterator[int]:
        """Hold the verified Git directory by descriptor across later Git mutations.

        A pathname identity check alone has a check/use gap: another process can
        rename the canonical checkout and put a different repository at the same
        name before Git starts. Opening before the locked reload and matching the
        descriptor here lets callers address the already-authenticated repository
        through ``/dev/fd`` even if its pathname changes afterward.
        """
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
        try:
            descriptor = os.open(self.canonical_git_dir, flags)
        except OSError as exc:
            raise ClonegrownError(f"cannot open canonical Git directory: {exc}") from exc
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != self.canonical_git_dir_identity:
                raise ClonegrownError("canonical Git directory identity changed before descriptor binding")
            if not Path("/dev/fd").is_dir():
                raise ClonegrownError("this platform cannot bind Git to an open canonical directory")
            yield descriptor
        finally:
            os.close(descriptor)

    def reload_under_lock(self, ws: Path) -> WorkspaceState:
        """Reload and match state/identity; the caller must already hold ``workspace_lock``."""
        current = WorkspaceState.load(ws)
        if int(current.next_id) < int(self.state.next_id):
            raise ClonegrownError(
                "workspace allocation counter moved backwards between canonical verification and locked use"
            )
        prepared_json = self.state.to_json()
        current_json = current.to_json()
        prepared_json.pop("next_id", None)
        current_json.pop("next_id", None)
        if current_json != prepared_json:
            raise ClonegrownError("workspace identity changed between canonical verification and locked use")
        if Path(str(current.canonical)).resolve() != self.canonical:
            raise ClonegrownError("canonical root changed between verification and locked use")
        if Path(str(current.canonical_git_dir)).resolve() != self.canonical_git_dir:
            raise ClonegrownError("canonical Git directory changed between verification and locked use")
        if _directory_identity(self.canonical, "canonical root") != self.canonical_identity:
            raise ClonegrownError("canonical root identity changed between verification and locked use")
        if (_directory_identity(self.canonical_git_dir, "canonical Git directory")
                != self.canonical_git_dir_identity):
            raise ClonegrownError("canonical Git directory identity changed between verification and locked use")
        marker = load_canonical_marker(
            self.canonical_git_dir / PROTOCOL_NAME / f"{current.workspace_id}.json"
        )
        if (marker.get("token") != current.canonical_token
                or marker.get("workspace_id") != current.workspace_id
                or lexical_abs(marker.get("canonical", "")) != lexical_abs(self.canonical)):
            raise ClonegrownError("canonical repository identity marker mismatch")
        return current


# --- the worker record -------------------------------------------------------

@dataclass
class WorkerRecord:
    """``.cws/workers/<id>.json``: identity and recorded lifecycle checkpoints for one worker."""
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
    # spawn
    worktree_admin: str | None = None         # .git/worktrees/<name>; cleared once the directory is proved gone
    worktree_admin_left: str | None = None    # why the admin directory was not removed
    branch_cleanup_sha: str | None = None     # the task branch tip recorded before cleanup; cleared once deleted
    branch_cleanup_left: str | None = None    # why the task branch was retained
    pending_spawn_details: dict[str, Any] | None = None
    ready: float | None = None
    failed: float | None = None
    interrupted_error: str | None = None
    source_remote: str | None = None
    alternates_detached: bool | None = None
    copied_local_config: list[str] | None = None
    copied_sparse_checkout: bool | None = None
    copied_auxiliary_refs: dict[str, int] | None = None
    clone_private_refs: dict[str, str] | None = None  # non-task refs at clone publication; absent means unverified
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
    # ownership handoff (schema 3, compatible extension): absent means active/unreleased
    lease: str | None = None                  # "active" or "released"
    lease_released: float | None = None
    # deletion custody (schema 3, compatible extension): absent means never quarantined
    quarantine_path: str | None = None        # .cws/quarantine/<id>-<token>; the parked slot awaiting deletion
    quarantine_started: float | None = None
    quarantine_snapshot: dict[str, Any] | None = None  # custody fingerprint taken before the rename
    quarantine_error: str | None = None       # why the final deletion did not complete
    extra: dict[str, Any] = field(default_factory=dict)

    _ALWAYS = frozenset({"schema", "id", "workspace_id", "canonical_token", "worker_token", "status", "path",
                         "stage_root", "branch", "base", "base_sha", "strong", "mode", "task", "request_id",
                         "params_hash", "created"})

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "WorkerRecord":
        return _from_json(cls, data)

    _SPAWN_DETAILS = frozenset({"source_remote", "alternates_detached", "copied_local_config",
                                "copied_sparse_checkout", "copied_auxiliary_refs", "clone_private_refs",
                                "compatibility_warnings"})

    def to_json(self) -> dict[str, Any]:
        # Spawn details are part of the ready contract: present (possibly null) once the worker was published.
        always = self._ALWAYS | self._SPAWN_DETAILS if self.ready is not None else self._ALWAYS
        out = _to_json(self, always)
        if self.ready is not None and self.lease is None:
            out["lease"] = "active"  # an absent lease means leased; every published record says so
        return out

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

    @property
    def is_leased(self) -> bool:
        """The cooperative work lease. Absent means leased: records from before the field default safe."""
        return self.lease != "released"

    def take_ownership(self, status: str) -> None:
        """Record this process as the live owner of an operation on the worker."""
        self.status = status
        self.owner_pid = os.getpid()
        self.owner_start = pid_fingerprint(os.getpid())

    def release_ownership(self) -> None:
        self.owner_pid = None
        self.owner_start = None

    def clear_candidate(self) -> None:
        self.candidate_sha = None
        self.candidate_ref = None

    def validate(self, ws: Path, state: WorkspaceState, worker_id: int) -> None:
        """Validate durable metadata before it selects a path or a Git ref.

        One pass, in order: identity fields that bind the record to this
        workspace and slot; the shape of every field that is present; the
        fields each status requires and forbids; and the dependencies between
        fields (a ref must name its commit, a timestamp must follow its state).
        Absent lease and quarantine fields keep their conservative meaning:
        leased and never quarantined.
        """
        self._validate_identity(ws, state, worker_id)
        self._validate_shapes(state)
        self._validate_status_fields()
        self._validate_dependencies(ws, state, worker_id)

    # identity: the record is this workspace's record for this slot
    def _validate_identity(self, ws: Path, state: WorkspaceState, worker_id: int) -> None:
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
        if not isinstance(self.task, str) or not isinstance(self.base, str) or not self.base:
            raise ClonegrownError("worker task/base metadata is malformed")
        if self.branch != state.worker_branch(worker_id, self.task):
            raise ClonegrownError("worker branch does not match deterministic assignment")
        if self.mode not in WORKER_MODES:
            raise ClonegrownError(f"unknown worker mode: {self.mode!r}")
        if type(self.strong) is not bool:
            raise ClonegrownError("worker isolation flag is malformed")
        if self.is_worktree and self.strong:
            raise ClonegrownError("worktree worker cannot be strong")
        if self.params_hash != params_hash(self.base, self.task, self.strong, self.mode):
            raise ClonegrownError("worker parameter digest mismatch")
        # Exact normalized strings: a path that merely normalizes to the slot (``x/../app``)
        # would still be used verbatim by every operation.
        if self.path != str(state.worker_repo(ws, worker_id)):
            raise ClonegrownError("worker metadata path does not match its allocated slot")
        if self.stage_root != str(lexical_abs(staging_root(ws, worker_id, token))):
            raise ClonegrownError("worker staging path does not match its allocation token")
        if self.request_id is not None and not isinstance(self.request_id, str):
            raise ClonegrownError("worker request ID is malformed")

    # shape: every present field has the type and format its readers assume
    def _validate_shapes(self, state: WorkspaceState) -> None:
        for name, check, what in _FIELD_SHAPES:
            value = getattr(self, name)
            if value is not None and not check(value):
                raise ClonegrownError(f"worker {name} is malformed: expected {what}")
        for name in _COMMIT_FIELDS:
            value = getattr(self, name)
            if value is not None and not _is_commit_id(value, state.object_format):
                raise ClonegrownError(f"worker {name} is not a {state.object_format} commit ID")
        if self.created is None:
            raise ClonegrownError("worker created timestamp is missing")
        if self.lease is not None and self.lease not in LEASE_STATES:
            raise ClonegrownError(f"unknown worker lease state: {self.lease!r}")
        if self.discard_intent is not None and self.discard_intent not in WorkerStatus.GONE:
            raise ClonegrownError(f"unknown worker discard intent: {self.discard_intent!r}")
        if self.discard_previous is not None and self.discard_previous not in _DISCARD_ORIGINS:
            raise ClonegrownError(f"unknown worker discard origin: {self.discard_previous!r}")
        worktree_only = (self.worktree_admin, self.worktree_admin_left, self.branch_cleanup_sha, self.branch_cleanup_left)
        if any(value is not None for value in worktree_only) and not self.is_worktree:
            raise ClonegrownError("worktree cleanup fields are only valid for a worktree worker")
        if self.pending_spawn_details is not None and not set(self.pending_spawn_details) <= self._SPAWN_DETAILS:
            raise ClonegrownError("worker pending spawn details name fields that are not spawn details")
        if self.worktree_admin is not None:
            admin = lexical_abs(self.worktree_admin)
            if admin.parent != lexical_abs(str(state.canonical_git_dir)) / "worktrees" or admin.name in {"", ".", ".."}:
                raise ClonegrownError("worktree admin path is outside the canonical worktrees directory")

    # status: what this status must and must not carry
    def _validate_status_fields(self) -> None:
        required, forbidden = _STATUS_FIELDS[str(self.status)]
        for name in required:
            if getattr(self, name) is None:
                raise ClonegrownError(f"worker in status {self.status} is missing {name}")
        for name in forbidden:
            if getattr(self, name) is not None:
                raise ClonegrownError(f"worker in status {self.status} must not carry {name}")
        if self.status not in WorkerStatus.ACTIVE and self.owner_pid is not None:
            raise ClonegrownError(f"worker in status {self.status} must not have an operation owner")

    # dependencies: fields that only make sense together, and refs that must name their commit
    def _validate_dependencies(self, ws: Path, state: WorkspaceState, worker_id: int) -> None:
        if self.owner_start is not None and self.owner_pid is None:
            raise ClonegrownError("worker owner fingerprint without an owner process")
        for sha_name, ref_name in (("candidate_sha", "candidate_ref"), ("result_sha", "result_ref")):
            sha, ref = getattr(self, sha_name), getattr(self, ref_name)
            if (sha is None) != (ref is None):
                raise ClonegrownError(f"worker {sha_name} and {ref_name} must be recorded together")
            if sha is not None and ref != state.result_ref(worker_id, sha):
                raise ClonegrownError(f"worker {ref_name} does not name its commit inside this workspace's namespace")
        snapshot = self.collected_snapshot
        if snapshot is not None:
            if (not _is_commit_id(snapshot.get("head"), state.object_format)
                    or snapshot.get("branch_ref") != f"refs/heads/{self.branch}"):
                raise ClonegrownError("worker collected snapshot is malformed")
            if self.result_sha is not None and snapshot["head"] != self.result_sha:
                raise ClonegrownError("worker collected snapshot does not match its result")
        if self.discard_intent == WorkerStatus.DISCARDED and self.discard_previous not in {None, WorkerStatus.COLLECTED}:
            raise ClonegrownError("only a collected worker can be discarded without abandonment")
        if self.status == WorkerStatus.DISCARDED and self.discard_intent == WorkerStatus.ABANDONED:
            raise ClonegrownError("worker recorded as discarded carries an abandon intent")
        if self.status == WorkerStatus.ABANDONED and self.discard_intent == WorkerStatus.DISCARDED:
            raise ClonegrownError("worker recorded as abandoned carries a discard intent")
        if self.status == WorkerStatus.DISCARDING and self.discard_previous == WorkerStatus.COLLECTED and self.result_sha is None:
            raise ClonegrownError("discarding a collected worker requires its preserved result")
        if (self.status in _DISCARD_STATUSES and self.discard_previous in {WorkerStatus.READY, WorkerStatus.COLLECTED}
                and self.ready is None):
            raise ClonegrownError("a worker discarded after publication must record when it became ready")
        if self.lease_released is not None and self.lease != "released":
            raise ClonegrownError("worker lease release time without a released lease")
        if self.lease == "released" and self.status in _UNPUBLISHED:
            raise ClonegrownError("an unpublished worker cannot have a released lease")
        if self.quarantine_path is not None:
            expected = quarantine_root(ws, worker_id, str(self.worker_token))
            if lexical_abs(self.quarantine_path) != lexical_abs(expected):
                raise ClonegrownError("worker quarantine path does not match its identity")
        elif (self.quarantine_started is not None or self.quarantine_error is not None
                or self.quarantine_snapshot is not None):
            raise ClonegrownError("worker quarantine details without a quarantine path")


# --- the validation tables ---------------------------------------------------

def _is_number(value: Any) -> bool:
    return type(value) in {int, float}


def _is_commit_id(value: Any, object_format: str | None) -> bool:
    expected_len = 64 if object_format == "sha256" else 40
    return isinstance(value, str) and len(value) == expected_len and re.fullmatch(_HEX, value) is not None


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_str_int_dict(value: Any) -> bool:
    return isinstance(value, dict) and all(isinstance(k, str) and type(v) is int for k, v in value.items())


def _is_str_str_dict(value: Any) -> bool:
    return isinstance(value, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())


_COMMIT_FIELDS = ("base_sha", "candidate_sha", "result_sha", "branch_cleanup_sha")
_UNPUBLISHED = WorkerStatus.SPAWNING | {WorkerStatus.SPAWN_FAILED}
_DISCARD_STATUSES = frozenset({WorkerStatus.DISCARDING}) | WorkerStatus.GONE
# Statuses discard may start from; a tombstone or reset remembers which one.
_DISCARD_ORIGINS = frozenset({WorkerStatus.READY, WorkerStatus.COLLECTED, WorkerStatus.BROKEN, WorkerStatus.SPAWN_FAILED})

# (field, predicate over a non-None value, description for the error)
_FIELD_SHAPES: tuple[tuple[str, Callable[[Any], bool], str], ...] = (
    ("created", _is_number, "a timestamp"),
    ("ready", _is_number, "a timestamp"),
    ("failed", _is_number, "a timestamp"),
    ("collect_started", _is_number, "a timestamp"),
    ("collected", _is_number, "a timestamp"),
    ("collection_failed", _is_number, "a timestamp"),
    ("collection_recovered", _is_number, "a timestamp"),
    ("discard_started", _is_number, "a timestamp"),
    ("discarded", _is_number, "a timestamp"),
    ("lease_released", _is_number, "a timestamp"),
    ("quarantine_started", _is_number, "a timestamp"),
    ("owner_pid", lambda v: type(v) is int and v > 0, "a process ID"),
    ("owner_start", lambda v: isinstance(v, str), "a process fingerprint"),
    ("error", lambda v: isinstance(v, str), "text"),
    ("interrupted_error", lambda v: isinstance(v, str), "text"),
    ("collection_error", lambda v: isinstance(v, str), "text"),
    ("quarantine_error", lambda v: isinstance(v, str), "text"),
    ("worktree_admin", lambda v: isinstance(v, str), "a path"),
    ("worktree_admin_left", lambda v: isinstance(v, str), "text"),
    ("branch_cleanup_left", lambda v: isinstance(v, str), "text"),
    ("quarantine_path", lambda v: isinstance(v, str), "a path"),
    ("pending_spawn_details", lambda v: isinstance(v, dict), "an object"),
    ("collected_snapshot", lambda v: isinstance(v, dict), "an object"),
    ("collection_race", lambda v: isinstance(v, dict), "an object"),
    ("quarantine_snapshot", lambda v: isinstance(v, dict), "an object"),
    ("source_remote", lambda v: isinstance(v, str), "text"),
    ("alternates_detached", lambda v: type(v) is bool, "a boolean"),
    ("copied_local_config", _is_str_list, "a list of config keys"),
    ("copied_sparse_checkout", lambda v: type(v) is bool, "a boolean"),
    ("copied_auxiliary_refs", _is_str_int_dict, "ref counts by namespace"),
    ("clone_private_refs", _is_str_str_dict, "refs mapped to object IDs or symbolic targets"),
    ("compatibility_warnings", _is_str_list, "a list of warnings"),
    ("allow_rewrite", lambda v: type(v) is bool, "a boolean"),
)

_CANDIDATE = frozenset({"candidate_sha", "candidate_ref"})
_RESULT = frozenset({"result_sha", "result_ref"})
_DISCARD = frozenset({"discard_intent", "discard_previous", "discard_started"})
_QUARANTINE = frozenset({"quarantine_path", "quarantine_started", "quarantine_snapshot", "quarantine_error"})
_NOT_YET_PUBLISHED = (frozenset({"ready", "collected", "discarded", "lease_released"})
                      | _CANDIDATE | _RESULT | _DISCARD | _QUARANTINE)

# Per status: (fields the lifecycle always writes before entering it, fields that
# would select a path or ref this status has no right to). Fields not named are
# validated for shape only, so records written by earlier code keep loading.
_STATUS_FIELDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    WorkerStatus.ALLOCATED: (frozenset(), _NOT_YET_PUBLISHED),
    WorkerStatus.CLONING: (frozenset(), _NOT_YET_PUBLISHED),
    WorkerStatus.CONFIGURING: (frozenset(), _NOT_YET_PUBLISHED),
    WorkerStatus.PUBLISHING: (frozenset(), _NOT_YET_PUBLISHED),
    WorkerStatus.READY: (frozenset({"ready"}), frozenset({"collected", "discarded"}) | _CANDIDATE | _RESULT | _QUARANTINE),
    WorkerStatus.COLLECTING: (frozenset({"ready", "collect_started"}) | _CANDIDATE,
                              frozenset({"collected", "discarded"}) | _RESULT | _QUARANTINE),
    WorkerStatus.COLLECTED: (frozenset({"ready", "collected"}) | _RESULT, frozenset({"discarded"}) | _CANDIDATE | _QUARANTINE),
    WorkerStatus.DISCARDING: (_DISCARD, frozenset({"discarded"}) | _CANDIDATE),
    WorkerStatus.DISCARDED: (frozenset({"ready", "collected", "discarded"}) | _RESULT,
                             _CANDIDATE | _QUARANTINE),
    WorkerStatus.ABANDONED: (frozenset({"discarded"}), _CANDIDATE | _QUARANTINE),
    WorkerStatus.SPAWN_FAILED: (frozenset({"failed", "error"}), _NOT_YET_PUBLISHED),
    WorkerStatus.BROKEN: (frozenset({"error"}), frozenset()),
}
assert set(_STATUS_FIELDS) == WorkerStatus.ALL
