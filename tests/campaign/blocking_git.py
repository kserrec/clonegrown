#!/usr/bin/env python3
"""Test Git executable that lets a parent-only SIGKILL leave one child alive.

Nonmatching commands exec the real Git immediately. The first matching command
records its PID and arguments, waits for the harness to release it, runs real
Git, records the result, and exits with Git's status.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PREFIXES = {
    "clone": ("clone",),
    "fetch": ("fetch",),
    "update-ref": ("update-ref", "--stdin"),
    "worktree-add": ("worktree", "add"),
    "worktree-repair": ("worktree", "repair"),
}

GIT_OPTIONS_WITH_VALUE = {
    "-C",
    "-c",
    "--config-env",
    "--git-dir",
    "--namespace",
    "--work-tree",
}


def command_arguments(args: list[str]) -> list[str]:
    """Return Git's command and arguments after any leading global options."""
    index = 0
    while index < len(args):
        argument = args[index]
        if argument == "--":
            return args[index + 1:]
        if argument in GIT_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if argument.startswith("-"):
            index += 1
            continue
        return args[index:]
    return []


def inherited_descriptor_fds(args: list[str]) -> tuple[int, ...]:
    """Keep descriptor-backed Git paths alive when the wrapper starts real Git."""
    descriptors: set[int] = set()
    for argument in args:
        value = argument.partition("=")[2] if "=" in argument else argument
        for prefix in ("/dev/fd/", "/proc/self/fd/"):
            if value.startswith(prefix) and value[len(prefix):].isdigit():
                descriptors.add(int(value[len(prefix):]))
    return tuple(sorted(descriptors))


def write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    real_git = os.environ["CLONEGROWN_TEST_REAL_GIT"]
    control = Path(os.environ["CLONEGROWN_TEST_GIT_CONTROL"])
    target = os.environ["CLONEGROWN_TEST_GIT_TARGET"]
    args = sys.argv[1:]
    command = command_arguments(args)
    prefix = PREFIXES[target]
    if tuple(command[:len(prefix)]) != prefix:
        os.execv(real_git, [real_git, *args])

    control.mkdir(parents=True, exist_ok=True)
    try:
        claim = os.open(control / "claimed", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        os.execv(real_git, [real_git, *args])
    else:
        os.close(claim)

    write_json(control / "started.json", {"pid": os.getpid(), "args": command})
    deadline = time.monotonic() + 60
    while not (control / "release").exists():
        if time.monotonic() >= deadline:
            write_json(control / "result.json", {"pid": os.getpid(), "timed_out": True})
            return 97
        time.sleep(0.01)

    # The killed parent owned the original stdout/stderr pipes. Capture output
    # here so real Git cannot receive SIGPIPE merely because that reader died.
    completed = subprocess.run(
        [real_git, *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        pass_fds=inherited_descriptor_fds(args),
    )
    write_json(control / "result.json", {
        "pid": os.getpid(),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    })
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
