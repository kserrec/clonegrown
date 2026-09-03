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

> **Do not use this tree for irreplaceable work until it is qualified.** The
> 2026-09-02 cold review found six product defects: clone-private dangling
> symbolic refs could escape discard custody; dangling symbolic task branches
> and control-file names were not safely reserved; CLI workspace selection
> could follow a symlink; `GIT_CONFIG` could reach child Git; and repeated
> collection after an accepted history rewrite could fail. Eight later
> reviews found that inherited `GIT_*` overrides or worker-local replace refs and
> graft files could fake ancestry, that quarantine re-authorization skipped
> ignored content, and that some foreign occupants of Clonegrown's ref names
> (symbolic refs, symlinks, FIFOs, and chains between them) were not refused
> or could still block Git. All are repaired with class regressions; a fresh
> no-open-finding review and green hosted CI are still required. See `research/FINAL_COLD_REVIEW.md` and `PLAN.md` in the
> source repository.

A worker is either a **linked worktree** (`--worktree`, avoids copying a
second object database but still has repository- and host-dependent checkout
cost, and shares broad Git state with canonical) or a **local clone** (the CLI default, separate
refs, stash, local config, and a default private `.git/hooks` location but may
hard-link existing object files). `--strong` creates a clone with physically
separate object files at spawn; it is not an operating-system sandbox.

Choose a worktree when repository history is very large, tasks are short, or
workers are created and destroyed rapidly. Choose a clone when separate Git
refs, local config, stash, and the default private hook location matter.
Clone mode preserves ordered repository-local config occurrences, including
the semantic difference between valueless and explicitly empty entries. It
flattens effective repository-local includes without copying their directives,
and anchors relative local fetch and push paths to canonical before installing
them in a relocated worker. Absolute paths, URL schemes, and scp-like remotes
are left unchanged.
Clonegrown does not copy hook programs from canonical `.git/hooks`. It can copy
a configured `core.hooksPath` value, not the programs it names; any copied value
that resolves outside the worker remains shared. Absolute values receive a
compatibility warning, but tilde-prefixed and traversal-heavy values can also
resolve outside the worker without that warning. Treat every copied
`core.hooksPath` as potentially shared until its resolved location is known.
Choose `--strong` only when physical object independence at spawn justifies
copying the object database; it does not change this hook behavior.

## Core rule

Use the `clonegrown` command for lifecycle operations; do not manually
reproduce its marker, ref, remote, collection, or worktree-admin protocol.

Clonegrown normally discovers its workspace. Pass an explicit workspace only
when auto-discovery fails or the user deliberately selected a nonstandard
workspace path.

## Current alpha safety boundary

Before using this skill, account for these verified current limits:

- Collection and drift checks omit Git-ignored paths. Discarding a collected
  worker that holds ignored paths is refused until `--discard-ignored` is
  given; the refusal lists a count and a few names. Do not pass that flag
  unless the user has authorized destroying that ignored content.
- Recovery of an interrupted spawn has three outcomes: an untouched worker
  is promoted to `ready`, a changed one is preserved as `broken`, and one
  that recovery cannot inspect because another worker's foreign ref blocks
  Git is left untouched and reported as `recovery-failed` until that
  occupant is removed.
- Clone workers record a raw inventory of their non-task refs at publication,
  symbolic refs included whether or not their targets exist. If a later
  private ref or stash differs, collected-clone discard refuses until
  `--discard-private-refs` is given; a clone with no verifiable baseline (an
  older record, or refs not stored as files) fails closed the same way. Report
  changed ref names and do not pass that flag without authorization. The check also omits
  later local-config, hook, or other non-ref `.git` changes, so review any such
  clone-private setup before deletion.
- Every published worker holds a cooperative work lease from spawn until an
  explicit `clonegrown release <worker-id>`. Discard, including `--abandon` and
  `--force`, refuses a leased worker, and recovery never treats a dead process
  as a release. The lease is a handoff protocol between cooperating callers,
  not an operating-system sandbox: a process that ignores it, or keeps file
  descriptors open, can still write after the final check. Stop every agent,
  watcher, editor, server, and other process that can write to the worker
  before releasing it.
- Discard moves the worker to `.cws/quarantine/`, rechecks it, deletes it
  with errors enabled, and proves it absent before recording it gone. If the
  worker changed before deletion, it stays intact in quarantine. If authorized
  recursive deletion had already begun when an error or interruption occurred,
  only the remainder may survive. In either case `status` reports the retained
  `quarantine_path` and `quarantine_error`; report that to the user rather than
  deleting anything by hand. Running `clonegrown recover` reconciles the
  recorded intent: it resumes a quarantined or durably authorized deletion,
  while an untouched normal discard can be withdrawn for a fresh retry.
- Recovery covers recorded lifecycle checkpoints, not every possible
  filesystem interruption. A published worker whose spawn was interrupted is
  promoted to `ready` if it is untouched and otherwise preserved in place as
  `broken`, with `error` saying how it differs; it is deleted only by an
  explicit release and `discard --abandon`. A worktree task branch is deleted
  only when Clonegrown proves it created it and it has not moved; a retained
  branch is reported, never forced. An interrupted collection is finished only
  when its exact candidate can be published without replacing a ref and the
  worker still matches; otherwise recovery returns it to `ready` and leaves
  any conflicting ref untouched.
- A collected worker is one-shot. An unchanged repeat collection is a no-op
  judged by the rewrite policy the original collection recorded, so a repeat
  after an accepted `--allow-rewrite` needs no option; new commits or a new
  rewrite after collection are rejected under any option, and `--abandon` and
  `claim` are refused for it. Spawn a new worker for new work.
- Worktrees share broad Git state. Default clones can share existing object
  files through hard links. Neither mode is an operating-system sandbox.
- The clone's invalid canonical-source push URL is an accident guard, not a
  security boundary.
- Git command failures redact copied configuration values, remote URLs, and
  URL userinfo from their displayed command, stdout, and stderr. Other Git
  diagnostic text remains visible; this is targeted redaction rather than a
  general secret scanner, so review error output before putting it in a public
  channel.
- Failure text also hides the private token component of Clonegrown's own
  staging and quarantine paths, including quoted operating-system filenames.
  Successful `status` output deliberately retains the full `quarantine_path`
  as recovery evidence while hiding the separate `worker_token` field.
- An `init`, `spawn`, `collect`, `discard`, or `recover` failure states its
  operation stage, last known durable mutation, work-preservation confidence,
  and required recovery or manual inspection. Treat `unverified` literally:
  do not infer that a write, rename, publication, or deletion did or did not
  happen. Follow the stated recovery action, then use `clonegrown status` to
  audit the documented workspace and worker invariants. The CLI prints one
  contextual error without a traceback;
  command causes keep the targeted redaction above. Arbitrary exception text
  receives the same URL-userinfo and Clonegrown-custody-token filtering but is
  not generally secret-scanned. Process-control exceptions are deliberately
  not converted.

Do not run `clonegrown release` until every process you started in the worker
has stopped; release is your statement that the worker is quiet. Do not run
`discard --abandon` unless the user has explicitly authorized destroying all
content in that uncollected worker. Do not run `discard --force` unless the
user has explicitly authorized destroying the detected post-collection
changes. Do not run `discard --discard-ignored` or
`discard --discard-private-refs` unless the user has authorized destroying the
named category. No flag overrides the lease. Never inspect dotenv files while
assessing ignored content; ask the user to handle those files themselves.

## Workspace lifecycle

1. From the canonical Git checkout, initialize once if needed:

   `clonegrown init`

   By default this creates a sibling workspace named `<repo>-dev`.

2. Spawn a worker for the task:

   `clonegrown spawn "<short task description>"`

   The worker starts from canonical `HEAD` unless `--base <ref-or-sha>` is
   supplied. Add `--worktree` for a linked worktree or `--strong` for a clone
   with physically separate object files at spawn. Pass
   `--request-id <stable-id>` only when a
   caller may retry the same request. A matching retry rejoins an in-flight
   request or returns its existing ready, collected, or discarded outcome;
   `abandoned` and `spawn_failed` outcomes make the ID retryable and allocate
   anew, while `broken` must be resolved first. A spawn without a request ID
   creates a new worker.

3. Work only inside the returned worker repository. Keep unrelated processes
   out of it and retain the worker until all desired content is accounted for.

4. Test the work and commit the desired result. Collection accepts a clean
   committed tip; ignored content is outside its current snapshot.

5. Stop every process that can write to the worker, then preserve the committed
   tip:

   `clonegrown collect <worker-id>`

6. Report the preserved commit and result ref. Integration is a separate,
   explicit Git operation chosen by the user; collection does not perform it.

7. Once every process you started in the worker has stopped, release the
   lease:

   `clonegrown release <worker-id>`

   Collection does not require release; release is the handoff that permits
   deletion. A released worker that is still `ready` can be taken over again
   with `clonegrown claim <worker-id>`; a collected worker cannot.

8. Remove the collected worker:

   `clonegrown discard <worker-id>`

   If it refuses because of ignored paths, report them to the user; only with
   their authorization add `--discard-ignored`. If it refuses because of
   changes after collection, that is `--force`, separately authorized. If a
   clone's private refs differ from its publication baseline, report the names
   and add `--discard-private-refs` only with separate authorization.

9. If an operation was interrupted or durable state is unclear, reconcile the
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

## Target custody contract — intended; checkpoint not qualified

The accepted protocol adds a durable cooperative work lease with an explicit
release before deletion (`release`, `claim`), detects ignored paths and
requires a separate `--discard-ignored` acknowledgement for a collected
worker, detects changed clone-private refs (direct or symbolic, dangling
included) and requires `--discard-private-refs`, quarantines an authenticated worker before checked
deletion, keeps workers one-shot after collection, retains discarded result
custody, and leaves integration explicit. The notice at the top records the
repaired deviations and the review still required; do not treat this tree as
qualified until that review is recorded.

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
