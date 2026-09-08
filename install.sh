#!/bin/sh
# Optional source-checkout helper. Ordinary uv/pipx installation needs no helper.
set -eu
[ "$#" -eq 0 ] || { printf '%s\n' 'usage: sh install.sh' >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { printf '%s\n' 'clonegrown installer: Python 3.11+ is required' >&2; exit 1; }
SOURCE_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec python3 - "$SOURCE_DIR" <<'PY'
import contextlib
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys

package_attempted = False
try:
    if sys.version_info < (3, 11) or sys.platform not in ('linux', 'darwin'):
        raise RuntimeError('Python 3.11+ on Linux or macOS is required')
    for command in ('git', 'uv'):
        if shutil.which(command) is None:
            raise RuntimeError(f'{command} is required')
    legacy = ('CLONEGROWN_HOME', 'CLONEGROWN_BIN_DIR', 'CLONEGROWN_REPO_URL', 'CLONEGROWN_REF')
    if any(name in os.environ for name in legacy):
        raise RuntimeError('legacy installer settings are unsupported; use ordinary uv tool commands to choose the source and locations')
    source = Path(sys.argv[1])
    if not (source / 'pyproject.toml').is_file():
        raise RuntimeError('run this helper from a Clonegrown source checkout')
    if not os.environ.get('HOME'):
        raise RuntimeError('HOME is required')
    home = Path(os.environ['HOME']).resolve(strict=True)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with contextlib.ExitStack() as stack:
        def open_directory(name, parent=None):
            descriptor = os.open(name, directory_flags, dir_fd=parent)
            stack.callback(os.close, descriptor)
            return descriptor

        def read_regular(name, parent=None, expected_size=None):
            descriptor = os.open(name, file_flags, dir_fd=parent)
            with os.fdopen(descriptor, 'rb') as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode):
                    raise RuntimeError(f'{name} is not a regular file')
                if expected_size is not None and info.st_size != expected_size:
                    return None
                return handle.read() if expected_size is None else handle.read(expected_size + 1)

        skill = read_regular(source / 'SKILL.md')
        home_fd = open_directory(home)
        edges = []
        targets = []
        # Preflight both destinations before asking the package manager to write.
        for agent in ('.claude', '.agents'):
            parts = (agent, 'skills', 'clonegrown')
            parent = home_fd
            display = home
            missing = ()
            for index, part in enumerate(parts):
                display = display / part
                try:
                    child = open_directory(part, parent)
                except FileNotFoundError:
                    missing = parts[index:]
                    break
                except OSError as error:
                    raise RuntimeError(f'unsafe skill directory: {display}: {error.strerror}') from error
                edges.append((parent, part, child, display))
                parent = child
            destination = home.joinpath(*parts)
            if not missing:
                if read_regular('SKILL.md', parent, len(skill)) != skill:
                    raise RuntimeError(f'existing skill differs: {destination / "SKILL.md"}; review it manually')
            targets.append((parent, missing, destination))

        def verify_directories():
            for parent, name, child, display in edges:
                current = os.stat(name, dir_fd=parent, follow_symlinks=False)
                opened = os.fstat(child)
                if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
                    raise RuntimeError(f'skill directory changed during installation: {display}')

        package_attempted = True
        subprocess.run(['uv', 'tool', 'install', '--reinstall', '--python', sys.executable, str(source)], check=True)
        verify_directories()
        for parent, missing, destination in targets:
            for part in missing:
                os.mkdir(part, 0o755, dir_fd=parent)  # an intervening occupant is a refusal
                child = open_directory(part, parent)
                edges.append((parent, part, child, destination))
                parent = child
            if missing:
                descriptor = os.open('SKILL.md', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                     0o644, dir_fd=parent)
                with os.fdopen(descriptor, 'wb') as handle:
                    handle.write(skill)
            elif read_regular('SKILL.md', parent, len(skill)) != skill:
                raise RuntimeError(f'existing skill changed: {destination / "SKILL.md"}; review it manually')
        verify_directories()
        print('Clonegrown installed through uv. Try: clonegrown --help')
        for _, _, destination in targets:
            print(f'Skill: {destination / "SKILL.md"}')
        print('Restart Claude Code or Codex to discover newly installed skills.')
except (OSError, RuntimeError, subprocess.SubprocessError) as error:
    print(f'clonegrown installer: {error}', file=sys.stderr)
    if package_attempted:
        print('The package or some skills may already be installed. Completed steps were kept; inspect the reported path before retrying.', file=sys.stderr)
    raise SystemExit(1)
PY
