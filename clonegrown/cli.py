"""The installed ``clonegrown`` command.

Workspaces are discovered automatically from the canonical checkout, the
workspace, or any worker beneath it. Output is JSON with internal identity
and transaction fields removed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import __version__
from .core import ClonegrownError, validate_primary_repo
from .lifecycle import collect, discard, init_workspace, spawn
from .recovery import recover, status

# The JSON a caller sees is the record minus two kinds of field: secrets and
# transaction bookkeeping. What remains is the documented output contract
# (ARCHITECTURE.md, "Command output"); timestamps are rendered as ISO 8601.
_SECRET_KEYS = {"canonical_token", "worker_token", "params_hash"}
_BOOKKEEPING_KEYS = {
    "schema", "next_id", "canonical_git_dir",
    "owner_pid", "owner_start", "heartbeat", "stage_root",
    "worktree_admin", "worktree_admin_left", "pending_spawn_details",
    "candidate_sha", "candidate_ref", "collect_started", "collected_snapshot", "collection_race",
    "discard_intent", "discard_previous", "discard_started",
}
_TIMESTAMP_KEYS = {"created", "ready", "failed", "collected", "discarded", "collection_failed", "collection_recovered"}


def _iso(seconds: float) -> str:
    return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def public_result(value: Any) -> Any:
    """Reduce a record (or a list/dict of records) to the documented CLI output."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in _SECRET_KEYS or key in _BOOKKEEPING_KEYS:
                continue
            if key in _TIMESTAMP_KEYS and isinstance(item, (int, float)):
                out[key] = _iso(item)
            else:
                out[key] = public_result(item)
        return out
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
                    "work in it, preserve its committed result, then discard it. "
                    "Recover reconciles recorded interruption boundaries.",
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
                           help="clone with no object files shared with canonical")
    isolation.add_argument("--worktree", action="store_true",
                           help="linked worktree sharing canonical's Git internals (fastest, least isolated)")
    p.add_argument("--request-id", help="stable id that makes matching spawn retries return one allocation")
    p.add_argument("--wait-seconds", type=float, default=120.0,
                   help="how long to wait for an in-flight spawn with the same request id")

    p = sub.add_parser("collect", help="preserve a worker's clean committed tip under a canonical ref")
    p.add_argument("id", type=int, help="worker id")
    workspace_option(p)
    p.add_argument("--allow-rewrite", action="store_true",
                   help="accept a result that does not descend from the worker's base")

    p = sub.add_parser(
        "discard",
        help="delete a worker (alpha: ignored files and external writers are not protected)",
        description="Delete a worker. In this alpha, ignored files and external writers are not protected; "
                    "read the README safety boundary before cleanup.",
    )
    p.add_argument("id", type=int, help="worker id")
    workspace_option(p)
    p.add_argument("--abandon", action="store_true", help="discard all uncollected worker content intentionally")
    p.add_argument("--force", action="store_true", help="discard detected post-collection changes intentionally")

    p = sub.add_parser("recover", help="reconcile interrupted operations represented in durable state")
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
