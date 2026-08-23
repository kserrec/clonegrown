"""The installed ``clonegrown`` command.

Workspaces are discovered automatically from the canonical checkout, the
workspace, or any worker beneath it. Output is JSON with internal identity
and transaction fields removed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .core import ClonegrownError, validate_primary_repo
from .lifecycle import collect, discard, init_workspace, spawn
from .recovery import recover, status

_PRIVATE_KEYS = {"canonical_token", "worker_token", "params_hash", "owner_pid", "owner_start", "stage_root"}


def public_result(value: Any) -> Any:
    """Remove internal transaction/identity fields from CLI output."""
    if isinstance(value, dict):
        return {k: public_result(v) for k, v in value.items() if k not in _PRIVATE_KEYS}
    if isinstance(value, list):
        return [public_result(item) for item in value]
    return value


def default_workspace(canonical: Path) -> Path:
    """The conventional sibling workspace for a canonical checkout: ``<repo>-dev``."""
    canonical = canonical.resolve()
    return canonical.parent / f"{canonical.name}-dev"


def discover_workspace(start: Path | None = None) -> Path:
    """Find a workspace from a canonical checkout, a worker, or the workspace itself."""
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".cws" / "state.json").is_file():
            return candidate
    canonical = validate_primary_repo(start)
    workspace = default_workspace(canonical)
    if (workspace / ".cws" / "state.json").is_file():
        return workspace
    raise ClonegrownError(f"no Clonegrown workspace found for {canonical}; run `clonegrown init` first")


def resolve_workspace(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return discover_workspace()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clonegrown",
        description="Per-task Git working directories for coding agents: spawn a worker, "
                    "work in it, collect the result, discard the worker. Interrupted steps recover.",
    )
    parser.add_argument("--version", action="version", version=f"clonegrown {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def workspace_option(p: argparse.ArgumentParser) -> None:
        p.add_argument("--workspace", help="workspace path (normally auto-discovered)")

    p = sub.add_parser("init", help="create the workspace that will hold this repo's workers")
    p.add_argument("canonical", nargs="?", help="canonical checkout (default: current repo)")
    p.add_argument("--workspace", help="workspace path (default: <repo>-dev sibling)")

    p = sub.add_parser("spawn", help="create a worker (a clone by default, a worktree with --worktree)")
    p.add_argument("task", nargs="?", help="short description of the worker task")
    p.add_argument("--task", dest="task_flag", help="task description (alternate form)")
    workspace_option(p)
    p.add_argument("--base", default="HEAD", help="base ref or commit (default: HEAD)")
    isolation = p.add_mutually_exclusive_group()
    isolation.add_argument("--strong", action="store_true",
                           help="independent clone with no object sharing at all")
    isolation.add_argument("--worktree", action="store_true",
                           help="linked worktree sharing canonical's Git internals (fastest, least isolated)")
    p.add_argument("--request-id", help="stable id for idempotent repeated spawn requests")
    p.add_argument("--wait-seconds", type=float, default=120.0,
                   help="how long to wait for an in-flight spawn with the same request id")

    p = sub.add_parser("collect", help="save a worker's committed result into the canonical repo")
    p.add_argument("id", type=int, help="worker id")
    workspace_option(p)
    p.add_argument("--allow-rewrite", action="store_true",
                   help="accept a result that does not descend from the worker's base")

    p = sub.add_parser("discard", help="delete a worker whose result is saved (or --abandon it)")
    p.add_argument("id", type=int, help="worker id")
    workspace_option(p)
    p.add_argument("--abandon", action="store_true", help="discard uncollected work intentionally")
    p.add_argument("--force", action="store_true", help="discard even if the worker changed after collection")

    p = sub.add_parser("recover", help="finish or roll back operations interrupted by a crash")
    workspace_option(p)

    p = sub.add_parser("status", help="show workspace and worker state")
    workspace_option(p)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            canonical = validate_primary_repo(Path(args.canonical or "."))
            workspace = Path(args.workspace).expanduser().resolve() if args.workspace else default_workspace(canonical)
            result = init_workspace(canonical, workspace)
        elif args.command == "spawn":
            task = args.task_flag or args.task
            if not task:
                parser.error("spawn requires a task, e.g. `clonegrown spawn \"fix auth race\"`")
            result = spawn(resolve_workspace(args.workspace), args.base, task,
                           args.strong, args.request_id, args.wait_seconds,
                           mode="worktree" if args.worktree else "clone")
        elif args.command == "collect":
            result = collect(resolve_workspace(args.workspace), args.id, args.allow_rewrite)
        elif args.command == "discard":
            result = discard(resolve_workspace(args.workspace), args.id, args.abandon, args.force)
        elif args.command == "recover":
            result = recover(resolve_workspace(args.workspace))
        else:
            result = status(resolve_workspace(args.workspace))
        print(json.dumps(public_result(result), indent=2, sort_keys=True))
        return 0
    except ClonegrownError as exc:
        print(f"clonegrown: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
