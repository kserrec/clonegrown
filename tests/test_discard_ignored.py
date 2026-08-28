"""Ignored content is in discard's custody: a collected worker's ignored paths need their own acknowledgement."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from clonegrown import ClonegrownError, collect, discard, release, spawn
from clonegrown.worker import IGNORED_SAMPLE_LIMIT, inspect_ignored_content
from support import commit, make_repo, run_cli, run_git, filesystem_accepts_non_utf8_names

MODES = ("clone", "worktree")
SECRET_CONTENT = "ignored-file-body-that-must-never-be-printed-7f3a9c"


class DiscardIgnoredTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name).resolve()  # macOS: TMPDIR is a symlink
        # Global excludes come from the user's own Git configuration; point them at a throwaway home.
        self.home = self.root / "home"
        (self.home / ".config" / "git").mkdir(parents=True)
        self.saved_env = {key: os.environ.get(key) for key in ("HOME", "XDG_CONFIG_HOME")}
        os.environ["HOME"] = str(self.home)
        os.environ["XDG_CONFIG_HOME"] = str(self.home / ".config")
        self.repo = make_repo(self.root)
        (self.repo / ".gitignore").write_text("*.log\nbuild/\n", encoding="utf-8")
        commit(self.repo, ".gitignore", "*.log\nbuild/\n")
        self.ws = self.root / "demo-dev"
        rc, _ = run_cli(self.repo, "init")
        self.assertEqual(rc, 0)

    def tearDown(self) -> None:
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.td.cleanup()

    def collected_worker(self, task: str, mode: str = "clone") -> dict:
        worker = spawn(self.ws, "HEAD", task, strong=False, mode=mode)
        commit(Path(worker["path"]), "work.txt")
        collect(self.ws, worker["id"])
        release(self.ws, worker["id"])
        return worker

    def assert_refused_for_ignored(self, worker: dict, *fragments: str) -> str:
        with self.assertRaisesRegex(ClonegrownError, "--discard-ignored") as caught:
            discard(self.ws, worker["id"])
        message = str(caught.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)
        self.assertNotIn(SECRET_CONTENT, message)
        self.assertTrue(Path(worker["path"]).is_dir())
        return message

    # --- every way Git can ignore a path ------------------------------------------

    def test_ignored_file_needs_discard_ignored(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                worker = self.collected_worker(f"ignored file {mode}", mode)
                (Path(worker["path"]) / "debug.log").write_text(SECRET_CONTENT + "\n", encoding="utf-8")
                self.assert_refused_for_ignored(worker, "1 ignored path (debug.log)")
                self.assertEqual(discard(self.ws, worker["id"], discard_ignored=True)["status"], "discarded")
                self.assertFalse(Path(worker["path"]).exists())

    def test_ignored_directory_is_one_entry(self) -> None:
        worker = self.collected_worker("ignored directory")
        build = Path(worker["path"]) / "build"
        (build / "nested").mkdir(parents=True)
        (build / "nested" / "artifact.bin").write_bytes(b"\x00" + SECRET_CONTENT.encode() + b"\x00")
        (build / "other.o").write_text("o\n", encoding="utf-8")
        self.assert_refused_for_ignored(worker, "1 ignored path (build/)")

    def test_info_exclude_is_honored(self) -> None:
        worker = self.collected_worker("info exclude")
        repo = Path(worker["path"])
        exclude = Path(run_git(repo, "rev-parse", "--git-path", "info/exclude").stdout.strip())
        exclude = exclude if exclude.is_absolute() else repo / exclude
        exclude.parent.mkdir(parents=True, exist_ok=True)
        exclude.write_text("private-notes\n", encoding="utf-8")
        (repo / "private-notes").write_text(SECRET_CONTENT + "\n", encoding="utf-8")
        self.assert_refused_for_ignored(worker, "(private-notes)")

    def test_global_excludes_are_honored(self) -> None:
        (self.home / ".config" / "git" / "ignore").write_text("*.swp\n", encoding="utf-8")
        worker = self.collected_worker("global excludes")
        (Path(worker["path"]) / ".work.txt.swp").write_text(SECRET_CONTENT + "\n", encoding="utf-8")
        self.assert_refused_for_ignored(worker, "(.work.txt.swp)")

    def test_large_ignored_set_is_counted_exactly_and_sampled(self) -> None:
        worker = self.collected_worker("many ignored")
        repo = Path(worker["path"])
        total = 600
        for index in range(total):
            (repo / f"trace-{index:04d}.log").write_text(SECRET_CONTENT + "\n", encoding="utf-8")
        message = self.assert_refused_for_ignored(worker, f"{total} ignored paths")
        self.assertIn(f"and {total - IGNORED_SAMPLE_LIMIT} more", message)
        self.assertLess(len(message), 600, "the sample is not bounded")
        listing = inspect_ignored_content(repo)
        self.assertEqual(listing.count, total)
        self.assertEqual(len(listing.sample), IGNORED_SAMPLE_LIMIT)
        self.assertEqual(listing.sample[0], "trace-0000.log")

    def test_non_utf8_ignored_name_is_listed_without_failing(self) -> None:
        if not filesystem_accepts_non_utf8_names(self.root):
            self.skipTest("this filesystem rejects non-UTF-8 file names")
        worker = self.collected_worker("non utf8 name")
        repo = Path(worker["path"])
        raw = os.fsencode(str(repo)) + b"/tr\xfface.log"
        with open(raw, "wb") as stream:
            stream.write(b"x\n")
        listing = inspect_ignored_content(repo)
        self.assertEqual(listing.count, 1)
        self.assertEqual(os.fsencode(listing.sample[0]), b"tr\xfface.log")
        self.assert_refused_for_ignored(worker, "1 ignored path")

    # --- the acknowledgements stay separate -----------------------------------------

    def test_drift_and_ignored_content_each_need_their_own_flag(self) -> None:
        worker = self.collected_worker("both")
        repo = Path(worker["path"])
        (repo / "out.log").write_text(SECRET_CONTENT + "\n", encoding="utf-8")
        commit(repo, "after-collection.txt")
        message = self.assert_refused_for_ignored(worker, "--force", "--discard-ignored")
        self.assertNotIn(SECRET_CONTENT, message)
        with self.assertRaisesRegex(ClonegrownError, "--discard-ignored"):
            discard(self.ws, worker["id"], force=True)
        with self.assertRaisesRegex(ClonegrownError, "--force"):
            discard(self.ws, worker["id"], discard_ignored=True)
        self.assertTrue(repo.is_dir())
        self.assertEqual(discard(self.ws, worker["id"], force=True, discard_ignored=True)["status"], "discarded")

    def test_abandon_covers_ignored_content_of_an_uncollected_worker(self) -> None:
        worker = spawn(self.ws, "HEAD", "uncollected", strong=False)
        (Path(worker["path"]) / "scratch.log").write_text(SECRET_CONTENT + "\n", encoding="utf-8")
        release(self.ws, worker["id"])
        with self.assertRaisesRegex(ClonegrownError, "--abandon"):
            discard(self.ws, worker["id"])
        self.assertEqual(discard(self.ws, worker["id"], abandon=True)["status"], "abandoned")

    def test_lease_is_checked_before_ignored_content(self) -> None:
        worker = spawn(self.ws, "HEAD", "still leased", strong=False)
        commit(Path(worker["path"]), "work.txt")
        collect(self.ws, worker["id"])
        (Path(worker["path"]) / "debug.log").write_text("x\n", encoding="utf-8")
        with self.assertRaisesRegex(ClonegrownError, "leased"):
            discard(self.ws, worker["id"], discard_ignored=True)

    def test_clean_collected_worker_discards_with_or_without_the_flag(self) -> None:
        first = self.collected_worker("clean one")
        self.assertEqual(discard(self.ws, first["id"])["status"], "discarded")
        second = self.collected_worker("clean two")
        self.assertEqual(discard(self.ws, second["id"], discard_ignored=True)["status"], "discarded")

    def test_cli_flag_and_error_text(self) -> None:
        rc, worker = run_cli(self.repo, "spawn", "cli ignored")
        self.assertEqual(rc, 0)
        repo = Path(worker["path"])
        commit(repo, "work.txt")
        (repo / "cli.log").write_text(SECRET_CONTENT + "\n", encoding="utf-8")
        run_cli(self.repo, "collect", str(worker["id"]))
        run_cli(self.repo, "release", str(worker["id"]))
        with self.assertRaisesRegex(ClonegrownError, "cli.log") as caught:
            from clonegrown.lifecycle import discard as api_discard
            api_discard(self.ws, worker["id"])
        self.assertNotIn(SECRET_CONTENT, str(caught.exception))
        rc, discarded = run_cli(self.repo, "discard", str(worker["id"]), "--discard-ignored")
        self.assertEqual(rc, 0)
        self.assertEqual(discarded["status"], "discarded")


if __name__ == "__main__":
    unittest.main()
