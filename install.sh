#!/bin/sh
set -eu

REPO_URL="${CLONEGROWN_REPO_URL:-https://github.com/kserrec/clonegrown.git}"
REF="${CLONEGROWN_REF:-main}"
INSTALL_ROOT="${CLONEGROWN_HOME:-$HOME/.local/share/clonegrown}"
BIN_DIR="${CLONEGROWN_BIN_DIR:-$HOME/.local/bin}"

say() {
  printf '%s\n' "$*"
}

fail() {
  printf 'clonegrown installer: %s\n' "$*" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || fail "git is required"
command -v python3 >/dev/null 2>&1 || fail "Python 3.11+ is required"

python3 - <<'PY' || fail "Python 3.11+ is required"
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY

tmp="$(mktemp -d 2>/dev/null || mktemp -d -t clonegrown)"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

say "Installing Clonegrown..."
git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$tmp/repo"

parent="$(dirname "$INSTALL_ROOT")"
mkdir -p "$parent" "$BIN_DIR"
rm -rf "$INSTALL_ROOT.new"
mv "$tmp/repo" "$INSTALL_ROOT.new"
rm -rf "$INSTALL_ROOT"
mv "$INSTALL_ROOT.new" "$INSTALL_ROOT"

cat > "$BIN_DIR/clonegrown" <<EOF
#!/bin/sh
exec python3 "$INSTALL_ROOT/clonegrown_cli.py" "\$@"
EOF
chmod +x "$BIN_DIR/clonegrown"

# Claude Code personal skill.
mkdir -p "$HOME/.claude/skills/clonegrown"
cp "$INSTALL_ROOT/SKILL.md" "$HOME/.claude/skills/clonegrown/SKILL.md"

# Codex current user-scope Agent Skills location.
mkdir -p "$HOME/.agents/skills/clonegrown"
cp "$INSTALL_ROOT/SKILL.md" "$HOME/.agents/skills/clonegrown/SKILL.md"

say ""
say "Clonegrown installed."
say "  command: $BIN_DIR/clonegrown"
say "  source:  $INSTALL_ROOT"
say "  Claude:  $HOME/.claude/skills/clonegrown/SKILL.md"
say "  Codex:   $HOME/.agents/skills/clonegrown/SKILL.md"
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
