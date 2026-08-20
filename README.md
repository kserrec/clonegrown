# Clonegrown

**Isolated Git clone workspaces for coding agents.**

Clonegrown gives autonomous coding agents ordinary, independent Git clones instead of linked worktrees, while keeping creation, collection, recovery, and cleanup deterministic.

> **Status:** alpha. The Git mechanics have been heavily adversarially tested on Linux. Broader real-agent and cross-platform validation is still ongoing.

## Install

Recommended one-line install:

```bash
curl -fsSL https://raw.githubusercontent.com/kserrec/clonegrown/main/install.sh | sh
```

Prefer to inspect it first?

```bash
git clone https://github.com/kserrec/clonegrown.git
cd clonegrown
sh install.sh
```

The installer does four things:

```text
Clonegrown source
  -> ~/.local/share/clonegrown

Command
  -> ~/.local/bin/clonegrown

Claude Code skill
  -> ~/.claude/skills/clonegrown/SKILL.md

Codex skill
  -> ~/.agents/skills/clonegrown/SKILL.md
```

It does not edit your shell profile. If `~/.local/bin` is not already on `PATH`, it prints the one line you need to add.

The installer needs Git and Python 3.11+. Rerun the same command to update Clonegrown.

You can also install the Python package directly:

```bash
pipx install git+https://github.com/kserrec/clonegrown.git
```

or:

```bash
uv tool install git+https://github.com/kserrec/clonegrown.git
```

Those package-manager forms install the CLI only; the recommended `install.sh` also installs the agent skill.

## Use

From a Git repository:

```bash
clonegrown init
```

For a repo named `my-project`, Clonegrown creates a sibling workspace named `my-project-dev` and manages numbered worker clones underneath it.

Spawn an isolated worker:

```bash
clonegrown spawn "fix the authentication race"
```

Clonegrown prints JSON containing the worker ID, path, branch, and exact base commit. The agent works normally in that returned repository and commits the result.

Preserve the finished result back into the canonical repository:

```bash
clonegrown collect 1
```

Then remove the worker:

```bash
clonegrown discard 1
```

To intentionally throw away uncollected work:

```bash
clonegrown discard 1 --abandon
```

Inspect or recover state:

```bash
clonegrown status
clonegrown recover
```

Clonegrown discovers the workspace automatically when run from the canonical checkout, the workspace, or one of its worker repositories. Explicit `--workspace` paths are available for unusual layouts but should rarely be needed.

Workers start from canonical `HEAD` by default, so Clonegrown does not assume your default branch is named `main`. Override the base when needed:

```bash
clonegrown spawn "compare parser approach" --base feature/parser
```

## Fast vs strong clones

Normal workers use Git's efficient local clone behavior:

```bash
clonegrown spawn "add tests"
```

For physical independence of Git object files:

```bash
clonegrown spawn "risky Git experiment" --strong
```

The default fast mode still isolates Git config, refs, remotes, stashes, indexes, reflogs, and ordinary repository state. `--strong` additionally avoids local object sharing, which can cost substantial disk space when Git history is large.

## Why clones?

Worktrees are extremely efficient, but they deliberately share repository state. That can include repo-local config, remotes, refs, stashes, and object maintenance.

For autonomous agents, reducing shared mutable Git state can be worth a small workspace-creation cost. Clonegrown is therefore most promising when:

- you run a small or moderate number of autonomous agents;
- tasks last minutes or longer rather than seconds;
- the repository's Git history is not enormous;
- isolation between workers matters more than absolute spawn speed.

Worktrees are usually the better fit when:

- `.git` history is very large;
- you create and destroy many workers rapidly;
- tasks are extremely short;
- minimizing disk and spawn overhead dominates isolation concerns.

Clonegrown does **not** claim clones are always better.

## Safety model

Clonegrown's lifecycle is deliberately stricter than ad-hoc local cloning:

- workers start from an explicit resolved commit;
- worker allocation is serialized under concurrency;
- the local canonical source is configured as non-pushable;
- collection preserves and verifies a worker result before cleanup;
- deletion is blocked until work is collected or explicitly abandoned;
- interrupted lifecycle operations can be recovered;
- helper Git calls strip hostile process-level `GIT_*` overrides.

Clonegrown provides **Git-state isolation, not an OS sandbox**. An unrestricted process can still deliberately traverse into sibling directories.

## Agent skill

The recommended installer copies [`SKILL.md`](SKILL.md) into the current personal skill locations for both Claude Code and Codex, so agents can learn when Clonegrown is preferable to worktrees and use the CLI without reproducing its Git plumbing themselves.

Claude Code currently discovers personal skills from `~/.claude/skills/`. Codex's current user-scope Agent Skills location is `~/.agents/skills/`.

After first installation, starting a fresh agent session is the safest way to ensure the new skill is discovered.

## Evidence

The included [`research/REPORT.md`](research/REPORT.md), [`research/REPRODUCE.md`](research/REPRODUCE.md), and test harnesses preserve the adversarial prototype campaign.

Highlights from the frozen candidate include:

- 56/56 named deterministic/adversarial tests passed;
- 11/11 explicit collection/deletion crash points recovered;
- 24/24 randomized lifecycle seeds passed across 1,000 generated operations;
- process-kill campaigns during spawn, collection, and deletion recovered successfully;
- eight simultaneous `git gc --prune=now` operations produced 8/8 successes in independent clones versus 1/8 in linked worktrees in the stress fixture;
- worktrees were dramatically faster to create;
- fast local clones stayed close to worktree disk usage in working-tree-heavy fixtures;
- fully independent clones became expensive when Git history dominated repository size.

Those results establish mechanical viability and the tradeoff. They do not yet prove that every coding agent behaves better with Clonegrown than with worktrees.

## Requirements and limitations

Clonegrown currently targets POSIX environments with Git and Python 3.11+. The implementation uses `fcntl`, so native Windows support is not ready yet. Git LFS and broader cross-platform behavior still deserve dedicated validation.
