# Clonegrown plan

## Goal

Turn the validated alpha implementation into a conventional, explicit Python
package without changing its Git protocol, command-line behavior, durable
state, or safety guarantees — then, and only then, take on new product
behavior.

## Status

**The refactor is complete** (2026-08-22). The implementation is the
`clonegrown/` package described in `ARCHITECTURE.md`; the seven flat modules
and their wildcard import chain are gone.

Verified against the package on 2026-08-22, all with generated output kept
outside the checkout:

- 56/56 hardening cases (`tests/campaign/hardening_suite.py`);
- 11/11 collect/discard crash failpoints (`tests/campaign/run_crash_case.py`);
- 3/3 SIGKILL seeds, one per lifecycle mode (`tests/campaign/random_kill.py`);
- 2/2 state-machine fuzz seeds × 40 steps (`tests/campaign/state_machine_fuzz.py`,
  runnable again — it now drives the package API instead of the lost `cws`);
- 3/3 unit tests; wheel build + isolated install; `clonegrown --version`,
  `python -m clonegrown`; installer run into a throwaway `HOME`.

The same baseline (56/56, 3/3) was recorded against the flat modules at
commit `5d1cd58` immediately before the move, so the package is verified
equivalent on every check the repository has.

### What changed beyond pure movement

Deliberate, small departures from "move only", each checked by the suite:

- Root-level `clonegrown_*.py` compatibility shims were **not** kept. Nothing
  outside this repository imported them, and shims would have recreated the
  coupling the refactor removes. The research harnesses go through
  `tests/campaign/legacy_cli.py` → `clonegrown.legacy_cli`.
- `copy_replace_refs` was removed: it was never called (`copy_auxiliary_refs`
  already covers `refs/replace/`).
- `recover` is now one small class with one method per worker status, instead
  of a 180-line function. Every recovery path clears stale `owner_pid` /
  `owner_start` fields on terminal transitions; two paths previously left them
  behind, harmlessly.
- The installed CLI gained `--version` and help text on every flag.
- `run_crash_case.py` honours `CWS_CRASH_RESULTS_PATH`; default harness output
  paths under `tests/campaign/` are git-ignored.

### Still true

- The historical campaign in `research/` is evidence for the frozen `cws.py`
  candidate, not a rerun; `research/REPRODUCE.md` separates the two.
- `repository.copy_auxiliary_refs` still eagerly fetches every remote-tracking
  ref, note, and replace ref into each worker. Its performance on ref-heavy
  repositories has not been remeasured; see product decision 1.
- No runtime dependency was added, and none is planned.

## Worktree mode (decided and built, 2026-08-22)

Decision 2 below was resolved: Clonegrown is a **workspace manager**, not a
clone-only tool. The custody lifecycle (idempotent spawn, verified collection,
guarded deletion, recovery) was the most proven and most broadly useful part
of the project and is not inherently about clones, so it now runs over either
kind of worker:

- `clonegrown spawn --worktree` creates a linked worktree worker;
  `spawn(..., mode="worktree")` in the API. Clone remains the default.
- Worker records carry `mode`; pre-existing records without it are clones and
  still validate (the request-id digest includes `mode` only when it is not
  `clone`, so old digests are unchanged).
- Covered by `tests/test_worktree.py` (11 cases incl. crash at
  `spawn.after_publish`, `spawn.after_checkout`, `discard.after_delete`); the
  56-case clone suite is unchanged and still passes.
- Documented in `ARCHITECTURE.md` ("Worker modes") and the README's
  "Three kinds of worker" table.

### Worktree adversarial campaign (2026-08-22)

Every harness takes `CWS_SUITE_MODE=worktree`. Results on the current code:

- hardening suite: 56/56 worktree, 56/56 clone (CI runs both);
- state-machine fuzzer: 6/6 worktree seeds × 50 steps, 3/3 clone seeds;
- SIGKILL campaign: 6/6 worktree seeds (two per lifecycle mode);
- the concurrent-`gc` fixture reproduced the historical 1/8 in worktrees
  versus 8/8 in clones, now a current measurement.

The campaign found one real defect before it shipped: Git recycles worktree
admin-directory names, and tombstone cleanup deleted the recorded admin path
on every later `recover`, destroying a newer worker that had inherited the
name. Fixed by proving ownership (marker id+token, or Git's `gitdir` pointer)
before any admin-dir deletion and clearing the path from the record once
handled; `tests/test_worktree.py` pins the scenario.

Known, measured, not fixed: eight parallel worktree spawns run ~6.6× one
spawn (clones: well under 5.5×) because the lock-held metadata phases
dominate when creation itself is near-free. Shortening those critical
sections is a possible follow-up, not a correctness problem.

## Product decisions still open

Each requires an explicit decision and its own plan before code changes.

1. **Auxiliary-ref policy.** First rerun a ref-heavy benchmark against the
   current package. Then choose which remote-tracking refs workers truly need
   and whether to narrow the fetch, compact refs, or combine both. This can
   change offline worker semantics and cannot be smuggled into cleanup work.
2. **Clone tool or workspace manager.** Resolved and hardened: workspace
   manager; see "Worktree mode" above.
3. **Preflight recommendations.** Decide whether the CLI merely reports
   repository facts or recommends a mode. Any thresholds need new measurements
   across real repositories; the historical results from one machine are not a
   sufficient universal policy.
4. **Repository bootstrap contract.** Define how a repository opts in, which
   setup steps may run, what trust is required before they run, what files they
   may change, and what failure means. Submodules, dependencies, generated code,
   databases, and private Git configuration all depend on this contract.
5. **Platform scope.** Decide whether the supported product stays POSIX-only or
   gains native Windows support. Windows requires a replacement for `fcntl`
   plus path, locking, deletion, crash, and filesystem tests. Git LFS,
   network/distributed filesystems, and disk/inode exhaustion remain separate
   validation gaps.
6. **Live-agent evidence.** Design and run the paired A/B experiment described
   in `research/REPORT.md` before claiming that clones reduce real agent
   mistakes or human intervention relative to worktrees.
7. **Historical harness restoration.** If the original `cws.py`, raw JSONL
   rows, or missing probes are recovered later, preserve them byte-for-byte and
   verify their provenance. Do not recreate files and label them as original
   campaign artifacts. A current-only replacement harness must be named and
   reported as a new experiment.

## Maintainability pass (2026-08-23)

A fresh read of the package after the worktree work found no logic defects
but plenty of generated-code drift: two product names, stale help text,
string-keyed dicts as the data model, pieces living in the wrong module
with lazy imports to compensate, duplicated guards, a second CLI kept only
for the harnesses, and an output shape nobody had designed. Five phases,
each verified by the full campaign in both modes:

1. Product strings and names (`ClonegrownError`, `PROTOCOL_NAME`,
   `CLONEGROWN_GIT`, `--help` text).
2. `WorkerRecord` / `WorkspaceState` dataclasses; `WorkerStatus` owns the
   state machine.
3. Each piece in its home: liveness in core, worktree removal in worker,
   repository.py pure Git; one rollback guard; no lazy imports.
4. `clonegrown/legacy_cli.py` deleted; `tests/campaign/legacy_cli.py` translates the
   harnesses' positional form onto the real CLI. Worktree provisioning no
   longer rewrites shared sparse config.
5. A documented CLI output contract (ARCHITECTURE.md "Command output"),
   pinned by `test_output_contract`.

Deliberately kept: `params_hash` includes `mode` only for non-clone
workers. Removing that needs a schema bump plus a migration of every v3
record and request-index entry — more machinery than the one-line
conditional it would replace. Also kept: `tests/campaign/hardening_suite.py`'s
one-liner style; it is the evidence base and rewriting it risks changing
what it tests.

Measured, not fixed: each spawn makes ~64 Git subprocess calls, 17 of them
`rev-parse --git-common-dir`, because canonical is fully re-verified five
times per spawn under the workspace lock. That is what makes eight parallel
spawns ~4× (clone) to ~6× (worktree) one spawn. Caching the verification
within one transaction is the obvious follow-up.

The next work is one of the open product decisions above; none is in
progress.
