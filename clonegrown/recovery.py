"""Recovery at represented durable checkpoints, plus workspace-state reporting.

``recover`` examines worker records one at a time. It leaves an in-flight
operation alone while its recorded owner is alive. Once that owner is gone, it
runs the finish, reset, or cleanup path for the record's current status; it
also checks certain settled records. These paths cover only the Git and
filesystem boundaries represented by the durable record.

Interrupted-spawn recovery never deletes a published worker. A published
worker that authenticates and is still clean at its recorded base is
promoted to ``ready``; one that differs (dirty, advanced, off its branch) is
marked ``broken`` and preserved in place with a description of how it differs,
and its base pin stays until it is discarded. Only an unpublished stage, and
the admin directory and task branch this worker is proved to own, are removed.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

import os
import re

from .core import (
    ClonegrownError, file_lock, git, operation_boundary, operation_checkpoint, process_alive,
    public_exception_text, redact_public_text,
)
from .audit import (
    NamespaceRefs, _PIN_DROPPED, audit_lock_files, audit_namespace, audit_request_indexes, audit_stages, audit_worker,
)
from .repository import delete_ref, is_symbolic_ref, ref_points_at, resolve_ref, write_ref
from .state import WorkerRecord, WorkerStatus, WorkspaceState, worker_lock_path, worker_slot, workspace_lock, ws_paths
from .worker import (
    adoptable_quarantine, delete_through_quarantine, delete_verified, describe_divergence, finish_deletion,
    forget_worktree, load_worker_record, orphan_quarantines, repair_owned_worktree, snapshot_worker,
    unrecorded_quarantine, verify_worker, withdraw_discard, worktree_cleanup_conflict,
)

Report = dict[str, Any]


_WORKER_ID = re.compile(r"(0|[1-9][0-9]*)")


def _worker_id_of(name: str) -> int | None:
    """The worker id a slot or record name denotes, if it is exactly one in canonical decimal form.

    ``str.isdigit`` also accepts superscripts and other Unicode digits that
    ``int`` rejects, and ``int`` accepts ``01``; neither names a worker.
    """
    return int(name) if _WORKER_ID.fullmatch(name) else None


def _worker_record_files(ws: Path) -> tuple[list[Path], list[Path]]:
    """Worker record files in id order, and any stray files found beside them."""
    records, stray = [], []
    for candidate in ws_paths(ws)["workers"].iterdir():
        if candidate.suffix == ".json" and _worker_id_of(candidate.stem) is not None:
            records.append(candidate)
        else:
            stray.append(candidate)
    return sorted(records, key=lambda p: int(p.stem)), sorted(stray)


def _orphan_slots(ws: Path, state: WorkspaceState, known_ids: set[int]) -> list[tuple[int, Path]]:
    """Numbered directories in the workspace that no record describes."""
    out = []
    for child in ws.iterdir():
        wid = _worker_id_of(child.name)
        if wid is not None and child.is_dir() and wid != state.canonical_slot and wid not in known_ids:
            out.append((wid, child))
    return out


def _loadable_records(ws: Path, state: WorkspaceState, record_files: list[Path]) -> dict[int, WorkerRecord]:
    """Records that load and validate against ``state``, keyed by id; invalid ones are reported elsewhere."""
    out: dict[int, WorkerRecord] = {}
    for path in record_files:
        try:
            out[int(path.stem)] = load_worker_record(ws, state, int(path.stem))
        except ClonegrownError:
            continue
    return out


class _Recovery:
    """Recovery of one worker; each ``_recover_<status>`` method handles one status."""

    def __init__(self, ws: Path, state: WorkspaceState, worker: WorkerRecord, canonical: Path,
                 reports: list[Report]) -> None:
        self.ws = ws
        self.state = state
        self.worker = worker
        self.canonical = canonical
        self.reports = reports
        self.worker_id = int(worker.id)
        self.slot = worker_slot(ws, self.worker_id)

    # helpers

    def report(self, action: str) -> None:
        self.reports.append({"id": self.worker_id, "action": action})

    def save(self) -> None:
        self.worker.release_ownership()
        self.worker.save(self.ws)

    def mark_broken(self, error: str, action: str) -> None:
        self.worker.status = WorkerStatus.BROKEN
        self.worker.error = redact_public_text(error)[:1000]
        self.save()
        self.report(action)

    def drop_base_pin(self) -> None:
        """Drop this worker's base pin at its recorded value; a pin naming anything else is reported and kept."""
        ref = self.state.base_ref(self.worker_id)
        value = resolve_ref(self.canonical, ref)
        if value is None:
            return
        if value != self.worker.base_sha or is_symbolic_ref(self.canonical, ref):
            self.report("base-ref-ambiguous")
            return
        delete_ref(self.canonical, ref, value)

    def drop_stale_base_pin(self) -> None:
        """Remove this worker's base pin only when its status says it must be gone and its value is the recorded base.

        A pin that names any other commit, or belongs to a broken or in-flight
        worker, is left for ``status`` to report.
        """
        worker = self.worker
        if worker.status not in _PIN_DROPPED:
            return
        ref = self.state.base_ref(self.worker_id)
        value = resolve_ref(self.canonical, ref)
        if value is None:
            return
        if value != worker.base_sha or is_symbolic_ref(self.canonical, ref):
            self.report("base-ref-ambiguous")
            return
        delete_ref(self.canonical, ref, value)
        self.report("base-ref-dropped")

    def forget_worktree(self) -> None:
        """Targeted worktree cleanup; a retained branch or admin directory is reported, never forced."""
        forget_worktree(self.canonical, self.worker, persist=lambda: self.worker.save(self.ws))
        if worktree_cleanup_conflict(self.worker):
            self.report("worktree-cleanup-conflict")

    def owner_alive(self) -> bool:
        return process_alive(self.worker.owner_pid, self.worker.owner_start)

    # dispatch

    def run(self) -> None:
        status = self.worker.status
        if status in WorkerStatus.SPAWNING:
            if self.owner_alive():
                self.report("active-spawn-alive")
            else:
                self._recover_spawn()
        elif status == WorkerStatus.COLLECTING:
            if self.owner_alive():
                self.report("active-collect-alive")
            else:
                self._recover_collecting()
        elif status == WorkerStatus.DISCARDING:
            if self.owner_alive():
                self.report("active-discard-alive")
            else:
                self._recover_discarding()
        elif status == WorkerStatus.READY:
            self._recover_ready()
        elif status == WorkerStatus.COLLECTED:
            self._recover_collected()
        elif status in WorkerStatus.TOMBSTONE:
            self._recover_tombstone()

    # one method per status

    def _recover_spawn(self) -> None:
        worker = self.worker
        repo = worker.repo
        if repo.exists():
            self._recover_published_spawn()
            return
        if self.slot.exists():
            self.mark_broken("allocated worker slot is occupied by an unrecognized path", "spawn-broken-slot-collision")
            return
        # Never published: only the stage, the admin directory, and the task branch this
        # worker is proved to own are removed.
        stage = Path(str(worker.stage_root))
        if os.path.lexists(stage):
            try:
                delete_verified(stage, "worker stage")
            except ClonegrownError as exc:
                self.mark_broken(f"could not remove the worker stage: {exc}", "spawn-stage-left")
                return
        self.drop_base_pin()
        self.forget_worktree()
        if worktree_cleanup_conflict(worker):
            self.mark_broken("interrupted spawn left canonical worktree state that could not be cleaned",
                             "spawn-cleanup-incomplete")
            return
        worker.status = WorkerStatus.SPAWN_FAILED
        worker.failed = time.time()
        worker.error = "interrupted spawn recovered"
        self.save()
        self.report("spawn-cleaned")

    def _recover_published_spawn(self) -> None:
        """A worker directory exists: finish the publication if it is untouched, otherwise preserve it."""
        worker = self.worker
        repo = worker.repo
        try:
            repair_owned_worktree(self.canonical, worker, repo)
            verify_worker(self.state, worker)
        except ClonegrownError as exc:
            self.mark_broken(f"unverified path exists after interrupted spawn: {exc}", "spawn-broken-unverified-path")
            return
        try:
            divergence = describe_divergence(self.state, worker)
        except ClonegrownError as exc:
            self.mark_broken(f"published worker preserved after interrupted spawn: cannot inspect it ({exc})",
                             "spawn-preserved-broken")
            return
        if divergence is None:
            details = worker.pending_spawn_details
            if isinstance(details, dict):
                for key, value in details.items():
                    if key in WorkerRecord._SPAWN_DETAILS:
                        setattr(worker, key, value)
            worker.pending_spawn_details = None
            worker.status = WorkerStatus.READY
            worker.ready = time.time()
            self.save()
            self.drop_base_pin()
            self.report("spawn-publish-finished")
            return
        # Work may have happened after publication. Keep the directory, its base pin, its
        # branch, and its admin directory exactly as they are; say how it differs, not what it holds.
        self.mark_broken(f"published worker preserved after interrupted spawn: {divergence}", "spawn-preserved-broken")

    def _recover_collecting(self) -> None:
        worker = self.worker
        candidate, ref = worker.candidate_sha, worker.candidate_ref
        can_finish = bool(candidate) and ref_points_at(self.canonical, ref, candidate)
        if can_finish:
            try:
                snap = snapshot_worker(self.state, worker, require_ancestry=not worker.allow_rewrite)
                can_finish = snap.head == candidate
            except Exception:
                can_finish = False
        if can_finish and is_symbolic_ref(self.canonical, self.state.summary_ref(self.worker_id)):
            can_finish = False  # never write through a symbolic ref in our namespace
        if can_finish:
            write_ref(self.canonical, self.state.summary_ref(self.worker_id), str(candidate))
            worker.status = WorkerStatus.COLLECTED
            worker.result_sha = candidate
            worker.result_ref = ref
            worker.collected = time.time()
            self.report("collect-finished")
        else:
            worker.status = WorkerStatus.READY
            worker.collection_recovered = time.time()
            self.report("collect-reset-ready")
        worker.clear_candidate()
        self.save()

    def _recover_discarding(self) -> None:
        worker = self.worker
        intent = worker.discard_intent or WorkerStatus.DISCARDED
        finished = "abandon-finished" if intent == WorkerStatus.ABANDONED else "discard-finished"
        try:
            found = adoptable_quarantine(self.ws, self.state, worker, self.canonical)
        except ClonegrownError as exc:
            # Something that is not this worker occupies its derived quarantine path. Never
            # touch it; withdraw a normal discard whose worker is still in place, otherwise
            # leave the record recoverable and say exactly what blocks it.
            if self.slot.exists() and intent != WorkerStatus.ABANDONED:
                self._withdraw_discard()
            else:
                worker.error = public_exception_text(exc)[:1000]
                self.save()
            self.report("quarantine-path-occupied")
            return
        if found is not None:
            # Content sits at this worker's derived quarantine path but the record never learned
            # of it: adopt the path, with no fingerprint, so it is preserved and reported.
            worker.quarantine_path = str(found)
            worker.quarantine_started = worker.quarantine_started or time.time()
            self.save()
        intended_only = (worker.quarantine_path is not None and not os.path.lexists(worker.quarantine_path)
                         and self.slot.exists())
        if intended_only and intent != WorkerStatus.ABANDONED:
            # Intent was recorded but nothing moved. A normal discard is simply withdrawn; the
            # caller retries it against the worker as it is now.
            self._withdraw_discard()
        elif worker.quarantine_path is not None:
            # An interrupted or refused deletion left the worker in (or on its way to) quarantine:
            # resume it against the fingerprint recorded before the rename. Never label residue gone.
            self._resume_deletion(finished, "quarantine-preserved")
        elif not self.slot.exists():
            self._resume_deletion(finished, "discard-cleanup-incomplete")
        elif intent == WorkerStatus.ABANDONED and worker.is_leased:
            # Only an explicit release authorizes deletion; a dead owner does not.
            worker.status = worker.discard_previous or WorkerStatus.READY
            self.save()
            self.report("abandon-blocked-by-lease")
        elif intent == WorkerStatus.ABANDONED:
            # Explicit abandonment is the durable intent. With the owner gone, the
            # deletion runs the same authenticated quarantine flow a live discard does.
            self._resume_deletion(finished, "abandon-preserved")
        else:
            # For a collected result, rollback is conservative: keep the worker if the
            # deletion never happened; the caller may retry discard.
            self._withdraw_discard()

    def _withdraw_discard(self) -> None:
        withdraw_discard(self.worker)
        self.save()
        self.report("discard-reset")

    def _resume_deletion(self, finished: str, preserved: str) -> None:
        worker = self.worker
        try:
            delete_through_quarantine(self.ws, self.state, worker, self.canonical, self.save)
        except Exception as exc:  # noqa: BLE001 - a filesystem error here is a preserved quarantine, not a crash
            reason = public_exception_text(exc)
            if worker.quarantine_path is not None:
                worker.quarantine_error = reason[:1000]
                self.save()
                self.report(preserved)
            elif self.slot.exists():
                self.mark_broken(f"could not safely finish deletion: {reason}", "discard-marked-broken")
            else:
                # The content is gone; only the stage or canonical cleanup remains. Keep the
                # record recoverable and try again next time.
                worker.error = f"deletion incomplete: {reason[:900]}"
                self.save()
                self.report("discard-cleanup-incomplete")
            return
        if finish_deletion(self.canonical, worker, self.save):
            self.report(finished)
        else:
            self.report("worktree-cleanup-conflict")

    def _recover_ready(self) -> None:
        # Dirty files and detached HEAD can be ordinary in-progress agent work; recovery
        # must not relabel or destroy them. Only structural identity/branch loss is fatal.
        try:
            repo = verify_worker(self.state, self.worker)
            branch = git(repo, "rev-parse", "--verify", f"refs/heads/{self.worker.branch}^{{commit}}", check=False)
            if branch.returncode:
                raise ClonegrownError("assigned task branch is missing")
        except Exception as exc:
            self.mark_broken(public_exception_text(exc), "ready-marked-broken")

    def _recover_collected(self) -> None:
        worker = self.worker
        if not ref_points_at(self.canonical, worker.result_ref, worker.result_sha):
            self.mark_broken("preserved result ref missing", "collected-marked-broken")
            return
        summary = self.state.summary_ref(self.worker_id)
        if is_symbolic_ref(self.canonical, summary):
            self.report("summary-ref-symbolic-left")
            return
        current = resolve_ref(self.canonical, summary)
        if current != worker.result_sha:
            # Compare-and-swap against what was observed; the result ref above is the authority.
            expected_old = current or ("0" * len(str(worker.result_sha)))
            write_ref(self.canonical, summary, str(worker.result_sha), expected_old)
            self.report("summary-ref-repaired")

    def _recover_tombstone(self) -> None:
        worker = self.worker
        if worker.stage_root and os.path.lexists(worker.stage_root):
            try:
                delete_verified(Path(str(worker.stage_root)), "worker stage")
            except ClonegrownError:
                self.report("tombstone-stage-left")
        # A terminal record owns no directory. Whatever occupies its slot now was put there
        # after the deletion was proved (or after a failed spawn); it is reported, never deleted
        # without a new discard.
        if worker.status in WorkerStatus.TOMBSTONE and self.slot.exists():
            self.report("tombstone-path-left")
        found = unrecorded_quarantine(self.ws, worker)
        if found is not None:
            self.report("tombstone-quarantine-left")
        if not self.slot.exists() and (worker.worktree_admin or worker.branch_cleanup_sha):
            # Retained evidence means an earlier cleanup did not finish; try again, never by name alone.
            self.forget_worktree()
            worker.save(self.ws)
        # The base pin, if any, is handled by drop_stale_base_pin with its ownership rule.


@operation_boundary("recover")
def recover(ws_path: Path) -> list[Report]:
    """Reconcile the lifecycle checkpoints represented by current worker records.

    Nothing published is deleted here; a diverged published spawn is
    preserved as ``broken`` and a quarantine is resumed only against its
    recorded fingerprint. See the module contract.
    """
    ws = ws_path.resolve()
    reports: list[Report] = []
    removed_locks = 0
    completed_workers = 0
    operation_checkpoint(
        stage="workspace recovery inventory",
        durable_state="no recovery mutation from this attempt is known to have completed",
        work_preservation="believed preserved — workspace and worker custody are being inspected",
        recovery="retry recover; manually inspect the workspace only if inventory remains unreadable",
    )
    with workspace_lock(ws):
        state = WorkspaceState.load(ws)
        canonical = state.verify_canonical()
        record_files, stray = _worker_record_files(ws)
        for path in stray:
            reports.append({"path": str(path), "action": "unknown-metadata-file"})
        for wid, child in _orphan_slots(ws, state, {int(p.stem) for p in record_files}):
            reports.append({"id": wid, "path": str(child), "action": "orphan-worker-directory"})
        valid = _loadable_records(ws, state, record_files)
        for child in orphan_quarantines(ws, valid):
            reports.append({"path": str(child), "action": "orphan-quarantine"})
        refs = NamespaceRefs(canonical, state)
        known_ids = {int(p.stem) for p in record_files}
        for found in audit_namespace(state, refs, known_ids):
            reports.append({**found, "action": found["issue"] + "-left"})
        for found in audit_request_indexes(ws, state, valid):
            reports.append({**found, "action": found["issue"] + "-left"})
        for found in audit_stages(ws, valid):
            reports.append({**found, "action": "orphan-stage-left"})
        for found in audit_lock_files(ws, known_ids):
            # A lock file is Clonegrown's own advisory control file; one for an id with no record
            # holds nothing and would only block that id's allocation later.
            try:
                operation_checkpoint(
                    stage="orphan lock-file cleanup",
                    durable_state=(f"{removed_locks} orphan lock files were removed; completion of the next "
                                   "control-file removal is unverified"),
                    work_preservation="believed preserved — orphan advisory lock files hold no worker content",
                    recovery="retry recover; manually inspect a lock path only if removal repeatedly fails",
                )
                os.unlink(found["path"])
                removed_locks += 1
                reports.append({**found, "action": "orphan-lock-file-removed"})
            except OSError as exc:
                reports.append({**found, "action": "orphan-lock-file-left",
                                "error": public_exception_text(exc)[:200]})
    for path in record_files:
        worker_id = int(path.stem)
        failure_stage = "worker recovery-lock acquisition"
        failure_durable_state = (
            f"{removed_locks} orphan lock files and recovery for {completed_workers} workers completed; "
            "this worker has not been changed in the current stage"
        )
        failure_work_preservation = "believed preserved — this worker has not entered recovery mutation"
        failure_recovery = "retry recover; manually inspect this worker after a repeated recovery failure"
        operation_checkpoint(
            stage=f"worker {worker_id} recovery-lock acquisition",
            durable_state=failure_durable_state,
            work_preservation=failure_work_preservation,
            recovery=failure_recovery,
        )
        try:
            with file_lock(worker_lock_path(ws, worker_id), blocking=False) as acquired:
                if not acquired:
                    reports.append({"id": worker_id, "action": "active-lock-held"})
                    continue
                failure_stage = "worker metadata loading"
                with workspace_lock(ws):
                    try:
                        worker = load_worker_record(ws, state, worker_id)
                    except ClonegrownError as exc:
                        reports.append({
                            "id": worker_id,
                            "path": str(path),
                            "action": "corrupt-or-unreadable-metadata",
                            "error": public_exception_text(exc)[:1000],
                        })
                        continue
                    try:
                        recovery = _Recovery(ws, state, worker, canonical, reports)
                        failure_stage = "worker reconciliation"
                        failure_durable_state = (
                            f"prior recovery actions completed for {completed_workers} workers; worker "
                            f"{worker_id}'s next durable mutation is unverified"
                        )
                        failure_work_preservation = (
                            "unverified — this worker may be reset, preserved, repaired, or deleted only "
                            "according to its recorded custody state"
                        )
                        failure_recovery = (
                            "retry recover; manually inspect the worker if repeated reports cannot reconcile it"
                        )
                        operation_checkpoint(
                            stage=f"worker {worker_id} reconciliation",
                            durable_state=failure_durable_state,
                            work_preservation=failure_work_preservation,
                            recovery=failure_recovery,
                        )
                        recovery.run()
                        if not any(r.get("id") == worker_id and r.get("action") == "base-ref-ambiguous"
                                   for r in reports):
                            recovery.drop_stale_base_pin()
                        completed_workers += 1
                        failure_stage = f"after worker {worker_id} reconciliation"
                        failure_durable_state = (
                            f"{removed_locks} orphan lock files were removed and recovery completed for "
                            f"{completed_workers} workers"
                        )
                        failure_work_preservation = (
                            "believed handled according to each authenticated record; status remains the "
                            "authority for preserved or deleted worker content"
                        )
                        failure_recovery = (
                            "retry recover if another stage fails; manually inspect only issues status cannot resolve"
                        )
                        operation_checkpoint(
                            stage=failure_stage,
                            durable_state=failure_durable_state,
                            work_preservation=failure_work_preservation,
                            recovery=failure_recovery,
                        )
                    except Exception as exc:  # noqa: BLE001 - one worker's failure must not stop the others
                        reports.append({
                            "id": worker_id,
                            "action": "recovery-failed",
                            "error": f"{type(exc).__name__}: {public_exception_text(exc)[:900]}",
                            "stage": "worker reconciliation",
                            "durable_state": ("the last completed worker checkpoint remains authoritative; "
                                              "later mutation is unverified"),
                            "work_preservation": "unverified; inspect this worker and its reported custody paths",
                            "recovery": ("retry recover; if this worker fails again, inspect it manually before "
                                         "any deletion"),
                        })
        except Exception as exc:  # noqa: BLE001 - a worker-local setup failure must not stop later workers
            reports.append({
                "id": worker_id,
                "action": "recovery-failed",
                "error": f"{type(exc).__name__}: {public_exception_text(exc)[:900]}",
                "stage": failure_stage,
                "durable_state": failure_durable_state,
                "work_preservation": failure_work_preservation,
                "recovery": failure_recovery,
            })
    return reports


def status(ws_path: Path) -> dict[str, Any]:
    """Describe the workspace, every worker record, and any inconsistencies found."""
    ws = ws_path.resolve()
    with workspace_lock(ws):
        state = WorkspaceState.load(ws)
        canonical = state.verify_canonical()
        issues: list[Report] = []
        record_files, stray = _worker_record_files(ws)
        for path in stray:
            issues.append({"path": str(path), "issue": "unexpected-metadata-file"})
        for wid, child in _orphan_slots(ws, state, {int(p.stem) for p in record_files}):
            issues.append({"id": wid, "path": str(child), "issue": "orphan-worker-directory"})
        refs = NamespaceRefs(canonical, state)
        valid: dict[int, WorkerRecord] = {}
        workers = []
        for path in record_files:
            worker_id = int(path.stem)
            try:
                worker = load_worker_record(ws, state, worker_id)
            except ClonegrownError as exc:
                issues.append({"id": worker_id, "path": str(path), "issue": "invalid-worker-metadata",
                               "error": public_exception_text(exc)[:200]})
                continue
            valid[worker_id] = worker
            item = worker.to_json()
            issues.extend(audit_worker(ws, state, canonical, worker, refs))
            if worker.status in {WorkerStatus.READY, WorkerStatus.COLLECTED} and worker.repo.exists():
                try:
                    snap = snapshot_worker(state, worker, require_ancestry=not worker.allow_rewrite)
                    if worker.status == WorkerStatus.COLLECTED and snap.head != worker.result_sha:
                        item["drift"] = "changed-after-collection"
                except Exception as exc:
                    item["drift"] = public_exception_text(exc)[:200]
            workers.append(item)
        known_ids = {int(p.stem) for p in record_files}
        for child in orphan_quarantines(ws, valid):
            issues.append({"path": str(child), "issue": "orphan-quarantine"})
        issues.extend(audit_request_indexes(ws, state, valid))
        issues.extend(audit_namespace(state, refs, known_ids))
        issues.extend(audit_stages(ws, valid))
        issues.extend(audit_lock_files(ws, known_ids))
        return {"workspace": str(ws), "canonical": str(canonical), "workspace_id": state.workspace_id,
                "workers": workers, "issues": issues}
