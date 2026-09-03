"""Public operation failures carry truthful durable-state and custody context."""
from __future__ import annotations

import contextlib
import errno
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clonegrown import ClonegrownError, collect, discard, init_workspace, recover, release, spawn, status
from clonegrown import cli
from clonegrown import core
from clonegrown import lifecycle
from clonegrown import recovery as recovery_module
from clonegrown.core import CommandFailure
from clonegrown.state import WorkspaceState, canonical_marker_path, worker_lock_path, worker_record_path
from support import commit, make_repo, run_git


class UnrenderableError(Exception):
    def __str__(self) -> str:
        raise ValueError("broken exception renderer")


class SafetyErrorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name).resolve()
        self.repo = make_repo(self.root)
        self.ws = self.root / "demo-dev"
        init_workspace(self.repo, self.ws)

    def tearDown(self) -> None:
        self.td.cleanup()

    def assert_context(self, error: BaseException, operation: str) -> str:
        self.assertIs(type(error), ClonegrownError)
        message = str(error)
        self.assertIn(f"{operation} failed during ", message)
        self.assertIn("Durable state: ", message)
        self.assertRegex(message, r"Work preservation: (believed preserved|unverified)")
        self.assertIn("Recovery: ", message)
        self.assertIn("Cause: ", message)
        return message

    def test_low_level_error_families_translate_at_all_five_boundaries(self) -> None:
        cases = (
            (
                "init",
                OSError("filesystem probe"),
                lambda cause: patch.object(lifecycle, "validate_primary_repo", side_effect=cause),
                lambda: init_workspace(self.repo, self.root / "unused-init"),
            ),
            (
                "spawn",
                subprocess.SubprocessError("subprocess probe"),
                lambda cause: patch.object(lifecycle, "allocate_spawn", side_effect=cause),
                lambda: spawn(self.ws, "HEAD", "probe"),
            ),
            (
                "collect",
                ValueError("conversion probe"),
                lambda cause: patch.object(lifecycle, "require_worker", side_effect=cause),
                lambda: collect(self.ws, 1),
            ),
            (
                "discard",
                json.JSONDecodeError("JSON probe", "x", 0),
                lambda cause: patch.object(lifecycle, "require_worker", side_effect=cause),
                lambda: discard(self.ws, 1),
            ),
            (
                "recover",
                OSError("recovery filesystem probe"),
                lambda cause: patch.object(recovery_module, "workspace_lock", side_effect=cause),
                lambda: recover(self.ws),
            ),
        )
        for operation, cause, make_patch, call in cases:
            with self.subTest(operation=operation), make_patch(cause):
                with self.assertRaises(ClonegrownError) as caught:
                    call()
                self.assert_context(caught.exception, operation)
                self.assertIs(caught.exception.__cause__, cause)

        cause = UnrenderableError()
        with patch.object(lifecycle, "allocate_spawn", side_effect=cause):
            with self.assertRaises(ClonegrownError) as caught:
                spawn(self.ws, "HEAD", "unrenderable cause")
        self.assertIn("UnrenderableError (message unavailable)", str(caught.exception))
        self.assertIs(caught.exception.__cause__, cause)

    def test_process_control_exceptions_pass_through_untouched(self) -> None:
        for cause in (KeyboardInterrupt(), SystemExit(19), GeneratorExit()):
            with self.subTest(exception=type(cause).__name__):
                with patch.object(lifecycle, "allocate_spawn", side_effect=cause):
                    with self.assertRaises(type(cause)) as caught:
                        spawn(self.ws, "HEAD", "control probe")
                self.assertIs(caught.exception, cause)

    def test_process_control_exceptions_do_not_run_lifecycle_rollback(self) -> None:
        for worker_id, cause in enumerate((KeyboardInterrupt(), SystemExit(19), GeneratorExit()), start=1):
            with self.subTest(exception=type(cause).__name__):
                with patch.object(lifecycle, "git", side_effect=cause):
                    with self.assertRaises(type(cause)) as caught:
                        spawn(self.ws, "HEAD", f"in-flight {type(cause).__name__}")
                self.assertIs(caught.exception, cause)
                record = json.loads(worker_record_path(self.ws, worker_id).read_text(encoding="utf-8"))
                self.assertEqual(record["status"], "cloning")
                self.assertIsNotNone(record["owner_pid"])
                self.assertNotIn("error", record)

    def test_cli_prints_one_redacted_contextual_error_without_traceback(self) -> None:
        secret = "https://alice:token@example.test/private.git"
        failure = CommandFailure(
            returncode=23,
            operation="git fetch",
            command=["git", "fetch", secret],
            cwd=self.repo,
            stdout="",
            stderr=f"cannot fetch {secret}",
            sensitive=(secret,),
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(lifecycle, "allocate_spawn", side_effect=failure):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = cli.main(["spawn", "probe", "--workspace", str(self.ws)])
        self.assertEqual(result, 2)
        self.assertEqual(stdout.getvalue(), "")
        rendered = stderr.getvalue()
        self.assertEqual(rendered.count("clonegrown:"), 1)
        self.assertIn("spawn failed during allocation validation", rendered)
        self.assertIn("Durable state:", rendered)
        self.assertIn("Work preservation:", rendered)
        self.assertIn("Recovery:", rendered)
        self.assertIn("<redacted>", rendered)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("Traceback", rendered)

    def test_cli_input_resolution_failures_have_the_operation_safety_context(self) -> None:
        cases = (
            ("spawn", ["spawn", "probe"]),
            ("collect", ["collect", "1"]),
            ("discard", ["discard", "1"]),
            ("recover", ["recover"]),
        )
        for operation, arguments in cases:
            with self.subTest(operation=operation):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with patch.object(cli, "resolve_workspace", side_effect=OSError("workspace discovery probe")):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        result = cli.main(arguments)
                rendered = stderr.getvalue()
                self.assertEqual(result, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertIn(f"{operation} failed during input and workspace resolution", rendered)
                self.assertIn("Durable state:", rendered)
                self.assertIn("Work preservation:", rendered)
                self.assertIn("Recovery:", rendered)
                self.assertNotIn("Traceback", rendered)

    def test_cli_init_missing_custom_git_is_one_structured_contextual_error(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(core, "GIT_BIN", self.root / "missing-custom-git"):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = cli.main([
                    "init", str(self.repo), "--workspace", str(self.root / "unused-init"),
                ])
        rendered = stderr.getvalue()
        self.assertEqual(result, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("init failed during input and workspace resolution", rendered)
        self.assertIn("git rev-parse could not start", rendered)
        self.assertEqual(rendered.count("clonegrown:"), 1)
        self.assertNotIn("Traceback", rendered)

    def test_internal_custody_token_is_absent_from_public_and_durable_failures(self) -> None:
        for worker_id, kind in enumerate(("command", "filesystem"), start=1):
            with self.subTest(kind=kind):
                def fail_clone(cwd: Path, *args: str | Path, **kwargs: object) -> None:
                    if kind == "command":
                        raise CommandFailure(
                            returncode=71,
                            operation="git clone",
                            command=[str(core.GIT_BIN), *(str(value) for value in args)],
                            cwd=cwd,
                            stdout="",
                            stderr="ordinary staged clone failure",
                        )
                    raise PermissionError(
                        errno.EACCES, "ordinary staged filesystem failure", str(cwd),
                    )

                stdout = io.StringIO()
                stderr = io.StringIO()
                with patch.object(lifecycle, "git", side_effect=fail_clone):
                    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                        result = cli.main([
                            "spawn", f"token redaction {kind}", "--workspace", str(self.ws),
                        ])

                self.assertEqual(result, 2)
                self.assertEqual(stdout.getvalue(), "")
                record = json.loads(worker_record_path(self.ws, worker_id).read_text(encoding="utf-8"))
                token = str(record["worker_token"])
                public_error = stderr.getvalue()
                durable_error = str(record["error"])
                self.assertNotIn(token, public_error)
                self.assertNotIn(token, durable_error)
                self.assertIn("ordinary staged", public_error)
                self.assertIn("ordinary staged", durable_error)
                self.assertIn("<redacted>", public_error)
                self.assertIn("<redacted>", durable_error)

    def test_init_failure_after_state_names_checkpoint_and_retry_finishes(self) -> None:
        workspace = self.root / "second-dev"
        with patch.dict(os.environ, {
            "CLONEGROWN_TEST_MODE": "1",
            "CLONEGROWN_TEST_ERRORPOINT": "init.after_state",
        }):
            with self.assertRaises(ClonegrownError) as caught:
                init_workspace(self.repo, workspace)
        message = self.assert_context(caught.exception, "init")
        self.assertIn("after initializing-state commit", message)
        self.assertIn("initializing workspace state was written", message)
        self.assertIn("retry init", message)

        state_path = workspace / ".cws" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "initializing")
        self.assertFalse(canonical_marker_path(self.repo, state["workspace_id"]).exists())
        self.assertEqual(init_workspace(self.repo, workspace)["status"], "ready")

    def test_init_refuses_selected_workspace_symlink_before_external_writes(self) -> None:
        repo = make_repo(self.root, "selected-workspace-symlink-repo")
        external = self.root / "external-selected-workspace"
        external.mkdir()
        selected = self.root / "selected-workspace-symlink-dev"
        os.symlink(external, selected, target_is_directory=True)

        with self.assertRaisesRegex(ClonegrownError, "workspace directory is not a real directory"):
            init_workspace(repo, selected)
        self.assertEqual(list(external.iterdir()), [])
        self.assertTrue(selected.is_symlink())

    def test_init_refuses_workspace_control_symlink_before_external_writes(self) -> None:
        repo = make_repo(self.root, "workspace-symlink-repo")
        workspace = self.root / "workspace-symlink-dev"
        workspace.mkdir()
        external = self.root / "external-workspace-control"
        external.mkdir()
        os.symlink(external, workspace / ".cws", target_is_directory=True)

        with self.assertRaisesRegex(ClonegrownError, "workspace control directory is not a real directory"):
            init_workspace(repo, workspace)
        self.assertEqual(list(external.iterdir()), [])
        self.assertTrue((workspace / ".cws").is_symlink())

    def test_init_preflights_existing_control_subdirectory_symlinks(self) -> None:
        repo = make_repo(self.root, "subdirectory-symlink-repo")
        workspace = self.root / "subdirectory-symlink-dev"
        control = workspace / ".cws"
        control.mkdir(parents=True)
        external = self.root / "external-workers"
        external.mkdir()
        os.symlink(external, control / "workers", target_is_directory=True)

        with self.assertRaisesRegex(ClonegrownError, "workspace workers directory is not a real directory"):
            init_workspace(repo, workspace)
        self.assertEqual(list(external.iterdir()), [])
        self.assertEqual(sorted(path.name for path in control.iterdir()), ["workers"])

    def test_init_refuses_canonical_marker_symlink_before_external_writes(self) -> None:
        repo = make_repo(self.root, "marker-symlink-repo")
        workspace = self.root / "marker-symlink-dev"
        external = self.root / "external-canonical-markers"
        external.mkdir()
        os.symlink(external, repo / ".git" / "cws", target_is_directory=True)

        with self.assertRaisesRegex(ClonegrownError, "canonical marker directory is not a real directory"):
            init_workspace(repo, workspace)
        self.assertEqual(list(external.iterdir()), [])
        self.assertFalse(workspace.exists())

    def test_init_real_directories_remains_idempotent(self) -> None:
        before = (self.ws / ".cws" / "state.json").read_bytes()
        first = init_workspace(self.repo, self.ws)
        second = init_workspace(self.repo, self.ws)
        self.assertEqual(first, second)
        self.assertEqual((self.ws / ".cws" / "state.json").read_bytes(), before)

    def test_spawn_failure_after_publication_preserves_worker_for_recovery(self) -> None:
        with patch.dict(os.environ, {
            "CLONEGROWN_TEST_MODE": "1",
            "CLONEGROWN_TEST_ERRORPOINT": "spawn.after_publish",
        }):
            with self.assertRaises(ClonegrownError) as caught:
                spawn(self.ws, "HEAD", "published failure")
        message = self.assert_context(caught.exception, "spawn")
        self.assertIn("spawn failure after publication", message)
        self.assertIn("published worker directory remains in place", message)
        self.assertIn("run `clonegrown recover`", message)

        (worker,) = status(self.ws)["workers"]
        self.assertEqual(worker["status"], "publishing")
        self.assertTrue(Path(worker["path"]).is_dir())
        recover(self.ws)
        (recovered,) = status(self.ws)["workers"]
        self.assertEqual(recovered["status"], "ready")
        self.assertTrue(Path(recovered["path"]).is_dir())

    def test_collect_failure_after_fetch_retains_candidate_and_returns_ready(self) -> None:
        worker = spawn(self.ws, "HEAD", "collect failure")
        commit(Path(worker["path"]), "work.txt")
        with patch.dict(os.environ, {
            "CLONEGROWN_TEST_MODE": "1",
            "CLONEGROWN_TEST_ERRORPOINT": "collect.after_fetch",
        }):
            with self.assertRaises(ClonegrownError) as caught:
                collect(self.ws, worker["id"])
        message = self.assert_context(caught.exception, "collect")
        self.assertIn("collection rolled back", message)
        self.assertIn("published immutable candidate ref was retained", message)
        self.assertIn("not required", message)

        (listed,) = status(self.ws)["workers"]
        self.assertEqual(listed["status"], "ready")
        state = WorkspaceState.load(self.ws)
        refs = run_git(
            self.repo,
            "for-each-ref",
            "--format=%(refname)",
            f"{state.ref_prefix}/workers/{worker['id']}/results/",
        ).stdout.splitlines()
        self.assertEqual(len(refs), 1)
        self.assertEqual(collect(self.ws, worker["id"])["status"], "collected")

    def test_discard_failure_after_quarantine_preserves_then_recovery_finishes(self) -> None:
        worker = spawn(self.ws, "HEAD", "discard failure")
        commit(Path(worker["path"]), "work.txt")
        collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        with patch.dict(os.environ, {
            "CLONEGROWN_TEST_MODE": "1",
            "CLONEGROWN_TEST_ERRORPOINT": "discard.after_quarantine",
        }):
            with self.assertRaises(ClonegrownError) as caught:
                discard(self.ws, worker["id"])
        message = self.assert_context(caught.exception, "discard")
        self.assertIn("discard failure with preserved quarantine", message)
        self.assertIn("worker content remains quarantined", message)
        self.assertIn("run `clonegrown recover`", message)

        record = json.loads(worker_record_path(self.ws, worker["id"]).read_text(encoding="utf-8"))
        quarantine = Path(record["quarantine_path"])
        self.assertEqual(record["status"], "discarding")
        self.assertTrue(quarantine.is_dir())
        self.assertFalse(Path(worker["path"]).parent.exists())
        recover(self.ws)
        (finished,) = status(self.ws)["workers"]
        self.assertEqual(finished["status"], "discarded")
        self.assertFalse(quarantine.exists())

    def test_recover_worker_failure_report_carries_safety_fields(self) -> None:
        worker = spawn(self.ws, "HEAD", "recover failure")
        with patch.object(recovery_module._Recovery, "run", side_effect=OSError("worker recovery probe")):
            reports = recover(self.ws)
        report = next(item for item in reports if item.get("action") == "recovery-failed")
        self.assertEqual(report["id"], worker["id"])
        self.assertEqual(report["stage"], "worker reconciliation")
        self.assertIn("checkpoint", report["durable_state"])
        self.assertIn("unverified", report["work_preservation"])
        self.assertIn("retry recover", report["recovery"])
        self.assertTrue(Path(worker["path"]).is_dir())

    def test_unrenderable_worker_recovery_error_is_reported_and_later_workers_continue(self) -> None:
        first = spawn(self.ws, "HEAD", "first recovery failure")
        second = spawn(self.ws, "HEAD", "later recovery continues")
        visited: list[int] = []

        def fail_first(recovery: recovery_module._Recovery) -> None:
            worker_id = int(recovery.worker.id)
            visited.append(worker_id)
            if worker_id == first["id"]:
                raise UnrenderableError()

        with patch.object(recovery_module._Recovery, "run", fail_first):
            reports = recover(self.ws)

        self.assertEqual(visited, [first["id"], second["id"]])
        report = next(item for item in reports if item.get("action") == "recovery-failed")
        self.assertEqual(report["id"], first["id"])
        self.assertIn("UnrenderableError (message unavailable)", report["error"])
        self.assertFalse(any(item.get("id") == second["id"] and item.get("action") == "recovery-failed"
                             for item in reports))

    def test_worker_lock_failure_is_reported_and_later_workers_continue(self) -> None:
        first = spawn(self.ws, "HEAD", "unsafe recovery lock")
        second = spawn(self.ws, "HEAD", "later recovery after unsafe lock")
        first_lock = worker_lock_path(self.ws, first["id"])
        first_lock.unlink()
        first_lock.symlink_to(self.root / "untrusted-lock-target")
        visited: list[int] = []

        def record_visit(recovery: recovery_module._Recovery) -> None:
            visited.append(int(recovery.worker.id))

        with patch.object(recovery_module._Recovery, "run", record_visit):
            reports = recover(self.ws)

        self.assertEqual(visited, [second["id"]])
        report = next(item for item in reports if item.get("id") == first["id"]
                      and item.get("action") == "recovery-failed")
        self.assertEqual(report["stage"], "worker recovery-lock acquisition")
        self.assertIn("believed preserved", report["work_preservation"])
        self.assertIn("retry recover", report["recovery"])


if __name__ == "__main__":
    unittest.main()
