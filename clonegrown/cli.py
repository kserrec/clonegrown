"""The installed ``clonegrown`` command.

Workspaces are discovered automatically from the canonical checkout, the
workspace, or any worker beneath it. Successful lifecycle subcommands write
JSON to stdout with internal identity and transaction fields removed. Help and
version output are text on stdout; argument and Clonegrown runtime errors are
text on stderr.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Callable, Sequence, TypeVar

from . import __version__
from .core import (
    ClonegrownError, operation_boundary, operation_checkpoint, validate_primary_repo,
)
from .lifecycle import claim, collect, discard, init_workspace, release, spawn
from .recovery import recover, status

# The JSON a caller sees is the record minus two kinds of field: secrets and
# transaction bookkeeping. What remains is the documented output contract
# (ARCHITECTURE.md, "Command output"); timestamps are rendered as ISO 8601.
_SECRET_KEYS = {"canonical_token", "worker_token", "params_hash"}
_BOOKKEEPING_KEYS = {
    "schema", "next_id", "canonical_git_dir",
    "owner_pid", "owner_start", "heartbeat", "stage_root",
    "worktree_admin", "branch_cleanup_sha", "pending_spawn_details",
    "clone_private_refs",
    "candidate_sha", "candidate_ref", "collect_started", "collected_snapshot", "collection_race",
    "discard_intent", "discard_previous", "discard_started", "quarantine_snapshot",
}
_TIMESTAMP_KEYS = {"created", "ready", "failed", "collected", "discarded", "collection_failed", "collection_recovered",
                   "lease_released"}
_T = TypeVar("_T")


def _iso(seconds: float) -> str:
    return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def public_result(value: Any) -> Any:
    """Reduce a record (or a list/dict of records) to documented successful CLI JSON."""
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


def _resolve_operation_input(operation: str, resolver: Callable[[], _T]) -> _T:
    """Give CLI-only path/workspace discovery the same safety context as its operation."""
    @operation_boundary(operation)
    def resolve() -> _T:
        operation_checkpoint(
            stage="input and workspace resolution",
            durable_state=f"no durable mutation from this {operation} attempt has begun",
            work_preservation="believed preserved — only paths and repository identity are being inspected",
            recovery=f"not required; correct the input or Git setup and retry {operation}",
        )
        return resolver()

    return resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clonegrown",
        description="Per-task Git working directories for coding agents. Collection preserves a commit "
                    "under a canonical ref; integration into a user branch is separate. Published workers "
                    "hold a cooperative lease until release. Recover reconciles represented durable checkpoints.",
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
                           help="clone with physically separate object files at spawn (not an OS sandbox)")
    isolation.add_argument("--worktree", action="store_true",
                           help="linked worktree sharing canonical refs, config, stash, hooks, and objects")
    p.add_argument(
        "--request-id",
        help="stable id for matching retries; abandoned or spawn_failed outcomes may allocate anew",
    )
    p.add_argument("--wait-seconds", type=float, default=120.0,
                   help="how long to wait for an in-flight spawn with the same request id")

    p = sub.add_parser(
        "collect",
        help="preserve a clean committed tip under a canonical ref; do not update a user branch",
        description="Preserve a worker's clean committed tip under a canonical ref. Collection does not "
                    "merge, rebase, cherry-pick, or update a user branch; a collected worker is one-shot.",
    )
    p.add_argument("id", type=int, help="worker id")
    workspace_option(p)
    p.add_argument("--allow-rewrite", action="store_true",
                   help="accept a result that does not descend from the worker's base")

    p = sub.add_parser(
        "release",
        help="record that every writer has stopped and release the lease for discard",
        description="Release the cooperative work lease only after every process that can write to the "
                    "worker has stopped. Clonegrown records this assertion but cannot verify it.",
    )
    p.add_argument("id", type=int, help="worker id")
    workspace_option(p)

    p = sub.add_parser("claim", help="take the lease on a released worker that is still ready")
    p.add_argument("id", type=int, help="worker id")
    workspace_option(p)

    p = sub.add_parser(
        "discard",
        help="delete an authorized worker through authenticated quarantine",
        description="Delete a published worker whose lease has been released. A failed unpublished spawn has "
                    "no releasable lease but still needs --abandon. A collected worker needs --force for "
                    "changes after collection, --discard-ignored for Git-ignored paths, and "
                    "--discard-private-refs for changed clone-private refs; another uncollected worker also "
                    "needs --abandon. The lease is cooperative, not enforced; read the README safety boundary "
                    "before cleanup.",
    )
    p.add_argument("id", type=int, help="worker id")
    workspace_option(p)
    p.add_argument("--abandon", action="store_true",
                   help="discard an uncollected worker and all of its content intentionally")
    p.add_argument("--force", action="store_true", help="discard detected post-collection changes intentionally")
    p.add_argument("--discard-ignored", action="store_true",
                   help="discard a collected worker's Git-ignored paths intentionally")
    p.add_argument("--discard-private-refs", action="store_true",
                   help="discard a collected clone's changed private refs intentionally")

    p = sub.add_parser(
        "recover",
        help="reconcile represented checkpoints; may finish recorded deletion but never infer lease release",
        description="Reconcile lifecycle checkpoints represented in durable state. Recovery preserves a "
                    "diverged interrupted-spawn worker, may finish an already-recorded quarantine deletion, "
                    "and never infers lease release from a dead process.",
    )
    workspace_option(p)

    p = sub.add_parser(
        "status",
        help="audit documented invariants without repairing worker state or Git content",
        description="Audit Clonegrown's documented workspace and worker invariants without repairing records, "
                    "refs, worker content, or Git indexes. Acquiring the workspace lock can recreate its "
                    "missing control file. This is not a general filesystem-integrity or security scan.",
    )
    workspace_option(p)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            def init_inputs() -> tuple[Path, Path]:
                canonical = validate_primary_repo(Path(args.canonical or "."))
                workspace = (Path(args.workspace).expanduser().resolve()
                             if args.workspace else default_workspace(canonical))
                return canonical, workspace

            canonical, workspace = _resolve_operation_input("init", init_inputs)
            result = init_workspace(canonical, workspace)
        elif args.command == "spawn":
            task = args.task_flag or args.task
            if not task:
                parser.error("spawn requires a task, e.g. `clonegrown spawn \"fix auth race\"`")
            workspace = _resolve_operation_input("spawn", lambda: resolve_workspace(args.workspace))
            result = spawn(workspace, args.base, task,
                           args.strong, args.request_id, args.wait_seconds,
                           mode="worktree" if args.worktree else "clone")
        elif args.command == "collect":
            workspace = _resolve_operation_input("collect", lambda: resolve_workspace(args.workspace))
            result = collect(workspace, args.id, args.allow_rewrite)
        elif args.command == "release":
            result = release(resolve_workspace(args.workspace), args.id)
        elif args.command == "claim":
            result = claim(resolve_workspace(args.workspace), args.id)
        elif args.command == "discard":
            workspace = _resolve_operation_input("discard", lambda: resolve_workspace(args.workspace))
            result = discard(workspace, args.id, args.abandon, args.force,
                             args.discard_ignored, args.discard_private_refs)
        elif args.command == "recover":
            workspace = _resolve_operation_input("recover", lambda: resolve_workspace(args.workspace))
            result = recover(workspace)
        else:
            result = status(resolve_workspace(args.workspace))
        print(json.dumps(public_result(result), indent=2, sort_keys=True))
        return 0
    except ClonegrownError as exc:
        print(f"clonegrown: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
