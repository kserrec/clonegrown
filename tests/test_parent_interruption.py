"""Real parent-only process death while a configured Git child remains alive."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

from clonegrown import collect, recover, release, spawn, status
from clonegrown.state import WorkspaceState, worker_record_path
from support import commit, git_out, make_repo, run_cli, run_git


ROOT = Path(__file__).resolve().parents[1]
BLOCKING_GIT = ROOT / "tests" / "campaign" / "blocking_git.py"
REAL_GIT = os.environ.get("CLONEGROWN_GIT")
if not REAL_GIT:
    REAL_GIT = str(Path("/usr/bin/git") if Path("/usr/bin/git").exists()
                   else Path(shutil.which("git") or "git"))


class ParentInterruptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.repo = make_repo(self.root)
        rc, initialized = run_cli(self.repo, "init")
        self.assertEqual(rc, 0)
        self.workspace = Path(initialized["workspace"])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def read_json(self, path: Path, timeout: float = 20) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while True:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                if time.monotonic() >= deadline:
                    self.fail(f"timed out waiting for {path}")
                time.sleep(0.01)
                continue
            self.assertIsInstance(value, dict)
            return value

    def process_state(self, pid: int) -> str | None:
        result = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        state = result.stdout.strip()
        return state if result.returncode == 0 and state else None

    def wait_for_child_exit(self, pid: int, timeout: float = 10) -> str | None:
        deadline = time.monotonic() + timeout
        while True:
            state = self.process_state(pid)
            if state is None or state.startswith("Z"):
                return state
            if time.monotonic() >= deadline:
                self.fail(f"configured Git child {pid} remained alive in state {state}")
            time.sleep(0.01)

    def interrupt(self, target: str, *arguments: str) -> dict[str, Any]:
        control = self.root / f"control-{target}"
        environment = {
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "CLONEGROWN_GIT": str(BLOCKING_GIT),
            "CLONEGROWN_TEST_REAL_GIT": REAL_GIT,
            "CLONEGROWN_TEST_GIT_CONTROL": str(control),
            "CLONEGROWN_TEST_GIT_TARGET": target,
        }
        parent = subprocess.Popen(
            [sys.executable, "-m", "clonegrown", *arguments],
            cwd=self.repo,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        child_pid: int | None = None
        finished = False
        try:
            child = self.read_json(control / "started.json")
            child_pid = int(child["pid"])
            before = self.process_state(child_pid)
            self.assertIsNotNone(before)
            self.assertFalse(str(before).startswith("Z"))

            os.kill(parent.pid, signal.SIGKILL)
            parent.wait(timeout=10)
            after_parent = self.process_state(child_pid)
            self.assertIsNotNone(after_parent)
            self.assertFalse(str(after_parent).startswith("Z"))

            (control / "release").write_text("continue\n", encoding="utf-8")
            child_result = self.read_json(control / "result.json")
            exit_state = self.wait_for_child_exit(child_pid)
            stdout, stderr = parent.communicate(timeout=10)
            self.assertEqual(parent.returncode, -signal.SIGKILL, (stdout, stderr))
            self.assertEqual(child_result.get("returncode"), 0, child_result)
            finished = True
            return {
                "args": child["args"],
                "pid": child_pid,
                "state_before_parent_kill": before,
                "state_after_parent_kill": after_parent,
                "exit_state": exit_state,
                "result": child_result,
            }
        finally:
            if parent.poll() is None:
                os.kill(parent.pid, signal.SIGKILL)
                parent.wait(timeout=10)
            if not finished:
                control.mkdir(parents=True, exist_ok=True)
                (control / "release").touch()
                if child_pid is not None:
                    try:
                        self.wait_for_child_exit(child_pid, timeout=5)
                    except AssertionError:
                        os.kill(child_pid, signal.SIGKILL)
            if parent.stdout is not None:
                parent.stdout.close()
            if parent.stderr is not None:
                parent.stderr.close()

    def record(self, worker_id: int = 1) -> dict[str, Any]:
        return json.loads(worker_record_path(self.workspace, worker_id).read_text(encoding="utf-8"))

    def ref(self, name: str) -> str | None:
        result = run_git(self.repo, "rev-parse", "--verify", name, check=False)
        return result.stdout.strip() if result.returncode == 0 else None

    def recovery_actions(self, worker_id: int = 1) -> set[str]:
        return {str(item.get("action")) for item in recover(self.workspace) if item.get("id") == worker_id}

    def admin_names(self) -> list[str]:
        root = self.repo / ".git" / "worktrees"
        return sorted(path.name for path in root.iterdir()) if root.exists() else []

    def assert_clean_audit(self) -> None:
        self.assertEqual(status(self.workspace)["issues"], [])

    def test_worktree_add_child_finishes_after_parent_death_before_admin_persist(self) -> None:
        process = self.interrupt(
            "worktree-add", "spawn", "probe", "--workspace", str(self.workspace),
            "--worktree", "--request-id", "probe",
        )
        self.assertEqual(process["args"][:2], ["worktree", "add"])
        before = self.record()
        state = WorkspaceState.load(self.workspace)
        self.assertEqual(before["status"], "cloning")
        self.assertIsNone(before.get("worktree_admin"))
        self.assertTrue(Path(before["stage_root"]).is_dir())
        self.assertFalse(Path(before["path"]).parent.exists())
        self.assertEqual(len(self.admin_names()), 1)
        self.assertEqual(self.ref(state.base_ref(1)), before["base_sha"])

        self.assertIn("spawn-cleaned", self.recovery_actions())
        after = self.record()
        self.assertEqual(after["status"], "spawn_failed")
        self.assertFalse(Path(after["stage_root"]).exists())
        self.assertEqual(self.admin_names(), [])
        self.assertIsNone(self.ref(state.base_ref(1)))
        self.assertIsNone(self.ref(f"refs/heads/{after['branch']}"))
        self.assertIsNone(self.ref(state.branch_owner_ref(1)))
        self.assert_clean_audit()

    def test_clone_child_finishes_after_parent_death_and_recovery_removes_stage(self) -> None:
        process = self.interrupt(
            "clone", "spawn", "probe", "--workspace", str(self.workspace), "--request-id", "probe",
        )
        self.assertEqual(process["args"][0], "clone")
        before = self.record()
        state = WorkspaceState.load(self.workspace)
        staged_repo = Path(before["stage_root"]) / self.repo.name
        self.assertEqual(before["status"], "cloning")
        self.assertTrue(staged_repo.is_dir())
        self.assertEqual(git_out(staged_repo, "rev-parse", "HEAD"), before["base_sha"])
        self.assertFalse(Path(before["path"]).parent.exists())
        self.assertEqual(self.ref(state.base_ref(1)), before["base_sha"])

        self.assertIn("spawn-cleaned", self.recovery_actions())
        after = self.record()
        self.assertEqual(after["status"], "spawn_failed")
        self.assertFalse(Path(after["stage_root"]).exists())
        self.assertIsNone(self.ref(state.base_ref(1)))
        self.assert_clean_audit()

    def test_fetch_child_finishes_after_parent_death_and_recovery_accepts_candidate(self) -> None:
        worker = spawn(self.workspace, "HEAD", "collect", strong=False)
        sha = commit(Path(worker["path"]), "result.txt")
        process = self.interrupt(
            "fetch", "collect", str(worker["id"]), "--workspace", str(self.workspace),
        )
        self.assertEqual(process["args"][0], "fetch")
        before = self.record(worker["id"])
        state = WorkspaceState.load(self.workspace)
        self.assertEqual(before["status"], "collecting")
        self.assertEqual(before["candidate_sha"], sha)
        self.assertIsNone(self.ref(before["candidate_ref"]))
        self.assertEqual(run_git(self.repo, "cat-file", "-e", f"{sha}^{{commit}}").returncode, 0)
        self.assertIsNone(self.ref(state.summary_ref(worker["id"])))
        self.assertTrue(Path(worker["path"]).is_dir())

        self.assertIn("collect-finished", self.recovery_actions(worker["id"]))
        after = self.record(worker["id"])
        self.assertEqual(after["status"], "collected")
        self.assertEqual(after["result_sha"], sha)
        self.assertEqual(self.ref(after["result_ref"]), sha)
        self.assertEqual(self.ref(state.summary_ref(worker["id"])), sha)
        self.assert_clean_audit()

    def test_published_worktree_repair_child_finishes_after_parent_death(self) -> None:
        process = self.interrupt(
            "worktree-repair", "spawn", "probe", "--workspace", str(self.workspace),
            "--worktree", "--request-id", "probe",
        )
        self.assertEqual(process["args"][:2], ["worktree", "repair"])
        before = self.record()
        state = WorkspaceState.load(self.workspace)
        self.assertEqual(before["status"], "publishing")
        self.assertTrue(Path(before["path"]).is_dir())
        self.assertFalse(Path(before["stage_root"]).exists())
        self.assertTrue(Path(before["worktree_admin"]).is_dir())
        self.assertEqual(self.ref(f"refs/heads/{before['branch']}"), before["base_sha"])
        self.assertEqual(self.ref(state.branch_owner_ref(1)), before["base_sha"])

        self.assertIn("spawn-publish-finished", self.recovery_actions())
        after = self.record()
        self.assertEqual(after["status"], "ready")
        self.assertEqual(git_out(Path(after["path"]), "rev-parse", "HEAD"), after["base_sha"])
        self.assertIsNone(self.ref(state.base_ref(1)))
        self.assert_clean_audit()

    def collected_worktree(self, task: str) -> tuple[dict[str, Any], str]:
        worker = spawn(self.workspace, "HEAD", task, strong=False, mode="worktree")
        sha = commit(Path(worker["path"]), "result.txt")
        collect(self.workspace, worker["id"])
        release(self.workspace, worker["id"])
        return worker, sha

    def test_quarantined_worktree_repair_child_finishes_after_parent_death(self) -> None:
        worker, sha = self.collected_worktree("quarantine repair")
        process = self.interrupt(
            "worktree-repair", "discard", str(worker["id"]), "--workspace", str(self.workspace),
        )
        self.assertEqual(process["args"][:2], ["worktree", "repair"])
        before = self.record(worker["id"])
        quarantine = Path(before["quarantine_path"])
        self.assertEqual(before["status"], "discarding")
        self.assertTrue(quarantine.is_dir())
        self.assertFalse(Path(worker["path"]).exists())
        self.assertNotEqual(before["quarantine_snapshot"], {"deleting": True})
        self.assertTrue(Path(worker["worktree_admin"]).is_dir())
        self.assertEqual(self.ref(before["result_ref"]), sha)

        self.assertIn("discard-finished", self.recovery_actions(worker["id"]))
        after = self.record(worker["id"])
        self.assertEqual(after["status"], "discarded")
        self.assertFalse(quarantine.exists())
        self.assertFalse(Path(worker["worktree_admin"]).exists())
        self.assertIsNone(self.ref(f"refs/heads/{worker['branch']}"))
        self.assertEqual(self.ref(after["result_ref"]), sha)
        self.assert_clean_audit()

    def test_branch_cleanup_child_finishes_after_parent_death(self) -> None:
        worker, sha = self.collected_worktree("branch cleanup")
        process = self.interrupt(
            "update-ref", "discard", str(worker["id"]), "--workspace", str(self.workspace),
        )
        self.assertEqual(process["args"][:2], ["update-ref", "--stdin"])
        before = self.record(worker["id"])
        state = WorkspaceState.load(self.workspace)
        self.assertEqual(before["status"], "discarding")
        self.assertFalse(Path(worker["path"]).exists())
        self.assertFalse(Path(worker["worktree_admin"]).exists())
        self.assertIsNone(self.ref(f"refs/heads/{worker['branch']}"))
        self.assertIsNone(self.ref(state.branch_owner_ref(worker["id"])))
        self.assertEqual(self.ref(before["result_ref"]), sha)

        self.assertIn("discard-finished", self.recovery_actions(worker["id"]))
        after = self.record(worker["id"])
        self.assertEqual(after["status"], "discarded")
        self.assertNotIn("worktree_admin", after)
        self.assertNotIn("branch_cleanup_sha", after)
        self.assertEqual(self.ref(after["result_ref"]), sha)
        self.assert_clean_audit()


if __name__ == "__main__":
    unittest.main()
