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

- 56/56 hardening cases (`tests/hardening_suite.py`);
- 11/11 collect/discard crash failpoints (`tests/run_crash_case.py`);
- 3/3 SIGKILL seeds, one per lifecycle mode (`tests/random_kill.py`);
- 2/2 state-machine fuzz seeds × 40 steps (`tests/state_machine_fuzz.py`,
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
  `tests/legacy_cli.py` → `clonegrown.legacy_cli`.
- `copy_replace_refs` was removed: it was never called (`copy_auxiliary_refs`
  already covers `refs/replace/`).
- `recover` is now one small class with one method per worker status, instead
  of a 180-line function. Every recovery path clears stale `owner_pid` /
  `owner_start` fields on terminal transitions; two paths previously left them
  behind, harmlessly.
- The installed CLI gained `--version` and help text on every flag.
- `run_crash_case.py` honours `CWS_CRASH_RESULTS_PATH`; default harness output
  paths under `tests/` are git-ignored.

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

Not yet done for worktree mode: the adversarial campaign (symlink/tamper
matrix, SIGKILL runs, fuzzer) has only been run against clone workers.
Extending `tests/hardening_suite.py` to parametrize over mode is the next
testing step.

## Product decisions still open

Each requires an explicit decision and its own plan before code changes.

1. **Auxiliary-ref policy.** First rerun a ref-heavy benchmark against the
   current package. Then choose which remote-tracking refs workers truly need
   and whether to narrow the fetch, compact refs, or combine both. This can
   change offline worker semantics and cannot be smuggled into cleanup work.
2. **Clone tool or workspace manager.** Resolved: workspace manager; see
   "Worktree mode" above. Remaining follow-up is test parity for worktree
   workers.
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

The next executable work is **worktree test parity**: parametrize the
hardening suite over worker mode and run the SIGKILL and fuzz campaigns with
worktree workers. After that, the open product decisions above.
