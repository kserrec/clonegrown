"""Process, Git, filesystem, and locking primitives shared by every layer.

Nothing in this module knows about workspaces or workers. It owns the error
type, generic public-operation safety context, the Git runner, atomic JSON
I/O, test failpoints, repository path discovery, and the advisory file lock.
"""
from __future__ import annotations

import contextlib
import contextvars
import errno
import fcntl
import functools
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, ParamSpec, TypeVar

# The on-disk protocol name. Workspace control dirs (.cws/), canonical refs
# (refs/cws/...), marker files (cws-worker.json), and the reserved remote name
# all carry it. It predates the product name and is kept on purpose: renaming
# it would break every existing workspace.
PROTOCOL_NAME = "cws"


def _find_git() -> Path:
    """Pick the Git binary. CLONEGROWN_GIT wins; otherwise /usr/bin/git if present, else PATH.

    Preferring the system binary over PATH is deliberate: an agent's shell
    can put a fake ``git`` first on PATH, and this tool runs Git with
    authority over the user's repositories. Homebrew or other non-system Git
    installs set CLONEGROWN_GIT explicitly.
    """
    override = os.environ.get("CLONEGROWN_GIT")
    if override:
        return Path(override)
    system = Path("/usr/bin/git")
    if system.exists():
        return system
    return Path(shutil.which("git") or "git")


GIT_BIN = _find_git()

# Environment variables that can retarget Git, inject config, or replace its helpers.
# User/system/global config files still apply; only per-process injection is stripped.
GIT_ENV_EXACT = {
    "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE",
    "GIT_PREFIX", "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_QUARANTINE_PATH", "GIT_SHALLOW_FILE", "GIT_EXEC_PATH", "GIT_TEMPLATE_DIR",
    "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_NOSYSTEM", "GIT_ATTR_NOSYSTEM", "GIT_ALLOW_PROTOCOL",
    "GIT_NO_REPLACE_OBJECTS", "GIT_REPLACE_REF_BASE",
    "GIT_PROTOCOL_FROM_USER", "GIT_PROTOCOL", "GIT_SSH", "GIT_SSH_COMMAND",
    "GIT_ASKPASS", "SSH_ASKPASS", "GIT_PROXY_COMMAND", "GIT_EXTERNAL_DIFF",
    "GIT_DIFF_OPTS", "GIT_OPTIONAL_LOCKS", "GIT_FLUSH", "GIT_CONFIG_COUNT",
}
GIT_ENV_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_", "GIT_TRACE")


class ClonegrownError(RuntimeError):
    """Any failure Clonegrown reports to its caller; the CLI prints it and exits 2."""


_P = ParamSpec("_P")
_R = TypeVar("_R")


@dataclass
class _OperationContext:
    """The last trustworthy safety statement for one public operation."""

    operation: str
    stage: str
    durable_state: str
    work_preservation: str
    recovery: str

    def checkpoint(self, *, stage: str, durable_state: str,
                   work_preservation: str, recovery: str) -> None:
        self.stage = stage
        self.durable_state = durable_state
        self.work_preservation = work_preservation
        self.recovery = recovery

    def failure(self, cause: Exception) -> ClonegrownError:
        cause_text = public_exception_text(cause)
        error = ClonegrownError(
            f"{self.operation} failed during {self.stage}. "
            f"Durable state: {self.durable_state}. "
            f"Work preservation: {self.work_preservation}. "
            f"Recovery: {self.recovery}. Cause: {cause_text}"
        )
        # Useful to an in-process developer without expanding the public error hierarchy.
        error.operation = self.operation  # type: ignore[attr-defined]
        error.stage = self.stage  # type: ignore[attr-defined]
        error.durable_state = self.durable_state  # type: ignore[attr-defined]
        error.work_preservation = self.work_preservation  # type: ignore[attr-defined]
        error.recovery = self.recovery  # type: ignore[attr-defined]
        return error


_CURRENT_OPERATION: contextvars.ContextVar[_OperationContext | None] = contextvars.ContextVar(
    "clonegrown_operation_context", default=None,
)


def operation_boundary(operation: str) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Translate ordinary failures at a public boundary with explicit safety context.

    The wrapped operation advances the context with ``operation_checkpoint``.
    Catching ``Exception`` deliberately excludes process-control exceptions
    such as ``KeyboardInterrupt``, ``SystemExit``, and ``GeneratorExit``.
    """
    def decorate(function: Callable[_P, _R]) -> Callable[_P, _R]:
        @functools.wraps(function)
        def wrapped(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            context = _OperationContext(
                operation=operation,
                stage="validation",
                durable_state=f"no durable mutation from this {operation} attempt is known to have completed",
                work_preservation="believed preserved — no write boundary has been entered",
                recovery=f"not required; correct the cause and retry {operation}",
            )
            token = _CURRENT_OPERATION.set(context)
            try:
                return function(*args, **kwargs)
            except Exception as exc:
                raise context.failure(exc) from exc
            finally:
                _CURRENT_OPERATION.reset(token)

        return wrapped

    return decorate


def operation_checkpoint(*, stage: str, durable_state: str,
                         work_preservation: str, recovery: str) -> None:
    """Replace the active public operation's safety statement, if there is one."""
    context = _CURRENT_OPERATION.get()
    if context is not None:
        context.checkpoint(
            stage=stage,
            durable_state=durable_state,
            work_preservation=work_preservation,
            recovery=recovery,
        )


# --- processes ---------------------------------------------------------------

_REDACTED = "<redacted>"
_URL_USERINFO = re.compile(r"(?P<scheme>\b[A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@")
_INTERNAL_CUSTODY_TOKEN = re.compile(
    r"(?P<prefix>(?:^|[/\\])\.cws[/\\](?:staging|quarantine)[/\\][0-9]+-)"
    r"[0-9a-f]{32}",
)


def _diagnostic_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "backslashreplace")
    return value


def _redact(text: str, sensitive: Iterable[str | Path]) -> str:
    """Remove caller-known values and URL userinfo from public diagnostics."""
    known = {str(value) for value in sensitive if str(value)}
    for value in sorted(known, key=len, reverse=True):
        if len(value) < 4:
            # A one-character config value must not turn every matching letter
            # in an unrelated command name or diagnostic into noise. Treat a
            # short value as sensitive only when it appears as its own token.
            text = re.sub(rf"(?<!\w){re.escape(value)}(?!\w)", _REDACTED, text)
        else:
            text = text.replace(value, _REDACTED)
    text = _INTERNAL_CUSTODY_TOKEN.sub(r"\g<prefix><redacted>", text)
    return _URL_USERINFO.sub(r"\g<scheme><redacted>@", text)


def _redact_argument(argument: str, sensitive: Iterable[str | Path]) -> str:
    """Redact a marked argv value exactly while preserving unrelated arguments."""
    known = {str(value) for value in sensitive if str(value)}
    if argument in known:
        return _REDACTED
    return _redact(argument, known)


def redact_public_text(text: str) -> str:
    """Remove Clonegrown-owned path tokens and URL userinfo from public text."""
    return _redact(text, ())


def public_exception_text(error: BaseException) -> str:
    """Render an exception without letting its renderer or internal path tokens escape."""
    try:
        text = str(error).strip() or type(error).__name__
    except Exception:
        text = f"{type(error).__name__} (message unavailable)"
    return redact_public_text(text)


def _git_operation(args: tuple[str | Path, ...]) -> str:
    """Name the Git subcommand without mistaking a global-option value for it."""
    takes_value = {"-c", "-C", "--exec-path", "--git-dir", "--namespace", "--work-tree"}
    skip = False
    for raw in args:
        arg = str(raw)
        if skip:
            skip = False
            continue
        if arg in takes_value:
            skip = True
            continue
        if arg.startswith(("--exec-path=", "--git-dir=", "--namespace=", "--work-tree=")):
            continue
        if not arg.startswith("-"):
            return f"git {arg}"
    return "git"


class CommandFailure(ClonegrownError):
    """A failed direct command with targeted public redaction and private diagnostics.

    ``str(error)`` and ``repr(error)`` contain only the redacted rendering used
    by the CLI and durable worker error fields. The underscore-prefixed values
    retain the original process diagnostics for an in-process developer who
    deliberately inspects them; Clonegrown never serializes those values.
    """

    def __init__(self, *, returncode: int | None, operation: str,
                 command: list[str], cwd: Path | None,
                 stdout: str | bytes | None, stderr: str | bytes | None,
                 sensitive: Iterable[str | Path] = (), timed_out: bool = False,
                 timeout: float | None = None, start_error: OSError | None = None) -> None:
        known = tuple(str(value) for value in sensitive if str(value))
        self.returncode = returncode
        self.operation = operation
        self.timed_out = timed_out
        self.timeout = timeout
        self.start_failed = start_error is not None
        self._private_command = tuple(command)
        self._private_cwd = cwd
        self._private_stdout = stdout
        self._private_stderr = stderr
        self._private_start_error = start_error

        public_args = [_redact_argument(arg, known) for arg in command]
        self.public_command = shlex.join(public_args)
        self.public_stdout = _redact(_diagnostic_text(stdout), known)
        self.public_stderr = _redact(_diagnostic_text(stderr), known)
        if timed_out:
            duration = f" after {timeout:g} seconds" if timeout is not None else ""
            first = f"{operation} timed out{duration}: {self.public_command}"
        elif start_error is not None:
            first = f"{operation} could not start: {self.public_command}"
        else:
            first = f"{operation} failed (exit {returncode}): {self.public_command}"
        lines = [first]
        if self.public_stdout:
            lines.append(f"stdout: {self.public_stdout.rstrip()}")
        if self.public_stderr:
            lines.append(f"stderr: {self.public_stderr.rstrip()}")
        super().__init__("\n".join(lines))


def clean_git_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key in GIT_ENV_EXACT or key.startswith(GIT_ENV_PREFIXES):
            env.pop(key, None)
    # Every Git runner uses this environment, including a custom executable.
    env["GIT_TERMINAL_PROMPT"] = "0"
    if extra:
        env.update(extra)
    return env


def run(cmd: list[str | Path], cwd: Path | None = None, check: bool = True,
        env: dict[str, str] | None = None, timeout: float | None = None,
        input: str | None = None, operation: str | None = None,
        sensitive: Iterable[str | Path] = (),
        pass_fds: Iterable[int] = ()) -> subprocess.CompletedProcess[str]:
    """Run a generic non-Git command with the caller's environment semantics."""
    argv = [str(x) for x in cmd]
    actual_env = env if env is not None else os.environ.copy()
    label = operation or (Path(argv[0]).name if argv else "command")
    try:
        # Paths in Git's output need not be UTF-8; surrogateescape keeps their bytes intact.
        p = subprocess.run(argv, cwd=cwd, text=True, errors="surrogateescape", stdout=subprocess.PIPE,
                           input=input, stderr=subprocess.PIPE, env=actual_env, timeout=timeout,
                           pass_fds=tuple(pass_fds))
    except subprocess.TimeoutExpired as exc:
        raise CommandFailure(
            returncode=None, operation=label, command=argv, cwd=cwd,
            stdout=exc.stdout, stderr=exc.stderr, sensitive=sensitive,
            timed_out=True, timeout=timeout,
        ) from exc
    except OSError as exc:
        raise CommandFailure(
            returncode=None, operation=label, command=argv, cwd=cwd,
            stdout=None, stderr=str(exc), sensitive=sensitive, start_error=exc,
        ) from exc
    if check and p.returncode:
        raise CommandFailure(
            returncode=p.returncode, operation=label, command=argv, cwd=cwd,
            stdout=p.stdout, stderr=p.stderr, sensitive=sensitive,
        )
    return p


def git(repo: Path, *args: str | Path, check: bool = True,
        timeout: float | None = None, input: str | None = None,
        sensitive: Iterable[str | Path] = (),
        pass_fds: Iterable[int] = ()) -> subprocess.CompletedProcess[str]:
    """Run the configured Git executable with a sanitized, noninteractive environment."""
    return run(
        [GIT_BIN, *args], cwd=repo, check=check, env=clean_git_env(), timeout=timeout,
        input=input, operation=_git_operation(args), sensitive=sensitive, pass_fds=pass_fds,
    )


def git_bytes(repo: Path, *args: str | Path, timeout: float | None = None,
              sensitive: Iterable[str | Path] = ()) -> bytes:
    """Run Git and return its raw stdout, for NUL-delimited listings whose paths need not be UTF-8."""
    argv = [str(GIT_BIN), *(str(a) for a in args)]
    try:
        p = subprocess.run(argv, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           env=clean_git_env(), timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise CommandFailure(
            returncode=None, operation=_git_operation(args), command=argv, cwd=repo,
            stdout=exc.stdout, stderr=exc.stderr, sensitive=sensitive,
            timed_out=True, timeout=timeout,
        ) from exc
    except OSError as exc:
        raise CommandFailure(
            returncode=None, operation=_git_operation(args), command=argv, cwd=repo,
            stdout=None, stderr=str(exc), sensitive=sensitive, start_error=exc,
        ) from exc
    if p.returncode:
        raise CommandFailure(
            returncode=p.returncode, operation=_git_operation(args), command=argv, cwd=repo,
            stdout=p.stdout, stderr=p.stderr, sensitive=sensitive,
        )
    return p.stdout


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


def atomic_json_create(path: Path, data: Any) -> None:
    """Write JSON to a path that must not exist yet; an existing file is never replaced.

    The content is written and fsynced to a temporary file, then linked to
    its final name with ``os.link``, which fails atomically if the name is
    taken. The directory is fsynced afterwards.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    except OSError as exc:
        raise ClonegrownError(f"cannot create record {path}: {exc}") from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp, path)
        except FileExistsError as exc:
            raise ClonegrownError(f"record already exists and is never replaced: {path}") from exc
        dfd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except OSError as exc:
        raise ClonegrownError(f"cannot create record {path}: {exc}") from exc
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)


def load_json(path: Path) -> dict[str, Any]:
    try:
        mode = os.lstat(path).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise ClonegrownError(f"metadata is not a regular non-symlink file: {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ClonegrownError(f"cannot read metadata {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ClonegrownError(f"metadata is not an object: {path}")
    return value


def failpoint(name: str) -> None:
    """Test-only hook: pause, hard-exit, or raise at an exact lifecycle transition.

    Controlled by ``CLONEGROWN_TEST_*`` variables only when the explicit test
    mode gate is exactly ``1``. Production execution ignores every hook value.
    """
    if os.environ.get("CLONEGROWN_TEST_MODE") != "1":
        return
    if os.environ.get("CLONEGROWN_TEST_PAUSEPOINT") == name:
        marker = os.environ.get("CLONEGROWN_TEST_PAUSE_MARKER")
        if marker:
            Path(marker).write_text(name, encoding="utf-8")
        time.sleep(float(os.environ.get("CLONEGROWN_TEST_PAUSE_SECONDS", "1")))
    if os.environ.get("CLONEGROWN_TEST_FAILPOINT") == name:
        os._exit(88)
    if os.environ.get("CLONEGROWN_TEST_ERRORPOINT") == name:
        raise ClonegrownError(f"injected ordinary failure at {name}")


# --- repository paths --------------------------------------------------------

def _rev_parse_path(repo: Path, flag: str, *args: str) -> Path:
    out = git(repo, "rev-parse", flag, *args).stdout.strip()
    p = Path(out)
    return p.resolve() if p.is_absolute() else (repo / p).resolve()


def repo_root(path: Path) -> Path:
    p = git(path, "rev-parse", "--show-toplevel", check=False)
    if p.returncode:
        raise ClonegrownError(f"not a non-bare Git working tree: {path}")
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
        raise ClonegrownError("bare repositories are not supported as canonical working copies")
    if git_dir(root) != git_common_dir(root):
        raise ClonegrownError("canonical path is a linked worktree; use the primary checkout")
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


# --- process ownership -------------------------------------------------------

def pid_fingerprint(pid: int) -> str | None:
    """A value that changes if ``pid`` is reused by a new process (Linux start tick).

    Other platforms return None and fall back to PID-only liveness.
    """
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


# --- locking -----------------------------------------------------------------

@contextlib.contextmanager
def file_lock(path: Path, blocking: bool = True) -> Iterator[bool]:
    """Hold an exclusive ``flock`` on ``path``; yields whether it was acquired."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flags_open = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags_open, 0o600)
    except OSError as exc:
        raise ClonegrownError(f"cannot safely open lock file {path}: {exc}") from exc
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise ClonegrownError(f"lock path is not a regular file: {path}")
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
