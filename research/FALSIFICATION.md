# Falsification Run: Independent Clones vs Git Worktrees for AI-Agent Workspaces

## Goal

This second experiment was designed to *disprove* the clone-workspace idea rather than confirm it. It attacked the assumptions that made independent local clones look attractive for parallel coding agents.

Three designs were compared:

1. **Worktree** — ordinary `git worktree` workers sharing one Git repository.
2. **Naive clone** — worker created with a normal local `git clone canonical worker` and a task branch.
3. **Hardened clone** — local clone with explicit base selection, preserved upstream `origin`, a separate fetch-only local `canonical` remote, and `--no-hardlinks` for stronger object isolation.

Git version: 2.47.3.

No Codex, Claude Code, Aider, or similar agent CLI is installed in this environment, so this run measures Git/workspace behavior and failure modes, not model confusion or human-intervention rates.

## Falsification results

### 1. The naive clone design silently changes `origin`

A worker cloned from the canonical local repository received the canonical path as its `origin`, not the canonical repository's real upstream.

When the worker performed the completely normal command:

```bash
git push origin agent/task
```

its branch was pushed into the canonical local repository, not upstream.

Likewise, after upstream advanced independently, `git fetch origin` in the naive clone did **not** see the upstream change because `origin` pointed at canonical.

Worktrees preserved normal upstream semantics. The hardened clone fixed this by preserving the real `origin` and naming the local integration source `canonical`, with pushes to `canonical` disabled.

**Verdict:** This is a serious flaw in the naive design and must be explicitly fixed in any skill.

### 2. Naive clones inherit the source repository's currently checked-out branch

Canonical was deliberately left on an `accidental` feature branch while `main` remained at an older commit.

- Worktree explicitly created from `main`: correct base.
- Naive clone + new task branch: worker started from `accidental`: wrong base.
- Hardened clone explicitly created the worker branch from `canonical/main`: correct base.

**Verdict:** Worker creation must always name/verify the exact base commit or branch. Cloning and then branching from `HEAD` is unsafe.

### 3. Independent clones do not inherit canonical repo-local Git config

A canonical-only local config setting was added before worker creation.

- Worktree inherited it automatically.
- Naive clone did not.
- Hardened clone did not.

This is the exact opposite side of clone isolation: local configuration cannot leak from workers into canonical, but required canonical configuration also does not automatically reach workers.

Projects relying on local Git settings such as `core.hooksPath`, filters, sparse-checkout-related configuration, or other repo-local setup may need an explicit bootstrap policy.

**Verdict:** Real clone downside. Usually manageable, but a generic skill cannot simply assume every clone is behaviorally identical to canonical.

### 4. Worktrees have a substantially larger shared-state blast radius

Canonical had a stash and a normal upstream remote. A worker then performed plausible repository-level operations.

#### Worker ran `git stash clear`

- Worktree: canonical stash was deleted.
- Clones: canonical stash survived.

#### Worker changed local Git config

- Worktree: change appeared in canonical.
- Clones: change remained isolated.

#### Worker removed `origin`

- Worktree: canonical's `origin` disappeared too.
- Clones: canonical was unaffected.

**Verdict:** This is strong evidence in favor of clones for fallible autonomous workers. Worktrees share more operational state than their separate directories suggest.

### 5. Normal local clones are not a perfect physical isolation boundary

Git optimizes local clones using hard links when possible. In the test, the canonical repository's pack file and the naive clone's pack file had the **same inode**.

The benchmark deliberately corrupted the worker's pack file *in place*. Canonical immediately failed `git fsck` as well.

- Worktree: canonical corrupted, as expected from a shared object database.
- Naive local clone: canonical also corrupted because of hard-linked objects.
- Hardened `--no-hardlinks` clone: canonical remained healthy.

This attack required directly modifying Git object storage; ordinary Git commands treat objects as immutable and normally do not perform this kind of in-place corruption. It is therefore a lower-probability agent mistake than `git config`, `stash`, or remote operations.

**Verdict:** The claim that ordinary local clones provide *complete* Git isolation is false. `--no-hardlinks` fixes it but costs storage and setup time.

### 6. `--no-hardlinks` has a measurable cost

A synthetic repository with about 6 MiB of incompressible tracked blobs was used to create five workers.

| Strategy | Median setup | Allocated bytes |
|---|---:|---:|
| Worktrees | 0.322 s | 47.1 MB |
| Naive local clones | 0.459 s | 47.8 MB |
| Hardened `--no-hardlinks` clones | 0.858 s | 79.4 MB |

The naive local clones were nearly as storage-efficient as worktrees because Git hard-linked repository objects. The stronger-isolation clone protocol gave up that advantage.

A separate 16 MiB probe also showed six ordinary local clones growing from about 129 MiB to 225 MiB after each worker diverged and was force-repacked, so long-lived clones can gradually lose the initial hard-link storage advantage anyway.

**Verdict:** Not a dealbreaker for ordinary repositories and a handful of agents, but this becomes material for very large repos, many workers, or LFS-heavy repositories.

### 7. Worktrees retain forgotten commits more safely

A worker made a valuable commit and was then deleted before collection.

- Worktree: commit remained accessible through the shared repository/branch.
- Both clone designs: canonical did not have the commit.

The hardened clone collection invariant was then tested:

1. Fetch worker branch into canonical.
2. Verify the commit exists in canonical.
3. Delete worker.

The commit survived correctly.

**Verdict:** Worktrees are safer by default. Clones require a hard lifecycle invariant: **never delete a worker before desired commits are collected and verified.**

### 8. The proposed "find the next number" allocator races badly

Twenty-four allocators simultaneously performed the naive rule: scan the existing numeric worker folders, choose highest + 1, then create it.

- Successes: 1
- Collisions: 23

An atomic `mkdir` retry allocator produced 24/24 unique workers.

**Verdict:** The skill cannot literally use a read-then-create numbering algorithm under parallel spawning. Allocation must be atomic. Easy fix, but another reason this should be a small deterministic helper plus a skill rather than prose alone.

### 9. Shared Git maintenance can contend under worktrees

Eight workers simultaneously ran `git gc --prune=now`.

- Worktrees: 1 succeeded, 7 failed because GC was already running in the common repository.
- Naive clones: 8/8 succeeded.
- Hardened clones: 8/8 succeeded.

Manual GC is not a common coding-agent operation, but the result demonstrates that shared repository internals create real concurrency coupling.

**Verdict:** Evidence in favor of clones for autonomous parallel workers.

### 10. Repeated worker lifecycle did not expose a correctness failure

Ten complete create → change → commit → collect/merge → cleanup cycles were run for each strategy.

| Strategy | Failures | All commits integrated | `git fsck` | Time |
|---|---:|---|---|---:|
| Worktrees | 0 | yes | clean | 1.33 s |
| Naive clones | 0 | yes | clean | 2.42 s |
| Hardened clones | 0 | yes | clean | 3.25 s |

**Verdict:** The hardened clone lifecycle is mechanically sound in repeated use, but worktrees are clearly more efficient.

## What this run disproved

The strongest version of the original thesis does **not** survive:

> "Just use normal local clones; you get essentially all the worktree benefits, stronger isolation, and no meaningful new complexity."

That is false.

Plain local clones introduce several hidden semantics that are dangerous for autonomous agents:

- `origin` changes meaning.
- normal `fetch origin` can become stale relative to real upstream.
- normal `push origin` can unexpectedly mutate canonical.
- the worker can accidentally start from canonical's currently checked-out branch rather than the requested base.
- required repo-local Git configuration is not inherited.
- local-clone object storage may still be physically shared through hard links.
- forgotten commits are easier to destroy during cleanup.
- naive numbered allocation races.

## What survived falsification

A **hardened clone protocol** survived every tested correctness attack:

1. Determine and verify the exact base commit/branch.
2. Clone from canonical.
3. For strong object isolation, use `--no-hardlinks` (optional if standard Git-command isolation is sufficient).
4. Rename the local source remote to `canonical`.
5. Make `canonical` fetchable but not pushable.
6. Preserve the real upstream as `origin` when one exists.
7. Create a globally unique task branch from the explicit base, with no accidental upstream tracking.
8. Allocate worker directories atomically.
9. Explicitly fetch canonical when newer integrated state is required.
10. Collect and verify desired commits in canonical before deleting a worker.
11. Bootstrap any required repo-local configuration or project setup explicitly.

Under that protocol, the clone design retained its strongest advantage: worker-level Git state such as stashes, remotes, config, refs, and maintenance operations were genuinely more independent than under worktrees.

## Scientific verdict

### Naive clone workflow: **reject**

The second run found enough realistic semantic traps that I would not recommend teaching agents simply to replace `git worktree` with `git clone <canonical>`.

### Hardened clone workflow: **still promising, but no longer "obviously simpler"**

It appears mechanically robust and gives stronger operational isolation between fallible workers, but we now have to admit that we are building a small orchestration layer to recover semantics worktrees provide automatically.

The evidence currently favors hardened clones when these are the priorities:

- a small/moderate number of autonomous agents;
- strong containment of accidental Git-state changes;
- easy disposal/recovery of a bad worker;
- ordinary-sized repositories where extra Git storage is unimportant;
- a harness/skill that can enforce lifecycle rules deterministically.

The evidence favors worktrees when these are the priorities:

- very large repositories or many workers;
- maximum creation/integration efficiency;
- preserving repo-local Git configuration automatically;
- automatic retention/visibility of local commits and refs;
- relying on existing agent tooling that already has native worktree lifecycle support.

## Remaining experiment

The central behavioral hypothesis is still untested here:

> Does a real coding agent make fewer Git/workspace mistakes, use fewer tool calls/tokens, and require fewer human interventions when given the hardened independent-clone model rather than native worktrees?

That requires a live agent CLI/harness. This environment has none installed. The mechanical evidence is now strong enough to justify that A/B, but **not** strong enough to declare clones universally better for agents.

The strongest evidence-based position after trying to disprove the idea is therefore:

> **Independent clones are a viable and potentially better isolation primitive for AI workers, but only as a hardened protocol. Worktrees remain the simpler and safer default at the Git-mechanics level. The final winner should be decided by live-agent behavioral testing, not by Git mechanics alone.**
