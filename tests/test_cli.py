from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clonegrown import cli
from support import commit, git_out, make_repo, run_cli

PRIVATE_FIELDS = {"canonical_token", "worker_token", "params_hash", "owner_pid", "owner_start", "stage_root"}

READY_WORKER_KEYS = {
    "id", "status", "mode", "strong", "task", "base", "base_sha", "branch", "path", "request_id",
    "workspace_id", "created", "ready", "lease",
    "source_remote", "alternates_detached", "copied_local_config", "copied_sparse_checkout",
    "copied_auxiliary_refs", "compatibility_warnings",
}


class ClonegrownCliTests(unittest.TestCase):
    def cli(self, cwd: Path, *args: str) -> tuple[int, dict]:
        return run_cli(cwd, *args)

    def assert_no_private_fields(self, value) -> None:
        if isinstance(value, dict):
            self.assertTrue(PRIVATE_FIELDS.isdisjoint(value.keys()))
            for item in value.values():
                self.assert_no_private_fields(item)
        elif isinstance(value, list):
            for item in value:
                self.assert_no_private_fields(item)

    def test_zero_config_lifecycle_from_canonical_and_worker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            repo = make_repo(root)

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
            self.assertEqual(worker["base_sha"], git_out(repo, "rev-parse", "HEAD"))

            # Auto-discovery must also work from inside the worker itself.
            rc, state = self.cli(worker_repo, "status")
            self.assertEqual(rc, 0)
            self.assert_no_private_fields(state)
            self.assertEqual(Path(state["workspace"]).resolve(), workspace.resolve())

            commit(worker_repo, "README.md", "changed\n")

            rc, collected = self.cli(worker_repo, "collect", str(worker["id"]))
            self.assertEqual(rc, 0)
            self.assert_no_private_fields(collected)
            self.assertEqual(collected["status"], "collected")

            rc, released = self.cli(repo, "release", str(worker["id"]))
            self.assertEqual(rc, 0)
            self.assertEqual(released["lease"], "released")

            rc, discarded = self.cli(repo, "discard", str(worker["id"]))
            self.assertEqual(rc, 0)
            self.assert_no_private_fields(discarded)
            self.assertEqual(discarded["status"], "discarded")
            self.assertFalse(worker_repo.exists())

    def test_output_contract(self) -> None:
        # The CLI's JSON is a documented contract, not whatever the record happens to hold.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            repo = make_repo(root)
            _, initialized = self.cli(repo, "init")
            self.assertEqual(set(initialized), {"status", "workspace_id", "workspace", "canonical",
                                                 "object_format", "repo_name", "created"})
            _, worker = self.cli(repo, "spawn", "contract", "--request-id", "r1")
            self.assertEqual(set(worker), READY_WORKER_KEYS)
            self.assertRegex(worker["created"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            commit(Path(worker["path"]), "c.txt")
            _, collected = self.cli(repo, "collect", str(worker["id"]))
            self.assertEqual(set(collected), READY_WORKER_KEYS | {"allow_rewrite", "result_sha", "result_ref", "collected"})
            _, listing = self.cli(repo, "status")
            self.assertEqual(set(listing), {"workspace", "canonical", "workspace_id", "workers", "issues"})
            self.assertEqual(set(listing["workers"][0]), set(collected))
            _, released = self.cli(repo, "release", str(worker["id"]))
            self.assertEqual(set(released), set(collected) | {"lease_released"})
            self.assertRegex(released["lease_released"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            _, discarded = self.cli(repo, "discard", str(worker["id"]))
            self.assertEqual(set(discarded), set(released) | {"discarded"})

    def test_default_workspace_name_and_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            repo = make_repo(root)
            custom = root / "custom-workers"
            rc, initialized = self.cli(repo, "init", str(repo), "--workspace", str(custom))
            self.assertEqual(rc, 0)
            self.assertEqual(Path(initialized["workspace"]).resolve(), custom.resolve())

    def test_spawn_requires_task(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["spawn"])
        self.assertIsNone(args.task)
        self.assertIsNone(args.task_flag)


if __name__ == "__main__":
    unittest.main()
