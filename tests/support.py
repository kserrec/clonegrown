"""Helpers shared by the unit tests: a throwaway repo, Git shortcuts, and an in-process CLI runner."""
from __future__ import annotations

import io
import json
import os
import subprocess
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from clonegrown import cli


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def git_out(repo: Path, *args: str) -> str:
    return run_git(repo, *args).stdout.strip()


def make_repo(root: Path, name: str = "demo", branch: str = "trunk") -> Path:
    """A repository with one commit, on a branch deliberately not named main."""
    repo = root / name
    repo.mkdir()
    run_git(repo, "init", "-q", "-b", branch)
    commit(repo, "README.md", "hello\n")
    return repo


def commit(repo: Path, name: str, content: str | None = None) -> str:
    """Write one file and commit it; returns the new HEAD."""
    run_git(repo, "config", "user.name", "Clonegrown Test")
    run_git(repo, "config", "user.email", "clonegrown@example.test")
    (repo / name).write_text(content if content is not None else name + "\n", encoding="utf-8")
    run_git(repo, "add", name)
    run_git(repo, "commit", "-q", "-m", name)
    return git_out(repo, "rev-parse", "HEAD")


def run_cli(cwd: Path, *args: str) -> tuple[int, Any]:
    """Run the installed CLI in-process from ``cwd``; returns (exit code, parsed JSON)."""
    old = Path.cwd()
    output = io.StringIO()
    try:
        os.chdir(cwd)
        with redirect_stdout(output):
            rc = cli.main(list(args))
    finally:
        os.chdir(old)
    return rc, json.loads(output.getvalue())
