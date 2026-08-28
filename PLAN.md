# Clonegrown plan

## Goal

Turn the validated alpha implementation into a conventional, explicit Python
package without changing its Git protocol, command-line behavior, durable
state, or safety guarantees — then, and only then, take on new product
behavior.

## Plan vocabulary

A **Phase** is one major body of related roadmap work. A **Step** is one
numbered part inside that Phase. This remediation roadmap is intentionally
multi-pass: `$next` completes exactly one unfinished Step and stops; completing
a Step does not mean its Phase is complete. For example, **Phase 1** is the
whole contract-and-installer remediation body and contains **Steps 1.1 through
1.11**. Use “Phase 1” for that whole body and “Step 1.8” for its individual
next part.

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

The source review is `clonegrown-engineering-review.md`, written against
commit `2cd212c2cf76dd8bb9567b92341c6fb451ad375b`, which is the current `HEAD`.
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

### Step 1.8 — State recovery guarantees at represented checkpoints

- Rewrite the `recovery.py` module contract to describe the actual durable
  checkpoints and the destructive published-alpha recovery path. Remove the
  unconditional promises of rollback to the last safe state and no deletion
  unless they first become executable invariants in a later Step.
- Check nearby recovery comments and user-facing descriptions for the same
  stronger claim, changing only prose that contradicts the represented state
  machine.
- Verification: focused recovery-claim search, recovery tests, the unit suite,
  and `git diff --check`. This Step changes prose only.

### Step 1.9 — Print PATH guidance as a shell-safe command

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

### Step 1.10 — Scope the JSON output claim to lifecycle success results

- Update `ARCHITECTURE.md` to say that successful lifecycle operations emit
  JSON, while help, version output, argument errors, and Clonegrown runtime
  errors are text on their documented streams. Check the adjacent CLI prose
  for equivalent absolutes.
- Verification: direct probes of one lifecycle success plus help, version,
  argument-error, and runtime-error paths; focused claim search; the unit suite;
  and `git diff --check`. This Step changes prose only.

### Step 1.11 — Cold-review Phase 1 remediation

- A fresh agent reviews the complete Phase 1 diff, concentrating on the seven
  Step 1.3 findings, installer deletion authority, path framing and quoting,
  rollback behavior, sentinel preservation, and exact user-facing claims. The
  reviewer does not patch opportunistically.
- Re-run every Phase 1 check, including the adversarial probes added in Steps
  1.4–1.10. Record the review result here; any confirmed issue becomes another
  bounded Phase 1 Step before Phase 2 begins.

## Phase 2 — Make destructive worker operations conservative and recoverable

### Step 2.1 — Centralize status-specific durable-state validation

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

### Step 2.2 — Add an explicit worker lease and one-shot handoff

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

### Step 2.3 — Bring ignored files into discard custody

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

### Step 2.4 — Give worktree branch and admin cleanup compare-and-swap ownership

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

### Step 2.5 — Quarantine, recheck, and prove deletion

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

### Step 2.6 — Preserve interrupted-spawn work and close the worktree-add window

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

### Step 2.7 — Cold-review Phase 2

- A fresh agent attacks active-writer handoff, ignored content, quarantine
  authentication, partial deletion, published-worker recovery, and branch/admin
  compare-and-swap behavior. It must try concrete failing scenarios in both
  worker modes.
- Run focused destructive tests first, then unit tests and the full hardening
  suite in clone and worktree modes. Insert confirmed fixes before Phase 3.

## Phase 3 — Make state allocation, idempotency, status, and recovery auditable

### Step 3.1 — Make worker allocation create-only

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

### Step 3.2 — Validate idempotent request-index hits end to end

- Validate request-index field types, exact request ID, parameter digest, and
  worker ID before loading a record. Validate the target record against state
  and ensure its own request ID/digest point back to the same index.
- Before returning a settled record, authenticate live ready/collected workers,
  verify collected result refs, and prove gone workers have no owned live path.
  Corrupt or stale indexes fail closed with a status-visible diagnosis.
- Regressions cover missing records, nonnumeric IDs, cross-linked indexes,
  altered digests, replaced workers, missing result refs, tombstone residue,
  and concurrent valid reuse.

### Step 3.3 — Turn `status` into a complete nonmutating invariant audit

- Audit live-status worker/stage/quarantine presence, worker authentication,
  expected branches and worktree admin entries, immutable and summary result
  refs, temporary base refs, tombstone residue, request indexes, and namespace
  refs with no record.
- Surface retained collection candidate refs and deletion/cleanup conflicts.
  Use stable issue codes plus bounded human context; never repair during
  `status` and never print secret config values or file contents.
- Extend the documented output contract and tests for each contradiction,
  including a missing repository that current `status` silently omits.

### Step 3.4 — Reconcile only provably owned residue in `recover`

- Teach recovery to resume quarantined deletion, finish checked branch/admin
  cleanup, remove stale temporary base refs only when their worker/status makes
  ownership unambiguous, and retain candidate/result refs as custody evidence.
- Report ambiguous namespace refs, stale request indexes, and residue instead of
  deleting them. Recovery remains idempotent and continues past one corrupt
  record.
- Add repeated-recovery tests for every issue introduced in Step 3.3, including
  interrupted finalization and summary-ref repair.

### Step 3.5 — Cold-review Phase 3

- A fresh agent corrupts records, indexes, counters, refs, and paths while
  checking that `status` observes without mutation and `recover` mutates only
  authenticated targets.
- Re-run metadata red-team, state-machine, unit, and both hardening modes.

## Phase 4 — Restore exact Git semantics and safe operational errors

### Step 4.1 — Make Git execution explicit, sanitized, structured, and redacted

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

### Step 4.2 — Build a pure remote/config copy plan, then apply it imperatively

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

### Step 4.3 — Align the Python API and reject invalid generated branches early

- Change the Python `spawn` default to `strong=False` and pin CLI/API parity in
  tests and examples. Preserve explicit `strong=True` and worktree rejection.
- Validate the complete generated branch with `git check-ref-format --branch`
  before advancing allocation metadata or creating refs. Cover `.lock`, ref
  syntax edge cases, maximum task length, Unicode sanitization, and hostile
  input without shell execution.
- Remove the repository-unreferenced public `CWSError` alias and update
  imports/docs while retaining the on-disk `cws` protocol and test-variable
  names until their separately planned gate exists.

### Step 4.4 — Give every public operation safety-context errors

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

### Step 4.5 — Cold-review Phase 4

- A fresh agent probes custom Git execution, relative URLs, valueless config,
  secret-bearing failures, branch generation, API defaults, and low-level error
  conversion. It verifies that redaction does not erase the information needed
  to diagnose a failure.
- Run focused compatibility tests, unit tests, and both hardening modes.

## Phase 5 — Separate correctness from benchmarks and close validation gaps

### Step 5.1 — Make concurrency correctness deterministic and benchmarking nonblocking

- Keep eight-way uniqueness, no-overwrite, request-id, and state-integrity
  assertions blocking. Remove the single-sample wall-time ratio from the
  correctness result.
- Add a manual/scheduled benchmark job that measures multiple single and
  parallel samples per worker mode, reports raw samples plus median and spread,
  and never turns runner noise into a correctness failure.
- Verify the formerly red worktree scenario repeatedly without code changes;
  CI is green only because all deterministic assertions pass, not because the
  threshold was loosened.

### Step 5.2 — Add real parent/child interruption coverage

- Add real-process cases that kill only the Python parent while a spawned Git
  child may remain alive, including the exact worktree-add/admin-persist
  window, clone provisioning, collection fetch, and worktree repair/cleanup.
  Track child exit and filesystem/ref state before invoking recovery.
- Extend crash matrices for every new lease/quarantine/cleanup boundary. If a
  new failure appears, stop this Step after naming its cause and insert a
  focused fix Step; do not patch the harness around it.

### Step 5.3 — Put bounded randomized campaigns on a scheduled lane

- Run bounded random-kill and state-machine seeds for clone and worktree modes
  on a nightly/manual workflow with seed, step count, Python/Git versions, and
  artifacts recorded. Keep PR CI deterministic and reasonably short.
- Make a failed seed directly replayable with one documented command and retain
  no generated output in the checkout.

### Step 5.4 — Test the supported version and operating-system envelope

- Run destructive-path tests on macOS as well as Linux. Test the oldest
  supported Python (3.11) and the latest stable Python at execution time.
- Derive a minimum Git version from the commands Clonegrown actually uses,
  document it, and add one job that runs that exact minimum rather than relying
  only on mutable hosted-runner Git versions.
- Keep native Windows explicitly unsupported in 0.x; do not imply POSIX
  `fcntl`, rename, or deletion results transfer to Windows.

### Step 5.5 — Pin filter/resource behavior or state the boundary

- Add real-repository tests for a custom clean/smudge filter and any Git LFS
  behavior that can be exercised reproducibly without credentials. If Git LFS
  is not made a supported dependency, state it as unvalidated/unsupported
  rather than simulating it.
- Exercise write, rename, and deletion failures through targeted fault
  injection, including no-space and partial-cleanup equivalents. State that
  genuine disk/inode exhaustion and network/distributed filesystems remain
  outside support until run on those systems.

### Step 5.6 — Run a small real-repository qualification matrix

- On disposable clones outside this checkout, run lifecycle and recovery
  scenarios against at least: an ordinary history-heavy repository, a
  ref-heavy repository, and a repository using submodules/sparse checkout or
  filters. Record exact public commit IDs, Git/Python versions, worker modes,
  and results under `research/`.
- Treat this as validation evidence, not a universal performance policy and
  not proof that coding agents make fewer mistakes.

### Step 5.7 — Cold-review Phase 5

- A fresh agent audits the workflows for test theater, machine-sensitive gates,
  missing replay data, unsupported-platform overclaims, and failures hidden by
  `continue-on-error` or permissive shell behavior.
- Require green deterministic CI and replay at least one artifact from every
  scheduled campaign before Phase 6.

## Phase 6 — Remove residue and optimize only from measurements

### Step 6.1 — Gate test hooks, remove dead heartbeat state, and prune campaign residue

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

### Step 6.2 — Cache canonical verification within one transaction

- Instrument current spawn Git calls and establish the baseline. Introduce a
  transaction-scoped verified workspace/canonical value that can be reused
  only while the relevant lock and identity assumptions remain valid; add no
  global or cross-command cache.
- Remove repeated `rev-parse --git-common-dir` and equivalent verification only
  where the same transaction has already proved the invariant. Re-run tamper,
  replacement, and crash tests before comparing call counts and timings.

### Step 6.3 — Shorten workspace-lock critical sections without weakening allocation

- Measure lock-held phases with multiple samples after Step 6.2. Move only
  immutable preparation outside the lock; keep worker-ID allocation, request
  indexing, state transitions, publication checks, and compare-and-swap ref
  mutations serialized where correctness requires it.
- Re-run eight-way uniqueness and request-id races many times unchanged, then
  report lock time and total time without a pass/fail performance ratio.

### Step 6.4 — Measure and decide the auxiliary-ref compatibility contract

- Rerun the ref-heavy benchmark against the current package, including remote
  tracking refs, notes, and replace refs, with spawn time, ref count, loose-ref
  count, and disk use recorded.
- Define the minimum offline compatibility contract before choosing all refs,
  narrowing, packing, or a combination. Notes and replace refs remain
  correctness-sensitive; do not optimize them away by accident.
- End this Step by replacing Step 6.5's generic wording with the exact chosen
  policy and measured acceptance thresholds. No provisioning code changes in
  this Step.

### Step 6.5 — Implement the measured auxiliary-ref policy

- Apply only the policy recorded by Step 6.4, with real Git tests for offline
  remote comparisons, notes, replace refs, ref updates, and ref-heavy workers.
- Compare correctness, spawn time, and disk use to the Step 6.4 baseline. Revert
  the optimization if its compatibility contract cannot be proved.

### Step 6.6 — State retention and teardown conservatively

- For 0.x, retain worker metadata and immutable result refs indefinitely by
  default, and provide no automatic workspace teardown that could outrun user
  custody. Document how to inspect and manually integrate retained refs.
- Specify the evidence a future explicit prune/teardown operation would need,
  but do not add that destructive command without its own approved plan and
  adversarial tests.

### Step 6.7 — Complete package and support metadata

- Add accurate project metadata, tested Python/Git requirements, platform
  classifiers, and release/support boundaries; verify wheel and sdist metadata
  in isolated installs.
- **User gate:** a software license grants real redistribution rights and
  cannot be inferred. Before this Step, Kyle must reply with the literal choice
  `Use the <license name> license for Clonegrown.` Then add that exact license
  file and matching package metadata. Until then, skip this blocked Step and
  continue with another unblocked one.

### Step 6.8 — Cold-review Phase 6

- A fresh agent checks that test hooks are inert in production, historical
  evidence was not rewritten, performance changes preserve every safety
  invariant, and package claims match tested support.
- Run the full deterministic suite and compare measured performance/call-count
  reports to the pre-optimization baselines.

## Phase 7 — Synchronize the artifact and qualify the result

### Step 7.1 — Perform the final claim, comment, and evidence audit

- Synchronize README, installed skill, package/API docstrings, CLI help, and
  architecture with the implemented lease/quarantine/state/error protocols.
  Cover ignored files, active writers, worktree sharing, clone object sharing,
  one-shot collection, collection versus integration, and recovery limits.
- Label every reported experiment as current-package evidence or preserved
  historical evidence with commit, environment, and reproducibility status.
  Remove no historical artifact and recreate no missing artifact as “original.”
- Search every “never,” “always,” “safe,” “isolated,” “idempotent,” and
  “recovered” claim and tie it to a tested invariant or qualify it literally.

### Step 7.2 — Prune the development transcript into a current roadmap

- Invoke the repository `$prune` procedure: archive completed narrative from
  this `PLAN.md` under `research/` with dates/provenance, preserve every open
  decision, and leave `PLAN.md` as a concise statement of current state and
  remaining executable Steps.
- Update architecture/research links to the archive without turning the archive
  into normative product documentation.

### Step 7.3 — Run the one-afternoon orchestrator simulation

- On a scratch clone, have an agent use the installed `SKILL.md` alone to
  initialize, spawn at least three workers, claim/release leases, work, collect,
  integrate explicitly, discard, interrupt one lifecycle operation, recover,
  and inspect status.
- Record where the agent needed human correction. Fix only confirmed product or
  instruction defects through newly inserted Steps; do not tune prompts to hide
  a broken CLI.

### Step 7.4 — Run paired live-agent research only before making behavior claims

- If Clonegrown will claim fewer agent mistakes or less human intervention than
  ordinary worktrees, design and run the paired A/B experiment already required
  by `research/REPORT.md`. Otherwise keep that claim explicitly out of product
  prose and mark this Step not applicable.

### Step 7.5 — Final cold review and release qualification

- A fresh agent receives the original 18 findings, comment/AI-residue audit,
  test-gap list, and this coverage map, but no implementation narrative. It
  must prove or reject each claimed closure from current code and tests.
- Run unit tests; installer tests; clone/worktree hardening; every crash case;
  bounded state-machine and random-kill seeds; package build/install; Linux and
  macOS CI; the minimum-Git job; and `git diff --check`. Keep outputs outside
  the checkout and require the pushed destination's CI to be green.
- Completion means every verified defect is fixed with a class regression,
  every unsupported boundary is stated literally, every product claim matches
  evidence, and no cold-review finding remains open.

### Review coverage map

| Review item | Planned closure |
|---|---|
| 5.1 active-writer race | 2.2 lease, 2.5 quarantine/recheck, 5.2 process interruption |
| 5.2 ignored work | 2.3 policy/tests, 7.1 final claims |
| 5.3 unchecked deletion | 2.5 checked protocol, 3.4 recovery |
| 5.4 branch ownership | 2.4 compare-and-swap refs |
| 5.5 changed published recovery | 2.6 preserve as broken |
| 5.6 unsafe installer root | 1.2 ownership/staged replacement |
| 5.7 relative remotes | 4.2 canonicalized copy plan |
| 5.8 valueless config | 4.2 tri-state config entries |
| 5.9 custom Git sanitation | 4.1 explicit Git runner |
| 5.10 secret-bearing errors | 4.1 redaction, 4.2 sensitive application |
| 5.11 stale request reuse | 3.2 end-to-end validation |
| 5.12 incomplete status | 3.3 invariant audit |
| 5.13 implicit lifecycle / stale ID | 2.1 validators, 3.1 create-only allocation |
| 5.14 API/CLI mismatch | 4.3 `strong=False` parity |
| 5.15 invalid generated branch | 4.3 Git validation |
| 5.16 low-level errors | 4.4 operation safety context |
| 5.17 noisy CI timing gate | 5.1 benchmark separation |
| 5.18 one-shot ambiguity | roadmap call 1, 1.1/2.2/7.1 |
| Comment and public overclaims | 1.1 immediate correction, 7.1 final audit |
| `CWSError`, heartbeat, failpoints, campaign residue | 4.3, 6.1 |
| PLAN/history and two evidence eras | 7.1–7.2 |
| Parent-only death and add/persist window | 2.6, 5.2 |
| macOS, Python/Git versions | 5.4 |
| filters/LFS, resource/filesystem boundaries | 5.5 |
| broad repository diversity | 5.6 |
| repeated verification and lock time | 6.2–6.3 |
| auxiliary-ref cost/contract | 6.4–6.5 |
| retention, teardown, license, package metadata | 6.6–6.7 |

### Milestones

- After Phases 1–2: destructive operations have a truthful contract and a
  conservative, recoverable custody protocol.
- After Phases 1–4: the review's correctness, safety, Git-fidelity, state, and
  error-handling findings are implemented and regression-tested; this is the
  review's threshold for “well engineered.”
- After Phases 5–7: CI, support boundaries, evidence, performance, packaging,
  and public prose are release-quality. Product outreach or claims about agent
  behavior happen only after this point.
