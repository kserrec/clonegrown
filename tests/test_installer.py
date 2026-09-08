"""The optional helper delegates packaging and preserves occupied skill destinations."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / 'home with spaces'
        self.home.mkdir()
        self.source = self.root / 'source checkout'
        self.source.mkdir()
        for name in ('install.sh', 'SKILL.md', 'pyproject.toml'):
            shutil.copy2(PROJECT / name, self.source / name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'package-calls.jsonl'
        self.uv = self.bin / 'uv'
        self.uv.write_text(
            f'#!{sys.executable}\n' + '''import json, os, sys
from pathlib import Path
with Path(os.environ['INSTALL_TEST_LOG']).open('a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\\n')
home = Path(os.environ['HOME'])
action = os.environ.get('INSTALL_TEST_ACTION')
if action == 'occupy':
    destination = home / '.agents/skills/clonegrown'
    destination.mkdir()
    (destination / 'SKILL.md').write_text('foreign skill')
elif action == 'substitute':
    (home / '.agents').rename(home / 'displaced-agents')
    (home / '.agents').symlink_to(Path(os.environ['INSTALL_TEST_OUTSIDE']))
raise SystemExit(int(os.environ.get('INSTALL_TEST_EXIT', '0')))
''')
        self.uv.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), INSTALL_TEST_LOG=str(self.log),
                        PATH=str(self.bin) + os.pathsep + os.environ['PATH'])
        for name in ('CLONEGROWN_HOME', 'CLONEGROWN_BIN_DIR', 'CLONEGROWN_REPO_URL', 'CLONEGROWN_REF'):
            self.env.pop(name, None)

    def run_helper(self, **overrides):
        return subprocess.run(['/bin/sh', str(self.source / 'install.sh')],
                              cwd=self.root, env={**self.env, **overrides},
                              text=True, capture_output=True, timeout=15)

    def skills(self):
        return [self.home / agent / 'skills/clonegrown/SKILL.md' for agent in ('.claude', '.agents')]

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in self.skills():
            self.assertEqual(path.read_bytes(), (self.source / 'SKILL.md').read_bytes())

    def test_clean_install_delegates_packaging_and_installs_both_skills(self):
        self.assert_success(self.run_helper())
        (arguments,) = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(arguments[:2], ['tool', 'install'])
        self.assertIn('--reinstall', arguments)
        self.assertIn(str(self.source), arguments)

    def test_update_reinstalls_package_and_keeps_matching_skills_and_other_files(self):
        self.assert_success(self.run_helper())
        before = [path.stat().st_ino for path in self.skills()]
        note = self.skills()[0].parent / 'personal-notes.txt'
        note.write_text('keep this')
        self.assert_success(self.run_helper())
        self.assertEqual(len(self.log.read_text().splitlines()), 2)
        self.assertEqual([path.stat().st_ino for path in self.skills()], before)
        self.assertEqual(note.read_text(), 'keep this')

    def test_differing_skill_refuses_before_package_update(self):
        self.assert_success(self.run_helper())
        self.skills()[1].write_text('my edited skill')
        before = self.log.read_bytes()
        result = self.run_helper()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('existing skill differs', result.stderr)
        self.assertEqual(self.skills()[1].read_text(), 'my edited skill')
        self.assertEqual(self.log.read_bytes(), before)

    def test_unsafe_destination_types_are_refused_without_following_or_blocking(self):
        for relative in ('.agents', '.agents/skills', '.agents/skills/clonegrown',
                         '.agents/skills/clonegrown/SKILL.md'):
            for kind in ('symlink', 'file', 'fifo'):
                with self.subTest(path=relative, kind=kind), tempfile.TemporaryDirectory(dir=self.root) as td:
                    home = Path(td)
                    target = home / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    outside = home / 'outside'
                    outside.mkdir()
                    sentinel = outside / 'sentinel'
                    sentinel.write_text('untouched')
                    if kind == 'symlink':
                        target.symlink_to(sentinel if target.name == 'SKILL.md' else outside)
                    elif kind == 'file':
                        target.write_text('foreign')
                    else:
                        os.mkfifo(target)
                    result = self.run_helper(HOME=str(home))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertTrue(os.path.lexists(target))
                    self.assertEqual(sentinel.read_text(), 'untouched')
                    self.assertEqual(sorted(path.name for path in outside.iterdir()), ['sentinel'])
                    self.assertFalse(self.log.exists())
                    self.assertFalse((home / '.claude').exists())

    def test_missing_prerequisites_refuse_before_installation(self):
        for missing in ('python3', 'git', 'uv'):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory(dir=self.root) as td:
                command_dir = Path(td)
                for name in ('python3', 'git', 'uv', 'dirname'):
                    if name != missing:
                        command_dir.joinpath(name).symlink_to(
                            self.uv if name == 'uv' else sys.executable if name == 'python3' else shutil.which(name))
                result = self.run_helper(PATH=str(command_dir))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('required', result.stderr)
                self.assertFalse(self.log.exists())
                self.assertFalse((self.home / '.claude').exists())

    def test_package_failure_keeps_skill_destinations_absent(self):
        result = self.run_helper(INSTALL_TEST_EXIT='23')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(self.log.exists())
        self.assertFalse((self.home / '.claude').exists())
        self.assertFalse((self.home / '.agents').exists())
        self.assertIn('Completed steps were kept', result.stderr)

    def test_path_appearing_during_package_install_is_preserved(self):
        (self.home / '.agents/skills').mkdir(parents=True)
        result = self.run_helper(INSTALL_TEST_ACTION='occupy')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.skills()[1].read_text(), 'foreign skill')
        self.assertIn('Completed steps were kept', result.stderr)

    def test_directory_substitution_during_package_install_is_refused(self):
        (self.home / '.agents').mkdir()
        outside = self.root / 'outside'
        outside.mkdir()
        result = self.run_helper(INSTALL_TEST_ACTION='substitute', INSTALL_TEST_OUTSIDE=str(outside))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertTrue((self.home / 'displaced-agents').is_dir())
        self.assertFalse((self.home / '.claude').exists())

    def test_legacy_settings_are_not_silently_ignored(self):
        result = self.run_helper(CLONEGROWN_HOME=str(self.root / 'old-installation'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('legacy installer settings', result.stderr)
        self.assertFalse(self.log.exists())
        self.assertFalse((self.home / '.claude').exists())

    def test_missing_skill_source_refuses_before_package_install(self):
        (self.source / 'SKILL.md').unlink()
        self.assertNotEqual(self.run_helper().returncode, 0)
        self.assertFalse(self.log.exists())
