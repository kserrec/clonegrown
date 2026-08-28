#!/bin/sh
set -eu

umask 022

REPO_URL="${CLONEGROWN_REPO_URL:-https://github.com/kserrec/clonegrown.git}"
REF="${CLONEGROWN_REF:-main}"
INSTALL_HOME="${HOME:-}"
[ -n "$INSTALL_HOME" ] || {
  printf '%s\n' "clonegrown installer: HOME is required" >&2
  exit 1
}
INSTALL_ROOT_INPUT="${CLONEGROWN_HOME:-$INSTALL_HOME/.local/share/clonegrown}"
BIN_DIR_INPUT="${CLONEGROWN_BIN_DIR:-$INSTALL_HOME/.local/bin}"

MARKER_NAME=".clonegrown-install"
MARKER_FORMAT="clonegrown-installer=v1"
BACKUP_RESERVATION_NAME=".clonegrown-backup-reservation"

say() {
  printf '%s\n' "$*"
}

warn() {
  printf 'clonegrown installer: %s\n' "$*" >&2
}

fail() {
  warn "$*"
  exit 1
}

posix_shell_literal() {
  python3 - "$1" <<'PY'
import os
import sys

# Paths may contain non-UTF-8 bytes. Write the original filesystem bytes back
# out; a text-mode print would refuse them under a UTF-8 locale.
value = sys.argv[1]
sys.stdout.buffer.write(os.fsencode("'" + value.replace("'", "'\"'\"'") + "'"))
PY
}

path_exists() {
  [ -e "$1" ] || [ -L "$1" ]
}

command -v git >/dev/null 2>&1 || fail "git is required"
command -v python3 >/dev/null 2>&1 || fail "Python 3.11+ is required"

python3 - <<'PY' || fail "Python 3.11+ is required"
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY

path_identity() {
  python3 - "$1" <<'PY'
import os
import stat
import sys

try:
    value = os.lstat(sys.argv[1])
except OSError:
    raise SystemExit(1)
print(f"{value.st_dev}:{value.st_ino}:{stat.S_IFMT(value.st_mode)}")
PY
}

control_tmp="$(mktemp -d 2>/dev/null || mktemp -d -t clonegrown)"
control_tmp_identity="$(path_identity "$control_tmp")" || fail "could not identify installer control directory"

# Every path below is either empty, created by this invocation, or authenticated
# by the preflight. Initialize them before installing the EXIT trap because the
# script runs with nounset enabled.
INSTALL_ROOT=""
BIN_DIR=""
BIN_DIR_SHELL_LITERAL=""
WRAPPER=""
WRAPPER_SHELL_LITERAL=""
CLAUDE_SKILL=""
CODEX_SKILL=""
installation_id=""
source_stage=""
wrapper_stage=""
claude_stage=""
codex_stage=""
source_stage_identity=""
wrapper_stage_identity=""
claude_stage_identity=""
codex_stage_identity=""
source_backup=""
wrapper_backup=""
claude_backup=""
codex_backup=""
source_backup_identity=""
wrapper_backup_identity=""
claude_backup_identity=""
codex_backup_identity=""
source_had_old=0
wrapper_had_old=0
claude_had_old=0
codex_had_old=0
source_published=0
wrapper_published=0
claude_published=0
codex_published=0
transaction_started=0
committed=0

owned_directory() {
  _owned_dir="$1"
  _owned_kind="$2"
  _owned_id="$3"
  [ -d "$_owned_dir" ] || return 1
  [ ! -L "$_owned_dir" ] || return 1
  _owned_marker="$_owned_dir/$MARKER_NAME"
  [ -f "$_owned_marker" ] || return 1
  [ ! -L "$_owned_marker" ] || return 1
  [ "$(sed -n '1p' "$_owned_marker")" = "$MARKER_FORMAT" ] || return 1
  [ "$(sed -n '2p' "$_owned_marker")" = "installation_id=$_owned_id" ] || return 1
  [ "$(sed -n '3p' "$_owned_marker")" = "target=$_owned_kind" ] || return 1
}

owned_wrapper() {
  _owned_wrapper="$1"
  _owned_id="$2"
  [ -f "$_owned_wrapper" ] || return 1
  [ ! -L "$_owned_wrapper" ] || return 1
  [ "$(sed -n '1p' "$_owned_wrapper")" = "#!/bin/sh" ] || return 1
  [ "$(sed -n '2p' "$_owned_wrapper")" = "# $MARKER_FORMAT" ] || return 1
  [ "$(sed -n '3p' "$_owned_wrapper")" = "# installation_id=$_owned_id" ] || return 1
  [ "$(sed -n '4p' "$_owned_wrapper")" = "# target=command" ] || return 1
}

fsync_paths() {
  python3 - "$@" <<'PY'
import errno
import os
import sys

unsupported = {errno.EINVAL, errno.EROFS}
for name in ("ENOTSUP", "EOPNOTSUPP"):
    value = getattr(errno, name, None)
    if value is not None:
        unsupported.add(value)

for raw in sys.argv[1:]:
    try:
        descriptor = os.open(raw, os.O_RDONLY)
    except OSError as exc:
        if exc.errno in unsupported:
            continue
        raise
    try:
        try:
            os.fsync(descriptor)
        except OSError as exc:
            if exc.errno not in unsupported:
                raise
    finally:
        os.close(descriptor)
PY
}

rollback_path() {
  _rollback_target="$1"
  _rollback_backup="$2"
  _rollback_path_kind="$3"
  _rollback_label="$4"
  _rollback_published="$5"
  _rollback_published_identity="$6"
  _rollback_had_old="$7"
  _rollback_backup_identity="$8"
  _rollback_owner_kind="$9"
  _rollback_parent="$(dirname "$_rollback_target")"

  if [ "$_rollback_published" -eq 1 ] && path_exists "$_rollback_target"; then
    cleanup_created_path \
      "$_rollback_target" \
      "$_rollback_published_identity" \
      "$_rollback_path_kind" \
      "newly published $_rollback_label target" \
      "$_rollback_owner_kind" \
      "$installation_id"
    fsync_paths "$_rollback_parent" >/dev/null 2>&1 || true
  fi

  if [ "$_rollback_had_old" -eq 1 ] && path_exists "$_rollback_backup"; then
    if path_has_identity "$_rollback_target" "$_rollback_backup_identity"; then
      # The relocation to the backup was refused, so the previous target never
      # moved. Whatever occupies the reserved backup name is not ours.
      warn "previous $_rollback_label target is still in place; the object at its reserved backup name was preserved: $_rollback_backup"
    elif path_exists "$_rollback_target"; then
      warn "previous $_rollback_label target remains in backup because its destination is occupied: $_rollback_backup"
    elif relocate_created_path \
      "$_rollback_backup" \
      "$_rollback_backup_identity" \
      "$_rollback_target" \
      "" \
      "" \
      "$_rollback_path_kind" \
      "$_rollback_owner_kind" \
      "$installation_id"
    then
      fsync_paths "$_rollback_parent" >/dev/null 2>&1 || true
    else
      warn "could not restore previous $_rollback_label target; the object at its backup name was preserved: $_rollback_backup"
    fi
  fi
}

path_has_identity() {
  _has_identity_current="$(path_identity "$1" 2>/dev/null)" || return 1
  [ "$_has_identity_current" = "$2" ]
}

created_directory_has_identity() {
  _created_directory="$1"
  _created_identity="$2"
  [ -n "$_created_directory" ] || return 1
  [ -n "$_created_identity" ] || return 1
  [ -d "$_created_directory" ] || return 1
  [ ! -L "$_created_directory" ] || return 1
  _created_current_identity="$(path_identity "$_created_directory")" || return 1
  [ "$_created_current_identity" = "$_created_identity" ]
}

created_file_has_identity() {
  _created_file="$1"
  _created_identity="$2"
  [ -n "$_created_file" ] || return 1
  [ -n "$_created_identity" ] || return 1
  [ -f "$_created_file" ] || return 1
  [ ! -L "$_created_file" ] || return 1
  _created_current_identity="$(path_identity "$_created_file")" || return 1
  [ "$_created_current_identity" = "$_created_identity" ]
}


cleanup_created_path() {
  _cleanup_path="$1"
  _cleanup_identity="$2"
  _cleanup_kind="$3"
  _cleanup_label="$4"
  _cleanup_owner_kind="${5:-}"
  _cleanup_owner_id="${6:-}"
  [ -n "$_cleanup_path" ] || return 0

  # Keep the identity decision, the ownership decision, and deletion inside one
  # process. In particular, do not return a validated pathname to a separately
  # resolved rm command.
  if python3 - "$_cleanup_path" "$_cleanup_identity" "$_cleanup_kind" \
    "$_cleanup_owner_kind" "$_cleanup_owner_id" <<'PY'
import os
import shutil
import stat
import sys

path, expected_identity, kind, owner_kind, owner_id = sys.argv[1:]
def owned(path: str, owner_kind: str, owner_id: str) -> bool:
    """Ownership evidence for an object this invocation authenticated earlier.

    Device, inode, and type alone do not prove the object is still the one
    that was authenticated: the same user can delete it and the filesystem
    can hand its inode number to whatever is created next. An owned object
    also has to carry the Clonegrown marker (or wrapper header) for this
    installation. An empty owner kind means no evidence is expected, which is
    only right for a private object this invocation created and never
    published: a stage, or the control directory.

    Evidence is read the way the preflight reads it: lines split on newline
    only, with one optional trailing newline. The marker must be exactly its
    three lines; the wrapper header is its first four lines.
    """
    if not owner_kind:
        return True
    if owner_kind == "command":
        evidence = path
        expected = [
            b"#!/bin/sh",
            b"# clonegrown-installer=v1",
            b"# installation_id=" + owner_id.encode("ascii"),
            b"# target=command",
        ]
    else:
        evidence = os.path.join(path, ".clonegrown-install")
        expected = [
            b"clonegrown-installer=v1",
            b"installation_id=" + owner_id.encode("ascii"),
            b"target=" + owner_kind.encode("ascii"),
        ]
    try:
        # Never open anything but a regular file: opening a FIFO would block
        # until a writer appears. O_NONBLOCK covers a swap after the lstat.
        if not stat.S_ISREG(os.lstat(evidence).st_mode):
            return False
        descriptor = os.open(evidence, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return False
        data = os.read(descriptor, 4097)
    except OSError:
        return False
    finally:
        os.close(descriptor)
    lines = data.split(b"\n")
    if owner_kind == "command":
        return lines[:4] == expected
    if lines and lines[-1] == b"":
        lines.pop()
    return lines == expected


try:
    value = os.lstat(path)
except FileNotFoundError:
    raise SystemExit(0)
except OSError:
    raise SystemExit(4)

current_identity = f"{value.st_dev}:{value.st_ino}:{stat.S_IFMT(value.st_mode)}"
expected_mode = stat.S_IFDIR if kind == "directory" else stat.S_IFREG
if current_identity != expected_identity or stat.S_IFMT(value.st_mode) != expected_mode:
    raise SystemExit(3)
if not owned(path, owner_kind, owner_id):
    raise SystemExit(3)

try:
    if kind == "directory":
        if not shutil.rmtree.avoids_symlink_attacks:
            raise SystemExit(4)
        shutil.rmtree(path)
    else:
        os.unlink(path)
except FileNotFoundError:
    pass
except OSError:
    raise SystemExit(4)
PY
  then
    return 0
  else
    _cleanup_status=$?
  fi

  case "$_cleanup_status" in
    3)
      warn "preserved unexpected object at $_cleanup_label path: $_cleanup_path"
      ;;
    *)
      warn "could not safely remove invocation-created $_cleanup_label: $_cleanup_path"
      ;;
  esac
}

cleanup_created_directory() {
  cleanup_created_path "$1" "$2" "directory" "$3" "${4:-}" "${5:-}"
}

cleanup_created_file() {
  cleanup_created_path "$1" "$2" "file" "$3" "${4:-}" "${5:-}"
}

relocate_created_path() {
  _relocate_source="$1"
  _relocate_source_identity="$2"
  _relocate_destination="$3"
  _relocate_destination_identity="$4"
  _relocate_destination_token="$5"
  _relocate_kind="$6"
  _relocate_owner_kind="${7:-}"
  _relocate_owner_id="${8:-}"

  # Keep source/destination validation and rename inside one process. An empty
  # destination identity means the destination must still be absent. A nonempty
  # identity names the file or directory reserved for a backup. A nonempty
  # owner kind requires the moved object to carry this installation's marker.
  python3 - \
    "$_relocate_source" \
    "$_relocate_source_identity" \
    "$_relocate_destination" \
    "$_relocate_destination_identity" \
    "$_relocate_destination_token" \
    "$_relocate_kind" \
    "$_relocate_owner_kind" \
    "$_relocate_owner_id" <<'PY'
import os
import stat
import sys

(source, expected_source, destination, expected_destination, destination_token, kind,
 owner_kind, owner_id) = sys.argv[1:]
expected_mode = stat.S_IFDIR if kind == "directory" else stat.S_IFREG
reservation_name = ".clonegrown-backup-reservation"


def identity(value: os.stat_result) -> str:
    return f"{value.st_dev}:{value.st_ino}:{stat.S_IFMT(value.st_mode)}"


def owned(path: str, owner_kind: str, owner_id: str) -> bool:
    """Ownership evidence for an object this invocation authenticated earlier.

    Device, inode, and type alone do not prove the object is still the one
    that was authenticated: the same user can delete it and the filesystem
    can hand its inode number to whatever is created next. An owned object
    also has to carry the Clonegrown marker (or wrapper header) for this
    installation. An empty owner kind means no evidence is expected, which is
    only right for a private object this invocation created and never
    published: a stage, or the control directory.

    Evidence is read the way the preflight reads it: lines split on newline
    only, with one optional trailing newline. The marker must be exactly its
    three lines; the wrapper header is its first four lines.
    """
    if not owner_kind:
        return True
    if owner_kind == "command":
        evidence = path
        expected = [
            b"#!/bin/sh",
            b"# clonegrown-installer=v1",
            b"# installation_id=" + owner_id.encode("ascii"),
            b"# target=command",
        ]
    else:
        evidence = os.path.join(path, ".clonegrown-install")
        expected = [
            b"clonegrown-installer=v1",
            b"installation_id=" + owner_id.encode("ascii"),
            b"target=" + owner_kind.encode("ascii"),
        ]
    try:
        # Never open anything but a regular file: opening a FIFO would block
        # until a writer appears. O_NONBLOCK covers a swap after the lstat.
        if not stat.S_ISREG(os.lstat(evidence).st_mode):
            return False
        descriptor = os.open(evidence, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return False
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return False
        data = os.read(descriptor, 4097)
    except OSError:
        return False
    finally:
        os.close(descriptor)
    lines = data.split(b"\n")
    if owner_kind == "command":
        return lines[:4] == expected
    if lines and lines[-1] == b"":
        lines.pop()
    return lines == expected


def checked(path: str, expected: str) -> os.stat_result:
    value = os.lstat(path)
    if stat.S_IFMT(value.st_mode) != expected_mode or identity(value) != expected:
        raise RuntimeError(f"filesystem identity changed: {path}")
    if not owned(path, owner_kind, owner_id):
        raise RuntimeError(f"ownership evidence changed: {path}")
    return value


def checked_reservation() -> None:
    value = os.lstat(destination)
    if stat.S_IFMT(value.st_mode) != expected_mode or identity(value) != expected_destination:
        raise RuntimeError(f"filesystem identity changed: {destination}")
    reservation = os.path.join(destination, reservation_name) if kind == "directory" else destination
    if not stat.S_ISREG(os.lstat(reservation).st_mode):
        raise RuntimeError(f"backup reservation changed: {destination}")
    descriptor = os.open(reservation, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise RuntimeError(f"backup reservation changed: {destination}")
        content = os.read(descriptor, 4097)
    finally:
        os.close(descriptor)
    if content != (destination_token + "\n").encode("ascii"):
        raise RuntimeError(f"backup reservation changed: {destination}")


def remove_unchanged_reservation() -> None:
    if not expected_destination:
        return
    try:
        checked_reservation()
        if kind == "directory":
            os.unlink(os.path.join(destination, reservation_name))
            os.rmdir(destination)
        else:
            os.unlink(destination)
    except (OSError, RuntimeError):
        pass


try:
    checked(source, expected_source)
    if expected_destination:
        checked_reservation()
    else:
        try:
            os.lstat(destination)
        except FileNotFoundError:
            pass
        else:
            raise RuntimeError(f"destination is occupied: {destination}")

    # Recheck immediately before the rename. POSIX has no portable atomic
    # rename-if-absent operation, so a hostile same-user syscall race remains.
    checked(source, expected_source)
    if expected_destination:
        checked_reservation()
        if kind == "directory":
            os.unlink(os.path.join(destination, reservation_name))
    else:
        try:
            os.lstat(destination)
        except FileNotFoundError:
            pass
        else:
            raise RuntimeError(f"destination is occupied: {destination}")
    os.replace(source, destination)
    checked(destination, expected_source)
except (OSError, RuntimeError) as exc:
    remove_unchanged_reservation()
    print(f"clonegrown installer: relocation refused: {exc}", file=sys.stderr)
    raise SystemExit(1)
PY
}

on_exit() {
  _exit_status="$1"
  trap - 0 1 2 15
  set +e

  if [ "$committed" -ne 1 ]; then
    # If a publish moved the exact staged object but the shell exited before
    # clearing its old name, revoke that name before rollback frees the inode.
    # A stage that never moved remains eligible for identity-checked cleanup.
    if [ "$codex_published" -eq 1 ] && created_directory_has_identity "$CODEX_SKILL" "$codex_stage_identity"; then
      codex_stage=""
    fi
    if [ "$claude_published" -eq 1 ] && created_directory_has_identity "$CLAUDE_SKILL" "$claude_stage_identity"; then
      claude_stage=""
    fi
    if [ "$wrapper_published" -eq 1 ] && created_file_has_identity "$WRAPPER" "$wrapper_stage_identity"; then
      wrapper_stage=""
    fi
    if [ "$source_published" -eq 1 ] && created_directory_has_identity "$INSTALL_ROOT" "$source_stage_identity"; then
      source_stage=""
    fi

    rollback_path "$CODEX_SKILL" "$codex_backup" "directory" "Codex skill" \
      "$codex_published" "$codex_stage_identity" "$codex_had_old" "$codex_backup_identity" "codex-skill"
    rollback_path "$CLAUDE_SKILL" "$claude_backup" "directory" "Claude skill" \
      "$claude_published" "$claude_stage_identity" "$claude_had_old" "$claude_backup_identity" "claude-skill"
    rollback_path "$WRAPPER" "$wrapper_backup" "file" "command wrapper" \
      "$wrapper_published" "$wrapper_stage_identity" "$wrapper_had_old" "$wrapper_backup_identity" "command"
    rollback_path "$INSTALL_ROOT" "$source_backup" "directory" "source" \
      "$source_published" "$source_stage_identity" "$source_had_old" "$source_backup_identity" "source"
    if [ "$transaction_started" -eq 1 ] && [ "$_exit_status" -ne 0 ]; then
      warn "installation failed; previous owned targets were restored where possible"
    fi
  fi

  cleanup_created_directory "$codex_stage" "$codex_stage_identity" "Codex skill stage"
  cleanup_created_directory "$claude_stage" "$claude_stage_identity" "Claude skill stage"
  cleanup_created_file "$wrapper_stage" "$wrapper_stage_identity" "command stage"
  cleanup_created_directory "$source_stage" "$source_stage_identity" "source stage"
  cleanup_created_directory "$control_tmp" "$control_tmp_identity" "installer control directory"
  exit "$_exit_status"
}

# A closed stdout (SIGPIPE) must also reach the EXIT trap so the control
# directory is removed; the default action would end the shell without it.
trap 'on_exit $?' 0
trap 'exit 129' 1
trap 'exit 130' 2
trap 'exit 141' 13
trap 'exit 143' 15

# Normalize aliases, reject overlapping targets, and authenticate every existing
# replacement before creating parents, cloning, removing, or renaming anything.
if ! python3 - "$INSTALL_HOME" "$INSTALL_ROOT_INPUT" "$BIN_DIR_INPUT" > "$control_tmp/preflight" <<'PY'
import os
import re
import secrets
import stat
import sys
import unicodedata

FORMAT = "clonegrown-installer=v1"
MARKER = ".clonegrown-install"
ID_RE = re.compile(r"[0-9a-f]{32}")


def stop(message: str) -> "None":
    raise SystemExit(f"clonegrown installer: {message}")


def evidence_head(path: str) -> bytes:
    # Read only the start of a regular file, never following a symlink and
    # never blocking on a FIFO. Ownership evidence is ASCII at the head of the
    # file; a command wrapper's body may carry non-UTF-8 path bytes after it.
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            stop(f"ownership evidence is not a regular file: {path}")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        stop(f"cannot read ownership evidence at {path}: {exc}")
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            stop(f"ownership evidence is not a regular file: {path}")
        return os.read(descriptor, 4097)
    except OSError as exc:
        stop(f"cannot read ownership evidence at {path}: {exc}")
    finally:
        os.close(descriptor)


def evidence_lines(path: str, *, header_lines: int | None = None) -> list[str]:
    # Split on newline only, allowing one trailing newline, so that every
    # ownership check in this installer reads the same lines. A marker is the
    # whole file; a wrapper header is the first lines of a longer file.
    data = evidence_head(path)
    if header_lines is None and len(data) > 4096:
        stop(f"ownership marker is unexpectedly large: {path}")
    lines = data.decode("utf-8", "surrogateescape").split("\n")
    if header_lines is not None:
        return lines[:header_lines]
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def normalize(raw: str, label: str, *, target: bool = False) -> str:
    if not raw:
        stop(f"{label} is empty")
    if "\n" in raw or "\r" in raw:
        stop(f"{label} contains a line break")
    lexical = os.path.abspath(raw)
    if target and os.path.islink(lexical):
        stop(f"{label} is a symlink: {lexical}")
    canonical = os.path.realpath(lexical)
    if "\n" in canonical or "\r" in canonical:
        stop(f"{label} contains a line break after canonicalization")
    return canonical


def directory_id(path: str, kind: str, label: str) -> str | None:
    if not os.path.lexists(path):
        return None
    if os.path.islink(path):
        stop(f"{label} is a symlink: {path}")
    if not os.path.isdir(path):
        stop(f"existing {label} is not owned by Clonegrown: expected a directory at {path}")
    marker = os.path.join(path, MARKER)
    if os.path.islink(marker) or not os.path.isfile(marker):
        stop(f"existing {label} is not owned by Clonegrown: missing regular marker {marker}")
    lines = evidence_lines(marker)
    if len(lines) != 3 or lines[0] != FORMAT or lines[2] != f"target={kind}":
        stop(f"existing {label} is not owned by Clonegrown: invalid marker {marker}")
    prefix = "installation_id="
    if not lines[1].startswith(prefix) or not ID_RE.fullmatch(lines[1][len(prefix):]):
        stop(f"existing {label} is not owned by Clonegrown: invalid installation id in {marker}")
    return lines[1][len(prefix):]


def wrapper_id(path: str) -> str | None:
    if not os.path.lexists(path):
        return None
    if os.path.islink(path):
        stop(f"command wrapper is a symlink: {path}")
    if not os.path.isfile(path):
        stop(f"existing command wrapper is not owned by Clonegrown: expected a regular file at {path}")
    lines = evidence_lines(path, header_lines=4)
    expected = ["#!/bin/sh", f"# {FORMAT}"]
    if len(lines) < 4 or lines[:2] != expected or lines[3] != "# target=command":
        stop(f"existing command wrapper is not owned by Clonegrown: invalid embedded marker at {path}")
    prefix = "# installation_id="
    if not lines[2].startswith(prefix) or not ID_RE.fullmatch(lines[2][len(prefix):]):
        stop(f"existing command wrapper is not owned by Clonegrown: invalid installation id at {path}")
    return lines[2][len(prefix):]


home = normalize(sys.argv[1], "HOME")
install_root = normalize(sys.argv[2], "installation source", target=True)
bin_dir = normalize(sys.argv[3], "command directory")
wrapper = normalize(os.path.join(bin_dir, "clonegrown"), "command wrapper", target=True)
claude_skill = normalize(os.path.join(home, ".claude", "skills", "clonegrown"),
                         "Claude skill directory", target=True)
codex_skill = normalize(os.path.join(home, ".agents", "skills", "clonegrown"),
                        "Codex skill directory", target=True)

if home == os.path.sep:
    stop("HOME must not be the filesystem root")
for label, path in (("installation source", install_root), ("command directory", bin_dir)):
    if path == os.path.sep:
        stop(f"{label} must not be the filesystem root")
    if path == home:
        stop(f"{label} must not be the home directory")

targets = [
    ("installation source", install_root),
    ("command wrapper", wrapper),
    ("Claude skill directory", claude_skill),
    ("Codex skill directory", codex_skill),
]


def comparison_path(path: str) -> str:
    # Be conservative on the default case-insensitive and Unicode-normalizing
    # macOS filesystem while preserving the actual path used for operations.
    return unicodedata.normalize("NFC", path).casefold()


for index, (left_label, left) in enumerate(targets):
    if left in {os.path.sep, home}:
        stop(f"{left_label} must not be the filesystem root or home directory")
    for right_label, right in targets[index + 1:]:
        comparable_left = comparison_path(left)
        comparable_right = comparison_path(right)
        common = os.path.commonpath((comparable_left, comparable_right))
        if common == comparable_left or common == comparable_right:
            stop(f"replacement targets overlap: {left_label} ({left}) and {right_label} ({right})")

ids = [
    directory_id(install_root, "source", "installation source"),
    wrapper_id(wrapper),
    directory_id(claude_skill, "claude-skill", "Claude skill directory"),
    directory_id(codex_skill, "codex-skill", "Codex skill directory"),
]
present_ids = {value for value in ids if value is not None}
if len(present_ids) > 1:
    stop("existing Clonegrown targets belong to different installation identities")
installation_id = present_ids.pop() if present_ids else secrets.token_hex(16)

# Emit the original filesystem bytes of each path; a text-mode print would
# refuse non-UTF-8 components under a UTF-8 locale.
for value in (install_root, bin_dir, wrapper, claude_skill, codex_skill, installation_id):
    sys.stdout.buffer.write(os.fsencode(value) + b"\n")
PY
then
  exit 1
fi

# Validate the raw record before POSIX shell reads can discard NUL bytes or
# otherwise hide malformed framing. Paths may contain non-UTF-8 bytes, so keep
# this check byte-oriented.
if ! python3 - "$control_tmp/preflight" <<'PY'
import sys
from pathlib import Path

data = Path(sys.argv[1]).read_bytes()
if b"\0" in data or b"\r" in data:
    raise SystemExit(1)
if not data.endswith(b"\n") or data.count(b"\n") != 6:
    raise SystemExit(1)
fields = data[:-1].split(b"\n")
if len(fields) != 6 or any(not field for field in fields[:5]):
    raise SystemExit(1)
installation_id_bytes = fields[5]
if len(installation_id_bytes) != 32 or any(
    byte not in b"0123456789abcdef" for byte in installation_id_bytes
):
    raise SystemExit(1)
PY
then
  fail "preflight returned malformed bytes or fields"
fi

preflight_read_ok=1
{
  IFS= read -r INSTALL_ROOT || preflight_read_ok=0
  IFS= read -r BIN_DIR || preflight_read_ok=0
  IFS= read -r WRAPPER || preflight_read_ok=0
  IFS= read -r CLAUDE_SKILL || preflight_read_ok=0
  IFS= read -r CODEX_SKILL || preflight_read_ok=0
  IFS= read -r installation_id || preflight_read_ok=0
  preflight_extra=""
  if IFS= read -r preflight_extra || [ -n "$preflight_extra" ]; then
    preflight_read_ok=0
  fi
} < "$control_tmp/preflight"

[ "$preflight_read_ok" -eq 1 ] || fail "preflight returned a malformed field count"
if [ -z "$INSTALL_ROOT" ] || [ -z "$BIN_DIR" ] || [ -z "$WRAPPER" ] || \
   [ -z "$CLAUDE_SKILL" ] || [ -z "$CODEX_SKILL" ]; then
  fail "preflight returned an empty path field"
fi
case "$installation_id" in
  ""|*[!0123456789abcdef]*)
    fail "preflight returned an invalid installation id"
    ;;
esac
[ "${#installation_id}" -eq 32 ] || fail "preflight returned an invalid installation id"

BIN_DIR_SHELL_LITERAL="$(posix_shell_literal "$BIN_DIR")" || \
  fail "could not encode the binary directory for shell guidance"
WRAPPER_SHELL_LITERAL="$(posix_shell_literal "$WRAPPER")" || \
  fail "could not encode the command path for shell guidance"

INSTALL_PARENT="$(dirname "$INSTALL_ROOT")"
CLAUDE_PARENT="$(dirname "$CLAUDE_SKILL")"
CODEX_PARENT="$(dirname "$CODEX_SKILL")"

mkdir -p "$INSTALL_PARENT" "$BIN_DIR" "$CLAUDE_PARENT" "$CODEX_PARENT"
fsync_paths "$INSTALL_PARENT" "$BIN_DIR" "$CLAUDE_PARENT" "$CODEX_PARENT"

write_marker() {
  _marker_path="$1"
  _marker_kind="$2"
  [ ! -e "$_marker_path" ] && [ ! -L "$_marker_path" ] || fail "staged source uses reserved marker path: $_marker_path"
  printf '%s\n%s\n%s\n' \
    "$MARKER_FORMAT" \
    "installation_id=$installation_id" \
    "target=$_marker_kind" > "$_marker_path"
}

reserve_directory_backup() {
  _reserve_parent="$1"
  _reserve_label="$2"
  _reserve_token="$3"
  _reserve_path="$(mktemp -d "$_reserve_parent/.clonegrown-$_reserve_label.backup.XXXXXX")"
  printf '%s\n' "$_reserve_token" > "$_reserve_path/$BACKUP_RESERVATION_NAME"
  fsync_paths "$_reserve_path/$BACKUP_RESERVATION_NAME" "$_reserve_path"
  printf '%s\n' "$_reserve_path"
}

reserve_file_backup() {
  _reserve_parent="$1"
  _reserve_label="$2"
  _reserve_token="$3"
  _reserve_path="$(mktemp "$_reserve_parent/.clonegrown-$_reserve_label.backup.XXXXXX")"
  printf '%s\n' "$_reserve_token" > "$_reserve_path"
  fsync_paths "$_reserve_path"
  printf '%s\n' "$_reserve_path"
}

say "Installing Clonegrown..."

# Build all four replacements before moving any live target.
source_stage="$(mktemp -d "$INSTALL_PARENT/.clonegrown-source.new.XXXXXX")"
source_stage_identity="$(path_identity "$source_stage")" || fail "could not identify staged source"
git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$source_stage"
write_marker "$source_stage/$MARKER_NAME" "source"
[ -f "$source_stage/SKILL.md" ] && [ ! -L "$source_stage/SKILL.md" ] || fail "cloned source has no regular SKILL.md"
fsync_paths "$source_stage/$MARKER_NAME" "$source_stage/SKILL.md" "$source_stage"

wrapper_stage="$(mktemp "$BIN_DIR/.clonegrown-command.new.XXXXXX")"
wrapper_stage_identity="$(path_identity "$wrapper_stage")" || fail "could not identify staged command wrapper"
python3 - "$wrapper_stage" "$INSTALL_ROOT" "$installation_id" <<'PY'
import os
import shlex
import sys
from pathlib import Path

path, install_root, installation_id = sys.argv[1:]
launcher = (
    "import runpy, sys; "
    "install_root = sys.argv.pop(1); "
    "sys.path.insert(0, install_root); "
    'runpy.run_module("clonegrown", run_name="__main__", alter_sys=True)'
)
content = "\n".join((
    "#!/bin/sh",
    "# clonegrown-installer=v1",
    f"# installation_id={installation_id}",
    "# target=command",
    f"CLONEGROWN_INSTALL_ROOT={shlex.quote(install_root)}",
    f'exec python3 -c {shlex.quote(launcher)} "$CLONEGROWN_INSTALL_ROOT" "$@"',
    "",
))
Path(path).write_bytes(os.fsencode(content))
PY
chmod 0755 "$wrapper_stage"
fsync_paths "$wrapper_stage" "$BIN_DIR"

claude_stage="$(mktemp -d "$CLAUDE_PARENT/.clonegrown-claude.new.XXXXXX")"
claude_stage_identity="$(path_identity "$claude_stage")" || fail "could not identify staged Claude skill"
cp "$source_stage/SKILL.md" "$claude_stage/SKILL.md"
write_marker "$claude_stage/$MARKER_NAME" "claude-skill"
fsync_paths "$claude_stage/SKILL.md" "$claude_stage/$MARKER_NAME" "$claude_stage"

codex_stage="$(mktemp -d "$CODEX_PARENT/.clonegrown-codex.new.XXXXXX")"
codex_stage_identity="$(path_identity "$codex_stage")" || fail "could not identify staged Codex skill"
cp "$source_stage/SKILL.md" "$codex_stage/SKILL.md"
write_marker "$codex_stage/$MARKER_NAME" "codex-skill"
fsync_paths "$codex_stage/SKILL.md" "$codex_stage/$MARKER_NAME" "$codex_stage"

transaction_started=1

# Source directory.
if path_exists "$INSTALL_ROOT"; then
  owned_directory "$INSTALL_ROOT" "source" "$installation_id" || fail "installation source ownership changed after preflight"
  source_backup="$(reserve_directory_backup "$INSTALL_PARENT" "source" "$installation_id")"
  source_backup_reservation_identity="$(path_identity "$source_backup")" || fail "could not identify source backup reservation"
  source_backup_identity="$(path_identity "$INSTALL_ROOT")" || fail "could not identify previous source"
  source_had_old=1
  relocate_created_path \
    "$INSTALL_ROOT" "$source_backup_identity" \
    "$source_backup" "$source_backup_reservation_identity" \
    "$installation_id" \
    "directory" "source" "$installation_id" || fail "could not move previous source to its reserved backup"
  fsync_paths "$INSTALL_PARENT"
fi
source_published=1
relocate_created_path \
  "$source_stage" "$source_stage_identity" \
  "$INSTALL_ROOT" "" "" "directory" "source" "$installation_id" || fail "could not publish staged source"
source_stage=""
fsync_paths "$INSTALL_PARENT"

# Command wrapper.
if path_exists "$WRAPPER"; then
  owned_wrapper "$WRAPPER" "$installation_id" || fail "command wrapper ownership changed after preflight"
  wrapper_backup="$(reserve_file_backup "$BIN_DIR" "command" "$installation_id")"
  wrapper_backup_reservation_identity="$(path_identity "$wrapper_backup")" || fail "could not identify command backup reservation"
  wrapper_backup_identity="$(path_identity "$WRAPPER")" || fail "could not identify previous command wrapper"
  wrapper_had_old=1
  relocate_created_path \
    "$WRAPPER" "$wrapper_backup_identity" \
    "$wrapper_backup" "$wrapper_backup_reservation_identity" \
    "$installation_id" \
    "file" "command" "$installation_id" || fail "could not move previous command wrapper to its reserved backup"
  fsync_paths "$BIN_DIR"
fi
wrapper_published=1
relocate_created_path \
  "$wrapper_stage" "$wrapper_stage_identity" \
  "$WRAPPER" "" "" "file" "command" "$installation_id" || fail "could not publish staged command wrapper"
wrapper_stage=""
fsync_paths "$BIN_DIR"

# Claude Code skill.
if path_exists "$CLAUDE_SKILL"; then
  owned_directory "$CLAUDE_SKILL" "claude-skill" "$installation_id" || fail "Claude skill ownership changed after preflight"
  claude_backup="$(reserve_directory_backup "$CLAUDE_PARENT" "claude" "$installation_id")"
  claude_backup_reservation_identity="$(path_identity "$claude_backup")" || fail "could not identify Claude skill backup reservation"
  claude_backup_identity="$(path_identity "$CLAUDE_SKILL")" || fail "could not identify previous Claude skill"
  claude_had_old=1
  relocate_created_path \
    "$CLAUDE_SKILL" "$claude_backup_identity" \
    "$claude_backup" "$claude_backup_reservation_identity" \
    "$installation_id" \
    "directory" "claude-skill" "$installation_id" || fail "could not move previous Claude skill to its reserved backup"
  fsync_paths "$CLAUDE_PARENT"
fi
claude_published=1
relocate_created_path \
  "$claude_stage" "$claude_stage_identity" \
  "$CLAUDE_SKILL" "" "" "directory" "claude-skill" "$installation_id" || fail "could not publish staged Claude skill"
claude_stage=""
fsync_paths "$CLAUDE_PARENT"

# Codex skill.
if path_exists "$CODEX_SKILL"; then
  owned_directory "$CODEX_SKILL" "codex-skill" "$installation_id" || fail "Codex skill ownership changed after preflight"
  codex_backup="$(reserve_directory_backup "$CODEX_PARENT" "codex" "$installation_id")"
  codex_backup_reservation_identity="$(path_identity "$codex_backup")" || fail "could not identify Codex skill backup reservation"
  codex_backup_identity="$(path_identity "$CODEX_SKILL")" || fail "could not identify previous Codex skill"
  codex_had_old=1
  relocate_created_path \
    "$CODEX_SKILL" "$codex_backup_identity" \
    "$codex_backup" "$codex_backup_reservation_identity" \
    "$installation_id" \
    "directory" "codex-skill" "$installation_id" || fail "could not move previous Codex skill to its reserved backup"
  fsync_paths "$CODEX_PARENT"
fi
codex_published=1
relocate_created_path \
  "$codex_stage" "$codex_stage_identity" \
  "$CODEX_SKILL" "" "" "directory" "codex-skill" "$installation_id" || fail "could not publish staged Codex skill"
codex_stage=""
fsync_paths "$CODEX_PARENT"

owned_directory "$INSTALL_ROOT" "source" "$installation_id" || fail "published source failed ownership verification"
owned_wrapper "$WRAPPER" "$installation_id" || fail "published command failed ownership verification"
owned_directory "$CLAUDE_SKILL" "claude-skill" "$installation_id" || fail "published Claude skill failed ownership verification"
owned_directory "$CODEX_SKILL" "codex-skill" "$installation_id" || fail "published Codex skill failed ownership verification"

committed=1

# The new four-target installation is committed. Remove only the exact old
# objects authenticated before relocation: the same device, inode, and type,
# still carrying this installation's marker. Leave a warning rather than
# rolling back a committed update if cleanup itself fails.
if [ "$source_had_old" -eq 1 ] && path_exists "$source_backup"; then
  cleanup_created_directory "$source_backup" "$source_backup_identity" "old source backup" "source" "$installation_id"
fi
if [ "$wrapper_had_old" -eq 1 ] && path_exists "$wrapper_backup"; then
  cleanup_created_file "$wrapper_backup" "$wrapper_backup_identity" "old command backup" "command" "$installation_id"
fi
if [ "$claude_had_old" -eq 1 ] && path_exists "$claude_backup"; then
  cleanup_created_directory "$claude_backup" "$claude_backup_identity" "old Claude skill backup" "claude-skill" "$installation_id"
fi
if [ "$codex_had_old" -eq 1 ] && path_exists "$codex_backup"; then
  cleanup_created_directory "$codex_backup" "$codex_backup_identity" "old Codex skill backup" "codex-skill" "$installation_id"
fi
fsync_paths "$INSTALL_PARENT" "$BIN_DIR" "$CLAUDE_PARENT" "$CODEX_PARENT" || \
  warn "could not fsync every parent after committed backup cleanup"

say ""
say "Clonegrown installed."
say "  command: $WRAPPER"
say "  source:  $INSTALL_ROOT"
say "  Claude:  $CLAUDE_SKILL/SKILL.md"
say "  Codex:   $CODEX_SKILL/SKILL.md"
say ""

case "$BIN_DIR" in
  *:*)
    say "$BIN_DIR contains a colon, which POSIX PATH treats as a separator."
    say "Run Clonegrown by its full path or reinstall with a different CLONEGROWN_BIN_DIR:"
    say "  $WRAPPER_SHELL_LITERAL --help"
    ;;
  *)
    case ":${PATH:-}:" in
      *":$BIN_DIR:"*)
        say "Try: clonegrown --help"
        ;;
      *)
        say "$BIN_DIR is not currently on PATH. Add this to your shell profile:"
        say "  export PATH=$BIN_DIR_SHELL_LITERAL:\"\$PATH\""
        say "Then run: clonegrown --help"
        ;;
    esac
    ;;
esac

say ""
say "If Claude Code was already running and this created ~/.claude/skills for the first time, start a new Claude Code session so it discovers the skill."
