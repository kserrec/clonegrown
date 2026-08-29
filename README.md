# Clonegrown

**Per-task Git working-directory lifecycle management for coding agents.**

Clonegrown creates each task in its own Git working directory (a *worker*),
records the worker lifecycle, and can preserve a worker's clean committed tip
under a ref in the canonical repository. A worker can be a linked worktree or a
local clone. Collection preserves a result; it does not merge, rebase,
cherry-pick, or otherwise integrate that result into a user branch.

> **Status:** alpha; supported operating-system targets are Linux and macOS
> (POSIX only). Destructive operations are conservative, but
> the work lease that guards discard is cooperative and cannot stop a process
> that ignores it. Do not use unattended cleanup for valuable work. Read [Current alpha safety
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
machine power loss cannot run that rollback, and a caught signal after the
commit skips the remaining backup removal; in those cases an authenticated
backup may remain beside its destination for manual recovery.

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

It does not edit the shell profile. If the command directory is not on `PATH`,
it prints the shell-safe line needed to add it. A directory containing `:`
cannot be represented as one POSIX `PATH` entry, so that case receives a
shell-safe full-path command instead. Git 2.29.0 or newer and Python 3.11 or
newer are required. CI runs the full unit suite, including destructive
installer and lifecycle paths, through a Linux/macOS matrix configured for
Python 3.11 and the latest stable Python 3.x release. A separate job builds
exact Git 2.29.0 and runs the full unit and clone/worktree adversarial suites
against it.
`clonegrown --version` confirms the CLI installation, and
`python -m clonegrown` is equivalent to the command.

## Use

From a Git repository:

```bash
clonegrown init
```

For a repository named `my-project`, Clonegrown creates a sibling workspace
named `my-project-dev` and manages numbered workers underneath it.
The workspace must live on a filesystem that supports hard links: worker
records are created with `os.link`.

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

Every worker is leased from spawn. After stopping every process that can
write to the worker, release the lease, then remove the worker:

```bash
clonegrown release 1
clonegrown discard 1
```

Discard refuses a leased worker whatever flags it is given; `release` is the
caller's statement that the worker is quiet, which Clonegrown records but
cannot verify. A released worker that is still `ready` can be taken over again
with `clonegrown claim 1`.

To intentionally throw away an uncollected worker and all content Clonegrown
does and does not inspect, release it and then:

```bash
clonegrown discard 1 --abandon
```

A collected worker is one-shot: `--abandon` is refused for it. Its two
remaining custody questions each have their own flag: detected changes after
collection need `--force`, and Git-ignored paths, which collection never
inspects, need `--discard-ignored`. The refusal names the count and a bounded
sample of ignored path names; it never prints file contents.

```bash
clonegrown discard 1 --discard-ignored
```

Inspect or reconcile recorded interrupted operations:

```bash
clonegrown status
clonegrown recover
```

`status` is a complete audit that changes nothing: every disagreement
between the records, the workspace, and the canonical repository is listed
under `issues` with a stable code (the codes are enumerated in
[Architecture](ARCHITECTURE.md#command-output)). `recover` repairs only what
a record provably owns and reports the rest.

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

Clone workers receive a validated snapshot of canonical's effective
repository-local configuration. Valueless entries remain distinct from empty
strings, repeated occurrences retain their order, and repository-local include
values are flattened without copying the include directives. Relative local
fetch and push paths are anchored to canonical before the worker is relocated;
absolute paths, URL schemes, and scp-like remotes keep their spelling. The full
copied and omitted state boundary is the
[minimum clone-fidelity contract](ARCHITECTURE.md#minimum-clone-fidelity-contract).

Ordinary required clean/smudge filters are covered with a real external driver:
tracked attributes select the filter, Git stores the cleaned bytes, both clone
and worktree workers materialize the smudged bytes, subsequent `git add`
cleans them again, and collection preserves the cleaned blob. The driver
command must already be available wherever Git runs. Clonegrown copies eligible
repository-local filter configuration into a clone and shares canonical config
with a worktree; it does not copy or install the driver program.

## Implemented safeguards

- Workers start from an explicitly resolved and pinned commit.
- The complete generated task branch is validated by Git before allocation
  advances its counter or creates a ref, record, request index, stage, or
  worker slot. An invalid result such as a `.lock` suffix leaves no allocation
  evidence behind.
- Worker allocation and lifecycle metadata updates use workspace and worker
  locks.
- Collection and normal deletion authenticate the published worker path and
  marker before acting on it. A request-index hit is validated field by field
  and its settled worker is authenticated on disk before it is returned.
- Collection compares snapshots before and after fetch, preserves the fetched
  commit under an immutable result ref, and does not accept a change detected
  between those snapshots as collected.
- Every deletion requires an explicit lease release first; neither
  `--abandon` nor `--force` overrides the lease, and recovery never infers a
  release from a dead process. Normal deletion requires a collected result;
  deleting an uncollected worker requires explicit `--abandon`; detected
  post-collection drift requires explicit `--force`; a collected worker's
  Git-ignored paths require explicit `--discard-ignored`; a collected worker
  cannot be abandoned or claimed again.
- Deletion goes through an authenticated quarantine: intent is recorded, the
  worker is fingerprinted, its slot is renamed to `.cws/quarantine/`, the
  quarantined worker is authenticated and rechecked against the fingerprint,
  deleted with errors enabled, and proved absent. A change in the old
  final-check window, a deletion error, or an interruption leaves the worker
  preserved in quarantine with the reason recorded; `status` reports it,
  `recover` resumes it, and a repeated `discard` with the same acknowledgement
  deletes it (a quarantined worktree whose admin directory Git has since
  pruned is fingerprinted without Git for that deletion). Content found both
  in the slot and at the quarantine path is never resolved automatically. The terminal `discarded`/`abandoned` state is recorded only
  after the worker, its stage, the quarantine, and canonical's worktree
  state are each proved clean.
- Worktree cleanup targets the recorded, authenticated admin entry rather than
  running a blanket `git worktree prune`, verifies that the directory is
  gone, and deletes the task branch only in a ref transaction that proves this
  worker created it and that it still points where cleanup recorded. A moved
  branch, or one checked out in canonical or in another working tree, is
  retained and reported, and the record stays `discarding` until the branch
  is moved back, the checkout released, or a stale worktree entry pruned
  (`git worktree prune`); a branch that is absent, or that
  was already absent when cleanup was recorded, is nothing of the worker's
  and cleanup finishes without touching it.
- Clone workers receive an invalid push URL for the local canonical-source
  remote. This is a best-effort accident guard, not a security boundary.
- Recovery reconciles the interruption boundaries represented by the current
  durable record and covered by the test campaigns.

## Current alpha safety boundary

The following limits are verified properties of the current implementation,
not hypothetical platform concerns:

- Collection and drift snapshots omit Git-ignored paths. Discard of a
  collected worker enumerates them by name through Git's own ignore rules and
  refuses without `--discard-ignored`; `--abandon` on an uncollected worker
  authorizes deleting everything, ignored content included.
- The work lease is cooperative. A process that ignores it, or keeps file
  descriptors open across a release, can still write after the final
  fingerprint. The fingerprint covers Git's status listing plus the size and
  modification time of every entry in the worker directory tree except
  `.git` (nested repositories, FIFOs, and sockets included); a rewrite that
  keeps both size and timestamp is not detected.
- The deletion unit is the slot directory `<workspace>/<id>/`. Anything
  placed beside the repository inside it is fingerprinted but never
  inspected for ignored-content or drift acknowledgement.
- Git command failures redact copied configuration values, remote URLs, and
  URL userinfo from the displayed command, stdout, and stderr before the text
  reaches CLI output or a durable worker error field. Failure text also hides
  the private token component of Clonegrown's own staging and quarantine
  paths, including paths quoted by operating-system errors. Successful
  `status` output deliberately keeps the full `quarantine_path` so it can guide
  recovery while hiding the separate `worker_token` field. Other diagnostic
  text remains visible; this is targeted redaction, not general secret
  detection, so review an error before publishing it outside a trusted
  channel.
- Failures from `init`, `spawn`, `collect`, `discard`, and `recover` name the
  exact operation stage, the last known durable mutation, whether work is
  believed preserved or unverified, and whether to retry, run `recover`, or
  inspect manually. A write or rename that raised is reported as unverified,
  never assumed complete or absent. The Python exception keeps the original
  low-level cause chained for debugging; the CLI prints one contextual
  `clonegrown:` error with no traceback. Command causes retain the targeted
  redaction described above. Arbitrary exception text receives the same
  URL-userinfo and Clonegrown-custody-token filtering but is not generally
  secret-scanned. Process-control exceptions such as `KeyboardInterrupt`,
  `SystemExit`, and `GeneratorExit` pass through untouched.
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
[Architecture](ARCHITECTURE.md#target-custody-contract-implemented):
a durable cooperative lease, explicit acknowledgement for ignored content,
authenticated quarantine before checked deletion, one-shot workers after
collection, and explicit integration. All of it is implemented in this
release.

Git LFS remains unsupported in 0.x: `git-lfs` is not a Clonegrown dependency,
and Clonegrown neither installs it nor simulates its filter-process, object
transfer, credential, or remote-storage behavior. Long-running `filter.process`
drivers, delayed checkout, credentialed/network filters, and other filter
protocols beyond the tested clean/smudge case are also unsupported.

Deterministic fault tests cover an `ENOSPC` equivalent before atomic metadata
publication, a refused cross-device quarantine rename, and an I/O error after
recursive deletion has removed one file. They prove the represented recovery
behavior, not the behavior of a genuinely exhausted disk or inode table.
Genuine disk/inode exhaustion and network or distributed filesystems remain
unvalidated and unsupported; this is not a claim that each is known to fail.
Native Windows is explicitly unsupported in 0.x: the implementation imports
POSIX-only `fcntl` and relies on POSIX advisory locking, rename, and deletion
semantics. Linux and macOS results do not establish equivalent Windows
behavior.

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
  lifecycle seeds before this review. A later CI worktree run exposed a
  one-sample timing assertion: it treated host scheduling and I/O contention as
  a correctness property. Phase 5.1 removed timing from the deterministic
  concurrency gate and moved raw multi-sample measurements to a nonblocking
  benchmark.
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
from clonegrown import ClonegrownError, claim, collect, discard, init_workspace, recover, release, spawn, status
```

The Python API and CLI both default to a non-strong clone:

```python
worker = spawn(workspace, "HEAD", "fix auth race")
strong_worker = spawn(workspace, "HEAD", "isolate object files", strong=True)
worktree_worker = spawn(workspace, "HEAD", "quick comparison", mode="worktree")
```

The API returns full internal dictionaries; successful CLI results remove
secret and transaction-bookkeeping fields before printing JSON. Error output
has the exposure described in the alpha safety boundary. Pass `strong=True`
only for a clone whose object files must be physically independent;
`mode="worktree"` uses the default `strong=False`, and the API rejects the
incompatible combination of worktree mode with `strong=True`.

[`ARCHITECTURE.md`](ARCHITECTURE.md) describes the package layout, durable
state, current recovery behavior, and planned custody contract.
