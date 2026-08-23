"""Worker identity: markers, authentication, result snapshots, and allocation."""
from __future__ import annotations

import os
import secrets
import stat
import time
from pathlib import Path
from typing import Any

from .core import CWSError, atomic_json, git, git_common_dir, git_dir, git_path, load_json, object_format, repo_root
from .state import (
    SCHEMA, TERMINAL_SPAWN_FAILURE, base_ref, final_worker_root, owner_fields, params_hash, read_state, request_path, staging_root, validate_worker_meta,
    verify_canonical, worker_branch, worker_marker_path, worker_meta_path, workspace_lock, write_state,
)

# Git-directory entries whose presence means a merge/rebase/etc. is mid-flight.
OPERATION_GIT_PATHS = (
    "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG",
    "rebase-apply", "rebase-merge", "sequencer",
)


def write_worker_marker(repo: Path, meta: dict[str, Any]) -> None:
    atomic_json(worker_marker_path(repo), {
        "workspace_id": meta["workspace_id"],
        "worker_id": meta["id"],
        "worker_token": meta["worker_token"],
        "canonical_token": meta["canonical_token"],
        "base_sha": meta["base_sha"],
        "branch": meta["branch"],
        "created": time.time(),
    })


def verify_worker(state: dict[str, Any], meta: dict[str, Any], require_exists: bool = True) -> Path:
    """Authenticate the on-disk worker against its metadata before touching it."""
    repo = Path(meta["path"])
    if not repo.exists():
        if require_exists:
            raise CWSError("worker repository is missing")
        return repo
    for boundary, label in ((repo.parent, "worker slot"), (repo, "worker repository")):
        try:
            mode = os.lstat(boundary).st_mode
        except FileNotFoundError:
            raise CWSError(f"{label} is missing")
        if stat.S_ISLNK(mode):
            raise CWSError(f"{label} was replaced by a symlink")
        if not stat.S_ISDIR(mode):
            raise CWSError(f"{label} is not a directory")
    if repo_root(repo) != repo.resolve():
        raise CWSError("worker repository root changed")
    if git_dir(repo) != git_common_dir(repo):
        raise CWSError("worker was replaced with a linked worktree")
    marker = load_json(worker_marker_path(repo))
    checks = {
        "workspace_id": state["workspace_id"],
        "worker_id": meta["id"],
        "worker_token": meta["worker_token"],
        "canonical_token": state["canonical_token"],
        "base_sha": meta["base_sha"],
        "branch": meta["branch"],
    }
    for key, expected in checks.items():
        if marker.get(key) != expected:
            raise CWSError(f"worker identity marker mismatch: {key}")
    if object_format(repo) != state["object_format"]:
        raise CWSError("worker object format differs from canonical")
    return repo


def op_in_progress(repo: Path) -> list[str]:
    return [rel for rel in OPERATION_GIT_PATHS if git_path(repo, rel).exists()]


def worker_snapshot(state: dict[str, Any], meta: dict[str, Any], require_ancestry: bool = True) -> dict[str, Any]:
    """Describe a clean, collectable worker; raise if it is not in that condition."""
    repo = verify_worker(state, meta)
    dirty = git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout
    if dirty.strip():
        raise CWSError("worker has uncommitted or untracked changes")
    operations = op_in_progress(repo)
    if operations:
        raise CWSError("worker has an in-progress Git operation: " + ", ".join(operations))
    sym = git(repo, "symbolic-ref", "-q", "HEAD", check=False)
    expected_ref = f"refs/heads/{meta['branch']}"
    if sym.returncode or sym.stdout.strip() != expected_ref:
        raise CWSError("worker HEAD is detached or not on its assigned task branch")
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    if head != git(repo, "rev-parse", expected_ref).stdout.strip():
        raise CWSError("worker HEAD and assigned branch disagree")
    if require_ancestry:
        anc = git(repo, "merge-base", "--is-ancestor", meta["base_sha"], head, check=False)
        if anc.returncode != 0:
            raise CWSError("worker result does not descend from its assigned base")
    return {"head": head, "branch_ref": expected_ref, "status": dirty, "operations": operations}


def load_worker_state(ws: Path, worker_id: int) -> tuple[dict[str, Any], dict[str, Any], Path]:
    """Return validated (workspace state, worker metadata, canonical path)."""
    state = read_state(ws)
    canonical = verify_canonical(state)
    mp = worker_meta_path(ws, worker_id)
    if not mp.exists():
        raise CWSError(f"unknown worker: {worker_id}")
    meta = load_json(mp)
    validate_worker_meta(ws, state, worker_id, meta)
    return state, meta, canonical


def allocate_spawn(ws: Path, base: str, task: str, strong: bool,
                   request_id: str | None) -> tuple[dict[str, Any], bool]:
    """Reserve a worker ID, pin its base commit, and record ``allocated`` metadata.

    Returns ``(meta, created)``. With a request ID that already maps to a
    live or finished worker, the existing metadata is returned unchanged.
    """
    with workspace_lock(ws):
        state = read_state(ws)
        canonical = verify_canonical(state)
        ph = params_hash(base, task, strong)
        if request_id:
            rp = request_path(ws, request_id)
            if rp.exists():
                req = load_json(rp)
                if req.get("request_id") != request_id:
                    raise CWSError("request index hash collision or corruption")
                if req.get("params_hash") != ph:
                    raise CWSError("request ID was reused with different base/task/isolation parameters")
                old = load_json(worker_meta_path(ws, int(req["worker_id"])))
                if old.get("status") not in TERMINAL_SPAWN_FAILURE:
                    return old, False
                # A failed incomplete spawn may be retried under the same idempotency key.
        resolved = git(canonical, "rev-parse", "--verify", f"{base}^{{commit}}", check=False)
        if resolved.returncode:
            raise CWSError(f"base does not resolve to a commit: {base}")
        base_sha = resolved.stdout.strip()
        worker_id = int(state["next_id"])
        state["next_id"] = worker_id + 1
        write_state(ws, state)
        token = secrets.token_hex(16)
        git(canonical, "update-ref", base_ref(state, worker_id), base_sha, "0" * len(base_sha))
        meta: dict[str, Any] = {
            "schema": SCHEMA,
            "id": worker_id,
            "workspace_id": state["workspace_id"],
            "canonical_token": state["canonical_token"],
            "worker_token": token,
            "status": "allocated",
            "path": str(final_worker_root(ws, worker_id) / state["repo_name"]),
            "stage_root": str(staging_root(ws, worker_id, token)),
            "branch": worker_branch(state, worker_id, task),
            "base": base,
            "base_sha": base_sha,
            "strong": bool(strong),
            "task": task,
            "request_id": request_id,
            "params_hash": ph,
            "created": time.time(),
            **owner_fields(),
        }
        atomic_json(worker_meta_path(ws, worker_id), meta)
        if request_id:
            atomic_json(request_path(ws, request_id), {
                "request_id": request_id,
                "params_hash": ph,
                "worker_id": worker_id,
                "created": time.time(),
            })
        return meta, True
