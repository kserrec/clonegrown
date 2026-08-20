---
name: clonegrown
description: Use Clonegrown to create and manage isolated Git clone workspaces for parallel or delegated coding-agent work when clone isolation is a better fit than linked Git worktrees.
---

# Clonegrown

Use Clonegrown when work needs an isolated Git workspace and independent-clone isolation is a better fit than a linked worktree.

Good fits include a small or moderate number of autonomous workers, ordinary-sized repositories, tasks lasting minutes or longer, risky Git experimentation, and situations where reducing shared Git state is valuable.

Prefer native worktrees when repository history is enormous, worker creation/destruction is extremely frequent, tasks are very short, or spawn/storage efficiency clearly matters more than Git-state isolation.

## Core rule

Do not manually reproduce Clonegrown's clone/remotes/collection protocol. Use the `clonegrown` command for lifecycle operations.

Clonegrown normally discovers its workspace automatically. Do not pass explicit workspace paths unless auto-discovery fails or the user deliberately chose a nonstandard workspace location.

## Workspace lifecycle

1. From the canonical Git checkout, initialize once if needed:

   `clonegrown init`

   By default this creates a sibling workspace named `<repo>-dev`.

2. Spawn a worker for the task:

   `clonegrown spawn "<short task description>"`

   The worker starts from canonical `HEAD` unless `--base <ref-or-sha>` is supplied. Fast local cloning is the default. Use `--strong` only when physical independence of Git object files is specifically required.

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
- Do not treat clone isolation as an OS security sandbox.
- Prefer the default fast clone mode for ordinary application repositories.
- Use `--strong` sparingly because large Git histories can make fully independent clones expensive.

## Result handoff

When finishing, report at minimum:

- worker ID;
- worker path;
- branch;
- final commit SHA;
- whether collection succeeded;
- test/result summary.
