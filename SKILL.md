---
name: clonegrown
description: Use Clonegrown to create, collect, recover, and delete per-task Git working directories (linked worktrees or isolated clones) for parallel or delegated coding-agent work without losing or duplicating work.
---

# Clonegrown

Use Clonegrown whenever a task needs its own Git working directory. It manages the whole lifecycle — spawn, collect, discard, recover — so work is never duplicated, deleted before it is saved, or left half-created after a crash.

Each worker is either a **linked worktree** (`--worktree`: near-instant, shares canonical's config, refs, stash, and hooks) or an **independent clone** (default: seconds to create, shares nothing; `--strong` additionally copies object files).

Choose `--worktree` when history is enormous, tasks are short, or workers are created and destroyed rapidly. Choose a clone when several autonomous workers will run for minutes or longer, when the task involves risky Git operations, or when one worker's Git mistakes must not reach another.

## Core rule

Do not manually reproduce Clonegrown's clone/remotes/collection protocol. Use the `clonegrown` command for lifecycle operations.

Clonegrown normally discovers its workspace automatically. Do not pass explicit workspace paths unless auto-discovery fails or the user deliberately chose a nonstandard workspace location.

## Workspace lifecycle

1. From the canonical Git checkout, initialize once if needed:

   `clonegrown init`

   By default this creates a sibling workspace named `<repo>-dev`.

2. Spawn a worker for the task:

   `clonegrown spawn "<short task description>"`

   The worker starts from canonical `HEAD` unless `--base <ref-or-sha>` is supplied. Add `--worktree` for a linked worktree, or `--strong` for a clone with nothing shared. Pass `--request-id <stable-id>` when a spawn may be retried, so a retry returns the same worker.

3. Work only inside the returned worker repository. Treat that repository as disposable and exclusively owned by this task.

4. Test the work and commit the desired result.

5. Preserve the worker result in the canonical repository:

   `clonegrown collect <worker-id>`

6. Only after successful collection, remove the worker:

   `clonegrown discard <worker-id>`

7. To intentionally throw away uncollected work:

   `clonegrown discard <worker-id> --abandon`

8. If an operation was interrupted or state is unclear:

   `clonegrown recover`

   then inspect:

   `clonegrown status`

## Hard invariants

- Never delete a worker directory manually.
- Never assume another independent clone can see this worker's commits until the result is collected or otherwise synchronized.
- Never reuse a worker for an unrelated task.
- Never intentionally give two tasks the same worker branch.
- Never push to Clonegrown's local canonical-source remote; the CLI configures it as non-pushable.
- In a worktree worker, never change Git config, delete branches, or touch the stash you did not create: those are shared with canonical and every other worktree.
- Do not treat clone isolation as an OS security sandbox.
- Use `--strong` sparingly because large Git histories can make fully independent clones expensive.

## Result handoff

When finishing, report at minimum:

- worker ID;
- worker path;
- branch;
- final commit SHA;
- whether collection succeeded;
- test/result summary.
