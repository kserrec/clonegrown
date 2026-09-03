# Reproduction notes

This repository contains two different kinds of evidence:

1. **Preserved historical evidence** from the original falsification and
   hardening campaign.
2. **Current harnesses** that exercise the current `clonegrown` package.

Those are not interchangeable. The current harnesses can test the current
checkout, but they cannot recreate the historical `RESULTS.json` byte for byte
because the frozen candidate and several campaign inputs are absent.

[`PLAN-ARCHIVE.md`](PLAN-ARCHIVE.md) separately preserves the dated
implementation and review
transcript moved from the active roadmap. It is provenance, not an additional
evidence set or normative product documentation.

## Preserved historical evidence

- `REPORT.md` is the narrative adversarial evidence report.
- `RESULTS.json` is the recovered consolidated machine-readable result set for
  the frozen `cws.py` candidate identified in `REPORT.md`.
- `FALSIFICATION.md` is the earlier independent-clone-versus-worktree
  falsification report.

The preserved recovered files have these SHA-256 digests:

```text
be38e48911d5a7fc2096b23bee251a05b286ebd9288c43c87bb10687db6cd17c  RESULTS.json
51e1b2d6ca4aa12280febefae5c53865a6b1389adc86394dfba84a200446baff  FALSIFICATION.md
```

`REPORT.md` identifies its absent `cws.py` candidate at source commit
`be4391c` and records Linux 6.18.35 x86_64, Git 2.47.3, and Python 3.13.5.
`FALSIFICATION.md` records Git 2.47.3 but does not preserve its exact source
revision, operating system, or Python version. Those omissions are part of the
historical record; do not infer or reconstruct the missing provenance.

## Requirements for current checks

Run commands from the repository root on Linux or macOS with Git 2.29.0 or
newer and Python 3.11 or newer. Native Windows is explicitly unsupported in
0.x: the implementation imports `fcntl` and its POSIX lock, rename, and
deletion results do not transfer to Windows.

The blocking `ci.yml` endpoint matrix is configured to run the complete unit
suite, including the destructive installer and lifecycle modules, on both
`ubuntu-latest` and `macos-latest` with Python 3.11 and setup-python's `3.x`
selector. That selector means the latest stable Python 3 release at job
execution time; it was Python 3.14.7 when this boundary was established on
2026-08-29.

The separate `minimum-git` job fixes the Git endpoint rather than inheriting a
mutable runner version. It downloads `git-2.29.0.tar.xz` from kernel.org,
checks the archive against the published SHA-256 digest
`28432d995257c4626fe0fb2091f588df6eed98e9571419e72c83bc23372e6b89`,
builds it without the optional libcurl HTTP transport, OpenSSL, gettext, or
Tcl/Tk components,
and selects that exact binary through both `PATH` and `CLONEGROWN_GIT` for the
full unit suite and both hardening modes. Those omitted build components are
not used by Clonegrown's local clone, local fetch, ref, config, worktree, or
status commands.

Git 2.29.0 is the derived floor because Clonegrown directly requires
`fetch --no-write-fetch-head` and `worktree repair`, both added in Git 2.29.
The `worktree list --porcelain -z` optimization is not part of the floor: the
implementation detects its rejection and retries the older porcelain form.
Git 2.29 also requires Clonegrown to copy worktree-local sparse-checkout flags
explicitly before checking out a linked worker; the exact-minimum worktree
campaign covers both included and excluded paths.

The harnesses write the original prototype's positional command form;
`tests/campaign/legacy_cli.py` translates it onto the installed `clonegrown` CLI, so
they exercise the code users run. They do **not** invoke the absent frozen
`cws.py` candidate.

## Recorded current-package evidence

The latest full local result was produced on 2026-08-29 from the uncommitted
Phase 6 package tree based on commit
`354d16bc662f15f65dded911d3c26729bf5804aa`. On Linux with CPython 3.12.3,
the full suite passed 226/226 with Git 2.43.0 and 226/226 with exact Git
2.29.0. Clone and worktree hardening each reported 57 defined cases, 56
exercised passes, one conditional reftable skip, and zero failures.
`PLAN-ARCHIVE.md` and `HANDOFF.md` preserve the exact local-diff boundary,
durations, and result hashes; `../PLAN.md` retains the current release
boundary. Because the tree was uncommitted and generated outputs remained under
`/tmp`, these commands can produce new current-package evidence but cannot
reconstruct the old output byte-for-byte.

The latest hosted blocking evidence before the local Phase 6–7 tree is GitHub
Actions run 33278590221 at committed revision
`354d16bc662f15f65dded911d3c26729bf5804aa`. All seven jobs passed:
Ubuntu/macOS, Python 3.11/latest stable, exact Git 2.29.0, and both hardening
modes. That commit changes only Phase 5 completion records from the earlier
`a2ae7793` executable tree. Scheduled randomized run 33638194991 is the latest
hosted randomized result observed before final qualification and passed at the
same revision. Neither result includes the uncommitted Phase 6–7 tree; its own
pushed-SHA runs are required before release completion.

## Current fresh-agent orchestration simulation

[`ORCHESTRATOR_SIMULATION.md`](ORCHESTRATOR_SIMULATION.md) preserves the
complete Phase 7 Step 7.3 prompt boundary, fresh-agent report, exact public
outputs, and coordinating-session checks. On 2026-09-02, the current
uncommitted tree was snapshotted outside the checkout, installed with CPython
3.12.3, and paired with a disposable canonical repository. The agent read only
the installed `SKILL.md` for Clonegrown guidance.

The agent initialized one workspace; spawned, committed, collected, separately
integrated, released, and discarded three independent workers; exercised a
ready-state release/claim handoff; then SIGKILLed only Clonegrown's parent
during a filter-blocked fourth spawn. Recovery returned `spawn-cleaned`, final
status reported no issues, and every retained result ref remained resolvable.
No human workflow correction or product/skill defect was observed.

This is one qualitative run, not a timing benchmark or paired comparison. Its
temporary repository and process IDs are not stable reproduction inputs, and
it does not establish that Clonegrown reduces agent mistakes or human
intervention relative to ordinary worktrees.

## Current deterministic checks

Run one named adversarial case:

```bash
python3 tests/campaign/hardening_suite.py --one exact_base_dirty
```

Names are defined by `TESTS` in `tests/campaign/hardening_suite.py`. Run the whole
current suite while keeping its consolidated output outside the checkout:

```bash
CWS_RESULTS_PATH=/tmp/clonegrown-hardening-results.json python3 tests/campaign/hardening_suite.py
```

The same suite runs against worktree workers (every harness below accepts the
same variable):

```bash
CWS_SUITE_MODE=worktree CWS_RESULTS_PATH=/tmp/clonegrown-hardening-worktree.json python3 tests/campaign/hardening_suite.py
```

The consolidated JSON distinguishes `passed`, `skipped`, and `failed`.
`total` is the number of defined cases, not the number exercised. In the
2026-08-29 local result identified above, Git 2.43.0 reported 57 total, 56
passed, one conditional reftable skip, and zero failed in each mode; a missing
optional repository format is never counted as a pass.

Blocking CI disables hardening-matrix fail-fast and configures each mode's
structured JSON upload with `if: always()` and `if-no-files-found: error`; job
cancellation or runner loss can still prevent that step from completing. A
hardening child that emits success JSON but exits nonzero is recorded as failed.

Run the current unit tests:

```bash
python3 -m unittest discover -s tests -v
```

Run the real parent/child interruption cases:

```bash
python3 -m unittest discover -s tests -p 'test_parent_interruption.py' -v
```

These six cases pause one configured Git child, send `SIGKILL` only to its
Python parent, prove the Git child remains alive, let that child finish, and
track its exit. Before invoking recovery they inspect the durable worker record
and the relevant staged/final paths, worktree administration directory, task
branch, ownership ref, transferred candidate object, candidate ref, or result
ref. The collection-fetch case proves that the child can finish with the exact
object present and its destination ref still absent, after which recovery
publishes through an absent-ref compare-and-swap. The cases also cover worktree
add before its administration path is persisted, clone provisioning,
published and quarantined worktree repair, and branch cleanup. They create only
temporary fixtures and retain no generated output in the checkout.

Run the filter and resource-boundary cases:

```bash
python3 -m unittest discover -s tests -p 'test_filters_and_resources.py' -v
```

The filter case creates an actual repository-local required clean/smudge
driver outside the canonical checkout and completes spawn, edit, add, commit,
collect, release, and discard in both clone and worktree modes. The resource
cases inject `ENOSPC` before atomic record publication, `EXDEV` at the
slot-to-quarantine rename, and `EIO` after one file has been removed from an
authorized recursive deletion. All fixtures stay in temporary directories.

These are targeted equivalents, not claims about actual capacity exhaustion or
filesystem durability. Genuine disk/inode exhaustion and network or
distributed filesystems remain unsupported until exercised on those systems.
Git LFS also remains unsupported: the project does not require or install
`git-lfs`, and no stand-in filter is treated as LFS evidence. Long-running
filter-process, delayed checkout, credential, and remote object-transfer
behavior is outside the clean/smudge fixture.

## Current real-repository qualification

`tests/campaign/real_repository_qualification.py` runs the same bounded
lifecycle/recovery scenario in clone and worktree modes against three pinned
public-source profiles: curl history at
`8a2bb9ca241bbd82a0da536f6f39dca9037dd046`, Git's refs at
`c73e85354c275c9d409b26445089bc16940fc527`, and a second checkout of that Git
commit narrowed to `Documentation`, `.gitmodules`, and its
`sha1collisiondetection` gitlink. Every scenario interrupts spawn after
publication, recovers it, commits and collects work, releases and discards the
worker, then proves the immutable result ref survived and the workspace audit
and connectivity check are clean.

Run the complete six-scenario matrix with generated output outside the
checkout:

```bash
python3 -B tests/campaign/real_repository_qualification.py --output /tmp/clonegrown-real-repository-qualification.json
```

The harness starts each public source clone with `--no-checkout`. Before any
checkout it applies sparse exclusions for `.env`, `*.env`, `.env.*`, and
`*.env.*` at every depth; it never searches for, lists, opens, or reads an
excluded file and never initializes the public submodule. Successful runs
remove their disposable `/tmp` root. Failed runs retain it and print its exact
path.

This command requires GitHub network access and enough temporary storage for
two full public clones plus worker copies. The recorded run held 477,078 KiB
of packed source objects before worktrees and workers. It adds no package: the
harness uses the Python standard library and the existing Git executable.

The preserved 2026-08-29 run is
`research/REAL_REPOSITORY_QUALIFICATION.json`; its interpretation, exact
versions, source and result commits, and limitations are in
`research/REAL_REPOSITORY_QUALIFICATION.md`. This is bounded qualification
evidence, not a performance gate or evidence that coding agents make fewer
mistakes.

Run the focused lease and discard boundary matrices in both worker modes while
keeping their fixture roots outside the checkout:

```bash
CWS_TEST_ROOT=/tmp/clonegrown-lease-clone CWS_SUITE_MODE=clone python3 tests/campaign/hardening_suite.py --one lease_crash_matrix
CWS_TEST_ROOT=/tmp/clonegrown-lease-worktree CWS_SUITE_MODE=worktree python3 tests/campaign/hardening_suite.py --one lease_crash_matrix
CWS_TEST_ROOT=/tmp/clonegrown-discard-clone CWS_SUITE_MODE=clone python3 tests/campaign/hardening_suite.py --one discard_crash_matrix
CWS_TEST_ROOT=/tmp/clonegrown-discard-worktree CWS_SUITE_MODE=worktree python3 tests/campaign/hardening_suite.py --one discard_crash_matrix
```

## Current crash and generated campaigns

The random-kill campaigns create temporary repositories, kill only the child
processes they launch, and write their requested result files under `/tmp`:

```bash
python3 tests/campaign/random_kill.py spawn --start 0 --count 1 --output /tmp/clonegrown-kill-spawn.json
python3 tests/campaign/random_kill.py collect --start 0 --count 1 --output /tmp/clonegrown-kill-collect.json
python3 tests/campaign/random_kill.py discard --start 0 --count 1 --output /tmp/clonegrown-kill-discard.json
```

The former one-row `run_crash_case.py` wrapper was removed after its collect
and discard cases became strict subsets of the deterministic hardening
matrices above. Its generated JSONL was never preserved historical evidence.

## Current auxiliary-ref policy benchmark

`tests/campaign/auxiliary_ref_benchmark.py` creates a synthetic canonical
repository carrying all three promised auxiliary namespaces together. Its
default fixture has 4,096 remote-tracking refs, 256 notes refs, and 256 replace
refs. Every sample uses a fresh canonical/workspace pair; current clone,
the retained Step 6.4 candidate simulation, and worktree-control order rotates
by sample. It measures:

- the current clone implementation, which enumerates exact canonical
  name/object-ID pairs, supplies those refspecs to one `git fetch --stdin`, and
  packs the staged clone immediately afterward;
- a benchmark-only simulation that submits all nonempty namespace refspecs in
  one fetch and then runs `git pack-refs --all` (intentionally the same policy,
  retained so the Step 6.5 acceptance rerun used the unchanged harness); and
- the current worktree control, which shares canonical's refs and must not be
  packed by Clonegrown.

Each path records spawn time, total and per-class ref counts, loose/packed ref
counts, and logical/allocated Git-directory storage. The product enumeration
is the snapshot boundary: a ref added or moved afterward cannot change the
explicit object-ID refspecs, and an object that cannot be fetched makes spawn
fail rather than producing a ready record with mismatched counts. A sample is
valid only if every canonical name retains its resolved object ID, clone
metadata reports the exact canonical per-class counts, offline remote
comparison/notes/replace behavior passes with the canonical path temporarily
unavailable, and packed clone remote/notes/replace refs can be deleted and
restored. A canonical symbolic remote-tracking ref is checked by name and
resolved tip; symbolic form is not part of the contract. Timing remains
observational and never controls the harness exit status.

Run the exact five-sample measurement with output outside the checkout:

```bash
python3 -B tests/campaign/auxiliary_ref_benchmark.py --samples 5 --remote-refs 4096 --notes-refs 256 --replace-refs 256 --output /tmp/clonegrown-auxiliary-refs.json
```

Run the focused command-shape and real-Git contract matrix:

```bash
PYTHONPYCACHEPREFIX=/tmp/clonegrown-auxiliary-pycache python3 -m unittest discover -s tests -p 'test_auxiliary_refs.py' -v
```

The simulation patches only the benchmark process's call boundary; it does
not alter `clonegrown/` product code. The harness uses the Python standard
library and existing Git executable, creates no external account or network
traffic, explicitly excludes every dotenv filename pattern from recursive
storage accounting, and deletes successful fixtures. The measured policy and
completed one-time Step 6.5 acceptance decision are recorded in
`PLAN-ARCHIVE.md`.
Timing remains descriptive and is not a continuing test or CI gate.

## Current scaling probe

This observational probe accepts an output path, so its result can stay
outside the checkout:

```bash
python3 tests/campaign/scaling_v2.py tiny --workers 4 --output /tmp/clonegrown-scale-tiny.json
```

The old single-sample `concurrency_v2.py` probe was removed after deterministic
allocation integrity moved to `hardening_suite.py` and timing moved to the
multi-sample benchmark below.

## Current spawn concurrency benchmark

`tests/campaign/spawn_benchmark.py` keeps performance measurements separate
from the deterministic hardening result. It creates a fresh fixture for every
sample, measures single and eight-way parallel spawn in one worker mode, and
reports every raw sample plus the median, median absolute deviation, minimum,
and maximum for single time, parallel time, and their ratio. No timing value or
ratio changes the command's exit status; setup, command, JSON, or worker-ID
integrity failures still make the measurement invalid and return nonzero.

Run the same five-sample measurements used by the informational GitHub Actions
workflow, keeping both JSON files outside the checkout:

```bash
python3 tests/campaign/spawn_benchmark.py --mode clone --samples 5 --parallelism 8 --output /tmp/clonegrown-spawn-benchmark-clone.json
python3 tests/campaign/spawn_benchmark.py --mode worktree --samples 5 --parallelism 8 --output /tmp/clonegrown-spawn-benchmark-worktree.json
```

`.github/workflows/spawn-benchmark.yml` runs those measurements weekly and on
manual dispatch. It has no push or pull-request trigger, so benchmark timing is
not a required correctness check. The raw JSON and summaries appear in each
job's log; the workflow does not commit generated output.

The allocation module also pins the narrower canonical-verification boundary:
each successful clone or worktree spawn performs four full verifications, one
immediately before each of the allocation, cloning, configuring, and
publishing lock transactions. Locked reconciliation then permits only the
serialized workspace-counter change and rematches repository directory and
marker identity before mutation; the final transaction reuses its verified
value for ready-state cleanup. The tests replace canonical both between spawn
transactions and between verification and lock acquisition, and require
refusal before unsafe publication or allocation:

```bash
python3 -m unittest discover -s tests -p 'test_allocation.py' -v
```

The Step 6.2 five-fixture diagnostic recorded in `PLAN-ARCHIVE.md` counted
exact Git
argument vectors before and after the change. Its timing distributions are
observations, not a threshold or a performance guarantee; the benchmark above
remains the reproducible multi-sample timing tool.

Step 6.3 measured the held and waiting time of every spawn workspace-lock
phase across five fresh single-spawn and five fresh eight-way fixtures per
worker mode. Its before/after raw distributions remained under `/tmp`; the
durable medians and limitations are recorded in `PLAN-ARCHIVE.md`. Timing did
not
decide correctness. The unchanged hardening cases below remain the allocation
and request-index race gates:

```bash
CWS_SUITE_MODE=clone python3 tests/campaign/hardening_suite.py --one parallel_spawns_unique
CWS_SUITE_MODE=clone python3 tests/campaign/hardening_suite.py --one same_request_concurrent
CWS_SUITE_MODE=worktree python3 tests/campaign/hardening_suite.py --one parallel_spawns_unique
CWS_SUITE_MODE=worktree python3 tests/campaign/hardening_suite.py --one same_request_concurrent
```

The retained present-day Git garbage-collection comparison is runnable, but it
writes a fixed JSON file inside `tests/campaign/`:

```bash
python3 tests/campaign/gc_compare.py
```

Its generated file, `tests/campaign/gc-concurrency.json`, is current
experimental output, not a replacement for `research/RESULTS.json`. The old
shared-state probe was removed after the clone/worktree config, stash, remote,
and branch behaviors were pinned by deterministic hardening. The file-size
limit I/O probe was removed after deterministic atomic-write,
quarantine-rename, and partial-deletion tests became the supported recovery
evidence; neither the old probe nor those targeted injections establish
support for genuine disk or inode exhaustion.

## State-machine fuzzer

`tests/campaign/state_machine_fuzz.py` originally imported the frozen `cws` module. It
now drives the current package's Python API directly, so it is a current
experiment, not a rerun of the historical campaign:

```bash
CWS_FUZZ_ROOT=/tmp/clonegrown-fuzz python3 tests/campaign/state_machine_fuzz.py --start 0 --seeds 1 --steps 50 --output /tmp/clonegrown-fuzz.json
```

## Scheduled randomized campaigns and replay

`.github/workflows/randomized-campaigns.yml` runs nightly at 09:37 UTC and by
manual dispatch. It has no push or pull-request trigger. Its six random-kill
jobs cover spawn, collect, and discard in clone and worktree modes; two more
jobs run the state-machine fuzzer in both modes. Matrix fail-fast is disabled,
so one failure does not cancel evidence from the other jobs, but no campaign
uses `continue-on-error`: a failed campaign leaves its job failed.

A scheduled run uses its GitHub Actions run number as the first seed. A manual
run accepts a literal first seed and bounded choices only: 1, 2, 3, or 5 seeds
per case and 25, 50, 75, or 100 state-machine steps per seed. The nightly
defaults are two seeds per job and 50 state-machine steps. Every job has a
45-minute timeout. Checkout and Python setup each have five minutes, campaign
execution has 25 minutes, and the always-run artifact upload has five minutes.
Those step limits total 40 minutes and leave five minutes for between-step
overhead. Upload remains best-effort if GitHub cancels the job or loses the
runner; the workflow does not claim that any timeout can guarantee retention
after runner loss.

Each result JSON records the campaign and worker mode, requested seed range,
Python implementation/version/build, selected Git executable and version,
platform, checked-out commit SHA, selected non-secret GitHub run identifiers,
and one `replay_command` per requested seed. Before the first seed begins, the
harness atomically writes those replay rows with `pending` status; it replaces
the artifact after each result and reports executed, pending, passed, and
failed counts. Abrupt termination therefore leaves the last complete JSON
rather than no replay data or a partial document. A random-kill result can pass
only when its target was actually killed by `SIGKILL`. Artifacts are named
with job coordinates, run ID, and run attempt; they are uploaded even after a
campaign failure and retained for 30 days. Fixtures and result files live
under runner-temporary storage, so the workflow never writes generated output
into the checkout.

To replay a result, check out the recorded `environment.commit_sha`, run from
the repository root, select the recorded Git executable—or set
`CLONEGROWN_GIT` to an executable with the recorded `git_version`—and execute
that row's `replay_command` exactly. The campaign fixture and Clonegrown then
use the same selected Git. The command always narrows the run to one worker
mode, one seed, one operation when applicable, and the recorded state-machine
step count. For example, these are complete one-seed replay commands:

```bash
CWS_SUITE_MODE=clone python3 tests/campaign/random_kill.py spawn --start 42 --count 1 --output /tmp/clonegrown-random-kill-clone-spawn-42.json
CWS_FUZZ_ROOT=/tmp/clonegrown-state-machine-worktree-42 CWS_SUITE_MODE=worktree python3 tests/campaign/state_machine_fuzz.py --start 42 --seeds 1 --steps 50 --output /tmp/clonegrown-state-machine-worktree-42.json
```

## Missing historical inputs

The following artifacts named by the original report or earlier reproduction
guide are not in this repository:

- the frozen `cws.py` candidate;
- `run_one.py` (the current deterministic suite instead supports `--one`);
- `manyrefs_v2.py`;
- `partial_clone_probe.py`;
- `narrow_clone_probe.py`;
- `ref_compaction_probe.py`;
- `self_host_probe.py`;
- `consolidate_results.py`;
- the original `hardening-results.jsonl` and `crash-results.jsonl` inputs.

Because `consolidate_results.py` and its raw inputs are missing, there is no
honest command in this checkout for rebuilding the preserved historical
`RESULTS.json`. That file should be treated as a recovered research artifact;
current reruns should be stored separately and compared explicitly.
