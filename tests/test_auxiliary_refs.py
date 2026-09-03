"""Exact command and real-Git coverage for clone auxiliary-ref snapshots."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clonegrown import init_workspace, spawn
from clonegrown import repository as repository_module
from clonegrown.repository import copy_auxiliary_refs
from support import git_out, make_repo, run_git


AUXILIARY_PREFIXES = {
    "remote_tracking": "refs/remotes/",
    "notes": "refs/notes/",
    "replace": "refs/replace/",
}


def selected_refs(repo: Path) -> dict[str, str]:
    lines = run_git(
        repo, "for-each-ref", "--format=%(refname) %(objectname)",
    ).stdout.splitlines()
    return {
        name: object_id
        for line in lines
        for name, object_id in [line.split(" ", 1)]
        if any(name.startswith(prefix) for prefix in AUXILIARY_PREFIXES.values())
    }


def git_path(repo: Path, name: str) -> Path:
    path = Path(git_out(repo, "rev-parse", "--git-path", name))
    return path if path.is_absolute() else repo / path


def packed_ref_names(repo: Path) -> set[str]:
    packed = git_path(repo, "packed-refs")
    if not packed.exists():
        return set()
    return {
        line.partition(" ")[2]
        for line in packed.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith(("#", "^")) and " " in line
    }


class AuxiliaryRefCommandTests(unittest.TestCase):
    def test_nonempty_namespaces_share_one_fetch_then_pack(self) -> None:
        canonical = Path("/canonical")
        worker = Path("/worker")
        advertised = (
            f"refs/remotes/upstream/main\0{'1' * 40}\n"
            f"refs/remotes/upstream/HEAD\0{'2' * 40}\n"
            f"refs/notes/review\0{'3' * 40}\n"
        )
        calls: list[tuple[Path, tuple[object, ...], dict[str, object]]] = []

        def fake_git(repo: Path, *arguments: object, **keywords: object) -> subprocess.CompletedProcess[str]:
            calls.append((repo, arguments, keywords))
            stdout = ""
            if arguments[0] == "for-each-ref":
                stdout = advertised
            return subprocess.CompletedProcess(["git"], 0, stdout, "")

        with mock.patch("clonegrown.repository.git", side_effect=fake_git):
            counts = copy_auxiliary_refs(canonical, worker)

        self.assertEqual(counts, {"remote_tracking": 2, "notes": 1, "replace": 0})
        worker_calls = [(arguments, keywords) for repo, arguments, keywords in calls if repo == worker]
        fetch_input = (
            f"+{'1' * 40}:refs/remotes/upstream/main\n"
            f"+{'2' * 40}:refs/remotes/upstream/HEAD\n"
            f"+{'3' * 40}:refs/notes/review\n"
        )
        self.assertEqual(worker_calls, [
            (("fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
              "--stdin", str(canonical)), {"input": fetch_input, "sensitive": (canonical,)}),
            (("pack-refs", "--all"), {}),
        ])

    def test_empty_namespaces_run_neither_fetch_nor_pack(self) -> None:
        canonical = Path("/canonical")
        worker = Path("/worker")
        calls: list[tuple[Path, tuple[object, ...]]] = []

        def fake_git(repo: Path, *arguments: object, **_keywords: object) -> subprocess.CompletedProcess[str]:
            calls.append((repo, arguments))
            return subprocess.CompletedProcess(["git"], 0, "", "")

        with mock.patch("clonegrown.repository.git", side_effect=fake_git):
            counts = copy_auxiliary_refs(canonical, worker)

        self.assertEqual(counts, {"remote_tracking": 0, "notes": 0, "replace": 0})
        self.assertEqual([call for call in calls if call[0] == worker], [])

    def test_counts_and_refs_share_one_enumerated_snapshot_during_canonical_changes(self) -> None:
        for change in ("add", "delete"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                canonical = make_repo(root, name="canonical")
                worker = root / "worker"
                run_git(canonical, "update-ref", "refs/remotes/upstream/one", "HEAD")
                run_git(root, "clone", "-q", "--no-checkout", str(canonical), str(worker))
                original_git = repository_module.git
                mutated = False

                def mutate_after_enumeration(repo: Path, *arguments: object, **keywords: object):
                    nonlocal mutated
                    result = original_git(repo, *arguments, **keywords)
                    if not mutated and repo == canonical and arguments[0] == "for-each-ref":
                        if change == "add":
                            run_git(canonical, "update-ref", "refs/remotes/upstream/two", "HEAD")
                        else:
                            run_git(canonical, "update-ref", "-d", "refs/remotes/upstream/one")
                        mutated = True
                    return result

                with mock.patch.object(repository_module, "git", side_effect=mutate_after_enumeration):
                    counts = copy_auxiliary_refs(canonical, worker)
                copied = run_git(
                    worker, "for-each-ref", "--format=%(refname)", "refs/remotes/upstream/",
                ).stdout.splitlines()
                self.assertTrue(mutated)
                self.assertEqual(counts["remote_tracking"], 1)
                self.assertEqual(copied, ["refs/remotes/upstream/one"])


class AuxiliaryRefRealGitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.canonical = make_repo(self.root, name="canonical", branch="main")
        self.base = git_out(self.canonical, "rev-parse", "HEAD")
        tree = git_out(self.canonical, "show", "-s", "--format=%T", self.base)
        self.replacement_commit = git_out(
            self.canonical, "commit-tree", tree, "-m", "replacement history",
        )
        self.later_commit = git_out(
            self.canonical, "commit-tree", tree, "-p", self.base, "-m", "later canonical tip",
        )
        self.alternate_commit = git_out(
            self.canonical, "commit-tree", tree, "-m", "temporary packed-ref value",
        )

        self.original_blob = git_out(self.canonical, "rev-parse", f"{self.base}:README.md")
        replacement_source = self.root / "replacement-blob.txt"
        replacement_source.write_text("replacement blob content\n", encoding="utf-8")
        self.replacement_blob = git_out(
            self.canonical, "hash-object", "-w", str(replacement_source),
        )

        self.remote_ref = "refs/remotes/upstream/main"
        self.symbolic_remote = "refs/remotes/upstream/HEAD"
        self.note_ref = "refs/notes/review"
        self.replace_commit_ref = f"refs/replace/{self.base}"
        self.replace_blob_ref = f"refs/replace/{self.original_blob}"
        run_git(self.canonical, "update-ref", self.remote_ref, self.base)
        run_git(self.canonical, "symbolic-ref", self.symbolic_remote, self.remote_ref)
        run_git(
            self.canonical, "notes", f"--ref={self.note_ref}",
            "add", "-m", "review note", self.base,
        )
        run_git(self.canonical, "replace", self.base, self.replacement_commit)
        run_git(self.canonical, "replace", self.original_blob, self.replacement_blob)
        run_git(self.canonical, "update-ref", "refs/stash", self.base)

        self.workspace = self.root / "workspace"
        init_workspace(self.canonical, self.workspace)
        for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD"):
            git_path(self.canonical, name).write_text(self.base + "\n", encoding="ascii")

        self.expected_refs = selected_refs(self.canonical)
        self.expected_counts = {
            label: sum(name.startswith(prefix) for name in self.expected_refs)
            for label, prefix in AUXILIARY_PREFIXES.items()
        }
        self.assertEqual(self.expected_counts, {
            "remote_tracking": 2,
            "notes": 1,
            "replace": 2,
        })
        self.assertEqual(
            git_out(self.canonical, "symbolic-ref", self.symbolic_remote),
            self.remote_ref,
        )
        self.canonical_packed_refs = git_path(self.canonical, "packed-refs")
        self.assertFalse(self.canonical_packed_refs.exists())

    def tearDown(self) -> None:
        self.temp.cleanup()

    def assert_semantics(self, repo: Path) -> None:
        self.assertEqual(git_out(repo, "rev-parse", self.remote_ref), self.base)
        self.assertEqual(
            git_out(repo, "rev-list", "--left-right", "--count", f"HEAD...{self.remote_ref}"),
            "0\t0",
        )
        self.assertEqual(
            git_out(repo, "notes", f"--ref={self.note_ref}", "show", self.base),
            "review note",
        )
        self.assertEqual(
            git_out(repo, "log", "-1", "--format=%s", self.base),
            "replacement history",
        )
        self.assertEqual(
            git_out(repo, "--no-replace-objects", "log", "-1", "--format=%s", self.base),
            "README.md",
        )
        self.assertEqual(
            git_out(repo, "cat-file", "-p", self.original_blob),
            "replacement blob content",
        )

    def assert_exact_snapshot(self, repo: Path) -> None:
        actual = selected_refs(repo)
        self.assertEqual(
            {name: actual.get(name) for name in self.expected_refs},
            self.expected_refs,
        )
        extras = set(actual) - set(self.expected_refs)
        self.assertTrue(all(name.startswith("refs/remotes/cws-source") for name in extras))
        self.assertEqual(git_out(repo, "rev-parse", self.symbolic_remote), self.base)

    def assert_excluded_clone_state(self, repo: Path) -> None:
        for name in ("refs/stash", "MERGE_HEAD", "CHERRY_PICK_HEAD"):
            with self.subTest(excluded=name):
                result = run_git(repo, "rev-parse", "--verify", "--quiet", name, check=False)
                self.assertNotEqual(result.returncode, 0)
        self.assertEqual(run_git(repo, "for-each-ref", "refs/cws/").stdout, "")

    def exercise_packed_updates(self, repo: Path) -> None:
        refs = (self.remote_ref, self.note_ref, self.replace_commit_ref)
        for name in refs:
            original = self.expected_refs[name]
            with self.subTest(ref=name):
                run_git(repo, "update-ref", name, self.alternate_commit, original)
                self.assertEqual(git_out(repo, "rev-parse", name), self.alternate_commit)
                run_git(repo, "update-ref", "-d", name, self.alternate_commit)
                missing = run_git(repo, "rev-parse", "--verify", "--quiet", name, check=False)
                self.assertNotEqual(missing.returncode, 0)
                run_git(repo, "update-ref", name, original, "0" * len(original))
        self.assert_semantics(repo)

    def test_default_strong_and_worktree_preserve_the_full_contract(self) -> None:
        workers = {
            "default": spawn(
                self.workspace, "HEAD", "default auxiliary refs",
                request_id="aux-default", strong=False, mode="clone",
            ),
            "strong": spawn(
                self.workspace, "HEAD", "strong auxiliary refs",
                request_id="aux-strong", strong=True, mode="clone",
            ),
            "worktree": spawn(
                self.workspace, "HEAD", "shared auxiliary refs",
                request_id="aux-worktree", strong=False, mode="worktree",
            ),
        }
        clone_repos = [Path(workers[label]["path"]) for label in ("default", "strong")]
        worktree_repo = Path(workers["worktree"]["path"])

        self.assertFalse(self.canonical_packed_refs.exists())
        self.assertNotEqual(run_git(self.canonical, "for-each-ref", "refs/cws/").stdout, "")
        for label, repo in zip(("default", "strong"), clone_repos, strict=True):
            with self.subTest(mode=label):
                self.assertEqual(workers[label]["copied_auxiliary_refs"], self.expected_counts)
                self.assert_exact_snapshot(repo)
                self.assert_semantics(repo)
                self.assert_excluded_clone_state(repo)
                packed = packed_ref_names(repo)
                self.assertTrue({
                    self.remote_ref,
                    self.note_ref,
                    self.replace_commit_ref,
                    self.replace_blob_ref,
                }.issubset(packed))

        self.assertEqual(workers["worktree"]["copied_auxiliary_refs"], {})
        self.assertEqual(selected_refs(worktree_repo), self.expected_refs)
        self.assert_semantics(worktree_repo)
        self.assertEqual(
            git_out(worktree_repo, "symbolic-ref", self.symbolic_remote),
            self.remote_ref,
        )

        disconnected = self.canonical.with_name("canonical-offline")
        self.canonical.rename(disconnected)
        try:
            for repo in clone_repos:
                self.assert_semantics(repo)
        finally:
            disconnected.rename(self.canonical)

        for repo in clone_repos:
            self.exercise_packed_updates(repo)

        changed = {
            self.remote_ref: self.later_commit,
            self.note_ref: None,
            self.replace_commit_ref: None,
            self.replace_blob_ref: None,
        }
        try:
            run_git(self.canonical, "update-ref", self.remote_ref, self.later_commit, self.base)
            for name in (self.note_ref, self.replace_commit_ref, self.replace_blob_ref):
                run_git(self.canonical, "update-ref", "-d", name, self.expected_refs[name])

            for repo in clone_repos:
                self.assert_exact_snapshot(repo)
                self.assert_semantics(repo)

            live_refs = selected_refs(worktree_repo)
            self.assertEqual(live_refs[self.remote_ref], self.later_commit)
            self.assertEqual(live_refs[self.symbolic_remote], self.later_commit)
            for name in (self.note_ref, self.replace_commit_ref, self.replace_blob_ref):
                self.assertNotIn(name, live_refs)
        finally:
            for name, object_id in changed.items():
                expected = self.expected_refs[name]
                if object_id is None:
                    run_git(self.canonical, "update-ref", name, expected, "0" * len(expected))
                else:
                    run_git(self.canonical, "update-ref", name, expected, object_id)

        self.assertEqual(selected_refs(worktree_repo), self.expected_refs)
        self.assert_semantics(worktree_repo)
        self.assertFalse(self.canonical_packed_refs.exists())


if __name__ == "__main__":
    unittest.main()
