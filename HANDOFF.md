# Session handoff

Updated 2026-09-02 during `$wrapup` after the second Phase 7 cold review.
`PLAN.md` is the normative roadmap; `research/PLAN-ARCHIVE.md` preserves the
completed dated transcript that formerly made this file and the plan difficult
to use.

## Exact current state

- Work is on `main`. This handoff is part of the combined Phase 6–7 checkpoint
  being committed and pushed from base revision
  `354d16bc662f15f65dded911d3c26729bf5804aa`. The checkpoint deliberately
  preserves an incomplete Phase 7 and must not be treated as a release.
- Phases 1–6 and Phase 7 Steps 7.1–7.5i are complete in the checkpoint. The
  second fresh cold review returned a no-go with six independently reproduced
  in-contract defects. Remediation Steps 7.5j–7.5o and final Step 7.5 remain
  incomplete.
- Kyle authorized Apache License 2.0 and authorized completion of these
  refactor/rework phases without another `$next` or permission prompt unless
  genuinely required. Kyle then explicitly invoked `$wrapup` and asked to stop
  this session after documenting, committing, and pushing the checkpoint. The
  approved product boundary remains the end of Phase 7: do not begin outreach,
  comparative agent-behavior claims, or new product work.
- The tree has 43 recognized changed paths: 9 product modules; 23 tests and
  campaign paths, including 4 intentional deletions and 3 new paths; and 11
  documentation, research, licensing, or package-metadata paths. No dependency
  or workflow file is changed.
- No dotenv file has been opened, read, searched, printed, diffed, parsed, or
  sourced. Repository-wide searches and copies must continue to exclude
  `.env`, `*.env`, `.env.*`, and `*.env.*`.

## Changed boundary

Executable product changes are in:

- `clonegrown/__init__.py`
- `clonegrown/audit.py`
- `clonegrown/cli.py`
- `clonegrown/core.py`
- `clonegrown/lifecycle.py`
- `clonegrown/recovery.py`
- `clonegrown/repository.py`
- `clonegrown/state.py`
- `clonegrown/worker.py`

The cumulative Phase 6 implementation preserves promised auxiliary refs in
clone workers and removes redundant canonical verification while retaining
locked identity reconciliation. The Phase 7 remediation adds these observable
contracts:

- `discard(..., discard_private_refs=False)` and CLI
  `--discard-private-refs` separately authorize deletion of changed or
  unverified clone-private refs. New clone records carry
  `clone_private_refs`; non-ref `.git` state such as local config and hooks is
  explicitly outside that baseline. The current inventory correctly covers
  direct refs but misses dangling symbolic private refs; Step 7.5j owns that
  open defect.
- Collection transfers a candidate object without a destination ref and
  creates the immutable result only through an absent-ref compare-and-swap.
  Direct conflicts and all symbolic refs are preserved and refused. Prepared
  Git transactions hold result and summary locks while raw types are checked,
  commit the summary, and hold both values stable across collected metadata.
  Recovery can finish an object-only interrupted transfer through that same
  compare-and-swap and locked finalization.
- A normal `discarded` record must retain its result fields. Audit, request
  reuse, and recovery continue authenticating that terminal result custody.
- Live and dangling worker-slot symlinks are occupied unauthenticated paths,
  not absence.
- Init refuses symlinked or non-directory workspace-control and canonical
  marker parents before creating children or writing markers through them. The
  Python API also validates the exact selected workspace path before resolving
  it. The CLI currently defeats that check by resolving `--workspace` first;
  Step 7.5m owns that open adapter defect.

Test and campaign changes are:

- Modified:
  `tests/campaign/blocking_git.py`,
  `tests/campaign/hardening_suite.py`,
  `tests/campaign/real_repository_qualification.py`,
  `tests/campaign/state_machine_fuzz.py`,
  `tests/test_allocation.py`,
  `tests/test_audit.py`,
  `tests/test_campaign_records.py`,
  `tests/test_cli.py`,
  `tests/test_core.py`,
  `tests/test_discard_ignored.py`,
  `tests/test_lease.py`,
  `tests/test_parent_interruption.py`,
  `tests/test_quarantine.py`,
  `tests/test_safety_errors.py`,
  `tests/test_state.py`, and
  `tests/test_worktree.py`.
- New:
  `tests/campaign/auxiliary_ref_benchmark.py`,
  `tests/test_auxiliary_refs.py`, and
  `tests/test_package_metadata.py`.
- Deleted after deterministic replacements were proved:
  `tests/campaign/concurrency_v2.py`,
  `tests/campaign/io_fault_probe.py`,
  `tests/campaign/run_crash_case.py`, and
  `tests/campaign/shared_state_compare.py`.

Documentation, research, licensing, and metadata changes are:

- Modified: `README.md`, `SKILL.md`, `ARCHITECTURE.md`, `PLAN.md`, this file,
  `research/REPRODUCE.md`, and `pyproject.toml`.
- New: canonical Apache-2.0 `LICENSE`, the verbatim historical
  `research/PLAN-ARCHIVE.md`, qualitative
  `research/ORCHESTRATOR_SIMULATION.md`, and current-package
  `research/FINAL_COLD_REVIEW.md`.

There is no runtime dependency addition. The API adds one backward-compatible
optional discard argument. New records add one optional clone-only baseline;
legacy clone records fail closed before deletion. Normal terminal `discarded`
records now require the result fields that successful collection already
created. CLI output continues to hide internal baseline and token fields.

## Verified final-review findings

The first fresh cold review was a no-go. Disposable real-repository probes
independently reproduced five product defects before repair:

1. normal clone discard could silently lose a unique stash or another private
   ref;
2. collect could force-overwrite a conflicting exact result-ref name;
3. a discarded result could disappear without status, request-retry, or record
   validation refusing it;
4. a dangling worker-slot symlink could be treated as absence while discard
   recorded success; and
5. init could create children or markers through symlinked control parents.

Steps 7.5b–7.5e repair those classes. The restarted 246-test suite then passed
244 tests and exposed one stale expected error string plus one real product
regression: an object-only successful fetch child was reset to `ready` instead
of being completed by recovery. Inspection led to reproduced symbolic-ref
races during fetch and between the first type/value checks, followed by a
direct result-ref move between the worker recheck and final metadata. Step
7.5g closed those product gaps, updated the stale assertion, and corrected
rollback wording that had conflated transferred objects with published refs.

A subsequent disposable probe found that selecting the workspace itself as a
symlink still redirected initialization into the target because init resolved
the path before preflight. Step 7.5h validates the lexical selection first;
the link and empty external target now remain unchanged.

The fresh re-review then reproduced a symbolic result planted between final
type and value observations and a direct result moved while summary publication
began. Independent probes reproduced both. Step 7.5i replaces the separate
observations with prepared Git transactions that hold both ref locks while raw
types are inspected and across the collected-record write.

The second fresh cold review was also a no-go. Its full suite and both
hardening modes passed, but independent disposable probes established six
remaining blocker roots:

1. `/tmp/clonegrown_probe_dangling_private_ref.py` proved that a collected
   clone can lose a changed dangling symbolic private ref without
   `--discard-private-refs`. `for-each-ref` omits that ref from both the
   publication baseline and deletion fingerprint. Step 7.5j owns the raw
   direct/symbolic inventory and class regression.
2. `/tmp/clonegrown_probe_dangling_task_branch.py` proved worktree spawn can
   overwrite a dangling symbolic task-branch name. The create transaction has
   no raw symbolic-occupancy preflight and allocation evidence omits the
   generated branch. Step 7.5k owns this class.
3. The workspace-state, request-index, and worker-record probes proved one
   `Path.exists()` occupancy root: dangling control-file symlinks can be
   replaced, and spawn can consume an ID and advance `next_id` before refusal.
   Step 7.5l owns every atomic-write preflight in that class.
4. `/tmp/clonegrown_probe_init_symlink.py` proved the CLI resolves a selected
   workspace symlink before the Step 7.5h lifecycle check. It creates `.cws`
   in the external target and exits successfully. Step 7.5m owns CLI/API
   parity at the lexical boundary.
5. `/tmp/clonegrown_probe_git_config_env.py` proved `GIT_CONFIG` survives
   `clean_git_env()` and reaches child Git. Step 7.5n owns the exact denylist
   addition and end-to-end hostile-environment regression.
6. `/tmp/clonegrown_probe_recollect_rewrite.py` proved an unchanged repeat
   collection fails after an accepted history rewrite because it uses the new
   call's default `allow_rewrite=False` rather than stored
   `worker.allow_rewrite`. Step 7.5o owns durable-policy reuse.

The reviewer separately confirmed the Step 7.5i collection timing properties:
direct and symbolic conflicts stayed untouched, result and summary moves were
blocked while their locks were held, and object-only recovery used the exact
all-zero expected-old compare-and-swap. A late writer that continued after
lease release was reproduced but is not a defect under the documented
cooperative lease boundary. `research/FINAL_COLD_REVIEW.md` contains the full
review, cause, reproduction, coverage, and evidence record.

## Verification completed on the current tree

- Before the first cold review: 233/233 tests passed in 280.715 seconds;
  installer tests passed 25/25; package build and isolated wheel/source installs
  passed with Apache-2.0 metadata; clone and worktree hardening each reported
  56 exercised passes, one conditional reftable skip, and zero failures; two
  random-kill seeds per operation/mode and two 50-step state-machine seeds per
  mode passed.
- Step 7.5b affected gates: discard 14/14, quarantine 35/35, CLI 6/6, state
  12/12, plus the post-authorization ref race.
- Step 7.5c affected gates: audit 23/23, allocation 19/19, state 12/12, and all
  collection crash boundaries in both modes.
- Step 7.5d affected gates: quarantine 35/35, audit 23/23, allocation 19/19,
  plus dangling/live symlink and discard-crash cases in both modes.
- Step 7.5e affected gates: safety errors 18/18, core 14/14, state 12/12, API
  6/6, both init crash matrices, and the control/lock-symlink case.
- Step 7.5g direct regressions passed 7/7. Complete affected modules passed:
  audit/recovery 27/27, parent interruption 6/6, allocation 19/19, and safety
  errors 18/18.
- Step 7.5h's direct regression passed 1/1 and the complete safety/error module
  passed 19/19.
- Step 7.5i's three transaction-window regressions passed 3/3; audit/recovery,
  parent interruption, core, and repository modules passed 30/30, 6/6, 14/14,
  and 8/8.
- The coordinating exact-tree full suite passed 254/254 in 278.176 seconds.
  The second fresh reviewer independently repeated 254/254 in 295.072 seconds
  on Linux with CPython 3.12.3 and Git 2.43.0.
- Exact-tree hardening passed in both modes: clone and worktree each reported
  57 defined, 56 exercised passes, one conditional reftable skip, and zero
  failures. Result hashes were
  `1187f15cc753f88d2c9120f055f4fab37913afea885c65fc3cc8a604f149d83a`
  for clone and
  `b957a705996843646a098e284400a458b012cbe8c541a322c93fbe1e7cae0fd7`
  for worktree.
- All 12 bounded random-kill runs passed: two seeds for spawn, collect, and
  discard in both modes, every selected process was killed, and every return
  code was `-9`. Aggregate hashes were clone spawn
  `57bf2c478476eebd3f6f43bed5a766781c508d2dc506cc811a3030a34ed3385f`,
  collect
  `1fbcd860abba32188237321dc7a635b09d3c59ab77216f32bf8bcfdf81c7fa36`,
  discard
  `78eb4c325d09cc4ebb71c98288ca4fffd687a5dfad12c3ed4b4ac24f4e4f1b3b`,
  worktree spawn
  `126d6e6190d4e003c7ffcf201eee48e44176755ba36c3c365c1881a1651e4356`,
  collect
  `19f0ab4e0121c8647296ce63abbc395c34e6165464d63996ae1648d6a4cdef21`,
  and discard
  `42e9b15a4c11f897a8e5e703611445a971f01bda2198c9d52cbb6e5339979066`.
- Both 50-step state-machine seeds passed in both modes. Aggregate hashes were
  `29325a69c49bcc2fb33f3a25273f3153a0ef2f38bfdbfa932c2d52c57237afae`
  for clone and
  `26518aecc560308027389f49d86691a032d1f0c0c96597eef28d3e6530a1a7cc`
  for worktree.
- The exact-tree package gate passed during wrapup: source and wheel archives
  built, installed into isolated CPython 3.12.3 environments, both CLI/module
  entry points reported `0.1.0a1`, and `Apache-2.0`, `Requires-Python >=3.11`,
  public imports, and canonical license hash passed. Artifact hashes were
  wheel
  `4633ac18fd8ac3ad1965b381bd4d4cc265916c9db89d47a212b8c0d749b7ffb3`
  and source
  `2c3aae9f9c648b87235d5d49d0d470f0df16ec9e99284e3af108cc4c5339151f`.
- Shell syntax, CLI smoke, out-of-checkout Python parsing, the repository
  Markdown link audit, and `git diff --check` passed. These successes do not
  clear the six independently reproduced blockers.

## Hosted evidence boundary

GitHub Actions run 33278590221 passed all seven blocking jobs at committed
revision `354d16bc662f15f65dded911d3c26729bf5804aa`; scheduled randomized run
33638194991 later passed at that same revision. The executable tree there is
the Phase 5 tree from `a2ae7793`; the later commit changes completion records
only. Neither hosted run includes the local Phase 6–7 tree, so neither may be
used as its release proof.

The wrapup checkpoint is pushed to preserve the current work and no-go record;
its CI is not release evidence and need not be awaited before closing this
session. Release completion still requires a later repaired product revision,
all seven blocking jobs—including Ubuntu, macOS, exact Git 2.29.0, and both
hardening modes—and a recorded no-open-finding fresh review. Any final
evidence-only commit must itself be pushed and receive green blocking CI before
Phase 7 is called complete.

## Remaining exact sequence

1. Execute Step 7.5j: inventory dangling symbolic clone-private refs as raw
   names/targets and protect them at authorization and quarantine boundaries.
2. Execute Step 7.5k: reserve a generated task branch against any raw direct or
   symbolic occupant before worktree publication.
3. Execute Step 7.5l: treat dangling workspace-state, request-index, and worker
   record paths as occupied without consuming IDs or replacing paths.
4. Execute Step 7.5m: pass the selected workspace lexically through the CLI to
   the lifecycle check.
5. Execute Step 7.5n: remove `GIT_CONFIG` from every child Git environment.
6. Execute Step 7.5o: use the stored accepted rewrite policy for unchanged
   repeated collection.
7. For each Step, start from the recorded independent reproducer, add a class
   regression, run the smallest affected module, and do not stack an unproved
   change. Then restart all local release gates and exact Git 2.29.0 coverage.
8. Give a new fresh reviewer the original review bundle, both no-go records,
   and the coverage map but no implementation narrative. Release requires a
   no-open-finding verdict.
9. Push the repaired revision, wait for every blocking job on that exact SHA,
   record hosted evidence in a documentation-only commit, wait for that exact
   revision's CI, verify `main == origin/main`, and stop at Phase 7 completion.

## Preserved local residue

Ignored Python bytecode directories and `tests/campaign/hardening-results.json`
predate this qualification and are not session-owned. Do not remove them as
cleanup. Temporary probes and generated qualification artifacts created by the
current session live under `/tmp`; they are intentionally outside Git and were
left for the next session because they contain the independent reproductions
and exact package/campaign evidence needed to resume.

The remaining unsupported boundaries are native Windows, Git LFS, genuine
disk or inode exhaustion, and network or distributed filesystems. No current
evidence supports a claim that Clonegrown causes coding agents to make fewer
mistakes or require less human intervention than ordinary worktrees.
