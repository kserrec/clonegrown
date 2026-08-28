"""Create-only allocation and end-to-end request-index validation (Phase 3, Steps 3.1 and 3.2)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from clonegrown import ClonegrownError, collect, discard, recover, release, spawn, status
from clonegrown.state import WorkspaceState, request_path, worker_record_path
from support import commit, make_repo, run_cli, run_git

ROOT = Path(__file__).resolve().parents[1]


class AllocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name).resolve()  # macOS: TMPDIR is a symlink
        self.repo = make_repo(self.root)
        self.ws = self.root / "demo-dev"
        rc, _ = run_cli(self.repo, "init")
        self.assertEqual(rc, 0)
        self.state_path = self.ws / ".cws" / "state.json"

    def tearDown(self) -> None:
        self.td.cleanup()

    def state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def set_next_id(self, value: int) -> None:
        data = self.state()
        data["next_id"] = value
        self.state_path.write_text(json.dumps(data), encoding="utf-8")

    def cli_process(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        full_env = {**os.environ, "PYTHONPATH": str(ROOT), **(env or {})}
        return subprocess.run([sys.executable, "-m", "clonegrown", *args], cwd=self.repo, env=full_env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # --- Step 3.1: create-only allocation -----------------------------------------

    def test_stale_counter_never_overwrites_an_existing_worker(self) -> None:
        worker = spawn(self.ws, "HEAD", "first", strong=False)
        record_path = worker_record_path(self.ws, worker["id"])
        before = record_path.read_bytes()
        slot_files = sorted(p.relative_to(self.ws) for p in Path(worker["path"]).parent.rglob("*") if p.is_file())
        self.set_next_id(worker["id"])
        with self.assertRaisesRegex(ClonegrownError, "counter is stale") as caught:
            spawn(self.ws, "HEAD", "second", strong=False)
        self.assertIn("record", str(caught.exception))
        self.assertEqual(record_path.read_bytes(), before)
        self.assertEqual(sorted(p.relative_to(self.ws) for p in Path(worker["path"]).parent.rglob("*") if p.is_file()),
                         slot_files)
        self.assertEqual(self.state()["next_id"], worker["id"])  # not advanced past the evidence
        self.assertEqual(status(self.ws)["workers"][0]["status"], "ready")

    def test_every_collision_target_refuses_allocation(self) -> None:
        state = WorkspaceState.load(self.ws)
        next_id = int(state.next_id)
        targets = {
            "record": lambda: worker_record_path(self.ws, next_id).write_text("{}", encoding="utf-8"),
            "slot directory": lambda: (self.ws / str(next_id)).mkdir(),
            "stage directory": lambda: (self.ws / ".cws" / "staging" / f"{next_id}-deadbeef").mkdir(parents=True),
            "quarantine directory": lambda: (self.ws / ".cws" / "quarantine" / f"{next_id}-deadbeef").mkdir(parents=True),
            "operation lock file": lambda: (self.ws / ".cws" / "locks" / f"{next_id}.lock").write_text("", encoding="utf-8"),
            "base ref": lambda: run_git(self.repo, "update-ref", state.base_ref(next_id), "HEAD"),
            "worker refs": lambda: run_git(self.repo, "update-ref", state.summary_ref(next_id), "HEAD"),
        }
        for label, plant in targets.items():
            with self.subTest(target=label):
                plant()
                try:
                    with self.assertRaisesRegex(ClonegrownError, "counter is stale") as caught:
                        spawn(self.ws, "HEAD", f"collide {label}", strong=False)
                    self.assertIn(label, str(caught.exception))
                    self.assertEqual(self.state()["next_id"], next_id)
                finally:
                    # Remove the planted evidence so the next target is tested alone.
                    for path in (worker_record_path(self.ws, next_id), self.ws / ".cws" / "locks" / f"{next_id}.lock"):
                        if path.exists():
                            path.unlink()
                    for directory in (self.ws / str(next_id), self.ws / ".cws" / "staging" / f"{next_id}-deadbeef",
                                      self.ws / ".cws" / "quarantine" / f"{next_id}-deadbeef"):
                        if directory.exists():
                            directory.rmdir()
                    run_git(self.repo, "update-ref", "-d", state.base_ref(next_id), check=False)
                    run_git(self.repo, "update-ref", "-d", state.summary_ref(next_id), check=False)
        self.assertEqual(spawn(self.ws, "HEAD", "clean", strong=False)["id"], next_id)

    def test_interrupted_allocation_leaves_an_observable_gap_and_the_old_record_intact(self) -> None:
        first = spawn(self.ws, "HEAD", "first", strong=False)
        before = worker_record_path(self.ws, first["id"]).read_bytes()
        state = WorkspaceState.load(self.ws)
        for point in ("allocate.after_state", "allocate.after_base_ref", "allocate.after_record"):
            with self.subTest(point=point):
                expected_id = self.state()["next_id"]
                p = self.cli_process("spawn", f"crash {point}", "--request-id", point, env={"CWS_FAILPOINT": point})
                self.assertEqual(p.returncode, 88, p.stderr)
                self.assertEqual(self.state()["next_id"], expected_id + 1)  # consumed, never reused
                self.assertEqual(worker_record_path(self.ws, first["id"]).read_bytes(), before)
                recover(self.ws)
                if point == "allocate.after_state":
                    self.assertFalse(worker_record_path(self.ws, expected_id).exists())
                elif point == "allocate.after_base_ref":
                    self.assertFalse(worker_record_path(self.ws, expected_id).exists())
                    self.assertEqual(run_git(self.repo, "rev-parse", "--verify", state.base_ref(expected_id),
                                             check=False).returncode, 0)  # a pin with no record: evidence, kept
                else:
                    self.assertTrue(worker_record_path(self.ws, expected_id).exists())
                    listed = [w for w in status(self.ws)["workers"] if w["id"] == expected_id][0]
                    self.assertEqual(listed["status"], "spawn_failed")
        later = spawn(self.ws, "HEAD", "after the gaps", strong=False)
        self.assertGreater(later["id"], first["id"] + 3)

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_record_write_failure_withdraws_only_this_calls_pin(self) -> None:
        state = WorkspaceState.load(self.ws)
        next_id = int(state.next_id)
        workers_dir = self.ws / ".cws" / "workers"
        workers_dir.chmod(0o555)
        try:
            with self.assertRaises(ClonegrownError):
                spawn(self.ws, "HEAD", "unwritable", strong=False)
        finally:
            workers_dir.chmod(0o755)
        self.assertEqual(self.state()["next_id"], next_id + 1)
        self.assertFalse(worker_record_path(self.ws, next_id).exists())
        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", state.base_ref(next_id), check=False).returncode, 0)
        self.assertEqual(spawn(self.ws, "HEAD", "next", strong=False)["id"], next_id + 1)

    def test_records_are_never_replaced_by_the_create_primitive(self) -> None:
        from clonegrown.core import atomic_json_create
        target = self.root / "once.json"
        atomic_json_create(target, {"a": 1})
        with self.assertRaisesRegex(ClonegrownError, "never replaced"):
            atomic_json_create(target, {"a": 2})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"a": 1})
        self.assertEqual([p.name for p in self.root.glob("once.json.*")], [])

    def test_operations_on_unknown_ids_leave_no_evidence_behind(self) -> None:
        from clonegrown import claim
        first = spawn(self.ws, "HEAD", "first", strong=False)
        next_id = self.state()["next_id"]
        for operation in (lambda: collect(self.ws, next_id), lambda: release(self.ws, next_id),
                          lambda: claim(self.ws, next_id), lambda: discard(self.ws, next_id, abandon=True)):
            with self.assertRaisesRegex(ClonegrownError, "unknown worker"):
                operation()
        self.assertFalse((self.ws / ".cws" / "locks" / f"{next_id}.lock").exists())
        self.assertEqual(status(self.ws)["issues"], [])
        # A stray lock from before this guard is removed by recovery instead of bricking the id.
        (self.ws / ".cws" / "locks" / f"{next_id}.lock").write_text("", encoding="utf-8")
        self.assertEqual([i["issue"] for i in status(self.ws)["issues"]], ["orphan-lock-file"])
        self.assertIn("orphan-lock-file-removed", {r.get("action") for r in recover(self.ws)})
        self.assertEqual(status(self.ws)["issues"], [])
        self.assertEqual(spawn(self.ws, "HEAD", "second", strong=False)["id"], next_id)  # not bricked
        self.assertEqual(first["status"], "ready")

    # --- Step 3.2: request-index validation ---------------------------------------

    def index_of(self, request_id: str) -> Path:
        return request_path(self.ws, request_id)

    def test_corrupt_or_stale_indexes_fail_closed(self) -> None:
        worker = spawn(self.ws, "HEAD", "indexed", strong=False, request_id="r1")
        other = spawn(self.ws, "HEAD", "other", strong=False, request_id="r2")
        original = json.loads(self.index_of("r1").read_text(encoding="utf-8"))
        cases = {
            "missing record": ({"worker_id": 99}, "has no record"),
            "nonnumeric id": ({"worker_id": "1"}, "worker ID is malformed"),
            "boolean id": ({"worker_id": True}, "worker ID is malformed"),
            "cross-linked": ({"worker_id": other["id"]}, "disagree about the request"),
            "altered digest": ({"params_hash": "f" * 64}, "different base/task"),
            "malformed digest": ({"params_hash": "not-hex"}, "digest is malformed"),
            "wrong request": ({"request_id": "r9"}, "does not name this request"),
        }
        for name, (mutation, fragment) in cases.items():
            with self.subTest(case=name):
                data = dict(original)
                data.update(mutation)
                self.index_of("r1").write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaisesRegex(ClonegrownError, fragment):
                    spawn(self.ws, "HEAD", "indexed", strong=False, request_id="r1")
                self.assertEqual(status(self.ws)["workers"][0]["id"], worker["id"])  # nothing allocated
                self.assertEqual(len(status(self.ws)["workers"]), 2)
        self.index_of("r1").write_text(json.dumps(original), encoding="utf-8")
        self.assertEqual(spawn(self.ws, "HEAD", "indexed", strong=False, request_id="r1")["id"], worker["id"])

    def test_settled_results_are_authenticated_before_they_are_returned(self) -> None:
        import shutil
        # A replaced ready worker.
        ready = spawn(self.ws, "HEAD", "ready", strong=False, request_id="ready")
        marker = next(Path(ready["path"]).rglob("cws-worker.json"))
        marker.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ClonegrownError, "marker mismatch"):
            spawn(self.ws, "HEAD", "ready", strong=False, request_id="ready")
        # A collected worker whose result ref vanished.
        collected = spawn(self.ws, "HEAD", "collected", strong=False, request_id="collected")
        commit(Path(collected["path"]), "c.txt")
        result = collect(self.ws, collected["id"])
        run_git(self.repo, "update-ref", "-d", result["result_ref"])
        with self.assertRaisesRegex(ClonegrownError, "result ref is missing"):
            spawn(self.ws, "HEAD", "collected", strong=False, request_id="collected")
        # A discarded worker with residue in its slot.
        gone = spawn(self.ws, "HEAD", "gone", strong=False, request_id="gone")
        keep = self.root / "copy"
        shutil.copytree(Path(gone["path"]).parent, keep)
        commit(Path(gone["path"]), "g.txt")
        collect(self.ws, gone["id"])
        release(self.ws, gone["id"])
        discard(self.ws, gone["id"])
        shutil.copytree(keep, Path(gone["path"]).parent)
        with self.assertRaisesRegex(ClonegrownError, "slot still exists"):
            spawn(self.ws, "HEAD", "gone", strong=False, request_id="gone")
        shutil.rmtree(Path(gone["path"]).parent)
        again = spawn(self.ws, "HEAD", "gone", strong=False, request_id="gone")
        self.assertEqual((again["id"], again["status"]), (gone["id"], "discarded"))

    def test_retry_racing_an_abandonment_allocates_afresh(self) -> None:
        worker = spawn(self.ws, "HEAD", "raced", strong=False, request_id="raced")
        release(self.ws, worker["id"])
        pause = self.root / "paused"
        env = {**os.environ, "PYTHONPATH": str(ROOT), "CWS_PAUSEPOINT": "discard.after_quarantine",
               "CWS_PAUSE_MARKER": str(pause), "CWS_PAUSE_SECONDS": "3"}
        process = subprocess.Popen([sys.executable, "-m", "clonegrown", "discard", str(worker["id"]), "--abandon"],
                                   cwd=self.repo, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        import time
        deadline = time.monotonic() + 30
        while not pause.exists():
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.02)
        again = spawn(self.ws, "HEAD", "raced", strong=False, request_id="raced")
        process.communicate(timeout=60)
        self.assertEqual(process.returncode, 0)
        self.assertNotEqual(again["id"], worker["id"])
        self.assertEqual(again["status"], "ready")
        self.assertTrue(Path(again["path"]).is_dir())
        self.assertEqual(status(self.ws)["issues"], [])

    def test_concurrent_valid_reuse_returns_one_worker(self) -> None:
        import concurrent.futures as cf
        def go() -> dict:
            p = self.cli_process("spawn", "same", "--request-id", "same")
            self.assertEqual(p.returncode, 0, p.stderr)
            return json.loads(p.stdout)
        with cf.ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: go(), range(3)))
        self.assertEqual({r["id"] for r in results}, {results[0]["id"]})
        self.assertTrue(all(r["status"] == "ready" for r in results))
        self.assertEqual(len(status(self.ws)["workers"]), 1)


if __name__ == "__main__":
    unittest.main()
