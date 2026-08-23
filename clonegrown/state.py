"""Durable workspace and worker state: layout, identity, validation, ref names.

A workspace is a directory holding a ``.cws/`` control tree plus numbered
worker slots. The canonical repository carries a marker file under its Git
directory binding it to each workspace. Every record is validated before it
may select a path or a Git ref.
"""
from __future__ import annotations

import contextlib
import errno
import hashlib
import json
import os
import re
import stat
import time
from pathlib import Path
from typing import Any, Iterator

from .core import (
    CWSError, atomic_json, file_lock, git_common_dir, git_dir, lexical_abs, load_json, object_format,
    validate_primary_repo,
)

SCHEMA = 3
RESERVED_SOURCE_PREFIX = "cws-source"
WORKER_MODES = {"clone", "worktree"}

ACTIVE_SPAWN = {"allocated", "cloning", "configuring", "publishing"}
ACTIVE_COLLECT = {"collecting"}
ACTIVE_DISCARD = {"discarding"}
TERMINAL_SPAWN_FAILURE = {"spawn_failed", "abandoned"}
KNOWN_WORKER_STATUSES = {
    "allocated", "cloning", "configuring", "publishing", "ready",
    "collecting", "collected", "discarding", "discarded", "abandoned",
    "spawn_failed", "broken",
}

_HEX = r"[0-9a-f]+"


# --- workspace layout --------------------------------------------------------

def ws_paths(ws: Path) -> dict[str, Path]:
    ctl = ws / ".cws"
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


def worker_meta_path(ws: Path, worker_id: int) -> Path:
    return ws_paths(ws)["workers"] / f"{worker_id}.json"


def request_path(ws: Path, request_id: str) -> Path:
    key = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
    return ws_paths(ws)["requests"] / f"{key}.json"


def final_worker_root(ws: Path, worker_id: int) -> Path:
    return ws / str(worker_id)


def staging_root(ws: Path, worker_id: int, token: str) -> Path:
    return ws_paths(ws)["staging"] / f"{worker_id}-{token}"


def expected_worker_repo(ws: Path, state: dict[str, Any], worker_id: int) -> Path:
    return lexical_abs(final_worker_root(ws, worker_id) / state["repo_name"])


def canonical_marker_path(canonical: Path, workspace_id: str) -> Path:
    return git_common_dir(canonical) / "cws" / f"{workspace_id}.json"


def worker_marker_path(repo: Path) -> Path:
    # The per-repository Git directory: for a clone that is .git itself; for a
    # linked worktree it is the private .git/worktrees/<name> admin directory.
    return git_dir(repo) / "cws-worker.json"


def validate_control_dir(ws: Path, require_state: bool = False) -> None:
    paths = ws_paths(ws)
    ctl = paths["ctl"]
    try:
        mode = os.lstat(ctl).st_mode
    except FileNotFoundError:
        raise CWSError(f"workspace control directory is missing: {ctl}")
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise CWSError("workspace control directory is not a real directory")
    for key in ("workers", "requests", "locks", "staging"):
        p = paths[key]
        try:
            mode = os.lstat(p).st_mode
        except FileNotFoundError:
            raise CWSError(f"workspace control subdirectory is missing: {p.name}")
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise CWSError(f"workspace control subdirectory is unsafe: {p.name}")
    if paths["state"].exists() or require_state:
        try:
            mode = os.lstat(paths["state"]).st_mode
        except FileNotFoundError:
            raise CWSError("workspace state file is missing")
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise CWSError("workspace state file is unsafe")


@contextlib.contextmanager
def workspace_lock(ws: Path) -> Iterator[None]:
    validate_control_dir(ws)
    with file_lock(ws_paths(ws)["lock"]) as acquired:
        if not acquired:
            raise CWSError("could not acquire workspace lock")
        yield


# --- canonical ref names -----------------------------------------------------

def canonical_ref_prefix(state: dict[str, Any]) -> str:
    return f"refs/cws/{state['workspace_id']}"


def base_ref(state: dict[str, Any], worker_id: int) -> str:
    """Pins a worker's base commit against GC until the spawn is published."""
    return f"{canonical_ref_prefix(state)}/bases/{worker_id}"


def summary_ref(state: dict[str, Any], worker_id: int) -> str:
    """Mutable pointer to a worker's most recently collected result."""
    return f"{canonical_ref_prefix(state)}/workers/{worker_id}/result"


def immutable_result_ref(state: dict[str, Any], worker_id: int, sha: str) -> str:
    return f"{canonical_ref_prefix(state)}/workers/{worker_id}/results/{sha}"


# --- worker identity ---------------------------------------------------------

def sanitize_task(task: str) -> str:
    s = task.strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"[-_.]{2,}", "-", s).strip("-._")
    return (s or "task")[:48]


def worker_branch(state: dict[str, Any], worker_id: int, task: str) -> str:
    return f"agent/{state['workspace_id']}/{worker_id}-{sanitize_task(task)}"


def worker_mode(meta: dict[str, Any]) -> str:
    """Records written before worktree mode existed carry no ``mode`` and are clones."""
    return meta.get("mode", "clone")


def params_hash(base: str, task: str, strong: bool, mode: str = "clone") -> str:
    params: dict[str, Any] = {"base": base, "task": task, "strong": bool(strong)}
    if mode != "clone":
        params["mode"] = mode  # omitted for clones so pre-worktree records still verify
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_worker_meta(ws: Path, state: dict[str, Any], worker_id: int, meta: dict[str, Any]) -> None:
    """Validate durable metadata before it selects a path or a Git ref."""
    if meta.get("schema") != SCHEMA:
        raise CWSError("worker metadata schema mismatch")
    if type(meta.get("id")) is not int or meta["id"] != worker_id:
        raise CWSError("worker metadata ID does not match its filename")
    if meta.get("workspace_id") != state.get("workspace_id"):
        raise CWSError("worker metadata belongs to a different workspace")
    if meta.get("canonical_token") != state.get("canonical_token"):
        raise CWSError("worker metadata canonical identity mismatch")
    token = meta.get("worker_token")
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
        raise CWSError("worker metadata token is malformed")
    if meta.get("status") not in KNOWN_WORKER_STATUSES:
        raise CWSError(f"unknown worker status: {meta.get('status')!r}")
    if not isinstance(meta.get("task"), str) or not isinstance(meta.get("base"), str):
        raise CWSError("worker task/base metadata is malformed")
    if meta.get("branch") != worker_branch(state, worker_id, meta["task"]):
        raise CWSError("worker branch does not match deterministic assignment")
    mode = worker_mode(meta)
    if mode not in WORKER_MODES:
        raise CWSError(f"unknown worker mode: {mode!r}")
    if mode == "worktree" and meta.get("strong"):
        raise CWSError("worktree worker cannot be strong")
    if meta.get("params_hash") != params_hash(meta["base"], meta["task"], bool(meta.get("strong")), mode):
        raise CWSError("worker parameter digest mismatch")
    admin = meta.get("worktree_admin")
    if admin is not None:
        if mode != "worktree" or not isinstance(admin, str):
            raise CWSError("worktree admin path is malformed")
        admin_path = lexical_abs(admin)
        worktrees = lexical_abs(state["canonical_git_dir"]) / "worktrees"
        if admin_path.parent != worktrees or admin_path.name in {"", ".", ".."}:
            raise CWSError("worktree admin path is outside the canonical worktrees directory")
    if lexical_abs(meta.get("path", "")) != expected_worker_repo(ws, state, worker_id):
        raise CWSError("worker metadata path does not match its allocated slot")
    if lexical_abs(meta.get("stage_root", "")) != lexical_abs(staging_root(ws, worker_id, token)):
        raise CWSError("worker staging path does not match its allocation token")
    sha = meta.get("base_sha")
    expected_len = 64 if state.get("object_format") == "sha256" else 40
    if not isinstance(sha, str) or len(sha) != expected_len or not re.fullmatch(_HEX, sha):
        raise CWSError("worker base commit ID is malformed")


# --- process ownership -------------------------------------------------------

def pid_fingerprint(pid: int) -> str | None:
    # Linux exposes a stable process start tick, which defeats PID reuse.
    # Other platforms fall back to PID-only liveness.
    try:
        return Path(f"/proc/{pid}/stat").read_text().split()[21]
    except Exception:
        return None


def process_alive(pid: Any, fingerprint: Any = None) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM
    if fingerprint is not None:
        return pid_fingerprint(pid) == str(fingerprint)
    return True


def owner_fields() -> dict[str, Any]:
    """Fields marking this process as the live owner of an in-flight operation."""
    return {"owner_pid": os.getpid(), "owner_start": pid_fingerprint(os.getpid()), "heartbeat": time.time()}


def clear_owner(meta: dict[str, Any], *extra: str) -> None:
    for key in ("owner_pid", "owner_start", *extra):
        meta.pop(key, None)


# --- workspace state ---------------------------------------------------------

def validate_state(ws: Path, state: dict[str, Any], require_ready: bool = True) -> None:
    if state.get("schema") != SCHEMA:
        raise CWSError("unsupported workspace metadata schema")
    if require_ready and state.get("status") != "ready":
        raise CWSError(f"workspace is not ready: {state.get('status')}")
    if state.get("status") not in {"initializing", "ready"}:
        raise CWSError(f"unknown workspace state: {state.get('status')!r}")
    workspace_id = state.get("workspace_id")
    token = state.get("canonical_token")
    if not isinstance(workspace_id, str) or not re.fullmatch(r"[0-9a-f]{16}", workspace_id):
        raise CWSError("workspace ID is malformed")
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{48}", token):
        raise CWSError("canonical identity token is malformed")
    if lexical_abs(state.get("workspace", "")) != lexical_abs(ws):
        raise CWSError("workspace path identity changed")
    repo_name = state.get("repo_name")
    if (not isinstance(repo_name, str) or not repo_name or repo_name in {".", ".."}
            or Path(repo_name).is_absolute() or Path(repo_name).name != repo_name
            or "/" in repo_name or "\\" in repo_name):
        raise CWSError("repository name in workspace state is unsafe")
    if state.get("object_format") not in {"sha1", "sha256"}:
        raise CWSError("unsupported object format in workspace state")
    if type(state.get("next_id")) is not int or state["next_id"] < 1:
        raise CWSError("workspace next worker ID is malformed")
    canonical = state.get("canonical")
    canonical_git = state.get("canonical_git_dir")
    if not isinstance(canonical, str) or lexical_abs(canonical) != Path(canonical):
        raise CWSError("canonical path in workspace state is not normalized")
    if not isinstance(canonical_git, str) or lexical_abs(canonical_git) != Path(canonical_git):
        raise CWSError("canonical Git path in workspace state is not normalized")
    slot = state.get("canonical_slot")
    if slot is not None and (type(slot) is not int or slot < 1):
        raise CWSError("canonical slot metadata is malformed")


def read_state(ws: Path) -> dict[str, Any]:
    validate_control_dir(ws, require_state=True)
    state = load_json(ws_paths(ws)["state"])
    validate_state(ws, state, require_ready=True)
    return state


def write_state(ws: Path, state: dict[str, Any]) -> None:
    atomic_json(ws_paths(ws)["state"], state)


def verify_canonical(state: dict[str, Any]) -> Path:
    """Confirm the canonical repository is still the one this workspace was bound to."""
    canonical = validate_primary_repo(Path(state["canonical"]))
    if str(canonical) != str(Path(state["canonical"]).resolve()):
        raise CWSError("canonical root changed")
    if git_common_dir(canonical) != Path(state["canonical_git_dir"]).resolve():
        raise CWSError("canonical Git directory identity changed")
    if object_format(canonical) != state.get("object_format"):
        raise CWSError("canonical object format changed")
    marker = load_json(canonical_marker_path(canonical, state["workspace_id"]))
    if (marker.get("token") != state.get("canonical_token")
            or marker.get("workspace_id") != state.get("workspace_id")
            or lexical_abs(marker.get("canonical", "")) != lexical_abs(canonical)):
        raise CWSError("canonical repository identity marker mismatch")
    return canonical
