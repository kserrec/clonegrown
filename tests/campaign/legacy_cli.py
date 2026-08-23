#!/usr/bin/env python3
"""Research-harness entry point: the harnesses' positional command form, run through the real CLI.

The harnesses predate the installed command and write ``spawn <workspace>
--task T --base B [--fast|--worktree]`` (strong unless told otherwise,
default base ``main``). This translates that form to ``clonegrown``'s own
arguments so the harnesses exercise the code users run.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from clonegrown.cli import main  # noqa: E402


def translate(argv: list[str]) -> list[str]:
    command, rest = argv[0], argv[1:]
    if command == "init":
        canonical, workspace, *rest = rest
        return ["init", canonical, "--workspace", workspace, *rest]
    workspace, *rest = rest
    if command == "spawn":
        if "--base" not in rest:
            rest += ["--base", "main"]
        if "--fast" not in rest and "--worktree" not in rest:
            rest.append("--strong")
        rest = [arg for arg in rest if arg != "--fast"]
    return [command, "--workspace", workspace, *rest]


raise SystemExit(main(translate(sys.argv[1:])))
