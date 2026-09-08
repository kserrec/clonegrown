---
name: clonegrown
description: Use Clonegrown to create, collect, recover, and remove per-task Git working directories for parallel or delegated coding-agent work, with linked-worktree and local-clone modes.
---

# Clonegrown

Use Clonegrown when a task needs its own Git working directory and the
repository owner has authorized this alpha tool. It records worker lifecycle
and preserves clean committed results in canonical. Collection does not
integrate those results into a user branch. The current stabilization
candidate's qualification is tracked in the source repository's `PLAN.md`.

Use the `clonegrown` command for lifecycle operations. Never manually reproduce
its marker, ref, remote, or worktree-admin protocol, and never delete a worker
or quarantine by hand. Do not inspect dotenv files when assessing ignored
content; ask the user to handle those files without sharing their contents.

## Supported boundary

Git 2.29.0+, Python 3.11+, Linux/macOS, and local POSIX filesystems are required.
Both canonical and clone workers must use files-based refs; reftable is
unsupported and refused. Native Windows, network/distributed filesystems,
partial clones, initialized/recursive submodules, Git LFS, and long-running or
credentialed/network filters are outside support. Ordinary clean/smudge filters
need their external driver already installed. Clonegrown does not sandbox it.

The default worker is a local clone with separate refs, stash, local config,
and default `.git/hooks`; object files may be hard-linked or borrowed through
alternates. `--strong` gives physically independent object files at spawn,
with extra copying cost. `--worktree` shares canonical refs, stash, config,
hooks, and objects. None is an operating-system sandbox.

Clone config preserves ordered local values and flattened includes; relative
local remote paths are anchored to canonical. Private hook programs are not
copied, but a copied `core.hooksPath` can still resolve outside the worker.
Absolute values warn; tilde or relative traversal may not. Treat such hooks
as shared until their resolved location is known. The invalid push URL on the
canonical-source remote guards accidents only; never intentionally push there.

## Workflow

1. Initialize from the canonical checkout if needed: `clonegrown init`.
   The default workspace is the sibling `REPO-dev`. Discovery works from the
   conventional canonical checkout, workspace, or worker. Use `--workspace`
   for an explicitly selected nonstandard layout.
2. Allocate with `clonegrown spawn "short task description"`. It starts at
   pinned canonical `HEAD`; `--base` selects another commit/ref. Choose
   `--worktree` when shared Git state is acceptable or `--strong` when physical
   object independence matters. Report and use the returned worker path/ID.
3. Work only in that worker, test, and commit the desired result. Do not assign
   unrelated tasks to one worker or two tasks to its branch. In a worktree,
   do not alter shared config, branches, or stash belonging to others.
4. Stop writers and run `clonegrown collect ID`. This preserves a clean
   committed tip. Use `--allow-rewrite` only for an authorized history rewrite.
   Report the commit and immutable `result_ref`. Integration is a separate
   explicit Git operation authorized by the user.
5. After every agent, watcher, server, and other writer has stopped, run
   `clonegrown release ID`. Release records your assertion; Clonegrown cannot
   verify it. Collection does not itself require release.
6. Run `clonegrown discard ID` to remove the collected worker. Stop on a
   custody refusal and report what the user must decide. Do not bypass it
   merely to finish cleanup.
7. After interruption or uncertain durable state, run `clonegrown status`,
   then `clonegrown recover` when reconciliation of recorded intent is
   appropriate, then inspect status again. Recovery can finish an already
   authorized deletion; it is not a read-only diagnostic.

For retrying callers, a stable `--request-id` rejoins a matching in-flight
spawn or returns the existing ready/collected/discarded outcome. Abandoned or
spawn-failed outcomes can allocate anew; broken outcomes need resolution.
Spawns without a request ID always create new workers.

## Custody rules

- No deletion flag overrides the lease. Recovery never interprets a dead
  process as lease release. A released ready worker can be taken over with
  `claim`; collected workers cannot be claimed or reused. An unchanged repeat
  collection is a no-op using the recorded rewrite policy; later commits are
  refused under any option. Spawn a new worker for new work.
- `--abandon` authorizes all content of an uncollected worker, ignored content
  included. It is refused for a collected worker. Failed unpublished spawn
  residue has no releasable lease but still needs this acknowledgement.
- `--force` authorizes detected changes after collection. It does not authorize
  ignored content or changed clone-private refs. Obtain authorization for the
  detected changes before using it.
- `--discard-ignored` authorizes a collected worker's ignored paths. Collection
  never inspects them. Report the bounded names from the refusal; obtain
  authorization for their destruction without opening dotenv files.
- `--discard-private-refs` authorizes changed clone-private refs, including
  stash and dangling symbolic refs, or an older record without a verifiable
  baseline. Report the affected names before seeking authorization. Pseudo-refs
  such as `ORIG_HEAD`/`FETCH_HEAD`, local-config/hook edits, and other non-ref
  `.git` changes are not protected by that baseline; review private setup
  before deletion.
- The deletion unit is the whole numbered slot, including files beside its
  repository. Such siblings are fingerprinted but have no separate content
  acknowledgement. Do not store unrelated work there.
- The lease is cooperative. A process ignoring it can write after the final
  check. The fingerprint records Git status and entry type/size/mtime outside
  `.git`, plus clone refs; same-size/same-timestamp rewrites can evade it.
  Do not use unattended cleanup for valuable work.

## Recovery and reporting

An interrupted published spawn is promoted to ready only when untouched;
changed work is preserved as broken. If a foreign ref prevents inspection,
recovery reports failure and retains the worker. A broken worker needs
inspection, explicit release where leased, and authorized abandonment; never
infer that broken means disposable.

Interrupted collection completes only with valid candidate custody and an
unchanged worker. An exact summary without durable proof that this attempt
published it is retained as foreign, including after a crash between Git's
summary commit and the provenance write. Report it for manual inspection;
do not manufacture provenance or delete refs automatically to unblock it.
Missing collected results can be restored only from available recorded objects
into free names. No normal deletion proceeds without the preserved result.

Discard first moves an authenticated worker into quarantine. Failed checks
before deletion preserve the intact slot; interruption after deletion begins
can leave a partial remainder. Report `quarantine_path`, `quarantine_error`,
and whether deletion began. A new discard of an intact quarantine requires
current authorization for every applicable category. A worktree whose admin
entry was pruned needs ignored-content acknowledgement because enumeration is
unavailable; an unreadable quarantined clone stays refused. Recovery may
resume durably authorized deletion. Occupied slots, changed task branches,
foreign refs, or conflicting admin identity require inspection, never forceful
manual cleanup.

Status audits documented invariants without repairing records, refs, content,
or Git indexes; acquiring its lock can recreate the missing control file.
Inspect both `workers`/`drift` and `issues`. Recovery covers represented
checkpoints, not every possible filesystem interruption. Worker records and
collected results are retained indefinitely after discard; no prune or teardown
command exists. Never infer that another clone can see a commit before explicit
collection/synchronization.

Failure text identifies the stage, durable state, preservation confidence,
and recovery action. Treat `unverified` literally. Known config values, remote
URLs, URL userinfo, and private custody tokens are redacted, but other text is
not generally secret-scanned. Review errors before publishing them. Successful
status intentionally exposes the full quarantine path for recovery.

## Installation and handoff

Prefer ordinary `uv tool install git+https://github.com/kserrec/clonegrown.git`
or `pipx install` for the executable. The optional source `install.sh` requires
uv and installs the checkout plus this skill under both
`~/.claude/skills/clonegrown/SKILL.md` and
`~/.agents/skills/clonegrown/SKILL.md`. It keeps identical files, refuses
unsafe/differing destinations, and retains completed work on failure. It does
not migrate old custom installations or automatically remove skills. The user
reviews old wrappers/skill files before moving them aside; never invent an
ownership marker or overwrite a differing file to bypass refusal.

At handoff, report worker ID/path, branch/final commit, collection status and
result ref, whether separate integration occurred, whether the worker remains,
test results, and any ignored-content or writer uncertainty.
