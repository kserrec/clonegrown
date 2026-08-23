"""Process, Git, filesystem, and locking primitives shared by every layer.

Nothing in this module knows about workspaces or workers. It owns the error
type, the hardened Git runner, atomic JSON I/O, test failpoints, repository
path discovery, and the advisory file lock.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterator

GIT_BIN = Path("/usr/bin/git") if Path("/usr/bin/git").exists() else Path(shutil.which("git") or "git")

# Environment variables that can retarget Git, inject config, or replace its helpers.
# User/system/global config files still apply; only per-process injection is stripped.
GIT_ENV_EXACT = {
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
    "GIT_PREFIX", "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_QUARANTINE_PATH", "GIT_SHALLOW_FILE", "GIT_EXEC_PATH", "GIT_TEMPLATE_DIR",
    "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_NOSYSTEM", "GIT_ATTR_NOSYSTEM", "GIT_ALLOW_PROTOCOL",
    "GIT_PROTOCOL_FROM_USER", "GIT_PROTOCOL", "GIT_SSH", "GIT_SSH_COMMAND",
    "GIT_ASKPASS", "SSH_ASKPASS", "GIT_PROXY_COMMAND", "GIT_EXTERNAL_DIFF",
    "GIT_DIFF_OPTS", "GIT_OPTIONAL_LOCKS", "GIT_FLUSH", "GIT_CONFIG_COUNT",
}
GIT_ENV_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "GIT_TRACE")


class CWSError(RuntimeError):
    """Any failure Clonegrown reports to its caller; the CLIs print it and exit 2."""


# --- processes ---------------------------------------------------------------

def clean_git_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key in GIT_ENV_EXACT or key.startswith(GIT_ENV_PREFIXES):
            env.pop(key, None)
    # Helper operations are local and must never prompt an unattended agent.
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
        # Git stderr is kept for diagnosis; config values and the environment are not dumped.
        raise CWSError(f"command failed ({p.returncode}): {' '.join(argv)}\nstdout: {p.stdout}\nstderr: {p.stderr}")
    return p


def git(repo: Path, *args: str | Path, check: bool = True,
        timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return run([GIT_BIN, *args], cwd=repo, check=check, timeout=timeout)


# --- durable JSON ------------------------------------------------------------

def atomic_json(path: Path, data: Any) -> None:
    """Write JSON via a fsynced temp file and rename, then fsync the directory."""
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
    """Test-only hook: pause, hard-exit, or raise at an exact lifecycle transition.

    Controlled by CWS_PAUSEPOINT / CWS_FAILPOINT / CWS_ERRORPOINT. A no-op in
    ordinary use.
    """
    if os.environ.get("CWS_PAUSEPOINT") == name:
        marker = os.environ.get("CWS_PAUSE_MARKER")
        if marker:
            Path(marker).write_text(name, encoding="utf-8")
        time.sleep(float(os.environ.get("CWS_PAUSE_SECONDS", "1")))
    if os.environ.get("CWS_FAILPOINT") == name:
        os._exit(88)
    if os.environ.get("CWS_ERRORPOINT") == name:
        raise CWSError(f"injected ordinary failure at {name}")


# --- repository paths --------------------------------------------------------

def _rev_parse_path(repo: Path, flag: str, *args: str) -> Path:
    out = git(repo, "rev-parse", flag, *args).stdout.strip()
    p = Path(out)
    return p.resolve() if p.is_absolute() else (repo / p).resolve()


def repo_root(path: Path) -> Path:
    p = git(path, "rev-parse", "--show-toplevel", check=False)
    if p.returncode:
        raise CWSError(f"not a non-bare Git working tree: {path}")
    return Path(p.stdout.strip()).resolve()


def git_dir(path: Path) -> Path:
    return _rev_parse_path(path, "--git-dir")


def git_common_dir(path: Path) -> Path:
    return _rev_parse_path(path, "--git-common-dir")


def git_path(repo: Path, rel: str) -> Path:
    """Location of a file inside the repository's Git directory (e.g. ``info/exclude``)."""
    out = git(repo, "rev-parse", "--git-path", rel).stdout.strip()
    p = Path(out)
    return p if p.is_absolute() else (repo / p).resolve()


def object_format(path: Path) -> str:
    p = git(path, "rev-parse", "--show-object-format", check=False)
    return p.stdout.strip() if p.returncode == 0 and p.stdout.strip() else "sha1"


def validate_primary_repo(path: Path) -> Path:
    """Resolve ``path`` to the root of a non-bare, non-linked-worktree checkout."""
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


def lexical_abs(path: str | Path) -> Path:
    """Normalize a path without following symlinks.

    Metadata paths are protocol values, not discovery hints. Resolving a
    symlink here would let a substituted path compare equal to its victim.
    """
    return Path(os.path.abspath(os.path.normpath(os.fspath(path))))


# --- locking -----------------------------------------------------------------

@contextlib.contextmanager
def file_lock(path: Path, blocking: bool = True) -> Iterator[bool]:
    """Hold an exclusive ``flock`` on ``path``; yields whether it was acquired."""
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
