---
name: clonegrown
description: Use Clonegrown to create, collect, recover, and remove per-task Git working directories for parallel or delegated coding-agent work, with linked-worktree and local-clone modes.
---

# Clonegrown

Use Clonegrown when a task needs its own Git working directory and the
repository owner has authorized this alpha tool. Clonegrown records spawn,
collection, discard, and recovery. Collection can preserve a worker's clean
committed tip under a canonical ref; it does not integrate that commit into a
user branch.

A worker is either a **linked worktree** (`--worktree`, near-instant, shares
broad Git state with canonical) or a **local clone** (the CLI default, separate
refs, stash, local config, and a default private `.git/hooks` location but may
hard-link existing object files). `--strong` creates a clone with physically
separate object files.

Choose a worktree when repository history is very large, tasks are short, or
workers are created and destroyed rapidly. Choose a clone when separate Git
refs, local config, stash, and the default private hook location matter.
Clonegrown does not copy hook programs from canonical `.git/hooks`. It can copy
a configured `core.hooksPath` value, not the programs it names; any copied value
that resolves outside the worker remains shared. Absolute values receive a
compatibility warning, but tilde-prefixed and traversal-heavy values can also
resolve outside the worker without that warning. Treat every copied
`core.hooksPath` as potentially shared until its resolved location is known.
Choose `--strong` only when physical object independence justifies copying the
object database; it does not change this hook behavior.

## Core rule

Use the `clonegrown` command for lifecycle operations; do not manually
reproduce its marker, ref, remote, collection, or worktree-admin protocol.

Clonegrown normally discovers its workspace. Pass an explicit workspace only
when auto-discovery fails or the user deliberately selected a nonstandard
workspace path.

## Current alpha safety boundary

Before using this skill, account for these verified current limits:

- Collection and drift checks omit Git-ignored paths. Do not discard a worker
  that may contain valuable ignored content.
- Clonegrown has no durable work lease. Stop every agent, watcher, editor,
  server, and other process that can write to the worker before collection or
  discard.
- Recursive deletion can currently suppress a filesystem error and record the
  worker as gone without proving its path is absent. Verify the result after a
  destructive command.
- Recovery covers recorded lifecycle checkpoints, not every possible
  filesystem interruption. In particular, interrupted spawn recovery can
  delete an authenticated published worker that changed after publication,
  and worktree rollback can delete a same-named branch without proving the
  failed spawn created it. Treat interrupted-spawn recovery as destructive.
- A collected worker is one-shot. An unchanged repeat collection is a no-op;
  new commits after collection are rejected. Spawn a new worker for new work.
- Worktrees share broad Git state. Default clones can share existing object
  files through hard links. Neither mode is an operating-system sandbox.
- The clone's invalid canonical-source push URL is an accident guard, not a
  security boundary.
- Command failures can include full Git arguments and stderr, including copied
  configuration values or credential-bearing remote URLs. Do not paste error
  output into a public channel without reviewing it for secrets.

Do not run `discard --abandon` unless the user has explicitly authorized
destroying all content in that uncollected worker. Do not run `discard --force`
unless the user has explicitly authorized destroying the detected
post-collection changes. Never inspect dotenv files while assessing ignored
content; ask the user to handle those files themselves.

## Workspace lifecycle

1. From the canonical Git checkout, initialize once if needed:

   `clonegrown init`

   By default this creates a sibling workspace named `<repo>-dev`.

2. Spawn a worker for the task:

   `clonegrown spawn "<short task description>"`

   The worker starts from canonical `HEAD` unless `--base <ref-or-sha>` is
   supplied. Add `--worktree` for a linked worktree or `--strong` for a clone
   with separate object files. Pass `--request-id <stable-id>` only when a
   caller may retry the same request; matching retries with that ID and the
   same parameters return the existing allocation. A spawn without a request
   ID creates a new worker.

3. Work only inside the returned worker repository. Keep unrelated processes
   out of it and retain the worker until all desired content is accounted for.

4. Test the work and commit the desired result. Collection accepts a clean
   committed tip; ignored content is outside its current snapshot.

5. Stop every process that can write to the worker, then preserve the committed
   tip:

   `clonegrown collect <worker-id>`

6. Report the preserved commit and result ref. Integration is a separate,
   explicit Git operation chosen by the user; collection does not perform it.

7. Only when the worker contains no needed ignored content and no writer can
   race cleanup, remove the collected worker:

   `clonegrown discard <worker-id>`

8. If an operation was interrupted or durable state is unclear, reconcile the
   checkpoints Clonegrown can represent:

   `clonegrown recover`

   Then inspect:

   `clonegrown status`

## Hard invariants

- Never delete a worker directory manually.
- Never assume another clone can see a worker's commit before collection or
  another explicit synchronization operation.
- Never reuse a collected worker or use one worker for unrelated tasks.
- Never intentionally assign two tasks the same worker branch.
- Never intentionally push to the local canonical-source remote. Its invalid
  push URL is only a best-effort guard against mistakes.
- In a worktree worker, do not change shared Git config, delete branches, or
  alter a stash you did not create.
- Do not treat Clonegrown as an operating-system security boundary.

## Target custody contract — planned, not implemented

The accepted next protocol adds a durable cooperative work lease, requires an
explicit lease release before deletion, detects ignored paths and requires a
separate `--discard-ignored` acknowledgement for a collected worker,
quarantines an authenticated worker before checked deletion, keeps workers
one-shot after collection, and leaves integration explicit. Current releases
do not provide the lease/release or `--discard-ignored` commands or the
quarantine protocol. Do not instruct a user to run those planned operations
yet.

## Installation ownership

The custom `install.sh` gives its source directory, command wrapper, Claude
skill directory, and Codex skill directory versioned ownership evidence tied
to one installation ID. It creates absent targets and updates only targets
carrying that ID. It refuses unowned targets, direct symlinks, root/home
targets, and overlapping replacement paths. Do not manufacture or copy an
ownership marker to bypass a refusal.

Installations made before these markers existed cannot be adopted
automatically. The user must personally verify and move or remove each old
target before a fresh custom install. A Python tool manager remains the
CLI-only alternative. An owned custom update replaces the entire source and
skill directories, including extra files placed inside them.

## Result handoff

When finishing, report at minimum:

- worker ID and path;
- branch and final commit SHA;
- whether collection succeeded and the preserved result ref;
- whether integration occurred as a separate operation;
- whether the worker remains on disk;
- test/result summary and any ignored-content or active-writer uncertainty.
