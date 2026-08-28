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
WRAPPER=""
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

rollback_directory() {
  _rollback_target="$1"
  _rollback_backup="$2"
  _rollback_kind="$3"
  _rollback_published="$4"
  _rollback_had_old="$5"
  _rollback_parent="$(dirname "$_rollback_target")"

  if [ "$_rollback_published" -eq 1 ] && path_exists "$_rollback_target"; then
    if owned_directory "$_rollback_target" "$_rollback_kind" "$installation_id"; then
      rm -rf "$_rollback_target" || warn "could not remove newly published $_rollback_kind target: $_rollback_target"
      fsync_paths "$_rollback_parent" >/dev/null 2>&1 || true
    else
      warn "rollback left an unexpected target in place: $_rollback_target"
    fi
  fi

  if [ "$_rollback_had_old" -eq 1 ] && path_exists "$_rollback_backup"; then
    if path_exists "$_rollback_target"; then
      warn "previous $_rollback_kind target remains in backup because its destination is occupied: $_rollback_backup"
    elif owned_directory "$_rollback_backup" "$_rollback_kind" "$installation_id"; then
      mv "$_rollback_backup" "$_rollback_target" || warn "could not restore $_rollback_kind backup: $_rollback_backup"
      fsync_paths "$_rollback_parent" >/dev/null 2>&1 || true
    else
      warn "previous $_rollback_kind target has invalid ownership evidence; backup preserved: $_rollback_backup"
    fi
  fi
}

rollback_wrapper() {
  _rollback_target="$1"
  _rollback_backup="$2"
  _rollback_published="$3"
  _rollback_had_old="$4"
  _rollback_parent="$(dirname "$_rollback_target")"

  if [ "$_rollback_published" -eq 1 ] && path_exists "$_rollback_target"; then
    if owned_wrapper "$_rollback_target" "$installation_id"; then
      rm -f "$_rollback_target" || warn "could not remove newly published command wrapper: $_rollback_target"
      fsync_paths "$_rollback_parent" >/dev/null 2>&1 || true
    else
      warn "rollback left an unexpected command target in place: $_rollback_target"
    fi
  fi

  if [ "$_rollback_had_old" -eq 1 ] && path_exists "$_rollback_backup"; then
    if path_exists "$_rollback_target"; then
      warn "previous command wrapper remains in backup because its destination is occupied: $_rollback_backup"
    elif owned_wrapper "$_rollback_backup" "$installation_id"; then
      mv "$_rollback_backup" "$_rollback_target" || warn "could not restore command wrapper: $_rollback_backup"
      fsync_paths "$_rollback_parent" >/dev/null 2>&1 || true
    else
      warn "previous command wrapper has invalid ownership evidence; backup preserved: $_rollback_backup"
    fi
  fi
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
  [ -n "$_cleanup_path" ] || return 0

  # Keep the identity decision and deletion inside one process. In particular,
  # do not return a validated pathname to a separately resolved rm command.
  if python3 - "$_cleanup_path" "$_cleanup_identity" "$_cleanup_kind" <<'PY'
import os
import shutil
import stat
import sys

path, expected_identity, kind = sys.argv[1:]
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
  cleanup_created_path "$1" "$2" "directory" "$3"
}

cleanup_created_file() {
  cleanup_created_path "$1" "$2" "file" "$3"
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
      codex_stage_identity=""
    fi
    if [ "$claude_published" -eq 1 ] && created_directory_has_identity "$CLAUDE_SKILL" "$claude_stage_identity"; then
      claude_stage=""
      claude_stage_identity=""
    fi
    if [ "$wrapper_published" -eq 1 ] && created_file_has_identity "$WRAPPER" "$wrapper_stage_identity"; then
      wrapper_stage=""
      wrapper_stage_identity=""
    fi
    if [ "$source_published" -eq 1 ] && created_directory_has_identity "$INSTALL_ROOT" "$source_stage_identity"; then
      source_stage=""
      source_stage_identity=""
    fi

    rollback_directory "$CODEX_SKILL" "$codex_backup" "codex-skill" "$codex_published" "$codex_had_old"
    rollback_directory "$CLAUDE_SKILL" "$claude_backup" "claude-skill" "$claude_published" "$claude_had_old"
    rollback_wrapper "$WRAPPER" "$wrapper_backup" "$wrapper_published" "$wrapper_had_old"
    rollback_directory "$INSTALL_ROOT" "$source_backup" "source" "$source_published" "$source_had_old"
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

trap 'on_exit $?' 0
trap 'exit 129' 1
trap 'exit 130' 2
trap 'exit 143' 15

# Normalize aliases, reject overlapping targets, and authenticate every existing
# replacement before creating parents, cloning, removing, or renaming anything.
if ! python3 - "$INSTALL_HOME" "$INSTALL_ROOT_INPUT" "$BIN_DIR_INPUT" > "$control_tmp/preflight" <<'PY'
import os
import re
import secrets
import sys
import unicodedata
from pathlib import Path

FORMAT = "clonegrown-installer=v1"
MARKER = ".clonegrown-install"
ID_RE = re.compile(r"[0-9a-f]{32}")


def stop(message: str) -> "None":
    raise SystemExit(f"clonegrown installer: {message}")


def checked_text(path: str) -> list[str]:
    try:
        stat = os.stat(path, follow_symlinks=False)
        if stat.st_size > 4096:
            stop(f"ownership marker is unexpectedly large: {path}")
        return Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        stop(f"cannot read ownership evidence at {path}: {exc}")


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
    lines = checked_text(marker)
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
    lines = checked_text(path)
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

for value in (install_root, bin_dir, wrapper, claude_skill, codex_skill, installation_id):
    print(value)
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
  _reserve_path="$(mktemp -d "$_reserve_parent/.clonegrown-$_reserve_label.backup.XXXXXX")"
  rmdir "$_reserve_path"
  printf '%s\n' "$_reserve_path"
}

reserve_file_backup() {
  _reserve_parent="$1"
  _reserve_label="$2"
  _reserve_path="$(mktemp "$_reserve_parent/.clonegrown-$_reserve_label.backup.XXXXXX")"
  rm -f "$_reserve_path"
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
Path(path).write_text(content, encoding="utf-8")
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
  source_backup="$(reserve_directory_backup "$INSTALL_PARENT" "source")"
  source_had_old=1
  mv "$INSTALL_ROOT" "$source_backup"
  fsync_paths "$INSTALL_PARENT"
fi
path_exists "$INSTALL_ROOT" && fail "installation source reappeared during update: $INSTALL_ROOT"
created_directory_has_identity "$source_stage" "$source_stage_identity" || fail "staged source ownership changed before publication"
source_published=1
mv "$source_stage" "$INSTALL_ROOT"
created_directory_has_identity "$INSTALL_ROOT" "$source_stage_identity" || fail "published source does not match its staged object"
source_stage=""
source_stage_identity=""
fsync_paths "$INSTALL_PARENT"

# Command wrapper.
if path_exists "$WRAPPER"; then
  owned_wrapper "$WRAPPER" "$installation_id" || fail "command wrapper ownership changed after preflight"
  wrapper_backup="$(reserve_file_backup "$BIN_DIR" "command")"
  wrapper_had_old=1
  mv "$WRAPPER" "$wrapper_backup"
  fsync_paths "$BIN_DIR"
fi
path_exists "$WRAPPER" && fail "command wrapper reappeared during update: $WRAPPER"
created_file_has_identity "$wrapper_stage" "$wrapper_stage_identity" || fail "staged command ownership changed before publication"
wrapper_published=1
mv "$wrapper_stage" "$WRAPPER"
created_file_has_identity "$WRAPPER" "$wrapper_stage_identity" || fail "published command does not match its staged object"
wrapper_stage=""
wrapper_stage_identity=""
fsync_paths "$BIN_DIR"

# Claude Code skill.
if path_exists "$CLAUDE_SKILL"; then
  owned_directory "$CLAUDE_SKILL" "claude-skill" "$installation_id" || fail "Claude skill ownership changed after preflight"
  claude_backup="$(reserve_directory_backup "$CLAUDE_PARENT" "claude")"
  claude_had_old=1
  mv "$CLAUDE_SKILL" "$claude_backup"
  fsync_paths "$CLAUDE_PARENT"
fi
path_exists "$CLAUDE_SKILL" && fail "Claude skill target reappeared during update: $CLAUDE_SKILL"
created_directory_has_identity "$claude_stage" "$claude_stage_identity" || fail "staged Claude skill ownership changed before publication"
claude_published=1
mv "$claude_stage" "$CLAUDE_SKILL"
created_directory_has_identity "$CLAUDE_SKILL" "$claude_stage_identity" || fail "published Claude skill does not match its staged object"
claude_stage=""
claude_stage_identity=""
fsync_paths "$CLAUDE_PARENT"

# Codex skill.
if path_exists "$CODEX_SKILL"; then
  owned_directory "$CODEX_SKILL" "codex-skill" "$installation_id" || fail "Codex skill ownership changed after preflight"
  codex_backup="$(reserve_directory_backup "$CODEX_PARENT" "codex")"
  codex_had_old=1
  mv "$CODEX_SKILL" "$codex_backup"
  fsync_paths "$CODEX_PARENT"
fi
path_exists "$CODEX_SKILL" && fail "Codex skill target reappeared during update: $CODEX_SKILL"
created_directory_has_identity "$codex_stage" "$codex_stage_identity" || fail "staged Codex skill ownership changed before publication"
codex_published=1
mv "$codex_stage" "$CODEX_SKILL"
created_directory_has_identity "$CODEX_SKILL" "$codex_stage_identity" || fail "published Codex skill does not match its staged object"
codex_stage=""
codex_stage_identity=""
fsync_paths "$CODEX_PARENT"

owned_directory "$INSTALL_ROOT" "source" "$installation_id" || fail "published source failed ownership verification"
owned_wrapper "$WRAPPER" "$installation_id" || fail "published command failed ownership verification"
owned_directory "$CLAUDE_SKILL" "claude-skill" "$installation_id" || fail "published Claude skill failed ownership verification"
owned_directory "$CODEX_SKILL" "codex-skill" "$installation_id" || fail "published Codex skill failed ownership verification"

committed=1

# The new four-target installation is committed. Old backups were authenticated
# before their rename; remove them now, leaving a warning rather than rolling
# back a committed update if cleanup itself fails.
if [ "$source_had_old" -eq 1 ] && path_exists "$source_backup"; then
  if owned_directory "$source_backup" "source" "$installation_id"; then
    rm -rf "$source_backup" || warn "could not remove old source backup: $source_backup"
  else
    warn "old source backup lost ownership evidence and was preserved: $source_backup"
  fi
fi
if [ "$wrapper_had_old" -eq 1 ] && path_exists "$wrapper_backup"; then
  if owned_wrapper "$wrapper_backup" "$installation_id"; then
    rm -f "$wrapper_backup" || warn "could not remove old command backup: $wrapper_backup"
  else
    warn "old command backup lost ownership evidence and was preserved: $wrapper_backup"
  fi
fi
if [ "$claude_had_old" -eq 1 ] && path_exists "$claude_backup"; then
  if owned_directory "$claude_backup" "claude-skill" "$installation_id"; then
    rm -rf "$claude_backup" || warn "could not remove old Claude skill backup: $claude_backup"
  else
    warn "old Claude skill backup lost ownership evidence and was preserved: $claude_backup"
  fi
fi
if [ "$codex_had_old" -eq 1 ] && path_exists "$codex_backup"; then
  if owned_directory "$codex_backup" "codex-skill" "$installation_id"; then
    rm -rf "$codex_backup" || warn "could not remove old Codex skill backup: $codex_backup"
  else
    warn "old Codex skill backup lost ownership evidence and was preserved: $codex_backup"
  fi
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

case ":${PATH:-}:" in
  *":$BIN_DIR:"*)
    say "Try: clonegrown --help"
    ;;
  *)
    say "$BIN_DIR is not currently on PATH. Add this to your shell profile:"
    say "  export PATH=\"$BIN_DIR:\$PATH\""
    say "Then run: clonegrown --help"
    ;;
esac

say ""
say "If Claude Code was already running and this created ~/.claude/skills for the first time, start a new Claude Code session so it discovers the skill."
