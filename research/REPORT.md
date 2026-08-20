# Independent Clone Workspaces for Coding Agents

## Adversarial evidence report

**Candidate:** `cws.py`  
**Candidate SHA-256:** `e7e9a8ef8cc17cbb590a73aeab4147b1c99d46c4ed503bfd18cdd1b5f736f852`  
**Last source change:** Git commit `be4391c`  
**Environment:** Linux 6.18.35 x86_64, Git 2.47.3, Python 3.13.5  
**Status:** Experimental reference implementation, not production software

## Bottom line

The experiment supports this claim:

> A transactional independent-clone protocol can provide a robust, agent-friendly isolation boundary for ordinary Git operations, with reliable commit collection and crash recovery.

It does **not** support this stronger claim:

> Independent clones are simply better than worktrees for most workflows.

The trade is real and sharp:

- **Worktrees are dramatically faster and more storage-efficient**, especially when workers are short-lived or full physical object isolation is requested.
- **Independent clones remove shared mutable Git state**, so one agent's config changes, remote deletion, stash operations, branch deletion, repository maintenance, or damaged worker metadata do not naturally affect another worker or canonical repository.
- A hardened clone workflow requires a real transactional helper. It is no longer credible as “just teach the agent to run `git clone`.” The frozen helper is 1,389 lines and 67,430 bytes, excluding tests.
- The decisive behavioral question remains unanswered: whether real coding agents make fewer workspace mistakes or require fewer human interventions under this protocol than under native worktrees. Neither Codex CLI nor Claude Code CLI was available in the test environment.

The evidence is strong enough to justify an **experimental alpha tool and real-agent A/B test**. It is not strong enough to market the approach as a general worktree replacement.

---

## What was built

The reference helper implements six commands:

```text
init      register canonical repository and workspace
spawn     create and publish an isolated worker clone
collect   preserve an exact committed worker result in canonical
recover   reconstruct interrupted operations from durable state
discard   safely remove a collected worker, or explicitly abandon one
status    inspect workers and detect drift/tampering
```

The protocol's important invariants are:

1. A worker starts from an explicitly resolved immutable base commit, not canonical `HEAD`.
2. Worker IDs and branch namespaces are unique, including across multiple workspaces using one canonical repository.
3. The local canonical source remote is non-pushable; real upstream remotes retain their names.
4. A stable request ID is idempotent only when task parameters match.
5. The helper refuses to collect detached-HEAD work, the wrong branch, dirty work, or unrelated rewritten history unless explicitly permitted.
6. Collection first fetches the exact candidate SHA into an immutable namespaced canonical ref.
7. The worker is rechecked after preservation so a commit made during collection is detected rather than silently omitted.
8. A collected worker that later changes cannot be deleted without an explicit force decision.
9. Worker paths, Git directories, identity markers, control files, lock files, metadata IDs, and branch names are validated rather than trusted from JSON.
10. Operations are recoverable across process death at every durable transition tested.
11. Strong mode uses `--no-hardlinks`; fast mode explicitly accepts shared object-file storage for speed and space efficiency.
12. Provisioning suppresses Git hooks and sanitizes ambient `GIT_*` variables.

This is materially more machinery than a skill file should implement in prose. A skill could decide **when** to request a workspace and how agents should use it; the helper must own allocation, identity, preservation, recovery, and deletion.

---

## Test summary

### Deterministic and adversarial tests

| Group | Passed | Tested | Examples |
|---|---:|---:|---|
| Core integrity | 17 | 17 | exact base, request reuse, wrong branch, dirty state, post-collection drift, repository replacement |
| Concurrency | 7 | 7 | parallel spawn, duplicate requests, collection/discard race, canonical advance, multiple workspaces, concurrent worker GC |
| Crash recovery | 5 | 5 | initialization, spawn, collection, discard, dirty-worker recovery |
| Compatibility | 14 | 14 | strong/fast object modes, alternates, SHA-256, reftable, shallow, sparse, submodules, symlinks, executable bits |
| Red-team | 13 | 13 | metadata-path tampering, symlink substitution, malformed metadata, Git-dir substitution, control-file attacks |
| **Total** | **56** | **56** | |

Collection and discard crash matrices were also executed as **11 individual failpoint cases** to avoid aggregate-runner timeout contamination. All 11 passed.

### Generated and noncooperative testing

| Campaign | Result |
|---|---:|
| Randomized state-machine seeds | 24 / 24 passed |
| Generated lifecycle operations | 1,000 |
| Random real-process SIGKILL during spawn | 10 / 10 recovered |
| Random real-process SIGKILL during collect | 10 / 10 recovered |
| Random real-process SIGKILL during discard | 5 / 5 recovered |
| Forced file-write failure during strong clone | recovered and retried safely |
| Self-host lifecycle | passed |
| Partial/promisor clone, fast and strong modes | passed |

The randomized model repeatedly mixed spawning, committing, dirtying, collection, abandonment, deletion, recovery, canonical advancement, duplicate requests, request mismatches, and worker config/remote/stash mutation. Invariants were checked after sequences with canonical `git fsck`, identity validation, ref validation, and deletion-state validation.

### Scientific provenance note

An early aggregate file, `hardening-results.json`, was interrupted by the execution environment and contains a stale partial failure. It is intentionally **not** used as the final source of truth. `RESULTS.json` consolidates the latest isolated result for every named test from `hardening-results.jsonl` and the separately executed crash rows from `crash-results.jsonl`.

---

## Failures the experiment found before hardening

The naive design did not survive adversarial testing. Important failures included:

### 1. Local canonical accidentally became `origin`

A worker created with an ordinary local clone could run a normal command such as:

```bash
git push origin agent/task
```

and push into the local canonical repository rather than the intended upstream. The hardened protocol renames the local source and assigns it a deliberately invalid push URL while preserving the canonical repository's real named remotes.

### 2. Workers could start from the wrong branch

Cloning whatever canonical had checked out could silently seed a worker from an accidental feature branch. The helper now resolves the requested base to an immutable SHA before worker creation and verifies the checkout exactly.

### 3. Duplicate request IDs could silently mean different work

The first prototype returned an existing worker when a request ID was reused, even if the task or base differed. The hardened helper hashes request parameters and rejects mismatched reuse.

### 4. The wrong committed work could be “successfully” collected

An agent could switch to another branch, commit valuable work there, leave the assigned task branch untouched, and submit. A naive collector would preserve the stale assigned branch and report success. The helper now validates symbolic `HEAD`, branch identity, cleanliness, ancestry policy, and a post-fetch snapshot.

### 5. Crash recovery confused abandonment with safe deletion

The initial state machine did not persist whether a deletion was an explicit abandonment or disposal of an already collected worker. A crash could reconstruct the wrong state. The transaction now persists deletion intent before filesystem mutation.

### 6. Metadata paths were dangerous to trust

Editing a worker metadata path could direct deletion or collection at an unrelated directory/repository. The helper now derives expected paths from workspace state, rejects mismatches and symlinks, validates Git directories, and uses per-repository identity markers.

### 7. Shared object files undermined “physical isolation”

Normal local clones may hardlink Git objects. Ordinary Git commands generally replace/unlink object files safely, but intentional in-place corruption of a shared pack can affect canonical. Strong mode eliminates hardlinks; fast mode states the weaker guarantee explicitly.

### 8. Naive numeric allocation raced

A “highest existing number plus one” allocator collided badly under concurrent spawn. Allocation is now serialized transactionally while expensive clone provisioning proceeds under a per-worker operation lock.

These failures justify the helper. They also disprove the idea that a copied skill file alone can safely implement the workflow.

---

## Direct isolation evidence

A canonical repository was prepared with:

- repo-local config `agent.sentinel=canonical`,
- an `origin` remote,
- a stash,
- a dormant local branch.

A worker then changed the config, removed `origin`, cleared its stash, and deleted its private copy of the dormant branch.

| Strategy | Canonical config changed | Canonical remote removed | Canonical stash cleared | Canonical dormant branch deleted |
|---|---:|---:|---:|---:|
| Worktree | Yes | Yes | Yes | Yes |
| Independent clone | No | No | No | No |

This does not mean worktrees are broken. Sharing those structures is their design. It does mean independent clones provide a materially different failure domain for autonomous workers.

### Repository maintenance contention

Eight workers simultaneously ran:

```bash
git gc --prune=now
```

| Strategy | Successes | Failures |
|---|---:|---:|
| Worktrees | 1 | 7 |
| Independent clones | 8 | 0 |

The worktree failures came from the shared repository's `gc.pid` and lock files. Independent clones did not contend because each worker owned its Git repository.

---

## Performance and storage results

All measurements are local and environment-specific. They establish order of magnitude, not universal constants.

### Worker creation

| Repository profile | Workers | Worktree | Fast clones | Strong clones |
|---|---:|---:|---:|---:|
| Tiny | 1 | 0.042 s | 1.730 s | 2.386 s |
| Tiny | 4 | 0.167 s | 7.109 s | 7.318 s |
| 6,000 files | 4 | 0.630 s | 8.033 s | 8.304 s |
| 16 MiB current binary tree | 4 | 0.282 s | 8.155 s | 9.227 s |
| 29.6 MiB history / 1 MiB checkout | 4 | 0.625 s | 8.052 s | 8.050 s |
| 16 concurrent workers | 16 | 0.552 s | 17.660 s | not measured |

For one tiny worker, fast clone provisioning was about **41× slower** than a worktree in this environment. For 16 concurrent workers, clone provisioning was about **32× slower** overall.

That is the strongest evidence against treating clones as a universal replacement. For tasks lasting minutes or hours, a two-second setup cost may be irrelevant. For hundreds of tiny workers lasting seconds, it is decisive.

### Additional disk consumed by four workers

| Repository profile | Worktrees | Fast clones | Strong clones |
|---|---:|---:|---:|
| Tiny | 3.56 MB | 4.42 MB | 4.55 MB |
| 6,000 files | 101.10 MB | 101.95 MB | 103.88 MB |
| 16 MiB current binary tree | 67.35 MB | 68.20 MB | 135.41 MB |
| 29.6 MiB history / 1 MiB checkout | 4.42 MB | 5.27 MB | 122.84 MB |

The important distinction is **what is large**:

- When checked-out files and dependencies dominate, fast clones and worktrees can consume nearly the same space.
- When Git history is large but the checkout is small, strong clones multiply that history per worker and become unattractive quickly.
- Fast mode remains close to worktree storage because local object files are shared, but it does not promise protection against deliberate in-place object corruption.

### Ref-heavy repositories: discovered bug and workaround

The frozen prototype initially materialized thousands of canonical remote-tracking refs as loose refs and reflogs. With 5,000 branch/ref pairs, one worker's `.git` directory grew to **41.48 MB**.

This looked like a clone dealbreaker. A follow-up falsification showed it is primarily an implementation flaw:

- A narrow local clone with 10,001 source refs used only **0.20 MB** of Git metadata and still fetched an exact base SHA successfully.
- Running `git pack-refs --all --prune` after the prototype's ref snapshot reduced the worker from **41.48 MB to 0.66 MB** in **0.56 seconds**, while preserving the tested remote ref.

Therefore:

> Ref-heavy repositories expose a serious flaw in the current prototype, but not a fundamental limitation of independent clones.

A real tool should avoid eagerly copying every remote-tracking ref, or compact them before publishing the worker.

---

## Compatibility evidence

The frozen candidate completed tested lifecycles for:

- SHA-1 and SHA-256 repositories,
- files and reftable ref storage,
- shallow repositories,
- partial/promisor clones with `blob:none`, including lazy retrieval of missing historical blobs,
- sparse checkout,
- canonical repositories using object alternates,
- multiple/remapped remotes and push URLs,
- detached canonical `HEAD`,
- repositories without an upstream remote,
- symlinks and executable bits,
- custom `info/exclude`,
- selected safe repo-local config,
- notes, replace refs, and remote-tracking refs.

### Qualified submodule result

The top-level gitlink was correct, but the submodule remained uninitialized. This is a policy decision the real tool cannot hide. It needs a bootstrap contract such as:

```text
spawn worker
→ run repository-defined bootstrap
→ only then declare application workspace ready
```

The same general issue applies to dependencies, generated code, local databases, and build caches.

---

## What the tests do not prove

### 1. Actual coding-agent behavior

No Codex or Claude CLI was installed. The central product hypothesis remains untested:

> Do real agents make fewer workspace mistakes, spend fewer tool calls/tokens on Git, and need fewer human interventions with isolated clones than with native worktrees?

This should be a paired A/B test using identical model versions, repository snapshots, prompts, and task sets.

### 2. Native Windows and macOS

Only Linux was tested. The candidate imports `fcntl`, so the current implementation is POSIX-only. That is a concrete release blocker for broad distribution, though not a conceptual blocker. Windows needs a tested cross-platform locking implementation and path/filesystem-specific cases.

### 3. Git LFS

`git-lfs` was unavailable. LFS can dominate both network and disk behavior and must be tested before broad claims about large repositories.

### 4. OS sandboxing

Independent clones are not a security boundary. An unrestricted agent can still traverse into sibling directories and damage canonical. The protocol isolates normal Git state and accidental worker-local operations; actual containment requires cooperation from the agent harness, container, permissions, namespace, or sandbox.

### 5. Network and distributed filesystems

Tests used a local Linux filesystem. NFS/SMB locking semantics, abrupt machine loss, network remotes, credentials, and cross-device rename behavior remain untested.

### 6. Broad real-repository diversity

The candidate self-hosted successfully and passed synthetic compatibility profiles, but it has not yet been run across a representative corpus of real monorepos, LFS projects, nested tooling, platform-specific build systems, and repositories with custom hooks.

### 7. Long soak and resource exhaustion

The campaign included forced file-write failure, but not true disk exhaustion, inode exhaustion, out-of-memory kills, power-loss durability, or week-long churn.

---

## Decision

### Is the mechanics hypothesis strong enough to build an alpha tool?

**Yes.** The protocol survived enough adversarial testing that there is no longer a hidden basic Git reason to abandon it.

### Is it proven better than worktrees for agents?

**No.** Mechanical isolation is better; creation efficiency is much worse. The agent-behavior benefit has not yet been measured.

### Is it likely to be better in a useful segment?

**Yes.** The evidence favors independent clones when most of these are true:

- roughly 2–20 autonomous workers,
- jobs last long enough that ~2 seconds of provisioning is negligible,
- workers are mostly independent and submit committed results,
- accidental shared-Git mutation is a meaningful risk,
- the repository's working tree/dependencies dominate its history size,
- the orchestrator values simple worker ownership and disposable recovery,
- native worktree enforcement from the agent harness is absent or weak.

Worktrees remain preferable when most of these are true:

- workers are extremely short-lived or numerous,
- repository history is huge and strong object isolation is required,
- immediate shared branch/ref visibility is central,
- the harness already has mature native worktree lifecycle and confinement,
- shared repository config/hooks/refs are intentional features,
- storage or provisioning latency is tightly constrained.

---

## Recommended product direction

Do not build an ideological “worktree killer.” Build an **agent workspace manager** with evidence-based modes.

### Suggested modes

```text
clone-fast     independent Git state; locally shared object files
clone-strong   physically independent object files; highest disk cost
worktree       efficient fallback for unsuitable repositories/workloads
```

### Required preflight

Before choosing a mode, inspect:

- `.git` size,
- checked-out tree size,
- local/ref count,
- Git LFS usage,
- submodules,
- partial/shallow clone state,
- available disk space,
- operating system/filesystem,
- expected worker count and lifetime,
- whether the harness provides an actual filesystem sandbox.

The initial tool should report evidence and recommend rather than silently guess. Thresholds should be learned from more tests, not hard-coded from this one machine.

### Required architecture

- The skill contains policy: when to isolate, worker rules, required committed output, and what counts as completion.
- The CLI owns all filesystem and Git transactions.
- Canonical should remain where it is during early adoption; do not move an active agent's repository under a new umbrella directory.
- Worker publication should remain staging-plus-atomic-rename.
- Result preservation and integration should remain separate operations.
- Ref copying must be narrowed or compacted before publication.
- Bootstrap must be explicit and repository-defined.
- Cross-platform locking must replace `fcntl` before a public release.
- Actual filesystem confinement should be a separate, honestly named feature.

---

## Next decisive experiment

Run a real-agent paired trial:

1. Freeze one or more real repository snapshots.
2. Prepare native-worktree and clone-workspace variants.
3. Randomly assign identical tasks to the same model/tool version.
4. Include independent work, conflicts, dependencies, stale bases, interrupted workers, destructive Git commands, reviews, and long-running processes.
5. Record:
   - correct task completion,
   - Git/workspace mistakes,
   - cross-worker interference,
   - human interventions,
   - recovery events,
   - tool calls and tokens spent on Git,
   - elapsed time and disk use.
6. Blindly review outputs where possible.
7. Decide by intervention/error rates, not by whether either system can eventually finish.

A clone advantage smaller than ordinary model-run variance would not justify the added tool. A clear reduction in Git mistakes or human repair at equal code quality would.

---

## Reproduction artifacts

- `cws.py` — frozen candidate
- `hardening_suite.py` — deterministic suite
- `state_machine_fuzz.py` — generated lifecycle campaign
- `random_kill.py` — noncooperative process-kill campaign
- `scaling_v2.py` and `manyrefs_v2.py` — time/disk scaling
- `concurrency_v2.py` and `gc_compare.py` — concurrency comparisons
- `shared_state_compare.py` — direct shared-state mutation comparison
- `partial_clone_probe.py` — promisor/partial clone compatibility
- `narrow_clone_probe.py` and `ref_compaction_probe.py` — ref-explosion falsification/workarounds
- `self_host_probe.py` — self-hosted lifecycle
- `io_fault_probe.py` — forced I/O failure recovery
- `RESULTS.json` — consolidated machine-readable evidence

