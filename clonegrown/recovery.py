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

from .core import CWSError, atomic_json, git
from .state import (
    ACTIVE_SPAWN, base_ref, clear_owner, final_worker_root, process_alive, read_state,
    summary_ref, verify_canonical, worker_lock_path, workspace_lock, ws_paths,
)
from .core import file_lock
from .worker import load_worker_state, verify_worker, worker_snapshot

Report = dict[str, Any]


def _worker_files(ws: Path, reports: list[Report], bad_key: str) -> list[Path]:
    files = []
    for candidate in ws_paths(ws)["workers"].glob("*.json"):
        if candidate.stem.isdigit():
            files.append(candidate)
        else:
            reports.append({"path": str(candidate), bad_key: "unknown-metadata-file" if bad_key == "action" else "unexpected-metadata-file"})
    return sorted(files, key=lambda p: int(p.stem))


def _orphan_dirs(ws: Path, state: dict[str, Any], known_ids: set[int]) -> list[tuple[int, Path]]:
    canonical_slot = state.get("canonical_slot")
    return [(int(child.name), child) for child in ws.iterdir()
            if child.is_dir() and child.name.isdigit()
            and int(child.name) != canonical_slot and int(child.name) not in known_ids]


def _ref_points_at(canonical: Path, ref: Any, sha: Any) -> bool:
    if not ref:
        return False
    got = git(canonical, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    return got.returncode == 0 and got.stdout.strip() == sha


class _Recovery:
    """One worker's recovery; each ``_recover_<status>`` method handles one status."""

    def __init__(self, ws: Path, worker_id: int, mp: Path, state: dict[str, Any],
                 meta: dict[str, Any], canonical: Path, reports: list[Report]) -> None:
        self.ws, self.worker_id, self.mp = ws, worker_id, mp
        self.state, self.meta, self.canonical = state, meta, canonical
        self.reports = reports

    def report(self, action: str) -> None:
        self.reports.append({"id": self.worker_id, "action": action})

    def save(self, **fields: Any) -> None:
        self.meta.update(fields)
        clear_owner(self.meta)
        atomic_json(self.mp, self.meta)

    def mark_broken(self, error: str, action: str) -> None:
        self.save(status="broken", error=error[:1000])
        self.report(action)

    def drop_base_pin(self) -> None:
        git(self.canonical, "update-ref", "-d", base_ref(self.state, self.worker_id), check=False)

    def run(self) -> None:
        status = self.meta["status"]
        alive = process_alive(self.meta.get("owner_pid"), self.meta.get("owner_start"))
        if status in ACTIVE_SPAWN:
            self.report("active-spawn-alive") if alive else self._recover_spawn()
        elif status == "collecting":
            self.report("active-collect-alive") if alive else self._recover_collecting()
        elif status == "discarding":
            self.report("active-discard-alive") if alive else self._recover_discarding()
        elif status == "ready":
            self._recover_ready()
        elif status == "collected":
            self._recover_collected()
        elif status in {"discarded", "abandoned", "spawn_failed"}:
            self._recover_tombstone(status)

    def _recover_spawn(self) -> None:
        meta = self.meta
        final_repo = Path(meta["path"])
        final_root = final_worker_root(self.ws, self.worker_id)
        # A crash after the atomic publish but before ready metadata can be completed safely.
        try:
            if final_repo.exists():
                verify_worker(self.state, meta)
                if worker_snapshot(self.state, meta)["head"] == meta["base_sha"]:
                    details = meta.pop("pending_spawn_details", {})
                    self.save(status="ready", ready=time.time(), **(details if isinstance(details, dict) else {}))
                    self.drop_base_pin()
                    self.report("spawn-publish-finished")
                    return
        except Exception:
            pass
        shutil.rmtree(Path(meta.get("stage_root", "")), ignore_errors=True)
        if final_root.exists() and not final_repo.exists():
            self.mark_broken("allocated worker slot is occupied by an unrecognized path", "spawn-broken-slot-collision")
            return
        # Never delete a published path unless it authenticates as this incomplete worker.
        if final_repo.exists():
            try:
                verify_worker(self.state, meta)
                shutil.rmtree(final_root, ignore_errors=True)
            except Exception:
                self.mark_broken("unverified path exists after interrupted spawn", "spawn-broken-unverified-path")
                return
        self.drop_base_pin()
        self.save(status="spawn_failed", failed=time.time(), error="interrupted spawn recovered")
        self.report("spawn-cleaned")

    def _recover_collecting(self) -> None:
        meta = self.meta
        candidate, ref = meta.get("candidate_sha"), meta.get("candidate_ref")
        can_finish = bool(candidate) and _ref_points_at(self.canonical, ref, candidate)
        if can_finish:
            try:
                snap = worker_snapshot(self.state, meta, require_ancestry=not meta.get("allow_rewrite", False))
                can_finish = snap["head"] == candidate
            except Exception:
                can_finish = False
        if can_finish:
            git(self.canonical, "update-ref", summary_ref(self.state, self.worker_id), candidate)
            meta.update({"status": "collected", "result_sha": candidate, "result_ref": ref, "collected": time.time()})
            self.report("collect-finished")
        else:
            meta.update({"status": "ready", "collection_recovered": time.time()})
            self.report("collect-reset-ready")
        clear_owner(meta, "candidate_sha", "candidate_ref")
        atomic_json(self.mp, meta)

    def _recover_discarding(self) -> None:
        meta = self.meta
        final_root = final_worker_root(self.ws, self.worker_id)
        intent = meta.get("discard_intent", "discarded")
        if not final_root.exists():
            self.save(status=intent, discarded=time.time())
            self.report("discard-finished")
        elif intent == "abandoned":
            # Explicit abandonment is the durable intent. With the owner gone, verify
            # this is still our worker before completing the destructive cleanup.
            try:
                verify_worker(self.state, meta)
                shutil.rmtree(final_root)
                self.save(status="abandoned", discarded=time.time())
                self.report("abandon-finished")
            except Exception as exc:
                self.mark_broken(f"could not safely finish abandonment: {exc}", "abandon-marked-broken")
        else:
            # For a collected result, rollback is conservative: keep the worker if the
            # deletion never happened; the caller may retry discard.
            self.save(status=meta.get("discard_previous", "collected"))
            self.report("discard-reset")

    def _recover_ready(self) -> None:
        # Dirty files and detached HEAD can be ordinary in-progress agent work; recovery
        # must not relabel or destroy them. Only structural identity/branch loss is fatal.
        try:
            repo = verify_worker(self.state, self.meta)
            branch = git(repo, "rev-parse", "--verify", f"refs/heads/{self.meta['branch']}^{{commit}}", check=False)
            if branch.returncode:
                raise CWSError("assigned task branch is missing")
        except Exception as exc:
            self.mark_broken(str(exc), "ready-marked-broken")

    def _recover_collected(self) -> None:
        sha = self.meta.get("result_sha")
        if _ref_points_at(self.canonical, self.meta.get("result_ref"), sha):
            git(self.canonical, "update-ref", summary_ref(self.state, self.worker_id), sha)
        else:
            self.mark_broken("preserved result ref missing", "collected-marked-broken")

    def _recover_tombstone(self, status: str) -> None:
        stage = Path(self.meta.get("stage_root", ""))
        if str(stage) and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        # Tombstones own no published directory; an explicitly abandoned one may linger.
        final_root = final_worker_root(self.ws, self.worker_id)
        if status in {"discarded", "abandoned"} and final_root.exists():
            try:
                verify_worker(self.state, self.meta)
                shutil.rmtree(final_root, ignore_errors=True)
                self.report("tombstone-path-cleaned")
            except Exception:
                self.report("tombstone-unverified-path-left")
        self.drop_base_pin()


def recover(ws_path: Path) -> list[Report]:
    """Finish or roll back every interrupted operation whose owner has died. Safe to repeat."""
    ws = ws_path.resolve()
    reports: list[Report] = []
    with workspace_lock(ws):
        state = read_state(ws)
        verify_canonical(state)
        worker_files = _worker_files(ws, reports, "action")
        for wid, child in _orphan_dirs(ws, state, {int(p.stem) for p in worker_files}):
            reports.append({"id": wid, "path": str(child), "action": "orphan-worker-directory"})
    for mp in worker_files:
        worker_id = int(mp.stem)
        with file_lock(worker_lock_path(ws, worker_id), blocking=False) as acquired:
            if not acquired:
                reports.append({"id": worker_id, "action": "active-lock-held"})
                continue
            with workspace_lock(ws):
                try:
                    state, meta, canonical = load_worker_state(ws, worker_id)
                except CWSError as exc:
                    reports.append({"id": worker_id, "path": str(mp), "action": "corrupt-or-unreadable-metadata",
                                    "error": str(exc)[:1000]})
                    continue
                _Recovery(ws, worker_id, mp, state, meta, canonical, reports).run()
    return reports


def status(ws_path: Path) -> dict[str, Any]:
    """Describe the workspace, every worker record, and any inconsistencies found."""
    ws = ws_path.resolve()
    with workspace_lock(ws):
        state = read_state(ws)
        canonical = verify_canonical(state)
        issues: list[Report] = []
        files = _worker_files(ws, issues, "issue")
        for wid, child in _orphan_dirs(ws, state, {int(p.stem) for p in files}):
            issues.append({"id": wid, "path": str(child), "issue": "orphan-worker-directory"})
        workers = []
        for mp in files:
            worker_id = int(mp.stem)
            try:
                _, meta, _ = load_worker_state(ws, worker_id)
            except CWSError as exc:
                issues.append({"id": worker_id, "path": str(mp), "issue": "invalid-worker-metadata", "error": str(exc)})
                continue
            item = dict(meta)
            if meta.get("status") in {"ready", "collected"} and Path(meta.get("path", "")).exists():
                try:
                    snap = worker_snapshot(state, meta, require_ancestry=not meta.get("allow_rewrite", False))
                    if meta.get("status") == "collected" and snap["head"] != meta.get("result_sha"):
                        item["drift"] = "changed-after-collection"
                except Exception as exc:
                    item["drift"] = str(exc)
            workers.append(item)
        return {"workspace": str(ws), "canonical": str(canonical), "workspace_id": state["workspace_id"],
                "workers": workers, "issues": issues}
