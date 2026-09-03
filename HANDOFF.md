# Session handoff

Updated 2026-09-02 during final Step 7.5, after Steps 7.5j–7.5ae were executed by `$next`.
`PLAN.md` is the normative roadmap; `research/PLAN-ARCHIVE.md` preserves the
completed dated transcript.

## Exact current state

- Work is on `main`, uncommitted, on top of the pushed checkpoint
  `c9728a0` (Phase 6–7 checkpoint with the no-go record). Kyle's convention
  is to commit only at `$wrapup`.
- Phases 1–6 and Phase 7 Steps 7.1–7.5ae are complete in the working tree.
  The findings of the second (7.5j–7.5o), third (7.5p–7.5s), fourth
  (7.5t–7.5v), fifth (7.5w–7.5z), sixth (7.5aa), seventh (7.5ab), eighth (7.5ac),
  ninth (7.5ad), and tenth (7.5ae) fresh cold reviews are repaired, each
  starting from its recorded independent reproducer and closed with a class
  regression. Final Step 7.5's local part is complete: the eleventh fresh reviewer
  returned GO on this exact tree. What remains is commit, push, hosted CI on
  that SHA, and an evidence-only commit.
- Kyle authorized completion of these refactor/rework phases without another
  `$next` or permission prompt unless genuinely required. The approved product
  boundary remains the end of Phase 7: do not begin outreach, comparative
  agent-behavior claims, or new product work.
- No dotenv file has been opened, read, searched, printed, diffed, parsed, or
  sourced. Repository-wide searches and copies must continue to exclude
  `.env`, `*.env`, `.env.*`, and `*.env.*`.

## What this session changed

Product modules: `clonegrown/core.py`, `clonegrown/cli.py`,
`clonegrown/lifecycle.py`, `clonegrown/repository.py`, `clonegrown/state.py`,
`clonegrown/worker.py`.

- **7.5j** `worker.raw_ref_inventory` unions `for-each-ref` with a
  symlink-free walk of the loose ref files, so a dangling symbolic ref is
  recorded as `symref:<target>`. The publication baseline and the quarantine
  custody fingerprint both use it. A repository whose `extensions.refstorage`
  is not `files` has no raw walk and fails closed like a legacy record.
- **7.5k** `repository.create_task_branch` is a prepared transaction that
  reads both names' raw types under the locks and aborts on any symbolic
  occupant. `allocation_evidence` lists a direct or symbolic occupant of the
  generated branch as evidence for worktree spawns. The transaction helper now
  carries Git's redacted stderr when `prepare` is refused.
- **7.5l** Workspace-state, request-index, and worker-record occupancy uses
  `os.path.lexists`; `core.atomic_json` preflights its destination with
  `refuse_unowned_occupant`; `require_worker` refuses a non-regular record
  before any lock file exists.
- **7.5m** The CLI passes `--workspace` to `init_workspace` lexically
  (`expanduser()` only).
- **7.5n** `GIT_CONFIG` is in `GIT_ENV_EXACT`.
- **7.5o** The collected branch of `collect` snapshots with the recorded
  `worker.allow_rewrite`.
- **7.5p** `clean_git_env` strips every `GIT_*` name except the six
  author/committer identity variables (`git_env_is_stripped`), still strips
  `SSH_ASKPASS`, and forces `GIT_TERMINAL_PROMPT=0`.
- **7.5q** `_reauthorize_quarantined` takes `discard_ignored`, enumerates
  ignored paths on the quarantined checkout for a normal discard, and fails
  closed when Git cannot read it.
- **7.5r** `raw_ref_inventory` lives in `repository.py`, walks `refs/` with
  `dir_fd`-relative `O_NOFOLLOW` opens (optionally anchored on the held
  canonical descriptor), and feeds `NamespaceRefs` (with a `malformed` list
  and per-worker attribution of symbolic reports) and the worker-ref
  allocation evidence.
- **7.5s** Public docs corrected; `research/FINAL_COLD_REVIEW.md` now records
  the third review verbatim.
- **7.5t** `repository.is_ancestor` judges ancestry with `--no-replace-objects`
  and `GIT_GRAFT_FILE=/dev/null` (via a new `env_extra` argument on the
  sanitized Git runner); `snapshot_worker` uses it and `collect` re-judges on
  canonical after the fetch.
- **7.5u** `repository.loose_ref_occupant` and `is_foreign_ref`; every
  write-path symbolic check uses `is_foreign_ref`; allocation evidence lists
  any raw inventory entry at the base-pin or task-branch name.
- **7.5v** Notices and architecture wording updated; fourth review recorded
  verbatim in `research/FINAL_COLD_REVIEW.md`.
- **7.5w** `_recover_collecting` requires canonical-side `is_ancestor` before
  finishing; `status` reports canonical-view drift for collected records.
- **7.5x** `is_foreign_ref` and `resolve_ref` `lstat` first; allocation
  evidence `lstat`-inspects the base-pin and task-branch names.
- **7.5y** `_release_task_branch` / `release_task_branch` retain a foreign
  branch-name occupant; new `task-branch-foreign` status code.
- **7.5z** Wording; fifth review recorded verbatim.
- **7.5aa** `resolve_ref`/`ref_points_at`/`result_ref_transaction` and the
  collected-repeat `collect` path inspect before Git; `verify_worker`
  refuses a worktree worker with a foreign branch name; audit reporting
  precision; sixth review recorded verbatim.
- **7.5ab** Result preservation rechecked at resumed and re-authorized
  deletion; `require_plain_worktree_heads` before worktree commands and the
  collect fetch; `ENOTDIR` as a foreign occupant; audit codes and ids;
  seventh review recorded verbatim.
- **7.5ac** Component-aware `loose_ref_occupant`; `loose_symbolic_target`;
  `ForeignWorktreeHead` re-raised by recovery; preflight before clone-mode
  spawn's clone; prefixed namespace inventory; eighth review recorded.
- **7.5ad** Raw-first inventory that skips Git when a symbolic chain ends
  foreign; chain-aware `resolve_ref`/`ref_points_at`; `ref_prefixes` walked
  before every worktree command, the fetch, and the clone; admin `gitdir`
  inspected; `collected-result-restored` / `collected-result-missing`
  instead of `broken`; ninth review recorded.
- **7.5ae** `is_symbolic_ref` raw-first with `--no-recurse`; regular-file
  pointer reads; `packed-refs` read raw when enumeration is skipped; wording;
  tenth review recorded.

Tests: modified `tests/test_allocation.py`, `tests/test_audit.py`,
`tests/test_cli.py`, `tests/test_core.py`, `tests/test_discard_ignored.py`,
`tests/test_quarantine.py`, `tests/test_safety_errors.py`,
`tests/test_worktree.py`; new `tests/test_collect_policy.py`. The direct
branch-collision expectation in `test_worktree.py` was tightened to the
earlier pre-allocation refusal (no worker record is created any more).

Documentation: `README.md`, `SKILL.md`, `ARCHITECTURE.md`, `PLAN.md`, and this
file describe the repaired behavior and a qualification that is pending.
`research/FINAL_COLD_REVIEW.md` gained the third review's record and verbatim
report; it is the record every later fresh reviewer receives.

No dependency, workflow, installer, or package-metadata file changed. The
public API and CLI surface are unchanged; the only new error texts are the
refusals recorded in `PLAN.md`.

## Verification on the current tree

All results below come from the final tree (Steps 7.5j–7.5ae applied), on
Linux with CPython 3.12.3 and Git 2.43.0.

- Full discovered unit suite: 294/294 passed in 389.573 seconds.
- Clone and worktree hardening each reported 57 defined, 56 exercised passes,
  one conditional reftable skip (this Git lacks reftable), and zero failures.
  Result hashes were `3f8800b4cc47d5d66de10fdffe1e2a3e61d4d997c282e4dc63bbcfd554e8a3bc`
  for clone and `6ac4e9f2ccbe7112071241c5bccfa3cfd98b0112fe1f1b537a31556d7542eb66` for worktree.
- All 12 bounded random-kill runs passed: two seeds each for spawn, collect,
  and discard in both modes; every selected process was killed and every
  return code was `-9`. Result hashes were clone spawn
  `70e97b32d5de8e5a2cc6b32369d379a4a5ea94b24db72ce0fccb39516781dcdd`, collect
  `4b2facc801283619b1020139ae3a7e10015a21f97f885a7fec580aea66d2b677`, discard
  `8714d4c4f01ba7a8ef54db0ea0147f432e6b1bb50fb36a40d91243584730cc2d`, worktree spawn
  `33544b71efb48af1eb52e33122575294f4b0f40394a89956b2f8041552756b1d`, collect
  `6e66be838aba3da6b2982e12f9974ddae6c7eb457e4a77ac9ee57ad71a25348e`, and discard
  `38faa4b492ce3a7b595051b2fbe29cdd353101f0e49c3cb7c1e3762b7af0632d`.
- Both 50-step state-machine seeds passed in both modes. Result hashes were
  `120e798f8cb0bc36ef1bb6904d8ae3ec7524d4803c672f0803b84ff44dc02b12` for clone and
  `00fd6a2b19168cf7005276197006570d711f1003a1a848cb4e030f20b0456fed` for worktree.
- Package gate: wheel and source archives built with an isolated `build`
  toolchain and installed into two fresh venvs; both entry points report
  `0.1.0a1`; `Apache-2.0`, `Requires-Python >=3.11`, the public import, and
  the canonical license hash
  `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` passed.
  Artifact hashes: wheel
  `95b3d689be30ecaa4d4b6d6baa7f6e9fc38f6ccd8b9a39ad50baf402568ad4fc`, source
  `9c858efd8c1e8b8e753dabf0202267fab8616be03e0f579a8ed1e5c313492927`.
- `python -m compileall`, `sh -n install.sh`, `git diff --check`, and the
  repository Markdown link audit (33 links and anchors) passed.

## Verification recorded after Steps 7.5j–7.5o (superseded by the section above)

Every module gate for each Step passed as recorded in `PLAN.md`
(discard-ignored 16/16, quarantine race 1/1, worktree 26/26, allocation 20/20,
repository 8/8, safety errors 21/21, state 12/12, core 15/15, CLI 7/7,
collect policy 3/3). All nine `/tmp` probes were rerun before and after each
change: each reproduced the defect on the checkpoint tree and each now shows
the required refusal or success.

Whole-tree gates on the repaired tree:

- Full discovered unit suite: 266/266 passed in 568.861 seconds on the
  final tree (Linux, CPython 3.12.3, Git 2.43.0). An earlier whole-tree run
  had failed two Step 7.5i transaction-window tests because the 7.5k
  transaction-helper change relabeled the prepare-refusal error; the label was
  restored to `git update-ref transaction` and the suite rerun in full.
- Hardening and campaigns: see "Local gate results" below.
- Package gate: wheel and source archives built (isolated `build` toolchain),
  installed into two fresh CPython 3.12.3 venvs; both CLI and module entry
  points report `0.1.0a1`; `Apache-2.0`, `Requires-Python >=3.11`, public
  imports, and the canonical license hash
  `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` passed.
  Artifact hashes: wheel
  `0d13f802b45b044844bb079835bb3a03186dc931e656e27749d5a0c1c87dafc6`, source
  `e6574d9432347a5ff6dc1ef73687415816d3776f03e77cfcc2fdef8243e8114f`.
- `python -m compileall`, `sh -n install.sh`, `git diff --check`, and the
  repository Markdown link audit (33 links and anchors) passed.

## Local gate results

All results below come from the final tree, after the full 266/266 suite.

- Clone and worktree hardening each reported 57 defined, 56 exercised passes,
  one conditional reftable skip (this Git 2.43.0 lacks reftable), and zero
  failures. Result hashes were `789d37c0bb851bf112d0e546a204c07eb7f3317297ce065c533139debca22f85`
  for clone and `fbee03118148b28184aac5a21937a87c3187161618967b3b27765ce3a6d762c5` for worktree.
- All 12 bounded random-kill runs passed: two seeds each for spawn, collect,
  and discard in both modes; every selected process was killed and every
  return code was `-9`. Result hashes were clone spawn
  `2778ec1fbcd35ff47bed54bb281f4dedca422a1bb04e7fabf79a1e0c4dcee67a`, collect
  `1fb782b9e4466793f806a6b71914bec0c6c34f7f429488ff3442439d45e71291`, discard
  `8c5422843c0390ee392cc6887e590db8e1456129ef62a3740565f8c49f45cd85`, worktree spawn
  `67a19415c54e92c6e0e021762a8779acd3063331168f100d3da749625502e3ed`, collect
  `ab53b647f8c9869f6a831a0beb1861b76f30a220afb394b8613efc505e0440bd`, and discard
  `9800e854f9b3b5782558b161ec9057e3cd3629c9b35e88fbc21454d4d09bdfd1`.
- Both 50-step state-machine seeds passed in both modes. Result hashes were
  `9486ba4b8dd5d3879d6f1a6f494dedbb30855ee667018f23295b04c5e18c99f4` for clone and
  `ee43c36d29372ba7b32a73781611fb738bdd43b6345d843f38d405cd43ef7462` for worktree.
- An earlier identical hardening and campaign pass on the tree before the
  error-label correction also passed everywhere (56/56 per mode, 12/12
  random-kill, 4/4 state-machine); it is superseded by the runs above.

## Hosted evidence boundary

GitHub Actions has run only on `354d16bc` (Phase 5 executable tree) and the
`c9728a0` checkpoint. Neither is release evidence for this tree. Release
completion still requires pushing the repaired revision, all seven blocking
jobs on that exact SHA (Ubuntu, macOS, exact Git 2.29.0, both hardening
modes), and a recorded no-open-finding fresh review.

## Remaining exact sequence

1. Commit and push the reviewed tree; wait for every blocking job on that
   SHA; record hosted evidence in a documentation-only commit; wait for that
   revision's CI; verify `main == origin/main`; stop at Phase 7 completion.

## Preserved local residue

Ignored Python bytecode directories and `tests/campaign/hardening-results.json`
predate this qualification and are not session-owned. The nine
`/tmp/clonegrown_probe_*.py` reproducers and the earlier `/tmp/clonegrown-*`
qualification artifacts are intentionally outside Git. This session's gate
outputs live under the session scratchpad and are not needed to resume.

The remaining unsupported boundaries are native Windows, Git LFS, genuine
disk or inode exhaustion, and network or distributed filesystems. No current
evidence supports a claim that Clonegrown causes coding agents to make fewer
mistakes or require less human intervention than ordinary worktrees.
