# Architecture

Clonegrown is a single Python package with no runtime dependencies beyond the
standard library, Git, and Python 3.11+.

```text
clonegrown/
  __init__.py     public Python API: CWSError, init_workspace, spawn, collect, discard, recover, status
  __main__.py     python -m clonegrown
  cli.py          the installed `clonegrown` command (auto-discovery, redacted JSON output)
  legacy_cli.py   positional interface used by the research harnesses in tests/
  lifecycle.py    the four transactions: init, spawn, collect, discard
  recovery.py     recover (finish or roll back interrupted transactions) and status
  worker.py       worker identity markers, authentication, result snapshots, allocation
  repository.py   making a worker out of a clone (remotes, config, refs, sparse, alternates) or a linked worktree
  state.py        durable layout, schema validation, ref names, process ownership
  core.py         Git runner with environment sanitization, atomic JSON, failpoints, file locks
```

Dependencies point strictly downward: `cli` → `lifecycle`/`recovery` →
`worker` → `repository`/`state` → `core`. Every import is explicit.

## On-disk layout

For a canonical checkout `~/src/app`, the default workspace is `~/src/app-dev`:

```text
app-dev/
  .cws/
    state.json        workspace identity, canonical path, next worker id   (schema 3)
    lock              workspace-wide advisory lock
    workers/<id>.json one durable record per worker
    requests/<sha>.json  request-id → worker-id index for idempotent spawns
    locks/<id>.lock   per-worker operation lock
    staging/          clones under construction; moved into place atomically
  1/app/              worker 1 (an independent Git clone)
  2/app/              worker 2 (a linked worktree: its .git is a file pointing into app/.git/worktrees/)
```

The canonical repository carries `.git/cws/<workspace_id>.json`, binding it to
the workspace with a secret token. Each worker carries a `cws-worker.json`
marker in its private Git directory (`.git/` for a clone,
`app/.git/worktrees/<name>/` for a worktree). Both markers are checked before
any operation trusts a path from metadata.

## Worker modes

A worker record carries `mode`: `clone` (records from before this field
existed are clones) or `worktree`. The lifecycle, locking, metadata,
collection, deletion guards, and recovery are the same for both. What differs:

| | clone | worktree |
|---|---|---|
| created by | `git clone --no-checkout` (`--no-hardlinks` when strong) | `git worktree add --no-checkout --detach` |
| after the atomic rename into its slot | nothing | `git worktree repair` (recover repeats it if the spawn died in between) |
| provisioning | copy remotes, local config, auxiliary refs, info files, sparse policy | sparse policy only; a compatibility warning records what is shared |
| identity check | private git dir == common dir | private dir is `<canonical>/.git/worktrees/<name>`; common dir is canonical's; recorded `worktree_admin` matches |
| on discard | delete the directory | delete the directory, then its recorded admin directory and task branch in canonical |
| request-id digest | base, task, strong | base, task, strong, mode — so a retry cannot silently switch mode |

The admin directory is removed by path, never by `git worktree prune`, which
would also drop any of the user's own worktrees whose directories are
currently unreachable.

Inside the canonical repository Clonegrown owns refs under
`refs/cws/<workspace_id>/`:

- `bases/<id>` pins a worker's base commit against GC until the spawn is published;
- `workers/<id>/results/<sha>` is an immutable copy of each collected result;
- `workers/<id>/result` points at the most recent collected result.

## Worker states

```text
allocated → cloning → configuring → publishing → ready → collecting → collected → discarding → discarded
                                                   │                                 └→ abandoned
                                                   └→ spawn_failed        any verified-unsafe state → broken
```

Every transition is written to the worker's JSON record *before* the step it
describes, so a crash leaves a record that says exactly how far the operation
got. `recover` reads those records, checks whether the owning process is still
alive (PID plus Linux start-tick fingerprint), and either finishes the
operation or rolls it back to the last safe state. It never deletes a directory
it cannot authenticate as the worker the record describes.

## Safety properties

- Worker allocation and every metadata write happen under the workspace lock;
  each worker additionally has its own operation lock.
- A worker directory becomes visible only through one atomic rename from
  `.cws/staging`, so a visible worker is always complete.
- Collection snapshots the worker before and after fetching; a worker that
  changed in between is not accepted, but the fetched candidate is kept.
- Deletion requires a preserved result (`discard`), explicit intent
  (`--abandon`), or explicit acknowledgement of post-collection drift (`--force`).
  For worktree workers the task branch is deleted with the directory, so an
  abandoned worktree does not leave its commits reachable in canonical.
- Git helper calls strip process-level `GIT_*` overrides and never prompt.
- The canonical-source remote in each clone worker has an invalid push URL.

Clone workers isolate Git state; worktree workers share it by design. Neither
is an operating-system sandbox.

## Testing

- `tests/test_cli.py` — unit tests for the installed command.
- `tests/test_worktree.py` — worktree-mode lifecycle, guards, tampering, and
  crash recovery.
- `tests/hardening_suite.py` — 56 deterministic and adversarial cases, including
  every crash failpoint, run through `tests/legacy_cli.py`.
- `tests/run_crash_case.py`, `tests/random_kill.py` — single failpoint and
  SIGKILL campaigns.
- `tests/state_machine_fuzz.py` — randomized lifecycle sequences against the
  Python API.
- The remaining `tests/*.py` files are comparative probes (scaling, concurrency,
  GC, shared state, I/O faults).

`research/REPRODUCE.md` lists the exact commands.
