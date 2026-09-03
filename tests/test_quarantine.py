"""Deletion through quarantine: intent, rename, recheck, verified deletion, and recovery that never lies."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from clonegrown import ClonegrownError, collect, discard, recover, release, spawn, status
from clonegrown.state import quarantine_root, worker_record_path
from support import commit, make_repo, run_cli, run_git, filesystem_accepts_non_utf8_names

ROOT = Path(__file__).resolve().parents[1]
MODES = ("clone", "worktree")


class QuarantineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name).resolve()  # macOS: TMPDIR is a symlink
        self.repo = make_repo(self.root)
        self.ws = self.root / "demo-dev"
        rc, _ = run_cli(self.repo, "init")
        self.assertEqual(rc, 0)

    def tearDown(self) -> None:
        self.td.cleanup()

    def record(self, worker_id: int) -> dict:
        return json.loads(worker_record_path(self.ws, worker_id).read_text(encoding="utf-8"))

    def quarantine_of(self, worker: dict) -> Path:
        return quarantine_root(self.ws, worker["id"], worker["worker_token"])

    def cli_process(self, *args: str, env: dict[str, str] | None = None) -> subprocess.Popen:
        full_env = {
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "CLONEGROWN_TEST_MODE": "1",
            **(env or {}),
        }
        return subprocess.Popen([sys.executable, "-m", "clonegrown", *args], cwd=self.repo, env=full_env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def released_collected(self, task: str, mode: str = "clone") -> dict:
        worker = spawn(self.ws, "HEAD", task, strong=False, mode=mode)
        commit(Path(worker["path"]), "work.txt")
        collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        return worker

    def assert_gone(self, worker: dict) -> None:
        self.assertFalse(Path(worker["path"]).parent.exists())
        self.assertFalse(self.quarantine_of(worker).exists())
        record = self.record(worker["id"])
        self.assertIn(record["status"], ("discarded", "abandoned"))
        for name in ("quarantine_path", "quarantine_started", "quarantine_snapshot", "quarantine_error"):
            self.assertNotIn(name, record)

    # --- the normal path ----------------------------------------------------------

    def test_discard_passes_through_quarantine_and_leaves_nothing(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                worker = self.released_collected(f"normal {mode}", mode)
                discarded = discard(self.ws, worker["id"])
                self.assertEqual(discarded["status"], "discarded")
                self.assert_gone(worker)
                self.assertEqual(status(self.ws)["issues"], [])

    # --- a mutation in the old final-check window is preserved ------------------------

    def test_mutation_after_the_custody_check_is_preserved_and_reported(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                worker = self.released_collected(f"mutated {mode}", mode)
                repo = Path(worker["path"])
                pause_marker = self.root / f"paused-{mode}"
                process = self.cli_process(
                    "discard", str(worker["id"]),
                    env={"CLONEGROWN_TEST_PAUSEPOINT": "discard.before_delete", "CLONEGROWN_TEST_PAUSE_MARKER": str(pause_marker),
                         "CLONEGROWN_TEST_PAUSE_SECONDS": "2"})
                deadline = time.monotonic() + 30
                while not pause_marker.exists():
                    self.assertLess(time.monotonic(), deadline, process.stderr.read() if process.poll() is not None else "")
                    time.sleep(0.02)
                # The fingerprint is taken; a second process now writes new work.
                (repo / "late-work.txt").write_text("written after the custody check\n", encoding="utf-8")
                _, stderr = process.communicate(timeout=60)
                self.assertEqual(process.returncode, 2, stderr)
                self.assertIn("preserved in quarantine", stderr)

                quarantine = self.quarantine_of(worker)
                self.assertTrue((quarantine / repo.name / "late-work.txt").is_file())
                self.assertFalse(repo.parent.exists())
                record = self.record(worker["id"])
                self.assertEqual(record["status"], "discarding")
                self.assertIsNone(record.get("owner_pid"))
                self.assertEqual(record["quarantine_path"], str(quarantine))
                self.assertIn("changed after its custody check", record["quarantine_error"])
                (listed,) = [w for w in status(self.ws)["workers"] if w["id"] == worker["id"]]
                self.assertEqual(listed["quarantine_path"], str(quarantine))
                self.assertIn("changed after", listed["quarantine_error"])
                self.assertEqual([(i["issue"], i["id"]) for i in status(self.ws)["issues"]],
                                 [("quarantine-preserved", worker["id"])])

                # Recovery keeps the quarantine, repeatedly, and says so.
                for _ in range(2):
                    actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
                    self.assertIn("quarantine-preserved", actions)
                    self.assertTrue((quarantine / repo.name / "late-work.txt").is_file())
                # Discard without a fresh acknowledgement is refused; with it, the quarantine is deleted.
                with self.assertRaisesRegex(ClonegrownError, "pass --force"):
                    discard(self.ws, worker["id"])
                self.assertEqual(discard(self.ws, worker["id"], force=True)["status"], "discarded")
                self.assert_gone(worker)

    def test_clone_ref_added_after_custody_check_is_preserved_in_quarantine(self) -> None:
        worker = self.released_collected("late private ref", "clone")
        repo = Path(worker["path"])
        pause_marker = self.root / "private-ref-paused"
        process = self.cli_process(
            "discard", str(worker["id"]), "--discard-private-refs",
            env={"CLONEGROWN_TEST_PAUSEPOINT": "discard.before_delete",
                 "CLONEGROWN_TEST_PAUSE_MARKER": str(pause_marker),
                 "CLONEGROWN_TEST_PAUSE_SECONDS": "2"},
        )
        deadline = time.monotonic() + 30
        while not pause_marker.exists():
            self.assertLess(
                time.monotonic(), deadline,
                process.stderr.read() if process.poll() is not None else "",
            )
            time.sleep(0.02)
        run_git(repo, "update-ref", "refs/stash", "HEAD")
        _, stderr = process.communicate(timeout=60)
        self.assertEqual(process.returncode, 2, stderr)
        self.assertIn("preserved in quarantine", stderr)

        quarantine_repo = self.quarantine_of(worker) / repo.name
        self.assertEqual(run_git(quarantine_repo, "rev-parse", "refs/stash").returncode, 0)
        self.assertIn(("quarantine-preserved", worker["id"]), [
            (issue["issue"], issue.get("id")) for issue in status(self.ws)["issues"]
        ])

    # --- partial deletion stays recoverable ---------------------------------------------

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_partial_deletion_keeps_the_quarantine_and_the_error(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                # An ignored directory (acknowledged with --discard-ignored) that cannot be deleted.
                exclude = self.repo / ".git" / "info" / "exclude"
                exclude.parent.mkdir(parents=True, exist_ok=True)
                exclude.write_text("stuck/\n", encoding="utf-8")
                worker = self.released_collected(f"partial {mode}", mode)
                repo = Path(worker["path"])
                quarantine = self.quarantine_of(worker)
                stuck = repo / "stuck"
                stuck.mkdir()
                (stuck / "file").write_text("x\n", encoding="utf-8")
                stuck.chmod(0o555)
                try:
                    with self.assertRaisesRegex(ClonegrownError, "could not delete quarantined worker"):
                        discard(self.ws, worker["id"], discard_ignored=True)
                    self.assertTrue(quarantine.exists())
                    record = self.record(worker["id"])
                    self.assertEqual(record["status"], "discarding")
                    self.assertEqual(record["quarantine_path"], str(quarantine))
                    self.assertIn("could not delete", record["quarantine_error"])
                    actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
                    self.assertIn("quarantine-preserved", actions)
                    self.assertEqual(self.record(worker["id"])["status"], "discarding")
                    # A bare discard finishes an already-authorized deletion, but cannot yet.
                    with self.assertRaisesRegex(ClonegrownError, "could not delete"):
                        discard(self.ws, worker["id"])
                finally:
                    for candidate in (quarantine / repo.name / "stuck", stuck):
                        if candidate.exists():
                            candidate.chmod(0o755)
                actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
                self.assertIn("discard-finished", actions)
                self.assert_gone(worker)

    # --- the quarantine path is derived and must be free --------------------------------

    def test_occupied_quarantine_path_refuses_and_keeps_the_worker(self) -> None:
        worker = self.released_collected("collision")
        quarantine = self.quarantine_of(worker)
        quarantine.mkdir(parents=True)
        (quarantine / "someone-elses").write_text("keep\n", encoding="utf-8")
        with self.assertRaisesRegex(ClonegrownError, "already occupied"):
            discard(self.ws, worker["id"])
        self.assertTrue(Path(worker["path"]).is_dir())
        self.assertEqual((quarantine / "someone-elses").read_text(encoding="utf-8"), "keep\n")
        record = self.record(worker["id"])
        self.assertEqual(record["status"], "collected")
        self.assertNotIn("quarantine_path", record)
        listing = status(self.ws)
        self.assertEqual([i["issue"] for i in listing["issues"]], ["orphan-quarantine"])
        self.assertEqual([r["action"] for r in recover(self.ws) if "path" in r and "id" not in r], ["orphan-quarantine"])
        self.assertTrue((quarantine / "someone-elses").is_file())

    def test_symlinked_quarantine_directory_is_refused(self) -> None:
        worker = self.released_collected("symlink")
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (self.ws / ".cws" / "quarantine").symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(ClonegrownError, "not a real directory"):
            discard(self.ws, worker["id"])
        self.assertTrue(Path(worker["path"]).is_dir())
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.assertEqual(self.record(worker["id"])["status"], "collected")

    # --- every new boundary, interrupted, in both modes ---------------------------------

    def test_interrupting_every_boundary_recovers_idempotently(self) -> None:
        common_boundaries = (
            "discard.after_mark", "discard.before_delete", "discard.after_quarantine",
            "discard.after_recheck", "discard.after_delete",
        )
        for mode in MODES:
            boundaries = common_boundaries
            if mode == "worktree":
                boundaries += ("discard.after_admin_cleanup", "discard.after_branch_cleanup")
            boundaries += ("discard.after_metadata",)
            for boundary in boundaries:
                with self.subTest(mode=mode, boundary=boundary):
                    worker = self.released_collected(f"{boundary} {mode}", mode)
                    process = self.cli_process("discard", str(worker["id"]), env={"CLONEGROWN_TEST_FAILPOINT": boundary})
                    _, stderr = process.communicate(timeout=120)
                    self.assertEqual(process.returncode, 88, stderr)
                    for _ in range(2):
                        reports = recover(self.ws)
                        listed = [w for w in status(self.ws)["workers"] if w["id"] == worker["id"]][0]
                        if listed["status"] == "collected":
                            # Interrupted before anything moved: the worker is intact and discard is retried.
                            self.assertTrue(Path(worker["path"]).is_dir())
                            self.assertEqual(discard(self.ws, worker["id"])["status"], "discarded")
                        self.assert_gone(worker)
                        self.assertEqual(status(self.ws)["issues"], [])
                        self.assertNotIn("quarantine-preserved",
                                         {r.get("action") for r in reports if r.get("id") == worker["id"]})

    def test_abandonment_interrupted_before_the_rename_resumes_through_quarantine(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                worker = spawn(self.ws, "HEAD", f"abandon {mode}", strong=False, mode=mode)
                (Path(worker["path"]) / "scratch.txt").write_text("x\n", encoding="utf-8")
                release(self.ws, worker["id"])
                process = self.cli_process("discard", str(worker["id"]), "--abandon",
                                           env={"CLONEGROWN_TEST_FAILPOINT": "discard.after_mark"})
                _, stderr = process.communicate(timeout=120)
                self.assertEqual(process.returncode, 88, stderr)
                actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
                self.assertIn("abandon-finished", actions)
                self.assert_gone(worker)
                self.assertEqual(self.record(worker["id"])["status"], "abandoned")

    # --- the record is honest about residue ------------------------------------------

    def test_residue_after_a_crash_is_never_labelled_gone(self) -> None:
        worker = self.released_collected("residue")
        process = self.cli_process("discard", str(worker["id"]), env={"CLONEGROWN_TEST_FAILPOINT": "discard.after_quarantine"})
        _, stderr = process.communicate(timeout=120)
        self.assertEqual(process.returncode, 88, stderr)
        quarantine = self.quarantine_of(worker)
        # Someone tampers with the quarantined worker's identity before recovery runs.
        marker = next(quarantine.rglob("cws-worker.json"))
        marker.write_text("{}", encoding="utf-8")
        actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("quarantine-preserved", actions)
        self.assertTrue(quarantine.exists())
        record = self.record(worker["id"])
        self.assertEqual(record["status"], "discarding")
        self.assertIn("marker mismatch", record["quarantine_error"])

    # --- findings of the Phase 2 cold review ------------------------------------------

    def test_crash_between_intent_and_rename_resumes_or_preserves(self) -> None:
        # discard.before_delete now sits after the path and fingerprint are persisted and
        # before the rename: the record describes a quarantine that does not exist yet.
        for mode, mutate in (("clone", False), ("worktree", False), ("clone", True), ("worktree", True)):
            with self.subTest(mode=mode, mutate=mutate):
                worker = self.released_collected(f"intent {mode} {mutate}", mode)
                process = self.cli_process("discard", str(worker["id"]), env={"CLONEGROWN_TEST_FAILPOINT": "discard.before_delete"})
                _, stderr = process.communicate(timeout=120)
                self.assertEqual(process.returncode, 88, stderr)
                record = self.record(worker["id"])
                self.assertEqual(record["quarantine_path"], str(self.quarantine_of(worker)))
                self.assertTrue(Path(worker["path"]).is_dir())
                self.assertFalse(self.quarantine_of(worker).exists())
                if mutate:
                    commit(Path(worker["path"]), "late.txt")
                # A normal discard that never moved anything is withdrawn: the worker stays where
                # it is, as it is, and the caller decides again with the current facts.
                actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
                self.assertIn("discard-reset", actions)
                self.assertTrue(Path(worker["path"]).is_dir())
                record = self.record(worker["id"])
                self.assertEqual(record["status"], "collected")
                self.assertNotIn("quarantine_path", record)
                self.assertNotIn("discard_intent", record)
                self.assertEqual(status(self.ws)["issues"], [])
                if mutate:
                    with self.assertRaisesRegex(ClonegrownError, "--force"):
                        discard(self.ws, worker["id"])
                    self.assertEqual(discard(self.ws, worker["id"], force=True)["status"], "discarded")
                else:
                    self.assertEqual(discard(self.ws, worker["id"])["status"], "discarded")
                self.assert_gone(worker)

    def test_abandonment_crashed_before_the_rename_resumes_against_its_fingerprint(self) -> None:
        for mode, mutate in (("clone", False), ("worktree", True)):
            with self.subTest(mode=mode, mutate=mutate):
                worker = spawn(self.ws, "HEAD", f"abandon intent {mode}", strong=False, mode=mode)
                release(self.ws, worker["id"])
                process = self.cli_process("discard", str(worker["id"]), "--abandon",
                                           env={"CLONEGROWN_TEST_FAILPOINT": "discard.before_delete"})
                _, stderr = process.communicate(timeout=120)
                self.assertEqual(process.returncode, 88, stderr)
                if mutate:
                    (Path(worker["path"]) / "late.txt").write_text("after the fingerprint\n", encoding="utf-8")
                actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
                if mutate:
                    self.assertIn("quarantine-preserved", actions)
                    self.assertTrue((self.quarantine_of(worker) / Path(worker["path"]).name / "late.txt").is_file())
                    self.assertEqual(discard(self.ws, worker["id"], abandon=True)["status"], "abandoned")
                else:
                    self.assertIn("abandon-finished", actions)
                self.assert_gone(worker)

    def test_quarantine_the_record_never_learned_of_is_adopted_not_ignored(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                worker = self.released_collected(f"unrecorded {mode}", mode)
                process = self.cli_process("discard", str(worker["id"]), env={"CLONEGROWN_TEST_FAILPOINT": "discard.after_quarantine"})
                process.communicate(timeout=120)
                path = worker_record_path(self.ws, worker["id"])
                data = self.record(worker["id"])
                for name in ("quarantine_path", "quarantine_started", "quarantine_snapshot"):
                    data.pop(name, None)  # a record from before the fields were persisted first
                path.write_text(json.dumps(data), encoding="utf-8")
                quarantine = self.quarantine_of(worker)
                self.assertTrue(quarantine.is_dir())

                actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}

                self.assertIn("quarantine-preserved", actions)
                self.assertTrue(quarantine.is_dir())
                after = self.record(worker["id"])
                self.assertEqual(after["status"], "discarding")
                self.assertEqual(after["quarantine_path"], str(quarantine))
                self.assertIn("without a recorded custody fingerprint", after["quarantine_error"])
                self.assertEqual([(i["issue"], i["id"]) for i in status(self.ws)["issues"]],
                                 [("quarantine-preserved", worker["id"])])
                with self.assertRaisesRegex(ClonegrownError, "pass --force"):
                    discard(self.ws, worker["id"])
                self.assertEqual(discard(self.ws, worker["id"], force=True)["status"], "discarded")
                self.assert_gone(worker)
                if mode == "worktree":
                    self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", f"refs/heads/{worker['branch']}",
                                                check=False).returncode, 0)

    def test_content_only_rewrite_after_the_fingerprint_is_preserved(self) -> None:
        worker = spawn(self.ws, "HEAD", "rewrite", strong=False)
        repo = Path(worker["path"])
        notes = repo / "notes.txt"
        notes.write_text("first draft\n", encoding="utf-8")
        sibling = repo.parent / "beside-the-repo.txt"
        sibling.write_text("sibling\n", encoding="utf-8")
        release(self.ws, worker["id"])
        pause_marker = self.root / "paused-rewrite"
        process = self.cli_process(
            "discard", str(worker["id"]), "--abandon",
            env={"CLONEGROWN_TEST_PAUSEPOINT": "discard.before_delete", "CLONEGROWN_TEST_PAUSE_MARKER": str(pause_marker),
                 "CLONEGROWN_TEST_PAUSE_SECONDS": "2"})
        deadline = time.monotonic() + 30
        while not pause_marker.exists():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.02)
        time.sleep(0.05)  # a distinct modification timestamp
        notes.write_text("second draft, same path\n", encoding="utf-8")
        _, stderr = process.communicate(timeout=60)
        self.assertEqual(process.returncode, 2, stderr)
        quarantine = self.quarantine_of(worker)
        self.assertEqual((quarantine / repo.name / "notes.txt").read_text(encoding="utf-8"), "second draft, same path\n")
        self.assertEqual((quarantine / "beside-the-repo.txt").read_text(encoding="utf-8"), "sibling\n")
        self.assertEqual(discard(self.ws, worker["id"], abandon=True)["status"], "abandoned")
        self.assert_gone(worker)

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_failed_spawn_with_stage_residue_stays_valid_and_discardable(self) -> None:
        worker = spawn(self.ws, "HEAD", "keep valid", strong=False)
        release(self.ws, worker["id"])
        # Model a failed spawn whose stage could not be removed: the record is spawn_failed and
        # a stage directory with an undeletable entry remains.
        path = worker_record_path(self.ws, worker["id"])
        data = self.record(worker["id"])
        import shutil
        shutil.rmtree(Path(worker["path"]).parent)
        stage = Path(data["stage_root"])
        (stage / "stuck").mkdir(parents=True)
        (stage / "stuck" / "f").write_text("x\n", encoding="utf-8")
        (stage / "stuck").chmod(0o555)
        data.update(status="spawn_failed", failed=1.0, error="injected", ready=None, lease=None)
        for name in ("source_remote", "alternates_detached", "copied_local_config", "copied_sparse_checkout",
                     "copied_auxiliary_refs", "compatibility_warnings", "lease_released"):
            data.pop(name, None)
        path.write_text(json.dumps(data), encoding="utf-8")
        try:
            with self.assertRaisesRegex(ClonegrownError, "could not delete worker stage"):
                discard(self.ws, worker["id"], abandon=True)
            listed = [w for w in status(self.ws)["workers"] if w["id"] == worker["id"]][0]
            self.assertEqual(listed["status"], "discarding")  # a valid, recoverable record
            self.assertIn("deletion incomplete", listed["error"])
            self.assertEqual({i["issue"] for i in status(self.ws)["issues"]}, {"stage-residue", "deletion-incomplete"})
            actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
            self.assertIn("discard-cleanup-incomplete", actions)
            self.assertEqual(self.record(worker["id"])["status"], "discarding")
        finally:
            (stage / "stuck").chmod(0o755)
        self.assertEqual(discard(self.ws, worker["id"])["status"], "abandoned")  # finishing needs no new flag
        self.assertFalse(stage.exists())

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_stage_failure_after_content_deletion_stays_discarding(self) -> None:
        worker = self.released_collected("stage after")
        stage = Path(self.record(worker["id"])["stage_root"])
        (stage / "stuck").mkdir(parents=True)
        (stage / "stuck" / "f").write_text("x\n", encoding="utf-8")
        (stage / "stuck").chmod(0o555)
        try:
            with self.assertRaisesRegex(ClonegrownError, "could not delete worker stage"):
                discard(self.ws, worker["id"])
            record = self.record(worker["id"])
            self.assertEqual(record["status"], "discarding")
            self.assertIn("deletion incomplete", record["error"])
            self.assertFalse(Path(worker["path"]).parent.exists())
            actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
            self.assertIn("discard-cleanup-incomplete", actions)
            self.assertEqual(self.record(worker["id"])["status"], "discarding")
        finally:
            (stage / "stuck").chmod(0o755)
        self.assertIn("discard-finished", {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]})
        self.assert_gone(worker)

    def test_recover_continues_past_a_worker_it_cannot_inspect(self) -> None:
        first = self.cli_process("spawn", "uninspectable", "--request-id", "u", env={"CLONEGROWN_TEST_FAILPOINT": "spawn.after_publish"})
        first.communicate(timeout=120)
        second = self.cli_process("spawn", "fine", "--request-id", "f", env={"CLONEGROWN_TEST_FAILPOINT": "spawn.after_publish"})
        second.communicate(timeout=120)
        workers = {w["request_id"]: w for w in status(self.ws)["workers"]}
        broken_index = Path(workers["u"]["path"]) / ".git" / "index"
        broken_index.write_bytes(b"not an index")
        reports = recover(self.ws)
        by_id = {r.get("id"): r.get("action") for r in reports if "id" in r}
        self.assertEqual(by_id[workers["u"]["id"]], "spawn-preserved-broken")
        self.assertEqual(by_id[workers["f"]["id"]], "spawn-publish-finished")
        after = {w["request_id"]: w for w in status(self.ws)["workers"]}
        self.assertEqual(after["u"]["status"], "broken")
        self.assertIn("cannot inspect", after["u"]["error"])
        self.assertEqual(after["f"]["status"], "ready")
        self.assertTrue(Path(workers["u"]["path"]).is_dir())

    def test_tombstone_slot_reoccupied_is_reported_not_deleted(self) -> None:
        worker = self.released_collected("tombstone")
        import shutil
        keep = self.root / "restored-copy"
        shutil.copytree(Path(worker["path"]).parent, keep)
        self.assertEqual(discard(self.ws, worker["id"])["status"], "discarded")
        shutil.copytree(keep, Path(worker["path"]).parent)  # the user restores an authentic copy
        for _ in range(2):
            actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
            self.assertIn("tombstone-path-left", actions)
            self.assertNotIn("tombstone-path-cleaned", actions)
            self.assertTrue((Path(worker["path"]) / "work.txt").is_file())

    def test_dangling_worker_slot_symlink_never_counts_as_absent(self) -> None:
        worker = self.released_collected("dangling slot")
        slot = Path(worker["path"]).parent
        relocated = self.root / "relocated-authentic-worker"
        record_path = worker_record_path(self.ws, worker["id"])
        before = record_path.read_bytes()
        os.rename(slot, relocated)
        os.symlink(self.root / "missing-target", slot, target_is_directory=True)
        try:
            with self.assertRaisesRegex(ClonegrownError, "symlink"):
                discard(self.ws, worker["id"])
            self.assertEqual(record_path.read_bytes(), before)
            self.assertTrue(os.path.lexists(slot) and slot.is_symlink() and not slot.exists())
            self.assertTrue((relocated / self.repo.name / "work.txt").is_file())

            issues = [issue for issue in status(self.ws)["issues"] if issue.get("id") == worker["id"]]
            self.assertEqual([issue["issue"] for issue in issues], ["worker-authentication-failed"])
            reports = [item for item in recover(self.ws) if item.get("id") == worker["id"]]
            self.assertIn("collected-worker-path-invalid", [item["action"] for item in reports])
            self.assertEqual(record_path.read_bytes(), before)
            self.assertTrue(os.path.lexists(slot))
            self.assertTrue((relocated / self.repo.name / "work.txt").is_file())
        finally:
            if os.path.lexists(slot):
                slot.unlink()
            if relocated.exists():
                shutil.rmtree(relocated)

    def test_dangling_tombstone_slot_is_reported_and_left(self) -> None:
        worker = self.released_collected("dangling tombstone")
        discard(self.ws, worker["id"])
        slot = Path(worker["path"]).parent
        os.symlink(self.root / "missing-after-discard", slot, target_is_directory=True)
        self.assertEqual(
            [(issue["issue"], issue["id"]) for issue in status(self.ws)["issues"]],
            [("tombstone-path-occupied", worker["id"])],
        )
        actions = [item["action"] for item in recover(self.ws) if item.get("id") == worker["id"]]
        self.assertIn("tombstone-path-left", actions)
        self.assertTrue(os.path.lexists(slot) and not slot.exists())
        slot.unlink()

    def test_quarantine_directory_as_file_or_symlink_is_refused_and_reported(self) -> None:
        worker = self.released_collected("bad root")
        root = self.ws / ".cws" / "quarantine"
        root.write_text("not a directory\n", encoding="utf-8")
        with self.assertRaisesRegex(ClonegrownError, "not a real directory"):
            discard(self.ws, worker["id"])
        self.assertTrue(Path(worker["path"]).is_dir())
        self.assertEqual(self.record(worker["id"])["status"], "collected")
        root.unlink()
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "victim").mkdir()
        root.symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(ClonegrownError, "not a real directory"):
            status(self.ws)
        with self.assertRaisesRegex(ClonegrownError, "not a real directory"):
            discard(self.ws, worker["id"])
        self.assertTrue((elsewhere / "victim").is_dir())

    def test_stale_intent_never_bypasses_the_acknowledgements(self) -> None:
        # A discard that crashed right after recording its intent must not be finished by a
        # flag-less discard: the worker is re-authorized against its current state.
        for mode in MODES:
            with self.subTest(mode=mode):
                worker = self.released_collected(f"stale intent {mode}", mode)
                process = self.cli_process("discard", str(worker["id"]), env={"CLONEGROWN_TEST_FAILPOINT": "discard.after_mark"})
                _, stderr = process.communicate(timeout=120)
                self.assertEqual(process.returncode, 88, stderr)
                repo = Path(worker["path"])
                commit(repo, "late.txt")
                (repo / "cache.log").write_text("ignored\n", encoding="utf-8")
                (repo / ".gitignore").write_text("*.log\n", encoding="utf-8")
                commit(repo, ".gitignore", "*.log\n")
                with self.assertRaisesRegex(ClonegrownError, "--force") as caught:
                    discard(self.ws, worker["id"])
                self.assertIn("--discard-ignored", str(caught.exception))
                self.assertTrue(repo.is_dir())
                record = self.record(worker["id"])
                self.assertEqual(record["status"], "collected")
                self.assertNotIn("discard_intent", record)
                with self.assertRaisesRegex(ClonegrownError, "--discard-ignored"):
                    discard(self.ws, worker["id"], force=True)
                self.assertEqual(discard(self.ws, worker["id"], force=True, discard_ignored=True)["status"], "discarded")
                self.assert_gone(worker)

    def test_rewrite_inside_an_ignored_directory_is_preserved(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                worker = spawn(self.ws, "HEAD", f"ignored dir {mode}", strong=False, mode=mode)
                repo = Path(worker["path"])
                (repo / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
                commit(repo, ".gitignore", "node_modules/\n")
                deep = repo / "node_modules" / "pkg" / "lib"
                deep.mkdir(parents=True)
                (deep / "out.txt").write_text("first build\n", encoding="utf-8")
                release(self.ws, worker["id"])
                pause_marker = self.root / f"paused-ignored-{mode}"
                process = self.cli_process(
                    "discard", str(worker["id"]), "--abandon",
                    env={"CLONEGROWN_TEST_PAUSEPOINT": "discard.before_delete", "CLONEGROWN_TEST_PAUSE_MARKER": str(pause_marker),
                         "CLONEGROWN_TEST_PAUSE_SECONDS": "2"})
                deadline = time.monotonic() + 30
                while not pause_marker.exists():
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.02)
                time.sleep(0.05)
                (deep / "out.txt").write_text("rebuilt while the discard was deciding\n", encoding="utf-8")
                _, stderr = process.communicate(timeout=60)
                self.assertEqual(process.returncode, 2, stderr)
                self.assertIn("preserved in quarantine", stderr)
                self.assertEqual(
                    (self.quarantine_of(worker) / repo.name / "node_modules" / "pkg" / "lib" / "out.txt").read_text(encoding="utf-8"),
                    "rebuilt while the discard was deciding\n")
                self.assertEqual(discard(self.ws, worker["id"], abandon=True)["status"], "abandoned")
                self.assert_gone(worker)

    def test_foreign_content_at_the_derived_quarantine_path_is_never_repaired_or_deleted(self) -> None:
        import shutil
        # Worker Y's slot copied to worker X's derived quarantine path (worktree mode): X's recovery
        # must neither redirect Y's admin entry nor treat the copy as X's quarantine.
        x = spawn(self.ws, "HEAD", "x", strong=False, mode="worktree")
        y = spawn(self.ws, "HEAD", "y", strong=False, mode="worktree")
        release(self.ws, x["id"])
        process = self.cli_process("discard", str(x["id"]), "--abandon", env={"CLONEGROWN_TEST_FAILPOINT": "discard.after_mark"})
        process.communicate(timeout=120)
        target = self.quarantine_of(x)
        target.parent.mkdir(exist_ok=True)
        shutil.copytree(Path(y["path"]).parent, target)
        y_gitdir = (Path(y["worktree_admin"]) / "gitdir").read_text(encoding="utf-8")

        actions = {r.get("action") for r in recover(self.ws) if r.get("id") == x["id"]}

        self.assertIn("quarantine-path-occupied", actions)
        self.assertEqual((Path(y["worktree_admin"]) / "gitdir").read_text(encoding="utf-8"), y_gitdir)
        self.assertTrue(target.is_dir())
        self.assertTrue(Path(x["path"]).is_dir())
        record = self.record(x["id"])
        self.assertEqual(record["status"], "discarding")
        self.assertIn("slot is still in place", record["error"])
        self.assertNotIn("quarantine_path", record)
        with self.assertRaisesRegex(ClonegrownError, "slot is still in place"):
            discard(self.ws, x["id"], abandon=True)
        self.assertTrue(target.is_dir())
        sha = commit(Path(y["path"]), "still-y.txt")
        self.assertEqual(collect(self.ws, y["id"])["result_sha"], sha)
        # The user moves the occupant away; recovery then finishes the abandonment.
        shutil.move(str(target), str(self.root / "moved-away"))
        self.assertIn("abandon-finished", {r.get("action") for r in recover(self.ws) if r.get("id") == x["id"]})
        self.assert_gone(x)

    def test_occupied_derived_path_withdraws_a_normal_discard(self) -> None:
        worker = self.released_collected("occupied normal")
        process = self.cli_process("discard", str(worker["id"]), env={"CLONEGROWN_TEST_FAILPOINT": "discard.after_mark"})
        process.communicate(timeout=120)
        target = self.quarantine_of(worker)
        target.mkdir(parents=True)
        (target / "intruder").write_text("keep\n", encoding="utf-8")
        actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("quarantine-path-occupied", actions)
        self.assertEqual(self.record(worker["id"])["status"], "collected")
        self.assertTrue((target / "intruder").is_file())
        self.assertIn("orphan-quarantine", [i["issue"] for i in status(self.ws)["issues"]])
        with self.assertRaisesRegex(ClonegrownError, "already occupied"):
            discard(self.ws, worker["id"])
        self.assertTrue(Path(worker["path"]).is_dir())

    def test_status_reports_a_reoccupied_tombstone_slot(self) -> None:
        import shutil
        worker = self.released_collected("tombstone status")
        keep = self.root / "copy"
        shutil.copytree(Path(worker["path"]).parent, keep)
        discard(self.ws, worker["id"])
        shutil.copytree(keep, Path(worker["path"]).parent)
        issues = status(self.ws)["issues"]
        self.assertEqual([(i["issue"], i["id"]) for i in issues], [("tombstone-path-occupied", worker["id"])])

    def test_rewrite_inside_a_nested_repository_is_preserved(self) -> None:
        worker = spawn(self.ws, "HEAD", "nested repo", strong=False)
        repo = Path(worker["path"])
        nested = repo / "vendor" / "dep"
        nested.mkdir(parents=True)
        run_git(nested, "init", "-q")
        (nested / "sub").mkdir()
        (nested / "sub" / "deep.txt").write_text("v1\n", encoding="utf-8")
        release(self.ws, worker["id"])
        pause_marker = self.root / "paused-nested"
        process = self.cli_process(
            "discard", str(worker["id"]), "--abandon",
            env={"CLONEGROWN_TEST_PAUSEPOINT": "discard.before_delete", "CLONEGROWN_TEST_PAUSE_MARKER": str(pause_marker),
                 "CLONEGROWN_TEST_PAUSE_SECONDS": "2"})
        deadline = time.monotonic() + 30
        while not pause_marker.exists():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.02)
        time.sleep(0.05)
        (nested / "sub" / "deep.txt").write_text("v2 written during the decision\n", encoding="utf-8")
        _, stderr = process.communicate(timeout=60)
        self.assertEqual(process.returncode, 2, stderr)
        self.assertIn("preserved in quarantine", stderr)
        self.assertEqual((self.quarantine_of(worker) / repo.name / "vendor" / "dep" / "sub" / "deep.txt").read_text(encoding="utf-8"),
                         "v2 written during the decision\n")
        self.assertEqual(discard(self.ws, worker["id"], abandon=True)["status"], "abandoned")
        self.assert_gone(worker)

    def test_quarantined_worktree_whose_admin_was_pruned_is_still_deletable_with_acknowledgement(self) -> None:
        import shutil
        worker = self.released_collected("pruned admin", "worktree")
        process = self.cli_process("discard", str(worker["id"]), env={"CLONEGROWN_TEST_FAILPOINT": "discard.after_quarantine"})
        process.communicate(timeout=120)
        shutil.rmtree(Path(worker["worktree_admin"]))  # what `git worktree prune` would do to a moved checkout
        actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("quarantine-preserved", actions)
        record = self.record(worker["id"])
        self.assertIn("admin directory", record["quarantine_error"])
        self.assertIn("pruned", record["quarantine_error"])
        self.assertTrue(self.quarantine_of(worker).is_dir())
        with self.assertRaisesRegex(ClonegrownError, "pass --force"):
            discard(self.ws, worker["id"])
        self.assertEqual(discard(self.ws, worker["id"], force=True)["status"], "discarded")
        self.assert_gone(worker)
        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", f"refs/heads/{worker['branch']}",
                                    check=False).returncode, 0)

    def test_authentic_copies_in_both_slot_and_quarantine_are_never_resolved_automatically(self) -> None:
        import shutil
        for mode in MODES:
            with self.subTest(mode=mode):
                worker = spawn(self.ws, "HEAD", f"two copies {mode}", strong=False, mode=mode)
                release(self.ws, worker["id"])
                process = self.cli_process("discard", str(worker["id"]), "--abandon",
                                           env={"CLONEGROWN_TEST_FAILPOINT": "discard.after_quarantine"})
                process.communicate(timeout=120)
                quarantine = self.quarantine_of(worker)
                shutil.copytree(quarantine, Path(worker["path"]).parent)  # an authentic copy is put back in the slot
                for _ in range(2):
                    actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
                    self.assertIn("quarantine-preserved", actions)
                    self.assertIn("both in its slot and at its quarantine path", self.record(worker["id"])["quarantine_error"])
                with self.assertRaisesRegex(ClonegrownError, "both in its slot"):
                    discard(self.ws, worker["id"], abandon=True)
                self.assertTrue(quarantine.is_dir())
                self.assertTrue(Path(worker["path"]).is_dir())
                self.assertEqual(self.record(worker["id"])["status"], "discarding")
                shutil.rmtree(Path(worker["path"]).parent)
                self.assertIn("abandon-finished", {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]})
                self.assert_gone(worker)

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_one_unreadable_quarantine_does_not_stop_recovery_of_the_others(self) -> None:
        stuck = self.released_collected("unreadable")
        fine = self.released_collected("fine")
        for worker in (stuck, fine):
            process = self.cli_process("discard", str(worker["id"]), env={"CLONEGROWN_TEST_FAILPOINT": "discard.after_quarantine"})
            process.communicate(timeout=120)
        stuck_repo = self.quarantine_of(stuck) / Path(stuck["path"]).name
        stuck_repo.chmod(0)  # Git cannot even enter it: a bare OSError, not a Clonegrown error
        try:
            reports = recover(self.ws)
            by_id = {r.get("id"): r.get("action") for r in reports if "id" in r}
            self.assertEqual(by_id[fine["id"]], "discard-finished")
            self.assertEqual(by_id[stuck["id"]], "quarantine-preserved")
            self.assertIn("quarantine_error", self.record(stuck["id"]))
            self.assert_gone(fine)
            self.assertTrue(self.quarantine_of(stuck).exists())
        finally:
            stuck_repo.chmod(0o755)
        self.assertIn("discard-finished", {r.get("action") for r in recover(self.ws) if r.get("id") == stuck["id"]})
        self.assert_gone(stuck)

    def test_unicode_digit_names_and_leading_zeros_are_not_worker_ids(self) -> None:
        (self.ws / "²").mkdir()
        (self.ws / "01").mkdir()
        (self.ws / ".cws" / "workers" / "³.json").write_text("{}", encoding="utf-8")
        listing = status(self.ws)
        self.assertEqual([i["issue"] for i in listing["issues"]], ["unexpected-metadata-file"])
        self.assertEqual([r["action"] for r in recover(self.ws)], ["unknown-metadata-file"])
        (self.ws / "7").mkdir()
        self.assertIn(("orphan-worker-directory", 7), [(i["issue"], i.get("id")) for i in status(self.ws)["issues"]])

    def test_non_utf8_workspace_path_runs_the_whole_lifecycle(self) -> None:
        if not filesystem_accepts_non_utf8_names(self.root):
            self.skipTest("this filesystem rejects non-UTF-8 file names")
        raw_root = os.fsencode(str(self.root)) + b"/w\xff-space"
        os.mkdir(raw_root)
        root = Path(os.fsdecode(raw_root))
        repo = make_repo(root, "app")
        rc, initialized = run_cli(repo, "init")
        self.assertEqual(rc, 0)
        ws = Path(initialized["workspace"])
        for mode in MODES:
            with self.subTest(mode=mode):
                worker = spawn(ws, "HEAD", f"bytes {mode}", strong=False, mode=mode)
                sha = commit(Path(worker["path"]), "b.txt")
                self.assertEqual(collect(ws, worker["id"])["result_sha"], sha)
                release(ws, worker["id"])
                self.assertEqual(discard(ws, worker["id"])["status"], "discarded")
                self.assertFalse(Path(worker["path"]).parent.exists())
                self.assertEqual(status(ws)["issues"], [])
        remaining = sorted(p.name for p in (repo / ".git" / "worktrees").iterdir()) if (repo / ".git" / "worktrees").exists() else []
        self.assertEqual(remaining, [])

    def test_request_id_retry_after_discard_returns_the_completed_record(self) -> None:
        # A discarded request is complete; retrying its id returns that outcome rather than a new worker.
        worker = spawn(self.ws, "HEAD", "done", strong=False, request_id="r-done")
        commit(Path(worker["path"]), "d.txt")
        collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        discard(self.ws, worker["id"])
        again = spawn(self.ws, "HEAD", "done", strong=False, request_id="r-done")
        self.assertEqual((again["id"], again["status"]), (worker["id"], "discarded"))
        abandoned = spawn(self.ws, "HEAD", "gone", strong=False, request_id="r-gone")
        release(self.ws, abandoned["id"])
        discard(self.ws, abandoned["id"], abandon=True)
        fresh = spawn(self.ws, "HEAD", "gone", strong=False, request_id="r-gone")
        self.assertNotEqual(fresh["id"], abandoned["id"])
        self.assertEqual(fresh["status"], "ready")

    def test_pending_spawn_details_cannot_smuggle_other_fields(self) -> None:
        worker = self.released_collected("details")
        path = worker_record_path(self.ws, worker["id"])
        data = self.record(worker["id"])
        data["pending_spawn_details"] = {"lease": "released", "source_remote": None}
        path.write_text(json.dumps(data), encoding="utf-8")
        listing = status(self.ws)
        self.assertEqual([i["issue"] for i in listing["issues"]], ["invalid-worker-metadata"])
        self.assertIn("not spawn details", listing["issues"][0]["error"])

    def test_fifo_and_socket_changes_are_fingerprinted(self) -> None:
        import socket
        from clonegrown.worker import custody_fingerprint
        worker = spawn(self.ws, "HEAD", "special files", strong=False)
        repo = Path(worker["path"])
        before = custody_fingerprint(repo)
        os.mkfifo(repo / "pipe")
        with_fifo = custody_fingerprint(repo)
        self.assertNotEqual(before, with_fifo)
        listener = socket.socket(socket.AF_UNIX)
        previous = os.getcwd()
        try:
            os.chdir(repo)  # Unix socket paths are short; bind relative to the worker
            listener.bind("sock")
            self.assertNotEqual(with_fifo, custody_fingerprint(repo))
        finally:
            listener.close()
            os.chdir(previous)
        os.unlink(repo / "sock")
        self.assertEqual(with_fifo, custody_fingerprint(repo))

    def test_cli_status_shows_quarantine_without_bookkeeping(self) -> None:
        worker = self.released_collected("cli view")
        process = self.cli_process("discard", str(worker["id"]), env={"CLONEGROWN_TEST_FAILPOINT": "discard.after_quarantine"})
        process.communicate(timeout=120)
        rc, listing = run_cli(self.repo, "status")
        self.assertEqual(rc, 0)
        (item,) = listing["workers"]
        self.assertEqual(item["status"], "discarding")
        self.assertEqual(item["quarantine_path"], str(self.quarantine_of(worker)))
        self.assertNotIn("quarantine_snapshot", item)
        self.assertNotIn("worker_token", item)
        rc, reports = run_cli(self.repo, "recover")
        self.assertEqual(rc, 0)
        self.assertIn("discard-finished", {r.get("action") for r in reports})
        self.assert_gone(worker)


if __name__ == "__main__":
    unittest.main()
