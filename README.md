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

> **Qualification pending (2026-09-02):** This tree is not yet a release. The
> second fresh cold review found six contract defects: clone discard could miss
> a dangling symbolic private ref; worktree spawn could overwrite a dangling
> symbolic task-branch name; dangling workspace-state, request-index, and
> worker-record links could be treated as absent; CLI init could follow a
> selected workspace symlink; `GIT_CONFIG` could reach child Git commands; and
> an unchanged repeat collection could reject a previously accepted history
> rewrite. All six are repaired on this tree, each with a class regression
> (Steps 7.5j–7.5o in [`PLAN.md`](PLAN.md)). Eight further fresh reviews of
> the repaired tree found and Steps 7.5p–7.5ae repaired: an inherited
> `GIT_*` override or a worker-local replace ref or graft file could fake
> ancestry; quarantine re-authorization skipped the ignored-content
> category; dangling symbolic refs, non-ref files, filesystem symlinks, FIFOs,
> and FIFO-backed symbolic chains under Clonegrown's ref names were not all
> treated as foreign occupants or could still block Git.
> Release still requires a fresh
> no-open-finding cold review and green hosted CI on the pushed revision; until
> then do not use it for irreplaceable work. The reproductions and causes are
> in [the Phase 7 cold-review record](research/FINAL_COLD_REVIEW.md).

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

A fresh spawn allocation reaches `ready` with an active cooperative lease.
After stopping every process that can write to the worker, release the lease,
then remove the worker:

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

A collected worker is one-shot: `--abandon` is refused for it. Each detected
custody category has its own flag: changes to the collected task branch need
`--force`; Git-ignored paths, which collection never inspects, need
`--discard-ignored`; and changed clone-private refs (including `refs/stash`)
need `--discard-private-refs`. A clone record created before private-ref
baselines existed also needs that last acknowledgement. The refusal names
bounded path or ref-name samples; it never prints file contents.

```bash
clonegrown discard 1 --discard-ignored
clonegrown discard 1 --discard-private-refs
```

Inspect or reconcile recorded interrupted operations:

```bash
clonegrown status
clonegrown recover
```

`status` audits Clonegrown's documented workspace and worker invariants without
repairing worker records, refs, worker content, or Git indexes. It acquires the
workspace's advisory lock and therefore recreates that control file if it was
removed. Each detected disagreement is listed under `issues` with a stable
code (the implemented codes are enumerated in
[Architecture](ARCHITECTURE.md#command-output)). It is not a general
filesystem-integrity or security scanner. `recover` reconciles only the
recorded cases whose ownership and next action it can establish; it reports
the rest.

### 0.x retention and manual integration

Every Clonegrown 0.x release retains worker records and collected immutable
result refs indefinitely by default. There is no expiry, background cleanup,
workspace prune, or workspace teardown command. `discard` removes an
authorized worker directory and its owned checkout state; it does not remove
the terminal worker record or a collected result ref. Consequently, workspace
metadata and canonical `refs/cws/` storage can grow until the user manages
them outside Clonegrown.

Run `clonegrown status` and inspect both `workers` and `issues`. A collected or
discarded worker's `result_ref` is the literal immutable ref to use from the
canonical repository. Before integration, verify that no `result-ref-missing`
or other custody issue names that worker. Normal Git can inspect it with
`git show`, `git log`, or `git diff`; it can also create a review branch at
that ref. After review, the user chooses whether the intended branch should
merge or cherry-pick the result. Clonegrown never chooses or performs that
branch mutation, and it does not infer from reachability that integration is
complete or that the retained evidence may be deleted.

Manual deletion of the workspace control directory or `refs/cws/` can strand
the other half of the custody record. Clonegrown 0.x intentionally provides no
shortcut for it. The minimum evidence currently required before a future
explicit prune or teardown operation could be added is recorded in
[Architecture](ARCHITECTURE.md#0x-retention-and-future-teardown-boundary).

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

Pass a stable request ID when a caller may retry the same spawn. A matching
retry rejoins an in-flight request or returns its existing ready, collected, or
discarded outcome. An `abandoned` or `spawn_failed` outcome makes that request
ID retryable and the next attempt allocates a new worker; a `broken` outcome
must be resolved before another retry. Spawns without a request ID always
create new workers:

```bash
clonegrown spawn "compare parser approach" --request-id parser-comparison-1
```

## Three kinds of worker

```bash
clonegrown spawn "add tests" --worktree   # linked worktree
clonegrown spawn "add tests"              # default clone; object files may be hard-linked
clonegrown spawn "add tests" --strong     # clone with physically separate object files at spawn
```

| | Separate working files | Separate refs, stash, local config, default `.git/hooks` | Separate object files | Provisioning work |
|---|---|---|---|---|
| `--worktree` | yes | no | no | register a worktree and check out files; repository-dependent |
| clone (default CLI mode) | yes | yes | no | make a local clone and check out files; repository-dependent |
| `--strong` | yes | yes | yes, at spawn | copy and repack the object database, then check out files; repository-dependent |

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
hook location matter. A preserved historical experiment ran eight concurrent
`git gc --prune=now` commands: all eight clone commands succeeded, while one
of eight linked-worktree commands succeeded because the others could not take
the shared repository's garbage-collection lock; no repository corruption was
observed. [`research/FALSIFICATION.md`](research/FALSIFICATION.md) records Git
2.47.3 but not that run's exact source revision, operating system, or Python
version, and its original inputs are absent, so the result is historical and
cannot be reproduced byte-for-byte from this checkout. The retained current
`tests/campaign/gc_compare.py` harness can produce a new package-specific
measurement.

Choose `--strong` only when physical object independence at spawn matters. It
copies the object database, so histories with many objects cost more time and
disk; it is not an operating-system boundary against later external linking or
mutation.

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

## Intended safeguards and current checkpoint gaps

Except where the qualification warning above names an open deviation, these
safeguards are implemented and covered by the recorded tests. The warning and
cold-review record take precedence over any affected statement in this
section.

- Workers start from an explicitly resolved and pinned commit.
- The complete generated task branch is validated by Git before allocation
  advances its counter or creates a ref, record, request index, stage, or
  worker slot. An invalid result such as a `.lock` suffix leaves no allocation
  evidence behind.
- Worker allocation and lifecycle metadata updates use workspace and worker
  locks.
- The Python API and the CLI both refuse a selected workspace path that is
  itself a symlink, leaving the link and its target untouched; a symlink
  higher up the selected path is followed, and the workspace is recorded at
  its resolved location. Init then
  refuses symlinked workspace-control and canonical-marker parents before
  creating children or writing markers through them. Collection and normal
  deletion authenticate the published worker path and marker before acting on
  it; dangling slot symlinks count as occupied paths, never absence. A
  request-index hit is validated field by field and its settled worker and any
  retained discarded result are authenticated before return.
- Collection compares snapshots before and after fetch, fetches the candidate
  object without a destination ref, then creates its content-addressed result
  ref only if absent. An existing exact result is reused; a direct or symbolic
  conflict is refused without overwrite. A change detected between the worker
  snapshots is not accepted as collected. Git prepared transactions lock the
  result and summary refs while Clonegrown checks their raw types, commits the
  summary, and then holds both expected values stable across the collected
  metadata write. If a fetch child finishes after its parent dies but before
  ref creation, recovery may create the absent ref with the same
  compare-and-swap and accepts it only if the worker still matches; any ref
  conflict remains untouched.
- Every published-worker deletion requires an explicit lease release first; neither
  `--abandon` nor `--force` overrides the lease, and recovery never infers a
  release from a dead process. Normal deletion requires a collected result;
  deleting an uncollected worker requires explicit `--abandon`; detected
  post-collection drift requires explicit `--force`; a collected worker's
  Git-ignored paths require explicit `--discard-ignored`; and changed or
  unverified clone-private refs, direct or symbolic and whether or not a
  symbolic target exists, require explicit `--discard-private-refs`.
  A collected worker cannot be abandoned or claimed again. A failed
  unpublished spawn owns no published worker and has no releasable lease;
  discarding its authenticated residue still requires `--abandon`.
- Deletion goes through an authenticated quarantine: intent is recorded, the
  worker is fingerprinted, its slot is renamed to `.cws/quarantine/`, the
  quarantined worker is authenticated and rechecked against the fingerprint,
  deleted with errors enabled, and proved absent. A change before deletion
  preserves the intact worker in quarantine. An error or interruption after
  authorized recursive deletion begins can leave a partial remainder there;
  the record says deletion is incomplete rather than calling that remainder
  intact. `status` reports the retained path and reason, `recover` resumes it,
  and a repeated `discard` with the same acknowledgement deletes an intact
  quarantine whose earlier recheck failed (a quarantined worktree whose admin
  directory Git has since pruned is fingerprinted without Git for that
  deletion). Content found both
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
  authorizes deleting everything, ignored content included. A worker
  preserved in quarantine is asked every category again against the
  quarantined content before a second `discard` deletes it, one missing
  category per refusal, and no normal deletion resumes or is re-authorized
  while the collected result is no longer preserved in canonical. A
  collected worker whose result ref disappears is never marked `broken` for
  that alone: `recover` re-creates the ref from the recorded identity when
  the object is still present and the name is free, and otherwise reports it
  and leaves the worker collected and undeleted. A `broken` worker that
  still records a collected result keeps that result audited by `status`
  until it is abandoned. A quarantined worktree whose admin directory was
  pruned needs `--discard-ignored` because its ignored paths cannot be
  enumerated; a quarantined clone whose Git directory no longer works is
  refused outright and stays in quarantine for manual inspection.
- A clone records a raw inventory of its non-task refs at publication:
  `for-each-ref` for everything that resolves plus a walk of the loose ref
  files under `refs/`, so a symbolic ref is recorded by its target whether or
  not that target exists. Pseudo-refs outside `refs/` such as `ORIG_HEAD`,
  `FETCH_HEAD`, and `MERGE_HEAD` are not refs and are not in the baseline;
  a commit reachable only from one of them is not protected by it. Normal collected-clone discard compares that inventory,
  including `refs/stash`, and refuses differences or an absent baseline
  without `--discard-private-refs`. A clone whose refs are not stored as files
  (`extensions.refstorage` other than `files`) has no raw walk and fails
  closed the same way. The
  assigned task branch remains covered by the result and drift checks. This ref
  baseline does not inspect or preserve other changes inside `.git`, such as
  later local-config or hook edits; review any such clone-private setup before
  authorizing deletion.
- The work lease is cooperative. A process that ignores it, or keeps file
  descriptors open across a release, can still write after the final
  fingerprint. The fingerprint covers Git's status listing plus the size and
  modification time of every entry in the worker directory tree except
  `.git` (nested repositories, FIFOs, and sockets included), and for clones it
  also covers the same raw ref inventory, dangling symbolic refs included; a
  non-ref `.git` change or a file-tree rewrite that keeps both size and
  timestamp is not detected.
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
  no-op judged by the rewrite policy the original collection recorded, so a
  repeat after `--allow-rewrite` needs no flag, while new commits or a new
  rewrite after collection are rejected under any argument. Ancestry is
  judged by object content: replace refs and graft files, whether inherited
  through the environment or planted inside the worker, are ignored, and the
  judgement is repeated on canonical's copy of the objects after the fetch,
  again by recovery before it finishes an interrupted collection, and by
  `status`, which reports drift for a collected result canonical cannot
  confirm. Start a new worker for new work.
- Clonegrown provides Git-state separation, not an operating-system sandbox.
  An unrestricted process can traverse into other directories.
- Worktree workers share broad Git state. Default clones separate refs, stash,
  local config, and the default private hook location, subject to the configured
  `core.hooksPath` caveats above; they may also share existing object files
  through hard links. Only `--strong` supplies physical object-file
  independence at spawn, and neither clone mode is an operating-system
  sandbox.

The intended target custody contract is recorded in [`PLAN.md`](PLAN.md) and
[Architecture](ARCHITECTURE.md#target-custody-contract--intended-checkpoint-not-qualified):
a durable cooperative lease, explicit acknowledgement for ignored content,
authenticated quarantine before checked deletion, one-shot workers after
collection, and explicit integration. The qualification notice above records
the six deviations repaired on this tree and the review still required before
this contract is called implemented.

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

Current-package and frozen-prototype results are separate evidence sets:

- **Current package, latest local deterministic result.** On 2026-08-29 the
  uncommitted Phase 6 package tree based on Git commit
  `354d16bc662f15f65dded911d3c26729bf5804aa` passed 226/226 unit and
  destructive tests on Linux with CPython 3.12.3 and Git 2.43.0, and again
  with exact Git 2.29.0. Clone and worktree hardening each exercised 56
  passing cases, conditionally skipped the unavailable reftable case, and had
  zero failures. The precise local-diff boundary, commands, durations, and
  result hashes are recorded in
  [`research/PLAN-ARCHIVE.md`](research/PLAN-ARCHIVE.md) and
  [`HANDOFF.md`](HANDOFF.md); [`PLAN.md`](PLAN.md) retains the current release
  boundary. The current harnesses can rerun those checks,
  but their timestamped `/tmp` output is not a checked-in byte-for-byte
  reconstruction artifact.
- **Current package, fresh-agent simulation.** On 2026-09-02 a fresh agent
  using only the installed skill completed three independent worker
  lifecycles, separate Git integration, and recovery from a parent-SIGKILLed
  fourth spawn without human workflow correction or a status issue. The
  complete single-run record and its limitations are in
  [`research/ORCHESTRATOR_SIMULATION.md`](research/ORCHESTRATOR_SIMULATION.md).
  This qualitative run is not a paired comparison or a universal behavior
  claim.
- **Current package, latest hosted blocking result before this local tree.**
  GitHub Actions run 33278590221 passed all seven blocking jobs at committed
  revision `354d16bc662f15f65dded911d3c26729bf5804aa`: Ubuntu and macOS at
  Python 3.11/latest stable, exact Git 2.29.0, and both hardening modes. That
  revision changes only the Phase 5 completion records from the earlier
  `a2ae7793` executable tree; it does not include the local Phase 6–7 changes.
  Scheduled randomized run 33638194991 is the latest hosted randomized result
  observed before this release qualification and passed at the same revision.
  Commands and retained-artifact limitations are in
  [`research/REPRODUCE.md`](research/REPRODUCE.md).
- **Preserved historical prototype.** [`research/REPORT.md`](research/REPORT.md)
  describes the absent `cws.py` candidate at source commit `be4391c` on Linux
  6.18.35 x86_64 with Git 2.47.3 and Python 3.13.5.
  [`research/REPRODUCE.md`](research/REPRODUCE.md) identifies which original
  inputs are missing, so the preserved `research/RESULTS.json` cannot be
  rebuilt byte-for-byte from this checkout.

These checks establish the recorded lifecycle behavior only for their stated
fixtures and environments. They do not establish universal performance or
that coding agents make fewer mistakes or require less human intervention
with Clonegrown.

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
only for a clone whose object files must start physically independent;
`mode="worktree"` uses the default `strong=False`, and the API rejects the
incompatible combination of worktree mode with `strong=True`.

[`ARCHITECTURE.md`](ARCHITECTURE.md) describes the package layout, durable
state, current recovery behavior, and implemented custody contract.

## Release and license

Clonegrown 0.x is alpha software. Its supported package envelope is Python
3.11 or newer on Linux and macOS with Git 2.29.0 or newer; native Windows and
the additional unvalidated environments listed above remain outside support.

Clonegrown is distributed under the Apache License, Version 2.0
(`Apache-2.0`). See [`LICENSE`](LICENSE) for the complete terms.
