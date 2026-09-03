"""Create-only allocation and end-to-end request-index validation (Phase 3, Steps 3.1 and 3.2)."""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clonegrown import ClonegrownError, collect, discard, recover, release, spawn, status
from clonegrown import lifecycle
from clonegrown import worker as worker_module
from clonegrown.state import (
    VerifiedWorkspace, WorkspaceState, request_path, worker_record_path,
    workspace_lock as state_workspace_lock,
)
from support import commit, git_out, make_repo, run_cli, run_git

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
        full_env = {
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "CLONEGROWN_TEST_MODE": "1",
            **(env or {}),
        }
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
            "base ref file": lambda: ((self.repo / ".git" / state.base_ref(next_id)).parent.mkdir(parents=True, exist_ok=True),
                                      (self.repo / ".git" / state.base_ref(next_id)).write_bytes(b"not a ref\n")),
            "base ref name occupied by a non-regular file": lambda: (
                (self.repo / ".git" / state.base_ref(next_id)).parent.mkdir(parents=True, exist_ok=True),
                (self.repo / ".git" / state.base_ref(next_id)).mkdir(),
                (self.repo / ".git" / state.base_ref(next_id) / "child").write_bytes(b"x\n")),
            "fifo base ref": lambda: (
                (self.repo / ".git" / state.base_ref(next_id)).parent.mkdir(parents=True, exist_ok=True),
                os.mkfifo(self.repo / ".git" / state.base_ref(next_id))),
            "dangling symbolic worker refs": lambda: run_git(
                self.repo, "symbolic-ref", f"refs/cws/{state.workspace_id}/workers/{next_id}/branch-owner",
                "refs/heads/absent-owner-target"),
        }
        for label, plant in targets.items():
            with self.subTest(target=label):
                plant()
                try:
                    with self.assertRaisesRegex(ClonegrownError, "counter is stale") as caught:
                        spawn(self.ws, "HEAD", f"collide {label}", strong=False)
                    expected = {"fifo base ref": "non-regular file"}.get(label, label.replace("dangling symbolic ", ""))
                    self.assertIn(expected, str(caught.exception))
                    self.assertEqual(self.state()["next_id"], next_id)
                    if not label.startswith(("base ref", "fifo base ref")):  # the plant itself; otherwise no pin
                        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", state.base_ref(next_id),
                                                    check=False).returncode, 0)
                finally:
                    # Remove the planted evidence so the next target is tested alone.
                    for path in (worker_record_path(self.ws, next_id), self.ws / ".cws" / "locks" / f"{next_id}.lock"):
                        if path.exists():
                            path.unlink()
                    for directory in (self.ws / str(next_id), self.ws / ".cws" / "staging" / f"{next_id}-deadbeef",
                                      self.ws / ".cws" / "quarantine" / f"{next_id}-deadbeef"):
                        if directory.exists():
                            directory.rmdir()
                    pin_file = self.repo / ".git" / state.base_ref(next_id)
                    if pin_file.is_dir():
                        shutil.rmtree(pin_file)
                    elif os.path.lexists(pin_file) and not pin_file.is_file():
                        pin_file.unlink()  # a FIFO must go before Git is asked to open the name
                    run_git(self.repo, "update-ref", "-d", state.base_ref(next_id), check=False)
                    if os.path.lexists(pin_file):
                        pin_file.unlink()
                    run_git(self.repo, "update-ref", "-d", state.summary_ref(next_id), check=False)
                    run_git(self.repo, "symbolic-ref", "--delete",
                            f"refs/cws/{state.workspace_id}/workers/{next_id}/branch-owner", check=False)
        self.assertEqual(spawn(self.ws, "HEAD", "clean", strong=False)["id"], next_id)

    def test_generated_branch_occupancy_is_worktree_allocation_evidence(self) -> None:
        """A worktree worker's branch lives in canonical: any raw occupant of the generated
        name (direct, live symbolic, or dangling symbolic) refuses allocation before the ID is
        consumed. A clone's branch lives in its own refs, so canonical occupancy is not evidence."""
        state = WorkspaceState.load(self.ws)
        next_id = int(state.next_id)
        branch = state.worker_branch(next_id, "occupied")
        ref = f"refs/heads/{branch}"
        plants = {
            "task branch": lambda: run_git(self.repo, "update-ref", ref, "HEAD"),
            "symbolic task branch": lambda: run_git(self.repo, "symbolic-ref", ref, "refs/heads/absent"),
            "task branch name occupied by a non-regular file": lambda: (
                (self.repo / ".git" / ref).mkdir(parents=True), (self.repo / ".git" / ref / "child").write_bytes(b"x\n")),
            "task branch file": lambda: (self.repo / ".git" / ref).write_bytes(b"not a ref\n"),
        }
        for label, plant in plants.items():
            with self.subTest(target=label):
                plant()
                try:
                    with self.assertRaisesRegex(ClonegrownError, "counter is stale") as caught:
                        spawn(self.ws, "HEAD", "occupied", strong=False, mode="worktree")
                    self.assertIn(label, str(caught.exception))
                    self.assertEqual(self.state()["next_id"], next_id)
                    self.assertFalse(worker_record_path(self.ws, next_id).exists())
                finally:
                    planted = self.repo / ".git" / ref
                    if planted.is_dir():
                        shutil.rmtree(planted)
                    else:
                        run_git(self.repo, "update-ref", "--no-deref", "-d", ref, check=False)
                        if os.path.lexists(planted):
                            planted.unlink()
        run_git(self.repo, "symbolic-ref", ref, "refs/heads/absent")
        self.assertEqual(spawn(self.ws, "HEAD", "occupied", strong=False, mode="clone")["id"], next_id)
        self.assertEqual(git_out(self.repo, "symbolic-ref", ref), "refs/heads/absent")

    def test_symbolic_ref_to_a_fifo_at_the_next_names_is_evidence_without_git(self) -> None:
        """A loose symbolic ref is read raw: allocation never asks Git to follow a chain that ends
        at a FIFO, whether the ref sits at the next ID's base-pin name or at the generated branch."""
        import signal
        fifo = self.repo / ".git" / "refs" / "zz-fifo"
        os.mkfifo(fifo)
        for which in ("base pin", "task branch"):
            state = WorkspaceState.load(self.ws)
            next_id = int(state.next_id)
            name = state.base_ref(next_id) if which == "base pin" else f"refs/heads/{state.worker_branch(next_id, 'next task')}"
            loose = self.repo / ".git" / name
            loose.parent.mkdir(parents=True, exist_ok=True)
            loose.write_bytes(b"ref: refs/zz-fifo\n")

            def alarm(*_: object) -> None:
                raise AssertionError("a Git command blocked on the planted FIFO")
            previous = signal.signal(signal.SIGALRM, alarm)
            signal.alarm(45)
            try:
                with self.subTest(name=which):
                    for mode in ("worktree", "clone"):
                        with self.assertRaisesRegex(ClonegrownError, "symbolic|task branch|base ref"):
                            spawn(self.ws, "HEAD", "next task", strong=False, mode=mode)
                        if which == "base pin" or mode == "worktree":
                            self.assertEqual(self.state()["next_id"], next_id)  # evidence: nothing consumed
                        # A clone spawn does not use the canonical branch name, so it is refused later
                        # by the enumeration guard; that leaves the documented ID gap.
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, previous)
            self.assertEqual(loose.read_bytes(), b"ref: refs/zz-fifo\n")
            loose.unlink()
        fifo.unlink()

    def test_interrupted_allocation_leaves_an_observable_gap_and_the_old_record_intact(self) -> None:
        first = spawn(self.ws, "HEAD", "first", strong=False)
        before = worker_record_path(self.ws, first["id"]).read_bytes()
        state = WorkspaceState.load(self.ws)
        for point in ("allocate.after_state", "allocate.after_base_ref", "allocate.after_record"):
            with self.subTest(point=point):
                expected_id = self.state()["next_id"]
                p = self.cli_process("spawn", f"crash {point}", "--request-id", point, env={"CLONEGROWN_TEST_FAILPOINT": point})
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

    def test_locked_reconciliation_rejects_next_id_rollback_before_gap_reuse(self) -> None:
        gap = self.cli_process(
            "spawn", "consume one ID", "--request-id", "counter-gap",
            env={"CLONEGROWN_TEST_FAILPOINT": "allocate.after_state"},
        )
        self.assertEqual(gap.returncode, 88, gap.stderr)
        self.assertEqual(WorkspaceState.load(self.ws).next_id, 2)
        self.assertFalse(worker_record_path(self.ws, 1).exists())
        rewound = False

        @contextlib.contextmanager
        def rewind_before_lock(ws: Path):
            nonlocal rewound
            if not rewound:
                data = self.state()
                data["next_id"] = 1
                self.state_path.write_text(json.dumps(data), encoding="utf-8")
                rewound = True
            with state_workspace_lock(ws):
                yield

        with mock.patch.object(worker_module, "workspace_lock", rewind_before_lock):
            with self.assertRaises(ClonegrownError) as caught:
                spawn(self.ws, "HEAD", "must not reuse consumed gap", strong=False)
        self.assertTrue(rewound)
        self.assertIsInstance(caught.exception.__cause__, ClonegrownError)
        self.assertIn("allocation counter moved backwards", str(caught.exception.__cause__))
        self.assertFalse(worker_record_path(self.ws, 1).exists())
        self.assertFalse((self.ws / "1").exists())

    def test_canonical_replacement_after_allocation_check_cannot_receive_base_pin(self) -> None:
        state = WorkspaceState.load(self.ws)
        original_repo = self.root / "original-canonical"
        base_ref = state.base_ref(1)
        original_reload = VerifiedWorkspace.reload_under_lock
        replaced = False

        def replace_after_check(verified: VerifiedWorkspace, ws: Path) -> WorkspaceState:
            nonlocal replaced
            current = original_reload(verified, ws)
            if not replaced and not worker_record_path(ws, 1).exists():
                self.repo.rename(original_repo)
                make_repo(self.root)
                replaced = True
            return current

        with mock.patch.object(VerifiedWorkspace, "reload_under_lock", replace_after_check):
            with self.assertRaises(ClonegrownError):
                spawn(self.ws, "HEAD", "replace after allocation check", strong=False)
        self.assertTrue(replaced)
        self.assertNotEqual(
            run_git(self.repo, "rev-parse", "--verify", base_ref, check=False).returncode, 0,
        )
        self.assertEqual(
            run_git(original_repo, "rev-parse", "--verify", base_ref, check=False).returncode, 0,
        )
        self.assertFalse((self.ws / "1").exists())
        record = json.loads(worker_record_path(self.ws, 1).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "spawn_failed")

    def test_spawn_verifies_canonical_before_each_lock_and_reuses_the_final_value(self) -> None:
        original = WorkspaceState.verify_canonical
        calls: list[str] = []
        lock_depth = 0

        @contextlib.contextmanager
        def tracked_workspace_lock(ws: Path):
            nonlocal lock_depth
            with state_workspace_lock(ws):
                lock_depth += 1
                try:
                    yield
                finally:
                    lock_depth -= 1

        def counted(state: WorkspaceState) -> Path:
            self.assertEqual(lock_depth, 0)
            calls.append(str(state.workspace_id))
            return original(state)

        for mode in ("clone", "worktree"):
            with (self.subTest(mode=mode),
                  mock.patch.object(WorkspaceState, "verify_canonical", counted),
                  mock.patch.object(worker_module, "workspace_lock", tracked_workspace_lock),
                  mock.patch.object(lifecycle, "workspace_lock", tracked_workspace_lock)):
                worker = spawn(self.ws, "HEAD", f"count {mode}", strong=False, mode=mode)
            self.assertEqual(worker["status"], "ready")
            self.assertEqual(len(calls), 4)
            calls.clear()

    def test_canonical_replacement_between_verification_and_allocation_lock_is_detected(self) -> None:
        state = WorkspaceState.load(self.ws)
        original_repo = self.root / "original-canonical"
        replaced = False

        @contextlib.contextmanager
        def replace_before_lock(ws: Path):
            nonlocal replaced
            if not replaced:
                self.repo.rename(original_repo)
                make_repo(self.root)
                replaced = True
            with state_workspace_lock(ws):
                yield

        with mock.patch.object(worker_module, "workspace_lock", replace_before_lock):
            with self.assertRaises(ClonegrownError) as caught:
                spawn(self.ws, "HEAD", "replace before allocation lock", strong=False)
        self.assertTrue(replaced)
        self.assertIsInstance(caught.exception.__cause__, ClonegrownError)
        self.assertIn("identity changed between verification and locked use", str(caught.exception.__cause__))
        self.assertEqual(WorkspaceState.load(self.ws).next_id, 1)
        self.assertFalse(worker_record_path(self.ws, 1).exists())
        self.assertFalse((self.ws / "1").exists())
        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", state.base_ref(1), check=False).returncode, 0)

    def test_workspace_identity_change_between_verification_and_allocation_lock_is_detected(self) -> None:
        changed = False

        @contextlib.contextmanager
        def change_before_lock(ws: Path):
            nonlocal changed
            if not changed:
                data = self.state()
                data["repo_name"] = "different-repository-name"
                self.state_path.write_text(json.dumps(data), encoding="utf-8")
                changed = True
            with state_workspace_lock(ws):
                yield

        with mock.patch.object(worker_module, "workspace_lock", change_before_lock):
            with self.assertRaises(ClonegrownError) as caught:
                spawn(self.ws, "HEAD", "change workspace identity before allocation lock", strong=False)
        self.assertTrue(changed)
        self.assertIsInstance(caught.exception.__cause__, ClonegrownError)
        self.assertIn("workspace identity changed between canonical verification and locked use",
                      str(caught.exception.__cause__))
        self.assertEqual(WorkspaceState.load(self.ws).next_id, 1)
        self.assertFalse(worker_record_path(self.ws, 1).exists())
        self.assertFalse((self.ws / "1").exists())

    def test_canonical_replacement_between_spawn_transactions_is_detected(self) -> None:
        original_repo = self.root / "original-canonical"
        replaced = False

        def replace_after_clone(point: str) -> None:
            nonlocal replaced
            if point != "spawn.after_clone" or replaced:
                return
            self.repo.rename(original_repo)
            make_repo(self.root)
            replaced = True

        with mock.patch.object(lifecycle, "failpoint", replace_after_clone):
            with self.assertRaises(ClonegrownError) as caught:
                spawn(self.ws, "HEAD", "replace between transactions", strong=False)
        self.assertTrue(replaced)
        self.assertEqual(getattr(caught.exception, "stage", None), "spawn failure before publication")
        self.assertIsInstance(caught.exception.__cause__, ClonegrownError)
        self.assertIn("canonical marker directory is missing", str(caught.exception.__cause__))
        self.assertIn("/.git/cws", str(caught.exception.__cause__))
        self.assertTrue((original_repo / ".git").is_dir())
        self.assertTrue((self.repo / ".git").is_dir())
        self.assertFalse((self.ws / "1").exists())
        record = json.loads(worker_record_path(self.ws, 1).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "spawn_failed")

    def test_canonical_replacement_after_publication_cannot_mutate_the_replacement(self) -> None:
        state = WorkspaceState.load(self.ws)
        original_repo = self.root / "original-canonical"
        base_ref = state.base_ref(1)
        planted = False

        def replace_after_publish(point: str) -> None:
            nonlocal planted
            if point != "spawn.after_publish" or planted:
                return
            self.repo.rename(original_repo)
            replacement = make_repo(self.root)
            run_git(replacement, "update-ref", base_ref, "HEAD")
            planted = True

        with mock.patch.object(lifecycle, "failpoint", replace_after_publish):
            with self.assertRaises(ClonegrownError) as caught:
                spawn(self.ws, "HEAD", "replace after publication", strong=False)
        self.assertTrue(planted)
        self.assertEqual(getattr(caught.exception, "stage", None), "spawn failure after publication")
        self.assertIsInstance(caught.exception.__cause__, ClonegrownError)
        self.assertIn("canonical root identity changed", str(caught.exception.__cause__))
        self.assertEqual(run_git(self.repo, "rev-parse", "--verify", base_ref, check=False).returncode, 0)
        self.assertEqual(run_git(original_repo, "rev-parse", "--verify", base_ref, check=False).returncode, 0)
        self.assertTrue((self.ws / "1").is_dir())
        record = json.loads(worker_record_path(self.ws, 1).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "publishing")

    def test_canonical_replacement_after_final_check_cannot_receive_pin_cleanup(self) -> None:
        state = WorkspaceState.load(self.ws)
        original_repo = self.root / "original-canonical"
        base_ref = state.base_ref(1)
        original_reload = VerifiedWorkspace.reload_under_lock
        replaced = False

        def replace_after_final_check(verified: VerifiedWorkspace, ws: Path) -> WorkspaceState:
            nonlocal replaced
            current = original_reload(verified, ws)
            if not replaced and worker_record_path(ws, 1).exists():
                record = json.loads(worker_record_path(ws, 1).read_text(encoding="utf-8"))
                if record.get("status") == "ready":
                    self.repo.rename(original_repo)
                    replacement = make_repo(self.root)
                    run_git(replacement, "update-ref", base_ref, "HEAD")
                    replaced = True
            return current

        with mock.patch.object(VerifiedWorkspace, "reload_under_lock", replace_after_final_check):
            worker = spawn(self.ws, "HEAD", "replace after final check", strong=False)
        self.assertTrue(replaced)
        self.assertEqual(worker["status"], "ready")
        self.assertEqual(
            run_git(self.repo, "rev-parse", "--verify", base_ref, check=False).returncode, 0,
        )
        self.assertNotEqual(
            run_git(original_repo, "rev-parse", "--verify", base_ref, check=False).returncode, 0,
        )
        self.assertTrue((self.ws / "1").is_dir())

    def test_canonical_replacement_before_worktree_repair_cannot_mutate_replacement(self) -> None:
        state = WorkspaceState.load(self.ws)
        original_repo = self.root / "original-canonical"
        base_ref = state.base_ref(1)
        original_repair = lifecycle.repair_worktree
        replaced = False

        def replace_before_repair(canonical: Path, path: Path, *, git_dir_fd=None, **kwargs) -> None:
            nonlocal replaced
            if not replaced:
                self.repo.rename(original_repo)
                replacement = make_repo(self.root)
                run_git(replacement, "update-ref", base_ref, "HEAD")
                replaced = True
            original_repair(canonical, path, git_dir_fd=git_dir_fd)

        with mock.patch.object(lifecycle, "repair_worktree", replace_before_repair):
            with self.assertRaises(ClonegrownError):
                spawn(self.ws, "HEAD", "replace before worktree repair", strong=False, mode="worktree")
        self.assertTrue(replaced)
        self.assertEqual(
            run_git(self.repo, "rev-parse", "--verify", base_ref, check=False).returncode, 0,
        )
        self.assertEqual(
            run_git(original_repo, "rev-parse", "--verify", base_ref, check=False).returncode, 0,
        )
        foreign_worktrees = run_git(self.repo, "worktree", "list", "--porcelain").stdout
        self.assertNotIn(str(self.ws / "1"), foreign_worktrees)
        self.assertTrue((self.ws / "1").is_dir())
        record = json.loads(worker_record_path(self.ws, 1).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "publishing")

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
        run_git(self.repo, "update-ref", "-d", again["result_ref"])
        with self.assertRaisesRegex(ClonegrownError, "discarded.*result ref is missing"):
            spawn(self.ws, "HEAD", "gone", strong=False, request_id="gone")

    def test_retry_racing_an_abandonment_allocates_afresh(self) -> None:
        worker = spawn(self.ws, "HEAD", "raced", strong=False, request_id="raced")
        release(self.ws, worker["id"])
        pause = self.root / "paused"
        env = {**os.environ, "PYTHONPATH": str(ROOT), "CLONEGROWN_TEST_MODE": "1",
               "CLONEGROWN_TEST_PAUSEPOINT": "discard.after_quarantine",
               "CLONEGROWN_TEST_PAUSE_MARKER": str(pause), "CLONEGROWN_TEST_PAUSE_SECONDS": "3"}
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
