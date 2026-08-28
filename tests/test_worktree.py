"""Worktree-mode workers: same custody lifecycle, linked worktree underneath."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from clonegrown import ClonegrownError, collect, discard, recover, release, spawn, status
from support import commit, git_out, make_repo, run_cli, run_git

ROOT = Path(__file__).resolve().parents[1]


class WorktreeWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name).resolve()  # macOS: TMPDIR is a symlink
        self.repo = make_repo(self.root)
        self.ws = self.root / "demo-dev"
        self.cli(self.repo, "init")

    def tearDown(self) -> None:
        self.td.cleanup()

    def cli(self, cwd: Path, *args: str) -> dict | list:
        rc, payload = run_cli(cwd, *args)
        self.assertEqual(rc, 0, payload)
        return payload

    def cli_process(self, cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        full_env = {**os.environ, "PYTHONPATH": str(ROOT), **(env or {})}
        return subprocess.run([sys.executable, "-m", "clonegrown", *args], cwd=cwd, env=full_env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def worktree_paths(self) -> set[str]:
        lines = git_out(self.repo, "worktree", "list", "--porcelain").splitlines()
        return {line.split(" ", 1)[1] for line in lines if line.startswith("worktree ")}

    def assert_forgotten(self, worker: dict) -> None:
        """The worker's directory, worktree registration, task branch, and every admin dir are gone."""
        self.assertFalse(Path(worker["path"]).exists())
        self.assertNotIn(str(Path(worker["path"]).resolve()), self.worktree_paths())
        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", f"refs/heads/{worker['branch']}", check=False).returncode, 0)
        admin_root = self.repo / ".git" / "worktrees"
        remaining = sorted(p.name for p in admin_root.iterdir()) if admin_root.exists() else []
        self.assertEqual(remaining, [])

    # --- lifecycle -----------------------------------------------------------

    def test_spawn_is_a_linked_worktree_sharing_canonical(self) -> None:
        worker = self.cli(self.repo, "spawn", "try worktree", "--worktree")
        path = Path(worker["path"])
        self.assertEqual(worker["mode"], "worktree")
        self.assertEqual(worker["status"], "ready")
        self.assertIsNone(worker["source_remote"])
        self.assertTrue(any("shares canonical" in w for w in worker["compatibility_warnings"]))
        self.assertNotIn("worker_token", worker)
        # Linked worktree: private git dir under canonical's .git/worktrees, common dir is canonical's .git.
        self.assertEqual(Path(git_out(path, "rev-parse", "--git-common-dir")).resolve(), (self.repo / ".git").resolve())
        self.assertEqual(Path(git_out(path, "rev-parse", "--git-dir")).resolve().parent, (self.repo / ".git" / "worktrees").resolve())
        self.assertIn(str(path.resolve()), self.worktree_paths())
        self.assertEqual(git_out(path, "rev-parse", "HEAD"), worker["base_sha"])
        self.assertEqual(git_out(path, "symbolic-ref", "HEAD"), f"refs/heads/{worker['branch']}")
        # The task branch lives in the shared refs, visible to canonical.
        self.assertEqual(git_out(self.repo, "rev-parse", worker["branch"]), worker["base_sha"])

    def test_collect_then_discard_forgets_worktree_and_branch(self) -> None:
        worker = self.cli(self.repo, "spawn", "collect me", "--worktree")
        path = Path(worker["path"])
        sha = commit(path, "work.txt")
        collected = self.cli(path, "collect", str(worker["id"]))
        self.assertEqual(collected["result_sha"], sha)
        self.assertEqual(git_out(self.repo, "rev-parse", collected["result_ref"]), sha)
        self.cli(self.repo, "release", str(worker["id"]))
        discarded = self.cli(self.repo, "discard", str(worker["id"]))
        self.assertEqual(discarded["status"], "discarded")
        self.assert_forgotten(worker)
        # The collected result survives the branch deletion.
        self.assertEqual(git_out(self.repo, "rev-parse", collected["result_ref"]), sha)
        self.assertEqual(run_git(self.repo, "fsck", "--connectivity-only").returncode, 0)

    def test_uncollected_needs_abandon(self) -> None:
        worker = spawn(self.ws, "HEAD", "throwaway", strong=False, mode="worktree")
        commit(Path(worker["path"]), "lost.txt")
        with self.assertRaises(ClonegrownError):
            discard(self.ws, worker["id"])
        release(self.ws, worker["id"])
        with self.assertRaisesRegex(ClonegrownError, "abandon"):
            discard(self.ws, worker["id"])
        abandoned = discard(self.ws, worker["id"], abandon=True)
        self.assertEqual(abandoned["status"], "abandoned")
        self.assert_forgotten(worker)

    def test_request_id_is_idempotent_and_mode_bound(self) -> None:
        first = spawn(self.ws, "HEAD", "same", strong=False, request_id="r1", mode="worktree")
        again = spawn(self.ws, "HEAD", "same", strong=False, request_id="r1", mode="worktree")
        self.assertEqual(first["id"], again["id"])
        with self.assertRaisesRegex(ClonegrownError, "reused with different"):
            spawn(self.ws, "HEAD", "same", strong=False, request_id="r1", mode="clone")

    def test_strong_and_worktree_are_incompatible(self) -> None:
        with self.assertRaisesRegex(ClonegrownError, "strong"):
            spawn(self.ws, "HEAD", "x", strong=True, mode="worktree")
        p = self.cli_process(self.repo, "spawn", "x", "--strong", "--worktree")
        self.assertEqual(p.returncode, 2)
        self.assertIn("not allowed with", p.stderr)

    def test_clone_and_worktree_workers_coexist(self) -> None:
        clone = self.cli(self.repo, "spawn", "clone task")
        wt = self.cli(self.repo, "spawn", "worktree task", "--worktree")
        self.assertEqual(clone["mode"], "clone")
        self.assertEqual(wt["mode"], "worktree")
        # Clone is independent: canonical's refs do not see its branch; the worktree's are shared.
        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", clone["branch"], check=False).returncode, 0)
        self.assertEqual(run_git(self.repo, "rev-parse", "--verify", wt["branch"], check=False).returncode, 0)
        listing = status(self.ws)
        self.assertEqual({w["id"]: w["mode"] for w in listing["workers"]}, {clone["id"]: "clone", wt["id"]: "worktree"})
        self.assertEqual(listing["issues"], [])
        for w in (clone, wt):
            release(self.ws, w["id"])
            discard(self.ws, w["id"], abandon=True)
        self.assert_forgotten(wt)

    def test_tampered_mode_is_refused(self) -> None:
        worker = spawn(self.ws, "HEAD", "tamper", strong=False, mode="worktree")
        mp = self.ws / ".cws" / "workers" / f"{worker['id']}.json"
        data = json.loads(mp.read_text())
        data["worktree_admin"] = str(self.root / "elsewhere")
        mp.write_text(json.dumps(data))
        with self.assertRaisesRegex(ClonegrownError, "worktrees directory"):
            collect(self.ws, worker["id"])
        data["worktree_admin"] = worker["worktree_admin"]
        data["mode"] = "clone"
        mp.write_text(json.dumps(data))
        with self.assertRaisesRegex(ClonegrownError, "digest mismatch"):
            collect(self.ws, worker["id"])

    def test_records_without_mode_are_clones(self) -> None:
        worker = spawn(self.ws, "HEAD", "old record", strong=False)
        mp = self.ws / ".cws" / "workers" / f"{worker['id']}.json"
        data = json.loads(mp.read_text())
        del data["mode"]
        mp.write_text(json.dumps(data))
        sha = commit(Path(worker["path"]), "w.txt")
        self.assertEqual(collect(self.ws, worker["id"])["result_sha"], sha)

    def test_recycled_admin_name_is_never_deleted_from_a_newer_worker(self) -> None:
        # Git reuses admin-dir names (app, app1, ...) once freed. A tombstone must never
        # delete, on a later recover, an admin dir that now belongs to a newer worker.
        first = spawn(self.ws, "HEAD", "first", strong=False, mode="worktree")
        release(self.ws, first["id"])
        discard(self.ws, first["id"], abandon=True)
        second = spawn(self.ws, "HEAD", "second", strong=False, mode="worktree")
        self.assertEqual(Path(second["worktree_admin"]).name, Path(first["worktree_admin"]).name)
        for _ in range(2):
            recover(self.ws)
        self.assertTrue(Path(second["worktree_admin"]).is_dir())
        sha = commit(Path(second["path"]), "still-mine.txt")
        self.assertEqual(collect(self.ws, second["id"])["result_sha"], sha)
        tombstone = json.loads((self.ws / ".cws" / "workers" / f"{first['id']}.json").read_text())
        self.assertFalse(tombstone.get("worktree_admin"))

    def test_admin_dir_of_another_worker_is_refused(self) -> None:
        from clonegrown.worker import remove_worktree_admin
        from clonegrown.state import WorkerRecord
        a = spawn(self.ws, "HEAD", "a", strong=False, mode="worktree")
        b = spawn(self.ws, "HEAD", "b", strong=False, mode="worktree")
        # Ask to delete b's admin dir while claiming to be a: must refuse and leave it.
        self.assertFalse(remove_worktree_admin(self.repo, Path(b["worktree_admin"]), WorkerRecord.from_json(a)))
        self.assertTrue(Path(b["worktree_admin"]).is_dir())
        self.assertTrue(remove_worktree_admin(self.repo, Path(b["worktree_admin"]), WorkerRecord.from_json(b)))
        self.assertFalse(Path(b["worktree_admin"]).exists())

    # --- branch and admin ownership --------------------------------------------

    def owner_ref(self, worker: dict) -> str:
        return f"refs/cws/{worker['workspace_id']}/workers/{worker['id']}/branch-owner"

    def test_pre_existing_task_branch_aborts_spawn_untouched(self) -> None:
        from clonegrown.state import WorkspaceState
        state = WorkspaceState.load(self.ws)
        foreign_sha = commit(self.repo, "foreign.txt")
        branch = state.worker_branch(int(state.next_id), "taken")
        run_git(self.repo, "branch", branch, foreign_sha)
        base = git_out(self.repo, "rev-parse", "HEAD~1")
        with self.assertRaisesRegex(ClonegrownError, "already exists"):
            spawn(self.ws, base, "taken", strong=False, mode="worktree")
        recover(self.ws)
        # The foreign branch is exactly where it was; no ownership ref, no admin directory, no worktree.
        self.assertEqual(git_out(self.repo, "rev-parse", branch), foreign_sha)
        worker = status(self.ws)["workers"][0]
        self.assertEqual(worker["status"], "spawn_failed")
        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", self.owner_ref(worker), check=False).returncode, 0)
        self.assertEqual(self.worktree_paths(), {str(self.repo.resolve())})
        self.assertEqual(sorted(p.name for p in (self.repo / ".git" / "worktrees").iterdir())
                         if (self.repo / ".git" / "worktrees").exists() else [], [])

    def test_spawn_creates_branch_and_ownership_ref_together_and_discard_removes_both(self) -> None:
        worker = spawn(self.ws, "HEAD", "owned", strong=False, mode="worktree")
        self.assertEqual(git_out(self.repo, "rev-parse", self.owner_ref(worker)), worker["base_sha"])
        sha = commit(Path(worker["path"]), "w.txt")
        collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        discarded = discard(self.ws, worker["id"])
        self.assertEqual(discarded["status"], "discarded")
        self.assertNotIn("branch_cleanup_left", discarded)
        self.assertNotIn("branch_cleanup_sha", discarded)
        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", self.owner_ref(worker), check=False).returncode, 0)
        self.assert_forgotten(worker)
        self.assertEqual(git_out(self.repo, "rev-parse", discarded["result_ref"]), sha)

    def test_branch_moved_during_discard_is_retained_and_reported(self) -> None:
        worker = spawn(self.ws, "HEAD", "moved", strong=False, mode="worktree")
        commit(Path(worker["path"]), "w.txt")
        collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        p = self.cli_process(self.repo, "discard", str(worker["id"]), env={"CWS_FAILPOINT": "discard.after_delete"})
        self.assertEqual(p.returncode, 88, p.stderr)
        # The worker directory is gone; before cleanup finishes, someone moves the task branch.
        moved_to = commit(self.repo, "elsewhere.txt")
        run_git(self.repo, "update-ref", f"refs/heads/{worker['branch']}", moved_to)
        reports = recover(self.ws)
        actions = {r.get("action") for r in reports if r.get("id") == worker["id"]}
        self.assertIn("worktree-cleanup-conflict", actions)
        self.assertNotIn("discard-finished", actions)
        self.assertEqual(git_out(self.repo, "rev-parse", worker["branch"]), moved_to)
        self.assertEqual(git_out(self.repo, "rev-parse", self.owner_ref(worker)), worker["base_sha"])
        record = json.loads((self.ws / ".cws" / "workers" / f"{worker['id']}.json").read_text())
        self.assertEqual(record["status"], "discarding")  # not terminal until canonical is clean
        self.assertIsNone(record.get("owner_pid"))
        self.assertIn("task branch retained", record["branch_cleanup_left"])
        self.assertIsNotNone(record["branch_cleanup_sha"])
        listed = self.cli(self.repo, "status")["workers"][0]
        self.assertIn("task branch retained", listed["branch_cleanup_left"])
        self.assertNotIn("branch_cleanup_sha", listed)  # bookkeeping stays out of the documented output
        # Repeated recovery keeps reporting and keeps both refs; nothing is forced.
        again = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("worktree-cleanup-conflict", again)
        self.assertEqual(git_out(self.repo, "rev-parse", worker["branch"]), moved_to)
        self.assertEqual(self.worktree_paths(), {str(self.repo.resolve())})
        # Once the branch is back where cleanup recorded it, recovery finishes.
        run_git(self.repo, "update-ref", f"refs/heads/{worker['branch']}", record["branch_cleanup_sha"])
        final = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("discard-finished", final)
        self.assert_forgotten(worker)
        self.assertEqual(status(self.ws)["workers"][0]["status"], "discarded")

    @unittest.skipIf(os.geteuid() == 0, "root ignores directory permissions")
    def test_admin_deletion_failure_keeps_the_record_and_retries(self) -> None:
        worker = spawn(self.ws, "HEAD", "stuck admin", strong=False, mode="worktree")
        admin = Path(worker["worktree_admin"])
        release(self.ws, worker["id"])
        admin.chmod(0o555)
        try:
            with self.assertRaisesRegex(ClonegrownError, "canonical cleanup is incomplete"):
                discard(self.ws, worker["id"], abandon=True)
            self.assertFalse(Path(worker["path"]).exists())
            self.assertTrue(admin.is_dir())
            record = json.loads((self.ws / ".cws" / "workers" / f"{worker['id']}.json").read_text())
            self.assertEqual(record["status"], "discarding")
            self.assertIn("could not remove worktree admin directory", record["worktree_admin_left"])
            self.assertEqual(record["worktree_admin"], str(admin))  # kept: its target is not proved gone
            reports = recover(self.ws)
            self.assertIn("worktree-cleanup-conflict", {r.get("action") for r in reports if r.get("id") == worker["id"]})
            self.assertTrue(admin.is_dir())
        finally:
            admin.chmod(0o755)
        reports = recover(self.ws)
        self.assertIn("abandon-finished", {r.get("action") for r in reports if r.get("id") == worker["id"]})
        self.assert_forgotten(worker)
        record = json.loads((self.ws / ".cws" / "workers" / f"{worker['id']}.json").read_text())
        self.assertEqual(record["status"], "abandoned")
        self.assertIsNone(record.get("worktree_admin"))
        self.assertIsNone(record.get("worktree_admin_left"))

    def test_legacy_worker_without_ownership_ref_keeps_its_branch(self) -> None:
        worker = spawn(self.ws, "HEAD", "legacy", strong=False, mode="worktree")
        run_git(self.repo, "update-ref", "-d", self.owner_ref(worker))  # a record from before the ownership ref
        release(self.ws, worker["id"])
        with self.assertRaisesRegex(ClonegrownError, "no ownership ref"):
            discard(self.ws, worker["id"], abandon=True)
        self.assertEqual(git_out(self.repo, "rev-parse", worker["branch"]), worker["base_sha"])
        self.assertFalse(Path(worker["path"]).exists())
        listed = status(self.ws)["workers"][0]
        self.assertEqual(listed["status"], "discarding")
        self.assertIn("no ownership ref", listed["branch_cleanup_left"])
        # The user resolves it by hand; the next recovery then finishes without deleting anything itself.
        run_git(self.repo, "branch", "-D", worker["branch"])
        self.assertIn("abandon-finished", {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]})
        self.assertEqual(status(self.ws)["workers"][0]["status"], "abandoned")

    def test_branch_absent_when_cleanup_was_recorded_is_never_deleted_if_it_reappears(self) -> None:
        worker = spawn(self.ws, "HEAD", "reappearing", strong=False, mode="worktree")
        commit(Path(worker["path"]), "w.txt")
        collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        run_git(self.repo, "update-ref", "-d", f"refs/heads/{worker['branch']}")  # the branch is gone before discard
        p = self.cli_process(self.repo, "discard", str(worker["id"]), "--force",
                             env={"CWS_FAILPOINT": "discard.after_delete"})
        self.assertEqual(p.returncode, 88, p.stderr)
        foreign = commit(self.repo, "someone-elses.txt")
        run_git(self.repo, "branch", worker["branch"], foreign)  # someone reuses the name meanwhile
        actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        # The branch was recorded absent, so the new one is not ours: left alone, and cleanup finishes.
        self.assertIn("discard-finished", actions)
        self.assertEqual(git_out(self.repo, "rev-parse", worker["branch"]), foreign)
        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", self.owner_ref(worker), check=False).returncode, 0)
        self.assertEqual(status(self.ws)["workers"][0]["status"], "discarded")
        run_git(self.repo, "branch", "-D", worker["branch"])
        self.assert_forgotten(worker)

    def test_branch_checked_out_elsewhere_is_retained_and_head_survives(self) -> None:
        for where in ("canonical", "users-worktree"):
            with self.subTest(where=where):
                worker = spawn(self.ws, "HEAD", f"checked out {where}", strong=False, mode="worktree")
                commit(Path(worker["path"]), "w.txt")
                collect(self.ws, worker["id"])
                release(self.ws, worker["id"])
                before = git_out(self.repo, "rev-parse", "HEAD")
                if where == "canonical":
                    run_git(self.repo, "switch", "--ignore-other-worktrees", worker["branch"])
                    checkout = self.repo
                else:
                    checkout = self.root / f"mine-{worker['id']}"
                    run_git(self.repo, "worktree", "add", "--force", str(checkout), worker["branch"])
                with self.assertRaisesRegex(ClonegrownError, "checked out at"):
                    discard(self.ws, worker["id"])
                self.assertEqual(run_git(checkout, "rev-parse", "--verify", "HEAD").returncode, 0)
                self.assertEqual(git_out(checkout, "symbolic-ref", "HEAD"), f"refs/heads/{worker['branch']}")
                self.assertFalse(Path(worker["path"]).exists())
                listed = [w for w in status(self.ws)["workers"] if w["id"] == worker["id"]][0]
                self.assertEqual(listed["status"], "discarding")
                self.assertIn("checked out at", listed["branch_cleanup_left"])
                # The user moves off the branch; recovery then finishes and deletes it.
                if where == "canonical":
                    run_git(self.repo, "switch", "--detach", before)
                else:
                    run_git(self.repo, "worktree", "remove", "--force", str(checkout))
                self.assertIn("discard-finished", {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]})
                self.assert_forgotten(worker)

    def test_stuck_cleanup_states_all_have_an_exit(self) -> None:
        # (a) admin name recycled by a newer worker: nothing of ours is left there.
        first = spawn(self.ws, "HEAD", "first", strong=False, mode="worktree")
        release(self.ws, first["id"])
        p = self.cli_process(self.repo, "discard", str(first["id"]), "--abandon", env={"CWS_FAILPOINT": "discard.after_delete"})
        self.assertEqual(p.returncode, 88, p.stderr)
        run_git(self.repo, "worktree", "prune")
        second = spawn(self.ws, "HEAD", "second", strong=False, mode="worktree")
        self.assertEqual(Path(second["worktree_admin"]).name, Path(first["worktree_admin"]).name)
        self.assertIn("abandon-finished", {r.get("action") for r in recover(self.ws) if r.get("id") == first["id"]})
        self.assertTrue(Path(second["worktree_admin"]).is_dir())
        mine = commit(Path(second["path"]), "mine.txt")
        self.assertEqual(collect(self.ws, second["id"])["result_sha"], mine)
        # (b) branch moved, then deleted by hand: nothing of ours remains, so the record finishes.
        third = spawn(self.ws, "HEAD", "third", strong=False, mode="worktree")
        commit(Path(third["path"]), "t.txt")
        collect(self.ws, third["id"])
        release(self.ws, third["id"])
        p = self.cli_process(self.repo, "discard", str(third["id"]), env={"CWS_FAILPOINT": "discard.after_delete"})
        self.assertEqual(p.returncode, 88, p.stderr)
        run_git(self.repo, "update-ref", f"refs/heads/{third['branch']}", commit(self.repo, "moved.txt"))
        self.assertIn("worktree-cleanup-conflict", {r.get("action") for r in recover(self.ws) if r.get("id") == third["id"]})
        run_git(self.repo, "branch", "-D", third["branch"])
        self.assertIn("discard-finished", {r.get("action") for r in recover(self.ws) if r.get("id") == third["id"]})
        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", self.owner_ref(third), check=False).returncode, 0)
        # (c) recorded absent, then the user creates their own branch under the name: retained, and we finish.
        fourth = spawn(self.ws, "HEAD", "fourth", strong=False, mode="worktree")
        commit(Path(fourth["path"]), "f.txt")
        collect(self.ws, fourth["id"])
        release(self.ws, fourth["id"])
        run_git(self.repo, "update-ref", "-d", f"refs/heads/{fourth['branch']}")
        p = self.cli_process(self.repo, "discard", str(fourth["id"]), "--force", env={"CWS_FAILPOINT": "discard.after_delete"})
        self.assertEqual(p.returncode, 88, p.stderr)
        theirs = commit(self.repo, "theirs.txt")
        run_git(self.repo, "branch", fourth["branch"], theirs)
        self.assertIn("discard-finished", {r.get("action") for r in recover(self.ws) if r.get("id") == fourth["id"]})
        self.assertEqual(git_out(self.repo, "rev-parse", fourth["branch"]), theirs)
        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", self.owner_ref(fourth), check=False).returncode, 0)
        self.assertEqual(status(self.ws)["issues"], [])

    # --- crash recovery --------------------------------------------------------

    def test_crash_after_publish_before_repair_is_recovered(self) -> None:
        p = self.cli_process(self.repo, "spawn", "crash", "--worktree", "--request-id", "c",
                             env={"CWS_FAILPOINT": "spawn.after_publish"})
        self.assertEqual(p.returncode, 88, p.stderr)
        reports = recover(self.ws)
        self.assertIn("spawn-publish-finished", {r.get("action") for r in reports})
        worker = status(self.ws)["workers"][0]
        self.assertEqual(worker["status"], "ready")
        path = Path(worker["path"])
        self.assertIn(str(path.resolve()), self.worktree_paths())
        sha = commit(path, "after-crash.txt")
        self.assertEqual(collect(self.ws, worker["id"])["result_sha"], sha)

    def test_crash_before_publish_leaves_nothing_behind(self) -> None:
        p = self.cli_process(self.repo, "spawn", "crash early", "--worktree", "--request-id", "e",
                             env={"CWS_FAILPOINT": "spawn.after_checkout"})
        self.assertEqual(p.returncode, 88, p.stderr)
        recover(self.ws)
        worker = status(self.ws)["workers"][0]
        self.assertEqual(worker["status"], "spawn_failed")
        self.assert_forgotten(worker)
        self.assertEqual(self.worktree_paths(), {str(self.repo.resolve())})

    def test_crash_right_after_worktree_add_leaves_no_admin_dir(self) -> None:
        # Git has created .git/worktrees/<name> but nothing else has happened yet.
        p = self.cli_process(self.repo, "spawn", "crash after add", "--worktree", "--request-id", "a",
                             env={"CWS_FAILPOINT": "spawn.after_clone"})
        self.assertEqual(p.returncode, 88, p.stderr)
        recover(self.ws)
        worker = status(self.ws)["workers"][0]
        self.assertEqual(worker["status"], "spawn_failed")
        self.assert_forgotten(worker)

    def test_crash_between_worktree_add_and_its_record_is_cleaned_by_gitdir_ownership(self) -> None:
        # The user's own worktree must survive; only the entry pointing into our staged path goes.
        mine = self.root / "users-own-worktree"
        run_git(self.repo, "worktree", "add", "--detach", str(mine))
        p = self.cli_process(self.repo, "spawn", "crash after add", "--worktree", "--request-id", "w",
                             env={"CWS_FAILPOINT": "spawn.after_worktree_add"})
        self.assertEqual(p.returncode, 88, p.stderr)
        record = json.loads((self.ws / ".cws" / "workers" / "1.json").read_text())
        self.assertIsNone(record.get("worktree_admin"))  # the window: Git created it, nothing recorded it
        admin_root = self.repo / ".git" / "worktrees"
        self.assertEqual(len(list(admin_root.iterdir())), 2)
        reports = recover(self.ws)
        self.assertIn("spawn-cleaned", {r.get("action") for r in reports})
        worker = status(self.ws)["workers"][0]
        self.assertEqual(worker["status"], "spawn_failed")
        self.assertFalse(Path(worker["path"]).exists())
        remaining = [p.name for p in admin_root.iterdir()]
        self.assertEqual(len(remaining), 1)
        self.assertIn(str(mine.resolve()), self.worktree_paths())
        self.assertEqual(run_git(mine, "status").returncode, 0)
        self.assertEqual(self.worktree_paths(), {str(self.repo.resolve()), str(mine.resolve())})

    def test_published_spawn_that_diverged_is_preserved_not_deleted(self) -> None:
        for mode, mutation in (("clone", "dirty"), ("worktree", "dirty"), ("clone", "advanced"), ("worktree", "advanced")):
            with self.subTest(mode=mode, mutation=mutation):
                request = f"{mode}-{mutation}"
                args = ["spawn", request, "--request-id", request] + (["--worktree"] if mode == "worktree" else [])
                p = self.cli_process(self.repo, *args, env={"CWS_FAILPOINT": "spawn.after_publish"})
                self.assertEqual(p.returncode, 88, p.stderr)
                (record,) = [w for w in status(self.ws)["workers"] if w["request_id"] == request]
                self.assertEqual(record["status"], "publishing")
                repo = Path(record["path"])
                if mode == "worktree":
                    run_git(self.repo, "worktree", "repair", str(repo))  # what an agent's Git would need too
                if mutation == "dirty":
                    (repo / "unsaved.txt").write_text("work in progress\n", encoding="utf-8")
                else:
                    advanced_to = commit(repo, "after-publish.txt")
                pin = f"refs/cws/{record['workspace_id']}/bases/{record['id']}"

                reports = recover(self.ws)

                actions = {r.get("action") for r in reports if r.get("id") == record["id"]}
                self.assertIn("spawn-preserved-broken", actions)
                (after,) = [w for w in status(self.ws)["workers"] if w["id"] == record["id"]]
                self.assertEqual(after["status"], "broken")
                self.assertIn("published worker preserved", after["error"])
                if mutation == "dirty":
                    self.assertIn("uncommitted or untracked", after["error"])
                    self.assertTrue((repo / "unsaved.txt").is_file())
                    self.assertNotIn("work in progress", after["error"])
                    self.assertNotIn("unsaved.txt", after["error"])
                else:
                    self.assertIn("HEAD moved", after["error"])
                    self.assertEqual(git_out(repo, "rev-parse", "HEAD"), advanced_to)
                # Retained until discarded: the directory, the base pin, the branch, and (worktree) the admin dir.
                self.assertTrue(repo.is_dir())
                self.assertEqual(git_out(self.repo, "rev-parse", pin), record["base_sha"])
                if mode == "worktree":
                    self.assertEqual(run_git(self.repo, "rev-parse", "--verify", f"refs/heads/{record['branch']}").returncode, 0)
                    self.assertTrue(Path(record["worktree_admin"]).is_dir())
                # Repeated recovery changes nothing.
                again = {r.get("action") for r in recover(self.ws) if r.get("id") == record["id"]}
                self.assertNotIn("spawn-cleaned", again)
                self.assertTrue(repo.is_dir())
                # The user decides: release, then abandon through quarantine cleans everything.
                release(self.ws, record["id"])
                abandoned = discard(self.ws, record["id"], abandon=True)
                self.assertEqual(abandoned["status"], "abandoned")
                self.assertFalse(repo.parent.exists())
                self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", pin, check=False).returncode, 0)
                if mode == "worktree":
                    self.assert_forgotten(after)

    def test_crash_during_discard_is_recovered(self) -> None:
        worker = spawn(self.ws, "HEAD", "discard crash", strong=False, mode="worktree")
        sha = commit(Path(worker["path"]), "w.txt")
        collected = collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        p = self.cli_process(self.repo, "discard", str(worker["id"]), env={"CWS_FAILPOINT": "discard.after_delete"})
        self.assertEqual(p.returncode, 88, p.stderr)
        reports = recover(self.ws)
        self.assertIn("discard-finished", {r.get("action") for r in reports})
        self.assert_forgotten(worker)
        self.assertEqual(git_out(self.repo, "rev-parse", collected["result_ref"]), sha)


if __name__ == "__main__":
    unittest.main()
