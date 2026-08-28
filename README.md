# Clonegrown

**Per-task Git working-directory lifecycle management for coding agents.**

Clonegrown creates each task in its own Git working directory (a *worker*),
records the worker lifecycle, and can preserve a worker's clean committed tip
under a ref in the canonical repository. A worker can be a linked worktree or a
local clone. Collection preserves a result; it does not merge, rebase,
cherry-pick, or otherwise integrate that result into a user branch.

> **Status:** alpha, POSIX-only. The current release has known custody gaps in
> destructive operations. In particular, discard does not protect ignored
> files or coordinate with processes writing outside Clonegrown, and a failed
> recursive deletion can currently be recorded as complete. Do not use
> unattended cleanup for valuable work. Read [Current alpha safety
> boundary](#current-alpha-safety-boundary) before using `discard`.

## Install

Installing the CLI through a Python tool manager avoids Clonegrown's custom
installer replacement behavior:

```bash
pipx install git+https://github.com/kserrec/clonegrown.git
```

or:

```bash
uv tool install git+https://github.com/kserrec/clonegrown.git
```

The custom installer also copies the bundled agent skill for Claude Code and
Codex:

```bash
curl -fsSL https://raw.githubusercontent.com/kserrec/clonegrown/main/install.sh | sh
```

The installer treats its source directory, command wrapper, Claude skill
directory, and Codex skill directory as four whole, installer-owned targets.
A first install creates only absent targets. Each target receives versioned
ownership evidence tied to one random installation ID; an update replaces only
absent targets or targets carrying that same ID. Existing unowned targets,
direct symlinks, filesystem-root or home-directory targets, and overlapping
replacement paths are refused before cloning or renaming anything.

All four replacements are staged beside their destinations and synced before
publication. During an update, each old owned target is renamed to a unique
backup. Before the four-target commit, a command failure or caught `HUP`,
`INT`, or `TERM` restores the previous targets in reverse order. `SIGKILL` and
machine power loss cannot run that rollback; an authenticated backup may
remain beside its destination for manual recovery.

Abandoned-stage cleanup checks the filesystem identity captured when the stage
was created and does not pass that validated name to a separate `rm` command.
This ownership protocol is not an operating-system sandbox against a hostile
process running as the same user and deliberately swapping paths between POSIX
filesystem calls; such a process already has direct authority over these
user-owned destinations.

**Pre-marker installations are not adopted automatically.** If any destination
was created by an older `install.sh` but has no `.clonegrown-install` marker
(or embedded marker in the command wrapper), this installer refuses to replace
it because it cannot prove ownership. Verify and move or remove those old
targets yourself before treating the run as a first install. Do not manufacture
a marker to bypass the check. A successful owned update replaces the entire
source and skill directories, including extra files placed inside them.

To inspect the installer first:

```bash
git clone https://github.com/kserrec/clonegrown.git
cd clonegrown
sh install.sh
```

The custom installer writes:

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

It does not edit the shell profile. If `~/.local/bin` is not on `PATH`, it
prints the line needed to add it. Git and Python 3.11+ are required.
`clonegrown --version` confirms the CLI installation, and
`python -m clonegrown` is equivalent to the command.

## Use

From a Git repository:

```bash
clonegrown init
```

For a repository named `my-project`, Clonegrown creates a sibling workspace
named `my-project-dev` and manages numbered workers underneath it.

Spawn a worker:

```bash
clonegrown spawn "fix the authentication race"
```

The command prints JSON containing the worker ID, path, branch, and resolved
base commit. The agent works in that repository and commits the desired result.

Preserve the worker's clean committed tip in the canonical repository:

```bash
clonegrown collect 1
```

Collection creates an immutable result ref and updates Clonegrown's summary
ref. Review and integrate that commit into the intended user branch with an
explicit Git operation outside Clonegrown.

After stopping every process that can write to the worker, remove it:

```bash
clonegrown discard 1
```

To intentionally throw away an uncollected worker and all content Clonegrown
does and does not inspect:

```bash
clonegrown discard 1 --abandon
```

Inspect or reconcile recorded interrupted operations:

```bash
clonegrown status
clonegrown recover
```

Recovery covers the lifecycle checkpoints represented in durable state. It
does not currently prove cleanup at every filesystem boundary.

Clonegrown discovers the workspace when run from the canonical checkout, the
workspace, or a worker repository. Explicit `--workspace` paths are available
for nonstandard layouts.

Workers start from canonical `HEAD` by default; no default branch name is
assumed. Override the base when needed:

```bash
clonegrown spawn "compare parser approach" --base feature/parser
```

Pass a stable request ID when a caller may retry the same spawn. Matching
retries with that ID and the same parameters return the existing allocation;
spawns without a request ID create new workers:

```bash
clonegrown spawn "compare parser approach" --request-id parser-comparison-1
```

## Three kinds of worker

```bash
clonegrown spawn "add tests" --worktree   # linked worktree
clonegrown spawn "add tests"              # default clone; object files may be hard-linked
clonegrown spawn "add tests" --strong     # clone with physically separate object files
```

| | Separate working files | Separate refs, stash, local config, default `.git/hooks` | Separate object files | Spawn cost |
|---|---|---|---|---|
| `--worktree` | yes | no | no | near zero |
| clone (default CLI mode) | yes | yes | no | seconds |
| `--strong` | yes | yes | yes | seconds plus a full object copy |

The same recorded lifecycle commands operate on all three modes, but their Git
isolation differs. Default local clones can use hard links for existing Git
objects. `--strong` passes Git's no-hardlinks option and supplies physical
object-file independence at spawn time.

For clone workers, hook separation applies to the default private `.git/hooks`
location: Clonegrown does not copy programs from the canonical repository's
private hook directory. A configured `core.hooksPath` is different. Clonegrown
copies that configuration value unless its generic path-bound check finds the
canonical path's literal text; it never copies the hook programs the value
names. Any copied value that resolves outside the worker remains a shared
dependency. Absolute values receive a compatibility warning, but Git can also
expand values such as `~/hooks` or traversal-heavy relative paths outside the
worker without that warning. A conventional repository-relative value such as
`.githooks` resolves within the worker.

Choose a worktree when history is very large, tasks are short, or workers are
created and destroyed rapidly. Worktrees share the canonical repository's
broad Git state, including refs, stash, config, and hooks; Clonegrown records a
compatibility warning on each worktree worker.

Choose a clone when separate refs, stash, local config, and the default private
hook location matter. In the stress fixture, eight concurrent
`git gc --prune=now` runs succeeded 8/8 in clones and 1/8 in linked worktrees;
the worktree failures were Git refusing a concurrent garbage-collection lock,
not repository corruption.

Choose `--strong` only when physical object independence matters. It copies the
object database, so histories with many objects cost more time and disk.

## Implemented safeguards

- Workers start from an explicitly resolved and pinned commit.
- Worker allocation and lifecycle metadata updates use workspace and worker
  locks.
- Collection and normal deletion authenticate the published worker path and
  marker before acting on it. Existing request-index hits currently return the
  stored record without equivalent revalidation or worker authentication.
- Collection compares snapshots before and after fetch, preserves the fetched
  commit under an immutable result ref, and does not accept a change detected
  between those snapshots as collected.
- Normal deletion requires a collected result; deleting an uncollected worker
  requires explicit `--abandon`; detected post-collection drift requires
  explicit `--force`.
- Worktree cleanup targets the recorded, authenticated admin entry rather than
  running a blanket `git worktree prune`.
- Clone workers receive an invalid push URL for the local canonical-source
  remote. This is a best-effort accident guard, not a security boundary.
- Recovery reconciles the interruption boundaries represented by the current
  durable record and covered by the test campaigns.

## Current alpha safety boundary

The following limits are verified properties of the current implementation,
not hypothetical platform concerns:

- Collection and drift snapshots omit Git-ignored paths. Normal discard can
  therefore delete ignored content without requiring separate acknowledgement.
- A worker has no durable work lease. A process outside Clonegrown can write
  after the final check and race discard.
- Recursive deletion currently suppresses filesystem errors and can record a
  terminal discarded or abandoned state without proving the worker path is
  absent.
- Recovery of an interrupted spawn can currently delete an authenticated,
  published worker after observing that it changed from its base.
- Worktree spawn uses a deterministic task branch, and rollback can delete a
  branch of that name without proving this invocation created it.
- Command-failure output currently includes the full Git argument vector and
  stderr. Copied configuration values or credential-bearing remote URLs can
  therefore appear in an error even though successful CLI records redact
  secret and transaction fields.
- A collected worker is one-shot: collecting the same unchanged tip is a
  no-op, while new commits after collection are rejected. Start a new worker
  for new work.
- Clonegrown provides Git-state separation, not an operating-system sandbox.
  An unrestricted process can traverse into other directories.
- Worktree workers share broad Git state. Default clones separate refs, stash,
  local config, and the default private hook location, subject to the configured
  `core.hooksPath` caveats above; they may also share existing object files
  through hard links. Only `--strong` supplies physical object-file
  independence.

The accepted target custody contract is recorded in [`PLAN.md`](PLAN.md) and
[Architecture](ARCHITECTURE.md#target-custody-contract-planned-not-implemented):
a durable cooperative lease, explicit acknowledgement for ignored content,
authenticated quarantine before checked deletion, one-shot workers after
collection, and explicit integration. Those additions are planned and are
**not implemented in this release**.

Git LFS, arbitrary filters, network or distributed filesystems, genuine
disk/inode exhaustion, and native Windows are separate unverified validation
gaps. Clonegrown 0.x treats them as unsupported; this is not a claim that each
is known to fail.

## Agent skill

The custom installer copies [`SKILL.md`](SKILL.md) into the current personal
skill locations for Claude Code and Codex. Their directories carry the same
installation identity as the source and command wrapper, so an unrelated
pre-existing skill directory is refused rather than overwritten.

After first installation, start a fresh agent session if the agent has not
discovered the skill.

## Evidence

The current package and the frozen prototype campaign are different evidence
sets:

- Current-package campaigns and their dates are recorded in
  [`PLAN.md`](PLAN.md). The package passed the documented clone and worktree
  hardening campaigns, crash failpoints, SIGKILL campaigns, and randomized
  lifecycle seeds before this review. A later CI worktree run exposed a timing
  gate failure; its root cause remains to be diagnosed in the planned
  verification phase.
- [`research/REPORT.md`](research/REPORT.md) preserves the conclusions of the
  frozen prototype campaign. [`research/REPRODUCE.md`](research/REPRODUCE.md)
  distinguishes commands that run against the current package from historical
  candidate inputs that are no longer present and therefore cannot be
  reproduced byte-for-byte.

These results establish mechanical viability and the measured clone/worktree
tradeoff. They do not establish that every coding agent behaves better with
Clonegrown.

## Python API

The operations are importable with no runtime dependencies beyond the standard
library:

```python
from clonegrown import ClonegrownError, collect, discard, init_workspace, recover, spawn, status
```

The API returns full internal dictionaries; successful CLI results remove
secret and transaction-bookkeeping fields before printing JSON. Error output
has the exposure described in the alpha safety boundary. The current Python
API default `spawn(..., strong=True)` differs from the CLI's default
non-strong clone; this verified mismatch is scheduled for correction in
[`PLAN.md`](PLAN.md). Pass `strong=False` or `strong=True` explicitly until
then. `spawn(..., mode="worktree", strong=False)` selects a worktree worker.

[`ARCHITECTURE.md`](ARCHITECTURE.md) describes the package layout, durable
state, current recovery behavior, and planned custody contract.
