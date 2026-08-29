"""Real clean/smudge behavior and deterministic filesystem-failure boundaries."""
from __future__ import annotations

import errno
import json
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clonegrown import ClonegrownError, collect, discard, init_workspace, recover, release, spawn, status
from clonegrown import core
from clonegrown import worker as worker_module
from clonegrown.state import quarantine_root, worker_record_path
from support import git_out, make_repo, run_git


class FilterIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.repo = make_repo(self.root)
        self.workspace = self.root / "demo-dev"
        self.driver = self.root / "filter-driver.py"
        self.driver.write_text(
            """from __future__ import annotations
import sys

mode = sys.argv[1]
data = sys.stdin.buffer.read()
if mode == "clean":
    output = data.replace(b"WORKTREE:", b"STORED:")
elif mode == "smudge":
    output = data.replace(b"STORED:", b"WORKTREE:")
else:
    raise SystemExit(2)
sys.stdout.buffer.write(output)
""",
            encoding="utf-8",
        )
        clean = shlex.join([sys.executable, str(self.driver), "clean"])
        smudge = shlex.join([sys.executable, str(self.driver), "smudge"])
        run_git(self.repo, "config", "filter.clonegrown-step.clean", clean)
        run_git(self.repo, "config", "filter.clonegrown-step.smudge", smudge)
        run_git(self.repo, "config", "filter.clonegrown-step.required", "true")
        (self.repo / ".gitattributes").write_text(
            "filtered.txt filter=clonegrown-step\n", encoding="utf-8",
        )
        (self.repo / "filtered.txt").write_text("WORKTREE: canonical\n", encoding="utf-8")
        run_git(self.repo, "add", ".gitattributes", "filtered.txt")
        self.assertEqual(git_out(self.repo, "show", ":filtered.txt"), "STORED: canonical")
        run_git(self.repo, "commit", "-q", "-m", "filtered baseline")
        init_workspace(self.repo, self.workspace)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_required_clean_smudge_filter_runs_in_clone_and_worktree_lifecycles(self) -> None:
        clean = git_out(self.repo, "config", "--get", "filter.clonegrown-step.clean")
        smudge = git_out(self.repo, "config", "--get", "filter.clonegrown-step.smudge")
        for mode in ("clone", "worktree"):
            with self.subTest(mode=mode):
                worker = spawn(self.workspace, "HEAD", f"filtered {mode}", mode=mode)
                checkout = Path(worker["path"])
                self.assertEqual(
                    (checkout / "filtered.txt").read_text(encoding="utf-8"),
                    "WORKTREE: canonical\n",
                )
                self.assertEqual(
                    git_out(checkout, "config", "--get", "filter.clonegrown-step.clean"), clean,
                )
                self.assertEqual(
                    git_out(checkout, "config", "--get", "filter.clonegrown-step.smudge"), smudge,
                )

                changed = f"WORKTREE: changed in {mode}\n"
                (checkout / "filtered.txt").write_text(changed, encoding="utf-8")
                run_git(checkout, "add", "filtered.txt")
                self.assertEqual(
                    git_out(checkout, "show", ":filtered.txt"), f"STORED: changed in {mode}",
                )
                run_git(checkout, "commit", "-q", "-m", f"filtered {mode} result")
                result_sha = git_out(checkout, "rev-parse", "HEAD")
                self.assertEqual(collect(self.workspace, worker["id"])["result_sha"], result_sha)
                self.assertEqual(
                    git_out(self.repo, "show", f"{result_sha}:filtered.txt"),
                    f"STORED: changed in {mode}",
                )
                release(self.workspace, worker["id"])
                self.assertEqual(discard(self.workspace, worker["id"])["status"], "discarded")
                self.assertEqual(status(self.workspace)["issues"], [])


class ResourceFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.repo = make_repo(self.root)
        self.workspace = self.root / "demo-dev"
        init_workspace(self.repo, self.workspace)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def record(self, worker_id: int) -> dict:
        return json.loads(worker_record_path(self.workspace, worker_id).read_text(encoding="utf-8"))

    def released_collected(self, task: str, mode: str) -> dict:
        worker = spawn(self.workspace, "HEAD", task, mode=mode)
        checkout = Path(worker["path"])
        (checkout / "work.txt").write_text(f"{task}\n", encoding="utf-8")
        run_git(checkout, "add", "work.txt")
        run_git(checkout, "commit", "-q", "-m", task)
        collect(self.workspace, worker["id"])
        release(self.workspace, worker["id"])
        return worker

    def assert_gone(self, worker: dict) -> None:
        self.assertFalse(Path(worker["path"]).parent.exists())
        self.assertFalse(quarantine_root(
            self.workspace, worker["id"], worker["worker_token"],
        ).exists())
        self.assertEqual(self.record(worker["id"])["status"], "discarded")

    def test_enospc_before_atomic_publication_preserves_or_omits_the_record(self) -> None:
        existing = self.root / "existing.json"
        original = b'{"generation": 1}\n'
        existing.write_bytes(original)
        no_space = OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))
        with patch.object(core.os, "fsync", side_effect=no_space):
            with self.assertRaises(OSError) as caught:
                core.atomic_json(existing, {"generation": 2})
        self.assertIs(caught.exception, no_space)
        self.assertEqual(existing.read_bytes(), original)
        self.assertEqual(list(self.root.glob("existing.json.*")), [])

        created = self.root / "created.json"
        no_space_create = OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))
        with patch.object(core.os, "fsync", side_effect=no_space_create):
            with self.assertRaisesRegex(ClonegrownError, "No space left on device"):
                core.atomic_json_create(created, {"generation": 1})
        self.assertFalse(created.exists())
        self.assertEqual(list(self.root.glob("created.json.*")), [])

    def test_quarantine_rename_failure_keeps_the_worker_and_withdraws_intent(self) -> None:
        for mode in ("clone", "worktree"):
            with self.subTest(mode=mode):
                worker = self.released_collected(f"rename failure {mode}", mode)
                slot = Path(worker["path"]).parent
                cross_device = OSError(errno.EXDEV, os.strerror(errno.EXDEV))
                with patch.object(worker_module.os, "rename", side_effect=cross_device):
                    with self.assertRaisesRegex(ClonegrownError, "could not move worker slot to quarantine"):
                        discard(self.workspace, worker["id"])

                self.assertTrue(slot.is_dir())
                record = self.record(worker["id"])
                self.assertEqual(record["status"], "collected")
                self.assertEqual(record["lease"], "released")
                self.assertNotIn("quarantine_path", record)
                self.assertNotIn("discard_intent", record)
                self.assertEqual(status(self.workspace)["issues"], [])
                self.assertEqual(discard(self.workspace, worker["id"])["status"], "discarded")
                self.assert_gone(worker)

    def test_partial_recursive_deletion_stays_authorized_and_recovery_finishes(self) -> None:
        for mode in ("clone", "worktree"):
            with self.subTest(mode=mode):
                worker = self.released_collected(f"partial deletion {mode}", mode)
                checkout = Path(worker["path"])
                quarantine = quarantine_root(
                    self.workspace, worker["id"], worker["worker_token"],
                )

                def delete_one_then_fail(path: str | os.PathLike[str], *args: object, **kwargs: object) -> None:
                    self.assertEqual(Path(path), quarantine)
                    victim = quarantine / checkout.name / "work.txt"
                    self.assertTrue(victim.is_file())
                    victim.unlink()
                    raise OSError(errno.EIO, os.strerror(errno.EIO), str(victim))

                with patch.object(worker_module.shutil, "rmtree", side_effect=delete_one_then_fail):
                    with self.assertRaisesRegex(ClonegrownError, "could not delete quarantined worker"):
                        discard(self.workspace, worker["id"])

                self.assertTrue(quarantine.is_dir())
                self.assertFalse((quarantine / checkout.name / "work.txt").exists())
                self.assertTrue((quarantine / checkout.name / "README.md").is_file())
                record = self.record(worker["id"])
                self.assertEqual(record["status"], "discarding")
                self.assertEqual(record["quarantine_snapshot"], worker_module.DELETION_AUTHORIZED)
                self.assertIn("Input/output error", record["quarantine_error"])
                self.assertIn(
                    "quarantine-preserved",
                    {issue["issue"] for issue in status(self.workspace)["issues"]},
                )

                actions = {
                    report.get("action") for report in recover(self.workspace)
                    if report.get("id") == worker["id"]
                }
                self.assertIn("discard-finished", actions)
                self.assert_gone(worker)


if __name__ == "__main__":
    unittest.main()
