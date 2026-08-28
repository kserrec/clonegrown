from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from support import filesystem_accepts_non_utf8_names


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = PROJECT_ROOT / "install.sh"
MARKER = ".clonegrown-install"


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def git(repo: Path, *args: str) -> None:
    result = run(["git", *args], cwd=repo)
    if result.returncode:
        raise AssertionError(result.stderr)


@dataclass
class InstallFixture:
    root: Path
    home: Path
    source_repo: Path
    install_root: Path
    bin_dir: Path

    @property
    def wrapper(self) -> Path:
        return self.bin_dir / "clonegrown"

    @property
    def claude_skill(self) -> Path:
        return self.home / ".claude" / "skills" / "clonegrown"

    @property
    def codex_skill(self) -> Path:
        return self.home / ".agents" / "skills" / "clonegrown"

    def targets(self) -> dict[str, Path]:
        return {
            "source": self.install_root,
            "command": self.wrapper,
            "claude-skill": self.claude_skill,
            "codex-skill": self.codex_skill,
        }

    def environment(self, **overrides: str) -> dict[str, str]:
        env = os.environ.copy()
        env.update({
            "HOME": str(self.home),
            "CLONEGROWN_HOME": str(self.install_root),
            "CLONEGROWN_BIN_DIR": str(self.bin_dir),
            "CLONEGROWN_REPO_URL": str(self.source_repo),
            "CLONEGROWN_REF": "main",
        })
        env.update(overrides)
        return env

    def write_version(self, version: str, *, initial: bool = False) -> None:
        package = self.source_repo / "clonegrown"
        if initial:
            self.source_repo.mkdir(parents=True)
            package.mkdir()
            git(self.source_repo, "init", "-q", "-b", "main")
            git(self.source_repo, "config", "user.name", "Clonegrown Installer Test")
            git(self.source_repo, "config", "user.email", "installer@example.test")
        (package / "__init__.py").write_text(f'VERSION = "{version}"\n', encoding="utf-8")
        (package / "__main__.py").write_text(
            "import json\n"
            "import os\n"
            "import sys\n"
            "from . import VERSION\n"
            "if sys.argv[1:2] == ['--fixture-report']:\n"
            "    from caller_probe import VALUE\n"
            "    print(json.dumps({\n"
            "        'args': sys.argv[2:],\n"
            "        'caller_probe': VALUE,\n"
            "        'pythonpath': os.environ.get('PYTHONPATH'),\n"
            "        'version': VERSION,\n"
            "    }, sort_keys=True))\n"
            "elif sys.argv[1:2] == ['--fixture-exit']:\n"
            "    raise SystemExit(int(sys.argv[2]))\n"
            "else:\n"
            "    print(VERSION)\n",
            encoding="utf-8",
        )
        (self.source_repo / "SKILL.md").write_text(f"fixture skill {version}\n", encoding="utf-8")
        git(self.source_repo, "add", "clonegrown/__init__.py", "clonegrown/__main__.py", "SKILL.md")
        git(self.source_repo, "commit", "-q", "-m", version)


def make_fixture(root: Path, name: str, version: str = "v1") -> InstallFixture:
    case = root / name
    fixture = InstallFixture(
        root=case,
        home=case / "throwaway home",
        source_repo=case / "source repo",
        install_root=case / "installed source",
        bin_dir=case / "throwaway home" / ".local" / "bin",
    )
    fixture.home.mkdir(parents=True)
    fixture.write_version(version, initial=True)
    return fixture


def run_installer(fixture: InstallFixture, **overrides: str) -> subprocess.CompletedProcess[str]:
    return run(["sh", str(INSTALLER)], cwd=PROJECT_ROOT, env=fixture.environment(**overrides))


class InstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()  # macOS: TMPDIR is a symlink; the installer prints real paths

    def marker_id(self, target: Path, kind: str) -> str:
        lines = (target / MARKER).read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "clonegrown-installer=v1")
        self.assertRegex(lines[1], r"^installation_id=[0-9a-f]{32}$")
        self.assertEqual(lines[2], f"target={kind}")
        return lines[1].removeprefix("installation_id=")

    def wrapper_id(self, wrapper: Path) -> str:
        lines = wrapper.read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[0], "#!/bin/sh")
        self.assertEqual(lines[1], "# clonegrown-installer=v1")
        self.assertRegex(lines[2], r"^# installation_id=[0-9a-f]{32}$")
        self.assertEqual(lines[3], "# target=command")
        return lines[2].removeprefix("# installation_id=")

    def assert_installed(self, fixture: InstallFixture, version: str) -> str:
        ids = {
            self.marker_id(fixture.install_root, "source"),
            self.wrapper_id(fixture.wrapper),
            self.marker_id(fixture.claude_skill, "claude-skill"),
            self.marker_id(fixture.codex_skill, "codex-skill"),
        }
        self.assertEqual(len(ids), 1)
        self.assertEqual((fixture.claude_skill / "SKILL.md").read_text(encoding="utf-8"),
                         f"fixture skill {version}\n")
        self.assertEqual((fixture.codex_skill / "SKILL.md").read_text(encoding="utf-8"),
                         f"fixture skill {version}\n")
        command = run([str(fixture.wrapper), "--version"], cwd=fixture.root)
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertEqual(command.stdout.strip(), version)
        return ids.pop()

    def stage_reoccupying_path(
        self,
        fixture: InstallFixture,
        *,
        fail_kind: str = "",
    ) -> tuple[Path, str]:
        """Return a PATH whose Python wrapper recreates each vacated publication stage."""
        fake_bin = fixture.root / f"fake-python-{fail_kind or 'success'}"
        fake_bin.mkdir()
        records = fixture.root / f"stage-records-{fail_kind or 'success'}"
        records.mkdir()
        real_python = shutil.which("python3")
        self.assertIsNotNone(real_python)
        fake_python = fake_bin / "python3"
        fake_python.write_text(
            "#!/bin/sh\n"
            f"real_python={shlex.quote(str(real_python))}\n"
            f"record_dir={shlex.quote(str(records))}\n"
            f"fail_kind={shlex.quote(fail_kind)}\n"
            "kind=\n"
            "if [ \"$#\" -eq 9 ] && [ \"$1\" = - ]; then\n"
            "  case \"$2\" in\n"
            "    */.clonegrown-source.new.*) kind=source ;;\n"
            "    */.clonegrown-command.new.*) kind=command ;;\n"
            "    */.clonegrown-claude.new.*) kind=claude-skill ;;\n"
            "    */.clonegrown-codex.new.*) kind=codex-skill ;;\n"
            "  esac\n"
            "fi\n"
            "if [ -n \"$kind\" ]; then\n"
            "  \"$real_python\" \"$@\" || exit $?\n"
            "  if [ \"$kind\" = command ]; then\n"
            "    printf '%s\\n' \"unowned $kind stage replacement\" > \"$2\"\n"
            "  else\n"
            "    mkdir \"$2\" || exit $?\n"
            "    printf '%s\\n' \"unowned $kind stage replacement\" > \"$2/sentinel.txt\"\n"
            "  fi\n"
            "  printf '%s\\n' \"$2\" > \"$record_dir/$kind.path\"\n"
            "  if [ \"$kind\" = \"$fail_kind\" ]; then\n"
            "    exit 73\n"
            "  fi\n"
            "  exit 0\n"
            "fi\n"
            "exec \"$real_python\" \"$@\"\n",
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        path = f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"
        return records, path

    def backup_reoccupying_path(
        self,
        fixture: InstallFixture,
        kind: str,
    ) -> tuple[Path, str]:
        """Replace one reserved backup object before the relocation helper runs."""
        fake_bin = fixture.root / f"fake-backup-python-{kind}"
        fake_bin.mkdir()
        record = fixture.root / f"{kind}-backup.path"
        real_python = shutil.which("python3")
        real_rm = shutil.which("rm")
        real_mkdir = shutil.which("mkdir")
        self.assertTrue(all((real_python, real_rm, real_mkdir)))
        fake_python = fake_bin / "python3"
        fake_python.write_text(
            "#!/bin/sh\n"
            f"real_python={shlex.quote(str(real_python))}\n"
            f"real_rm={shlex.quote(str(real_rm))}\n"
            f"real_mkdir={shlex.quote(str(real_mkdir))}\n"
            f"selected={shlex.quote(kind)}\n"
            f"record={shlex.quote(str(record))}\n"
            "kind=\n"
            "if [ \"$#\" -eq 9 ] && [ \"$1\" = - ]; then\n"
            "  case \"$4\" in\n"
            "    */.clonegrown-source.backup.*) kind=source ;;\n"
            "    */.clonegrown-command.backup.*) kind=command ;;\n"
            "    */.clonegrown-claude.backup.*) kind=claude-skill ;;\n"
            "    */.clonegrown-codex.backup.*) kind=codex-skill ;;\n"
            "  esac\n"
            "fi\n"
            "if [ \"$kind\" = \"$selected\" ]; then\n"
            "  if [ \"$kind\" = command ]; then\n"
            "    \"$real_rm\" -f \"$4\" || exit $?\n"
            "    printf '%s\\n' \"unowned $kind backup replacement\" > \"$4\"\n"
            "  else\n"
            "    \"$real_rm\" -rf \"$4\" || exit $?\n"
            "    \"$real_mkdir\" \"$4\" || exit $?\n"
            "    printf '%s\\n' \"unowned $kind backup replacement\" > \"$4/sentinel.txt\"\n"
            "  fi\n"
            "  printf '%s\\n' \"$4\" > \"$record\"\n"
            "fi\n"
            "exec \"$real_python\" \"$@\"\n",
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        return record, f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"

    def assert_stage_replacement_preserved(self, records: Path, kind: str) -> Path:
        record = records / f"{kind}.path"
        self.assertTrue(record.is_file(), f"mv did not record the {kind} stage")
        stage = Path(record.read_text(encoding="utf-8").rstrip("\n"))
        sentinel = stage if kind == "command" else stage / "sentinel.txt"
        self.assertTrue(sentinel.is_file(), f"installer deleted the replacement at {stage}")
        self.assertEqual(
            sentinel.read_text(encoding="utf-8"),
            f"unowned {kind} stage replacement\n",
        )
        return stage

    def test_first_install_and_owned_update_preserve_one_identity(self) -> None:
        fixture = make_fixture(self.root, "owned update 'quoted' $dollar")

        first = run_installer(fixture)
        self.assertEqual(first.returncode, 0, first.stderr)
        installation_id = self.assert_installed(fixture, "v1")

        fixture.write_version("v2")
        second = run_installer(fixture)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.assert_installed(fixture, "v2"), installation_id)

    def test_wrapper_preserves_literal_root_and_process_contract(self) -> None:
        fixture = make_fixture(
            self.root,
            "launcher : space $dollar 'single' \"double\" `backtick` [glob]*?",
        )
        first = run_installer(fixture)
        self.assertEqual(first.returncode, 0, first.stderr)
        installation_id = self.assert_installed(fixture, "v1")

        caller_one = self.root / "caller PYTHONPATH one"
        caller_two = self.root / "caller PYTHONPATH two"
        caller_one.mkdir()
        caller_two.mkdir()
        (caller_one / "caller_probe.py").write_text(
            "VALUE = 'caller PYTHONPATH remains active'\n",
            encoding="utf-8",
        )
        shadow_package = caller_one / "clonegrown"
        shadow_package.mkdir()
        (shadow_package / "__init__.py").write_text(
            "raise RuntimeError('caller PYTHONPATH shadowed the installed package')\n",
            encoding="utf-8",
        )
        caller_pythonpath = os.pathsep.join((str(caller_one), str(caller_two)))
        command_environment = os.environ.copy()
        command_environment["PYTHONPATH"] = caller_pythonpath
        arguments = [
            "space argument",
            "$dollar",
            "'single quote'",
            '"double quote"',
            "`backtick`",
            "[glob]*?",
            "colon:value",
            "",
        ]

        def assert_launcher(version: str) -> None:
            wrapper_text = fixture.wrapper.read_text(encoding="utf-8")
            self.assertNotIn("PYTHONPATH=", wrapper_text)
            report = run(
                [str(fixture.wrapper), "--fixture-report", *arguments],
                cwd=fixture.root,
                env=command_environment,
            )
            self.assertEqual(report.returncode, 0, report.stderr)
            self.assertEqual(
                json.loads(report.stdout),
                {
                    "args": arguments,
                    "caller_probe": "caller PYTHONPATH remains active",
                    "pythonpath": caller_pythonpath,
                    "version": version,
                },
            )
            intentional_exit = run(
                [str(fixture.wrapper), "--fixture-exit", "37"],
                cwd=fixture.root,
                env=command_environment,
            )
            self.assertEqual(intentional_exit.returncode, 37, intentional_exit.stderr)

        assert_launcher("v1")
        fixture.write_version("v2")
        update = run_installer(fixture)
        self.assertEqual(update.returncode, 0, update.stderr)
        self.assertEqual(self.assert_installed(fixture, "v2"), installation_id)
        assert_launcher("v2")

    def test_non_utf8_paths_are_preserved_as_filesystem_bytes(self) -> None:
        if not filesystem_accepts_non_utf8_names(self.root):
            self.skipTest("this filesystem rejects non-UTF-8 file names")
        # Every path the installer prints back through Python (preflight record,
        # PATH guidance) carries a byte no UTF-8 decoder accepts; this pins
        # byte-oriented output regardless of the developer's locale.
        fixture = make_fixture(self.root, "non-utf8-paths")
        root_bytes = os.fsencode(str(fixture.root))
        install_bytes = root_bytes + b"/installed-\xff-source"
        bin_bytes = root_bytes + b"/bin-\xfe-dir"
        fixture.install_root = Path(os.fsdecode(install_bytes))
        fixture.bin_dir = Path(os.fsdecode(bin_bytes))

        # Under a C or C.UTF-8 locale Python's stdout would use surrogateescape
        # and hide a text-mode print; force the strict handler every locale
        # can otherwise select.
        installed = subprocess.run(
            ["sh", str(INSTALLER)],
            cwd=PROJECT_ROOT,
            env=fixture.environment(PYTHONIOENCODING="utf-8:strict"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(
            installed.returncode,
            0,
            installed.stderr.decode("utf-8", "backslashreplace"),
        )
        self.assertTrue(os.path.isdir(install_bytes))
        self.assertTrue(os.path.isfile(bin_bytes + b"/clonegrown"))
        guidance = [line for line in installed.stdout.splitlines() if line.startswith(b"  export PATH=")]
        self.assertEqual(len(guidance), 1, installed.stdout.decode("utf-8", "backslashreplace"))
        self.assertEqual(guidance[0], b"  export PATH='" + bin_bytes + b"':\"$PATH\"")

        command = run([str(fixture.wrapper), "--version"], cwd=fixture.root)
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertEqual(command.stdout.strip(), "v1")

        # The wrapper's body now carries the raw path bytes; an owned update
        # must read only its ASCII header as ownership evidence.
        fixture.write_version("v2")
        updated = subprocess.run(
            ["sh", str(INSTALLER)],
            cwd=PROJECT_ROOT,
            env=fixture.environment(PYTHONIOENCODING="utf-8:strict"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(updated.returncode, 0, updated.stderr.decode("utf-8", "backslashreplace"))
        command = run([str(fixture.wrapper), "--version"], cwd=fixture.root)
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertEqual(command.stdout.strip(), "v2")
        wrapper_lines = fixture.wrapper.read_bytes().splitlines()
        self.assertEqual(wrapper_lines[:2], [b"#!/bin/sh", b"# clonegrown-installer=v1"])
        wrapper_id = wrapper_lines[2].decode("ascii").removeprefix("# installation_id=")
        ids = {
            self.marker_id(fixture.install_root, "source"),
            wrapper_id,
            self.marker_id(fixture.claude_skill, "claude-skill"),
            self.marker_id(fixture.codex_skill, "codex-skill"),
        }
        self.assertEqual(len(ids), 1)

    def test_printed_path_guidance_is_shell_safe(self) -> None:
        fixture = make_fixture(self.root, "path-guidance")
        fixture.bin_dir = fixture.root / (
            "bin space $dollar 'single' \"double\" "
            "$(printf side-effect > dollar-effect) "
            "`printf side-effect > backtick-effect` [glob]*?"
        )
        dollar_effect = fixture.root / "dollar-effect"
        backtick_effect = fixture.root / "backtick-effect"

        installed = run_installer(fixture)

        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertFalse(dollar_effect.exists(), "installer evaluated the binary directory as shell code")
        self.assertFalse(backtick_effect.exists(), "installer evaluated the binary directory as shell code")
        guidance = [
            line for line in installed.stdout.splitlines()
            if line.startswith("  export PATH=")
        ]
        self.assertEqual(len(guidance), 1, installed.stdout)

        shell = shutil.which("sh")
        self.assertIsNotNone(shell)
        original_path = os.pathsep.join((
            str(fixture.root / "existing PATH one"),
            str(fixture.root / "existing [glob]*?"),
        ))
        command_environment = os.environ.copy()
        command_environment.update({"PATH": original_path, "dollar": "PARAMETER_EXPANDED"})
        executed = run(
            [str(shell), "-c", f"{guidance[0]}\nprintf '%s\\n' \"$PATH\"\n"],
            cwd=fixture.root,
            env=command_environment,
        )

        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertFalse(dollar_effect.exists(), "printed guidance ran dollar command substitution")
        self.assertFalse(backtick_effect.exists(), "printed guidance ran backtick command substitution")
        self.assertEqual(executed.stdout, f"{fixture.bin_dir}{os.pathsep}{original_path}\n")
        self.assertEqual(
            guidance[0],
            f"  export PATH={shlex.quote(str(fixture.bin_dir))}:\"$PATH\"",
        )

    def test_colon_bin_directory_prints_a_safe_full_path_instead_of_invalid_path_guidance(self) -> None:
        fixture = make_fixture(self.root, "colon-path-guidance")
        fixture.bin_dir = fixture.root / "bin:with-colon $dollar 'quote'"

        installed = run_installer(fixture)

        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertNotIn("  export PATH=", installed.stdout)
        self.assertIn("POSIX PATH treats as a separator", installed.stdout)
        commands = [line.removeprefix("  ") for line in installed.stdout.splitlines()
                    if line.startswith("  '") and line.endswith(" --help")]
        self.assertEqual(len(commands), 1, installed.stdout)
        executed = run(["/bin/sh", "-c", commands[0]], cwd=fixture.root)
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertEqual(executed.stdout.strip(), "v1")

    def test_each_existing_unowned_target_is_preserved(self) -> None:
        for kind in ("source", "command", "claude-skill", "codex-skill"):
            with self.subTest(kind=kind):
                fixture = make_fixture(self.root, f"unowned-{kind}")
                target = fixture.targets()[kind]
                if kind == "command":
                    target.parent.mkdir(parents=True)
                    target.write_text("user command sentinel\n", encoding="utf-8")
                    sentinel = target
                else:
                    target.mkdir(parents=True)
                    sentinel = target / "sentinel.txt"
                    sentinel.write_text("user directory sentinel\n", encoding="utf-8")

                result = run_installer(fixture)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not owned by Clonegrown", result.stderr)
                expected = "user command sentinel\n" if kind == "command" else "user directory sentinel\n"
                self.assertEqual(sentinel.read_text(encoding="utf-8"), expected)

    def test_each_symlink_target_is_refused_without_touching_its_referent(self) -> None:
        for kind in ("source", "command", "claude-skill", "codex-skill"):
            with self.subTest(kind=kind):
                fixture = make_fixture(self.root, f"symlink-{kind}")
                target = fixture.targets()[kind]
                target.parent.mkdir(parents=True, exist_ok=True)
                referent = fixture.root / f"{kind}-referent"
                if kind == "command":
                    referent.write_text("referent file\n", encoding="utf-8")
                    target.symlink_to(referent)
                    sentinel = referent
                else:
                    referent.mkdir()
                    sentinel = referent / "sentinel.txt"
                    sentinel.write_text("referent directory\n", encoding="utf-8")
                    target.symlink_to(referent, target_is_directory=True)

                result = run_installer(fixture)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("symlink", result.stderr)
                self.assertTrue(target.is_symlink())
                expected = "referent file\n" if kind == "command" else "referent directory\n"
                self.assertEqual(sentinel.read_text(encoding="utf-8"), expected)

    def test_home_directory_is_refused_as_install_root(self) -> None:
        fixture = make_fixture(self.root, "home-root")
        sentinel = fixture.home / "sentinel.txt"
        sentinel.write_text("keep home\n", encoding="utf-8")

        result = run_installer(fixture, CLONEGROWN_HOME=str(fixture.home))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("home directory", result.stderr)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep home\n")

    def test_parent_child_target_aliases_are_refused(self) -> None:
        cases = {
            "source-contains-skill": lambda fixture: {
                "CLONEGROWN_HOME": str(fixture.home / ".agents" / "skills")
            },
            "wrapper-inside-source": lambda fixture: {
                "CLONEGROWN_HOME": str(fixture.root / "overlap"),
                "CLONEGROWN_BIN_DIR": str(fixture.root / "overlap"),
            },
            "case-folded-skill-alias": lambda fixture: {
                "CLONEGROWN_HOME": str(fixture.home / ".AGENTS" / "SKILLS" / "CLONEGROWN")
            },
        }
        for name, overrides in cases.items():
            with self.subTest(name=name):
                fixture = make_fixture(self.root, name)
                result = run_installer(fixture, **overrides(fixture))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("overlap", result.stderr)

    def assert_canonicalized_line_break_refused(
        self,
        line_break: str,
        label: str,
    ) -> None:
        fixture = make_fixture(self.root, f"canonical-{label}")
        canonical_parent = fixture.root / f"canonical{line_break}parent"
        canonical_parent.mkdir()
        lexical_parent = fixture.root / f"{label}-free-parent-link"
        lexical_parent.symlink_to(canonical_parent, target_is_directory=True)
        lexical_install = lexical_parent / "installed source"
        canonical_install = canonical_parent / "installed source"

        destinations = {
            "source": canonical_install,
            "command": fixture.wrapper,
            "claude-skill": fixture.claude_skill,
            "codex-skill": fixture.codex_skill,
        }
        sentinels: dict[Path, str] = {}
        for kind, target in destinations.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            sentinel = target.parent / f"{kind}-parent-sentinel.txt"
            content = f"preserve {kind} parent\n"
            sentinel.write_text(content, encoding="utf-8")
            sentinels[sentinel] = content

        fake_bin = fixture.root / "line-break-fake-bin"
        fake_bin.mkdir()
        mkdir_record = fixture.root / "line-break-reached-mkdir"
        fake_mkdir = fake_bin / "mkdir"
        fake_mkdir.write_text(
            "#!/bin/sh\n"
            f": > {shlex.quote(str(mkdir_record))}\n"
            "exit 97\n",
            encoding="utf-8",
        )
        fake_mkdir.chmod(0o755)
        path = f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"

        result = run_installer(
            fixture,
            CLONEGROWN_HOME=str(lexical_install),
            PATH=path,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("installation source contains a line break", result.stderr)
        self.assertFalse(mkdir_record.exists(), "malformed preflight reached mkdir")
        self.assertTrue(lexical_parent.is_symlink())
        for target in destinations.values():
            self.assertFalse(target.exists(), f"preflight changed destination {target}")
        for sentinel, content in sentinels.items():
            self.assertEqual(sentinel.read_text(encoding="utf-8"), content)

    def test_canonicalized_line_break_is_refused_before_destination_mutation(self) -> None:
        for label, line_break in (("newline", "\n"), ("carriage-return", "\r")):
            with self.subTest(label=label):
                self.assert_canonicalized_line_break_refused(line_break, label)

    def test_malformed_preflight_records_are_refused_before_destination_mutation(self) -> None:
        mutations = {
            "empty-install": "1s/.*//",
            "empty-bin": "2s/.*//",
            "empty-wrapper": "3s/.*//",
            "empty-claude": "4s/.*//",
            "empty-codex": "5s/.*//",
            "invalid-id": "6s/.*/not-an-installation-id/",
            "uppercase-id": "6s/.*/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/",
            "short-id": "6s/.*/0123456789abcdef/",
        }
        for mutation in (*mutations, "extra-field", "partial-field", "nul-partial"):
            with self.subTest(mutation=mutation):
                fixture = make_fixture(self.root, f"malformed-preflight-{mutation}")
                fake_bin = fixture.root / "fake-preflight-bin"
                fake_bin.mkdir()
                mkdir_record = fixture.root / "malformed-preflight-reached-mkdir"
                real_python = shutil.which("python3")
                self.assertIsNotNone(real_python)

                fake_python = fake_bin / "python3"
                mutation_cases = "".join(
                    f"    {name}) \"$real_python\" \"$@\" | sed {shlex.quote(expression)} ;;\n"
                    for name, expression in mutations.items()
                )
                fake_python.write_text(
                    "#!/bin/sh\n"
                    "set -eu\n"
                    f"real_python={shlex.quote(str(real_python))}\n"
                    f"preflight_home={shlex.quote(str(fixture.home))}\n"
                    "mutation=${CLONEGROWN_TEST_PREFLIGHT_MUTATION:-}\n"
                    "if [ \"$#\" -eq 4 ] && [ \"$1\" = - ] && [ \"$2\" = \"$preflight_home\" ]; then\n"
                    "  case \"$mutation\" in\n"
                    + mutation_cases
                    + "    extra-field)\n"
                    "      \"$real_python\" \"$@\" || exit $?\n"
                    "      printf '%s\\n' unexpected-extra-field\n"
                    "      ;;\n"
                    "    partial-field)\n"
                    "      \"$real_python\" \"$@\" || exit $?\n"
                    "      printf '%s' unexpected-partial-field\n"
                    "      ;;\n"
                    "    nul-partial)\n"
                    "      \"$real_python\" \"$@\" || exit $?\n"
                    "      printf '\\000'\n"
                    "      ;;\n"
                    "  esac\n"
                    "  exit $?\n"
                    "fi\n"
                    "exec \"$real_python\" \"$@\"\n",
                    encoding="utf-8",
                )
                fake_python.chmod(0o755)

                fake_mkdir = fake_bin / "mkdir"
                fake_mkdir.write_text(
                    "#!/bin/sh\n"
                    f": > {shlex.quote(str(mkdir_record))}\n"
                    "exit 98\n",
                    encoding="utf-8",
                )
                fake_mkdir.chmod(0o755)
                path = f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"

                result = run_installer(
                    fixture,
                    PATH=path,
                    CLONEGROWN_TEST_PREFLIGHT_MUTATION=mutation,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("preflight returned", result.stderr)
                self.assertFalse(mkdir_record.exists(), "malformed preflight reached mkdir")
                for target in fixture.targets().values():
                    self.assertFalse(target.exists(), f"preflight changed destination {target}")

    def test_mismatched_installation_identity_refuses_update_before_changes(self) -> None:
        fixture = make_fixture(self.root, "identity-mismatch")
        first = run_installer(fixture)
        self.assertEqual(first.returncode, 0, first.stderr)
        installation_id = self.assert_installed(fixture, "v1")
        fixture.write_version("v2")
        marker = fixture.codex_skill / MARKER
        lines = marker.read_text(encoding="utf-8").splitlines()
        replacement_id = "0" * 32 if installation_id != "0" * 32 else "1" * 32
        lines[1] = "installation_id=" + replacement_id
        marker.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = run_installer(fixture)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("different installation identities", result.stderr)
        command = run([str(fixture.wrapper), "--version"], cwd=fixture.root)
        self.assertEqual(command.stdout.strip(), "v1")
        self.assertEqual((fixture.claude_skill / "SKILL.md").read_text(encoding="utf-8"),
                         "fixture skill v1\n")
        self.assertEqual((fixture.codex_skill / "SKILL.md").read_text(encoding="utf-8"),
                         "fixture skill v1\n")

    def test_interrupted_update_restores_all_previous_targets(self) -> None:
        fixture = make_fixture(self.root, "interrupted")
        first = run_installer(fixture)
        self.assertEqual(first.returncode, 0, first.stderr)
        installation_id = self.assert_installed(fixture, "v1")
        preserved = fixture.install_root / "local-preserved.txt"
        preserved.write_text("restore this whole directory\n", encoding="utf-8")
        fixture.write_version("v2")

        fake_bin = fixture.root / "fake-bin"
        fake_bin.mkdir()
        failure_record = fixture.root / "mv-failed"
        real_python = shutil.which("python3")
        self.assertIsNotNone(real_python)
        fake_python = fake_bin / "python3"
        fake_python.write_text(
            "#!/bin/sh\n"
            f"real_python={shlex.quote(str(real_python))}\n"
            f"if [ \"$#\" -eq 9 ] && [ \"$4\" = {shlex.quote(str(fixture.claude_skill))} ]; then\n"
            "  case \"$2\" in\n"
            "    */.clonegrown-claude.new.*)\n"
            f"      if [ ! -e {shlex.quote(str(failure_record))} ]; then\n"
            "        \"$real_python\" \"$@\" || exit $?\n"
            f"        : > {shlex.quote(str(failure_record))}\n"
            "        kill -TERM \"$PPID\"\n"
            "        exit 0\n"
            "      fi\n"
            "      ;;\n"
            "  esac\n"
            "fi\n"
            "exec \"$real_python\" \"$@\"\n",
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        path = f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"

        interrupted = run_installer(fixture, PATH=path)

        self.assertNotEqual(interrupted.returncode, 0)
        self.assertTrue(failure_record.is_file())
        self.assertEqual(self.assert_installed(fixture, "v1"), installation_id)
        self.assertEqual(preserved.read_text(encoding="utf-8"), "restore this whole directory\n")
        for parent in {
            fixture.install_root.parent,
            fixture.wrapper.parent,
            fixture.claude_skill.parent,
            fixture.codex_skill.parent,
        }:
            leftovers = list(parent.glob(".clonegrown-*.new.*")) + list(parent.glob(".clonegrown-*.backup.*"))
            self.assertEqual(leftovers, [])

    def test_reoccupied_stage_names_are_preserved_after_success(self) -> None:
        fixture = make_fixture(self.root, "reoccupied-success")
        records, path = self.stage_reoccupying_path(fixture)

        result = run_installer(fixture, PATH=path)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_installed(fixture, "v1")
        for kind in fixture.targets():
            with self.subTest(kind=kind):
                self.assert_stage_replacement_preserved(records, kind)
        self.assertNotIn("preserved unexpected object", result.stderr)

    def test_reoccupied_stage_names_are_preserved_during_rollback(self) -> None:
        publication_order = ("source", "command", "claude-skill", "codex-skill")
        for failed_index, kind in enumerate(publication_order):
            with self.subTest(kind=kind):
                fixture = make_fixture(self.root, f"reoccupied-rollback-{kind}")
                first = run_installer(fixture)
                self.assertEqual(first.returncode, 0, first.stderr)
                installation_id = self.assert_installed(fixture, "v1")
                fixture.write_version("v2")
                records, path = self.stage_reoccupying_path(fixture, fail_kind=kind)

                failed = run_installer(fixture, PATH=path)

                self.assertNotEqual(failed.returncode, 0)
                self.assertEqual(self.assert_installed(fixture, "v1"), installation_id)
                for published_kind in publication_order[:failed_index + 1]:
                    self.assert_stage_replacement_preserved(records, published_kind)
                self.assertNotIn("preserved unexpected object", failed.stderr)

    def test_reoccupied_backup_reservations_are_preserved_and_update_rolls_back(self) -> None:
        for kind in ("source", "command", "claude-skill", "codex-skill"):
            with self.subTest(kind=kind):
                fixture = make_fixture(self.root, f"reoccupied-backup-{kind}")
                first = run_installer(fixture)
                self.assertEqual(first.returncode, 0, first.stderr)
                installation_id = self.assert_installed(fixture, "v1")
                fixture.write_version("v2")
                record, path = self.backup_reoccupying_path(fixture, kind)

                failed = run_installer(fixture, PATH=path)

                self.assertNotEqual(failed.returncode, 0)
                self.assertIn("relocation refused", failed.stderr)
                self.assertIn("target is still in place", failed.stderr)
                self.assertNotIn("remains in backup", failed.stderr)
                self.assertNotIn("could not restore", failed.stderr)
                self.assertEqual(self.assert_installed(fixture, "v1"), installation_id)
                self.assertTrue(record.is_file())
                backup = Path(record.read_text(encoding="utf-8").rstrip("\n"))
                sentinel = backup if kind == "command" else backup / "sentinel.txt"
                self.assertEqual(
                    sentinel.read_text(encoding="utf-8"),
                    f"unowned {kind} backup replacement\n",
                )

    def backup_gutting_path(
        self,
        fixture: InstallFixture,
        *,
        trigger: str,
        fail_kind: str = "",
    ) -> tuple[Path, str]:
        """Return a PATH whose Python wrapper guts every backup object in place.

        The backup keeps its device, inode, and type but loses its marker and
        contents, which is what a same-user delete-and-recreate looks like when
        the filesystem hands the freed inode number to the next object. With
        ``trigger="cleanup"`` each backup is gutted when the committed cleanup
        helper is about to examine it. With ``trigger="publication"`` every
        backup is gutted when the ``fail_kind`` target's publication runs, and
        that publication then fails so rollback has to decide what to restore.
        """
        fake_bin = fixture.root / f"fake-gut-python-{trigger}-{fail_kind or 'all'}"
        fake_bin.mkdir()
        records = fixture.root / f"gut-records-{trigger}-{fail_kind or 'all'}"
        records.mkdir()
        real_python = shutil.which("python3")
        real_rm = shutil.which("rm")
        real_find = shutil.which("find")
        self.assertTrue(all((real_python, real_rm, real_find)))
        gut = (
            "gut_backup() {\n"
            "  case \"$1\" in\n"
            "    */.clonegrown-source.backup.*) gut_kind=source ;;\n"
            "    */.clonegrown-command.backup.*) gut_kind=command ;;\n"
            "    */.clonegrown-claude.backup.*) gut_kind=claude-skill ;;\n"
            "    */.clonegrown-codex.backup.*) gut_kind=codex-skill ;;\n"
            "    *) return 0 ;;\n"
            "  esac\n"
            "  [ ! -e \"$record_dir/$gut_kind.path\" ] || return 0\n"
            "  if [ -d \"$1\" ]; then\n"
            "    \"$real_find\" \"$1\" -mindepth 1 -delete || exit $?\n"
            "    printf '%s\\n' \"unowned $gut_kind object at backup name\" > \"$1/sentinel.txt\"\n"
            "  else\n"
            "    printf '%s\\n' \"unowned $gut_kind object at backup name\" > \"$1\"\n"
            "  fi\n"
            "  printf '%s\\n' \"$1\" > \"$record_dir/$gut_kind.path\"\n"
            "}\n"
        )
        if trigger == "cleanup":
            hook = (
                "if [ \"$#\" -eq 6 ] && [ \"$1\" = - ]; then\n"
                "  gut_backup \"$2\"\n"
                "fi\n"
            )
        else:
            stage_glob = {
                "source": "source", "command": "command",
                "claude-skill": "claude", "codex-skill": "codex",
            }[fail_kind]
            hook = (
                "if [ \"$#\" -eq 9 ] && [ \"$1\" = - ]; then\n"
                "  case \"$2\" in\n"
                f"    */.clonegrown-{stage_glob}.new.*)\n"
                "      \"$real_python\" \"$@\" || exit $?\n"
                "      for parent in \"$source_parent\" \"$bin_dir\" \"$claude_parent\" \"$codex_parent\"; do\n"
                "        for candidate in \"$parent\"/.clonegrown-*.backup.*; do\n"
                "          [ -e \"$candidate\" ] && gut_backup \"$candidate\"\n"
                "        done\n"
                "      done\n"
                "      exit 73\n"
                "      ;;\n"
                "  esac\n"
                "fi\n"
            )
        fake_python = fake_bin / "python3"
        fake_python.write_text(
            "#!/bin/sh\n"
            f"real_python={shlex.quote(str(real_python))}\n"
            f"real_rm={shlex.quote(str(real_rm))}\n"
            f"real_find={shlex.quote(str(real_find))}\n"
            f"record_dir={shlex.quote(str(records))}\n"
            f"source_parent={shlex.quote(str(fixture.install_root.parent))}\n"
            f"bin_dir={shlex.quote(str(fixture.bin_dir))}\n"
            f"claude_parent={shlex.quote(str(fixture.claude_skill.parent))}\n"
            f"codex_parent={shlex.quote(str(fixture.codex_skill.parent))}\n"
            + gut + hook +
            "exec \"$real_python\" \"$@\"\n",
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        return records, f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"

    def assert_gutted_backup_preserved(self, records: Path, kind: str) -> Path:
        record = records / f"{kind}.path"
        self.assertTrue(record.is_file(), f"the {kind} backup was never gutted")
        backup = Path(record.read_text(encoding="utf-8").rstrip("\n"))
        sentinel = backup if kind == "command" else backup / "sentinel.txt"
        self.assertEqual(
            sentinel.read_text(encoding="utf-8"),
            f"unowned {kind} object at backup name\n",
            f"installer removed the unowned object at the {kind} backup name",
        )
        return backup

    def test_committed_cleanup_preserves_backups_that_lost_ownership_evidence(self) -> None:
        fixture = make_fixture(self.root, "gutted-committed-backups")
        first = run_installer(fixture)
        self.assertEqual(first.returncode, 0, first.stderr)
        installation_id = self.assert_installed(fixture, "v1")
        fixture.write_version("v2")
        records, path = self.backup_gutting_path(fixture, trigger="cleanup")

        updated = run_installer(fixture, PATH=path)

        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertEqual(self.assert_installed(fixture, "v2"), installation_id)
        for kind in fixture.targets():
            with self.subTest(kind=kind):
                self.assert_gutted_backup_preserved(records, kind)
        self.assertEqual(updated.stderr.count("preserved unexpected object"), 4, updated.stderr)

    def test_rollback_never_restores_a_backup_that_lost_ownership_evidence(self) -> None:
        publication_order = ("source", "command", "claude-skill", "codex-skill")
        for failed_index, fail_kind in enumerate(publication_order):
            with self.subTest(fail_kind=fail_kind):
                fixture = make_fixture(self.root, f"gutted-rollback-{fail_kind}")
                first = run_installer(fixture)
                self.assertEqual(first.returncode, 0, first.stderr)
                self.assert_installed(fixture, "v1")
                fixture.write_version("v2")
                records, path = self.backup_gutting_path(
                    fixture, trigger="publication", fail_kind=fail_kind,
                )

                failed = run_installer(fixture, PATH=path)

                self.assertNotEqual(failed.returncode, 0)
                # Every backup taken so far was gutted, so none may be restored
                # and none may be deleted; the targets stay absent.
                for kind in publication_order[:failed_index + 1]:
                    with self.subTest(fail_kind=fail_kind, kind=kind):
                        self.assert_gutted_backup_preserved(records, kind)
                        self.assertFalse(fixture.targets()[kind].exists(),
                                         f"rollback installed an unowned object as the {kind} target")
                # Targets whose backup was never taken keep their v1 objects.
                for kind in publication_order[failed_index + 1:]:
                    with self.subTest(fail_kind=fail_kind, kind=kind):
                        target = fixture.targets()[kind]
                        if kind == "command":
                            self.wrapper_id(target)
                        else:
                            self.marker_id(target, kind)
                self.assertEqual(failed.stderr.count("could not restore previous"),
                                 failed_index + 1, failed.stderr)
                self.assertNotIn("restored where possible\n\n", failed.stderr)

    def test_marker_line_definition_is_shared_by_every_ownership_check(self) -> None:
        # The installer writes three newline-terminated marker lines. A marker
        # that lost its trailing newline is still this installation; a marker
        # with carriage returns or a fourth line is not. Every check must agree,
        # or an update passes preflight and is then refused as "changed". The
        # wrapper header is the same predicate over its first four lines.
        cases = {
            "no-trailing-newline": (lambda data: data.rstrip(b"\n"), True),
            "crlf": (lambda data: data.replace(b"\n", b"\r\n"), False),
            "fourth-line": (lambda data: data + b"extra\n", False),
            "long-body": (lambda data: data + b"# padding\n" * 600, True),
        }
        for name, (mutate, accepted) in cases.items():
            for kind in ("source", "command"):
                if (kind == "command") != (name in ("crlf", "long-body")):
                    continue  # the wrapper body already follows its header
                with self.subTest(case=name, kind=kind):
                    fixture = make_fixture(self.root, f"marker-{name}-{kind}")
                    first = run_installer(fixture)
                    self.assertEqual(first.returncode, 0, first.stderr)
                    installation_id = self.assert_installed(fixture, "v1")
                    fixture.write_version("v2")
                    target = fixture.targets()[kind]
                    evidence = target if kind == "command" else target / MARKER
                    mutated = mutate(evidence.read_bytes())
                    evidence.write_bytes(mutated)

                    result = run_installer(fixture)

                    if accepted:
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(self.assert_installed(fixture, "v2"), installation_id)
                        self.assertNotIn("ownership evidence changed", result.stderr)
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertIn("not owned by Clonegrown", result.stderr)
                        self.assertNotIn("ownership changed after preflight", result.stderr)
                        self.assertNotIn("ownership evidence changed", result.stderr)
                        self.assertEqual(evidence.read_bytes(), mutated)
                        self.assertEqual((fixture.claude_skill / "SKILL.md").read_text(encoding="utf-8"),
                                         "fixture skill v1\n")

    def test_fifo_at_backup_marker_is_preserved_without_blocking(self) -> None:
        fixture = make_fixture(self.root, "fifo-marker")
        first = run_installer(fixture)
        self.assertEqual(first.returncode, 0, first.stderr)
        fixture.write_version("v2")
        fake_bin = fixture.root / "fake-fifo-python"
        fake_bin.mkdir()
        record = fixture.root / "fifo-backup.path"
        real_python = shutil.which("python3")
        real_rm = shutil.which("rm")
        real_mkfifo = shutil.which("mkfifo")
        self.assertTrue(all((real_python, real_rm, real_mkfifo)))
        fake_python = fake_bin / "python3"
        fake_python.write_text(
            "#!/bin/sh\n"
            f"real_python={shlex.quote(str(real_python))}\n"
            f"real_rm={shlex.quote(str(real_rm))}\n"
            f"real_mkfifo={shlex.quote(str(real_mkfifo))}\n"
            f"record={shlex.quote(str(record))}\n"
            "if [ \"$#\" -eq 6 ] && [ \"$1\" = - ]; then\n"
            "  case \"$2\" in\n"
            "    */.clonegrown-source.backup.*)\n"
            "      if [ ! -e \"$record\" ]; then\n"
            f"        \"$real_rm\" -f \"$2/{MARKER}\" || exit $?\n"
            f"        \"$real_mkfifo\" \"$2/{MARKER}\" || exit $?\n"
            "        printf '%s\\n' \"$2\" > \"$record\"\n"
            "      fi\n"
            "      ;;\n"
            "  esac\n"
            "fi\n"
            "exec \"$real_python\" \"$@\"\n",
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        path = f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"

        try:
            updated = subprocess.run(
                ["sh", str(INSTALLER)], cwd=PROJECT_ROOT, env=fixture.environment(PATH=path),
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120,
            )
        except subprocess.TimeoutExpired:
            self.fail("installer blocked on a FIFO at the backup marker path")

        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assert_installed(fixture, "v2")
        backup = Path(record.read_text(encoding="utf-8").rstrip("\n"))
        self.assertTrue((backup / MARKER).is_fifo(), "installer removed the FIFO")
        self.assertIn("preserved unexpected object", updated.stderr)

    def test_closed_stdout_still_removes_the_control_directory(self) -> None:
        # The success banner is printed after the commit. If stdout is already
        # closed, SIGPIPE must reach the EXIT trap rather than end the shell
        # before the private control directory is removed.
        fixture = make_fixture(self.root, "closed-stdout")
        tmpdir = fixture.root / "installer tmp"
        tmpdir.mkdir()
        shell = shutil.which("sh")
        self.assertIsNotNone(shell)

        result = subprocess.run(
            [str(shell), "-c", 'sh "$1" | head -c 1 >/dev/null; exit "${PIPESTATUS:-0}"', "sh", str(INSTALLER)],
            cwd=PROJECT_ROOT,
            env=fixture.environment(TMPDIR=str(tmpdir)),
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

        self.assert_installed(fixture, "v1")
        self.assertEqual(sorted(tmpdir.iterdir()), [], "control directory survived a closed stdout")
        for parent in {fixture.install_root.parent, fixture.wrapper.parent,
                       fixture.claude_skill.parent, fixture.codex_skill.parent}:
            self.assertEqual(list(parent.glob(".clonegrown-*")), [], result.stderr)

    def test_reoccupied_publication_targets_are_preserved(self) -> None:
        for kind in ("source", "command", "claude-skill", "codex-skill"):
            with self.subTest(kind=kind):
                fixture = make_fixture(self.root, f"reoccupied-publication-{kind}")
                fake_bin = fixture.root / "fake-publication-python"
                fake_bin.mkdir()
                record = fixture.root / f"{kind}-publication.path"
                real_python = shutil.which("python3")
                real_mkdir = shutil.which("mkdir")
                self.assertTrue(all((real_python, real_mkdir)))
                fake_python = fake_bin / "python3"
                fake_python.write_text(
                    "#!/bin/sh\n"
                    f"real_python={shlex.quote(str(real_python))}\n"
                    f"real_mkdir={shlex.quote(str(real_mkdir))}\n"
                    f"selected={shlex.quote(kind)}\n"
                    f"record={shlex.quote(str(record))}\n"
                    "kind=\n"
                    "if [ \"$#\" -eq 9 ] && [ \"$1\" = - ]; then\n"
                    "  case \"$2\" in\n"
                    "    */.clonegrown-source.new.*) kind=source ;;\n"
                    "    */.clonegrown-command.new.*) kind=command ;;\n"
                    "    */.clonegrown-claude.new.*) kind=claude-skill ;;\n"
                    "    */.clonegrown-codex.new.*) kind=codex-skill ;;\n"
                    "  esac\n"
                    "fi\n"
                    "if [ \"$kind\" = \"$selected\" ]; then\n"
                    "  if [ \"$kind\" = command ]; then\n"
                    "    printf '%s\\n' \"unowned $kind publication target\" > \"$4\"\n"
                    "  else\n"
                    "    \"$real_mkdir\" \"$4\" || exit $?\n"
                    "    printf '%s\\n' \"unowned $kind publication target\" > \"$4/sentinel.txt\"\n"
                    "  fi\n"
                    "  printf '%s\\n' \"$4\" > \"$record\"\n"
                    "fi\n"
                    "exec \"$real_python\" \"$@\"\n",
                    encoding="utf-8",
                )
                fake_python.chmod(0o755)
                path = f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"

                failed = run_installer(fixture, PATH=path)

                self.assertNotEqual(failed.returncode, 0)
                self.assertIn("destination is occupied", failed.stderr)
                target = fixture.targets()[kind]
                sentinel = target if kind == "command" else target / "sentinel.txt"
                self.assertEqual(
                    sentinel.read_text(encoding="utf-8"),
                    f"unowned {kind} publication target\n",
                )
                for other_kind, other_target in fixture.targets().items():
                    if other_kind != kind:
                        self.assertFalse(other_target.exists(), f"rollback left {other_kind} published")

    def test_reoccupied_rollback_destination_preserves_target_and_old_backup(self) -> None:
        fixture = make_fixture(self.root, "reoccupied-rollback-destination")
        first = run_installer(fixture)
        self.assertEqual(first.returncode, 0, first.stderr)
        preserved = fixture.install_root / "local-preserved.txt"
        preserved.write_text("old source remains recoverable\n", encoding="utf-8")
        fixture.write_version("v2")
        fake_bin = fixture.root / "fake-restore-python"
        fake_bin.mkdir()
        record = fixture.root / "source-restore-backup.path"
        real_python = shutil.which("python3")
        real_mkdir = shutil.which("mkdir")
        self.assertTrue(all((real_python, real_mkdir)))
        fake_python = fake_bin / "python3"
        fake_python.write_text(
            "#!/bin/sh\n"
            f"real_python={shlex.quote(str(real_python))}\n"
            f"real_mkdir={shlex.quote(str(real_mkdir))}\n"
            f"install_root={shlex.quote(str(fixture.install_root))}\n"
            f"codex_skill={shlex.quote(str(fixture.codex_skill))}\n"
            f"record={shlex.quote(str(record))}\n"
            "if [ \"$#\" -eq 9 ] && [ \"$1\" = - ]; then\n"
            "  case \"$2:$4\" in\n"
            "    */.clonegrown-codex.new.*:*)\n"
            "      if [ \"$4\" = \"$codex_skill\" ]; then\n"
            "        \"$real_python\" \"$@\" || exit $?\n"
            "        exit 73\n"
            "      fi\n"
            "      ;;\n"
            "    */.clonegrown-source.backup.*:*)\n"
            "      if [ \"$4\" = \"$install_root\" ]; then\n"
            "        \"$real_mkdir\" \"$4\" || exit $?\n"
            "        printf '%s\\n' 'unowned restore target' > \"$4/sentinel.txt\"\n"
            "        printf '%s\\n' \"$2\" > \"$record\"\n"
            "      fi\n"
            "      ;;\n"
            "  esac\n"
            "fi\n"
            "exec \"$real_python\" \"$@\"\n",
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        path = f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"

        failed = run_installer(fixture, PATH=path)

        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual((fixture.install_root / "sentinel.txt").read_text(encoding="utf-8"),
                         "unowned restore target\n")
        backup = Path(record.read_text(encoding="utf-8").rstrip("\n"))
        self.assertEqual((backup / "local-preserved.txt").read_text(encoding="utf-8"),
                         "old source remains recoverable\n")
        self.assertTrue((backup / MARKER).is_file())

    def test_reoccupied_committed_backup_is_preserved(self) -> None:
        fixture = make_fixture(self.root, "reoccupied-committed-backup")
        first = run_installer(fixture)
        self.assertEqual(first.returncode, 0, first.stderr)
        fixture.write_version("v2")
        fake_bin = fixture.root / "fake-cleanup-python"
        fake_bin.mkdir()
        record = fixture.root / "committed-backup.path"
        saved_old = fixture.root / "saved-old-source"
        real_python = shutil.which("python3")
        real_mv = shutil.which("mv")
        real_mkdir = shutil.which("mkdir")
        self.assertTrue(all((real_python, real_mv, real_mkdir)))
        fake_python = fake_bin / "python3"
        fake_python.write_text(
            "#!/bin/sh\n"
            f"real_python={shlex.quote(str(real_python))}\n"
            f"real_mv={shlex.quote(str(real_mv))}\n"
            f"real_mkdir={shlex.quote(str(real_mkdir))}\n"
            f"record={shlex.quote(str(record))}\n"
            f"saved_old={shlex.quote(str(saved_old))}\n"
            "if [ \"$#\" -eq 6 ] && [ \"$1\" = - ]; then\n"
            "  case \"$2\" in\n"
            "    */.clonegrown-source.backup.*)\n"
            "      if [ ! -e \"$record\" ]; then\n"
            "        \"$real_mv\" \"$2\" \"$saved_old\" || exit $?\n"
            "        \"$real_mkdir\" \"$2\" || exit $?\n"
            "        printf '%s\\n' 'unowned committed-backup target' > \"$2/sentinel.txt\"\n"
            "        printf '%s\\n' \"$2\" > \"$record\"\n"
            "      fi\n"
            "      ;;\n"
            "  esac\n"
            "fi\n"
            "exec \"$real_python\" \"$@\"\n",
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        path = f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"

        updated = run_installer(fixture, PATH=path)

        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assert_installed(fixture, "v2")
        backup = Path(record.read_text(encoding="utf-8").rstrip("\n"))
        self.assertEqual((backup / "sentinel.txt").read_text(encoding="utf-8"),
                         "unowned committed-backup target\n")
        self.assertTrue((saved_old / MARKER).is_file())
        self.assertIn("preserved unexpected object", updated.stderr)

    def test_stage_cleanup_does_not_delegate_verified_names_to_rm(self) -> None:
        fixture = make_fixture(self.root, "single-operation-cleanup")
        fake_bin = fixture.root / "fake-cleanup-bin"
        fake_bin.mkdir()
        rm_record = fixture.root / "external-rm-stage-paths"
        real_cp = shutil.which("cp")
        real_rm = shutil.which("rm")
        self.assertIsNotNone(real_cp)
        self.assertIsNotNone(real_rm)

        fake_cp = fake_bin / "cp"
        fake_cp.write_text(
            "#!/bin/sh\n"
            f"real_cp={shlex.quote(str(real_cp))}\n"
            "\"$real_cp\" \"$@\" || exit $?\n"
            "case \"$2\" in\n"
            "  */.clonegrown-claude.new.*/SKILL.md) exit 75 ;;\n"
            "esac\n"
            "exit 0\n",
            encoding="utf-8",
        )
        fake_cp.chmod(0o755)

        fake_rm = fake_bin / "rm"
        fake_rm.write_text(
            "#!/bin/sh\n"
            f"real_rm={shlex.quote(str(real_rm))}\n"
            f"record={shlex.quote(str(rm_record))}\n"
            "for candidate in \"$@\"; do\n"
            "  case \"$candidate\" in\n"
            "    */.clonegrown-*.new.*) printf '%s\\n' \"$candidate\" >> \"$record\" ;;\n"
            "  esac\n"
            "done\n"
            "exec \"$real_rm\" \"$@\"\n",
            encoding="utf-8",
        )
        fake_rm.chmod(0o755)
        path = f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"

        failed = run_installer(fixture, PATH=path)

        self.assertNotEqual(failed.returncode, 0)
        self.assertFalse(
            rm_record.exists(),
            "stage identity was checked separately before an external rm call",
        )
        for parent in {
            fixture.install_root.parent,
            fixture.wrapper.parent,
            fixture.claude_skill.parent,
            fixture.codex_skill.parent,
        }:
            self.assertEqual(list(parent.glob(".clonegrown-*.new.*")), [])


if __name__ == "__main__":
    unittest.main()
