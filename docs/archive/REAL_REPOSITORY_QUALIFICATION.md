# Real-repository qualification — 2026-08-29

## Outcome

Clonegrown passed all 6 lifecycle/recovery scenarios: 3 pinned public-repository
profiles × both the default clone worker and linked-worktree worker. Every
scenario intentionally stopped spawn at `spawn.after_publish` with exit 88,
then required `recover` to report `spawn-publish-finished`. The recovered
worker remained pinned to the public commit, accepted and committed a new
file, collected that commit under an immutable canonical result ref, released
its lease, and was discarded. The worker path and, for worktree mode, task
branch were gone; the result ref remained; `status` reported no audit issue;
and `git fsck --connectivity-only` passed.

The complete machine-readable record is
[`REAL_REPOSITORY_QUALIFICATION.json`](REAL_REPOSITORY_QUALIFICATION.json),
SHA-256
`7d0e36fd68bcb8d6b22af5e88d5c7f248147c81e1c09d5cd773a190e0928cb6c`.

## Pinned matrix

| Profile | Pinned public commit | Observed characteristic | Modes | Result |
| --- | --- | --- | --- | --- |
| curl history | [`8a2bb9ca241bbd82a0da536f6f39dca9037dd046`](https://github.com/curl/curl/commit/8a2bb9ca241bbd82a0da536f6f39dca9037dd046) | 39,564 commits reachable from `HEAD`; 39,654 across all cloned refs; 154,506 KiB packed object database | clone, worktree | 2/2 passed |
| Git refs | [`c73e85354c275c9d409b26445089bc16940fc527`](https://github.com/git/git/commit/c73e85354c275c9d409b26445089bc16940fc527) | 1,019 refs, including 1,008 tags; 85,469 commits across all cloned refs; 322,572 KiB packed object database | clone, worktree | 2/2 passed |
| Git features | [`c73e85354c275c9d409b26445089bc16940fc527`](https://github.com/git/git/commit/c73e85354c275c9d409b26445089bc16940fc527) | narrow sparse checkout retained `Documentation/git.adoc` and `.gitmodules`, excluded `Makefile`, and retained the uninitialized `sha1collisiondetection` gitlink at `855827c583bc30645ba427885caa40c5b81764d2` with mode `160000` | clone, worktree | 2/2 passed |

The feature profile was a second local full clone of the already downloaded,
pinned Git source, with its `origin` reset to the public URL. This avoided a
second network transfer without sharing Git administration or worker state.

All source clones used `--no-checkout`. Before the first checkout, the harness
enabled non-cone sparse checkout and excluded `.env`, `*.env`, `.env.*`, and
`*.env.*` at the root and every depth. The history and ref profiles otherwise
included the complete worktree. The harness did not search for, list, open, or
read any excluded file and makes no claim about whether one exists in public
history. It did not initialize the public submodule.

## Exact execution environment

- Generated at `2026-08-29T15:55:22.645257+00:00`.
- Clonegrown repository `HEAD`:
  `17bb42a4d69aeac1ca0b1db4e7a28f4c710f0af0`.
- Executed package-tree SHA-256:
  `d43e907baf57ed6e1191dd46306f19afb9081c272662f873b8c04cc98ada0734`.
  This identifies the uncommitted Phase 5 runtime files actually exercised,
  rather than implying that `HEAD` alone identifies the run.
- Harness SHA-256:
  `3f787f8f0c662734e38e04f4a517e4012ea351ada777a32b417e29063a2c3c41`.
- CPython 3.12.3 at `/usr/bin/python3`, build
  `3.12.3 (main, Jul 15 2026, 23:46:41) [GCC 13.3.0]`.
- Git 2.43.0 at `/usr/bin/git`.
- `Linux-6.17.0-35-generic-x86_64-with-glibc2.39`.

The observed end-to-end run took 168.309 seconds. Durations are retained only
as run provenance. No duration or ratio affected pass/fail.

## Exact scenario results

| Profile | Mode | Collected commit retained after discard |
| --- | --- | --- |
| curl history | clone | `91ff491aefb8060b673698596eb7105470067fdc` |
| curl history | worktree | `91cc825be69f4ddbbeb627b64d8960ae0224ecc9` |
| Git refs | clone | `ec1eacd7bee634e0769c86d9f003e1ef3be98579` |
| Git refs | worktree | `86c0e90aebe95ece18ebf8acd7124e9fdc0d41b0` |
| Git features | clone | `14697554ac50ace0777d62ce6cc5a42bd9bf8ff7` |
| Git features | worktree | `a8488d2e646e52068e534fae71ab83624c996a0e` |

## Reproduction and cost

Run from the repository root; the output must stay outside the checkout:

```bash
python3 -B tests/campaign/real_repository_qualification.py --output /tmp/clonegrown-real-repository-qualification.json
```

The harness uses only the Python standard library and the existing Git binary:
there is no added package size, transitive dependency tree, or dependency-alert
surface. It needs GitHub network access and creates disposable clones under
`/tmp`. This run recorded 477,078 KiB of packed objects across the two network
sources, before working-tree and worker copies. Successful runs delete the
temporary root; failed runs retain it and print its exact path for diagnosis.

## What this does not establish

This is bounded qualification evidence for these exact repositories, commits,
versions, operating system, and scenarios. It is not a universal performance
policy, a benchmark gate, evidence for repositories or platforms not run, or
proof that coding agents make fewer mistakes. It does not add support evidence
for initialized/recursive submodules, Git LFS, credentialed filters, partial
clones, network/distributed filesystems, native Windows, or genuine disk/inode
exhaustion.
