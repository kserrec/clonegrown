# Phase 7 final cold-review record

This document records the current-package qualification performed for Phase 7
Step 7.5. It separates the first cold review, independently reproduced defects,
their remediation gates, the final fresh re-review, and hosted evidence by
exact revision. It is not evidence for the preserved historical prototype.

## Review input and boundary

The first reviewer received the original 18 source-review findings, the
comment and public-claim audit, the known validation gaps, and the coverage map
in `PLAN.md`. Claimed closure locations were leads to verify, not accepted
proof. The review covered product code, durable state, CLI and Python APIs,
tests and campaign harnesses, packaging, public documentation, and evidence
provenance. Git LFS, native Windows, network or distributed filesystems, and
genuine disk or inode exhaustion remained stated unsupported boundaries rather
than inferred passing cases.

Before that review, the local tree based on
`354d16bc662f15f65dded911d3c26729bf5804aa` passed 233/233 discovered tests in
280.715 seconds. Installer checks passed 25/25; shell syntax, wheel and source
archive builds, isolated artifact installs, Apache-2.0 metadata, both full
hardening modes, two random-kill seeds for every operation and mode, and two
50-step state-machine seeds per mode also passed. Those results described the
uncommitted local tree only; they did not make it hosted-validated.

## First cold review: no-go

The first fresh review rejected release. Each finding below was then reproduced
independently in a disposable real repository before product code changed.

| Finding | Independent reproduction | Cause |
|---|---|---|
| Collected clone deletion could lose private refs such as `refs/stash`. | Normal release and discard removed the clone and left its unique stash commit unreachable from canonical. | Publication recorded the task branch but no baseline for other clone refs, and the quarantine fingerprint excluded `.git`. |
| Collection could overwrite a planted exact result ref. | A content-addressed result ref planted at a different commit was force-updated by collect. | Collection fetched with a force destination refspec instead of create-only publication. |
| A discarded record could lose its retained result without audit or retry failure. | After deleting the result ref, status reported no issue, a matching request returned the stale discarded record, and terminal metadata without result fields still validated. | Result custody and required result fields applied to `collected`, not the normal terminal `discarded` state. |
| A dangling worker-slot symlink could be treated as absence. | After moving the authentic worker aside and planting a dangling slot symlink, discard recorded success while both paths survived and status reported no issue. | Ownership decisions followed symlink targets through `Path.exists()` instead of checking lexical occupancy. |
| Init could write through symlinked control parents. | A symlinked `.cws` gained control children before refusal; a symlinked canonical `.git/cws` accepted a marker and init succeeded. | Child directories and the canonical marker were created before every parent was non-followingly validated. |

The reviewer also found that public documents still described an older hosted
run as the latest result. GitHub Actions run 33278590221 is the actual blocking
run at base revision `354d16bc662f15f65dded911d3c26729bf5804aa`, and scheduled
randomized run 33638194991 later passed at that same revision. Both predate the
local Phase 6–7 tree.

## Remediation and focused proof

| Plan step | Changed contract | Focused and affected gates |
|---|---|---|
| 7.5b | New clone records retain a non-task-ref baseline; changed or unverified clone-private refs require `--discard-private-refs`; clone quarantine fingerprints include refs. Non-ref `.git` state such as config or hooks remains outside that baseline and is documented. | Baseline and acknowledgement 3/3; post-authorization ref race 1/1; discard 14/14; quarantine 35/35; CLI 6/6; state 12/12. |
| 7.5c | Collection fetches the candidate object without a destination and compare-and-swaps an absent result ref; discarded records retain and authenticate result custody. | Audit 23/23; allocation 19/19; state 12/12; every collection crash boundary passed in clone and worktree modes. |
| 7.5d | Live and dangling worker-slot symlinks are occupied, unauthenticated paths at every discard, audit, tombstone, and recovery boundary. | New regressions 2/2; quarantine 35/35; audit 23/23; allocation 19/19; live-symlink and full discard-crash hardening passed in both modes. |
| 7.5e | Init preflights existing workspace-control and canonical-marker parents without following symlinks, then creates real directories parent before child. | Safety errors 18/18; core 14/14; state 12/12; API 6/6; both init crash matrices and the control/lock-symlink hardening case passed. |
| 7.5h | Init validates the exact selected workspace path before resolving it, so a selected symlink cannot redirect control-directory creation into its target. | The direct regression and complete safety/error module passed 1/1 and 19/19. |

These are focused remediation results, not the final release matrix. The final
fresh re-review and exact pushed-revision evidence are recorded below only
after they run.

## Restarted qualification finding

The first restarted full suite ran 246 tests in 295.045 seconds: 244 passed.
One failure was a stale expected error string after the new init-parent check
correctly refused a replaced canonical repository earlier. The second exposed
a product recovery regression. A configured Git fetch child survived parent
`SIGKILL`, returned zero, and transferred the recorded candidate commit, but
the separate create-only result-ref step never ran. The exact object was
present, the result and summary refs were absent, and recovery returned the
worker from `collecting` to `ready` instead of completing the formerly
supported transition.

Inspection of that boundary prompted disposable symbolic-ref races. One
planted the result ref during fetch; another planted it between the helper's
first type check and exact-value lookup. Both pointed at another ref holding
the exact candidate. Collection returned `collected`; status then reported
`namespace-ref-symbolic`. This was a distinct verified defect: the type and
target-value checks could not always distinguish the symbolic conflict from an
acceptable direct exact-ref race.

A third disposable race moved the direct result ref after the worker's second
snapshot but before the collected record write. Collection returned
`collected` even though the ref now named another commit; status immediately
reported `result-ref-missing` and `candidate-ref-retained`.

Step 7.5g made recovery publish an available exact candidate only through an
all-zero expected-old compare-and-swap and kept the existing post-publication
worker validation. It also made collection reject symbolic result refs before
transfer, after exact-value observation, after object validation, and after
any failed create, and rechecks the direct result inside the final metadata
transaction. A direct recovery conflict, both symbolic races, and the late
direct move remain unchanged on disk and return the worker to `ready`. The
seven direct regressions passed 7/7; complete audit/recovery,
parent-interruption, allocation, and safety-error modules passed 27/27, 6/6,
19/19, and 18/18 respectively.

A later disposable path-boundary probe selected an existing workspace symlink
whose target was an empty external directory. Init accepted the selection and
created `.cws` in the target because it resolved the selected path before the
Step 7.5e preflight. Step 7.5h now validates the lexical selection before
resolution. Its regression proves both the link and external target remain
unchanged, and the complete safety/error module passed 19/19.

The fresh re-review next found two narrower collection-finalization races.
Independent disposable probes reproduced both: a symbolic result planted
between the final type and value observations was accepted when it resolved to
the candidate, and a direct result moved as summary publication began was
accepted into collected metadata. The workspace lock did not protect Git refs,
and the checks and writes were separate Git processes. Step 7.5i now prepares
and locks the result/summary transaction, checks raw types while both locks are
held, and commits the summary only on agreement. A second prepared verification
holds both values stable across the collected-record write; idempotent collect
and recovery use the same primitive. Three direct transaction-window
regressions passed 3/3, and audit/recovery, parent interruption, core, and
repository modules passed 30/30, 6/6, 14/14, and 8/8.

## Final fresh re-review

The final fresh reviewer rejected release. The reviewer independently ran the
complete 254-test suite (254/254 passed in 295.072 seconds), both hardening
modes (56 exercised passes, one conditional reftable skip, and zero failures
per mode), shell syntax, and CLI smoke checks on Linux with CPython 3.12.3 and
Git 2.43.0. None of those broad gates exposed the six remaining contract
defects below; disposable real-repository probes did.

1. A collected clone can lose a changed dangling symbolic private ref without
   `--discard-private-refs`. The probe created
   `refs/local/dangling-bookmark` as a symbolic ref to an absent branch before
   lease release; ordinary discard removed the worker. The private-ref
   snapshot and deletion fingerprint use `for-each-ref`, which omits this
   dangling symbolic ref.
2. Worktree spawn can overwrite a pre-existing dangling symbolic task-branch
   name. The create transaction does not first establish the raw ref type, and
   allocation evidence does not reserve the generated branch name.
3. Dangling symbolic links at three control-file names are treated as absence:
   init replaces `.cws/state.json`; matching-request spawn replaces an invalid
   request index and advances `next_id`; and an occupied worker-record name is
   refused only after its ID is consumed. The shared cause is use of
   `Path.exists()` at lexical occupancy boundaries before atomic replacement.
4. CLI init resolves `--workspace` before the lifecycle's lexical-path check,
   so it accepts a selected workspace symlink and creates `.cws` in the link
   target. The existing regression covers the Python API, not the CLI adapter.
5. `clean_git_env()` does not remove `GIT_CONFIG`. An inherited override
   therefore reached a Clonegrown Git command and made spawn fail with Git's
   "only one config file at a time" error. Existing sanitation coverage checks
   `GIT_CONFIG_COUNT`, not `GIT_CONFIG`.
6. An unchanged repeat collection after an accepted history rewrite uses the
   new call's default `allow_rewrite=False` rather than the stored worker
   policy. The first collection succeeds with `allow_rewrite=True`; the
   immediate repeat incorrectly rejects the same result as not descending
   from its assigned base.

The reproductions are retained outside the checkout as
`/tmp/clonegrown_probe_dangling_private_ref.py`,
`/tmp/clonegrown_probe_dangling_task_branch.py`,
`/tmp/clonegrown_probe_dangling_workspace_state.py`,
`/tmp/clonegrown_probe_dangling_request_index.py`,
`/tmp/clonegrown_probe_dangling_worker_record.py`,
`/tmp/clonegrown_probe_init_symlink.py`,
`/tmp/clonegrown_probe_git_config_env.py`, and
`/tmp/clonegrown_probe_recollect_rewrite.py`. They are diagnostic artifacts,
not repository evidence or tests. Each finding must receive a class regression
when repaired.

The same reviewer separately verified the Step 7.5i collection boundary with
`/tmp/clonegrown_probe_collection_timing.py`: direct and symbolic result
conflicts remained untouched; attempted result and summary moves both failed
while the prepared transaction held their locks; object-only recovery used an
all-zero expected-old create; and a conflicting recovery ref stayed unchanged
while the worker reset to `ready`. A post-release writer probe was not counted
as a defect because the documented lease is a cooperative writer boundary.

No additional blocker was found in cooperative lease enforcement,
ignored-content acknowledgement, checked quarantine deletion, interrupted
published-spawn preservation, installer ownership checks, remote/config
fidelity, targeted redaction, ordinary request reuse, lifecycle reporting,
generated-branch validation, contextual public errors, retained direct-result
custody, or package/license/evidence scoping. Native macOS, CPython 3.11, exact
Git 2.29.0, and reftable were not freshly exercised by this reviewer. Release
therefore remains a no-go until Steps 7.5j–7.5o repair these findings and a new
independent review returns no open finding.

## Release qualification and hosted evidence

The current wrapup checkpoint has strong but non-qualifying local evidence:
the coordinating run passed 254/254 tests in 278.176 seconds; the independent
reviewer repeated 254/254 in 295.072 seconds; clone and worktree hardening each
passed 56 exercised cases with one conditional reftable skip and zero failures;
all 12 bounded random-kill runs and four 50-step state-machine runs passed; and
the wheel/source build, isolated installs, entry points, Apache-2.0 metadata,
and canonical license hash passed. Step 7.5i's focused and timing probes also
passed. These results establish what was exercised, not release readiness in
the presence of the six findings above.

This record is committed and pushed as part of a deliberately incomplete
Phase 6–7 checkpoint so that the work and no-go evidence are not stranded in a
local checkout. That checkpoint is not the release commit. The last completed
hosted evidence remains blocking run 33278590221 and scheduled randomized run
33638194991 at revision
`354d16bc662f15f65dded911d3c26729bf5804aa`; both predate this tree. Exact
pushed-revision CI, minimum-Git and macOS results, and a no-open-finding cold
review remain pending after remediation.
