"""``status`` as a complete non-mutating audit, and ``recover`` reconciling only provably owned residue."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from clonegrown import ClonegrownError, collect, discard, recover, release, spawn, status
from clonegrown.state import WorkspaceState, request_path, worker_record_path
from support import commit, git_out, make_repo, run_cli, run_git

ROOT = Path(__file__).resolve().parents[1]


def tree_fingerprint(root: Path) -> dict[str, tuple[int, int]]:
    """Size and mtime of every file below ``root``: proof that an audit touched nothing."""
    out = {}
    for path in root.rglob("*"):
        if path.is_file() or path.is_symlink():
            st = path.lstat()
            out[str(path.relative_to(root))] = (st.st_size, st.st_mtime_ns)
    return out


class AuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name).resolve()  # macOS: TMPDIR is a symlink
        self.repo = make_repo(self.root)
        self.ws = self.root / "demo-dev"
        rc, _ = run_cli(self.repo, "init")
        self.assertEqual(rc, 0)
        self.state = WorkspaceState.load(self.ws)

    def tearDown(self) -> None:
        self.td.cleanup()

    def cli_process(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        full_env = {**os.environ, "PYTHONPATH": str(ROOT), **(env or {})}
        return subprocess.run([sys.executable, "-m", "clonegrown", *args], cwd=self.repo, env=full_env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def issues(self) -> list[tuple[str, int | None]]:
        return sorted(((i["issue"], i.get("id")) for i in status(self.ws)["issues"]),
                      key=lambda pair: (pair[0], -1 if pair[1] is None else pair[1]))

    def assert_status_is_pure(self) -> list[dict]:
        """Two audits in a row report the same thing and change nothing: not `.cws`, not any worker
        slot (its Git index included), not canonical's `.git`, not the refs, not the worktree list."""
        watched = [self.ws / ".cws", self.repo / ".git", *[p for p in self.ws.iterdir() if p.name.isdigit()]]
        before = [tree_fingerprint(path) for path in watched]
        before_refs = run_git(self.repo, "for-each-ref").stdout
        before_trees = run_git(self.repo, "worktree", "list", "--porcelain").stdout
        first = status(self.ws)
        second = status(self.ws)
        self.assertEqual(first["issues"], second["issues"])
        self.assertEqual([tree_fingerprint(path) for path in watched], before)
        self.assertEqual(run_git(self.repo, "for-each-ref").stdout, before_refs)
        self.assertEqual(run_git(self.repo, "worktree", "list", "--porcelain").stdout, before_trees)
        return first["issues"]

    def ready(self, task: str, mode: str = "clone", **kw) -> dict:
        return spawn(self.ws, "HEAD", task, strong=False, mode=mode, **kw)

    def collected(self, task: str, mode: str = "clone") -> dict:
        worker = self.ready(task, mode)
        commit(Path(worker["path"]), "w.txt")
        return collect(self.ws, worker["id"])

    # --- a clean workspace has no issues, in both modes ----------------------------

    def test_clean_lifecycle_reports_nothing(self) -> None:
        for mode in ("clone", "worktree"):
            worker = self.collected(f"clean {mode}", mode)
            self.assertEqual(self.assert_status_is_pure(), [])
            release(self.ws, worker["id"])
            discard(self.ws, worker["id"])
        self.assertEqual(self.assert_status_is_pure(), [])
        self.assertEqual([r["action"] for r in recover(self.ws)], [])

    # --- every issue code, observed without mutation, then recovered idempotently ---

    def test_missing_repository_is_reported_not_omitted(self) -> None:
        worker = self.collected("missing repo")
        shutil.rmtree(Path(worker["path"]))
        issues = self.assert_status_is_pure()
        self.assertIn(("worker-repository-missing", worker["id"]), [(i["issue"], i["id"]) for i in issues])
        listed = [w for w in status(self.ws)["workers"] if w["id"] == worker["id"]]
        self.assertEqual(len(listed), 1)  # the worker itself is still listed
        actions = [{r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]} for _ in range(2)]
        self.assertEqual(actions, [set(), set()])  # a collected worker's missing repo is reported, not "repaired"

    def test_authentication_failure_and_ref_issues(self) -> None:
        worker = self.collected("refs")
        result = status(self.ws)["workers"][0]
        marker = next(Path(worker["path"]).rglob("cws-worker.json"))
        marker.write_text("{}", encoding="utf-8")
        run_git(self.repo, "update-ref", "-d", result["result_ref"])
        run_git(self.repo, "update-ref", self.state.summary_ref(worker["id"]), "HEAD")
        run_git(self.repo, "update-ref", self.state.result_ref(worker["id"], "a" * 40), "HEAD")  # a retained candidate
        run_git(self.repo, "update-ref", self.state.base_ref(worker["id"]), worker["base_sha"])  # a stale pin
        codes = {i["issue"] for i in self.assert_status_is_pure() if i.get("id") == worker["id"]}
        self.assertEqual(codes, {"worker-authentication-failed", "result-ref-missing", "summary-ref-mismatch",
                                 "candidate-ref-retained", "base-ref-stale"})
        for issue in status(self.ws)["issues"]:
            self.assertNotIn("worker_token", json.dumps(issue))
        # Recovery marks the collected worker broken because its result is gone; a broken worker's
        # pin is never dropped (it may be preserving an interrupted spawn); the retained candidate stays.
        first = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("collected-marked-broken", first)
        self.assertNotIn("base-ref-dropped", first)
        self.assertEqual(run_git(self.repo, "rev-parse", "--verify", self.state.result_ref(worker["id"], "a" * 40)).returncode, 0)
        self.assertEqual(run_git(self.repo, "rev-parse", "--verify", self.state.base_ref(worker["id"])).returncode, 0)

    def test_stale_pin_at_its_recorded_value_is_dropped_once(self) -> None:
        worker = self.collected("stale pin")
        run_git(self.repo, "update-ref", self.state.base_ref(worker["id"]), worker["base_sha"])
        self.assertIn(("base-ref-stale", worker["id"]), self.issues())
        first = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("base-ref-dropped", first)
        self.assertEqual(self.issues(), [])
        second = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertEqual(second, set())

    def test_ambiguous_base_pin_is_reported_not_dropped(self) -> None:
        worker = self.ready("pin")
        other = commit(self.repo, "other.txt")
        run_git(self.repo, "update-ref", self.state.base_ref(worker["id"]), other)
        self.assertIn(("base-ref-stale", worker["id"]), self.issues())
        for _ in range(2):
            self.assertIn("base-ref-ambiguous", {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]})
            self.assertEqual(run_git(self.repo, "rev-parse", self.state.base_ref(worker["id"])).stdout.strip(), other)

    def test_orphan_namespace_refs_lock_files_and_indexes_are_reported_and_kept(self) -> None:
        worker = self.ready("indexed", request_id="idx")
        run_git(self.repo, "update-ref", self.state.base_ref(50), "HEAD")
        run_git(self.repo, "update-ref", self.state.summary_ref(51), "HEAD")
        run_git(self.repo, "update-ref", f"{self.state.ref_prefix}/strange/ref", "HEAD")
        (self.ws / ".cws" / "locks" / "60.lock").write_text("", encoding="utf-8")
        stale = request_path(self.ws, "stale")
        stale.write_text(json.dumps({"request_id": "stale", "params_hash": "0" * 64, "worker_id": 70}), encoding="utf-8")
        broken = request_path(self.ws, "broken")
        broken.write_text("not json", encoding="utf-8")
        wrong_name = self.ws / ".cws" / "requests" / (hashlib.sha256(b"x").hexdigest() + ".json")
        wrong_name.write_text(json.dumps({"request_id": "y", "params_hash": "0" * 64, "worker_id": worker["id"]}),
                              encoding="utf-8")
        codes = self.issues()
        self.assertIn(("orphan-namespace-ref", 50), codes)
        self.assertIn(("orphan-namespace-ref", 51), codes)
        self.assertIn(("orphan-namespace-ref", None), codes)
        self.assertIn(("orphan-lock-file", None), codes)
        self.assertIn(("request-index-stale", 70), codes)
        self.assertEqual(codes.count(("request-index-invalid", None)), 2)
        self.assertNotIn(("orphan-lock-file", worker["id"]), codes)
        before = run_git(self.repo, "for-each-ref").stdout
        for _ in range(2):
            actions = {r.get("action") for r in recover(self.ws)}
            self.assertTrue({"orphan-namespace-ref-left", "request-index-stale-left", "request-index-invalid-left"} <= actions)
        self.assertEqual(run_git(self.repo, "for-each-ref").stdout, before)
        self.assertTrue(stale.exists() and broken.exists() and wrong_name.exists())
        self.assertFalse((self.ws / ".cws" / "locks" / "60.lock").exists())  # an orphan lock is removed, not kept
        self.assertNotIn(("orphan-lock-file", None), self.issues())

    def test_worktree_branch_owner_and_admin_issues(self) -> None:
        worker = self.ready("wt", "worktree")
        run_git(self.repo, "update-ref", "-d", f"refs/cws/{worker['workspace_id']}/workers/{worker['id']}/branch-owner")
        codes = {i["issue"] for i in self.assert_status_is_pure() if i.get("id") == worker["id"]}
        self.assertEqual(codes, {"branch-owner-ref-missing"})
        shutil.rmtree(Path(worker["worktree_admin"]))
        codes = {i["issue"] for i in status(self.ws)["issues"] if i.get("id") == worker["id"]}
        self.assertIn("worktree-admin-missing", codes)
        self.assertIn("worker-authentication-failed", codes)
        other = self.ready("wt2", "worktree")
        run_git(self.repo, "update-ref", "-d", f"refs/heads/{other['branch']}")
        codes = {i["issue"] for i in status(self.ws)["issues"] if i.get("id") == other["id"]}
        self.assertIn("task-branch-missing", codes)
        actions = {r.get("action") for r in recover(self.ws) if r.get("id") == other["id"]}
        self.assertIn("ready-marked-broken", actions)
        self.assertTrue(Path(other["path"]).is_dir())

    def test_stage_residue_and_missing_base_pin(self) -> None:
        worker = self.ready("stage")
        record = json.loads(worker_record_path(self.ws, worker["id"]).read_text(encoding="utf-8"))
        Path(record["stage_root"]).mkdir(parents=True)
        (Path(record["stage_root"]) / "leftover").write_text("x\n", encoding="utf-8")
        self.assertIn(("stage-residue", worker["id"]), self.issues())
        p = self.cli_process("spawn", "pinless", "--request-id", "pinless", env={"CWS_FAILPOINT": "spawn.after_clone"})
        self.assertEqual(p.returncode, 88, p.stderr)
        pinless = [w for w in status(self.ws)["workers"] if w["request_id"] == "pinless"][0]
        run_git(self.repo, "update-ref", "-d", self.state.base_ref(pinless["id"]))
        self.assertIn(("base-ref-missing", pinless["id"]), self.issues())
        recover(self.ws)
        self.assertNotIn(("base-ref-missing", pinless["id"]), self.issues())

    def test_discarding_states_and_tombstone_evidence_are_reported(self) -> None:
        worker = self.collected("preserved")
        release(self.ws, worker["id"])
        p = self.cli_process("discard", str(worker["id"]), env={"CWS_FAILPOINT": "discard.after_quarantine"})
        self.assertEqual(p.returncode, 88, p.stderr)
        marker = next((self.ws / ".cws" / "quarantine").rglob("cws-worker.json"))
        marker.write_text("{}", encoding="utf-8")
        recover(self.ws)
        self.assertIn(("quarantine-preserved", worker["id"]), self.issues())
        gone = self.collected("gone")
        release(self.ws, gone["id"])
        discard(self.ws, gone["id"])
        data = json.loads(worker_record_path(self.ws, gone["id"]).read_text(encoding="utf-8"))
        data["quarantine_path"] = str(self.ws / ".cws" / "quarantine" / f"{gone['id']}-{data['worker_token']}")
        worker_record_path(self.ws, gone["id"]).write_text(json.dumps(data), encoding="utf-8")
        codes = self.issues()
        self.assertIn(("invalid-worker-metadata", gone["id"]), codes)  # a tombstone may not carry quarantine fields

    def test_interrupted_collection_finalization_is_finished_by_recovery(self) -> None:
        worker = self.ready("finalize")
        sha = commit(Path(worker["path"]), "f.txt")
        p = self.cli_process("collect", str(worker["id"]), env={"CWS_FAILPOINT": "collect.after_summary"})
        self.assertEqual(p.returncode, 88, p.stderr)
        actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("collect-finished", actions)
        self.assertEqual(self.issues(), [])
        self.assertEqual(run_git(self.repo, "rev-parse", self.state.summary_ref(worker["id"])).stdout.strip(), sha)
        run_git(self.repo, "update-ref", "-d", self.state.summary_ref(worker["id"]))
        self.assertIn(("summary-ref-mismatch", worker["id"]), self.issues())
        recover(self.ws)
        self.assertEqual(self.issues(), [])
        self.assertEqual([r["action"] for r in recover(self.ws) if r.get("id") == worker["id"]], [])

    def test_spawn_recovery_keeps_a_pin_that_names_another_commit(self) -> None:
        for mode, point in (("clone", "spawn.after_allocated"), ("worktree", "spawn.after_repair")):
            with self.subTest(mode=mode, point=point):
                args = ["spawn", f"pin {mode}", "--request-id", f"pin-{mode}"] + (["--worktree"] if mode == "worktree" else [])
                p = self.cli_process(*args, env={"CWS_FAILPOINT": point})
                self.assertEqual(p.returncode, 88, p.stderr)
                worker = [w for w in status(self.ws)["workers"] if w["request_id"] == f"pin-{mode}"][0]
                other = commit(self.repo, f"other-{mode}.txt")
                run_git(self.repo, "update-ref", self.state.base_ref(worker["id"]), other)
                actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
                self.assertIn("base-ref-ambiguous", actions)
                self.assertTrue(actions & {"spawn-cleaned", "spawn-publish-finished"})
                self.assertEqual(run_git(self.repo, "rev-parse", self.state.base_ref(worker["id"])).stdout.strip(), other)
                self.assertIn(("base-ref-stale", worker["id"]), self.issues())

    def test_summary_ref_repair_is_reported_and_conditional(self) -> None:
        worker = self.collected("summary")
        other = commit(self.repo, "elsewhere.txt")
        run_git(self.repo, "update-ref", self.state.summary_ref(worker["id"]), other)
        self.assertIn(("summary-ref-mismatch", worker["id"]), self.issues())
        first = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("summary-ref-repaired", first)
        self.assertEqual(run_git(self.repo, "rev-parse", self.state.summary_ref(worker["id"])).stdout.strip(),
                         worker["result_sha"] if "result_sha" in worker else status(self.ws)["workers"][0]["result_sha"])
        second = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertNotIn("summary-ref-repaired", second)

    def test_failed_spawn_slot_residue_is_reported(self) -> None:
        p = self.cli_process("spawn", "failed", "--request-id", "failed", env={"CWS_ERRORPOINT": "spawn.after_clone"})
        self.assertNotEqual(p.returncode, 0)
        worker = [w for w in status(self.ws)["workers"] if w["request_id"] == "failed"][0]
        self.assertEqual(worker["status"], "spawn_failed")
        slot = self.ws / str(worker["id"])
        slot.mkdir()
        (slot / "junk").write_text("x\n", encoding="utf-8")
        self.assertIn(("tombstone-path-occupied", worker["id"]), self.issues())
        for _ in range(2):
            self.assertIn("tombstone-path-left", {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]})
            self.assertTrue((slot / "junk").is_file())

    def test_invalid_record_claims_nothing(self) -> None:
        evil = self.ws / ".cws" / "quarantine" / "evil"
        evil.mkdir(parents=True)
        worker_record_path(self.ws, 90).write_text(json.dumps({"id": 90, "status": "ready", "quarantine_path": str(evil)}),
                                                   encoding="utf-8")
        codes = self.issues()
        self.assertIn(("invalid-worker-metadata", 90), codes)
        self.assertIn(("orphan-quarantine", None), codes)
        actions = {r.get("action") for r in recover(self.ws)}
        self.assertIn("orphan-quarantine", actions)
        self.assertTrue(evil.is_dir())

    def test_dead_owner_is_an_issue_status_can_see(self) -> None:
        p = self.cli_process("spawn", "dead", "--request-id", "dead", env={"CWS_FAILPOINT": "spawn.after_allocated"})
        self.assertEqual(p.returncode, 88, p.stderr)
        worker = [w for w in status(self.ws)["workers"] if w["request_id"] == "dead"][0]
        self.assertIn(("owner-process-dead", worker["id"]), self.issues())
        self.assert_status_is_pure()
        recover(self.ws)
        self.assertNotIn(("owner-process-dead", worker["id"]), self.issues())

    def test_symbolic_refs_in_the_namespace_are_never_written_through(self) -> None:
        # A symbolic ref planted under one of our names must be reported and left alone; canonical's
        # own branch behind it must survive every write path: pin drop, summary repair, collect, discard.
        for mode in ("clone", "worktree"):
            with self.subTest(mode=mode):
                trunk_before = git_out(self.repo, "rev-parse", "refs/heads/trunk")
                worker = self.collected(f"symref {mode}", mode)
                run_git(self.repo, "symbolic-ref", self.state.base_ref(worker["id"]), "refs/heads/trunk")
                run_git(self.repo, "symbolic-ref", self.state.summary_ref(worker["id"]), "refs/heads/trunk")
                symbolic = {i["ref"] for i in status(self.ws)["issues"] if i["issue"] == "namespace-ref-symbolic"}
                self.assertTrue({self.state.base_ref(worker["id"]), self.state.summary_ref(worker["id"])} <= symbolic)
                codes = self.issues()
                self.assertNotIn(("base-ref-stale", worker["id"]), codes)
                actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
                self.assertNotIn("base-ref-dropped", actions)
                self.assertNotIn("summary-ref-repaired", actions)
                self.assertEqual(git_out(self.repo, "rev-parse", "refs/heads/trunk"), trunk_before)
                with self.assertRaisesRegex(ClonegrownError, "symbolic ref"):
                    collect(self.ws, worker["id"])  # a re-collect would refresh the summary ref
                release(self.ws, worker["id"])
                if mode == "worktree":
                    owner = f"refs/cws/{worker['workspace_id']}/workers/{worker['id']}/branch-owner"
                    run_git(self.repo, "update-ref", "-d", owner)
                    run_git(self.repo, "symbolic-ref", owner, "refs/heads/trunk")
                    with self.assertRaisesRegex(ClonegrownError, "cleanup is incomplete"):
                        discard(self.ws, worker["id"])
                else:
                    discard(self.ws, worker["id"])
                self.assertEqual(git_out(self.repo, "rev-parse", "refs/heads/trunk"), trunk_before)
                self.assertEqual(run_git(self.repo, "symbolic-ref", self.state.base_ref(worker["id"])).stdout.strip(),
                                 "refs/heads/trunk")
                for ref in (self.state.base_ref(worker["id"]), self.state.summary_ref(worker["id"])):
                    run_git(self.repo, "update-ref", "--no-deref", "-d", ref)
                if mode == "worktree":
                    run_git(self.repo, "update-ref", "--no-deref", "-d", owner)
                    run_git(self.repo, "branch", "-D", worker["branch"])
                    recover(self.ws)

    def test_orphan_stage_is_reported_and_blocks_allocation_honestly(self) -> None:
        stage = self.ws / ".cws" / "staging" / f"{self.state.next_id}-deadbeef"
        stage.mkdir(parents=True)
        self.assertIn(("orphan-stage", None), self.issues())
        self.assertIn("orphan-stage-left", {r.get("action") for r in recover(self.ws)})
        self.assertTrue(stage.is_dir())
        with self.assertRaisesRegex(ClonegrownError, "stage directory"):
            self.ready("blocked")
        stage.rmdir()
        self.assertEqual(self.issues(), [])
        self.ready("unblocked")

    def test_temp_record_files_and_wrong_length_result_refs_are_reported(self) -> None:
        worker = self.collected("classify")
        stray = self.ws / ".cws" / "workers" / f"{worker['id']}.json.ab12xyz9"
        os.link(worker_record_path(self.ws, worker["id"]), stray)
        run_git(self.repo, "update-ref", f"{self.state.ref_prefix}/workers/{worker['id']}/results/abc", "HEAD")
        codes = self.issues()
        self.assertIn(("unexpected-metadata-file", None), codes)
        self.assertIn(("orphan-namespace-ref", None), codes)  # an unrecognized shape names no worker
        self.assertNotIn(("candidate-ref-retained", worker["id"]), codes)

    def test_dangling_symbolic_refs_are_seen_by_the_audit_and_by_allocation(self) -> None:
        next_id = int(self.state.next_id)
        run_git(self.repo, "symbolic-ref", self.state.base_ref(next_id), "refs/heads/does-not-exist")
        with self.assertRaisesRegex(ClonegrownError, "symbolic base ref"):
            self.ready("blocked")
        self.assertEqual(self.state.next_id, WorkspaceState.load(self.ws).next_id)  # nothing consumed
        p = self.cli_process("spawn", "pinned", "--request-id", "pinned", env={"CWS_FAILPOINT": "spawn.after_allocated"})
        self.assertNotEqual(p.returncode, 0)  # refused before the counter moved: the id is still blocked
        run_git(self.repo, "update-ref", "--no-deref", "-d", self.state.base_ref(next_id))
        p = self.cli_process("spawn", "pinned", "--request-id", "pinned", env={"CWS_FAILPOINT": "spawn.after_allocated"})
        self.assertEqual(p.returncode, 88, p.stderr)
        worker = [w for w in status(self.ws)["workers"] if w["request_id"] == "pinned"][0]
        run_git(self.repo, "update-ref", "--no-deref", "-d", self.state.base_ref(worker["id"]))
        run_git(self.repo, "symbolic-ref", self.state.base_ref(worker["id"]), "refs/heads/does-not-exist")
        codes = self.issues()
        self.assertIn(("namespace-ref-symbolic", worker["id"]), codes)
        self.assertNotIn(("base-ref-missing", worker["id"]), codes)
        actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("spawn-cleaned", actions)
        self.assertEqual(run_git(self.repo, "symbolic-ref", self.state.base_ref(worker["id"])).stdout.strip(),
                         "refs/heads/does-not-exist")

    def test_cli_status_issue_shape(self) -> None:
        worker = self.ready("cli")
        run_git(self.repo, "update-ref", self.state.base_ref(worker["id"]), worker["base_sha"])
        rc, listing = run_cli(self.repo, "status")
        self.assertEqual(rc, 0)
        (issue,) = listing["issues"]
        self.assertEqual(issue["issue"], "base-ref-stale")
        self.assertEqual(issue["id"], worker["id"])
        self.assertEqual(issue["ref"], self.state.base_ref(worker["id"]))
        self.assertNotIn("worker_token", json.dumps(listing))


if __name__ == "__main__":
    unittest.main()
