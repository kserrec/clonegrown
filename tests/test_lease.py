"""The cooperative work lease: leased from spawn, released explicitly, never inferred from a dead process."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from clonegrown import ClonegrownError, claim, collect, discard, recover, release, spawn, status
from clonegrown.state import WorkerRecord, WorkspaceState, worker_record_path
from support import commit, make_repo, run_cli

MODES = ("clone", "worktree")


class LeaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.repo = make_repo(self.root)
        self.ws = self.root / "demo-dev"
        rc, _ = run_cli(self.repo, "init")
        self.assertEqual(rc, 0)

    def tearDown(self) -> None:
        self.td.cleanup()

    def spawn(self, task: str, mode: str = "clone") -> dict:
        return spawn(self.ws, "HEAD", task, strong=False, mode=mode)

    def record(self, worker_id: int) -> dict:
        return json.loads(worker_record_path(self.ws, worker_id).read_text(encoding="utf-8"))

    def lease_of(self, worker_id: int) -> str:
        listing = status(self.ws)
        (item,) = [w for w in listing["workers"] if w["id"] == worker_id]
        return item["lease"]

    # --- the lease blocks every deletion path until an explicit release ---------

    def test_spawned_worker_is_leased_and_every_discard_form_is_refused(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                worker = self.spawn(f"leased {mode}", mode)
                self.assertEqual(worker["lease"], "active")
                self.assertEqual(self.lease_of(worker["id"]), "active")
                with self.assertRaisesRegex(ClonegrownError, "leased"):
                    discard(self.ws, worker["id"], abandon=True)
                with self.assertRaisesRegex(ClonegrownError, "leased"):
                    discard(self.ws, worker["id"], abandon=True, force=True)
                sha = commit(Path(worker["path"]), "work.txt")
                self.assertEqual(collect(self.ws, worker["id"])["result_sha"], sha)  # collection is lease-independent
                with self.assertRaisesRegex(ClonegrownError, "leased"):
                    discard(self.ws, worker["id"])
                with self.assertRaisesRegex(ClonegrownError, "leased"):
                    discard(self.ws, worker["id"], force=True)
                self.assertTrue(Path(worker["path"]).is_dir())

                released = release(self.ws, worker["id"])
                self.assertEqual(released["lease"], "released")
                self.assertIsInstance(released["lease_released"], float)
                self.assertEqual(release(self.ws, worker["id"])["lease_released"], released["lease_released"])
                self.assertEqual(self.lease_of(worker["id"]), "released")
                self.assertEqual(discard(self.ws, worker["id"])["status"], "discarded")
                self.assertFalse(Path(worker["path"]).exists())

    def test_force_does_not_override_the_lease_on_drift(self) -> None:
        worker = self.spawn("drift")
        commit(Path(worker["path"]), "first.txt")
        collect(self.ws, worker["id"])
        commit(Path(worker["path"]), "after-collection.txt")
        with self.assertRaisesRegex(ClonegrownError, "leased"):
            discard(self.ws, worker["id"], force=True)
        release(self.ws, worker["id"])
        with self.assertRaisesRegex(ClonegrownError, "--force"):
            discard(self.ws, worker["id"])
        self.assertEqual(discard(self.ws, worker["id"], force=True)["status"], "discarded")

    def test_legacy_record_without_lease_field_is_leased(self) -> None:
        worker = self.spawn("legacy")
        path = worker_record_path(self.ws, worker["id"])
        data = self.record(worker["id"])
        data.pop("lease", None)
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(self.lease_of(worker["id"]), "active")
        with self.assertRaisesRegex(ClonegrownError, "leased"):
            discard(self.ws, worker["id"], abandon=True)
        release(self.ws, worker["id"])
        self.assertEqual(discard(self.ws, worker["id"], abandon=True)["status"], "abandoned")

    # --- one-shot handoff --------------------------------------------------------

    def test_abandon_is_refused_for_a_collected_worker(self) -> None:
        worker = self.spawn("one shot")
        commit(Path(worker["path"]), "work.txt")
        collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        with self.assertRaisesRegex(ClonegrownError, "one-shot"):
            discard(self.ws, worker["id"], abandon=True)
        self.assertTrue(Path(worker["path"]).is_dir())
        self.assertEqual(discard(self.ws, worker["id"])["status"], "discarded")

    def test_claim_only_after_release_and_only_while_ready(self) -> None:
        worker = self.spawn("handoff")
        with self.assertRaisesRegex(ClonegrownError, "already leased"):
            claim(self.ws, worker["id"])
        release(self.ws, worker["id"])
        claimed = claim(self.ws, worker["id"])
        self.assertEqual(claimed["lease"], "active")
        self.assertNotIn("lease_released", claimed)
        with self.assertRaisesRegex(ClonegrownError, "leased"):
            discard(self.ws, worker["id"], abandon=True)
        commit(Path(worker["path"]), "work.txt")
        collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        with self.assertRaisesRegex(ClonegrownError, "only a ready worker"):
            claim(self.ws, worker["id"])
        self.assertEqual(discard(self.ws, worker["id"])["status"], "discarded")
        with self.assertRaisesRegex(ClonegrownError, "no releasable lease"):
            release(self.ws, worker["id"])
        with self.assertRaisesRegex(ClonegrownError, "only a ready worker"):
            claim(self.ws, worker["id"])

    def test_release_is_refused_during_an_operation_and_before_publication(self) -> None:
        worker = self.spawn("in flight")
        path = worker_record_path(self.ws, worker["id"])
        pristine = self.record(worker["id"])
        for in_flight in ("collecting", "publishing"):
            with self.subTest(status=in_flight):
                data = dict(pristine)
                data.update(status=in_flight, owner_pid=os.getpid(), owner_start=None)
                if in_flight == "collecting":
                    state = WorkspaceState.load(self.ws)
                    data.update(candidate_sha=data["base_sha"],
                                candidate_ref=state.result_ref(worker["id"], data["base_sha"]), collect_started=1.0)
                else:
                    data.update(ready=None)
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaisesRegex(ClonegrownError, "no releasable lease"):
                    release(self.ws, worker["id"])

    # --- recovery never treats a dead owner as a release --------------------------

    def test_recovery_does_not_finish_an_abandonment_while_leased(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                worker = self.spawn(f"crashed abandon {mode}", mode)
                commit(Path(worker["path"]), "unsaved-work.txt")
                path = worker_record_path(self.ws, worker["id"])
                data = self.record(worker["id"])
                # A discard that started under an older release, before the lease field existed,
                # then died: its intent is durable but nothing ever released the worker.
                data.pop("lease", None)
                data.update(status="discarding", discard_intent="abandoned", discard_previous="ready",
                            discard_started=1.0, owner_pid=2 ** 22 - 1, owner_start="gone")
                path.write_text(json.dumps(data), encoding="utf-8")

                reports = recover(self.ws)

                self.assertIn("abandon-blocked-by-lease",
                              {r.get("action") for r in reports if r.get("id") == worker["id"]})
                self.assertTrue((Path(worker["path"]) / "unsaved-work.txt").is_file())
                record = WorkerRecord.load(self.ws, worker["id"])
                self.assertEqual(record.status, "ready")
                self.assertIsNone(record.owner_pid)
                # After an explicit release the same abandonment completes.
                release(self.ws, worker["id"])
                self.assertEqual(discard(self.ws, worker["id"], abandon=True)["status"], "abandoned")
                self.assertFalse(Path(worker["path"]).exists())

    def test_recovery_leaves_a_leased_tombstone_directory_alone(self) -> None:
        worker = self.spawn("tombstone residue")
        path = worker_record_path(self.ws, worker["id"])
        data = self.record(worker["id"])
        data.pop("lease", None)
        data.update(status="abandoned", discard_intent="abandoned", discard_previous="ready",
                    discard_started=1.0, discarded=2.0)
        path.write_text(json.dumps(data), encoding="utf-8")
        reports = recover(self.ws)
        self.assertIn("tombstone-path-left", {r.get("action") for r in reports if r.get("id") == worker["id"]})
        self.assertTrue(Path(worker["path"]).is_dir())

    # --- spawn failures carry no lease to release ----------------------------------

    def test_failed_spawn_is_discardable_without_a_release(self) -> None:
        environment = {"CWS_ERRORPOINT": "spawn.after_clone"}
        old = {key: os.environ.get(key) for key in environment}
        os.environ.update(environment)
        try:
            with self.assertRaisesRegex(ClonegrownError, "injected"):
                self.spawn("doomed")
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        listing = status(self.ws)
        (failed,) = listing["workers"]
        self.assertEqual(failed["status"], "spawn_failed")
        self.assertNotIn("lease", failed)
        with self.assertRaisesRegex(ClonegrownError, "no releasable lease"):
            release(self.ws, failed["id"])
        self.assertEqual(discard(self.ws, failed["id"], abandon=True)["status"], "abandoned")

    # --- the CLI surface ----------------------------------------------------------

    def test_cli_release_and_claim_output(self) -> None:
        rc, worker = run_cli(self.repo, "spawn", "cli lease")
        self.assertEqual(rc, 0)
        self.assertEqual(worker["lease"], "active")
        rc, released = run_cli(self.repo, "release", str(worker["id"]))
        self.assertEqual(rc, 0)
        self.assertEqual(released["lease"], "released")
        self.assertRegex(released["lease_released"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        rc, claimed = run_cli(self.repo, "claim", str(worker["id"]))
        self.assertEqual(rc, 0)
        self.assertEqual(set(claimed), set(worker))
        self.assertEqual(claimed["lease"], "active")
        rc, listing = run_cli(self.repo, "status")
        self.assertEqual(listing["workers"][0]["lease"], "active")
        self.assertNotIn("worker_token", listing["workers"][0])


if __name__ == "__main__":
    unittest.main()
