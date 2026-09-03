"""``status`` audits documented invariants without mutation; ``recover`` acts only on established custody."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from clonegrown import ClonegrownError, collect, discard, recover, release, spawn, status
from clonegrown import lifecycle, repository
from clonegrown.state import WorkerRecord, WorkspaceState, request_path, worker_record_path
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
        full_env = {
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "CLONEGROWN_TEST_MODE": "1",
            **(env or {}),
        }
        return subprocess.run([sys.executable, "-m", "clonegrown", *args], cwd=self.repo, env=full_env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_dangling_symbolic_namespace_refs_are_reported_wherever_they_sit(self) -> None:
        """for-each-ref omits a symbolic ref whose target is absent; status must still
        report it under every Clonegrown name, and never write through or delete it."""
        worker = spawn(self.ws, "HEAD", "namespace", strong=False)
        state = WorkspaceState.load(self.ws)
        wid = worker["id"]
        planted = {
            f"{state.ref_prefix}/workers/{wid}/branch-owner": "refs/heads/absent-owner",
            f"{state.ref_prefix}/workers/{wid}/results/{'0' * 40}": "refs/heads/absent-result",
            state.summary_ref(wid): "refs/heads/absent-summary",
            f"{state.ref_prefix}/bases/{wid + 7}": "refs/heads/absent-base",
        }
        for ref, target in planted.items():
            run_git(self.repo, "symbolic-ref", ref, target)
        reported = {i["ref"] for i in status(self.ws)["issues"] if i["issue"] == "namespace-ref-symbolic"}
        self.assertEqual(reported, set(planted))
        recover(self.ws)
        for ref, target in planted.items():
            self.assertEqual(git_out(self.repo, "symbolic-ref", ref), target)
        # A loose file under our namespace that is not a ref at all is reported, not used.
        garbage = self.repo / ".git" / state.ref_prefix / "bases" / str(wid + 8)
        garbage.write_bytes(b"not a ref\n")
        self.assertIn((f"{state.ref_prefix}/bases/{wid + 8}", "orphan-namespace-ref"),
                      [(i.get("ref"), i["issue"]) for i in status(self.ws)["issues"]])
        self.assertEqual(garbage.read_bytes(), b"not a ref\n")

    def test_filesystem_symlink_at_a_namespace_name_is_reported_and_never_replaced(self) -> None:
        """A symlink planted as the loose file of a summary or result name, pointing outside
        refs/, is not a symbolic ref to Git but is still a foreign occupant: status reports it,
        collect refuses, and the link and its target are left exactly as they were."""
        worker = spawn(self.ws, "HEAD", "symlink summary", strong=False)
        commit(Path(worker["path"]), "work.txt")
        state = WorkspaceState.load(self.ws)
        external = self.root / "external-ref-file"
        external.write_text("0" * 40 + "\n", encoding="utf-8")
        summary = self.repo / ".git" / state.summary_ref(worker["id"])
        summary.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(external, summary)
        self.assertIn((state.summary_ref(worker["id"]), "namespace-ref-symbolic"),
                      [(i.get("ref"), i["issue"]) for i in status(self.ws)["issues"]])
        with self.assertRaisesRegex(ClonegrownError, "symbolic ref"):
            collect(self.ws, worker["id"])
        self.assertTrue(summary.is_symlink())
        self.assertEqual(os.readlink(summary), str(external))
        self.assertEqual(external.read_text(encoding="utf-8"), "0" * 40 + "\n")
        recover(self.ws)
        self.assertTrue(summary.is_symlink())
        self.assertEqual(self.record_status(worker["id"]), "ready")

    def test_fifo_at_an_owned_name_is_refused_without_asking_git(self) -> None:
        """Git blocks forever opening a FIFO it takes for a loose ref; every owned name is
        lstat-checked first, so status, allocation, and collect refuse instead of hanging."""
        worker = spawn(self.ws, "HEAD", "fifo", strong=False)
        commit(Path(worker["path"]), "work.txt")
        state = WorkspaceState.load(self.ws)
        summary = self.repo / ".git" / state.summary_ref(worker["id"])
        summary.parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(summary)
        self.assertIn((state.summary_ref(worker["id"]), "orphan-namespace-ref"),
                      [(i.get("ref"), i["issue"]) for i in status(self.ws)["issues"]])
        with self.assertRaisesRegex(ClonegrownError, "symbolic ref"):
            collect(self.ws, worker["id"])
        self.assertTrue(os.path.exists(summary) and not summary.is_file())
        recover(self.ws)
        self.assertTrue(os.path.exists(summary) and not summary.is_file())
        summary.unlink()

    def test_fifo_occupants_of_a_collected_worker_are_refused_not_opened(self) -> None:
        """A FIFO, or a symlink to one, at a collected worker's summary, base-pin, or result
        name must never be opened by Git: status, recover, a repeat collect, discard, and a
        request retry all return with a refusal instead of blocking."""
        import signal
        fifo_target = self.root / "external-fifo"
        os.mkfifo(fifo_target)

        def alarm(*_: object) -> None:
            raise AssertionError("a Git command blocked on the planted FIFO")
        previous = signal.signal(signal.SIGALRM, alarm)
        try:
            for kind in ("fifo", "link"):
                request = f"fifo-retry-{kind}"
                worker = spawn(self.ws, "HEAD", f"fifo collected {kind}", strong=False, request_id=request)
                commit(Path(worker["path"]), "work.txt")
                collected = collect(self.ws, worker["id"])
                release(self.ws, worker["id"])
                state = WorkspaceState.load(self.ws)
                # The result name goes last: recovery of a worker whose result is gone marks it broken.
                for name, plant in (
                    ("summary", state.summary_ref(worker["id"])),
                    ("base pin", state.base_ref(worker["id"])),
                    ("results", collected["result_ref"]),
                ):
                    with self.subTest(name=name, occupant=kind):
                        loose = self.repo / ".git" / plant
                        run_git(self.repo, "update-ref", "--no-deref", "-d", plant, check=False)
                        loose.parent.mkdir(parents=True, exist_ok=True)
                        if kind == "fifo":
                            os.mkfifo(loose)
                        else:
                            os.symlink(fifo_target, loose)
                        signal.alarm(30)
                        try:
                            issues = [(i.get("ref"), i["issue"]) for i in status(self.ws)["issues"]]
                            self.assertTrue(any(ref == plant for ref, _ in issues), issues)
                            if name == "summary":
                                with self.assertRaisesRegex(ClonegrownError, "symbolic ref"):
                                    collect(self.ws, worker["id"])
                                self.assertEqual(
                                    sorted(p.name for p in loose.parent.iterdir() if p.name.endswith(".lock")), [])
                            if name == "results":
                                with self.assertRaisesRegex(ClonegrownError, "not preserved"):
                                    discard(self.ws, worker["id"])
                                with self.assertRaisesRegex(ClonegrownError, "missing or moved"):
                                    spawn(self.ws, "HEAD", f"fifo collected {kind}", strong=False, request_id=request)
                            recover(self.ws)
                        finally:
                            signal.alarm(0)
                        self.assertTrue(os.path.lexists(loose))
                        loose.unlink()
                        if name in ("summary", "results"):
                            run_git(self.repo, "update-ref", plant, collected["result_sha"])
                        if name == "results":
                            # The name is occupied, so recovery cannot re-publish the result: the record
                            # stays collected, reported, and the worker is never deleted.
                            self.assertEqual(self.record_status(worker["id"]), "collected")
                            self.assertTrue(Path(worker["path"]).is_dir())
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)

    def test_empty_directory_at_an_owned_name_is_reported(self) -> None:
        state = WorkspaceState.load(self.ws)
        name = f"{state.ref_prefix}/bases/{int(state.next_id) + 3}"
        (self.repo / ".git" / name).mkdir(parents=True)
        self.assertIn((name, "orphan-namespace-ref"),
                      [(i.get("ref"), i["issue"]) for i in status(self.ws)["issues"]])
        self.assertTrue((self.repo / ".git" / name).is_dir())

    def test_non_regular_occupants_of_a_recorded_worker_names_get_one_correct_code(self) -> None:
        """A non-empty directory, an empty directory, a FIFO, or a non-ref file at a recorded
        worker's base-pin or summary name is reported once, as orphan-namespace-ref with the
        worker id, never as a dangling symbolic ref."""
        worker = spawn(self.ws, "HEAD", "codes", strong=False)
        commit(Path(worker["path"]), "work.txt")
        collect(self.ws, worker["id"])
        state = WorkspaceState.load(self.ws)
        for name in (state.base_ref(worker["id"]), state.summary_ref(worker["id"])):
            loose = self.repo / ".git" / name
            run_git(self.repo, "update-ref", "--no-deref", "-d", name, check=False)
            for kind in ("directory", "empty directory", "fifo", "garbage"):
                with self.subTest(name=name.rsplit("/", 1)[-1], occupant=kind):
                    loose.parent.mkdir(parents=True, exist_ok=True)
                    if kind == "directory":
                        loose.mkdir()
                        (loose / "child").write_bytes(b"x\n")
                    elif kind == "empty directory":
                        loose.mkdir()
                    elif kind == "fifo":
                        os.mkfifo(loose)
                    else:
                        loose.write_bytes(b"not a ref\n")
                    reports = [(i["issue"], i.get("id")) for i in status(self.ws)["issues"] if i.get("ref") == name]
                    self.assertEqual(reports, [("orphan-namespace-ref", worker["id"])])
                    if kind.endswith("directory"):
                        shutil.rmtree(loose)
                    else:
                        loose.unlink()

    def test_foreign_occupant_at_a_container_name_is_reported_not_crashed(self) -> None:
        worker = spawn(self.ws, "HEAD", "container", strong=False)
        state = WorkspaceState.load(self.ws)
        for container in (f"{state.ref_prefix}/bases", f"{state.ref_prefix}/workers/{worker['id']}"):
            path = self.repo / ".git" / container
            for kind in ("fifo", "garbage"):
                with self.subTest(container=container.rsplit("/", 1)[-1], occupant=kind):
                    shutil.rmtree(path, ignore_errors=True)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    if kind == "fifo":
                        os.mkfifo(path)
                    else:
                        path.write_bytes(b"junk\n")
                    reports = {(i.get("ref"), i["issue"]) for i in status(self.ws)["issues"]}
                    self.assertIn((container, "orphan-namespace-ref"), reports)
                    recover(self.ws)
                    self.assertTrue(os.path.lexists(path))
                    path.unlink()
        # The namespace root itself: a symlink there is reported rather than silently followed.
        root = self.repo / ".git" / state.ref_prefix
        external = self.root / "external-namespace"
        external.mkdir()
        shutil.rmtree(root, ignore_errors=True)
        os.symlink(external, root)
        self.assertIn((state.ref_prefix, "namespace-ref-symbolic"),
                      {(i.get("ref"), i["issue"]) for i in status(self.ws)["issues"]})
        root.unlink()

    def test_packed_namespace_refs_stay_visible_when_git_enumeration_is_skipped(self) -> None:
        """When a symbolic ref below the namespace leads to a FIFO, Git is not asked to enumerate;
        the packed refs are read raw instead, so intact packed custody refs are not reported missing."""
        import signal
        worker = spawn(self.ws, "HEAD", "packed", strong=False)
        commit(Path(worker["path"]), "work.txt")
        collect(self.ws, worker["id"])
        wt = spawn(self.ws, "HEAD", "packed worktree", strong=False, mode="worktree")
        run_git(self.repo, "pack-refs", "--all")
        state = WorkspaceState.load(self.ws)
        fifo = self.repo / ".git" / "refs" / "zz-fifo"
        os.mkfifo(fifo)
        planted = state.summary_ref(int(state.next_id))
        loose = self.repo / ".git" / planted
        loose.parent.mkdir(parents=True, exist_ok=True)
        loose.write_bytes(b"ref: refs/zz-fifo\n")

        def alarm(*_: object) -> None:
            raise AssertionError("a Git command blocked on the planted FIFO")
        previous = signal.signal(signal.SIGALRM, alarm)
        signal.alarm(45)
        try:
            issues = [(i["issue"], i.get("id")) for i in status(self.ws)["issues"]]
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
        self.assertIn(("namespace-ref-symbolic", int(state.next_id)), issues)
        for false_code in ("summary-ref-mismatch", "branch-owner-ref-missing", "base-ref-missing", "result-ref-missing"):
            self.assertNotIn(false_code, {i for i, _ in issues})
        loose.unlink()
        fifo.unlink()

    def test_names_below_a_symlinked_container_are_foreign(self) -> None:
        """A symlink at a container of the namespace is reported and every name below it is
        treated as foreign: the result no longer counts as preserved, so discard is refused."""
        import shutil
        worker = spawn(self.ws, "HEAD", "container link", strong=False)
        commit(Path(worker["path"]), "work.txt")
        collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        state = WorkspaceState.load(self.ws)
        container = self.repo / ".git" / f"{state.ref_prefix}/workers/{worker['id']}"
        moved = self.root / "moved-worker-refs"
        shutil.move(str(container), str(moved))
        os.symlink(moved, container)
        reports = {(i.get("ref"), i["issue"]) for i in status(self.ws)["issues"]}
        self.assertIn((f"{state.ref_prefix}/workers/{worker['id']}", "namespace-ref-symbolic"), reports)
        self.assertIn((worker["result_ref"] if "result_ref" in worker else self.record(worker["id"])["result_ref"],
                       "result-ref-missing"), reports)
        with self.assertRaisesRegex(ClonegrownError, "not preserved"):
            discard(self.ws, worker["id"])
        self.assertTrue(Path(worker["path"]).is_dir())
        container.unlink()
        shutil.move(str(moved), str(container))
        self.assertEqual(discard(self.ws, worker["id"])["status"], "discarded")

    def record(self, worker_id: int) -> dict:
        return json.loads(worker_record_path(self.ws, worker_id).read_text(encoding="utf-8"))

    def test_missing_result_is_restored_when_safe_and_reported_otherwise(self) -> None:
        """A collected worker's immutable result is content-addressed and recorded: recovery
        re-creates the ref when the object is still present and the name is free, and otherwise
        leaves the worker collected and reported, never broken and never deleted."""
        worker = spawn(self.ws, "HEAD", "restore result", strong=False)
        commit(Path(worker["path"]), "work.txt")
        collected = collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        run_git(self.repo, "update-ref", "--no-deref", "-d", collected["result_ref"])
        self.assertIn((collected["result_ref"], "result-ref-missing"),
                      {(i.get("ref"), i["issue"]) for i in status(self.ws)["issues"]})
        actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("collected-result-restored", actions)
        self.assertEqual(run_git(self.repo, "rev-parse", collected["result_ref"]).stdout.strip(), collected["result_sha"])
        self.assertEqual(self.record_status(worker["id"]), "collected")
        self.assertNotIn("result-ref-missing", {i["issue"] for i in status(self.ws)["issues"]})
        # A foreign occupant at the name: nothing is replaced, the worker stays collected and reported.
        run_git(self.repo, "update-ref", "--no-deref", "-d", collected["result_ref"])
        loose = self.repo / ".git" / collected["result_ref"]
        loose.parent.mkdir(parents=True, exist_ok=True)
        loose.write_bytes(b"not a ref\n")
        actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("collected-result-missing", actions)
        self.assertEqual(self.record_status(worker["id"]), "collected")
        self.assertEqual(loose.read_bytes(), b"not a ref\n")
        with self.assertRaisesRegex(ClonegrownError, "not preserved"):
            discard(self.ws, worker["id"])
        self.assertTrue(Path(worker["path"]).is_dir())

    def test_symbolic_ref_to_a_fifo_inside_the_namespace_is_refused_without_enumeration(self) -> None:
        """A symbolic ref at an owned namespace name whose chain ends at a FIFO would block Git's
        enumeration; the namespace is walked raw first, so status, recover, both spawns, collect,
        and discard all return with the occupant reported and untouched."""
        import signal
        worker = spawn(self.ws, "HEAD", "namespace symref", strong=False)
        commit(Path(worker["path"]), "work.txt")
        collected = collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        other = spawn(self.ws, "HEAD", "other", strong=False)
        commit(Path(other["path"]), "work.txt")
        state = WorkspaceState.load(self.ws)
        fifo = self.repo / ".git" / "refs" / "zz-fifo"
        os.mkfifo(fifo)
        for which in ("summary", "next pin", "result"):
            state = WorkspaceState.load(self.ws)  # refused spawns consume IDs: plant at the *current* next pin
            name = {"summary": state.summary_ref(worker["id"]), "next pin": state.base_ref(int(state.next_id)),
                    "result": collected["result_ref"]}[which]
            with self.subTest(name=which):
                loose = self.repo / ".git" / name
                run_git(self.repo, "update-ref", "--no-deref", "-d", name, check=False)
                loose.parent.mkdir(parents=True, exist_ok=True)
                loose.write_bytes(b"ref: refs/zz-fifo\n")

                def alarm(*_: object) -> None:
                    raise AssertionError("a Git command blocked on the planted FIFO")
                previous = signal.signal(signal.SIGALRM, alarm)
                signal.alarm(45)
                try:
                    reports = {(i.get("ref"), i["issue"]) for i in status(self.ws)["issues"]}
                    self.assertIn((name, "namespace-ref-symbolic"), reports)
                    recover(self.ws)
                    with self.assertRaisesRegex(ClonegrownError, "symbolic ref leading to|occupied|task branch"):
                        spawn(self.ws, "HEAD", "clone spawn", strong=False)
                    with self.assertRaisesRegex(ClonegrownError, "symbolic ref leading to|occupied|task branch"):
                        spawn(self.ws, "HEAD", "worktree spawn", strong=False, mode="worktree")
                    with self.assertRaisesRegex(ClonegrownError, "symbolic ref leading to"):
                        collect(self.ws, other["id"])
                    if name == collected["result_ref"]:
                        with self.assertRaisesRegex(ClonegrownError, "not preserved"):
                            discard(self.ws, worker["id"])
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, previous)
                self.assertEqual(loose.read_bytes(), b"ref: refs/zz-fifo\n")
                loose.unlink()
                if name in (state.summary_ref(worker["id"]), collected["result_ref"]):
                    run_git(self.repo, "update-ref", name, collected["result_sha"])
        fifo.unlink()

    def record_status(self, worker_id: int) -> str:
        return json.loads(worker_record_path(self.ws, worker_id).read_text(encoding="utf-8"))["status"]

    def issues(self) -> list[tuple[str, int | None]]:
        return sorted(((i["issue"], i.get("id")) for i in status(self.ws)["issues"]),
                      key=lambda pair: (pair[0], -1 if pair[1] is None else pair[1]))

    def record_status(self, worker_id: int) -> str:
        return json.loads(worker_record_path(self.ws, worker_id).read_text(encoding="utf-8"))["status"]

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
        # The result object is still in canonical and its content-addressed name is free, so
        # recovery re-publishes exactly the recorded result instead of breaking the worker;
        # the retained candidate stays.
        first = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertIn("collected-result-restored", first)
        self.assertEqual(run_git(self.repo, "rev-parse", result["result_ref"]).stdout.strip(), result["result_sha"])
        self.assertEqual(run_git(self.repo, "rev-parse", "--verify", self.state.result_ref(worker["id"], "a" * 40)).returncode, 0)
        self.assertEqual(self.record_status(worker["id"]), "collected")

    def test_collect_refuses_a_conflicting_content_addressed_result_ref(self) -> None:
        worker = self.ready("result conflict")
        candidate = commit(Path(worker["path"]), "conflict.txt")
        result_ref = self.state.result_ref(worker["id"], candidate)
        planted = git_out(self.repo, "rev-parse", "HEAD")
        self.assertNotEqual(planted, candidate)
        run_git(self.repo, "update-ref", result_ref, planted)

        with self.assertRaisesRegex(ClonegrownError, "result ref.*already exists|conflicting result ref"):
            collect(self.ws, worker["id"])
        self.assertEqual(git_out(self.repo, "rev-parse", result_ref), planted)
        record = json.loads(worker_record_path(self.ws, worker["id"]).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "ready")

    def test_collect_reuses_an_exact_result_ref_but_loses_a_create_race_safely(self) -> None:
        existing = self.ready("existing exact result")
        existing_repo = Path(existing["path"])
        existing_candidate = commit(existing_repo, "existing.txt")
        existing_ref = self.state.result_ref(existing["id"], existing_candidate)
        run_git(self.repo, "fetch", "--no-tags", str(existing_repo), f"{existing_candidate}:{existing_ref}")
        self.assertEqual(collect(self.ws, existing["id"])["result_sha"], existing_candidate)
        self.assertEqual(git_out(self.repo, "rev-parse", existing_ref), existing_candidate)

        raced = self.ready("result create race")
        raced_candidate = commit(Path(raced["path"]), "raced.txt")
        raced_ref = self.state.result_ref(raced["id"], raced_candidate)
        planted = git_out(self.repo, "rev-parse", "HEAD")
        original_git = lifecycle.git
        planted_during_fetch = False

        def git_with_race(repo: Path, *args: str, **kwargs):
            nonlocal planted_during_fetch
            result = original_git(repo, *args, **kwargs)
            if args and args[0] == "fetch" and args[-1] == raced_candidate and not planted_during_fetch:
                run_git(self.repo, "update-ref", raced_ref, planted)
                planted_during_fetch = True
            return result

        with mock.patch.object(lifecycle, "git", git_with_race):
            with self.assertRaisesRegex(ClonegrownError, "conflicting result ref appeared"):
                collect(self.ws, raced["id"])
        self.assertTrue(planted_during_fetch)
        self.assertEqual(git_out(self.repo, "rev-parse", raced_ref), planted)
        self.assertEqual(
            json.loads(worker_record_path(self.ws, raced["id"]).read_text(encoding="utf-8"))["status"],
            "ready",
        )

    def test_collect_refuses_a_symbolic_result_ref_planted_during_fetch(self) -> None:
        worker = self.ready("symbolic result race")
        worker_repo = Path(worker["path"])
        candidate = commit(worker_repo, "symbolic.txt")
        result_ref = self.state.result_ref(worker["id"], candidate)
        target_ref = "refs/heads/symbolic-result-target"
        run_git(self.repo, "fetch", "--no-tags", str(worker_repo), f"{candidate}:{target_ref}")
        original_git = lifecycle.git
        planted = False

        def git_with_race(repo: Path, *args: str, **kwargs):
            nonlocal planted
            result = original_git(repo, *args, **kwargs)
            if args and args[0] == "fetch" and args[-1] == candidate and not planted:
                run_git(self.repo, "symbolic-ref", result_ref, target_ref)
                planted = True
            return result

        with mock.patch.object(lifecycle, "git", git_with_race):
            with self.assertRaisesRegex(ClonegrownError, "conflicting symbolic result ref"):
                collect(self.ws, worker["id"])
        self.assertTrue(planted)
        self.assertEqual(git_out(self.repo, "symbolic-ref", result_ref), target_ref)
        record = json.loads(worker_record_path(self.ws, worker["id"]).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "ready")

    def test_collect_refuses_a_symbolic_result_ref_planted_before_exact_reuse(self) -> None:
        worker = self.ready("symbolic exact reuse race")
        worker_repo = Path(worker["path"])
        candidate = commit(worker_repo, "symbolic-exact.txt")
        result_ref = self.state.result_ref(worker["id"], candidate)
        target_ref = "refs/heads/symbolic-exact-target"
        run_git(self.repo, "fetch", "--no-tags", str(worker_repo), f"{candidate}:{target_ref}")
        original_resolve = lifecycle.resolve_ref
        planted = False

        def resolve_with_race(repo: Path, ref: str):
            nonlocal planted
            if ref == result_ref and not planted:
                run_git(self.repo, "symbolic-ref", result_ref, target_ref)
                planted = True
            return original_resolve(repo, ref)

        with mock.patch.object(lifecycle, "resolve_ref", resolve_with_race):
            with self.assertRaisesRegex(ClonegrownError, "conflicting symbolic result ref"):
                collect(self.ws, worker["id"])
        self.assertTrue(planted)
        self.assertEqual(git_out(self.repo, "symbolic-ref", result_ref), target_ref)
        record = json.loads(worker_record_path(self.ws, worker["id"]).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "ready")

    def test_collect_recovery_never_overwrites_a_result_ref_conflict(self) -> None:
        worker = self.ready("recovery result conflict")
        worker_repo = Path(worker["path"])
        candidate = commit(worker_repo, "recovery-conflict.txt")
        interrupted = self.cli_process(
            "collect", str(worker["id"]),
            env={"CLONEGROWN_TEST_FAILPOINT": "collect.before_fetch"},
        )
        self.assertEqual(interrupted.returncode, 88, interrupted.stderr)
        record = json.loads(worker_record_path(self.ws, worker["id"]).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "collecting")
        self.assertEqual(record["candidate_sha"], candidate)
        run_git(
            self.repo, "fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
            str(worker_repo), candidate,
        )
        planted = git_out(self.repo, "rev-parse", "HEAD")
        self.assertNotEqual(planted, candidate)
        run_git(self.repo, "update-ref", record["candidate_ref"], planted)

        actions = {item.get("action") for item in recover(self.ws) if item.get("id") == worker["id"]}
        self.assertIn("collect-reset-ready", actions)
        self.assertEqual(git_out(self.repo, "rev-parse", record["candidate_ref"]), planted)
        after = json.loads(worker_record_path(self.ws, worker["id"]).read_text(encoding="utf-8"))
        self.assertEqual(after["status"], "ready")

    def test_collect_refuses_a_result_ref_moved_before_finalization(self) -> None:
        worker = self.ready("late result race")
        candidate = commit(Path(worker["path"]), "late-result.txt")
        result_ref = self.state.result_ref(worker["id"], candidate)
        planted = git_out(self.repo, "rev-parse", "HEAD")
        self.assertNotEqual(planted, candidate)
        raced = False

        def plant_after_worker_recheck(point: str) -> None:
            nonlocal raced
            if point == "collect.after_worker_recheck" and not raced:
                run_git(self.repo, "update-ref", result_ref, planted)
                raced = True

        with mock.patch.object(lifecycle, "failpoint", plant_after_worker_recheck):
            with self.assertRaisesRegex(ClonegrownError, "update-ref transaction"):
                collect(self.ws, worker["id"])
        self.assertTrue(raced)
        self.assertEqual(git_out(self.repo, "rev-parse", result_ref), planted)
        self.assertNotEqual(
            run_git(self.repo, "rev-parse", "--verify", self.state.summary_ref(worker["id"]), check=False).returncode,
            0,
        )
        record = json.loads(worker_record_path(self.ws, worker["id"]).read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "ready")

    def test_collect_refuses_a_symbolic_result_planted_before_locked_finalization(self) -> None:
        worker = self.ready("locked symbolic finalization")
        worker_repo = Path(worker["path"])
        candidate = commit(worker_repo, "locked-symbolic.txt")
        result_ref = self.state.result_ref(worker["id"], candidate)
        target_ref = "refs/heads/locked-symbolic-target"
        run_git(self.repo, "fetch", "--no-tags", str(worker_repo), f"{candidate}:{target_ref}")
        original = repository.prepared_ref_transaction
        planted = False

        @contextmanager
        def plant_before_prepare(repo: Path, lines: list[str], **kwargs):
            nonlocal planted
            if not planted and f"verify {result_ref} {candidate}" in lines:
                run_git(self.repo, "symbolic-ref", result_ref, target_ref)
                planted = True
            with original(repo, lines, **kwargs):
                yield

        with mock.patch.object(repository, "prepared_ref_transaction", plant_before_prepare):
            with self.assertRaisesRegex(ClonegrownError, "symbolic ref"):
                collect(self.ws, worker["id"])
        self.assertTrue(planted)
        self.assertEqual(git_out(self.repo, "symbolic-ref", result_ref), target_ref)
        self.assertNotEqual(
            run_git(
                self.repo, "rev-parse", "--verify", self.state.summary_ref(worker["id"]),
                check=False,
            ).returncode,
            0,
        )
        self.assertEqual(self.record_status(worker["id"]), "ready")

    def test_collect_refuses_a_direct_result_move_after_locked_summary_commit(self) -> None:
        worker = self.ready("locked direct finalization")
        candidate = commit(Path(worker["path"]), "locked-direct.txt")
        result_ref = self.state.result_ref(worker["id"], candidate)
        planted = git_out(self.repo, "rev-parse", "HEAD")
        self.assertNotEqual(planted, candidate)
        original = lifecycle.result_ref_transaction
        moved = False

        @contextmanager
        def move_after_summary(repo: Path, result: str, summary: str, sha: str,
                               *, update_summary: bool, **kwargs):
            nonlocal moved
            with original(
                repo, result, summary, sha, update_summary=update_summary, **kwargs,
            ):
                yield
            if update_summary and not moved:
                run_git(self.repo, "update-ref", result_ref, planted)
                moved = True

        with mock.patch.object(lifecycle, "result_ref_transaction", move_after_summary):
            with self.assertRaisesRegex(ClonegrownError, "update-ref transaction"):
                collect(self.ws, worker["id"])
        self.assertTrue(moved)
        self.assertEqual(git_out(self.repo, "rev-parse", result_ref), planted)
        self.assertEqual(self.record_status(worker["id"]), "ready")

    def test_result_ref_locks_cover_the_collected_metadata_write(self) -> None:
        worker = self.ready("locked metadata finalization")
        candidate = commit(Path(worker["path"]), "locked-metadata.txt")
        result_ref = self.state.result_ref(worker["id"], candidate)
        planted = git_out(self.repo, "rev-parse", "HEAD")
        original = WorkerRecord.save
        attempted_returncode: int | None = None

        def save_while_move_is_attempted(record: WorkerRecord, workspace: Path) -> None:
            nonlocal attempted_returncode
            if record.status == "collected" and attempted_returncode is None:
                attempted_returncode = run_git(
                    self.repo, "update-ref", result_ref, planted, check=False,
                ).returncode
            original(record, workspace)

        with mock.patch.object(WorkerRecord, "save", save_while_move_is_attempted):
            outcome = collect(self.ws, worker["id"])
        self.assertIsNotNone(attempted_returncode)
        self.assertNotEqual(attempted_returncode, 0)
        self.assertEqual(outcome["status"], "collected")
        self.assertEqual(git_out(self.repo, "rev-parse", result_ref), candidate)
        self.assertEqual(status(self.ws)["issues"], [])

    def test_discarded_result_and_summary_remain_audited_custody(self) -> None:
        missing = self.ready("discarded missing result")
        commit(Path(missing["path"]), "missing.txt")
        result = collect(self.ws, missing["id"])
        release(self.ws, missing["id"])
        discard(self.ws, missing["id"])
        run_git(self.repo, "update-ref", "-d", result["result_ref"])

        self.assertIn(("result-ref-missing", missing["id"]), self.issues())
        actions = {item.get("action") for item in recover(self.ws) if item.get("id") == missing["id"]}
        self.assertIn("discarded-result-missing", actions)
        self.assertEqual(
            json.loads(worker_record_path(self.ws, missing["id"]).read_text(encoding="utf-8"))["status"],
            "discarded",
        )

        repairable = self.ready("discarded summary repair")
        commit(Path(repairable["path"]), "repairable.txt")
        kept = collect(self.ws, repairable["id"])
        release(self.ws, repairable["id"])
        discard(self.ws, repairable["id"])
        run_git(self.repo, "update-ref", self.state.summary_ref(repairable["id"]), "HEAD")
        self.assertIn(("summary-ref-mismatch", repairable["id"]), self.issues())
        actions = {item.get("action") for item in recover(self.ws) if item.get("id") == repairable["id"]}
        self.assertIn("summary-ref-repaired", actions)
        self.assertEqual(git_out(self.repo, "rev-parse", self.state.summary_ref(repairable["id"])),
                         kept["result_sha"])
        self.assertNotIn(("summary-ref-mismatch", repairable["id"]), self.issues())

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
        p = self.cli_process("spawn", "pinless", "--request-id", "pinless", env={"CLONEGROWN_TEST_FAILPOINT": "spawn.after_clone"})
        self.assertEqual(p.returncode, 88, p.stderr)
        pinless = [w for w in status(self.ws)["workers"] if w["request_id"] == "pinless"][0]
        run_git(self.repo, "update-ref", "-d", self.state.base_ref(pinless["id"]))
        self.assertIn(("base-ref-missing", pinless["id"]), self.issues())
        recover(self.ws)
        self.assertNotIn(("base-ref-missing", pinless["id"]), self.issues())

    def test_discarding_states_and_tombstone_evidence_are_reported(self) -> None:
        worker = self.collected("preserved")
        release(self.ws, worker["id"])
        p = self.cli_process("discard", str(worker["id"]), env={"CLONEGROWN_TEST_FAILPOINT": "discard.after_quarantine"})
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
        p = self.cli_process("collect", str(worker["id"]), env={"CLONEGROWN_TEST_FAILPOINT": "collect.after_summary"})
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
                p = self.cli_process(*args, env={"CLONEGROWN_TEST_FAILPOINT": point})
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
        p = self.cli_process("spawn", "failed", "--request-id", "failed", env={"CLONEGROWN_TEST_ERRORPOINT": "spawn.after_clone"})
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
        p = self.cli_process("spawn", "dead", "--request-id", "dead", env={"CLONEGROWN_TEST_FAILPOINT": "spawn.after_allocated"})
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
        p = self.cli_process("spawn", "pinned", "--request-id", "pinned", env={"CLONEGROWN_TEST_FAILPOINT": "spawn.after_allocated"})
        self.assertNotEqual(p.returncode, 0)  # refused before the counter moved: the id is still blocked
        run_git(self.repo, "update-ref", "--no-deref", "-d", self.state.base_ref(next_id))
        p = self.cli_process("spawn", "pinned", "--request-id", "pinned", env={"CLONEGROWN_TEST_FAILPOINT": "spawn.after_allocated"})
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
