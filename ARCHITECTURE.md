# Architecture

Clonegrown manages a canonical Git checkout, a workspace of isolated workers,
and explicit collection, release, discard, and recovery. It does not integrate
results into user branches. The Python package uses only the standard library;
Git is an external executable. [README.md](README.md) covers use and limits.

## Modules

| Module | Responsibility |
| --- | --- |
| `core.py` | Sanitized Git execution, errors, atomic JSON, locks, repository discovery |
| `state.py` | Workspace and worker records, validation, identity, derived paths and refs |
| `repository.py` | Clone provisioning, ref transactions, ancestry, worktree Git operations |
| `worker.py` | Worker authentication, snapshots, allocation, quarantine and removal |
| `audit.py` | Workspace, worker, request-index, and ref invariants |
| `recovery.py` | Reconcile recorded checkpoints and assemble status |
| `lifecycle.py` | Init, spawn, collect, release, claim, discard |
| `cli.py` | Arguments, discovery, public JSON and errors |
| `__init__.py`, `__main__.py` | Public API and module command entry point |

Dependencies flow from CLI/lifecycle/recovery toward worker/repository/state
and then core. Status and recovery share audit checks. The lifecycle modules
remain cohesive; state transitions are explicit in their command bodies.

## Platform and Git boundary

Python 3.11+ and Git 2.29.0+ on Linux/macOS are supported. The protocol needs
POSIX advisory locks, hard links for create-only record publication, and atomic
same-filesystem renames. Native Windows and network/distributed filesystems
are unsupported. Genuine disk/inode exhaustion is unvalidated; tests inject
`ENOSPC`, `EXDEV`, and deletion `EIO` at represented boundaries.

`require_files_ref_backend` asks Git for `rev-parse --show-ref-format`.
Git versions predating that option echo it; those versions use repository-local
`extensions.refStorage`, with its absent value meaning files. Canonical
validation and worker authentication reject any other backend before mutation.
Raw ref inspection below assumes files storage; reftable is deliberately
unsupported, including a repository migrated after workspace creation.

Git selection prefers `CLONEGROWN_GIT`, then `/usr/bin/git`, then `PATH`.
Child Git processes receive no inherited `GIT_*` variables except the reviewed
author/committer identity/date allowlist; `SSH_ASKPASS` is also removed.
Global and system configuration still apply. Arguments are arrays, never shell
commands. Ancestry judgments additionally disable replace refs and graft files
inside both worker and canonical repositories.

Git 2.29 supports the required fetch and worktree-repair operations. Its
`update-ref` acknowledgements are not flushed to pipes: prepared transactions
use a pseudo-terminal for those versions so preparation is positively
acknowledged before raw inspection. Lock-file existence alone is not evidence
of preparation. Newer Git uses a pipe. Worktree checkout enumeration falls
back from NUL-delimited to line-oriented porcelain when the older Git rejects
`-z`. Sparse worktree-local flags are explicitly copied where Git 2.29 does
not initialize them.

## Durable layout and validation

For canonical `app`, the default workspace is its sibling `app-dev`:

| Path | Meaning |
| --- | --- |
| `.cws/state.json` | Schema 3 workspace identity, canonical path, next worker ID |
| `.cws/lock` | Workspace advisory lock |
| `.cws/workers/ID.json` | One worker record, including terminal records |
| `.cws/requests/DIGEST.json` | Request-ID index |
| `.cws/locks/ID.lock` | Per-worker operation lock |
| `.cws/staging/` | Private construction paths awaiting publication |
| `.cws/quarantine/ID-TOKEN/` | Authorized slot awaiting checked deletion |
| `ID/app/` | Published worker repository |

The original `cws` protocol spelling is retained for on-disk compatibility.
Canonical carries `.git/cws/WORKSPACE_ID.json` with the workspace's secret
token. A worker has `cws-worker.json` in its private Git directory. For a
worktree, that directory is canonical's `.git/worktrees/NAME`; its common Git
directory must be canonical's, and its recorded admin identity must match.

`WorkerRecord.validate` checks identity, types, required/forbidden fields for
each status, object-ID width, derived candidate/result refs, and consistent
lease/discard/quarantine fields before they select paths or refs. Unknown
extension keys round-trip. Older records without `mode` mean clone, and those
without a lease remain leased. A historical `heartbeat` key is retained as
unknown data but is neither written nor used for liveness.

Workspace/canonical authentication rechecks directory identities under the
lock. Canonical Git commands can run from an opened Git-directory descriptor
using child `fchdir`, avoiding reliance on Linux-only descriptor paths.
Selected init-workspace symlinks are refused before resolving the path;
ancestors may resolve to their real locations. Control and custody paths use
non-following regular-file/directory checks. Foreign occupants, including
dangling symlinks, are evidence rather than absence.

Metadata updates write and sync a temporary file before atomic publication.
New worker records use a hard link for create-only publication. Workspace
allocation is serialized; per-worker locks protect lifecycle operations.
These locks coordinate cooperating callers, not arbitrary writers.

## Allocation and spawn

Allocation resolves and pins the base commit, derives the task branch, and
asks Git to validate the complete branch name before advancing the counter or
creating allocation evidence. Task text is reduced to at most 48 lowercase
ASCII slug characters. Existing records, slots, stages, quarantines, locks,
or private refs at the next ID mean a stale counter and cause refusal. An
allocation that fails after advancing the counter can leave an unused ID.

A request index must match its literal request ID, parameter digest, worker
ID, and validated record. Matching retries rejoin an in-flight request or
return an authenticated ready, collected, or discarded result. Abandoned and
spawn-failed requests can allocate anew; broken requests require resolution.
The digest includes the mode so a retry cannot silently change isolation.

Spawn records `allocated`, `cloning`, `configuring`, and `publishing` as it
constructs a private stage, configures it, and atomically renames it into the
numbered slot. A published worktree needs `git worktree repair` after that
rename. Only then does the worker become `ready` with an active lease.

### Clone fidelity

A clone begins with `git clone --no-checkout`; strong adds `--no-hardlinks`.
Before applying configuration, an immutable plan validates every remote and
config key. Read failures abort rather than pretending configuration is empty.

| State | Provisioning contract |
| --- | --- |
| Remotes | Copy every effective repository-local occurrence in order; anchor relative local fetch/push paths to canonical; retain absolute paths, URLs, and scp-like syntax |
| Local config | Preserve valueless versus empty and ordered repeated values; flatten effective local includes without their directives; leave global/system config external |
| Repository shape | Derive core/extension/index/branch shape for the new repository instead of copying it blindly |
| Auxiliary refs | Snapshot resolvable `refs/remotes/`, `refs/notes/`, and `refs/replace/` by exact name and resolved object ID; do not copy stash or private custody refs |
| Info files | Copy `info/exclude` and `info/attributes` only |
| Sparse checkout | Copy effective sparse flags and required patterns |
| Hooks | Do not copy private `.git/hooks` programs; suppress hooks for provisioning checkout |
| Objects | Default clones may hard-link objects or retain alternates with a warning; strong repacks/removes alternates for physical independence at spawn |

The local canonical-source remote takes the first free `cws-source` name and
an invalid push URL as an accident guard. A remote lacking effective local
configuration is refused. Config keys containing canonical's resolved path
in any value are omitted with a warning. This substring check does not recognize
alternate symlink spellings or analyze containment. A copied `core.hooksPath`
can still refer outside the worker. Absolute paths warn, but tilde and relative traversal can resolve
outside without that warning. Strong mode does not change hook behavior.

Auxiliary refs are enumerated with their object IDs, fetched together through
standard-input refspecs, then packed only in the staged clone. Concurrent
canonical ref moves cannot change that snapshot; unavailable objects cause
failure. A symbolic remote ref is promised by name and resolved tip, not its
symbolic representation. Later canonical changes do not propagate.

Required clean/smudge filters are supported when the external driver already
exists. Tracked attributes select it, Git stores the cleaned blob, and checkout
materializes the smudged form. Clonegrown does not install drivers, initialize
submodules, or support Git LFS/filter-process/credentialed network filters.

A worktree uses `git worktree add --no-checkout --detach`, sharing canonical
refs, stash, config, hooks, and objects. Only sparse policy is copied. Its
record carries a compatibility warning. Worktree mode rejects strong mode.

## Ref ownership and collection

Canonical refs under `refs/cws/WORKSPACE_ID/` are:

| Suffix | Purpose |
| --- | --- |
| `bases/ID` | Pin the assigned base through spawn/recovery |
| `workers/ID/results/SHA` | Immutable collected result, named by its exact object ID |
| `workers/ID/result` | Accepted-result summary |
| `workers/ID/branch-owner` | Worktree task-branch creation evidence at the assigned base |

Every custody write uses no-dereference, expected-value or create-only
transactions. Raw files inspection rejects symbolic refs, filesystem
symlinks, FIFOs, malformed occupants, and chains that could redirect or block
Git. Prepared transactions hold the relevant Git ref locks while callers
check raw types. Direct refs must also have the value their recorded purpose
requires; an exact name or a resolvable value alone does not establish ownership.

For worktree spawn, task branch and ownership ref are created in one
transaction at the assigned base. An occupied name aborts both. During
cleanup, the branch is deleted only at its recorded cleanup tip with valid
ownership evidence and no other checkout (canonical included) using it.
Moved/checked-out branches remain reported; absent branches are not recreated
or deleted by name. Admin cleanup authenticates the recorded entry, including
its marker or pre-marker staged back-pointer, before removal. A name recycled
for another worker is not owned by the old record. Cleanup never runs blanket
worktree pruning.

Collection moves `ready` to `collecting`, snapshots the authenticated clean
worker, checks ancestry unless rewrite was authorized, and fetches its
candidate object without a destination ref. It checks the worker again and
publishes a create-only content-addressed result. An exact existing result
can be reused; conflicting values or types are preserved and refused. Ancestry
is rechecked using canonical's objects rather than trusting only the worker.

The summary is created under a prepared transaction. After Git commits,
`summary_published` is saved as durable provenance; the result and summary
values are held stable across the final `collected` record write. An ordinary
failure after publication keeps a recoverable collecting checkpoint. A crash
between summary commit and provenance write leaves an exact but unproven
summary: recovery reports it and refuses to adopt, replace, or delete it.
Manual inspection and removal of that specific conflicting summary are needed
before recovery can proceed. This narrow fail-closed gap is intentional.

A collected worker is one-shot. An identical repeat uses its recorded rewrite
policy and is a no-op; further changes are refused. Records and immutable
results survive discard indefinitely. No automatic prune or teardown exists.

## Lease, discard, and quarantine

The lease is an explicit cooperative handoff. `release` asserts all writers
stopped; `claim` reacquires only a released ready worker. Every published
worker needs release before deletion, with no flag override or dead-process
shortcut. Failed unpublished spawns have no releasable lease.

Normal discard requires a preserved collected result. An uncollected worker
needs `--abandon`; post-collection drift needs `--force`; ignored content needs
`--discard-ignored`; changed/unverified clone-private refs need
`--discard-private-refs`. These categories remain independent. A clone's raw
private-ref baseline includes direct and dangling symbolic refs under `refs/`
except its assigned task branch. It excludes pseudo-refs and non-ref `.git`
changes. Old records without a baseline require acknowledgement.

Discard records intent and a fingerprint before renaming the complete numbered
slot to its authenticated quarantine. It reauthenticates and compares the
fingerprint before recursive deletion, enables deletion errors, then proves
the slot, stage, quarantine, and owned worktree state absent before recording
`discarded` or `abandoned`.

The fingerprint includes Git status; entry type, size, and modification time
outside the worker's `.git`; slot siblings; and, for clones, raw private refs.
Symlinks are not followed, and FIFO/socket entries are represented without
reading them. Same-size/same-timestamp rewrites and later non-ref `.git`
changes remain outside this detection. Slot siblings are deleted and
fingerprinted but have no separate content-category acknowledgement.

A failed pre-deletion check preserves an intact quarantine. A later discard
must reauthorize its current categories; a missing collected result still
blocks deletion. A pruned worktree admin directory prevents ignored-content
inspection and therefore requires that acknowledgement. An unreadable
quarantined clone is refused. Once durably authorized deletion has begun,
an error or crash can leave a partial remainder; recovery may finish that
recorded deletion. No fingerprint or lease prevents an uncooperative process
from writing after the final check.

## Recovery and audit

Recovery inspects durable status and the recorded operation owner's liveness
(PID and a Linux process-start fingerprint where available), then reconciles
only proven transitions. It continues past corrupt records and per-worker
failures. It does not infer lease release.

| Recorded condition | Action |
| --- | --- |
| Interrupted unpublished spawn | Clean only authenticated staging and owned worktree state |
| Interrupted published spawn | Repair/authenticate; promote untouched worker to ready, preserve changed worker as broken |
| Interrupted collection | Preserve candidate; finish only with unchanged worker, valid ancestry, and owned/free refs |
| Pending discard | Withdraw untouched unfulfilled intent or resume recorded quarantine/deletion authorization |
| Collected result missing | Restore only from recorded available object into a free name; otherwise report and preserve worker |
| Missing summary | Repair from a verified retained result, subject to ownership rules |
| Stale base pin | Delete only when status no longer needs it and its value matches the recorded base |
| Foreign/orphan evidence | Report and retain refs, stages, paths, and invalid request indexes; remove an orphan advisory lock for an ID with no record |

A foreign ref preventing safe Git inspection leaves the worker untouched and
reported. Recovery covers recorded lifecycle checkpoints, not every possible
filesystem or machine-failure boundary. `status` audits the same custody
model without repairing records, refs, content, or Git indexes. Acquiring its
workspace lock can recreate a missing control file.

## Command output

Lifecycle success is JSON on stdout; help/version are text. Argument/runtime
errors use stderr with exit 2 and empty stdout. Python returns full internal
dictionaries. The CLI recursively removes secret and bookkeeping fields and
renders timestamps as ISO 8601 UTC. `cli.public_result` defines that projection;
`tests/test_cli.py::test_output_contract` pins the exact public key sets.

Worker output identifies ID, status, mode, path, branch, base, and lease;
collection adds result SHA/ref and rewrite policy. Failure and quarantine
fields remain visible when relevant. Status returns `workspace`, `canonical`,
`workspace_id`, `workers`, and `issues`; each issue has an `issue` code and
bounded ID/path/ref/error context. Worker `drift` is separate from that list.
The exact issue cases are defined in `audit.py` and covered by
`tests/test_audit.py`. Recover returns action reports with optional context.

Init/spawn/collect/discard/recover failures carry operation/stage, last known
durable state, preservation confidence, recovery action, and cause. Diagnostic
checkpoints describe meaningful boundaries; rollback paths derive their final
message from observed custody. A primitive that raised is not assumed to have
completed. Ordinary exceptions are wrapped with their cause chained;
process-control exceptions pass through. Recovery failures retain the same
context in their reports.

`CommandFailure` retains private raw diagnostics for deliberate Python
inspection but displays redacted output. Known config values, remote URLs,
URL userinfo, and custody path tokens are removed from public/durable errors;
arbitrary diagnostic text is not generally secret-scanned. Successful status
retains literal `quarantine_path` as recovery evidence while hiding the
separate token field.

## Installation

The package uses setuptools and a conventional `clonegrown.cli:main` entry
point. Ordinary `uv`, `pipx`, or environment-specific `pip` installation owns
the executable and its environment. No runtime dependencies are added.

The optional `install.sh` runs `uv tool install --reinstall` on its checkout,
then copies the skill to the two documented agent locations. It preflights
both destinations, opens directories without following symlinks, checks their
identities after the package step, exclusively creates missing files, and
leaves matching existing files alone. Differing files and unsafe occupants
are refused. It never deletes, backs up, or transactionally replaces trees.
Partial success is reported honestly and kept. Legacy custom-install settings
and migration are unsupported; the user reviews old paths manually.

## Development and tests

Run from the checkout:

```bash
python3 -m compileall -q clonegrown tests
python3 -m unittest discover -s tests -v
sh -n install.sh
CWS_SUITE_MODE=clone python3 tests/campaign/hardening_suite.py
CWS_SUITE_MODE=worktree python3 tests/campaign/hardening_suite.py
```

Campaigns use disposable repositories. Set result paths outside the source
checkout. For deterministic bounded replay:

```bash
CWS_SUITE_MODE=clone python3 tests/campaign/state_machine_fuzz.py --start 10 --seeds 2 --steps 50 --output /tmp/clonegrown-state.json
CWS_SUITE_MODE=worktree python3 tests/campaign/random_kill.py collect --start 10 --count 2 --output /tmp/clonegrown-kill.json
```

Repeat for each mode and spawn/collect/discard interruption. Failure records
include seed, replay command, environment, and source identity. The state
machine independently models private refs and proves that changed refs cannot
be silently discarded. Focused tests also inject broken behavior to establish
that the model detects invalid states.

CI runs full unit/destructive checks and package install/help/version/uninstall
on Linux and macOS with Python 3.11 and the latest stable 3.x. Hardening runs
both modes on both operating systems. A pinned Git 2.29.0 build runs the full
unit suite and both hardening modes. Reftable-rejection fixtures skip only
when the selected Git cannot create that format; those skips are not passes.
The scheduled workflow supplies broader deterministic randomized campaigns.
Current completion is tracked in [PLAN.md](PLAN.md); the dated material in
[docs/archive](docs/archive/README.md) is historical evidence only.
