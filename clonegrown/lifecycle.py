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
    ClonegrownError, atomic_json, failpoint, file_lock, git, git_common_dir, inside, load_json, object_format,
    operation_boundary, operation_checkpoint, process_alive, public_exception_text, validate_primary_repo,
)
from .recovery import recover
from .repository import (
    WORKTREE_SHARING_WARNING, absent_marker, add_worktree, apply_clone_config_plan,
    build_clone_config_plan, checkout_without_hooks, copy_auxiliary_refs, copy_info_files,
    copy_sparse_patterns, copy_sparse_policy, create_task_branch, delete_ref,
    detach_alternates_if_needed, is_symbolic_ref, private_hook_warnings, ref_points_at,
    repair_worktree, resolve_ref, sparse_checkout_enabled, write_ref,
)
from .state import (
    SCHEMA, WORKER_MODES, WorkerRecord, WorkerStatus, WorkspaceState, branch_owner_ref, canonical_marker_path,
    worker_lock_path, worker_slot, workspace_lock, ws_paths,
)
from .worker import (
    DELETION_AUTHORIZED, AdminDirectoryMissing, adoptable_quarantine, allocate_spawn, authenticate_settled, require_worker,
    clear_quarantine, custody_fingerprint,
    delete_through_quarantine, delete_verified, finish_deletion, forget_worktree, inspect_ignored_content,
    load_worker, repair_owned_worktree, snapshot_worker, unrecorded_quarantine, verify_worker, withdraw_discard,
    write_worker_marker,
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
        if not isinstance(exc, Exception):
            raise
        with contextlib.suppress(Exception):
            on_error(exc)
        raise


def _canonical_marker(workspace_id: str, token: str, canonical: Path) -> dict[str, Any]:
    return {"workspace_id": workspace_id, "token": token, "canonical": str(canonical), "created": time.time()}


# --- init --------------------------------------------------------------------

@operation_boundary("init")
def init_workspace(canonical_path: Path, ws_path: Path) -> dict[str, Any]:
    """Create (or finish creating) a workspace bound to one canonical checkout. Idempotent."""
    canonical = validate_primary_repo(canonical_path)
    ws = ws_path.resolve()
    if ws == canonical or inside(ws, canonical):
        raise ClonegrownError("workspace cannot be the canonical repository or live inside its working tree")
    paths = ws_paths(ws)
    operation_checkpoint(
        stage="workspace control-directory creation",
        durable_state="workspace control-directory creation is in progress and may be partial",
        work_preservation="believed preserved — initialization writes only Clonegrown metadata, not working files",
        recovery="retry init; if the workspace path remains unsafe, inspect that path manually",
    )
    for key in ("workers", "requests", "locks", "staging"):
        paths[key].mkdir(parents=True, exist_ok=True)
    operation_checkpoint(
        stage="workspace-state inspection",
        durable_state="workspace control directories were created or confirmed; no identity record was changed",
        work_preservation="believed preserved — canonical working files were not changed",
        recovery="retry init; manually inspect an existing state or marker only if the reported conflict persists",
    )
    with workspace_lock(ws):
        if paths["state"].exists():
            state = WorkspaceState.from_json(load_json(paths["state"]))
            state.validate(ws, require_ready=False)
            operation_checkpoint(
                stage="existing workspace verification",
                durable_state=f"existing workspace state {state.status!r} was read; this attempt has not changed it",
                work_preservation=("believed preserved — the existing workspace and canonical checkout "
                                   "remain in place"),
                recovery=("retry init; manually inspect the workspace state and canonical marker if "
                          "verification keeps failing"),
            )
            if Path(str(state.canonical)).resolve() != canonical:
                raise ClonegrownError("workspace is already initialized for a different canonical path")
            if state.status == "initializing":
                # Finish either crash window: after the state write or after the marker write.
                marker_path = canonical_marker_path(canonical, str(state.workspace_id))
                if marker_path.exists():
                    if load_json(marker_path).get("token") != state.canonical_token:
                        raise ClonegrownError("initializing workspace has a conflicting canonical marker")
                else:
                    operation_checkpoint(
                        stage="canonical marker creation",
                        durable_state=("the initializing workspace state exists; canonical marker creation "
                                       "is unverified"),
                        work_preservation="believed preserved — only Clonegrown identity metadata may be changing",
                        recovery="retry init; inspect the canonical marker manually if the conflict persists",
                    )
                    atomic_json(
                        marker_path,
                        _canonical_marker(str(state.workspace_id), str(state.canonical_token), canonical),
                    )
                operation_checkpoint(
                    stage="workspace ready-state commit",
                    durable_state=("the initializing state and token-matching canonical marker exist; the "
                                   "ready-state write is unverified"),
                    work_preservation=("believed preserved — canonical working files and existing workers "
                                       "remain untouched"),
                    recovery="retry init to finish the represented initialization checkpoint",
                )
                state.status = "ready"
                state.save(ws)
                operation_checkpoint(
                    stage="completed workspace verification",
                    durable_state="workspace ready state and canonical identity marker were written",
                    work_preservation="believed preserved — initialization changed only Clonegrown metadata",
                    recovery="not required; retry init only if the caller did not receive the result",
                )
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
        operation_checkpoint(
            stage="initializing-state commit",
            durable_state="the initializing workspace-state write is unverified",
            work_preservation="believed preserved — no canonical working file or worker content is modified",
            recovery="retry init; it can finish a valid initializing record",
        )
        state.save(ws)
        operation_checkpoint(
            stage="after initializing-state commit",
            durable_state="the initializing workspace state was written; no canonical marker is confirmed yet",
            work_preservation="believed preserved — only the new workspace metadata exists",
            recovery="retry init to create or verify the canonical marker",
        )
        failpoint("init.after_state")
        operation_checkpoint(
            stage="canonical marker creation",
            durable_state="the initializing workspace state exists; canonical marker creation is unverified",
            work_preservation="believed preserved — only Clonegrown identity metadata may be changing",
            recovery="retry init; inspect the canonical marker manually if the conflict persists",
        )
        atomic_json(canonical_marker_path(canonical, workspace_id), _canonical_marker(workspace_id, token, canonical))
        operation_checkpoint(
            stage="after canonical marker creation",
            durable_state="the initializing workspace state and canonical identity marker were written",
            work_preservation="believed preserved — canonical working files remain untouched",
            recovery="retry init to commit the ready state",
        )
        failpoint("init.after_marker")
        state.status = "ready"
        operation_checkpoint(
            stage="workspace ready-state commit",
            durable_state="the state and marker exist; completion of the ready-state write is unverified",
            work_preservation="believed preserved — initialization changed only Clonegrown metadata",
            recovery="retry init; it reconciles this represented initialization checkpoint",
        )
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


class _RetryableOutcome(Exception):
    """The existing worker for this request ended in a state that lets the request be allocated again."""


def _require_plain_refs(canonical: Path, *refs: str) -> None:
    """A namespace ref that is symbolic is not ours: refuse to write through it."""
    for ref in refs:
        if is_symbolic_ref(canonical, ref):
            raise ClonegrownError(f"refusing to write through a symbolic ref in Clonegrown's namespace: {ref}")


def _wait_for_existing(ws: Path, worker_id: int, timeout_seconds: float) -> dict[str, Any]:
    """Wait for another process's spawn of the same request ID to settle, then hand back a proven outcome."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        state, worker, canonical = load_worker(ws, worker_id)
        if worker.status in WorkerStatus.RETRYABLE:
            raise _RetryableOutcome(worker.status)  # the caller allocates afresh, as a retry would
        if worker.status in WorkerStatus.SETTLED:
            authenticate_settled(ws, state, worker, canonical)
            return worker.to_json()
        if worker.status == WorkerStatus.BROKEN:
            raise ClonegrownError(f"existing request failed in worker {worker_id}: {worker.error or worker.status}")
        if time.monotonic() >= deadline:
            raise ClonegrownError(f"timed out waiting for existing request worker {worker_id}; run recover")
        if not process_alive(worker.owner_pid, worker.owner_start):
            operation_checkpoint(
                stage="existing request recovery",
                durable_state=f"worker {worker_id} has a dead recorded owner; recovery completion is unverified",
                work_preservation=("unverified — recovery must reconcile the existing worker before it can "
                                   "be returned"),
                recovery=("run `clonegrown recover`; manually inspect the worker only if reconciliation "
                          "repeatedly fails"),
            )
            recover(ws)
            operation_checkpoint(
                stage="existing request settlement",
                durable_state=f"recovery examined worker {worker_id}; this spawn made no new allocation",
                work_preservation="believed handled according to the existing worker's authenticated record",
                recovery="inspect `clonegrown status` if the existing request still cannot settle",
            )
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
    function records it; recovery then locates the entry by its ``gitdir``
    back-pointer into this worker's unique staged path.
    """
    failpoint("spawn.after_worktree_add")
    with workspace_lock(ws):
        worker = WorkerRecord.load(ws, worker_id)
        worker.worktree_admin = str(admin)
        worker.save(ws)


def _check_out_base(stage_repo: Path, worker: WorkerRecord, canonical: Path | None = None) -> None:
    """Put the staged repository on its task branch at the pinned base and stamp its identity.

    A clone creates the branch in its own refs. A worktree's branch lives in
    canonical's shared refs, so it is created there first, together with the
    worker's private ownership ref, in one create-only transaction that a
    pre-existing branch of that name aborts untouched.
    """
    if canonical is not None:
        create_task_branch(canonical, str(worker.branch),
                           branch_owner_ref(str(worker.workspace_id), int(worker.id)), str(worker.base_sha))
        checkout_without_hooks(stage_repo, str(worker.branch), str(worker.base_sha), create=False)
    else:
        checkout_without_hooks(stage_repo, str(worker.branch), str(worker.base_sha))
    write_worker_marker(stage_repo, worker)
    if git(stage_repo, "rev-parse", "HEAD").stdout.strip() != worker.base_sha:
        raise ClonegrownError("worker checkout differs from immutable requested base")


def _provision_worktree(canonical: Path, stage_repo: Path, worker: WorkerRecord) -> SpawnDetails:
    """Check out the base in a staged worktree; everything else is shared with canonical."""
    sparse = sparse_checkout_enabled(canonical)  # the config is shared; only the pattern file is per-worktree
    if sparse:
        copy_sparse_patterns(canonical, stage_repo)
    _check_out_base(stage_repo, worker, canonical)
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
    config_plan = build_clone_config_plan(canonical)
    detached, warnings = detach_alternates_if_needed(stage_repo, strong)
    source_remote, copied_config, config_warnings = apply_clone_config_plan(stage_repo, config_plan)
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
            worker.interrupted_error = public_exception_text(exc)[:1000]
        else:
            worker.status = WorkerStatus.SPAWN_FAILED
            worker.failed = time.time()
            worker.error = public_exception_text(exc)[:1000]
        worker.release_ownership()
        worker.save(ws)
        if not published:
            delete_ref(state.verify_canonical(), state.base_ref(worker_id), check=False)


def _discard_unpublished_stage(ws: Path, worker_id: int, stage: Path) -> None:
    if worker_slot(ws, worker_id).exists():
        return
    stage_error: str | None = None
    try:
        delete_verified(stage, "worker stage")
    except ClonegrownError as exc:
        stage_error = public_exception_text(exc)[:500]  # left for recovery; the record says so
    with contextlib.suppress(Exception):
        state = WorkspaceState.load(ws)
        canonical = state.verify_canonical()
        worker = WorkerRecord.load(ws, worker_id)
        forget_worktree(canonical, worker, persist=lambda: worker.save(ws))
        if stage_error:
            worker.error = f"{worker.error or 'spawn failed'}; stage not removed: {stage_error}"
        worker.save(ws)


@operation_boundary("spawn")
def spawn(ws_path: Path, base: str, task: str, strong: bool = False,
          request_id: str | None = None, wait_seconds: float = 120.0,
          mode: str = "clone") -> dict[str, Any]:
    """Create a worker at ``base`` and return its ``ready`` record.

    The default is a non-strong clone. ``mode`` is ``"clone"`` (an independent
    repository; ``strong=True`` disables object sharing) or ``"worktree"`` (a
    linked worktree sharing canonical's Git internals). Stages: allocated ->
    cloning -> configuring -> publishing -> ready. The worker is built under
    ``.cws/staging`` and moved into its numbered slot with one atomic rename.
    Worktree repair and the final ready record occur after that rename while
    Clonegrown still holds its locks.
    """
    if mode not in WORKER_MODES:
        raise ClonegrownError(f"unknown worker mode: {mode!r}")
    if mode == "worktree" and strong:
        raise ClonegrownError("a worktree worker shares canonical's objects; --strong does not apply")
    ws = ws_path.resolve()
    operation_checkpoint(
        stage="allocation validation",
        durable_state="no allocation metadata or Git ref has been changed by this spawn attempt",
        work_preservation="believed preserved — the workspace is being inspected before allocation",
        recovery=("not required unless the cause reports existing inconsistent metadata; then inspect "
                  "`clonegrown status`"),
    )
    for _ in range(3):
        worker, created = allocate_spawn(ws, base, task, strong, request_id, mode)
        if created:
            break
        operation_checkpoint(
            stage="existing request settlement",
            durable_state="this spawn made no allocation; it is waiting on an existing request worker",
            work_preservation="believed preserved — the existing worker is authenticated and not modified here",
            recovery="run `clonegrown recover` only if the cause reports an interrupted existing request",
        )
        try:
            return _wait_for_existing(ws, int(worker.id), wait_seconds)
        except _RetryableOutcome:
            continue  # the existing worker was abandoned or failed meanwhile; allocate again
    else:
        raise ClonegrownError(f"request {request_id!r} kept settling in a retryable state; try again")
    worker_id = int(worker.id)
    stage = Path(str(worker.stage_root))
    published_by_this_call = False
    operation_checkpoint(
        stage="worker operation-lock acquisition",
        durable_state=f"worker {worker_id} has an allocated record and base pin but no published directory",
        work_preservation="believed preserved — existing workers are untouched and this worker is not published",
        recovery="run `clonegrown recover`, then inspect `clonegrown status` before retrying spawn",
    )

    def roll_back(exc: BaseException) -> None:
        operation_checkpoint(
            stage="spawn failure recording and rollback",
            durable_state=f"worker {worker_id} rollback and failure-record writes are in progress and unverified",
            work_preservation="unverified — publication and cleanup must be determined from the slot and record",
            recovery=("run `clonegrown recover`, then inspect `clonegrown status`; manually inspect any "
                      "reported residue"),
        )
        with contextlib.suppress(Exception):
            _record_spawn_failure(ws, worker_id, exc)
        _discard_unpublished_stage(ws, worker_id, stage)
        if published_by_this_call:
            operation_checkpoint(
                stage="spawn failure after publication",
                durable_state=(f"worker {worker_id} is published; its failure record or cleanup completion "
                               "is unverified"),
                work_preservation="believed preserved — the published worker directory remains in place",
                recovery="run `clonegrown recover`; manually inspect the worker if recovery reports it as broken",
            )
        elif os.path.lexists(worker_slot(ws, worker_id)):
            operation_checkpoint(
                stage="spawn failure with occupied publication slot",
                durable_state=(f"something exists at worker {worker_id}'s slot; publication ownership and "
                               "failure-record completion are unverified"),
                work_preservation="unverified — Clonegrown did not delete or authenticate the occupied slot",
                recovery="run `clonegrown status`; inspect the occupied slot manually before any further action",
            )
        else:
            operation_checkpoint(
                stage="spawn failure before publication",
                durable_state=(f"worker {worker_id} remains allocated or failed; unpublished-stage and base-pin "
                               "cleanup were attempted but must be checked"),
                work_preservation=("believed preserved — no worker directory was published and existing "
                                   "work was untouched"),
                recovery="run `clonegrown recover`, then inspect `clonegrown status` for stage or ref residue",
            )

    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise ClonegrownError("worker operation lock unexpectedly unavailable")
        with _rolling_back(roll_back):
            failpoint("spawn.after_allocated")
            operation_checkpoint(
                stage="cloning-state commit",
                durable_state=f"worker {worker_id} is allocated; the cloning checkpoint write is unverified",
                work_preservation="believed preserved — no worker directory is published",
                recovery="run `clonegrown recover`, then inspect `clonegrown status`",
            )
            worker, state, canonical = _advance_spawn(ws, worker_id, WorkerStatus.CLONING)
            shutil.rmtree(stage, ignore_errors=True)
            operation_checkpoint(
                stage="staging-directory creation",
                durable_state=f"worker {worker_id} is recorded as cloning; staging-directory creation is unverified",
                work_preservation="believed preserved — the numbered worker slot is still absent",
                recovery="run `clonegrown recover`; it reconciles unpublished staging residue",
            )
            stage.mkdir(parents=True, exist_ok=False)
            stage_repo = stage / str(state.repo_name)
            operation_checkpoint(
                stage="repository provisioning",
                durable_state=(f"worker {worker_id} has an unpublished staging directory; repository "
                               "creation is unverified"),
                work_preservation="believed preserved — staged content is not published as worker work",
                recovery="run `clonegrown recover`; inspect any reported stage or worktree residue manually",
            )
            if mode == "worktree":
                admin = add_worktree(canonical, stage_repo, str(worker.base_sha))
                _record_worktree_admin(ws, worker_id, admin)
            else:
                clone_args: list[str | Path] = ["clone", "--no-checkout"]
                if strong:
                    clone_args.append("--no-hardlinks")
                git(stage, *clone_args, canonical, stage_repo, sensitive=(canonical,))
            operation_checkpoint(
                stage="staged repository verification",
                durable_state=f"worker {worker_id} has an unpublished staged repository; no worker slot is published",
                work_preservation=("believed preserved — existing worker and canonical working files remain "
                                   "untouched"),
                recovery="run `clonegrown recover`; it cleans only authenticated unpublished spawn state",
            )
            failpoint("spawn.after_clone")
            git(stage_repo, "cat-file", "-e", f"{worker.base_sha}^{{commit}}")

            operation_checkpoint(
                stage="configuring-state commit",
                durable_state=(f"worker {worker_id} has an unpublished staged repository; checkpoint write "
                               "is unverified"),
                work_preservation="believed preserved — the numbered worker slot is still absent",
                recovery="run `clonegrown recover`; inspect reported stage or worktree residue manually",
            )
            worker, state, canonical = _advance_spawn(ws, worker_id, WorkerStatus.CONFIGURING)
            if mode == "worktree":
                details = _provision_worktree(canonical, stage_repo, worker)
            else:
                details = _provision_clone(canonical, stage_repo, worker, strong)
            operation_checkpoint(
                stage="staged checkout completion",
                durable_state=(f"worker {worker_id} is fully staged but not published; publication metadata "
                               "is unchanged"),
                work_preservation="believed preserved — staged content remains outside the numbered worker slot",
                recovery="run `clonegrown recover`; it removes only authenticated unpublished state",
            )
            failpoint("spawn.after_checkout")

            with workspace_lock(ws):
                state = WorkspaceState.load(ws)
                state.verify_canonical()
                current = WorkerRecord.load(ws, worker_id)
                if current.worker_token != worker.worker_token or current.status not in WorkerStatus.SPAWNING:
                    raise ClonegrownError("spawn metadata ownership changed")
                current.take_ownership(WorkerStatus.PUBLISHING)
                current.pending_spawn_details = asdict(details)
                operation_checkpoint(
                    stage="publishing-state commit",
                    durable_state=f"worker {worker_id} is staged; the publishing checkpoint write is unverified",
                    work_preservation="believed preserved — the worker slot is not yet known to exist",
                    recovery=("run `clonegrown recover`; it distinguishes unpublished from published state "
                              "by custody evidence"),
                )
                current.save(ws)
                slot = worker_slot(ws, worker_id)
                if slot.exists():
                    raise ClonegrownError("worker final path already exists")
                operation_checkpoint(
                    stage="worker publication rename",
                    durable_state=(f"worker {worker_id} is recorded as publishing; completion of the staging-to-slot "
                                   "rename is unverified"),
                    work_preservation=("unverified — the worker may be staged or published, so neither path "
                                       "may be assumed"),
                    recovery=("run `clonegrown recover`; manually inspect the worker only if recovery cannot "
                              "authenticate it"),
                )
                os.replace(stage, slot)
                published_by_this_call = True
                operation_checkpoint(
                    stage="published worker repair",
                    durable_state=f"worker {worker_id} was published and remains recorded as publishing",
                    work_preservation="believed preserved — recovery never deletes a published interrupted spawn",
                    recovery="run `clonegrown recover`; manually inspect the worker if it is reported broken",
                )
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
                operation_checkpoint(
                    stage="ready-state commit",
                    durable_state=(f"worker {worker_id} is published; completion of its ready-record write "
                                   "is unverified"),
                    work_preservation="believed preserved — the published worker directory remains in place",
                    recovery=("run `clonegrown recover`; inspect the worker manually only if recovery reports "
                              "it broken"),
                )
                current.save(ws)
                # Best effort: the worker is ready either way; a pin that cannot be dropped (a
                # symbolic ref planted under its name) is reported by status, not by this spawn.
                delete_ref(state.verify_canonical(), state.base_ref(worker_id), check=False)
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
        current.collection_error = public_exception_text(error)[:1000]
        current.collection_failed = time.time()
        current.release_ownership()
        current.clear_candidate()
        current.save(ws)


@operation_boundary("collect")
def collect(ws_path: Path, worker_id: int, allow_rewrite: bool = False) -> dict[str, Any]:
    """Fetch the worker's committed HEAD into canonical under an immutable ref.

    The worker is snapshotted before and after the fetch; if it changed in
    between, the fetched candidate is kept but not accepted. Re-collecting an
    already collected, unchanged worker is a no-op that refreshes the summary ref.
    """
    ws = ws_path.resolve()
    require_worker(ws, worker_id)  # never create a lock file for an id that names no worker
    operation_checkpoint(
        stage="worker operation-lock acquisition",
        durable_state=f"worker {worker_id} exists; this collect attempt has not changed its metadata or refs",
        work_preservation="believed preserved — the worker and canonical repository have only been inspected",
        recovery="not required; retry collect after resolving the reported lock or metadata problem",
    )
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise ClonegrownError("worker is busy")
        operation_checkpoint(
            stage="worker and canonical custody verification",
            durable_state=f"worker {worker_id} has not been changed by this collect attempt",
            work_preservation="believed preserved — collection has not written metadata or refs",
            recovery=("not required for an ordinary refusal; run `clonegrown status` and inspect manually "
                      "if metadata, identity, or custody verification failed"),
        )
        with workspace_lock(ws):
            state, worker, canonical = load_worker(ws, worker_id)
            if worker.status == WorkerStatus.COLLECTED:
                snap = snapshot_worker(state, worker, require_ancestry=not allow_rewrite)
                if snap.head != worker.result_sha:
                    raise ClonegrownError("worker changed after collection; refusing to hide newer work")
                if not ref_points_at(canonical, worker.result_ref, worker.result_sha):
                    raise ClonegrownError("collected result ref is missing or changed")
                _require_plain_refs(canonical, state.summary_ref(worker_id), str(worker.result_ref))
                operation_checkpoint(
                    stage="collected summary-ref refresh",
                    durable_state=(f"worker {worker_id} is already collected and its immutable result exists; "
                                   "summary-ref update completion is unverified"),
                    work_preservation="believed preserved — the worker and immutable result ref remain in place",
                    recovery="run `clonegrown status`; manually inspect only a reported symbolic or conflicting ref",
                )
                write_ref(canonical, state.summary_ref(worker_id), str(worker.result_sha))
                return worker.to_json()
            if worker.status != WorkerStatus.READY:
                raise ClonegrownError(f"worker is not collectable from state {worker.status}")
        first = snapshot_worker(state, worker, require_ancestry=not allow_rewrite)
        candidate = first.head
        result_ref = state.result_ref(worker_id, candidate)
        _require_plain_refs(canonical, result_ref, state.summary_ref(worker_id))
        with workspace_lock(ws):
            state, current, canonical = load_worker(ws, worker_id)
            if current.status != WorkerStatus.READY or current.worker_token != worker.worker_token:
                raise ClonegrownError("worker state changed before collection")
            current.take_ownership(WorkerStatus.COLLECTING)
            current.candidate_sha = candidate
            current.candidate_ref = result_ref
            current.allow_rewrite = bool(allow_rewrite)
            current.collect_started = time.time()
            operation_checkpoint(
                stage="collecting-state commit",
                durable_state=(f"worker {worker_id} is still ready; completion of the collecting checkpoint "
                               "write is unverified"),
                work_preservation="believed preserved — the worker directory is not modified by collection",
                recovery="run `clonegrown recover`, then inspect `clonegrown status` before retrying collect",
            )
            current.save(ws)
            worker = current
            operation_checkpoint(
                stage="candidate fetch",
                durable_state=(f"worker {worker_id} is recorded as collecting candidate {candidate}; "
                               "candidate-ref creation is unverified"),
                work_preservation=("believed preserved — the worker stays in place and any fetched candidate "
                                   "is retained"),
                recovery=("run `clonegrown recover`; it either finishes the proven candidate or resets the "
                          "worker ready"),
            )

        def roll_back(exc: BaseException) -> None:
            operation_checkpoint(
                stage="collection rollback",
                durable_state=(f"worker {worker_id} rollback is in progress; any fetched immutable candidate ref "
                               "is intentionally retained"),
                work_preservation="unverified — the worker record must be checked after rollback",
                recovery="run `clonegrown recover`, then inspect `clonegrown status`",
            )
            _rollback_collect(ws, worker_id, str(worker.worker_token), exc)
            operation_checkpoint(
                stage="collection rolled back",
                durable_state=(f"worker {worker_id} was returned to ready; any fetched immutable candidate ref "
                               "was retained as evidence"),
                work_preservation="believed preserved — the worker directory and fetched candidate remain available",
                recovery="not required; inspect `clonegrown status` and retry collect when ready",
            )

        with _rolling_back(roll_back):
            failpoint("collect.after_mark")
            failpoint("collect.before_fetch")
            git(canonical, "fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
                str(worker.repo), f"+{candidate}:{result_ref}", sensitive=(worker.repo,))
            operation_checkpoint(
                stage="candidate verification",
                durable_state=(f"immutable candidate ref {result_ref} was fetched; the worker record remains "
                               "collecting"),
                work_preservation="believed preserved — both the worker and fetched candidate are retained",
                recovery=("run `clonegrown recover`; it validates the candidate before accepting or resetting "
                          "collection"),
            )
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
                operation_checkpoint(
                    stage="collection race refusal",
                    durable_state=(f"worker {worker_id} was returned to ready and candidate ref {result_ref} "
                                   "was retained but not accepted"),
                    work_preservation="believed preserved — both versions remain available for inspection",
                    recovery="not required; inspect the worker, then retry collect when its intended tip is stable",
                )
                raise ClonegrownError("worker changed during collection; candidate preserved but not accepted")
            failpoint("collect.after_worker_recheck")
            with workspace_lock(ws):
                state, current, canonical = load_worker(ws, worker_id)
                if current.status != WorkerStatus.COLLECTING or current.candidate_sha != candidate:
                    raise ClonegrownError("collection metadata changed")
                operation_checkpoint(
                    stage="summary-ref commit",
                    durable_state=(f"immutable candidate ref {result_ref} exists; summary-ref update completion "
                                   "is unverified"),
                    work_preservation="believed preserved — the worker and immutable candidate ref remain available",
                    recovery="run `clonegrown recover`; manually inspect only a reported symbolic or conflicting ref",
                )
                write_ref(canonical, state.summary_ref(worker_id), candidate)
                operation_checkpoint(
                    stage="collected-state commit",
                    durable_state=(f"candidate and summary refs preserve {candidate}; completion of worker "
                                   f"{worker_id}'s collected-record write is unverified"),
                    work_preservation=("believed preserved — the worker directory and immutable result ref "
                                       "remain available"),
                    recovery="run `clonegrown recover`; it can finish the represented collection checkpoint",
                )
                failpoint("collect.after_summary")
                current.status = WorkerStatus.COLLECTED
                current.result_sha = candidate
                current.result_ref = result_ref
                current.collected = time.time()
                current.collected_snapshot = second.to_json()
                current.release_ownership()
                current.clear_candidate()
                current.save(ws)
                operation_checkpoint(
                    stage="completed collection",
                    durable_state=(f"worker {worker_id} is recorded collected and immutable result ref "
                                   f"{result_ref} preserves its accepted tip"),
                    work_preservation=("believed preserved — the worker and accepted immutable result remain "
                                       "available"),
                    recovery="not required; inspect `clonegrown status` if the result was not returned",
                )
                failpoint("collect.after_metadata")
                return current.to_json()


# --- the work lease ------------------------------------------------------------

# Statuses whose lease can be released: the worker is published and no operation is in flight.
LEASE_RELEASABLE = frozenset({WorkerStatus.READY, WorkerStatus.COLLECTED, WorkerStatus.BROKEN})


def claim(ws_path: Path, worker_id: int) -> dict[str, Any]:
    """Take the cooperative work lease on a released worker that is still ``ready``.

    A spawned worker is leased from the start; ``claim`` exists for the
    handoff after an explicit ``release``. A collected worker is one-shot and
    cannot be claimed again.
    """
    ws = ws_path.resolve()
    require_worker(ws, worker_id)  # never create a lock file for an id that names no worker
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise ClonegrownError("worker is busy")
        with workspace_lock(ws):
            _, worker, _ = load_worker(ws, worker_id)
            if worker.status != WorkerStatus.READY:
                raise ClonegrownError(f"only a ready worker can be claimed; worker {worker_id} is {worker.status}")
            if worker.is_leased:
                raise ClonegrownError(f"worker {worker_id} is already leased; it must be released before it can be claimed again")
            worker.lease = "active"
            worker.lease_released = None
            worker.save(ws)
            return worker.to_json()


def release(ws_path: Path, worker_id: int) -> dict[str, Any]:
    """Release the cooperative work lease so the worker may be discarded. Repeating it is a no-op.

    Release is the caller's statement that every process it started in the
    worker has stopped. Clonegrown records that statement; it cannot verify it.
    """
    ws = ws_path.resolve()
    require_worker(ws, worker_id)  # never create a lock file for an id that names no worker
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise ClonegrownError("worker is busy")
        with workspace_lock(ws):
            _, worker, _ = load_worker(ws, worker_id)
            if worker.status not in LEASE_RELEASABLE:
                raise ClonegrownError(f"worker {worker_id} holds no releasable lease in state {worker.status}")
            if worker.is_leased:
                worker.lease = "released"
                worker.lease_released = time.time()
                worker.save(ws)
            return worker.to_json()


# --- discard -----------------------------------------------------------------

@operation_boundary("discard")
def discard(ws_path: Path, worker_id: int, abandon: bool = False, force: bool = False,
            discard_ignored: bool = False) -> dict[str, Any]:
    """Delete a released worker through an authenticated quarantine.

    Each acknowledgement is separate and explicit: an uncollected worker needs
    ``abandon`` (which covers everything it holds); a collected worker needs
    ``force`` for changes detected after collection and ``discard_ignored``
    for Git-ignored paths, which the collection snapshot never saw. The lease
    is checked before any flag: none of them overrides it. A collected worker
    is one-shot, so ``abandon`` does not apply to it.

    Deletion records its intent, fingerprints the worker, moves the slot to
    ``.cws/quarantine/<id>-<token>`` with one rename, rechecks the quarantined
    worker against that fingerprint, deletes it with errors enabled, proves
    the path absent, and cleans canonical's worktree state. The terminal
    status is recorded only when every part succeeded; otherwise the record
    stays ``discarding`` with the quarantine path and the error, and a later
    ``recover`` resumes it. A worker preserved in quarantine because it
    changed can be deleted by running ``discard`` again with the same
    acknowledgement (``abandon``, or ``force`` for a collected one), which
    takes a fresh fingerprint.
    """
    ws = ws_path.resolve()
    require_worker(ws, worker_id)  # never create a lock file for an id that names no worker
    operation_checkpoint(
        stage="worker operation-lock acquisition",
        durable_state=f"worker {worker_id} exists; this discard attempt has not recorded intent or moved content",
        work_preservation="believed preserved — the worker has only been located",
        recovery="not required; retry discard after resolving the reported lock or metadata problem",
    )
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise ClonegrownError("worker is busy")
        operation_checkpoint(
            stage="custody verification",
            durable_state=f"worker {worker_id} is unchanged; no discard intent or move completed",
            work_preservation="believed preserved — deletion has not begun",
            recovery=("not required for refusal; use `clonegrown status` and inspect manually if custody "
                      "verification failed"),
        )
        with workspace_lock(ws):
            state, worker, canonical = load_worker(ws, worker_id)
            if worker.status in WorkerStatus.GONE:
                return worker.to_json()
            if worker.status == WorkerStatus.DISCARDING and _intent_never_moved(ws, worker):
                # A recorded intent that moved nothing is stale: withdraw it and decide again
                # with the caller's acknowledgements against the worker as it is now.
                withdraw_discard(worker)
                operation_checkpoint(
                    stage="stale discard-intent withdrawal",
                    durable_state=(f"worker {worker_id} remains in its slot; completion of the intent-withdrawal "
                                   "record write is unverified"),
                    work_preservation="believed preserved — no worker content was moved or deleted",
                    recovery=("run `clonegrown recover`, then inspect `clonegrown status` if the record stays "
                              "discarding"),
                )
                worker.save(ws)  # the withdrawal stands even if the fresh authorization refuses
                _authorize_discard(ws, state, worker, canonical, worker_id, abandon, force, discard_ignored)
            elif worker.status == WorkerStatus.DISCARDING:
                _reauthorize_quarantined(state, worker, canonical, abandon, force)
            else:
                _authorize_discard(ws, state, worker, canonical, worker_id, abandon, force, discard_ignored)
            worker.take_ownership(WorkerStatus.DISCARDING)
            operation_checkpoint(
                stage="discard-intent commit",
                durable_state=(f"worker {worker_id} remains in its slot; completion of its discard-intent "
                               "checkpoint write is unverified"),
                work_preservation="believed preserved — quarantine and deletion have not begun",
                recovery="run `clonegrown recover`; it reconciles only the recorded, acknowledged intent",
            )
            worker.save(ws)
        operation_checkpoint(
            stage="quarantine preparation",
            durable_state=f"worker {worker_id} is recorded discarding but remains in its numbered slot",
            work_preservation="believed preserved — no worker content has moved or been deleted",
            recovery="run `clonegrown recover`; it withdraws or resumes the represented discard checkpoint",
        )
        failpoint("discard.after_mark")

        def persist() -> None:
            with workspace_lock(ws):
                worker.save(ws)

        def preserve(exc: BaseException) -> None:
            # Decide by what is on disk, not by which field happens to be set. Nothing moved:
            # return the worker to its previous status with the discard intent withdrawn.
            # Content in quarantine: keep it there with the reason. Content gone but cleanup
            # unfinished: stay discarding so recover finishes it.
            operation_checkpoint(
                stage="discard failure preservation",
                durable_state=f"worker {worker_id}'s slot, quarantine, and record are being reconciled after failure",
                work_preservation="unverified — the custody locations must be checked before any claim is made",
                recovery=("run `clonegrown recover`, then inspect `clonegrown status`; manually inspect "
                          "ambiguous residue"),
            )
            with workspace_lock(ws):
                _, current, _ = load_worker(ws, worker_id)
                if current.status != WorkerStatus.DISCARDING or current.worker_token != worker.worker_token:
                    return
                slot_present = worker_slot(ws, worker_id).exists()
                quarantine_present = bool(current.quarantine_path and os.path.lexists(current.quarantine_path))
                reason = public_exception_text(exc)
                if slot_present and not quarantine_present:
                    withdraw_discard(current)
                elif quarantine_present:
                    current.quarantine_error = reason[:1000]
                else:
                    current.error = f"deletion incomplete: {reason[:900]}"
                current.release_ownership()
                current.save(ws)
                if slot_present and not quarantine_present:
                    operation_checkpoint(
                        stage="discard failure before quarantine",
                        durable_state=f"worker {worker_id} remains in its slot and its discard intent was withdrawn",
                        work_preservation="believed preserved — no worker content was moved or deleted",
                        recovery="not required; resolve the cause and retry discard with the required acknowledgement",
                    )
                elif quarantine_present and current.quarantine_snapshot == DELETION_AUTHORIZED:
                    operation_checkpoint(
                        stage="discard failure during authorized deletion",
                        durable_state=f"worker {worker_id} remains discarding at its recorded quarantine path",
                        work_preservation="unverified — explicitly authorized deletion may be partial",
                        recovery="run `clonegrown recover`; do not move or edit the quarantine while it finishes",
                    )
                elif quarantine_present:
                    operation_checkpoint(
                        stage="discard failure with preserved quarantine",
                        durable_state=(f"worker {worker_id} remains discarding with content at its recorded "
                                       "quarantine path"),
                        work_preservation="believed preserved — the worker content remains quarantined",
                        recovery=("run `clonegrown recover`; manually inspect only if it reports changed or "
                                  "ambiguous content"),
                    )
                else:
                    operation_checkpoint(
                        stage="discard failure after content deletion",
                        durable_state=(f"worker {worker_id}'s content is absent but terminal cleanup remains "
                                       "incomplete"),
                        work_preservation=("believed preserved — deletion was confined to the authorized worker; "
                                           "any collected result ref is separate"),
                        recovery="run `clonegrown recover` to finish canonical cleanup and terminal metadata",
                    )

        with _rolling_back(preserve):
            delete_through_quarantine(ws, state, worker, canonical, persist)
        with workspace_lock(ws):
            state, current, canonical = load_worker(ws, worker_id)
            if current.status != WorkerStatus.DISCARDING or current.worker_token != worker.worker_token:
                raise ClonegrownError("discard metadata changed")
            operation_checkpoint(
                stage="canonical cleanup and terminal-state commit",
                durable_state=(f"worker {worker_id}'s content is absent; completion of canonical cleanup and "
                               "terminal metadata is unverified"),
                work_preservation=("believed preserved — deletion was confined to the authorized worker; "
                                   "any collected result ref remains separate"),
                recovery="run `clonegrown recover`; manually inspect only cleanup conflicts it reports",
            )
            if not finish_deletion(canonical, current, lambda: current.save(ws)):
                operation_checkpoint(
                    stage="incomplete canonical cleanup",
                    durable_state=f"worker {worker_id}'s content is absent and its record remains discarding",
                    work_preservation=("believed preserved — any collected result ref remains; worker content was "
                                       "explicitly authorized for deletion"),
                    recovery="run `clonegrown recover`; manually inspect retained branch/admin cleanup evidence",
                )
                raise ClonegrownError(
                    f"worker {worker_id} content is deleted but canonical cleanup is incomplete "
                    f"({current.branch_cleanup_left or current.worktree_admin_left}); "
                    "the record stays discarding and recover will retry")
            operation_checkpoint(
                stage="completed discard",
                durable_state=f"worker {worker_id}'s content is absent and its terminal record is committed",
                work_preservation=("believed preserved — deletion was confined to the authorized worker; "
                                   "any collected result remains under its immutable ref"),
                recovery="not required; inspect `clonegrown status` if the result was not returned",
            )
            failpoint("discard.after_metadata")
            return current.to_json()


def _authorize_discard(ws: Path, state: WorkspaceState, worker: WorkerRecord, canonical: Path, worker_id: int,
                       abandon: bool, force: bool, discard_ignored: bool) -> None:
    """Every refusal before deletion intent is recorded; the record is not modified here."""
    if worker.status in WorkerStatus.ACTIVE:
        raise ClonegrownError(f"worker has an active operation: {worker.status}")
    # Every destructive path authenticates the published worker first, so that
    # --abandon cannot turn metadata tampering into an accepted deletion.
    if worker_slot(ws, worker_id).exists():
        verify_worker(state, worker)
    if abandon and worker.status == WorkerStatus.COLLECTED:
        raise ClonegrownError("a collected worker is one-shot; --abandon applies only to an uncollected worker")
    if worker.status != WorkerStatus.SPAWN_FAILED and worker.is_leased:
        raise ClonegrownError(
            f"worker {worker_id} is leased; stop every process that writes to it, then run "
            f"`clonegrown release {worker_id}` before discarding it")
    if worker.status == WorkerStatus.COLLECTED:
        if not ref_points_at(canonical, worker.result_ref, worker.result_sha):
            raise ClonegrownError("refusing deletion because collected result is not preserved")
        if worker.repo.exists():
            # Two custody questions, answered separately: did the committed tip move,
            # and is there ignored content the collection snapshot never inspected?
            missing: list[str] = []
            if not force:
                snap = snapshot_worker(state, worker, require_ancestry=not worker.allow_rewrite)
                if snap.head != worker.result_sha:
                    missing.append("--force: the worker changed after collection")
            if not discard_ignored:
                ignored = inspect_ignored_content(worker.repo)
                if ignored.count:
                    missing.append(f"--discard-ignored: the worker holds {ignored.describe()}")
            if missing:
                raise ClonegrownError(
                    f"refusing to discard collected worker {worker_id} without explicit acknowledgement; "
                    "required: " + "; ".join(missing))
    elif not abandon:
        raise ClonegrownError("refusing to delete an uncollected worker; use explicit --abandon")
    worker.discard_intent = WorkerStatus.ABANDONED if abandon else WorkerStatus.DISCARDED
    worker.discard_previous = worker.status
    worker.discard_started = time.time()
    if worker.is_worktree:
        # Record where the task branch points now, before anything is deleted; cleanup
        # deletes it only if it still points there. An absent branch is recorded as the
        # all-zero id, so one that appears later under the same name is not taken as ours.
        worker.branch_cleanup_sha = (resolve_ref(canonical, f"refs/heads/{worker.branch}")
                                     or absent_marker(str(worker.base_sha)))


def ws_for(worker: WorkerRecord) -> Path:
    """The workspace a validated record belongs to: two levels above its repository path."""
    return worker.repo.parent.parent


def _intent_never_moved(ws: Path, worker: WorkerRecord) -> bool:
    """A discarding record whose owner is gone and whose slot is still in place, with no quarantine anywhere."""
    if process_alive(worker.owner_pid, worker.owner_start):
        raise ClonegrownError(f"worker has an active operation: {worker.status}")
    quarantined = worker.quarantine_path is not None and os.path.lexists(worker.quarantine_path)
    return (worker_slot(ws, int(worker.id)).exists() and not quarantined
            and unrecorded_quarantine(ws, worker) is None)


def _reauthorize_quarantined(state: WorkspaceState, worker: WorkerRecord, canonical: Path,
                             abandon: bool, force: bool) -> None:
    """A worker preserved in quarantine is deleted only by a fresh, matching acknowledgement."""
    if process_alive(worker.owner_pid, worker.owner_start):
        raise ClonegrownError(f"worker has an active operation: {worker.status}")
    if worker.quarantine_path is None:
        found = adoptable_quarantine(ws_for(worker), state, worker, canonical)
        if found is None:
            return  # nothing of the worker remains to ask about; this run finishes stage and canonical cleanup
        worker.quarantine_path = str(found)  # found at its derived path with no recorded fingerprint
    if worker.quarantine_snapshot == DELETION_AUTHORIZED:
        return  # the custody check already passed and deletion began; this run just finishes it
    needed = "abandon" if worker.discard_intent == WorkerStatus.ABANDONED else "force"
    if not (abandon if needed == "abandon" else force):
        raise ClonegrownError(
            f"worker {int(worker.id)} is preserved in quarantine at {worker.quarantine_path} "
            f"({worker.quarantine_error or 'deletion did not complete'}); pass --{needed} to delete it anyway")
    repo = Path(worker.quarantine_path) / str(state.repo_name)
    if worker_slot(ws_for(worker), int(worker.id)).exists():
        raise ClonegrownError(
            f"worker {int(worker.id)} has content both in its slot and at {worker.quarantine_path}; "
            "nothing is deleted until one of them is moved away by hand")
    try:
        repair_owned_worktree(canonical, worker, repo)
        verify_worker(state, worker, repo=repo)
    except AdminDirectoryMissing:
        # Git can no longer read the quarantined checkout, but the path is derived from this
        # record's identity under .cws and the caller has just acknowledged deleting it.
        pass
    worker.quarantine_snapshot = custody_fingerprint(repo)  # the new baseline the caller just accepted
    worker.quarantine_error = None
