"""Public API parity and pre-allocation validation of generated task branches."""
from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

import clonegrown
import clonegrown.core as core
from clonegrown import ClonegrownError, spawn
from clonegrown import cli
from clonegrown.lifecycle import init_workspace
from clonegrown.state import WorkspaceState, request_path, sanitize_task
from clonegrown.worker import validate_generated_branch
from support import make_repo, run_cli, run_git


class PublicApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.repo = make_repo(self.root)
        self.workspace = self.root / "workspace"
        init_workspace(self.repo, self.workspace)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def metadata_snapshot(self) -> dict[str, bytes | None]:
        control = self.workspace / ".cws"
        return {
            str(path.relative_to(control)): path.read_bytes() if path.is_file() else None
            for path in sorted(control.rglob("*"))
        }

    def test_python_and_cli_defaults_are_the_same_non_strong_clone(self) -> None:
        signature = inspect.signature(spawn)
        self.assertIs(signature.parameters["strong"].default, False)
        parsed = cli.build_parser().parse_args(["spawn", "parser default"])
        self.assertIs(parsed.strong, False)
        self.assertIs(parsed.worktree, False)

        api_worker = spawn(self.workspace, "HEAD", "API default")
        returncode, cli_worker = run_cli(
            self.repo, "spawn", "CLI default", "--workspace", str(self.workspace),
        )

        self.assertEqual(returncode, 0)
        self.assertEqual((api_worker["mode"], api_worker["strong"]), ("clone", False))
        self.assertEqual((cli_worker["mode"], cli_worker["strong"]), ("clone", False))

    def test_explicit_strong_clone_and_worktree_rejection_are_unchanged(self) -> None:
        worker = spawn(self.workspace, "HEAD", "explicit strong", strong=True)
        self.assertEqual((worker["mode"], worker["strong"]), ("clone", True))
        with self.assertRaisesRegex(ClonegrownError, "strong does not apply"):
            spawn(self.workspace, "HEAD", "invalid worktree", strong=True, mode="worktree")

    def test_cwserror_alias_is_no_longer_public(self) -> None:
        self.assertIs(clonegrown.ClonegrownError, core.ClonegrownError)
        self.assertFalse(hasattr(clonegrown, "CWSError"))
        self.assertFalse(hasattr(core, "CWSError"))
        self.assertNotIn("CWSError", clonegrown.__all__)

    def test_lock_suffix_is_rejected_before_any_allocation_mutation(self) -> None:
        state_before = (self.workspace / ".cws" / "state.json").read_bytes()
        metadata_before = self.metadata_snapshot()
        refs_before = run_git(
            self.repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/cws/",
        ).stdout

        with self.assertRaisesRegex(ClonegrownError, r"invalid for Git: .*x\.lock"):
            spawn(self.workspace, "HEAD", "x.lock", request_id="invalid-lock")

        self.assertEqual((self.workspace / ".cws" / "state.json").read_bytes(), state_before)
        self.assertEqual(self.metadata_snapshot(), metadata_before)
        self.assertEqual(run_git(
            self.repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/cws/",
        ).stdout, refs_before)
        self.assertFalse(request_path(self.workspace, "invalid-lock").exists())
        self.assertFalse((self.workspace / "1").exists())

    def test_task_sanitization_is_bounded_unicode_safe_and_git_valid(self) -> None:
        state = WorkspaceState.load(self.workspace)
        cases = {
            "normal task": "normal-task",
            "feature/@{bad}": "feature-bad",
            ".leading": "leading",
            "trailing.": "trailing",
            "double..dot": "double-dot",
            "back\\slash": "back-slash",
            "雪だるま": "task",
            "café parser": "caf-parser",
            "a" * 48: "a" * 48,
            "a" * 49: "a" * 48,
            "b" * 10_000: "b" * 48,
        }
        for worker_id, (task, expected_slug) in enumerate(cases.items(), start=1):
            with self.subTest(task=task[:60]):
                self.assertEqual(sanitize_task(task), expected_slug)
                branch = state.worker_branch(worker_id, task)
                self.assertTrue(branch.endswith(f"/{worker_id}-{expected_slug}"))
                validate_generated_branch(self.repo, branch)

        prefix = f"agent/{state.workspace_id}/"
        for invalid in (
            prefix + "1-x.lock",
            prefix + "1-trailing.",
            prefix + "1-double..dot",
            prefix + "1-@{bad}",
            prefix + "1-back\\slash",
            prefix + "/1-empty-component",
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ClonegrownError, "invalid for Git"):
                    validate_generated_branch(self.repo, invalid)

    def test_hostile_task_text_remains_literal_and_cannot_execute_a_shell(self) -> None:
        victim = self.root / "shell-ran"
        task = f"../../x; touch {victim} $(touch {victim}) Ω"

        worker = spawn(self.workspace, "HEAD", task)

        self.assertFalse(victim.exists())
        self.assertEqual(worker["task"], task)
        validate_generated_branch(self.repo, worker["branch"])
        self.assertNotIn("..", worker["branch"])
        self.assertNotIn(";", worker["branch"])
        self.assertNotIn(" ", worker["branch"])


if __name__ == "__main__":
    unittest.main()
