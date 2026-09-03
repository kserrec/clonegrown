from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from clonegrown import cli
from clonegrown.state import worker_record_path
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

    def help_text(self, *args: str) -> str:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            cli.build_parser().parse_args([*args, "--help"])
        self.assertEqual(raised.exception.code, 0)
        return " ".join(output.getvalue().split())

    def test_help_exposes_lifecycle_custody_and_isolation_boundaries(self) -> None:
        top = self.help_text()
        self.assertIn("Collection preserves a commit under a canonical ref", top)
        self.assertIn("integration into a user branch is separate", top)
        self.assertIn("cooperative lease until release", top)

        spawn_help = self.help_text("spawn")
        self.assertIn("physically separate object files at spawn", spawn_help)
        self.assertIn("sharing canonical refs, config, stash, hooks, and objects", spawn_help)
        self.assertIn("abandoned or spawn_failed outcomes may allocate anew", spawn_help)

        self.assertIn(
            "does not merge, rebase, cherry-pick, or update a user branch",
            self.help_text("collect"),
        )
        self.assertIn(
            "only after every process that can write to the worker has stopped",
            self.help_text("release"),
        )

        discard_help = self.help_text("discard")
        self.assertIn("lease is cooperative", discard_help)
        self.assertIn("--discard-ignored", discard_help)
        self.assertIn("--discard-private-refs", discard_help)
        self.assertIn("failed unpublished spawn has no releasable lease", discard_help)

        recover_help = self.help_text("recover")
        self.assertIn("may finish an already-recorded quarantine deletion", recover_help)
        self.assertIn("never infers lease release from a dead process", recover_help)
        self.assertIn(
            "without repairing records, refs, worker content, or Git indexes",
            self.help_text("status"),
        )

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

    def test_historical_heartbeat_round_trips_on_disk_but_stays_out_of_cli_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            repo = make_repo(root)
            _, initialized = self.cli(repo, "init")
            workspace = Path(initialized["workspace"])
            _, worker = self.cli(repo, "spawn", "historical heartbeat")
            record_path = worker_record_path(workspace, int(worker["id"]))
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["heartbeat"] = 123.5
            record_path.write_text(json.dumps(record), encoding="utf-8")

            _, listing = self.cli(repo, "status")
            self.assertNotIn("heartbeat", listing["workers"][0])
            self.assertEqual(
                json.loads(record_path.read_text(encoding="utf-8"))["heartbeat"],
                123.5,
            )

    def test_default_workspace_name_and_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            repo = make_repo(root)
            custom = root / "custom-workers"
            rc, initialized = self.cli(repo, "init", str(repo), "--workspace", str(custom))
            self.assertEqual(rc, 0)
            self.assertEqual(Path(initialized["workspace"]).resolve(), custom.resolve())

    def test_init_refuses_a_symlink_selected_as_workspace_through_the_cli(self) -> None:
        """The CLI hands --workspace to the lifecycle lexically, so a symlink selected as the
        workspace is refused exactly as through the Python API: the link and its external
        target are left untouched, and nothing is written into the canonical repository."""
        import os
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            repo = make_repo(root)
            external = root / "external"
            external.mkdir()
            selected = root / "selected"
            os.symlink(external, selected, target_is_directory=True)
            for label, argument in (("absolute", str(selected)), ("relative", os.path.relpath(selected, repo))):
                with self.subTest(path=label):
                    process = subprocess.run(
                        [sys.executable, "-m", "clonegrown", "init", str(repo), "--workspace", argument],
                        cwd=repo, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        env={**os.environ, "PYTHONPATH": str(Path(cli.__file__).resolve().parent.parent)},
                    )
                    self.assertEqual(process.returncode, 2, process.stderr)
                    self.assertIn("workspace directory is not a real directory", process.stderr)
                    self.assertTrue(selected.is_symlink())
                    self.assertEqual(list(external.iterdir()), [])
                    self.assertFalse((repo / ".git" / "cws").exists())
            # A relative real path still works and lands where it lexically names.
            rc, initialized = self.cli(repo, "init", str(repo), "--workspace", "../real-workers")
            self.assertEqual(rc, 0)
            self.assertEqual(Path(initialized["workspace"]), root / "real-workers")

    def test_spawn_requires_task(self) -> None:
        parser = cli.build_parser()
        args = parser.parse_args(["spawn"])
        self.assertIsNone(args.task)
        self.assertIsNone(args.task_flag)


if __name__ == "__main__":
    unittest.main()
