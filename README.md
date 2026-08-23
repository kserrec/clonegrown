# Clonegrown

**Safe worker management for coding agents — as worktrees or as isolated clones.**

Clonegrown gives each agent task its own Git working directory (a *worker*) and manages the whole lifecycle so that nothing is created twice, nothing is deleted before its work is saved, and nothing is left half-done after a crash. A worker can be a linked worktree (fast, shares canonical's Git internals) or an independent clone (slower, shares nothing). You choose per task.

> **Status:** alpha. The Git mechanics have been heavily adversarially tested on Linux. The CLI and installer are also exercised on macOS in CI.

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

Those package-manager forms install the CLI only; the recommended `install.sh` also installs the agent skill. Either way, `clonegrown --version` confirms the install, and `python -m clonegrown` is equivalent to the command.

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

## Three kinds of worker

```bash
clonegrown spawn "add tests" --worktree   # linked worktree: fastest, shares Git internals
clonegrown spawn "add tests"              # clone (default): independent repo, shares object files
clonegrown spawn "add tests" --strong     # clone with nothing shared at all
```

| | Separate files | Separate config, refs, stash, hooks | Separate object files | Spawn cost |
|---|---|---|---|---|
| `--worktree` | yes | no | no | near zero |
| clone (default) | yes | yes | no | seconds |
| `--strong` | yes | yes | yes | seconds + full copy |

The lifecycle — idempotent spawn, verified collection, guarded deletion, crash recovery — is identical for all three. Only the isolation differs.

**Choose a worktree** when history is very large, tasks are short, or you create and destroy many workers quickly. Everything the agent does to Git config, branches, stashes, or hooks is visible to canonical and to every other worktree; Clonegrown records a compatibility warning on every worktree worker to say so.

**Choose a clone** when several autonomous agents will run for minutes or longer, when a task involves risky Git operations (history rewriting, `gc`, hook or config changes), or when one agent's Git mistakes must not be able to reach another. In the stress fixture, eight concurrent `git gc --prune=now` runs succeeded 8/8 in clones and 1/8 in linked worktrees.

**Choose `--strong`** only when physical independence of object files is specifically required; with a large history it costs a full copy.

Clonegrown does **not** claim clones are always better. It gives you the lifecycle either way and the evidence to pick.

## Safety model

Clonegrown's lifecycle is deliberately stricter than ad-hoc local cloning:

- workers start from an explicit resolved commit;
- worker allocation is serialized under concurrency;
- the local canonical source is configured as non-pushable (clone workers);
- a discarded worktree worker's admin entry and task branch are removed from canonical, never via a blanket `git worktree prune`;
- collection preserves and verifies a worker result before cleanup;
- deletion is blocked until work is collected or explicitly abandoned;
- interrupted lifecycle operations can be recovered;
- helper Git calls strip hostile process-level `GIT_*` overrides.

Clonegrown provides **Git-state isolation, not an OS sandbox**. An unrestricted process can still deliberately traverse into sibling directories. Worktree workers share Git state with canonical by design; the custody guarantees hold, the isolation ones do not.

## Agent skill

The recommended installer copies [`SKILL.md`](SKILL.md) into the current personal skill locations for both Claude Code and Codex, so agents can learn when Clonegrown is preferable to worktrees and use the CLI without reproducing its Git plumbing themselves.

Claude Code currently discovers personal skills from `~/.claude/skills/`. Codex's current user-scope Agent Skills location is `~/.agents/skills/`.

After first installation, starting a fresh agent session is the safest way to ensure the new skill is discovered.

## Evidence

The included [`research/REPORT.md`](research/REPORT.md), [`research/REPRODUCE.md`](research/REPRODUCE.md), and test harnesses preserve the adversarial prototype campaign.

Highlights from the frozen candidate include:

- 56/56 named deterministic/adversarial tests passed (clone workers); worktree workers are covered by `tests/test_worktree.py`, including crash recovery;
- 11/11 explicit collection/deletion crash points recovered;
- 24/24 randomized lifecycle seeds passed across 1,000 generated operations;
- process-kill campaigns during spawn, collection, and deletion recovered successfully;
- eight simultaneous `git gc --prune=now` operations produced 8/8 successes in independent clones versus 1/8 in linked worktrees in the stress fixture;
- worktrees were dramatically faster to create;
- fast local clones stayed close to worktree disk usage in working-tree-heavy fixtures;
- fully independent clones became expensive when Git history dominated repository size.

Those results establish mechanical viability and the tradeoff. They do not yet prove that every coding agent behaves better with Clonegrown than with worktrees.

## Python API

The same operations are importable, with no dependencies beyond the standard library:

```python
from clonegrown import init_workspace, spawn, collect, discard, recover, status, CWSError
```

Every function takes the workspace path and returns the same dictionaries the CLI prints (the CLI additionally redacts internal identity fields). `spawn(..., mode="worktree")` selects a worktree worker. [`ARCHITECTURE.md`](ARCHITECTURE.md) describes the package layout, on-disk state, and recovery model.

## Requirements and limitations

Clonegrown currently targets POSIX environments with Git and Python 3.11+. Native Windows support is not ready yet. Git LFS and broader cross-platform behavior still deserve dedicated validation.
