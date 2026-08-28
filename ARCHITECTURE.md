# Architecture

Clonegrown is a single Python package with no runtime dependencies beyond the
standard library, Git, and Python 3.11+.

```text
clonegrown/
  __init__.py     public Python API: ClonegrownError (plus CWSError compatibility alias), init_workspace, spawn, collect, discard, recover, status
  __main__.py     python -m clonegrown
  cli.py          the installed `clonegrown` command (auto-discovery, documented JSON output)
  lifecycle.py    the four transactions: init, spawn, collect, discard
  recovery.py     recover (finish or roll back interrupted transactions) and status
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
renames; the installer does not currently auto-reconcile those remnants. This
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
  1/app/              worker 1 (a local Git clone)
  2/app/              worker 2 (a linked worktree: its .git is a file pointing into app/.git/worktrees/)
```

The canonical repository carries `.git/cws/<workspace_id>.json`, binding it to
the workspace with a secret token. Each worker carries a `cws-worker.json`
marker in its private Git directory (`.git/` for a clone,
`app/.git/worktrees/<name>/` for a worktree). Collection and normal deletion
check this identity before mutating a published worker. Existing request-index
hits currently return stored records without equivalent validation or worker
authentication.

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

The current cleanup targets the recorded admin path rather than running
`git worktree prune`, which could also drop the user's own worktrees whose
directories are currently unreachable. It does not trust the path alone. Git recycles admin names
(`app`, `app1`, …) as soon as one is freed, so the path a tombstone recorded
may later belong to a newer worker. Before deleting, the directory must
identify as this worker (its `cws-worker.json` carries the worker's id and
token; before the marker exists, Git's `gitdir` back-pointer must point into
the worker's path), and once handled the recorded path is cleared from the
record so no later recovery can act on it. The worktree-mode fuzzer found
the original version of this deleting a live worker's admin directory.

Two related ownership gaps remain in the alpha. Worktree provisioning checks
out the deterministic task branch before Clonegrown has established whether
this invocation created it, but rollback later deletes that branch with
`branch -D`. Also, recovery of an interrupted published spawn can authenticate
the worker, observe that it changed from its base, and still delete it while
rolling back the spawn. Both are scheduled for remediation in `PLAN.md`.

Inside the canonical repository Clonegrown owns refs under
`refs/cws/<workspace_id>/`:

- `bases/<id>` pins a worker's base commit through spawn and its recovery;
- `workers/<id>/results/<sha>` is an immutable copy of each collected result;
- `workers/<id>/result` points at the accepted collected result.

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
directory it will act on; authentication alone does not protect work created
after an interrupted spawn was published, as described above.

## Command output

Every command prints JSON. The Python API returns the full record; the CLI
prints the record minus two kinds of field — secrets (`canonical_token`,
`worker_token`, `params_hash`) and transaction bookkeeping (owner, staging
and candidate fields, admin paths, snapshots) — with timestamps rendered as
ISO 8601 UTC strings. `tests/test_cli.py::test_output_contract` pins the
exact key sets for successful structured results. Command failures currently
include the complete subprocess argument vector, stdout, and stderr inside the
error text. Copied config values or credential-bearing remote URLs can
therefore appear in error output despite the normal record filtering.

A ready worker:

```json
{
  "id": 1, "status": "ready", "mode": "clone", "strong": false,
  "task": "fix auth race", "base": "HEAD", "base_sha": "…", "branch": "agent/<ws>/1-fix-auth-race",
  "path": "/…/app-dev/1/app", "request_id": null, "workspace_id": "…",
  "created": "2026-08-23T03:10:00Z", "ready": "2026-08-23T03:10:02Z",
  "source_remote": "cws-source", "alternates_detached": false,
  "copied_local_config": [], "copied_sparse_checkout": false, "copied_auxiliary_refs": {},
  "compatibility_warnings": []
}
```

Collection adds `allow_rewrite`, `result_sha`, `result_ref`, `collected`;
discard adds `discarded`. Failures carry `error` (spawn), `collection_error`
(collect) or `interrupted_error`. `status` returns `{workspace, canonical,
workspace_id, workers: [...], issues: [...]}` where a worker may also carry
`drift`; `recover` returns a list of `{id, action}` reports; `init` returns
`{status, workspace_id, workspace, canonical, object_format, repo_name,
created}`.

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
  remains under its immutable result ref. A writer can still race the interval
  after the second snapshot because there is no work lease.
- Normal deletion requires a preserved result. Deleting an uncollected worker
  requires `--abandon`, and detected post-collection drift requires `--force`.
  The drift snapshot omits ignored paths.
- Worker markers, workspace identity, and recorded tokens authenticate paths
  before collection and normal deletion trust them. An existing request-index
  hit currently returns its stored `WorkerRecord` without equivalent record
  validation or worker authentication. Worktree admin cleanup is targeted
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

The current deletion protocol authenticates a published worker and, for a
collected worker without `--force`, snapshots it. It then releases the
workspace lock, recursively deletes with `ignore_errors=True`, performs
worktree cleanup, and records a terminal state. It does not:

- enumerate or protect Git-ignored content;
- acquire a cooperative lease from external writers;
- quarantine the authenticated directory before deletion;
- surface a recursive-deletion error or verify final path absence;
- prove ownership of a pre-existing deterministic worktree branch before
  deleting that branch during rollback; or
- preserve work written to a published worker before interrupted-spawn
  recovery decides to roll it back.

Collection preserves a clean committed tip under an immutable Clonegrown ref.
It does not integrate the tip into a user branch. Current collection is
one-shot: an unchanged repeat is a no-op, while a changed collected worker is
rejected. Request-keyed spawn retries are idempotent only when the caller
supplies the same nonempty request ID and matching parameters; request-less
spawns allocate new workers.

## Target custody contract — planned, not implemented

The roadmap freezes the following contract for the remediation work. None of
the new lease, ignored-content acknowledgement, or quarantine mechanisms in
this section exist in the current schema or CLI yet.

1. Every published worker has a durable cooperative work lease. Normal and
   abandoned deletion require explicit lease release; `--force` does not
   silently override a live lease. Records predating the field are treated as
   leased.
2. Normal discard enumerates ignored content. A collected worker with ignored
   paths requires a separate `--discard-ignored` acknowledgement in addition
   to any acknowledgement of post-collection drift. `--abandon` applies only
   to an uncollected worker and authorizes abandoning all of its content.
3. Deletion authenticates the worker, records intent, atomically moves it to an
   authenticated quarantine path, rechecks it, deletes with errors enabled,
   verifies absence, cleans owned worktree state, and only then records a
   terminal status. Unexpected work remains quarantined and reported.
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
