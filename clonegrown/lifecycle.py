"""The four lifecycle transactions: init, spawn, collect, discard.

Each transaction records its progress in durable metadata before every
irreversible step, so a crash at any point leaves a state that ``recover``
can finish or roll back. ``failpoint`` names mark those crash windows.
"""
from __future__ import annotations

import contextlib
import os
import secrets
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from .core import GIT_BIN, CWSError, atomic_json, failpoint, file_lock, git, git_common_dir, inside, load_json, object_format, run, validate_primary_repo
from .recovery import recover
from .repository import (
    WORKTREE_SHARING_WARNING, add_worktree, checkout_without_hooks, copy_auxiliary_refs, copy_info_files,
    copy_local_config, copy_remote_config, copy_sparse_policy, delete_branch, detach_alternates_if_needed,
    private_hook_warnings, remove_worktree_admin, repair_worktree,
)
from .state import (
    ACTIVE_COLLECT, ACTIVE_DISCARD, ACTIVE_SPAWN, SCHEMA, TERMINAL_SPAWN_FAILURE, WORKER_MODES, base_ref,
    canonical_marker_path, clear_owner, final_worker_root, immutable_result_ref, owner_fields,
    process_alive, read_state, summary_ref, validate_state, verify_canonical, worker_lock_path,
    worker_meta_path, worker_mode, workspace_lock, write_state, ws_paths,
)
from .worker import allocate_spawn, load_worker_state, verify_worker, worker_snapshot, write_worker_marker

_SETTLED = {"ready", "collected", "discarded", "abandoned"}


def _canonical_marker(workspace_id: str, token: str, canonical: Path) -> dict[str, Any]:
    return {"workspace_id": workspace_id, "token": token, "canonical": str(canonical), "created": time.time()}


# --- init --------------------------------------------------------------------

def init_workspace(canonical_path: Path, ws_path: Path) -> dict[str, Any]:
    """Create (or finish creating) a workspace bound to one canonical checkout. Idempotent."""
    canonical = validate_primary_repo(canonical_path)
    ws = ws_path.resolve()
    if ws == canonical or inside(ws, canonical):
        raise CWSError("workspace cannot be the canonical repository or live inside its working tree")
    paths = ws_paths(ws)
    for key in ("workers", "requests", "locks", "staging"):
        paths[key].mkdir(parents=True, exist_ok=True)
    with workspace_lock(ws):
        if paths["state"].exists():
            state = load_json(paths["state"])
            validate_state(ws, state, require_ready=False)
            if Path(state.get("canonical", "")).resolve() != canonical:
                raise CWSError("workspace is already initialized for a different canonical path")
            if state.get("schema") != SCHEMA:
                raise CWSError("unsupported workspace metadata schema")
            if state.get("status") == "initializing":
                # Finish either crash window: after the state write or after the marker write.
                marker_path = canonical_marker_path(canonical, state["workspace_id"])
                if marker_path.exists():
                    if load_json(marker_path).get("token") != state.get("canonical_token"):
                        raise CWSError("initializing workspace has a conflicting canonical marker")
                else:
                    atomic_json(marker_path, _canonical_marker(state["workspace_id"], state["canonical_token"], canonical))
                state["status"] = "ready"
                write_state(ws, state)
            verify_canonical(state)
            return state

        workspace_id = uuid.uuid4().hex[:16]
        token = secrets.token_hex(24)
        state = {
            "schema": SCHEMA,
            "status": "initializing",
            "workspace_id": workspace_id,
            "canonical_token": token,
            "workspace": str(ws),
            "canonical": str(canonical),
            "canonical_git_dir": str(git_common_dir(canonical)),
            "object_format": object_format(canonical),
            "repo_name": canonical.name,
            "next_id": 1,
            "created": time.time(),
        }
        # If canonical already lives in a numeric top-level slot of this workspace, reserve it.
        if inside(canonical, ws):
            rel = canonical.relative_to(ws)
            if rel.parts and rel.parts[0].isdigit():
                state["next_id"] = max(state["next_id"], int(rel.parts[0]) + 1)
                state["canonical_slot"] = int(rel.parts[0])
        write_state(ws, state)
        failpoint("init.after_state")
        atomic_json(canonical_marker_path(canonical, workspace_id), _canonical_marker(workspace_id, token, canonical))
        failpoint("init.after_marker")
        state["status"] = "ready"
        write_state(ws, state)
        return state


# --- spawn -------------------------------------------------------------------

def _wait_for_existing(ws: Path, worker_id: int, timeout_seconds: float) -> dict[str, Any]:
    """Wait for another process's spawn of the same request ID to settle."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        meta = load_json(worker_meta_path(ws, worker_id))
        status = meta.get("status")
        if status in _SETTLED:
            return meta
        if status in TERMINAL_SPAWN_FAILURE or status == "broken":
            raise CWSError(f"existing request failed in worker {worker_id}: {meta.get('error', status)}")
        if time.monotonic() >= deadline:
            raise CWSError(f"timed out waiting for existing request worker {worker_id}; run recover")
        if not process_alive(meta.get("owner_pid"), meta.get("owner_start")):
            recover(ws)
        time.sleep(0.05)


def _advance_spawn(ws: Path, worker_id: int, status: str,
                   worktree_admin: Path | None = None) -> tuple[dict[str, Any], dict[str, Any], Path]:
    """Record the next spawn stage and re-verify canonical under the workspace lock."""
    with workspace_lock(ws):
        current = load_json(worker_meta_path(ws, worker_id))
        current.update({"status": status, **owner_fields()})
        if worktree_admin is not None:
            current["worktree_admin"] = str(worktree_admin)
        atomic_json(worker_meta_path(ws, worker_id), current)
        state = read_state(ws)
        return current, state, verify_canonical(state)


def _provision_worktree(canonical: Path, stage_repo: Path, meta: dict[str, Any]) -> dict[str, Any]:
    """Check out the base in a staged worktree; everything else is shared with canonical."""
    sparse = copy_sparse_policy(canonical, stage_repo)
    checkout_without_hooks(stage_repo, meta["branch"], meta["base_sha"])
    write_worker_marker(stage_repo, meta)
    if git(stage_repo, "rev-parse", "HEAD").stdout.strip() != meta["base_sha"]:
        raise CWSError("worker checkout differs from immutable requested base")
    return {
        "source_remote": None,
        "alternates_detached": False,
        "copied_local_config": [],
        "copied_sparse_checkout": sparse,
        "copied_auxiliary_refs": {},
        "compatibility_warnings": [WORKTREE_SHARING_WARNING],
    }


def _provision_clone(canonical: Path, stage_repo: Path, meta: dict[str, Any], strong: bool) -> dict[str, Any]:
    """Configure the staged clone and check out the base; return the spawn details."""
    detached, warnings = detach_alternates_if_needed(stage_repo, strong)
    source_remote = copy_remote_config(canonical, stage_repo)
    copied_config, cfg_warnings = copy_local_config(canonical, stage_repo)
    auxiliary_refs = copy_auxiliary_refs(canonical, stage_repo)
    copy_info_files(canonical, stage_repo)
    sparse = copy_sparse_policy(canonical, stage_repo)
    warnings += cfg_warnings + private_hook_warnings(canonical)
    checkout_without_hooks(stage_repo, meta["branch"], meta["base_sha"])
    write_worker_marker(stage_repo, meta)
    if git(stage_repo, "rev-parse", "HEAD").stdout.strip() != meta["base_sha"]:
        raise CWSError("worker checkout differs from immutable requested base")
    git(stage_repo, "fsck", "--connectivity-only")
    return {
        "source_remote": source_remote,
        "alternates_detached": detached,
        "copied_local_config": copied_config,
        "copied_sparse_checkout": sparse,
        "copied_auxiliary_refs": auxiliary_refs,
        "compatibility_warnings": sorted(set(warnings)),
    }


def _record_spawn_failure(ws: Path, worker_id: int, exc: BaseException) -> None:
    with workspace_lock(ws):
        state = read_state(ws)
        current = load_json(worker_meta_path(ws, worker_id))
        published = final_worker_root(ws, worker_id).exists()
        if published or current.get("status") == "ready":
            # A published directory is never downgraded to a disposable failure.
            # Leave a recoverable transaction record; recover will authenticate it.
            current["status"] = "publishing" if current.get("status") != "ready" else "ready"
            current["interrupted_error"] = str(exc)[:1000]
        else:
            current.update({"status": "spawn_failed", "failed": time.time(), "error": str(exc)[:1000]})
        clear_owner(current)
        atomic_json(worker_meta_path(ws, worker_id), current)
        if not published:
            git(verify_canonical(state), "update-ref", "-d", base_ref(state, worker_id), check=False)


def spawn(ws_path: Path, base: str, task: str, strong: bool = True,
          request_id: str | None = None, wait_seconds: float = 120.0,
          mode: str = "clone") -> dict[str, Any]:
    """Create a worker at ``base`` and return its ``ready`` metadata.

    ``mode`` is ``"clone"`` (an independent repository; ``strong`` disables
    object sharing) or ``"worktree"`` (a linked worktree sharing canonical's
    Git internals). Stages: allocated -> cloning -> configuring -> publishing
    -> ready. The worker is built under ``.cws/staging`` and moved into its
    numbered slot with one atomic rename, so a visible worker directory is
    always complete.
    """
    if mode not in WORKER_MODES:
        raise CWSError(f"unknown worker mode: {mode!r}")
    if mode == "worktree" and strong:
        raise CWSError("a worktree worker shares canonical's objects; --strong does not apply")
    ws = ws_path.resolve()
    meta, created = allocate_spawn(ws, base, task, strong, request_id, mode)
    if not created:
        return _wait_for_existing(ws, int(meta["id"]), wait_seconds)
    worker_id = int(meta["id"])
    stage = Path(meta["stage_root"])
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise CWSError("worker operation lock unexpectedly unavailable")
        try:
            failpoint("spawn.after_allocated")
            meta, state, canonical = _advance_spawn(ws, worker_id, "cloning")
            shutil.rmtree(stage, ignore_errors=True)
            stage.mkdir(parents=True, exist_ok=False)
            stage_repo = stage / state["repo_name"]
            admin: Path | None = None
            if mode == "worktree":
                admin = add_worktree(canonical, stage_repo, meta["base_sha"])
            else:
                cmd: list[str | Path] = [GIT_BIN, "clone", "--no-checkout"]
                if strong:
                    cmd.append("--no-hardlinks")
                run([*cmd, canonical, stage_repo], timeout=None)
            failpoint("spawn.after_clone")
            git(stage_repo, "cat-file", "-e", f"{meta['base_sha']}^{{commit}}")

            meta, state, canonical = _advance_spawn(ws, worker_id, "configuring", worktree_admin=admin)
            if mode == "worktree":
                spawn_details = _provision_worktree(canonical, stage_repo, meta)
            else:
                spawn_details = _provision_clone(canonical, stage_repo, meta, strong)
            failpoint("spawn.after_checkout")

            with workspace_lock(ws):
                state = read_state(ws)
                verify_canonical(state)
                current = load_json(worker_meta_path(ws, worker_id))
                if current.get("worker_token") != meta["worker_token"] or current.get("status") not in ACTIVE_SPAWN:
                    raise CWSError("spawn metadata ownership changed")
                current.update({"status": "publishing", "pending_spawn_details": spawn_details, **owner_fields()})
                atomic_json(worker_meta_path(ws, worker_id), current)
                final = final_worker_root(ws, worker_id)
                if final.exists():
                    raise CWSError("worker final path already exists")
                os.replace(stage, final)
                failpoint("spawn.after_publish")
                if mode == "worktree":
                    # The rename moved the worktree; Git's pointer back to it is now stale.
                    repair_worktree(canonical, final / state["repo_name"])
                failpoint("spawn.after_repair")
                current.update({"status": "ready", "ready": time.time(), **spawn_details})
                current.pop("pending_spawn_details", None)
                clear_owner(current)
                atomic_json(worker_meta_path(ws, worker_id), current)
                git(verify_canonical(state), "update-ref", "-d", base_ref(state, worker_id))
                failpoint("spawn.after_ready")
                return current
        except BaseException as exc:
            # SIGKILL / os._exit bypass this block; recover() handles those.
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            with contextlib.suppress(Exception):
                _record_spawn_failure(ws, worker_id, exc)
            if not final_worker_root(ws, worker_id).exists():
                shutil.rmtree(stage, ignore_errors=True)
                with contextlib.suppress(Exception):
                    _forget_worktree(ws, worker_id)
            raise


def forget_worktree(canonical: Path, meta: dict[str, Any]) -> None:
    """Remove a worktree worker's admin directory and task branch from canonical.

    Mutates ``meta``: the admin path is cleared once handled so that a later
    recovery can never act on it again after Git has recycled the name.
    """
    if worker_mode(meta) != "worktree":
        return
    admin = meta.get("worktree_admin")
    if admin:
        if not remove_worktree_admin(canonical, Path(admin), meta):
            meta["worktree_admin_left"] = "admin directory no longer identified as this worker; left in place"
        meta["worktree_admin"] = None
    delete_branch(canonical, meta["branch"])


def _forget_worktree(ws: Path, worker_id: int) -> None:
    state = read_state(ws)
    canonical = verify_canonical(state)
    meta = load_json(worker_meta_path(ws, worker_id))
    if worker_mode(meta) != "worktree":
        return
    forget_worktree(canonical, meta)
    atomic_json(worker_meta_path(ws, worker_id), meta)


# --- collect -----------------------------------------------------------------

def _rollback_collect_error(ws: Path, worker_id: int, worker_token: str, error: BaseException) -> None:
    """Return a live worker to ``ready`` after an ordinary collection failure.

    Any fetched immutable result ref is deliberately retained: keeping an
    extra candidate is safer than deleting evidence. Crash failpoints use
    ``os._exit`` and are therefore handled by recover().
    """
    with workspace_lock(ws):
        _, current, _ = load_worker_state(ws, worker_id)
        if current.get("status") != "collecting" or current.get("worker_token") != worker_token:
            return
        current.update({
            "status": "ready",
            "collection_error": str(error)[:1000],
            "collection_failed": time.time(),
        })
        clear_owner(current, "candidate_sha", "candidate_ref")
        atomic_json(worker_meta_path(ws, worker_id), current)


def collect(ws_path: Path, worker_id: int, allow_rewrite: bool = False) -> dict[str, Any]:
    """Fetch the worker's committed HEAD into canonical under an immutable ref.

    The worker is snapshotted before and after the fetch; if it changed in
    between, the fetched candidate is kept but not accepted. Re-collecting an
    already collected, unchanged worker is a no-op that refreshes the summary ref.
    """
    ws = ws_path.resolve()
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise CWSError("worker is busy")
        with workspace_lock(ws):
            state, meta, canonical = load_worker_state(ws, worker_id)
            if meta["status"] == "collected":
                snap = worker_snapshot(state, meta, require_ancestry=not allow_rewrite)
                if snap["head"] != meta.get("result_sha"):
                    raise CWSError("worker changed after collection; refusing to hide newer work")
                ref = meta["result_ref"]
                got = git(canonical, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
                if got.returncode or got.stdout.strip() != meta["result_sha"]:
                    raise CWSError("collected result ref is missing or changed")
                git(canonical, "update-ref", summary_ref(state, worker_id), meta["result_sha"])
                return meta
            if meta["status"] != "ready":
                raise CWSError(f"worker is not collectable from state {meta['status']}")
        first = worker_snapshot(state, meta, require_ancestry=not allow_rewrite)
        candidate = first["head"]
        result_ref = immutable_result_ref(state, worker_id, candidate)
        with workspace_lock(ws):
            state, current, canonical = load_worker_state(ws, worker_id)
            if current["status"] != "ready" or current["worker_token"] != meta["worker_token"]:
                raise CWSError("worker state changed before collection")
            current.update({
                "status": "collecting", "candidate_sha": candidate, "candidate_ref": result_ref,
                "allow_rewrite": bool(allow_rewrite), "collect_started": time.time(), **owner_fields(),
            })
            atomic_json(worker_meta_path(ws, worker_id), current)
            meta = current
        try:
            failpoint("collect.after_mark")
            failpoint("collect.before_fetch")
            git(canonical, "fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
                str(Path(meta["path"])), f"+{candidate}:{result_ref}")
            failpoint("collect.after_fetch")
            got = git(canonical, "rev-parse", "--verify", f"{result_ref}^{{commit}}").stdout.strip()
            if got != candidate:
                raise CWSError("preserved result differs from candidate commit")
            git(canonical, "cat-file", "-e", f"{candidate}^{{commit}}")
            failpoint("collect.after_verify")
            second = worker_snapshot(state, meta, require_ancestry=not allow_rewrite)
            if second != first:
                with workspace_lock(ws):
                    state, current, _ = load_worker_state(ws, worker_id)
                    current.update({"status": "ready", "collection_race": {
                        "candidate": candidate, "observed": second["head"], "time": time.time()}})
                    clear_owner(current, "candidate_sha", "candidate_ref")
                    atomic_json(worker_meta_path(ws, worker_id), current)
                raise CWSError("worker changed during collection; candidate preserved but not accepted")
            failpoint("collect.after_worker_recheck")
            with workspace_lock(ws):
                state, current, canonical = load_worker_state(ws, worker_id)
                if current.get("status") != "collecting" or current.get("candidate_sha") != candidate:
                    raise CWSError("collection metadata changed")
                git(canonical, "update-ref", summary_ref(state, worker_id), candidate)
                failpoint("collect.after_summary")
                current.update({
                    "status": "collected", "result_sha": candidate, "result_ref": result_ref,
                    "collected": time.time(), "collected_snapshot": second,
                })
                clear_owner(current, "candidate_sha", "candidate_ref")
                atomic_json(worker_meta_path(ws, worker_id), current)
                failpoint("collect.after_metadata")
                return current
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            with contextlib.suppress(Exception):
                _rollback_collect_error(ws, worker_id, meta["worker_token"], exc)
            raise


# --- discard -----------------------------------------------------------------

def discard(ws_path: Path, worker_id: int, abandon: bool = False, force: bool = False) -> dict[str, Any]:
    """Delete a worker directory. Uncollected work needs ``abandon``; drift after collection needs ``force``."""
    ws = ws_path.resolve()
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise CWSError("worker is busy")
        with workspace_lock(ws):
            state, meta, canonical = load_worker_state(ws, worker_id)
            if meta["status"] in {"discarded", "abandoned"}:
                return meta
            if meta["status"] in ACTIVE_SPAWN | ACTIVE_COLLECT | ACTIVE_DISCARD:
                raise CWSError(f"worker has an active operation: {meta['status']}")
            # Every destructive path authenticates the published worker first, so that
            # --abandon cannot turn metadata tampering into an accepted deletion.
            if final_worker_root(ws, worker_id).exists():
                verify_worker(state, meta)
            if meta["status"] == "collected":
                ref = meta.get("result_ref")
                got = git(canonical, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
                if got.returncode or got.stdout.strip() != meta.get("result_sha"):
                    raise CWSError("refusing deletion because collected result is not preserved")
                if Path(meta["path"]).exists() and not force:
                    snap = worker_snapshot(state, meta, require_ancestry=not meta.get("allow_rewrite", False))
                    if snap["head"] != meta["result_sha"]:
                        raise CWSError("worker changed after collection; use --force only to knowingly discard it")
            elif not abandon:
                raise CWSError("refusing to delete an uncollected worker; use explicit --abandon")
            meta.update({
                "status": "discarding", "discard_intent": "abandoned" if abandon else "discarded",
                "discard_previous": meta["status"], "discard_started": time.time(), **owner_fields(),
            })
            atomic_json(worker_meta_path(ws, worker_id), meta)
        failpoint("discard.after_mark")
        failpoint("discard.before_delete")
        shutil.rmtree(final_worker_root(ws, worker_id), ignore_errors=True)
        stage = Path(meta.get("stage_root", ""))
        if str(stage) and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        failpoint("discard.after_delete")
        with workspace_lock(ws):
            state, current, canonical = load_worker_state(ws, worker_id)
            forget_worktree(canonical, current)
            current["status"] = current.get("discard_intent", "discarded")
            current["discarded"] = time.time()
            clear_owner(current)
            atomic_json(worker_meta_path(ws, worker_id), current)
            failpoint("discard.after_metadata")
            return current
