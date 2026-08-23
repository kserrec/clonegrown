"""Positional command-line interface used by the research harnesses in ``tests/``.

This is not the installed command. It differs from ``clonegrown.cli`` on
purpose: every command takes the workspace path explicitly, ``spawn`` is
strong unless ``--fast`` is given, the default base is ``main``, and output
is the unredacted metadata. Run it as ``python -m clonegrown.legacy_cli``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .core import CWSError
from .lifecycle import collect, discard, init_workspace, spawn
from .recovery import recover, status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clonegrown-legacy", description="Clonegrown research-harness interface")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("canonical")
    p.add_argument("workspace")
    p = sub.add_parser("spawn")
    p.add_argument("workspace")
    p.add_argument("--base", default="main")
    p.add_argument("--task", required=True)
    p.add_argument("--fast", action="store_true")
    p.add_argument("--request-id")
    p.add_argument("--wait-seconds", type=float, default=120.0)
    p = sub.add_parser("collect")
    p.add_argument("workspace")
    p.add_argument("id", type=int)
    p.add_argument("--allow-rewrite", action="store_true")
    p = sub.add_parser("discard")
    p.add_argument("workspace")
    p.add_argument("id", type=int)
    p.add_argument("--abandon", action="store_true")
    p.add_argument("--force", action="store_true")
    for name in ("recover", "status"):
        sub.add_parser(name).add_argument("workspace")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            result = init_workspace(Path(args.canonical), Path(args.workspace))
        elif args.command == "spawn":
            result = spawn(Path(args.workspace), args.base, args.task, not args.fast, args.request_id, args.wait_seconds)
        elif args.command == "collect":
            result = collect(Path(args.workspace), args.id, args.allow_rewrite)
        elif args.command == "discard":
            result = discard(Path(args.workspace), args.id, args.abandon, args.force)
        elif args.command == "recover":
            result = recover(Path(args.workspace))
        else:
            result = status(Path(args.workspace))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except CWSError as exc:
        print(f"clonegrown: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
