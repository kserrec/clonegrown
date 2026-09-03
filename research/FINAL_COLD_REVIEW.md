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

## Third fresh review (first Step 7.5 pass on the repaired tree): no-go

After Steps 7.5j–7.5o repaired the second review's six roots, a third fresh
reviewer received this record, the `PLAN.md` contract, evidence boundary,
input bundle, and coverage map, and the archived starting state, with no
access to `HANDOFF.md` or the Step completion records. It ran the full suite
(266/266), both hardening modes (56 pass, 1 conditional reftable skip, 0 fail
each), the Step 7.5i timing probe, and its own disposable probes under
`/tmp/clonegrown-review-probes/`. Every one of the six repaired classes held
under adjacent probes. The verdict was nevertheless no-go, on these findings:

1. **F1 (medium, in-contract).** `GIT_GRAFT_FILE` survived `clean_git_env()`,
   was honoured by Git 2.43.0, flipped `merge-base --is-ancestor`, and let
   `collect` record a non-descending result as `collected` with
   `allow_rewrite: false`; fifteen other unlisted `GIT_*` names also reached
   child Git. The class ("an inherited process-level `GIT_*` override reaches
   a Clonegrown Git command and changes its outcome") was still open after the
   `GIT_CONFIG` name fix. Step 7.5p owns it.
2. **F2 (medium, in-contract).** A collected worker preserved in quarantine
   after a post-authorization change was deleted by `--force` alone even when
   the quarantined checkout now held Git-ignored paths; only the private-ref
   category was re-asked. Step 7.5q owns it.
3. **F3 (low, claim mismatch).** Dangling symbolic refs under `branch-owner`,
   `results/<sha>`, and an uncollected worker's `result` name were invisible
   to `status` and to allocation evidence (the ID was consumed and a base pin
   written before the create transaction refused). Nothing was written
   through or deleted. Step 7.5r owns it.
4. **F4 (low, claim mismatch).** `README.md`, `ARCHITECTURE.md`, and
   `SKILL.md` still carried pre-repair statements for the CLI workspace check,
   repeat-collection policy, and "direct"/"resolvable" ref wording, and the
   re-authorization flag list omitted `--discard-ignored`. Step 7.5s owns it.
5. **F5 (informational).** Boundaries to state literally: pseudo-refs outside
   `refs/` are not in the private-ref baseline; a symlink above the selected
   workspace name is followed; init creates real control subdirectories
   before it refuses a dangling state file. Step 7.5s owns it.

The reviewer's full report, with every probe path and output, is preserved
verbatim below.

---

# Clonegrown final cold review — release qualification (third fresh review)

Date: 2026-09-02. Reviewer: fresh agent, read-only on the checkout
`/home/serrecchia/Projects/clonegrown` (uncommitted working tree on `main`,
base `c9728a0`). Environment: Linux 6.17.0-35-generic, CPython 3.12.3,
Git 2.43.0. All probes, logs, and results live outside the checkout under
`/tmp/clonegrown-review-*`. HANDOFF.md and the Step 7.5a–7.5o completion
records were not read; no `.env`-pattern file was opened.

## 1. Verdict: NO-GO

Every one of the six second-review blocker classes is repaired on this tree
and each repair held under my adjacent probes. The full unit suite (266/266),
both hardening modes (56 pass / 1 conditional skip / 0 fail each), the 7.5i
collection-timing properties, `git diff --check`, `sh -n install.sh`, byte
compilation, and a wheel build all pass. Release is nevertheless blocked by
two in-contract defects found in the *same classes* the last review opened
(Git-environment sanitation and discard acknowledgement custody), plus two
low-severity claim mismatches and one set of stale public statements that
contradict the repaired behaviour. The instructions require no open finding of
any severity that contradicts the contract or public claims; there are four.

## 2. Findings, ranked by severity

### F1 — Medium — `GIT_GRAFT_FILE` reaches child Git and defeats the `--allow-rewrite` gate (in-contract defect; same class as second-review finding 5)

- **Claim.** `clonegrown/core.py:53-54` ("Environment variables that can
  retarget Git, inject config, or replace its helpers" are stripped);
  ARCHITECTURE.md:692-696 ("The exact denylist includes `GIT_CONFIG` beside
  `GIT_CONFIG_COUNT` and **the other process-level `GIT_*` overrides**");
  README.md:449-453 (a result that does not descend from the base is accepted
  only under `--allow-rewrite`, and the recorded policy governs repeats).
  History-interpretation overrides are explicitly treated as in scope: the
  denylist strips `GIT_NO_REPLACE_OBJECTS` and `GIT_REPLACE_REF_BASE`
  (core.py:62) and `tests/test_core.py:122` pins that.
- **What the code does.** `clean_git_env` (core.py:279-288) removes only the
  literal names in `GIT_ENV_EXACT` and the three prefixes. `GIT_GRAFT_FILE`
  is not among them, Git 2.43.0 still honours it (deprecated, with a hint on
  stderr), and grafts change `merge-base --is-ancestor`, which is exactly
  what `snapshot_worker` (worker.py:135-138) uses to enforce ancestry.
- **Reproduction.** `/tmp/clonegrown-review-probes/p7_adjacent.py` (output
  `p7.out`, key `7a_graft_collect`) and `p5_git_env.py` (`p5.out`). A
  worker's task branch was rewritten to an orphan history. Plain
  `clonegrown collect N` exits 2 with "worker result does not descend from its
  assigned base". The same command with `GIT_GRAFT_FILE=<file grafting the
  new tip onto the base>` exits 0; the durable record then says
  `status: collected, allow_rewrite: false` while `git merge-base
  --is-ancestor <base> <result_sha>` is false in canonical. Without the
  variable, `status` immediately reports drift "worker result does not
  descend from its assigned base" and a normal `discard` fails with that same
  text as an *error* (not a missing-flag refusal), so the record is
  self-contradictory and the worker cannot be discarded normally.
  `p5.out` also lists every hostile name that reached the child Git across
  323 invocations of a wrapper `CLONEGROWN_GIT`:
  `GIT_ADVICE, GIT_ATTR_SOURCE, GIT_CURL_VERBOSE, GIT_DEFAULT_HASH, GIT_EDITOR,
  GIT_GLOB_PATHSPECS, GIT_GRAFT_FILE, GIT_ICASE_PATHSPECS, GIT_INDEX_VERSION,
  GIT_LITERAL_PATHSPECS, GIT_NOGLOB_PATHSPECS, GIT_PAGER, GIT_REFLOG_ACTION,
  GIT_REF_FORMAT, GIT_SEQUENCE_EDITOR, GIT_SSL_NO_VERIFY` (plus
  `GIT_TERMINAL_PROMPT`, correctly forced to `0` every time). Of these only
  `GIT_GRAFT_FILE` was proven to change a custody decision on Git 2.43;
  `GIT_DEFAULT_HASH=sha256` did not change a local clone's object format
  (`7d_worker_object_format: sha1`). `GIT_REF_FORMAT` (Git ≥ 2.45) would make
  every clone worker a reftable repository, which the private-ref baseline
  then reports as unverifiable; not exercisable on 2.43.
- **Affected files.** `clonegrown/core.py:55-67` (denylist),
  `clonegrown/worker.py:118-139` (ancestry gate), `tests/test_core.py:40-113`
  (regression checks a fixed name list, not the class).
- **Why it matters.** The second review's finding 5 was closed by adding one
  name (`GIT_CONFIG`) and a same-shape test. The class ("an inherited
  process-level `GIT_*` override reaches a Clonegrown Git command and changes
  its outcome") remains open, and this instance produces a durably false
  custody statement. A class fix would deny every `GIT_*` name by default and
  allow only a reviewed set (author/committer identity at most), with a test
  that fails when a new honoured variable appears.

### F2 — Medium — a quarantined collected worker is deleted with `--force` alone even when it now holds Git-ignored paths (in-contract defect; contract item 3 / README category rule)

- **Claim.** PLAN.md contract item 3: "A collected worker with ignored paths
  requires `--discard-ignored` in addition to any post-collection drift
  acknowledgement." README.md:172-178 ("Each detected custody category has
  its own flag"), README.md:400-404, ARCHITECTURE.md:669-680, SKILL.md:62-65
  and 136-138 ("Do not run `discard --discard-ignored` … unless the user has
  authorized destroying the named category").
- **What the code does.** First-pass authorization (`_authorize_discard`,
  lifecycle.py:1202-1205) enumerates ignored paths. The re-authorization of a
  worker already preserved in quarantine (`_reauthorize_quarantined`,
  lifecycle.py:1246-1292) re-asks the private-ref question
  (lines 1275-1288) but never the ignored-content question; it accepts
  `force` alone. The sibling case where the intent was recorded but nothing
  moved *does* re-ask both flags
  (`tests/test_quarantine.py::test_stale_intent_never_bypasses_the_acknowledgements`),
  so the two post-intent paths are inconsistent with each other.
- **Reproduction.** `p7_adjacent.py`, keys `7b_first_discard`,
  `7b_reauth_force_only`, `7b2_*`. A collected clone with no ignored content
  is discarded with no flags while paused at `discard.after_quarantine`; an
  ignored file (`secret.log`, matched by the committed `*.log` rule) is
  written into the quarantined checkout during the pause. The recheck
  correctly preserves the quarantine ("changed after its custody check").
  `discard N --force` (no `--discard-ignored`) then returns `discarded`;
  `secret.log` and the quarantine are gone. The control case `7b2` shows the
  same file present *before* the first discard is refused with
  "required: --discard-ignored" even with `--force`.
- **Affected files.** `clonegrown/lifecycle.py:1246-1292`; the docstring at
  lifecycle.py:1001-1005 and ARCHITECTURE.md:805-809 describe the
  re-authorization as "`--force` and `--discard-private-refs`", so the
  protocol text and the category rule contradict each other.
- **Severity note.** Requires a writer that ignores the cooperative lease,
  which the docs call a stated boundary; but the fresh-fingerprint recheck
  exists precisely to catch that writer, and the re-ask must cover every
  documented category or the docs must say it does not.

### F3 — Low — dangling symbolic refs at `branch-owner`, `results/<sha>`, and an uncollected worker's `result` name are invisible to `status` and to allocation evidence (claim mismatch)

- **Claim.** ARCHITECTURE.md:487-491 ("a symbolic ref planted under one of
  Clonegrown's names is reported as `namespace-ref-symbolic`") and :460-463
  ("Before `next_id` advances, nothing may already represent that id: …
  or any worker ref").
- **What the code does.** `NamespaceRefs` (audit.py:54) and
  `allocation_evidence`'s worker-ref listing (worker.py:740-745) use
  `for-each-ref`, which omits dangling symbolic refs; `audit_worker` asks Git
  directly only for the base-pin name (audit.py:133) and, for collected or
  discarded workers only, the summary name (audit.py:147).
- **Reproduction.** `p2_task_branch.py` (`p2.out`), keys `2d_*` and `2g_*`
  and the final `status_issues: []`. A dangling symbolic
  `refs/cws/<ws>/workers/1/branch-owner` planted before spawn was not
  allocation evidence: ID 1 was consumed, the base pin was written, the
  worktree create transaction then refused it (correctly, byte-for-byte
  untouched), and the record ended `spawn_failed`. A dangling symbolic
  `workers/3/result` let spawn succeed and made `collect` refuse (correct),
  but `status` reported no issue for either ref. No ref was written through
  or deleted, so this is a reporting/claim gap, not a custody loss.
- **Affected files.** `clonegrown/audit.py:38-76,129-150`,
  `clonegrown/worker.py:740-745`.

### F4 — Low — public documents still state the pre-repair behaviour for two repaired classes (claim mismatch; internally contradictory docs)

Each of these is contradicted by current code and by the same document's own
qualification notice, so a reader cannot tell which statement is true:

- README.md:336-338: "the current CLI adapter does not preserve that lexical
  check" — false; `cli.py:206-216` hands the selected path over lexically and
  `p4_cli_init_symlink.py` (`p4.out`, 4a–4e) shows the CLI refusing absolute,
  relative, default-name, and trailing-slash symlinks identically to the API.
- ARCHITECTURE.md:630-631: "the current CLI resolves that option before the
  check" — same stale statement.
- ARCHITECTURE.md:731-732: "An unchanged repeat after an accepted history
  rewrite currently consults the new call's default policy and can fail" —
  false; `lifecycle.py:750-756` and `p6_recollect_rewrite.py` (`p6.out`,
  6a) show the stored policy is used.
- SKILL.md:223-224 ("detects changed **direct** clone-private refs") and
  ARCHITECTURE.md:768 ("every **resolvable** non-task ref … dangling symbolic
  refs"), :789 ("the same resolvable ref listing") — understate the raw
  inventory that `worker.py:208-269` actually records.

### F5 — Informational — boundaries that are implemented as designed but not stated literally

- Pseudo-refs outside `refs/` (`ORIG_HEAD`, `FETCH_HEAD`, `MERGE_HEAD`, …)
  are not part of the clone-private-ref baseline. `p1.out` key `1i`: a
  unique commit reachable only from `ORIG_HEAD` was deleted by a flag-less
  normal discard. README.md:405-407 says "non-task refs … `for-each-ref` …
  plus a walk of the loose ref files", which a reader could take to include
  top-level pseudo-refs; say literally that only names under `refs/` count.
- A symlinked *parent* of the selected workspace is followed (`p4.out` 4f):
  `init --workspace <link>/ws` creates the workspace inside the link's target
  and records the resolved path. README.md:336 says "a selected workspace
  path that is **itself** a symlink", so this is consistent, but worth one
  literal sentence.
- `init` creates the four real control subdirectories before it refuses a
  dangling `.cws/state.json` or `.cws/lock` (`p3.out` 3a, 3c). This matches
  ARCHITECTURE.md:632-636 (parent-before-child creation precedes state
  inspection), consumes no ID, creates no lock, and replaces nothing.

## 3. Per-class verification record (six second-review blocker classes)

All probes: `/tmp/clonegrown-review-probes/p*.py`, outputs `p*.out`, disposable
repositories under `/tmp/clonegrown-review-p{1..7}-*`.

**Class 1 — dangling symbolic clone-private refs (p1).** PASS. Dangling
symref added after publication → refused without `--discard-private-refs`,
symref byte-for-byte intact, deleted with the flag (1a). Live symref added
(1b), baseline symref `refs/remotes/cws-source/HEAD` retargeted to a dangling
name (1c) or removed (1d), baseline direct ref removed (1e), `refs/stash`
(1g), a filesystem symlink planted as a ref file (1h), legacy record with no
baseline (1n) → all refused. `git pack-refs --all` alone (1f) and an explicit
`extensions.refstorage=files` (1o) → not refused (correct: no semantic
change). Post-authorization plants: dangling symref written into the
quarantined checkout during `discard.after_quarantine` (1j) and into the slot
during `discard.before_delete` (1k) → "changed after its custody check;
preserved in quarantine", record `discarding` with `quarantine_error`,
`--force` alone re-refused with the exact changed ref name, `--force
--discard-private-refs` deleted; `recover` twice reported
`quarantine-preserved` and left the quarantine (1l). Worktree worker not
asked (1m). Boundary observed: pseudo-ref `ORIG_HEAD` (1i, F5).

**Class 2 — dangling symbolic task-branch names (p2).** PASS. Dangling
symbolic (2a), live symbolic (2b), and direct (2c) task-branch names →
refused as "symbolic task branch"/"task branch" evidence with `next_id`,
records, base pin, owner ref, slot, and `git worktree list` all unchanged;
raw ref bytes identical before and after. Symref planted *during* spawn at
`spawn.after_clone` (2e) → create transaction refused, symref intact, record
`spawn_failed`, `recover` left it alone. Dangling symbolic base pin (2f) →
refused before allocation. Adjacent gaps: dangling symbolic `branch-owner`
(2d) and `result` (2g) names are not allocation evidence and not audited
(F3) but are never written through.

**Class 3 — dangling links at control names (p3).** PASS. Init: dangling
`state.json` (3a), `state.json` as a directory (3b), dangling `.cws/lock`
(3c), dangling `.git/cws` (3d), dangling workspace path (3e), dangling
`.cws/quarantine` (3f) → all refused, nothing replaced, no marker written, no
workspace created for 3d/3e. Spawn: dangling request index (3g), live
request-index symlink to a valid-looking file elsewhere (3h, victim
unchanged), dangling worker record (3i), dangling worker lock (3j), dangling
staging entry (3k), dangling quarantine entry (3l), dangling slot (3m),
dangling workspace lock (3n), dangling state file (3o) → all refused with
`next_id` unchanged, no record, no base pin, no lock, every link intact.
Healthy re-init and spawn afterwards succeed (3p, 3q).

**Class 4 — CLI `init --workspace <symlink>` parity (p4).** PASS. Absolute,
relative (cwd = parent), default `<repo>-dev` name, and trailing-slash forms
through `python -m clonegrown init` all exit 2 with the same message as the
Python API (4d); the link survives, the external target stays empty, and no
canonical marker directory is created. Boundary: symlinked parent followed
(4f, F5).

**Class 5 — `GIT_*` overrides reaching child Git (p5, p7a).** PARTIAL. All
42 hostile names set at once (including `GIT_CONFIG`, `GIT_CONFIG_COUNT`,
`GIT_DIR`, `GIT_WORK_TREE`, `GIT_CEILING_DIRECTORIES`, `GIT_NAMESPACE`,
`GIT_EXEC_PATH`, `GIT_TERMINAL_PROMPT=1`): init, clone spawn, worktree spawn,
collect, release, discard, status, recover all exit 0, and the wrapper log
shows none of the denylisted names reaching any of 323 Git invocations, with
`GIT_TERMINAL_PROMPT=0` every time. Sixteen names not on the denylist do
reach Git; `GIT_GRAFT_FILE` is honoured by Git 2.43 and flips
`merge-base --is-ancestor`, which end-to-end let `collect` accept a
non-descending result without `--allow-rewrite` (F1).

**Class 6 — repeat collection after `--allow-rewrite` (p6).** PASS. Rewrite
refused by default, accepted with the flag, repeated with and without the
flag as a no-op returning the same `result_sha`, `allow_rewrite: true`, no
`drift` in `status`, CLI repeat exit 0 (6a). A second rewrite or a new
ordinary commit after collection is refused under either argument and the
immutable result and summary refs still name the accepted tip (6b, 6d).
Normal discard of an unchanged rewrite-collected worker needs no `--force`
(6c). Parent killed at `collect.after_verify` during a rewrite collection →
`recover` reports `collect-finished` using the stored policy and the default
repeat is a no-op (6e). A legacy record with the field removed is judged
conservatively (ancestry required, drift reported) (6f).

## 4. Coverage-map spot checks

| Item | Result |
|---|---|
| 5.1 active-writer race / 7.5i timing | `/tmp/clonegrown_probe_collection_timing.py` rerun (`timing.out`): direct conflict preserved at the planted value, worker `ready`; symbolic exact conflict refused, symref target intact; result and summary moves both failed (rc 128) while the prepared transaction held their locks, record `collected` with both refs at the candidate; object-only recovery published through an all-zero expected-old `write_ref` and finished; conflicting recovery ref untouched, worker reset `ready`. Adjacent: a dangling symbolic summary ref planted at `collect.after_verify` (p7 7c) → refused, worker back to `ready`, symref intact, immutable candidate retained and reported `candidate-ref-retained`. |
| 5.2 ignored work | First-pass refusal with count and name sample holds (p7 7b2); quarantine re-authorization gap (F2). |
| 5.3 unchecked deletion | Quarantine, recheck, preserved-on-change, `recover` preserves, errors-enabled deletion all observed (p1 1j–1l, p7 7b). |
| 5.4 branch ownership | Create-only transaction refuses direct, live-symbolic, dangling-symbolic occupants (p2). |
| 5.5 changed published recovery | Covered by suite (`test_worktree`, `test_parent_interruption`) — passed; not separately probed. |
| 5.6 installer root | `sh -n install.sh` OK; `tests/test_installer.py` (25 ownership/replacement tests) passed in the suite; not re-probed by hand. |
| 5.7 / 5.8 remotes and config | `tests/test_repository.py` passed; canonical with a credentialed remote spawned cleanly (p7 7e). |
| 5.9 Git sanitation | Denylisted names never reach Git, custom `CLONEGROWN_GIT` wrapper included; class remains open (F1). |
| 5.10 secret-bearing errors | `CommandFailure` for a fetch of `https://user:s3cretpass@…` contains no `s3cretpass` and shows `https://example.invalid/…` (p7 7e). |
| 5.11 stale request reuse | Same request ID + different params refused; same params returns the same worker; discarded worker whose result ref was deleted is refused on retry and reported `result-ref-missing` by `status`, `discarded-result-missing` by `recover` (p7 7e). |
| 5.12 incomplete status | The 28 issue codes enumerated in ARCHITECTURE.md:600-610 match `audit.py`/`recovery.py` exactly. Gap: dangling symbolic worker refs (F3). Live slot symlink → `worker-authentication-failed`, discard refused, moved content intact (p7 7e). |
| 5.13 create-only allocation | Every occupancy case in p3 left `next_id` unchanged; `x.lock` task refused with no evidence (p7 7e). |
| 5.14 API/CLI parity | Both default to a non-strong clone (`cli.py:222-224`, `lifecycle.py:418`); init symlink parity (p4). |
| 5.15 invalid generated branch | `check-ref-format --branch` before allocation (p7 7e). |
| 5.16 low-level errors | Every refusal in every probe carried the five-part operation/stage/durable-state/preservation/recovery text. |
| 5.18 one-shot | `--abandon` and `claim` refused for a collected worker; leased discard refused (p7 7e). |
| Comment/public overclaims | Stale statements (F4); boundaries to state literally (F5). |
| retention/license/package | `pyproject.toml` Apache-2.0 with `license-files`, version `0.1.0a1`; wheel built to `/tmp/clonegrown-review-build/clonegrown-0.1.0a1-py3-none-any.whl` (94,194 bytes); isolated install not exercised. |

## 5. Gate results

- Unit suite: `python3 -m unittest discover -s tests -v` → **Ran 266 tests in
  451.576 s, OK** (`/tmp/clonegrown-review-unittest.log`; ran concurrently
  with the hardening suites, hence slower than the recorded ~280 s).
- Hardening, clone mode: 57 defined, **56 passed, 1 skipped**
  (`reftable_repository`, conditional), **0 failed**; wall 1 min 54.49 s;
  `sha256 79f4c07c54f6edaddb20c14c2df6c9f0c01ccf4e6080095096842c495d83eca4
  /tmp/clonegrown-review-hardening-clone.json`.
- Hardening, worktree mode: 57 defined, **56 passed, 1 skipped, 0 failed**;
  wall 1 min 39.42 s;
  `sha256 3b502d3f4ccd8163c583dfd57904314cd0888514872366aea961a893c1ebb7a5
  /tmp/clonegrown-review-hardening-worktree.json`
  (log `/tmp/clonegrown-review-hardening.log`).
- `git diff --check` clean; `sh -n install.sh` OK; `python3 -m compileall`
  OK; wheel build OK (residue `build/` and `clonegrown.egg-info/` created by
  pip inside the checkout were removed; the checkout's `git status` is the
  same 19 entries as at the start).
- Versions: Python 3.12.3, Git 2.43.0, Linux 6.17.0-35-generic.

## 6. Not verified, and why

- Hosted CI on the pushed revision, macOS, CPython 3.11, exact Git 2.29.0:
  not available locally; the tree is uncommitted.
- reftable repositories: Git 2.43 cannot create them (hardening skip);
  `GIT_REF_FORMAT` leakage (F1 list) therefore untested end-to-end.
- Random-kill and state-machine campaign seeds, isolated wheel/sdist install,
  and `tests/campaign/real_repository_qualification.py`: not run in this
  review (not in the requested gate list; the unit suite's
  `test_campaign_records.py` and `test_parent_interruption.py` passed).
- `GIT_ATTR_SOURCE`, `GIT_INDEX_VERSION`, and the pathspec-mode variables
  reach child Git (p5) but were not shown to change any Clonegrown decision;
  they are listed for the class fix, not as proven defects.
- Genuine disk/inode exhaustion, network filesystems, Git LFS, native
  Windows: stated boundaries, not exercised.

## Fourth fresh review (second Step 7.5 pass, after Steps 7.5p–7.5s): no-go

A fourth fresh reviewer, with the same inputs and the same exclusions, found
the third review's F1–F5 closed and every earlier class holding, and ran the
suite (270/270 on the end-of-review tree) and both hardening modes (56 pass,
1 conditional skip, 0 fail each). It still returned no-go on:

1. **N1 (medium, in-contract).** A `refs/replace/*` ref or a deprecated
   `info/grafts` file planted inside the worker's own repository flipped the
   worker-side `merge-base --is-ancestor` gate, so `collect` recorded a
   non-descending result as `collected` with `allow_rewrite: false`. Step
   7.5t owns it.
2. **N2 (low, claim mismatch).** A loose non-ref file at the next ID's
   base-pin name was reported by `status` but was not allocation evidence, so
   the ID was consumed before Git refused the pin. Step 7.5u owns it.
3. **N3 (low, claim mismatch).** A filesystem symlink at a summary name whose
   target lies outside `refs/` was reported as "never written through or
   deleted" but `collect` replaced it. Step 7.5u owns it.
4. Informational: the public notices described only the second review; the
   architecture wording for an unreadable quarantined clone read as if a flag
   unlocked deletion; re-authorization names one missing category per call;
   a global `clone.defaultRemoteName` makes every clone spawn fail closed.
   Step 7.5v owns the wording.

The reviewer's full report is preserved verbatim below.

---

# Clonegrown final cold review — release qualification (fourth fresh review)

Date: 2026-09-02. Reviewer: fresh agent, read-only on
`/home/serrecchia/Projects/clonegrown` (uncommitted working tree on `main`,
base `c9728a00557d6f5ca1763922d33591d8798a1283`). Environment: Linux
6.17.0-35-generic, CPython 3.12.3, Git 2.43.0. All probes, outputs, and
results are outside the checkout under `/tmp/clonegrown-review2-*`.
`HANDOFF.md` and the Step 7.5a–7.5s completion records were not read; no
`.env`-pattern file was opened; nothing inside the checkout was modified (the
one `pip wheel` residue, `build/` and `clonegrown.egg-info/`, was deleted and
`git status` shows the same 22 entries as at the start).

**Reviewed tree fingerprint.** `git diff | sha256sum` =
`54b8040e47d111cc8b99e2b2e1008ea3e31f956b600a8457914cd3e77329bfc4`; product
files (sha256 prefix): audit `ab0a0a5c`, cli `a309e205`, core `dc45d2f4`,
lifecycle `cfcd44e3`, recovery `97f7552b`, repository `8af509bd`, state
`043a08cd`, worker `9a0f509e`; README `4ed73871`, SKILL `f8c98c1c`,
ARCHITECTURE `96b68c51`. **The tree changed under review:** a concurrent
session rewrote `tests/test_quarantine.py` at 20:29:51 (and `HANDOFF.md` at
20:22:55) while my first full suite run (started 20:21:47) was executing. The
product code and the three public documents did not change during the review
(mtimes 20:04–20:07, before my first read), so every probe below is against
the fingerprinted product. Gate results are reported for both tree states.

## 1. Verdict: NO-GO

Every one of the third review's findings F1–F5 is closed on this tree, and
each closure held under my adjacent probes (section 3). The six earlier
classes hold. Both hardening modes pass (56/1 skip/0 fail each), the 7.5i
collection-timing properties hold, and static gates pass. Release is
nevertheless blocked by one in-contract defect adjacent to F1 (the ancestry
gate is decided inside the worker's own repository, so a graft file or replace
ref planted there records a non-descending result as `collected` with
`allow_rewrite: false`), two low claim mismatches adjacent to F3, and the
fact that the tree was being edited by another session during the review
(the unit suite was red on the start-of-review state because of a stale test
expectation and green, 270/270, on the end-of-review state — see gate
results). The instructions permit GO only with no open
finding of any severity that contradicts the contract or public claims.

## 2. Findings, ranked by severity

### N1 — Medium — worker-local grafts or replace refs defeat the `--allow-rewrite` ancestry gate (in-contract defect; adjacent to F1)

- **Claim.** `clonegrown/cli.py:145-146` (`--allow-rewrite`: "accept a result
  that does not descend from the worker's base"); README.md:455-459 and
  SKILL.md:101-105 ("new commits or a new rewrite after collection are
  rejected under any argument"); the product's own stated principle at
  `core.py:53-58` ("a custody decision such as ancestry must not depend on
  which variable a hostile parent set") and the regression docstring at
  `tests/test_core.py:132-134`. Contract item 8 keeps "exact-base pinning"
  intact.
- **What the code does.** `snapshot_worker` (`worker.py:136-139`) runs
  `git merge-base --is-ancestor <base> HEAD` *inside the worker repository*
  and nowhere else. After the candidate is fetched into canonical
  (`lifecycle.py:825-838`) only `rev-parse`/`cat-file` checks run; there is no
  canonical-side ancestry check. Step 7.5p closed the process-environment
  vector (`GIT_GRAFT_FILE`, `GIT_REPLACE_REF_BASE`, …), but Git also reads
  `<gitdir>/info/grafts` and `refs/replace/*` from the repository itself, both
  of which any writer inside the worker (the agent, or the uncooperative
  writer the fingerprint protocol exists to catch) can create.
- **Reproduction.** `/tmp/clonegrown-review2-probes/pA_env.py`, output
  `pA.out`, keys `A3_*` and `A3b_*`. A worker's task branch is rewritten to
  an orphan commit. Plain `collect` exits 2 ("does not descend"). Writing
  `.git/info/grafts` = `<orphan> <base>` in the worker: `git merge-base
  --is-ancestor` in the worker returns 0, `collect` exits 0, the record reads
  `status: collected, allow_rewrite: false, result_sha: <orphan>`, and in
  canonical `git merge-base --is-ancestor <base> <orphan>` returns 1.
  `status` reports no drift and no issue while the graft persists; once the
  graft file is removed `status` reports drift "worker result does not
  descend from its assigned base" and a normal `discard` fails with that text
  as an error, i.e. the same self-contradictory record the third review
  described for F1. The replace-ref variant (`git replace <orphan>
  <commit-parented-on-base>` inside the worker, `A3b_*`) gives the same
  `collected / allow_rewrite: false` record; canonical holds no replace ref
  and says non-descending; here the private-ref custody at least refuses a
  flagless discard with `--discard-private-refs: … refs/replace/<sha>`.
- **Affected files.** `clonegrown/worker.py:119-140`,
  `clonegrown/lifecycle.py:773,835-840`, `clonegrown/recovery.py:651`
  (status drift is judged in the worker too); `tests/test_core.py:132-156`
  and `tests/test_collect_policy.py` cover the environment vector and the
  policy, not repository-local overrides.
- **Classification.** In-contract defect. No document states that
  repository-local history overrides are outside the gate; README.md:419-422
  ("this ref baseline does not inspect … other changes inside `.git`") is
  about deletion custody, not the ancestry claim. A class fix would evaluate
  ancestry in canonical after the fetch (canonical holds both objects) and/or
  refuse a worker whose Git directory carries `info/grafts` or `shallow`.

### N2 — Low — a non-ref loose file at the next ID's base-pin name is not allocation evidence: the ID is consumed before Git refuses the pin (claim mismatch; same shape as F3)

- **Claim.** ARCHITECTURE.md:460-463: "Before `next_id` advances, nothing
  may already represent that id: a record, a slot directory, a stage or
  quarantine directory, an operation lock file, a base pin, or any worker
  ref. A stale counter is reported as corruption … and nothing is changed."
- **What the code does.** `allocation_evidence` (`worker.py:673-676`) tests
  the base-pin name only with `resolve_ref` and `is_symbolic_ref`; the raw
  inventory (which does see the file, as `raw:<digest>`) is consulted only
  for the `workers/<id>/` prefix (`worker.py:677-686`).
- **Reproduction.** `pC_namespace.py`, `pC.out` key
  `C2_garbage_at_base_pin_name`. A loose file `refs/cws/<ws>/bases/1`
  containing `this is not a ref` is reported by `status` as
  `orphan-namespace-ref`; `spawn` then advances `next_id` 1→2, fails at "pin
  creation" with Git's "unable to resolve reference …: reference broken",
  leaves no record, and leaves the file byte-for-byte intact. The same file
  under `workers/1/garbage` (key `C2_garbage_under_worker_prefix`) *is*
  evidence and consumes nothing. Nothing is written through or deleted; the
  error carries honest five-part context.
- **Affected files.** `clonegrown/worker.py:647-687`; ARCHITECTURE.md:460-463.

### N3 — Low — a filesystem symlink at a worker's summary name pointing outside `refs/` is reported as "never written through or deleted" but `collect` replaces it (claim mismatch; adjacent to F3)

- **Claim.** `audit.py:218-220` (`namespace-ref-symbolic`: "a symbolic ref
  under Clonegrown's namespace is never written through or deleted");
  ARCHITECTURE.md:487-492.
- **What the code does.** The raw inventory classifies a filesystem symlink
  as `link:<target>` and `NamespaceRefs` lists it as symbolic
  (`audit.py:62-63`). The write path decides with Git's `symbolic-ref -q`
  (`repository.py:595-598`, used by `_require_plain_refs` at
  `lifecycle.py:249-254,776` and `result_ref_transaction` at
  `repository.py:744-764`). Git treats a symlink ref file as symbolic only
  when its target starts with `refs/`; otherwise it follows the link and
  reads the target file's content as the ref value, and `update-ref` renames
  a new file over the link.
- **Reproduction.** `pC.out` key `C3_fs_symlink_at_summary_outside_refs`.
  With `refs/cws/<ws>/workers/2/result` a symlink to an external file holding
  the base SHA: `status` reports `namespace-ref-symbolic` for that name;
  `git symbolic-ref -q` returns 1; `collect` exits 0 and the name now holds a
  regular file with the result SHA (the symlink is gone); the external file
  is unchanged; `status` afterwards reports nothing. Contrast key `C3b`: a
  symlink whose target is `refs/heads/main` is refused ("refusing to write
  through a symbolic ref"), the link survives, and `main` is untouched.
- **Severity note.** Nothing of the user's is written through, and the
  occupant is a planted symlink inside `.git/refs`; but the audit's literal
  promise for that occupant is false, and Git used the link target's content
  as the summary's expected old value.

### F4-adjacent — Informational — stale or imprecise public statements (not defects)

- README.md:17-28, SKILL.md:14-22, ARCHITECTURE.md:6-13 still describe only
  the *second* review's six defects; the third review's three code findings
  (F1–F3, repaired in Steps 7.5p–7.5r) are not mentioned in those notices.
  Not a behavior contradiction; the notices are due for rewrite at release.
- ARCHITECTURE.md:818-823 ("a checkout Git can no longer read fails closed
  on the ignored category") reads as if `--discard-ignored` then unlocks the
  deletion. That is true for a quarantined **worktree** whose admin directory
  was pruned (`pB.out` `B_worktree3_*`: `--force` refused naming
  `--discard-ignored`; `--force --discard-ignored` deletes without Git). For a
  quarantined **clone** whose Git directory no longer works (`B_clone3_*`,
  `.git/HEAD` removed) every flag combination is refused with "not a non-bare
  Git working tree" and `recover` reports `quarantine-preserved`: fail-closed,
  but no `discard` path deletes it. README.md:376-379 states the worktree
  case precisely; the ARCHITECTURE sentence should say the clone case is a
  hard refusal.
- Re-authorization of a preserved quarantine names one missing category per
  call (`lifecycle.py:1285-1310`: `--force`, then `--discard-ignored`, then
  `--discard-private-refs`; `pB.out` `B_clone1_sequence`), whereas the first
  authorization names every missing flag at once (`lifecycle.py:1198-1219`;
  ARCHITECTURE.md:784-786 "One refusal names every missing acknowledgement"
  is stated for the first authorization). Not a contradiction; a usability
  inconsistency.

### Other observations (not findings)

- Global Git config still applies, as documented — including
  `clone.defaultRemoteName=upstream`, which makes every clone spawn fail with
  "local clone did not create its source remote" (`pA.out` `A4_*`). A
  `spawn_failed` record and no damage; a usability trap worth a sentence.
- A worktree quarantine re-authorized with `--force` after the planted change
  moved the shared task branch deletes the content, retains the branch at its
  new tip, and leaves the record `discarding` ("task branch retained:
  expected …, found …"; `pB.out` `B_worktree2_force`). This is exactly
  README.md:386-392; note that `branch_cleanup_sha` is not refreshed at
  re-authorization even though the user acknowledged the change.
- A directory holding a file at a live worker's summary name (`pC.out` `C6`)
  is reported as `orphan-namespace-ref` (without an `id`) and makes `collect`
  fail at Git's fetch ("bad object refs/…/result/child"); the worker returns
  to `ready`, nothing is touched.
- `pip wheel . --no-build-isolation` fails on this host because system
  setuptools 68.1.2 cannot parse PEP 639 `license = "Apache-2.0"`; with
  isolation (pyproject requires setuptools>=77.0.3) the wheel builds. Expected.

## 3. Verification record

### F1 — Git environment (`pA_env.py` → `pA.out`). CLOSED.

A wrapper `CLONEGROWN_GIT` logged every `GIT_*`/`SSH_ASKPASS`/`HOME`/`EMAIL`
variable each child Git received across init, clone spawn, worktree spawn,
two collects, two releases, status, recover, and two discards (490 Git
invocations, all through the wrapper including the `update-ref --stdin`
prepared-transaction `Popen` and the raw-byte runner) under 60 hostile
names at once: `GIT_DIR`, `GIT_WORK_TREE`, `GIT_COMMON_DIR`,
`GIT_CEILING_DIRECTORIES`, `GIT_NAMESPACE`, `GIT_CONFIG`,
`GIT_CONFIG_COUNT/KEY_0/VALUE_0`, `GIT_CONFIG_GLOBAL/SYSTEM/NOSYSTEM/
PARAMETERS`, `GIT_GRAFT_FILE`, `GIT_REPLACE_REF_BASE`,
`GIT_NO_REPLACE_OBJECTS`, `GIT_ATTR_SOURCE`, `GIT_ATTR_NOSYSTEM`,
`GIT_SHALLOW_FILE`, `GIT_EXEC_PATH`, `GIT_TEMPLATE_DIR`, `GIT_REF_FORMAT`,
`GIT_DEFAULT_HASH`, `GIT_INDEX_VERSION`, `GIT_SSH*`, `GIT_ASKPASS`,
`SSH_ASKPASS`, `GIT_PROXY_COMMAND`, `GIT_EXTERNAL_DIFF`, `GIT_PAGER`,
`GIT_EDITOR`, `GIT_SEQUENCE_EDITOR`, `GIT_TERMINAL_PROMPT=1`, the four
pathspec modes, `GIT_OPTIONAL_LOCKS`, `GIT_FLUSH`, `GIT_TRACE*`,
`GIT_ADVICE`, `GIT_REFLOG_ACTION`, `GIT_ALLOW_PROTOCOL`, `GIT_PROTOCOL*`,
`GIT_CURL_VERBOSE`, `GIT_SSL_NO_VERIFY`, `GIT_DISCOVERY_ACROSS_FILESYSTEM`,
`GIT_QUARANTINE_PATH`, `GIT_PREFIX`, the invented
`GIT_FUTURE_UNKNOWN_OVERRIDE_2031`, and the bare name `GIT_`. All ten
operations exited 0. Names that reached child Git: exactly
`GIT_AUTHOR_NAME/EMAIL/DATE`, `GIT_COMMITTER_NAME/EMAIL/DATE` (with the
values set), and `GIT_TERMINAL_PROMPT=0` on every one of the 490 invocations;
no other `GIT_*` name and not `SSH_ASKPASS`. Unrelated variables passed
(`PROBE_UNRELATED`, `EMAIL`, `HOME`). End to end (`A2`): with the task branch
rewritten to an orphan, `collect` under `GIT_GRAFT_FILE` exits 2 "does not
descend" while the same file makes ambient `git merge-base` return 0;
`--allow-rewrite` then collects. Local config still applies (`A4`:
canonical `core.sparseCheckout=true` → `copied_sparse_checkout: true`), and
global config still applies (`A4`, the `clone.defaultRemoteName` case).
Adjacent gap: repository-local overrides (N1).

### F2 — quarantine re-authorization (`pB_reauth.py` → `pB.out`). CLOSED, both modes.

For each of clone and worktree: a collected, released worker with no ignored
content; flagless `discard` paused at `discard.after_quarantine`; during the
pause an ignored `secret.log` (and for clones `refs/local/planted`) is
written into the quarantined checkout; the recheck preserves the quarantine
("changed after its custody check"), record `discarding` with
`quarantine_error`. Then: `--force` alone → refused naming
`--discard-ignored` (quarantine intact); `--force --discard-ignored` →
clone refused naming `--discard-private-refs` (`refs/local/planted`),
worktree deleted; `--discard-ignored --discard-private-refs` without
`--force` → refused naming `--force`; all three → `discarded`, quarantine
and slot gone, `status` clean (`B_*1_*`). A planted new commit alone →
`--force` alone suffices (`B_*2_*`; worktree then retains the moved branch as
documented). Git unable to read the checkout: worktree admin removed →
`--force` refused "cannot be enumerated … pass --discard-ignored", then
`--force --discard-ignored` deletes; clone `.git/HEAD` removed → hard
refusal under every combination, `recover` → `quarantine-preserved`
(`B_*3_*`, see informational note). Abandon intent preserved in quarantine →
no flag / `--force` refused "pass --abandon"; `--abandon` deletes
(`B_*4_*`). Intent recorded but rename pending (`discard.before_delete`) →
after the planted change the recheck preserves; `--force` alone re-asks
ignored (`B_*5_*`).

### F3 — namespace refs (`pC_namespace.py` → `pC.out`). CLOSED.

Dangling symbolic refs planted at `bases/1`, `workers/1/result`,
`workers/1/branch-owner`, and `workers/1/results/<sha>` (each in turn): every
one is reported by `status` as `namespace-ref-symbolic` with `id: 1`; clone
and worktree `spawn` are both refused before allocation ("already has a
symbolic base ref" / "worker refs; nothing was changed"); `next_id` stays 1,
no record, no base pin, ref bytes identical before and after; `recover`
reports `namespace-ref-symbolic-left` and leaves it (`C1_*`). A loose non-ref
file under `workers/1/` is `orphan-namespace-ref` and allocation evidence
(`C2_garbage_under_worker_prefix`); at the base-pin name it is reported but
not evidence (N2). A direct ref packed at `workers/4/result` (loose file
absent, present in `packed-refs`) is evidence; a dangling symref survives
`pack-refs --all` and is evidence for a worktree spawn (`C4`). A filesystem
symlink into `refs/` is refused as symbolic (`C3b`); one pointing outside
`refs/` is N3. Canonical as a linked worktree is refused at `init` ("use the
primary checkout") and, after init, at `spawn`/`status` when canonical's
`.git` is replaced by another repository's worktree gitfile (`C5`), so the
fd-anchored inventory never runs against a linked canonical.

### F4 / F5 — documents. CLOSED.

The three pre-repair statements the third review quoted are gone (`grep` for
"current CLI adapter", "does not preserve that lexical", "currently
consults", "resolves that option before", "detects changed direct", "every
resolvable non-task", "same resolvable ref" returns nothing). Checked
statement by statement against observed behavior: CLI workspace check
(README:336-339, ARCHITECTURE:630-633 → `pD.out` `class4`: absolute,
relative, and default-name symlinks refused with the API's message, link
intact, target empty, no canonical marker directory; a symlinked *parent* is
followed and the resolved path recorded — stated literally at README:337-339
and ARCHITECTURE:633); repeat-collection policy (README:455-459,
SKILL:101-105, ARCHITECTURE:740-742 → `class6`); private-ref inventory
wording (README:409-418, SKILL:66-73, ARCHITECTURE:679-682 → `class1`,
symbolic and dangling); re-authorization flag list (README:404-408,
ARCHITECTURE:816-823, `lifecycle.py:1001-1007` → `pB.out`); Git
environment (ARCHITECTURE:697-705 lists the six identity names and
`SSH_ASKPASS` → `pA.out`). Boundaries stated literally and observed:
pseudo-refs outside `refs/` not in the baseline (README:411-414,
ARCHITECTURE:779-781 → `pD.out` `F5_pseudo_ref_orig_head_flagless_discard`:
an `ORIG_HEAD`-only commit is deleted by a flagless discard); symlinked
parent followed (above); control subdirectories created before a dangling
`state.json` is refused (ARCHITECTURE:633-637 → `class3`:
`locks/requests/staging/workers` exist, link intact, "workspace state file is
unsafe").

### Six second-review classes (`pD_classes.py` → `pD.out`). All PASS.

1. Dangling symbolic clone-private ref after publication → refused naming
   `refs/local/dangling-bookmark`, bytes intact, deleted with the flag;
   baseline `refs/remotes/cws-source/HEAD` retargeted → refused.
2. Dangling symbolic task-branch name → worktree spawn refused ("symbolic
   task branch"), `next_id` 1, no record, bytes intact; a clone spawn of the
   same task (private refs) succeeds.
3. Dangling `state.json` → init refused, link intact; dangling worker record
   and dangling request index → spawn refused, `next_id` unchanged, links
   intact.
4. CLI init symlink parity (above).
5. `GIT_CONFIG` alone and `GIT_CONFIG_COUNT` injection of `core.bare=true` →
   spawn succeeds.
6. Rewrite refused by default, accepted with the flag, repeated with and
   without the flag as a no-op with `allow_rewrite: true`, no drift; a new
   commit after collection refused under either argument; the immutable
   result still names the accepted tip.

### Step 7.5i timing properties (`/tmp/clonegrown_probe_collection_timing.py` → `timing.out`). All five hold.

Direct conflict preserved at the planted value, worker `ready`; symbolic
exact conflict refused, symref target intact; result and summary move
attempts both rc 128 while the prepared transaction held the locks, record
`collected`; object-only recovery published through an all-zero
expected-old `write_ref` and `collect-finished`; conflicting recovery ref
untouched, `collect-reset-ready`.

## 4. Coverage-map spot checks (`pE_spot.py` → `pE.out`, plus code reading)

| Item | Result |
|---|---|
| 5.1 active-writer race / 7.5i | timing probe 5/5; adjacent symbolic/directory occupants at the summary name refused or reported (`pC` C3b, C6). Gap: N3. |
| 5.2 ignored work | First authorization names count and sample; re-authorization re-asks in both modes (`pB`). |
| 5.3 unchecked deletion | Quarantine, recheck, preserved-on-change, `recover` preserves, errors-enabled deletion observed in every `pB` case. |
| 5.4 branch ownership | Create-only transaction refuses direct, packed, live- and dangling-symbolic occupants (`pC` C1/C4, `pD` class 2). |
| 5.5 changed published recovery | `recovery.py:217-248` marks divergence `broken`, never deletes; suite `test_worktree`/`test_parent_interruption` passed in both runs. |
| 5.6 installer root | `sh -n install.sh` OK; `tests/test_installer.py` passed in the suite; not hand-probed. |
| 5.7 / 5.8 remotes and config | `_canonicalize_remote_url` and `ConfigOccurrence(value=None)` read; `test_repository.py` passed; a credentialed remote is copied verbatim (`pE` 5.10). |
| 5.9 Git sanitation | Allowlist rule proven across 490 invocations including a custom `CLONEGROWN_GIT` (`pA`). |
| 5.10 secret-bearing errors | `CommandFailure` for a fetch of `https://user:s3cretpass@…` shows `https://<redacted>@example.invalid/…` and no `s3cretpass` (`pE` 5.10). |
| 5.11 stale request reuse | Same params → same worker; different params refused; discarded worker with deleted result ref → retry refused, `status` `result-ref-missing`, `recover` `discarded-result-missing`. |
| 5.12 incomplete status | The 28 issue codes in `audit.py`/`recovery.py` equal the 28 enumerated at ARCHITECTURE.md:600-611 exactly. Gap: N3 (occupant reported then replaced). |
| 5.13 create-only allocation | Rewound counter → "already has a record, slot directory, operation lock file; nothing was changed", records intact. Gap: N2. |
| 5.14 API/CLI parity | API `spawn(ws, "HEAD", task)` → `strong: false, mode: clone`; CLI default identical; `strong=True, mode="worktree"` refused. |
| 5.15 invalid generated branch | `x.lock` → "generated task branch is invalid for Git", `next_id` unchanged, no `refs/cws/` refs, no record. |
| 5.16 low-level errors | Every `init/spawn/collect/discard/recover` refusal in every probe carried the five-part context; `release`/`claim`/`status` errors are bare, as README.md:444 scopes. |
| 5.17 timing gate | No `ratio` assertion in `hardening_suite.py`; `parallel_spawns_unique` passed in both modes. |
| 5.18 one-shot | Leased discard refused whatever the flags; `--abandon` and `claim` refused for a collected worker. |
| Comment/public overclaims | F4 closed; informational notices above. |
| `CWSError`, heartbeat, failpoints | `grep CWSError` finds nothing in the package; `failpoint` gated on `CLONEGROWN_TEST_MODE == "1"` (`core.py:474-490`). |
| retention/license/package | `pyproject.toml` `license = "Apache-2.0"`, `license-files`; wheel `clonegrown-0.1.0a1-py3-none-any.whl` carries `License-Expression: Apache-2.0` and `licenses/LICENSE`; sha256 `10418d0baf338a607af60b762c07015493bdafecdcc41728c6874e5764473431`. Isolated install not exercised. |

## 5. Gate results

- **Unit suite, run 1** (tree state at 20:21:47, before the concurrent test
  rewrite): `python3 -m unittest discover -s tests -v` → **Ran 270 tests in
  487.279 s, FAILED (errors=1)**, 269 ok
  (`/tmp/clonegrown-review2-unittest.log`; concurrent with the clone
  hardening run). The error:
  `test_quarantine.QuarantineTests.test_quarantined_worktree_whose_admin_was_pruned_is_still_deletable_with_acknowledgement`
  at the then-line 748 called `discard(..., force=True)` and expected
  `discarded`; the product raised "the quarantined worker's ignored paths
  cannot be enumerated because Git can no longer read it; pass
  --discard-ignored" — the Step 7.5q behavior that ARCHITECTURE.md:818-823
  documents and my `pB.out` `B_worktree3_*` observed. A stale test
  expectation, not a product regression.
- **Unit suite, run 2** (tree state at 20:36:21, after
  `tests/test_quarantine.py` was rewritten at 20:29:51 to assert the
  `--discard-ignored` refusal and then delete with both flags): **Ran 270 tests in 438.864 s, OK** — 270 ok, 0 errors, 0 failures
  (`/tmp/clonegrown-review2-unittest-run2.log`; run alone, no concurrent
  hardening). So the suite is green on the end-of-review tree state and was
  red only on the start-of-review state because of the stale test. The rewritten test alone:
  `python3 -m unittest discover -s tests -p test_quarantine.py -k
  pruned_is_still_deletable` → Ran 1 test in 1.524 s, OK.
- **Hardening, clone mode:** 57 defined, **56 passed, 1 skipped**
  (`reftable_repository`, conditional on Git ≥ 2.45), **0 failed**; sum of
  case times 143.1 s; wall 20:22:14 → 20:24:49 (2 min 35 s, concurrent with
  run 1); `sha256 28c7669ac4fffd568a2a09295760ce65a16840a0bbf44753eb71331e0a9fcab3
  /tmp/clonegrown-review2-hardening-clone.json`.
- **Hardening, worktree mode:** 57 defined, **56 passed, 1 skipped
  (`reftable_repository`), 0 failed**; sum of case times 103.5 s; wall
  20:33:49 → 20:35:42 (1 min 53 s);
  `sha256 6facb8f8543790e4c94db381ef57823d8c517e46a24a29b349c3d7e40c421d1c
  /tmp/clonegrown-review2-hardening-worktree.json`.
- `git diff --check` clean; `sh -n install.sh` OK; `python3 -m compileall
  clonegrown tests` OK (bytecode redirected outside the checkout); wheel
  build OK with build isolation (see observation); residue removed.
- Versions: CPython 3.12.3, Git 2.43.0, Linux 6.17.0-35-generic, pip 24.0,
  system setuptools 68.1.2.

## 6. Not verified, and why

- Hosted CI on a pushed revision, macOS, CPython 3.11, exact Git 2.29.0: not
  available locally; the tree is uncommitted and was being edited by another
  session during this review.
- reftable repositories and `GIT_REF_FORMAT` end to end: Git 2.43 cannot
  create them (hardening skip); the fallback-to-`for-each-ref` branches in
  `raw_ref_inventory`/`NamespaceRefs`/`allocation_evidence` were read, not
  exercised.
- Random-kill and state-machine campaign seeds, isolated wheel/sdist install,
  `real_repository_qualification.py`: not in the requested gate list and not
  run.
- Genuine disk/inode exhaustion, network filesystems, Git LFS, native
  Windows: stated boundaries, not exercised.
- `HANDOFF.md` and the Step 7.5a–7.5s completion records: deliberately not
  read, per instructions.

## Fifth fresh review (third Step 7.5 pass, after Steps 7.5t–7.5v): no-go

A fifth fresh reviewer found N1–N3 and the wording notes closed, every earlier
class holding, the suite 273/273, and both hardening modes clean, and still
returned no-go on four adjacent findings:

1. **R1 (medium, in-contract).** Recovery finished an interrupted collection
   on the worker-side ancestry judgement alone; a forged loose parent object
   inside a strong clone (Git does not verify a parent's hash while walking)
   produced a durable `collected, allow_rewrite: false` record for a
   non-descending result that `status` did not surface. Step 7.5w owns it.
2. **R2 (low).** A directory at the base-pin or task-branch name was not
   allocation evidence, so the ID was consumed first. Step 7.5x owns it.
3. **R3 (low).** A symbolic ref or filesystem symlink planted at a worktree
   worker's task-branch name was deleted by discard's branch cleanup, and no
   status code named it while the worker was live. Step 7.5y owns it.
4. **R4 (low).** A FIFO at the base-pin name hung `spawn` inside Git because
   the name was resolved before it was `lstat`-inspected; the wording also
   over-promised `namespace-ref-symbolic` for non-regular files. Step 7.5x
   and 7.5z own it.

The reviewer's full report is preserved verbatim below.

---

# Clonegrown final cold review — release qualification (fifth fresh review)

Date: 2026-09-02. Reviewer: fresh agent, read-only on `/home/serrecchia/Projects/clonegrown`
(uncommitted working tree on `main`, base `c9728a0`). Environment: Linux 6.17.0-35-generic,
CPython 3.12.3, Git 2.43.0, pip 24.0. Every probe, log, and result lives outside the checkout under
`/tmp/clonegrown-review3-*`. `HANDOFF.md` and the Step 7.5a–7.5v completion records were not read;
no `.env`-pattern file was opened; nothing inside the checkout was modified (the wheel was built from an
`rsync` copy under `/tmp/clonegrown-review3-build/src`, so no `build/` or `egg-info` residue was ever
created in the checkout; `git status --short` shows the same 23 entries at start and end).

**Tree fingerprints.** `git diff | sha256sum` at start:
`cc48f892502fe5d2ebfbe1e25abfd24b2eb7f6b7561994b465569ca32e0b80ef`; at end: `d04b332a0c24cc6401419fd5c445c80f7c2ec4e6a15398b1e23a833ef882957a`.
**The tree changed under review, but not the product:** only `PLAN.md` and `HANDOFF.md` were rewritten by
another session at 21:08:37 (neither was read by me beyond the sections allowed at the start). Every product
module, test, and public document kept its pre-review mtime (20:44–20:53) and hash (sha256 prefix): audit
`30487aa5`, cli `a309e205`, core `fc2af01a`, lifecycle `f449d978`, recovery `a7174846`, repository
`1e963b23`, state `043a08cd`, worker `a5997d3d`; README `38e7249b`, SKILL `b1b2789e`, ARCHITECTURE
`7cda18a3`, FINAL_COLD_REVIEW `4c41b60e`, test_quarantine `aff85bc6`, test_collect_policy `18c20199`. Every
probe and gate below ran against that fingerprinted product.

## 1. Verdict: NO-GO

The fourth review's N1, N2, N3 and its wording notes are closed on this tree and every closure held under
adjacent probes; the third review's F1–F5, the six second-review classes, and the Step 7.5i
collection-timing properties all hold; the full unit suite (273/273), both hardening modes (56 pass / 1
conditional reftable skip / 0 fail each), `git diff --check`, `sh -n install.sh`, out-of-checkout byte
compilation, and a wheel build + isolated install all pass.

Release is nevertheless blocked by one in-contract defect adjacent to N1 (the interrupted-collection
recovery path finishes a collection on the worker-side ancestry judgement alone, so a worker-side lie that
never crosses the fetch — a forged parent object — yields a durable `collected, allow_rewrite: false`
record for a non-descending result) and by three low claim mismatches adjacent to N2/N3 (directory
occupants of the base-pin and task-branch names still consume the ID; a symbolic ref or filesystem symlink
planted at a worktree worker's task-branch name is deleted by discard; a FIFO at an owned name hangs
`spawn` inside Git instead of being refused). The instructions permit GO only with no open finding of any
severity that contradicts the contract or public claims; there are four.

## 2. Findings, ranked by severity

### R1 — Medium — recovery finishes an interrupted collection on the worker-side ancestry judgement alone; a forged parent object inside the worker yields `collected, allow_rewrite: false` for a non-descending result (in-contract defect; adjacent to N1)

- **Claim.** README.md:465-471 ("Ancestry is judged by object content … and the judgement is repeated on
  canonical's copy of the objects after the fetch"); ARCHITECTURE.md:711-717 (same); `cli.py:145-146`
  (`--allow-rewrite`: "accept a result that does not descend from the worker's base"); PLAN contract item
  8 ("exact-base pinning … remain intact"); Step 7.5t's own bullet ("a worker-side check forced to lie is
  still caught on canonical's copy after the fetch").
- **What the code does.** `collect` (lifecycle.py:836-843) re-judges ancestry on canonical after
  `_publish_result_ref`. `_recover_collecting` (recovery.py:250-301) does not: when the exact candidate
  object and its `results/<sha>` ref are present in canonical it runs `snapshot_worker(...,
  require_ancestry=not worker.allow_rewrite)` — the judgement *inside the worker's repository* — and then
  commits the summary and the collected record. The worker-side judgement is content-only with respect to
  replace refs and grafts (`repository.is_ancestor`), but Git's commit-parent traversal
  (`repo_parse_commit`) does not verify the hash of a parent object it reads, so a loose object file
  planted under a real parent's id with a `parent <base>` line makes `merge-base --is-ancestor` — and
  therefore `is_ancestor` — return true inside the worker. Git's `fsck` and the fetch path do detect the
  mismatch, which is exactly why `collect` is safe and recovery is not: recovery never fetches.
- **Reproduction.** `/tmp/clonegrown-review3-probes/p1b_forged_recovery.py` → `p1b.out`.
  Canonical `main` = base; an unrelated canonical branch `side` ends at commit X whose parent S1 is real.
  A strong clone worker is `reset --hard X` (so X, an object canonical already holds, is the candidate and
  base is not its ancestor: `honest_worker_rc: 1`). The worker's loose object for S1 is replaced by a copy
  carrying `parent <base>` (`h3.forge_loose_commit`): ambient `merge-base` in the worker returns 0 and
  `clonegrown.repository.is_ancestor(worker, base, X)` returns **True** (`1b_setup`). Plain `collect`
  is correctly refused by the canonical re-check ("does not descend"), leaving `results/<X>` retained and
  reported `candidate-ref-retained` (`1b_collect`). A later `collect` interrupted at `collect.after_mark`
  (`CLONEGROWN_TEST_MODE=1`, exit 88) leaves the record `collecting` with `candidate_sha = X`
  (`1b_interrupted`). `recover` then reports `collect-finished`; the record reads `status: collected,
  allow_rewrite: false, result_sha: X`, the summary ref names X, `status` shows no issue and no drift, while
  `git merge-base --is-ancestor <base> X` in canonical returns 1 (`1b_recover`). The honest control (same
  worker shape, no forgery) is refused at both `collect` and the interrupted attempt (`1b_honest_*`), and a
  forged object that *would* have to cross the fetch fails closed with Git's "hash mismatch"
  (`p1.out` `1f_forged_collect`).
- **Affected files.** `clonegrown/recovery.py:265-296` (no canonical-side `is_ancestor` before
  `result_ref_transaction`); `clonegrown/recovery.py:651` and `worker.py:136-138` (`status` drift is
  judged in the worker too, so the false record is not surfaced); `tests/test_collect_policy.py:108-123`
  proves the canonical re-check only for `collect` and only with a mock; `tests/test_audit.py:546-559` and
  `tests/test_parent_interruption.py:207-224` recover only descending candidates.
- **Classification.** In-contract defect. The precondition is a hostile or corrupt object inside the
  worker's own object store (which `git fsck` reports, and which only the worker's own writer can plant) plus
  an interruption in the `collecting` window; no document states that a corrupted worker object store is out
  of scope, and the durable effect is the same false custody statement N1 and F1 were rated Medium for. A
  class fix: recovery judges ancestry on canonical's copy (`is_ancestor(canonical, base, candidate)`) before
  finishing, exactly as `collect` does, and `status` reports drift from canonical's view for a collected
  worker.

### R2 — Low — a directory at the base-pin name or at a worktree worker's task-branch name is not allocation evidence: the ID is consumed (and for the task branch a record and base pin are written) before the collision is refused (claim mismatch; same shape as N2)

- **Claim.** ARCHITECTURE.md:463-467 ("Before `next_id` advances, nothing may already represent that id:
  … a base pin, or any worker ref. A stale counter is reported as corruption … and nothing is changed");
  ARCHITECTURE.md:350-352 ("Allocation also lists any raw occupant of the generated name as evidence, so
  the ID is never consumed over a collision"); Step 7.5u ("Treat every raw occupant of an owned ref name
  as foreign … Allocation evidence lists any raw inventory entry at the base-pin or task-branch name").
- **What the code does.** `allocation_evidence` (worker.py:657-680) decides the base-pin and task-branch
  names with `resolve_ref`, `is_symbolic_ref`, and `name in inventory`. `raw_ref_inventory` records a
  directory's *children* (`<name>/child`) but never the directory itself, so a directory at exactly the
  owned name matches nothing; the worker-refs prefix test (line 688) does see children, which is why the
  same directory under `workers/<id>/…` *is* evidence. `loose_ref_occupant` would classify the directory as
  `special`, but it is consulted only on the write path, after the counter has advanced.
- **Reproduction.** `/tmp/clonegrown-review3-probes/p2_occupants.py` → `p2.out`, keys
  `A_clone_base_pin_dir_nonempty`, `A_clone_base_pin_dir_empty`, `A_worktree_base_pin_dir_*`: `status`
  reports the child as `orphan-namespace-ref`; `spawn` advances `next_id` 1→2, then fails at "base-pin
  creation" with the (misworded) "refusing to touch a symbolic ref in Clonegrown's namespace"; no record;
  directory and child byte-for-byte intact. Key `A_worktree_task_branch_dir_nonempty`: `next_id` 1→2, a
  record is created, the base pin is written and withdrawn, `create_task_branch` refuses ("it or its
  ownership ref already exists"), record `spawn_failed`, occupant intact. Every other occupant kind at every
  name (dangling/live symbolic ref, filesystem symlink with `refs/` text, absolute link inside or outside
  `refs/`, dangling link, non-ref file, loose and packed direct refs, packed ref shadowed by a dangling
  symref) is evidence with `next_id` unchanged and no record (117 rows, all `occupant_unchanged: true`).
- **Affected files.** `clonegrown/worker.py:657-680`, `clonegrown/repository.py:699-750`;
  ARCHITECTURE.md:350-352 and :463-467.
- **Note.** An *empty* directory at `branch-owner`, `result`, `results/<sha>`, or the task-branch name is
  silently replaced by Git when the ref is created (`A_*_dir_empty` rows with `occupant_unchanged:
  false`); that is Git's own handling of its transient directories and is not counted here.

### R3 — Low — a symbolic ref or filesystem symlink planted at a worktree worker's task-branch name is deleted by discard (claim mismatch; adjacent to N3)

- **Claim.** README.md:389-398 ("deletes the task branch only in a ref transaction that proves this
  worker created it and that it still points where cleanup recorded"); ARCHITECTURE.md:343-374 ("The task
  branch is intended to have the same compare-and-swap ownership … Nothing is deleted by name alone");
  Step 7.5u ("Every write-path check that used `is_symbolic_ref` (…, branch cleanup, …) now uses
  `is_foreign_ref`"); the fourth review listed the task-branch name among the names at which nothing may be
  written through, replaced, or deleted.
- **What the code does.** `_release_task_branch` (worker.py:1094-1134) applies `is_foreign_ref` to the
  *ownership ref* only. `release_task_branch` (repository.py:862-894) resolves the branch name through
  whatever occupies it, and the `delete refs/heads/<branch> <tip>` line of the no-deref transaction deletes
  the occupant itself when its resolved value matches the tip recorded at authorization — Git resolves a
  symbolic ref for the old-value check even under `no-deref`, as the code's own docstring at
  repository.py:504-507 notes for the create case.
- **Reproduction.** `/tmp/clonegrown-review3-probes/p3e.py` → `p3e.out`. A collected, released
  worktree worker; `refs/heads/other` is set to the result tip; the task branch is deleted and replaced by
  (i) a symbolic ref to `refs/heads/other`, (ii) a filesystem symlink whose text is `refs/heads/other`,
  (iii) a filesystem symlink to an external file holding the tip, (iv) a symbolic ref to `other` after
  `other` moved to the base. Flagless discard is refused for (i), (ii), (iv) — the worker's `HEAD`
  resolves through the occupant, so the snapshot says "HEAD is detached or not on its assigned task branch"
  or "uncommitted changes" — but `--force` deletes the worker and the **occupant is gone**
  (`occupant_unchanged: false`, name `absent`), record `discarded`, `branch_cleanup_left: null`. For
  (iii) even a **flagless** discard succeeds and deletes the link (Git reads the external file's content as
  the branch value). In every case the target (`refs/heads/other`, the external file) is byte-for-byte
  unchanged: nothing is written *through*; the foreign occupant is what is deleted. A live worktree worker
  whose task-branch name holds a symbolic ref is invisible to `status` except as `drift`
  (`p4.out` `taskbranch_symref_status`): no issue code names it.
- **Affected files.** `clonegrown/worker.py:1094-1134`, `clonegrown/repository.py:862-894`;
  ARCHITECTURE.md:343-374.
- **Classification.** Low claim mismatch. The occupant can only exist after someone deleted the worker's
  real branch; what is lost is the planted ref file, never its target. But the 7.5u contract for "every raw
  occupant of an owned ref name" and the documented "proves this worker created it" rule are not met for the
  task-branch name, and the same `is_foreign_ref` guard the owner ref receives would close it.

### R4 — Low — a FIFO at the base-pin name hangs `spawn` inside Git instead of being refused (robustness; claim mismatch on the "reported" wording)

- **Claim.** ARCHITECTURE.md:490-496 ("a filesystem symlink or non-regular file at that name
  (`is_foreign_ref`), is reported as `namespace-ref-symbolic`, excluded from every per-worker view");
  README.md:335-339 (allocation refuses occupied names).
- **What the code does.** `allocation_evidence` calls `resolve_ref` → `git rev-parse --verify` on the
  base-pin name *before* any `lstat`-based check; Git's files backend opens the loose file with `open(2)`,
  which blocks forever on a FIFO with no writer. `is_foreign_ref` (repository.py:656-660) also asks Git
  (`symbolic-ref`) before its own `lstat` (`loose_ref_occupant`), so the write-path guard cannot help
  either. `for-each-ref` skips non-regular entries, so `raw_ref_inventory` and therefore `status` and
  `recover` do not hang.
- **Reproduction.** `/tmp/clonegrown-review3-probes/p5_fifo.py` → `p5.out`: `git rev-parse --verify`,
  `git symbolic-ref`, and `git update-ref` on the name all time out (15 s); `clonegrown status` and
  `recover` return 0 and report `orphan-namespace-ref` (not `namespace-ref-symbolic`); `clonegrown spawn`
  times out with `next_id` unchanged and the FIFO intact (the first run of `p2_occupants.py` sat for 5 min
  48 s in `git --git-dir=/dev/fd/3 rev-parse --verify --quiet refs/cws/<ws>/bases/1^{commit}` until killed;
  `p2-partial-with-fifo.out`).
- **Affected files.** `clonegrown/worker.py:675-680`, `clonegrown/repository.py:656-660`.
- **Classification.** Low. Nothing is written, replaced, deleted, or consumed; the hang is Git's, but the
  product promises refusal-and-report for non-regular occupants and has the `lstat` primitive to deliver it
  before asking Git. Also a wording nit: a FIFO, directory, or non-ref file is reported as
  `orphan-namespace-ref`, not `namespace-ref-symbolic` as ARCHITECTURE.md:494-495 says.

### Informational (not findings)

- **Directory refusal wording.** The base-pin refusal for a directory occupant reads "refusing to touch a
  symbolic ref in Clonegrown's namespace" (`_refuse_symbolic`); the occupant is a directory.
- **Collect with a garbage file at an unrelated owned name.** A non-ref loose file at the base-pin or
  branch-owner name makes `collect` fail inside `git fetch` ("bad object refs/cws/…"); the worker returns to
  `ready` and the file is untouched (`p2.out` `B_*_base_pin_garbage`, `B_*_branch_owner_garbage`). Fail-closed,
  but the refusal comes from Git, not from a Clonegrown check.
- **Retained result through a symlink.** A filesystem symlink pointing outside `refs/` at the
  `results/<sha>` name of a collected worker satisfies `ref_points_at` (Git reads the target file), so a
  flagless discard proceeds; the link and its target are untouched and `status`/`recover` report
  `namespace-ref-symbolic` for the name (`C_clone_results_sha_fs_link_outside`). The other occupant kinds at
  that name are refused ("collected result is not preserved").
- **Direct ref at the summary name.** A direct ref planted at `workers/<id>/result` is treated as a previous
  summary and moved to the accepted result (`p2b.out` `B2_clone_summary_loose_direct`, `packed_direct`); the
  summary is the documented mutable pointer, so this is by design.
- **Empty directories** at owned names are removed by Git when the ref is created (see R2 note) and, at the
  summary name during recovery, replaced (`p6.out` `E_collecting_summary_dir_empty`).

## 3. Verification record

### N1 — worker-local grafts / replace refs (`p1_ancestry.py` → `p1.out`). CLOSED, with adjacent gap R1.

Clone mode: a `refs/replace/<orphan>` ref (`1_replace_clone`) and an `info/grafts` file (`1_grafts_clone`)
planted in the worker make ambient `merge-base --is-ancestor` return 0 while `collect` is refused with
"does not descend" before any fetch (no summary ref, record `ready`); `--allow-rewrite` collects with
`allow_rewrite: true` and clean `status`. Worktree mode: the replace ref lands in canonical's shared
`refs/replace/` and the grafts file in canonical's `.git/info` (`1c_worktree_*`) — both fool ambient Git in
both repositories and both are refused by Clonegrown. Inherited `GIT_GRAFT_FILE`, `GIT_REPLACE_REF_BASE`,
and `GIT_CONFIG_COUNT` injection of `core.useReplaceRefs` through the CLI are stripped and refused
(`1d_env`). Canonical's own replace ref or grafts file — with the orphan object present in canonical — do
not help either (`1g_canonical_*`, `p1g.py`). A shallow file in the worker can only hide ancestry: cutting
the tip refuses, cutting the base collects (`1e_shallow`). A graft planted after a legitimate collection
produces no drift and no issue and does not block a flagless discard (`1h`; a graft is a non-ref `.git`
change, outside the stated baseline). A forged loose parent object in a strong clone fools ambient Git *and*
`is_ancestor` inside the worker but the fetch fails with Git's "hash mismatch" (`1f_forged_*`); the variant
in which the candidate already exists in canonical is R1 (`p1b.out`).

### N2 / N3 — foreign occupants of owned ref names (`p2_occupants.py` → `p2.out`; `p2b_clone_direct.py` → `p2b.out`; `p6_recover_occupants.py` → `p6.out`; `p5_fifo.py` → `p5.out`; rerun of the fourth review's `pC_namespace.py` → `rerun-pC_namespace.out`). CLOSED for the two proven roots, with adjacent gaps R2–R4.

Twelve occupant kinds (dangling symbolic ref, live symbolic ref, filesystem symlink with `refs/heads/main`
text, absolute symlink into `refs/`, absolute symlink to an external file, dangling symlink, non-ref file,
non-empty directory, empty directory, loose direct ref, packed direct ref, packed ref shadowed by a dangling
symbolic ref) × five names (base pin, branch-owner, summary, `results/<sha>`, task branch) × allocation in
clone and worktree mode: every non-directory occupant is allocation evidence (`next_id` unchanged, no record,
no pin, bytes identical), and `status` reports it beforehand as `namespace-ref-symbolic` (symbolic refs and
links) or `orphan-namespace-ref` (non-ref files, directory children). The fourth review's exact roots are
closed: the non-ref file at the base-pin name is "base ref file" evidence with `next_id` 1 and no record
(`A_*_base_pin_garbage`; `rerun-pC` `C2_garbage_at_base_pin_name`), and the outside-`refs/` symlink at the
summary name is refused by `collect` with the link and its target intact (`B_*_summary_fs_link_outside`;
`rerun-pC` `C3_fs_symlink_at_summary_outside_refs`). At collect (both modes) every occupant at the summary
and `results/<tip>` names is refused and left byte-for-byte, the worker returns to `ready`, `status`
reports it, and `recover` leaves it (`B_*`; the nine clone rows whose planting needed an object canonical
holds are in `p2b.out`: a direct ref at another value at `results/<tip>` is "conflicting result ref …
found …" and preserved). At recovery of a `collecting` record, every occupant at the `results/<sha>` and
summary names is left untouched and the worker resets to `ready` (`p6.out`, 24 rows; the exact-value direct
ref cases finish, as designed). At discard, occupants at base pin and (clone) branch-owner are never touched
and the worker is deleted normally; occupants at `results/<sha>` refuse deletion ("collected result is not
preserved") except the outside-`refs/` symlink noted above; at the summary name discard proceeds and the
occupant survives (`C_*`). At discard of a worktree worker, an occupant at the branch-owner name leaves the task branch retained with
`branch_cleanup_left: "its ownership ref is a symbolic ref, which is not ours"` (or "no ownership ref proves
this worker created it" for a non-ref file), record `discarding`, occupant intact (`C_worktree_branch_owner_*`).
`recover` on a collected worker with occupants leaves every one untouched: summary occupants are
`summary-ref-symbolic-left` / `orphan-namespace-ref-left`, `results/<sha>` occupants mark the worker `broken`
("preserved result ref missing", since the real result is gone), and a base pin at the recorded base is dropped
(`base-ref-dropped`, documented) (`D_*`). Retention held in every discard row: the packed summary and
`results/<sha>` entries survive in `packed-refs` after `discarded` (the `packed-refs` rewrites seen are the
worker's own branch/owner deletions). Packed vs loose: a packed direct ref and a packed ref shadowed by a loose
dangling symref behave like their loose forms. Gaps: directories (R2), the task-branch name at discard (R3), FIFOs (R4).

### Wording notes (`p3_wording.py` → `p3.out`; `p3e.py` → `p3e.out`; `p4_spot.py` → `p4.out`). CLOSED except where R2–R4 apply.

- Quarantine re-authorization: clone — `discard` with no flag names `--force`; `--force` names
  `--discard-ignored`; `--force --discard-ignored` names `--discard-private-refs` (`refs/local/planted`);
  the two category flags without `--force` name `--force`; all three delete (`3b_clone_sequence`).
  Worktree — the same minus the private-ref step (`3b_worktree_sequence`). One missing category per call, as
  README.md:412-415 and ARCHITECTURE.md:833-837 state.
- Unreadable quarantined checkout: clone with `.git/HEAD` removed — every combination including `--abandon`
  is refused ("not a non-bare Git working tree"), `recover` reports `quarantine-preserved`, the quarantine
  stays (`3a2_clone_unreadable`); worktree whose admin directory was pruned — `--force` is refused naming
  `--discard-ignored`, `--force --discard-ignored` deletes (`3a2_worktree_unreadable`). Matches
  README.md:415-418 and ARCHITECTURE.md:838-842 exactly.
- `clone.defaultRemoteName = upstream` in the user's global config: clone spawn fails closed with "local
  clone did not create its source remote", record `spawn_failed`, no slot, no stage residue, no status issue;
  a worktree spawn under the same config succeeds (`3c_*`). Matches ARCHITECTURE.md:718-721.
- Git environment: a logging `CLONEGROWN_GIT` wrapper across init, clone and worktree spawn, two collects,
  two releases, status, recover, and two discards (515 Git invocations) under 60 hostile names at once shows
  only `GIT_AUTHOR_NAME`, `GIT_COMMITTER_EMAIL` (allowlisted identity), `GIT_TERMINAL_PROMPT=0`,
  Clonegrown's own `GIT_GRAFT_FILE=/dev/null` on its ancestry calls, and the unrelated `PROBE_UNRELATED`
  reaching Git (`3d_env`); all eleven operations exit 0. Matches ARCHITECTURE.md:701-710. The rerun of the
  fourth review's `pA_env.py` agrees (490+ invocations, `A1_*`).
- Ancestry wording (README.md:465-471, ARCHITECTURE.md:711-717): true for `collect`; not true for
  `recover` (R1).
- Foreign-occupant wording (ARCHITECTURE.md:490-496): true for symbolic refs and symlinks; a FIFO,
  directory, or non-ref file is reported as `orphan-namespace-ref`, not `namespace-ref-symbolic` (R4 nit).
- The public notices (README.md:17-34, SKILL.md:14-25, ARCHITECTURE.md:6-16) now describe the second,
  third, and fourth reviews' findings as repaired and say a fresh no-open-finding review and hosted CI are
  still required. Accurate.
- Stated boundaries observed as stated: pseudo-refs outside `refs/` are not in the private-ref baseline
  (`rerun-pD` `F5_pseudo_ref_orig_head_flagless_discard`: an `ORIG_HEAD`-only commit is deleted by a flagless
  discard; README.md:422-424); a symlinked parent of the selected workspace is followed (README.md:343-345);
  the four control subdirectories exist before a dangling `state.json` is refused (ARCHITECTURE.md:637-641,
  `rerun-pD` `class3`).

### F1–F5 (third review). CLOSED.

F1 (`GIT_*` overrides): allowlist proven above (`3d_env`, `rerun-pA_env`). F2 (quarantine
re-authorization skips the ignored category): both modes re-ask it (`3b_*`, `rerun-pB_reauth`
`B_*1_sequence`). F3 (dangling symbolic refs at branch-owner/results/result invisible): all are
`namespace-ref-symbolic` with the worker `id` and are allocation evidence (`A_*_dangling_symref`,
`rerun-pC` `C1_*`). F4 (stale statements): none of the quoted pre-repair sentences remains (grep for
"current CLI adapter", "does not preserve that lexical", "currently consults", "resolves that option
before", "detects changed direct", "every resolvable non-task", "same resolvable ref" finds nothing; the
replacement sentences match `rerun-pD` `class4`/`class6`/`class1`). F5 (boundaries stated literally): all
three sentences are present and observed (above).

### Six second-review classes (rerun of `pD_classes.py` → `rerun-pD_classes.out`, plus `rerun-pB`, `rerun-pC`). All PASS.

1. Dangling symbolic clone-private ref after publication → refused naming the ref, bytes intact, deleted
   only with `--discard-private-refs`; retargeted baseline symref refused (`class1_private_refs`).
2. Dangling symbolic task-branch name → worktree spawn refused, `next_id` 1, no record, bytes intact; the
   same in `A_worktree_task_branch_dangling_symref` and after `pack-refs` (`rerun-pC` `C4`).
3. Dangling `state.json`, worker-record, and request-index links → refused, nothing replaced,
   `next_id` unchanged (`class3_control_links`).
4. CLI `init --workspace <symlink>` in absolute, relative, and default-name forms → exit 2 with the API's
   message, link and target intact, no canonical marker (`class4_cli_init_symlink`).
5. `GIT_CONFIG` alone and `GIT_CONFIG_COUNT` injection → spawn succeeds (`class5_git_config`).
6. Rewrite refused by default, accepted with the flag, repeated with and without the flag as a no-op with
   `allow_rewrite: true`; a new commit after collection refused under either argument
   (`class6_recollect_rewrite`; `rerun-pA` `A2_*`).

### Step 7.5i collection-timing properties (`/tmp/clonegrown_probe_collection_timing.py` → `rerun-timing.out`). All five hold.

Direct conflict preserved at the planted value with the worker `ready`; symbolic exact conflict refused
with the symref target intact; result and summary move attempts both rc 128 while the prepared transaction
held the locks, record `collected` with both refs at the candidate; object-only recovery published through
one all-zero expected-old `write_ref` and reported `collect-finished`; a conflicting recovery ref stayed
at the planted value and the worker reset `ready`.

## 4. Coverage-map spot checks

| Item | Result |
|---|---|
| 5.1 active-writer race / 7.5i | Timing probe 5/5 (above); occupants at the summary and result names during collect and during recovery are refused or left untouched (`p2.out` B rows, `p6.out`). Gap: recovery's ancestry judgement (R1). |
| 5.2 ignored work | First authorization names count and sample; re-authorization re-asks in both modes (`p3.out` `3b_*`). |
| 5.3 unchecked deletion | Quarantine, recheck, preserved-on-change, `recover` preserves, errors-enabled deletion observed in every `p3` re-authorization case and `rerun-pB`. |
| 5.4 branch ownership | Create-only transaction refuses direct, packed, live- and dangling-symbolic, symlink, and non-ref occupants (`A_worktree_task_branch_*`); non-empty directory consumes the ID first (R2); cleanup deletes a symbolic occupant (R3). |
| 5.5 changed published recovery | `recovery.py:217-248` preserves divergence as `broken`; `test_worktree` / `test_parent_interruption` passed in the suite; not separately probed. |
| 5.6 installer root | `sh -n install.sh` OK; the 25 `test_installer` tests passed in the suite; not hand-probed. |
| 5.7 / 5.8 remotes and config | `_canonicalize_remote_url` and `ConfigOccurrence(value=None)` read; `test_repository` passed; a credentialed remote is copied verbatim into a clone (`p4.out` `5.10_redaction`, `copied_verbatim: true`). |
| 5.9 Git sanitation | Allowlist proven across 515 invocations including a custom `CLONEGROWN_GIT` (`3d_env`). |
| 5.10 secret-bearing errors | `CommandFailure` for `git fetch creds` (URL `https://user:s3cretpass@example.invalid/…`) shows `git fetch creds` and `https://example.invalid/repo.git/` with no `s3cretpass` (`p4.out` `5.10_redaction`). |
| 5.11 stale request reuse | Same request ID + same params → same worker; different params refused (`5.11_request_reuse`); discarded worker with deleted result ref refused on retry, `result-ref-missing` / `discarded-result-missing` (`rerun-pE` `5.11_discarded_result_deleted`). |
| 5.12 incomplete status | The 28 issue codes in `audit.py`/`recovery.py` equal the 28 enumerated at ARCHITECTURE.md:604-615 (`rerun-pE` `5.12_codes`, `in_code_not_doc: [] / in_doc_not_code: []`). Gaps: a symbolic ref at a live worktree task-branch name has no issue code (R3); a FIFO is `orphan-namespace-ref` (R4). |
| 5.13 create-only allocation | Rewound counter → "already has a record, slot directory, operation lock file; nothing was changed" (`rerun-pE` `5.13_*`); 105 of 117 occupant rows consume nothing (R2 for the 12 directory rows). |
| 5.14 API/CLI parity | API `spawn(ws, "HEAD", task)` → `strong: false, mode: clone`; CLI identical; `strong=True` + worktree refused by both (`p4.out` `5.14_parity`). |
| 5.15 invalid generated branch | `x.lock` → "generated task branch is invalid for Git", `next_id` unchanged, no `refs/cws/` refs, no record (`5.15_x_lock`). |
| 5.16 low-level errors | Every `init/spawn/collect/discard/recover` refusal in every probe carried the five-part context (`5.16_context` checks all five markers on `collect 999`). |
| 5.17 timing gate | No `ratio` assertion in `hardening_suite.py` (`grep ratio` finds none); `parallel_spawns_unique` passed in both modes. |
| 5.18 one-shot | `--abandon` and `claim` refused for a collected worker; leased discard refused whatever the flags (`5.18_one_shot`). |
| Comment/public overclaims | Notices current; boundaries stated (section 3). Stale wording: R1 (recovery), R2/R3 (allocation and task-branch claims), R4 (issue code). |
| `CWSError`, heartbeat, failpoints | `grep -rn CWSError clonegrown/` finds nothing; `heartbeat` appears only as a hidden bookkeeping key in `cli.py:31`; `failpoint` is gated on `CLONEGROWN_TEST_MODE == "1"` (`core.py:485`). |
| retention, teardown, license, package | `pyproject.toml`: `license = "Apache-2.0"`, `license-files = ["LICENSE"]`, `requires-python = ">=3.11"`, dynamic version `0.1.0a1`. Wheel built from an out-of-checkout copy: `clonegrown-0.1.0a1-py3-none-any.whl`, 97,451 bytes, sha256 `a27f54bfc283f2280f5896efb6bf6d3de1fa1860d47c107c87086758f8a2da2e`, `License-Expression: Apache-2.0`, `licenses/LICENSE` present; installed into a fresh venv, both `clonegrown --version` and `python -m clonegrown --version` print `clonegrown 0.1.0a1`. Retention: `finish_deletion` leaves result and summary refs and the record (`C_*` rows keep `results/<sha>` after `discarded`). |
| macOS, Python/Git versions, filters/LFS, resource boundaries, repository diversity, repeated verification, auxiliary-ref cost | Not freshly exercised (section 6); the unit suite's `test_filters_and_resources`, `test_auxiliary_refs`, `test_campaign_records`, and `test_lease` passed. |

## 5. Gate results

- **Unit suite:** `python3 -m unittest discover -s tests -v` → **Ran 273 tests in 485.302 s, OK**
  (273 `ok`, 0 failures, 0 errors, 0 skipped; `/tmp/clonegrown-review3-unittest.log`; ran concurrently
  with the first probes).
- **Hardening, clone mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`: "git lacks
  reftable support"), **0 failed**; sum of case seconds 98.4; wall 21:02:45 → 21:04:32 (1 min 47 s);
  `sha256 5eb355505e7047b7bb25c40a23a2cd972e2819bc67afee544f37af5c7d45440b
  /tmp/clonegrown-review3-hardening-clone.json` (log `…-hardening-clone.log`).
- **Hardening, worktree mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`), **0
  failed**; sum of case seconds 98.4; wall 21:05:30 → 21:07:16 (1 min 46 s);
  `sha256 9333ebfddc7bda798e87e28989127222f90f2d78ead0f9eb4cc0d87039a106ba
  /tmp/clonegrown-review3-hardening-worktree.json` (log `…-hardening-worktree.log`).
- `git diff --check` clean; `sh -n install.sh` OK; `python3 -m compileall clonegrown tests` OK with
  `PYTHONPYCACHEPREFIX=/tmp/clonegrown-review3-pyc`; wheel build and isolated install OK (above).
- Versions: CPython 3.12.3, Git 2.43.0 (`/usr/bin/git`), Linux 6.17.0-35-generic.
- Tree fingerprint start `cc48f892502fe5d2ebfbe1e25abfd24b2eb7f6b7561994b465569ca32e0b80ef`, end
  `d04b332a0c24cc6401419fd5c445c80f7c2ec4e6a15398b1e23a833ef882957a` (only `PLAN.md`/`HANDOFF.md` differ, see the
  header); `git status --short` 23 entries at both ends; no `build/`, `dist/`, or `egg-info`
  inside the checkout.

## 6. Not verified, and why

- Hosted CI on a pushed revision, macOS, CPython 3.11, exact Git 2.29.0: not available locally; the tree is
  uncommitted.
- reftable repositories and `GIT_REF_FORMAT` end to end: Git 2.43 cannot create them (hardening skip); the
  `inventory is None` fallbacks in `raw_ref_inventory` / `NamespaceRefs` / `allocation_evidence` were read,
  not exercised.
- Random-kill and state-machine campaign seeds, `real_repository_qualification.py`, and the benchmark
  harnesses: not in the requested gate list and not run.
- FIFO occupants at names other than the base pin (R4 was proven at the base pin; the summary-name variant
  of `p5_fifo.py` could not run because the killed `update-ref` left a lock file in that disposable
  repository).
- A forged *commit-graph* file as a second worker-side lie for R1: not attempted; the loose-object forgery
  proves the class.
- Genuine disk/inode exhaustion, network filesystems, Git LFS, native Windows: stated boundaries, not
  exercised.
- `HANDOFF.md` and the Step 7.5a–7.5v completion records: deliberately not read.

Probe inventory: `/tmp/clonegrown-review3-probes/{h3,p1_ancestry,p1b_forged_recovery,p1g,p2_occupants,p2h,
p2b_clone_direct,p3_wording,p3e,p4_spot,p5_fifo,p6_recover_occupants}.py` with outputs `*.out` / `*.err`,
`rerun-*.out` for the fourth review's probes, and `rerun-timing.out`; disposable repositories under
`/tmp/clonegrown-review3-work/`.

## Sixth fresh review (fourth Step 7.5 pass, after Steps 7.5w–7.5z): no-go

A sixth fresh reviewer found R1–R4 and every earlier finding closed, the
suite 277/277, both hardening modes clean, and the 29 issue codes equal
between the architecture and the code, and returned no-go on one Low
finding plus informational wording notes:

1. **Q1 (low, claim mismatch).** Four paths still handed an owned ref name
   to Git before the `lstat` inspection: `ref_points_at` had none,
   `resolve_ref` let a symlink through, the collected-repeat `collect` path
   opened the summary inside its prepared transaction, and a worktree
   worker's own Git commands resolved `HEAD` through a foreign task-branch
   name. A FIFO, or a symlink to one, planted at a collected worker's result,
   summary, or base-pin name, or at a live worktree worker's branch name,
   therefore hung `status`, `recover`, `collect`, `discard`, or a request
   retry inside Git. Nothing was written, replaced, deleted, or consumed.
   Step 7.5aa owns it.
2. Informational: the canonical-side ancestry judgement protects only where
   canonical's objects are physically separate (shared-store boundary of
   worktree and default-clone modes); a FIFO or directory at a recorded
   worker's pin or summary name was reported twice, once mislabelled; an
   empty directory at a ref-shaped name was invisible to `status`; the
   branch-owner retention text said "symbolic ref" for any occupant. Step
   7.5aa owns the wording.

The reviewer's full report is preserved verbatim below.

---

# Clonegrown final cold review — release qualification (sixth fresh review)

Date: 2026-09-02. Reviewer: fresh agent, read-only on `/home/serrecchia/Projects/clonegrown` (uncommitted
working tree on `main`, base `c9728a0`). Environment: Linux 6.17.0-35-generic, CPython 3.12.3, Git 2.43.0
(`/usr/bin/git`). Every probe, log, and result lives outside the checkout under `/tmp/clonegrown-review4-*`.
`HANDOFF.md` and the Step 7.5a–7.5z completion records were not read; no `.env`-pattern file was opened;
nothing inside the checkout was modified (the wheel was built and the authoritative unit-suite run was made from
`rsync` copies under `/tmp/clonegrown-review4-build/`, proven byte-identical to the checkout by a full sha256
listing; no `build/`, `dist/`, or `egg-info` exists in the checkout).

**Tree fingerprints.** `git diff | sha256sum` at start:
`67e4de366535d1154aad01d2fc456322b6fd6daf26f7c3d58bcb2840eb16cd35`; at end:
`1a1fb2e30546748f92719d67c6c6e9c948f0bfdc76c45054d21a274fb80581c3`. `git status --short` lists the same 23 entries
at both ends. **The tree changed under review, but not the product:** only `PLAN.md` and `HANDOFF.md` were rewritten
by another session at 21:54:08 (the PLAN step list is unchanged: 7.5a–7.5z plus 7.5, 1079 lines). Every product
module, test, and public document kept its pre-review mtime (18:14–21:44) and hash (sha256 prefix): audit
`606f2e01`, cli `a309e205`, core `fc2af01a`, lifecycle `f449d978`, recovery `878da4ff`, repository `a11a348f`,
state `043a08cd`, worker `fc4f4d1e`; README `af8f0efa`, SKILL `b1b2789e`, ARCHITECTURE `878e9630`. Every probe and
gate below ran against that fingerprinted product (review start 21:48:43).

## 1. Verdict: NO-GO

The fifth review's R1, R2, R3 and R4 are closed on this tree and every closure held under adjacent probes; the
fifth review's wording notes, the fourth review's N1–N3, the third review's F1–F5, the six second-review classes,
and the Step 7.5i collection-timing properties all hold; the full unit suite (277/277), both hardening modes
(56 pass / 1 conditional reftable skip / 0 fail each), `git diff --check`, `sh -n install.sh`, out-of-checkout
byte compilation, the 28+1 issue-code equality, and a wheel build + isolated install all pass.

Release is blocked by one open Low finding, adjacent to R4 and of exactly the class the fifth review named: the
architecture now states that "every owned ref name is `lstat`-inspected before any Git command reads it … none is
ever opened by Git (a FIFO would block it)" and that a live worktree worker with a foreign task-branch name "is
reported as `task-branch-foreign`". Three product helpers still hand an un-inspected owned name to Git —
`ref_points_at` (no `lstat` at all), `resolve_ref` (inspects, but lets a *symlink* through), and the prepared
summary transaction on the collected-repeat path — and the worktree worker's own Git commands resolve its `HEAD`
through the task-branch name. A FIFO, or a symlink whose target is a FIFO, planted at the `results/<sha>`,
summary, base-pin, or task-branch name therefore hangs `status`, `recover`, `collect`, `discard`, and a
request-ID retry inside Git instead of being reported and refused. Nothing is written through, replaced,
deleted, or consumed in any row (every occupant and its target byte-for-byte intact; `next_id` unchanged), so
the severity is Low, but the instructions permit GO only with no open finding of any severity that contradicts a
public claim, and this one contradicts ARCHITECTURE.md:724-733 directly. Everything else I found is informational
(stated boundaries or wording precision) and is listed as such.

## 2. Findings, ranked by severity

### Q1 — Low — un-inspected Git reads of owned ref names: a FIFO, or a symlink to a FIFO, planted at `results/<sha>`, the summary, the base pin, or a live worktree worker's task-branch name hangs `status`/`recover`/`collect`/`discard`/request retry inside Git (claim mismatch; same class as R4)

- **Claim.** ARCHITECTURE.md:724-733 ("Every owned ref name is `lstat`-inspected before any Git command reads it
  (`loose_ref_occupant`): a filesystem symlink is a foreign occupant … a directory, FIFO, or other non-regular
  file … none is ever opened by Git (a FIFO would block it), written through, replaced, or deleted … A live
  worktree worker whose task-branch name holds a symbolic ref or foreign ref file is reported as
  `task-branch-foreign`"); README.md:198-206 (`status` "audits … and lists each disagreement under `issues`");
  Step 7.5x's own bullets (`resolve_ref` "treats a non-regular occupant as absent without opening it"; "no Git
  command opening it").
- **What the code does.** Four paths reach Git before, or instead of, the `lstat` question:
  1. `repository.ref_points_at` (repository.py:935-944) runs `git rev-parse --verify <ref>^{commit}` with no
     `loose_ref_occupant` call at all. Call sites: `audit_worker` (audit.py:166, every `status` of a collected or
     discarded worker), `_recover_collecting` (recovery.py:257, 268), `_recover_collected` (:407),
     `_recover_tombstone` (:438), `authenticate_settled` (worker.py:736, 740, the request-ID retry path),
     `_authorize_discard` (lifecycle.py:1197), `_publish_result_ref` (lifecycle.py:712).
  2. `repository.resolve_ref` (repository.py:808-820) refuses only `"special"`; a `"link"` occupant is passed to
     `rev-parse`, which follows the link (Git's files backend: `lstat` → `readlink` → target not under `refs/` →
     `open(2)`), so a symlink to a FIFO blocks. Reached by `drop_stale_base_pin` (recovery.py:142, every `recover`
     of a worker past spawn), `_authorize_discard` (lifecycle.py:1234, worktree branch tip), and
     `result_ref_transaction` (repository.py:830).
  3. The collected-repeat path of `collect` (lifecycle.py:751-771) calls `result_ref_transaction(update_summary=True)`
     without the `_require_plain_refs` guard the `ready` path has at :777; the prepared `git update-ref --stdin`
     takes both locks and reads the summary's old value — opening the FIFO — before the raw-type check inside
     the transaction can run. The hung process, once killed, leaves `result.lock` and `results/<sha>.lock`
     behind, and every later collect fails with Git's "Another git process seems to be running".
  4. For a live worktree worker, `audit_worker` does compute `task-branch-foreign` (audit.py:181-183, `lstat`
     first), but `status` then runs `snapshot_worker` (recovery.py:656 → `git status` in the worker, whose `HEAD`
     resolves through `refs/heads/<branch>` in canonical's shared refs) and blocks, so the issue is never printed;
     `_recover_ready` runs `git rev-parse refs/heads/<branch>^{commit}` (recovery.py:391) with no guard;
     `discard --abandon` records `discarding` intent first (lifecycle.py:1062-1070) and then blocks in
     `custody_fingerprint`, leaving the record `discarding` with a dead owner.
- **Reproduction.** `/tmp/clonegrown-review4-probes/q2_fifo.py` → `q2.out` (groups A–C), `q2b_fifo_rest.py` →
  `q2b.out` (groups D–F), `q3_attribution.py` → `q3.out`; every CLI call in its own session under a 10–20 s
  timeout, `TIMEOUT` = a Git child blocked in `open(2)`. Rows (clone mode unless stated):
  - `A_collected_results_fifo`, `A_collected_results_link_fifo`: FIFO / symlink→FIFO at `results/<sha>` of a
    collected, released worker: `status`, `recover`, `collect` (repeat), `discard`, `discard --force` all
    `TIMEOUT`; record stays `collected`; occupant and external FIFO intact.
  - `3_tombstone_results_fifo` (`q3.out`): same name for a normally discarded worker with a request ID: `status`,
    `recover`, and `spawn --request-id <same>` all `TIMEOUT` (`authenticate_settled`).
  - `F_collecting_candidate_fifo` / `_link_fifo`: a `collecting` record (interrupted at `collect.after_mark`) with
    the occupant at its candidate name: `status` returns 0 (the record is not yet collected) but `recover`
    `TIMEOUT`s in `_recover_collecting`.
  - `A_collected_base_pin_link_fifo`: symlink→FIFO at the base-pin name of a collected worker: `status` 0,
    `recover` `TIMEOUT` (`drop_stale_base_pin` → `resolve_ref`); the plain FIFO variant is handled
    (`A_collected_base_pin_fifo`: all five operations return).
  - `A_collected_summary_fifo` / `_link_fifo`: FIFO / symlink→FIFO at the summary name of a collected worker:
    `status`, `recover`, `discard` return (discard completes, occupant intact — by design, the summary is
    repairable), but the repeat `collect` `TIMEOUT`s in `git update-ref` and leaves
    `refs/cws/<ws>/workers/1/result.lock` and `…/results/<sha>.lock` (`lock_files_left`; reproduced directly in
    the q3b run: `result_ref_transaction(update_summary=True)` → `TIMEOUT`, then the CLI collect fails with
    "Another git process seems to be running"). For a *ready* worker the same occupants are refused before any
    Git command (`B_ready_summary_*`, `B_ready_results_*`: `collect` rc 2, `status`/`recover` 0 — the 7.5x claim
    holds there).
  - `C_ready_worktree_task_branch_fifo` / `_link_fifo`: FIFO / symlink→FIFO at a live worktree worker's
    `refs/heads/<branch>`: `status`, `recover`, `collect`, `discard --abandon` all `TIMEOUT`; plain
    `git --no-optional-locks status` in the worker also `TIMEOUT`s (`C_worktree_task_branch_*_git_status_in_worker`);
    after the FIFO case the record is left `discarding` (intent recorded, then the hang), after the link case
    `ready`. `D_collected_worktree_task_branch_*`: `status`, `discard`, `discard --force` `TIMEOUT`, `recover`
    returns 0 (a collected worker's recovery does not touch the branch).
  - Attribution (`q3.out`): for the FIFO, `loose_ref_occupant` = `special`, `is_foreign_ref` = `True`,
    `resolve_ref` = `None`, **`ref_points_at` = `TIMEOUT`**; for the symlink→FIFO, `loose_ref_occupant` = `link`,
    `is_foreign_ref` = `True`, **`resolve_ref` = `TIMEOUT`, `ref_points_at` = `TIMEOUT`,
    `result_ref_transaction` = `TIMEOUT`**. Direct Git on the names: `rev-parse` and `symbolic-ref` `TIMEOUT`,
    `for-each-ref` 0 (skips non-regular entries), which is why the inventory-driven checks and allocation are
    unaffected.
  - What is *not* affected (R4's fix holds): allocation with a FIFO or symlink→FIFO at the next ID's base-pin or
    task-branch name is refused before any Git read ("occupied by a non-regular file" / "by a symlink"),
    `next_id` 1 → 1, no record, occupant intact, `status`/`recover` return and report (`E_alloc_*`, six rows;
    rerun of the fifth review's `p5_fifo.py`); a FIFO/symlink→FIFO at the branch-owner name of a live or
    collected worktree worker returns everywhere and discard retains the branch with `branch_cleanup_left`
    (`C_*_branch_owner_*`, `D_*_branch_owner_*`).
- **Affected files.** `clonegrown/repository.py:808-820` (`resolve_ref` link case), `:935-944` (`ref_points_at`),
  `:823-844` (transaction before the raw-type check); `clonegrown/lifecycle.py:751-771` (no `_require_plain_refs`
  on the collected-repeat path), `:1234`; `clonegrown/recovery.py:142, 257, 268, 391, 407, 438, 656`;
  `clonegrown/audit.py:166`; `clonegrown/worker.py:736, 740`; ARCHITECTURE.md:724-733.
- **Classification.** Low claim mismatch (robustness). The precondition is a same-user process planting a
  non-regular file under canonical's `.git/refs` (or, for the task branch, breaking the worker's own `HEAD`
  resolution), which can already do worse; nothing is written, replaced, deleted, or consumed, and the hang is
  Git's. But the product promises, in a sentence added for exactly this class, that the `lstat` question is asked
  before *any* Git read of an owned name, and it is not. A class fix: `ref_points_at` and `resolve_ref` refuse
  both `link` and `special` occupants before running Git (as `is_foreign_ref` already does), the collected-repeat
  collect calls `_require_plain_refs` before its transaction, and the worktree paths check
  `is_foreign_ref(canonical, refs/heads/<branch>)` before any Git command runs inside the worker (`status`,
  `_recover_ready`, `_authorize_discard`), reporting `task-branch-foreign` and refusing instead of hanging.

### Informational (not findings)

- **I1 — Shared object stores defeat the canonical-side ancestry judgement (stated boundary; wording precision).**
  `q1_r1.py` rows `1d_*` and `1e_*`: a *worktree* worker's forged loose parent object lands in canonical's shared
  store (`same_store: true`), and a *default (non-strong) clone* can rewrite a hard-linked loose object in place
  (`hard_linked: true`, `chmod` + open for write); in both, `is_ancestor(canonical, base, X)` becomes `True`,
  `collect` accepts the non-descending result with `allow_rewrite: false`, `status` shows no drift, and
  `fsck --connectivity-only` in canonical still returns 0. README.md:289-292 and :477-482 state that worktrees
  share the object database and that default clones share object files through hard links ("Only `--strong`
  supplies physical object-file independence … neither clone mode is an operating-system sandbox"), so this is a
  stated boundary, not a defect. The ancestry paragraph (ARCHITECTURE.md:716-723, README.md:468-474) describes
  the canonical re-judgement without saying it protects only where canonical's copy is physically separate
  (a strong clone, or objects the fetch actually transfers); one cross-reference would close the reading gap.
- **I2 — Double, mislabelled issue code for a non-regular occupant of a recorded worker's pin or summary name
  (wording).** A FIFO or a non-empty directory at a recorded worker's base-pin or summary name is reported twice:
  `orphan-namespace-ref` from the namespace audit (as ARCHITECTURE.md:726-727 says) *and* `namespace-ref-symbolic`
  from `audit_worker` (audit.py:156-157, 170-171, whose `is_foreign_ref` test is true for `special` too) with the
  text "dangling symbolic ref under this worker's … name", which is false for a FIFO/directory (`q4` run in the
  transcript: `fifo base_pin -> [('namespace-ref-symbolic', 1, "dangling symbolic ref …"), ('orphan-namespace-ref',
  None, …)]`). A non-ref file is reported once, correctly. The occupant is excluded and never touched either way.
- **I3 — An empty directory at an owned name is invisible to `status`.** The raw walk records a directory's
  children, so an empty directory yields no issue for an unrecorded ID (`p5`-style `status` shows nothing), while
  allocation still refuses it as "occupied by a non-regular file" with `next_id` unchanged
  (`rerun-p2_occupants.out` `A_*_dir_empty` rows, `records: []`, occupant intact). ARCHITECTURE.md:726-727 says a
  directory is reported as `orphan-namespace-ref`; that is true only of a non-empty one (via its children). Git's
  own removal of an empty directory when it creates a ref (`A_worktree_branch_owner_dir_empty`,
  `E_collecting_summary_dir_empty`) is, per the instructions, not counted.
- **I4 — Branch-owner retention text.** With a FIFO or symlink at the branch-owner name, cleanup retains the task
  branch with `branch_cleanup_left: "its ownership ref is a symbolic ref, which is not ours"` (`D_*_branch_owner_*`);
  the occupant is not a symbolic ref. Behaviour matches the contract; the text is imprecise.
- **I5 — Discard proceeds past a FIFO at the summary name.** A collected clone with a FIFO at its summary name is
  discarded normally (record `discarded`, occupant intact, `A_collected_summary_fifo`). By design (the summary is
  the repairable pointer; discard authenticates only the immutable result), consistent with the fifth review's
  analysis.
- **I6 — Lock residue after a hung Git is killed.** The `.lock` files in Q1 are Git's own after `SIGKILL`; they
  are a consequence of the hang, not a separate defect.
- **I7 — Unit-suite environment sensitivity (not a product claim).** With `PYTHONPYCACHEPREFIX` exported, two
  installer tests fail (`test_marker_line_definition_is_shared_by_every_ownership_check[long-body/command]`,
  `test_non_utf8_paths_are_preserved_as_filesystem_bytes`: wrapper prints `v1` after the `v2` update) because the
  fixture's `__init__.py` keeps the same size and mtime second across the update, so CPython reuses the v1 bytecode
  cached under the prefix; the installed copy's own `__pycache__` is replaced with the directory, which is why the
  documented configuration passes. Reproduced in isolation on the copy: both tests fail with the prefix (used or
  fresh) and pass without it. The wrapper bootstrap does honour the caller's `PYTHONPYCACHEPREFIX`; a real update
  changes sizes and mtimes, so this is a test-environment note, recorded here so the next reviewer does not
  misread it.
- **I8 — Sequential-probe staleness.** The fifth review's `p3_wording.py` rerun stops at its `3e` planting step
  (`FileNotFoundError`: the branch directory Git removed after the earlier case's cleanup); rows 3a–3d completed
  and `3e` is covered by `p3e.py` (rc 0). `p5_fifo.py` still exits 1 at its summary-name variant for the lock left
  by its own killed `update-ref`, as the fifth review recorded.

## 3. Verification record

### R1 — recovery judges ancestry on canonical's objects (`q1_r1.py` → `q1.out`; rerun of `p1b_forged_recovery.py`). CLOSED.

Strong clone reset to `X` (canonical already holds `X`; `honest: worker_is_ancestor false, canonical false`).
Forged loose parent `S1` with `parent <base>` (`h4.forge_loose_commit`): ambient `merge-base` 0,
`is_ancestor(worker) true`, worker `fsck --connectivity-only` 0. Plain `collect` refused on canonical ("does not
descend"), no summary, record `ready`. Interrupted at `collect.after_mark` (rc 88, record `collecting`,
candidate = `X`) → `recover` reports **`collect-reset-ready`**, record `ready`, `result_sha` null, no summary;
interrupted at `collect.after_fetch` (candidate ref already published) → the same reset; `status` shows only
`candidate-ref-retained` and no drift. `--allow-rewrite` collects honestly (`allow_rewrite: true`). A **forged
commit-graph** (graph written while the forgery was present, then the honest object restored:
`fsck` 16, `commit-graph verify` 1, ambient 0, `is_ancestor(worker) true`) is refused by `collect` and reset by
`recover` the same way (`1c_*`). **`status` drift:** a collected record whose `allow_rewrite` claim is false shows
`drift: "collected result does not descend from its assigned base in canonical"` when the worker's own store lies
(`1b_false_record_status`) and the worker-side refusal text when it does not (`1b2_*`). The fifth review's own
`p1b` rerun agrees (`1b_recover: collect-reset-ready`, `result_sha: null`).

### R2 — directories and FIFOs are allocation evidence (rerun of `p2_occupants.py` → `rerun-p2_occupants.out`, 348 rows; `q2b.out` E rows; rerun `p5_fifo.py`). CLOSED.

No row consumes an ID. A non-empty *and* an empty directory at the base-pin name (clone and worktree) and at the
task-branch name (worktree) are refused with "base ref name occupied by a non-regular file" / "task branch name
occupied by a non-regular file", `records: []`, occupant intact. A FIFO and a symlink→FIFO at either name are
refused the same way with `next_id` 1 → 1 (`E_alloc_*`, six rows; `p5`: `spawn` rc 2, `status`/`recover`
`orphan-namespace-ref`, FIFO intact). Every other occupant kind at every name remains evidence as the fifth review
recorded; the only changed occupants are Git's removal of an empty directory when it creates the branch-owner ref
and the documented base-pin drop / packed-refs rewrite rows the fifth review analysed.

### R3 — a foreign task-branch name is retained by cleanup and reported (rerun of `p3e.py` → `rerun-p3e.out`; `p4_spot.py` `taskbranch_symref_status`; `q2b.out` D rows). CLOSED.

All eight `p3e` rows (symbolic ref to `other` at the tip, symlink with `refs/` text, symlink to an external file,
symbolic ref after `other` moved; with and without `--force`): flagless discard refused by the snapshot; `--force`
deletes the content and stops with "cleanup incomplete (task branch retained: the name now holds a symbolic ref
or foreign ref file, which is not ours)", record `discarding`, `recover` → `worktree-cleanup-conflict`, occupant and
target byte-for-byte intact (`occupant_unchanged: true` in every row, including the outside-`refs/` link that the
fifth review saw deleted flaglessly). A live worktree worker with a symbolic ref at its branch name is reported
`task-branch-foreign` by `status` (`p4`). Gap: when the occupant is a FIFO, `status` hangs before printing it (Q1).

### R4 — FIFO at the base-pin name (rerun `p5_fifo.py` → `rerun-p5_fifo.out`; `q2b.out` `E_alloc_*`). CLOSED at the allocation and audit paths, with adjacent gap Q1.

`spawn` is refused before any Git read, `status`/`recover` report `orphan-namespace-ref`, the FIFO survives; the
symlink→FIFO variant likewise ("occupied by a symlink"). The same FIFO at a *collected* worker's result name, and a
symlink→FIFO at its base-pin name, still reach Git through `ref_points_at`/`resolve_ref` (Q1).

### Fifth review's wording notes (`q1`, `q2`, `q3`, `q4`; reruns of `p3_wording.py`, `p3e.py`, `p4_spot.py`). CLOSED except where Q1 and I1–I4 apply.

- Ancestry judgement at collect, recovery, status: true (R1 above), with the shared-store boundary noted (I1).
- `lstat`-first inspection: true for `loose_ref_occupant`, `is_foreign_ref`, allocation, `resolve_ref` on a
  FIFO, every `status`/`recover` path that goes through the raw inventory or `is_foreign_ref`; false for
  `ref_points_at`, `resolve_ref` on a symlink, the collected-repeat transaction, and the worktree worker's own Git
  (Q1). Issue code per occupant kind: symbolic ref and filesystem symlink → `namespace-ref-symbolic`
  (`rerun-p6`: every symref/link row); non-ref file, directory child, FIFO → `orphan-namespace-ref` (`rerun-p6`
  garbage/dir rows, `p5`), plus the duplicate mislabelled code for a recorded worker's pin/summary (I2) and the
  empty-directory silence (I3).
- Task-branch retention: true (R3).
- Quarantine re-authorization: clone `3b_clone_sequence` names `--force`, then `--discard-ignored`, then
  `--discard-private-refs` (`refs/local/planted`), one category per refusal, then deletes; worktree the same minus
  the private-ref step; unreadable quarantined clone refused under every combination and `recover` reports
  `quarantine-preserved`; pruned quarantined worktree needs `--discard-ignored` then deletes (`3a2_*`). Matches
  README.md:412-418 and ARCHITECTURE.md:846-858.
- Git environment sanitation: `3d_env`: 535 Git invocations across init, both spawns, collects, releases, status,
  recover, discards under 60 hostile names; only `GIT_AUTHOR_NAME`, `GIT_COMMITTER_EMAIL`, `GIT_TERMINAL_PROMPT=0`,
  Clonegrown's own `GIT_GRAFT_FILE=/dev/null`, and the unrelated `PROBE_UNRELATED` reach Git; all eleven
  operations exit 0. `rerun-pA_env` agrees. Matches ARCHITECTURE.md:702-711.
- `clone.defaultRemoteName`: clone spawn fails closed (`spawn_failed`, no slot, no stage, no issue), worktree spawn
  succeeds (`3c_*`). Matches ARCHITECTURE.md:734-737.
- The 28+1 issue codes at ARCHITECTURE.md:604-616 equal the codes emitted by `audit.py`/`recovery.py`:
  29 = 29, `in_code_not_doc: []`, `in_doc_not_code: []` (`task-branch-foreign` present in both).
- Stated boundaries observed as stated: pseudo-refs outside `refs/` are not protected
  (`rerun-pD` `F5_pseudo_ref_orig_head_flagless_discard` deletes an `ORIG_HEAD`-only commit; README.md:422-424);
  a symlinked parent of the selected workspace is followed (`class4` `parent_symlink_followed`); the four control
  subdirectories exist before a dangling `state.json` is refused (`class3`).

### N1–N3 (fourth review). CLOSED.

N1: `rerun-p1_ancestry.out` (19 rows) and `rerun-p1g.out`: replace ref and grafts file in the worker or in
canonical fool ambient Git and are refused by `is_ancestor`/`collect`; environment injection stripped; shallow
boundary only hides; forged object crossing the fetch fails with Git's hash mismatch; plus R1's closure above.
N2/N3: `rerun-p2_occupants` (348 rows, nothing consumed, nothing written through), `rerun-p2b_clone_direct`
(a direct ref at another value at `results/<tip>` → "conflicting result ref already exists", preserved; a direct
ref at the summary is moved by design; a packed ref shadowed by a dangling symref → "refusing to write through a
symbolic ref"), `rerun-p6_recover_occupants` (24 rows: every symref/link/garbage/dir occupant at the candidate and
summary names left untouched, `collect-reset-ready`; exact direct refs finish, as designed),
`rerun-pC_namespace` (rc 0, stderr empty).

### F1–F5 (third review). CLOSED.

F1 (`GIT_*` overrides): `3d_env`, `rerun-pA_env`. F2 (re-authorization skips ignored): `3b_*`, `rerun-pB_reauth`.
F3 (dangling symbolic refs invisible): `rerun-pC` and `p2` dangling-symref rows are `namespace-ref-symbolic` with
the worker id and allocation evidence. F4 (stale statements): grep for "current CLI adapter", "does not preserve
that lexical", "currently consults", "resolves that option before", "detects changed direct", "every resolvable
non-task", "same resolvable ref" finds nothing in README/SKILL/ARCHITECTURE. F5 (boundaries literal): all three
sentences present and observed (above).

### Six second-review classes (rerun of `pD_classes.py` → `rerun-pD_classes.out`, plus `rerun-pB`, `rerun-pC`). All PASS.

1. Dangling symbolic clone-private ref → discard refused, bytes intact, deleted only with
   `--discard-private-refs`; retargeted baseline symref refused. 2. Dangling symbolic task-branch name → worktree
   spawn refused, `next_id` 1, no record, bytes intact; clone spawn of the same name fine. 3. Dangling `state.json`,
   record, request-index links → refused, nothing replaced, `next_id` unchanged. 4. CLI `init --workspace <symlink>`
   absolute/relative/default-name → exit 2, link intact, no marker; parent symlink followed. 5. `GIT_CONFIG` and
   `GIT_CONFIG_COUNT` injection → spawn succeeds. 6. Rewrite refused by default, accepted with the flag, repeated
   with and without the flag as a no-op with `allow_rewrite: true`, new commit refused under either argument,
   result ref still names the accepted tip.

### Step 7.5i collection-timing properties (`/tmp/clonegrown_probe_collection_timing.py` → `rerun-timing.out`). All five hold.

Direct conflict preserved at the planted value with the worker `ready`; symbolic exact conflict refused with the
target intact; result and summary move attempts both rc 128 while the prepared transaction held the locks, record
`collected` with both refs at the candidate; object-only recovery published through one all-zero expected-old
`write_ref` and reported `collect-finished`; a conflicting recovery ref stayed at the planted value and the worker
reset `ready`.

## 4. Coverage-map spot checks

| Item | Result |
|---|---|
| 5.1 active-writer race / 7.5i | Timing probe 5/5; occupants at the summary and result names during collect and recovery refused or left (`rerun-p2` B rows, `rerun-p6`); R1 closed. Gap: Q1 hangs, no custody effect. |
| 5.2 ignored work | First refusal names count and sample; re-authorization re-asks in both modes (`3b_*`). |
| 5.3 unchecked deletion | Quarantine, recheck, preserved-on-change, `recover` preserves, errors-enabled deletion in every `3a`/`3b` row and `rerun-pB`. |
| 5.4 branch ownership | Create-only transaction refuses every occupant kind at allocation (`rerun-p2` `A_worktree_task_branch_*`, `E_alloc_worktree_task_branch_*`); cleanup retains a foreign name (R3) and a foreign owner ref (`D_*_branch_owner_*`). |
| 5.5 changed published recovery | `recovery.py:217-248` preserves divergence as `broken`; `test_worktree` / `test_parent_interruption` pass in the final suite; not separately probed. |
| 5.6 installer root | `sh -n install.sh` OK; all 25 `test_installer` tests pass in the final suite (see I7 for the cache-prefix artifact). |
| 5.7 / 5.8 remotes and config | `_canonicalize_remote_url` / `ConfigOccurrence(value=None)` read; `test_repository` passes; credentialed remote copied verbatim (`rerun-pE` `5.10_remote_copied: true`). |
| 5.9 Git sanitation | 535 invocations, allowlist only (`3d_env`; `rerun-pA_env`). |
| 5.10 secret-bearing errors | `CommandFailure` for `git fetch creds` shows `https://<redacted>@example.invalid/…` and no password (`rerun-pE` `5.10_command_failure_text`, `rerun-p4` `secret_in_error: false`). |
| 5.11 stale request reuse | Same ID + params → same worker; different params refused; discarded worker with deleted result → retry refused, `result-ref-missing` / `discarded-result-missing` (`rerun-pE` `5.11_*`). Gap: a FIFO at that result name hangs the retry (Q1). |
| 5.12 incomplete status | 29 codes in docs = 29 in code (`rerun-pE` `5.12_codes`; my own grep). Gaps: Q1 (hang before reporting), I2/I3 wording. |
| 5.13 create-only allocation | Rewound counter → "already has a record, slot directory, operation lock file; nothing was changed" (`5.13_stale_counter`, records intact); 348 + 6 occupant rows consume nothing. |
| 5.14 API/CLI parity | API and CLI both `mode: clone, strong: false`; `strong=True` + worktree refused by both (`rerun-p4` `5.14_parity`). |
| 5.15 invalid generated branch | `x.lock` → "generated task branch is invalid for Git", `next_id` unchanged, no refs, no record (`5.15_x_lock`). |
| 5.16 low-level errors | Five-part context present on `collect 999` (`5.16_context` all true) and on every refusal quoted above. |
| 5.17 timing gate | No `ratio` assertion in `hardening_suite.py` (grep finds only the word inside `operation`); `parallel_spawns_unique` PASS in both modes (2.45 s / 2.30 s). |
| 5.18 one-shot | `--abandon` and `claim` refused for a collected worker; leased discard refused under every flag (`5.18_one_shot`, `rerun-pE` `5.18`). |
| Comment/public overclaims | Notices current (README.md:17-34, SKILL.md:14-25, ARCHITECTURE.md:6-16 describe the second–fourth reviews as repaired and require a fresh review; the fifth review's notice is in FINAL_COLD_REVIEW.md); boundaries stated. Stale wording: ARCHITECTURE.md:724-733 (Q1); I1–I4. |
| `CWSError`, heartbeat, failpoints | `grep -rn CWSError clonegrown/` finds nothing; `heartbeat` only as a hidden bookkeeping key (`cli.py:31`); `failpoint` gated on `CLONEGROWN_TEST_MODE == "1"` (`core.py:485`). |
| retention, teardown, license, package | `pyproject.toml`: `Apache-2.0`, `LICENSE`, `>=3.11`, version `0.1.0a1`. Wheel from the out-of-checkout copy: `clonegrown-0.1.0a1-py3-none-any.whl`, 98,201 bytes, sha256 `dd3c72f26379554fc5e0e37f549cd47f44b971a8a27d795e3dc21c31587db932`, `License-Expression: Apache-2.0`, `licenses/LICENSE` present; fresh venv install: `clonegrown --version` and `python -m clonegrown --version` both print `clonegrown 0.1.0a1`. Retention: result and summary refs and the record survive discard in every `C_*`/`A_collected_*` row. |
| macOS, Python/Git versions, filters/LFS, resource boundaries, repository diversity, repeated verification, auxiliary-ref cost | Not freshly exercised (section 6); `test_filters_and_resources`, `test_auxiliary_refs`, `test_campaign_records`, `test_lease` pass in the final suite. |

## 5. Gate results

- **Unit suite (authoritative):** `python3 -m unittest discover -s tests -v` on the byte-identical copy
  `/tmp/clonegrown-review4-build/src2` (includes `.git`), no cache prefix → **Ran 277 tests in 347.667 s, OK**
  (277 `ok`, 0 failures, 0 errors, 0 skipped; `/tmp/clonegrown-review4-unittest-final.log`; wall 5 min 48 s).
  Two earlier full runs are recorded for transparency and are environment artifacts, proven in section 2 (I7):
  in the checkout with `PYTHONPYCACHEPREFIX` set → 277 run, 2 installer failures, 302.793 s
  (`/tmp/clonegrown-review4-unittest.log`); on the `.git`-less copy without the prefix → 277 run, 1 failure
  (`test_environment_records_exact_python_git_and_commit_provenance`: no commit SHA without `.git`), 335.129 s
  (`…-noprefix.log`). The suite grew from the fifth review's 273 to 277.
- **Hardening, clone mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`: git lacks reftable
  support), **0 failed**; sum of case seconds 77.6; wall 1 min 24 s;
  `sha256 e78521f127f62fa381c3dd4e1ac9740d87b338f381e309fdef12a15333be3b34 /tmp/clonegrown-review4-hardening-clone.json`.
- **Hardening, worktree mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`), **0 failed**; sum of
  case seconds 74.8; wall 1 min 21 s;
  `sha256 f3f35df7190244f93b88a58c217025465d4b282a4c8c1fde95d9096103084202 /tmp/clonegrown-review4-hardening-worktree.json`.
- `git diff --check` clean; `sh -n install.sh` OK; `python3 -m compileall -q clonegrown tests` OK with
  `PYTHONPYCACHEPREFIX=/tmp/clonegrown-review4-pyc`; wheel build and isolated install OK (above); no `build/`,
  `dist/`, or `egg-info` in the checkout.
- Versions: CPython 3.12.3, Git 2.43.0 (`/usr/bin/git`), Linux 6.17.0-35-generic, pip 24.0.
- Tree fingerprint start `67e4de366535d1154aad01d2fc456322b6fd6daf26f7c3d58bcb2840eb16cd35`, end
  `1a1fb2e30546748f92719d67c6c6e9c948f0bfdc76c45054d21a274fb80581c3` (only `PLAN.md`/`HANDOFF.md` differ, header);
  `git status --short` 23 entries at both ends.

## 6. Not verified, and why

- Hosted CI on a pushed revision, macOS, CPython 3.11, exact Git 2.29.0: not available locally; the tree is
  uncommitted.
- reftable repositories and `GIT_REF_FORMAT` end to end: Git 2.43 cannot create them (hardening skip); the
  `inventory is None` fallbacks were read, not exercised.
- Random-kill and state-machine campaign seeds, `real_repository_qualification.py`, and the benchmark harnesses:
  not in the requested gate list and not run.
- A hand-crafted commit-graph (I built the forged graph from a forged object instead); a socket occupant (a FIFO
  proves the class).
- The fifth review's `p3_wording.py` `3e` rows and `p5_fifo.py` summary-name variant did not complete on rerun
  (I8); both are covered by `p3e.py`, `q2`, and `q3`.
- Genuine disk/inode exhaustion, network filesystems, Git LFS, native Windows: stated boundaries, not exercised.
- `HANDOFF.md` and the Step 7.5a–7.5z completion records: deliberately not read.

Probe inventory: `/tmp/clonegrown-review4-probes/{h4,q1_r1,q2_fifo,q2b_fifo_rest,q3_attribution}.py` with
outputs `q1.out`, `q2.out`, `q2b.out`, `q3.out` (and `*.err`); `rerun_all.sh` with `rerun-*.out`/`.err` and
`rerun.log` for the fourth review's `pA`–`pE`, the 7.5i timing probe, and the fifth review's
`p1`, `p1b`, `p1g`, `p2`, `p2b`, `p3_wording`, `p3e`, `p4`, `p5`, `p6`; disposable repositories under
`/tmp/clonegrown-review4-work/`; suite logs `/tmp/clonegrown-review4-unittest*.log`; hardening logs and JSON
`/tmp/clonegrown-review4-hardening-*`; wheel and venv under `/tmp/clonegrown-review4-build/`.

## Seventh fresh review (fifth Step 7.5 pass, after Step 7.5aa): no-go

A seventh fresh reviewer found Q1 closed at every named path (80-row
matrix), every earlier finding holding, the suite 280/280, and both
hardening modes clean, and returned no-go on:

1. **S1 (medium, in-contract custody defect).** A deletion resumed by
   `recover`, or re-authorized by `discard --force`, deleted a quarantined
   collected worker without rechecking that its immutable result ref was
   still preserved; the last copy of the collected work was deleted and the
   record became `discarded` with `result-ref-missing`. Step 7.5ab owns it.
2. **S2 (low).** Canonical-side `git worktree add/repair/list` and the
   collect fetch resolve every linked worktree's `HEAD`, so a FIFO at one
   worktree worker's branch name hung other workers' collect, worktree
   spawn, discard, and recovery. Step 7.5ab owns it.
3. **S3 (low).** A non-empty directory at a recorded worker's base-pin or
   summary name was still reported as a dangling symbolic ref. Step 7.5ab
   owns it.
4. **S4 (low).** A FIFO or plain file at a container name of the namespace
   made `status` fail with a raw `ENOTDIR` error instead of reporting it.
   Step 7.5ab owns it.
5. Informational: refusal wording ("before a Git command runs in the
   worker"), symlinked container directories followed by Git, and the
   missing worker `id` on `orphan-namespace-ref` reports. Step 7.5ab owns
   the wording.

The reviewer's full report is preserved verbatim below.

---

# Clonegrown final cold review — release qualification (seventh fresh review)

Date: 2026-09-02. Reviewer: fresh agent, read-only on `/home/serrecchia/Projects/clonegrown` (uncommitted
working tree on `main`, base `c9728a0`). Environment: Linux 6.17.0-35-generic, CPython 3.12.3, Git 2.43.0
(`/usr/bin/git`). Every probe, log, wheel, and result lives outside the checkout under
`/tmp/clonegrown-review5-*` (probes and outputs in `/tmp/clonegrown-review5-probes/`, disposable repositories
in `/tmp/clonegrown-review5-work/`). `HANDOFF.md` and the Step 7.5a–7.5aa "Completion record" sections were not
read; no `.env`-pattern file was opened; nothing inside the checkout was modified by this review (the wheel was
built from an `rsync` copy; `compileall` ran with `PYTHONPYCACHEPREFIX=/tmp/clonegrown-review5-pyc`; the unit
suite ran in the checkout without a cache prefix, as CI does).

**Tree fingerprints.** `git diff | sha256sum` at start
`26a601c0992e750e78cfc071a16230f38d2d1d8900f60c52132cf7ff2364367b`, at end
`9075fa64043acf2fac41291bf28e6deebce75169bdddd16f2b386a78dd035847`; `git status --short` lists the same 23
entries at both ends (22 modified tracked files plus untracked `tests/test_collect_policy.py`). The difference is
`PLAN.md` and `HANDOFF.md`, both rewritten by another session at 22:42 while this review ran (neither was read).
Every product module and public document kept a modification time earlier than the review's first command
(22:33:37) — `audit.py` 22:29, `lifecycle.py` 22:20, `repository.py` 22:29, `worker.py` 22:20, `ARCHITECTURE.md`
22:32, the rest 16:05–21:43 — so every probe and gate below ran against one product. sha256 of that product:
audit `349a22bc…`, cli `a309e205…`, core `fc2af01a…`, lifecycle `7ef0435a…`, recovery `878da4ff…`, repository
`0108d952…`, state `043a08cd…`, worker `193e6fa8…`; README `af8f0efa…`, SKILL `b1b2789e…`, ARCHITECTURE
`fe84287d…`; `tests/test_collect_policy.py` `c4a6a75f…`.

## 1. Verdict: NO-GO

The sixth review's Q1 is closed at every name and state it named: a FIFO, or a symlink to a FIFO, at the base pin,
summary, and `results/<sha>` names of ready, collected, collecting, quarantined, and discarded workers in both
modes returns with a refusal from `status`, `recover`, first and repeat `collect`, every `discard` flag
combination, `release`/`claim`, and a request-ID retry, with the occupant and its target byte-for-byte intact,
`next_id` unchanged, and no lock residue (78 of the 80 matrix rows in `m1.out`). I1–I4, R1–R4, N1–N3, F1–F5, the
six second-review classes, and the five Step 7.5i properties hold. The unit suite passes 280/280, both hardening
modes pass 56 with the one conditional reftable skip, and every static gate passes.

Release is blocked by four open findings that contradict public claims, one of them a custody defect:

- **S1 (Medium)** — a deletion resumed by `recover`, or re-authorized by a second `discard --force`, finishes
  deleting a quarantined *collected* worker without checking that its immutable result ref is still preserved,
  although ARCHITECTURE.md:679-680 states "Normal deletion requires a preserved result" and the first
  authorization refuses exactly that. The quarantine — by then the only copy of the collected work — is deleted
  and the record becomes `discarded` with `result-ref-missing`.
- **S2 (Low)** — the FIFO class the sixth review named is not fully closed: a FIFO (or symlink to one) at a
  worktree worker's task-branch name is still opened by Git, now through canonical-side commands that resolve
  every linked worktree's `HEAD` (`git worktree repair`, `git worktree add`, `git worktree list`, `git fetch`).
  The worker's own operations are refused as claimed, but once that worker is quarantined or its spawn was
  interrupted after publication, its `discard`, `recover`, and request retry hang; and with the worker simply
  live, every other worker's `collect`, every new worktree spawn, every worktree discard/abandon, and `recover`
  hang, leaving their records `collecting`/`cloning`/`discarding` with content in quarantine until the FIFO is
  removed by hand. Nothing is written, replaced, deleted, or consumed.
- **S3 (Low)** — a non-empty directory at a recorded worker's base-pin or summary name is still reported as
  `namespace-ref-symbolic` with the text "dangling symbolic ref under this worker's … name" (the sixth review's
  I2, which Step 7.5aa claims closed; it is closed for FIFOs only).
- **S4 (Low)** — a FIFO or non-ref file at a container name of the namespace makes `status` exit 2 with an
  `[Errno 20] Not a directory` message instead of listing the occupant, while the documents say such occupants
  are reported as `orphan-namespace-ref`.

Everything else I found is informational (stated boundaries, wording precision) and listed as such.

## 2. Findings, ranked by severity

### S1 — Medium — resumed or re-authorized deletion of a quarantined collected worker does not re-check that its result is preserved (in-contract custody defect; claim mismatch; same shape as the third review's F2)

- **Claim.** ARCHITECTURE.md:679-680: "Every published-worker deletion requires a released lease. Normal deletion
  requires a preserved result". Contract item 4 (PLAN.md "Current product contract"): "Deletion is a recoverable
  protocol: authenticate, record intent, atomically quarantine, recheck, delete … Unexpected work stays in
  quarantine and is reported; it is never converted into success." README.md:405-418 ("A worker preserved in
  quarantine is asked every category again … before a second `discard` deletes it").
- **What the code does.** The first authorization checks the result (`lifecycle.py:1197-1199`,
  `ref_points_at(canonical, worker.result_ref, worker.result_sha)` → "refusing deletion because collected result
  is not preserved"). Neither later path repeats it: `_reauthorize_quarantined` (`lifecycle.py:1253-1320`) asks
  intent, ignored paths, and private refs only, and `_recover_discarding` → `_resume_deletion`
  (`recovery.py:308-384`) runs `delete_through_quarantine` and `finish_deletion` against the recorded fingerprint
  with no result check. So a collected worker whose deletion was interrupted after the quarantine rename, or
  preserved in quarantine because it changed, is deleted by the next `recover` (no flag at all) or by
  `discard --force` even when the immutable result ref has since disappeared.
- **Reproduction.** `/tmp/clonegrown-review5-probes/m8_quarantine_result.py` → `m8_quarantine_result.out`, both
  modes. Setup: collected + released worker; `discard` interrupted at `discard.after_quarantine` (record
  `discarding`, `quarantine_path` set, fingerprint recorded); then `git update-ref --no-deref -d <result_ref>`
  (no FIFO involved). Rows: `m8-{clone,worktree}-resume_recover`: `before {result_present: false,
  quarantine_exists: true, record: discarding}` → `recover` reports `discard-finished` → `after {record:
  discarded, quarantine_exists: false, result_present: false, status_issues: ['1:result-ref-missing']}`.
  `m8-*-reauth_discard_force`: `discard --force` rc 0, `status: discarded`, same after-state.
  `m8-*-changed_in_quarantine`: a late file added in quarantine makes `recover` preserve it (`quarantine_error:
  "worker 1 changed after its custody check; preserved in quarantine …"`), the result ref is then deleted, and
  `discard --force` deletes the quarantine (rc 0, `discarded`, `result-ref-missing`). Controls
  (`m8-*-control_intact`) delete normally with the result present. The matrix also shows it with a FIFO planted
  over the result name (`m1-{clone,worktree}-quarantined-results-{fifo,link_fifo}`: `discard --force` → rc 0,
  record `discarded`, then `recover` reports `discarded-result-missing`). In every row the fetched commit object
  still exists in canonical (`commit_object_still_in_canonical: true`) but is unreferenced — it survives only
  until Git prunes unreachable objects.
- **Affected files.** `clonegrown/lifecycle.py:1253-1320` (`_reauthorize_quarantined`), `clonegrown/recovery.py:
  308-384` (`_recover_discarding`, `_resume_deletion`), `clonegrown/worker.py:394-557` (`delete_through_quarantine`,
  no result check), versus `clonegrown/lifecycle.py:1197-1199`; ARCHITECTURE.md:679-680, README.md:405-418.
- **Classification.** Medium, in-contract custody defect and claim mismatch. The precondition is narrow (a
  collected worker sitting in quarantine and its `refs/cws/…/results/<sha>` ref removed out of band), but the
  outcome is the one the first-authorization check exists to prevent: the last copy of collected work is deleted
  by an operation (`recover`) the documents describe as safe to run at any time, and the record is converted to
  a terminal success. Class fix: `_reauthorize_quarantined` and `_resume_deletion` (for `discard_intent ==
  discarded`) refuse, leaving the quarantine and reporting `quarantine-preserved`, when
  `ref_points_at(canonical, result_ref, result_sha)` is false.

### S2 — Low — a FIFO, or a symlink to a FIFO, at a worktree worker's task-branch name is opened by canonical-side Git (`worktree repair/add/list`, `fetch`): the quarantined or interrupted worker's own discard/recover/retry, and every other worker's collect, every worktree spawn, and every worktree discard/recover hang (claim mismatch; robustness; the class of R4/Q1)

- **Claim.** ARCHITECTURE.md:729-744: "Every owned ref name is `lstat`-inspected before any Git command reads it …
  a FIFO or other non-regular file … none is ever opened by Git (a FIFO would block it) … A worktree worker's own
  Git commands resolve its `HEAD` through the shared task-branch name, so a worker whose branch name holds a
  symbolic ref, symlink, or FIFO is reported as `task-branch-foreign` and every operation on it (status drift,
  collect, discard, recovery) is refused before a Git command runs in the worker". Step 7.5aa's bullet ("status
  drift, collect, discard, and recovery all refuse instead of hanging").
- **What the code does.** Git resolves every registered linked worktree's `HEAD` (through
  `refs/heads/<branch>` in the shared refs) inside `git worktree list`, `git worktree repair`, `git worktree add`,
  and `git fetch` (raw probe `g0.out`/`g1.out`: with a FIFO behind one worktree's branch these four block;
  `for-each-ref`, `show-ref`, `ls-remote`, `upload-pack --advertise-refs`, `clone`, `rev-parse --git-dir` in the
  worktree, `cat-file`, `merge-base`, and `update-ref` on other names all return; a FIFO at a plain loose ref
  that no worktree's `HEAD` targets blocks none of them). Clonegrown runs those four in canonical without asking
  the `lstat` question for the worktree workers whose `HEAD`s they resolve:
  `repository.py:934-946` (`add_worktree`, `repair_worktree`), `:861-885` (`branch_checkouts`), and
  `lifecycle.py:705-706` (the collect fetch). Callers: `worker.py:932-962` `repair_owned_worktree`, reached from
  `delete_through_quarantine` (`worker.py:480-483`, every worktree discard through quarantine and every resumed
  deletion), `_reauthorize_quarantined` (`lifecycle.py:1285`), `_recover_published_spawn` (`recovery.py:222`),
  `adoptable_quarantine` (`worker.py:995`); `release_task_branch` (`repository.py:910`); spawn
  (`lifecycle.py:543-546`, `:635-638`); `_publish_result_ref` (`lifecycle.py:705`). `verify_worker`'s guard
  (`worker.py:78-83`) covers only the worker whose branch is foreign, and only where `verify_worker` runs first.
- **Reproduction** (every CLI call in its own session under a 15 s timeout; `TIMEOUT` = killed while a Git child
  blocked; the wrapper in `m7` logs each Git invocation before `exec`, so the last logged line is the blocked
  command):
  - Same worker, quarantined: `m1_matrix.py` rows `m1-worktree-quarantined-task_branch-{fifo,link_fifo}` (`m1.out`):
    `discard` without flags refuses ("pass --force"), then `discard --force`, `discard --force --discard-ignored
    --discard-private-refs`, `recover`, `recover` again, and `spawn --request-id <same>` all `TIMEOUT`; record stays
    `discarding`, quarantine `1-<token>` stays, occupant and external FIFO intact, no lock files.
    `m7_attribution.out` `m7_quarantined_own_branch_fifo`: `discard --force` blocks at Git call 9, `worktree repair
    <ws>/.cws/quarantine/1-<token>/app` with cwd canonical; `recover` blocks at the same command (call 12).
  - Same worker, spawn interrupted after publication: `m6_interrupted_worktree.py` → `m6.out`
    `m6-publishing-{fifo,link_fifo}`: `recover`, `recover` again, and the request retry `TIMEOUT` (record stays
    `publishing`); `spawn other --worktree` `TIMEOUT` (record 2 left `cloning`, stage left). `status` returns
    (`owner-process-dead`). The staged (unpublished) and intent-only cases return: `spawn-cleanup-incomplete` /
    `discard-marked-broken`, occupant intact.
  - Other workers, worker B live and `ready`: `m2_cross_worker.py` → `m2_cross_worker.out`, both kinds:
    `status` returns with `2:task-branch-foreign, 2:worker-authentication-failed`; `spawn new-clone` succeeds;
    `spawn new-wt --worktree` `TIMEOUT` (record 6 `cloning`, stage left); `collect <clone A>` `TIMEOUT` (A
    `collecting`); `discard <collected worktree C>` `TIMEOUT` (C `discarding`, content in
    `.cws/quarantine/3-<token>`); `discard --abandon <worktree D>` `TIMEOUT` (D `discarding`); `recover` `TIMEOUT`
    (after marking B `broken` and finishing A). `m7_cross_worker_attribution`: the blocked commands are
    `fetch --no-tags --no-write-fetch-head --no-auto-maintenance <A path> <sha>` (collect), `worktree repair
    <quarantine path>/app` (discard C, recover), and `--git-dir=/dev/fd/4 worktree add --no-checkout --detach
    <stage>/app <sha>` (worktree spawn), all with cwd canonical. After the FIFO is unlinked, one `recover`
    settles everything (`3:discard-finished`, `4:abandon-finished`, `6:spawn-cleaned`) and `status` is clean;
    `occupant_unchanged: true`, `locks_left: []` in every row.
  - Raw attribution: `m2_attribution`: `worktree list/repair/add` and `fetch` `TIMEOUT`; `for-each-ref`, `clone`,
    `rev-parse --git-dir …` in B return; `status` in B `TIMEOUT` (the case `verify_worker` guards).
- **Affected files.** `clonegrown/repository.py:861-885, 934-946`; `clonegrown/lifecycle.py:543-546, 635-638,
  705-706, 1285`; `clonegrown/worker.py:480-483, 932-962, 995`; `clonegrown/recovery.py:222`; ARCHITECTURE.md:729-744.
- **Classification.** Low claim mismatch (robustness). Same precondition as R4/Q1 (a same-user process planting a
  non-regular file under canonical's `.git/refs/heads/`), nothing is written through, replaced, deleted, or
  consumed, and every stuck record settles once the occupant is removed. But the document says, in the sentence
  written for this class, that such an occupant is never opened by Git, and it is — by commands Clonegrown runs
  for unrelated workers. Class fix: before any canonical-side `git worktree add/repair/list` or `git fetch`,
  check `is_foreign_ref(canonical, refs/heads/<branch>)` for every worktree record whose worker directory (slot,
  quarantine, or stage) still exists, and refuse naming the worker and `task-branch-foreign`; or equivalently
  `lstat` the `HEAD` target of every registered admin entry under `.git/worktrees/`.

### S3 — Low — a non-empty directory at a recorded worker's base-pin or summary name is reported as `namespace-ref-symbolic` ("dangling symbolic ref …") (claim mismatch; the sixth review's I2, not closed for directories)

- **Claim.** ARCHITECTURE.md:729-736: "a directory (empty or not) at a ref-shaped name, a FIFO or other
  non-regular file, and a loose file that is not a ref are reported as `orphan-namespace-ref`". Step 7.5aa: "The
  audit no longer double-reports a malformed occupant as a dangling symbolic ref".
- **What the code does.** The raw walk (`repository.py:766-805`) lists a non-empty directory only through its
  children, so the directory's own name is in neither `refs.symbolic` nor `refs.malformed`; `audit_worker` then
  falls through to `is_foreign_ref(canonical, pin_ref)` (`audit.py:161-163`) / `is_foreign_ref(canonical,
  summary_ref)` (`audit.py:177-179`), whose `loose_ref_occupant` answer for a directory is `special`, and emits
  `namespace-ref-symbolic` with "dangling symbolic ref under this worker's base pin name" / "… summary name".
- **Reproduction.** `m4_issue_codes.py` → `m4_issue_codes.out` `m4A_codes_dir_nonempty`: `base_pin` →
  `[(1, 'namespace-ref-symbolic', "dangling symbolic ref under this worker's base pin name")]`, `summary` → the
  same text for the summary name; the child file is separately `orphan-namespace-ref`. Every other kind is
  labelled once and correctly: FIFO, non-ref file, and empty directory → `orphan-namespace-ref`; symlink to a
  FIFO, symlink with `refs/` text, symlink to an external file, dangling and live symbolic refs →
  `namespace-ref-symbolic` with the worker `id`. The fourth review's `pC_namespace.py` rerun agrees
  (`rerun-pC_namespace.out` `C6_directory_at_summary_name`: `namespace-ref-symbolic` for `workers/2/result`).
- **Affected files.** `clonegrown/audit.py:157-182`; ARCHITECTURE.md:733-735; the Step 7.5aa bullet.
- **Classification.** Low claim mismatch (issue code and text). The occupant is never touched (`unchanged: true`
  before and after `recover`).

### S4 — Low — a FIFO or non-ref file at a container name of the namespace makes `status` fail with a raw `ENOTDIR` message instead of reporting it (claim mismatch; robustness)

- **Claim.** README.md:198-203 ("`status` audits Clonegrown's documented workspace and worker invariants …
  Each detected disagreement is listed under `issues` with a stable code"); ARCHITECTURE.md:733-735 (FIFOs and
  non-ref loose files "are reported as `orphan-namespace-ref`"), :738-739 (only an *empty directory* at a
  container name is exempt).
- **What the code does.** `loose_ref_occupant` (`repository.py:643-648`) turns any `OSError` other than
  `FileNotFoundError` into `ClonegrownError("cannot inspect ref file …")`. With a FIFO or regular file at
  `refs/cws/<ws>/bases`, `…/workers/<id>`, `…/workers/<id>/results`, or `refs/cws/<ws>` itself, the `lstat` of a
  name below it fails with `ENOTDIR`, and `audit_worker` (`audit.py:161-162, 173, 177-178`) raises out of
  `status`. `recover` survives (its per-worker `except`) and reports `orphan-namespace-ref-left` for the
  container plus `recovery-failed` for each worker, except for the root, which the namespace walk never lists.
- **Reproduction.** `m3_containers.py` → `m3_containers.out`, rows `m3-{bases,workers_id,workers_id_results,root}-
  {fifo,garbage_file}` (8 rows): `status` rc 2, e.g. `clonegrown: cannot inspect ref file
  refs/cws/<ws>/bases/1: [Errno 20] Not a directory`; `recover` rc 0 with `1:recovery-failed`,
  `2:recovery-failed`, and `None:orphan-namespace-ref-left:refs/cws/<ws>/bases` (nothing for the root);
  `spawn`, `discard`, and (for `workers/<id>`, root) `collect` refuse with the same low-level text; `next_id`
  unchanged; occupant intact; no hang. The same rows with a symlink to a directory or a non-empty directory are
  reported (`namespace-ref-symbolic` / `orphan-namespace-ref` for the child) and `status` returns.
- **Affected files.** `clonegrown/repository.py:643-648`; `clonegrown/audit.py:157-182`; README.md:198-203;
  ARCHITECTURE.md:733-739.
- **Classification.** Low claim mismatch (fails closed, nothing touched, no hang; but the promised report is not
  produced and the error text is a raw `errno`). Class fix: treat `ENOTDIR` on the parent path as a foreign
  occupant above the name (return `special` for the name, or report the container) instead of raising.

### Informational (not findings)

- **I-a — "refused before a Git command runs in the worker" is literally imprecise.** With a dangling symbolic
  ref at a live worktree worker's branch name, `status`, `collect`, `recover`, and `discard --abandon` each run
  `rev-parse --show-toplevel`, `rev-parse --git-dir`, `rev-parse --git-common-dir` (twice), and `symbolic-ref -q
  refs/heads/<branch>` with cwd inside the worker before the refusal (`m5_gitlog.out` `m5_foreign_branch_*`,
  `git_calls_in_worker`); none of them resolves `HEAD`, and with a FIFO `symbolic-ref` is skipped (`m1` rows show
  no hang). The substantive property holds; the sentence at ARCHITECTURE.md:741-744 would be exact as "before a
  Git command that resolves its `HEAD` runs".
- **I-b — Symlinked container directories are followed.** A symlink at `refs/cws/<ws>/bases`,
  `…/workers/<id>`, or `…/workers/<id>/results` is reported as `namespace-ref-symbolic` (no `id`) and the raw
  walk does not descend into it, but Git and `lstat` follow it, so refs of new workers are created and dropped
  inside the target directory; a symlink at the namespace root `refs/cws/<ws>` is not reported at all and the
  whole namespace is redirected (`m3_containers.out` `m3-root-link_dir`: `ext_dir_changed: true` with worker 2's
  `result` and `results/<sha>` created in the external directory; `status2 issues: []`). Because every
  Clonegrown write is create-only or compare-and-swap, no foreign file is written through, replaced, or deleted
  (`m3-*-link_dir` rows: `next_id` advances normally; occupants unchanged), so this is outside the stated
  per-ref-name model rather than a contradiction of it; one sentence and a root check would close the gap.
- **I-c — A non-ref file anywhere under `refs/` breaks canonical's `git fetch`.** A garbage file at
  `refs/cws/<ws>/bases` or a `junk` child inside a non-empty directory makes the collect fetch fail with Git's
  "fatal: bad object refs/cws/…" (`m3-bases-garbage_file collect_ready`, `m3-*-dir_nonempty collect_ready`), so
  collection fails closed for every worker until the file is removed; `status` reports it as
  `orphan-namespace-ref` (where `status` runs, see S4). Git's behaviour, nothing touched.
- **I-d — A FIFO at a live worktree worker's branch name turns the worker `broken` on the next `recover`**
  (`ready-marked-broken`, `m1-worktree-ready-task_branch-*`, `m6-discard_intent_only-*` → `discard-marked-broken`)
  even though its content is intact and authenticates again once the occupant is removed; it then needs `release`
  and `--abandon`. Consistent with the documented rule that structural identity loss is fatal; stated here so the
  next reader does not mistake it for deletion.
- **I-e — Attribution of `orphan-namespace-ref`.** A FIFO, non-ref file, or empty directory at a *recorded*
  worker's name is reported once, but without the worker `id` (`m4A_codes_{fifo,garbage_file,dir_empty}`:
  `(None, 'orphan-namespace-ref', …)`), whereas `namespace-ref-symbolic` carries it; ARCHITECTURE.md:602-603 promises
  the `id` "when one applies".
- **I-f — Shared-store wording for ancestry is accurate.** `rerun-q1_r1.out` `1d_*` (worktree: `same_store:
  true`, `canonical_is_ancestor: true`, `collect` accepted with `allow_rewrite: false`, no drift) and `1e_*`
  (default clone: `hard_linked: true`, same acceptance) match ARCHITECTURE.md:722-728 and README.md:477-482
  exactly; a strong clone (`1a_*`) and a forged commit-graph (`1c_*`) are refused and reset.
- **I-g — Sequential-probe staleness.** Every row of my probes uses a fresh repository; none stalled. Of the
  earlier reviews' reruns, all 16 completed with rc 0 (`rerun.log`); `p3_wording.py` and `p5_fifo.py` were not
  rerun (their known stale-step stalls are covered by `p3e.py`, `m1`, and `m4`).
- **I-h — Environment sensitivity of the suite (sixth review's I7).** Not re-tested; the authoritative run here
  was in the checkout without `PYTHONPYCACHEPREFIX`, exactly as instructed, and passed 280/280.
- **I-i — Tree change under review.** `PLAN.md`/`HANDOFF.md` were rewritten at 22:42 by another session (see the
  fingerprints above); no product file or public document changed.

## 3. Verification record

### Q1 (sixth review) — CLOSED at every named path; adjacent gap S2

`m1_matrix.py` → `m1.out`: 80 rows = {clone: base pin, summary, `results/<sha>`; worktree: those plus task branch
and branch-owner} × {FIFO, symlink→FIFO} × {ready, collected, collecting (interrupted at `collect.after_mark`),
quarantined (interrupted at `discard.after_quarantine`), discarded} × per-state operations (status, recover,
request-ID retry, first or repeat collect, discard with no flag / `--abandon` / `--force` / `--force
--discard-ignored` / all three, release, claim, second status and recover). 78 rows: every operation returns
(rc 0 or a refusal), `occupant_unchanged: true` after every operation, `ext_fifo_unchanged: true`, no `.lock`
under canonical's Git directory, `next_id` unchanged, one record. Specifically: the collected-repeat `collect`
with a FIFO or symlink→FIFO at the summary or result name is refused ("refusing to write through a symbolic ref …")
with no lock residue (`m1-*-collected-{summary,results}-*` `collect_repeat`); `status` of a collected worker with
a FIFO at the result name reports `result-ref-missing` + `orphan-namespace-ref`, `recover` marks it
`collected-marked-broken` and leaves the directory; `discard` is refused ("collected result is not preserved");
the request retry is refused ("result ref is missing or moved"); a symlink→FIFO at the base pin of a collected
worker: `recover` returns (`base-ref-*` untouched); the tombstone (`discarded`) rows: status/recover/retry return
with `result-ref-missing` / `discarded-result-missing` / "missing or moved"; a `collecting` record with the
occupant at its candidate name: `recover` → `collect-reset-ready`, `retry` returns; live worktree worker with
FIFO/symlink→FIFO at its branch name: `status` reports `task-branch-foreign` + `worker-authentication-failed`,
collect/discard(all flags)/retry refused with the `task-branch-foreign` text, `recover` returns
(`ready-marked-broken`), directory kept; collected worktree worker with the occupant at its branch name: every
discard flag refused before deletion, slot present, `recover` returns; branch-owner occupants: discard proceeds
and retains the branch with `branch_cleanup_left: "… its ownership ref is a symbolic ref or foreign ref file, which
is not ours"`, record `discarding`, `recover` → `worktree-cleanup-conflict`. Helper attribution
(`rerun-q3_attribution.out`): for both kinds `loose_ref_occupant` is `special`/`link`, `is_foreign_ref` True,
`resolve_ref` None, `ref_points_at` False, `result_ref_transaction(update_summary=True)` refuses (rc 1) — none
times out. The two rows that still block are the quarantined worktree worker's task-branch rows (S2).

### I1–I4 (sixth review)

- I1 (shared-store wording): stated at ARCHITECTURE.md:722-728 and observed (`rerun-q1_r1.out` `1d_*`, `1e_*`);
  CLOSED.
- I2 (double, mislabelled code): CLOSED for FIFOs, non-ref files, and empty directories (`m4A_codes_*`: one
  `orphan-namespace-ref` each); NOT closed for a non-empty directory (S3).
- I3 (empty directory invisible): CLOSED — an empty directory at a ref-shaped name of an unrecorded id is
  `orphan-namespace-ref` (`m4A_codes_dir_empty` `u_*` rows; `rerun-q3_attribution.out` `3_empty_dir_*_status`)
  and one at a container name (`workers/9`) is not reported (`container_empty_dir_only: count 0`), matching
  ARCHITECTURE.md:738-739.
- I4 (branch-owner retention text): CLOSED — "its ownership ref is a symbolic ref or foreign ref file, which is
  not ours" for FIFO, symlink→FIFO, dangling/live symbolic ref, and external-file symlink; "no ownership ref
  proves this worker created it" for a non-ref file (`m4B_owner_*`, branch retained, occupant intact).

### R1–R4 (fifth review) — CLOSED (with S2 adjacent to R4)

R1: `rerun-q1_r1.out` (26 rows) and `rerun-p1b_forged_recovery.out`: forged loose parent in a strong clone —
plain collect refused on canonical, interrupted collections (`after_mark`, after fetch) reset `collect-reset-ready`
with `result_sha: null`, `--allow-rewrite` collects with `allow_rewrite: true`; forged commit-graph the same;
`status` drift for a false record ("collected result does not descend from its assigned base in canonical").
R2: `rerun-p2_occupants.out` (348 rows): no row consumes an ID; the 13 rows whose occupant changed are the
documented classes (base-pin drop at the recorded value, the worker's own branch-owner deletion, `packed-refs`
rewrites, Git's removal of an empty directory when it creates the branch-owner ref); `m1-*-ready-*`,
`rerun-pC_namespace.out` `C1_*` (`next_id_after: 1`, `records_after: []`). R3: `rerun-p3e.out` (8 rows, symbolic
ref / symlink at a worktree worker's branch name, with and without `--force`: content deleted, branch retained,
occupant byte-identical), `m4C_taskbranch_*` (six occupant kinds, discard refused before deletion), `rerun-p4_spot.out`
`taskbranch_symref_status`. R4: `m1-*-ready-base_pin-*`, `rerun-pC` `C2_garbage_at_base_pin_name`; allocation with
a FIFO at the pin or branch name refused before Git (`test_allocation.py` "fifo base ref"; `rerun-p2` E rows).

### N1–N3 (fourth review) — CLOSED

N1: `rerun-p1_ancestry.out` (19 rows: replace refs and grafts in worker and canonical refused by `is_ancestor`
and `collect`; environment overrides stripped, `1d_env` rc 2; shallow boundary only hides; forged object crossing
the fetch fails with "hash mismatch"), `rerun-p1g.out`, `rerun-pA_env.out` `A2_*`/`A3_*`. N2/N3: `rerun-p2b_clone_direct.out`
(a direct ref at another value at `results/<tip>` → "conflicting result ref already exists", preserved; a direct
ref at the summary moved by design; packed ref shadowed by a dangling symref → refused), `rerun-p6_recover_occupants.out`
(24 rows, every occupant at candidate and summary names left untouched), `rerun-pC_namespace.out` (`C3_fs_symlink_at_summary_outside_refs`:
collect rc 2, link and victim intact).

### F1–F5 (third review) — CLOSED

F1: `m5_gitlog.out` `m5_env_{clone,worktree}` — 336 / 349 Git invocations across init, spawn, two collects,
release, status, recover, discard under 58 hostile `GIT_*` names plus `SSH_ASKPASS` and a `GIT_CONFIG_COUNT`
injection: only `GIT_AUTHOR_NAME`, `GIT_COMMITTER_EMAIL`, `GIT_TERMINAL_PROMPT=0`, Clonegrown's own
`GIT_GRAFT_FILE=/dev/null`, and `PROBE_UNRELATED` reach Git; all eight operations rc 0. `rerun-pA_env.out` agrees
(573 invocations). F2: `rerun-pB_reauth.out` `B_{clone,worktree}1_sequence` (force alone refused, `--discard-ignored`
asked). F3: `rerun-pC` `C1_*` and `m4A_codes_symref_dangling` (`namespace-ref-symbolic` with the id, allocation
evidence). F4: grep for the seven pre-repair phrases finds nothing in README/SKILL/ARCHITECTURE. F5: the
literal-boundary sentences are present (README.md:422-424, :343-345; ARCHITECTURE.md:637-641) and observed
(`rerun-pD_classes.out` `F5_pseudo_ref_orig_head_flagless_discard` rc 0, `class4` `parent_symlink_followed`, `class3`).

### Six second-review classes — all PASS (`rerun-pD_classes.out`)

1 private refs: no flag rc 2, ref intact, with flag rc 0, retargeted baseline refused. 2 dangling symbolic task
branch: worktree spawn rc 2, `next_id` 1, bytes intact, clone spawn of the same name rc 0. 3 dangling control
links: init/spawn rc 2, links intact, `next_id` 1. 4 CLI init symlink: absolute/relative/default-name rc 2, link
intact, no marker; parent symlink followed. 5 `GIT_CONFIG`/`GIT_CONFIG_COUNT`: spawn rc 0. 6 rewrite: default rc 2,
flag rc 0, repeats rc 0 under either argument, new commit rc 2 under either, result ref still names the accepted tip.

### Step 7.5i collection-timing properties — all five hold (`rerun-timing.out`)

Direct conflict preserved at the planted value with the worker `ready`; symbolic exact conflict refused with the
target intact; result and summary move attempts both rc 128 while the prepared transaction held the locks,
record `collected` with both refs at the candidate; object-only recovery published through one all-zero
expected-old `write_ref` and reported `collect-finished`; a conflicting recovery ref stayed at the planted value
and the worker reset `ready`.

## 4. Coverage-map spot checks

| Item | Result |
|---|---|
| 5.1 active-writer race / 7.5i | Timing 5/5; occupants at summary and result names during collect and recovery refused or left (`m1`, `rerun-p6`, `rerun-p2b`). Gaps: S1 (resume path), S2 (hang, no custody effect). |
| 5.2 ignored work | First refusal names count and sample; re-authorization re-asks in both modes (`rerun-pB`). |
| 5.3 unchecked deletion | Quarantine, fingerprint recheck, preserved-on-change (`m8-*-changed_in_quarantine` first step), errors-enabled deletion, `recover` resumes (`rerun-pB`, `m8`). Gap: S1. |
| 5.4 branch ownership | Create-only transaction refuses every occupant kind at allocation (`rerun-p2` A rows, `test_allocation`); cleanup retains a foreign branch name (`rerun-p3e`, `m4C`) and a foreign owner ref (`m4B`, `m1-*-branch_owner-*`). |
| 5.5 changed published recovery | `recovery.py:217-248` preserves divergence as `broken`; `test_worktree`/`test_parent_interruption` pass; `m6-publishing-*` `status` reports `owner-process-dead` (recover blocked by S2 in that row). |
| 5.6 installer root | `sh -n install.sh` OK; the installer tests pass in the suite; not hand-probed. |
| 5.7 / 5.8 remotes and config | `_canonicalize_remote_url` (`repository.py:140-148`) and `ConfigOccurrence(value=None)` (`:43-48`, `:93-106`) read; `test_repository` passes; credentialed remote copied verbatim (`rerun-pE` `5.10_remote_copied: true`). |
| 5.9 Git sanitation | Allowlist proven across 336/349 (`m5`) and 573 (`rerun-pA`) invocations including a custom `CLONEGROWN_GIT`. |
| 5.10 secret-bearing errors | `rerun-pE` `5.10_command_failure_text`: `https://<redacted>@example.invalid/…`, `5.10_raw_git_shows_secret: false`; `rerun-p4` `5.10_redaction`. |
| 5.11 stale request reuse | Same ID + params → same worker; different params refused; discarded worker with deleted result → retry refused (`rerun-pE` `5.11_*`; `m1-*-discarded-results-*` `retry`). |
| 5.12 incomplete status | 29 codes in ARCHITECTURE.md:604-616 = 29 emitted by `audit.py`/`recovery.py` (my grep and `rerun-pE` `5.12_codes`: `in_code_not_doc: [], in_doc_not_code: []`). Gaps: S3, S4 (wrong code / no report), I-e. |
| 5.13 create-only allocation | Rewound counter → "already has a record, slot directory, operation lock file; nothing was changed" (`rerun-pE` `5.13_*`); 348 + 80 occupant rows consume nothing. |
| 5.14 API/CLI parity | API and CLI both `mode: clone, strong: false`; `strong=True` + worktree refused by both (`rerun-p4` `5.14_parity`). |
| 5.15 invalid generated branch | `x.lock` → "generated task branch is invalid for Git", `next_id` unchanged, no refs, no record (`rerun-pE`, `rerun-p4`). |
| 5.16 low-level errors | Five-part context on `collect 999` (`rerun-p4` `5.16_context`) and on every refusal quoted above; S4's refusals carry it around a raw `errno` cause. |
| 5.17 timing gate | No `ratio` assertion in `hardening_suite.py` (`grep ratio` finds only the word inside `operation`); `parallel_spawns_unique` PASS in both modes (2.20 s / 2.34 s). |
| 5.18 one-shot | `--abandon` and `claim` refused for a collected worker; leased discard refused under every flag (`rerun-pE` `5.18`, `rerun-p4` `5.18_one_shot`, `m1-*-collected-*` `discard_abandon`/`claim`). |
| Comment/public overclaims | Notices current (README.md:17-34, SKILL.md:14-25, ARCHITECTURE.md:6-16 describe the second–fourth reviews as repaired and require a fresh review); F4 phrases absent. Stale wording: ARCHITECTURE.md:679-680 (S1), :729-744 (S2, S3, S4, I-a). |
| `CWSError`, heartbeat, failpoints | `grep -rn CWSError clonegrown/` finds nothing; `heartbeat` only as a hidden bookkeeping key (`cli.py:31`); `failpoint` gated on `CLONEGROWN_TEST_MODE == "1"` (`core.py:485`). |
| retention, teardown, license, package | `pyproject.toml`: `license = "Apache-2.0"`, `license-files = ["LICENSE"]`, `requires-python = ">=3.11"`, dynamic version `0.1.0a1`. Wheel from the out-of-checkout copy: `clonegrown-0.1.0a1-py3-none-any.whl`, 98,820 bytes, sha256 `14c0d0fc619d81461f8661fb95a0e18fccbfd7888b0dd502ae5271a8ef3a2ef7`, `License-Expression: Apache-2.0`, `Requires-Python: >=3.11`, `licenses/LICENSE` present; fresh venv: `clonegrown --version` and `python -m clonegrown --version` both print `clonegrown 0.1.0a1`. Retention: result and summary refs and the record survive every normal discard in `m1`/`m8` control rows. |
| macOS, Python/Git versions, filters/LFS, resource boundaries, repository diversity, repeated verification, auxiliary-ref cost | Not freshly exercised (section 6); `test_filters_and_resources`, `test_auxiliary_refs`, `test_campaign_records`, `test_lease` pass in the suite. |

## 5. Gate results

- **Unit suite:** `cd /home/serrecchia/Projects/clonegrown && python3 -m unittest discover -s tests -v` (in the
  checkout, no cache prefix) → **Ran 280 tests in 305.668 s, OK** (280 `ok`, 0 failures, 0 errors, 0 skipped);
  wall 22:33:37 → 22:38:42; log `/tmp/clonegrown-review5-unittest.log`. The suite grew from the sixth review's
  277 to 280 (`tests/test_collect_policy.py` is new and untracked).
- **Hardening, clone mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`: "git lacks reftable
  support"), **0 failed**; sum of case seconds 70.1; wall 22:41:37 → 22:42:53 (1 min 16 s);
  `sha256 c6f6222d4050cd988a4c6793e12f21e32a6c81bf714170784de2100f2b129e45 /tmp/clonegrown-review5-hardening-clone.json`
  (log `/tmp/clonegrown-review5-hardening-clone.log`).
- **Hardening, worktree mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`), **0 failed**; sum of
  case seconds 77.4; wall 22:42:53 → 22:44:15 (1 min 22 s);
  `sha256 a278badd72133d8d481520f1808deb4cc1660697c9aaafd83edd71a199e0f49e /tmp/clonegrown-review5-hardening-worktree.json`
  (log `…-hardening-worktree.log`).
- `git diff --check` clean; `sh -n install.sh` OK; `python3 -m compileall -q clonegrown tests` OK with
  `PYTHONPYCACHEPREFIX=/tmp/clonegrown-review5-pyc`; wheel build (`python -m build --wheel` in a venv on the
  rsync copy `/tmp/clonegrown-review5-build/src`) and isolated install OK (above); no `build/`, `dist/`, or
  `egg-info` in the checkout; `clonegrown/__pycache__` (gitignored) is the only thing the in-checkout suite run
  wrote.
- Versions: CPython 3.12.3, Git 2.43.0 (`/usr/bin/git`), Linux 6.17.0-35-generic.
- Tree fingerprints: start `26a601c0992e750e78cfc071a16230f38d2d1d8900f60c52132cf7ff2364367b`, end
  `9075fa64043acf2fac41291bf28e6deebce75169bdddd16f2b386a78dd035847` (only `PLAN.md`/`HANDOFF.md` differ, header);
  `git status --short` 23 entries at both ends.

## 6. Not verified, and why

- Hosted CI on a pushed revision, macOS, CPython 3.11, exact Git 2.29.0: not available locally; the tree is
  uncommitted. Whether Git 2.29's `worktree`/`fetch` commands resolve worktree `HEAD`s the same way (S2) was
  not checked on that version.
- reftable repositories and `GIT_REF_FORMAT` end to end: Git 2.43 cannot create them (hardening skip); the
  `inventory is None` fallbacks were read, not exercised.
- Random-kill and state-machine campaign seeds, `real_repository_qualification.py`, and the benchmark harnesses:
  not in the requested gate list and not run.
- A socket occupant (a FIFO proves the class); occupants at container names in the *worker's own* refs (a
  clone's private refs are the agent's, out of scope).
- The fifth review's `p3_wording.py` and `p5_fifo.py` were not rerun (their known stale-step stalls; the
  behaviours they cover are in `p3e`, `m1`, `m4`, and the reauthorization rerun `pB`).
- Genuine disk/inode exhaustion, network filesystems, Git LFS, native Windows: stated boundaries, not exercised.
- `HANDOFF.md` and the Step 7.5a–7.5aa completion records: deliberately not read.

Probe inventory: `/tmp/clonegrown-review5-probes/{h5,m1_matrix,m2_cross_worker,m3_containers,m4_issue_codes,
m5_gitlog,m6_interrupted_worktree,m7_attribution,m8_quarantine_result}.py` with outputs `m1.out`,
`m1-clone-ready.out`, `m2_cross_worker.out`, `m3_containers.out`, `m4_issue_codes.out`, `m5_gitlog.out`, `m6.out`,
`m7_attribution.out`, `m8_quarantine_result.out` (and `*.err`, `chain.log`, `chain2.log`); raw Git probes
`g0_rawgit_fifo.sh` → `g0.out`, `g1_fetch_isolate.sh` → `g1.out`; `rerun_all.sh` → `rerun-*.out`/`.err`,
`rerun.log` for the fourth review's `pA`–`pE`, the 7.5i timing probe, the fifth review's `p1`, `p1b`, `p1g`,
`p3e`, `p4`, `p6`, `p2b`, `p2`, and the sixth review's `q1`, `q3`; disposable repositories under
`/tmp/clonegrown-review5-work/` (and, for the reruns, the earlier reviews' work roots); suite log
`/tmp/clonegrown-review5-unittest.log`; hardening logs and JSON `/tmp/clonegrown-review5-hardening-*`; wheel and
venvs under `/tmp/clonegrown-review5-build/`.

## Eighth fresh review (sixth Step 7.5 pass, after Step 7.5ab): no-go

An eighth fresh reviewer found S1–S4 closed as stated, every earlier finding
holding, the suite 284/284, and both hardening modes clean, and returned
no-go on three Low findings:

1. **S5 (low).** With a foreign occupant on worker A's branch name,
   `recover` marked worker B's untouched interrupted spawn `broken` through
   the new refusal, and nothing promoted B afterwards. Step 7.5ac owns it.
2. **S6 (low).** The architecture said every name below a symlinked
   container is treated as foreign; the occupant inspection looked only at
   the final component. Step 7.5ac owns it.
3. **S7 (low).** A symbolic ref at a worktree worker's branch name whose
   target is a FIFO blocked Git's whole-repository ref enumeration in
   `status`, `recover`, spawn, and collect. Step 7.5ac owns it.
4. Informational: a non-regular admin `HEAD` or a symlinked admin entry
   still reached Git; a `broken` worker's recorded result left the audit;
   permission denial is a raw errno; a refused worktree spawn consumes an
   ID (documented). Step 7.5ac owns the first two.

The reviewer's full report is preserved verbatim below.

---

# Clonegrown final cold review — release qualification (eighth fresh review)

Date: 2026-09-02/03. Reviewer: fresh agent, read-only on `/home/serrecchia/Projects/clonegrown` (uncommitted
working tree on `main`, base `c9728a0`). Environment: Linux 6.17.0-35-generic, CPython 3.12.3, Git 2.43.0
(`/usr/bin/git`). Every probe, log, wheel, and result lives outside the checkout under `/tmp/clonegrown-review6-*`
(probes and outputs in `/tmp/clonegrown-review6-probes/`, disposable repositories in `/tmp/clonegrown-review6-work/`,
reruns of earlier reviews' probes as `/tmp/clonegrown-review6-probes/rerun-*.out`). `HANDOFF.md` and the Step 7.5a–7.5ab
"Completion record" sections were not read; no `.env`-pattern file was opened; nothing inside the checkout was modified
(the wheel was built from an `rsync` copy; `compileall` ran with `PYTHONPYCACHEPREFIX=/tmp/clonegrown-review6-pyc`; the
unit suite ran in the checkout without a cache prefix, as CI does). Every Git command and Clonegrown call that could
touch a planted FIFO ran under a 5–20 s timeout (`TIMEOUT` below means the process was killed while blocked).

**Tree fingerprints.** `git diff | sha256sum` at start `da3b1b0668b3336ea23f9b41e7e46fa15af744e196fd4341d8d076b5ada6e96f`,
at end `3d2870cf71535b197354bf40bdde479b6ee505a764044b4628a34e7a6e7cc36f`; `git status --short` lists 23 entries at both ends (22 modified tracked files plus untracked
`tests/test_collect_policy.py`). The end fingerprint differs only because `PLAN.md` and `HANDOFF.md` were rewritten
by another session at 23:22:38 while this review ran (neither was read); every product module and public document has the
same sha256 at both ends. Product-file modification times all precede the review's first command (23:13):
`audit.py` 23:10, `lifecycle.py`/`repository.py`/`worker.py` 23:04, `recovery.py` 21:23, `README.md`/`ARCHITECTURE.md`
23:12, `SKILL.md` 20:52. sha256 (first 12) of the product reviewed: audit `7f1e0c210e77`, cli `a309e205fbb4`, core
`fc2af01adbd3`, lifecycle `f7825d8bdd30`, recovery `878da4ff5556`, repository `24273c32f677`, state `043a08cd21ac`,
worker `7b37e3ecb2dd`; README `64e94da13b40`, SKILL `b1b2789e2375`, ARCHITECTURE `c529ece53b68`.

## 1. Verdict: NO-GO

The seventh review's four findings are closed as stated: S1 (a quarantined collected worker whose result ref disappears
is never deleted, in both modes, at every failpoint of the deletion protocol where the content still exists, by `recover`
and by re-authorized `discard`, and restoring the ref lets the recorded deletion finish), S2 for the occupant kinds it
named (a FIFO or symlink-to-FIFO at a live, collected, quarantined, or interrupted-spawn worktree worker's branch name
makes every other worker's collect, worktree spawn, worktree discard/abandon, recover, and the worker's own discard and
retry refuse by name in ≤0.4 s; clone spawns proceed; nothing is written, replaced, deleted, or consumed; removing the
occupant lets one `recover` settle everything), S3 (a non-empty directory at a recorded worker's pin or summary name is
`orphan-namespace-ref` with the id), and S4 (a FIFO or plain file at every container name and at the namespace root, and
even at `refs/cws` above it, is reported and `status` returns rc 0). The seventh review's informational notes I-a, I-b
(root symlink now reported), and I-e (id attribution) are addressed. Q1, R1–R4, N1–N3, F1–F5, the six second-review
classes, and the five Step 7.5i properties hold on reruns. The unit suite passes 284/284, both hardening modes pass 56
with the one conditional reftable skip, and every static gate passes.

Release is blocked by three open findings, all Low, each contradicting a sentence the documents state as a property:

- **S5 (Low)** — `recover` durably marks an *untouched* interrupted-spawn worktree worker `broken` when a *different*
  worker's branch name holds a FIFO or symlink-to-FIFO; after the occupant is removed nothing promotes it, so a fresh
  worker must be released and abandoned. ARCHITECTURE.md:376-380 promises promotion of an untouched worker and a
  `broken` error "naming the kind of difference"; Step 7.5ab's claim that "everything proceeds once it is removed" does
  not hold for this path, and the refusal text's "then retry" is unfulfillable.
- **S6 (Low)** — ARCHITECTURE.md:739-743 now states that below a symlinked container name "every name below it is
  treated as foreign". It is not: Git and Clonegrown's own `lstat` follow the symlinked directory, `status` reports only
  the container, the result reads as preserved, and `discard` deletes the worker through it. (The names below a FIFO or
  plain-file container are treated as foreign, as stated.)
- **S7 (Low)** — a symbolic ref at a worktree worker's branch name whose target is a FIFO (or symlink-to-FIFO) is not
  "reported as `task-branch-foreign`" (ARCHITECTURE.md:746-750): `status`, `recover`, every spawn (clone included),
  every collect, and every discard block in Git's whole-repository `for-each-ref` (Clonegrown's namespace inventory), in
  `symbolic-ref -q`, or in `fetch`. The same two objects at names Clonegrown does not own (`refs/heads/foo` →
  `refs/heads/zz-fifo`) block every Clonegrown command identically and also hang the user's own `git branch`, so this is
  Git's ref enumeration rather than the per-owned-name inspection; it still contradicts the two sentences above, and no
  document states the boundary.

Everything else I found is informational and listed as such.

## 2. Findings, ranked by severity

### S5 — Low — recovery of another worker's interrupted spawn is converted into a durable `broken` state by the FIFO refusal (claim mismatch; robustness; adjacent to S2)

- **Claim.** ARCHITECTURE.md:376-380: "Recovery of an interrupted published spawn never deletes the worker. It repairs a
  worktree's back-pointer, authenticates the directory, and promotes an untouched worker (clean, on its task branch,
  `HEAD` at the recorded base, no Git operation in progress) to `ready`. Anything else is marked `broken` and preserved
  exactly as it is, with `error` naming the kind of difference". ARCHITECTURE.md:751-756: "other workers' operations
  therefore fail closed instead of blocking". PLAN.md Step 7.5ab: "everything proceeds once it is removed". The refusal
  text itself: "Remove that occupant by hand, then retry".
- **What the code does.** `_recover_published_spawn` (`recovery.py:217-225`) calls `repair_owned_worktree` →
  `repair_worktree` → `require_plain_worktree_heads` (`repository.py:659-707`, `:999-1002`). The new refusal raises
  `ClonegrownError` for worker A's branch name; the `except ClonegrownError` at `recovery.py:224-226` turns it into
  `mark_broken("unverified path exists after interrupted spawn: linked worktree app has HEAD on refs/heads/<A> …")`.
  `broken` is terminal for `recover` (`run()` has no branch for it), so once the occupant is gone B is never re-examined.
  Every other refusal site leaves a retryable record: collect returns the worker `ready`, discard leaves `discarding`
  (`quarantine-preserved` / `discard-cleanup-incomplete`), a worktree spawn records `spawn_failed`.
- **Reproduction.** `/tmp/clonegrown-review6-probes/r2d_recover_other.py` → `r2d.out`, rows
  `r2d-B_interrupted_{spawn.after_publish,spawn.after_repair}-{fifo,link_fifo}`: A worktree `ready`; B's worktree spawn
  killed at the failpoint (record `publishing`, untouched checkout); FIFO planted at A's branch name; `recover` →
  `["1:ready-marked-broken", "2:spawn-broken-unverified-path"]`, B `broken`, `B_error` = the require_plain_worktree_heads
  text naming worktree `app` and A's branch; occupant unchanged. Occupant removed; `recover` → `[]`, B still `broken`,
  `status` issues `[]`; B is only usable through `release` + `discard --abandon` (rc 0, `abandoned`). Controls
  (`…-control`, no occupant) → `spawn-publish-finished`, B `ready`.
- **Affected.** `clonegrown/recovery.py:217-226`; `clonegrown/repository.py:659-707`; ARCHITECTURE.md:376-380, :751-756;
  PLAN.md Step 7.5ab bullets.
- **Classification.** Low claim mismatch (robustness). Nothing is deleted; B's content is a fresh checkout; the exit
  path is explicit. But a `recover` the documents call safe to run at any time converts a foreign occupant on *another*
  worker's name into a terminal state for an untouched worker. Class fix: let the require-plain-heads refusal propagate
  as a per-worker `recovery-failed` (or a new retryable report) instead of `mark_broken`, so the next `recover` promotes B.

### S6 — Low — names below a symlinked container are not "treated as foreign" (claim mismatch; wording introduced by Step 7.5ab)

- **Claim.** ARCHITECTURE.md:739-743: "a FIFO, plain file, or symlink at a container name of the namespace, or at the
  namespace root itself, is reported (`orphan-namespace-ref` or `namespace-ref-symbolic`) and every name below it is
  treated as foreign."
- **What the code does.** `loose_ref_occupant` (`repository.py:625-656`) `lstat`s only the final component, so a symlinked
  parent directory is followed; `NotADirectoryError` (FIFO/plain-file parent) is the only "foreign above" case (`:647-648`).
  `ref_points_at`, `resolve_ref`, and Git therefore read refs through a symlinked container as ordinary refs.
- **Reproduction.** `/tmp/clonegrown-review6-probes/r3b_symlinked_container.py` → `r3b.out`, rows `r3b-{workers_1,
  workers_1_results,root}`: a collected, released clone worker; the real container directory is moved out and a symlink
  put in its place (the same refs now live behind the link). `status` rc 0 with exactly one issue,
  `(None, "namespace-ref-symbolic", <container>)` — no `result-ref-missing`, no summary issue; `discard 1` rc 0 →
  `discarded`, slot gone, `result_still_resolves: true` (through the link), target intact; `recover` reports only
  `namespace-ref-symbolic-left`. Contrast the seventh review's `m3-*-link_dir` rerun (`rerun-m3_containers.out`), where
  the link points at an *empty* directory and `result-ref-missing`/`summary-ref-mismatch` are reported because the refs
  are genuinely absent — the names are followed, not treated as foreign, in both cases. A FIFO or plain file at the same
  container names does make every name below foreign (`m3-*-{fifo,garbage_file}`, `r3-cont_*`, section 3).
- **Affected.** ARCHITECTURE.md:739-743; `clonegrown/repository.py:625-656`; `clonegrown/audit.py:212-227`.
- **Classification.** Low wording/claim mismatch. Custody effect: the collected work stays reachable through the link
  (Git sees the ref), so nothing is lost while the link stands; but the sentence promises a fail-closed behaviour that is
  not implemented. Either implement it (walk each path component with `lstat` before trusting a namespace ref, as
  `raw_ref_inventory` already does for the listing) or state the observed behaviour (the seventh review's I-b wording).

### S7 — Low — a symbolic ref at a worktree worker's branch name whose target is a FIFO blocks every Clonegrown command, `status` included (claim mismatch; Git enumeration; adjacent to S2)

- **Claim.** ARCHITECTURE.md:746-750: "a worker whose branch name holds a symbolic ref, symlink, or FIFO is reported as
  `task-branch-foreign` and every operation on it (status drift, collect, discard, recovery) is refused before a Git
  command that resolves its `HEAD` runs in the worker"; :751-756: "other workers' operations therefore fail closed
  instead of blocking".
- **What the code does.** `require_plain_worktree_heads` and `is_foreign_ref` `lstat` the branch name only; a symbolic ref
  there is a regular file, so it passes, and the target it names is never inspected. Git then resolves the symref while
  enumerating refs: `raw_ref_inventory` runs an unprefixed `for-each-ref --format=%(refname)%00%(objectname)%00%(symref)`
  (`repository.py:786-788`) for every `status`, `recover`, and allocation (`allocation_evidence`, `worker.py:670`), and
  `is_symbolic_ref` runs `symbolic-ref -q <branch>` (`:722-725`); both open the FIFO.
- **Reproduction.** `/tmp/clonegrown-review6-probes/r2_s2.py` → `r2_s2.out`, rows `r2-{ready,collected}-symref_to_fifo`
  and `…-symref_to_link_fifo`: `status`, `collect` of a clone and of a worktree, `spawn` (clone and worktree), `discard`
  of a collected worktree, `discard --abandon`, the request retry, and `recover` all `TIMEOUT` (20 s); records left
  `collecting`/`discarding`; occupant and FIFO unchanged; no locks; after the occupant is removed one `recover` settles
  every record (`collect-reset-ready`, `collect-finished`, `discard-finished`, `abandon-finished`). Attribution with a
  logging `CLONEGROWN_GIT` (`r2e_attribution.py` → `r2e.out`): `status` and `recover` block at call 9, `for-each-ref …`;
  clone `spawn` at call 11, `--git-dir=/dev/fd/3 for-each-ref …`; the clone worker's `collect` at call 41, `fetch …`;
  the worktree worker's own `collect` at call 12, `symbolic-ref -q refs/heads/<branch>`. The same plant at names
  Clonegrown does not own (`r2e2_unowned.py` → `r2e2.out`: `refs/heads/foo` → FIFO `refs/heads/zz-fifo`, both workers'
  branches intact) blocks the same five commands at the same calls, and raw Git in canonical (`r2c_rawgit.sh` →
  `r2c_rawgit.out`): `git branch`, `for-each-ref`, `show-ref`, `fetch`, `clone`, `symbolic-ref -q foo`, `rev-parse
  --verify foo` `TIMEOUT`; `git status`, `log`, `worktree list`, `for-each-ref refs/cws/`, `update-ref` return; the FIFO
  alone (no symref) blocks only `rev-parse --verify zz-fifo`.
- **Affected.** `clonegrown/repository.py:659-725, 786-788`; `clonegrown/worker.py:78-83, 670-681`; ARCHITECTURE.md:746-756.
- **Classification.** Low claim mismatch (robustness). Same precondition class as R4/Q1/S2 (a same-user process planting
  under canonical's `.git/refs/`), one more object than S2, nothing written, replaced, deleted, or consumed, everything
  settles once the FIFO is removed. It sits at the edge of the documented per-owned-name model — the FIFO is at an
  unowned name and the identical plant at two unowned names hangs the repository owner's own `git branch` — but the two
  sentences quoted promise a report and a refusal that do not happen, and no document states that the target of a
  symbolic ref is not inspected. A one-sentence boundary statement closes it; a code fix would prefix the canonical
  inventory (`for-each-ref refs/cws/` and the exact branch name) and read a symbolic ref's target raw before letting Git
  resolve it.

### Informational (not findings)

- **I-1 — A FIFO at a worktree worker's admin `HEAD` file, or a symlinked admin directory, hangs `status`, `collect`,
  worktree `spawn`, and `recover`** (`r2d.out` rows `r2d-admin_{fifo_head,symlink_admin_dir}`, all `TIMEOUT`).
  `require_plain_worktree_heads` deliberately skips a non-regular `HEAD` and a symlinked admin entry (`repository.py:685,
  :691-692`), but Git reads both. The admin directory is not an owned ref name and no document claims inspection of it;
  the fix is the same shape as 7.5ab's (refuse when `HEAD` is not a regular file or the admin entry is a symlink).
- **I-2 — `recover` marks a collected worker `broken` on a transient result-ref absence and never un-breaks it.**
  `r1_s1.out` rows `r1-*-discard.{after_mark,before_delete}`: after `discard-reset`, the next `recover` reports
  `collected-marked-broken`; restoring the ref leaves it `broken`; `status` then reports nothing for it (a `broken` record
  is outside the result audit, `audit.py:177`), and `r4_misc.py` → `r4-broken_from_collected-{clone,worktree}`: after
  `release`, `discard --abandon` deletes the worker content (rc 0, `abandoned`) while the commit object survives only
  unreferenced. This is the documented `broken` → release → abandon path and both steps are explicit, but once
  `collected` becomes `broken` the "last copy" is no longer flagged by `status`; the record still carries `result_ref`
  and `result_sha`, so `status` could keep reporting `result-ref-missing` for it and `--abandon` could keep refusing while
  they are unpreserved, mirroring S1's rule.
- **I-3 — Permission denial is a raw errno.** A `chmod 000` container directory (`r4-perm`) makes `status` exit 2 with
  `cannot inspect ref file …: [Errno 13] Permission denied` and `recover` report `recovery-failed` per worker. Not an
  occupant kind, nothing touched, fails closed; listed because S4's rule ("never a raw errno") was about occupants.
- **I-4 — A refused worktree spawn consumes an ID.** With A's branch name occupied, `spawn --worktree` allocates, then
  `add_worktree` refuses, and the worker is recorded `spawn_failed` (`r2_s2.out` `next_id: [6, 8]` after one refused
  worktree spawn plus one successful clone spawn). Documented as the observable gap; `status` is clean afterwards.
- **I-5 — Request retry against a quarantined worker waits out `--wait-seconds`.** `r2-quarantined-*` `A_retry`: the
  retry loops `recover` until the deadline (3.3 s with `--wait-seconds 3`; 120 s by default) and then fails with "timed
  out waiting for existing request worker 1; run recover". Pre-existing; a wait, not a Git block.
- **I-6 — `git fetch` in canonical still fails closed on a non-ref file anywhere under `refs/`** (seventh review's I-c;
  `rerun-m3_containers.out` `*-garbage_file`/`*-dir_nonempty` `collect_ready` rc 2 "fatal: bad object"). Git's behaviour.
- **I-8 — Non-empty directory attribution.** ARCHITECTURE.md:733-739 says a directory "(empty or not)" at a ref-shaped
  name is `orphan-namespace-ref` carrying the id "when the name has a worker's shape". For a non-empty directory the raw
  walk lists only the children, so outside the collected worker's pin and summary names (S3, fixed) the report is the
  child's id-less `orphan-namespace-ref` plus `result-ref-missing`/`branch-owner-ref-missing` where a recorded worker
  owns the name (`r3-{rec1_result,rec2_summary,rec2_branch_owner,unrec9_*}-dir_nonempty`). The occupant is reported and
  never touched; the reported name (`…/junk`) has no worker shape, so the promise attaches to a name that is not listed.
  Correct but less context than the sentence suggests; listing the directory itself would close it.
- **I-7 — Harness note.** Planting an occupant at a live worker's branch name destroys the real branch, so after the
  occupant is removed A is `task-branch-missing` (collected) or stays `broken` (ready, `ready-marked-broken`, the seventh
  review's I-d); a quarantined A whose branch was destroyed is re-preserved ("changed after its custody check") because
  its `HEAD` no longer resolves. All caused by the plant, not by Clonegrown.

## 3. Verification record

### S1 — CLOSED (`r1_s1.py` → `r1_s1.out`, 128 rows, both modes; `rerun-m8_quarantine_result.out`)

Setup: collected + released worker with an ignored file; `discard --discard-ignored --discard-private-refs` killed at
each failpoint; then `git update-ref --no-deref -d <result ref>`; then `status`, `recover` ×2, `discard --force`,
`discard --force --discard-ignored --discard-private-refs`, then the ref restored and `recover` again.
- `discard.after_quarantine` and `discard.after_recheck` (content in quarantine, fingerprint recorded / deletion
  authorized): `status` → `quarantine-preserved` + `result-ref-missing`; `recover` ×2 → `quarantine-preserved`,
  `quarantine_error` "worker 1 is kept in quarantine at …: its collected result … is no longer preserved in canonical";
  both forced discards rc 2 "refusing deletion because the collected result is no longer preserved in canonical; the
  quarantined worker is the last copy and is kept"; quarantine present throughout; after the ref is restored `recover` →
  `discard-finished`, `discarded`, issues `[]`. No `.lock` residue.
- `discard.after_mark` and `discard.before_delete` (nothing moved): `recover` → `discard-reset` (`collected`,
  `result-ref-missing`); the second `recover` → `collected-marked-broken` (I-2); every discard flag combination refused
  (`--abandon` required for `broken`); slot present.
- `discard.after_delete`, `discard.after_admin_cleanup`, `discard.after_branch_cleanup` (content already proved absent
  with the result present at authorization): `recover` → `discard-finished`, then `discarded-result-missing`; `status`
  → `result-ref-missing`. Nothing left to preserve.
- `changed_in_quarantine`: `recover` preserves ("changed after its custody check"); ref deleted → `discard --force …`
  rc 2 and `recover` → `quarantine-preserved`; ref restored → `discard --force` alone re-asks `--discard-ignored`
  (one missing category per refusal), then the full acknowledgement deletes (`discarded`).
- `fifo_at_result_quarantined`: FIFO at the result name → `orphan-namespace-ref` + `quarantine-preserved` +
  `result-ref-missing`, forced discard refused, occupant unchanged, restored → `discard-finished`.
- `first_auth_ref_missing`: every flag refused ("collected result is not preserved" / one-shot); `abandon_unaffected`:
  an abandoned uncollected worker interrupted at `after_quarantine` → `abandon-finished`; `control_intact` →
  `discard-finished`. `rerun-m8`: resume/reauth rows now `quarantine-preserved` / rc 2, controls delete.

### S2 — CLOSED for FIFO and symlink-to-FIFO at the branch name; adjacent gaps S5, S7, I-1

`r2_s2.py` (`r2_s2.out`) + `r2b_s2_rest.py` (`r2b_s2_rest.out`): A worktree in {ready, collected, quarantined
(killed at `discard.after_quarantine`), publishing (killed at `spawn.after_publish`)} × {FIFO, symlink→FIFO} at A's
branch name, with B clone `ready`, C worktree `ready`, D worktree collected+released, E worktree released. Every row:
`collect B`, `collect C`, `spawn --worktree`, `discard D`, `discard --abandon E`, A's own `discard`/`discard --force`,
A's request retry, and `recover` return in 0.1–0.4 s (rc 2 "linked worktree app has HEAD on refs/heads/<A>, whose name
holds a symlink or non-regular file; Git would block resolving it. Remove that occupant by hand, then retry", or A's
own "task branch name holds a symbolic ref or foreign ref file"); `spawn` (clone) rc 0; `status` returns
(`task-branch-foreign` + `worker-authentication-failed` for a live A, `owner-process-dead` for quarantined/publishing);
`occupant_unchanged: true`, external FIFO intact, no `.lock` files; refused discards leave D/E `discarding` with content
in quarantine (`quarantine-preserved`); after the occupant is removed one `recover` reports `discard-finished` and
`abandon-finished` and `status` is clean (A itself per I-7). `rerun-m2_cross_worker.out` (the seventh review's probe):
0 Clonegrown timeouts (the only `TIMEOUT` line is its raw-Git attribution row), `records_after_*` as expected;
`rerun-m6_interrupted_worktree.out`: 0 timeouts, `publishing`/`staged`/`intent-only` rows refuse.

### S3 / S4 — CLOSED (`r3_codes.py` → `r3_codes.out`; `rerun-m4_issue_codes.out`; `rerun-m3_containers.out`; `r4_misc.py`)

153 rows = 17 names × 9 occupant kinds, each in a fresh repository holding a collected+released clone (worker 1) and a
ready worktree (worker 2). Names: recorded pin/summary/`results/<sha>` of worker 1, pin/summary/branch-owner of
worker 2, pin/summary/`results/<40 hex>`/branch-owner of unrecorded id 9, containers `bases`, `workers`, `workers/1`,
`workers/1/results`, `workers/9`, the namespace root, and `refs/cws` above it. Kinds: FIFO, symlink→FIFO, non-ref file,
empty directory, non-empty directory, symlink→directory, symlink→external file, dangling symbolic ref, live symbolic ref.
Per row: `status`, `recover`, `spawn` (clone), `status` again.
- **No hang, no raw errno, no failure:** 0 `TIMEOUT`, 0 `[Errno` in any stderr, `status` rc 0 in all 153 rows (both
  calls), `recover` rc 0 in all rows, no unexpected `next_id` change, occupant unchanged except the two documented
  Git-creates-a-ref-in-an-empty-directory rows (`cont_bases-dir_empty`, `root-dir_empty`).
- **Recorded names (S3/I-e):** FIFO, non-ref file, and empty directory at worker 1's pin, summary, result name and at
  worker 2's pin, summary, branch-owner → exactly one `orphan-namespace-ref` carrying the id (the result name adds
  `result-ref-missing`, the branch-owner name adds `branch-owner-ref-missing`); a non-empty directory at a pin or
  summary name of the collected worker → `orphan-namespace-ref` with the id ("a non-regular file or directory sits at
  this worker's … name") plus the child as a separate id-less `orphan-namespace-ref` (the seventh review's S3 rows now
  correct); symlink→FIFO/directory/external file and dangling/live symbolic refs → `namespace-ref-symbolic` with the id
  (`recover` adds `base-ref-ambiguous` for a live symref at a pin name and `summary-ref-{symbolic,conflict}-left` at
  the collected summary, all untouched).
- **Unrecorded id 9:** every single-file kind → `orphan-namespace-ref`/`namespace-ref-symbolic` with `id: 9`.
- **Containers and root (S4):** FIFO or non-ref file at `bases`, `workers`, `workers/1`, `workers/1/results`,
  `workers/9`, the root, and `refs/cws` → `status` rc 0, the container reported as `orphan-namespace-ref` (no id;
  `refs/cws` itself is above the namespace and is not listed), every recorded name below it reported per worker as
  `orphan-namespace-ref` "a non-regular file or directory sits at this worker's … name" (with the id) and
  `result-ref-missing`; `spawn` refuses with allocation evidence ("base ref name occupied by a non-regular file") where
  the pin name is below the occupant and succeeds otherwise; a symlink→external file behaves the same with
  `namespace-ref-symbolic` for the container; a symlink→directory at any container or at the root →
  `namespace-ref-symbolic` (I-b's root case now reported) with the names below *followed*, not foreign (S6). `r4_misc`
  `r4-refs_cws_fifo` and the seventh review's `rerun-m3_containers.out` agree (`status` rc 0 in every row that
  previously exited 2).
- **Residual (informational, I-8 below):** a non-empty directory at a ref-shaped name the per-worker audit does not
  inspect (worker 2's ready-state summary and branch-owner, worker 1's `results/<sha>`, every unrecorded id 9 name) is
  reported only through its child (`…/<name>/junk`, `orphan-namespace-ref`, no id) and, where applicable,
  `result-ref-missing` / `branch-owner-ref-missing` with the id; the directory's own name is not listed.

### Seventh review's informational notes

- I-a wording: ARCHITECTURE.md:749 now reads "before a Git command that resolves its `HEAD` runs in the worker" —
  matches `rerun-p4_spot.out` and `m1`-class behaviour.
- I-b: a symlink at the namespace root is now reported (`r3-root-link_dir`, `rerun-m3 m3-root-link_dir`:
  `namespace-ref-symbolic`); the followed-container behaviour is stated at ARCHITECTURE.md:743-745 — but the new clause
  "every name below it is treated as foreign" overclaims (S6).
- I-c: unchanged Git behaviour (I-6). I-d: unchanged (`ready-marked-broken` in every `r2-ready-*` row). I-e:
  `orphan-namespace-ref` at a recorded worker's name now carries the id (`r3-rec*` rows, `rerun-pC_namespace.out` gained
  `"id": 1`).

### Q1 (sixth review) — holds

`rerun-q1_r1.out` and `rerun-q3_attribution.out` are byte-identical to the seventh review's after path/hash
normalization; `r1-*-fifo_at_result_quarantined` and `r3-rec1_{summary,result}-{fifo,link_fifo}` (S3/S4 section) add
the same-session rows.

### R1–R4 (fifth review), N1–N3 (fourth), F1–F5 (third) — hold

`rerun-p1_ancestry`, `rerun-p1b_forged_recovery`, `rerun-p1g`, `rerun-p3e`, `rerun-p4_spot`, `rerun-q1_r1`,
`rerun-q3_attribution` identical to the seventh review's outputs after normalization; `rerun-p2_occupants` 348 rows, 0
IDs consumed, the same 13 documented-class changes (packed-refs rewrites, base-pin drop at the recorded value, the
worker's own branch-owner deletion, Git's removal of an empty directory when creating the branch-owner ref);
`rerun-p6_recover_occupants` and `rerun-p2b_clone_direct` differ only in hashes; `rerun-pA_env` 589 Git invocations,
`A1_git_invocations_missing_any_GIT_line: 0`, grafts not honoured (`A2`/`A3` = 0); `rerun-pB_reauth`,
`rerun-pC_namespace` (plus the new `"id": 1`), `rerun-pE_spot` identical. F4 phrase sweep of README/SKILL/ARCHITECTURE
finds nothing (only "explicit guarantees and limits" at ARCHITECTURE.md:246, a heading); F5 boundary sentences present.

### Six second-review classes — all PASS (`rerun-pD_classes.out`)

class1 private refs (no flag rc 2, flag rc 0), class2 dangling symbolic task branch (worktree spawn rc 2, `next_id` 1,
bytes intact, clone spawn rc 0), class3 dangling control links (init/spawn rc 2, links intact), class4 CLI init symlink
(absolute/relative/default rc 2), class5 `GIT_CONFIG`/`GIT_CONFIG_COUNT` (spawn rc 0 ×2), class6 rewrite (default rc 2,
flag rc 0, repeat rc 0, new commit rc 2 under either), F5 flagless discard rc 0.

### Step 7.5i collection-timing properties — 5/5 (`rerun-timing.out`)

`direct_conflict` preserved at the planted value, worker `ready`; `symbolic_exact_conflict` refused, target intact;
`locked_metadata_finalization` result/summary move attempts rc 128 while prepared, record `collected`;
`object_only_recovery` published through one all-zero expected-old `write_ref`, `collect-finished`;
`object_only_recovery_conflict` → `collect-reset-ready`, conflict preserved.

## 4. Coverage-map spot checks

| Item | Result |
|---|---|
| 5.1 active-writer race / 7.5i | Timing 5/5; occupants at summary/result names during collect and recovery refused or left (`rerun-p6`, `rerun-p2b`, `r1 fifo_at_result`). Gap: S7 (hang, no custody effect). |
| 5.2 ignored work | First refusal names count and sample; re-authorization re-asks (`r1 changed_in_quarantine restored_discard_force_only`, `rerun-pB`). |
| 5.3 unchecked deletion | Quarantine, fingerprint recheck, preserved-on-change, result-preservation at resume and re-authorization (S1 record). |
| 5.4 branch ownership | Create-only allocation refuses every occupant (`rerun-p2` A rows, 0 consumed); cleanup retains a foreign name/owner (`rerun-p3e`, `rerun-m4 m4B_*`, `rerun-p2` changed rows). |
| 5.5 changed published recovery | `recovery.py:217-248`; `test_worktree` 25 + `test_parent_interruption` 6 pass; `r2d-*-control` promotes untouched B. Gap: S5. |
| 5.6 installer root | `sh -n install.sh` OK; `test_installer` 25/25 in the suite; not hand-probed. |
| 5.7 / 5.8 remotes and config | `_canonicalize_remote_url` (`repository.py:140-148`), `ConfigOccurrence(value=None)` (`:43-48`, `:93-106`) read; `test_repository` passes; credentialed remote copied verbatim (`rerun-pE 5.10_remote_copied: true`). |
| 5.9 Git sanitation | `rerun-pA_env`: 589 invocations, none missing the identity-only environment; `rerun-pD class5`. |
| 5.10 secret-bearing errors | `rerun-pE 5.10_command_failure_text` `https://<redacted>@example.invalid/…`, `5.10_raw_git_shows_secret: false`; `rerun-p4 5.10_redaction secret_in_error: false`. |
| 5.11 stale request reuse | Same params → same worker; different → refused; discarded with deleted result → retry refused, `discarded-result-missing` (`rerun-pE 5.11_*`). |
| 5.12 incomplete status | 29 codes at ARCHITECTURE.md:605-616 = 29 emitted by `audit.py`/`recovery.py` (my regex and `rerun-pE 5.12_codes`: both empty diffs). Gaps: S6 wording; I-2. |
| 5.13 create-only allocation | Rewound counter → "already has a record, slot directory, operation lock file; nothing was changed" (`rerun-pE 5.13`); 348 + this review's occupant rows consume nothing. |
| 5.14 API/CLI parity | `rerun-p4 5.14_parity`: both `mode: clone, strong: false`; worktree+strong refused by both. |
| 5.15 invalid generated branch | `x.lock` → "generated task branch is invalid for Git", `next_id` unchanged, no refs/records (`rerun-pE`, `rerun-p4`). |
| 5.16 low-level errors | Five-part context on `collect 999` (`rerun-p4 5.16_context parts: [true×5]`) and on every refusal quoted above. |
| 5.17 timing gate | `grep ratio tests/campaign/hardening_suite.py` matches only the word inside `operation`; `parallel_spawns_unique` passes in both modes. |
| 5.18 one-shot | `--abandon` and `claim` refused for a collected worker; leased discard refused under every flag (`rerun-pE 5.18`, `rerun-p4 5.18_one_shot`, `r1 first_auth discard--abandon`). |
| Comment/public overclaims | Notices current (README.md:17-34, SKILL.md:14-25, ARCHITECTURE.md:6-16) and require a fresh review; F4 phrases absent. Overclaims found: ARCHITECTURE.md:376-380 (S5), :739-743 (S6), :746-756 (S7). |
| `CWSError`, heartbeat, failpoints | `grep -rn CWSError clonegrown/` empty; `heartbeat` only as a hidden bookkeeping key (`cli.py:31`); `failpoint` gated on `CLONEGROWN_TEST_MODE == "1"` (`core.py:485`). |
| retention, teardown, license, package | `pyproject.toml`: `license = "Apache-2.0"`, `license-files`, `requires-python >=3.11`, dynamic version `0.1.0a1`; wheel from the rsync copy `clonegrown-0.1.0a1-py3-none-any.whl` 100,093 bytes sha256 `f847b47e575e73ef640f68151ddf79f2c276b1eb74e851af6af248bcbb108f66`, `License-Expression: Apache-2.0`, `licenses/LICENSE` present; fresh venv `clonegrown --version` and `python -m clonegrown --version` both `clonegrown 0.1.0a1`. Result refs and records survive every normal discard in `r1` control rows. |
| macOS, Python/Git versions, filters/LFS, resource boundaries, repository diversity, repeated verification, auxiliary-ref cost | Not freshly exercised (section 6); `test_filters_and_resources` 4, `test_auxiliary_refs` 4, `test_campaign_records` 16, `test_lease` 10 pass in the suite. |

## 5. Gate results

- **Unit suite:** `cd /home/serrecchia/Projects/clonegrown && python3 -m unittest discover -s tests -v` (in the
  checkout, no cache prefix) → **Ran 284 tests in 311.415 s, OK** (0 failures, 0 errors, 0 skipped); wall 23:13:43 →
  23:18:54; log `/tmp/clonegrown-review6-unittest.log`. The suite grew from the seventh review's 280 to 284.
- **Hardening, clone mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`: git lacks reftable support),
  **0 failed**; sum of case seconds 72.1; wall 23:19:25 → 23:20:43 (1 min 18 s);
  `sha256 07c6f5f8902978effcfef1503a26a8dcf41de8065b5258876419d9eca33ce653 /tmp/clonegrown-review6-hardening-clone.json`
  (log `/tmp/clonegrown-review6-hardening-clone.log`).
- **Hardening, worktree mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`), **0 failed**; sum of case
  seconds 72.2; wall 23:20:43 → 23:22:01 (1 min 18 s);
  `sha256 577bc832e581bccecca1152325de1ad28c9ce341d48bf94533eb19b016bd56e7 /tmp/clonegrown-review6-hardening-worktree.json`.
- `git diff --check` clean; `sh -n install.sh` OK; `python3 -m compileall -q clonegrown tests` OK with
  `PYTHONPYCACHEPREFIX=/tmp/clonegrown-review6-pyc`; wheel build (`python -m build --wheel` in a venv on the rsync copy
  `/tmp/clonegrown-review6-build/src`) and isolated install OK (above); no `build/`, `dist/`, or `egg-info` in the checkout.
- Versions: CPython 3.12.3, Git 2.43.0 (`/usr/bin/git`), Linux 6.17.0-35-generic.
- Tree fingerprints: start `da3b1b0668b3336ea23f9b41e7e46fa15af744e196fd4341d8d076b5ada6e96f`, end `3d2870cf71535b197354bf40bdde479b6ee505a764044b4628a34e7a6e7cc36f`;
  `git status --short` 23 entries at both ends (only `PLAN.md`/`HANDOFF.md` differ, header).

## 6. Not verified, and why

- Hosted CI on a pushed revision, macOS, CPython 3.11, exact Git 2.29.0: not available locally; the tree is uncommitted.
  Whether Git 2.29's `for-each-ref` resolves symbolic refs the same way (S7) was not checked on that version.
- reftable repositories and `GIT_REF_FORMAT` end to end: Git 2.43 cannot create them (hardening skip); the
  `inventory is None` fallbacks were read, not exercised.
- Random-kill and state-machine campaign seeds, `real_repository_qualification.py`, and the benchmark harnesses: not in
  the requested gate list and not run.
- A socket occupant (a FIFO proves the class); occupants inside a worker's own private refs (the agent's).
- The fifth review's `p3_wording.py`, `p5_fifo.py`, and the seventh review's `m1_matrix.py`/`m5_gitlog.py`/`m7_attribution.py`
  were not rerun (their FIFO rows are covered by `r1`, `r2`, `r3`, and the `m2`/`m6`/`m4`/`m3`/`m8` reruns).
- Genuine disk/inode exhaustion, network filesystems, Git LFS, native Windows: stated boundaries, not exercised.
- `HANDOFF.md` and the Step 7.5a–7.5ab completion records: deliberately not read.

Probe inventory: `/tmp/clonegrown-review6-probes/{h6,r1_s1,r2_s2,r2b_s2_rest,r2d_recover_other,r2e_attribution,
r2e2_unowned,r3_codes,r3b_symlinked_container,r4_misc}.py`, `r2c_rawgit.sh`, `gitlog.sh`, with outputs `r1_s1.out`,
`r2_s2.out`, `r2b_s2_rest.out`, `r2d.out`, `r2e.out`, `r2e2.out`, `r2c_rawgit.out`, `r3_codes.out`, `r3b.out`, `r4_misc`
(printed inline; rows quoted above), `rerun_all6.sh` → `rerun-*.out`/`.err`, `rerun.log`; disposable repositories under
`/tmp/clonegrown-review6-work/` (and the earlier reviews' work roots for the reruns); suite log
`/tmp/clonegrown-review6-unittest.log`; hardening logs and JSON `/tmp/clonegrown-review6-hardening-*`; wheel and venvs
under `/tmp/clonegrown-review6-build/`.

## Ninth fresh review (seventh Step 7.5 pass, after Step 7.5ac): no-go

A ninth fresh reviewer found S5–S7 and the notes closed for the cases they
named, every earlier finding holding, the suite 289/289, and both hardening
modes clean, and returned no-go on two Low findings:

1. **T1 (low).** A symbolic ref at an owned name inside the namespace whose
   chain ends at a FIFO still reached Git through the prefixed
   `for-each-ref`, through `rev-parse` in `resolve_ref`/`ref_points_at`,
   and through the collect fetch and clone; a detached-HEAD worktree
   worker's branch name was not covered by the admin-HEAD preflight. Step
   7.5ad owns it.
2. **T2 (low).** A foreign container occupant made `recover` mark every
   collected worker below it `broken` durably. Step 7.5ad owns it.
3. Informational: a FIFO at a worker's own `HEAD` or admin `gitdir`; a
   symlinked next-ID container; the third interrupted-spawn outcome absent
   from `SKILL.md`. Step 7.5ad owns the `gitdir` inspection and the wording.

The reviewer's full report is preserved verbatim below.

---

# Clonegrown final cold review — release qualification (ninth fresh review)

Date: 2026-09-03. Reviewer: fresh agent, read-only on `/home/serrecchia/Projects/clonegrown` (uncommitted working
tree on `main`, base `c9728a0`). Environment: Linux 6.17.0-35-generic, CPython 3.12.3, Git 2.43.0 (`/usr/bin/git`).
Every probe, log, wheel, venv and result lives outside the checkout under `/tmp/clonegrown-review7-*` (new probes and
outputs in `/tmp/clonegrown-review7-probes/`, disposable repositories in `/tmp/clonegrown-review7-work/`, reruns of
earlier reviews' probes as `/tmp/clonegrown-review7-probes/rerun-*.out`). `HANDOFF.md` and the Step 7.5a–7.5ac
"Completion record" sections were not read; no `.env`-pattern file was opened; nothing inside the checkout was modified
(the wheel and sdist were built from an `rsync` copy; `compileall` ran with `PYTHONPYCACHEPREFIX=/tmp/clonegrown-review7-pyc`;
the unit suite ran in the checkout without a cache prefix, as CI does). Every Git command and Clonegrown call that could
touch a planted FIFO ran under a 5–20 s timeout (`TIMEOUT` below means the process was killed while blocked); the 230
Git grandchildren those kills left blocked on FIFO opens were killed at the end (`kill -9`, matched by cwd/argv under the
review work roots). One blocked `git symbolic-ref … refs/heads/zz-fifo` (pid 3906144, cwd `/tmp/tmpvxs86rap/demo`,
started 00:36:27, before this review began) belongs to another session's test run and was left alone.

**Tree fingerprints.** `git diff | sha256sum` at start `1e9f3ad478d1a78f78ddaaf59d9500307042324d09eb062a5165a05cf82b9190`,
at end `c6717371d1ac2bcae119f246ca813e1e624651b9c70cc502ba3672c178bf657d`; `git status --short` lists 23 entries at
both ends (22 modified tracked files plus untracked `tests/test_collect_policy.py`). The fingerprints differ because
another session rewrote `README.md`, `ARCHITECTURE.md` and `research/FINAL_COLD_REVIEW.md` at 00:46:58 and `PLAN.md`/
`HANDOFF.md` at 00:57:57 while this review ran. No product module or test changed: every `clonegrown/*.py` and
`tests/*.py` mtime precedes the review's first command (latest: `lifecycle.py` 00:41:54, `test_worktree.py` 00:39:31),
and the unit suite (started 00:47:53) and both hardening runs exercised that code. Every document sentence quoted below
was re-read after 00:46:58, so the wording judged is the current wording. `git diff -- clonegrown README.md SKILL.md
ARCHITECTURE.md tests | sha256sum` at the end: `eb700802229fcd7db882b362f829e811a60e0e4068bfd582f86d687047509b3a`.
sha256 (first 12) of the product reviewed: audit `52b5f6f500ba`, cli `a309e205fbb4`, core `fc2af01adbd3`, lifecycle
`5bab2d832e7c`, recovery `c54e33caa975`, repository `ff1e7e06f5d8`, state `043a08cd21ac`, worker `ba6c749a733e`;
README `773630aa53c6`, SKILL `b1b2789e2375`, ARCHITECTURE `d475b7a53cb1`.

## 1. Verdict: NO-GO

The eighth review's findings are closed as stated for the cases they named: S5 (another worker's interrupted spawn stays
`publishing`, is reported `recovery-failed`, and is promoted once the occupant is gone — also true for interrupted
collects, discards, abandonments and unpublished worktree spawns of other workers), S6 (every read below a symlinked, FIFO
or plain-file container is foreign; the result is not preserved, discard and re-collection are refused, nothing is
written, allocation refuses a symlinked `bases`/root), S7 for the case it named (a symbolic ref at a worktree worker's
branch name whose target is a FIFO or symlink-to-FIFO, with the worker's `HEAD` on that branch: `status` reports
`task-branch-foreign`, clone spawn, worktree spawn, every collect and every discard refuse by name in ≤0.4 s, `recover`
returns, and the unowned-name boundary is literal and true), I-1 (a FIFO admin `HEAD`, a symlink at admin `HEAD`, or a
symlinked admin entry is refused by name before `worktree add`, the collect fetch and the clone), and I-2 (a `broken`
worker's recorded result is audited until it is abandoned). S1–S4, Q1, R1–R4, N1–N3, F1–F5, the six second-review classes
and the five Step 7.5i properties hold on reruns. The unit suite passes 289/289, both hardening modes pass 56 with the one
conditional reftable skip, and every static and packaging gate passes.

Release is blocked by one open finding that contradicts sentences the documents state as properties, plus one Low
finding the caller may reclassify:

- **T1 (Low)** — a symbolic ref at an *owned* name **inside Clonegrown's namespace** (`workers/<id>/result`,
  `workers/<id>/results/<sha>`, `bases/<id>`, `workers/<id>/branch-owner`, and the next ID's pin and summary names) whose
  target is a FIFO, directly, via a symlink, or through a chain of symbolic refs, blocks `status`, `recover`, every clone
  and worktree spawn (in the *prefixed* `for-each-ref refs/cws/<ws>/`), every collect (in `fetch`), and the discard of the
  worker whose immutable result name holds it (in `rev-parse --verify`); the same object at the next ID's generated branch
  name blocks a worktree spawn inside allocation evidence; and at a live or collected worktree worker's branch name whose
  `HEAD` is detached (ordinary agent state) it blocks every clone spawn and every collect. S7's closure ("reported and
  refused by name without any Git enumeration blocking") holds only for the branch name of a worker whose `HEAD` is on it.
  Nothing is written, replaced, deleted or consumed (except the documented clone-spawn ID gap), and everything settles once
  the occupant is removed, but ARCHITECTURE.md:729-736, :761-762, :764-765 and :765-769 promise otherwise.
- **T2 (Low)** — a foreign occupant (symlink, FIFO or plain file) at a container of the namespace makes one `recover`
  durably mark **every** collected worker below it `broken` (`collected-marked-broken`); restoring the container brings
  every result ref back and clears `status`, but the records stay `broken` and normal `discard` is refused forever
  ("use explicit --abandon"). This is the mechanism the eighth review listed as informational I-2; Step 7.5ac's S6 fix
  widened its trigger from "the result ref is genuinely gone" to "anything foreign sits above it", and README.md:204-206
  says `recover` "reconciles only the recorded cases whose ownership and next action it can establish; it reports the
  rest". The verdict does not hinge on T2.

Everything else I found is informational and listed as such.

## 2. Findings, ranked by severity

### T1 — Low — a symbolic ref at an owned name whose target is a FIFO still blocks Git wherever Clonegrown lets Git resolve the name rather than reading the target raw (claim mismatch; robustness; S7 not closed as stated)

- **Claims.** ARCHITECTURE.md:729-736: "Every owned ref name is `lstat`-inspected before any Git command reads it
  (`loose_ref_occupant`, applied by `is_foreign_ref`, `resolve_ref`, `ref_points_at`, the result/summary transaction, and
  allocation evidence) … none is ever opened by Git (a FIFO would block it)". :761-762: "other workers' operations
  therefore fail closed instead of blocking". :764-765: "The inventory of Clonegrown's own namespace is confined to
  `refs/cws/<workspace>/` for the same reason." :765-769: "A symbolic ref at a name Clonegrown does **not** own whose target
  is a FIFO is outside this inspection … that is a stated boundary." PLAN.md Step 7.5ac bullet: "`loose_symbolic_target`
  reads a symbolic ref's target raw and `is_foreign_ref` uses it before asking Git".
- **What the code does.** Only `is_foreign_ref` (`repository.py:779-793`) reads a symbolic ref's target raw. Three other
  readers of owned names hand a regular symref file to Git, which follows it and `open()`s the FIFO target:
  `raw_ref_inventory` runs `for-each-ref --format=%(refname)%00%(objectname)%00%(symref) refs/cws/<ws>/` *before* its raw
  walk (`repository.py:864-868`; used by `NamespaceRefs`, `audit.py:57`, for every `status`/`recover`, and by
  `allocation_evidence`, `worker.py:670`, for every spawn); `resolve_ref` (`:961-973`) and `ref_points_at` (`:1096-1107`)
  only reject `link`/`special` occupants and then run `rev-parse --verify`. Git's loose-ref enumeration skips a FIFO that
  sits *at* a name (`DT_FIFO`), which is why the earlier FIFO-at-name rows passed, but a symref is a regular file, so Git
  reads it and resolves the target. The canonical-side `fetch` and `git clone` enumerate every ref for the same reason.
- **Reproduction** (`/tmp/clonegrown-review7-probes/n1_symref_namespace.py` → `n1_symref_namespace.out`, 24 rows =
  6 names × 4 kinds, each in a fresh repository with a collected+released clone (1) and a ready worktree (2); kinds:
  symref → unowned FIFO `refs/heads/zz-fifo`, symref → FIFO inside the namespace `bases/9`, symref → symlink → FIFO, and a
  chain through a second symref at `workers/9/result`): raw `git for-each-ref refs/cws/<ws>/` TIMEOUT in 24/24; `status`,
  `recover`, `spawn` (clone), `spawn --worktree`, `collect 2` TIMEOUT in 24/24 (8 s each); `discard 1` completes (rc 0)
  except when the immutable result name `results/<sha>` itself holds the symref (4/4 TIMEOUT); `next_id` unchanged;
  occupant byte-identical; no `.lock`; after removal two `recover`s settle every record (worker 1 `broken` +
  `result-ref-missing` only in the four rows where the plant replaced its real result ref; worker 2
  `branch-owner-ref-missing` where the plant replaced its owner ref — harness-caused). Attribution with a logging
  `CLONEGROWN_GIT` (`n1b_attribution.py` → `n1b.out`): `status`/`recover` block at call 9, `for-each-ref … refs/cws/<ws>/`;
  clone and worktree spawn at call 11, `--git-dir=/dev/fd/3 for-each-ref … refs/cws/<ws>/`; collect of the worktree
  worker at call 48, `fetch …`. Next-ID names: a symref→FIFO at the generated branch name `refs/heads/agent/<ws>/3-next-task`
  blocks `spawn --worktree` at call 12, `--git-dir=/dev/fd/3 rev-parse --verify --quiet refs/heads/…^{commit}`
  (allocation evidence; ID not consumed) and a clone spawn at call 24 inside `git clone` after consuming ID 3 (record
  `cloning`, cleaned by the next `recover` as `spawn-cleaned`); a symref→FIFO at the next pin name `bases/4` blocks the
  clone spawn and `status` at `for-each-ref` (ID not consumed). Raw Git in canonical with only the namespace symref
  planted: `for-each-ref refs/cws/<ws>/`, `rev-parse --verify <name>`, `symbolic-ref -q <name>` TIMEOUT; `for-each-ref
  refs/heads/`, `worktree list`, `status`, `update-ref` return. Detached-`HEAD` variant (`n2_detached_head.py` →
  `n2_detached_head_b.out`, 6 rows): worktree worker A `ready` or `collected`, `git checkout --detach HEAD` inside A, then
  symref→FIFO or symref→symlink→FIFO at A's branch name: `status`, `recover`, `spawn --worktree`, `discard` of a collected
  worktree return; `spawn` (clone), `collect` of a clone and of another worktree TIMEOUT (`git clone` / `fetch`); a plain
  FIFO at the same name blocks nothing. After removal one `recover` settles everything.
- **Affected.** `clonegrown/repository.py:832-907` (`raw_ref_inventory`), `:961-973` (`resolve_ref`), `:1096-1107`
  (`ref_points_at`); `clonegrown/audit.py:57`; `clonegrown/worker.py:670-699`; `clonegrown/lifecycle.py:549-553`
  (clone) and `:690-708` (fetch); ARCHITECTURE.md:729-769; `tests/test_worktree.py:378` covers only the branch name with
  `HEAD` on it.
- **Classification.** Low claim mismatch (robustness), the class of R4/Q1/S2/S7: a same-user process planting under
  canonical's `.git/refs/`; nothing written, replaced, deleted or lost; everything settles when the object is removed.
  It is the direct continuation of S7 — the raw-target read was added to one reader and the inventory was prefixed, but
  the prefixed inventory, `resolve_ref` and `ref_points_at` still let Git resolve symrefs at owned names, and the stated
  boundary attributes the enumeration block to unowned names only. Class fix: do the raw walk first and never run
  `for-each-ref` over a subtree in which the walk found a `symref:` entry (or resolve packed refs only through
  `for-each-ref` on the exact names the walk did not find loose); read the target raw in `resolve_ref`/`ref_points_at` as
  `is_foreign_ref` does; and either extend `require_plain_worktree_heads` to every owned branch name of a live worktree
  worker (detached `HEAD` included) or state the detached-`HEAD` case as a boundary.

### T2 — Low — a foreign occupant at a container of the namespace makes one `recover` durably mark every collected worker below it `broken`, and nothing un-breaks them once the container is restored (claim mismatch; adjacent to S6 and the eighth review's I-2)

- **Claims.** README.md:204-206: "`recover` reconciles only the recorded cases whose ownership and next action it can
  establish; it reports the rest." ARCHITECTURE.md:479: "`recover` reconciles only what a record's status makes
  unambiguous". ARCHITECTURE.md:740-745 says a container occupant "is reported … and every name below it is treated as
  foreign" — it does not say every collected record below it becomes terminal.
- **What the code does.** `_recover_collected` (`recovery.py:698-711`) calls `ref_points_at`, which is now `False` for
  every name below a foreign container (`loose_ref_occupant`, `repository.py:643-659`), and then `mark_broken("preserved
  result ref missing", "collected-marked-broken")`. `broken` has no path back to `collected` (`run()`, `recovery.py:460-482`).
- **Reproduction** (`n8_container_breaks.py` → `n8.out`, 6 rows; `n5_container.py` → `n5_container_c.out` populated rows;
  `rerun-r3b.out`; `rerun-r3_codes.out`): three collected workers (clone, worktree, clone); the real `workers` container or
  the namespace root is moved aside and replaced by a symlink to it, a FIFO, or a plain file. `status`: the container is
  `namespace-ref-symbolic`/`orphan-namespace-ref` and every worker `result-ref-missing`. `recover`: `1:collected-marked-broken`,
  `2:collected-marked-broken`, `3:collected-marked-broken` in all six rows. The occupant is removed and the real container
  moved back: every `result_ref` resolves (`result_refs_resolve: true`), `status` issues `[]`, `recover` `[]`, all three
  records still `broken`; `discard 1` (released, previously collected) → rc 2 "refusing to delete an uncollected worker;
  use explicit --abandon". The eighth review's own `r3_codes` matrix shows the same effect in 54 rows (`rerun-r3_codes.out`,
  identical count in `/tmp/clonegrown-review6-probes/r3_codes.out`), and `rerun-r3b.out`/`n5` show it for a symlinked
  `workers/1`, `workers/1/results`, `workers`, and the root.
- **Affected.** `clonegrown/recovery.py:698-711`; README.md:204-206; ARCHITECTURE.md:479, :740-745.
- **Classification.** Low claim mismatch. No content is deleted and the immutable result refs survive; the exit path
  (`release` + `discard --abandon`, which deletes the checkout and leaves the commit reachable only through the still-present
  result ref and the `abandoned` record's `result_ref` field) is explicit. But a `recover` the documents describe as
  reporting what it cannot establish converts a transient, reported occupant *above* the workers into a terminal state for
  every collected record in the workspace. The eighth review saw the "never un-breaks" half and listed it as informational
  (I-2); Step 7.5ac closed the audit half only, and its S6 fix made any container occupant a trigger. If the caller keeps
  the eighth review's classification, this drops to informational; I list it as a finding because the trigger widened and
  the README sentence is stated as a property. Class fix: treat an unconfirmable result the same way recovery treats a
  foreign occupant elsewhere — report (`result-ref-missing` is already emitted) and leave the record `collected` — or let
  `_recover_collected` restore `collected` when the recorded result ref resolves again.

### Informational (not findings)

- **I-A — the worker's own `HEAD` as a FIFO hangs `status`, `recover`, and that worker's own discard.** A FIFO at a
  worktree worker's admin `HEAD` or at a clone's `.git/HEAD` (`n4_admin.py` → `n4_admin_b.out`, rows `n4-fifo_head`,
  `n4-clone_fifo_head`): `collect` of every other worker and both spawns are refused by name ("linked worktree app has a
  HEAD that is not a regular file") — I-1 closed as stated — but `status`, `recover` and the worker's own `discard
  --abandon` block inside `verify_worker` → `git rev-parse --show-toplevel` *in the worker* (Git validates `HEAD` while
  discovering the repository). The worker's private Git directory is the agent's, no document claims inspection of it, and
  ARCHITECTURE.md:797-799 says a damaged worker Git directory makes `status` "fail" — a hang is not a failure, so the
  sentence is imprecise for this object. A symlinked `HEAD` (→ FIFO) and a symlinked admin entry instead make Git refuse
  the worker ("not a non-bare Git working tree"): `status` returns, `recover` marks the worker `ready-marked-broken`.
- **I-B — a FIFO at an admin `gitdir` file blocks the canonical-side commands the guard protects, and blocks Clonegrown's
  own Python.** `n4-fifo_gitdir`: `collect` (clone and worktree), `spawn --worktree`, `recover` and the worker's own
  discard TIMEOUT; `status` and clone spawn return. `git worktree add/repair` read every admin entry's `gitdir`; `recover`
  blocks in `locate_worktree_admin` → `_read_pointer(admin / "gitdir")` (`worker.py:1030`), a plain Python read. The
  guard inspects only `HEAD` and the entry's type (`repository.py:706-742`), and ARCHITECTURE.md:754-761 claims exactly
  that, so no claim is contradicted; it is the same admin-directory class as I-1 and one more `lstat` closes it.
- **I-C — a symlinked container at the next ID's `workers/<id>` name is not allocation evidence.** `n5_container.py`
  rows `n5-next_workers_link_empty-*`: with `refs/cws/<ws>/workers/1` a symlink to an empty directory, a clone spawn
  consumes ID 1 and succeeds; its later `collect` is refused ("refusing to write through a symbolic ref in Clonegrown's
  namespace: …/workers/1/results/<sha>") and nothing is written into the target (`target_listing: []`); a worktree spawn
  consumes ID 1 and fails in `create_task_branch` ("…/workers/1/branch-owner already exists as a symbolic ref"), the target
  again empty. ARCHITECTURE.md:736-738 names only the base-pin and task-branch names as allocation evidence, so this is
  the documented ID gap, and "never written" holds. Wording: "already exists as a symbolic ref" (and, for `bases/<id>`
  below a symlinked `bases`, "dangling symbolic ref under this worker's base pin name") describes a name that does not
  exist; the container is what is symbolic.
- **I-D — wording.** SKILL.md:69-72 ("promoted to `ready` if it is untouched and otherwise preserved in place as
  `broken`") and ARCHITECTURE.md:379 ("Anything else is marked `broken`") describe two outcomes of interrupted-spawn
  recovery; the third, S5's `recovery-failed` with the record left `publishing`, is stated only at ARCHITECTURE.md:762-764.
- **I-E — harness notes.** Planting at a live worker's own branch name destroys its real branch, so that worker ends
  `broken` (`ready-marked-broken`) or `task-branch-missing` after the occupant is removed; planting at a recorded worker's
  own result or branch-owner name leaves `result-ref-missing`/`branch-owner-ref-missing`. All caused by the plant.
- **I-F — the refusal of a worktree worker whose branch name is foreign is attributed to the *worker's* verification.**
  `verify_worker` (`worker.py:78-83`) raises "the task branch name holds a symbolic ref or foreign ref file", so `status`
  reports both `task-branch-foreign` and `worker-authentication-failed` and `recover` marks a `ready` worker
  `ready-marked-broken` (`n2`, `r2_s2` rows). Documented at ARCHITECTURE.md:748-754; the `broken` mark is durable
  (eighth review's I-d), but the occupant is not the worker's and the branch it destroyed is gone anyway.

## 3. Verification record

### S5 — CLOSED (`rerun-r2d.out`; `n6_s5_adjacent.py` → `n6_s5_adjacent_b.out`, 20 rows; `tests/test_worktree.py:338`)

`r2d` rows `B_interrupted_spawn.{after_publish,after_repair}-{fifo,link_fifo}`: with the occupant, `recover` →
`["1:ready-marked-broken", "2:recovery-failed"]`, B `publishing`, `B_error` empty, slot present, occupant unchanged;
after removal `recover` → `2:spawn-publish-finished`, B `ready`, `B_collect` rc 0; controls promote directly. `n6`
(A worktree `ready` with a FIFO or symref→FIFO at its branch name; B interrupted by a hard exit): interrupted collects
of a clone and a worktree (`collect.after_fetch`, `collect.before_fetch`) → `collected` on the first `recover` (no
enumeration needed); a worktree discard killed at `discard.after_quarantine` → `discarding` with `quarantine_error`
"linked worktree app has HEAD on …; Git would block resolving it" (`quarantine-preserved`), killed at
`discard.after_delete` → `2:recovery-failed`, both `discard-finished` after removal; a clone discard finishes with the
occupant present; an abandonment → `abandon-finished` after removal; unpublished worktree spawns killed at
`spawn.after_worktree_add` → `spawn_failed` at once, at `spawn.after_checkout` → `recovery-failed` then `spawn-cleaned`,
at `spawn.after_repair` → `recovery-failed` then `spawn-publish-finished`/`ready`. Occupant unchanged in every row, no
`.lock` files, no leftover issues for B.

### S6 — CLOSED as stated, with T2 (`rerun-r3b.out`; `n5_container.py` → `n5_container_c.out`; `rerun-m3_containers.out`; `tests/test_audit.py:252`)

`r3b` (`workers_1`, `workers_1_results`, root symlinked to the moved real directory): `status` reports the container
`namespace-ref-symbolic` and the worker `result-ref-missing` (previously: only the container); `discard 1` rc 2
"collected result is not preserved" (previously: deleted through the link); the target is untouched. `n5` populated rows
add `workers` and `bases`: re-collection refused ("refusing to write through a symbolic ref"), a clone spawn proceeds
(no owned name below the link is written) except below a symlinked `bases` or root where allocation refuses "base ref
name occupied by a symlink" with nothing consumed, a worktree spawn below a symlinked `workers` refused at
`create_task_branch` (Git's prepared transaction created and removed an empty `workers/4` directory in the target — Git's
own directory handling); restoring the container lets `discard` proceed only for the `bases` row, because `recover` had
marked the collected worker `broken` in the others (T2). `rerun-m3_containers.out` differs from the eighth review's
only where the fix bites: `*-link_dir` rows no longer collect through the link (`ext_dir_changed: false`,
`next_id_after` 3 not 4, no third record).

### S7 — CLOSED for the branch name of a worker whose `HEAD` is on it; OPEN elsewhere (T1)

`rerun-r2_s2.out` (16 rows: A `ready`/`collected`/`quarantined`/`publishing` × FIFO, symlink→FIFO, symref→FIFO,
symref→symlink→FIFO at A's branch name): 0 TIMEOUTs (the eighth review had 8 rows all TIMEOUT); `collect` of a clone and
a worktree, clone spawn, worktree spawn, discard of a collected worktree, abandonment, A's own discard/retry all rc 2 in
0.1–0.4 s; `recover` rc 0; after removal every record settles (D `discarded`, E `abandoned`, B/C `ready`, A per I-E/I-F).
`rerun-r2b_s2_rest.out` 54 lines, 0 TIMEOUTs. `rerun-r2e.out` (owned name, logging Git): `status` rc 0 (49 calls, ends at
`merge-base`), clone spawn / collect of B / collect of A refused (rc 2) with the last Git call `rev-parse --git-common-dir`
— no enumeration ran; `recover` rc 0. Unowned boundary (`n3_unowned_boundary.py` → `n3_unowned_boundary_b.out`;
`rerun-r2e2.out`; `r2c_rawgit.sh` → `r2c_rawgit.out`): with `refs/heads/foo` → FIFO `refs/heads/zz-fifo` and every
worker's branch intact, `status`, `recover`, `spawn --worktree`, discard of a collected worktree, an abandonment, discard
of a collected clone, `release`, `claim` all return; clone spawn (`git clone`), collect of a worktree and of a clone
(`fetch`) TIMEOUT — exactly the two operations ARCHITECTURE.md:765-769 names; raw `git branch`, `for-each-ref`,
`show-ref`, `fetch`, `clone`, `symbolic-ref -q foo`, `rev-parse --verify foo` TIMEOUT while `status`, `log`, `worktree
list`, `for-each-ref refs/cws/`, `update-ref` return; the FIFO alone blocks only `rev-parse --verify zz-fifo`. The
boundary sentence is literal and true for unowned names. T1 records the owned-name cases it does not cover.

### I-1 — CLOSED as stated; I-A/I-B adjacent (`n4_admin.py` → `n4_admin_b.out`; `tests/test_worktree.py:417`)

FIFO admin `HEAD`, symlinked `HEAD` → FIFO, symlinked admin entry: `collect` of a clone and of a worktree, `spawn
--worktree`, `spawn` (clone) all rc 2 in ≤0.3 s naming the worktree ("has a HEAD that is not a regular file" / "registry
entry app is a symlink"). `status`/`recover` and the victim's own discard: see I-A; `gitdir` FIFO: see I-B.

### I-2 — CLOSED (`n7_broken_audit.py` → `n7_broken_audit_b.out`; `rerun-r1_s1.out`; `tests/test_audit.py:279`)

Clone and worktree: result ref deleted → `recover` `collected-marked-broken`, record keeps `result_ref`/`result_sha`,
`status` → `1:result-ref-missing`; `discard --force` refused (leased, then "uncollected worker; use --abandon"); ref
restored → issues `[]`, record stays `broken`; ref deleted again → `discard --abandon` rc 0, `abandoned`, commit object
still present. README.md:416-418 states exactly this ("keeps that result audited by `status` until it is abandoned").
`rerun-r1_s1.out` differs from the eighth review's in 12 rows only by the added `1:result-ref-missing` after
`collected-marked-broken` (14 further rows differ only in random path text).

### Wording and issue codes

The 29 codes at ARCHITECTURE.md:605-616 equal the 29 emitted by `audit.py`/`recovery.py` (regex over `issue("…")`,
`"issue": "…"`: both diffs empty). The F4 phrase sweep finds nothing (only the heading "explicit guarantees and limits",
ARCHITECTURE.md:246). Statements contradicted by observation: ARCHITECTURE.md:729-736, :761-762, :764-769 (T1);
README.md:204-206, ARCHITECTURE.md:479 (T2). Imprecise but not contradicted: SKILL.md:69-72, ARCHITECTURE.md:379 (I-D);
ARCHITECTURE.md:797-799 "status fails" (I-A).

### S1–S4 (seventh review) — hold

S1: `rerun-r1_s1.out` 128 rows, 0 TIMEOUTs; every `after_quarantine`/`after_recheck` row keeps the quarantine with
`quarantine-preserved` + `result-ref-missing`, both forced discards rc 2 "last copy and is kept", restored ref →
`discard-finished`; `rerun-m8_quarantine_result.out` identical to the eighth review's. S2: `rerun-r2_s2.out`,
`rerun-r2b_s2_rest.out`, `rerun-m2_cross_worker.out` (0 Clonegrown TIMEOUTs), `rerun-m6_interrupted_worktree.out`
(refusal text now names the linked worktree). S3/S4: `rerun-r3_codes.out` 306 lines = 153 rows, `status` rc 0 and
`recover` rc 0 in every row, 0 TIMEOUTs, 0 `[Errno`; `rerun-m4_issue_codes.out` identical; `rerun-r4_misc.out` 10 lines
(`refs/cws` FIFO → `status` rc 0; `chmod 000` → raw errno, unchanged from I-3).

### Q1 (sixth), R1–R4 (fifth), N1–N3 (fourth), F1–F5 (third) — hold

`rerun-q1_r1.out`, `rerun-q3_attribution.out`, `rerun-p1_ancestry.out` (19 rows), `rerun-p1b_forged_recovery.out`,
`rerun-p1g.out`, `rerun-p3e.out` (8 rows), `rerun-p4_spot.out`, `rerun-pE_spot.out` identical to the eighth review's
after hash/path normalization (0 diff lines); `rerun-p6_recover_occupants.out` and `rerun-p2b_clone_direct.out` differ
only in hashes; `rerun-p2_occupants.out` 348 rows, 0 IDs consumed, the same 13 documented-class changes, only the
hash-bearing `before`/`after`/`plant_error` fields differ; `rerun-pA_env.out` 662 Git invocations (589 before the new
guards), `A1_git_invocations_missing_any_GIT_line: 0`, `A2_git_honours_graft_env_directly: 0`,
`A3_worker_git_honours_local_grafts: 0`; `rerun-pB_reauth.out`, `rerun-pC_namespace.out`, `rerun-pD_classes.out` differ
only in random temp-path text. F4 sweep clean; F5 boundary sentences present (README.md:422-435, ARCHITECTURE.md:765-769).

### Six second-review classes — all PASS (`rerun-pD_classes.out`, 139 lines, identical after normalization)

Private refs (no flag rc 2, flag rc 0), dangling symbolic task branch (worktree spawn rc 2, `next_id` 1, bytes intact,
clone spawn rc 0), dangling control links (init/spawn rc 2, links intact), CLI init symlink (absolute/relative/default
rc 2), `GIT_CONFIG`/`GIT_CONFIG_COUNT` (spawn rc 0 ×2), rewrite policy (default rc 2, flag rc 0, repeats rc 0, new
commit rc 2 under either), F5 flagless discard rc 0.

### Step 7.5i collection-timing properties — 5/5 (`rerun-timing.out`)

`direct_conflict`: "conflicting result ref already exists … expected <candidate>, found <planted>", preserved;
`symbolic_exact_conflict`: "refusing to write through a symbolic ref", raw target intact; `locked_metadata_finalization`:
move attempts on result and summary both rc 128 while prepared, record `collected`, both refs at the candidate;
`object_only_recovery`: one `write_ref` with the all-zero expected value, `collect-finished`, `collected`;
`object_only_recovery_conflict`: `collect-reset-ready`, conflict preserved at the planted value.

## 4. Coverage-map spot checks

| Item | Result |
|---|---|
| 5.1 active-writer race / 7.5i | Timing 5/5; occupants at summary/result names during collect and recovery refused or left (`rerun-p6`, `rerun-p2b`, `r1 fifo_at_result`). Gap: T1 (hang, no custody effect). |
| 5.2 ignored work | First refusal names count and sample; re-authorization re-asks (`rerun-pB`, `r1 changed_in_quarantine`). |
| 5.3 unchecked deletion | Quarantine, fingerprint recheck, preserved-on-change, result preservation at resume/re-authorization (`r1`, `m8`); foreign-head refusal leaves discards retryable (`n6`). |
| 5.4 branch ownership | Create-only allocation refuses every occupant (`rerun-p2` 348 rows, 0 consumed); cleanup retains a foreign name/owner (`rerun-p3e`, `rerun-m4`). Gap: T1 at the generated name (block, not refusal; nothing consumed for worktree). |
| 5.5 changed published recovery | `recovery.py:516-549`; `test_worktree` 26 + `test_parent_interruption` 6 pass; `r2d` promotes B after the occupant is gone (S5). |
| 5.6 installer root | `sh -n install.sh` OK; `test_installer` 25/25 in the suite; not hand-probed. |
| 5.7 / 5.8 remotes and config | `_canonicalize_remote_url` (`repository.py:140-148`), `ConfigOccurrence(value=None)` (`:43-48`, `:93-106`); `test_repository` 8 pass; `rerun-pE 5.10_remote_copied: true`. |
| 5.9 Git sanitation | `rerun-pA_env`: 662 invocations, none missing the identity-only environment; `rerun-pD class5`. |
| 5.10 secret-bearing errors | `rerun-pE 5.10_command_failure_text` `https://<redacted>@…`, `5.10_raw_git_shows_secret: false`; `rerun-p4 5.10_redaction`. |
| 5.11 stale request reuse | Same params → same worker; different → refused; discarded with deleted result → retry refused (`rerun-pE 5.11_*`). |
| 5.12 incomplete status | 29 codes = 29 emitted (both diffs empty). Gaps: T2 (a report becomes a terminal state), I-C wording. |
| 5.13 create-only allocation | Rewound counter refused with "nothing was changed" (`rerun-pE 5.13`); 348 + 24 + 6 occupant rows consume nothing; the two clone-spawn ID gaps (`n1b`, `n3`) are the documented gap. |
| 5.14 API/CLI parity | `rerun-p4 5.14_parity`: both `mode: clone, strong: false`; worktree+strong refused by both. |
| 5.15 invalid generated branch | `x.lock` → "generated task branch is invalid for Git", `next_id` unchanged (`rerun-pE`, `rerun-p4`). |
| 5.16 low-level errors | Five-part context on `collect 999` (`rerun-p4 5.16_context`) and on every refusal quoted above, including the new `ForeignWorktreeHead` text. |
| 5.17 timing gate | `grep ratio tests/campaign/hardening_suite.py` matches only the word inside `operation`; `parallel_spawns_unique` PASS in both modes. |
| 5.18 one-shot | `--abandon` and `claim` refused for a collected worker; leased discard refused under every flag (`rerun-pE 5.18`, `rerun-p4`, `n7 discard_force_leased`). |
| Comment/public overclaims | Notices current (README.md:17-34, SKILL.md:14-25, ARCHITECTURE.md:6-16) and require a fresh review; F4 phrases absent. Overclaims found: ARCHITECTURE.md:729-769 (T1), README.md:204-206 / ARCHITECTURE.md:479 (T2). |
| `CWSError`, heartbeat, failpoints | `grep -rn CWSError clonegrown/` empty; `heartbeat` only as a hidden bookkeeping key (`cli.py:31`); `failpoint` gated on `CLONEGROWN_TEST_MODE == "1"` (`core.py:485`). |
| retention, teardown, license, package | `pyproject.toml`: `license = "Apache-2.0"`, `license-files`, `requires-python >=3.11`, dynamic version `0.1.0a1`; wheel/sdist from the rsync copy (section 5); `licenses/LICENSE` in the wheel, identical to the checkout's (`cfc7749b…`); result refs and records survive every normal discard (`r1` controls, `n3`). |
| macOS, Python/Git versions, filters/LFS, resource boundaries, repository diversity, repeated verification, auxiliary-ref cost | Not freshly exercised (section 6); `test_filters_and_resources` 4, `test_auxiliary_refs` 4, `test_campaign_records` 16, `test_lease` 10 pass in the suite. |

## 5. Gate results

- **Unit suite:** `cd /home/serrecchia/Projects/clonegrown && python3 -m unittest discover -s tests -v` (in the checkout,
  no cache prefix) → **Ran 289 tests in 344.910 s, OK** (289 `ok`, 0 failures, 0 errors, 0 skipped); wall 00:47:53 →
  00:53:38; log `/tmp/clonegrown-review7-unittest.log`. The suite grew from the eighth review's 284 to 289. Per module:
  quarantine 35, audit 33, worktree 26, installer 25, safety_errors 19, allocation 19, campaign_records 16,
  discard_ignored 15, core 14, state 12, lease 10, repository 8, parent_interruption 6, cli 6, api 6,
  filters_and_resources 4, collect_policy 4, auxiliary_refs 4, package_metadata 2. The three gates ran concurrently.
- **Hardening, clone mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`: "git lacks reftable support"),
  **0 failed**; sum of case seconds 86.0; wall 92.85 s (`/usr/bin/time`), `generated` 00:49:29;
  `sha256 69f666d5d4b5c579de723e7461b01e4755e0152cc114fc64623c7eae55c3252d /tmp/clonegrown-review7-hardening-clone.json`
  (log `/tmp/clonegrown-review7-hardening-clone.log`, exit 0).
- **Hardening, worktree mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`), **0 failed**; sum of case
  seconds 87.6; wall 94.40 s, `generated` 00:49:33;
  `sha256 a3c380273b16169ee342141cdbd54c74d9d006f9a447770da5a1e51a3d20da21 /tmp/clonegrown-review7-hardening-worktree.json`
  (log `/tmp/clonegrown-review7-hardening-worktree.log`, exit 0).
- `git diff --check` clean; `sh -n install.sh` OK; `python3 -m compileall -q clonegrown tests` OK with
  `PYTHONPYCACHEPREFIX=/tmp/clonegrown-review7-pyc`; wheel and sdist built with `python -m build` in a venv on the rsync
  copy `/tmp/clonegrown-review7-build/src`: `clonegrown-0.1.0a1-py3-none-any.whl` 101,148 bytes sha256
  `c1926079eda75f73c1ff7b16eea575b0c4fc2a691db22b19304e7d728206111d`, `clonegrown-0.1.0a1.tar.gz` 202,837 bytes sha256
  `ba432cd88954ec5f01a77f1bc3669bb16faf9a1cf308810d6e0a8f6e28c1ba1a`; `License-Expression: Apache-2.0`, `Requires-Python:
  >=3.11`, MacOS and POSIX::Linux classifiers, `clonegrown-0.1.0a1.dist-info/licenses/LICENSE` present; isolated install in
  a second venv: `clonegrown --version` and `python -m clonegrown --version` both print `clonegrown 0.1.0a1`. No `build/`,
  `dist/` or `egg-info` in the checkout; `clonegrown/__pycache__`, `tests/__pycache__` and `tests/campaign/__pycache__`
  (gitignored) are the only things the in-checkout suite run wrote.
- Versions: CPython 3.12.3, Git 2.43.0 (`/usr/bin/git`), Linux 6.17.0-35-generic.
- Tree fingerprints: start `1e9f3ad478d1a78f78ddaaf59d9500307042324d09eb062a5165a05cf82b9190`, end
  `c6717371d1ac2bcae119f246ca813e1e624651b9c70cc502ba3672c178bf657d` (README/ARCHITECTURE/FINAL_COLD_REVIEW rewritten
  at 00:46:58 and PLAN/HANDOFF at 00:57:57 by another session; product modules and tests unchanged, see the header);
  `git status --short` 23 entries at both ends.

## 6. Not verified, and why

- Hosted CI on a pushed revision, macOS, CPython 3.11, exact Git 2.29.0: not available locally; the tree is uncommitted.
  Whether Git 2.29's `for-each-ref`, `fetch` and `clone` resolve symbolic refs to a FIFO the same way (T1) was not
  checked on that version.
- reftable repositories and `GIT_REF_FORMAT` end to end: Git 2.43 cannot create them (hardening skip); the
  `inventory is None` fallbacks were read, not exercised.
- Random-kill and state-machine campaign seeds, `real_repository_qualification.py`, and the benchmark harnesses: not in the
  requested gate list and not run.
- A socket occupant (a FIFO proves the class); a symbolic ref whose target is a FIFO planted *inside a worker's own*
  refs (the agent's); admin-directory files other than `HEAD` and `gitdir` (`commondir`, `locked`).
- The fifth review's `p3_wording.py`/`p5_fifo.py` and the seventh review's `m1_matrix.py`/`m5_gitlog.py`/
  `m7_attribution.py` were not rerun (their rows are covered by `r1`, `r2`, `r3`, `m2`/`m3`/`m4`/`m6`/`m8` reruns and
  `rerun-pA_env`).
- Genuine disk/inode exhaustion, network filesystems, Git LFS, native Windows: stated boundaries, not exercised.
- `HANDOFF.md` and the Step 7.5a–7.5ac completion records: deliberately not read.

Probe inventory: `/tmp/clonegrown-review7-probes/{h7,n0_smoke,n1_symref_namespace,n1b_attribution,n2_detached_head,
n3_unowned_boundary,n4_admin,n5_container,n6_s5_adjacent,n7_broken_audit,n8_container_breaks,cmp}.py`, `r2c_rawgit.sh`,
`gitlog.sh`, with outputs `n0` (inline), `n1_symref_namespace.out`, `n1b.out`, `n2_detached_head_b.out`,
`n3_unowned_boundary_b.out`, `n4_admin_b.out`, `n5_container_c.out`, `n6_s5_adjacent_b.out`, `n7_broken_audit_b.out`,
`n8.out`, `r2c_rawgit.out` (the `n*.out` files without suffix are a second, sequential run of the same probes and agree);
`rerun_all7.sh` → `rerun-*.out`/`.err`, `rerun.log` for the fourth review's `pA`–`pE`, the 7.5i timing probe, the fifth
review's `p1`, `p1b`, `p1g`, `p3e`, `p4`, `p6`, `p2b`, `p2`, the sixth review's `q1`, `q3`, the seventh review's `m2`,
`m3`, `m4`, `m6`, `m8`, and the eighth review's `r1_s1`, `r2_s2`, `r2b_s2_rest`, `r2d`, `r2e`, `r2e2`, `r3b`, `r3_codes`,
`r4_misc` (copied here with paths rewritten to `review7`); disposable repositories under `/tmp/clonegrown-review7-work/`
(and the earlier reviews' work roots for the reruns); suite log `/tmp/clonegrown-review7-unittest.log`; hardening logs
and JSON `/tmp/clonegrown-review7-hardening-*`; wheel, sdist and venvs under `/tmp/clonegrown-review7-build/`.

## Tenth fresh review (eighth Step 7.5 pass, after Step 7.5ad): no-go

A tenth fresh reviewer found T1–T2 and the notes closed for the cases they
named, every earlier finding holding, the suite 291/291, and both hardening
modes clean, and returned no-go on three Low findings:

1. **U1 (low).** Allocation evidence still asked Git `symbolic-ref` about a
   loose symbolic ref at the next ID's base-pin or task-branch name, and
   Git followed its chain into a FIFO; the regression meant to cover the
   case planted at a stale next ID. Step 7.5ae owns it.
2. **U2 (low).** A refused worktree spawn's rollback read every admin
   `gitdir` with a plain open, so a FIFO there blocked the rollback. Step
   7.5ae owns it.
3. **U3 (low).** When Git's enumeration was skipped, packed namespace refs
   became invisible and `status` reported custody refs missing that were
   intact. Step 7.5ae owns it.
4. Informational: the interrupted-spawn wording in the architecture, the
   list of read-only Git forms, and the notices' step range. Step 7.5ae owns
   the wording.

The reviewer's full report is preserved verbatim below.

---

# Clonegrown final cold review — release qualification (tenth fresh review)

Date: 2026-09-03. Reviewer: fresh agent, read-only on `/home/serrecchia/Projects/clonegrown` (uncommitted working tree
on `main`, base `c9728a0`). Environment: Linux 6.17.0-35-generic, CPython 3.12.3, Git 2.43.0 (`/usr/bin/git`).
Every probe, log, wheel, venv and result lives outside the checkout: new probes and outputs in
`/tmp/clonegrown-review8-probes/`, disposable repositories in `/tmp/clonegrown-review8-work/`, reruns of earlier
reviews' probes as `/tmp/clonegrown-review8-probes/rerun-*.out`, build products under `/tmp/clonegrown-review8-build/`,
byte-code cache under `/tmp/clonegrown-review8-pyc/`. `HANDOFF.md` and the Step 7.5a–7.5ad "Completion record"
sections were not read; no `.env`-pattern file was opened; nothing inside the checkout was modified (the wheel and
sdist were built from an `rsync` copy; `compileall` ran with `PYTHONPYCACHEPREFIX`; the unit suite ran in the checkout
without a cache prefix, as CI does). Every Git command and Clonegrown call that could touch a planted FIFO ran under a
4–10 s timeout (`TIMEOUT` below means the process was killed while blocked); the Git grandchildren those kills left
blocked on FIFO opens were killed at the end (`kill_blocked.sh`, matched by cwd/argv under the review work roots; the
final pass found no Git process of this user left running).

**Tree fingerprints.** `git diff | sha256sum` at start `342f9c3520db5994f6062acb4c6839d969f301f22eae5ac2065fe6c9c0a3054f`,
at end `961abeba9919a477cc1d8affcbb2f5af36303d13a437757284179a7a0a5fc987`; `git status --short` lists 23 entries at both ends (22 modified tracked files plus untracked
`tests/test_collect_policy.py`). The fingerprints differ because another session rewrote `PLAN.md` and `HANDOFF.md` at 01:59:22 while this review ran (after the gates started at 01:49:35). No product module, test, or public document changed: every `clonegrown/*.py`, `tests/*.py`, `README.md`, `SKILL.md` and `ARCHITECTURE.md` mtime precedes the review's first command (latest: `repository.py` and `test_allocation.py` 01:41:45; the three documents 01:48:16), and `git diff -- clonegrown README.md SKILL.md ARCHITECTURE.md tests | sha256sum` is `bf426b75001985fff59755722c99c010c9cc7233193f843a562eb43d066ff225` at the end. The Step 7.5ad bullet quoted below is still present in the rewritten `PLAN.md` (line 1138). sha256 (first 12) of the product reviewed: audit `52b5f6f500ba`, cli `a309e205fbb4`, core `fc2af01adbd3`, lifecycle `200799caa028`, recovery `7d207f6d7c96`, repository `5807b935a035`, state `043a08cd21ac`, worker `a79366313fb8`; README `39a4a4193c43`, SKILL `f7d7eb3ec0db`, ARCHITECTURE `2906c310c379`.

## 1. Verdict: NO-GO

The ninth review's findings are closed as stated for the cases they named:

- **T1** — a symbolic ref at an owned name inside `refs/cws/<ws>/` (a collected worker's summary, immutable result and
  base pin, a worktree worker's `branch-owner`, the next ID's summary) or at a live/collected worktree worker's branch
  name with `HEAD` detached, whose chain ends at a FIFO directly, via a symlink, or through a second symbolic ref, is
  reported (`namespace-ref-symbolic` / `task-branch-foreign`) and every operation refuses by name in ≤0.4 s: `status`,
  `recover`, clone and worktree spawn, collect of the worker and of others, discard, request retry (`rerun-n1`: 20 of its
  24 rows — the four `next_pin` rows are U1; `rerun-n2` 6 rows; `rerun-n1b` attribution). The unowned-name boundary sentence is literal and
  true (`rerun-n3`: with `refs/heads/foo` → FIFO, exactly `git clone` spawn and the collect fetch block; everything else
  returns).
- **T2** — a foreign occupant (symlink, FIFO, plain file) at `workers`, `workers/<id>`, `workers/<id>/results`, `bases`
  or the namespace root never marks a collected worker `broken`: `recover` reports `collected-result-missing` and leaves
  every record `collected`; restoring the container brings every result ref back, `status` and `recover` go quiet, and a
  normal `discard` succeeds (`rerun-n8` 6 rows, `p_t2` 15 container rows). A missing result ref whose object is present and
  whose name is free is re-created by `recover` (`collected-result-restored`, clone and worktree, `p_t2` restore rows); a
  name holding another commit, a dangling symbolic ref, or a pruned object is reported (`collected-result-missing`) with
  the record left `collected`, the worker directory in place, the occupant byte-identical, and normal and forced
  `discard` refused ("collected result is not preserved").
- **I-A/I-B/I-D** — a FIFO at an admin `gitdir` is refused by name before the collect fetch, the clone-mode clone, and
  `recover` returns (`rerun-n4`); a FIFO at a worker's own `HEAD` still blocks `status`/`recover`/the worker's own
  discard (the agent's private Git directory; no document claims inspection of it); `SKILL.md:69-72` now states the
  third interrupted-spawn outcome.
- S1–S7, Q1, R1–R4, N1–N3, F1–F5, the six second-review classes and the five Step 7.5i properties hold on reruns
  (section 3). The unit suite passes 291/291, both hardening modes pass 56 with the one conditional reftable skip, and
  every static and packaging gate passes (section 5).

Release is blocked by one open finding that contradicts sentences the documents state as properties, plus two Low
findings the caller may reclassify:

- **U1 (Low)** — the same object (a symbolic ref whose chain ends at a FIFO) at the **next ID's base-pin name**
  `refs/cws/<ws>/bases/<next>` blocks every `spawn` (clone and worktree) for 8 s+ inside `git symbolic-ref -q`, called
  by `allocation_evidence` after `resolve_ref` has already answered "absent" for the very chain it then hands to Git;
  at the **generated worktree task-branch name** `refs/heads/agent/<ws>/<next>-<task>` it blocks `spawn --worktree
  <task>` the same way. Nothing is consumed or written and the occupant is intact, but ARCHITECTURE.md:734-743 ("Every
  owned ref name is `lstat`-inspected before any Git command reads it … allocation evidence … none is ever opened by
  Git (a FIFO would block it) … any of them at the base-pin or task-branch name is allocation evidence so the ID is not
  consumed") and the Step 7.5ad closure ("at the next ID's base pin … both spawns … refuse by name") are contradicted.
  The regression that claims to cover the next ID's pin computes `next_id` once, before its first sub-test's two spawns
  consume two IDs, so it never plants at the next ID's pin (`p_testgap`).
- **U2 (Low)** — a FIFO at a linked worktree's admin `gitdir` is refused by name before `git worktree add` (as
  ARCHITECTURE.md:774-779 now promises), but the refused worktree spawn then blocks for good in its own rollback: a
  plain Python `read_bytes()` of every admin entry's `gitdir` in `locate_worktree_admin` (`worker.py:980`, `:1031`, via
  `forget_worktree` ← `_discard_unpublished_stage` ← `roll_back`). The record is already `spawn_failed` and everything
  settles after the FIFO is removed, but "other workers' operations therefore fail closed instead of blocking"
  (ARCHITECTURE.md:759-769) is not true for a worktree spawn.
- **U3 (Low, verdict does not hinge on it)** — when the namespace inventory skips Git's enumeration because a symbolic
  ref below the subtree leads to a FIFO (the Step 7.5ad design), every **packed** namespace ref becomes invisible to the
  raw walk. After an ordinary `git gc` / `git pack-refs --all` in canonical, one such occupant makes `status` report
  invariants that do not hold: `summary-ref-mismatch` for every collected worker, `branch-owner-ref-missing` for every
  worktree worker, `base-ref-missing` for an in-flight spawn. `recover` changes nothing (`ref_points_at`/`resolve_ref`
  ask Git per name) and everything is quiet once the occupant is gone (`p_packed`).

Everything else I found is informational and listed as such.

## 2. Findings, ranked by severity

### U1 — Low — a symbolic ref whose chain ends at a FIFO, at the next ID's base-pin name or at the generated worktree branch name, blocks `spawn` inside `git symbolic-ref -q` (claim mismatch; robustness; the class of R4/Q1/S2/S7/T1, T1 not closed for allocation)

- **Claims.** ARCHITECTURE.md:734-743: "Every owned ref name is `lstat`-inspected before any Git command reads it
  (`loose_ref_occupant`, applied by `is_foreign_ref`, `resolve_ref`, `ref_points_at`, the result/summary transaction,
  and allocation evidence) … none is ever opened by Git (a FIFO would block it) … any of them at the base-pin or
  task-branch name is allocation evidence so the ID is not consumed". :773-774: "`resolve_ref` and `ref_points_at` follow
  a symbolic ref's chain raw and answer 'absent' rather than let Git resolve into such an occupant." PLAN.md Step 7.5ad
  regression bullet: "a symbolic ref to a FIFO at a collected worker's summary, at the next ID's base pin, and at its
  result name is reported, both spawns and the other worker's collect refuse by name".
- **What the code does.** `allocation_evidence` (`clonegrown/worker.py:660-700`) asks, for the generated branch name
  (`:673-680`) and for the base-pin name (`:692-698`): `loose_ref_occupant` (regular file → not evidence), then
  `resolve_ref` (now correctly None because `symbolic_chain_ends_foreign` sees the FIFO), then **`is_symbolic_ref`**
  (`repository.py:823-826`), which runs `git symbolic-ref -q <name>`. Since Git 2.40 `symbolic-ref` recurses by default,
  so Git reads the chain and `open()`s the FIFO. `require_plain_worktree_heads`, which would refuse the same object by
  name, runs only after allocation (`lifecycle.py:541-551`, `add_worktree`/the clone), so it is never reached.
- **Reproduction.** `/tmp/clonegrown-review8-probes/p_alloc.py` → `p_alloc.out` (4 rows, fresh repositories):
  symref → FIFO and symref → symref → FIFO at `bases/1`: `status` rc 0 (reports `namespace-ref-symbolic`), `spawn`
  TIMEOUT 8.0 s, `spawn --worktree` TIMEOUT 8.0 s, `recover` rc 0; a direct `allocation_evidence(...)` call under an
  alarm dies in `git symbolic-ref -q refs/cws/<ws>/bases/1`; `next_id` 1 → 1, occupant unchanged, no `.lock`; after
  removal `recover` and `status` are empty. At the generated branch name `refs/heads/agent/<ws>/1-next-task` the direct
  call dies in `git symbolic-ref -q refs/heads/agent/…/1-next-task`; the CLI proof is `p_alloc2.py` → `p_alloc2.out`
  row `A spawn_wt_same_task`: TIMEOUT 8.0 s, `next_id` unchanged, occupant intact (a clone spawn and a collect are
  refused by name by the later guard, consuming an ID for the clone spawn — the documented gap). The ninth review's
  matrix rerun agrees: `rerun-n1_symref_namespace.out` rows `n1-next_pin-*` (4 kinds): `spawn_clone` and `spawn_wt`
  TIMEOUT 8.0 s in 8/8, every other operation returns, `next_id` 3 → 3; `rerun-n1b_attribution.out`:
  `spawn_clone_next` blocks at Git call 11 `--git-dir=/dev/fd/3 symbolic-ref -q refs/cws/<ws>/bases/6`,
  `spawn_wt_next` at call 12 `--git-dir=/dev/fd/3 symbolic-ref -q refs/heads/agent/<ws>/5-next-task`. Raw Git in a bare
  probe repository (`rawgit_symref.sh`): `symbolic-ref -q refs/heads/sym` TIMEOUT, `symbolic-ref -q --no-recurse
  refs/heads/sym` rc 0 in 0.0 s.
- **Test gap.** `tests/test_audit.py::test_symbolic_ref_to_a_fifo_inside_the_namespace_is_refused_without_enumeration`
  computes `state.base_ref(int(state.next_id))` once (next_id 3), then its first sub-test's clone and worktree spawns each
  consume an ID (refused after allocation by the raw-walk guard, records 3 and 4 `spawn_failed`); when it plants at
  `bases/3`, `next_id` is 5, so the spawn it asserts against never inspects the planted name (`p_testgap.py` →
  `p_testgap.out`: `is_next_ids_pin: false`, the "refusal" it observes is the guard's, "worker 5 remains allocated or
  failed"). The suite therefore passes while the claimed case is open.
- **Affected.** `clonegrown/worker.py:676-679`, `:695-698`; `clonegrown/repository.py:823-826` (`is_symbolic_ref`);
  ARCHITECTURE.md:734-743; PLAN.md Step 7.5ad; `tests/test_audit.py` (the test above).
- **Classification.** Low claim mismatch (robustness): a same-user process planting under canonical's `.git/refs/`;
  nothing written, replaced, deleted or consumed; settles when the object is removed. Class fix: `is_symbolic_ref` must
  never be asked about a name whose loose file is a regular symbolic ref (read it raw: `loose_symbolic_target` already
  answers), or pass `--no-recurse` on Git ≥ 2.40 and read raw below it; and make the regression reload `next_id` before
  each plant.

### U2 — Low — a FIFO at a linked worktree's admin `gitdir` is refused before `git worktree add`, but the refused worktree spawn then blocks in its own rollback (claim mismatch; robustness; adjacent to the ninth review's I-B)

- **Claims.** ARCHITECTURE.md:759-769: "Canonical-side `git worktree add` … resolve every registered linked worktree's
  `HEAD`, so before any of them Clonegrown reads each admin entry … and refuses, naming the worktree … other workers'
  operations therefore fail closed instead of blocking"; :774-779: "and also refuses a linked worktree whose admin
  `gitdir` file is not a regular file".
- **What the code does.** The refusal is right: `require_plain_worktree_heads` (`repository.py:718-729`) `lstat`s
  `gitdir` and raises `ForeignWorktreeHead` before `worktree add`. The spawn's `roll_back` (`lifecycle.py:475-511`) then
  calls `_discard_unpublished_stage` (`:400-417`) → `forget_worktree` (`worker.py:1073-1095`) → `locate_worktree_admin`
  (`:1013-1035`), which reads every admin entry's `gitdir` with `Path.read_bytes()` (`_read_pointer`, `:978-980`) — a
  plain open of the FIFO, which blocks the Python process.
- **Reproduction.** `p_gitdir.py` → `p_gitdir.out`: FIFO at `.git/worktrees/app/gitdir` of worktree worker 1;
  `spawn --worktree` TIMEOUT 8.0 s after 44 logged Git calls (the last logged Git call is `rev-parse --git-common-dir`;
  the block is not a Git call); `spawn` (clone) rc 2 "linked worktree app has a gitdir that is not a regular file",
  `status` rc 0, `recover` rc 0 `[]`. `p_gitdir2.py` → `p_gitdir2.err` (in-process, `faulthandler` stack after 5 s):
  `pathlib.read_bytes ← worker.py:980 _read_pointer ← :1031 locate_worktree_admin ← :1093 forget_worktree ←
  lifecycle.py:412 _discard_unpublished_stage ← :485 roll_back ← :62 _rolling_back ← :515 spawn`; the record is already
  `spawn_failed`, the stage is gone, and after the FIFO is replaced `recover` is `[]` and `status` has no issues.
  `rerun-n4_admin.out` row `n4-fifo_gitdir`: `spawn_wt` TIMEOUT 8.0 s; collect of a clone and of a worktree, clone
  spawn, `recover`, and the victim's own `discard --abandon` all return (rc 2 by name / rc 0) — I-B closed for those.
- **Affected.** `clonegrown/worker.py:978-980`, `:1013-1035`, `:1073-1095`; `clonegrown/lifecycle.py:400-417`;
  ARCHITECTURE.md:759-779.
- **Classification.** Low claim mismatch (robustness). The admin directory is the worker's private Git directory, which
  the caller's rules exempt unless a document claims otherwise — ARCHITECTURE.md:774-779 now does claim it for `gitdir`.
  Class fix: `lstat` each admin `gitdir` (or open it `O_NONBLOCK`/skip non-regular files) in `locate_worktree_admin`,
  as the guard already does.

### U3 — Low — with packed namespace refs, a blocking symbolic ref anywhere below `refs/cws/<ws>/` makes `status` report invariant violations that do not exist (claim mismatch; report quality; consequence of the Step 7.5ad raw-first inventory)

- **Claims.** README.md:198-206: "`status` audits Clonegrown's documented workspace and worker invariants … Each detected
  disagreement is listed under `issues` with a stable code". ARCHITECTURE.md:600-616 defines `summary-ref-mismatch`,
  `branch-owner-ref-missing`, `base-ref-missing` as detected disagreements. ARCHITECTURE.md:769-774 states the mechanism
  ("does not ask Git at all when a symbolic ref below the subtree leads to a symlink or non-regular file") but not its
  consequence for packed refs.
- **What the code does.** `raw_ref_inventory` (`repository.py:859-943`) skips `for-each-ref` when any walked symbolic
  ref ends foreign, so `NamespaceRefs.values` (`audit.py:38-108`) holds only loose refs. `audit_worker` (`:111-212`) then
  reports `summary-ref-mismatch` (`summary is None`), `branch-owner-ref-missing`, and `base-ref-missing` for refs that are
  packed and perfectly intact; `result-ref-missing` is not reported because `ref_points_at` asks Git per name.
- **Reproduction.** `p_packed.py` → `p_packed.out`: collected clone 1, ready worktree 2, ready clone 3, an interrupted
  worktree spawn 4 (`publishing`), then `git pack-refs --all` in canonical (`loose_ns: []`, `packed_has_ns: true`);
  symref → FIFO planted at the next ID's summary name. `status` (rc 0, 0.3 s): `1:summary-ref-mismatch`,
  `2:branch-owner-ref-missing`, `4:base-ref-missing`, `4:owner-process-dead`, `5:namespace-ref-symbolic`; the same
  sequence with loose refs reports only `4:owner-process-dead`, `5:namespace-ref-symbolic`. `recover` (twice):
  `4:recovery-failed`, `5:namespace-ref-symbolic-left`, no record changed, worker 1's result ref resolves; `collect 3`
  refused by name; `discard 1` rc 0; after removal `status` is `[4:owner-process-dead]`, `recover` promotes 4, `status`
  empty.
- **Affected.** `clonegrown/repository.py:920-943`; `clonegrown/audit.py:57-93`, `:111-212`; README.md:198-206;
  ARCHITECTURE.md:769-774.
- **Classification.** Low claim mismatch. Nothing is written or lost and `recover` is unaffected; but `git gc` packs
  `refs/cws` in ordinary use (the hardening suite's `*_survives_gc` cases assume it), and while the occupant is present
  the audit tells an agent that three intact custody refs are broken. The verdict does not hinge on it. Class fix: when the
  enumeration is skipped, read `packed-refs` raw (it cannot hold symbolic refs) or mark the inventory "unverified" and
  suppress the presence-based codes, rather than reporting absence.

### Informational (not findings)

- **I-1 — a FIFO at a worker's own `HEAD` blocks `status`, `recover`, and that worker's own discard** (`rerun-n4_admin.out`
  rows `n4-fifo_head`, `n4-clone_fifo_head`): the block is `git rev-parse --show-toplevel` in the worker
  (`verify_worker`); collect of every other worker and both spawns are refused by name. The worker's private Git
  directory is the agent's; no document claims inspection of it (the ninth review's I-A).
- **I-2 — the walk does not descend below a symlinked container, so the unowned boundary extends to everything under
  it.** `p_alloc2.py` case B: `refs/heads/agent/<ws>` replaced by a symlink to its moved contents, a symref → FIFO added
  there under a non-generated name, worktree worker 1 with `HEAD` detached. `status` rc 0 (`1:task-branch-foreign`,
  `1:worker-authentication-failed`), `recover` marks 1 `ready-marked-broken`, `spawn --worktree` refused at allocation
  ("task branch name occupied by a symlink"), but `collect 2` (clone) and a clone spawn TIMEOUT in `fetch`/`clone`.
  ARCHITECTURE.md:745-753 states that names below a symlinked container are foreign and that Git itself follows the link;
  :779-783 states the unowned boundary. Consistent, but worth one explicit sentence.
- **I-3 — refusals after allocation consume an ID.** With a blocking occupant at a *recorded* worker's name, every clone
  or worktree spawn refused by the pre-clone/pre-`worktree add` guard leaves a `spawn_failed` record (`rerun-n1`
  `after … next_id [3, 5]`; `p_testgap`). ARCHITECTURE.md:469 ("leaves the id unused, an observable gap") and the
  allocation docstring describe this; :698 and :743 promise "not consumed" only for occupants at the control-file, base-pin
  and task-branch names, which hold.
- **I-4 — wording.** ARCHITECTURE.md:376-379 still says interrupted-spawn recovery has two outcomes ("Anything else is
  marked `broken`"); the third (`recovery-failed`, promoted later) is stated at :762-769 and now in SKILL.md:69-72.
  ARCHITECTURE.md:616 lists `status`'s read-only Git forms as "`--no-optional-locks status`, `rev-parse`,
  `for-each-ref`"; a `status` also runs `symbolic-ref -q`, `config --get`, `cat-file -e`, `merge-base --is-ancestor`
  (`rerun-n1b`: 76–82 Git calls), all read-only. README.md:17-34, SKILL.md:14-25 and ARCHITECTURE.md:6-16 summarize the
  reviews only through Steps 7.5p–7.5v (2026-09-02); they still state that a fresh no-open-finding review and green
  hosted CI are required, which is true.
- **I-5 — the refusal of a worktree worker whose branch name is foreign is attributed to the worker's own verification**
  and `recover` marks a `ready` one `broken` durably (`rerun-n2` `ready` rows, `p_alloc2` case B). Documented at
  ARCHITECTURE.md:753-759 (the ninth review's I-F); the plant replaces the worker's real branch, which is gone anyway.
- **I-6 — harness notes.** Planting at a recorded worker's own summary/owner name leaves `branch-owner-ref-missing`
  after removal (`rerun-n1` `rec2_branch_owner` rows) and at a live worker's branch name leaves `task-branch-missing`
  (`rerun-n2` collected rows): caused by the plant. `git` removes the empty `bases` container when the last pin is
  dropped, so `p_t2`'s `bases` rows re-created it before planting (Git's own directory handling).

## 3. Verification record

### T1 (ninth review) — CLOSED for every recorded owned name and for the detached-`HEAD` branch name; OPEN at the next ID's pin and the generated branch name (U1)

`rerun-n1_symref_namespace.out` (24 rows = 6 names × 4 kinds — symref → unowned FIFO, symref → FIFO inside the namespace,
symref → symlink → FIFO, chain through a second symref at `workers/9/result` — each in a fresh repository with a
collected+released clone (1) and a ready worktree (2)): raw `git for-each-ref refs/cws/<ws>/` TIMEOUT in 24/24 (the
object does block Git); for the four recorded names (`workers/1/result`, `workers/1/results/<sha>`, `bases/1`,
`workers/2/branch-owner`) and the next ID's summary, `status` rc 0 reporting `namespace-ref-symbolic` (or
`orphan-namespace-ref` for the FIFO planted inside the namespace), `recover` rc 0, `spawn`, `spawn --worktree` and
`collect 2` rc 2 in 0.1–0.3 s naming the ref ("is a symbolic ref leading to a symlink or non-regular file; Git would
block enumerating it"), `discard 1` rc 0 except when the immutable result name holds the plant (rc 2 "not preserved",
record stays `collected`), occupant byte-identical in every row, no `.lock` files; after removal two `recover`s settle
every record (`2:branch-owner-ref-missing` remains only where the plant replaced worker 2's real owner ref — harness).
The four `next_pin` rows are U1: `spawn` and `spawn --worktree` TIMEOUT 8.0 s (8/8), `next_id` 3 → 3.
`rerun-n1b_attribution.out` (logging `CLONEGROWN_GIT`): `status` 82 calls ending at `merge-base`, `recover` 32,
clone spawn / worktree spawn / collect refused with the last Git call `rev-parse --git-common-dir` or the branch-name
`rev-parse` — no enumeration ran; `spawn_wt_next` blocks at call 12 `--git-dir=/dev/fd/3 symbolic-ref -q
refs/heads/agent/<ws>/5-next-task`, `spawn_clone_next` at call 11 `--git-dir=/dev/fd/3 symbolic-ref -q
refs/cws/<ws>/bases/6`; raw `for-each-ref refs/cws/<ws>/`, `rev-parse --verify <ns>/workers/1/result`, `symbolic-ref -q
<ns>/workers/1/result` TIMEOUT while `for-each-ref refs/heads/`, `worktree list`, `status`, `update-ref` return.
Detached-`HEAD` variant `rerun-n2_detached_head.out` (6 rows: A `ready`/`collected` × symref → FIFO, symref → symlink →
FIFO, plain FIFO at A's branch name after `git checkout --detach` in A): `status` rc 0, `recover` rc 0 (A `ready` →
`ready-marked-broken`, I-5), clone spawn, worktree spawn, collect of a clone and of a worktree, discard of a collected
worktree all rc 2 in ≤0.3 s naming A's branch ref; A's own collect and request retry refused (`task-branch-foreign`);
the plain FIFO blocks nothing; after removal one `recover` settles everything. Unowned boundary
`rerun-n3_unowned_boundary.out` (`refs/heads/foo` → FIFO `refs/heads/zz-fifo`, every worker's branch intact): `status`,
`recover`, `spawn --worktree`, discard of a collected worktree, an abandonment, discard of a collected clone, `release`,
`claim` return; clone spawn, collect of a worktree and of a clone TIMEOUT — exactly the two operations
ARCHITECTURE.md:779-783 names; after removal `recover` finishes both collects and cleans the interrupted clone spawn.
`tests/test_worktree.py:378-449` and `tests/test_audit.py:293-345` cover the recorded names and the detached branch;
the next-ID pin sub-test is the gap described under U1.

### T2 (ninth review) — CLOSED (`rerun-n8_container_breaks.out` 6 rows; `p_t2.out` 12 scenarios / 48 lines + `p_t2b.out` 28 lines; `rerun-r3b.out`; `rerun-r3_codes.out`; `rerun-r4_misc.out`; `rerun-n7_broken_audit.out`; `rerun-r1_s1.out`; `tests/test_audit.py:275-291`)

Three collected workers (clone, worktree, clone), the real `workers` container or the namespace root replaced by a symlink
to it, a FIFO, or a plain file (`n8`), and additionally `workers/1`, `workers/1/results`, `bases` (`p_t2`): `status`
reports the container (`namespace-ref-symbolic` / `orphan-namespace-ref`) and `result-ref-missing` per worker;
`recover` (twice) reports `collected-result-missing` per worker and `<container>-left`, every record stays `collected`,
the occupant is byte-identical and the moved refs untouched; `discard 1` rc 2 "collected result is not preserved" with
the directory in place (for `bases`, which holds no result name, discard proceeds). Restoring the container: every
result ref resolves, `status` `[]`, `recover` `[]`, records `collected`, `discard 1` rc 0 → `discarded`. Missing
result ref, object present, name free: `recover` → `collected-result-restored` for a clone and a worktree, the ref is
back at the recorded sha, `status` empty, discard rc 0. Name holding another commit (`p_t2b` `occupied-other-sha`):
`status` `candidate-ref-retained` + `result-ref-missing`, `recover` → `collected-result-missing`, value unchanged,
record `collected`, plain and fully-flagged discard rc 2, directory in place. Dangling symbolic ref at the name:
`collected-result-missing` + `namespace-ref-symbolic-left`, occupant intact. Object pruned (`git prune
--expire=now`): `collected-result-missing`, record `collected`, discard refused. `rerun-r3_codes.out` (153 rows) and
`rerun-r3b.out` differ from the ninth review's only by `collected-marked-broken` → `collected-result-missing`;
`rerun-r4_misc.out`, `rerun-n7_broken_audit.out` and 12 rows of `rerun-r1_s1.out` differ only by
`collected-marked-broken` → `collected-result-restored` (the object was present and the name free), after which the
previously refused forced discards succeed (so `r1_s1` has four fewer `restored_discard` rows: the harness skips them
once the record is already `discarded`). The m3 container matrix (`rerun-m3_containers.out`) differs from the ninth's
only where a real empty or junk directory replaced the container: `recover` now re-creates the result inside it
(`collected-result-restored`, `summary-ref-repaired`) and leaves the junk file reported as `orphan-namespace-ref`.

### I-A / I-B / I-D (ninth review) — CLOSED as stated, with U2 adjacent (`rerun-n4_admin.out`; `p_gitdir.out`; `p_gitdir2.err`)

`n4-fifo_gitdir`: collect of a clone and of a worktree, clone spawn, the victim's own `discard --abandon` rc 2 in ≤0.3 s
("linked worktree app has a gitdir that is not a regular file"), `recover` rc 0 `[]`, `status` rc 0; `spawn --worktree`
TIMEOUT (U2). `n4-fifo_head`, `n4-clone_fifo_head`: `status`, `recover` and the victim's own discard TIMEOUT inside
`git rev-parse --show-toplevel` in the worker (I-1); every other worker's collect and both spawns refused by name (or,
for the clone's private `HEAD`, unaffected). `n4-symlink_head_to_fifo`, `n4-symlink_admin_dir`: refused by name in
≤0.4 s; `recover` marks A `ready-marked-broken` because Git refuses the worker ("not a non-bare Git working tree").
SKILL.md:69-72 now states three outcomes; ARCHITECTURE.md:376-379 still states two (I-4).

### Wording and issue codes

The 29 codes at ARCHITECTURE.md:605-616 equal the 29 emitted by `audit.py`/`recovery.py` (regex over `issue("…")`,
`"issue": "…"`: both diffs empty). Every recovery action name used in README/SKILL/ARCHITECTURE (`*-left`, `*-finished`,
`*-restored`, `*-missing`, `*-broken`, `*-failed`, `*-dropped`, `*-ambiguous`, …) exists in `recovery.py` (42 action
names in code; none missing). README.md:204-206 ("reconciles only … it reports the rest") is now true for a foreign
container (T2). Statements contradicted by observation: ARCHITECTURE.md:734-743 (U1), :759-779 (U2), README.md:198-206
with ARCHITECTURE.md:769-774 (U3). Imprecise but not contradicted: ARCHITECTURE.md:376-379, :616 (I-4).

### S1–S4 (seventh review) — hold

S1: `rerun-r1_s1.out` 124 rows, 0 TIMEOUTs; every `after_quarantine`/`after_recheck` row keeps the quarantine with
`quarantine-preserved` + `result-ref-missing`, both forced discards rc 2 "last copy and is kept", restored ref →
`discard-finished`; `rerun-m8_quarantine_result.out` identical to the ninth review's. S2: `rerun-r2_s2.out` 216 rows,
`rerun-r2b_s2_rest.out` 54 rows, `rerun-m2_cross_worker.out`, `rerun-m6_interrupted_worktree.out`: 0 TIMEOUTs; the only
differences from the ninth review's are the refusal wording ("whose name holds" → "which leads to"). S3/S4:
`rerun-r3_codes.out` 306 lines = 153 rows, `status` rc 0 and `recover` rc 0 in every row, 0 TIMEOUTs, 0 `[Errno`;
`rerun-m4_issue_codes.out` identical; `rerun-r4_misc.out` (`refs/cws` FIFO → `status` rc 0; `chmod 000` → raw errno,
unchanged informational).

### S5–S7 (eighth review) — hold (S7 with U1 adjacent)

S5: `rerun-r2d.out` identical to the ninth review's after normalization (the same 4 TIMEOUT cells: `status` and
`recover` in the two admin-directory rows `admin_fifo_head` and `admin_symlink_admin_dir` — the victim worker's own Git
directory, I-1 — while collect and worktree spawn are refused by name there): B's untouched interrupted spawn stays `publishing`, `2:recovery-failed`, promoted
`spawn-publish-finished` after the occupant is removed; `rerun-n6_s5_adjacent.out` 80 rows, 0 TIMEOUTs, wording-only
differences. S6: `rerun-r3b.out`, `p_t2`, `rerun-n5_container.out` (symlinked `workers/1`, `workers/1/results`,
`workers`, `bases`, root: re-collection refused "refusing to write through a symbolic ref", nothing written into the
target, allocation refuses a symlinked `bases`/root with nothing consumed; a symlinked next-ID `workers/<id>` container
remains the documented ID gap, I-3). S7: `rerun-r2_s2.out` 16 scenario rows × operations, 0 TIMEOUTs; `rerun-r2e.out`
5 rows (`status` 49 calls ending at `merge-base`; clone spawn, collect of B, collect of A refused with the last call
`rev-parse --git-common-dir`; `recover` rc 0 — the probe's own `rev-parse HEAD` in A then fails because the plant replaced
A's branch, as in the ninth review's run); `rerun-r2e2.out` 8 rows (unowned symref: clone and both collects block in
`clone`/`fetch`, everything else returns).

### Q1 (sixth), R1–R4 (fifth), N1–N3 (fourth), F1–F5 (third) — hold

`rerun-q1_r1.out`, `rerun-q3_attribution.out`, `rerun-p1_ancestry.out` (19 rows), `rerun-p1b_forged_recovery.out`,
`rerun-p1g.out`, `rerun-p3e.out` (8 rows), `rerun-p4_spot.out`, `rerun-pE_spot.out`, `rerun-pB_reauth.out`,
`rerun-pC_namespace.out` (286 lines), `rerun-m4_issue_codes.out`, `rerun-m8_quarantine_result.out`, `rerun-r2d.out`,
`rerun-timing.out`: identical to the ninth review's after hash/path normalization (0 diff lines each);
`rerun-p6_recover_occupants.out` and `rerun-p2b_clone_direct.out` differ only in hashes; `rerun-p2_occupants.out`
348 rows, 0 IDs consumed, only hash-bearing `before`/`after`/`plant_error` fields differ; `rerun-pA_env.out` 710 Git
invocations (662 in the ninth review; the new guards add calls), `A1_git_invocations_missing_any_GIT_line: 0`, only
the six identity names, `GIT_TERMINAL_PROMPT` and Clonegrown's own `GIT_GRAFT_FILE=/dev/null` reach Git,
`A2_git_honours_graft_env_directly: 0`, `A3_worker_git_honours_local_grafts: 0`. F4 phrase sweep clean; F5 boundary
sentences present (README.md:422-435, ARCHITECTURE.md:779-783).

### Six second-review classes — all PASS (`rerun-pD_classes.out`, 139 lines, identical after normalization)

Private refs (no flag rc 2, flag rc 0, retargeted symref rc 2), dangling symbolic task branch (worktree spawn rc 2,
`next_id` 1, bytes intact, clone spawn rc 0), dangling control links (init/spawn rc 2, links intact, `next_id` 1), CLI
init symlink (absolute/relative/default rc 2, link intact), `GIT_CONFIG`/`GIT_CONFIG_COUNT` (spawn rc 0 ×2), rewrite
policy (default rc 2, flag rc 0, repeats rc 0), F5 flagless discard of a clone with `ORIG_HEAD` rc 0.

### Step 7.5i collection-timing properties — 5/5 (`rerun-timing.out`, identical to the ninth review's)

`direct_conflict`: "conflicting result ref already exists … expected <candidate>, found <planted>", preserved, worker
`ready`; `symbolic_exact_conflict`: "refusing to write through a symbolic ref", raw target intact;
`locked_metadata_finalization`: move attempts on result and summary both rc 128 while prepared, record `collected`,
both refs at the candidate; `object_only_recovery`: one `write_ref` with the all-zero expected value,
`collect-finished`, `collected`; `object_only_recovery_conflict`: `collect-reset-ready`, conflict preserved at the
planted value.

## 4. Coverage-map spot checks

| Item | Result |
|---|---|
| 5.1 active-writer race / 7.5i | Timing 5/5 (`rerun-timing.out`); occupants at summary/result names during collect and recovery refused or left (`rerun-p6`, `rerun-p2b`, `rerun-r1_s1` FIFO rows). Gap: U1 at the next ID's names (block, nothing consumed). |
| 5.2 ignored work | First refusal names count and sample; re-authorization re-asks (`rerun-pB_reauth`, `rerun-r1_s1` `changed_in_quarantine`). |
| 5.3 unchecked deletion | Quarantine, fingerprint recheck, preserved-on-change, result preservation at resume/re-authorization (`rerun-r1_s1` 124 rows, `rerun-m8`); foreign-head refusal leaves discards retryable (`rerun-n6`). |
| 5.4 branch ownership | Create-only allocation refuses every occupant (`rerun-p2_occupants` 348 rows, 0 consumed); cleanup retains a foreign name/owner (`rerun-p3e`, `rerun-m4`). Gap: U1 at the generated name (block instead of refusal; nothing consumed). |
| 5.5 changed published recovery | `recovery.py:217-250`; `test_worktree` and `test_parent_interruption` pass in the suite; `rerun-r2d`/`rerun-n6` promote B after the occupant is gone (S5). |
| 5.6 installer root | `sh -n install.sh` OK; `test_installer` 25 in the suite; not hand-probed. |
| 5.7 / 5.8 remotes and config | `_canonicalize_remote_url` (`repository.py:140-148`), `ConfigOccurrence(value=None)` (`:44-48`, `:93-106`); `test_repository` 8 pass; `rerun-pE 5.10_remote_copied: true`. |
| 5.9 Git sanitation | `rerun-pA_env`: 710 Git invocations, `A1_git_invocations_missing_any_GIT_line: 0`, only the six identity names, `GIT_TERMINAL_PROMPT` and Clonegrown's own `GIT_GRAFT_FILE=/dev/null` reach Git; `A2_git_honours_graft_env_directly: 0`, `A3_worker_git_honours_local_grafts: 0`; `rerun-pD class5`. |
| 5.10 secret-bearing errors | `rerun-pE 5.10_command_failure_text` `https://<redacted>@…`, `5.10_raw_git_shows_secret: false`; `rerun-p4 5.10_redaction`. |
| 5.11 stale request reuse | Same params → same worker; different → refused; discarded with deleted result → retry refused, `discarded-result-missing` (`rerun-pE 5.11_*`). |
| 5.12 incomplete status | 29 codes in ARCHITECTURE.md:605-616 = 29 emitted by `audit.py`/`recovery.py` (both diffs empty); every recovery action name used in the documents exists in `recovery.py`. Gap: U3 (false codes while a blocking occupant is present and the namespace is packed). |
| 5.13 create-only allocation | Rewound counter refused with "nothing was changed" (`rerun-pE 5.13`); 348 + 24 + 6 + 4 occupant rows consume nothing; the post-allocation refusal gap is documented (I-3). |
| 5.14 API/CLI parity | `rerun-p4 5.14_parity`: both `mode: clone, strong: false`; worktree+strong refused by both. |
| 5.15 invalid generated branch | `x.lock` → "generated task branch is invalid for Git", `next_id` unchanged (`rerun-pE`, `rerun-p4`). |
| 5.16 low-level errors | Five-part context on every refusal quoted above (`rerun-p4 5.16_context`), including the `ForeignWorktreeHead` texts. |
| 5.17 timing gate | `grep ratio tests/campaign/hardening_suite.py` matches only the word inside `operation`; `parallel_spawns_unique` PASS in both modes. |
| 5.18 one-shot | `--abandon` and `claim` refused for a collected worker; leased discard refused under every flag (`rerun-pE 5.18`, `rerun-p4`, `rerun-n7 discard_force_leased`). |
| Comment/public overclaims | Notices current in intent (require a fresh review and hosted CI) but summarize only through 7.5v (I-4); F4 phrases absent. Overclaims found: ARCHITECTURE.md:734-743 (U1), :759-779 (U2), README.md:198-206 with ARCHITECTURE.md:769-774 (U3). |
| `CWSError`, heartbeat, failpoints | `grep -rn CWSError clonegrown/` empty; `heartbeat` only as a hidden bookkeeping key (`cli.py:31`); `failpoint` gated on `CLONEGROWN_TEST_MODE == "1"` (`core.py:485`). |
| retention, teardown, license, package | `pyproject.toml`: `license = "Apache-2.0"`, `license-files`, `requires-python >=3.11`, dynamic version `0.1.0a1`; wheel/sdist from the rsync copy (section 5); `licenses/LICENSE` in the wheel identical to the checkout's (`cfc7749b…`); result refs and records survive every normal discard (`rerun-r1_s1` controls, `rerun-n3`, `p_t2`). |
| macOS, Python/Git versions, filters/LFS, resource boundaries, repository diversity, repeated verification, auxiliary-ref cost | Not freshly exercised (section 6); `test_filters_and_resources` 4, `test_auxiliary_refs` 4, `test_campaign_records` 16, `test_lease` 10 pass in the suite. |

## 5. Gate results

- **Unit suite:** `cd /home/serrecchia/Projects/clonegrown && python3 -m unittest discover -s tests -v` (in the checkout,
  no cache prefix) → **Ran 291 tests in 347.707 s, OK** (291 `ok`, 0 failures, 0 errors, 0 skipped); wall 01:49:35 →
  01:55:23; log `/tmp/clonegrown-review8-unittest.log`. Per module (from the log): quarantine 35, audit 32+, worktree 26+,
  installer 25, allocation 19+, safety_errors 19, campaign_records 16, discard_ignored 15, core 14, state 12, lease 10,
  repository 8, api 6, cli 6, parent_interruption 6, auxiliary_refs 4, collect_policy 4, filters_and_resources 4,
  package_metadata 2 (a few long names wrap in the verbose log; the total is Python's own count). The three gates ran
  sequentially (`gates.sh`) while nothing else of this review was running.
- **Hardening, clone mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`: "git lacks reftable
  support"), **0 failed**; sum of case seconds 74.7; wall 81 s; `generated` 01:56:43;
  `sha256 454ee65334b5bd3abde0aa21d714008a36025581210ac2bf34e01dcc5a3e3a51 /tmp/clonegrown-review8-hardening-clone.json`
  (log `/tmp/clonegrown-review8-hardening-clone.log`, exit 0).
- **Hardening, worktree mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`), **0 failed**; sum of case
  seconds 76.7; wall 82 s; `generated` 01:58:06;
  `sha256 ddff924fb0a8395346712300e304545bd9b5ad25e8727d0b7a6f75ae70370628 /tmp/clonegrown-review8-hardening-worktree.json`
  (log `/tmp/clonegrown-review8-hardening-worktree.log`, exit 0).
- `git diff --check` clean; `sh -n install.sh` OK; `python3 -m compileall -q clonegrown tests` OK with
  `PYTHONPYCACHEPREFIX=/tmp/clonegrown-review8-pyc`; wheel and sdist built with `python -m build` in a venv on the rsync
  copy `/tmp/clonegrown-review8-build/src`: `clonegrown-0.1.0a1-py3-none-any.whl` 102,142 bytes sha256
  `f0fca7f77cbb96af736b29d3eb53dcb322174ef220e75e6bbe28d940e86f0941`, `clonegrown-0.1.0a1.tar.gz` 204,767 bytes sha256
  `3021a3eb324efbb8940b12cb93f9f72a3bbfe5870bf659333f30712978e3764c`; `License-Expression: Apache-2.0`, `Requires-Python:
  >=3.11`, MacOS and POSIX::Linux classifiers, `clonegrown-0.1.0a1.dist-info/licenses/LICENSE` present and identical to
  the checkout's (`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`); isolated install in a second venv:
  `clonegrown --version` and `python -m clonegrown --version` both print `clonegrown 0.1.0a1`. No `build/`, `dist/` or
  `egg-info` in the checkout after the run; `git status --short` unchanged (log `/tmp/clonegrown-review8-static.log`).
- Versions: CPython 3.12.3, Git 2.43.0 (`/usr/bin/git`), Linux 6.17.0-35-generic.
- Tree fingerprints: start `342f9c3520db5994f6062acb4c6839d969f301f22eae5ac2065fe6c9c0a3054f`, end `961abeba9919a477cc1d8affcbb2f5af36303d13a437757284179a7a0a5fc987`.

## 6. Not verified, and why

- Hosted CI on a pushed revision, macOS, CPython 3.11, exact Git 2.29.0: not available locally; the tree is uncommitted.
  Whether Git 2.29's `symbolic-ref` follows a symbolic chain the way 2.43 does (U1) was not checked on that version
  (`--[no-]recurse` was added in 2.40; the earlier behaviour was to resolve fully).
- reftable repositories and `GIT_REF_FORMAT` end to end: Git 2.43 cannot create them (hardening skip); the
  `inventory is None` fallbacks were read, not exercised.
- Random-kill and state-machine campaign seeds, `real_repository_qualification.py`, and the benchmark harnesses: not in
  the requested gate list and not run.
- A socket occupant (a FIFO proves the class); admin-directory files other than `HEAD` and `gitdir` (`commondir`,
  `locked`: `git worktree list --porcelain` reads `locked`, but it is the worker's private Git directory and no document
  claims its inspection).
- The fifth review's `p3_wording.py`/`p5_fifo.py` and the seventh review's `m1_matrix.py`/`m5_gitlog.py`/
  `m7_attribution.py` were not rerun (their rows are covered by the `r1`, `r2`, `r3`, `m2`/`m3`/`m4`/`m6`/`m8` reruns and
  `rerun-pA_env`).
- Genuine disk/inode exhaustion, network filesystems, Git LFS, native Windows: stated boundaries, not exercised.
- `HANDOFF.md` and the Step 7.5a–7.5ad completion records: deliberately not read.

Probe inventory: `/tmp/clonegrown-review8-probes/{h8,p_alloc,p_alloc2,p_testgap,p_packed,p_t2,p_gitdir,p_gitdir2,cmp8}.py`,
`rawgit_symref.sh`, `gitlog.sh`, `kill_blocked.sh`, with outputs `p_alloc.out`, `p_alloc2.out`, `p_testgap.out`,
`p_packed.out`, `p_t2.out` (containers root/workers/workers/1/workers/1/results), `p_t2b.out` (bases, restore,
occupied, object-gone, symref), `p_gitdir.out`, `p_gitdir2.out`/`.err`; copies of the ninth review's `n1`–`n8`, `r1`–`r4`
probes with paths rewritten to `review8` and their reruns `rerun-*.out`/`.err` (`rerun_t1t2.sh`, `rerun_all8.sh`, logs
`rerun_t1t2.log`, `rerun_all8.log`); the fourth–seventh reviews' probes rerun in place from their own directories;
disposable repositories under `/tmp/clonegrown-review8-work/`; suite log `/tmp/clonegrown-review8-unittest.log`;
hardening logs and JSON `/tmp/clonegrown-review8-hardening-*`; wheel, sdist and venvs under `/tmp/clonegrown-review8-build/`.

## Eleventh fresh review (ninth Step 7.5 pass, after Step 7.5ae): GO

An eleventh fresh reviewer, with the same inputs and exclusions, found U1–U3
and the tenth review's wording notes closed, every earlier class holding by
probe, code reading, the 294/294 suite, and both hardening modes (56 pass, 1
conditional reftable skip, 0 fail each), and returned **GO: no open finding
of any severity contradicts the product contract or a public claim**. The
verdict is bounded as the report states: hosted CI, macOS, CPython 3.11,
and exact Git 2.29.0 were not exercised locally; 36 of the 44 earlier-review
probes were not rerun because six of the eight product modules were
byte-identical to the tree the tenth review had rerun them on; and one
Git-version-dependent behaviour (whether Git 2.29's loose-ref scan skips a
plain FIFO leaf) is left to the minimum-Git CI job. Informational notes:
the public notices counted the later reviews as "two" (corrected to eight
in a documentation-only change after the review); a FIFO at a linked
worktree's admin `commondir` file, which is the worker's private Git
directory and outside the documented inspection, still blocks Git.

The reviewer's full report is preserved verbatim below.

---

# Clonegrown final cold review — release qualification (eleventh fresh review)

Date: 2026-09-03. Reviewer: fresh agent, read-only on `/home/serrecchia/Projects/clonegrown` (uncommitted working tree
on `main`, base `c9728a0`). Environment: Linux 6.17.0-35-generic, CPython 3.12.3, Git 2.43.0 (`/usr/bin/git`).
Every probe, log, wheel, venv and result lives outside the checkout: new probes and outputs in
`/tmp/clonegrown-review9-probes/`, disposable repositories in `/tmp/clonegrown-review9-work/`, path-rewritten copies of
the earlier reviews' probes and their reruns in `/tmp/clonegrown-review9-rerun/` (`r<N>-probes/`, `r<N>-work/`,
`out/rerun-*.out`), build products under `/tmp/clonegrown-review9-build/`, byte-code cache under
`/tmp/clonegrown-review9-pyc/`. `HANDOFF.md` and the Step 7.5a–7.5ae "Completion record" sections were not read (Step
titles and task bullets were); no `.env`-pattern file was opened (the rsync build copy excluded them); nothing inside
the checkout was modified (the wheel and sdist were built from an `rsync` copy; `compileall` ran with
`PYTHONPYCACHEPREFIX`; the unit suite ran in the checkout without a cache prefix, as CI does). Every Git command and
Clonegrown call that could touch a planted FIFO ran under a 4–10 s `timeout` (`TIMEOUT` below means the process was
killed while blocked); Git grandchildren left blocked on FIFO opens were killed at the end (`kill_blocked.sh`, matched
by cwd/argv under the review work roots; see section 5).

**Tree fingerprints.** `git diff | sha256sum` at start `ec3791390347a7ac4f7a9c385236d8cbcf07c5a3157b9d9bf12bc48521e7d935`,
at end `eb760ece49025c57669cba9018c81f40ee5c48d90d59d31f3d40ec1ce634a174`; `git status --short` lists 23 entries at both ends (22 modified tracked files plus untracked
`tests/test_collect_policy.py`). The fingerprints differ because another session rewrote `PLAN.md` and `HANDOFF.md` at 02:53:34
while this review ran (first command 02:42:41). No product module, test, or public document changed: every `clonegrown/*.py`,
`tests/*.py`, `tests/campaign/*.py` mtime is ≤ 02:35:22 and `README.md`/`SKILL.md`/`ARCHITECTURE.md` are 02:41:30, all before
the review's first command; `git diff -- clonegrown README.md SKILL.md ARCHITECTURE.md tests | sha256sum` is
`f884cb08047f3d2601ee5657fde03ccafcffc5201256d743e81ac64e3cffa972` at the end. sha256 (first 12) of the product reviewed:
audit `52b5f6f500ba`, cli `a309e205fbb4`, core `fc2af01adbd3`, lifecycle `200799caa028`, recovery `7d207f6d7c96`,
repository `c0a0ed955bed`, state `043a08cd21ac`, worker `dcd6e8e0199a` — six of the eight modules are byte-identical to the
tree the tenth review verified (its hashes: audit, cli, core, lifecycle, recovery, state identical); only `repository.py`
(was `5807b935a035`) and `worker.py` (was `a79366313fb8`) changed, which is where Step 7.5ae's three fixes live.

## 1. Verdict: GO

No open finding contradicts the product contract or a public claim.

- **U1 — CLOSED.** A symbolic ref whose chain ends at a FIFO (directly, via a symlink, through a second symbolic ref,
  at a one-level name, or at an absolute/`..` target) at the next ID's base-pin name is allocation evidence for both
  spawns (`symbolic base ref`, nothing consumed, occupant byte-identical, no `.lock`); at the generated task-branch
  name it is evidence for a worktree spawn (`symbolic task branch`, nothing consumed) and a by-name refusal for a clone
  spawn (the documented post-allocation ID gap). No Git command blocks: `is_symbolic_ref` reads the loose file raw
  and only falls through to `git symbolic-ref -q --no-recurse` when there is no loose file. Every other caller of
  `is_symbolic_ref` (`is_foreign_ref` → audit, recovery, transactions) is behind the same raw read. Section 3.
- **U2 — CLOSED.** A FIFO or symlink-to-FIFO at a linked worktree's admin `gitdir` is refused by name before `git
  worktree add`; the refused spawn's rollback returns (record `spawn_failed`, stage removed, 64 Git calls, last one
  `rev-parse --verify --quiet <branch>^{commit}`), `status`, `recover` (which cleans an interrupted spawn whose admin
  entry was never recorded, i.e. `locate_worktree_admin` walks past the FIFO), clone spawn, collect of a clone and of a
  worktree, and the victim's own abandonment all return; after the pointer is restored `recover` finishes the
  abandonment and a new worktree spawn is `ready`. Section 3.
- **U3 — CLOSED.** With `refs/cws/<ws>/` fully packed and a blocking symbolic chain planted at the next ID's summary,
  at the next ID's base pin, at a collected worker's own summary name (loose symref shadowing the packed value), and
  through a second symref, `status` reports only the occupant (`namespace-ref-symbolic`) plus the genuine
  `owner-process-dead` of the interrupted spawn — no `summary-ref-mismatch`, `branch-owner-ref-missing`,
  `base-ref-missing`, or `result-ref-missing`; `recover` (twice) changes no record byte and reports only
  `recovery-failed` for the interrupted spawn and `<code>-left`; after removal one `recover` promotes the interrupted
  spawn and `status` is empty. Section 3.
- **Wording (I-4) — CLOSED.** ARCHITECTURE.md:377-387 states the three interrupted-spawn outcomes; :620-622 lists the
  read-only Git forms `status` runs, and a logged `status` (159 Git calls) used exactly `--no-optional-locks status`,
  `rev-parse`, `for-each-ref`, `symbolic-ref -q [--no-recurse]`, `config --get`, `merge-base --is-ancestor` plus
  `git --version` (the `--no-recurse` capability probe; read-only) — `cat-file -e` is in the list but appears only in
  `recover`, so the documented list is a superset; the notices name Steps 7.5p–7.5ae. The 29 issue codes in
  ARCHITECTURE.md equal the 29 emitted by `audit.py`/`recovery.py` (both set differences empty); every recovery action
  name used in README/SKILL/ARCHITECTURE exists in `recovery.py` (37 action names in code, none missing).
- T1–T2, S1–S7, Q1, R1–R4, N1–N3, F1–F5, the six second-review classes and the five Step 7.5i properties hold on
  reruns (section 3). Unit suite 294/294; both hardening modes 56 passed, 1 conditional reftable skip, 0 failed; every
  static and packaging gate passes (section 5).

Everything else found is informational (section 2). The GO is bounded by section 6: hosted CI on the pushed revision,
macOS, CPython 3.11 and exact Git 2.29.0 were not exercised locally, and one Git-version-dependent behaviour (whether
Git 2.29's ref enumeration opens a plain FIFO leaf) is stated there rather than verified.

## 2. Findings, ranked by severity

No finding of any severity is open. Informational notes, none of which contradicts a documented claim:

- **I-1 — Notice wording (documentation accuracy, not behaviour).** README.md:25-26 says "Two further fresh reviews of
  the repaired tree found and Steps 7.5p–7.5ae repaired …" and SKILL.md:19-20 says "Two later reviews found …".
  `research/FINAL_COLD_REVIEW.md` records eight fresh reviews after the one that produced Steps 7.5j–7.5o (headers at
  lines 203, 550, 973, 1377, 1770, 2223, 2620, 3025: third through tenth), producing 7.5p–7.5ae. ARCHITECTURE.md:10
  says "later reviews" and is accurate. The defect classes the sentences list are all present in those reviews; only
  the count "two" is stale. No product claim is affected.
- **I-2 — A FIFO at a linked worktree's admin `commondir` blocks Git for every worker (worker-private admin file; no
  document claims its inspection).** `p9_adj.py` rows `commondir`: raw `git worktree list` and `git worktree add`
  block; Clonegrown `status`, `recover`, `spawn --worktree` and `collect` of a clone worker TIMEOUT 8 s while a clone
  spawn returns. The preflight `lstat`s exactly `HEAD` and `gitdir` (`repository.py:718`), which is exactly what
  ARCHITECTURE.md:764-771 and :788-789 promise; the tenth review listed `commondir`/`locked` as unverified for the same
  reason. The admin directory is the worker's private Git directory (ARCHITECTURE.md:207-210), so by the caller's rules
  this is not a finding. It is a one-token extension of the existing guard (add `"commondir"` to the tuple at
  `repository.py:718`) if the maintainers want other workers' operations to fail closed on it too; a FIFO at `locked`
  blocks only raw `git worktree list` (`p9_adj.py` row `locked`: every Clonegrown operation probed returned).
- **I-3 — Refusals after allocation consume an ID (documented gap).** A blocking occupant at a name allocation does not
  inspect — a recorded worker's summary (`p9_u3.py` `own_summary_shadow`: `next_id` 6 → 8 across a refused clone and
  worktree spawn), a stray name under `refs/heads/agent/<ws>/` (`p9_adj.py` `agentsub`: 2 → 4), or the generated branch
  name for a *clone* spawn (`p9_u1.py` `next_branch` rows: 1 → 2, record `spawn_failed`) — is refused by the
  pre-clone/pre-`worktree add` guard after `next_id` advanced. ARCHITECTURE.md:471-473 ("leaves the id unused, an
  observable gap") and :782-784 (evidence only at the base-pin and task-branch names) describe exactly this; the
  caller's rules exclude it.
- **I-4 — Git's own directory handling.** A refused clone spawn at the generated branch name leaves an empty
  `refs/cws/` directory after its withdrawn base pin (`p9_u1.py` `refs_same=false` rows; verified by listing diff:
  `added: ['refs/cws/']`), and `git pack-refs --all` removes the empty `bases/` directory (`rawgit9.sh` case f had to
  be redone inside `p9_u3.py`, which creates the directories when planting). Not reported by `status` (an empty
  container directory is documented as ordinary residue). Not a finding.
- **I-5 — A FIFO at a worker's own `HEAD` or `commondir` blocks `status`/`recover`/the worker's own operations**
  (rerun `n4_admin` rows `fifo_head`/`clone_fifo_head`; `p9_adj.py` `commondir`): Git running inside the victim
  (`rev-parse --show-toplevel` in `verify_worker`) opens the file. The agent's private Git directory; the ninth and
  tenth reviews' I-A/I-1; no document claims inspection of it.

## 3. Verification record

### U1 — CLOSED (`p9_u1.py` → `p9_u1.out`, 72 rows; `rawgit9.sh` → `rawgit9.out`; `p9_adj.py` rows `cycle`, `abs`; rerun `n1_symref_namespace` next-pin rows; `p_alloc2`, `p_testgap` reruns)

Eight fresh repositories (next ID 1): {next ID's base pin, generated worktree branch `refs/heads/agent/<ws>/1-next-task`} ×
{symref → FIFO, symref → symlink → FIFO, symref → symref (`workers/9/result`) → FIFO, symref → one-level FIFO at the Git
directory root}. In every row raw `git symbolic-ref -q <name>` TIMEOUT (the object does block Git), while `status` rc 0
(`namespace-ref-symbolic` for the pin rows; nothing for the branch rows — the branch name is not in the namespace),
`spawn --worktree` rc 2 in 0.1–0.2 s ("already has a symbolic base ref" / "symbolic task branch"; `next_id` 1 → 1, no
record, no `.lock`, occupant byte-identical), `spawn` (clone) rc 2 in 0.1 s at the pin with `next_id` 1 → 1, and at the
branch name rc 2 in 0.3 s by the enumeration guard with `next_id` 1 → 2 and record 1 `spawn_failed` (I-3),
`recover` rc 0; a direct `allocation_evidence(...)` call under a 6 s alarm returns `['symbolic base ref']` or
`['symbolic task branch', …]` without blocking; after removal `recover` `[]`, `status` `[]`, and a worktree spawn
succeeds. Adjacent: a two-ref cycle at the next pin (Git itself refuses, rc 128) and symrefs whose target is an
absolute path or `../../ext-fifo` (Git refuses those targets, rc 128; `rawgit9.sh` d) are all `symbolic base ref` /
`symbolic task branch` evidence with `next_id` unchanged. `rawgit9.sh` c: `symbolic-ref -q --no-recurse` on a symref →
FIFO returns rc 0 in 0.0 s on Git 2.43.0 (the fallback Clonegrown uses only when no loose file exists), and the
`_symbolic_ref_supports_no_recurse` probe is the one `git --version` call in every status. The rerun of the ninth
review's matrix (`rerun-n1_symref_namespace.out`, 24 rows) now has TIMEOUT only in the 24 raw `for-each-ref` cells: the
four `next_pin` rows report `spawn_clone` and `spawn_wt` rc 2 in 0.1 s with `next_id` 3 → 3 (they were the U1 blocks).
Test gap closed: `tests/test_allocation.py:169` reloads `WorkspaceState` before each plant and asserts `next_id`
unchanged for the pin and for the worktree spawn at the branch; `tests/test_audit.py:341` reloads `next_id` before every
plant ("refused spawns consume IDs: plant at the *current* next pin"); the rerun of `p_testgap.py` is preserved as a
record of the old gap's mechanics only. Code: `repository.py:823-833` (`is_symbolic_ref`), `:839-849`; callers
`worker.py:678`, `:697`, `repository.py:820`.

### U2 — CLOSED (`p9_u2.py` → `p9_u2.out`, 24 rows; rerun `n4_admin`, `p_gitdir2`)

Two fresh repositories (FIFO; symlink → FIFO at worktree worker 1's admin `gitdir`), each with a ready clone (2), a
ready worktree (3) and a worktree spawn interrupted at `spawn.after_worktree_add` (4, admin entry unrecorded). Logged
through `CLONEGROWN_GIT`: `spawn --worktree` rc 2 in ≤0.5 s after 64 Git calls (last `rev-parse --verify --quiet
refs/heads/agent/<ws>/5-new-wt^{commit}`; "linked worktree app has a gitdir that is not a regular file"), record 5
`spawn_failed`, the only stage left is worker 4's own; `spawn` (clone) rc 2 (46 calls, last `rev-parse
--git-common-dir`); `status` rc 0 (165 calls, issues `4:owner-process-dead` only); `recover` rc 0 → `4:spawn-cleaned`
(98 calls: `locate_worktree_admin` walked past the FIFO entry and found worker 4's by its `gitdir`); `collect 2`,
`collect 3` rc 2 by name; `release 1` rc 0; `discard 1 --abandon` rc 2 by name after quarantining (record `discarding`,
`recover` → `quarantine-preserved`, content intact); occupant byte-identical throughout. After restoring `gitdir`:
`recover` → `1:abandon-finished`, `status` `[]`, `spawn --worktree` → `ready`. Code: `worker.py:978-988`
(`_read_pointer`: `lstat` + `O_NOFOLLOW`), `:1021-1044` (`locate_worktree_admin` skips non-regular pointers),
`repository.py:718-729`.

### U3 — CLOSED (`p9_u3.py` → `p9_u3.out`, 44 rows; `p9_adj.py` row `packedfifo`; rerun `p_packed` not needed — superseded)

Four fresh repositories with a collected+released clone (1), a ready worktree (2), a ready clone (3), a normally
discarded clone (4), and a worktree spawn interrupted at `spawn.after_publish` (5, `publishing`), then `git pack-refs
--all` (loose namespace `[]`, 7 packed namespace refs). Plants: symref → FIFO at `workers/6/result`, at `bases/6`, at
`workers/1/result` (shadowing the packed summary), and `bases/6` → `workers/6/result` → FIFO. Raw `for-each-ref
refs/cws/<ws>/` TIMEOUT in 4/4. `status` rc 0 in 0.4–0.5 s: `5:owner-process-dead` + `6:namespace-ref-symbolic` (twice
for the chain), or `1:namespace-ref-symbolic` for the shadow — no `summary-ref-mismatch`, `branch-owner-ref-missing`,
`base-ref-missing` or `result-ref-missing`; `recover` twice: `5:recovery-failed` + `<code>-left` (+
`1:summary-ref-symbolic-left` for the shadow), `records_changed: []` (sha256 of every record file), worker 1's result
ref resolves, occupant byte-identical, no `.lock`; `collect 3` refused by name; spawns at the next-ID names refused with
`next_id` unchanged (the shadow row consumes two IDs, I-3); `discard 1` rc 0 (its immutable packed result is intact);
after removal `status` `[5:owner-process-dead]` → `recover` `[5:spawn-publish-finished]` → `status` `[]`, and worker 1's
packed summary still names its result. A plain FIFO leaf in a packed namespace (enumeration not skipped): Git 2.43's
`for-each-ref` returns rc 0 (it skips non-regular entries; `rawgit9.sh` a), `status` reports `9:orphan-namespace-ref`,
every operation returns. Code: `repository.py:940-953` (`enumeration_blocks` → `_packed_refs`), `:973-1007`.

### Wording and issue codes (`p9_forms.py` → `p9_forms.out`)

See section 1. Statements checked against observation: ARCHITECTURE.md:377-387 (three outcomes; `p9_u3` rows show
`recovery-failed` then `spawn-publish-finished`), :739-795 (every sentence about occupants, the packed read, the
`is_symbolic_ref` raw read, allocation evidence, the admin `gitdir` refusal and the rollback return, the unowned
boundary), :620-622 (Git forms), README.md:198-207 (`status` reports only detected disagreements — no false codes in
`p9_u3`), :17-35 and SKILL.md:14-26 (notices; I-1 for the count), SKILL.md:70-74.

### T1 (ninth review) — CLOSED (reruns `n1_symref_namespace` 24 rows, `n2_detached_head` 6 rows, `n1b_attribution`, `n3_unowned_boundary`, `p_alloc2`; plus `p9_u1`/`p9_u3`)

`rerun-n1_symref_namespace.out` (6 names × 4 kinds, fresh repositories with a collected+released clone and a ready worktree):
raw `git for-each-ref refs/cws/<ws>/` TIMEOUT in 24/24 (the object blocks Git); every Clonegrown operation returns:
`status` rc 0 reporting `namespace-ref-symbolic` (or `orphan-namespace-ref` for the FIFO inside the namespace), `recover`
rc 0, `spawn`, `spawn --worktree` and `collect 2` rc 2 by name in 0.1–0.3 s, `discard 1` rc 0 except at the immutable
result name ("not preserved"), occupant byte-identical, no `.lock`; the four `next_pin` rows — the tenth review's U1
blocks — now report `spawn_clone` and `spawn_wt` rc 2 in 0.1 s with `next_id` 3 → 3. The only TIMEOUT cells in the whole
file are the 24 raw `for-each-ref` checks. `rerun-n1b_attribution.out`: `status` 4× rc 0, `recover` rc 0, `spawn_clone`,
`spawn_wt`, `spawn_clone_next`, `spawn_wt_next` rc 2 (the last two were Git call 11/12 blocks in the tenth review); the
three TIMEOUT rows are raw `for-each-ref`, `rev-parse --verify` and `symbolic-ref -q` on the planted name.
`rerun-n2_detached_head.out` (6 rows, 0 TIMEOUT): A's collect and request retry refused (`task-branch-foreign`), every
other operation rc 0 or rc 2 by name, identical to the tenth review's after normalisation (32 diff lines are truncated
`err` tails that differ only by path length). `rerun-n3_unowned_boundary.out` (0 diff lines beyond paths): with
`refs/heads/foo` → FIFO exactly `spawn` (clone), collect of a worktree and collect of a clone TIMEOUT — the two
operations ARCHITECTURE.md:791-795 names — and everything else returns. `rerun-p_alloc2.out`: case A `spawn_wt_same_task`
now rc 2 (was TIMEOUT); case B (symlinked `refs/heads/agent/<ws>` container) still blocks only `collect 2` and the clone
spawn inside `fetch`/`clone` — the tenth review's I-2, consistent with :745-757.

### T2 (ninth review) — CLOSED (rerun `n8_container_breaks` 6 rows: 0 diff lines from the tenth review's, 0 TIMEOUT; rerun `n5_container` 40 rows: 0 TIMEOUT, wording-only diffs; `tests/test_audit.py:225-291` in the suite)

A foreign occupant (symlink, FIFO, plain file) at `workers` or the namespace root never marks a collected worker
`broken`: `recover` reports `collected-result-missing` and leaves every record `collected`; restoring the container brings
every result ref back and a normal `discard` succeeds. The tenth review's `p_t2.py` (containers `workers/<id>`,
`workers/<id>/results`, `bases`; the restore/occupied/pruned/symref rows of `p_t2b.py`) was interrupted by the
coordinator's finalisation request after 4 s and is recorded in section 6; the container walk it exercises
(`loose_ref_occupant` ancestors, `raw_ref_inventory` prefix inspection) is unchanged since that review except for the
packed-refs read verified under U3.

### I-A / I-B / I-D (ninth review) — CLOSED (rerun `n4_admin` 45 rows; `p9_u2`)

`n4-fifo_gitdir`: `status` rc 0, `recover` rc 0 `[]`, collect of a clone and of a worktree, clone spawn, worktree spawn
(now rc 2 in 0.3 s — the tenth review's U2 TIMEOUT), and the victim's own `discard --abandon` all rc 2 by name ("linked
worktree app has a gitdir that is not a regular file"). `n4-symlink_head_to_fifo`, `n4-symlink_admin_dir`: refused by
name in ≤0.4 s; `recover` marks A `ready-marked-broken` because Git refuses the worker. `n4-fifo_head`,
`n4-clone_fifo_head`: `status`, `recover` and the victim's own discard TIMEOUT inside Git running in the worker (I-5);
every other worker's collect and both spawns are refused by name (or unaffected for the clone's private `HEAD`).

### S1–S7 (seventh and eighth reviews) — hold by code reading, the unit suite, hardening, and the reruns that completed; earlier probes not rerun (section 6)

S1 (quarantine keeps the last copy when the result disappears): `worker.py:471-478`, `lifecycle.py:1298-1302`; suite
`test_quarantine` 35, `test_discard_ignored` 15. S2 (foreign occupants refused before Git): `repository.py:625-673`,
`:806-820`, `:1061-1076`, `:1200-1214`; `p9_u1`/`p9_u3`/`n1`/`n2` above. S3/S4 (audit codes, no crash on occupants):
`p9_forms` 29 = 29, `p9_adj` `packedfifo`/`cycle`/`abs` rows rc 0. S5 (foreign-head refusal leaves interrupted spawns
retryable): `recovery.py:224-225`, `p9_u3` rows `5:recovery-failed` → `5:spawn-publish-finished`; `p9_u2`
`discard_a_abandon` → `quarantine-preserved` → `abandon-finished`. S6 (writes through symlinked containers refused):
`n5_container` rerun 40 rows, 0 TIMEOUT, only wording diffs. S7 (task-branch-foreign): `n2` rerun, `p9_adj` `agentsub`.
The seventh/eighth reviews' `r1_s1`, `r2_s2`, `r2b`, `r2d`, `r2e`, `r2e2`, `r3_codes`, `r3b`, `r4_misc`, `n6`, `n7` probes
were queued in `rerun_all9.sh` and not reached before finalisation; the modules they exercise other than
`repository.py`/`worker.py` are byte-identical to the tree on which the tenth review reran them clean.

### Q1 (sixth), R1–R4 (fifth), N1–N3 (fourth), F1–F5 (third) — hold by code reading and the suites; earlier probes not rerun (section 6)

Q1/R1 (ancestry by object content, canonical-side repeat): `repository.py:459-482`, `lifecycle.py:848-851`,
`recovery.py:278-282`, `recovery.py:673-677`; suite `test_collect_policy` 4, `test_audit`, hardening
`unrelated_history_policy` PASS in both modes. R2–R4 (GIT_* stripping, raw occupants, lstat before Git): `core.py:53-86`,
`:298-307`; hardening `git_environment_sanitized` PASS ×2; `p9_forms` logged 159 Git calls per `status`, all read-only
forms. N1–N3 (rewrite policy, re-authorisation, raw namespace inventory): `lifecycle.py:757-778`, `:1260-1333`,
`repository.py:882-970`; hardening `collect_idempotent` PASS ×2; suite `test_quarantine`. F1–F5 (symbolic private refs,
dangling task-branch names, dangling control links, CLI symlink, GIT_CONFIG): `worker.py:214-240`, `repository.py:852-879`,
`core.py:387-402`, `cli.py:206-216`, `core.py:62-86`; suite `test_allocation` 19, `test_cli` 6, `test_core` 14; F4 phrase
sweep of README/SKILL/ARCHITECTURE found no absolute claim contradicted by observation; F5 boundary sentences present
(README.md:427-440, ARCHITECTURE.md:791-795).

### Six second-review classes — hold by suite and hardening; `pD_classes` not rerun (section 6)

Private refs (`test_discard_ignored`, hardening `config_stash_isolation`), dangling symbolic task branch
(`tests/test_worktree.py:188-230`, `p9_u1` `next_branch` rows: worktree spawn refused with `next_id` unchanged and the
occupant intact), dangling control links (`core.py:387-402`, `test_allocation`), CLI init symlink (`cli.py:206-216`,
`test_cli`), `GIT_CONFIG`/`GIT_CONFIG_COUNT` (`core.py:62-79`, `test_core`), rewrite policy (`lifecycle.py:757-763`,
`test_collect_policy` 4/4).

### Step 7.5i collection-timing properties — 5/5 (`/tmp/clonegrown_probe_collection_timing.py` → `timing.out`)

`direct_conflict`: "conflicting result ref already exists … expected <candidate>, found <planted>", planted value
preserved, worker `ready`; `symbolic_exact_conflict`: refused during custody verification, raw target
`refs/heads/probe-symbolic-result-target` intact, worker `ready`; `locked_metadata_finalization`: move attempts on
result and summary both rc 128 while prepared, record `collected`, both refs at the candidate; `object_only_recovery`:
one `write_ref` with the all-zero expected value, `collect-finished`, `collected`; `object_only_recovery_conflict`:
`collect-reset-ready`, conflict preserved at the planted value.

## 4. Coverage-map spot checks

| Item | Result |
|---|---|
| 5.1 active-writer race / 7.5i | Timing 5/5 (`timing.out`); occupants at summary/result names during collect and recovery refused or left (`p9_u3`, T1 reruns); U1 closed at the next ID's names (`p9_u1`). |
| 5.2 ignored work | `lifecycle.py:1216-1219`, `:1303-1314` (first refusal names count and sample; re-authorization re-asks); suite `test_discard_ignored` 15, `test_quarantine` 35. |
| 5.3 unchecked deletion | Quarantine, fingerprint recheck, preserved-on-change, result preservation at resume/re-authorization (`worker.py:394-566`); `p9_u2` victim discard → `quarantine-preserved` → `abandon-finished` after the occupant is gone; hardening `discard_crash_matrix`, `late_commit_crashed_discard` PASS ×2. |
| 5.4 branch ownership | Create-only allocation refuses every occupant probed (`p9_u1` 8 rows, `p9_adj` cycle/abs: 0 consumed); prepared-transaction raw check `repository.py:852-879`; cleanup retains a foreign name/owner (`worker.py:1123-1170`). |
| 5.5 changed published recovery | `recovery.py:217-250`; `p9_u3` rows promote the untouched interrupted spawn only after the occupant is gone; suite `test_worktree` 27, `test_parent_interruption` 6. |
| 5.6 installer root | `sh -n install.sh` OK; `test_installer` 25 in the suite; not hand-probed. |
| 5.7 / 5.8 remotes and config | `_canonicalize_remote_url` (`repository.py:140-148`), `ConfigOccurrence(value=None)` (`:44-48`, `:93-106`); `test_repository` 8. |
| 5.9 Git sanitation | `core.py:53-86`, `:298-307` (every `GIT_*` stripped except six identity names; `SSH_ASKPASS` stripped; custom `CLONEGROWN_GIT` goes through the same runner — `p9_u2`/`p9_forms` logged it); hardening `git_environment_sanitized` PASS ×2; `test_core` 14. `pA_env` not rerun. |
| 5.10 secret-bearing errors | `core.py:181-232`, `:253-295` (argv/stdout/stderr redaction, URL userinfo, custody tokens); `test_core`, `test_safety_errors` 19. `pE_spot` not rerun. |
| 5.11 stale request reuse | `worker.py:713-761` (field-by-field index validation, settled authentication); `test_allocation` 19; hardening `request_parameter_mismatch`, `same_request_concurrent` PASS ×2. |
| 5.12 incomplete status | 29 codes in ARCHITECTURE.md = 29 emitted (`p9_forms`); no false codes with packed refs (`p9_u3`, U3 closed); every documented recovery action exists. |
| 5.13 create-only allocation | `worker.py:660-710`, `:774-910`; 8 + 4 + 2 occupant rows consume nothing at the base-pin/task-branch names; the post-allocation gap is documented (I-3); suite `test_locked_reconciliation_rejects_next_id_rollback_before_gap_reuse`. |
| 5.14 API/CLI parity | `lifecycle.py:419-421` (`strong=False`, `mode="clone"`), `cli.py:222-224`; `test_api` 6. |
| 5.15 invalid generated branch | `worker.py:764-771` (`check-ref-format --branch` before allocation); `test_api`. |
| 5.16 low-level errors | Five-part context (`core.py:97-128`) on every refusal quoted in `p9_u1`/`p9_u2`/`p9_u3` ("… failed during <stage>. Durable state: … Cause: …"). |
| 5.17 timing gate | `grep ratio tests/campaign/hardening_suite.py` matches only the word inside `operation`; `parallel_spawns_unique` PASS in both modes. |
| 5.18 one-shot | `lifecycle.py:1198-1199` (`--abandon` refused for collected), `:954-957` (`claim` only `ready`); `test_lease` 10; `p9_u3` `discard 1` of a collected worker rc 0 only with a preserved result. |
| Comment/public overclaims | Notices require a fresh review and hosted CI (true); I-1 miscounts the reviews; F4 phrases absent; every occupant/packed/allocation/rollback sentence at ARCHITECTURE.md:739-795 matched observation. |
| `CWSError`, heartbeat, failpoints | `grep -rn CWSError clonegrown/` empty; `heartbeat` only as a hidden bookkeeping key (`cli.py:31`); `failpoint` gated on `CLONEGROWN_TEST_MODE == "1"` (`core.py:485`). |
| retention, teardown, license, package | `pyproject.toml`: `license = "Apache-2.0"`, `license-files`, `requires-python >=3.11`, dynamic version `0.1.0a1`; wheel/sdist from the rsync copy (section 5); `licenses/LICENSE` identical (`cfc7749b…`); result refs and records survive every normal discard (`p9_u3` worker 4 `discarded` keeps its packed result; `after_removal summary_1: true`). |
| macOS, Python/Git versions, filters/LFS, resource boundaries, repository diversity, repeated verification, auxiliary-ref cost | Not freshly exercised (section 6); `test_filters_and_resources` 4, `test_auxiliary_refs` 4, `test_campaign_records` 16, `test_lease` 10 pass in the suite. |

## 5. Gate results

- **Unit suite:** `cd /home/serrecchia/Projects/clonegrown && python3 -m unittest discover -s tests -v` (in the checkout,
  no cache prefix) → **Ran 294 tests in 385.023 s, OK** (294 `ok`, 0 failures, 0 errors, 0 skipped); wall 385 s;
  log `/tmp/clonegrown-review9-unittest.log`. Per module: quarantine 35, audit 32, worktree 27, installer 25,
  allocation 19, safety_errors 19, campaign_records 16, discard_ignored 15, core 14, state 12, lease 10, repository 8,
  api 6, cli 6, parent_interruption 6, auxiliary_refs 4, collect_policy 4, filters_and_resources 4,
  package_metadata 2 (264 attributable by the regex; the remaining 30 have wrapped names; the total is Python's own
  count). The suite ran concurrently with the two hardening modes (separate roots).
- **Hardening, clone mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`: "git lacks reftable
  support"), **0 failed**; sum of case seconds 80.9; wall 87 s; `generated` 1788428661.6;
  `sha256 dbdd5b43190a564f1349046be04bd2e1fc50c05235c44ffc01c56b3233d24d71 /tmp/clonegrown-review9-hardening-clone.json`
  (log `/tmp/clonegrown-review9-hardening-clone.log`, exit 0).
- **Hardening, worktree mode:** 57 defined, **56 passed, 1 skipped** (`reftable_repository`), **0 failed**; sum of case
  seconds 84.8; wall 91 s; `generated` 1788428752.3;
  `sha256 c50cbba702b312b0204ca23399d1bc2e30fa624e268cfcd70651952459eb63b4 /tmp/clonegrown-review9-hardening-worktree.json`
  (log `/tmp/clonegrown-review9-hardening-worktree.log`, exit 0).
- `git diff --check` clean; `sh -n install.sh` OK; `python3 -m compileall -q clonegrown tests` OK with
  `PYTHONPYCACHEPREFIX=/tmp/clonegrown-review9-pyc`; wheel and sdist built with `python -m build` in a venv on the rsync
  copy `/tmp/clonegrown-review9-build/src` (`.git`, `__pycache__` and every `.env` pattern excluded):
  `clonegrown-0.1.0a1-py3-none-any.whl` 102,935 bytes sha256
  `a3d529e99709d0e94a7537ff7dc796cda3a3114d1daf82246f4a4fdee32753b0`, `clonegrown-0.1.0a1.tar.gz` 206,536 bytes sha256
  `ede694ba5dab26006842a60f3bdbc326dfbabea8a893279a76eb7b37cf592e5a`; `License-Expression: Apache-2.0`, `Requires-Python:
  >=3.11`, MacOS and POSIX::Linux classifiers, `licenses/LICENSE` in the wheel identical to the checkout's
  (`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`); isolated install in a second venv:
  `clonegrown --version` and `python -m clonegrown --version` both print `clonegrown 0.1.0a1`. No `build/`, `dist/` or
  `egg-info` in the checkout after the run.
- Residue greps: `CWSError` absent from `clonegrown/`; `heartbeat` only as a hidden bookkeeping key (`cli.py:31`);
  `failpoint` gated on `CLONEGROWN_TEST_MODE == "1"` (`core.py:485`); `ratio` in `hardening_suite.py` matches only the
  word inside `operation`.
- Versions: CPython 3.12.3, Git 2.43.0 (`/usr/bin/git`), Linux 6.17.0-35-generic.
- Tree fingerprints: start `ec3791390347a7ac4f7a9c385236d8cbcf07c5a3157b9d9bf12bc48521e7d935`, end `eb760ece49025c57669cba9018c81f40ee5c48d90d59d31f3d40ec1ce634a174` (PLAN.md/HANDOFF.md rewritten by another session; product unchanged, see the fingerprint paragraph);
  `git status --short` 23 entries at both ends.
- Blocked-process cleanup: `kill_blocked.sh` killed 18 Git/probe processes left blocked on planted FIFOs under the review
  roots (`kill_blocked.out`), a second pass killed 0, and the two `git-upload-pack` children of the killed `n3`/`p_alloc2`
  clone attempts were killed by hand; the final check found no Git process of this user under any review9 root.

## 6. Not verified, and why

- Hosted CI on a pushed revision, macOS, CPython 3.11, exact Git 2.29.0: not available locally; the tree is uncommitted.
  In particular, Git 2.43's `for-each-ref` skips a plain FIFO leaf (`rawgit9.sh` a) because its loose-ref directory
  scan handles only regular files and directories; `raw_ref_inventory` relies on that (it skips Git's enumeration
  only for a *symbolic* chain that ends foreign). Whether Git 2.29's scan also skips non-regular entries was not
  checked on that version; the `minimum-git` CI job is the place that answers it. If 2.29 opened such a leaf, the
  affected case would be a plain FIFO planted directly at a loose name inside `refs/cws/<ws>/` with the audit's
  enumeration still running (Clonegrown's own reads never open it).
- reftable repositories and `GIT_REF_FORMAT` end to end: Git 2.43 cannot create them (hardening skip); the
  `inventory is None` fallbacks were read, not exercised.
- Random-kill and state-machine campaign seeds, `real_repository_qualification.py`, and the benchmark harnesses: not in
  the requested gate list and not run.
- A socket occupant (a FIFO proves the class); admin-directory files other than `HEAD` and `gitdir` are the worker's
  private Git directory (I-2, I-5).
- **Earlier reviews' probes only partly rerun.** `rerun_all9.sh` (44 probes, path-rewritten copies) completed
  `n1_symref_namespace`, `n2_detached_head`, `n8_container_breaks`, `n1b_attribution`, `n4_admin`, `n5_container`,
  `n3_unowned_boundary`, `p_alloc2` (all rc 0; `rerun_all9.log`) and was stopped during `p_t2` when the coordinator asked
  for finalisation. Not rerun: `p_t2`, `p_t2b`, `p_gitdir2`, `p_testgap`, `pA_env`, `pB_reauth`, `pC_namespace`,
  `pD_classes`, `pE_spot`, `p1_ancestry`, `p1b_forged_recovery`, `p1g`, `p3e`, `p4_spot`, `p6_recover_occupants`,
  `p2b_clone_direct`, `q1_r1`, `q3_attribution`, `p2_occupants`, `m4_issue_codes`, `m8_quarantine_result`,
  `m3_containers`, `m6_interrupted_worktree`, `m2_cross_worker`, `r2d`, `r3b`, `r4_misc`, `r2e`, `r2e2`, `r2_s2`,
  `r2b_s2_rest`, `r1_s1`, `r3_codes`, `n6_s5_adjacent`, `n7_broken_audit`. For those classes the evidence is the code
  reading in section 3, the 294-test suite and both hardening modes on this exact tree, and the fact that six of the
  eight product modules are byte-identical to the tree on which the tenth review reran every one of them clean (only
  `repository.py` and `worker.py` changed, in the three functions verified under U1–U3). The tenth review's
  `p_alloc.py`/`p_gitdir.py`/`p_packed.py` are superseded by `p9_u1`/`p9_u2`/`p9_u3`, which cover their rows and more.
- Genuine disk/inode exhaustion, network filesystems, Git LFS, native Windows: stated boundaries, not exercised.
- `HANDOFF.md` and the Step 7.5a–7.5ae completion records: deliberately not read.

Probe inventory: `/tmp/clonegrown-review9-probes/{h9,p9_u1,p9_u2,p9_u3,p9_adj,p9_forms,cmp9}.py`, `rawgit9.sh`,
`gitlog.sh`, `kill_blocked.sh`, with outputs `p9_u1.out`, `p9_u2.out` (+ `p9_u2_gitlog.txt`), `p9_u3.out`, `p9_adj.out`,
`p9_forms.out` (+ `p9_forms_gitlog.txt`), `rawgit9.out`, `timing.out`, `kill_blocked.out`; path-rewritten copies of the
second through tenth reviews' probes under `/tmp/clonegrown-review9-rerun/r<N>-probes/` with reruns
`/tmp/clonegrown-review9-rerun/out/rerun-*.out` (`rerun_all9.sh`, log `rerun_all9.log`); disposable repositories under
`/tmp/clonegrown-review9-work/` and `/tmp/clonegrown-review9-rerun/r<N>-work/`; suite log
`/tmp/clonegrown-review9-unittest.log`; hardening logs and JSON `/tmp/clonegrown-review9-hardening-*`; wheel, sdist and
venvs under `/tmp/clonegrown-review9-build/`.
