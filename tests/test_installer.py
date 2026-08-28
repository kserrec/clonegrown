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
        self.root = Path(self.temporary.name)

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
        """Return a PATH whose mv recreates each vacated publication stage."""
        fake_bin = fixture.root / f"fake-mv-{fail_kind or 'success'}"
        fake_bin.mkdir()
        records = fixture.root / f"stage-records-{fail_kind or 'success'}"
        records.mkdir()
        real_mv = shutil.which("mv")
        self.assertIsNotNone(real_mv)
        fake_mv = fake_bin / "mv"
        fake_mv.write_text(
            "#!/bin/sh\n"
            f"real_mv={shlex.quote(str(real_mv))}\n"
            f"record_dir={shlex.quote(str(records))}\n"
            f"fail_kind={shlex.quote(fail_kind)}\n"
            "kind=\n"
            "if [ \"$#\" -eq 2 ]; then\n"
            "  case \"$1\" in\n"
            "    */.clonegrown-source.new.*) kind=source ;;\n"
            "    */.clonegrown-command.new.*) kind=command ;;\n"
            "    */.clonegrown-claude.new.*) kind=claude-skill ;;\n"
            "    */.clonegrown-codex.new.*) kind=codex-skill ;;\n"
            "  esac\n"
            "fi\n"
            "if [ -n \"$kind\" ]; then\n"
            "  \"$real_mv\" \"$@\" || exit $?\n"
            "  if [ \"$kind\" = command ]; then\n"
            "    printf '%s\\n' \"unowned $kind stage replacement\" > \"$1\"\n"
            "  else\n"
            "    mkdir \"$1\" || exit $?\n"
            "    printf '%s\\n' \"unowned $kind stage replacement\" > \"$1/sentinel.txt\"\n"
            "  fi\n"
            "  printf '%s\\n' \"$1\" > \"$record_dir/$kind.path\"\n"
            "  if [ \"$kind\" = \"$fail_kind\" ]; then\n"
            "    exit 73\n"
            "  fi\n"
            "  exit 0\n"
            "fi\n"
            "exec \"$real_mv\" \"$@\"\n",
            encoding="utf-8",
        )
        fake_mv.chmod(0o755)
        path = f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"
        return records, path

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
        real_mv = shutil.which("mv")
        self.assertIsNotNone(real_mv)
        fake_mv = fake_bin / "mv"
        fake_mv.write_text(
            "#!/bin/sh\n"
            f"if [ \"$#\" -eq 2 ] && [ \"$2\" = {shlex.quote(str(fixture.claude_skill))} ]; then\n"
            "  case \"$1\" in\n"
            "    */.clonegrown-claude.new.*)\n"
            f"      if [ ! -e {shlex.quote(str(failure_record))} ]; then\n"
            f"        : > {shlex.quote(str(failure_record))}\n"
            "        kill -TERM \"$PPID\"\n"
            "        exit 0\n"
            "      fi\n"
            "      ;;\n"
            "  esac\n"
            "fi\n"
            f"exec {shlex.quote(str(real_mv))} \"$@\"\n",
            encoding="utf-8",
        )
        fake_mv.chmod(0o755)
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
