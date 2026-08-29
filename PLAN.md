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
1.13**. Use “Phase 1” for that whole body and “Step 1.8” for one individual
part.

## Status

### 2026-08-28 — Phases 1 through 4 of the remediation roadmap are complete

Kyle chose to run the remediation phases rather than the earlier
simulate/find-users/stop product choice. Phases 1 through 3 were each
cold-reviewed by a fresh agent and then bughunted, with every confirmed
finding fixed and re-reviewed in the same pass; Phase 4 closed with the same
fix-and-fresh-review discipline in Step 4.5. The records sit under each Phase
below. The working state is on `main`: 187 unit tests
(`python3 -m unittest discover -s tests`), the 56-case hardening campaign in
clone and worktree modes, out-of-checkout byte compilation, `sh -n install.sh`,
trailing-whitespace checks, and `git diff --check` all pass. The next `$next`
pass is Phase 5 Step 5.1. Nothing needs Kyle.

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
