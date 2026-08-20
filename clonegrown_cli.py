"""Ergonomic command-line interface for Clonegrown."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from clonegrown import CWSError, collect, discard, init_workspace, recover, spawn, status
from clonegrown_core import validate_primary_repo

_PRIVATE_KEYS = {
    "canonical_token",
    "worker_token",
    "params_hash",
    "owner_pid",
    "owner_start",
    "stage_root",
}


def public_result(value: Any) -> Any:
    """Remove internal transaction/identity fields from CLI output."""
    if isinstance(value, dict):
        return {
            key: public_result(item)
            for key, item in value.items()
            if key not in _PRIVATE_KEYS
        }
    if isinstance(value, list):
        return [public_result(item) for item in value]
    return value


def default_workspace(canonical: Path) -> Path:
    """Return the conventional sibling workspace for a canonical checkout."""
    canonical = canonical.resolve()
    return canonical.parent / f"{canonical.name}-dev"


def discover_workspace(start: Path | None = None) -> Path:
    """Find a Clonegrown workspace from a canonical checkout, worker, or workspace."""
    start = (start or Path.cwd()).resolve()

    # When called from the workspace itself or any worker beneath it, walk upward.
    for candidate in (start, *start.parents):
        if (candidate / ".cws" / "state.json").is_file():
            return candidate

    # When called from the canonical checkout, use its conventional sibling.
    canonical = validate_primary_repo(start)
    workspace = default_workspace(canonical)
    if (workspace / ".cws" / "state.json").is_file():
        return workspace

    raise CWSError(
        f"no Clonegrown workspace found for {canonical}; run `clonegrown init` first"
    )


def resolve_workspace(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    return discover_workspace()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clonegrown",
        description="Isolated Git clone workspaces for coding agents",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="initialize a sibling Clonegrown workspace")
    p.add_argument("canonical", nargs="?", help="canonical checkout (default: current repo)")
    p.add_argument("--workspace", help="workspace path (default: <repo>-dev sibling)")

    p = sub.add_parser("spawn", help="create an isolated worker clone")
    p.add_argument("task", nargs="?", help="short description of the worker task")
    p.add_argument("--task", dest="task_flag", help="task description (alternate form)")
    p.add_argument("--workspace", help="workspace path (normally auto-discovered)")
    p.add_argument("--base", default="HEAD", help="base ref or commit (default: HEAD)")
    p.add_argument(
        "--strong",
        action="store_true",
        help="disable Git's local object sharing for physical object independence",
    )
    p.add_argument("--request-id", help="stable id for idempotent repeated spawn requests")
    p.add_argument("--wait-seconds", type=float, default=120.0)

    p = sub.add_parser("collect", help="preserve a worker result in the canonical repo")
    p.add_argument("id", type=int, help="worker id")
    p.add_argument("--workspace", help="workspace path (normally auto-discovered)")
    p.add_argument("--allow-rewrite", action="store_true")

    p = sub.add_parser("discard", help="remove a worker after collection or abandonment")
    p.add_argument("id", type=int, help="worker id")
    p.add_argument("--workspace", help="workspace path (normally auto-discovered)")
    p.add_argument("--abandon", action="store_true", help="discard uncollected work intentionally")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("recover", help="recover interrupted lifecycle operations")
    p.add_argument("--workspace", help="workspace path (normally auto-discovered)")

    p = sub.add_parser("status", help="show workspace and worker state")
    p.add_argument("--workspace", help="workspace path (normally auto-discovered)")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "init":
            canonical = validate_primary_repo(Path(args.canonical or "."))
            workspace = (
                Path(args.workspace).expanduser().resolve()
                if args.workspace
                else default_workspace(canonical)
            )
            result = init_workspace(canonical, workspace)
        elif args.command == "spawn":
            task = args.task_flag or args.task
            if not task:
                parser.error("spawn requires a task, e.g. `clonegrown spawn \"fix auth race\"`")
            result = spawn(
                resolve_workspace(args.workspace),
                args.base,
                task,
                args.strong,
                args.request_id,
                args.wait_seconds,
            )
        elif args.command == "collect":
            result = collect(
                resolve_workspace(args.workspace), args.id, args.allow_rewrite
            )
        elif args.command == "discard":
            result = discard(
                resolve_workspace(args.workspace), args.id, args.abandon, args.force
            )
        elif args.command == "recover":
            result = recover(resolve_workspace(args.workspace))
        else:
            result = status(resolve_workspace(args.workspace))

        print(json.dumps(public_result(result), indent=2, sort_keys=True))
        return 0
    except CWSError as exc:
        print(f"clonegrown: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
