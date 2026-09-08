# Clonegrown

**Per-task Git working directories for coding agents.**

Clonegrown creates a worker for each task, records its lifecycle, and preserves
its clean committed result in the canonical repository. A worker is a local
clone or linked worktree. Collection preserves a commit; integration into a
user branch is a separate Git operation.

Clonegrown 0.x is alpha software. Final qualification of this stabilization
candidate is pending; see [PLAN.md](PLAN.md) for the current gate. The
supported operating-system targets are Linux and macOS. The lease that guards
deletion is cooperative: do not use unattended cleanup for valuable work.

## Requirements

Git 2.29.0 or newer and Python 3.11 or newer are required. Both the canonical
repository and clone workers must use Git's traditional **files ref backend**.
Reftable is explicitly unsupported and is rejected before workspace or worker
mutation. A workspace needs a local POSIX filesystem supporting hard links,
advisory locks, and same-filesystem atomic renames.

Native Windows is explicitly unsupported in 0.x. Network/distributed
filesystems, partial clones, initialized/recursive submodules, Git LFS,
long-running filter-process drivers, and credentialed/network filters are
outside the supported envelope. Ordinary required clean/smudge filters work
when their external driver is already installed; Clonegrown does not install
or sandbox that program. Submodule gitlinks are retained without initializing
the submodules. Disk/inode exhaustion has only injected-failure coverage.

Clonegrown prefers `/usr/bin/git` when it exists. To select another installed
Git, set `CLONEGROWN_GIT` to that executable's absolute path.

## Install


Git 2.29.0 or newer and Python 3.11 or newer are required.
Install the CLI with ordinary Python tool packaging:

```bash
uv tool install git+https://github.com/kserrec/clonegrown.git
clonegrown --version
clonegrown --help
```

`pipx install git+https://github.com/kserrec/clonegrown.git` is an alternative.
Use the same manager to update or uninstall the package:

```bash
uv tool upgrade clonegrown
uv tool uninstall clonegrown
```

The optional source-checkout helper also installs the bundled skill:

```bash
git clone https://github.com/kserrec/clonegrown.git
cd clonegrown
sh install.sh
```

It requires `git`, `uv`, and Python 3.11+ on `PATH`. It delegates package
installation/update to `uv tool install --reinstall` using that checkout and
Python interpreter, then installs `SKILL.md` at both
`~/.claude/skills/clonegrown/SKILL.md` and
`~/.agents/skills/clonegrown/SKILL.md`. Restart the agent app afterward.
Use `uv tool update-shell` if uv's executable directory is not on `PATH`.

The helper creates absent skill directories and keeps byte-identical skills.
It refuses symlinks, non-regular files, unexpected existing directories, or a
differing skill before package installation; it also rechecks destinations
afterward. Review a differing skill yourself before moving it aside and retrying.
Other files in a matching skill directory are preserved. Completed steps stay
installed if a later step fails; there is no custom rollback or backup protocol.
Package uninstall does not remove the separately copied skills.

The helper does not migrate old custom installations. Review any old command
wrapper and skill directories yourself before moving them aside. Legacy
`CLONEGROWN_HOME`, `CLONEGROWN_BIN_DIR`, `CLONEGROWN_REPO_URL`, and
`CLONEGROWN_REF` settings are refused; use the tool manager's options instead.

## Lifecycle

The **canonical repository** is the original checkout. Its **workspace** holds
numbered task slots and lifecycle records. For a checkout named `app`, the
default workspace is the sibling `app-dev`, and worker 1 lives in
`app-dev/1/app`. Run from the canonical checkout to initialize and allocate:

```bash
clonegrown init
clonegrown spawn "fix the authentication race"
```

Spawn prints JSON with the worker ID, path, task branch, and resolved base
commit. Work in that returned repository, test the changes, and commit the
result. Preserve its clean committed tip with the returned ID:

```bash
clonegrown collect 1
```

Collection writes an immutable `result_ref` and a summary ref in canonical;
it never merges, rebases, cherry-picks, or moves a user branch. Inspect the
literal `result_ref` with Git and explicitly choose any integration operation.
A collected worker is one-shot: collecting its unchanged tip again is a no-op;
new work requires a new worker.

After stopping **every process that can write to the worker**, release its
cooperative lease and remove the collected worker:

```bash
clonegrown release 1
clonegrown discard 1
```

Release records your assertion that the worker is quiet; Clonegrown cannot
verify it. No discard flag overrides an active lease. A released worker still
in `ready` can be claimed again with `clonegrown claim 1`; a collected worker
cannot. A failed unpublished spawn has no releasable lease, but removing its
authenticated residue still requires `--abandon`.

Discard refuses content outside the accepted result unless you explicitly
authorize its destruction. Flags have separate meanings:

| Option | What you authorize |
| --- | --- |
| `--abandon` | All content of an uncollected worker; refused for collected workers |
| `--force` | Detected changes after collection |
| `--discard-ignored` | A collected worker's Git-ignored content |
| `--discard-private-refs` | A collected clone's changed private refs, or refs without a verifiable baseline |

Use only the flags justified by the reported refusal and your intent. A refusal
lists bounded samples of path or ref names, never file contents.

### Worker modes and retries

| Mode | Working files | Refs, stash, local config, default hooks | Object files |
| --- | --- | --- | --- |
| Default clone | Separate | Separate | May use hard links or alternates |
| `--strong` clone | Separate | Separate | Physically separate at spawn |
| `--worktree` | Separate | Shared with canonical | Shared with canonical |

Use a worktree for short-lived tasks or large histories when shared Git state
is acceptable. Use a clone when separate refs, stash, and configuration matter.
Strong clones copy the object database and cost more time and disk. None of
these modes is an operating-system sandbox.

Spawn starts from canonical `HEAD` unless `--base` names another ref or commit.
It pins the resolved commit before provisioning; it assumes no branch name.
A stable `--request-id` makes matching retries rejoin an in-flight allocation
or return its ready, collected, or discarded outcome. An `abandoned` or
`spawn_failed` outcome permits a new allocation; a `broken` outcome must be
resolved first. Without a request ID, every spawn creates a new worker.

### Safety boundary

- Collection checks the task branch, clean tracked/untracked state, absence
  of in-progress Git operations, and descent from the assigned base. An
  intentional history rewrite needs `collect --allow-rewrite`. Later identical
  collection uses that recorded policy; new post-collection commits are refused.
  Ancestry checks ignore replace refs and graft files in both repositories.
- Collection omits ignored paths. Discard checks them separately. Clone
  private-ref custody covers all names under `refs/` except the task branch,
  including stash and dangling symbolic refs. It does not protect pseudo-refs
  such as `ORIG_HEAD` or `FETCH_HEAD`, later local-config/hook edits, or other
  non-ref `.git` changes. Review that setup before deletion.
- Discard authenticates the worker, records intent, moves the whole numbered
  slot into quarantine, rechecks it, and deletes it with errors enabled.
  Changes detected before deletion preserve the intact quarantine. An error
  or interruption after authorized deletion begins can leave only a partial
  remainder. The record is terminal only after directory and owned worktree
  cleanup are proved complete.
- The final fingerprint includes Git status and each non-`.git` tree entry's
  type, size, and modification time; clones also include private refs. A
  rewrite preserving size and timestamp can escape detection. A process
  ignoring the lease can write after the final check. Files beside the worker
  repository inside its numbered slot are included in deletion and fingerprinting
  but are not separately checked for drift or ignored-content acknowledgements.
- Worktrees share refs, config, stash, hooks, and objects with canonical.
  Clones copy eligible repository-local config and a snapshot of auxiliary
  refs. Private `.git/hooks` programs are not copied, but a configured
  `core.hooksPath` can still point outside the worker. Absolute values warn;
  tilde or relative traversal can also resolve outside without a warning.
  Filters and configuration may run trusted external commands during Git work.
- Clonegrown's canonical-source remote has an invalid push URL as an accident
  guard. It does not prevent arbitrary Git commands or access to other folders.
- Error output redacts known config values, remote URLs, URL userinfo, and
  private staging/quarantine tokens. Other diagnostic text remains visible;
  review it before sharing publicly. Successful status output intentionally
  retains the full quarantine path for recovery.

[ARCHITECTURE.md](ARCHITECTURE.md) describes authentication, ref transactions,
clone fidelity, and the on-disk contract in more detail.

## Recovery and retention

```bash
clonegrown status
clonegrown recover
clonegrown status
```

`status` audits recorded invariants without repairing worker records, refs,
content, or Git indexes. Taking the workspace lock can recreate its missing
control file. Inspect both `workers` (including `drift`) and `issues`; this is
not a general filesystem-integrity scan.

`recover` reconciles represented checkpoints and may finish an already
recorded deletion. It never infers lease release from a dead process. An
untouched published worker from an interrupted spawn becomes `ready`; a
changed one is preserved as `broken`. Unauthenticated paths or foreign refs
are reported and retained. Recovery is limited to recorded transitions, not
every possible filesystem interruption.

An interrupted collection keeps its candidate. Recovery accepts a summary
already at that candidate only when a durable marker proves this attempt
published it. A crash between the Git commit and marker write therefore
requires manual inspection; an exact but unproven summary is reported and
left untouched. After verifying and removing only the reported conflicting
summary, retry recovery. Never remove custody evidence simply to silence an
issue.

An intact quarantine whose checks failed can be retried with `discard` after
authorizing each currently required category again. A partially deleted
quarantine resumes only from its durable authorization. A quarantined worktree
whose Git admin directory was pruned needs `--discard-ignored` because that
content cannot be enumerated; an unreadable quarantined clone is retained.
Status reports `quarantine_path` and `quarantine_error`. Do not remove a worker
or quarantine manually.

A moved or checked-out worktree task branch is retained and reported; cleanup
never forces it. Resolve the named branch or checkout conflict before retrying
recovery. Missing collected result refs can be restored only when their
recorded objects remain available and their names are free.

Worker records and collected immutable result refs are retained indefinitely
in 0.x, including after discard. There is no expiry, background cleanup, prune,
or workspace teardown command. Manually deleting workspace records or
`refs/cws/` can strand the other half of the custody evidence.

## Commands and API

| Command | Purpose |
| --- | --- |
| `init [canonical]` | Bind a workspace to the original checkout |
| `spawn "task"` | Allocate a clone; accepts `--base`, `--strong`, `--worktree`, `--request-id`, `--wait-seconds` |
| `collect ID` | Preserve the result; `--allow-rewrite` acknowledges changed ancestry |
| `release ID` | Record that writers stopped and permit deletion |
| `claim ID` | Reacquire a released ready worker |
| `discard ID` | Remove an authorized worker; separate flags acknowledge extra custody categories |
| `status` | Audit the workspace and workers |
| `recover` | Reconcile recorded interrupted operations |

All accept `--workspace`. Discovery works from the conventional canonical
checkout, workspace, or worker; use an explicit path for nonstandard layouts.
`clonegrown COMMAND --help` gives exact options. Successful lifecycle commands
print JSON. Errors print to stderr and exit 2. `python -m clonegrown` is the
same interface.

The standard-library-only Python API exports `init_workspace`, `spawn`,
`collect`, `release`, `claim`, `discard`, `recover`, `status`, and
`ClonegrownError`. It accepts `Path` objects and returns full internal
dictionaries; CLI output removes secrets and transaction bookkeeping.
`spawn(workspace, "HEAD", "task")` defaults to a non-strong clone; add
`mode="worktree"` or `strong=True` for the other modes. Worktree plus strong
is rejected. See [the architecture](ARCHITECTURE.md#command-output) for the
output contract and [development checks](ARCHITECTURE.md#development-and-tests).

## License

Clonegrown is distributed under the Apache License, Version 2.0
(`Apache-2.0`). See [LICENSE](LICENSE).
