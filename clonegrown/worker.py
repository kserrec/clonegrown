"""One worker on disk: its identity marker, authentication, result snapshot, allocation, and removal."""
from __future__ import annotations

import json
import os
import secrets
import shutil
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import (
    PROTOCOL_NAME, ClonegrownError, atomic_json, git, git_common_dir, git_dir, git_path, lexical_abs, load_json, object_format,
    repo_root,
)
from .repository import delete_branch
from .state import (
    SCHEMA, WorkerRecord, WorkerStatus, WorkspaceState, params_hash, request_path, staging_root, worker_marker_path,
    worker_record_path, worker_slot, workspace_lock,
)

# Git-directory entries whose presence means a merge/rebase/etc. is mid-flight.
OPERATION_GIT_PATHS = (
    "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG",
    "rebase-apply", "rebase-merge", "sequencer",
)


# --- identity ----------------------------------------------------------------

def write_worker_marker(repo: Path, worker: WorkerRecord) -> None:
    atomic_json(worker_marker_path(repo), {
        "workspace_id": worker.workspace_id,
        "worker_id": worker.id,
        "worker_token": worker.worker_token,
        "canonical_token": worker.canonical_token,
        "base_sha": worker.base_sha,
        "branch": worker.branch,
        "created": time.time(),
    })


def verify_worker(state: WorkspaceState, worker: WorkerRecord, require_exists: bool = True) -> Path:
    """Authenticate the on-disk worker against its record before touching it."""
    repo = worker.repo
    if not repo.exists():
        if require_exists:
            raise ClonegrownError("worker repository is missing")
        return repo
    for boundary, label in ((repo.parent, "worker slot"), (repo, "worker repository")):
        try:
            mode = os.lstat(boundary).st_mode
        except FileNotFoundError:
            raise ClonegrownError(f"{label} is missing")
        if stat.S_ISLNK(mode):
            raise ClonegrownError(f"{label} was replaced by a symlink")
        if not stat.S_ISDIR(mode):
            raise ClonegrownError(f"{label} is not a directory")
    if repo_root(repo) != repo.resolve():
        raise ClonegrownError("worker repository root changed")
    private, common = git_dir(repo), git_common_dir(repo)
    if not worker.is_worktree:
        if private != common:
            raise ClonegrownError("worker was replaced with a linked worktree")
    else:
        if private == common:
            raise ClonegrownError("worktree worker was replaced with an independent repository")
        if common != Path(str(state.canonical_git_dir)).resolve():
            raise ClonegrownError("worktree worker is not linked to the canonical repository")
        if private.parent != common / "worktrees":
            raise ClonegrownError("worktree worker admin directory is not where Git keeps it")
        if worker.worktree_admin is not None and lexical_abs(worker.worktree_admin) != private:
            raise ClonegrownError("worktree worker admin directory changed")
    marker = load_json(worker_marker_path(repo))
    expected = {
        "workspace_id": state.workspace_id,
        "worker_id": worker.id,
        "worker_token": worker.worker_token,
        "canonical_token": state.canonical_token,
        "base_sha": worker.base_sha,
        "branch": worker.branch,
    }
    for key, value in expected.items():
        if marker.get(key) != value:
            raise ClonegrownError(f"worker identity marker mismatch: {key}")
    if object_format(repo) != state.object_format:
        raise ClonegrownError("worker object format differs from canonical")
    return repo


# --- result snapshot ---------------------------------------------------------

@dataclass(frozen=True)
class Snapshot:
    """What a clean, collectable worker looked like at one instant."""
    head: str
    branch_ref: str

    def to_json(self) -> dict[str, Any]:
        return {"head": self.head, "branch_ref": self.branch_ref}


def operations_in_progress(repo: Path) -> list[str]:
    return [rel for rel in OPERATION_GIT_PATHS if git_path(repo, rel).exists()]


def snapshot_worker(state: WorkspaceState, worker: WorkerRecord, require_ancestry: bool = True) -> Snapshot:
    """Describe a clean, collectable worker; raise if it is not in that condition."""
    repo = verify_worker(state, worker)
    dirty = git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout
    if dirty.strip():
        raise ClonegrownError("worker has uncommitted or untracked changes")
    operations = operations_in_progress(repo)
    if operations:
        raise ClonegrownError("worker has an in-progress Git operation: " + ", ".join(operations))
    sym = git(repo, "symbolic-ref", "-q", "HEAD", check=False)
    branch_ref = f"refs/heads/{worker.branch}"
    if sym.returncode or sym.stdout.strip() != branch_ref:
        raise ClonegrownError("worker HEAD is detached or not on its assigned task branch")
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    if head != git(repo, "rev-parse", branch_ref).stdout.strip():
        raise ClonegrownError("worker HEAD and assigned branch disagree")
    if require_ancestry:
        anc = git(repo, "merge-base", "--is-ancestor", str(worker.base_sha), head, check=False)
        if anc.returncode != 0:
            raise ClonegrownError("worker result does not descend from its assigned base")
    return Snapshot(head=head, branch_ref=branch_ref)


# --- loading -----------------------------------------------------------------

def load_worker(ws: Path, worker_id: int) -> tuple[WorkspaceState, WorkerRecord, Path]:
    """Return the validated workspace state, the validated worker record, and the canonical path."""
    state = WorkspaceState.load(ws)
    canonical = state.verify_canonical()
    if not worker_record_path(ws, worker_id).exists():
        raise ClonegrownError(f"unknown worker: {worker_id}")
    worker = WorkerRecord.load(ws, worker_id)
    worker.validate(ws, state, worker_id)
    return state, worker, canonical


# --- allocation --------------------------------------------------------------

def allocate_spawn(ws: Path, base: str, task: str, strong: bool, request_id: str | None,
                   mode: str = "clone") -> tuple[WorkerRecord, bool]:
    """Reserve a worker ID, pin its base commit, and write the ``allocated`` record.

    Returns ``(worker, created)``. With a request ID that already maps to a
    live or finished worker, that worker's record is returned unchanged.
    """
    with workspace_lock(ws):
        state = WorkspaceState.load(ws)
        canonical = state.verify_canonical()
        digest = params_hash(base, task, strong, mode)
        if request_id:
            index = request_path(ws, request_id)
            if index.exists():
                entry = load_json(index)
                if entry.get("request_id") != request_id:
                    raise ClonegrownError("request index hash collision or corruption")
                if entry.get("params_hash") != digest:
                    raise ClonegrownError("request ID was reused with different base/task/isolation/mode parameters")
                existing = WorkerRecord.load(ws, int(entry["worker_id"]))
                if existing.status not in WorkerStatus.RETRYABLE:
                    return existing, False
                # A failed incomplete spawn may be retried under the same idempotency key.
        resolved = git(canonical, "rev-parse", "--verify", f"{base}^{{commit}}", check=False)
        if resolved.returncode:
            raise ClonegrownError(f"base does not resolve to a commit: {base}")
        base_sha = resolved.stdout.strip()
        worker_id = int(state.next_id)
        state.next_id = worker_id + 1
        state.save(ws)
        token = secrets.token_hex(16)
        git(canonical, "update-ref", state.base_ref(worker_id), base_sha, "0" * len(base_sha))
        worker = WorkerRecord(
            schema=SCHEMA,
            id=worker_id,
            workspace_id=state.workspace_id,
            canonical_token=state.canonical_token,
            worker_token=token,
            path=str(worker_slot(ws, worker_id) / str(state.repo_name)),
            stage_root=str(staging_root(ws, worker_id, token)),
            branch=state.worker_branch(worker_id, task),
            base=base,
            base_sha=base_sha,
            strong=bool(strong),
            mode=mode,
            task=task,
            request_id=request_id,
            params_hash=digest,
            created=time.time(),
        )
        worker.take_ownership(WorkerStatus.ALLOCATED)
        worker.save(ws)
        if request_id:
            atomic_json(request_path(ws, request_id), {
                "request_id": request_id,
                "params_hash": digest,
                "worker_id": worker_id,
                "created": time.time(),
            })
        return worker, True


# --- removing a worktree worker's footprint in canonical ---------------------

def _admin_belongs_to(admin: Path, worker: WorkerRecord) -> bool:
    """Does this admin directory identify as ``worker``?

    Git recycles admin names (``app``, ``app1``, ...) as soon as one is freed,
    so the path a record holds may later belong to a different worker. The
    marker written at provisioning is authoritative; before it exists, Git's
    own ``gitdir`` back-pointer must point into this worker.
    """
    marker = admin / f"{PROTOCOL_NAME}-worker.json"
    if marker.is_file():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
        except Exception:
            return False
        return data.get("worker_id") == worker.id and data.get("worker_token") == worker.worker_token
    try:
        target = lexical_abs((admin / "gitdir").read_text(encoding="utf-8").strip())
    except Exception:
        return False
    owned = {lexical_abs(worker.repo / ".git")}
    if worker.stage_root:
        owned.add(lexical_abs(Path(worker.stage_root) / worker.repo.name / ".git"))
    return target in owned


def remove_worktree_admin(canonical: Path, admin: Path, worker: WorkerRecord) -> bool:
    """Delete one worktree's admin directory so Git forgets it; True if it was ours (or already gone).

    Deliberately not ``git worktree prune``: that would also drop any of the
    user's own worktrees whose directories happen to be unreachable. And
    never by path alone: the directory must identify as this worker.
    """
    admin = lexical_abs(admin)
    if admin.parent != git_common_dir(canonical) / "worktrees":
        raise ClonegrownError("refusing to delete a path outside the worktrees directory")
    try:
        mode = os.lstat(admin).st_mode
    except FileNotFoundError:
        return True
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ClonegrownError("worktree admin path is not a directory")
    if not _admin_belongs_to(admin, worker):
        return False
    shutil.rmtree(admin, ignore_errors=True)
    return True


def forget_worktree(canonical: Path, worker: WorkerRecord) -> None:
    """After a worktree worker's directory is gone, remove its admin dir and task branch from canonical.

    Clears ``worktree_admin`` on the record once handled, so no later recovery
    can act on a path Git may since have given to another worker.
    """
    if not worker.is_worktree:
        return
    if worker.worktree_admin:
        if not remove_worktree_admin(canonical, Path(worker.worktree_admin), worker):
            worker.worktree_admin_left = "admin directory no longer identified as this worker; left in place"
        worker.worktree_admin = None
    delete_branch(canonical, str(worker.branch))
