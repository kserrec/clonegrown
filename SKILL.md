---
name: clonegrown
description: Create and manage isolated Git clone workspaces for parallel or delegated coding-agent work using the Clonegrown CLI.
---

# Clonegrown

Use Clonegrown when a task needs an isolated Git workspace for parallel work, delegated agent work, risky experimentation, or concurrent implementation and independent-clone isolation is appropriate.

## Core rule

Do not manually reproduce Clonegrown's clone/remotes/collection protocol. Use the `clonegrown` CLI for lifecycle operations.

## Workspace lifecycle

1. Locate the primary (non-worktree) canonical Git checkout.
2. Initialize a sibling workspace if one does not already exist:

   `clonegrown init <canonical-repo> <workspace>`

3. Spawn a worker from the intended base branch or commit:

   `clonegrown spawn <workspace> --base <base> --task <short-task> --request-id <stable-id> --fast`

4. Work only inside the returned worker repository. Treat it as disposable and exclusively owned by this task.
5. Commit desired work before collection.
6. Preserve the result with:

   `clonegrown collect <workspace> <worker-id>`

7. Only after successful collection, remove the worker with:

   `clonegrown discard <workspace> <worker-id>`

8. If an operation was interrupted or state is unclear, run:

   `clonegrown recover <workspace>`

   followed by:

   `clonegrown status <workspace>`

## Hard invariants

- Never delete a worker directory manually.
- Never assume another worker can see this worker's commits without collection/synchronization.
- Never reuse a worker for an unrelated task.
- Never let two tasks intentionally share one worker branch.
- Never push to Clonegrown's local canonical-source remote; the CLI configures it as non-pushable.
- Do not treat clone isolation as an OS security sandbox.
- Prefer `--fast` for ordinary application repositories unless physical Git-object independence is specifically required.
- For enormous Git histories, very high worker churn, or extremely short tasks, consider native worktrees instead.

## Result handoff

When finishing, report at minimum:

- worker ID;
- worker path;
- branch;
- final commit SHA;
- whether collection succeeded;
- test/result summary.
