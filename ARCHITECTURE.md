# Architecture

Clonegrown is a single Python package with no runtime dependencies beyond the
standard library, Git, and Python 3.11+.

```text
clonegrown/
  __init__.py     public Python API: ClonegrownError (plus CWSError compatibility alias), init_workspace, spawn, collect, discard, recover, status
  __main__.py     python -m clonegrown
  cli.py          the installed `clonegrown` command (auto-discovery, documented lifecycle output)
  lifecycle.py    the four transactions: init, spawn, collect, discard
  recovery.py     recover at represented lifecycle checkpoints, and status
  worker.py       one worker on disk: marker, authentication, snapshot, allocation, worktree removal
  repository.py   Git operations only: provisioning a clone, creating and repairing worktrees
  state.py        WorkspaceState and WorkerRecord (the two JSON records), WorkerStatus (the state machine)
  core.py         Git runner and environment construction, atomic JSON, failpoints, process liveness, file locks
```

Dependencies point strictly downward: `cli` → `lifecycle`/`recovery` →
`worker` → `repository`/`state` → `core`. Every import is explicit.

## Installer transaction

`install.sh` owns four replacement targets: the cloned source directory, the
generated command wrapper, the Claude skill directory, and the Codex skill
directory. A source or skill directory carries a `.clonegrown-install` marker;
the wrapper carries equivalent marker lines in its header. The version-one
format binds all four targets to the same random 128-bit installation ID. The
ID is ownership evidence, not an authentication secret.

The command wrapper passes the installation root to a small Python bootstrap as
one quoted argument. The bootstrap inserts that literal path at the front of
`sys.path` and runs `clonegrown.__main__`; it leaves the caller's `PYTHONPATH`
environment and its remaining module-search entries unchanged.

Before it clones or renames anything, the installer canonicalizes its paths,
rejects filesystem-root and home-directory targets, rejects direct target
symlinks and parent/child target overlaps, validates every existing target's
kind and marker, and requires all existing markers to carry one installation
ID. An absent target may be created. An existing unmarked target—including one
from the pre-marker installer—is not inferred to be Clonegrown-owned and is
refused. Raw and canonicalized paths containing a carriage return or newline
are also refused. The installer necessarily creates a private control directory
and record to run preflight; before it creates any destination parent or
installation artifact, a byte-oriented check requires exactly six
newline-terminated fields with no NUL or carriage-return bytes, and the shell
rejects missing, extra, or empty fields and any installation ID other than 32
lowercase hexadecimal characters.

Each replacement is staged in its destination's parent directory. Marker,
wrapper, skill, staging-directory, and parent-directory writes are fsynced
where the POSIX filesystem supports it. For an update, the installer reserves
a unique sibling backup, records its rollback state before each rename, moves
the old authenticated target to the backup, then publishes the staged target.
After all four published targets revalidate, the transaction commits and only
authenticated old backups are removed. Before that commit, command failures
and caught `HUP`, `INT`, or `TERM` unwind the four targets in reverse order.

For abandoned stages and the installer control directory, the installer
captures device, inode, and file type when each object is created. Cleanup
rechecks that identity and performs deletion inside one Python process; it does
not validate a pathname and then hand that name to a separately resolved
`rm`. A published stage's old name is revoked before rollback deletes the moved
object. Directory cleanup proceeds only when Python reports descriptor-relative,
symlink-attack-resistant `rmtree` support; otherwise it preserves the stage.
POSIX has no atomic “unlink this pathname only if it still has this inode”
operation, so this is not a sandbox against a hostile process running as the
same user and swapping a pathname between filesystem syscalls. Such a process
already has direct mutation authority over these user-owned destinations.

No shell trap can handle `SIGKILL` or machine power loss. Either can leave an
authenticated new target and/or its authenticated sibling backup between
renames, and a caught signal after the commit leaves the backups not yet
removed beside a complete installation; the installer does not currently
auto-reconcile those remnants. This
is narrower than the former behavior: it never treats an unmarked destination
as disposable and never derives an unchecked recursive-deletion target from
`CLONEGROWN_HOME`.

## On-disk layout

For a canonical checkout `~/src/app`, the default workspace is `~/src/app-dev`:

```text
app-dev/
  .cws/
    state.json        workspace identity, canonical path, next worker id   (schema 3)
    lock              workspace-wide advisory lock
    workers/<id>.json one durable record per worker
    requests/<sha>.json  request-id → worker-id index for request-keyed retries
    locks/<id>.lock   per-worker operation lock
    staging/          workers under construction; moved into place atomically
    quarantine/<id>-<token>/  a slot parked before final deletion; normally empty
  1/app/              worker 1 (a local Git clone)
  2/app/              worker 2 (a linked worktree: its .git is a file pointing into app/.git/worktrees/)
```

Every worker record is validated in one place (`WorkerRecord.validate`)
before any command lets it select a path or a Git ref: identity fields must
bind it to this workspace and slot; every present field must have the shape
its readers assume; each status has fields it requires and fields it must not
carry (a spawning record cannot name a result, a settled record cannot name an
operation owner); commit IDs must match the workspace object format; candidate
and result refs must equal the namespace derived from the workspace and
worker IDs; discard intent, lease, and quarantine fields must be mutually
consistent, and a quarantine path must equal the one derived from the worker's
identity. Fields no status names are checked for shape only, so records written
by earlier releases (including those without `mode`) keep loading, and unknown
keys round-trip untouched.

The canonical repository carries `.git/cws/<workspace_id>.json`, binding it to
the workspace with a secret token. Each worker carries a `cws-worker.json`
marker in its private Git directory (`.git/` for a clone,
`app/.git/worktrees/<name>/` for a worktree). Collection and normal deletion
check this identity before mutating a published worker. A request-index hit is
validated field by field and its settled worker authenticated on disk before
it is returned.

## Worker modes

A worker record carries `mode`: `clone` (records from before this field
existed are clones) or `worktree`. The same lifecycle commands and durable
state machine cover both. Their Git isolation and provisioning differ:

| | clone | worktree |
|---|---|---|
| created by | `git clone --no-checkout` (`--no-hardlinks` when strong) | `git worktree add --no-checkout --detach` |
| after the atomic rename into its slot | nothing | `git worktree repair` (recover repeats it if the spawn died in between) |
| provisioning | copy remotes, local config, auxiliary refs, info files, sparse policy | sparse policy only; a compatibility warning records what is shared |
| identity check | private git dir == common dir | private dir is `<canonical>/.git/worktrees/<name>`; common dir is canonical's; recorded `worktree_admin` matches |
| on discard | delete the directory | delete the directory, then its recorded admin directory and task branch in canonical |
| request-id digest | base, task, strong | base, task, strong, mode — so a retry cannot silently switch mode |

The CLI defaults to a non-strong clone. The current Python API instead defaults
`spawn(..., strong=True)`; callers should pass `strong` explicitly until the
documented mismatch is corrected. A default CLI clone has separate refs, stash,
local config, and a default private `.git/hooks` location, but Git may hard-link
its existing object files to the canonical repository. A strong clone uses
`--no-hardlinks`; a worktree shares the canonical repository's broad Git state
and object database.

Clone provisioning does not copy programs from the canonical repository's
private `.git/hooks` directory. `copy_local_config()` copies an effective
`core.hooksPath` value unless any value contains the canonical path's literal
text, in which case the whole key is omitted by the generic path-bound-config
guard. This is a substring check, not a filesystem-containment check. The
function copies only configuration values, never the directories or programs
they name.

An absolute `core.hooksPath` value receives the compatibility warning
`absolute core.hooksPath remains an external shared dependency` before the
generic omission check. A copied absolute value therefore remains shared, but
the warning can also accompany a value that the later substring check omitted.
Values such as `.githooks`, `~/hooks`, and `../../hooks` are not classified as
absolute and receive no hook-specific warning. Git resolves the first within a
normal worker checkout, while the latter two can resolve outside it and remain
shared dependencies. `--strong` changes object-file handling only and does not
change any of this hook behavior.

Cleanup targets the recorded admin path rather than running
`git worktree prune`, which could also drop the user's own worktrees whose
directories are currently unreachable. It does not trust the path alone. Git
recycles admin names (`app`, `app1`, …) as soon as one is freed, so the path a
tombstone recorded may later belong to a newer worker. Before deleting, the
directory must identify as this worker (its `cws-worker.json` carries the
worker's id and token; before the marker exists, Git's `gitdir` back-pointer
must point into the worker's path). Deletion runs with errors enabled and the
path is verified absent; only then is `worktree_admin` cleared. A failure
keeps the path and records why in `worktree_admin_left`, and the next
`recover` tries again. The worktree-mode fuzzer found the original version of
this deleting a live worker's admin directory.

The task branch has the same compare-and-swap ownership. Worktree
provisioning creates `refs/heads/<branch>` and the worker's private ownership
ref `refs/cws/<ws>/workers/<id>/branch-owner` in one `git update-ref --stdin`
transaction with create-only semantics, before checkout: a branch that
already exists under the deterministic name aborts both, untouched. Before
cleanup, discard records the branch's current tip (`branch_cleanup_sha`), or
the all-zero id if the branch is already absent. Cleanup deletes the branch
only when it was recorded at a real tip and still exists, in a transaction
that deletes it at that tip and deletes the ownership ref at its recorded
value, and only if no working tree other than the worker's own (canonical
itself included) has it checked out, since `update-ref` would leave such a
checkout on an unborn branch. A branch recorded absent, or absent now, is
nothing of the worker's: only the ownership ref is deleted and any branch
under the name is left alone. A moved or checked-out branch is retained,
`branch_cleanup_left` says why, and the record stays `discarding` until the
tip is moved back (`git update-ref refs/heads/<branch> <recorded tip>`), the
checkout released, or a stale entry for a deleted working tree pruned
(`git worktree prune`); `recover` then finishes. An admin directory name Git
has since recycled for another worker is likewise nothing of ours to clean. If the branch moved, the ownership ref changed, or no
ownership ref exists (a record from before this mechanism), both refs and the
evidence are retained and `branch_cleanup_left` says why; `status` shows it
and `recover` reports `worktree-cleanup-conflict` on every pass. The
ownership ref's value is read at cleanup time, so a change to it is detected
when it races the transaction, not when it happened earlier; the branch is
still only ever deleted at its recorded tip. Nothing is deleted by name
alone.

Recovery of an interrupted published spawn never deletes the worker. It
repairs a worktree's back-pointer, authenticates the directory, and promotes
an untouched worker (clean, on its task branch, `HEAD` at the recorded base,
no Git operation in progress) to `ready`. Anything else is marked `broken`
and preserved exactly as it is, with `error` naming the kind of difference
(uncommitted or untracked changes, `HEAD` moved, off the branch, operation in
progress) and never a path or content; its base pin, branch, and admin
directory stay until the user releases and abandons it. An unpublished spawn
is cleaned only through verified stage deletion and the ownership-checked
worktree cleanup above. If the process died between `git worktree add` and
the record write, recovery locates the admin entry by its `gitdir`
back-pointer into the worker's unique staged path, and acts only when exactly
one entry matches.

Inside the canonical repository Clonegrown owns refs under
`refs/cws/<workspace_id>/`:

- `bases/<id>` pins a worker's base commit through spawn and its recovery;
- `workers/<id>/results/<sha>` is an immutable copy of each collected result;
- `workers/<id>/result` points at the accepted collected result;
- `workers/<id>/branch-owner` proves a worktree worker created its task
  branch; it is created with the branch and deleted with it.

## Allocation and request indexes

Allocation is create-only. Before `next_id` advances, nothing may already
represent that id: a record, a slot directory, a stage or quarantine
directory, an operation lock file, a base pin, or any worker ref. A stale
counter is reported as corruption (`workspace counter is stale`) and nothing
is changed. The record is linked into place with `os.link`, which cannot
replace an existing file; a failure after the counter advanced withdraws only
the base pin this call made and leaves the id unused, an observable gap. A
request index is validated field by field before it is trusted: exact request
id, well-formed digest and worker id, an existing record that validates, and
that record's own request id and digest pointing back at the index. Before a
settled record is returned as a request's outcome, a `ready` or `collected`
worker is authenticated on disk, a collected result ref is verified, and a
gone worker is proved to have no slot and no quarantine residue; any
contradiction fails closed and `status` reports the index as stale or
invalid.

`recover` reconciles only what a record's status makes unambiguous: it
resumes quarantines, finishes ownership-checked branch and admin cleanup,
repairs a missing summary ref from a verified result ref, and drops a base
pin only for a worker whose status has no use for it and only at the recorded
base value (`base-ref-dropped`; any other value is `base-ref-ambiguous`).
Orphan namespace refs, orphan staging directories, stale or invalid request
indexes, and retained candidate refs are reported and kept; an orphan lock
file (an advisory control file for an id with no record, which would
otherwise block that id's allocation) is removed and reported. No operation
creates a lock file for an id that names no worker. Every write or deletion
of a ref under `refs/cws/<ws>/` uses `--no-deref` and is refused outright for
a symbolic ref: a symbolic ref planted under one of Clonegrown's names is
reported as `namespace-ref-symbolic`, excluded from every per-worker view,
and never used to reach the branch it points at. Recovery is idempotent and
continues past a corrupt record.

## Worker states

```text
allocated → cloning → configuring → publishing → ready → collecting → collected → discarding → discarded
                                                   │                                 └→ abandoned
                                                   └→ spawn_failed        any verified-unsafe state → broken
```

Operations write durable checkpoints around their major phases, but the
current record does not precede every irreversible filesystem or Git substep.
`recover` reads those checkpoints, checks whether the recorded owner process is
still alive (PID plus Linux start-tick fingerprint), and attempts to finish or
roll back the represented operation. Path authentication limits which worker
directory it will act on, and a published worker that changed after an
interrupted spawn is preserved as `broken`, as described above.

## Command output

Successful lifecycle commands (`init`, `spawn`, `collect`, `discard`,
`recover`, and `status`) print JSON to stdout. Help and `--version` print text
to stdout. Argument errors and Clonegrown runtime errors print text to stderr,
leave stdout empty, and exit with status 2.

For successful structured results, the Python API returns the full value; the
CLI removes two kinds of field — secrets (`canonical_token`, `worker_token`,
`params_hash`) and transaction bookkeeping (owner, staging and candidate
fields, admin paths, snapshots) — and renders timestamps as ISO 8601 UTC
strings. `tests/test_cli.py::test_output_contract` pins the exact key sets.
When a Clonegrown runtime error wraps a failed subprocess, its text currently
includes the complete argument vector, stdout, and stderr. Copied config values
or credential-bearing remote URLs can therefore appear on stderr despite the
normal structured-result filtering.

A ready worker:

```json
{
  "id": 1, "status": "ready", "mode": "clone", "strong": false,
  "task": "fix auth race", "base": "HEAD", "base_sha": "…", "branch": "agent/<ws>/1-fix-auth-race",
  "path": "/…/app-dev/1/app", "request_id": null, "workspace_id": "…",
  "created": "2026-08-23T03:10:00Z", "ready": "2026-08-23T03:10:02Z", "lease": "active",
  "source_remote": "cws-source", "alternates_detached": false,
  "copied_local_config": [], "copied_sparse_checkout": false, "copied_auxiliary_refs": {},
  "compatibility_warnings": []
}
```

Collection adds `allow_rewrite`, `result_sha`, `result_ref`, `collected`;
`release` sets `lease` to `released` and adds `lease_released`; `claim` sets it
back to `active`; discard adds `discarded`. Worker records may carry `error` after a spawn
failure, `collection_error` after a collection failure, or `interrupted_error`.
`status` returns `{workspace, canonical, workspace_id, workers: [...], issues:
[...]}` where a worker may also carry `drift`. `status` is a complete,
non-mutating audit: every issue has a stable `issue` code, the worker `id`
when one applies, and bounded context (`path`, `ref`, `value`, or a short
`error`), never file contents or configuration values. The codes are:
`invalid-worker-metadata`, `unexpected-metadata-file`,
`orphan-worker-directory`, `orphan-quarantine`, `orphan-lock-file`,
`orphan-namespace-ref`, `request-index-invalid`, `request-index-stale`,
`worker-repository-missing`, `worker-authentication-failed`,
`stage-residue`, `base-ref-missing`, `base-ref-stale`, `result-ref-missing`,
`summary-ref-mismatch`, `candidate-ref-retained`, `task-branch-missing`,
`branch-owner-ref-missing`, `worktree-admin-missing`, `quarantine-preserved`,
`deletion-incomplete`, `cleanup-conflict`, `cleanup-evidence-retained`,
`owner-process-dead`, `tombstone-path-occupied`,
`tombstone-quarantine-occupied`, `namespace-ref-symbolic`, and
`orphan-stage`. `status` runs Git only in read-only forms
(`--no-optional-locks status`, `rev-parse`, `for-each-ref`), so it does not
refresh a worker's index either. Two issues have a manual remedy by design:
a `request-index-invalid`/`request-index-stale` file blocks its request ID
until the named file under `.cws/requests/` is removed by hand, and a
`candidate-ref-retained` ref (a fetched candidate from a collection that did
not complete) is custody evidence that stays until a user deletes it.
`tests/test_audit.py` produces each of them and proves two consecutive
audits report the same thing and change nothing. `recover` returns a list of
`{id, action}` reports (plus `path`/`ref`/`error` context on some); `init` returns `{status, workspace_id, workspace,
canonical, object_format, repo_name, created}`.

## Implemented safeguards

- Worker allocation and transactional metadata updates use advisory workspace
  and per-worker locks. Those locks do not coordinate with an agent or another
  process writing directly inside the worker.
- Clone provisioning stages a worker and publishes its directory with an
  atomic rename. Worktree publication then requires Git repair and final
  checkout/configuration checkpoints; visibility alone does not prove that the
  worker reached `ready`.
- Collection snapshots the worker before and after fetching. A change detected
  in that interval is not accepted as collected, while the fetched candidate
  remains under its immutable result ref. The work lease is cooperative, so a
  writer that ignores it can still race the interval after the second
  snapshot.
- Every deletion requires a released lease. Normal deletion requires a
  preserved result; deleting an uncollected worker requires `--abandon`;
  detected post-collection drift requires `--force`; ignored paths, which the
  drift snapshot omits, are enumerated by name with
  `git ls-files -z --others --ignored --exclude-standard --directory` and
  require `--discard-ignored`. The refusal reports an exact count and a
  bounded sample of names, never contents.
- Worker markers, workspace identity, and recorded tokens authenticate paths
  before collection and normal deletion trust them. A request-index hit is validated field by
  field and its settled worker authenticated before it is returned. Worktree admin cleanup is targeted
  instead of using blanket pruning.
- Git commands run without an interactive prompt. Process-level `GIT_*`
  overrides are stripped when the configured executable's basename is
  literally `git`; a custom `CLONEGROWN_GIT` executable currently bypasses
  that detection.
- The canonical-source remote in each clone worker has an invalid push URL.
  This is a best-effort accident guard, not a security boundary.

Clone workers separate refs, stash, local config, and the default private hook
location, subject to the configured `core.hooksPath` caveats above. Their
existing object files may still be hard-linked unless `strong` is enabled.
Worktree workers share broad Git state by design. Neither mode is an
operating-system sandbox.

## Current alpha safety boundary

The deletion protocol requires a released lease, authenticates the published
worker, asks its separate acknowledgements (`--abandon`; `--force` and
`--discard-ignored` for a collected worker), records intent, fingerprints the
worker, quarantines it with one rename, rechecks it, deletes it with errors
enabled, proves the path absent, cleans the worktree state it is proved to
own, and only then records a terminal state. What it still cannot do:

- stop a process that ignores the cooperative lease or keeps file descriptors
  open across a release; such a writer can still race the final fingerprint;
- see a rewrite of a listed path that keeps its size and modification
  timestamp, or inspect a worker whose Git directory has been damaged so
  `status` fails (preserved as unverifiable, never deleted);
  the deletion unit is the slot `<workspace>/<id>/`, and entries beside the
  repository in it are fingerprinted but not inspected;
- resolve a moved or foreign task branch, an undeletable admin directory, or
  a preserved quarantine on its own; each is reported and left for the user.

Collection preserves a clean committed tip under an immutable Clonegrown ref.
It does not integrate the tip into a user branch. Current collection is
one-shot: an unchanged repeat is a no-op, while a changed collected worker is
rejected. Request-keyed spawn retries are idempotent only when the caller
supplies the same nonempty request ID and matching parameters; request-less
spawns allocate new workers. A request whose worker was `discarded` is
complete: retrying its ID returns that record rather than a new worker,
whereas an `abandoned` or `spawn_failed` outcome makes the ID retryable, also
when a retry observes that outcome while waiting on the original operation
(it then allocates afresh, up to three times). A `broken` outcome fails every
retry until that worker is released and abandoned. `status` and `recover`
verify canonical once per command and validate each record against it, so
their cost is one Git listing plus per-worker checks, not a re-verification
per record.

## Target custody contract — implemented

The roadmap froze the following contract for the remediation work; every item
is now implemented.

1. Every published worker has a durable cooperative work lease
   (implemented). The record's `lease` field is `active` or `released`; an
   absent field means leased, so records predating it default safe.
   `release` is allowed for a `ready`, `collected`, or `broken` worker and is
   idempotent; `claim` re-leases a released worker only while it is `ready`.
   `discard` checks the lease before `--abandon` or `--force`, so neither
   overrides it, and a failed spawn (which owns no directory) needs no release.
   Recovery never treats a dead owner process as a release: an interrupted
   abandonment of a leased worker is reset to its previous status and
   reported as `abandon-blocked-by-lease`, and a tombstone's re-occupied slot
   is reported by `status` and `recover`, never deleted. The lease is a handoff between
   cooperating callers, not an operating-system sandbox.
2. Normal discard enumerates ignored content (implemented). A collected
   worker with ignored paths requires a separate `--discard-ignored`
   acknowledgement in addition to any acknowledgement of post-collection
   drift; one refusal names every missing acknowledgement. `--abandon` applies
   only to an uncollected worker and authorizes abandoning all of its content.
   The custody inspection is separate from the collection snapshot and reads
   no file contents; its count is of entries as Git lists them, which can name
   an untracked directory of only-ignored files both as the directory and as
   its files.
3. Deletion authenticates the worker, records intent, atomically moves it to an
   authenticated quarantine path, rechecks it, deletes with errors enabled,
   verifies absence, cleans owned worktree state, and only then records a
   terminal status (implemented). The quarantine path is derived from the
   worker's id and token (`.cws/quarantine/<id>-<token>`), never read from the
   record; a symlinked quarantine directory, an occupied destination, or a
   rename the filesystem refuses is an error with no copy fallback. The
   custody fingerprint is `HEAD` plus a digest of Git's complete
   NUL-delimited status listing (`--untracked-files=all
   --ignored=traditional`), with the size, modification time, and type of
   every entry in the worker directory tree except `.git`, walked directly so
   that nested repositories, FIFOs, sockets, and anything else Git does not
   list are covered, and of every entry beside the repository in the slot; a quarantined worktree whose admin directory was
   pruned gets a Git-free walk fingerprint for its acknowledged deletion; the location and that fingerprint
   are persisted before the rename, so an interruption at any later point
   finds the quarantine described in the record. A crash before the rename
   withdraws a normal discard (the worker stays in place, `discard-reset`)
   and resumes an abandonment against the recorded fingerprint. Content found
   at a `discarding` worker's derived quarantine path that no record field
   names is adopted as a quarantine without a fingerprint: preserved,
   reported, and deleted only by a new acknowledged `discard`; at any other
   worker's derived path it is reported as an orphan. A worktree's back-pointer is repaired to the
   quarantined path before the recheck. A fingerprint mismatch, a repair or
   authentication failure, a deletion error, or an interruption leaves the
   record `discarding` with `quarantine_path` and `quarantine_error`; `status`
   reports it without touching it, `recover` resumes the same flow from the
   persisted fingerprint and reports `quarantine-preserved` when it still
   cannot proceed, and `discard` run again with the original acknowledgement
   (`--abandon`, or `--force` for a collected worker) takes a fresh fingerprint
   and deletes. A quarantine entry no record claims is reported as
   `orphan-quarantine` and never touched. Branch or admin-directory cleanup
   that cannot complete also keeps the record `discarding`, with the reason
   in `branch_cleanup_left` / `worktree_admin_left`.
4. A worker remains one-shot after collection. New work gets a new worker and
   cannot create a second accepted result for the old session.
5. Collection remains preservation, not integration. Merging, rebasing,
   cherry-picking, or updating a user branch is a separate explicit operation.

The implementation order and compatibility rules are in [`PLAN.md`](PLAN.md).

## Testing

`tests/` holds the unit tests; `tests/campaign/` holds the adversarial
harnesses and comparative probes that produced the evidence in `research/`.

- `tests/test_cli.py` — unit tests for the installed command.
- `tests/test_worktree.py` — worktree-mode lifecycle, guards, tampering, and
  crash recovery.
- `tests/campaign/hardening_suite.py` — 56 deterministic and adversarial cases, including
  its deterministic failpoint cases. The harnesses write the original prototype's positional
  command form; `tests/campaign/legacy_cli.py` translates it onto the real CLI. `CWS_SUITE_MODE=worktree`
  runs the same cases with worktree workers; the ten cases that assert clone
  isolation assert the documented sharing instead (and that the spawn warned
  about it). CI runs both modes.
- `tests/campaign/run_crash_case.py`, `tests/campaign/random_kill.py` — single failpoint and
  SIGKILL campaigns (`CWS_SUITE_MODE=worktree` for worktree workers).
- `tests/campaign/state_machine_fuzz.py` — randomized lifecycle sequences against the
  Python API (`CWS_SUITE_MODE=worktree` switches the invariants to the
  worktree contract, including "no task branch outlives its worktree").
- The remaining `tests/campaign/*.py` files are comparative probes (scaling, concurrency,
  GC, shared state, I/O faults).

`research/REPRODUCE.md` lists the exact commands.
