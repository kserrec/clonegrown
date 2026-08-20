#!/usr/bin/env python3
"""Clonegrown: transactional independent-clone workspaces for coding agents.

This is an adversarial reference implementation, not a production release.
It exists to test whether isolated local clones can be made safe and usable
for coding agents without relying on a remote hub.
"""
from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

SCHEMA = 3
RESERVED_SOURCE_PREFIX = "cws-source"
ACTIVE_SPAWN = {"allocated", "cloning", "configuring", "publishing"}
ACTIVE_COLLECT = {"collecting"}
ACTIVE_DISCARD = {"discarding"}
TERMINAL_SPAWN_FAILURE = {"spawn_failed", "abandoned"}
KNOWN_WORKER_STATUSES = {
    "allocated", "cloning", "configuring", "publishing", "ready",
    "collecting", "collected", "discarding", "discarded", "abandoned",
    "spawn_failed", "broken",
}
GIT_BIN = Path("/usr/bin/git") if Path("/usr/bin/git").exists() else Path(shutil.which("git") or "git")

# Variables capable of retargeting Git, injecting config, or replacing Git's helpers.
# User/system/global config files still apply normally; only per-process injection is stripped.
GIT_ENV_EXACT = {
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
    "GIT_PREFIX", "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_QUARANTINE_PATH", "GIT_SHALLOW_FILE", "GIT_EXEC_PATH", "GIT_TEMPLATE_DIR",
    "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_NOSYSTEM", "GIT_ATTR_NOSYSTEM", "GIT_ALLOW_PROTOCOL",
    "GIT_PROTOCOL_FROM_USER", "GIT_PROTOCOL", "GIT_SSH", "GIT_SSH_COMMAND",
    "GIT_ASKPASS", "SSH_ASKPASS", "GIT_PROXY_COMMAND", "GIT_EXTERNAL_DIFF",
    "GIT_DIFF_OPTS", "GIT_OPTIONAL_LOCKS", "GIT_FLUSH",
}
GIT_ENV_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "GIT_TRACE")

STRUCTURAL_CONFIG_EXACT = {
    "core.repositoryformatversion", "core.filemode", "core.bare", "core.logallrefupdates",
    "core.worktree", "core.ignorecase", "core.precomposeunicode", "core.symlinks",
    "core.sparsecheckout", "core.sparsecheckoutcone", "index.sparse",
}
STRUCTURAL_CONFIG_PREFIXES = ("remote.", "branch.", "extensions.", "include.", "includeif.")
OPERATION_GIT_PATHS = (
    "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG",
    "rebase-apply", "rebase-merge", "sequencer",
)


class CWSError(RuntimeError):
    pass


def clean_git_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key in GIT_ENV_EXACT or key == "GIT_CONFIG_COUNT" or key.startswith(GIT_ENV_PREFIXES):
            env.pop(key, None)
    # Helper operations are local and must never unexpectedly prompt an unattended agent.
    env["GIT_TERMINAL_PROMPT"] = "0"
    if extra:
        env.update(extra)
    return env


def run(cmd: list[str | Path], cwd: Path | None = None, check: bool = True,
        env: dict[str, str] | None = None, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    argv = [str(x) for x in cmd]
    actual_env = clean_git_env(env) if argv and Path(argv[0]).name == "git" else (env or os.environ.copy())
    try:
        p = subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, env=actual_env, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise CWSError(f"command timed out: {argv[0]} {argv[1] if len(argv) > 1 else ''}") from exc
    if check and p.returncode:
        # Avoid dumping config values or full environment. Git stderr is retained for diagnosis.
        raise CWSError(f"command failed ({p.returncode}): {' '.join(argv)}\nstdout: {p.stdout}\nstderr: {p.stderr}")
    return p


def git(repo: Path, *args: str | Path, check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return run([GIT_BIN, *args], cwd=repo, check=check, timeout=timeout)


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)


def load_json(path: Path) -> dict[str, Any]:
    try:
        mode = os.lstat(path).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise CWSError(f"metadata is not a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CWSError(f"cannot read metadata {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CWSError(f"metadata is not an object: {path}")
    return value


def failpoint(name: str) -> None:
    # Deterministic test-only pause lets the harness mutate state at an exact transition.
    if os.environ.get("CWS_PAUSEPOINT") == name:
        marker = os.environ.get("CWS_PAUSE_MARKER")
        if marker:
            Path(marker).write_text(name, encoding="utf-8")
        time.sleep(float(os.environ.get("CWS_PAUSE_SECONDS", "1")))
    if os.environ.get("CWS_FAILPOINT") == name:
        os._exit(88)
    if os.environ.get("CWS_ERRORPOINT") == name:
        raise CWSError(f"injected ordinary failure at {name}")


def repo_root(path: Path) -> Path:
    p = git(path, "rev-parse", "--show-toplevel", check=False)
    if p.returncode:
        raise CWSError(f"not a non-bare Git working tree: {path}")
    return Path(p.stdout.strip()).resolve()


def git_dir(path: Path) -> Path:
    out = git(path, "rev-parse", "--git-dir").stdout.strip()
    p = Path(out)
    return p.resolve() if p.is_absolute() else (path / p).resolve()


def git_common_dir(path: Path) -> Path:
    out = git(path, "rev-parse", "--git-common-dir").stdout.strip()
    p = Path(out)
    return p.resolve() if p.is_absolute() else (path / p).resolve()


def object_format(path: Path) -> str:
    p = git(path, "rev-parse", "--show-object-format", check=False)
    return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else "sha1"


def validate_primary_repo(path: Path) -> Path:
    root = repo_root(path)
    if git(root, "rev-parse", "--is-bare-repository").stdout.strip() == "true":
        raise CWSError("bare repositories are not supported as canonical working copies")
    if git_dir(root) != git_common_dir(root):
        raise CWSError("canonical path is a linked worktree; use the primary checkout")
    return root


def inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


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
def file_lock(path: Path, blocking: bool = True) -> Iterator[bool]:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags_open = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags_open, 0o600)
    except OSError as exc:
        raise CWSError(f"cannot safely open lock file {path}: {exc}") from exc
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise CWSError(f"lock path is not a regular file: {path}")
    f = os.fdopen(fd, "a+")
    flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
    acquired = False
    try:
        try:
            fcntl.flock(f.fileno(), flags)
            acquired = True
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        if acquired:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


@contextlib.contextmanager
def workspace_lock(ws: Path) -> Iterator[None]:
    validate_control_dir(ws)
    with file_lock(ws_paths(ws)["lock"]) as acquired:
        if not acquired:
            raise CWSError("could not acquire workspace lock")
        yield


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


def lexical_abs(path: str | Path) -> Path:
    """Normalize a path without following symlinks.

    Metadata paths are protocol values, not discovery hints.  Resolving a
    symlink here would let a substituted path compare equal to its victim.
    """
    return Path(os.path.abspath(os.path.normpath(os.fspath(path))))


def expected_worker_repo(ws: Path, state: dict[str, Any], worker_id: int) -> Path:
    return lexical_abs(final_worker_root(ws, worker_id) / state["repo_name"])



def sanitize_task(task: str) -> str:
    s = task.strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"[-_.]{2,}", "-", s).strip("-._")
    return (s or "task")[:48]


def params_hash(base: str, task: str, strong: bool) -> str:
    raw = json.dumps({"base": base, "task": task, "strong": bool(strong)}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def validate_worker_meta(ws: Path, state: dict[str, Any], worker_id: int,
                         meta: dict[str, Any]) -> None:
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
    expected_branch = f"agent/{state['workspace_id']}/{worker_id}-{sanitize_task(meta['task'])}"
    if meta.get("branch") != expected_branch:
        raise CWSError("worker branch does not match deterministic assignment")
    if meta.get("params_hash") != params_hash(meta["base"], meta["task"], bool(meta.get("strong"))):
        raise CWSError("worker parameter digest mismatch")
    expected_repo = expected_worker_repo(ws, state, worker_id)
    if lexical_abs(meta.get("path", "")) != expected_repo:
        raise CWSError("worker metadata path does not match its allocated slot")
    expected_stage = lexical_abs(staging_root(ws, worker_id, token))
    if lexical_abs(meta.get("stage_root", "")) != expected_stage:
        raise CWSError("worker staging path does not match its allocation token")
    sha = meta.get("base_sha")
    expected_len = 64 if state.get("object_format") == "sha256" else 40
    if not isinstance(sha, str) or len(sha) != expected_len or not re.fullmatch(r"[0-9a-f]+", sha):
        raise CWSError("worker base commit ID is malformed")


def canonical_marker_path(canonical: Path, workspace_id: str) -> Path:
    return git_common_dir(canonical) / "cws" / f"{workspace_id}.json"


def worker_marker_path(repo: Path) -> Path:
    return git_common_dir(repo) / "cws-worker.json"


def pid_fingerprint(pid: int) -> str | None:
    # Linux gives a stable process start-tick to protect against PID reuse. Other platforms get PID-only semantics.
    p = Path(f"/proc/{pid}/stat")
    try:
        fields = p.read_text().split()
        return fields[21]
    except Exception:
        return None
