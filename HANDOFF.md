# Session handoff

Written 2026-08-28 (updated after Phase 4 Step 4.5). This handoff becomes stale
when Phase 5 Step 5.1 is completed, `PLAN.md` changes the next unfinished
Step, or this checkout moves away from `main`.

## Exact stop point

- Work is on `main`, tracking `origin/main`. Phases 1 through 3 are committed
  through `7b9b57e`; the Phase 4 Steps 4.1 through 4.5 implementation, tests,
  roadmap, architecture, README, and installed-skill guidance are committed as
  `3b2914f` (`Complete Phase 4 Git semantics and safe errors`). The only later
  change is this post-commit handoff synchronization.
- Phase 1 (Steps 1.1 through 1.13) is complete and closed by the Step 1.13
  fresh review, which found no open Phase 1 finding.
- Phase 2 Step 2.1 is complete: `WorkerRecord.validate` is the one
  table-driven validator, with the lease and quarantine fields reserved and
  validated but not yet set by any command.
- Phase 2 Step 2.2 is complete: workers are leased from spawn, `release`
  and `claim` exist in the API and CLI, discard and recovery deletion require
  a released lease, and a collected worker is one-shot.
- Phase 2 Step 2.3 is complete: discard of a collected worker enumerates
  ignored paths by name and requires `--discard-ignored`.
- Phase 2 Step 2.4 is complete: worktree task branches carry a private
  ownership ref created with them in one transaction and are deleted only by
  a verifying transaction; admin-directory removal is error-checked and
  absence-verified; conflicts retain evidence and are reported.
- Phase 2 Step 2.5 is complete: discard fingerprints, quarantines,
  rechecks, deletes with errors enabled, proves absence, and records a
  terminal status only when everything is clean; recovery resumes
  quarantines and never labels residue gone.
- Phase 2 Step 2.6 is complete: a diverged published spawn is preserved as
  `broken` with a content-free description; the worktree add/persist window
  is closed by gitdir-based ownership.
- Phase 2 (Steps 2.1 through 2.7) is complete and closed by the Step 2.7
  cold review; its six confirmed defects were fixed and re-reviewed in the
  same pass (details under Step 2.7 in `PLAN.md`). A Phase 2 bughunt then
  found and fixed eight more (checked-out branch deletion, three stuck
  cleanup states, Unicode-digit and non-UTF-8 path crashes, validator bypass,
  fingerprint blind spots); its record follows Step 2.7 in `PLAN.md`.
- Phase 3 (Steps 3.1 through 3.5) is complete and closed by the Step 3.5
  cold review: create-only allocation, validated request indexes, a
  non-mutating `status` audit with stable issue codes, and ownership-scoped
  `recover` reconciliation; its five review findings were fixed in the same
  pass (records under Phase 3 in `PLAN.md`). A Phase 3 bughunt then found
  and fixed eight more, chiefly namespace writes that followed symbolic refs
  onto canonical's own branches; its record follows Step 3.5 in `PLAN.md`.
- Phase 4 Step 4.1 is complete: every Git path uses the sanitized environment,
  command failures are structured and publicly redacted, copied config values
  and remote URLs are marked sensitive at their write/use sites, and the raw
  diagnostics remain in-memory only.
- Phase 4 Step 4.2 is complete: an immutable validated plan preserves config
  value form and occurrence order, include-effective values are flattened,
  relative local fetch/push paths are anchored to canonical, read failures are
  errors, and one redacted imperative stage applies and verifies the plan.
- Phase 4 Step 4.3 is complete: CLI and API both default to non-strong clones,
  Git validates the complete generated branch before allocation mutation,
  valid sanitizer output is pinned across edge cases, and the unused public
  `CWSError` alias is gone without renaming the durable `cws` protocol.
- Phase 4 Step 4.4 is complete: init/spawn/collect/discard/recover translate
  ordinary failures with exact operation stage, last known durable mutation,
  work-preservation confidence, recovery action, and a chained cause;
  process-control exceptions pass through and recovery-worker failures report
  the same safety fields while continuing other workers.
- Phase 4 Step 4.5 is complete: its fresh cold reviews proved and fixed ten
  defects across Git environment isolation, redaction, pre-mutation plan
  validation, process-control rollback, CLI launch/input errors, and recovery
  continuation. Fresh confirmation reviews found no open issue after the last
  fixes, and Phase 4 is closed.
- The next `$next` pass is **Phase 5 Step 5.1 — Make concurrency correctness
  deterministic and benchmarking nonblocking**; follow its exact scope in
  `PLAN.md`.

## Completed through this stop point

- Steps 1.1 through 1.11 as recorded in `PLAN.md`.
- Step 1.12 bound backup relocation to token-bearing reservations and to
  identity plus ownership evidence for every deletion and restoration path.
  A bughunt against that working tree found and fixed seven installer defects
  (non-UTF-8 paths under a UTF-8 locale, identity-only trust defeated by inode
  reuse, a false rollback message, a locale-dependent test, three disagreeing
  ownership predicates, a FIFO blocking the installer, and updates failing
  under a non-UTF-8 source path), each with a regression and three cold-review
  rounds; details are under Step 1.12 in `PLAN.md`.
- Step 1.13's fresh review closed Phase 1; its two low notes were fixed in the
  same pass (`SIGPIPE` trapped with a regression; README and architecture now
  say a caught signal after commit can leave authenticated backups).
- Phase 4 Step 4.1 separated generic command execution from the always-clean
  Git runner, introduced `CommandFailure`, moved clone provisioning onto that
  Git path, marked copied config/remote values sensitive, added nine focused
  regressions, and synchronized README, installed skill, and architecture.
- Phase 4 Step 4.2 replaced the grouped remote/config copy helpers with a pure
  `CloneConfigPlan` plus one validated apply stage, preserved valueless versus
  empty and exact occurrence order, canonicalized relocated relative remote
  paths, made config reads fail closed, added four focused regressions, and
  documented the complete minimum clone-fidelity boundary.
- Phase 4 Step 4.3 aligned Python's spawn default with the CLI, moved complete
  branch validation ahead of every durable allocation write, retained all
  valid deterministic branch names and explicit isolation behavior, removed
  the unused `CWSError` export, added six focused regressions, and synchronized
  the Python examples and architecture.
- Phase 4 Step 4.4 added call-local public-operation safety checkpoints around
  every represented mutation boundary, chained low-level causes without
  catching process control, extended per-worker recovery-failure reports,
  added eight focused custody/error regressions, and synchronized README,
  installed-skill guidance, and architecture. Its full-suite pass diagnosed
  and corrected one message-bound compatibility regression before rerunning
  clean.
- Phase 4 Step 4.5 stripped two replacement-ref environment controls; added
  structured process-launch failures; validated remote names and Git config
  grammar before staged-clone mutation; kept leading-dash remotes literal;
  made short-value and internal custody-token redaction diagnostic-preserving;
  kept all process-control exceptions out of rollback; put CLI-only resolution
  inside operation context; and made recovery continue across unrenderable
  exceptions and worker lock/setup failures. Thirteen new unit tests cover the
  added classes. The first full run caught the over-broad successful-string
  redaction hiding `status.quarantine_path`; the exact cause was corrected and
  both the status contract and real quoted-error redaction were freshly
  re-reviewed.

## Verified close state

- `python3 -m unittest discover -s tests -f`: 187 tests passed in 230.779
  seconds.
- `python3 -m unittest discover -s tests -p 'test_safety_errors.py' -v`: 14
  focused public-error/custody tests passed.
- `python3 -m unittest discover -s tests -p 'test_api.py' -v`: 6 focused
  API/default/branch-validation tests passed.
- `python3 -m unittest discover -s tests -p 'test_core.py' -v`: 12 focused
  command-runner/redaction tests passed.
- `python3 -m unittest discover -s tests -p 'test_repository.py' -v`: 8 focused
  clone-plan/fidelity tests passed.
- `python3 -m unittest discover -s tests -p 'test_cli.py' -v`: 4 focused CLI
  contract tests passed.
- Complete hardening campaign: 56/56 clone and 56/56 worktree; generated
  results stayed under `/tmp`.
- Retired alias/stale-default and remote/config-helper searches,
  out-of-checkout byte compilation, trailing-whitespace search, and
  `git diff --check`: passed.
- No session-owned Python, Git, shell, or reviewer process remains running.
- No pending user ruling or manual action blocks Phase 5 Step 5.1.
