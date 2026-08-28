"""The four lifecycle transactions: init, spawn, collect, discard.

Transactions persist named recovery checkpoints around their major stages.
Those records support the recovery paths represented in durable state; they do
not yet cover every destructive substep. ``failpoint`` names mark the tested
checkpoint windows.
"""
from __future__ import annotations

import contextlib
import os
import secrets
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from .core import (
    GIT_BIN, ClonegrownError, atomic_json, failpoint, file_lock, git, git_common_dir, inside, load_json, object_format,
    process_alive, run, validate_primary_repo,
)
from .recovery import recover
from .repository import (
    WORKTREE_SHARING_WARNING, add_worktree, checkout_without_hooks, copy_auxiliary_refs, copy_info_files,
    copy_local_config, copy_remote_config, copy_sparse_patterns, copy_sparse_policy, detach_alternates_if_needed,
    private_hook_warnings, ref_points_at, repair_worktree, sparse_checkout_enabled,
)
from .state import (
    SCHEMA, WORKER_MODES, WorkerRecord, WorkerStatus, WorkspaceState, canonical_marker_path, worker_lock_path,
    worker_slot, workspace_lock, ws_paths,
)
from .worker import (
    allocate_spawn, forget_worktree, load_worker, snapshot_worker, verify_worker, write_worker_marker,
)


@contextlib.contextmanager
def _rolling_back(on_error: Callable[[BaseException], None]) -> Iterator[None]:
    """Run ``on_error`` (best effort) if the body fails, then re-raise.

    SIGKILL and ``os._exit`` bypass this entirely; recover() handles the
    interruption states represented by the worker record.
    Interrupts are re-raised untouched so the record keeps its in-flight owner.
    """
    try:
        yield
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        with contextlib.suppress(Exception):
            on_error(exc)
        raise


def _canonical_marker(workspace_id: str, token: str, canonical: Path) -> dict[str, Any]:
    return {"workspace_id": workspace_id, "token": token, "canonical": str(canonical), "created": time.time()}


# --- init --------------------------------------------------------------------

def init_workspace(canonical_path: Path, ws_path: Path) -> dict[str, Any]:
    """Create (or finish creating) a workspace bound to one canonical checkout. Idempotent."""
    canonical = validate_primary_repo(canonical_path)
    ws = ws_path.resolve()
    if ws == canonical or inside(ws, canonical):
        raise ClonegrownError("workspace cannot be the canonical repository or live inside its working tree")
    paths = ws_paths(ws)
    for key in ("workers", "requests", "locks", "staging"):
        paths[key].mkdir(parents=True, exist_ok=True)
    with workspace_lock(ws):
        if paths["state"].exists():
            state = WorkspaceState.from_json(load_json(paths["state"]))
            state.validate(ws, require_ready=False)
            if Path(str(state.canonical)).resolve() != canonical:
                raise ClonegrownError("workspace is already initialized for a different canonical path")
            if state.status == "initializing":
                # Finish either crash window: after the state write or after the marker write.
                marker_path = canonical_marker_path(canonical, str(state.workspace_id))
                if marker_path.exists():
                    if load_json(marker_path).get("token") != state.canonical_token:
                        raise ClonegrownError("initializing workspace has a conflicting canonical marker")
                else:
                    atomic_json(marker_path, _canonical_marker(str(state.workspace_id), str(state.canonical_token), canonical))
                state.status = "ready"
                state.save(ws)
            state.verify_canonical()
            return state.to_json()

        workspace_id = uuid.uuid4().hex[:16]
        token = secrets.token_hex(24)
        state = WorkspaceState(
            schema=SCHEMA,
            status="initializing",
            workspace_id=workspace_id,
            canonical_token=token,
            workspace=str(ws),
            canonical=str(canonical),
            canonical_git_dir=str(git_common_dir(canonical)),
            object_format=object_format(canonical),
            repo_name=canonical.name,
            next_id=1,
            created=time.time(),
        )
        # If canonical already lives in a numbered slot of this workspace, reserve that slot.
        if inside(canonical, ws):
            first = canonical.relative_to(ws).parts[:1]
            if first and first[0].isdigit():
                state.canonical_slot = int(first[0])
                state.next_id = max(state.next_id, state.canonical_slot + 1)
        state.save(ws)
        failpoint("init.after_state")
        atomic_json(canonical_marker_path(canonical, workspace_id), _canonical_marker(workspace_id, token, canonical))
        failpoint("init.after_marker")
        state.status = "ready"
        state.save(ws)
        return state.to_json()


# --- spawn -------------------------------------------------------------------

@dataclass(frozen=True)
class SpawnDetails:
    """What provisioning did to the worker; copied onto the record when it becomes ready."""
    source_remote: str | None
    alternates_detached: bool
    copied_local_config: list[str]
    copied_sparse_checkout: bool
    copied_auxiliary_refs: dict[str, int]
    compatibility_warnings: list[str]

    def apply(self, worker: WorkerRecord) -> None:
        for key, value in asdict(self).items():
            setattr(worker, key, value)


def _wait_for_existing(ws: Path, worker_id: int, timeout_seconds: float) -> dict[str, Any]:
    """Wait for another process's spawn of the same request ID to settle."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        worker = WorkerRecord.load(ws, worker_id)
        if worker.status in WorkerStatus.SETTLED:
            return worker.to_json()
        if worker.status in WorkerStatus.RETRYABLE or worker.status == WorkerStatus.BROKEN:
            raise ClonegrownError(f"existing request failed in worker {worker_id}: {worker.error or worker.status}")
        if time.monotonic() >= deadline:
            raise ClonegrownError(f"timed out waiting for existing request worker {worker_id}; run recover")
        if not process_alive(worker.owner_pid, worker.owner_start):
            recover(ws)
        time.sleep(0.05)


def _advance_spawn(ws: Path, worker_id: int, status: str) -> tuple[WorkerRecord, WorkspaceState, Path]:
    """Record the next spawn stage and re-verify canonical, under the workspace lock."""
    with workspace_lock(ws):
        worker = WorkerRecord.load(ws, worker_id)
        worker.take_ownership(status)
        worker.save(ws)
        state = WorkspaceState.load(ws)
        return worker, state, state.verify_canonical()


def _record_worktree_admin(ws: Path, worker_id: int, admin: Path) -> None:
    """Persist the admin directory immediately after ``git worktree add`` returns.

    A process can still die after Git creates the directory but before this
    function records it; that current alpha gap is documented publicly.
    """
    with workspace_lock(ws):
        worker = WorkerRecord.load(ws, worker_id)
        worker.worktree_admin = str(admin)
        worker.save(ws)


def _check_out_base(stage_repo: Path, worker: WorkerRecord) -> None:
    """Put the staged repository on its task branch at the pinned base and stamp its identity."""
    checkout_without_hooks(stage_repo, str(worker.branch), str(worker.base_sha))
    write_worker_marker(stage_repo, worker)
    if git(stage_repo, "rev-parse", "HEAD").stdout.strip() != worker.base_sha:
        raise ClonegrownError("worker checkout differs from immutable requested base")


def _provision_worktree(canonical: Path, stage_repo: Path, worker: WorkerRecord) -> SpawnDetails:
    """Check out the base in a staged worktree; everything else is shared with canonical."""
    sparse = sparse_checkout_enabled(canonical)  # the config is shared; only the pattern file is per-worktree
    if sparse:
        copy_sparse_patterns(canonical, stage_repo)
    _check_out_base(stage_repo, worker)
    return SpawnDetails(
        source_remote=None,
        alternates_detached=False,
        copied_local_config=[],
        copied_sparse_checkout=sparse,
        copied_auxiliary_refs={},
        compatibility_warnings=[WORKTREE_SHARING_WARNING],
    )


def _provision_clone(canonical: Path, stage_repo: Path, worker: WorkerRecord, strong: bool) -> SpawnDetails:
    """Make the staged clone a faithful private copy of canonical and check out the base."""
    detached, warnings = detach_alternates_if_needed(stage_repo, strong)
    source_remote = copy_remote_config(canonical, stage_repo)
    copied_config, config_warnings = copy_local_config(canonical, stage_repo)
    auxiliary_refs = copy_auxiliary_refs(canonical, stage_repo)
    copy_info_files(canonical, stage_repo)
    sparse = copy_sparse_policy(canonical, stage_repo)
    warnings += config_warnings + private_hook_warnings(canonical)
    _check_out_base(stage_repo, worker)
    git(stage_repo, "fsck", "--connectivity-only")
    return SpawnDetails(
        source_remote=source_remote,
        alternates_detached=detached,
        copied_local_config=copied_config,
        copied_sparse_checkout=sparse,
        copied_auxiliary_refs=auxiliary_refs,
        compatibility_warnings=sorted(set(warnings)),
    )


def _record_spawn_failure(ws: Path, worker_id: int, exc: BaseException) -> None:
    """Leave a record recover() can act on: failed if unpublished, interrupted-but-live if published."""
    with workspace_lock(ws):
        state = WorkspaceState.load(ws)
        worker = WorkerRecord.load(ws, worker_id)
        published = worker_slot(ws, worker_id).exists()
        if published or worker.status == WorkerStatus.READY:
            # The ordinary exception path keeps a published directory in a
            # recoverable publishing state instead of marking spawn_failed.
            if worker.status != WorkerStatus.READY:
                worker.status = WorkerStatus.PUBLISHING
            worker.interrupted_error = str(exc)[:1000]
        else:
            worker.status = WorkerStatus.SPAWN_FAILED
            worker.failed = time.time()
            worker.error = str(exc)[:1000]
        worker.release_ownership()
        worker.save(ws)
        if not published:
            git(state.verify_canonical(), "update-ref", "-d", state.base_ref(worker_id), check=False)


def _discard_unpublished_stage(ws: Path, worker_id: int, stage: Path) -> None:
    if worker_slot(ws, worker_id).exists():
        return
    shutil.rmtree(stage, ignore_errors=True)
    with contextlib.suppress(Exception):
        state = WorkspaceState.load(ws)
        canonical = state.verify_canonical()
        worker = WorkerRecord.load(ws, worker_id)
        forget_worktree(canonical, worker)
        worker.save(ws)


def spawn(ws_path: Path, base: str, task: str, strong: bool = True,
          request_id: str | None = None, wait_seconds: float = 120.0,
          mode: str = "clone") -> dict[str, Any]:
    """Create a worker at ``base`` and return its ``ready`` record.

    ``mode`` is ``"clone"`` (an independent repository; ``strong`` disables
    object sharing) or ``"worktree"`` (a linked worktree sharing canonical's
    Git internals). Stages: allocated -> cloning -> configuring -> publishing
    -> ready. The worker is built under ``.cws/staging`` and moved into its
    numbered slot with one atomic rename. Worktree repair and the final ready
    record occur after that rename while Clonegrown still holds its locks.
    """
    if mode not in WORKER_MODES:
        raise ClonegrownError(f"unknown worker mode: {mode!r}")
    if mode == "worktree" and strong:
        raise ClonegrownError("a worktree worker shares canonical's objects; --strong does not apply")
    ws = ws_path.resolve()
    worker, created = allocate_spawn(ws, base, task, strong, request_id, mode)
    if not created:
        return _wait_for_existing(ws, int(worker.id), wait_seconds)
    worker_id = int(worker.id)
    stage = Path(str(worker.stage_root))

    def roll_back(exc: BaseException) -> None:
        with contextlib.suppress(Exception):
            _record_spawn_failure(ws, worker_id, exc)
        _discard_unpublished_stage(ws, worker_id, stage)

    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise ClonegrownError("worker operation lock unexpectedly unavailable")
        with _rolling_back(roll_back):
            failpoint("spawn.after_allocated")
            worker, state, canonical = _advance_spawn(ws, worker_id, WorkerStatus.CLONING)
            shutil.rmtree(stage, ignore_errors=True)
            stage.mkdir(parents=True, exist_ok=False)
            stage_repo = stage / str(state.repo_name)
            if mode == "worktree":
                admin = add_worktree(canonical, stage_repo, str(worker.base_sha))
                _record_worktree_admin(ws, worker_id, admin)
            else:
                clone_cmd: list[str | Path] = [GIT_BIN, "clone", "--no-checkout"]
                if strong:
                    clone_cmd.append("--no-hardlinks")
                run([*clone_cmd, canonical, stage_repo], timeout=None)
            failpoint("spawn.after_clone")
            git(stage_repo, "cat-file", "-e", f"{worker.base_sha}^{{commit}}")

            worker, state, canonical = _advance_spawn(ws, worker_id, WorkerStatus.CONFIGURING)
            if mode == "worktree":
                details = _provision_worktree(canonical, stage_repo, worker)
            else:
                details = _provision_clone(canonical, stage_repo, worker, strong)
            failpoint("spawn.after_checkout")

            with workspace_lock(ws):
                state = WorkspaceState.load(ws)
                state.verify_canonical()
                current = WorkerRecord.load(ws, worker_id)
                if current.worker_token != worker.worker_token or current.status not in WorkerStatus.SPAWNING:
                    raise ClonegrownError("spawn metadata ownership changed")
                current.take_ownership(WorkerStatus.PUBLISHING)
                current.pending_spawn_details = asdict(details)
                current.save(ws)
                slot = worker_slot(ws, worker_id)
                if slot.exists():
                    raise ClonegrownError("worker final path already exists")
                os.replace(stage, slot)
                failpoint("spawn.after_publish")
                if mode == "worktree":
                    # The rename moved the worktree; Git's pointer back to it is now stale.
                    repair_worktree(canonical, slot / str(state.repo_name))
                failpoint("spawn.after_repair")
                current.status = WorkerStatus.READY
                current.ready = time.time()
                details.apply(current)
                current.pending_spawn_details = None
                current.release_ownership()
                current.save(ws)
                git(state.verify_canonical(), "update-ref", "-d", state.base_ref(worker_id))
                failpoint("spawn.after_ready")
                return current.to_json()


# --- collect -----------------------------------------------------------------

def _rollback_collect(ws: Path, worker_id: int, worker_token: str, error: BaseException) -> None:
    """Return a live worker to ``ready`` after an ordinary collection failure.

    Any fetched immutable result ref is deliberately retained: keeping an
    extra candidate is safer than deleting evidence.
    """
    with workspace_lock(ws):
        _, current, _ = load_worker(ws, worker_id)
        if current.status != WorkerStatus.COLLECTING or current.worker_token != worker_token:
            return
        current.status = WorkerStatus.READY
        current.collection_error = str(error)[:1000]
        current.collection_failed = time.time()
        current.release_ownership()
        current.clear_candidate()
        current.save(ws)


def collect(ws_path: Path, worker_id: int, allow_rewrite: bool = False) -> dict[str, Any]:
    """Fetch the worker's committed HEAD into canonical under an immutable ref.

    The worker is snapshotted before and after the fetch; if it changed in
    between, the fetched candidate is kept but not accepted. Re-collecting an
    already collected, unchanged worker is a no-op that refreshes the summary ref.
    """
    ws = ws_path.resolve()
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise ClonegrownError("worker is busy")
        with workspace_lock(ws):
            state, worker, canonical = load_worker(ws, worker_id)
            if worker.status == WorkerStatus.COLLECTED:
                snap = snapshot_worker(state, worker, require_ancestry=not allow_rewrite)
                if snap.head != worker.result_sha:
                    raise ClonegrownError("worker changed after collection; refusing to hide newer work")
                if not ref_points_at(canonical, worker.result_ref, worker.result_sha):
                    raise ClonegrownError("collected result ref is missing or changed")
                git(canonical, "update-ref", state.summary_ref(worker_id), str(worker.result_sha))
                return worker.to_json()
            if worker.status != WorkerStatus.READY:
                raise ClonegrownError(f"worker is not collectable from state {worker.status}")
        first = snapshot_worker(state, worker, require_ancestry=not allow_rewrite)
        candidate = first.head
        result_ref = state.result_ref(worker_id, candidate)
        with workspace_lock(ws):
            state, current, canonical = load_worker(ws, worker_id)
            if current.status != WorkerStatus.READY or current.worker_token != worker.worker_token:
                raise ClonegrownError("worker state changed before collection")
            current.take_ownership(WorkerStatus.COLLECTING)
            current.candidate_sha = candidate
            current.candidate_ref = result_ref
            current.allow_rewrite = bool(allow_rewrite)
            current.collect_started = time.time()
            current.save(ws)
            worker = current

        def roll_back(exc: BaseException) -> None:
            _rollback_collect(ws, worker_id, str(worker.worker_token), exc)

        with _rolling_back(roll_back):
            failpoint("collect.after_mark")
            failpoint("collect.before_fetch")
            git(canonical, "fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
                str(worker.repo), f"+{candidate}:{result_ref}")
            failpoint("collect.after_fetch")
            got = git(canonical, "rev-parse", "--verify", f"{result_ref}^{{commit}}").stdout.strip()
            if got != candidate:
                raise ClonegrownError("preserved result differs from candidate commit")
            git(canonical, "cat-file", "-e", f"{candidate}^{{commit}}")
            failpoint("collect.after_verify")
            second = snapshot_worker(state, worker, require_ancestry=not allow_rewrite)
            if second != first:
                with workspace_lock(ws):
                    state, current, _ = load_worker(ws, worker_id)
                    current.status = WorkerStatus.READY
                    current.collection_race = {"candidate": candidate, "observed": second.head, "time": time.time()}
                    current.release_ownership()
                    current.clear_candidate()
                    current.save(ws)
                raise ClonegrownError("worker changed during collection; candidate preserved but not accepted")
            failpoint("collect.after_worker_recheck")
            with workspace_lock(ws):
                state, current, canonical = load_worker(ws, worker_id)
                if current.status != WorkerStatus.COLLECTING or current.candidate_sha != candidate:
                    raise ClonegrownError("collection metadata changed")
                git(canonical, "update-ref", state.summary_ref(worker_id), candidate)
                failpoint("collect.after_summary")
                current.status = WorkerStatus.COLLECTED
                current.result_sha = candidate
                current.result_ref = result_ref
                current.collected = time.time()
                current.collected_snapshot = second.to_json()
                current.release_ownership()
                current.clear_candidate()
                current.save(ws)
                failpoint("collect.after_metadata")
                return current.to_json()


# --- discard -----------------------------------------------------------------

def discard(ws_path: Path, worker_id: int, abandon: bool = False, force: bool = False) -> dict[str, Any]:
    """Delete a worker directory. Uncollected work needs ``abandon``; drift after collection needs ``force``."""
    ws = ws_path.resolve()
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise ClonegrownError("worker is busy")
        with workspace_lock(ws):
            state, worker, canonical = load_worker(ws, worker_id)
            if worker.status in WorkerStatus.GONE:
                return worker.to_json()
            if worker.status in WorkerStatus.ACTIVE:
                raise ClonegrownError(f"worker has an active operation: {worker.status}")
            # Every destructive path authenticates the published worker first, so that
            # --abandon cannot turn metadata tampering into an accepted deletion.
            if worker_slot(ws, worker_id).exists():
                verify_worker(state, worker)
            if worker.status == WorkerStatus.COLLECTED:
                if not ref_points_at(canonical, worker.result_ref, worker.result_sha):
                    raise ClonegrownError("refusing deletion because collected result is not preserved")
                if worker.repo.exists() and not force:
                    snap = snapshot_worker(state, worker, require_ancestry=not worker.allow_rewrite)
                    if snap.head != worker.result_sha:
                        raise ClonegrownError("worker changed after collection; use --force only to knowingly discard it")
            elif not abandon:
                raise ClonegrownError("refusing to delete an uncollected worker; use explicit --abandon")
            worker.discard_intent = WorkerStatus.ABANDONED if abandon else WorkerStatus.DISCARDED
            worker.discard_previous = worker.status
            worker.discard_started = time.time()
            worker.take_ownership(WorkerStatus.DISCARDING)
            worker.save(ws)
        failpoint("discard.after_mark")
        failpoint("discard.before_delete")
        shutil.rmtree(worker_slot(ws, worker_id), ignore_errors=True)
        if worker.stage_root and Path(worker.stage_root).exists():
            shutil.rmtree(Path(worker.stage_root), ignore_errors=True)
        failpoint("discard.after_delete")
        with workspace_lock(ws):
            state, current, canonical = load_worker(ws, worker_id)
            forget_worktree(canonical, current)
            current.status = current.discard_intent or WorkerStatus.DISCARDED
            current.discarded = time.time()
            current.release_ownership()
            current.save(ws)
            failpoint("discard.after_metadata")
            return current.to_json()
