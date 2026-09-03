# Clonegrown plan archive

> Archived 2026-09-02 by Phase 7 Step 7.2 from the pre-prune `PLAN.md`
> (SHA-256 `a19bf6fd4b6d62fea9b8880d8886dba94bc1c8cfb86ce151d6892cd4e6b5680b`).
> The transcript blocks below are verbatim from original lines 20–3062 and
> 3135–3144, in source order. Still-active decisions and product calls are
> also retained in
> the [current roadmap](../PLAN.md). This archive records provenance and
> completion history; it is not normative product documentation.

---

## Status

### 2026-09-02 — Phase 6 Step 6.7 is complete; Phase 6 is complete

Kyle explicitly selected the Apache License, Version 2.0 (`Apache-2.0`) for
Clonegrown. The previously nonexistent `LICENSE` now contains the canonical
Apache text byte-for-byte, at SHA-256
`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
PEP 639 package metadata declares the SPDX expression and license file;
Linux/macOS, Python 3.11–3.14, Python-3-only, developer-audience, console, and
alpha classifiers state the existing support boundary without adding a
deprecated license classifier. The build-only setuptools floor is 77.0.3,
the first version recorded by the Python Packaging User Guide as supporting
this metadata form. Runtime dependencies remain empty.

A filtered temporary source copy produced a pure-Python wheel and source
archive with setuptools 84.0.0. Each artifact carried Core Metadata 2.4,
`License-Expression: Apache-2.0`, `License-File: LICENSE`, `Requires-Python:
>=3.11`, the exact classifiers, and the canonical license bytes. Separate
CPython 3.12.3 environments installed the wheel directly and built/installed
the source archive in isolation; both command entry points, module entry
points, and public imports passed. The source regression passed 2/2.

No runtime product file, API, command behavior, durable schema or JSON,
installer behavior, workflow, architecture, installed skill, or preserved
research artifact changed. All Phase 6 Steps are now complete. Phase 7 Step
7.1 is already complete; the next unfinished roadmap work is Phase 7 Step 7.2.

### 2026-09-02 — Phase 7 Step 7.1 is complete; Step 6.7 was license-gated at this checkpoint

A source-backed audit synchronized the README, installed skill, architecture,
public package docstrings, command help, and current reproduction guide with
the implemented lease, quarantine, state, error, collection, and recovery
protocols. The corrected surfaces now distinguish published workers from
unpublished failed spawns, intact quarantine from residue after a partial
authorized delete, collection from user-selected integration, supported
request-ID retries from retryable terminal attempts, and the documented
`status` invariants from a general filesystem or security scan. They also
state the ignored-content, active-writer, worktree-sharing, clone-object,
one-shot collection, and represented-recovery boundaries literally.

Current-tree, hosted committed, and recovered historical experiment evidence
now carry separate commit, environment, and reproducibility labels. The
package dependency diagram includes the implemented audit module and its real
imports, while speed and physical-isolation descriptions are qualified by
repository, host, worker mode, and the absence of an operating-system sandbox.
No historical artifact was removed or recreated.

The executable product change is limited to CLI descriptions/help; Python
docstring changes affect introspection but not lifecycle control flow. One
focused CLI help-contract test was added, while two test comments and one test
module docstring were qualified without changing their assertions. Focused
verification passed 6/6 CLI, 6/6 public-API, and 20/20 audit/recovery tests.
Out-of-checkout byte compilation, preserved-research comparison, and
`git diff --check` also passed. No API signature, durable schema, JSON output,
dependency, workflow, lifecycle algorithm, or preserved evidence changed. At
this checkpoint Phase 6 Step 6.7 still required Kyle's explicit license
choice; Step 6.7 has since completed. The next roadmap work remains Phase 7
Step 7.2.

### 2026-08-29 — Phase 6 Step 6.8 is complete; Step 6.7 remains license-gated

A fresh read-only cold review of the complete local Phase 6 tree proved three
product defects: a canonical replacement after publication could receive the
old workspace's base-ref deletion, auxiliary-ref counts could race away from
the refs fetched, and locked reconciliation accepted a backward `next_id`
change that could reuse a consumed gap. Independent throwaway-repository probes
reproduced all three before any product edit. The repaired tree rematches
canonical identity before post-publication Git mutations, accepts only equal or
forward counter movement, and fetches the exact enumerated auxiliary-ref object
IDs through `git fetch --stdin`. Historical `heartbeat` data still round-trips
internally but remains absent from CLI JSON.

The final deterministic suite passed 226/226 on CPython 3.12.3 with Git 2.43.0
and again with exact Git 2.29.0. Both full hardening modes finished with 56
exercised passes, one conditional reftable skip, and zero failures. The
unchanged 4,096/256/256 benchmark passed all 15 scenarios: current clone median
was 3.335577 seconds with 4,612 total refs, 2 loose refs, 1 loose auxiliary ref,
and 20,344,832 allocated bytes. Five fresh call-count fixtures held clone at
64 total Git calls and worktree at 46, below the 73/53 pre-optimization
baselines. Preserved research evidence remains byte-identical. Step 6.7 is the
only unfinished Phase 6 Step and still requires Kyle's explicit license choice;
at that checkpoint, the next unblocked roadmap work was Phase 7 Step 7.1.

### 2026-08-29 — Phase 6 Step 6.4 checkpoint

The auxiliary-ref compatibility contract now preserves every resolvable
canonical name and object ID under `refs/remotes/`, `refs/notes/`, and
`refs/replace/`; it does not narrow correctness-sensitive notes or replace
refs. Two unchanged, order-rotated five-sample runs exercised 4,096
remote-tracking, 256 notes, and 256 replace refs in current clone, candidate
clone, and worktree control fixtures. The selected Step 6.5 policy combines all nonempty namespace
refspecs in one fetch and then packs clone refs, while never packing the shared
canonical refs of a worktree. Across the combined ten samples, the candidate
reduced the measured clone from 4,612 loose refs and 39,008,256 median
allocated Git-directory bytes to 2 and 20,342,784; median spawn moved from
2.979 to 3.373 seconds. All thirty scenarios passed every applicable
exact-ref, offline-semantic, metadata-count, and packed-update check; timing
remained observational. At that checkpoint Phase 6 Step 6.5 was next; Steps
6.5, 6.6, and 6.8 have since completed, while Step 6.7 remains blocked on the
license choice below.

### 2026-08-29 — Phase 6 Step 6.3 is complete

Canonical verification now runs immediately before, rather than while holding,
each allocation, cloning, configuring, and publishing workspace lock. The
locked code reloads and validates the workspace record, permits only the
concurrently owned `next_id` field to differ, and rechecks canonical root/Git
directory identity plus the direct identity marker before any serialized
mutation. Five fresh single-spawn and five fresh eight-way fixtures per mode
showed lower summed lock-held phase medians and lower eight-way wall medians;
single-spawn wall medians were noisier and slower, so the record below preserves
the raw ranges and makes no ratio or threshold claim. Forty unchanged race
campaigns passed, the complete suite passed 219/219, and both full hardening
modes passed with 56 exercised checks, one conditional reftable skip, and zero
failures. Steps 6.4, 6.5, 6.6, and 6.8 have since completed; Step 6.7 remains
blocked on the license choice below.

### 2026-08-29 — Phase 6 Step 6.2 is complete

A successful spawn now fully verifies canonical identity once in each of its
allocation, cloning, configuring, and publishing lock transactions, before
that transaction uses canonical. It reuses the publishing transaction's
verified value only until that uninterrupted lock block ends. Five fresh
fixtures per mode measured clone Git calls at 73 before and 66 after
(common-dir probes 17 to 14), and worktree calls at 53 before and 46 after
(common-dir probes 15 to 12). Focused replacement, marker-tamper, and spawn
crash coverage passed in both modes; the complete suite passed 217/217, and
both full hardening modes passed with 56 exercised passes, one conditional
reftable skip, and zero failures. Step 6.3 has since moved each full proof
immediately before its corresponding lock and added locked reconciliation;
Steps 6.4, 6.5, 6.6, and 6.8 have since completed; Step 6.7 remains blocked on
the license choice below.

### 2026-08-29 — Phase 6 Step 6.1 is complete

The runtime pause, hard-exit, and ordinary-error injection controls now use
`CLONEGROWN_TEST_*` names and are inert unless
`CLONEGROWN_TEST_MODE=1` is set exactly. Legacy `CWS_*` hook names are no
longer read. Current worker records no longer write the unused one-shot
`heartbeat`; a historical record carrying it still round-trips the key as
unknown extension data. Four standalone campaign programs were removed only
after their claims were mapped to current deterministic coverage:
`concurrency_v2.py`, `run_crash_case.py`, `shared_state_compare.py`, and
`io_fault_probe.py`. The scaling and concurrent-GC probes remain because their
measurements are not duplicated elsewhere. The full 215-test suite and both
57-case hardening modes pass; each hardening mode exercised 56 passes, one
conditional reftable skip, and zero failures. Phase 6 Step 6.2 has since
completed, as have Steps 6.3 through 6.6 and Step 6.8; Step 6.7 remains blocked
on the license choice below.

### 2026-08-29 — Phase 5 is complete

Kyle chose to run the remediation phases rather than the earlier
simulate/find-users/stop product choice. Phases 1 through 3 were each
cold-reviewed by a fresh agent and then bughunted, with every confirmed
finding fixed and re-reviewed in the same pass; Phase 4 closed with the same
fix-and-fresh-review discipline in Step 4.5. Phase 5 opened by separating its
machine-sensitive spawn measurements from deterministic concurrency
correctness in Step 5.1, then added real parent-only interruption coverage and
completed the lease/quarantine/cleanup crash matrices in Step 5.2. Step 5.3
put bounded randomized campaigns in a separate nightly/manual artifact lane
with exact seed replay. Step 5.4 defined the Linux/macOS,
Python 3.11-through-latest-stable, Git 2.29.0+ execution envelope, tested both
version endpoints locally on Linux, and kept native Windows explicitly
unsupported. Step 5.5 pinned one ordinary external clean/smudge-filter case
and the atomic-write, quarantine-rename, and partial-deletion failure
transitions while keeping Git LFS and genuine resource/filesystem failures
outside support. Step 5.6 passed six lifecycle/recovery scenarios across
pinned curl-history, Git-ref, and Git sparse/submodule profiles in both worker
modes and preserved the exact evidence under `research/`. Step 5.7 then
cold-reviewed the Phase 5 test and workflow layer, proved and repaired
false-green campaign behavior without changing product code, and passed its
local gates. The published tree has 212 passing unit tests; each
current-Git hardening mode reports 57 defined checks as 56 exercised passes,
one conditional reftable skip, and zero failures. Commit
`a2ae7793b5a3653435fde988f716558f74ce6b88` published all 24 Phase 5 paths.
Hosted deterministic CI run 33276649643 passed all seven jobs, and manually
dispatched randomized run 33277111128 passed all eight jobs at that exact
revision. All eight retained artifacts passed exact schema, provenance,
completion-status, and replay-command validation; the first recorded row from
each artifact replayed literally and passed. Phase 5 is closed. Phase 6 Steps
6.1 through 6.6 and Step 6.8 have since completed; Step 6.7 remains blocked on
the license choice below.

**The refactor is complete** (2026-08-22). The implementation is the
`clonegrown/` package described in `ARCHITECTURE.md`; the seven flat modules
and their wildcard import chain are gone.

Verified against the package on 2026-08-22, all with generated output kept
outside the checkout:

- 56/56 hardening cases (`tests/campaign/hardening_suite.py`);
- 11/11 collect/discard crash failpoints (the then-current
  `tests/campaign/run_crash_case.py`, superseded and removed in Step 6.1);
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
- At that checkpoint, `run_crash_case.py` honored `CWS_CRASH_RESULTS_PATH` and
  default harness output paths under `tests/campaign/` were git-ignored. Step
  6.1 later removed the wrapper after proving its cases were duplicated.

### Still true

- The historical campaign in `research/` is evidence for the frozen `cws.py`
  candidate, not a rerun; `research/REPRODUCE.md` separates the two.
- `repository.copy_auxiliary_refs` preserves every remote-tracking ref, note,
  and replace ref in clone workers. Since Step 6.5 it combines the nonempty
  wildcard refspecs in one fetch and immediately packs the staged clone; when
  all three classes are empty, it runs neither command. Worktree workers still
  share canonical refs without this operation.
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

The pre-Step-6.3 campaign measured lock-held metadata phases dominating
eight-way worktree spawn. Step 6.3 later remeasured and shortened those
critical sections; its completion record supersedes the earlier ratios without
turning timing into a correctness gate.

## Product decisions

Items marked open require an explicit decision and their own plan before code
changes.

1. **Auxiliary-ref policy.** Resolved by Step 6.4: preserve every promised
   remote-tracking, notes, and replace ref; combine their nonempty refspecs in
   one fetch; then pack clone refs. Step 6.5 owns implementation against the
   recorded compatibility and measurement gates.
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

### Cold refactor and one fix (2026-08-23)

A `/refactor` pass after the five phases (zero behavior change, verified
56/56 both modes): `ref_points_at` and `_check_out_base` shared,
`tests/support.py` for the unit tests, and the ten harnesses and probes
moved to `tests/campaign/` so `tests/` reads as unit tests + campaign. It
surfaced one bug, fixed in its own commit (`6798a5a`): a worktree's admin
directory was recorded one stage after Git created it, so a crash in the
`spawn.after_clone` window left a stale worktree entry recovery could not
see. Now persisted immediately; `test_crash_right_after_worktree_add_leaves_no_admin_dir`
pins it.

`main` at `6798a5a` is pushed; CI run 32617584688 passed all four jobs
(Linux, macOS, hardening clone, hardening worktree). Working tree clean.

## Where this stands and what next (2026-08-23)

Kyle's situation, stated plainly: he does not run multi-agent workflows and
has no tasks that need several workers, so he cannot dogfood this tool in
the sense of feeling its pain. He also does not want to experiment on this
repository (reasonable, though the blast radius is small: one marker under
`.git/cws/`, refs under `refs/cws/`, a sibling workspace folder).

Three honest options, none chosen yet:

A. **One-afternoon simulation** on a scratch clone of any project: ask
   Claude Code or Codex to act as orchestrator — split a job into three
   tasks, `clonegrown spawn --worktree` each, work, `collect`, `discard` —
   and watch whether the *agent* uses the CLI correctly from SKILL.md alone.
   Cheap, and the last thing that can still find a real flaw without users.
B. **Find the people who have the workflow** (multi-agent orchestrator
   users) and put the README in front of them. Outreach, not engineering.
C. **Call it finished as a research artifact.** Legitimate; nothing is
   wasted.

Recommendation on record: do A once, then choose B or C by whether Kyle
wants to find users. No engineering item should start before that, except
the measured throughput follow-up above if it ever matters.

## Engineering-review remediation roadmap (planned 2026-08-27)

This roadmap supersedes only the final "no engineering item should start"
sentence above. The product-direction choices and historical record remain
valid context, but the newly verified custody defects now take priority over
simulation, outreach, and performance work.

The standalone source-review artifact is not stored in this checkout. This
roadmap retains its verified starting state, findings, and decisions inline. It
was written against commit `2cd212c2cf76dd8bb9567b92341c6fb451ad375b`, which
was `HEAD` at the time.
The roadmap uses the Phase/Step vocabulary defined above. Every Step below
starts **pending**; completion adds `— complete YYYY-MM-DD` to its heading.
Step 6.7 is pending but blocked on the license choice stated there, so `$next`
skips it while any later unblocked Step remains.

### Verified starting state

Observed directly in the current checkout on 2026-08-27:

- The working tree was clean before this planning edit. The local unit suite
  passed 18/18. The latest GitHub Actions run for `2cd212c2` is red only in
  `hardening (worktree)`; Ubuntu, macOS, and clone hardening passed. The failing
  gate is the single-sample `ratio < 8.0` assertion in
  `t_parallel_spawns_unique`, not a worker-ID or state-integrity failure.
- `lifecycle.discard` snapshots a collected worker, releases the workspace
  lock, then calls `shutil.rmtree(..., ignore_errors=True)` and records a
  terminal state without checking that deletion succeeded. Clonegrown's
  worker-operation lock does not coordinate with the agent writing in the
  worker.
- `worker.snapshot_worker` uses `git status --untracked-files=all`, which omits
  ignored files. Normal discard can therefore delete ignored content without
  `--force`.
- `_Recovery._recover_spawn` can authenticate a published worker, find it
  changed from its base, then delete it while rolling back the interrupted
  spawn.
- Worktree provisioning creates a branch with `checkout -b`; rollback later
  calls unconditional `branch -D`. A deterministic branch that existed before
  the spawn can therefore be deleted even though this worker did not create it.
- `install.sh` accepts `CLONEGROWN_HOME` and recursively removes that path with
  no Clonegrown ownership proof. Its command wrapper and two skill targets are
  also replaced without installer ownership evidence.
- `repository.local_config_items` collapses Git's distinct valueless and empty
  representations to the same empty string. A local probe reproduced the
  distinction. Relative local remote URLs are copied unchanged into a worker
  at a different filesystem location.
- `core.run` sanitizes Git's environment only when the executable basename is
  literally `git`, although `CLONEGROWN_GIT` may name any executable. Its
  failure text includes the complete argument vector, including copied config
  values and credential-bearing remote URLs.
- Existing request-index hits return a `WorkerRecord` without record
  validation or worker authentication. Allocation trusts `next_id` and the
  record writer can replace an existing `<id>.json` file.
- `status` does not report several contradictions it can observe, including a
  missing live worker, a missing immutable result ref, or branch/admin/base-ref
  residue.
- The Python API defaults `spawn(..., strong=True)` while the CLI defaults to a
  non-strong clone. `sanitize_task("x.lock")` produces a branch that a direct
  `git check-ref-format --branch` probe rejected.
- `heartbeat` is written once but never consumed or refreshed. Runtime code
  honors failpoint environment variables without an explicit test-mode gate.
- The current public prose contains absolute claims disproved by the behaviors
  above. Default clones can hard-link object files; request-less spawns are not
  idempotent; collection is not integration; current collection behavior is
  one-shot even though that contract is not stated plainly.

These are verified defects or mismatches. Git LFS, arbitrary filters,
network/distributed filesystems, genuine disk/inode exhaustion, native
Windows, and broad real-repository behavior remain **unverified validation
gaps**, not observed failures.

### Calls this roadmap makes

These choices keep later Steps executable without reopening product semantics
mid-fix:

1. A worker is **one-shot after collection**. New work gets a new worker;
   collection never becomes implicit integration or a multi-result session.
2. Every published worker has a durable, cooperative work lease. Normal or
   abandoned deletion requires an explicit lease release; records predating
   the lease field are treated as still leased. `--force` does not silently
   override a live lease.
3. Normal discard protects ignored content. A collected worker with ignored
   paths requires `--discard-ignored` in addition to any post-collection drift
   acknowledgement. `--abandon` applies only to an uncollected worker and
   means abandoning all of its content.
4. Deletion is a recoverable protocol: authenticate, record intent, atomically
   quarantine, recheck, delete with errors enabled, verify absence, then clean
   worktree state and record a terminal status. Unexpected work stays in
   quarantine and is reported; it is never converted into success.
5. The Python API adopts the CLI's default: `mode="clone", strong=False`.
6. The on-disk `.cws` / `refs/cws` protocol name remains for compatibility.
   The repository-unreferenced public `CWSError` alias is removed before a
   stable release; `ClonegrownError` remains the public error type.
7. Clonegrown 0.x stays POSIX-only and standard-library-only. Native Windows,
   network/distributed filesystems, and Git LFS are stated as unsupported
   until their dedicated validation Steps pass. This is a support boundary,
   not a claim that they are broken.
8. The canonical-source push URL remains a best-effort accident guard, not a
   security boundary. Exact-base pinning, immutable result refs, explicit
   integration, authenticated paths, targeted worktree cleanup, direct argv
   subprocesses, and real-repository tests remain intact.

### Execution rules for every remediation Step

- Start from the exact source location and reproduce the failure with the
  smallest focused regression. State the causal chain before changing code.
- Before implementation, name the files/symbols that exist, what will be
  modified, what will be created new, and what must remain behaviorally
  unchanged. Compare the finished diff to that boundary.
- The regression must cover the failure class, not merely replay one proof.
  Keep real Git/filesystem behavior; use mocks only to inject an otherwise
  impractical boundary failure such as a partial `rmtree`.
- Complete the code, focused tests, output-contract changes, and immediately
  affected documentation together. Do not leave two competing protocols.
- Do not change code between repeated runs of an intermittent test. Measure
  first. Two failed hypotheses stop the Step and require a report.
- No implementation batch below contains more than ten fixes. The final Step
  of every Phase is a cold review by a fresh agent. Any confirmed issue becomes
  a new Step before the next Phase; the reviewer does not opportunistically
  patch it.
- On completion, report executable, test, and comment/documentation changes
  separately, followed by the exact focused and completion checks and results.
- Keep generated test and benchmark output outside the checkout. Never inspect
  a dotenv file. Preserve unrelated user changes.

## Phase 1 — Make the present contract honest and the installer non-destructive

### Step 1.1 — Correct current claims and freeze the custody contract — complete 2026-08-27

- Update `README.md`, `SKILL.md`, `ARCHITECTURE.md`, the package docstring, CLI
  help, and package description so they describe current behavior literally
  while the later fixes are pending. Remove “never lost,” “shares nothing,”
  unconditional idempotency, complete crash cleanup, and equivalent absolute
  wording.
- State precisely: collection preserves a clean committed tip but does not
  integrate it; ignored files and active external writers are not currently
  protected; worktrees share broad Git state; default clones may share object
  files; `--strong` supplies physical object independence; the source push URL
  is only an accident guard.
- Record the target lease, ignored-content, one-shot, quarantine, and explicit
  integration contracts without claiming those mechanisms already exist.
- Keep comments that explain genuine Git/path invariants. Rewrite only comments
  whose write-ahead, admin-recording, or redaction claims exceed the code.
- Verification: documentation claim search, `python3 -m unittest discover -s
  tests -v`, and `sh -n install.sh`. This Step changes prose only.

### Step 1.2 — Make every installer-owned replacement prove ownership — complete 2026-08-27

- Add a versioned Clonegrown installation marker. A first install may create an
  absent target; an update may replace only a target carrying the expected
  marker. Reject `/`, a home directory, an existing non-Clonegrown directory,
  symlinks, and unsafe parent/child aliases before any removal or rename.
- Stage beside the destination with a unique name, fsync as practical in POSIX
  shell, rename the old owned install to a backup, publish the new install, and
  restore the backup on failure. Delete only paths created or authenticated by
  this installer invocation; do not use a caller-controlled path as an
  unchecked recursive-deletion target.
- Give the generated command wrapper and both skill installations their own
  ownership evidence. Refuse to overwrite a pre-existing unowned wrapper or
  skill directory. Preserve the existing four-target install behavior after
  ownership is established.
- Add installer tests using throwaway `HOME`, `CLONEGROWN_HOME`, local clone
  sources, non-Clonegrown sentinel directories, symlinks, interrupted update,
  successful first install, and successful owned update. No test touches the
  real home directory.
- Verification: focused installer tests, `sh -n install.sh`, the unit suite,
  and an isolated command/skill install smoke test.

### Step 1.3 — Cold-review Phase 1 — complete 2026-08-27

- A fresh agent reviews only the Phase 1 diff for truthful claims, installer
  path ownership, rollback holes, shell quoting, and sentinel preservation.
- Re-run the Phase 1 checks. Record findings here; insert fixes before Phase 2.

Cold-review result (2026-08-27): the focused installer tests (7/7), full unit
suite (25/25), isolated first-install/update smoke test, byte compilation,
`sh -n install.sh`, retired-claim search, and `git diff --check` all passed.
The passing suite did not cover seven concrete issues found by the fresh
reviewer and independently confirmed against the source:

- **High — cleanup can delete a replacement it does not own.** After a staged
  source, wrapper, or skill is renamed into place, the corresponding stage
  variable still names the now-vacant path. The unconditional EXIT trap calls
  `rm -rf` on that name. A disposable `mv` probe recreated the vacated stage
  path with an unowned sentinel; installation succeeded, then the trap deleted
  the replacement.
- **Medium — a colon in the installation path breaks the command wrapper.**
  The wrapper transports the installation root through `PYTHONPATH`, whose
  entries are colon-delimited. A disposable install beneath a colon-containing
  path exited successfully, but its wrapper failed to import `clonegrown`.
- **Medium — canonicalization can introduce an unframed newline.** Preflight
  rejects newlines before `realpath`, then serializes canonical paths as
  newline-delimited records. A symlinked parent can resolve to a path containing
  a newline, so the shell reads shifted fields; the post-read validation checks
  only three fields.
- **Medium — the clone hook-isolation claim is unconditional but behavior is
  conditional.** `copy_local_config()` can preserve a configured
  `core.hooksPath` that resolves outside the worker. It warns for values Python
  classifies as absolute, but tilde-prefixed and traversal-heavy values can
  resolve externally without that warning. Three user-facing documents said
  clone mode had separate hooks without these qualifications.
- **Medium — `recovery.py` overstates rollback.** Its module docstring promises
  rollback to the last safe state and no unauthorized deletion, but the
  represented spawn-recovery path can authenticate a changed published worker,
  delete it, and mark the operation failed.
- **Low — printed PATH guidance is not shell-safe.** `BIN_DIR` is interpolated
  inside a double-quoted command; dollar signs, backticks, and related shell
  syntax in the path can expand or execute when the displayed command is
  copied.
- **Low — `ARCHITECTURE.md` says every command prints JSON.** Successful
  lifecycle operations do, but `--version`, help, argument errors, and runtime
  errors are text.

Each confirmed issue has its own bounded remediation Step below. Phase 1 ends
with another fresh cold review after those changes.

### Step 1.4 — Bind stage cleanup to the object this invocation created — complete 2026-08-27

- Replace name-only EXIT cleanup entitlement with explicit stage identity and
  publication state. Revoke a published stage's old name before rollback frees
  its inode. For an unpublished stage, keep identity validation and deletion in
  one cleanup helper and preserve a name that does not match the captured
  device, inode, and file type. State the unavoidable POSIX same-user race
  boundary rather than claiming atomic unlink-by-identity.
- Cover all four staged target kinds (source, wrapper, Codex skill, and Claude
  skill) on successful publication and rollback paths. Use disposable move
  probes that recreate the vacated stage name with an unowned sentinel and
  assert the sentinel survives.
- Verification: focused installer tests, `sh -n install.sh`, isolated
  first-install/update smoke tests, the unit suite, and `git diff --check`.

Completion record (2026-08-27): every created directory or file stage now
carries captured filesystem identity (device, inode, and file type). Publication
verifies that identity before and after rename, clears the vacated name on
success, and revokes it before rollback while the moved inode is still live.
EXIT cleanup validates identity and deletes inside one Python helper instead of
returning a trusted pathname to a separately resolved `rm`; the control
directory receives the same protection. Move probes reoccupy all four vacated
stage names after successful publication and at each rollback boundary, and a
command-interposition probe proves stage names are not delegated to external
`rm`. All replacement sentinels survive, while the prior owned installation is
restored. A fresh review caught and caused removal of the earlier shell-level
check/delete gap; the documented residual boundary is a hostile same-user swap
between POSIX filesystem syscalls, for which POSIX has no atomic
unlink-if-inode operation.

### Step 1.5 — Stop transporting the install root through `PYTHONPATH` — complete 2026-08-27

- Generate a launcher that inserts the literal installation root into Python's
  module search path without encoding it as a colon-delimited environment
  entry. Preserve caller arguments, exit status, and any caller-supplied
  `PYTHONPATH` without relying on that variable to locate Clonegrown.
- Add first-install and owned-update smoke tests beneath paths containing a
  colon, spaces, dollar signs, quotes, backticks, and glob characters; execute
  the installed command rather than merely inspecting wrapper text.
- Verification: focused wrapper/installer tests, `sh -n install.sh`, isolated
  command smoke tests, the unit suite, and `git diff --check`.

Completion record (2026-08-27): the shell wrapper now passes the installation
root as one quoted Python argument. A bootstrap removes that argument from
`sys.argv`, inserts the literal root at the front of `sys.path`, and runs the
package's `__main__` module. It does not rewrite `PYTHONPATH`. The isolated
first-install and owned-update regression executes the wrapper beneath one path
containing a colon, spaces, dollar signs, single and double quotes, backticks,
and glob characters. It also proves exact argument preservation (including an
empty argument), exit-status propagation, unchanged and usable caller
`PYTHONPATH`, installed-package precedence over a same-named caller package,
and the v1-to-v2 owned update.

### Step 1.6 — Validate canonical paths before parsing preflight output — complete 2026-08-27

- Revalidate every path after `realpath`, rejecting carriage returns and
  newlines introduced by canonicalization before emitting the preflight
  record. Make record framing and post-read validation exact: require the full
  expected field count, every required value, and the installation-ID format
  before any destination-parent or installation mutation.
- Add a regression whose newline-free lexical parent is a symlink to a
  newline-containing canonical parent. Assert preflight refuses it and leaves
  every destination and sentinel unchanged.
- Verification: focused preflight/installer tests, `sh -n install.sh`, the
  isolated smoke tests, the unit suite, and `git diff --check`.

Completion record (2026-08-27): `normalize()` now rejects carriage returns and
newlines both before and after `realpath`. A byte-oriented validator rejects
NUL and carriage-return bytes and requires exactly six newline-terminated
preflight fields with no seventh partial or complete field. The shell then
checks the parsed count and all five paths for emptiness and accepts only a
32-character lowercase hexadecimal installation ID before creating a
destination parent. A fake-`mkdir` boundary test proves that newline-free
parent symlinks resolving through newline or carriage-return path components
leave all four destinations and their parent sentinels untouched. A second
boundary test injects empty values into every path field, non-hexadecimal,
uppercase, and short IDs, complete and partial extra fields, and a NUL-only
partial field; none reaches the first destination-parent mutation. The private
control directory and preflight record necessarily exist before validation.

### Step 1.7 — Qualify clone hook isolation in user-facing documentation — complete 2026-08-27

- Update `README.md`, `SKILL.md`, and `ARCHITECTURE.md` to match
  `copy_local_config()` literally: the default private `.git/hooks` location is
  separate, while a configured `core.hooksPath` value can resolve to a shared
  external dependency. Absolute values receive a warning; tilde-prefixed and
  traversal-heavy values can also resolve externally without it. Do not imply
  that clone mode copies external hook programs or that the generic
  canonical-path substring check proves filesystem containment.
- Verification: focused claim search, documentation diff review, the unit
  suite, and `git diff --check`. This Step changes prose only.

Completion record (2026-08-27): the README comparison and mode guidance, the
agent skill's selection guidance, and the architecture now limit clone hook
isolation to the default private `.git/hooks` location. They state that
Clonegrown can copy configured `core.hooksPath` values rather than programs and
that any copied value resolving outside the worker remains shared. Absolute
values receive a warning, while tilde-prefixed and traversal-heavy values can
escape without one. The architecture records the raw canonical-string omission
check, its warning-before-omission ordering, conventional repository-relative
paths, and the fact that `--strong` does not change hook handling. A first cold
review caught and caused correction of the earlier relative-path and
filesystem-containment overstatements. Only prose changed; executable and test
behavior are unchanged.

### Step 1.8 — State recovery guarantees at represented checkpoints — complete 2026-08-28

- Rewrite the `recovery.py` module contract to describe the actual durable
  checkpoints and the destructive published-alpha recovery path. Remove the
  unconditional promises of rollback to the last safe state and no deletion
  unless they first become executable invariants in a later Step.
- Check nearby recovery comments and user-facing descriptions for the same
  stronger claim, changing only prose that contradicts the represented state
  machine.
- Verification: focused recovery-claim search, recovery tests, the unit suite,
  and `git diff --check`. This Step changes prose only.

Completion record (2026-08-28): `clonegrown/recovery.py` now scopes recovery
to the lifecycle and filesystem boundaries represented by current durable
records. Its module and public-function contracts no longer promise rollback
to a last safe state, coverage of every interrupted operation, or
unconditionally safe repetition. They state the current destructive boundary
literally: interrupted-spawn recovery can authenticate a published worker
whose `HEAD` differs from its recorded base, delete its slot, and record
`spawn_failed`; authentication identifies the recorded repository but does not
prove that it contains no post-publication work. The nearby spawn comment and
the architecture's module summary now use the same represented-checkpoint
scope. README, installed-skill, lifecycle, and CLI recovery prose already had
that scope and the destructive warning, so they were left unchanged. No
lifecycle control flow, test, CLI-output, or on-disk-protocol behavior changed.

### Step 1.9 — Print PATH guidance as a shell-safe command — complete 2026-08-28

- Quote the literal binary directory for POSIX shell copy/paste while leaving
  the user's existing `PATH` expansion active at execution time. Do not emit a
  command in which path contents can trigger parameter expansion, command
  substitution, globbing, or word splitting.
- In disposable shells, execute the exact command captured from installer
  output for binary paths containing spaces, dollar signs, quotes, backticks,
  and glob characters; assert the intended directory becomes one PATH entry
  and no injected side effect occurs.
- Verification: focused guidance/installer tests, `sh -n install.sh`, the unit
  suite, and `git diff --check`.

Completion record (2026-08-28): before any destination-parent mutation,
`install.sh` now encodes the canonical binary directory as an always
single-quoted POSIX shell literal, representing each embedded single quote by
ending the literal, quoting that character, and reopening the literal. The
printed command appends `:"$PATH"`, so the path's contents remain literal
while the user's existing `PATH` expands only when the command is executed.
The regression runs the exact captured line for a binary directory containing
spaces, dollar syntax, single and double quotes, dollar and backtick command
substitutions, and glob characters. It proves the directory becomes one exact
`PATH` entry, the prior entries survive unchanged, and neither substitution
creates its side-effect file. The encoder uses the already-required Python
runtime; no package or dependency was added. Installer ownership, publication,
launcher, and destination-mutation behavior were unchanged.

### Step 1.10 — Scope the JSON output claim to lifecycle success results — complete 2026-08-28

- Update `ARCHITECTURE.md` to say that successful lifecycle operations emit
  JSON, while help, version output, argument errors, and Clonegrown runtime
  errors are text on their documented streams. Check the adjacent CLI prose
  for equivalent absolutes.
- Verification: direct probes of one lifecycle success plus help, version,
  argument-error, and runtime-error paths; focused claim search; the unit suite;
  and `git diff --check`. This Step changes prose only.

Completion record (2026-08-28): direct subprocess probes established the
current stream and exit-status contract. Successful `init` emitted JSON on
stdout and exited 0; help and `--version` emitted text on stdout and exited 0;
an argument error and a caught `ClonegrownError` emitted text on stderr, left
stdout empty, and exited 2. `ARCHITECTURE.md` now limits JSON to successful
`init`, `spawn`, `collect`, `discard`, `recover`, and `status` results, records
the other streams literally, and distinguishes stored worker-error fields from
textual command errors. The `clonegrown.cli` module and `public_result`
docstrings carry the same successful-JSON scope. The README's JSON references
were already limited to a successful spawn and successful CLI results, so they
were left unchanged. Only descriptive text and Python docstrings changed; CLI
control flow, streams, exit statuses, tests, and protocol behavior did not.

### Step 1.11 — Cold-review Phase 1 remediation — complete 2026-08-28

- A fresh agent reviews the complete Phase 1 diff, concentrating on the seven
  Step 1.3 findings, installer deletion authority, path framing and quoting,
  rollback behavior, sentinel preservation, and exact user-facing claims. The
  reviewer does not patch opportunistically.
- Re-run every Phase 1 check, including the adversarial probes added in Steps
  1.4–1.10. Record the review result here; any confirmed issue becomes another
  bounded Phase 1 Step before Phase 2 begins.

Cold-review result (2026-08-28): a fresh agent reviewed the complete Phase 1
change set from baseline commit `2cd212c` through the working tree, without
modifying repository files. The 14 installer tests, 32-test unit suite,
out-of-checkout byte compilation, shell syntax, retired-claim search, five CLI
output probes, and focused recovery and hook campaigns in clone and worktree
modes all passed. The reviewer nevertheless found one high-severity ownership
defect that the primary agent independently reproduced with two disposable
probes:

- **High — a vacated backup name can overwrite an unowned object and defeat
  rollback.** `reserve_directory_backup()` and `reserve_file_backup()` create
  a unique object, delete it, and return only the now-vacant pathname. Each
  update later passes an authenticated old target and that unowned pathname to
  external `mv` without rechecking vacancy or binding the moved object's
  identity. In the file proof, reoccupying a command-backup name with a
  sentinel led to a successful update; immediately after the move that path
  began with `#!/bin/sh`, and the sentinel was gone. In the directory proof,
  reoccupying the source-backup name caused `mv` to nest the old installation
  inside the unexpected directory. A later injected wrapper-publication
  failure exited 74, removed the newly published source, rejected the outer
  backup as unowned, and left the installation root absent with the old source
  stranded below the backup. The existing adversarial tests reoccupy vacated
  **stage** names, not backup names.

This is a confirmed Phase 1 installer defect, not a Phase 2 worker-custody
issue. Step 1.12 fixes it; Step 1.13 preserves the rule that every Phase ends
with a fresh cold review. Still unverified here: macOS-specific rename behavior,
`SIGKILL`/power-loss persistence, and syscall-level same-user swaps inside the
already documented residual POSIX race boundary.

### Step 1.12 — Bind backup relocation to vacancy and object identity — complete 2026-08-28

- Replace the name-only reserve-then-`mv` gap for source, wrapper, Claude-skill,
  and Codex-skill backups. Record rollback intent and the old target's device,
  inode, and file type before relocation. Reserve the backup name with a
  token-bearing object this invocation created. In one Python helper,
  revalidate the source identity, require that reservation to be unchanged by
  identity and content, rename the source without an external-command
  interposition point, and verify that the backup now has the captured
  identity. Refuse a reoccupied name before touching either object; never
  overwrite it or nest the old target inside it.
- Make rollback and committed cleanup require both the target's Clonegrown
  marker/installation ID and the captured backup identity. An unexpected
  object is preserved and reported, not treated as the old target. Retain the
  current caught-signal rollback order and successful four-target update
  behavior; state the unavoidable same-user race between POSIX filesystem
  syscalls without claiming atomic no-replace semantics on every supported
  system.
- Add file and directory regressions that reoccupy each of the four backup
  names after reservation. Prove every sentinel and every previous target
  remains byte-for-byte intact on refusal. Inject failures after each
  successful backup relocation to prove reverse-order restoration, and retain
  successful owned first-install/update coverage with no backup residue.
- Verification: focused backup/rollback installer tests, the complete
  installer suite, `sh -n install.sh`, isolated first-install/update smoke
  tests, the unit suite, and `git diff --check`.

Completion record (2026-08-28): each backup name is reserved by an object
this invocation creates (`mktemp`) and marks with a token file holding the
installation ID. `relocate_created_path` validates, in one Python process, the
old target's captured device, inode, type, and ownership evidence, then the
reservation's identity and token, rechecks both immediately before
`os.replace`, and verifies the backup carries the old target's identity
afterwards. A reoccupied or altered reservation is refused before either object
is touched; refusal removes only an unchanged reservation. Rollback removal of
a newly published target, rollback restoration of a backup, and committed
backup cleanup all require the captured identity and this installation's
marker or wrapper header inside the same process; anything else is preserved
and reported. The regression set reoccupies every backup reservation, guts
every backup in place at committed cleanup and at each of the four rollback
boundaries, reoccupies publication and restore destinations, and injects a
publication failure after each successful backup relocation to prove
reverse-order restoration of all previous targets with no stage or backup
residue. The residual boundary stays as documented: a hostile same-user swap
between POSIX filesystem syscalls, for which POSIX offers no atomic
rename-if-absent. The bughunt below ran against this Step's working tree and
its fixes are part of this Step.

Bughunt result (2026-08-28, against the in-progress Step 1.12 working tree):
the reservation-token relocation helper was already present and its
reoccupation regressions passed, but a full close read of `install.sh` and
`tests/test_installer.py` found three defects, each reproduced before it was
fixed and each now pinned by a regression:

- **Confirmed — non-UTF-8 paths failed preflight under a UTF-8 locale.** The
  preflight record and the shell-literal encoder printed paths through
  Python's text stdout, whose `strict` handler refuses surrogate-escaped bytes
  when the locale is UTF-8 (the existing non-UTF-8 test failed on this
  machine; it passed only under `LC_ALL=C`). Both helpers now write the
  original filesystem bytes; the regression covers a non-UTF-8 installation
  source and command directory and checks the PATH guidance bytes.
- **Confirmed — committed cleanup and rollback trusted device/inode identity
  alone.** This Step's second bullet (marker *and* identity) was not yet
  implemented; the `HEAD` installer had checked the marker. Disposable probes
  deleted an old-source backup and recreated its name: the filesystem reused
  the inode number, committed cleanup silently deleted the foreign directory,
  and rollback silently installed a foreign directory as the installation
  root. The cleanup and relocation helpers now also require the object's
  marker (or wrapper header) for this installation ID inside the same process,
  for all four target kinds, on the old-to-backup move, publication, rollback
  removal, rollback restore, and committed cleanup. Private unpublished
  stages keep identity-only cleanup because an unfinished stage carries no
  evidence yet. Regressions gut every backup in place (same inode, marker and
  contents gone) at committed cleanup and at each of the four rollback
  boundaries; every gutted object survives and none is installed as a target.
- **Confirmed — a refused backup relocation printed a false rollback
  message.** After the relocation to a reoccupied backup name was refused, the
  previous target was intact in place, yet rollback warned that it "remains in
  backup because its destination is occupied". Rollback now recognizes the
  still-in-place target by identity and says that the object at the reserved
  backup name was preserved; the restore-failure message no longer calls a
  non-authenticating object "the backup".

Three fresh cold reviews of those fixes found and caused further
corrections. Code corrections, each pinned by a regression: the non-UTF-8
test is locale-independent (`PYTHONIOENCODING=utf-8:strict`) and also covers
an owned update, which previously failed because preflight decoded the whole
wrapper as strict UTF-8; preflight, the shell checks, and the Python helpers
share one line definition for ownership evidence (newline-separated, one
optional trailing newline, marker exactly three lines, wrapper header its
first four) and preflight reads only the head of a wrapper, so a long wrapper
body stays updatable; a FIFO at a backup marker is preserved and reported
instead of blocking the installer. Applied on the same principle without a
dedicated regression: the preflight evidence read and the reservation read
also refuse anything but a regular file before opening it, and open without
following symlinks or blocking. Documentation corrections: this Step's first
bullet now describes the token-bearing reservation the code uses.

Still open within the documented boundary: a leftover reservation object
(a token file, or a directory holding one) if the invocation fails or is
killed between reserving a backup name and the relocation, and identity-only
cleanup of private unpublished stages.

### Step 1.13 — Cold-review backup remediation and close Phase 1 — complete 2026-08-28

- A fresh agent reviews the complete Phase 1 diff, concentrating on backup
  name vacancy, old-target and backup identity, all four target kinds,
  rollback-state ordering, command interposition, sentinel preservation, and
  the residual POSIX same-user race boundary. The reviewer does not patch
  opportunistically; any confirmed issue becomes another bounded Phase 1 Step.
- Re-run every Phase 1 check, including all installer adversarial probes,
  claim searches, direct CLI output probes, recovery checks, shell syntax,
  byte compilation, the unit suite, and `git diff --check`. Phase 2 begins only
  if the review confirms no open Phase 1 finding.

Cold-review result (2026-08-28): a fresh agent reviewed the complete Phase 1
change set from `2cd212c` through the working tree without modifying any
repository file and found no open Phase 1 finding. It traced backup
reservation and token handling, identity plus ownership evidence for all four
target kinds across first install, owned update, refused update, and
interrupted update, rollback ordering and stage-name revocation, the absence
of any external `rm`/`mv`/`rmdir`, sentinel preservation on every deletion
path, the stated POSIX same-user race boundary, the seven Step 1.3 findings
(each closed in code, not only prose), and every user-facing claim. It re-ran
the 42-test suite, shell syntax, out-of-checkout byte compilation, the
retired-claim search, five CLI stream probes, eight campaign cases in clone
and worktree modes, and nine extra probes (failure and signals at the
backup-relocation boundary, partial prior install, non-empty and FIFO
reservations, group-wide `SIGINT`, closed stdout). Two low notes were closed
in the same pass: `SIGPIPE` is now trapped so a closed stdout cannot skip the
EXIT cleanup of the control directory (regression added), and the README and
architecture now say that a caught signal after the commit can also leave
authenticated backups beside a complete installation. Phase 1 is closed.

## Phase 2 — Make destructive worker operations conservative and recoverable

### Step 2.1 — Centralize status-specific durable-state validation — complete 2026-08-28

- Keep the single `WorkerRecord` dataclass, but add one centralized validator
  for required, forbidden, and mutually dependent fields in every status.
- Validate stored commit IDs against the workspace object format; validate
  base, candidate, result, branch, and cleanup refs against the exact namespace
  derivable from workspace/worker identity; validate discard intent, lease,
  quarantine, and worktree-cleanup fields before they select a path or ref.
- Extend schema 3 compatibly: an absent lease field means “active/unreleased,”
  and absent quarantine fields mean the old non-quarantined state. Do not add a
  schema migration framework solely for these conservative defaults.
- Add table-driven metadata-corruption tests for every status and new field,
  while retaining unknown-key round trips and records from before worktree
  mode.
- Verification: focused state tests, current metadata red-team cases, then the
  unit suite.

Completion record (2026-08-28): `WorkerRecord.validate` is now one ordered
pass over four concerns: identity (schema, slot ID, workspace and canonical
identity, token, deterministic branch, mode, isolation flag, parameter digest,
slot and staging paths); the shape of every present field from one table
(timestamps, owner process fields, error texts, spawn details, snapshots);
per-status required and forbidden fields from one table keyed by every
`WorkerStatus`; and cross-field dependencies. Commit IDs (`base_sha`,
`candidate_sha`, `result_sha`, the collected snapshot head) must match the
workspace object format; `candidate_ref` and `result_ref` must equal
`state.result_ref(worker_id, sha)` exactly; the branch must equal the
deterministic assignment; a worktree admin path must sit under the canonical
`worktrees` directory and only on a worktree worker; discard intent and origin
must be consistent with each other and with a terminal status; a settled
status may not carry an operation owner. Schema 3 is extended compatibly with
`lease`/`lease_released` (absent means leased) and
`quarantine_path`/`quarantine_started`/`quarantine_error` (absent means never
quarantined; a present path must equal the identity-derived
`.cws/quarantine/<id>-<token>`); no command sets them yet and no migration
framework was added. Fields no status names are checked for shape only, so
records written by earlier code, including pre-worktree records without
`mode`, keep loading, and unknown keys round-trip. `tests/test_state.py`
derives a valid record for all twelve statuses from one real spawn and, table
driven, removes every required field, injects every forbidden field, applies
forty named corruptions, checks both object formats, both lease states,
quarantine consistency, conservative defaults, and unknown-key/pre-mode round
trips, and proves five on-disk corruptions are diagnosed by `status` and
refused by `collect` and `discard --abandon --force` without touching the
worker or a victim path. The existing lifecycle tests and the eight metadata
red-team campaign cases pass unchanged in clone and worktree modes.

### Step 2.2 — Add an explicit worker lease and one-shot handoff — complete 2026-08-28

- Add `claim(ws, worker_id)` / `release(ws, worker_id)` to the API and
  `clonegrown claim <id>` / `clonegrown release <id>` to the CLI. Spawned and
  legacy workers are leased until an explicit release; `status` shows the
  lease state without exposing identity tokens. A released worker can be
  claimed again only while it remains `ready`.
- Make `discard`, including `--abandon`, refuse a leased worker. Do not let the
  existing `--force` drift flag override the lease. A crashed agent is handled
  by an explicit user/orchestrator release, never by silently inferring that
  its work is disposable from a dead PID.
- Keep collection independent from lease release. Update the installed skill
  workflow to collect, release, and only then discard; state plainly that the
  lease is a cooperative ownership handoff, not an OS sandbox against a process
  that violates the contract or retains open file descriptors.
- Reject `--abandon` for a collected worker and document the one-shot rule.
- Regressions: active lease blocks normal discard, abandon, recovery deletion,
  and `--force`; legacy records default safe; explicit release permits the
  next protocol stage; claim-after-collection is refused.

Completion record (2026-08-28): `claim(ws, id)` and `release(ws, id)` join
the Python API and the CLI as `clonegrown claim <id>` / `clonegrown release
<id>`. A worker is leased from spawn; the record's `lease` field is `active`
or `released`, an absent field means leased, and every published record's
JSON states its lease so `status` shows it without exposing tokens. `release`
is allowed for a `ready`, `collected`, or `broken` worker and is idempotent;
`claim` re-leases only a released worker that is still `ready`, so a collected
worker is never claimed again. `discard` authenticates the worker, then
refuses `--abandon` for a collected worker (one-shot), then refuses any
leased worker before `--abandon` or `--force` is considered; a failed spawn
owns no directory and needs no release. Collection is independent of the
lease. Recovery never infers a release from a dead owner: an interrupted
abandonment of a leased worker is reset to its previous status and reported
as `abandon-blocked-by-lease`, and a tombstone's lingering directory is
reported (`tombstone-path-left` since Step 2.7) rather than deleted. The validator
now also forbids a released lease on an unpublished record and accepts
`broken`/`spawn_failed` as discard origins, which the Step 2.1 table had
wrongly rejected. `tests/test_lease.py` proves in clone and worktree modes
that an active lease blocks normal discard, abandon, `--force`, and recovery
deletion; that legacy records default leased; that explicit release permits
the next stage; that claim after collection, claim on a leased worker, and
release during an operation are refused; that a failed spawn discards
without a release; and the CLI output for `release`/`claim`. The installed
skill workflow now reads collect, release, then discard, states that the lease
is a cooperative handoff rather than an operating-system sandbox, and the
README and architecture describe the lease and the one-shot rule as
implemented. The unit tests, hardening campaign, crash-case, random-kill, and
state-machine-fuzz harnesses release before discarding.

### Step 2.3 — Bring ignored files into discard custody — complete 2026-08-28

- Separate the clean committed snapshot used for collection from the custody
  inspection used for deletion. Enumerate ignored paths with Git's
  machine-readable, NUL-delimited interface without reading their contents.
- Normal collected-worker discard refuses when ignored paths exist and reports
  a bounded count/sample. Require `--discard-ignored` to delete them; do not
  overload `--abandon`, and do not print file contents.
- Preserve current tracked/untracked drift checks and make flag combinations
  explicit: uncollected → `--abandon`; collected drift → `--force`; collected
  ignored content → `--discard-ignored`; lease release is required in every
  case.
- Regressions cover ignored files, ignored directories, `.git/info/exclude`,
  global excludes, large ignored sets, tracked drift, and no content leakage in
  errors. The tests create ordinary ignored fixtures, never dotenv files.

Completion record (2026-08-28): `inspect_ignored_content()` in `worker.py`
is a custody inspection separate from the collection snapshot. It runs
`git ls-files -z --others --ignored --exclude-standard --directory` through a
new bytes-returning Git runner (`core.git_bytes`), so Git's own ignore
evaluation (`.gitignore`, `info/exclude`, the global excludes file) decides
what is ignored, an ignored directory counts as one entry ending in `/`, names
need not be UTF-8, and no file is opened. `discard` of a collected worker now
answers two custody questions separately and reports every missing
acknowledgement in one refusal: `--force` for a moved committed tip and
`--discard-ignored` for ignored paths, naming an exact count and a sample of
at most five names, never contents. `--abandon` is unchanged in meaning: it
applies only to an uncollected worker and authorizes deleting everything it
holds. The lease is checked before any flag. The CLI gained
`--discard-ignored`. `tests/test_discard_ignored.py` covers an ignored file in
both worker modes, an ignored directory as one entry, `info/exclude`, global
excludes through a throwaway `HOME`/`XDG_CONFIG_HOME`, a 600-file ignored set
with an exact count and bounded sample, a non-UTF-8 ignored name, drift plus
ignored content needing both flags in every combination, abandonment of an
uncollected worker with ignored content, lease-before-ignored ordering, a
clean worker with and without the flag, and the CLI path; every refusal is
checked for the absence of a sentinel file body. The random-kill discard
campaign, whose fixture holds 3,500 ignored build files, now passes the flag.

### Step 2.4 — Give worktree branch and admin cleanup compare-and-swap ownership — complete 2026-08-28

- In worktree mode, use one `git update-ref --stdin` transaction to create the
  deterministic task branch and a worker-private ownership ref, both with
  expected-old-zero semantics, before checkout. A pre-existing branch aborts
  the entire transaction untouched; the private ref closes the crash window
  between branch creation and metadata persistence.
- Delete a task branch only in a ref transaction that verifies the private
  ownership ref and the branch's expected current SHA, derived from the
  authenticated worker and persisted before cleanup. If either ref moved,
  retain both, retain the cleanup evidence, and report the conflict.
- Make admin-directory deletion checked and absence-verified. Clear
  `worktree_admin` and branch-cleanup fields only after their exact targets are
  proved gone; keep targeted cleanup and never call blanket `worktree prune`.
- Regressions pre-create the deterministic branch at a unique commit, move the
  branch during discard, inject admin deletion failure, recycle admin names,
  and prove no foreign branch/admin directory is removed.

Completion record (2026-08-28): worktree provisioning now creates
`refs/heads/<branch>` and the worker's private ownership ref
`refs/cws/<ws>/workers/<id>/branch-owner` in one `git update-ref --stdin`
transaction (`create_task_branch`, create-only semantics for both) before the
checkout, which no longer uses `checkout -b`; a pre-existing branch of the
deterministic name aborts the transaction untouched and the spawn fails
cleanly. Discard records the branch's current tip in the new
`branch_cleanup_sha` field before anything is deleted; `forget_worktree`
persists that tip first on the recovery paths that reach it without one.
`release_task_branch` deletes the branch only in one transaction that
verifies the ownership ref, deletes the branch at the recorded tip, and
deletes the ownership ref; a moved branch, a changed ownership ref, or a
record without an ownership ref retains both refs and the evidence and sets
`branch_cleanup_left`. `remove_worktree_admin` runs `rmtree` with errors
enabled and verifies the path absent; `forget_worktree` clears
`worktree_admin` only then, otherwise keeps the path and records the error in
`worktree_admin_left`. `recover` reports `worktree-cleanup-conflict` whenever
evidence remains and retries tombstones that still hold it; `status` shows
the retained-branch and admin reasons while hiding `branch_cleanup_sha` as
bookkeeping. `git worktree prune` is still never called. Clone workers are
unchanged: their branch is private to the clone. Regressions in
`tests/test_worktree.py` pre-create the deterministic branch at a unique
commit and prove the spawn fails with the branch, ownership ref, worktree
list, and admin directory untouched; prove spawn creates both refs and a
normal discard removes both; move the branch after a crashed discard and
prove recovery finishes the record while retaining the moved branch and the
ownership ref across repeated passes; make the admin directory undeletable
and prove the record keeps its path with the error until a later recovery
succeeds; and delete the ownership ref to model a legacy record and prove the
branch survives abandonment. The existing recycled-admin-name and
foreign-admin tests still pass.

### Step 2.5 — Quarantine, recheck, and prove deletion — complete 2026-08-28

- Add an authenticated `.cws/quarantine/` layout and one narrow domain
  operation for slot → quarantine rename and final deletion. Derive the
  quarantine path from validated worker identity; reject symlinks, collisions,
  and cross-filesystem fallbacks rather than degrading to copy/delete.
- Persist deletion intent before rename and the quarantine location immediately
  after rename. Recheck the quarantined worker against the pre-rename custody
  snapshot before deletion so a mutation in the old final-check window leaves
  a preserved, reported quarantine instead of lost work.
- For a worktree, repair Git's back-pointer to the quarantined path before that
  recheck and retain its authenticated admin/branch evidence until the final
  deletion outcome. A repair or recheck failure preserves the quarantine.
- Run recursive deletion with errors enabled, verify the exact path is absent,
  and record a terminal state only after worker, stage, quarantine, admin, and
  branch cleanup have each succeeded. A partial failure remains recoverable
  with its path and error intact.
- Recovery resumes an authenticated quarantine and never labels residue gone.
  `status` reports quarantine and deletion failures without mutating them.
- Regressions pause after the first snapshot and mutate from a second process,
  inject partial recursive deletion, collide with a quarantine path, interrupt
  every new boundary, and prove repeated recovery is idempotent in clone and
  worktree modes.

Completion record (2026-08-28): deletion is one shared flow,
`worker.delete_through_quarantine`, used by `discard` and by recovery.
`discard` records intent (and the worktree branch tip) before anything moves;
the flow authenticates the slot, takes a custody fingerprint (`HEAD` plus a
SHA-256 of Git's NUL-delimited `status --porcelain=v2 --untracked-files=all
--ignored=matching` listing, so untracked and ignored paths count and no
content is read), renames the slot with one `os.rename` to the
identity-derived `.cws/quarantine/<id>-<token>` (a symlinked quarantine
directory, an occupied destination, or a rename the filesystem refuses is an
error with no copy fallback), and persists `quarantine_path`,
`quarantine_started`, and `quarantine_snapshot` immediately. It then repairs a
worktree's back-pointer to the quarantined path, authenticates the quarantined
worker with `verify_worker(repo=...)`, re-fingerprints it, refuses on any
difference, persists a deletion-authorized checkpoint (the fingerprint is
cleared, so a later resume finishes the verified deletion of the
identity-derived path instead of re-asking the custody question of a
half-deleted directory), deletes with `shutil.rmtree` errors enabled, proves
the exact path absent, and deletes the stage the same way. `finish_deletion` cleans
canonical's worktree state and records the terminal status only when the
worker, stage, quarantine, admin directory, and task branch are each proved
clean; otherwise the record stays `discarding` with its evidence
(`quarantine_error`, `branch_cleanup_left`, `worktree_admin_left`), the owner
released, and `discard` raises. This tightens Step 2.4, whose retained branch
or admin directory no longer coexists with a terminal status; those tests now
prove the record stays `discarding` until the user resolves the conflict and
`recover` finishes. Recovery resumes a quarantine from its persisted
fingerprint (`quarantine-preserved` when it still cannot proceed), finishes
content-gone records only when canonical cleanup succeeds, runs an interrupted
abandonment through the same flow, and reports quarantine entries no record
claims as `orphan-quarantine` without touching them; `status` shows
`quarantine_path` and `quarantine_error` and hides the fingerprint as
bookkeeping. A worker preserved because it changed is deleted only by a fresh
`discard` carrying the original acknowledgement (`--abandon`, or `--force`
for a collected worker), which takes a new fingerprint first. Two failpoints
were added (`discard.after_quarantine`, `discard.after_recheck`) and the
campaign crash matrix covers all six. `tests/test_quarantine.py` proves, in
clone and worktree modes: a normal discard leaves nothing; a second process
writing after the fingerprint (paused at `discard.before_delete`) leaves a
preserved, reported quarantine that repeated recovery keeps, that a bare
`discard` refuses, and that `--force` then deletes; an undeletable ignored
directory keeps the quarantine and the error until a later recovery
succeeds; an occupied quarantine path and a symlinked quarantine directory
are refused with the worker intact and the intruder reported as an orphan;
every one of the six boundaries interrupted recovers idempotently to the
same clean end state; an abandonment interrupted before the rename resumes
through quarantine; a tampered quarantined marker is preserved, not deleted;
and the CLI view. The remaining custody gap is interrupted-spawn recovery
(Step 2.6).

### Step 2.6 — Preserve interrupted-spawn work and close the worktree-add window — complete 2026-08-28

- If an authenticated published worker differs from its assigned base during
  recovery, mark it broken and preserve it in place; never route it through
  disposable spawn rollback. Report whether it is dirty, advanced, or otherwise
  unverifiable without exposing content.
- When the parent dies after `git worktree add` creates an admin directory but
  before its path is persisted, locate only an admin entry whose `gitdir`
  back-pointer matches this worker's unique staged path. Record/authenticate it
  before cleanup; leave ambiguous entries untouched.
- Regressions mutate a published clone and worktree before recovery, exercise
  the exact add/persist interruption window, and prove base pins, branches,
  admin directories, stages, and useful work are either retained or cleaned
  according to recorded ownership.

Completion record (2026-08-28): interrupted-spawn recovery no longer
deletes a published worker. `_recover_published_spawn` repairs a worktree's
back-pointer, authenticates the directory (an unverifiable one is marked
`broken` in place, as before), and asks `worker.describe_divergence` whether
it is still a freshly published worker: a clean tree, no Git operation in
progress, `HEAD` at the recorded base, and on the task branch. An untouched
worker is promoted to `ready`; anything else is marked `broken` with
`error = "published worker preserved after interrupted spawn: ..."`, naming
the kind of difference (uncommitted or untracked changes, HEAD moved to a
commit, off the task branch, operation in progress) but never a path or
content. The directory, its base pin, its branch, and its admin directory
stay exactly as they are; repeated recovery changes nothing; the user
resolves it with `release` and `discard --abandon`, which now also drops the
base pin when it records the terminal status. An unpublished spawn is
cleaned only through verified stage deletion and the ownership-checked
worktree cleanup, and becomes `broken` rather than `spawn_failed` if any of
that cannot complete. The add/persist window is closed:
`spawn.after_worktree_add` is a new failpoint between `git worktree add` and
the record write, and `forget_worktree` now calls `locate_worktree_admin`,
which accepts an admin entry only if its `gitdir` back-pointer names this
worker's unique staged path (which embeds the private token) or its published
path, and only if exactly one entry matches; zero or several leave every
entry untouched. Regressions in `tests/test_worktree.py` crash in that window
with the user's own worktree also registered and prove ours is removed while
theirs survives, and crash after publication in clone and worktree modes
with a dirty tree and with an advanced `HEAD`, proving the worker is
preserved as `broken` with a content-free description, its base pin, branch,
and admin directory retained across repeated recovery, and everything cleaned
by release plus abandonment. The campaign spawn crash matrix covers the new
failpoint in worktree mode. README, SKILL, architecture, and the recovery
module contract no longer describe interrupted-spawn recovery as destructive.

### Step 2.7 — Cold-review Phase 2 — complete 2026-08-28

- A fresh agent attacks active-writer handoff, ignored content, quarantine
  authentication, partial deletion, published-worker recovery, and branch/admin
  compare-and-swap behavior. It must try concrete failing scenarios in both
  worker modes.
- Run focused destructive tests first, then unit tests and the full hardening
  suite in clone and worktree modes. Insert confirmed fixes before Phase 3.

Cold-review result (2026-08-28): a fresh agent attacked Steps 2.1 through
2.6 in both worker modes with thirteen probe families and found six confirmed
defects, none of which deleted a leased worker or a foreign path, plus
documentation mismatches. All were fixed in the same pass, each with a
regression in `tests/test_quarantine.py`:

- **Crash between the quarantine rename and its persist recorded a terminal
  status with the whole worker still in quarantine** (worktree mode also
  deleted its branch and admin directory). The path, start time, and
  fingerprint are now persisted before the rename; a record naming a
  quarantine that does not exist while the slot does means "intent recorded,
  not moved"; "deletion authorized" is the explicit sentinel
  `quarantine_snapshot == {"deleting": true}`; a quarantine found with no
  fingerprint is refused until a re-acknowledged `discard`; content at a
  `discarding` worker's derived path that the record never named is adopted
  only if it authenticates as the worker, and otherwise reported as
  `quarantine-path-occupied` and never touched.
- **`preserve()` judged "nothing moved" by a field, not by disk**, bricking a
  `spawn_failed` record with forbidden discard fields and resetting a
  stage-failure case to a live status with no directory. It now decides by
  the slot and quarantine on disk, withdraws the intent (`withdraw_discard`,
  shared with recovery and with a flag-less `discard` on a stale intent, which
  must re-authorize against the worker's current state instead of resuming
  the old acknowledgements), or keeps the record `discarding` with
  `error = "deletion incomplete: ..."`.
- **The custody fingerprint was blind to content-only writes** and, after the
  first fix, to writes inside ignored directories. It now lists every
  untracked and ignored file (`--ignored=traditional`) and folds the `lstat`
  size, modification time, and type of every listed path and of every entry
  beside the repository in the slot into the digest; a rewrite that keeps
  both size and timestamp remains the documented residual gap.
- **`recover` aborted for the whole workspace when one published-spawn
  worker's `git status` failed.** Inspection failure now marks that worker
  `broken` ("cannot inspect"), and the per-worker loop reports
  `recovery-failed` and continues.
- **Tombstone cleanup used `rmtree(ignore_errors=True)` and reported success
  with residue**, the last by-authentication-only deletion. A re-occupied
  tombstone slot is now reported (`tombstone-path-left`, and
  `tombstone-path-occupied` in `status`), never deleted; its stage uses
  verified deletion.
- **`git worktree repair` ran before authentication**, so foreign content at a
  derived quarantine path could redirect another worker's admin entry.
  `repair_owned_worktree` first checks the moved checkout's `.git` pointer
  names an admin directory under canonical's `worktrees` that identifies as
  this worker.

A third review of the batch found four more, fixed the same way: Git never
descends into a nested repository, so the fingerprint now also folds an
`lstat` walk below every listed directory; a quarantined worktree whose admin
directory Git had pruned was a dead end with a wrong diagnosis, and is now
named as such and deletable by an acknowledged `discard` with a Git-free walk
fingerprint; authentic content in both the slot and the quarantine path is
refused (nothing resolved automatically) and an unrecorded occupant is never
adopted, let alone repaired, while the slot exists; and `gitdir` pointers are
resolved against their containing directory for Git ≥ 2.48's relative
worktree paths.

Also fixed: the stale `recover()` docstring, a dead README anchor,
`worktree_admin_left` hidden from `status`, the ownership-ref wording, the
unreferenced by-name `delete_branch`, the ignored-path count wording, the
slot-sibling boundary, and `.cws/quarantine` as a file or symlink (refused by
`validate_control_dir`, reported by `status`). A second and third fresh review
of the fix batches found and caused the ignored-directory, sentinel-coverage
(`discard.after_recheck` now follows the persist), repair-authentication,
occupant-handling, and tombstone-reporting corrections above. Final state:
the unit suite passes (`python3 -m unittest discover -s tests`), the complete
hardening campaign passes 56/56 in clone and worktree modes, ten-seed
hundred-step state-machine fuzz passes in both modes, and random-kill spawn,
collect, and discard cases pass in both modes. Phase 2 is closed.

Bughunt result (2026-08-28, Phase 2, after the Step 2.7 close): a close
read of every Phase 2 function plus a fresh sweep of the angles the reviews
had not stressed (two-process races, request-id retries against the lease,
odd task names and paths, sha256 repositories, fingerprint edge cases, fifty
workers, canonical's own checkout) found six confirmed defects and one edge
case, all fixed with regressions, and settled one likely finding as intended:

- **A task branch checked out in canonical or in a user's working tree was
  deleted from under that `HEAD`**, leaving it on an unborn branch (`git
  update-ref` has no checked-out guard). Cleanup now consults `git worktree
  list` and retains such a branch with `checked out at ...`; `recover`
  finishes once the checkout is released.
- **Three cleanup states were stuck in `discarding` forever with nothing to
  resolve**: an admin directory name Git had recycled for a newer worker, a
  branch moved and then deleted by hand, and a branch recorded as absent
  that the user later created under the same name. Each is now recognized as
  "nothing of ours remains": the ownership ref is dropped, a foreign branch
  is left alone, and the record finishes.
- **A branch recorded as absent could be deleted if someone created one
  under the name before cleanup** (the record could not distinguish "never
  recorded" from "recorded absent"). Absence is recorded as the all-zero id.
- **A directory or record named with a Unicode digit such as `²` crashed
  `status` and `recover`** (`str.isdigit` accepts what `int` rejects), and
  `01` was silently treated as slot 1; worker ids are now parsed only in
  canonical decimal form.
- **A non-UTF-8 byte in the workspace or canonical path crashed every
  command** while decoding Git's output, and a worktree worker there could
  never be discarded because its `.git` and admin `gitdir` pointer files were
  read as strict UTF-8; the Git runner decodes with `surrogateescape` and the
  pointer files are read as filesystem bytes.
- **`pending_spawn_details` bypassed the validator** (any field could be set
  on promotion); its keys must be spawn-detail fields and only those are
  applied.
- **`recover` could still be aborted for every worker by a non-Clonegrown
  exception** from one worker (a sibling of the Step 2.7 fix); the per-worker
  guard and the deletion resume now catch any exception, preserve the
  quarantine, and continue.
- **FIFOs and sockets were invisible to the custody fingerprint**; the walk
  now covers the whole worker tree except `.git`, so nested repositories,
  special files, and anything else Git does not list are fingerprinted.

Settled as intended and now documented: retrying a request id whose worker
was `discarded` returns that completed record, while `abandoned` and
`spawn_failed` make the id retryable. Observed but outside Phase 2 (for Phase
3/4): a collected worker whose repository directory was removed by hand can
neither be collected nor discarded until recovery marks it, and task names
ending in `.lock` fail spawn with a misleading message (Step 4.3).

## Phase 3 — Make state allocation, idempotency, status, and recovery auditable

### Step 3.1 — Make worker allocation create-only — complete 2026-08-28

- Add a create-only atomic record primitive. Before advancing `next_id`, prove
  that the worker record, slot, stage, quarantine, lock identity, and base ref
  for that ID do not already represent another allocation. Treat a stale
  `next_id` as corruption to diagnose, not permission to overwrite or silently
  skip evidence.
- Preserve the existing expected-old-zero base-ref creation and make rollback
  leave an observable gap rather than reusing a possibly ambiguous ID.
- Regressions corrupt `next_id`, pre-create each collision target, interrupt
  state/record/base-ref writes, and prove the old record and paths remain byte
  for byte intact.

Completion record (2026-08-28): `core.atomic_json_create` writes and
fsyncs a temporary file and links it to its final name with `os.link`, which
fails atomically if the name exists; it never replaces a record.
`worker.allocation_evidence` lists everything that already represents the
next id (record, slot, stage and quarantine directories, operation lock file,
base pin, worker refs) and `allocate_spawn` refuses with `workspace counter
is stale: ...` before advancing `next_id` if any exists. The base pin keeps
its expected-old-zero creation; a failure after the counter advanced (record
creation, including an unwritable records directory) withdraws only this
call's pin and leaves the id unused. New failpoints `allocate.after_state`,
`allocate.after_base_ref`, and `allocate.after_record` mark the windows.
`tests/test_allocation.py` corrupts `next_id`, plants each collision target,
crashes at each window, and proves the old record and its slot are byte for
byte intact, the counter is never advanced past evidence, and every
interruption leaves an observable gap.

### Step 3.2 — Validate idempotent request-index hits end to end — complete 2026-08-28

- Validate request-index field types, exact request ID, parameter digest, and
  worker ID before loading a record. Validate the target record against state
  and ensure its own request ID/digest point back to the same index.
- Before returning a settled record, authenticate live ready/collected workers,
  verify collected result refs, and prove gone workers have no owned live path.
  Corrupt or stale indexes fail closed with a status-visible diagnosis.
- Regressions cover missing records, nonnumeric IDs, cross-linked indexes,
  altered digests, replaced workers, missing result refs, tombstone residue,
  and concurrent valid reuse.

Completion record (2026-08-28): `worker.load_request_index` validates the
index's exact request id, digest format and value, and worker id type and
range, requires the named record to exist and validate, and requires that
record's own request id and digest to point back at the index.
`worker.authenticate_settled` runs before `_wait_for_existing` returns a
settled record: a ready or collected worker is authenticated on disk, a
collected result ref must point at the result, and a gone worker must have
no slot and no quarantine residue. `tests/test_allocation.py` covers a missing
record, nonnumeric and boolean ids, cross-linked indexes, altered and
malformed digests, a wrong request id, a replaced ready worker, a missing
result ref, tombstone residue, and three concurrent valid retries that all
receive the one worker.

### Step 3.3 — Turn `status` into a complete nonmutating invariant audit — complete 2026-08-28

- Audit live-status worker/stage/quarantine presence, worker authentication,
  expected branches and worktree admin entries, immutable and summary result
  refs, temporary base refs, tombstone residue, request indexes, and namespace
  refs with no record.
- Surface retained collection candidate refs and deletion/cleanup conflicts.
  Use stable issue codes plus bounded human context; never repair during
  `status` and never print secret config values or file contents.
- Extend the documented output contract and tests for each contradiction,
  including a missing repository that current `status` silently omits.

Completion record (2026-08-28): `clonegrown/audit.py` is the non-mutating
audit. `NamespaceRefs` enumerates `refs/cws/<ws>/` once and parses it by
worker id; `audit_worker` checks presence and authentication of live
workers, tombstone residue, stage residue, base pins (required while
spawning, stale afterwards, kept for broken workers), collected result and
summary refs, retained candidate refs, worktree branches, ownership refs and
admin directories, and every discarding state; `audit_request_indexes`,
`audit_namespace`, and `audit_lock_files` cover the workspace. `status`
emits the stable codes listed in the architecture with bounded
context and no secrets; a missing repository is now reported instead of
silently omitted. `tests/test_audit.py` produces every code and proves two
consecutive audits report identically and change neither `.cws` nor
canonical's refs.

### Step 3.4 — Reconcile only provably owned residue in `recover` — complete 2026-08-28

- Teach recovery to resume quarantined deletion, finish checked branch/admin
  cleanup, remove stale temporary base refs only when their worker/status makes
  ownership unambiguous, and retain candidate/result refs as custody evidence.
- Report ambiguous namespace refs, stale request indexes, and residue instead of
  deleting them. Recovery remains idempotent and continues past one corrupt
  record.
- Add repeated-recovery tests for every issue introduced in Step 3.3, including
  interrupted finalization and summary-ref repair.

Completion record (2026-08-28): `recover` reports orphan namespace refs,
stale and invalid request indexes, and orphan lock files without touching
them (`*-left` actions), keeps candidate and result refs as custody evidence,
drops a base pin only for a status that has no use for it and only at the
recorded base value (`base-ref-dropped`; otherwise `base-ref-ambiguous`),
and no longer deletes a tombstone's pin by name. `finish_deletion` drops a
preserved worker's pin only at its recorded value. Quarantine resumption,
ownership-checked branch and admin cleanup, and summary-ref repair were
already in place. `tests/test_audit.py` runs recovery twice for every issue,
including an interrupted collection finalization and summary-ref repair, and
proves it is idempotent and mutates only authenticated targets.

### Step 3.5 — Cold-review Phase 3 — complete 2026-08-28

- A fresh agent corrupts records, indexes, counters, refs, and paths while
  checking that `status` observes without mutation and `recover` mutates only
  authenticated targets.
- Re-run metadata red-team, state-machine, unit, and both hardening modes.

Cold-review result (2026-08-28): a fresh agent corrupted records, indexes,
counters, refs, and paths across twenty states in both worker modes and
confirmed that `status` never touched `.cws`, the refs, or the worktree
list, that every unowned residue survived repeated `recover` byte for byte,
that concurrent request-less spawns get distinct ids, and that every one of
the documented issue codes is emitted with no false positive in a healthy
lifecycle. It found five defects, all fixed in the same pass with
regressions in `tests/test_audit.py`: `status` refreshed every live worker's
Git index through `git status` (now `--no-optional-locks`, and the purity
test fingerprints every worker slot and canonical's `.git`; `core.fsmonitor`
is no longer copied into clones because it names a program `status` would
run); spawn recovery dropped a base pin at any value (now only at the
recorded base, else `base-ref-ambiguous`); summary-ref repair was silent and
unconditional (now `summary-ref-repaired` with a compare-and-swap); an
occupied `spawn_failed` slot was invisible to both commands (tombstone checks
now cover `spawn_failed`); and unvalidated records could hide a quarantine
entry from the orphan audit (both commands use validated records). A new
`owner-process-dead` code names an in-flight record whose recorded owner is
gone. Documentation now states the by-design manual remedies (a corrupt or
stale request index blocks its id until the file under `.cws/requests/` is
removed; a retained candidate ref stays as evidence) and the hard-link
requirement of create-only records, and no longer claims request-index hits
are unvalidated. Final checks: the unit suite, the complete hardening
campaign in clone and worktree modes, state-machine fuzz, and random-kill
cases all pass. Phase 3 is closed.

Bughunt result (2026-08-28, Phase 3, after the Step 3.5 close): a close
read of `audit.py`, allocation, request-index handling, and the `status` /
`recover` loops plus a fresh sweep (concurrency with the audit, request-id
races, namespace ref shapes, create-only races, two workspaces on one
canonical, two hundred workers) found three confirmed defects, one likely
finding settled as real, and four edge cases, all fixed with regressions:

- **Every ref write in Clonegrown's namespace followed symbolic refs**, so a
  symbolic ref planted under `bases/<id>`, `workers/<id>/result`, or
  `workers/<id>/branch-owner` made `recover`, `collect`, or `discard` delete
  or move canonical's own branch (`refs/heads/trunk` gone after a
  `base-ref-dropped` or `summary-ref-repaired` report). All namespace writes
  now go through `write_ref`/`delete_ref` with `--no-deref` (and `option
  no-deref` in the branch transactions) and refuse a symbolic ref outright;
  `status` reports `namespace-ref-symbolic` and excludes such refs from every
  per-worker view.
- **Per-worker operations took the worker lock before checking the record
  existed**, so a mistyped `discard 99` created `locks/99.lock`, which
  create-only allocation then treated as evidence and refused id 99 forever.
  `require_worker` runs before any lock is taken, and `recover` removes an
  orphan lock file (`orphan-lock-file-removed`).
- **An unowned staging directory blocked allocation while `status` reported
  nothing.** `orphan-stage` is now audited and reported (`orphan-stage-left`
  in recovery), so the allocation refusal's advice to inspect `status` holds.
- **A request-id retry racing an abandonment returned the tombstone with
  exit 0** (`abandoned` is both settled and retryable). A waiter that
  observes a retryable outcome now allocates afresh, up to three times.
- `status`/`recover` re-verified canonical for every record (twenty seconds
  for two hundred workers); they now verify once and validate records
  against it. A dangling symbolic ref (invisible to `for-each-ref`) is asked
  of Git directly where it matters: allocation evidence, a spawning worker's
  pin name, and a collected worker's summary name; the ready-time pin drop
  is best effort so a symbolic pin cannot fail a spawn that is already ready. A temp file left beside a record by a crash is reported as
  `unexpected-metadata-file`; `results/<hex>` refs are classified by the
  object format's exact length; the PLAN's "twenty-five codes" count was
  replaced by a reference to the architecture list.

## Phase 4 — Restore exact Git semantics and safe operational errors

### Step 4.1 — Make Git execution explicit, sanitized, structured, and redacted — complete 2026-08-28

- Make `git()` always use `clean_git_env`, regardless of the configured
  executable's basename; keep generic non-Git `run()` semantics separate.
- Introduce a structured command failure carrying return code, operation, and
  private diagnostic data while rendering a redacted public command. Mark
  config values and remote URLs sensitive at call sites; redact URL userinfo
  and known values from stderr/stdout as well as argv.
- Preserve direct argument arrays and noninteractive Git. Do not add a shell or
  a subprocess abstraction hierarchy.
- Regressions use a renamed `CLONEGROWN_GIT`, hostile `GIT_*` variables,
  credential-bearing URLs/config values, timeouts, and ordinary useful Git
  stderr. Sentinel secrets must not appear in CLI output or stored errors.

Completion record (2026-08-28): `git()` now supplies `clean_git_env()`
unconditionally, independent of the configured executable's filename, while
generic `run()` preserves its caller's environment semantics. Clone
provisioning also goes through `git()`, so every package-owned Git execution,
including raw-byte listings and a renamed `CLONEGROWN_GIT`, strips the
process-level `GIT_*` overrides and sets `GIT_TERMINAL_PROMPT=0`.
`CommandFailure` is a structured `ClonegrownError` with return code (or
`None` for a timeout), named operation, safe public command/stdout/stderr, and
underscore-prefixed raw in-memory diagnostics. Its public rendering replaces
caller-marked values and URL userinfo while retaining unrelated diagnostic
text. Every write of a copied configuration value and remote URL, plus clone
and fetch source locations, marks the value sensitive; lifecycle persistence
continues to store only `str(error)`, so the raw values do not enter worker
records. Direct argument arrays remain in use and no shell, runtime package,
or subprocess wrapper hierarchy was added. `tests/test_core.py` adds nine
regressions for literal `CLONEGROWN_GIT` selection, exact and prefix hostile
Git variables, generic-run separation, nonzero and timeout structure,
raw-byte output, literal hostile arguments, useful ordinary stderr, and
end-to-end copied-config/remote failures; the sentinel values are absent from
both CLI stderr and the durable worker `error`. Verification: focused tests
9/9; unit suite 156/156; hardening campaign 56/56 in clone mode and 56/56 in
worktree mode; out-of-checkout byte compilation, retired-claim search, direct
Git-path search, and `git diff --check` all pass.

### Step 4.2 — Build a pure remote/config copy plan, then apply it imperatively — complete 2026-08-28

- Represent a config occurrence as valueless or string-valued, preserving an
  explicit empty string separately. Preserve occurrence order and current
  structural/include exclusions.
- Canonicalize relative local fetch and push URLs against the canonical
  repository before installing them in a differently located clone. Leave
  absolute local paths, URL schemes, and scp-like remote syntax semantically
  unchanged.
- Calculate the complete remote/config plan without mutation, validate it,
  then apply it in one readable provisioning stage using the redacted runner.
  A config read failure is an error, not an empty configuration.
- Document the minimum clone-fidelity contract across remotes, local config,
  auxiliary refs, info files, sparse policy, hooks, and object sharing; every
  copied class needs one compatibility reason and every omission needs a stated
  boundary.
- Regressions cover valueless versus empty values, repeated keys, includes,
  relative fetch/push paths, spaces and Unicode, credential redaction, remote
  name collision, and a worker moved far from canonical.

Completion record (2026-08-28): `ConfigOccurrence` now represents every
ordered config entry as either `None` (genuinely valueless) or a string (with
`""` remaining explicitly empty). `build_clone_config_plan()` reads raw and
include-expanded repository-local config with checked Git commands, calculates
the source-remote collision name, applies the existing structural/path-bound
exclusions, flattens effective include values, and validates the complete
immutable plan without mutation. `apply_clone_config_plan()` is the sole
imperative remote/config stage: it validates before touching the staged clone,
uses Git to validate remote names, clears Git-generated defaults, writes every
source value through the redacting runner, preserves cross-key and repeated
occurrence order with temporary sections, atomically restores genuinely
valueless syntax, and verifies the applied config and remote set. Relative
nonempty `url`/`pushurl` local paths are resolved against canonical before the
worker moves; absolute paths, schemes, scp-like syntax, empty strings, and
valueless entries are not reinterpreted. A config read error now aborts rather
than becoming `{}`. `ARCHITECTURE.md` records the minimum fidelity contract and
the compatibility reason and omission boundary for remotes, local config,
auxiliary refs, info files, sparse policy, hooks, and objects; README and the
installed skill summarize the user-facing behavior. `tests/test_repository.py`
adds four regressions covering pure planning, exact value/order/include
semantics, read failure and pre-mutation validation, relocated relative fetch
and push paths with spaces/Unicode, unchanged transports and canonical config,
and `cws-source` collision. The Step 4.1 credential-failure tests continue to
exercise both config and remote apply paths. Verification: repository tests
4/4; command/redaction tests 9/9; unit suite 160/160; hardening campaign 56/56
in clone mode and 56/56 in worktree mode; out-of-checkout byte compilation,
retired-function search, and `git diff --check` all pass. No dependency or
external protocol changed.

### Step 4.3 — Align the Python API and reject invalid generated branches early — complete 2026-08-28

- Change the Python `spawn` default to `strong=False` and pin CLI/API parity in
  tests and examples. Preserve explicit `strong=True` and worktree rejection.
- Validate the complete generated branch with `git check-ref-format --branch`
  before advancing allocation metadata or creating refs. Cover `.lock`, ref
  syntax edge cases, maximum task length, Unicode sanitization, and hostile
  input without shell execution.
- Remove the repository-unreferenced public `CWSError` alias and update
  imports/docs while retaining the on-disk `cws` protocol and test-variable
  names until their separately planned gate exists.

Completion record (2026-08-28): the public `spawn()` signature now defaults to
`strong=False`, matching the unchanged CLI default; `strong=True` still makes
a physically independent clone, and worktree mode still rejects that flag.
The README Python example and architecture now state the shared default and
show default clone, explicit strong clone, and default worktree calls.
Allocation computes the complete deterministic branch and calls Git's
`check-ref-format --branch` after resolving the base but before the collision
scan or any durable allocation write: an invalid branch cannot advance
`next_id` or create a base pin, worker record, request index, stage, or slot.
Valid branch naming and `sanitize_task()` are unchanged; focused cases pin the
48-character slug bound, 10,000-character input, Unicode-only and
mixed-Unicode input, leading/trailing/doubled dots, `@{`, slash and backslash
syntax, `.lock`, and literal shell punctuation. `CWSError` was removed from
`core.py`, the package namespace, and `__all__`; `ClonegrownError` remains the
sole public error type. Every on-disk `.cws` directory, `refs/cws` namespace,
and campaign test variable remains unchanged. The six regressions in
`tests/test_api.py` cover actual CLI/API default parity, explicit isolation
modes, the public export boundary, and pre-mutation rejection with
metadata/ref snapshots; sanitizer and Git ref edges; and hostile task text
without shell execution. Verification: focused
API tests 6/6; allocation 10/10; CLI 4/4; worktree 24/24; unit suite 166/166;
hardening campaign 56/56 in clone mode and 56/56 in worktree mode;
out-of-checkout byte compilation, retired-alias/stale-default searches, and
`git diff --check` all pass. No dependency, output key, valid branch name,
lifecycle transition, or durable protocol changed.

### Step 4.4 — Give every public operation safety-context errors — complete 2026-08-28

- At init/spawn/collect/discard/recover boundaries, translate low-level
  filesystem, JSON, subprocess, and conversion errors into `ClonegrownError`
  without catching process-control exceptions.
- Each error states the operation/stage, what durable mutation completed,
  whether work is believed preserved or unverified, and whether `recover` or a
  manual inspection is required. Do not claim safety where a check failed.
- Keep internal causal exceptions chained for developers while the CLI emits
  one redacted, actionable error with no traceback.
- Regressions inject failures before/after irreversible boundaries and assert
  both custody state and exact safety context.

Completion record (2026-08-28): `operation_boundary()` now catches ordinary
`Exception` at the public `init`, `spawn`, `collect`, `discard`, and `recover`
boundaries while deliberately leaving process-control `BaseException`
subclasses untouched. Every translated `ClonegrownError` has ordered
operation/stage, durable-state, work-preservation, recovery, and cause fields;
the original exception remains chained as `__cause__`. The active context is
local to the call and advances before and after allocation, metadata/ref
writes, fetch, publication, quarantine, authorized deletion, terminal cleanup,
and recovery reconciliation. A primitive that raised is therefore reported as
unverified rather than guessed complete or absent. Existing `CommandFailure`
targeted redaction remains in its cause text and its private diagnostics remain
available through the chain; arbitrary exception text is still not claimed to
be secret-scanned. The unchanged CLI catches the translated error, writes it
once to stderr with no traceback, and leaves stdout empty.

Recovery continues past one worker's ordinary failure; its existing
`recovery-failed` action now adds stage, durable-state, work-preservation, and
next-action fields. `tests/test_safety_errors.py` adds eight regressions for
filesystem, JSON, subprocess, conversion, and even unrenderable exception
causes; process-control passthrough; causal chaining and CLI redaction; and
real failures after initializing-state commit, publication, candidate fetch,
and quarantine rename with custody checked before recovery. The first full
run exposed one compatibility regression: contextual text made the bounded
large-ignore refusal 608 characters. The cause was the verbose pre-deletion
checkpoint, which was shortened without removing a required field; the single
test then passed before the full rerun. Verification: focused safety tests 8/8;
allocation 10/10; quarantine 32/32; worktree 24/24; CLI 4/4; command/redaction
9/9; API 6/6; state 11/11; lease 10/10; unit suite 174/174; hardening campaign
56/56 in clone mode and 56/56 in worktree mode; out-of-checkout byte
compilation and `git diff --check` pass. No dependency, public signature,
successful result shape, durable schema/ref protocol, lifecycle transition, or
custody behavior changed. `claim`, `release`, `status`, and direct low-level
`CommandFailure` behavior remain unchanged.

### Step 4.5 — Cold-review Phase 4 — complete 2026-08-28

- A fresh agent probes custom Git execution, relative URLs, valueless config,
  secret-bearing failures, branch generation, API defaults, and low-level error
  conversion. It verifies that redaction does not erase the information needed
  to diagnose a failure.
- Run focused compatibility tests, unit tests, and both hardening modes.

Completion record (2026-08-28): fresh, read-only reviewers probed every named
Phase 4 surface and proved ten defect classes that the completed Step-level
tests had not covered. Each cause was confirmed before modification, fixed
within this pass's ten-fix ceiling, given focused regression coverage, and
re-read by a fresh agent after the final edit:

1. Process-level `GIT_NO_REPLACE_OBJECTS` and `GIT_REPLACE_REF_BASE` could
   change the history Clonegrown saw; both now leave every package Git process
   with the rest of the hostile `GIT_*` environment.
2. Internal staging/quarantine worker tokens could enter contextual and
   durable error text; failure construction and persistence now apply one
   targeted custody-token redactor while retaining ordinary diagnostics.
3. `GeneratorExit` reached lifecycle rollback code even though the public
   boundary propagated it; rollback now runs only for ordinary `Exception`,
   so all process-control exceptions leave the in-flight durable state alone.
4. An exception whose `__str__` raised could abort recovery before later
   workers; exception rendering is bounded and recovery records the failed
   worker before continuing.
5. CLI-only input/workspace discovery sat outside the five operation
   boundaries, and a missing custom Git executable leaked `FileNotFoundError`;
   discovery now has the named operation context and process-launch `OSError`
   becomes a structured `CommandFailure` with its original cause chained.
6. A Git-invalid remote name was rejected only after the staged clone changed;
   all names are now checked before mutation, while valid leading-dash names
   remain literal through `--`.
7. Redacting a one-character copied value such as `a` erased unrelated key and
   diagnostic text; marked argv values redact exactly and short values in
   output redact only as standalone tokens.
8. A worker lock/setup failure escaped the per-worker recovery handler and
   prevented later workers from being reconciled; setup, locking, record load,
   reconciliation, and context-manager exit now report per worker and continue.
9. A hand-built plan could carry a Git-invalid config key past validation and
   mutate the clone before `git config` refused it; section/subsection/variable
   grammar is now validated before the first Git call, without rejecting legal
   spaces and URL punctuation in subsection names.
10. The first custody-token regex missed a real quoted `PermissionError`
    filename because a quote followed the 32-hex component; the specific
    Clonegrown path pattern now redacts the token independent of that delimiter.

The first full-suite run then caught a compatibility regression introduced by
the token hardening: recursively redacting every successful CLI string hid the
documented `status.quarantine_path`. The cause was isolated before editing;
successful result filtering again preserves that recovery path and hides its
separate token field, while public and durable failure text remains redacted.
The exact status and quoted-error tests passed, and a final fresh read-only
review found no open finding in the corrected output flow.

Final verification: command/redaction tests 12/12; repository fidelity tests
8/8; safety/error tests 14/14; API tests 6/6; CLI tests 4/4; unit suite 187/187;
hardening campaign 56/56 in clone mode and 56/56 in worktree mode;
out-of-checkout byte compilation, `sh -n install.sh`, trailing-whitespace
search, and `git diff --check` pass. No dependency, public signature,
successful result key set, durable schema/ref protocol, or successful
lifecycle behavior changed in this cold-review Step. Phase 4 is complete; the
next unfinished work is Phase 5 Step 5.1.

## Phase 5 — Separate correctness from benchmarks and close validation gaps — complete 2026-08-29

### Step 5.1 — Make concurrency correctness deterministic and benchmarking nonblocking — complete 2026-08-29

- Keep eight-way uniqueness, no-overwrite, request-id, and state-integrity
  assertions blocking. Remove the single-sample wall-time ratio from the
  correctness result.
- Add a manual/scheduled benchmark job that measures multiple single and
  parallel samples per worker mode, reports raw samples plus median and spread,
  and never turns runner noise into a correctness failure.
- Verify the formerly red worktree scenario repeatedly without code changes;
  CI is green only because all deterministic assertions pass, not because the
  threshold was loosened.

Completion record (2026-08-29): the verified starting implementation was
`t_parallel_spawns_unique` in `tests/campaign/hardening_suite.py`: it divided
one eight-way elapsed time by one single-spawn elapsed time and failed the
correctness case when that one ratio reached 8.0. The roadmap records the
worktree CI failure as that assertion alone, not an ID or state-integrity
failure. Before editing, ten unchanged local worktree repetitions all kept
their IDs unique while the timing ratio varied from 4.697 to 6.103, confirming
that the measured value varies independently of the invariant being tested.

Product executable code did not change. The deterministic hardening case now
launches exactly eight concurrent, distinct request IDs and blocks on the exact
ID set, exact create-only worker-record set, record task/request/status
identity, request-index-to-record agreement, `next_id`, and a clean public
`status` audit. It records no timing. New executable measurement tooling in
`tests/campaign/spawn_benchmark.py` creates a fresh fixture for every single
and parallel sample, records five raw samples per clone/worktree mode plus
per-worker times, and reports median, median absolute deviation, minimum, and
maximum for single time, parallel time, and their ratio. Timing has no pass/fail
threshold; only an invalid command, JSON result, ready state, or worker-ID set
invalidates a measurement. The script refuses output inside the checkout.

Configuration and documentation changed separately: the new
`.github/workflows/spawn-benchmark.yml` has only weekly and manual triggers,
runs the five-sample/eight-way measurement in both modes, and prints its raw
JSON and summary without adding a package or action dependency;
`research/REPRODUCE.md` gives the exact local commands and evidence boundary.
The push/pull-request `ci.yml` remains unchanged, so its hardening result is now
determined only by deterministic assertions.

Verification on the final code before this completion record: focused clone
and worktree concurrency cases passed; the formerly red worktree case passed
10/10 consecutive runs without code changes, each with IDs 1–8, eight records,
eight request indexes, and zero audit issues. The exact scheduled benchmark
commands completed five samples in each mode (clone median ratio 4.695, range
4.170–5.350; worktree median 5.084, range 4.378–5.906), with JSON under
`/tmp`. The unit suite passed 187/187; the complete hardening campaign passed
56/56 in clone mode and 56/56 in worktree mode; out-of-checkout byte
compilation, `sh -n install.sh`, YAML parsing, changed-file trailing-whitespace
search, and `git diff --check` passed. Public CLI/API behavior, durable state,
Git refs, lifecycle semantics, existing CI triggers, preserved historical
evidence, and runtime dependencies are unchanged. The next unfinished work is
Phase 5 Step 5.2.

### Step 5.2 — Add real parent/child interruption coverage — complete 2026-08-29

- Add real-process cases that kill only the Python parent while a spawned Git
  child may remain alive, including the exact worktree-add/admin-persist
  window, clone provisioning, collection fetch, and worktree repair/cleanup.
  Track child exit and filesystem/ref state before invoking recovery.
- Extend crash matrices for every new lease/quarantine/cleanup boundary. If a
  new failure appears, stop this Step after naming its cause and insert a
  focused fix Step; do not patch the harness around it.

Completion record (2026-08-29): the verified starting implementation had no
real parent-only process interruption test. `random_kill.start_and_kill` started
a process session and sent `SIGKILL` to its whole process group, while the
production Git runner waited synchronously in `subprocess.run`; consequently,
those campaigns killed Python and its Git descendant together. The exact
`claim` and `release` mutations were durable saves with no following crash
boundary, and `forget_worktree` performed administration-directory cleanup
followed by task-branch cleanup with no boundary between the two phases. The
existing discard matrix covered the six discard/quarantine boundaries but
neither of those internal worktree cleanup phases.

Before product-code edits, six temporary probes under `/tmp` used the existing
configured-Git seam to pause the direct Git child, kill only its Python parent,
let the child complete, inspect its exit and resulting record/files/refs, and
then recover. They covered worktree add before administration-path persistence,
clone provisioning, collection fetch, published worktree repair, quarantined
worktree repair, and transactional branch cleanup. All six passed against the
unchanged lifecycle implementation, so this Step found no product defect and
did not insert a corrective Step. The first narrow probe had inherited the
killed parent's output pipes and made the real Git process receive `SIGPIPE`;
the child result proved that harness artifact, and the temporary probe was
corrected to capture Git output before any product conclusion was drawn.

Executable product changes are limited to four inactive-by-default test
boundaries: `lease.after_claim`, `lease.after_release`,
`discard.after_admin_cleanup`, and `discard.after_branch_cleanup`. They occur
after the named durable lease mutation or external cleanup phase and do not
change an ordinary CLI/API path, durable schema, Git protocol, or cleanup
order. Test changes are separate:
`tests/campaign/blocking_git.py` and `tests/test_parent_interruption.py` turn the
six probes into deterministic regressions that prove the direct Git child is
alive before and after parent death, wait for its successful exit, inspect
filesystem/ref/record state before recovery, and require a clean recovered
audit. The hardening campaign adds a lease crash case and now has 57 cases;
its discard matrix covers six clone boundaries and eight worktree boundaries,
and the unit quarantine matrix covers the same mode-specific cleanup points.
`ARCHITECTURE.md` and `research/REPRODUCE.md` document the tests and exact
commands; no generated result was added to the checkout.

Verification on the final code: the six parent-interruption tests passed in
24.086 seconds; the focused lease module passed 10/10 and quarantine module
32/32; both focused lease and discard matrices passed in clone and worktree
modes. The complete unit suite passed 193/193 in 359.293 seconds, and the
hardening driver exited zero for all 57 defined rows in both modes with results
under `/tmp`; Step 5.7 later established that each total was 56 exercised
passes plus one reftable skip that the old reporter mislabeled `PASS`.
Out-of-checkout byte compilation, shell syntax
validation with `sh -n install.sh`, workflow YAML parsing, changed-file
trailing-whitespace search, executable-helper validation, and a clean
`git diff --check` passed. Phase 5 Step 5.3 is next.

### Step 5.3 — Put bounded randomized campaigns on a scheduled lane — complete 2026-08-29

- Run bounded random-kill and state-machine seeds for clone and worktree modes
  on a nightly/manual workflow with seed, step count, Python/Git versions, and
  artifacts recorded. Keep PR CI deterministic and reasonably short.
- Make a failed seed directly replayable with one documented command and retain
  no generated output in the checkout.

Completion record (2026-08-29): the verified starting repository had no
scheduled randomized workflow. Push/pull-request `ci.yml` ran only unit and
deterministic hardening checks, while the Step 5.1 workflow was a separate
weekly/manual timing benchmark. `random_kill.py` and
`state_machine_fuzz.py` already accepted bounded seed ranges and caller-chosen
output paths, but exact baseline JSON inspection proved that neither recorded
Python/Git/commit provenance or a replay command; state-machine output also did
not identify its worker mode. One pre-change clone seed from each harness
passed, establishing the runnable baseline before edits.

Product executable code did not change. New test-harness executable
`tests/campaign/campaign_record.py` records the Python implementation, version,
and build, Git version, platform, checked-out commit SHA, and an explicit
allowlist of non-secret GitHub run fields. It constructs validated literal
commands narrowed to one worker mode, one seed, one operation when applicable,
and the recorded state-machine step count. Both randomized harnesses now put
that environment object at the top level, identify their campaign and worker
mode, and attach the exact `replay_command` to every result row, including a
row that reports a caught seed failure. Four new unit tests cover exact command
rendering, injection rejection, bounds, and real environment provenance.

Configuration changed separately: new
`.github/workflows/randomized-campaigns.yml` has only nightly (09:37 UTC) and
manual triggers. Six matrix jobs run spawn/collect/discard random-kill cases in
clone and worktree modes; two run state-machine fuzzing in both modes. Nightly
runs use the workflow run number as their first seed and default to two seeds
per job and 50 steps per state-machine seed. Manual counts and steps are finite
choices (1/2/3/5 seeds and 25/50/75/100 steps), and every job is capped at 30
minutes at this Step 5.3 checkpoint; Step 5.7 later replaces that bound with 45
minutes and explicit per-step limits. Matrix fail-fast is disabled so one
failure cannot cancel other evidence, but no campaign is allowed to continue
on error. An artifact step uses `if: always()`, 30-day retention, and
missing-file failure; job cancellation or runner loss can still prevent it
from completing. Artifact names include mode/operation, run ID, and run
attempt. The official v7 checkout, Python setup, and artifact actions add no
project runtime package; artifact upload is the one new scheduled-workflow
dependency. Existing PR CI and the benchmark workflow are unchanged.

Documentation changed separately in `ARCHITECTURE.md` and
`research/REPRODUCE.md`, including two complete one-seed example commands and
the instruction to check out `environment.commit_sha` before running a row's
literal replay command. Generated fixtures and JSON remained under `/tmp`.
The new hosted workflow has not been claimed as live evidence because this
working tree is uncommitted; Step 5.7 still requires replaying a real retained
artifact before Phase 6.

Verification on the final code: four focused artifact-contract tests passed;
a post-change worktree collection seed was actually killed with `SIGKILL`,
recovered, and emitted complete provenance, and its exact recorded command plus
the fuzzer's exact recorded command both replayed successfully. The workflow's
full nightly defaults passed locally: 12/12 random-kill seeds (three operations
× two modes × two seeds), all with an actual killed process, and 4/4
state-machine seeds × 50 steps (two modes × two seeds). All eight result JSON
files passed schema/provenance/replay assertions. The full unit suite passed
197/197 in 369.469 seconds; the hardening driver exited zero for all 57 defined
rows in each mode (later corrected by Step 5.7 to 56 exercised passes plus one
reftable skip per mode). Workflow structure validation proved
eight bounded jobs, both artifact-on-failure steps, no permissive error flag,
and no push/pull-request trigger. Out-of-checkout byte compilation, shell
syntax validation with `sh -n install.sh`, YAML parsing, changed-file
trailing-whitespace search, and a clean `git diff --check` passed. Phase 5
Step 5.4 is next.

### Step 5.4 — Test the supported version and operating-system envelope — complete 2026-08-29

- Run destructive-path tests on macOS as well as Linux. Test the oldest
  supported Python (3.11) and the latest stable Python at execution time.
- Derive a minimum Git version from the commands Clonegrown actually uses,
  document it, and add one job that runs that exact minimum rather than relying
  only on mutable hosted-runner Git versions.
- Keep native Windows explicitly unsupported in 0.x; do not imply POSIX
  `fcntl`, rename, or deletion results transfer to Windows.

Completion record (2026-08-29): the blocking unit/destructive CI job is now a
four-job endpoint matrix: Linux and macOS, each on Python 3.11 and
setup-python's latest stable `3.x` selection. Matrix fail-fast is disabled, and
the job names the installer, lease, quarantine, worktree-cleanup, and real
parent-interruption destructive paths included in the full unit suite. Python
3.14.7 was the latest stable release when the boundary was established. Native
Windows remains explicitly unsupported because Clonegrown imports `fcntl` and
depends on POSIX lock, same-filesystem rename, and deletion semantics.

Git 2.29.0 is the derived floor: Git's 2.29 release introduced both directly
required operations that 2.28 lacks, `fetch --no-write-fetch-head` and
`worktree repair`. A dedicated CI job downloads the official 2.29.0 source
archive, verifies its pinned SHA-256 digest, builds it without unused optional
HTTP/OpenSSL/gettext/Tcl/Tk components, proves that both `PATH` and
`CLONEGROWN_GIT` select that binary, and runs all 197 unit/destructive tests
plus both 57-case hardening modes. The hardening harness and parent-only Git
blocker now honor `CLONEGROWN_GIT`, so the job tests the claimed binary rather
than only printing its version. The existing line-oriented fallback keeps the
newer `worktree list --porcelain -z` form out of the minimum.

The exact-minimum worktree campaign exposed one real product compatibility
failure before completion: on Git 2.29, `git worktree add` copied a sparse
pattern file but did not populate a new linked worktree's worktree-local
`core.sparseCheckout` flags when `extensions.worktreeConfig` was enabled. The
worker therefore materialized an excluded path. `copy_sparse_policy` now
copies the effective sparse flags into that worktree's local config before
checkout; shared-config worktrees and clone policy retain their prior behavior.
The campaign's assertion now reports included and excluded path failures
separately. A separate exact-Git probe also proved that a linked worktree with
shared sparse configuration still inherits those flags and excludes the
omitted path.

Post-change local verification on Linux passed 197/197 tests on Python 3.11.15
with exact Git 2.29.0 (232.069 seconds) and 197/197 on Python 3.14.7 with Git
2.43.0 (256.234 seconds). The exact-Git hardening driver exited zero for all 57
defined rows in both modes; Step 5.7 later corrected each result to 56
exercised passes plus one reftable skip. The focused sparse case also passed on
current Git.
Two earlier full suites run simultaneously each hit the same fixed 20-second
parent-interruption polling deadline under sustained local contention. No code
changed during diagnosis: that exact branch passed five serial probes and four
paired endpoint probes, after which both isolated full endpoint runs passed.
The CI matrix uses isolated jobs. Hosted run 33234743380 at committed revision
`17bb42a` supplies a green Python 3.11 full-suite baseline on both Ubuntu and
macOS. It predates the uncommitted Phase 5 additions, so hosted confirmation of
those additions and the expanded latest-stable jobs necessarily awaits
publication of this combined tree and remains an explicit Step 5.7 green-CI
gate; this completion record does not claim those unrun results.

### Step 5.5 — Pin filter/resource behavior or state the boundary — complete 2026-08-29

- Add real-repository tests for a custom clean/smudge filter and any Git LFS
  behavior that can be exercised reproducibly without credentials. If Git LFS
  is not made a supported dependency, state it as unvalidated/unsupported
  rather than simulating it.
- Exercise write, rename, and deletion failures through targeted fault
  injection, including no-space and partial-cleanup equivalents. State that
  genuine disk/inode exhaustion and network/distributed filesystems remain
  outside support until run on those systems.

Completion record (2026-08-29): the verified starting implementation already
copied eligible repository-local `filter.*` config into clone workers and
shared canonical config with worktree workers, but no test executed a real
filter driver. The local environment had no `git-lfs` command, and the project
had no LFS dependency. No product runtime change was needed: a new blocking
real-Git test creates an available external clean/smudge driver, selects it
through tracked attributes, proves Git stores cleaned bytes, proves clone and
worktree checkout both materialize smudged bytes, then edits, cleans, commits,
collects, releases, and discards each worker. It also proves the collected
commit retains the clean representation. Clonegrown still copies or shares
eligible config, never the external program itself.

Git LFS remains unsupported rather than simulated. Taking it would add a
separately installed and updated executable, Git hook and filter-process
behavior, credential and remote-object-transfer semantics, and an additional
upstream security-advisory surface. At the decision point, official Git LFS
3.8.0 Linux/macOS archives were approximately 5.6–6.2 MB compressed. That
dependency did not earn its place for the narrower clean/smudge behavior
Clonegrown can test directly, so the runtime and Python dependency trees remain
unchanged. Long-running filter-process drivers, delayed checkout,
credentialed/network filters, and other filter protocols remain unsupported.

Three deterministic fault tests pin the represented filesystem transitions.
An injected `ENOSPC` at file `fsync` before atomic publication leaves an old
record byte-identical, leaves a create-only record absent, and removes both
temporary files. Injected `EXDEV` at the slot-to-quarantine rename keeps the
complete worker in its slot, clears the unfulfilled quarantine metadata,
withdraws the discard intent, and permits a successful retry. Injected `EIO`
after recursive deletion removes one file leaves the remaining content in its
durably authorized quarantine, records `discarding`, and lets `recover` finish
without pretending the partial tree is intact. These are fault-injection
equivalents, not actual capacity or filesystem tests; genuine disk/inode
exhaustion and network or distributed filesystems remain unvalidated and
unsupported.

Verification on the final tree passed the four focused cases on Python 3.11.15
with exact Git 2.29.0 (6.914 seconds) and Python 3.14.7 with Git 2.43.0 (7.417
seconds). The complete suite passed 201/201 at the exact-minimum endpoint
(268.464 seconds) and 201/201 at the latest-stable endpoint (277.085 seconds).
No `clonegrown/` file, workflow, on-disk protocol, runtime dependency, or
normal product behavior changed. Out-of-checkout compilation at both Python
endpoints, workflow YAML parsing, `sh -n install.sh`, executable-helper and
trailing-whitespace checks, and `git diff --check` passed.

### Step 5.6 — Run a small real-repository qualification matrix — complete 2026-08-29

- On disposable clones outside this checkout, run lifecycle and recovery
  scenarios against at least: an ordinary history-heavy repository, a
  ref-heavy repository, and a repository using submodules/sparse checkout or
  filters. Record exact public commit IDs, Git/Python versions, worker modes,
  and results under `research/`.
- Treat this as validation evidence, not a universal performance policy and
  not proof that coding agents make fewer mistakes.

Completion record (2026-08-29): a new standard-library harness created all
fixtures outside this checkout and ran six scenarios: default clone and linked
worktree workers against curl/curl at
`8a2bb9ca241bbd82a0da536f6f39dca9037dd046`, Git's full ref set at
`c73e85354c275c9d409b26445089bc16940fc527`, and a second checkout of that Git
commit narrowed to `Documentation`, `.gitmodules`, and the
`sha1collisiondetection` gitlink. The curl profile had 39,564 commits reachable
from `HEAD`; the Git ref profile had 1,019 refs, including 1,008 tags; and the
feature profile retained the mode-`160000` gitlink while excluding `Makefile`.

Every public source clone began with `--no-checkout`. Before materialization,
the harness applied non-cone sparse rules excluding all `.env`, `*.env`,
`.env.*`, and `*.env.*` filename patterns at every depth. It never searched
for, listed, opened, or read an excluded file, made no claim about whether one
exists in public history, and did not initialize the public submodule. The
history/ref roles concern their full cloned histories and ref/object sets; the
only worktree omissions in those two profiles were the mandatory safety
patterns.

Each scenario required an intentional exit 88 after worker publication,
`spawn-publish-finished` recovery, an idempotent retry returning worker 1 at
the exact public base, preserved sparse materialization, a new committed and
collected result, release and discard, a removed worker path, a persistent
immutable result ref, an empty `status` audit, and a passing connectivity-only
Git check. All 6/6 passed on CPython 3.12.3 and Git 2.43.0 on Linux in 168.309
observed seconds; timing did not affect pass/fail. The executed package tree
and harness hashes, exact source/result commits, versions, counts, modes,
warnings, raw timings, and assertions are preserved in
`research/REAL_REPOSITORY_QUALIFICATION.json` (SHA-256
`7d0e36fd68bcb8d6b22af5e88d5c7f248147c81e1c09d5cd773a190e0928cb6c`),
with interpretation in `research/REAL_REPOSITORY_QUALIFICATION.md` and the
exact rerun command in `research/REPRODUCE.md`.

The run added no product behavior, workflow, protocol, or dependency. Its
477,078 KiB of recorded packed public-source objects and all worker fixtures
were disposable; the successful run proved its temporary root removed. This
is bounded evidence for the exact matrix, not a performance policy, broader
platform/repository support, or evidence about coding-agent mistake rates.

Post-record close verification passed the explicitly filtered complete unit
suite, 201/201 in 271.144 seconds on the local CPython 3.12.3/Git 2.43.0
environment. An initial explicit-file invocation imported tests as
`tests.test_*` without putting `tests/` on the import path: four independent
tests passed and 15 modules stopped at `ModuleNotFoundError: support` before
their test bodies. No file changed; the corrected explicit-module runner added
that path, matching normal discovery, and passed all 201. JSON assertions,
artifact/harness SHA-256 checks, new-file trailing-whitespace inspection,
executable-helper mode, and combined `git diff --check` passed. Phase 5 Step
5.7 is next.

### Step 5.7 — Cold-review Phase 5 — complete 2026-08-29

- A fresh agent audits the workflows for test theater, machine-sensitive gates,
  missing replay data, unsupported-platform overclaims, and failures hidden by
  `continue-on-error` or permissive shell behavior.
- Require green deterministic CI and replay at least one artifact from every
  scheduled campaign before Phase 6.

#### 2026-08-29 local cold-review and repair checkpoint — hosted gate pending

A fresh read-only reviewer audited the Phase 5 workflows and harnesses, and
the main pass reproduced every confirmed issue before editing. The audit found
no `continue-on-error`, permissive-shell failure suppression, timing-based
correctness gate, or unsupported native-Windows claim. It did confirm seven
test/workflow weaknesses:

1. Random-kill spawn rows could exit zero after the target had already exited;
   seed 0 in both worker modes and a fresh seed-2 probe recorded
   `killed: false, rc: 0` while printing `PASS`.
2. The four campaign-record tests covered helper return values but not the
   artifacts produced by either campaign. Mutations that recorded the entire
   process environment or removed either harness's replay assignment still
   passed all four tests.
3. State-machine metadata loading swallowed every JSON/read exception. A
   corrupted numeric worker record left zero visible records and the invariant
   returned true.
4. The hardening driver labeled conditional format skips as passes and added
   them to `passed`; local Git 2.43.0 therefore printed 57 passes although it
   exercised 56 and skipped reftable.
5. Campaign provenance and fixture setup invoked PATH's literal `git` while
   Clonegrown selected `clonegrown.core.GIT_BIN`; a controlled
   `CLONEGROWN_GIT=/bin/false` probe made the artifact describe Git 2.43.0 even
   though the product had selected `/bin/false`.
6. Both campaign artifacts were written only after the seed loop. Process or
   job termination could therefore leave no provenance or replay data, and the
   state-machine subprocess wrapper had no timeout.
7. The hardening matrix retained GitHub Actions' default fail-fast behavior,
   so one mode could cancel the other mode's diagnostic evidence. The README
   also retained the obsolete claim that the Step 5.1 timing failure was still
   undiagnosed.

The repair changes only test harnesses, tests, workflows, and documentation.
Random-kill uses short seeded interruption windows and refuses success unless
the process was actually sent `SIGKILL` and returned `-SIGKILL`. Both campaigns
use the same selected Git executable as Clonegrown, prewrite every requested
seed and replay command with `pending` status, atomically replace the artifact
after each result, and report executed/pending/pass/fail counts. Campaign
execution is bounded to 25 minutes; checkout, Python setup, and always-run
upload are each bounded to five minutes. Those 40 maximum step-minutes sit
inside a 45-minute job, leaving five minutes for between-step overhead without
claiming that runner loss can guarantee artifact retention. State-machine Git
subprocesses have a 120-second bound, and every invariant runs the public
non-mutating audit and requires exact agreement with readable worker records.
Hardening now reports skips separately, rejects a nonzero child even if it
emitted success JSON, disables matrix fail-fast, and configures an always-run
upload for each mode's structured result. Job cancellation or runner loss can
still prevent that upload. Fifteen focused tests cover these contracts,
including the exact GitHub provenance allowlist and last-complete-document
behavior.

A controlled five-part mutation batch then recreated the environment leak,
missed kill, absent initial artifact, swallowed corrupt metadata, and
skip-as-pass behaviors. The five corresponding tests all failed; all four
mutated source files were restored byte-for-byte to their recorded SHA-256
values, and the 12 focused tests passed. Post-repair local verification passed
209/209 unit tests in 249.502 seconds; 18/18 randomized interruption rows
(seeds 0–2, three operations, two worker modes), each with `killed: true` and
`rc: -9`; four state-machine seeds × 50 steps across both modes; and both
57-row hardening campaigns as 56 passed, one skipped, zero failed. The first
row from each of the eight local campaign artifacts replayed literally and
passed, and all eight replay outputs passed schema/provenance/status checks.
Official `actionlint` 1.7.12 accepted all three workflows; shell syntax
(`sh -n install.sh`), executable-helper checks, and `git diff --check` passed.

The first fresh post-repair cold review then proved four residual issues in the
test/workflow layer and no product defect: a hardening child could emit success
JSON and exit 137 while the driver returned zero; the documented 25/30-minute
timeout arithmetic ignored checkout/setup time; the executed state-machine
replay, kill ownership, and hardening aggregate wiring lacked end-to-end
mutation protection; and deterministic hardening JSON was not uploaded. The
repair added child-exit rejection, explicit 5/5/25/5-minute step bounds inside
a 45-minute job, always-run hardening uploads, and direct artifact/workflow
contract assertions. Six controlled regressions—one for each of those three
test seams plus nonzero-child handling, timeout arithmetic, and hardening
retention—made their named tests fail. The five source/workflow files were
restored to their recorded post-repair hashes, and all 15 focused tests passed.
A second fresh final review found no current implementation or workflow defect,
but proved that the contract suite still permitted three workflow regressions:
timeout values could move to the wrong steps while preserving the same counts,
the randomized matrices could regain default fail-fast cancellation, and
campaign failures could be hidden with `|| true`. The tests now bind every
timeout to its exact step, require randomized `fail-fast: false`, and reject
`continue-on-error`, `|| true`, `set +e`, or a custom shell in the audited jobs.
Three one-at-a-time controlled mutations made the named tests fail; both
workflows were then restored byte-for-byte to their recorded SHA-256 values and
all 15 focused tests passed. The initial, follow-up, and final-review batches
therefore cover 14 distinct mutations; the earlier broad “mutation-proven”
claim is replaced by this literal record. The explicit 16-module suite at that
checkpoint passed 212/212 in 281.760 seconds.

A terminal fresh review again found no current harness, workflow, or product
defect and no Phase 6 leakage, but proved four remaining test/documentation
gaps. Either campaign main could bypass the atomic writer while its tests
stayed green; the mocked random-kill test did not require a new process session
or the exact process group and `SIGKILL`; workflow tests did not protect the
no-push/no-pull-request trigger boundary or exact 30-day retention; and one
handoff timeout plus two upload sentences overstated current behavior. The
existing main tests now require two atomic-writer calls with the expected
pending/executed transitions. The signal test requires
`start_new_session=True` and exact `killpg(pid, SIGKILL)` calls. Workflow tests
require scheduled/manual-only triggers and one 30-day retention setting per
audited job. Documentation now says uploads are always-run but can still be
prevented by job cancellation or runner loss, and the stale bound is 45
minutes. Eight one-at-a-time mutations—two direct writers, omitted session,
wrong process group, wrong signal, two retention regressions, and a
pull-request trigger—made the named tests fail. All four temporarily mutated
source/workflow files were restored byte-for-byte to their recorded hashes,
and the 15 focused tests passed. Across all four mutation batches, 22 distinct
regressions were proved at that checkpoint; its explicit 16-module suite passed
212/212 in 257.084 seconds.

A subsequent fresh re-review confirmed all eight terminal repairs, then proved
one deeper workflow-test weakness while again finding the current workflows
correct. Raw-text assertions treated commented-out YAML as active, named only
two forbidden triggers instead of requiring the exact allowed trigger set, and
rejected `|| true` but not the equivalent `|| :`. The test helper now removes
YAML comments before inspecting jobs, extracts active two-space trigger keys,
requires exactly `workflow_dispatch` plus `schedule`, and rejects every `||`
fallback in the audited jobs. The historical Step 5.3 record now labels its
30-minute bound as a superseded checkpoint and does not promise upload after
cancellation or runner loss. Ten one-at-a-time mutations—three extra triggers,
commented-out job timeout, fail-fast, randomized retention, CI retention, and
CI always-run settings, plus randomized and CI `|| :` masking—made the named
tests fail. Both workflows were restored byte-for-byte to their recorded
hashes, and the 15 focused tests passed. Across the first five mutation batches,
32 distinct regressions were proved at that checkpoint; its explicit 16-module
suite passed 212/212 in 283.646 seconds.

The next fresh semantic review confirmed all ten preceding repairs, then found
three remaining test-protection gaps while again finding the current workflows
and harnesses correct. Job timeout, strategy fail-fast, upload always-run, and
retention values were still free-form substrings that active text under the
wrong YAML owner could shadow. Neither randomized job's actual campaign command
was bound to its upload path. The selected-Git test omitted the hardening
harness, allowing a hardcoded runner Git to evade it. Workflow assertions now
extract unique indentation-owned job, strategy, step, and `with` blocks and
require their direct values; each randomized run block is exact and its output
path equals the upload path. The hardening helper must invoke its patched
`GIT_BIN`. Eight one-at-a-time mutations—five misplaced active controls, two
no-op campaign commands that wrote `{}`, and hardcoded hardening Git—made the
named tests fail. Both workflows and the hardening harness were restored
byte-for-byte to their recorded hashes, and the 15 focused tests passed. Across
all six mutation batches, 40 distinct regressions are proved. The final explicit
16-module suite passed 212/212 in 283.846 seconds.

A further fresh ownership review confirmed all eight preceding repairs and
again found the current harnesses and workflows correct, but identified four
remaining test-protection gaps. The randomized workflow's six-job random-kill
matrix, two-job state-machine matrix, and per-job worker-mode environment were
not bound; the CI hardening worker mode was likewise unasserted. Replay tests
covered only one random-kill mode/operation pair and one state-machine mode.
The nightly cron, four manual-input environment expressions, and uploaded
artifact identities were also unprotected. The tests now require the complete
eight-job matrices and mode wiring, every replay-helper mode/operation
dimension, the exact scheduled/manual controls, and run-attempt-scoped
artifact names.
Sixteen one-at-a-time mutations—six matrix/mode regressions, three collapsed
replay dimensions, five scheduled/manual-control regressions, and two constant
artifact names—made their owning tests fail. Every temporarily mutated
source/workflow file was restored byte-for-byte to its recorded hash, and the
15 focused tests passed. Across seven mutation batches, 56 distinct
regressions are now proved. A preliminary direct-module full-suite command was
invalid because it omitted `tests/` from Python's import path; 15 modules
stopped at `ModuleNotFoundError: support`, the campaign-record module alone
ran, and no file changed. The corrected 16-module discovery suite passed
212/212 in 275.558 seconds.

The next fresh semantic review confirmed all 16 seventh-batch mutations, then
proved two broader false-green classes while again finding the current
harnesses and workflows correct. Complete helper tests did not protect the two
artifact call sites: random-kill artifacts could collapse their recorded mode
or operation, and state-machine artifacts could collapse their recorded mode.
The workflow parser also ignored quoted event keys, while job-level `if`
conditions or `env` mappings could silently skip scheduled jobs or override
the tested workflow-level campaign controls. Artifact integration now runs
both worker modes and every random-kill operation and checks exact pending and
completed replay rows. Workflow tests recognize quoted event keys, forbid an
audited job-level condition in both randomized jobs and CI hardening, and
forbid job-level environment shadowing in either randomized job. Twelve
one-at-a-time mutations—six pending/completed replay call-site substitutions,
one quoted push trigger, three job-disabling conditions, and two job-level
environment overrides—made their owning tests fail. Every temporarily mutated
source/workflow file was restored byte-for-byte to its recorded hash, and the
15 focused tests passed. Across eight mutation batches, 68 distinct
regressions are now proved. The corrected 16-module discovery suite passed
212/212 in 277.604 seconds.

A fresh closing review caught all 28 requested seventh/eighth-batch mutations
and found no current workflow or product defect, but proved one final parser
false-green class. YAML permits separation whitespace before a mapping colon;
the constrained key parser ignored that form. Six active variants—a quoted
push trigger, job-level disabling conditions on both randomized jobs and CI
hardening, and job-level environment shadows on both randomized jobs—therefore
survived. Accepting legal separator whitespace made all six fail, and the
16-module discovery suite passed 212/212 in 277.105 seconds. Before recording
that as final, a direct probe showed the value parser still disagreed with YAML
on a later duplicate key written with the same separator whitespace: YAML
resolved the later value while the test reported only the earlier expected
value. Key and value inspection now share one fail-closed direct-mapping
parser for plain or quoted simple keys, legal separator whitespace, duplicate
visibility, and rejection of unsupported active direct-key syntax. Two
additional duplicate timeout/retention mutations made the owning test fail.
Every temporarily mutated workflow was restored byte-for-byte to its recorded
hash, and all 15 focused tests passed. Across nine mutation batches, 76
distinct regressions are now proved. The final corrected 16-module discovery
suite passed 212/212 in 277.763 seconds.

The next fresh closing review caught all eight ninth-batch mutations, confirmed
that unsupported direct-key syntax fails closed, and found no current product,
workflow, or documentation defect. It did prove one last consumer gap: the
parser exposed duplicate direct block keys, but callers could collapse them to
a set or select only the earlier exact block. A later `schedule : []` therefore
disabled the effective nightly schedule while the trigger test stayed green;
a later `strategy :` block similarly replaced fail-fast and the matrix without
failing its owning test. The shared direct-mapping parser now rejects every
duplicate key before any caller consumes it. Both demonstrated block-override
mutations made the owning test fail, and the workflow was restored
byte-for-byte to its recorded hash. Across ten mutation batches, 78 distinct
regressions are now proved. All 15 focused tests passed. The final corrected
16-module discovery suite passed 212/212 in 535.241 seconds; the longer observed
duration did not affect pass/fail and is not a timing gate.

After that full pass, the same duplicate-key rejection was applied at the
workflow document root and `jobs` mapping boundaries rather than only inside a
selected job. Four additional later-override mutations—duplicate top-level
`on`, duplicate top-level `jobs`, duplicate randomized `random-kill`, and
duplicate CI `hardening`—made their owning tests fail. Both workflows were
restored byte-for-byte to their recorded hashes. That checkpoint brought the
total to 82 proved regressions across ten batches. All 15 focused tests passed,
and the corrected 16-module discovery suite passed 212/212 in 539.069 seconds;
this longer observed duration likewise did not affect pass/fail.

The nested `workflow_dispatch` mapping now passes through the same duplicate-key
rejection before its `inputs` block is selected. A later `inputs : {}` mutation
made the owning test fail, and the randomized workflow was restored byte-for-byte
to its recorded hash. The final total is 83 proved regressions across ten
batches. All 15 focused tests passed, and the exact final 16-module discovery
suite passed 212/212 in 538.210 seconds.

#### 2026-08-29 hosted completion record

Kyle explicitly authorized committing and pushing the exact 24-path Phase 5
tree. Commit `a2ae7793b5a3653435fde988f716558f74ce6b88` contains 4,199 insertions
and 113 deletions across those 24 paths and was pushed to `origin/main`.
Deterministic CI run 33276649643 passed all seven jobs at that exact SHA: the
Python 3.11 and latest-stable unit/destructive jobs on Ubuntu and macOS, the
exact Git 2.29.0 unit/adversarial job, and the clone/worktree hardening jobs
with both artifact uploads. GitHub emitted non-failing deprecation annotations
because the existing CI checkout/setup actions target Node.js 20 and were
forced onto Node.js 24; no job failed, skipped, or was cancelled.

Manual randomized run 33277111128 used seed start 0, two seeds per random-kill
case, two seeds per state-machine mode, and 50 steps per state-machine seed at
the same SHA. All six random-kill and two state-machine jobs and their uploads
passed. The eight non-expired artifacts were downloaded outside the checkout.
Every artifact had the exact expected top-level schema and allowlisted
environment/GitHub provenance, identified the published SHA and run, reported
two executed and two passed rows with zero pending or failed rows, and carried
the exact one-seed replay command for each row. The first row from every
artifact was then executed literally: all six interruption replays passed with
an actual `SIGKILL` and return code -9, and both state-machine replays passed 50
events with the public invariant active. Their eight generated replay results
also passed one-executed/one-passed/zero-pending/zero-failed validation. Phase
5 was complete and no Phase 6 work had begun at that checkpoint.

## Phase 6 — Remove residue and optimize only from measurements

### Step 6.1 — Gate test hooks, remove dead heartbeat state, and prune campaign residue — complete 2026-08-29

- Replace the active `CWS_*` pause/fail/error switches with
  `CLONEGROWN_TEST_*` names and require `CLONEGROWN_TEST_MODE=1` before any is
  honored; set them only in the harnesses. Prove production mode ignores both
  new hostile values and legacy `CWS_*` failpoint variables. Preserve historical
  artifacts containing the old names byte for byte.
- Stop writing the unused `heartbeat` field and remove it from current output
  bookkeeping while continuing to round-trip it as an unknown historical key.
- Prove campaign code is dead or duplicated before removing it. Reformat only
  touched harness regions, preserve historical evidence byte for byte, and keep
  current-versus-historical provenance explicit.

Completion record:

- The verified production hazard was `core.failpoint`: it read
  `CWS_PAUSEPOINT`, `CWS_FAILPOINT`, and `CWS_ERRORPOINT` without a mode gate.
  A pre-change direct probe with `CWS_ERRORPOINT=probe` raised the injected
  `ClonegrownError`. It now returns before reading any hook value unless
  `CLONEGROWN_TEST_MODE` is exactly `1`, and then reads only
  `CLONEGROWN_TEST_PAUSEPOINT`, `CLONEGROWN_TEST_PAUSE_MARKER`,
  `CLONEGROWN_TEST_PAUSE_SECONDS`, `CLONEGROWN_TEST_FAILPOINT`, and
  `CLONEGROWN_TEST_ERRORPOINT`. Unit and campaign harnesses set the explicit
  gate; a focused regression proves missing, empty, `0`, `true`, and `01`
  modes ignore hostile new values, and that retired `CWS_*` controls remain
  inert even in test mode. A gated crash-matrix probe still exited 88 and
  recovered at both init boundaries.
- `WorkerRecord.take_ownership` had written `heartbeat = time.time()` exactly
  once. No runtime path read or refreshed the field. The dataclass field,
  timestamp validation entry, assignment, import, and CLI bookkeeping entry
  are gone. `_from_json` / `_to_json` already preserve unknown keys, and the
  compatibility regression now proves a historical `heartbeat` value loads
  into `extra` and serializes unchanged while a current ownership record omits
  it.
- Repository and workflow reference searches proved the four removed scripts
  had no code or automation caller. `concurrency_v2.py` was superseded by the
  deterministic eight-way allocation audit plus the multi-sample nonblocking
  spawn benchmark; `run_crash_case.py` was a strict subset of the collect and
  discard crash matrices; `shared_state_compare.py` duplicated current
  clone/worktree config, stash, remote, and branch assertions; and
  `io_fault_probe.py` was superseded as supported evidence by deterministic
  atomic-write, quarantine-rename, and partial-deletion tests. `scaling_v2.py`
  and `gc_compare.py` were retained because they still provide unique
  observational measurements. `ARCHITECTURE.md` and `research/REPRODUCE.md`
  now describe that current surface without rewriting the historical report
  or machine artifacts.
- Pre-change focused evidence passed the deterministic allocation replacement
  and all four filter/resource tests. Post-change direct probes proved both
  legacy and new hostile controls are ignored in production, the exact test
  gate activates the new ordinary-error hook, and current records omit
  `heartbeat`. Focused `test_core.py` passed 14/14, `test_state.py` passed
  12/12, and `init_crash_matrix` passed. The complete suite passed 215/215 in
  509.059 seconds. Full current-Git hardening passed in clone and worktree
  modes: 57 defined, 56 exercised passes, one conditional reftable skip, zero
  failures in each mode. Generated output stayed under `/tmp`.
- The preserved research files remained byte-identical at their recorded
  SHA-256 values: `RESULTS.json` `be38e4891...`, `FALSIFICATION.md`
  `51e1b2d6...`, `REPORT.md` `4e56d0d5...`,
  `REAL_REPOSITORY_QUALIFICATION.json` `7d0e36fd...`, and its Markdown
  interpretation `7941e5e7...`.

### Step 6.2 — Cache canonical verification within one transaction — complete 2026-08-29

- Instrument current spawn Git calls and establish the baseline. Introduce a
  transaction-scoped verified workspace/canonical value that can be reused
  only while the relevant lock and identity assumptions remain valid; add no
  global or cross-command cache.
- Remove repeated `rev-parse --git-common-dir` and equivalent verification only
  where the same transaction has already proved the invariant. Re-run tamper,
  replacement, and crash tests before comparing call counts and timings.

Completion record:

- The verified starting state was five full `WorkspaceState.verify_canonical`
  calls in each successful spawn. Allocation, cloning, and configuring each
  began a separate workspace-lock transaction and had to keep their own
  verification. The publishing lock performed the fourth verification, then
  repeated the complete seven-Git-call proof before deleting the base pin even
  though that same lock had never been released.
- The publishing transaction now keeps the canonical path returned by its
  first verification and uses that value for ready-state base-pin cleanup.
  The value is a local variable inside that one uninterrupted `workspace_lock`
  block; no state module, object field, process cache, command cache, or value
  crossing a lock boundary was added. Lock boundaries, metadata transitions,
  publication ordering, ref compare-and-swap behavior, durable schema, and
  public output are unchanged.
- A focused regression counts exactly four full verifications for successful
  clone and worktree spawns. A second regression replaces canonical after
  `spawn.after_clone`, between the cloning and configuring transactions; the
  next transaction refuses the missing identity marker, records the worker
  `spawn_failed`, and leaves no published slot. Existing canonical replacement,
  canonical-marker loss, worker-marker tamper, and complete spawn crash
  matrices passed unchanged in both modes.
- Five fresh fixtures per mode produced stable exact call counts. Clone moved
  from 73 total Git calls, 44 `rev-parse`, and 17 common-dir probes to 66, 37,
  and 14. Worktree moved from 53, 40, and 15 to 46, 33, and 12. Median observed
  single-spawn time moved from 0.425 to 0.389 seconds for clone and 0.425 to
  0.398 seconds for worktree. The raw timing ranges overlap, so these are
  observations rather than thresholds or performance guarantees. Structured
  diagnostic output remained under `/tmp`.
- The focused allocation module passed 12/12. The complete suite passed
  217/217 in 274.549 seconds. Full current-Git hardening passed in clone and
  worktree modes: 57 defined, 56 exercised passes, one conditional reftable
  skip, and zero failures in each mode. `git diff --check` passed.

### Step 6.3 — Shorten workspace-lock critical sections without weakening allocation — complete 2026-08-29

- Measure lock-held phases with multiple samples after Step 6.2. Move only
  immutable preparation outside the lock; keep worker-ID allocation, request
  indexing, state transitions, publication checks, and compare-and-swap ref
  mutations serialized where correctness requires it.
- Re-run eight-way uniqueness and request-id races many times unchanged, then
  report lock time and total time without a pass/fail performance ratio.

Completion record:

- Twenty direct samples established that one complete canonical proof made
  seven Git calls and took a median 0.020628 seconds (median absolute deviation
  0.000249, range 0.020019–0.021608). Successful spawn performed that proof
  while holding each of its allocation, cloning, configuring, and publishing
  workspace locks. The repeated proof therefore occupied about 0.0825 seconds
  of serialized time per spawn before any other locked work was counted; the
  eight-way samples showed the resulting contention in lock waits.
- New immutable `VerifiedWorkspace` preparation loads and fully verifies the
  canonical repository immediately before each affected lock, resolving and
  fingerprinting the canonical root and Git directory. Under the lock it
  reloads the durable workspace record; all fields except the concurrently
  allocated `next_id` must match, both directory device/inode identities must
  still match, and the direct workspace identity marker must still bind the
  same token, workspace ID, and canonical path. Only after that reconciliation
  do the existing allocation decisions, request indexing, lifecycle state
  transitions, publication checks, and compare-and-swap ref mutations run.
  Each later spawn stage prepares a fresh proof; there is no global or
  cross-command cache.
- Two new regressions replace the canonical directory or change immutable
  workspace state after preparation but before allocation acquires the lock.
  Both are refused before `next_id`, records, slots, request indexes, or refs
  change. The existing replacement-between-transactions test and unchanged
  canonical-replacement, marker-loss, state-tamper, and complete clone/worktree
  spawn-crash campaigns also passed.
- Identical instrumentation sampled five fresh single spawns and five fresh
  eight-way fixtures per mode before and after the change. For clone, summed
  single-spawn lock-phase medians moved from 0.199512 to 0.139784 seconds and
  summed per-spawn eight-way lock-phase medians from 0.209271 to 0.158196;
  eight-way wall median moved from 1.790971 (range 1.638265–1.883432) to
  1.410101 seconds (1.405924–1.453328). For worktree, those lock-phase sums
  moved from 0.201623 to 0.156690 and from 0.214447 to 0.176585 seconds;
  eight-way wall median moved from 1.747280 (1.694627–1.990451) to 1.496226
  seconds (1.425680–1.564503). Single-spawn wall medians instead moved from
  0.357113 (0.291982–0.379384) to 0.469582 seconds
  (0.408388–0.582371) for clone and from 0.252098
  (0.227817–0.296769) to 0.421622 seconds (0.380869–0.463742) for worktree.
  The samples are observational, noisy, and deliberately impose no pass/fail
  ratio or performance threshold. Complete raw distributions remain outside
  the checkout at `/tmp/clonegrown-step-6.3-baseline.json` and
  `/tmp/clonegrown-step-6.3-post.json`.
- The unchanged eight-way uniqueness and same-request concurrency campaigns
  each passed 10/10 in clone and worktree modes: 40 total race passes, with
  generated evidence at `/tmp/clonegrown-step-6.3-race-stress.json`. Focused
  allocation tests passed 14/14 and state tests 12/12. The complete suite
  passed 219/219 in 472.105 seconds. Full current-Git hardening passed in clone
  and worktree modes: 57 defined, 56 exercised passes, one conditional
  reftable skip, and zero failures in each mode. `git diff --check` passed.
- This Step changed no durable schema, public lifecycle behavior, Git protocol,
  workflow, dependency, or preserved research artifact. It created no path.

### Step 6.4 — Measure and decide the auxiliary-ref compatibility contract — complete 2026-08-29

- Rerun the ref-heavy benchmark against the current package, including remote
  tracking refs, notes, and replace refs, with spawn time, ref count, loose-ref
  count, and disk use recorded.
- Define the minimum offline compatibility contract before choosing all refs,
  narrowing, packing, or a combination. Notes and replace refs remain
  correctness-sensitive; do not optimize them away by accident.
- End this Step by replacing Step 6.5's generic wording with the exact chosen
  policy and measured acceptance thresholds. No provisioning code changes in
  this Step.

Completion record:

- The verified starting implementation was
  `repository.copy_auxiliary_refs`: it enumerated and eagerly fetched every
  ref under `refs/remotes/`, `refs/notes/`, and `refs/replace/` through three
  separate wildcard fetches and did not pack them. The retained
  `scaling_v2.py refs` fixture created only heads and custom refs; the public
  Git qualification added neither notes nor replace refs. Those measurements
  therefore existed but did not cover this Step's combined auxiliary-ref
  question.
- The minimum clone compatibility contract preserves every resolvable
  canonical name and resolved object ID in all three namespaces. A symbolic
  remote-tracking ref is promised by name and resolved tip, not by symbolic
  representation. With canonical's path unavailable, copied remote tips must
  remain usable for ordinary comparisons, notes must display, and replace refs
  must retain their object/history interpretation. Later canonical changes do
  not propagate; worker-local ref update and deletion must work. Metadata
  counts canonical refs per class, excluding the worker's own `cws-source`
  refs. Stash, Clonegrown-private refs, and transient-operation refs remain
  excluded. Worktree workers continue to share these namespaces live, and
  Clonegrown must never pack or rewrite canonical refs on their behalf.
- New `tests/campaign/auxiliary_ref_benchmark.py` makes the comparison
  reproducible without changing product code. Each run used five fresh
  current-clone, candidate-clone, and current-worktree fixtures containing
  4,096 remote-tracking refs (including a symbolic `HEAD`), 256 notes refs,
  and 256 replace refs, with case order rotated by sample. It recorded spawn time, total/per-class and
  loose/packed counts, logical/allocated Git-directory storage, exact object
  IDs, offline semantics, metadata counts, and, for clone paths, packed ref
  delete/restore behavior. Timing never affected its exit status.
- The first order-balanced run's candidate/current medians were
  3.512329/2.845196 seconds, beyond the predeclared 1.20 ceiling. No code or
  fixture changed; the prescribed unchanged five-sample repeat measured
  3.363512/3.002327. Across the combined ten samples, current clone spawn had
  a 2.979489-second median (median absolute deviation 0.075804, range
  2.817034–3.200357), 4,612 total refs all loose, 4,610 loose auxiliary refs
  (the canonical 4,608 plus two private source-remote refs), and 39,008,256
  median allocated Git-directory bytes. Adding a separate post-spawn pack took
  a 0.854858-second median and projected 3.851855 seconds total.
- The selected candidate preserves all namespaces, submits their nonempty
  wildcard refspecs in one fetch, and immediately runs `git pack-refs --all`
  in the clone. Its combined median spawn was 3.372564 seconds (median absolute
  deviation 0.075283, range 3.241107–3.578968): 0.393075 seconds, or 13.2%,
  above current and inside the fixed ceiling, while remaining 0.479291 seconds
  below adding a separate pack. It retained all 4,612 refs while leaving 2
  loose in total and 1 loose auxiliary ref, packing 4,609 auxiliary refs, and
  using 20,342,784 median allocated Git-directory bytes. The combined
  worktree-control median was 0.558183 seconds (0.516510–0.585929), with its
  4,608 auxiliary refs shared from canonical, 3 total loose refs, and
  20,434,944 median allocated bytes.
- All thirty measured scenarios passed. The raw artifacts are
  `/tmp/clonegrown-step-6.4-auxiliary-refs.json` at SHA-256
  `f185d7d4b9299de897201611318884ece0c96d210020ac1a9904f83993e2f166`
  and `/tmp/clonegrown-step-6.4-auxiliary-refs-repeat.json` at
  `ec14544c4193f1dc01b51b167da0486e9870bc52f416a910d30b559fab6695f4`;
  both embed the final harness SHA
  `6feacc2947c0105bf7a6da3cbc8518ea6612a8c109cc5444ec44f2128382fc17`.
  They were generated on CPython 3.12.3 and Git 2.43.0 in 72.060 and 72.794
  observed seconds. Generated output stayed outside the checkout.
- The existing real-Git `auxiliary_refs` hardening case passed in clone and
  worktree modes. The new benchmark command's help surface and
  `git diff --check` passed. The full product suite was not rerun because this
  Step changed no product or unit-test code; the benchmark exercised 10 fresh
  current-clone, 10 simulated-candidate-clone, and 10 current-worktree package
  spawns.
- This Step chose **all promised refs plus one fetch plus packing**. It did not
  narrow a namespace and changed no `clonegrown/` product file, provisioning
  behavior, workflow, dependency, durable schema, public lifecycle behavior,
  or preserved research artifact. It created only the benchmark harness and
  updated descriptive/planning documentation.

### Step 6.5 — Implement the measured auxiliary-ref policy — complete 2026-08-29

- In `repository.copy_auxiliary_refs`, keep the exact three namespaces and
  per-class canonical counts. Submit every nonempty wildcard refspec in one
  `git fetch`; after that fetch succeeds, run `git pack-refs --all` in the
  staged clone before checkout. If all three namespaces are empty, run neither
  command. Do not narrow names, pack canonical/worktree refs, change the
  excluded namespaces, add maintenance, or change record schema/output.
- Add real-Git coverage on current Git and exact Git 2.29.0 for default and
  strong clone workers plus the unchanged shared-worktree control. Prove exact
  name/object-ID preservation, canonical per-class metadata counts, offline
  remote comparison, notes display, commit and blob replace interpretation,
  no propagation of later canonical updates, packed ref update/delete/restore,
  the symbolic-remote resolved-tip boundary, and continued omission of stash,
  Clonegrown-private, and transient-operation refs.
- Rerun the Step 6.4 harness unchanged at five samples and 4,096/256/256 refs.
  Correctness acceptance is zero missing or changed canonical refs and every
  semantic/update check passing in all 15 scenarios. Clone storage acceptance
  is exactly 4,612 total refs, at most 2 loose refs total, at most 1 loose
  auxiliary ref, at least 4,609 packed auxiliary refs, and at most 21,000,000
  allocated Git-directory bytes. The candidate clone-spawn median may be at
  most 1.20 times the interleaved current-clone median; this is a one-time
  implementation decision, never a CI timing gate. If timing alone misses,
  rerun one unchanged five-sample comparison and decide on the combined ten
  samples without editing between runs. Revert the optimization if any hard
  contract/storage gate fails or the confirmed timing ceiling is exceeded.

Completion record:

- The verified starting function enumerated the exact three promised
  namespaces, reported their canonical counts, issued one wildcard fetch per
  nonempty class, and did not pack. `copy_auxiliary_refs` now accumulates those
  same nonempty wildcard refspecs, submits them together in one fetch, and
  runs `git pack-refs --all` in the staged clone only after that fetch
  succeeds. Three empty classes still return explicit zero counts and now run
  neither fetch nor pack. Clone checkout remains later in provisioning;
  worktree provisioning still bypasses the function and never packs canonical.
- New `tests/test_auxiliary_refs.py` first binds the exact command boundary:
  two nonempty namespaces produce one fetch with both refspecs followed by one
  pack, while an all-empty fixture produces neither mutation. Its real-Git
  matrix then spawns a default clone, strong clone, and shared-worktree control
  together. It proves exact canonical name/resolved-object snapshots, symbolic
  remote resolved-tip semantics, per-class clone metadata, offline comparison,
  notes display, commit and blob replacement, packed update/delete/restore,
  clone isolation from later canonical changes, live worktree sharing,
  canonical non-packing, and omission of stash, Clonegrown-private, and
  transient operation refs from clones.
- The three focused tests passed on CPython 3.12.3 with current Git 2.43.0 in
  2.254 seconds and with the local exact Git 2.29.0 binary selected through
  both `PATH` and `CLONEGROWN_GIT` in 2.404 seconds. The existing real-Git
  `auxiliary_refs` hardening case also passed in clone and worktree modes on
  both Git versions.
- The prescribed harness stayed byte-for-byte unchanged at SHA-256
  `6feacc2947c0105bf7a6da3cbc8518ea6612a8c109cc5444ec44f2128382fc17`.
  Its five-sample, order-rotated 4,096/256/256 rerun passed all 15 scenarios in
  70.351 observed seconds. The implemented current clone kept exactly 4,612
  total refs in every sample, with 2 loose refs, 1 loose auxiliary ref, 4,609
  packed auxiliary refs, and 20,344,832 allocated Git-directory bytes. Every
  exact-ref, metadata, offline-semantic, and update check passed.
- Current clone spawn measured a 3.478675-second median (median absolute
  deviation 0.075438, range 3.403237–3.774483). The unchanged benchmark-only
  simulation, now intentionally the same policy at the call boundary, measured
  3.739621 seconds (median absolute deviation 0.090582, range
  3.444581–3.926305), a 1.075013 ratio to the interleaved implementation and
  inside the fixed 1.20 ceiling. It met the same storage counts in all five
  samples, so no repeat was required. The worktree control median was 0.458415
  seconds and its shared canonical ref/storage shape remained unchanged.
- The generated artifact is
  `/tmp/clonegrown-step-6.5-auxiliary-refs.json` at SHA-256
  `632a9efec6fd23da606b4fdad3ab3bf50d22838746dff082c965680056d0faa9`;
  it embeds Git 2.43.0, CPython 3.12.3, the unchanged harness hash, and the
  uncommitted package hash. Generated evidence stayed outside the checkout.
- The complete current-Git unit/destructive suite passed 222/222 in 528.065
  seconds. Full current-Git hardening passed in clone and worktree modes: 57
  defined, 56 exercised passes, one expected conditional reftable skip, and
  zero failures each. Preserved research-artifact hashes are unchanged.
- Executable change is limited to `clonegrown/repository.py`; the new focused
  test is `tests/test_auxiliary_refs.py`. Descriptive changes update
  `ARCHITECTURE.md`, `research/REPRODUCE.md`, this plan, and `HANDOFF.md`.
  No namespace, excluded ref, schema/output, CLI, workflow, dependency,
  maintenance policy, or public lifecycle changed. The benchmark and every
  preserved research artifact are byte-for-byte unchanged.

### Step 6.6 — State retention and teardown conservatively — complete 2026-08-29

- For 0.x, retain worker metadata and immutable result refs indefinitely by
  default, and provide no automatic workspace teardown that could outrun user
  custody. Document how to inspect and manually integrate retained refs.
- Specify the evidence a future explicit prune/teardown operation would need,
  but do not add that destructive command without its own approved plan and
  adversarial tests.

Completion record:

- The verified starting implementation already had the intended conservative
  behavior. `finish_deletion` commits a terminal record through
  `WorkerRecord.save`; it does not unlink that record. `status` enumerates all
  worker record files, including terminal ones. Collected discard first
  verifies the immutable `result_ref`, then deletes only authorized worker and
  owned checkout state; no discard path deletes the result or summary ref.
  The installed parser exposes exactly `init`, `spawn`, `collect`, `release`,
  `claim`, `discard`, `recover`, and `status`, with no prune, expiry, or
  workspace teardown surface.
- `README.md` now makes the 0.x retention cost and boundary explicit: terminal
  records and immutable result refs stay indefinitely by default, metadata and
  `refs/cws/` can grow, and manually deleting only one side can strand custody
  evidence. It directs users to inspect `clonegrown status`, require a clean
  result-ref audit for the worker, use the literal returned `result_ref` with
  ordinary Git inspection or a review branch, and choose merge or cherry-pick
  themselves. Clonegrown neither integrates nor infers that reachability is
  permission to delete retained evidence.
- `ARCHITECTURE.md` records the acceptance evidence for any future explicit
  prune/teardown plan: exact locked ownership scope; per-result object-ID
  verification and explicit consent; quiescent supported states; durable,
  idempotent, expected-old-object sequencing; a read-only inventory and exact
  outcome report; and adversarial coverage across worker modes, both Git
  endpoints, every interruption boundary, concurrency, filesystem/path
  attacks, I/O failures, corrupt or ambiguous state, and repeated recovery.
  Broad recursive targets and blanket `git worktree prune` remain forbidden.
- The focused CLI suite passed 4/4 in 2.968 seconds. The existing
  `result_survives_gc` real-Git hardening case passed in clone mode in 2.510
  seconds and worktree mode in 2.551 seconds: after collect, release, discard,
  reflog expiry, and `git gc --prune=now`, each immutable result ref still
  resolved to the exact collected commit. The preserved six-scenario public
  repository qualification already records a terminal discarded worker plus
  a surviving exact result ref and clean status audit in both modes.
- This Step changes only `README.md`, `ARCHITECTURE.md`, `PLAN.md`, and
  `HANDOFF.md`. It creates no path and changes no executable, test, workflow,
  dependency, schema/output, command surface, or preserved research artifact.
  The complete 222-test and both full-hardening passes from immediately prior
  Step 6.5 remain the executable baseline; no full rerun is warranted for this
  documentation-only decision.

### Step 6.7 — Complete package and support metadata — complete 2026-09-02

- Add accurate project metadata, tested Python/Git requirements, platform
  classifiers, and release/support boundaries; verify wheel and sdist metadata
  in isolated installs.
- **User gate:** a software license grants real redistribution rights and
  cannot be inferred. Before this Step, Kyle must reply with the literal choice
  `Use the <license name> license for Clonegrown.` Then add that exact license
  file and matching package metadata. Until then, skip this blocked Step and
  continue with another unblocked one.

Completion record:

- Kyle supplied the exact authorization `Use the Apache License 2.0
  (Apache-2.0) for Clonegrown.` The verified entry tree had no `LICENSE`,
  `NOTICE`, or other tracked license file. `pyproject.toml` existed with
  `requires-python = ">=3.11"`, four broad classifiers, and no license or
  license-file declaration. README and architecture already stated the tested
  Git 2.29.0+, Python 3.11+, Linux/macOS, alpha, and native-Windows boundaries.
- New `LICENSE` is byte-identical to
  `https://www.apache.org/licenses/LICENSE-2.0.txt` and to the operating
  system's packaged canonical copy. Its SHA-256 is
  `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
  No `NOTICE` or per-file copyright holder was invented: neither existed and
  Kyle supplied no attribution identity or notice text.
- `pyproject.toml` now uses the current PEP 639 form, `license =
  "Apache-2.0"` and `license-files = ["LICENSE"]`, and declares only the
  implemented alpha, developer/console, Linux/macOS, and Python 3.11–3.14
  support surface. It deliberately omits the deprecated `License ::`
  classifier. The existing setuptools build requirement moved from 68 to
  77.0.3 because that is the recorded minimum supporting PEP 639 metadata.
  This is a build-isolation cost only; it adds no runtime dependency.
  Every declared classifier was confirmed in PyPI's current official
  classifier registry. `README.md` now gives one literal release/license
  statement.
- New `tests/test_package_metadata.py` uses only the Python standard library
  to pin the official license SHA-256, SPDX expression, included license file,
  backend floor, classifiers, Python floor, and README support/license
  boundary. It passed 2/2 on CPython 3.12.3. Step 6.7 changed existing
  `pyproject.toml`, `README.md`, `PLAN.md`, and `HANDOFF.md`; created
  `LICENSE` and `tests/test_package_metadata.py`; and deleted nothing.
- `uv 0.12.4` built the current tree from an explicitly dotenv-filtered copy
  under `/tmp/clonegrown-step-6-7.ovAMWy` with setuptools 84.0.0. The wheel
  `clonegrown-0.1.0a1-py3-none-any.whl` has SHA-256
  `8eb69b2fa1ea3b0c5f386d61b19cdadc6398b2c09996d001295d17c3a92274ca`;
  the source archive `clonegrown-0.1.0a1.tar.gz` has SHA-256
  `9845a176f6f00f962ac315e6070441aac6f8a3a39686b54292dfe035951d70ab`.
  Both contain the canonical license, Core Metadata 2.4, the Apache SPDX
  expression, the license-file field, Python floor, and exact classifiers.
- Separate CPython 3.12.3 environments installed the wheel and source archive;
  the latter performed its own isolated build. In both, `clonegrown
  --version`, `python -I -m clonegrown --version`, the complete public import,
  installed metadata, and installed license hash passed. An earlier ambiguous
  `uv venv --python python3` request selected managed Python 3.10.20 and warned
  that it was incompatible; nothing was installed there. Fresh environments
  created with `/usr/bin/python3` exercised the supported interpreter.
- `git diff --check`, out-of-checkout byte compilation, and the preserved
  research comparison passed. No runtime product file, API signature,
  lifecycle behavior, command output, durable state/JSON, installer,
  workflow, architecture, skill, or preserved research artifact changed. The
  final 226-test/two-Git/two-hardening Step 6.8 result remains the runtime
  baseline; the full release matrix remains scheduled for Step 7.5.

### Step 6.8 — Cold-review Phase 6 — complete 2026-08-29

- A fresh agent checks that test hooks are inert in production, historical
  evidence was not rewritten, performance changes preserve every safety
  invariant, and package claims match tested support.
- Run the full deterministic suite and compare measured performance/call-count
  reports to the pre-optimization baselines.

Completion record:

- A fresh read-only reviewer entered and exited at
  `354d16bc662f15f65dded911d3c26729bf5804aa` with the same 27-path local
  boundary and no repository edit. It inspected all six product diffs, every
  retained/new/deleted test or campaign path, current documentation, workflow
  and package metadata, the saved Phase 6.2–6.5 reports, and the preserved
  research hashes. It confirmed the exact production test-mode gate, found no
  retired hook reader, found no historical-evidence rewrite, and reported
  three reproducible product defects plus one historical-output compatibility
  mismatch. The existing test suite had no case for any of those scenarios.
- The first defect was a custody regression in the publishing transaction. A
  deterministic `spawn.after_publish` probe renamed canonical, created a
  foreign repository at the old pathname, and planted the expected base ref;
  spawn returned `ready`, deleted the foreign ref, and left the original ref.
  The publishing proof is now rematched after both post-publication
  pausepoints and immediately before base-pin deletion. The regression proves
  replacement is reported after publication, both original and foreign refs
  survive, the published worker is preserved, and no Git repair or ref delete
  targets the replacement repository.
- The second defect was non-monotonic locked reconciliation. A process exited
  88 after committing `next_id = 2`, leaving ID 1 as an intentional gap; a
  rollback to 1 between proof preparation and lock acquisition was accepted
  and ID 1 was reused. `VerifiedWorkspace.reload_under_lock` now accepts an
  equal counter or a concurrent advance but rejects a lower value before any
  allocation mutation. The regression recreates the consumed gap and proves
  the rolled-back state cannot allocate it.
- The third defect was an auxiliary-ref snapshot race. Adding a canonical
  remote-tracking ref after enumeration made the worker copy two while
  recording one; deleting the enumerated ref produced a ready worker recording
  one while copying none. `copy_auxiliary_refs` now enumerates exact
  name/object-ID pairs once and sends forced object-ID refspecs to the same
  single `git fetch` through `--stdin`, avoiding argv limits. Counts and copied
  refs therefore share the enumeration boundary; later additions are omitted,
  later moves cannot change values, and an unavailable enumerated object fails
  provisioning instead of publishing inconsistent metadata. Packing, the
  three namespaces, exclusions, all-empty behavior, and worktree bypass remain
  unchanged.
- The first exact-snapshot implementation fetched into an intermediate
  namespace and atomically moved 4,608 refs. It passed correctness/storage but
  regressed current-clone median to 6.186671 seconds. A one-fixture profile
  attributed 2.453329 seconds to its 9,216-row `update-ref --stdin`
  transaction. That implementation was fully replaced before the next test;
  the explicit-refspec prototype measured 3.387948 seconds on the same shape.
  No unproved performance fix was stacked on it.
- Current records still omit `heartbeat`, and `WorkerRecord` still preserves a
  historical value as unknown extension data. Restoring `heartbeat` to the
  CLI bookkeeping filter keeps the pre-Phase-6 public-output contract: an
  on-disk historical value remains byte-for-value present while `status` JSON
  omits it. No current durable field or successful CLI key set changed.
- Five focused checks covering the four new regressions passed together on
  current Git in 1.896 seconds and exact Git 2.29.0 in 1.620 seconds. The final
  affected allocation, state,
  auxiliary-ref, CLI, and hook surface passed 51/51 on Git 2.43.0 in 60.581
  seconds and on exact Git 2.29.0 in 52.218 seconds. The complete final suite
  passed 226/226 in 557.611 seconds on Git 2.43.0 and 226/226 in 495.240
  seconds on exact Git 2.29.0, both with CPython 3.12.3. Final clone and
  worktree hardening each reported 57 defined, 56 exercised passes, one
  conditional reftable skip, and zero failures; their JSON SHA-256 values are
  `c1fe5910cb6225a64e2318850f8dd745845c7455b7a4699969ae1844fa52c58f`
  and `9ab5238ef80779b74c32a25d29054c8550304fa96fd269c128f9194d9c8c2dc1`.
- Saved Step 6.2 reports remained intact at SHA-256 `3a43aaca...` and
  `c0e8ef18...`. Against their stable five-fixture pre-change counts, the
  final five-fixture probe moved clone from 73 total/44 rev-parse/17 common-dir
  calls to 64/37/14 and worktree from 53/40/15 to 46/33/12; every final sample
  had the same counts. Saved Step 6.3 baseline/post reports remained intact at
  `bead75cbae...` and `e30e48db...`; their recorded reductions remain clone
  0.199512 to 0.139784 seconds summed single-lock time and 1.790971 to 1.410101
  seconds eight-way wall time, and worktree 0.201623 to 0.156690 and 1.747280
  to 1.496226. The 40/40 race artifact remained intact at `16f15aaf...`.
- A fresh final lock diagnostic kept exactly four measured workspace locks per
  clone and five per worktree and completed all 90 spawns. On the then-current
  host it observed single held medians of 0.181021/0.205584 seconds and
  eight-way per-spawn held medians of 0.283541/0.273808 for clone/worktree.
  That reconstructed probe is not the removed Step 6.3 harness, and its wider
  system wall times show the host was slower, so these figures are recorded as
  observations rather than substituted into the earlier before/after ratios.
- The unchanged auxiliary benchmark stayed at SHA-256 `6feacc2947...`. Its
  final 15-scenario artifact is
  `/tmp/clonegrown-step-6.8-final-auxiliary-refs.json` at SHA-256
  `d7b4a6bdae6592dfb42651cb450c15bf86ebd9a4b1464bc40822765787695634`.
  It passed in 65.312 observed seconds: current clone median 3.335577 seconds
  (MAD 0.063389, range 3.272188–3.684069), simulation median 3.434800 and
  ratio 1.029747, with the required 4,612 total refs, 2 loose refs, 1 loose
  auxiliary ref, and 20,344,832 allocated bytes in every current-clone sample.
  Worktree remained the shared-ref control. Timing is observational; every
  exact-ref, metadata, offline, update, and storage predicate passed.
- The five preserved research files remain byte-identical at their recorded
  SHA-256 values. Current-Python full suites now pass on both Git endpoints;
  the Python 3.11/latest-stable and Linux/macOS hosted endpoint evidence still
  belongs to the published Phase 5 SHA rather than this uncommitted tree, and
  this record does not relabel it. Step 6.7 still owns isolated wheel/sdist and
  final support-metadata verification after Kyle supplies an explicit license.
  No workflow, dependency, license, command surface, current durable schema,
  preserved artifact, or repository path was created by this review pass.

## Phase 7 — Synchronize the artifact and qualify the result

### Step 7.1 — Perform the final claim, comment, and evidence audit — complete 2026-09-02

- Synchronize README, installed skill, package/API docstrings, CLI help, and
  architecture with the implemented lease/quarantine/state/error protocols.
  Cover ignored files, active writers, worktree sharing, clone object sharing,
  one-shot collection, collection versus integration, and recovery limits.
- Label every reported experiment as current-package evidence or preserved
  historical evidence with commit, environment, and reproducibility status.
  Remove no historical artifact and recreate no missing artifact as “original.”
- Search every “never,” “always,” “safe,” “isolated,” “idempotent,” and
  “recovered” claim and tie it to a tested invariant or qualify it literally.

Completion record:

- The verified starting tree contained every named documentation surface but
  no standalone source-review artifact. Direct inspection of the lifecycle,
  recovery, audit, worker, state, repository, and CLI implementations exposed
  specific documentation mismatches: recovery can resume a previously
  authorized discard; `status` audits a finite set of documented invariants
  and may recreate the control lock; request-key reuse depends on recorded
  state; failed unpublished spawns have no releasable lease; recursive
  deletion errors can leave partial residue; and clone/worktree isolation is
  not an operating-system sandbox. Those claims were corrected without
  treating the nonexistent review artifact as something restored.
- `README.md`, `SKILL.md`, `ARCHITECTURE.md`, and
  `research/REPRODUCE.md` now cover ignored content, active writers,
  worktree-shared refs/config/stash/hooks/objects, clone object sharing at
  spawn, one-shot collection, separate integration, cooperative leases,
  quarantine custody, partial deletion, represented recovery, and the exact
  audit scope. Current local Phase 6 evidence, hosted Phase 5 evidence, and
  recovered historical evidence are labeled separately with the available
  revision, environment, and reproduction limits.
- Public docstrings in `clonegrown/__init__.py`, `clonegrown/audit.py`,
  `clonegrown/core.py`, `clonegrown/lifecycle.py`, and
  `clonegrown/recovery.py` were synchronized. `clonegrown/cli.py` help now
  exposes the same boundaries. The only executable product edits are those
  help strings; the docstrings affect runtime introspection but not lifecycle
  behavior. `tests/test_cli.py` adds one help-contract test;
  `tests/test_audit.py`, `tests/test_lease.py`, and
  `tests/campaign/state_machine_fuzz.py` contain comment/docstring
  qualifications only for this Step. `PLAN.md` and `HANDOFF.md` record the
  result. No file was created or deleted by Step 7.1.
- The Step changed no API signature, lifecycle algorithm, current durable
  schema, JSON output, dependency, workflow, or preserved research artifact.
  It preserved the complete uncommitted Phase 6 boundary. Focused discovery
  runs passed `tests/test_cli.py` 6/6, `tests/test_api.py` 6/6, and
  `tests/test_audit.py` 20/20. Two preliminary nonstandard invocations stopped
  during import because each omitted one required import root; no assertion
  ran in either. The repository-recorded discovery form produced the passing
  results. Out-of-checkout byte compilation, preserved-artifact comparison,
  the final absolute-language sweep, and `git diff --check` passed.

---

> Original lines 3063–3134 remain active in the current roadmap. The
> following source-ordered block resumes at original line 3135.

### Milestones

- After Phases 1–2: destructive operations have a truthful contract and a
  conservative, recoverable custody protocol.
- After Phases 1–4: the review's correctness, safety, Git-fidelity, state, and
  error-handling findings are implemented and regression-tested; this is the
  review's threshold for “well engineered.”
- After Phases 5–7: CI, support boundaries, evidence, performance, packaging,
  and public prose are release-quality. Product outreach or claims about agent
  behavior happen only after this point.
