# Clonegrown

**Isolated Git clone workspaces for coding agents.**

Clonegrown is an experimental workspace manager for running parallel coding agents in independent Git clones instead of linked Git worktrees. The goal is simple: give each autonomous worker an ordinary repository of its own, while making creation, collection, recovery, and cleanup deterministic and safe.

> **Status:** hardened research prototype / pre-release alpha. The Git mechanics have been heavily adversarially tested on Linux; real Claude/Codex behavioral A/B testing and cross-platform productization are still in progress.

## Why

Git worktrees are extremely efficient, but they deliberately share repository state. That means worktrees can share or contend over things such as repo-local config, remotes, refs, stashes, and object maintenance.

Clonegrown trades some workspace-creation speed and potentially some disk usage for stronger worker isolation. This can be attractive for coding agents, where reducing shared mutable state is often more valuable than saving a second or two of setup time.

The project does **not** claim clones are always better. Worktrees remain a strong choice for huge Git histories, very high workspace churn, and large numbers of very short-lived workers.

## Current workflow

```bash
# Install from a checkout
python3 -m pip install -e .

# Initialize a Clonegrown workspace around a canonical repository
clonegrown init /path/to/repo /path/to/repo-dev

# Spawn an isolated worker from an explicit base
clonegrown spawn /path/to/repo-dev \
  --base main \
  --task "fix auth race" \
  --request-id task-123 \
  --fast

# The agent works normally inside the returned repository and commits its work.

# Preserve the worker result back into the canonical repository
clonegrown collect /path/to/repo-dev 1

# Delete only after successful collection (or explicit abandonment)
clonegrown discard /path/to/repo-dev 1

# Inspect or recover workspace state
clonegrown status /path/to/repo-dev
clonegrown recover /path/to/repo-dev
```

Strong object isolation is currently the default. `--fast` accepts Git's normal local-clone object sharing for much lower disk cost.

## Safety model

Clonegrown's core invariants are deliberately stricter than ad-hoc local cloning:

- every worker starts from an explicit base commit, not the canonical checkout's accidental current branch;
- worker allocation is atomic under concurrency;
- the real upstream is preserved as `origin` while the local canonical source gets a separate, non-pushable remote;
- worker repositories carry identity metadata so replacement/tampering can be detected;
- collection preserves and verifies the exact worker result before cleanup;
- deletion is blocked until work is collected or explicitly abandoned;
- lifecycle operations are designed to be idempotent and crash-recoverable;
- hostile `GIT_*` process-environment overrides are stripped from helper Git calls.

Clonegrown provides **Git-state isolation, not an OS sandbox**. An unrestricted agent that can traverse the filesystem can still intentionally access sibling directories.

## What the experiments found

The included [`research/REPORT.md`](research/REPORT.md) and [`research/RESULTS.json`](research/RESULTS.json) preserve the evidence from the adversarial prototype campaign.

Highlights from the frozen candidate:

- 56/56 named deterministic/adversarial tests passed;
- 11/11 explicit collection/deletion crash points recovered;
- 24/24 randomized lifecycle seeds passed across 1,000 generated operations;
- random process-kill campaigns during spawn, collection, and deletion recovered successfully;
- eight simultaneous `git gc --prune=now` operations produced 8/8 successes in independent clones versus 1/8 in linked worktrees in the stress fixture;
- worktrees were dramatically faster to create;
- fast local clones stayed close to worktree disk usage in working-tree-heavy fixtures;
- fully independent clones became expensive when Git history dominated repository size.

Those results establish mechanical viability and the tradeoff. They do **not** yet prove coding agents behave better with Clonegrown than with worktrees.

## Clonegrown vs worktrees

Clonegrown is most promising when:

- you run a small or moderate number of autonomous agents;
- tasks last long enough that a few seconds of provisioning do not matter;
- the repository's Git history is not enormous;
- isolating each agent's Git state is valuable.

Worktrees are likely preferable when:

- `.git` history is very large;
- you create and destroy many workers rapidly;
- tasks are extremely short;
- minimizing disk and spawn overhead dominates isolation concerns.

## Agent skill

[`SKILL.md`](SKILL.md) contains an initial agent-facing workflow. The intended architecture is that the skill decides **when and how** to use Clonegrown, while the CLI—not the language model—owns filesystem allocation, Git plumbing, result preservation, and recovery.

## Requirements and limitations

The current prototype was hardened primarily on Linux with Git and Python 3. It uses POSIX `fcntl` locking, so native Windows support is not ready yet. Git LFS and broader cross-platform behavior still need dedicated product-level validation.
