from __future__ import annotations

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from clonegrown import cli
import clonegrown.core as core
from clonegrown.lifecycle import init_workspace
from clonegrown.repository import prepared_ref_transaction
from support import make_repo, run_git


class CommandExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.repo = make_repo(self.root)
        found = shutil.which("git")
        if found is None:
            self.fail("Git is required for the command-runner tests")
        self.real_git = str(Path(found).resolve())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def executable(self, name: str, source: str) -> Path:
        path = self.root / name
        path.write_text("#!/usr/bin/env python3\n" + source, encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_renamed_clonegrown_git_always_gets_clean_noninteractive_environment(self) -> None:
        capture = self.root / "git-environment.json"
        wrapper = self.executable(
            "renamed-git",
            """import json
import os
import sys
from pathlib import Path

keys = [
    "GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0",
    "GIT_CONFIG_VALUE_0", "GIT_TRACE_PACKET", "GIT_TERMINAL_PROMPT",
]
Path(os.environ["CLONEGROWN_TEST_CAPTURE"]).write_text(
    json.dumps({key: os.environ.get(key) for key in keys}), encoding="utf-8"
)
os.execv(%r, [%r, *sys.argv[1:]])
""" % (self.real_git, self.real_git),
        )
        hostile = {
            "CLONEGROWN_GIT": str(wrapper),
            "CLONEGROWN_TEST_CAPTURE": str(capture),
            "GIT_DIR": str(self.root / "attacker.git"),
            "GIT_WORK_TREE": str(self.root / "attacker-tree"),
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "alias.status",
            "GIT_CONFIG_VALUE_0": "!false",
            "GIT_TRACE_PACKET": "1",
            "GIT_TERMINAL_PROMPT": "1",
        }
        with patch.dict(os.environ, hostile, clear=False):
            self.assertEqual(core._find_git(), wrapper)
            with patch.object(core, "GIT_BIN", core._find_git()):
                result = core.git(self.repo, "rev-parse", "--git-dir")
                head = core.git(self.repo, "rev-parse", "HEAD").stdout.strip()
                branch = core.git(self.repo, "symbolic-ref", "HEAD").stdout.strip()
                with prepared_ref_transaction(self.repo, [f"verify {branch} {head}"]):
                    pass

        self.assertEqual(result.stdout.strip(), ".git")
        observed = json.loads(capture.read_text(encoding="utf-8"))
        for key in hostile:
            if key.startswith("GIT_") and key != "GIT_TERMINAL_PROMPT":
                self.assertIsNone(observed[key], key)
        self.assertEqual(observed["GIT_TERMINAL_PROMPT"], "0")

    def test_generic_run_keeps_non_git_environment_semantics(self) -> None:
        with patch.dict(os.environ, {"GIT_DIR": "generic-command-value"}, clear=False):
            result = core.run([
                sys.executable, "-c", "import os; print(os.environ['GIT_DIR'])",
            ])
        self.assertEqual(result.stdout.strip(), "generic-command-value")

    def test_process_environment_cannot_disable_or_retarget_replace_refs(self) -> None:
        original = run_git(self.repo, "rev-parse", "HEAD").stdout.strip()
        (self.repo / "replacement.txt").write_text("replacement\n", encoding="utf-8")
        run_git(self.repo, "add", "replacement.txt")
        run_git(self.repo, "commit", "-m", "replacement commit")
        replacement = run_git(self.repo, "rev-parse", "HEAD").stdout.strip()
        run_git(self.repo, "replace", original, replacement)
        expected = core.git(self.repo, "show", "-s", "--format=%s", original).stdout.strip()
        self.assertEqual(expected, "replacement commit")

        for hostile in (
            {"GIT_NO_REPLACE_OBJECTS": "1"},
            {"GIT_REPLACE_REF_BASE": "refs/hostile-replacements"},
        ):
            with self.subTest(hostile=hostile), patch.dict(os.environ, hostile, clear=False):
                observed = core.git(self.repo, "show", "-s", "--format=%s", original).stdout.strip()
            self.assertEqual(observed, expected)

    def test_failed_git_is_structured_and_redacts_values_and_url_userinfo(self) -> None:
        wrapper = self.executable(
            "failing-git",
            """import sys
print("useful stdout: " + " | ".join(sys.argv[1:]))
print("fatal: useful stderr: " + " | ".join(sys.argv[1:]), file=sys.stderr)
raise SystemExit(23)
""",
        )
        config_secret = "config-sentinel-value"
        url = "https://agent:p%40ss@example.invalid/visible-path.git"
        with patch.object(core, "GIT_BIN", wrapper):
            with self.assertRaises(core.CommandFailure) as caught:
                core.git(
                    self.repo, "config", "agent.private", config_secret, url,
                    sensitive=(config_secret,),
                )

        error = caught.exception
        rendered = str(error)
        self.assertEqual(error.returncode, 23)
        self.assertEqual(error.operation, "git config")
        self.assertFalse(error.timed_out)
        self.assertNotIn(config_secret, rendered)
        self.assertNotIn("agent:p%40ss", rendered)
        self.assertIn("https://<redacted>@example.invalid/visible-path.git", rendered)
        self.assertIn("useful stdout", rendered)
        self.assertIn("fatal: useful stderr", rendered)
        self.assertNotIn(config_secret, repr(error))
        self.assertIn(config_secret, error._private_command)
        self.assertIn(config_secret, str(error._private_stdout))
        self.assertIn(url, str(error._private_stderr))

    def test_short_sensitive_value_does_not_destroy_unrelated_diagnostics(self) -> None:
        error = core.CommandFailure(
            returncode=41,
            operation="git config",
            command=["git", "config", "--local", "--add", "agent.private", "a"],
            cwd=self.repo,
            stdout="",
            stderr="fatal: cannot add agent.private; rejected value a",
            sensitive=("a",),
        )

        self.assertIn("--add agent.private '<redacted>'", error.public_command)
        self.assertIn("fatal: cannot add agent.private", error.public_stderr)
        self.assertIn("rejected value <redacted>", error.public_stderr)
        self.assertEqual(error._private_command[-1], "a")
        self.assertTrue(str(error._private_stderr).endswith("value a"))

    def test_timeout_is_structured_and_redacted(self) -> None:
        wrapper = self.executable(
            "slow-git",
            """import time
time.sleep(30)
""",
        )
        remote = "https://agent:timeout-secret@example.invalid/private-timeout.git"
        with patch.object(core, "GIT_BIN", wrapper):
            with self.assertRaises(core.CommandFailure) as caught:
                core.git(self.repo, "fetch", remote, timeout=0.01, sensitive=(remote,))

        error = caught.exception
        self.assertIsNone(error.returncode)
        self.assertEqual(error.operation, "git fetch")
        self.assertTrue(error.timed_out)
        self.assertEqual(error.timeout, 0.01)
        self.assertNotIn(remote, str(error))
        self.assertIn("<redacted>", str(error))
        self.assertIn(remote, error._private_command)

    def test_launch_failures_are_structured_for_text_and_byte_git_runners(self) -> None:
        missing = self.root / "missing-custom-git"
        with patch.object(core, "GIT_BIN", missing):
            for invoke in (
                lambda: core.git(self.repo, "status"),
                lambda: core.git_bytes(self.repo, "status"),
            ):
                with self.subTest(invoke=invoke), self.assertRaises(core.CommandFailure) as caught:
                    invoke()

                error = caught.exception
                self.assertIsNone(error.returncode)
                self.assertEqual(error.operation, "git status")
                self.assertFalse(error.timed_out)
                self.assertTrue(error.start_failed)
                self.assertIn("could not start", str(error))
                self.assertNotIn("exit None", str(error))
                self.assertIsInstance(error.__cause__, FileNotFoundError)
                self.assertIs(error._private_start_error, error.__cause__)

    def test_git_bytes_uses_the_same_redacted_failure(self) -> None:
        wrapper = self.executable(
            "byte-failing-git",
            """import os
import sys
os.write(1, ("raw stdout " + sys.argv[-1]).encode() + b"\\xff")
os.write(2, ("raw stderr " + sys.argv[-1]).encode() + b"\\xfe")
raise SystemExit(29)
""",
        )
        secret = "byte-sentinel"
        with patch.object(core, "GIT_BIN", wrapper):
            with self.assertRaises(core.CommandFailure) as caught:
                core.git_bytes(self.repo, "status", secret, sensitive=(secret,))

        error = caught.exception
        self.assertEqual(error.returncode, 29)
        self.assertEqual(error.operation, "git status")
        self.assertNotIn(secret, str(error))
        self.assertIn("raw stdout <redacted>\\xff", str(error))
        self.assertIn(secret.encode(), error._private_stdout)
        self.assertIn(secret.encode(), error._private_stderr)

    def test_git_arguments_remain_literal_without_shell_execution(self) -> None:
        capture = self.root / "arguments.json"
        wrapper = self.executable(
            "argument-git",
            """import json
import os
import sys
from pathlib import Path
Path(os.environ["CLONEGROWN_TEST_CAPTURE"]).write_text(
    json.dumps(sys.argv[1:]), encoding="utf-8"
)
""",
        )
        victim = self.root / "shell-ran"
        hostile = f"value; touch {victim}"
        with patch.dict(os.environ, {"CLONEGROWN_TEST_CAPTURE": str(capture)}, clear=False):
            with patch.object(core, "GIT_BIN", wrapper):
                core.git(self.repo, "config", "agent.literal", hostile, sensitive=(hostile,))

        self.assertEqual(json.loads(capture.read_text(encoding="utf-8")),
                         ["config", "agent.literal", hostile])
        self.assertFalse(victim.exists())

    def test_ordinary_git_stderr_remains_useful(self) -> None:
        with patch.object(core, "GIT_BIN", Path(self.real_git)):
            with self.assertRaises(core.CommandFailure) as caught:
                core.git(self.repo, "rev-parse", "--verify", "refs/heads/definitely-missing")
        self.assertEqual(caught.exception.operation, "git rev-parse")
        self.assertIn("Needed a single revision", str(caught.exception))


class TestHookGateTests(unittest.TestCase):
    def test_production_mode_ignores_new_hostile_and_legacy_hook_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "must-not-exist"
            hostile = {
                "CLONEGROWN_TEST_PAUSEPOINT": "boundary",
                "CLONEGROWN_TEST_PAUSE_MARKER": str(marker),
                "CLONEGROWN_TEST_PAUSE_SECONDS": "not-a-number",
                "CLONEGROWN_TEST_FAILPOINT": "boundary",
                "CLONEGROWN_TEST_ERRORPOINT": "boundary",
                "CWS_PAUSEPOINT": "boundary",
                "CWS_PAUSE_MARKER": str(marker),
                "CWS_PAUSE_SECONDS": "not-a-number",
                "CWS_FAILPOINT": "boundary",
                "CWS_ERRORPOINT": "boundary",
            }
            for mode in (None, "", "0", "true", "01"):
                with self.subTest(mode=mode):
                    environment = dict(hostile)
                    if mode is not None:
                        environment["CLONEGROWN_TEST_MODE"] = mode
                    with patch.dict(os.environ, environment, clear=True):
                        core.failpoint("boundary")
                    self.assertFalse(marker.exists())

    def test_exact_test_mode_gate_enables_only_the_new_hook_names(self) -> None:
        with patch.dict(os.environ, {
            "CLONEGROWN_TEST_MODE": "1",
            "CLONEGROWN_TEST_ERRORPOINT": "boundary",
        }, clear=True):
            with self.assertRaisesRegex(core.ClonegrownError, "injected ordinary failure"):
                core.failpoint("boundary")

        with patch.dict(os.environ, {
            "CLONEGROWN_TEST_MODE": "1",
            "CWS_ERRORPOINT": "boundary",
        }, clear=True):
            core.failpoint("boundary")


class StoredErrorRedactionTests(unittest.TestCase):
    def _assert_spawn_failure_is_publicly_and_durably_redacted(self, kind: str) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            repo = make_repo(root)
            workspace = root / "workspace"
            if kind == "config":
                secret = "copied-config-sentinel"
                run_git(repo, "config", "agent.private", secret)
                forbidden_fragments = (secret,)
                useful_fragment = "agent.private"
            else:
                secret = "https://agent:remote-password@example.invalid/remote-path-sentinel.git"
                run_git(repo, "remote", "add", "private", secret)
                forbidden_fragments = (secret, "remote-password", "remote-path-sentinel")
                useful_fragment = "remote add"
            init_workspace(repo, workspace)

            found = shutil.which("git")
            self.assertIsNotNone(found)
            real_git = str(Path(found or "git").resolve())
            wrapper = root / "redacting-git"
            wrapper.write_text(
                "#!/usr/bin/env python3\n"
                "import os\n"
                "import sys\n"
                "target = os.environ['CLONEGROWN_TEST_FAIL_VALUE']\n"
                "if target in sys.argv[1:]:\n"
                "    print('ordinary Git setup failure while applying ' + target)\n"
                "    print('fatal: rejected ' + target, file=sys.stderr)\n"
                "    raise SystemExit(41)\n"
                f"os.execv({real_git!r}, [{real_git!r}, *sys.argv[1:]])\n",
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            environment = {
                "CLONEGROWN_GIT": str(wrapper),
                "CLONEGROWN_TEST_FAIL_VALUE": secret,
            }
            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch.dict(os.environ, environment, clear=False):
                with patch.object(core, "GIT_BIN", core._find_git()):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        returncode = cli.main([
                            "spawn", "redaction regression", "--workspace", str(workspace),
                        ])

            self.assertEqual(returncode, 2)
            self.assertEqual(stdout.getvalue(), "")
            public_error = stderr.getvalue()
            record = json.loads((workspace / ".cws" / "workers" / "1.json").read_text(encoding="utf-8"))
            durable_error = str(record["error"])
            for fragment in forbidden_fragments:
                self.assertNotIn(fragment, public_error)
                self.assertNotIn(fragment, durable_error)
            self.assertIn("ordinary Git setup failure", public_error)
            self.assertIn("ordinary Git setup failure", durable_error)
            self.assertIn(useful_fragment, public_error)
            self.assertIn(useful_fragment, durable_error)
            self.assertIn("<redacted>", public_error)
            self.assertIn("<redacted>", durable_error)

    def test_copied_config_value_is_not_in_cli_or_worker_error(self) -> None:
        self._assert_spawn_failure_is_publicly_and_durably_redacted("config")

    def test_remote_url_is_not_in_cli_or_worker_error(self) -> None:
        self._assert_spawn_failure_is_publicly_and_durably_redacted("remote")


if __name__ == "__main__":
    unittest.main()
