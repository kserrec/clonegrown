# Session handoff

Written 2026-08-28 (updated 2026-08-29 after the Phase 5 Step 5.7 hosted
completion gate). This handoff becomes stale when `PLAN.md` changes the next
unfinished Step or this checkout moves away from `main`.

## Exact stop point

- Work is on `main` at `a2ae7793b5a3653435fde988f716558f74ce6b88`, tracking
  the same revision on `origin/main`. Phases 1 through 5 are complete. Commit
  `a2ae779` published the exact 24-path combined Phase 5 tree; hosted
  deterministic CI and the randomized artifact/replay gate passed. Only
  `PLAN.md` and this handoff are now modified locally to record that hosted
  completion; no executable, test, workflow, or research artifact changed
  after the published commit.
  Step 5.1 changed `tests/campaign/hardening_suite.py`, created
  `tests/campaign/spawn_benchmark.py` and
  `.github/workflows/spawn-benchmark.yml`, and changed
  `research/REPRODUCE.md`, `PLAN.md`, and this handoff. Step 5.2 changed
  `clonegrown/lifecycle.py`, `clonegrown/worker.py`,
  `tests/campaign/hardening_suite.py`, `tests/test_quarantine.py`,
  `ARCHITECTURE.md`, `research/REPRODUCE.md`, `PLAN.md`, and this handoff, and
  created `tests/campaign/blocking_git.py` and
  `tests/test_parent_interruption.py`. Step 5.3 changed
  `tests/campaign/random_kill.py`, `tests/campaign/state_machine_fuzz.py`,
  `ARCHITECTURE.md`, `research/REPRODUCE.md`, `PLAN.md`, and this handoff, and
  created `.github/workflows/randomized-campaigns.yml`,
  `tests/campaign/campaign_record.py`, and `tests/test_campaign_records.py`.
  Step 5.4 changed `.github/workflows/ci.yml`, `clonegrown/lifecycle.py`,
  `clonegrown/repository.py`, `tests/campaign/hardening_suite.py`,
  `tests/test_parent_interruption.py`, `README.md`, `ARCHITECTURE.md`,
  `research/REPRODUCE.md`, `PLAN.md`, and this handoff. It created no product
  file. Step 5.5 created `tests/test_filters_and_resources.py` and changed
  `README.md`, `ARCHITECTURE.md`, `research/REPRODUCE.md`, `PLAN.md`, and this
  handoff. It changed no product or workflow file. The working tree was clean
  before Step 5.1. Step 5.6 created
  `tests/campaign/real_repository_qualification.py`,
  `research/REAL_REPOSITORY_QUALIFICATION.json`, and
  `research/REAL_REPOSITORY_QUALIFICATION.md`; it changed
  `research/REPRODUCE.md`, `PLAN.md`, and this handoff, and changed no product
  or workflow file. All 24 committed paths belong to the combined Steps.
  Step 5.7 changed `.github/workflows/ci.yml`,
  `.github/workflows/randomized-campaigns.yml`, `README.md`, `ARCHITECTURE.md`,
  `research/REPRODUCE.md`, `PLAN.md`, this handoff,
  `tests/campaign/campaign_record.py`, `tests/campaign/hardening_suite.py`,
  `tests/campaign/random_kill.py`, `tests/campaign/state_machine_fuzz.py`, and
  `tests/test_campaign_records.py`. It created no path and changed no
  `clonegrown/` product file, so the combined Phase 5 commit contains exactly
  24 paths.
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
- Phase 5 Step 5.1 is complete: the eight-way hardening case is now purely
  deterministic and audits allocation, no-overwrite, request-index, counter,
  and public-status integrity; raw multi-sample spawn timings live in a
  separate weekly/manual, nonblocking benchmark for both worker modes.
- Phase 5 Step 5.2 is complete: six real-process tests kill only the Python
  parent while a configured Git child remains alive, inspect child exit and
  filesystem/ref/record state before recovery, and cover provisioning, fetch,
  worktree add/repair, and cleanup; lease and cleanup failpoint matrices are
  complete. The probes found no product failure, so executable changes are
  limited to four inactive-by-default test boundaries.
- Phase 5 Step 5.3 is complete: eight nightly/manual, bounded randomized jobs
  cover three SIGKILL operations and state-machine sequences in both worker
  modes. Every artifact records environment/commit provenance and an exact
  one-seed replay command; failures remain job failures while their JSON is
  retained from runner-temporary storage.
- Phase 5 Step 5.4 is complete: blocking unit/destructive CI is configured for
  Linux and macOS at the Python 3.11 and latest-stable endpoints; exact Git
  2.29.0 is derived, documented, built, and locally proven; Git 2.29 linked
  worktrees now receive explicit worktree-local sparse flags before checkout;
  and native Windows remains explicitly unsupported.
- Phase 5 Step 5.5 is complete: a real external clean/smudge driver passes the
  full lifecycle in both worker modes; deterministic no-space, rename-refusal,
  and partial-deletion injections pin the represented recovery transitions;
  Git LFS, genuine exhaustion, and network/distributed filesystems remain
  explicitly unsupported; and no product code or dependency changed.
- Phase 5 Step 5.6 is complete: six pinned-public-source scenarios passed
  across history-heavy, ref-heavy, and sparse/submodule profiles in clone and
  worktree modes; the exact machine record and bounded interpretation are
  preserved under `research/`, and no product code, workflow, protocol, or
  dependency changed.
- Phase 5 Step 5.7 is complete. Its local cold review confirmed and repaired
  seven test/workflow weaknesses: missed-SIGKILL false greens, untested artifact
  wiring/allowlisting, swallowed corrupt records, skip-as-pass accounting,
  campaign/product Git-selection disagreement, no early durable artifact, and
  cancellable hardening evidence. A post-repair review then found and repaired
  nonzero-child false greens, three missing end-to-end assertions, inaccurate
  timeout arithmetic, and absent hardening-result uploads. Fifteen focused
  tests and all current local gates pass. No product file changed in this Step.
  Commit `a2ae779` published the combined Phase 5 tree; hosted CI run
  33276649643 passed all seven jobs, and randomized run 33277111128 passed all
  eight jobs. All eight retained artifacts validated, and one row from each
  replayed literally and passed.
- The next `$next` pass is **Phase 6 Step 6.1 — delete the legacy test surface**.
  No Phase 6 work has started.

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
- Phase 5 Step 5.1 removed the one-sample `ratio < 8.0` assertion from
  correctness instead of loosening it. `parallel_spawns_unique` now requires
  IDs 1–8, exactly eight non-overwritten records, matching request indexes,
  `next_id == 9`, and a clean `status` audit. The new benchmark records five
  fresh single/parallel samples per mode with raw rows, medians, median absolute
  deviation, minimum, and maximum; timing never changes its exit status. The
  new workflow has only weekly/manual triggers, and reproduction guidance
  keeps generated JSON outside the checkout. No `clonegrown/` code changed.
- Phase 5 Step 5.2 first proved all six parent-only interruption windows with
  temporary `/tmp` probes against the unchanged lifecycle implementation, so
  no product fix was needed. The committed regressions use a blocking
  configured-Git helper, prove the direct child remains alive across parent
  `SIGKILL`, require its successful exit, inspect the exact pre-recovery
  residue, and then verify clean recovery. Four failpoints expose the post-save
  claim/release transitions and the post-administration/post-branch cleanup
  phases to the matrices without changing normal behavior. The hardening suite
  is now 57 cases; clone discard covers six boundaries and worktree discard
  covers eight.
- Phase 5 Step 5.3 added no product behavior. A shared campaign-record helper
  adds Python/Git/platform/commit and allowlisted GitHub provenance plus
  validated one-seed replay commands to random-kill and state-machine output.
  The nightly/manual workflow runs six random-kill and two state-machine jobs,
  uses finite seed-count/step choices and 45-minute job bounds, disables matrix
  fail-fast without permitting campaign errors, and configures always-run
  uploads with 30-day retention. Job cancellation or runner loss can still
  prevent an upload. PR CI and the informational benchmark are unchanged. The
  published workflow and all eight hosted artifacts passed the Step 5.7 gate.
- Phase 5 Step 5.4 changed one product compatibility path after direct
  minimum-version evidence. Git 2.29 copied the sparse pattern file for a
  linked worker but did not copy the main worktree's worktree-local sparse
  flags, so an excluded path was materialized. `copy_sparse_policy` now writes
  the effective flags through `git config --worktree` before checkout when
  `extensions.worktreeConfig` is enabled; shared-config worktrees and clone
  behavior remain intact. The CI endpoint matrix adds latest-stable Python to
  both Linux and macOS, and an exact-minimum job builds the digest-pinned Git
  2.29.0 archive and runs the full unit plus both hardening modes with the
  binary selected through `PATH` and `CLONEGROWN_GIT`. Hosted CI run
  33276649643 passed the expanded Phase 5 matrix. A separate Git 2.29
  probe proved the unchanged shared-config worktree branch still inherits
  sparse flags and excludes the omitted path.
- Phase 5 Step 5.5 added four blocking tests and no product behavior. The real
  filter fixture proves clean storage, smudged checkout, clean worker staging,
  collection, and disposal in clone and worktree modes while requiring its
  external driver to exist independently. Fault injection proves atomic
  create/replace behavior before publication under `ENOSPC`, intact custody
  and intent withdrawal after an `EXDEV` quarantine-rename refusal, and
  recoverable authorized residue after an `EIO` follows one recursive deletion.
  Git LFS was absent locally and remains unsupported; adding its roughly
  5.6–6.2 MB compressed platform binary plus hook, credential, network-transfer,
  update, and advisory surface was rejected for this narrower task. Genuine
  disk/inode exhaustion and network/distributed filesystems remain unvalidated
  and unsupported.
- Phase 5 Step 5.6 added no product or workflow behavior. Its standard-library
  harness deferred every public checkout until sparse rules excluded all
  dotenv filename variants, then exercised curl/curl at
  `8a2bb9ca241bbd82a0da536f6f39dca9037dd046` and git/git at
  `c73e85354c275c9d409b26445089bc16940fc527`. The three roles measured 39,564
  curl `HEAD` commits, 1,019 Git refs including 1,008 tags, and a narrow Git
  checkout retaining `.gitmodules`, `Documentation/git.adoc`, and the
  uninitialized mode-`160000` `sha1collisiondetection` gitlink while excluding
  `Makefile`. Every clone/worktree scenario recovered an intentional
  post-publication interruption, collected and retained a new result, removed
  the released worker, finished with no audit issue, and passed a connectivity
  check. The JSON identifies the exact uncommitted package tree and harness,
  not only committed `HEAD`, and the narrative states the matrix's limits.
- Phase 5 Step 5.7 first reproduced its findings without editing product code:
  spawn seed 0 in both modes and a fresh seed-2 probe falsely passed with
  `killed: false, rc: 0`; helper-only tests survived environment-leak and
  missing-replay mutations; corrupt numeric worker JSON disappeared from the
  state-machine invariant; reftable skips were counted as passes; and campaign
  setup/provenance could disagree with Clonegrown's selected Git. Campaign
  output also did not exist until the seed loop ended. The repaired harnesses
  require actual `SIGKILL`, use the product-selected Git, prewrite and
  atomically update provenance plus every requested replay row, preserve
  pending status after interruption, and bound state-machine subprocesses.
  The invariant now requires a clean public audit and exact record agreement;
  hardening reports skips separately, rejects nonzero children, and uploads
  each structured mode result. Randomized checkout, Python setup, execution,
  and upload have 5/5/25/5-minute limits inside a 45-minute job, leaving five
  minutes for between-step overhead without promising survival after runner
  loss. A second fresh review found no current implementation/workflow defect,
  but proved that tests did not yet bind timeout values to their owning steps,
  require randomized matrix `fail-fast: false`, or reject permissive `|| true`
  masking. Those assertions are now explicit. A terminal fresh review then
  found no current implementation/workflow defect or Phase 6 leakage, but
  proved that tests did not bind either main to the atomic writer, require the
  exact new-session/process-group/`SIGKILL` call, protect the scheduled/manual
  trigger boundary, or require 30-day retention. It also found one stale
  30-minute statement and overly absolute upload wording. The existing tests
  and docs now cover those contracts. At that checkpoint, 22 controlled
  mutations across four batches proved the artifact, kill, invariant,
  aggregate, exit-code, timeout ownership, matrix, failure-propagation,
  trigger, and retention assertions. A subsequent fresh re-review found that
  raw YAML comments, alternate trigger names, and `|| :` could still evade the
  workflow tests while confirming the workflows themselves were correct. The
  tests now inspect comment-free active lines, require exactly scheduled/manual
  triggers, and reject every `||` fallback. Ten additional one-at-a-time
  mutations failed, reaching 32 proved regressions across five batches. A
  further fresh semantic review found that required active text could still sit
  under the wrong YAML owner, neither randomized command was exact, and the
  hardening selected-Git helper lacked a regression. Tests now bind unique
  indentation-owned blocks, commands to upload paths, and all three campaign
  Git helpers. Eight more one-at-a-time mutations failed, for 40 proved
  regressions across six batches; every mutated file was restored to its
  recorded post-repair hash. A further fresh ownership review then found four
  unprotected contracts while confirming that the current workflows and
  harnesses were correct: complete randomized matrices and worker-mode wiring,
  all replay-helper dimensions, the scheduled/manual controls, and artifact
  identity.
  Tests now bind those contracts. Sixteen more one-at-a-time mutations failed,
  reaching 56 proved regressions across seven batches; every mutated
  source/workflow file was again restored to its recorded hash. A final fresh
  semantic review found that artifact call sites could still collapse replay
  parameters and that quoted triggers, job-level conditions, or job-level
  environment precedence could evade the workflow checks. Integration now
  covers exact pending/completed replay rows across all modes and operations;
  workflow tests recognize quoted events and forbid disabling conditions or
  environment shadowing at the audited job level. Twelve more one-at-a-time
  mutations failed, reaching 68 proved regressions across eight batches; every
  mutated source/workflow file was again restored to its recorded hash. A fresh
  closing review then found that legal YAML whitespace before a mapping colon
  evaded the constrained key parser. Key/value inspection now shares one
  fail-closed parser that recognizes plain or quoted simple keys and separator
  whitespace, exposes duplicates, and rejects unsupported active direct-key
  syntax. Six separator-space trigger/condition/environment mutations and two
  duplicate-value hardening mutations failed, reaching 76 proved regressions
  across nine batches; the workflows were again restored exactly. A subsequent
  fresh closing review found that callers could still ignore duplicate direct
  block keys. The shared parser now rejects duplicates centrally; later
  `schedule : []` and replacement `strategy :` mutations both failed. The
  same parser is now required at the workflow root and `jobs` mapping
  boundaries; duplicate top-level `on`/`jobs` and duplicate randomized/CI job
  IDs also failed. The nested `workflow_dispatch` mapping is now checked before
  its `inputs` block is selected; a later `inputs : {}` mutation also failed.
  The current total is 83 proved regressions across ten
  batches, with every workflow mutation restored exactly. The complete
  finding/repair record is under Step 5.7 in `PLAN.md`.

## Verified close state

- Final post-Step-5.7 local full suite: 212/212 tests passed in 538.210 seconds on
  CPython 3.12.3 with Git 2.43.0.
- Pre-Step-5.7 exact minimum endpoint: 201/201 tests passed in 268.464 seconds on
  Python 3.11.15 with Git 2.29.0.
- Pre-Step-5.7 latest-stable endpoint: 201/201 tests passed in 277.085 seconds on
  Python 3.14.7 with Git 2.43.0.
- `python3 -m unittest discover -s tests -p 'test_filters_and_resources.py' -v`:
  4/4 real-filter/resource-fault tests passed at both endpoints (6.914 seconds
  minimum, 7.417 seconds latest stable).
- `python3 -m unittest discover -s tests -p 'test_campaign_records.py' -v`:
  15 provenance/replay/workflow/false-green contract tests passed. Eighty-three
  controlled mutations across ten batches made the relevant named tests fail
  before exact source restoration.
- `python3 -m unittest discover -s tests -p 'test_parent_interruption.py' -v`:
  6 parent-only process-interruption tests passed in 24.086 seconds.
- `python3 -m unittest discover -s tests -p 'test_lease.py' -v`: 10 lease
  tests passed in 19.146 seconds.
- `python3 -m unittest discover -s tests -p 'test_quarantine.py' -v`: 32
  quarantine/cleanup tests passed in 114.048 seconds.
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
- Post-Step-5.7 current-Git hardening campaign, both clone and worktree: 57
  defined, 56 exercised passes, one conditional reftable skip, zero failures;
  generated results stayed under `/tmp`. Earlier `57/57` records were the old
  reporter counting that skip as a pass, not 57 exercised checks.
- Hosted CI run 33276649643 at committed revision
  `a2ae7793b5a3653435fde988f716558f74ce6b88` passed all seven jobs: Python
  3.11 and latest stable on Ubuntu and macOS, exact Git 2.29.0, and both
  hardening modes with their artifact uploads. GitHub emitted non-failing
  Node.js 20 deprecation annotations for the existing CI checkout/setup
  actions, which it forced onto Node.js 24.
- Workflow-default randomized campaign: 12/12 random-kill seeds across three
  operations and two worker modes, all with a killed process; 4/4 state-machine
  seeds × 50 steps across both modes. All eight JSON results passed exact
  schema, provenance, and replay assertions.
- Hosted manual randomized run 33277111128 passed all eight jobs at the same
  revision. Its eight downloaded artifacts each reported two executed/two
  passed/zero pending/zero failed rows and passed exact schema, allowlisted
  provenance, run/SHA identity, status, and replay-command validation. The
  first row from each artifact was executed literally and passed; their eight
  replay result files each reported one executed/one passed/zero pending/zero
  failed row.
- Post-Step-5.7 interruption characterization passed 18/18 rows: seeds 0–2 for
  spawn, collect, and discard in clone and worktree modes, all with
  `killed: true` and `rc: -9`. Four state-machine seeds × 50 steps passed across
  both modes with the public audit active. The first row from each of the eight
  generated artifacts replayed literally and passed; all eight replay outputs
  passed schema, selected-Git provenance, completion-status, and replay-field
  assertions.
- Focused `lease_crash_matrix` and `discard_crash_matrix` cases passed in both
  clone and worktree modes; worktree discard exercised its two additional
  administration and branch cleanup boundaries.
- The changed worktree concurrency case passed 10/10 consecutive post-change
  runs without edits; each reported IDs 1–8, eight records, eight request
  indexes, and no audit issue.
- The exact five-sample benchmark completed in clone and worktree modes. Clone
  median parallel/single ratio was 4.695 (range 4.170–5.350); worktree was
  5.084 (range 4.378–5.906). JSON stayed under `/tmp`.
- Real-repository qualification passed 6/6 scenarios in 168.309 observed
  seconds on CPython 3.12.3 and Git 2.43.0. Its 17,412-byte checked-in JSON is
  byte-identical to the generated `/tmp` artifact at SHA-256
  `7d0e36fd68bcb8d6b22af5e88d5c7f248147c81e1c09d5cd773a190e0928cb6c`;
  a separate assertion audit rechecked profile/mode counts, recovery action,
  exit 88, custody after discard, clean audits, connectivity, and the
  uninitialized gitlink. The harness SHA in that artifact matches the final
  harness file.
- Post-Step-5.6 close verification passed the explicitly filtered full unit
  suite, 201/201 in 271.144 seconds on local CPython 3.12.3/Git 2.43.0. The
  first explicit-file command had the wrong import layout: 4 independent tests
  passed while 15 modules stopped before executing at
  `ModuleNotFoundError: support`. No file changed between attempts; adding
  `tests/` to the explicit runner's import path, as normal discovery does,
  produced the clean full pass.
- Out-of-checkout byte compilation, `sh -n install.sh`, workflow YAML parsing,
  changed-file trailing-whitespace search, executable-helper validation, and
  `git diff --check`: passed.
- No session-owned Python, Git, shell, or reviewer process remains running.
- Phase 5's hosted gate is complete. The only local changes are this completion
  record and the matching `PLAN.md` update; they are not committed or pushed.
  Phase 6 Step 6.1 is the next unfinished work.
