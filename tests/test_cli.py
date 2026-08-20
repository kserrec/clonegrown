from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import clonegrown_cli


def run_git(repo: Path, *args: str) -> str:
    p = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return p.stdout.strip()


class ClonegrownCliTests(unittest.TestCase):
    def make_repo(self, root: Path, branch: str = "trunk") -> Path:
        repo = root / "demo"
        repo.mkdir()
        run_git(repo, "init", "-b", branch)
        run_git(repo, "config", "user.name", "Clonegrown Test")
        run_git(repo, "config", "user.email", "clonegrown@example.test")
        (repo / "README.md").write_text("hello\n", encoding="utf-8")
        run_git(repo, "add", "README.md")
        run_git(repo, "commit", "-m", "initial")
        return repo

    def cli(self, cwd: Path, *args: str) -> tuple[int, dict]:
        old = Path.cwd()
        output = io.StringIO()
        try:
            os.chdir(cwd)
            with redirect_stdout(output):
                rc = clonegrown_cli.main(list(args))
        finally:
            os.chdir(old)
        payload = json.loads(output.getvalue())
        return rc, payload

    def assert_no_private_fields(self, value) -> None:
        private = {
            "canonical_token",
            "worker_token",
            "params_hash",
            "owner_pid",
            "owner_start",
            "stage_root",
        }
        if isinstance(value, dict):
            self.assertTrue(private.isdisjoint(value.keys()))
            for item in value.values():
                self.assert_no_private_fields(item)
        elif isinstance(value, list):
            for item in value:
                self.assert_no_private_fields(item)

    def test_zero_config_lifecycle_from_canonical_and_worker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = self.make_repo(root)

            rc, initialized = self.cli(repo, "init")
            self.assertEqual(rc, 0)
            self.assert_no_private_fields(initialized)
            workspace = root / "demo-dev"
            self.assertTrue((workspace / ".cws" / "state.json").is_file())
            self.assertEqual(Path(initialized["workspace"]).resolve(), workspace.resolve())

            rc, worker = self.cli(repo, "spawn", "change greeting")
            self.assertEqual(rc, 0)
            self.assert_no_private_fields(worker)
            worker_repo = Path(worker["path"])
            self.assertTrue(worker_repo.is_dir())

            # Default base is canonical HEAD, not a hard-coded branch name.
            self.assertEqual(worker["base_sha"], run_git(repo, "rev-parse", "HEAD"))

            # Auto-discovery must also work from inside the worker itself.
            rc, state = self.cli(worker_repo, "status")
            self.assertEqual(rc, 0)
            self.assert_no_private_fields(state)
            self.assertEqual(Path(state["workspace"]).resolve(), workspace.resolve())

            run_git(worker_repo, "config", "user.name", "Clonegrown Test")
            run_git(worker_repo, "config", "user.email", "clonegrown@example.test")
            (worker_repo / "README.md").write_text("changed\n", encoding="utf-8")
            run_git(worker_repo, "add", "README.md")
            run_git(worker_repo, "commit", "-m", "change greeting")

            rc, collected = self.cli(worker_repo, "collect", str(worker["id"]))
            self.assertEqual(rc, 0)
            self.assert_no_private_fields(collected)
            self.assertEqual(collected["status"], "collected")

            rc, discarded = self.cli(repo, "discard", str(worker["id"]))
            self.assertEqual(rc, 0)
            self.assert_no_private_fields(discarded)
            self.assertEqual(discarded["status"], "discarded")
            self.assertFalse(worker_repo.exists())

    def test_default_workspace_name_and_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = self.make_repo(root)
            custom = root / "custom-workers"
            rc, initialized = self.cli(
                repo, "init", str(repo), "--workspace", str(custom)
            )
            self.assertEqual(rc, 0)
            self.assertEqual(Path(initialized["workspace"]).resolve(), custom.resolve())

    def test_spawn_requires_task(self) -> None:
        parser = clonegrown_cli.build_parser()
        args = parser.parse_args(["spawn"])
        self.assertIsNone(args.task)
        self.assertIsNone(args.task_flag)


if __name__ == "__main__":
    unittest.main()
