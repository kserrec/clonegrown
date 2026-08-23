"""Worktree-mode workers: same custody lifecycle, linked worktree underneath."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from clonegrown import ClonegrownError, cli, collect, discard, recover, spawn, status

ROOT = Path(__file__).resolve().parents[1]


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def git_out(repo: Path, *args: str) -> str:
    return run_git(repo, *args).stdout.strip()


def commit(repo: Path, name: str) -> str:
    run_git(repo, "config", "user.name", "T")
    run_git(repo, "config", "user.email", "t@example.test")
    (repo / name).write_text(name + "\n", encoding="utf-8")
    run_git(repo, "add", name)
    run_git(repo, "commit", "-q", "-m", name)
    return git_out(repo, "rev-parse", "HEAD")


class WorktreeWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.repo = self.root / "demo"
        self.repo.mkdir()
        run_git(self.repo, "init", "-q", "-b", "trunk")
        commit(self.repo, "README.md")
        self.ws = self.root / "demo-dev"
        self.cli(self.repo, "init")

    def tearDown(self) -> None:
        self.td.cleanup()

    def cli(self, cwd: Path, *args: str) -> dict | list:
        old = Path.cwd()
        out = io.StringIO()
        try:
            os.chdir(cwd)
            with redirect_stdout(out):
                rc = cli.main(list(args))
        finally:
            os.chdir(old)
        self.assertEqual(rc, 0, out.getvalue())
        return json.loads(out.getvalue())

    def cli_process(self, cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        full_env = {**os.environ, "PYTHONPATH": str(ROOT), **(env or {})}
        return subprocess.run([sys.executable, "-m", "clonegrown", *args], cwd=cwd, env=full_env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def worktree_paths(self) -> set[str]:
        lines = git_out(self.repo, "worktree", "list", "--porcelain").splitlines()
        return {line.split(" ", 1)[1] for line in lines if line.startswith("worktree ")}

    def assert_forgotten(self, worker: dict) -> None:
        self.assertFalse(Path(worker["path"]).exists())
        self.assertNotIn(str(Path(worker["path"]).resolve()), self.worktree_paths())
        self.assertNotEqual(run_git(self.repo, "rev-parse", "--verify", f"refs/heads/{worker['branch']}", check=False).returncode, 0)
        self.assertFalse(list((self.repo / ".git" / "worktrees").glob("*")) if (self.repo / ".git" / "worktrees").exists() else [])

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

    def test_crash_during_discard_is_recovered(self) -> None:
        worker = spawn(self.ws, "HEAD", "discard crash", strong=False, mode="worktree")
        sha = commit(Path(worker["path"]), "w.txt")
        collected = collect(self.ws, worker["id"])
        p = self.cli_process(self.repo, "discard", str(worker["id"]), env={"CWS_FAILPOINT": "discard.after_delete"})
        self.assertEqual(p.returncode, 88, p.stderr)
        reports = recover(self.ws)
        self.assertIn("discard-finished", {r.get("action") for r in reports})
        self.assert_forgotten(worker)
        self.assertEqual(git_out(self.repo, "rev-parse", collected["result_ref"]), sha)


if __name__ == "__main__":
    unittest.main()
