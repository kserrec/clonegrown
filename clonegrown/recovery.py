"""Recovering interrupted transactions and reporting workspace state.

``recover`` visits every worker record whose owning process is gone and
either finishes the interrupted transaction or rolls it back to the last
safe state. It never deletes a directory it cannot authenticate as the
worker the record describes.
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from .core import ClonegrownError, file_lock, git, process_alive
from .state import WorkerRecord, WorkerStatus, WorkspaceState, worker_lock_path, worker_slot, workspace_lock, ws_paths
from .worker import forget_worktree, load_worker, snapshot_worker, verify_worker

Report = dict[str, Any]


def _worker_record_files(ws: Path) -> tuple[list[Path], list[Path]]:
    """Worker record files in id order, and any stray files found beside them."""
    records, stray = [], []
    for candidate in ws_paths(ws)["workers"].glob("*.json"):
        (records if candidate.stem.isdigit() else stray).append(candidate)
    return sorted(records, key=lambda p: int(p.stem)), stray


def _orphan_slots(ws: Path, state: WorkspaceState, known_ids: set[int]) -> list[tuple[int, Path]]:
    """Numbered directories in the workspace that no record describes."""
    return [(int(child.name), child) for child in ws.iterdir()
            if child.is_dir() and child.name.isdigit()
            and int(child.name) != state.canonical_slot and int(child.name) not in known_ids]


def _ref_points_at(canonical: Path, ref: str | None, sha: str | None) -> bool:
    if not ref:
        return False
    got = git(canonical, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    return got.returncode == 0 and got.stdout.strip() == sha


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
        self.worker.error = error[:1000]
        self.save()
        self.report(action)

    def drop_base_pin(self) -> None:
        git(self.canonical, "update-ref", "-d", self.state.base_ref(self.worker_id), check=False)

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
        # A crash after the atomic publish but before the ready record can be completed safely.
        try:
            if repo.exists():
                if worker.is_worktree:
                    git(self.canonical, "worktree", "repair", repo, check=False)
                verify_worker(self.state, worker)
                if snapshot_worker(self.state, worker).head == worker.base_sha:
                    details = worker.pending_spawn_details
                    if isinstance(details, dict):
                        for key, value in details.items():
                            setattr(worker, key, value)
                    worker.pending_spawn_details = None
                    worker.status = WorkerStatus.READY
                    worker.ready = time.time()
                    self.save()
                    self.drop_base_pin()
                    self.report("spawn-publish-finished")
                    return
        except Exception:
            pass
        shutil.rmtree(Path(str(worker.stage_root)), ignore_errors=True)
        if self.slot.exists() and not repo.exists():
            self.mark_broken("allocated worker slot is occupied by an unrecognized path", "spawn-broken-slot-collision")
            return
        # Never delete a published path unless it authenticates as this incomplete worker.
        if repo.exists():
            try:
                verify_worker(self.state, worker)
                shutil.rmtree(self.slot, ignore_errors=True)
            except Exception:
                self.mark_broken("unverified path exists after interrupted spawn", "spawn-broken-unverified-path")
                return
        self.drop_base_pin()
        forget_worktree(self.canonical, worker)
        worker.status = WorkerStatus.SPAWN_FAILED
        worker.failed = time.time()
        worker.error = "interrupted spawn recovered"
        self.save()
        self.report("spawn-cleaned")

    def _recover_collecting(self) -> None:
        worker = self.worker
        candidate, ref = worker.candidate_sha, worker.candidate_ref
        can_finish = bool(candidate) and _ref_points_at(self.canonical, ref, candidate)
        if can_finish:
            try:
                snap = snapshot_worker(self.state, worker, require_ancestry=not worker.allow_rewrite)
                can_finish = snap.head == candidate
            except Exception:
                can_finish = False
        if can_finish:
            git(self.canonical, "update-ref", self.state.summary_ref(self.worker_id), str(candidate))
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
        if not self.slot.exists():
            forget_worktree(self.canonical, worker)
            worker.status = intent
            worker.discarded = time.time()
            self.save()
            self.report("discard-finished")
        elif intent == WorkerStatus.ABANDONED:
            # Explicit abandonment is the durable intent. With the owner gone, verify
            # this is still our worker before completing the destructive cleanup.
            try:
                verify_worker(self.state, worker)
                shutil.rmtree(self.slot)
                forget_worktree(self.canonical, worker)
                worker.status = WorkerStatus.ABANDONED
                worker.discarded = time.time()
                self.save()
                self.report("abandon-finished")
            except Exception as exc:
                self.mark_broken(f"could not safely finish abandonment: {exc}", "abandon-marked-broken")
        else:
            # For a collected result, rollback is conservative: keep the worker if the
            # deletion never happened; the caller may retry discard.
            worker.status = worker.discard_previous or WorkerStatus.COLLECTED
            self.save()
            self.report("discard-reset")

    def _recover_ready(self) -> None:
        # Dirty files and detached HEAD can be ordinary in-progress agent work; recovery
        # must not relabel or destroy them. Only structural identity/branch loss is fatal.
        try:
            repo = verify_worker(self.state, self.worker)
            branch = git(repo, "rev-parse", "--verify", f"refs/heads/{self.worker.branch}^{{commit}}", check=False)
            if branch.returncode:
                raise ClonegrownError("assigned task branch is missing")
        except Exception as exc:
            self.mark_broken(str(exc), "ready-marked-broken")

    def _recover_collected(self) -> None:
        worker = self.worker
        if _ref_points_at(self.canonical, worker.result_ref, worker.result_sha):
            git(self.canonical, "update-ref", self.state.summary_ref(self.worker_id), str(worker.result_sha))
        else:
            self.mark_broken("preserved result ref missing", "collected-marked-broken")

    def _recover_tombstone(self) -> None:
        worker = self.worker
        if worker.stage_root and Path(worker.stage_root).exists():
            shutil.rmtree(Path(worker.stage_root), ignore_errors=True)
        # Tombstones own no published directory; an explicitly abandoned one may linger.
        if worker.status in WorkerStatus.GONE and self.slot.exists():
            try:
                verify_worker(self.state, worker)
                shutil.rmtree(self.slot, ignore_errors=True)
                self.report("tombstone-path-cleaned")
            except Exception:
                self.report("tombstone-unverified-path-left")
        if not self.slot.exists() and worker.worktree_admin:
            forget_worktree(self.canonical, worker)
            worker.save(self.ws)
        self.drop_base_pin()


def recover(ws_path: Path) -> list[Report]:
    """Finish or roll back every interrupted operation whose owner has died. Safe to repeat."""
    ws = ws_path.resolve()
    reports: list[Report] = []
    with workspace_lock(ws):
        state = WorkspaceState.load(ws)
        state.verify_canonical()
        record_files, stray = _worker_record_files(ws)
        for path in stray:
            reports.append({"path": str(path), "action": "unknown-metadata-file"})
        for wid, child in _orphan_slots(ws, state, {int(p.stem) for p in record_files}):
            reports.append({"id": wid, "path": str(child), "action": "orphan-worker-directory"})
    for path in record_files:
        worker_id = int(path.stem)
        with file_lock(worker_lock_path(ws, worker_id), blocking=False) as acquired:
            if not acquired:
                reports.append({"id": worker_id, "action": "active-lock-held"})
                continue
            with workspace_lock(ws):
                try:
                    state, worker, canonical = load_worker(ws, worker_id)
                except ClonegrownError as exc:
                    reports.append({"id": worker_id, "path": str(path), "action": "corrupt-or-unreadable-metadata",
                                    "error": str(exc)[:1000]})
                    continue
                _Recovery(ws, state, worker, canonical, reports).run()
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
        workers = []
        for path in record_files:
            worker_id = int(path.stem)
            try:
                _, worker, _ = load_worker(ws, worker_id)
            except ClonegrownError as exc:
                issues.append({"id": worker_id, "path": str(path), "issue": "invalid-worker-metadata", "error": str(exc)})
                continue
            item = worker.to_json()
            if worker.status in {WorkerStatus.READY, WorkerStatus.COLLECTED} and worker.repo.exists():
                try:
                    snap = snapshot_worker(state, worker, require_ancestry=not worker.allow_rewrite)
                    if worker.status == WorkerStatus.COLLECTED and snap.head != worker.result_sha:
                        item["drift"] = "changed-after-collection"
                except Exception as exc:
                    item["drift"] = str(exc)
            workers.append(item)
        return {"workspace": str(ws), "canonical": str(canonical), "workspace_id": state.workspace_id,
                "workers": workers, "issues": issues}
