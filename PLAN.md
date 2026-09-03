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
a Step does not mean its Phase is complete. Phases 1–6, Steps 7.1–7.4, and the
inserted Steps 7.5a–7.5i are complete. The second final cold review returned a
no-go and inserted remediation Steps 7.5j–7.5o. Final Step 7.5 resumes only
after those six verified blocker roots are repaired and freshly re-reviewed.

## Current state

Updated 2026-09-02 after the second Phase 7 Step 7.5 cold review.

- Phases 1–6 are complete in the local working tree. Phase 7 Steps 7.1–7.4,
  inserted remediation Steps 7.5a–7.5i are complete. Steps 7.5j–7.5o and final
  Step 7.5 remain incomplete after a fresh reviewer independently reproduced
  six in-contract defects.
- The dated development transcript through Step 7.1 moved verbatim to
  [`research/PLAN-ARCHIVE.md`](research/PLAN-ARCHIVE.md). That archive records
  provenance and completed work; this file is the normative current roadmap.
- The combined Phase 6–7 work is preserved as a deliberately incomplete
  checkpoint on `main`. It is not release-qualified. `HANDOFF.md` records the
  exact implemented boundary, all six open findings, and the next sequence.
- On the checkpoint tree, the coordinating session passed 254/254 tests in
  278.176 seconds and the independent reviewer repeated 254/254 in 295.072
  seconds on Linux with CPython 3.12.3 and Git 2.43.0. Clone and worktree
  hardening each exercised 56 passing cases, conditionally skipped reftable,
  and reported zero failures. All 12 bounded random-kill runs, four 50-step
  state-machine runs, and the package build/install gate passed. Those broad
  passes do not supersede the six independently reproduced defects.
- Apache License 2.0 is the authorized license. `LICENSE` contains the
  canonical text and `pyproject.toml` uses the `Apache-2.0` SPDX expression.
- No current evidence establishes that Clonegrown reduces coding-agent mistakes
  or human intervention relative to ordinary worktrees. Step 7.4 governs any
  such claim.

## Current product contract

These calls remain binding unless a later explicitly approved plan changes
them:

1. A worker is **one-shot after collection**. New work gets a new worker;
   collection never becomes implicit integration or a multi-result session.
2. Every published worker has a durable, cooperative work lease. Normal or
   abandoned deletion requires an explicit lease release; records predating
   the lease field are treated as still leased. `--force` does not silently
   override a live lease.
3. Normal discard protects ignored content and clone-private refs. A collected
   worker with ignored paths requires `--discard-ignored` in addition to any
   post-collection drift acknowledgement. A clone with changed private refs or
   no legacy baseline separately requires `--discard-private-refs`.
   `--abandon` applies only to an uncollected worker and means abandoning all
   of its content.
4. Deletion is a recoverable protocol: authenticate, record intent, atomically
   quarantine, recheck, delete with errors enabled, verify absence, then clean
   worktree state and record a terminal status. Unexpected work stays in
   quarantine and is reported; it is never converted into success.
5. The Python API matches the CLI default: `mode="clone", strong=False`.
6. The on-disk `.cws` / `refs/cws` protocol name remains for compatibility.
   `ClonegrownError` is the public error type; the unused `CWSError` alias is
   removed.
7. Clonegrown 0.x is POSIX-only and standard-library-only. Native Windows,
   network/distributed filesystems, and Git LFS are unsupported until dedicated
   validation passes. This is a support boundary, not a claim that they are
   broken.
8. The canonical-source push URL is a best-effort accident guard, not a
   security boundary. Exact-base pinning, immutable result refs, explicit
   integration, authenticated paths, targeted worktree cleanup, direct argv
   subprocesses, and real-repository tests remain intact.
9. Terminal worker metadata and immutable result refs are retained indefinitely
   by default in 0.x. A normally discarded record must retain and authenticate
   its result fields. Clonegrown provides no automatic workspace teardown;
   integration and any future destructive pruning remain separate,
   user-authorized operations.
10. Clone workers preserve the enumerated object-ID snapshot of every promised
    remote-tracking, notes, and replace ref, fetch those exact refspecs once,
    and pack the staged clone. Worktree workers continue to share canonical
    namespaces and Clonegrown does not pack canonical refs.

## Decisions

### Resolved

- **Auxiliary-ref policy.** Preserve every promised remote-tracking, notes,
   and replace ref using the exact enumerated object-ID snapshot, one fetch,
   and clone-only packing. Steps 6.4–6.5 implemented the measured policy; Step
   6.8 closed the snapshot/count race.
- **Clone tool or workspace manager.** Clonegrown is a workspace manager with
   supported clone and shared-worktree worker modes.
- **License.** Kyle authorized Apache License 2.0 (`Apache-2.0`) on
   2026-09-02; Step 6.7 added and verified it.

### Open

These decisions require an explicit choice and their own plan before code
changes.

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

## Evidence and release boundary

- **Current package, local Phase 6–7 checkpoint.** On Linux with CPython
  3.12.3 and Git 2.43.0, the coordinating run passed 254/254 tests in 278.176
  seconds and the independent reviewer repeated 254/254 in 295.072 seconds.
  Clone and worktree hardening each reported 57 defined, 56 exercised passes,
  one conditional reftable skip, and zero failures. Twelve bounded random-kill
  runs and four 50-step state-machine runs passed. The wheel and source archive
  built and installed in isolated environments; both entry points,
  Apache-2.0 metadata, and the canonical license hash passed. The final fresh
  review nevertheless found six release-blocking defects, so this is a
  preservation checkpoint rather than release evidence.
- **Earlier exact minimum-Git evidence.** On the prior Phase 6 tree, exact Git
  2.29.0 and Git 2.43.0 each passed 226/226 tests. Exact Git 2.29.0 has not been
  freshly rerun against the current checkpoint.
- **Claim audit, local Step 7.1 tree.** Focused discovery passed `test_cli.py`
  6/6, `test_api.py` 6/6, and `test_audit.py` 20/20. Out-of-checkout byte
  compilation, preserved-artifact comparison, the absolute-language sweep,
  and `git diff --check` passed.
- **Current package, hosted pre-Phase-6 revision.** GitHub Actions run
  33278590221 passed all seven blocking jobs at
  `354d16bc662f15f65dded911d3c26729bf5804aa`, covering Ubuntu, macOS,
  Python 3.11/latest-stable, exact Git 2.29.0, and both hardening modes.
  Scheduled randomized run 33638194991 later passed at the same revision.
  These runs predate the local Phase 6–7 tree.
- **Preserved historical prototype.** `research/REPORT.md` identifies the
  absent `cws.py` candidate at source commit `be4391c`.
  `research/RESULTS.json` is preserved, but missing candidate and raw campaign
  inputs prevent byte-for-byte reproduction. `research/FALSIFICATION.md` has
  additional missing provenance. Current harness results must not be relabeled
  as historical evidence.

`research/REPRODUCE.md` gives current commands and the exact reproduction
limits. None of these evidence sets establishes universal performance or
better coding-agent behavior.

## Final-review input bundle

Step 7.5 must use these inputs without relying on the implementation narrative:

- The standalone original source-review artifact is **nonexistent in this
  checkout**. Its inline verified starting state and finding descriptions are
  preserved in the archive under
  [`Verified starting state`](research/PLAN-ARCHIVE.md#verified-starting-state).
- The original 18 review items and their claimed closure locations are in the
  coverage map below. A closure location is a claim to prove from current code
  and tests, not proof by itself.
- The comment/public-claim and generated-residue record is preserved in
  archived Steps
  [1.1](research/PLAN-ARCHIVE.md#step-11--correct-current-claims-and-freeze-the-custody-contract--complete-2026-08-27),
  [6.1](research/PLAN-ARCHIVE.md#step-61--gate-test-hooks-remove-dead-heartbeat-state-and-prune-campaign-residue--complete-2026-08-29),
  and
  [7.1](research/PLAN-ARCHIVE.md#step-71--perform-the-final-claim-comment-and-evidence-audit--complete-2026-09-02).
- The original validation gaps were Git LFS, arbitrary filters,
  network/distributed filesystems, genuine disk/inode exhaustion, native
  Windows, and broad real-repository behavior. External clean/smudge behavior,
  deterministic resource/failure boundaries, and a bounded public-repository
  matrix now have evidence. Git LFS, genuine exhaustion,
  network/distributed filesystems, and native Windows remain unsupported and
  unvalidated; they must stay literal support boundaries.
- Evidence belongs to three separate eras listed above: the uncommitted local
  Phase 6 tree, the hosted Phase 5 revision, and the preserved historical
  prototype. Step 7.5 must not transfer a result across those boundaries.

## Phase 7 — Synchronize the artifact and qualify the result

### Step 7.2 — Prune the development transcript into a current roadmap — complete 2026-09-02

- The repository `$prune` procedure found `PLAN.md` as the only plan target in
  this repository and found no plan document directly one level up. Sibling
  project plans were outside scope.
- `research/PLAN-ARCHIVE.md` is new. It preserves original `PLAN.md` lines
  20–3062 and 3135–3144 verbatim, in order, with the source file's pre-prune
  SHA-256 and a provenance header. Still-active decisions and product calls
  remain here.
- `PLAN.md` now states current status, binding contracts, every open decision,
  evidence boundaries, the final-review input bundle, and only the remaining
  executable Steps. `ARCHITECTURE.md` and `research/REPRODUCE.md` link the
  archive as historical context, not normative product documentation.
  `HANDOFF.md` records this stop point.
- This Step changes documentation only. It creates no executable, test,
  workflow, package-metadata, or experimental-evidence path and changes no
  behavior.
- Verification confirmed 3,053 verbatim source lines (3,043 plus 10);
  `PLAN.md` fell from 3,144 to 280 lines. Every new file link and required
  archive heading resolves, preserved experimental evidence has no diff, the
  combined dirty-tree count is 37 paths, and `git diff --check` passes. The
  runtime suite was not rerun for this documentation-only Step; the Step 6.8
  baseline remains the current full result.

### Step 7.3 — Run the one-afternoon orchestrator simulation — complete 2026-09-02

- On a scratch clone, have an agent use the installed `SKILL.md` alone to
  initialize, spawn at least three workers, claim/release leases, work, collect,
  integrate explicitly, discard, interrupt one lifecycle operation, recover,
  and inspect status.
- Record where the agent needed human correction. Fix only confirmed product or
  instruction defects through newly inserted Steps; do not tune prompts to hide
  a broken CLI.

Completion record:

- The current 37-path tree based on
  `354d16bc662f15f65dded911d3c26729bf5804aa` was snapshotted outside the
  checkout at temporary commit `0576f933a066627a62996944bb1e395381027989`.
  Clonegrown 0.1.0a1 was installed from that snapshot with CPython 3.12.3.
  Its isolated installed `SKILL.md` was byte-identical to the source at
  SHA-256 `f9b51e944e60472745d2d26833c664b489865c651d35e678dbf2194cbf363a7d`.
  A fresh agent received that skill as its sole Clonegrown guidance and was
  barred from the implementation, tests, roadmap, architecture, and research.
- In disposable workspace `09a351954ded4dc7`, the agent spawned three
  default-clone workers, exercised `release` then `claim` on ready worker 2,
  made and committed the three independent requested changes, and collected
  all three before integration. It then explicitly cherry-picked the three
  immutable result refs into canonical `main`, stopped its writers, released
  and discarded workers 1–3, and proved their paths absent. The result refs
  remained resolvable after discard.
- For the interruption case, a required smudge filter blocked worker 4's
  checkout. The agent identified Clonegrown parent PID 685185 and its Git and
  filter children, sent SIGKILL only to the Clonegrown parent, released the
  filter, and let the child settle. `clonegrown recover` returned
  `spawn-cleaned`; final status recorded worker 4 as `spawn_failed` with
  `interrupted spawn recovered`, no worker path or container, and `issues: []`.
- The agent needed no human workflow correction and observed no Clonegrown
  product or installed-skill defect. Its one false start was inability to see
  another command's PID through this shell runner's per-command PID namespace;
  host process visibility resolved the fixture mechanics. `SKILL.md` makes no
  PID-namespace claim, so this is not a product or instruction finding and no
  remediation Step is inserted.
- The coordinating session independently repeated public status, Git ref,
  exact-content, path-absence, and canonical-history checks. Canonical was
  clean and exactly three commits ahead with only the requested files; all
  results matched the agent report. Parent-repository hashes remained
  byte-identical to their pre-delegation values.
- The complete prompt boundary, commands, public outputs, result table,
  interruption trace, correction record, and independent validation are in
  [`research/ORCHESTRATOR_SIMULATION.md`](research/ORCHESTRATOR_SIMULATION.md).
  This Step creates that current-package evidence report and changes only
  `PLAN.md`, `ARCHITECTURE.md`, `research/REPRODUCE.md`, and `HANDOFF.md`.
  It changes no executable, test, workflow, README, installed-skill, package
  metadata, durable protocol, or preserved historical evidence path.

### Step 7.4 — Run paired live-agent research only before making behavior claims — not applicable 2026-09-02

- If Clonegrown will claim fewer agent mistakes or less human intervention than
  ordinary worktrees, design and run the paired A/B experiment already required
  by `research/REPORT.md`. Otherwise keep that claim explicitly out of product
  prose and mark this Step not applicable.

Resolution record:

- The current release will not make that claim. A product-surface sweep of
  `README.md`, `SKILL.md`, `ARCHITECTURE.md`, `pyproject.toml`, and
  `clonegrown/` found no affirmative statement that Clonegrown causes fewer
  agent mistakes or less human intervention than ordinary worktrees. The
  matching README and architecture text explicitly disclaims that conclusion.
  The Step 7.3 report and reproduction guide now state the same limitation.
- `research/REPORT.md` continues to preserve the unanswered research question
  and paired A/B design as historical context. It is not product prose and was
  not rewritten. Because the release makes no comparative claim, no paired
  experiment was run and this conditional Step is not applicable.
- The sweep exposed one stale README evidence link left by the Step 7.2 plan
  prune. README now links the detailed Phase 6 transcript directly and lists
  the bounded Step 7.3 simulation as qualitative, non-comparative evidence.
  This Step changes only `README.md`, `PLAN.md`, and `HANDOFF.md`; it changes
  no executable, test, workflow, skill, package metadata, protocol, or
  preserved historical evidence.
- The post-change product-surface sweep found the target language only in
  explicit non-claim statements. Both README evidence links resolve, the
  preserved historical reports have no diff, and changed-file whitespace plus
  `git diff --check` pass. Runtime tests were not rerun for this documentation
  decision; Step 7.5 owns the complete release matrix.

### Step 7.5a — Restore fd-backed Git interruption coverage — complete 2026-09-02

- The first Step 7.5 unit-suite run must be diagnosed before qualification can
  resume. If the observed parent-interruption failures are confirmed as a
  harness incompatibility with fd-backed canonical Git invocations, teach the
  existing blocking-Git fixture to recognize Git commands after global
  options and preserve any inherited descriptor needed by the delayed child.
- Add a class regression for command recognition and descriptor forwarding,
  then rerun the two failed worktree interruption cases and all six
  parent-interruption cases unchanged. This inserted remediation changes no
  Clonegrown product behavior or protocol.

Completion record:

- The first final-suite run executed 232 tests in 284.631 seconds: 230 passed,
  while the published-worktree-repair and worktree-add parent-interruption
  cases each timed out waiting for `started.json`. Repeating the repair case
  alone failed identically after 20.101 seconds, so this was not treated as a
  transient timing miss.
- A disposable pre-released probe completed the worktree spawn but created no
  blocking-wrapper marker. Current `git_at_git_dir` prepends
  `--git-dir=/dev/fd/<n>` to authenticated canonical mutations; the unchanged
  Phase 5 wrapper compared its target only at argument zero. It therefore
  delegated both worktree commands directly to real Git instead of pausing.
  Once recognized, the delayed real-Git subprocess also has to inherit that
  descriptor because its pathname is the authenticated repository handle.
- `tests/campaign/blocking_git.py` now locates the Git command after leading
  global options, reports command-relative arguments to the parent harness,
  and forwards descriptor-backed paths through `pass_fds` when it launches
  real Git. `tests/test_campaign_records.py` adds a direct class regression
  for option parsing, target recognition, and descriptor forwarding. No
  product, workflow, package, public documentation, durable state, or
  preserved evidence path changed.
- The new focused regression passed 1/1. The two originally failing tests
  passed together 2/2 without modification, then the complete real
  parent-interruption module passed 6/6 in 14.634 seconds. Final Step 7.5 owns
  the restarted full release matrix.

### Step 7.5b — Put clone-private refs in deletion custody — complete 2026-09-02

- Record the exact non-task ref baseline of each newly published clone. Before
  deleting a collected clone, compare its current private refs (including
  `refs/stash`) with that baseline and require a separate
  `--discard-private-refs` acknowledgement when they differ. A published clone
  whose older record has no baseline fails closed under the same
  acknowledgement; worktree workers do not gain this clone-only question.
- Include clone refs in the quarantine fingerprint so a ref change after
  authorization is preserved rather than deleted. Add class regressions for a
  unique stash, changed private refs, ordinary task-branch commits, legacy
  records, explicit acknowledgement, and the post-authorization race.

Completion record:

- Independent disposable reproduction proved that a clean collected clone
  with a unique `refs/stash` passed normal discard, removed its worker path,
  and left the stash commit unreachable from canonical. The cause was literal:
  the collection and authorization snapshots considered the task branch and
  worktree, while the quarantine fingerprint excluded `.git` and no durable
  publication baseline described other clone refs.
- New clone records now carry the direct-object or resolved-symbolic value
  reported by `for-each-ref` for each resolvable non-task ref at publication.
  Normal collected-clone deletion compares that baseline and refuses changed
  or unverified legacy private refs unless `--discard-private-refs` is passed.
  The second fresh review later proved that this inventory omits dangling
  symbolic refs; Step 7.5j owns that newly exposed class. The assigned task
  branch remains governed by the result/drift check, and worktree workers keep
  sharing canonical refs without this clone-only acknowledgement.
- Clone quarantine fingerprints now include the same resolvable ref listing. A real
  process paused after its custody snapshot, gained `refs/stash`, and was
  preserved in quarantine when the recheck differed. Reauthorization also
  keeps the private-ref acknowledgement separate. No dependency, result-ref,
  integration, worktree-ref, or preserved-evidence behavior changed.
- The three focused baseline/acknowledgement tests passed 3/3, the new
  post-authorization ref-race test passed 1/1, and the complete affected
  modules passed: discard custody 14/14, quarantine 33/33, CLI 6/6, and state
  validation 12/12.

### Step 7.5c — Make result publication and terminal custody fail closed — complete 2026-09-02

- Fetch the candidate object without a destination ref, then create the
  content-addressed result ref only if absent. Reuse an existing exact match;
  refuse a direct or symbolic conflict without overwriting it. Preserve the
  current interrupted-collection recovery contract.
- Require discarded records to retain their collected-result fields. Audit
  and authenticate both collected and discarded result custody, make request
  retries refuse a missing or moved discarded result, and let recovery report
  an irrecoverable missing result while repairing only the mutable summary
  pointer from a valid immutable result. Add direct conflicts, races, malformed
  terminal metadata, status, recovery, and request-retry regressions.

Completion record:

- Independent reproduction planted the exact upcoming content-addressed ref
  at another commit; `status` reported `candidate-ref-retained`, but the old
  `+candidate:result` fetch replaced it and collection succeeded. Collection
  now fetches the candidate object without a destination ref, then creates the
  result ref with an all-zero expected old value. A matching existing ref is
  reused; a pre-existing conflict and a ref planted after fetch both remain
  byte-for-byte at their old commit while collection rolls back to `ready`.
- Independent reproduction also deleted a normally discarded worker's result
  ref: the old audit reported no issue, same-request spawn returned the stale
  `discarded` record, and deleting its result fields still validated. A
  `discarded` record now requires `ready`, `collected`, `result_sha`, and
  `result_ref`; status audits its immutable result and summary; request reuse
  authenticates the retained result; and recovery reports
  `discarded-result-missing` without inventing a repair. If the immutable ref
  is valid, recovery may compare-and-swap the mutable summary back to it.
- Focused create-conflict, exact-reuse, create-race, terminal-audit,
  summary-repair, request-retry, and missing-field regressions pass. Complete
  affected modules passed: audit 23/23, allocation 19/19, and state 12/12.
  The unchanged seven-boundary collection crash matrix passed in clone and
  worktree modes; interrupted fetch/ref publication still either resets
  `ready` or finishes the exact candidate. The restarted release suite later
  exposed an object-only parent-death recovery gap and an untested symbolic
  create race; Step 7.5g records their separate reproduction and closure.

### Step 7.5d — Treat dangling worker paths as occupied — complete 2026-09-02

- Replace target-following existence decisions at worker-slot custody
  boundaries with lexical occupancy checks. A dangling or live symlink must
  be authenticated and refused before intent, quarantine, deletion, recovery,
  or a tombstone can claim the slot is absent.
- Add a class regression that moves the authentic worker aside, plants a
  dangling slot symlink, and proves discard refuses without changing the
  record or either path; cover status and recovery as non-mutating reporters.

Completion record:

- Independent reproduction moved an authentic collected clone aside and put a
  dangling symlink at its numbered slot. Target-following `Path.exists()` was
  false at authorization, quarantine, terminal audit, and recovery checks, so
  the old path recorded `discarded` while both the symlink and moved worker
  survived and `status` reported no issue.
- Worker-slot ownership decisions now use lexical occupancy. Authentication
  inspects the slot itself before the nested repository, so both live and
  dangling symlinks are named as symlink replacements. Publication, rollback,
  discard intent, quarantine, collision handling, status, orphan inventory,
  tombstone handling, and recovery all treat a dangling name as occupied.
- The direct regression proves discard refuses before changing the record,
  status reports `worker-authentication-failed`, recovery reports
  `collected-worker-path-invalid` without mutation, and both the symlink and
  relocated authentic worker survive. A terminal regression proves a dangling
  reoccupation reports `tombstone-path-occupied` and recovery leaves it.
- The two new regressions passed 2/2. Complete quarantine, audit, and allocation
  modules passed 35/35, 23/23, and 19/19. The existing live-symlink and full
  discard-crash cases passed in both clone and worktree hardening modes.

### Step 7.5e — Refuse unsafe init parents before writing — complete 2026-09-02

- Create or validate the workspace, `.cws`, and each control subdirectory in
  parent-before-child order, rejecting a non-directory or symlink before any
  child is created through it. Apply the same rule to canonical `.git/cws`
  before writing the identity marker.
- Add regressions proving a symlinked workspace control directory and a
  symlinked canonical marker directory leave their external targets untouched,
  while new and idempotent real-directory initialization still work.

Completion record:

- Independent reproduction showed the old init created `workers`, `requests`,
  `locks`, and `staging` through a symlinked `.cws` before refusing it. A
  symlinked canonical `.git/cws` was never rejected: init succeeded and wrote
  its marker into the external target.
- Init now preflights every existing workspace/control parent and the canonical
  marker directory before its first mutation, then creates and non-followingly
  validates each real directory in parent-before-child order. Canonical marker
  reads also require a real parent and real marker file, so later verification
  does not follow a replacement symlink.
- Regressions prove symlinked `.cws`, `workers`, and `.git/cws` targets remain
  empty; the canonical-parent refusal leaves the proposed workspace absent;
  and real-directory init remains byte-stable and idempotent. The complete
  safety-error, core, state, and API modules passed 18/18, 14/14, 12/12, and
  6/6. Both init crash matrices and the existing control/lock symlink
  hardening case passed.

### Step 7.5f — Reconcile cold-review and hosted-evidence claims — complete 2026-09-02

- Preserve the first cold review, the independent reproductions, each closure,
  and the final fresh re-review in
  [`research/FINAL_COLD_REVIEW.md`](research/FINAL_COLD_REVIEW.md).
- Replace stale claims that the `a2ae7793` hosted run is latest. Keep hosted
  evidence separated by exact revision and do not call the unpushed local tree
  hosted-validated until its own pushed SHA passes every required job.

Completion record:

- `research/FINAL_COLD_REVIEW.md` now preserves both no-go reviews, every
  independently reproduced defect and cause, completed remediation evidence,
  the successful Step 7.5i timing probe, and the six findings deliberately left
  for the next session.
- `PLAN.md`, `HANDOFF.md`, and the review record distinguish the current local
  checkpoint from blocking run 33278590221 and scheduled run 33638194991 at
  base revision `354d16bc662f15f65dded911d3c26729bf5804aa`. No current-tree
  result is described as hosted validation or a release verdict.
- The repository Markdown link audit and `git diff --check` passed during
  wrapup. This Step changes documentation only; it changes no executable,
  test, workflow, package-metadata, or preserved historical-evidence path.

### Step 7.5g — Complete create-only result recovery and symbolic-race refusal — complete 2026-09-02

- Preserve the established parent-interruption contract after separating
  object transfer from create-only ref publication. Recovery may publish an
  already-transferred exact candidate only through the same absent-ref
  compare-and-swap, then must recheck the worker before accepting it.
- Refuse a symbolic result ref even when it resolves to the exact candidate,
  including one planted during fetch or between the type and value checks.
  Preserve every direct or symbolic conflict and add regressions for recovery
  conflict, both symbolic-publication timing windows, and a result ref moved
  after the worker recheck but before final metadata.

Completion record:

- The restarted 246-test release suite passed 244 tests. One failure was a
  stale assertion: the new init parent validation refused a replaced canonical
  at the same pre-publication stage with the more precise `canonical marker
  directory is missing` cause. The other was a product regression: after the
  configured fetch child survived parent `SIGKILL` and returned zero, the
  candidate object existed in canonical but its not-yet-created result ref did
  not; recovery checked only the ref and reset the worker to `ready` instead
  of finishing the previously supported transition.
- Disposable races then planted a symbolic result ref during fetch and between
  the helper's first type check and exact-value lookup, pointing it at the
  exact candidate. Collection accepted each worker as `collected` while
  status reported `namespace-ref-symbolic`. The create-only helper had refused
  the symbolic write but treated its resolving to the candidate as a
  successful direct exact-ref race.
- A third disposable race moved the direct result ref after the second worker
  snapshot and before final metadata. Collection returned `collected` with a
  result ref at the wrong commit; status immediately reported
  `result-ref-missing` and `candidate-ref-retained`.
- Recovery now creates an absent result ref from an available recorded commit
  only with the all-zero expected old value, then uses the existing worker and
  summary validation. A direct conflict stays unchanged and resets collection
  to `ready`. Collection checks for a symbolic result both before transfer and
  after any failed create, and refuses it even when it resolves to the target.
  The exact-reuse path rechecks the ref type after resolving its value and
  after validating the object. The final metadata transaction rechecks that
  the result is direct and still names the candidate. Generic rollback text
  distinguishes a published ref from an object that may merely have
  transferred.
- The seven direct regressions passed 7/7. Complete affected modules passed:
  audit/recovery 27/27, parent interruption 6/6, allocation 19/19, and public
  safety errors 18/18.

### Step 7.5h — Refuse a symlink selected as the workspace — complete 2026-09-02

- Validate the lexically selected workspace path before resolving it. An
  existing symbolic link or non-directory at that exact path must be refused
  before initialization creates `.cws` or any other child through it.
- Add a regression proving a selected workspace symlink and its empty external
  target remain unchanged.

Completion record:

- A disposable pre-gate probe selected a symlink whose target was an empty
  external directory. Init accepted it, returned the resolved external target
  as the workspace, and created `.cws` there. The cause was that
  `init_workspace` resolved the selection before the Step 7.5e preflight, so
  the check observed only the target directory.
- Init now normalizes the selected path without following symlinks, validates
  that exact existing path, and resolves it only after the refusal boundary.
  The regression proves the link and external target remain unchanged. The
  complete public safety/error module passes 19/19; final Step 7.5 owns the
  complete release and campaign reruns.

### Step 7.5i — Lock result type, value, summary, and metadata finalization — complete 2026-09-02

- Finalize a collection without separate, raceable observations of a result
  ref's raw type and resolved value. Preserve a symbolic conflict even when it
  resolves to the candidate, and refuse a direct result move before collected
  metadata is committed.
- Use behavior available on the minimum supported Git. Add regressions at the
  raw-type/value boundary, after summary publication, and during the metadata
  write; apply the same locked contract to idempotent collection and recovery.

Completion record:

- The fresh re-review and two independent disposable probes showed that a
  symbolic result planted after the last type check but before its value check
  was accepted as `collected`, and that a direct result moved while the summary
  write began was accepted before collected metadata. `status` detected both
  only afterward. The cause was that raw type, resolved value, summary update,
  and record write ran in separate processes; the workspace lock does not lock
  Git refs.
- A normal `update-ref --stdin` transaction was insufficient: Git 2.43.0
  demonstrated that legacy `option no-deref` can prepare an object-ID verify
  against a symbolic ref and replace a symbolic summary resolving to the
  expected object. Clonegrown now leaves the transaction prepared, inspects
  both raw ref types while Git holds their locks, and only then commits or
  aborts. A second prepared verification holds both values stable across the
  collected-record write. Idempotent collection, interrupted-collection
  recovery, and summary repair use the same primitive.
- Three new transaction-window regressions passed 3/3. The complete
  audit/recovery module passed 30/30, parent interruption passed 6/6, and core
  and repository modules passed 14/14 and 8/8. The discovered suite now has
  254 tests; final Step 7.5 owns its complete rerun and exact-Git-2.29 proof.

### Step 7.5j — Put dangling symbolic clone refs in deletion custody

- Replace the `for-each-ref`-only clone-private-ref snapshot and deletion
  fingerprint with a raw ref inventory that includes dangling symbolic refs as
  names with symbolic targets. A change to any direct or symbolic private ref
  created before lease release must require `--discard-private-refs`; a
  post-authorization change must preserve quarantine rather than report
  deletion success.
- Begin with the independently reproduced
  `/tmp/clonegrown_probe_dangling_private_ref.py` case, then add a class
  regression covering unchanged, changed, added, and removed symbolic private
  refs without weakening the existing direct-ref and legacy-record cases.

### Step 7.5k — Reserve dangling symbolic task-branch names during allocation

- Before worktree publication, determine the generated task branch's raw type
  under the allocation transaction. Any pre-existing direct or symbolic name,
  including a symbolic ref whose target is absent, is occupied and must remain
  byte-for-byte untouched while spawn fails before publication.
- Reproduce from `/tmp/clonegrown_probe_dangling_task_branch.py` and add a class
  regression beside the existing direct-branch collision case. Include the
  branch reservation in allocation evidence so crash recovery cannot convert
  a collision into ownership.

### Step 7.5l — Treat dangling control-file paths as occupied before allocation

- Remove `Path.exists()` from lexical occupancy decisions for workspace state,
  request indexes, and worker records. A dangling symbolic link at any of those
  names is an existing unauthenticated object: init and spawn must refuse it
  without replacing it, consuming an ID, advancing `next_id`, or creating a
  worker.
- Use the three independent probes
  `/tmp/clonegrown_probe_dangling_workspace_state.py`,
  `/tmp/clonegrown_probe_dangling_request_index.py`, and
  `/tmp/clonegrown_probe_dangling_worker_record.py` as proofs, then cover the
  shared occupancy class at every atomic-write preflight.

### Step 7.5m — Preserve the selected workspace path through the CLI boundary

- Stop resolving `--workspace` in the CLI before `init_workspace` receives it.
  The lifecycle owns lexical validation followed by canonical resolution; the
  CLI and Python API must therefore refuse the same selected symlink and leave
  both it and its external target untouched.
- Reproduce `/tmp/clonegrown_probe_init_symlink.py` through the installed-style
  CLI and add a CLI regression without weakening the Step 7.5h API regression.

### Step 7.5n — Remove `GIT_CONFIG` from every child Git environment

- Add `GIT_CONFIG` to the exact Git-environment denylist used by all Clonegrown
  Git subprocesses. Confirm that removing it neither strips unrelated process
  environment nor changes configured canonical behavior.
- Reproduce `/tmp/clonegrown_probe_git_config_env.py`, add a sanitation class
  regression beside `GIT_CONFIG_COUNT`, and run spawn through an inherited
  hostile override to prove no Clonegrown Git command observes it.

### Step 7.5o — Reuse the stored rewrite policy for idempotent collection

- Once a worker is collected, validate an unchanged repeat against the durable
  `worker.allow_rewrite` policy accepted by the original collection rather than
  the new call's default argument. The repeat must remain a no-op and must not
  allow a different candidate, result, or summary.
- Reproduce `/tmp/clonegrown_probe_recollect_rewrite.py` and add a class
  regression combining an accepted rewrite with an immediate default repeat;
  retain the existing separate rewrite and ordinary-repeat coverage.

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

The historical closure mappings below remain inputs, not proof. Steps
7.5j–7.5o are open because the second fresh review disproved completeness in
six mapped classes. After those Steps, final Step 7.5 must independently prove
the entire map again against the then-current tree.

| Review item | Claimed closure |
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

### Release milestone

After Steps 7.3–7.5, CI, support boundaries, evidence, performance, packaging,
and public prose are release-quality. Product outreach or claims about agent
behavior happen only after this point.
