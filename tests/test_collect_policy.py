"""Collection's rewrite policy is durable: an accepted rewrite stays accepted on an unchanged
repeat, and no repeat argument can admit a different candidate, result, or summary."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from clonegrown import ClonegrownError, collect, init_workspace, spawn
from clonegrown.state import WorkspaceState
from support import commit, git_out, make_repo, run_git


def rewrite_history(repo: Path) -> str:
    """Replace the worker's history with an unrelated root commit; returns its id."""
    run_git(repo, "config", "user.name", "Clonegrown Test")
    run_git(repo, "config", "user.email", "clonegrown@example.test")
    empty_tree = git_out(repo, "hash-object", "-w", "-t", "tree", "/dev/null")
    root = subprocess.run(["git", "commit-tree", empty_tree], cwd=repo, check=True, text=True,
                          input="rewritten root\n", stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()
    run_git(repo, "reset", "-q", "--hard", root)
    return root


class CollectPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name).resolve()
        self.repo = make_repo(self.root)
        self.ws = self.root / "demo-dev"
        init_workspace(self.repo, self.ws)

    def tearDown(self) -> None:
        self.td.cleanup()

    def summary(self, worker: dict) -> str:
        return git_out(self.repo, "rev-parse", WorkspaceState.load(self.ws).summary_ref(worker["id"]))

    def test_rewrite_needs_the_flag_and_is_recorded(self) -> None:
        worker = spawn(self.ws, "HEAD", "rewrite")
        root = rewrite_history(Path(worker["path"]))
        with self.assertRaisesRegex(ClonegrownError, "does not descend"):
            collect(self.ws, worker["id"])
        collected = collect(self.ws, worker["id"], allow_rewrite=True)
        self.assertEqual((collected["status"], collected["result_sha"], collected["allow_rewrite"]),
                         ("collected", root, True))

    def test_unchanged_repeat_uses_the_accepted_rewrite_policy(self) -> None:
        worker = spawn(self.ws, "HEAD", "accepted rewrite")
        root = rewrite_history(Path(worker["path"]))
        first = collect(self.ws, worker["id"], allow_rewrite=True)
        summary_before = self.summary(worker)
        for repeat_argument in (False, True):
            with self.subTest(allow_rewrite=repeat_argument):
                second = collect(self.ws, worker["id"], allow_rewrite=repeat_argument)
                self.assertEqual(second, first)  # a no-op: same record, result, and recorded policy
                self.assertEqual(second["result_sha"], root)
                self.assertEqual(git_out(self.repo, "rev-parse", first["result_ref"]), root)
                self.assertEqual(self.summary(worker), summary_before)

    def test_ordinary_repeat_stays_a_no_op_and_new_work_is_refused_under_any_argument(self) -> None:
        worker = spawn(self.ws, "HEAD", "ordinary repeat")
        repo = Path(worker["path"])
        head = commit(repo, "work.txt")
        first = collect(self.ws, worker["id"])
        self.assertEqual((first["result_sha"], first["allow_rewrite"]), (head, False))
        self.assertEqual(collect(self.ws, worker["id"]), first)
        self.assertEqual(collect(self.ws, worker["id"], allow_rewrite=True), first)
        # Neither a descendant nor a rewrite can be admitted by a repeat, whatever the argument says.
        for label, change in (("descendant", lambda: commit(repo, "more.txt")),
                              ("rewrite", lambda: rewrite_history(repo))):
            change()
            for repeat_argument in (False, True):
                with self.subTest(change=label, allow_rewrite=repeat_argument):
                    with self.assertRaisesRegex(ClonegrownError, "changed after collection|does not descend"):
                        collect(self.ws, worker["id"], allow_rewrite=repeat_argument)
                    self.assertEqual(git_out(self.repo, "rev-parse", first["result_ref"]), head)
                    self.assertEqual(self.summary(worker), head)

    def test_worker_local_history_overrides_cannot_fake_ancestry(self) -> None:
        """A replace ref or a grafts file inside the worker's own repository makes Git's
        default history view lie; the ancestry gate judges object content and refuses."""
        from clonegrown.repository import is_ancestor
        for label in ("replace ref", "grafts file"):
            with self.subTest(override=label):
                worker = spawn(self.ws, "HEAD", f"override {label}")
                repo = Path(worker["path"])
                root = rewrite_history(repo)
                base = worker["base_sha"]
                if label == "replace ref":
                    # Replace the orphan with a commit that carries its tree but is parented on the base.
                    tree = git_out(repo, "rev-parse", f"{root}^{{tree}}")
                    parented = subprocess.run(["git", "commit-tree", tree, "-p", base], cwd=repo, check=True, text=True,
                                              input="parented\n", stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()
                    run_git(repo, "replace", "-f", root, parented)
                else:
                    (repo / ".git" / "info" / "grafts").write_text(f"{root} {base}\n", encoding="utf-8")
                    run_git(repo, "config", "advice.graftFileDeprecated", "false")
                # Git's default view is fooled; Clonegrown's content-only judgement is not.
                self.assertEqual(run_git(repo, "merge-base", "--is-ancestor", base, root, check=False).returncode, 0)
                self.assertFalse(is_ancestor(repo, base, root))
                with self.assertRaisesRegex(ClonegrownError, "does not descend"):
                    collect(self.ws, worker["id"])
                self.assertEqual(collect(self.ws, worker["id"], allow_rewrite=True)["result_sha"], root)
                self.assertFalse(run_git(self.repo, "merge-base", "--is-ancestor", base, root, check=False).returncode == 0)

    def test_canonical_side_ancestry_check_holds_even_if_the_worker_snapshot_lied(self) -> None:
        """Belt and braces: after the fetch, ancestry is judged again on canonical's own
        copy of the objects, where nothing planted in the worker exists."""
        from unittest import mock
        from clonegrown import worker as worker_module
        worker = spawn(self.ws, "HEAD", "canonical recheck")
        repo = Path(worker["path"])
        root = rewrite_history(repo)
        real = worker_module.is_ancestor
        with mock.patch.object(worker_module, "is_ancestor", lambda *a, **k: True):
            with self.assertRaisesRegex(ClonegrownError, "does not descend"):
                collect(self.ws, worker["id"])
        self.assertIs(worker_module.is_ancestor, real)
        state = WorkspaceState.load(self.ws)
        self.assertEqual(run_git(self.repo, "rev-parse", "--verify", "-q", state.summary_ref(worker["id"]),
                                 check=False).returncode, 1)

    def test_recovery_judges_ancestry_on_canonical_before_finishing(self) -> None:
        """A forged parent object inside a strong clone fools every worker-side judgement (Git
        does not verify a parent's hash while walking history); an interrupted collection must
        still be refused by recovery, which judges on canonical's own objects."""
        import os
        import subprocess
        import sys
        import zlib
        from unittest import mock
        from clonegrown import recover, status
        from clonegrown import worker as worker_module
        from clonegrown.repository import is_ancestor
        base = git_out(self.repo, "rev-parse", "HEAD")
        run_git(self.repo, "checkout", "-q", "-b", "side", "HEAD~0")
        run_git(self.repo, "reset", "-q", "--hard", "HEAD")
        # side: an unrelated line that does not descend from the base commit.
        empty_tree = git_out(self.repo, "hash-object", "-w", "-t", "tree", "/dev/null")
        s1 = subprocess.run(["git", "commit-tree", empty_tree], cwd=self.repo, check=True, text=True,
                            input="side1\n", stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()
        x = subprocess.run(["git", "commit-tree", empty_tree, "-p", s1], cwd=self.repo, check=True, text=True,
                           input="side2\n", stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()
        run_git(self.repo, "update-ref", "refs/heads/side", x)
        run_git(self.repo, "checkout", "-q", "trunk")
        worker = spawn(self.ws, "HEAD", "forged parent", strong=True)
        repo = Path(worker["path"])
        run_git(repo, "fetch", "-q", str(self.repo), "refs/heads/side")
        run_git(repo, "reset", "-q", "--hard", x)
        # Forge S1 inside the worker so that it claims the base as its parent.
        body = run_git(repo, "cat-file", "commit", s1).stdout.encode()
        forged = body.replace(b"tree " + empty_tree.encode() + b"\n", b"tree " + empty_tree.encode() + b"\nparent " + base.encode() + b"\n", 1)
        objects = Path(git_out(repo, "rev-parse", "--git-path", "objects"))
        target = (repo / objects if not objects.is_absolute() else objects) / s1[:2] / s1[2:]
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            os.unlink(target)
        target.write_bytes(zlib.compress(b"commit %d\0" % len(forged) + forged))
        self.assertTrue(is_ancestor(repo, base, x))  # the worker-side judgement is fooled
        self.assertFalse(is_ancestor(self.repo, base, x))
        # Plain collect: refused on canonical's copy after the fetch.
        with self.assertRaisesRegex(ClonegrownError, "does not descend"):
            collect(self.ws, worker["id"])
        # Interrupted right after the collecting mark, then recovered.
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent), "CLONEGROWN_TEST_MODE": "1",
               "CLONEGROWN_TEST_FAILPOINT": "collect.after_mark"}
        process = subprocess.run([sys.executable, "-m", "clonegrown", "collect", str(worker["id"]), "--workspace",
                                  str(self.ws)], cwd=self.repo, env=env, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        self.assertEqual(process.returncode, 88, process.stderr)
        actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertNotIn("collect-finished", actions)
        self.assertIn("collect-reset-ready", actions)
        state = WorkspaceState.load(self.ws)
        self.assertEqual(run_git(self.repo, "rev-parse", "--verify", "-q", state.summary_ref(worker["id"]),
                                 check=False).returncode, 1)
        self.assertEqual([w["status"] for w in status(self.ws)["workers"] if w["id"] == worker["id"]], ["ready"])
        # Even a worker-side judgement forced to lie in-process cannot finish through recovery.
        process = subprocess.run([sys.executable, "-m", "clonegrown", "collect", str(worker["id"]), "--workspace",
                                  str(self.ws)], cwd=self.repo, env=env, text=True, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        self.assertEqual(process.returncode, 88, process.stderr)
        with mock.patch.object(worker_module, "is_ancestor", lambda *a, **k: True):
            actions = {r.get("action") for r in recover(self.ws) if r.get("id") == worker["id"]}
        self.assertNotIn("collect-finished", actions)
        self.assertEqual(run_git(self.repo, "rev-parse", "--verify", "-q", state.summary_ref(worker["id"]),
                                 check=False).returncode, 1)

    def test_status_reports_a_collected_result_that_canonical_says_does_not_descend(self) -> None:
        from clonegrown import status
        from clonegrown.state import worker_record_path
        worker = spawn(self.ws, "HEAD", "canonical drift")
        root = rewrite_history(Path(worker["path"]))
        collect(self.ws, worker["id"], allow_rewrite=True)
        self.assertNotIn("drift", [w for w in status(self.ws)["workers"] if w["id"] == worker["id"]][0])
        path = worker_record_path(self.ws, worker["id"])
        record = json.loads(path.read_text(encoding="utf-8"))
        record["allow_rewrite"] = False  # a record that claims descent canonical cannot confirm
        path.write_text(json.dumps(record), encoding="utf-8")
        item = [w for w in status(self.ws)["workers"] if w["id"] == worker["id"]][0]
        self.assertIn("does not descend", item.get("drift", ""))
        self.assertEqual(item["result_sha"], root)


if __name__ == "__main__":
    unittest.main()
