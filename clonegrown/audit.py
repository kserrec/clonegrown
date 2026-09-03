"""Non-mutating invariant audit of a workspace: what ``status`` reports and ``recover`` consults.

Every check here observes and describes; nothing is repaired. Each finding is
an issue with a stable ``issue`` code, the worker ``id`` when one applies, and
bounded context (a path, a ref, a commit id, or a short error text), never
file contents or configuration values.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .core import ClonegrownError, git, load_json, process_alive
from .repository import is_symbolic_ref, ref_points_at, resolve_ref
from .state import (
    WorkerRecord, WorkerStatus, WorkspaceState, branch_owner_ref, request_path, worker_lock_path, worker_record_path,
    worker_slot, ws_paths,
)
from .worker import unrecorded_quarantine, verify_worker

Issue = dict[str, Any]

# Statuses whose base pin should already be gone: it is dropped when the worker becomes
# ready, when a spawn fails, and when a worker is deleted. A broken worker keeps it.
_PIN_DROPPED = frozenset({WorkerStatus.READY, WorkerStatus.COLLECTING, WorkerStatus.COLLECTED,
                          WorkerStatus.DISCARDED, WorkerStatus.ABANDONED, WorkerStatus.SPAWN_FAILED})
_LIVE_ON_DISK = frozenset({WorkerStatus.READY, WorkerStatus.COLLECTING, WorkerStatus.COLLECTED})


def _short(text: str) -> str:
    return text[:200]


# --- the ref namespace -----------------------------------------------------------

class NamespaceRefs:
    """Every ref under ``refs/cws/<workspace_id>/``, parsed by worker id.

    A symbolic ref under one of our names is never ours: it is listed as
    symbolic, excluded from every per-worker view, and reported, so no
    write can be redirected through it onto the branch it names.
    """

    _BASE = re.compile(r"bases/(0|[1-9][0-9]*)$")

    def __init__(self, canonical: Path, state: WorkspaceState) -> None:
        self.prefix = state.ref_prefix
        hex_len = 64 if state.object_format == "sha256" else 40
        self._worker = re.compile(r"workers/(0|[1-9][0-9]*)/(result|branch-owner|results/[0-9a-f]{%d})$" % hex_len)
        self.values: dict[str, str] = {}
        self.symbolic: list[str] = []
        listing = git(canonical, "for-each-ref", "--format=%(refname) %(objectname) %(symref)", f"{self.prefix}/").stdout
        for line in listing.splitlines():
            parts = line.split(" ", 2)
            if len(parts) < 2 or not parts[0]:
                continue
            if len(parts) == 3 and parts[2]:
                self.symbolic.append(parts[0])
                continue
            self.values[parts[0]] = parts[1]
        self.bases: dict[int, str] = {}
        self.by_worker: dict[int, dict[str, str]] = {}
        self.unrecognized: list[str] = []
        for ref, value in self.values.items():
            rest = ref[len(self.prefix) + 1:]
            base = self._BASE.fullmatch(rest)
            worker = self._worker.fullmatch(rest)
            if base:
                self.bases[int(base.group(1))] = value
            elif worker:
                self.by_worker.setdefault(int(worker.group(1)), {})[worker.group(2)] = value
            else:
                self.unrecognized.append(ref)

    def ids(self) -> set[int]:
        return set(self.bases) | set(self.by_worker)


# --- per-worker audit -------------------------------------------------------------

def audit_worker(ws: Path, state: WorkspaceState, canonical: Path, worker: WorkerRecord,
                 refs: NamespaceRefs) -> list[Issue]:
    """Documented ways this record can disagree with workspace, canonical, or filesystem state."""
    worker_id = int(worker.id)
    status = str(worker.status)
    issues: list[Issue] = []

    def issue(code: str, **context: Any) -> None:
        issues.append({"id": worker_id, "issue": code, **context})

    slot = worker_slot(ws, worker_id)
    repo = worker.repo
    owned_refs = refs.by_worker.get(worker_id, {})

    # Presence of the things each status owns.
    if status in _LIVE_ON_DISK or (status == WorkerStatus.BROKEN and os.path.lexists(slot)):
        if not os.path.lexists(slot) or (not slot.is_symlink() and not os.path.lexists(repo)):
            issue("worker-repository-missing", path=str(repo))
        else:
            try:
                verify_worker(state, worker)
            except ClonegrownError as exc:
                issue("worker-authentication-failed", path=str(repo), error=_short(str(exc)))
    if (status in WorkerStatus.ACTIVE and worker.owner_pid is not None
            and not process_alive(worker.owner_pid, worker.owner_start)):
        issue("owner-process-dead", error=f"{status} owned by process {worker.owner_pid}, which is gone; recover finishes or withdraws it")
    if status in WorkerStatus.TOMBSTONE:
        if os.path.lexists(slot):
            issue("tombstone-path-occupied", path=str(slot))
        if unrecorded_quarantine(ws, worker) is not None:
            issue("tombstone-quarantine-occupied", path=str(unrecorded_quarantine(ws, worker)))
        if worker.worktree_admin or worker.branch_cleanup_sha or worker.quarantine_path:
            issue("cleanup-evidence-retained")
    if status not in WorkerStatus.SPAWNING and worker.stage_root and os.path.lexists(worker.stage_root):
        issue("stage-residue", path=str(worker.stage_root))
    if status == WorkerStatus.DISCARDING:
        if worker.quarantine_error:
            issue("quarantine-preserved", path=str(worker.quarantine_path), error=_short(worker.quarantine_error))
        elif worker.quarantine_path and not os.path.lexists(worker.quarantine_path) and not os.path.lexists(slot):
            issue("deletion-incomplete", path=str(worker.quarantine_path))
        if worker.branch_cleanup_left or worker.worktree_admin_left:
            issue("cleanup-conflict", error=_short(worker.branch_cleanup_left or worker.worktree_admin_left or ""))
        if worker.error and worker.error.startswith("deletion incomplete") and not any(
                i["issue"] == "deletion-incomplete" for i in issues):
            issue("deletion-incomplete", error=_short(worker.error))

    # Base pin: required while spawning, stale once the worker is past it. A symbolic ref
    # under the name (dangling ones never appear in the listing) is foreign, not missing.
    pin = refs.bases.get(worker_id)
    pin_ref = state.base_ref(worker_id)
    if pin is None and pin_ref not in refs.symbolic and is_symbolic_ref(canonical, pin_ref):
        issue("namespace-ref-symbolic", ref=pin_ref, error="dangling symbolic ref under this worker's base pin name")
    elif status in WorkerStatus.SPAWNING and pin is None and pin_ref not in refs.symbolic:
        issue("base-ref-missing", ref=pin_ref)
    elif status in _PIN_DROPPED and pin is not None:
        issue("base-ref-stale", ref=pin_ref, value=pin)

    # Collected and normally discarded results remain in custody indefinitely:
    # the immutable ref is authoritative and the summary is its repairable pointer.
    if status in {WorkerStatus.COLLECTED, WorkerStatus.DISCARDED}:
        if not ref_points_at(canonical, worker.result_ref, worker.result_sha):
            issue("result-ref-missing", ref=str(worker.result_ref), value=str(worker.result_sha))
        summary = owned_refs.get("result")
        summary_ref = state.summary_ref(worker_id)
        if summary is None and summary_ref not in refs.symbolic and is_symbolic_ref(canonical, summary_ref):
            issue("namespace-ref-symbolic", ref=summary_ref, error="dangling symbolic ref under this worker's summary name")
        elif summary != worker.result_sha and summary_ref not in refs.symbolic:
            issue("summary-ref-mismatch", ref=summary_ref, value=summary)
    for name, value in owned_refs.items():
        if name.startswith("results/") and value != worker.result_sha and value != worker.candidate_sha:
            issue("candidate-ref-retained", ref=f"{state.ref_prefix}/workers/{worker_id}/{name}", value=value)

    # Worktree workers: branch, ownership ref, admin directory.
    if worker.is_worktree and status in _LIVE_ON_DISK:
        if resolve_ref(canonical, f"refs/heads/{worker.branch}") is None:
            issue("task-branch-missing", ref=f"refs/heads/{worker.branch}")
        if "branch-owner" not in owned_refs:
            issue("branch-owner-ref-missing", ref=branch_owner_ref(str(state.workspace_id), worker_id))
        if worker.worktree_admin and not os.path.lexists(worker.worktree_admin):
            issue("worktree-admin-missing", path=str(worker.worktree_admin))
    return issues


# --- workspace-level audit ----------------------------------------------------------

def audit_request_indexes(ws: Path, state: WorkspaceState, records: dict[int, WorkerRecord]) -> list[Issue]:
    issues: list[Issue] = []
    for index in sorted(ws_paths(ws)["requests"].glob("*.json")):
        try:
            entry = load_json(index)
        except ClonegrownError as exc:
            issues.append({"path": str(index), "issue": "request-index-invalid", "error": _short(str(exc))})
            continue
        request_id = entry.get("request_id")
        digest = entry.get("params_hash")
        worker_id = entry.get("worker_id")
        if (not isinstance(request_id, str) or not isinstance(digest, str)
                or type(worker_id) is not int or worker_id < 1 or request_path(ws, request_id) != index):
            issues.append({"path": str(index), "issue": "request-index-invalid"})
            continue
        worker = records.get(worker_id)
        if worker is None:
            issues.append({"path": str(index), "issue": "request-index-stale", "id": worker_id,
                           "error": "names a worker with no valid record"})
        elif worker.request_id != request_id or worker.params_hash != digest:
            issues.append({"path": str(index), "issue": "request-index-stale", "id": worker_id,
                           "error": "worker record does not point back at this request"})
    return issues


def audit_namespace(state: WorkspaceState, refs: NamespaceRefs, known_ids: set[int]) -> list[Issue]:
    issues: list[Issue] = []
    for ref in refs.symbolic:
        issues.append({"ref": ref, "issue": "namespace-ref-symbolic",
                       "error": "a symbolic ref under Clonegrown's namespace is never written through or deleted"})
    for ref in refs.unrecognized:
        issues.append({"ref": ref, "issue": "orphan-namespace-ref", "error": "unrecognized ref shape"})
    for worker_id in sorted(refs.ids() - known_ids):
        for ref, value in sorted(refs.values.items()):
            rest = ref[len(refs.prefix) + 1:]
            if rest == f"bases/{worker_id}" or rest.startswith(f"workers/{worker_id}/"):
                issues.append({"ref": ref, "issue": "orphan-namespace-ref", "id": worker_id, "value": value})
    return issues


def audit_stages(ws: Path, records: dict[int, WorkerRecord]) -> list[Issue]:
    """Staging entries no valid record owns; they block their id's allocation until moved away."""
    root = ws_paths(ws)["staging"]
    claimed = {os.path.abspath(str(w.stage_root)) for w in records.values() if w.stage_root}
    return [{"path": str(child), "issue": "orphan-stage"}
            for child in sorted(root.iterdir()) if os.path.abspath(str(child)) not in claimed]


def audit_lock_files(ws: Path, known_ids: set[int]) -> list[Issue]:
    issues: list[Issue] = []
    for lock in sorted(ws_paths(ws)["locks"].glob("*.lock")):
        stem = lock.stem
        if not re.fullmatch(r"(0|[1-9][0-9]*)", stem) or int(stem) not in known_ids:
            issues.append({"path": str(lock), "issue": "orphan-lock-file"})
    return issues
