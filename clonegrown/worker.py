"""One worker on disk: its identity marker, authentication, result snapshot, allocation, and removal."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .core import (
    PROTOCOL_NAME, ClonegrownError, atomic_json, atomic_json_create, failpoint, git, git_bytes, git_common_dir,
    git_dir, git_path, lexical_abs, load_json, object_format, repo_root,
)
from .repository import (
    absent_marker, delete_ref, is_symbolic_ref, ref_points_at, release_task_branch, repair_worktree, resolve_ref,
    write_ref,
)
from .state import (
    SCHEMA, WorkerRecord, WorkerStatus, WorkspaceState, base_pin_ref, branch_owner_ref, params_hash, quarantine_root,
    request_path, staging_root, validate_control_dir, worker_lock_path, worker_marker_path, worker_record_path,
    worker_slot, workspace_lock, ws_paths,
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


def verify_worker(state: WorkspaceState, worker: WorkerRecord, require_exists: bool = True,
                  repo: Path | None = None) -> Path:
    """Authenticate the on-disk worker against its record before touching it.

    ``repo`` overrides the recorded path for a worker that has been moved to
    quarantine; the identity checks are the same either way.
    """
    repo = worker.repo if repo is None else repo
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
    # --no-optional-locks: observe without refreshing the index, so status/audit never write.
    dirty = git(repo, "--no-optional-locks", "status", "--porcelain=v1", "--untracked-files=all").stdout
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


def describe_divergence(state: WorkspaceState, worker: WorkerRecord) -> str | None:
    """How an authenticated worker differs from a freshly published one, or None if it does not.

    Names the kind of difference (dirty tree, HEAD moved from the base, HEAD
    off its task branch, an in-progress Git operation) without naming any
    path or content.
    """
    repo = worker.repo
    reasons: list[str] = []
    if git(repo, "--no-optional-locks", "status", "--porcelain=v1", "--untracked-files=all").stdout.strip():
        reasons.append("working tree has uncommitted or untracked changes")
    operations = operations_in_progress(repo)
    if operations:
        reasons.append("Git operation in progress: " + ", ".join(operations))
    head = git(repo, "rev-parse", "--verify", "--quiet", "HEAD", check=False).stdout.strip()
    if head != worker.base_sha:
        reasons.append(f"HEAD moved from the recorded base to {head or 'no commit'}")
    sym = git(repo, "symbolic-ref", "-q", "HEAD", check=False)
    if sym.returncode or sym.stdout.strip() != f"refs/heads/{worker.branch}":
        reasons.append("HEAD is detached or not on the assigned task branch")
    return "; ".join(reasons) or None


# --- custody inspection before deletion ---------------------------------------

IGNORED_SAMPLE_LIMIT = 5


@dataclass(frozen=True)
class IgnoredContent:
    """What Git-ignored paths a worker holds: an exact count and a bounded sample of names, never contents."""
    count: int
    sample: tuple[str, ...]

    def describe(self) -> str:
        shown = ", ".join(self.sample)
        more = f", and {self.count - len(self.sample)} more" if self.count > len(self.sample) else ""
        return f"{self.count} ignored path{'s' if self.count != 1 else ''} ({shown}{more})"


def inspect_ignored_content(repo: Path) -> IgnoredContent:
    """Enumerate ignored paths the collection snapshot never sees, so deletion can ask about them.

    Uses Git's own ignore evaluation (``.gitignore`` files, ``info/exclude``,
    and the global excludes file) through its NUL-delimited listing. An
    ignored directory is reported as one entry ending in ``/``; nothing is
    opened or read.
    """
    raw = git_bytes(repo, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory")
    names = [os.fsdecode(item) for item in raw.split(b"\0") if item]
    names.sort()
    return IgnoredContent(count=len(names), sample=tuple(names[:IGNORED_SAMPLE_LIMIT]))


# --- deletion through quarantine ------------------------------------------------

def _status_paths(listing: bytes) -> list[bytes]:
    """Paths named by a NUL-delimited ``status --porcelain=v2 -z`` listing.

    Ordinary, untracked, and ignored entries end in their path; a rename or
    copy entry (``2``) is followed by one extra NUL-terminated original path.
    """
    paths: list[bytes] = []
    tokens = listing.split(b"\0")
    index = 0
    while index < len(tokens):
        entry = tokens[index]
        index += 1
        if not entry:
            continue
        kind = entry[:1]
        if kind in (b"?", b"!"):
            paths.append(entry[2:])
        elif kind == b"1" or kind == b"u":
            paths.append(entry.split(b" ", 8 if kind == b"1" else 10)[-1])
        elif kind == b"2":
            paths.append(entry.split(b" ", 9)[-1])
            index += 1  # the original path of the rename
    return paths


def custody_fingerprint(repo: Path) -> dict[str, Any]:
    """What the worker holds right now, without reading contents.

    HEAD, Git's complete NUL-delimited status listing (tracked changes, every
    untracked and ignored file), and the ``lstat`` size, modification time,
    and type of every entry in the worker directory tree except its ``.git``
    (walked directly, so nested repositories, FIFOs, sockets, and anything
    else Git does not list are covered) and of every entry beside the
    repository in its slot. A path added, removed, or rewritten in place
    changes the fingerprint; a rewrite that keeps the same size and
    modification timestamp does not, which is the residual gap the README
    states. A worker whose Git directory no longer works (a quarantined
    worktree whose admin directory was pruned) gets a Git-free fingerprint:
    the walk alone, marked ``"listing": "walk"``.
    """
    slot = repo.parent
    head: str | None = None
    try:
        head = git(repo, "rev-parse", "--verify", "--quiet", "HEAD", check=False).stdout.strip() or None
        listing = git_bytes(repo, "--no-optional-locks", "status", "--porcelain=v2", "-z", "--untracked-files=all",
                            "--ignored=traditional")
        mode = "git"
        digest = hashlib.sha256(listing)
    except ClonegrownError:
        mode = "walk"
        digest = hashlib.sha256(b"walk")
    entries: list[tuple[bytes, Path]] = [(os.fsencode(child.name), Path(child.name))
                                         for child in repo.iterdir() if child.name != ".git"]
    for sibling in sorted(slot.iterdir()):
        if sibling.name != repo.name:
            entries.append((b"../" + os.fsencode(sibling.name), Path("..") / sibling.name))
    for raw, relative in _walk_below(repo, entries):
        try:
            value = os.lstat(repo / relative)
            record = f"{value.st_size}:{value.st_mtime_ns}:{stat.S_IFMT(value.st_mode)}".encode("ascii")
        except OSError:
            record = b"absent"
        digest.update(raw + b"\0" + record + b"\0")
    return {"head": head, "listing": mode, "status_digest": digest.hexdigest()}


def _walk_below(repo: Path, entries: list[tuple[bytes, Path]]) -> list[tuple[bytes, Path]]:
    """The entries plus everything found below any that is a real directory, sorted; symlinks are not followed."""
    out: dict[bytes, Path] = {}
    pending = list(entries)
    while pending:
        raw, relative = pending.pop()
        if raw in out:
            continue
        out[raw] = relative
        try:
            if stat.S_ISDIR(os.lstat(repo / relative).st_mode):
                for child in os.scandir(repo / relative):
                    pending.append((raw.rstrip(b"/") + b"/" + os.fsencode(child.name), relative / child.name))
        except OSError:
            continue
    return sorted(out.items())


DELETION_AUTHORIZED = {"deleting": True}  # the custody check passed; what remains is finishing the deletion


def prepare_quarantine(ws: Path, worker: WorkerRecord) -> Path:
    """The identity-derived quarantine path for this worker, checked to be usable and free.

    The destination is derived, never read from the record. A quarantine
    directory that is not a real directory, or an occupied destination, is an
    error.
    """
    target = quarantine_root(ws, int(worker.id), str(worker.worker_token))
    parent = target.parent
    try:
        parent.mkdir(exist_ok=True)
    except OSError as exc:
        raise ClonegrownError(f"workspace quarantine directory cannot be created: {exc}") from exc
    mode = os.lstat(parent).st_mode
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise ClonegrownError("workspace quarantine directory is not a real directory")
    if os.path.lexists(target):
        raise ClonegrownError(f"quarantine path is already occupied: {target}")
    return target


def rename_into_quarantine(slot: Path, target: Path) -> None:
    """One rename; a rename the filesystem refuses (including a cross-device move) is an error, never a copy."""
    if stat.S_ISLNK(os.lstat(slot).st_mode):
        raise ClonegrownError("worker slot was replaced by a symlink")
    if os.path.lexists(target):
        raise ClonegrownError(f"quarantine path is already occupied: {target}")
    try:
        os.rename(slot, target)
    except OSError as exc:
        raise ClonegrownError(f"could not move worker slot to quarantine (no copy fallback): {exc}") from exc


def delete_verified(path: Path, label: str) -> None:
    """Recursive deletion with errors enabled, then proof that the exact path is absent."""
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise ClonegrownError(f"could not delete {label}: {exc}") from exc
    if os.path.lexists(path):
        raise ClonegrownError(f"{label} still present after deletion: {path}")


def delete_through_quarantine(ws: Path, state: WorkspaceState, worker: WorkerRecord, canonical: Path,
                              persist: Callable[[], None]) -> None:
    """Remove a ``discarding`` worker's content, proving each part gone before the next.

    Slot → quarantine (one rename, location persisted at once) → worktree
    back-pointer repair → authentication and fingerprint recheck against the
    pre-rename snapshot → verified deletion → stage cleanup. Any failure
    raises with the quarantine left in place; the record then carries
    ``quarantine_path`` and ``quarantine_error`` for ``status`` and a later
    ``recover`` or re-authorized ``discard``. ``persist`` saves the record
    under whatever lock the caller holds.
    """
    worker_id = int(worker.id)
    slot = worker_slot(ws, worker_id)
    if worker.quarantine_path is None and slot.exists():
        # Persist where the slot is about to go and what it holds before it moves, so an
        # interruption at any later point finds the quarantine described in the record.
        repo = verify_worker(state, worker)
        target = prepare_quarantine(ws, worker)
        worker.quarantine_path = str(target)
        worker.quarantine_started = time.time()
        worker.quarantine_snapshot = custody_fingerprint(repo)
        worker.quarantine_error = None
        persist()
    if worker.quarantine_path is not None:
        quarantine = Path(worker.quarantine_path)
        if not os.path.lexists(quarantine) and slot.exists():
            # Intent was recorded but the rename never happened (or failed): do it now. The
            # recheck below then compares the moved slot with the recorded fingerprint.
            failpoint("discard.before_delete")
            try:
                rename_into_quarantine(slot, quarantine)
            except ClonegrownError:
                clear_quarantine(worker)  # nothing moved; the caller returns the worker to its status
                persist()
                raise
            failpoint("discard.after_quarantine")
        if os.path.lexists(quarantine) and slot.exists():
            raise ClonegrownError(
                f"worker {worker_id} has content both in its slot and at its quarantine path {quarantine}; "
                "nothing is deleted until one of them is moved away by hand")
        if os.path.lexists(quarantine):
            if worker.quarantine_snapshot is None:
                raise ClonegrownError(
                    f"worker {worker_id} was found in quarantine at {quarantine} without a recorded custody "
                    "fingerprint; run discard again with its acknowledgement to delete it")
            if worker.quarantine_snapshot != DELETION_AUTHORIZED:
                # The custody question: is this still exactly what was authorized for deletion?
                repo = quarantine / str(state.repo_name)
                try:
                    repair_owned_worktree(canonical, worker, repo)
                    verify_worker(state, worker, repo=repo)
                except AdminDirectoryMissing as exc:
                    if worker.quarantine_snapshot.get("listing") != "walk":
                        raise ClonegrownError(
                            f"{exc}; run discard again with its acknowledgement to delete the quarantined copy "
                            "without Git inspection") from exc
                now = custody_fingerprint(repo)
                if now != worker.quarantine_snapshot:
                    raise ClonegrownError(
                        f"worker {worker_id} changed after its custody check; preserved in quarantine at {quarantine}")
                # From here on the content is being destroyed; a later resume must not re-ask the
                # custody question of a half-deleted directory. The path itself is derived from the
                # record's identity, so finishing the deletion needs no further authentication.
                worker.quarantine_snapshot = DELETION_AUTHORIZED
                persist()
                failpoint("discard.after_recheck")
            delete_verified(quarantine, "quarantined worker")
        elif slot.exists():
            raise ClonegrownError(f"worker {worker_id} slot reappeared after quarantine; nothing deleted")
        clear_quarantine(worker)
        persist()
    if worker.stage_root and os.path.lexists(worker.stage_root):
        delete_verified(Path(str(worker.stage_root)), "worker stage")
    failpoint("discard.after_delete")


def withdraw_discard(worker: WorkerRecord) -> None:
    """Return a discarding record whose deletion never moved anything to its previous status, intent withdrawn."""
    worker.status = worker.discard_previous or WorkerStatus.COLLECTED
    worker.discard_intent = None
    worker.discard_previous = None
    worker.discard_started = None
    worker.branch_cleanup_sha = None
    worker.release_ownership()
    clear_quarantine(worker)


def clear_quarantine(worker: WorkerRecord) -> None:
    worker.quarantine_path = None
    worker.quarantine_started = None
    worker.quarantine_snapshot = None
    worker.quarantine_error = None


def unrecorded_quarantine(ws: Path, worker: WorkerRecord) -> Path | None:
    """The worker's identity-derived quarantine path if something sits there that no record field names."""
    target = quarantine_root(ws, int(worker.id), str(worker.worker_token))
    return target if worker.quarantine_path is None and os.path.lexists(target) else None


def finish_deletion(canonical: Path, worker: WorkerRecord, persist: Callable[[], None]) -> bool:
    """After the content is proved gone, clean canonical's worktree state and record the terminal status.

    Returns False, leaving the record ``discarding`` with its evidence, when a
    task branch or admin directory could not be cleaned; ``recover`` retries.
    """
    forget_worktree(canonical, worker, persist)
    worker.release_ownership()
    if worktree_cleanup_conflict(worker):
        persist()
        return False
    # A worker preserved as broken after an interrupted spawn still holds its base pin; drop it
    # only at its recorded value, so a pin naming anything else stays for status to report.
    delete_ref(canonical, base_pin_ref(str(worker.workspace_id), int(worker.id)), str(worker.base_sha), check=False)
    worker.status = worker.discard_intent or WorkerStatus.DISCARDED
    worker.discarded = time.time()
    persist()
    return True


def orphan_quarantines(ws: Path, records: dict[int, WorkerRecord]) -> list[Path]:
    """Quarantine entries no record claims, by name or by derived identity; reported, never touched."""
    root = ws_paths(ws)["quarantine"]
    try:
        if not stat.S_ISDIR(os.lstat(root).st_mode):
            return [root]  # a symlink or file where the quarantine directory belongs
    except FileNotFoundError:
        return []
    claimed = {lexical_abs(w.quarantine_path) for w in records.values() if w.quarantine_path}
    # A discarding worker's derived path is its own even before the record names it.
    claimed |= {lexical_abs(quarantine_root(ws, int(w.id), str(w.worker_token)))
                for w in records.values() if w.status == WorkerStatus.DISCARDING}
    return sorted(child for child in root.iterdir() if lexical_abs(child) not in claimed)


# --- loading -----------------------------------------------------------------

def require_worker(ws: Path, worker_id: int) -> None:
    """Refuse an id that names no worker before anything (a lock file included) is created for it."""
    validate_control_dir(ws)
    if not worker_record_path(ws, worker_id).exists():
        raise ClonegrownError(f"unknown worker: {worker_id}")


def load_worker(ws: Path, worker_id: int) -> tuple[WorkspaceState, WorkerRecord, Path]:
    """Return the validated workspace state, the validated worker record, and the canonical path."""
    state = WorkspaceState.load(ws)
    canonical = state.verify_canonical()
    return state, load_worker_record(ws, state, worker_id), canonical


def load_worker_record(ws: Path, state: WorkspaceState, worker_id: int) -> WorkerRecord:
    """The validated record for ``worker_id`` against an already loaded and verified workspace state."""
    if not worker_record_path(ws, worker_id).exists():
        raise ClonegrownError(f"unknown worker: {worker_id}")
    worker = WorkerRecord.load(ws, worker_id)
    worker.validate(ws, state, worker_id)
    return worker


# --- allocation --------------------------------------------------------------

def allocation_evidence(ws: Path, state: WorkspaceState, canonical: Path, worker_id: int) -> list[str]:
    """Everything that already represents worker ``worker_id``: a stale counter must not overwrite any of it."""
    found: list[str] = []
    if worker_record_path(ws, worker_id).exists():
        found.append("record")
    if os.path.lexists(worker_slot(ws, worker_id)):
        found.append("slot directory")
    if any(ws_paths(ws)["staging"].glob(f"{worker_id}-*")):
        found.append("stage directory")
    if any(ws_paths(ws)["quarantine"].glob(f"{worker_id}-*")):
        found.append("quarantine directory")
    if os.path.lexists(worker_lock_path(ws, worker_id)):
        found.append("operation lock file")
    if resolve_ref(canonical, state.base_ref(worker_id)) is not None:
        found.append("base ref")
    elif is_symbolic_ref(canonical, state.base_ref(worker_id)):
        found.append("symbolic base ref")  # dangling symrefs are invisible to for-each-ref; ask Git directly
    if git(canonical, "for-each-ref", f"{state.ref_prefix}/workers/{worker_id}/", check=False).stdout.strip():
        found.append("worker refs")
    return found


def load_request_index(ws: Path, state: WorkspaceState, request_id: str, digest: str) -> WorkerRecord | None:
    """The validated worker a request index names, or None if the request is new.

    Every field of the index is checked, the record it names must validate,
    and that record must point back at the same request and parameters. A
    corrupt or stale index fails closed; ``status`` reports it.
    """
    index = request_path(ws, request_id)
    if not index.exists():
        return None
    entry = load_json(index)
    if entry.get("request_id") != request_id:
        raise ClonegrownError("request index does not name this request ID (hash collision or corruption)")
    stored_digest = entry.get("params_hash")
    if not isinstance(stored_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", stored_digest):
        raise ClonegrownError("request index parameter digest is malformed")
    if stored_digest != digest:
        raise ClonegrownError("request ID was reused with different base/task/isolation/mode parameters")
    worker_id = entry.get("worker_id")
    if type(worker_id) is not int or worker_id < 1:
        raise ClonegrownError("request index worker ID is malformed")
    if not worker_record_path(ws, worker_id).exists():
        raise ClonegrownError(f"request index names worker {worker_id}, which has no record")
    worker = WorkerRecord.load(ws, worker_id)
    worker.validate(ws, state, worker_id)
    if worker.request_id != request_id or worker.params_hash != digest:
        raise ClonegrownError(f"request index and worker {worker_id} disagree about the request")
    return worker


def authenticate_settled(ws: Path, state: WorkspaceState, worker: WorkerRecord, canonical: Path) -> None:
    """Before a settled record is handed back as a request's outcome, prove it still describes reality."""
    worker_id = int(worker.id)
    if worker.status == WorkerStatus.READY:
        verify_worker(state, worker)
    elif worker.status == WorkerStatus.COLLECTED:
        verify_worker(state, worker)
        if not ref_points_at(canonical, worker.result_ref, worker.result_sha):
            raise ClonegrownError(f"worker {worker_id} is recorded as collected but its result ref is missing or moved")
    elif worker.status in WorkerStatus.GONE:
        if os.path.lexists(worker_slot(ws, worker_id)):
            raise ClonegrownError(f"worker {worker_id} is recorded as gone but its slot still exists")
        if unrecorded_quarantine(ws, worker) is not None:
            raise ClonegrownError(f"worker {worker_id} is recorded as gone but content sits at its quarantine path")


def allocate_spawn(ws: Path, base: str, task: str, strong: bool, request_id: str | None,
                   mode: str = "clone") -> tuple[WorkerRecord, bool]:
    """Reserve a worker ID, pin its base commit, and write the ``allocated`` record.

    Returns ``(worker, created)``. With a request ID that already maps to a
    live or finished worker, that worker's record is returned unchanged.

    Allocation is create-only: before ``next_id`` advances, nothing may
    already represent that ID (record, slot, stage, quarantine, lock file,
    base ref, worker refs); a stale counter is a corruption to diagnose, never
    permission to overwrite. The record itself is linked into place with
    create-only semantics. A failure after the counter advanced leaves the ID
    unused, an observable gap, rather than reusing it.
    """
    with workspace_lock(ws):
        state = WorkspaceState.load(ws)
        canonical = state.verify_canonical()
        digest = params_hash(base, task, strong, mode)
        if request_id:
            existing = load_request_index(ws, state, request_id, digest)
            if existing is not None and existing.status not in WorkerStatus.RETRYABLE:
                return existing, False
            # A failed incomplete spawn may be retried under the same idempotency key.
        resolved = git(canonical, "rev-parse", "--verify", f"{base}^{{commit}}", check=False)
        if resolved.returncode:
            raise ClonegrownError(f"base does not resolve to a commit: {base}")
        base_sha = resolved.stdout.strip()
        worker_id = int(state.next_id)
        evidence = allocation_evidence(ws, state, canonical, worker_id)
        if evidence:
            raise ClonegrownError(
                f"workspace counter is stale: the next worker ID {worker_id} already has a "
                f"{', '.join(evidence)}; nothing was changed. Inspect with `clonegrown status` and repair "
                "the workspace state by hand")
        state.next_id = worker_id + 1
        state.save(ws)
        failpoint("allocate.after_state")
        token = secrets.token_hex(16)
        write_ref(canonical, state.base_ref(worker_id), base_sha, "0" * len(base_sha))
        failpoint("allocate.after_base_ref")
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
        try:
            atomic_json_create(worker_record_path(ws, worker_id), worker.to_json())
        except Exception:
            # The ID stays consumed (a visible gap); only the pin this call made is withdrawn.
            delete_ref(canonical, state.base_ref(worker_id), base_sha, check=False)
            raise
        failpoint("allocate.after_record")
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
        target = _pointer_target(admin, _read_pointer(admin / "gitdir"))
    except Exception:
        return False
    owned = {lexical_abs(worker.repo / ".git")}
    if worker.stage_root:
        owned.add(lexical_abs(Path(worker.stage_root) / worker.repo.name / ".git"))
    return target in owned


def repair_owned_worktree(canonical: Path, worker: WorkerRecord, repo: Path) -> None:
    """Point Git's admin entry at a moved worktree, but only an entry that identifies as this worker.

    ``git worktree repair`` rewrites the admin directory named by the moved
    checkout's ``.git`` file. Running it on content that merely looks like a
    worktree would redirect another worker's (or the user's) admin entry, so
    the pointer is authenticated first.
    """
    if not worker.is_worktree:
        return
    pointer = repo / ".git"
    try:
        if not stat.S_ISREG(os.lstat(pointer).st_mode):
            raise ClonegrownError("worktree worker's .git pointer is not a regular file")
        text = _read_pointer(pointer)
    except OSError as exc:
        raise ClonegrownError(f"cannot read worktree worker's .git pointer: {exc}") from exc
    if not text.startswith("gitdir:"):
        raise ClonegrownError("worktree worker's .git pointer is malformed")
    admin = _pointer_target(repo, text[len("gitdir:"):].strip())
    if admin.parent != git_common_dir(canonical) / "worktrees":
        raise ClonegrownError("worktree worker's .git pointer names a path outside the canonical worktrees directory")
    if not os.path.lexists(admin):
        raise AdminDirectoryMissing(
            f"worktree worker's admin directory {admin} is missing (pruned?); Git cannot inspect this checkout")
    if not _admin_belongs_to(admin, worker):
        raise ClonegrownError("worktree worker's .git pointer names an admin directory that is not this worker's")
    repair_worktree(canonical, repo)


class AdminDirectoryMissing(ClonegrownError):
    """A quarantined worktree's admin directory is gone: Git cannot read it, but the record still identifies it."""


def _read_pointer(path: Path) -> str:
    """A Git pointer file (``.git`` or an admin ``gitdir``) as text; its path bytes need not be UTF-8."""
    return os.fsdecode(path.read_bytes()).strip()


def _pointer_target(base_dir: Path, raw: str) -> Path:
    """A ``gitdir`` pointer as an absolute lexical path; Git ≥ 2.48 may write it relative to the file's directory."""
    candidate = Path(raw)
    return lexical_abs(candidate if candidate.is_absolute() else base_dir / candidate)


def adoptable_quarantine(ws: Path, state: WorkspaceState, worker: WorkerRecord, canonical: Path) -> Path | None:
    """An unrecorded occupant of this worker's derived quarantine path, if it authenticates as this worker.

    Raises when the path is occupied by something that does not; nothing
    there is ever touched, and the caller says so.
    """
    found = unrecorded_quarantine(ws, worker)
    if found is None:
        return None
    if worker_slot(ws, int(worker.id)).exists():
        raise ClonegrownError(
            f"worker {int(worker.id)}'s quarantine path {found} is occupied while its slot is still in place; "
            "nothing there was touched. Move the occupant away by hand, then run recover")
    repo = found / str(state.repo_name)
    try:
        repair_owned_worktree(canonical, worker, repo)
        verify_worker(state, worker, repo=repo)
    except ClonegrownError as exc:
        raise ClonegrownError(
            f"worker {int(worker.id)}'s quarantine path {found} is occupied by content that does not authenticate as "
            f"this worker ({exc}); nothing there was touched. Move it away by hand, then run recover") from exc
    return found


def locate_worktree_admin(canonical: Path, worker: WorkerRecord) -> Path | None:
    """Find the one admin directory whose ``gitdir`` back-pointer names this worker's own path.

    The staged path embeds the worker's private token, so a match is proof of
    ownership without a marker. Zero or several matches return None: an
    ambiguous or absent entry is never acted on.
    """
    root = git_common_dir(canonical) / "worktrees"
    if not root.is_dir():
        return None
    owned = {lexical_abs(worker.repo / ".git")}
    if worker.stage_root:
        owned.add(lexical_abs(Path(str(worker.stage_root)) / worker.repo.name / ".git"))
    matches: list[Path] = []
    for admin in root.iterdir():
        try:
            if stat.S_ISLNK(os.lstat(admin).st_mode) or not admin.is_dir():
                continue
            target = _pointer_target(admin, _read_pointer(admin / "gitdir"))
        except OSError:
            continue
        if target in owned:
            matches.append(admin)
    return matches[0] if len(matches) == 1 else None


def remove_worktree_admin(canonical: Path, admin: Path, worker: WorkerRecord) -> bool:
    """Delete one worktree's admin directory so Git forgets it; True if it was ours (or already gone).

    Deliberately not ``git worktree prune``: that would also drop any of the
    user's own worktrees whose directories happen to be unreachable. And
    never by path alone: the directory must identify as this worker. Deletion
    runs with errors enabled and the path is verified absent afterwards; a
    failure raises with the directory left for a later attempt.
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
    try:
        shutil.rmtree(admin)
    except OSError as exc:
        raise ClonegrownError(f"could not remove worktree admin directory: {exc}") from exc
    try:
        os.lstat(admin)
    except FileNotFoundError:
        return True
    raise ClonegrownError(f"worktree admin directory still present after deletion: {admin}")


def forget_worktree(canonical: Path, worker: WorkerRecord, persist: Callable[[], None] | None = None) -> None:
    """After a worktree worker's directory is gone, remove its admin dir and task branch from canonical.

    Each field is cleared only once its exact target is proved gone. The
    admin directory must identify as this worker and be verified absent. The
    task branch is deleted only in a ref transaction that verifies this
    worker's ownership ref and the branch tip recorded before cleanup
    (``branch_cleanup_sha``, persisted through ``persist`` first when the
    caller has not already stored it). A conflict retains both refs and the
    evidence, and is recorded in ``branch_cleanup_left`` /
    ``worktree_admin_left`` for ``status`` and ``recover`` to report.
    """
    if not worker.is_worktree:
        return
    if worker.worktree_admin is None:
        # The parent may have died after `git worktree add` created the admin directory but
        # before its path was persisted. Only an entry whose gitdir names this worker's own
        # unique staged (or published) path can be ours; anything else is left alone.
        located = locate_worktree_admin(canonical, worker)
        if located is not None:
            worker.worktree_admin = str(located)
            if persist is not None:
                persist()
    if worker.worktree_admin:
        try:
            ours = remove_worktree_admin(canonical, Path(worker.worktree_admin), worker)
        except ClonegrownError as exc:
            worker.worktree_admin_left = str(exc)[:1000]
        else:
            # Ours and gone, or recycled by Git for another worker (then nothing of ours is
            # left there to clean): either way the recorded path is finished with.
            worker.worktree_admin_left = None
            worker.worktree_admin = None
    _release_task_branch(canonical, worker, persist)


def _release_task_branch(canonical: Path, worker: WorkerRecord, persist: Callable[[], None] | None) -> None:
    branch = str(worker.branch)
    owner_ref = branch_owner_ref(str(worker.workspace_id), int(worker.id))
    if is_symbolic_ref(canonical, owner_ref):
        # Never ours: an ownership ref that points elsewhere proves nothing and is never touched.
        worker.branch_cleanup_left = "task branch retained: its ownership ref is a symbolic ref, which is not ours"
        return
    owner_sha = resolve_ref(canonical, owner_ref)
    if owner_sha is None:
        # Nothing proves this worker created the branch: never delete by name alone.
        if resolve_ref(canonical, f"refs/heads/{branch}") is not None:
            worker.branch_cleanup_left = "task branch retained: no ownership ref proves this worker created it"
        else:
            worker.branch_cleanup_left = None
        worker.branch_cleanup_sha = None
        return
    if worker.branch_cleanup_sha is None:
        # Never recorded (an interrupted spawn's cleanup): record the tip now, or its absence.
        worker.branch_cleanup_sha = resolve_ref(canonical, f"refs/heads/{branch}") or absent_marker(str(worker.base_sha))
        if persist is not None:
            persist()
    own_paths = {lexical_abs(worker.repo),
                 lexical_abs(quarantine_root(worker.repo.parent.parent, int(worker.id), str(worker.worker_token))
                             / worker.repo.name)}
    if worker.quarantine_path:
        own_paths.add(lexical_abs(Path(worker.quarantine_path) / worker.repo.name))
    if worker.stage_root:
        own_paths.add(lexical_abs(Path(str(worker.stage_root)) / worker.repo.name))
    conflict = release_task_branch(canonical, branch, owner_ref, owner_sha, worker.branch_cleanup_sha, own_paths)
    if conflict is None:
        worker.branch_cleanup_sha = None
        worker.branch_cleanup_left = None
    else:
        worker.branch_cleanup_left = conflict[:1000]


def worktree_cleanup_conflict(worker: WorkerRecord) -> bool:
    """Did the last cleanup leave a task branch or admin directory behind with its evidence?"""
    return bool(worker.branch_cleanup_left or worker.worktree_admin_left)
