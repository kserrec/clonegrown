"""The centralized worker-record validator: every status, every field, before any path or ref is selected."""
from __future__ import annotations

import dataclasses
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any

from clonegrown import ClonegrownError, collect, discard, spawn, status
from clonegrown.core import pid_fingerprint
from clonegrown.state import (
    LEASE_STATES, WorkerRecord, WorkerStatus, WorkspaceState, quarantine_root, worker_record_path,
)
from support import commit, make_repo, run_cli

STATUSES = sorted(WorkerStatus.ALL)


class WorkerRecordValidationTests(unittest.TestCase):
    """Builds one genuine ready record, derives a valid record for every status, then corrupts them."""

    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.repo = make_repo(self.root)
        self.ws = self.root / "demo-dev"
        rc, _ = run_cli(self.repo, "init")
        self.assertEqual(rc, 0)
        self.ready = spawn(self.ws, "HEAD", "validate me", strong=False)
        self.worker_id = int(self.ready["id"])
        self.state = WorkspaceState.load(self.ws)
        self.base_sha = str(self.ready["base_sha"])
        self.record_path = worker_record_path(self.ws, self.worker_id)

    def tearDown(self) -> None:
        self.td.cleanup()

    # --- fixtures ------------------------------------------------------------

    def owner(self) -> dict[str, Any]:
        return {"owner_pid": os.getpid(), "owner_start": pid_fingerprint(os.getpid()), "heartbeat": 1.0}

    def result_fields(self) -> dict[str, Any]:
        return {
            "result_sha": self.base_sha,
            "result_ref": self.state.result_ref(self.worker_id, self.base_sha),
            "collected": 2.0,
            "collected_snapshot": {"head": self.base_sha, "branch_ref": f"refs/heads/{self.ready['branch']}"},
            "allow_rewrite": False,
        }

    def valid_record(self, target: str) -> dict[str, Any]:
        """A record the lifecycle could have written for ``target``, derived from the real ready record."""
        base = dict(self.ready)
        unpublished = {key: None for key in ("ready", "source_remote", "alternates_detached", "copied_local_config",
                                              "copied_sparse_checkout", "copied_auxiliary_refs",
                                              "compatibility_warnings")}
        if target in WorkerStatus.SPAWNING:
            base.update(unpublished, status=target, **self.owner())
            if target == WorkerStatus.PUBLISHING:
                base["pending_spawn_details"] = {"source_remote": None}
        elif target == WorkerStatus.READY:
            pass
        elif target == WorkerStatus.COLLECTING:
            base.update(status=target, candidate_sha=self.base_sha,
                        candidate_ref=self.state.result_ref(self.worker_id, self.base_sha),
                        collect_started=1.5, allow_rewrite=False, **self.owner())
        elif target == WorkerStatus.COLLECTED:
            base.update(status=target, **self.result_fields())
        elif target == WorkerStatus.DISCARDING:
            base.update(status=target, discard_intent="discarded", discard_previous="collected",
                        discard_started=3.0, **self.result_fields(), **self.owner())
        elif target == WorkerStatus.DISCARDED:
            base.update(status=target, discard_intent="discarded", discard_previous="collected",
                        discard_started=3.0, discarded=4.0, **self.result_fields())
        elif target == WorkerStatus.ABANDONED:
            base.update(status=target, discard_intent="abandoned", discard_previous="ready",
                        discard_started=3.0, discarded=4.0)
        elif target == WorkerStatus.SPAWN_FAILED:
            base.update(unpublished, status=target, failed=1.0, error="injected")
        elif target == WorkerStatus.BROKEN:
            base.update(status=target, error="assigned task branch is missing")
        else:
            raise AssertionError(target)
        return base

    def validate(self, data: dict[str, Any], state: WorkspaceState | None = None) -> WorkerRecord:
        record = WorkerRecord.from_json(data)
        record.validate(self.ws, state or self.state, self.worker_id)
        return record

    def assert_refused(self, data: dict[str, Any], fragment: str, state: WorkspaceState | None = None) -> None:
        with self.assertRaisesRegex(ClonegrownError, fragment):
            self.validate(data, state)

    # --- every status --------------------------------------------------------

    def test_every_status_has_a_valid_record(self) -> None:
        for target in STATUSES:
            with self.subTest(status=target):
                record = self.validate(self.valid_record(target))
                self.assertEqual(record.status, target)

    def test_every_status_rejects_missing_required_fields(self) -> None:
        required = {
            WorkerStatus.READY: ["ready"],
            WorkerStatus.COLLECTING: ["ready", "collect_started", "candidate_sha", "candidate_ref"],
            WorkerStatus.COLLECTED: ["ready", "collected", "result_sha", "result_ref"],
            WorkerStatus.DISCARDING: ["discard_intent", "discard_previous", "discard_started", "result_sha"],
            WorkerStatus.DISCARDED: ["discarded"],
            WorkerStatus.ABANDONED: ["discarded"],
            WorkerStatus.SPAWN_FAILED: ["failed", "error"],
            WorkerStatus.BROKEN: ["error"],
        }
        for target, names in required.items():
            for name in names:
                with self.subTest(status=target, missing=name):
                    data = self.valid_record(target)
                    data[name] = None
                    with self.assertRaises(ClonegrownError):
                        self.validate(data)

    def test_every_status_rejects_fields_it_has_no_right_to(self) -> None:
        # A field that would select a path or ref this status cannot own.
        values = {
            "ready": 1.0, "collected": 2.0, "discarded": 4.0,
            "candidate_sha": self.base_sha,
            "candidate_ref": self.state.result_ref(self.worker_id, self.base_sha),
            "result_sha": self.base_sha,
            "result_ref": self.state.result_ref(self.worker_id, self.base_sha),
            "discard_intent": "discarded", "discard_previous": "collected", "discard_started": 3.0,
            "quarantine_path": str(quarantine_root(self.ws, self.worker_id, str(self.ready["worker_token"]))),
            "quarantine_started": 5.0, "quarantine_error": "rmtree failed",
        }
        forbidden = {
            **{spawning: list(values) for spawning in WorkerStatus.SPAWNING},
            WorkerStatus.READY: ["collected", "discarded", "candidate_sha", "candidate_ref", "result_sha",
                                 "result_ref", "quarantine_path", "quarantine_started", "quarantine_error"],
            WorkerStatus.COLLECTING: ["collected", "discarded", "result_sha", "result_ref", "quarantine_path"],
            WorkerStatus.COLLECTED: ["discarded", "candidate_sha", "candidate_ref", "quarantine_path"],
            WorkerStatus.DISCARDING: ["discarded", "candidate_sha", "candidate_ref"],
            WorkerStatus.DISCARDED: ["candidate_sha", "candidate_ref", "quarantine_path", "quarantine_error"],
            WorkerStatus.ABANDONED: ["candidate_sha", "candidate_ref", "quarantine_path", "quarantine_error"],
            WorkerStatus.SPAWN_FAILED: list(values),
        }
        for target, names in forbidden.items():
            for name in names:
                with self.subTest(status=target, forbidden=name):
                    data = self.valid_record(target)
                    data[name] = values[name]
                    with self.assertRaises(ClonegrownError):
                        self.validate(data)

    def test_settled_status_rejects_an_operation_owner(self) -> None:
        for target in sorted(WorkerStatus.ALL - WorkerStatus.ACTIVE):
            with self.subTest(status=target):
                data = self.valid_record(target)
                data.update(self.owner())
                self.assert_refused(data, "must not have an operation owner")

    # --- field shapes and dependencies ---------------------------------------

    def test_corruptions_are_refused_by_name(self) -> None:
        other_ref = self.state.result_ref(self.worker_id + 1, self.base_sha)
        elsewhere = str(self.root / "elsewhere")
        cases: list[tuple[str, dict[str, Any], str]] = [
            ("ready", {"status": "quantum"}, "unknown worker status"),
            ("ready", {"base_sha": self.base_sha[:-1]}, "base_sha is not a sha1 commit ID"),
            ("ready", {"base_sha": "G" * 40}, "base_sha is not a sha1 commit ID"),
            ("ready", {"base": ""}, "task/base metadata is malformed"),
            ("ready", {"strong": "no"}, "isolation flag is malformed"),
            ("ready", {"created": "yesterday"}, "created is malformed"),
            ("ready", {"created": None}, "created timestamp is missing"),
            ("ready", {"ready": True}, "ready is malformed"),
            ("ready", {"request_id": 7}, "request ID is malformed"),
            ("ready", {"owner_start": "fingerprint"}, "owner fingerprint without an owner process"),
            ("ready", {"error": ["not", "text"]}, "error is malformed"),
            ("ready", {"copied_local_config": "core.hooksPath"}, "copied_local_config is malformed"),
            ("ready", {"copied_auxiliary_refs": {"refs/notes": "many"}}, "copied_auxiliary_refs is malformed"),
            ("ready", {"compatibility_warnings": [1]}, "compatibility_warnings is malformed"),
            ("ready", {"worktree_admin": elsewhere}, "only valid for a worktree worker"),
            ("ready", {"path": str(Path(self.ready["path"]).parent / "x" / ".." / Path(self.ready["path"]).name)},
             "path does not match its allocated slot"),
            ("ready", {"stage_root": self.ready["stage_root"] + "/."}, "staging path does not match"),
            ("ready", {"worktree_admin_left": "left"}, "only valid for a worktree worker"),
            ("ready", {"lease": "borrowed"}, "unknown worker lease state"),
            ("ready", {"lease_released": 1.0}, "release time without a released lease"),
            ("ready", {"lease": "released", "lease_released": "now"}, "lease_released is malformed"),
            ("ready", {"discard_intent": "gone"}, "unknown worker discard intent"),
            ("ready", {"discard_previous": "collecting"}, "unknown worker discard origin"),
            ("ready", {"discard_intent": "discarded", "discard_previous": "ready"},
             "only a collected worker can be discarded"),
            ("collecting", {"candidate_sha": "0" * 40}, "candidate_ref does not name its commit"),
            ("collecting", {"candidate_ref": other_ref}, "candidate_ref does not name its commit"),
            ("broken", {"candidate_sha": self.base_sha}, "must be recorded together"),
            ("collecting", {"owner_pid": -3}, "owner_pid is malformed"),
            ("collected", {"result_ref": other_ref}, "result_ref does not name its commit"),
            ("collected", {"result_ref": f"refs/heads/{self.ready['branch']}"}, "result_ref does not name its commit"),
            ("broken", {"result_ref": other_ref}, "must be recorded together"),
            ("collected", {"collected_snapshot": {"head": "0" * 40, "branch_ref": f"refs/heads/{self.ready['branch']}"}},
             "snapshot does not match its result"),
            ("collected", {"collected_snapshot": {"head": self.base_sha, "branch_ref": "refs/heads/main"}},
             "collected snapshot is malformed"),
            ("collected", {"collected_snapshot": "snap"}, "collected_snapshot is malformed"),
            ("collected", {"allow_rewrite": 1}, "allow_rewrite is malformed"),
            ("discarding", {"discard_previous": "ready"}, "only a collected worker can be discarded"),
            ("discarding", {"ready": None}, "must record when it became ready"),
            ("abandoned", {"ready": None}, "must record when it became ready"),
            ("discarded", {"ready": None}, "must record when it became ready"),
            ("discarded", {"discard_intent": "abandoned"}, "carries an abandon intent"),
            ("abandoned", {"discard_intent": "discarded", "discard_previous": "collected"}, "carries a discard intent"),
            ("broken", {"quarantine_path": elsewhere}, "quarantine path does not match its identity"),
            ("broken", {"quarantine_started": 1.0}, "quarantine details without a quarantine path"),
            ("broken", {"quarantine_error": "x"}, "quarantine details without a quarantine path"),
            ("broken", {"pending_spawn_details": ["x"]}, "pending_spawn_details is malformed"),
            ("spawn_failed", {"failed": "soon"}, "failed is malformed"),
        ]
        for target, corruption, fragment in cases:
            with self.subTest(status=target, corruption=corruption):
                data = self.valid_record(target)
                data.update(corruption)
                self.assert_refused(data, fragment)

    def test_a_failed_spawn_can_be_abandoned_without_a_ready_time(self) -> None:
        data = self.valid_record("spawn_failed")
        data.update(status="abandoned", discard_intent="abandoned", discard_previous="spawn_failed",
                    discard_started=3.0, discarded=4.0)
        self.assertEqual(self.validate(data).status, "abandoned")
        data.update(status="discarding", discarded=None, **self.owner())
        self.assertEqual(self.validate(data).status, "discarding")

    def test_commit_ids_follow_the_workspace_object_format(self) -> None:
        sha256_state = dataclasses.replace(self.state, object_format="sha256")
        data = self.valid_record("collected")
        self.assert_refused(data, "base_sha is not a sha256 commit ID", sha256_state)
        long_sha = "a" * 64
        data.update(base_sha=long_sha, result_sha=long_sha,
                    result_ref=sha256_state.result_ref(self.worker_id, long_sha),
                    collected_snapshot={"head": long_sha, "branch_ref": f"refs/heads/{self.ready['branch']}"})
        self.validate(data, sha256_state)
        self.assert_refused(data, "base_sha is not a sha1 commit ID")

    def test_quarantine_and_lease_fields_validate_when_consistent(self) -> None:
        token = str(self.ready["worker_token"])
        quarantine = str(quarantine_root(self.ws, self.worker_id, token))
        for target in (WorkerStatus.DISCARDING, WorkerStatus.BROKEN):
            with self.subTest(status=target):
                data = self.valid_record(target)
                data.update(quarantine_path=quarantine, quarantine_started=5.0, quarantine_error="partial deletion")
                record = self.validate(data)
                self.assertEqual(record.quarantine_path, quarantine)
        for lease in sorted(LEASE_STATES):
            with self.subTest(lease=lease):
                data = self.valid_record("ready")
                data["lease"] = lease
                if lease == "released":
                    data["lease_released"] = 6.0
                self.assertEqual(self.validate(data).lease, lease)

    # --- compatibility ---------------------------------------------------------

    def test_absent_extension_fields_keep_their_conservative_meaning(self) -> None:
        # A record written before the lease and quarantine fields existed is leased and never quarantined.
        data = self.valid_record("ready")
        data.pop("lease", None)
        record = self.validate(data)
        self.assertIsNone(record.lease)
        self.assertTrue(record.is_leased)
        self.assertIsNone(record.quarantine_path)
        serialized = record.to_json()
        self.assertEqual(serialized["lease"], "active")  # a published record states the default it carries
        for name in ("lease_released", "quarantine_path", "quarantine_started", "quarantine_error"):
            self.assertNotIn(name, serialized)
        unpublished = self.valid_record("allocated")
        unpublished.pop("lease", None)
        self.assertNotIn("lease", self.validate(unpublished).to_json())

    def test_unknown_keys_and_pre_worktree_records_round_trip(self) -> None:
        data = self.valid_record("collected")
        del data["mode"]
        data["future_field"] = {"nested": [1, 2]}
        record = self.validate(data)
        self.assertEqual(record.mode, "clone")
        self.assertFalse(record.is_worktree)
        self.assertEqual(record.extra, {"future_field": {"nested": [1, 2]}})
        self.assertEqual(record.to_json()["future_field"], {"nested": [1, 2]})
        self.assertEqual(record.to_json()["mode"], "clone")

    # --- the validator runs before any path or ref is used ---------------------

    def test_corrupt_records_on_disk_are_diagnosed_not_acted_on(self) -> None:
        victim = self.root / "victim"
        victim.mkdir()
        (victim / "KEEP").write_text("keep\n", encoding="utf-8")
        original = json.loads(self.record_path.read_text(encoding="utf-8"))
        corruptions: dict[str, dict[str, Any]] = {
            "foreign-result-ref": {"status": "collected", "collected": 2.0, "result_sha": self.base_sha,
                                   "result_ref": self.state.result_ref(self.worker_id + 1, self.base_sha)},
            "quarantine-elsewhere": {"status": "broken", "error": "x", "quarantine_path": str(victim)},
            "owner-on-settled": {"owner_pid": os.getpid(), "owner_start": pid_fingerprint(os.getpid())},
            "ready-without-ready": {"ready": None},
            "wrong-format-sha": {"base_sha": self.base_sha[:-2] + "zz"},
        }
        for name, corruption in corruptions.items():
            with self.subTest(corruption=name):
                data = dict(original)
                data.update(corruption)
                self.record_path.write_text(json.dumps(data), encoding="utf-8")
                report = status(self.ws)
                self.assertTrue(any(issue.get("id") == self.worker_id and issue["issue"] == "invalid-worker-metadata"
                                    for issue in report["issues"]), report)
                with self.assertRaises(ClonegrownError):
                    collect(self.ws, self.worker_id)
                with self.assertRaises(ClonegrownError):
                    discard(self.ws, self.worker_id, abandon=True, force=True)
                self.assertTrue(Path(self.ready["path"]).is_dir())
                self.assertEqual((victim / "KEEP").read_text(encoding="utf-8"), "keep\n")
        self.record_path.write_text(json.dumps(original), encoding="utf-8")
        sha = commit(Path(self.ready["path"]), "after.txt")
        self.assertEqual(collect(self.ws, self.worker_id)["result_sha"], sha)


if __name__ == "__main__":
    unittest.main()
