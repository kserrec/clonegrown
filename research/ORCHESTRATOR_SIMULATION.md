# Clonegrown Step 7.3 orchestration evidence

> Evidence class: current-package, single-run qualitative simulation.
> Recorded 2026-09-02. This is not comparative evidence and does not support a
> claim that Clonegrown reduces agent mistakes or human intervention.

## Provenance

- The current 37-path uncommitted tree based on
  `354d16bc662f15f65dded911d3c26729bf5804aa` was copied into an isolated
  source repository and committed there as
  `0576f933a066627a62996944bb1e395381027989`.
- Clonegrown 0.1.0a1 was installed from that snapshot in a temporary CPython
  3.12.3 environment.
- The fresh agent received no implementation or roadmap context. Its sole
  Clonegrown guidance was the isolated installed `SKILL.md`, SHA-256
  `f9b51e944e60472745d2d26833c664b489865c651d35e678dbf2194cbf363a7d`,
  byte-identical to the snapshot.
- The disposable canonical began at
  `98f3e826e318c902ae57069fa01ec1dc091ef38e`. The temporary raw agent report
  copied verbatim below had SHA-256
  `ac276301459516f7eda0868d261d50147837febbc7603cc63073a482c37ed92a`.

## Coordinating-session validation

The coordinating session independently reran the installed public status and
ordinary Git/filesystem probes after the agent stopped:

- Workspace `09a351954ded4dc7` reported `issues: []`.
- Workers 1–3 were `discarded` with released leases, and their immutable
  result refs still resolved to the recorded commits.
- The fourth worker was `spawn_failed` with `interrupted spawn recovered`
  after `recover` returned `spawn-cleaned`; its path and container were
  absent.
- Canonical `main` was clean and exactly three commits ahead of
  `origin/main`. The only changed paths were `apples.txt`, `pears.txt`,
  and `plums.txt`, containing `Honeycrisp`, `Comice`, and `Damson`.
- The parent project's tracked-diff SHA-256 and all five untracked-file
  SHA-256 values matched their pre-delegation values.
- No human workflow correction and no Clonegrown product or installed-skill
  defect was observed. The one false start concerned cross-namespace PID
  visibility in this shell runner's interruption fixture; the installed skill
  makes no PID-namespace claim.

---

<!-- Begin verbatim fresh-agent report. -->

# Clonegrown Phase 7.3 fresh-agent orchestration report

## Environment and allowed guidance

- Date: 2026-09-02; timezone: America/Los_Angeles.
- Disposable canonical repository: `/tmp/clonegrown-step-7-3.bddNTg/orchard`.
- Clonegrown-created sibling workspace: `/tmp/clonegrown-step-7-3.bddNTg/orchard-dev`.
- Installed command: `/tmp/clonegrown-step-7-3.bddNTg/venv/bin/clonegrown`.
- Sole Clonegrown guidance read in full: `/tmp/clonegrown-step-7-3.bddNTg/installed-skill/clonegrown/SKILL.md` (224 lines).
- I did not inspect Clonegrown implementation, tests, README, plans, handoff, architecture, research, or parent-repository history. I did not inspect any dotenv file or dotenv variant.
- Initial canonical state was `main` at `98f3e826e318c902ae57069fa01ec1dc091ef38e` (`Create orchestration fixture`), tracking `origin/main`, with no reported worktree changes.

## Outcome

The scenario completed. Three independent default-clone workers each produced one clean commit. Worker 2 was released and claimed again while still `ready`, before its task was performed or collected. All three commits were collected first, then separately integrated into canonical `main` with ordinary `git cherry-pick`. The three collected workers were released and discarded through Clonegrown. A fourth spawn was genuinely interrupted with SIGKILL directed only at the Clonegrown parent; `clonegrown recover` returned `spawn-cleaned`, and subsequent status recorded worker 4 as `spawn_failed` with no retained worker filesystem and no workspace issues.

## Worker, result, and integration table

| Worker | Task | Worker path | Worker branch | Worker/result commit | Preserved result ref | Separate canonical integration commit | Final worker state/filesystem |
|---:|---|---|---|---|---|---|---|
| 1 | Add `apples.txt` containing `Honeycrisp` | `/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/1/orchard` | `agent/09a351954ded4dc7/1-add-apples.txt-containing-honeycrisp` | `789710920e9ae090bfecbb3ca2f931f6cd1a3631` | `refs/cws/09a351954ded4dc7/workers/1/results/789710920e9ae090bfecbb3ca2f931f6cd1a3631` | `93a331a8dfb2c3ca37cfc2f766bb3ef3078283d2` | `discarded`; path absent |
| 2 | Add `pears.txt` containing `Comice` | `/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/2/orchard` | `agent/09a351954ded4dc7/2-add-pears.txt-containing-comice` | `e096ee5303e41c1cb42538e7d4cdfc53123d34a5` | `refs/cws/09a351954ded4dc7/workers/2/results/e096ee5303e41c1cb42538e7d4cdfc53123d34a5` | `5dc5efd66e7592beb31e7593c91509b7025da48c` | `discarded`; path absent |
| 3 | Add `plums.txt` containing `Damson` | `/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/3/orchard` | `agent/09a351954ded4dc7/3-add-plums.txt-containing-damson` | `3fa39e5d7696ea75ff44dc729000489e6f23c5fd` | `refs/cws/09a351954ded4dc7/workers/3/results/3fa39e5d7696ea75ff44dc729000489e6f23c5fd` | `c15bd2ece853a23bdf96c25c9602dc447051f3e7` | `discarded`; path absent |
| 4 | Interrupted disposable task | `/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/4/orchard` | `agent/09a351954ded4dc7/4-interrupted-disposable-task` | None | None | None | `spawn_failed`; path and worker-4 container absent after recovery |

The result refs remained resolvable after discard. Collection and integration were distinct operations: all three `clonegrown collect` calls completed before `git cherry-pick` was run against the three preserved refs.

## Chronological commands and exact outcomes

### 1. Canonical preflight and initialization

Command:

```text
pwd
git status --short --branch
git log -1 --format='%H %s'
```


Output:

```text
/tmp/clonegrown-step-7-3.bddNTg/orchard
## main...origin/main
98f3e826e318c902ae57069fa01ec1dc091ef38e Create orchestration fixture
```

Command:

```text
clonegrown init
```

Exact public output:

```json
{
  "canonical": "/tmp/clonegrown-step-7-3.bddNTg/orchard",
  "created": "2026-09-02T21:33:59Z",
  "object_format": "sha1",
  "repo_name": "orchard",
  "status": "ready",
  "workspace": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev",
  "workspace_id": "09a351954ded4dc7"
}
```

### 2. Three independent spawns

Command:

```text
clonegrown spawn "add apples.txt containing Honeycrisp"
```

Exact public output:

```json
{
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/1-add-apples.txt-containing-honeycrisp",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:06Z",
  "id": 1,
  "lease": "active",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/1/orchard",
  "ready": "2026-09-02T21:34:07Z",
  "request_id": null,
  "source_remote": "cws-source",
  "status": "ready",
  "strong": false,
  "task": "add apples.txt containing Honeycrisp",
  "workspace_id": "09a351954ded4dc7"
}
```

Command:

```text
clonegrown spawn "add pears.txt containing Comice"
```

Exact public output:

```json
{
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/2-add-pears.txt-containing-comice",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:10Z",
  "id": 2,
  "lease": "active",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/2/orchard",
  "ready": "2026-09-02T21:34:11Z",
  "request_id": null,
  "source_remote": "cws-source",
  "status": "ready",
  "strong": false,
  "task": "add pears.txt containing Comice",
  "workspace_id": "09a351954ded4dc7"
}
```

Command:

```text
clonegrown spawn "add plums.txt containing Damson"
```

Exact public output:

```json
{
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/3-add-plums.txt-containing-damson",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:14Z",
  "id": 3,
  "lease": "active",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/3/orchard",
  "ready": "2026-09-02T21:34:15Z",
  "request_id": null,
  "source_remote": "cws-source",
  "status": "ready",
  "strong": false,
  "task": "add plums.txt containing Damson",
  "workspace_id": "09a351954ded4dc7"
}
```

### 3. Ready-state release/claim handoff

Worker 2 remained `ready` and untouched when released.

Command:

```text
clonegrown release 2
```

Exact public output:

```json
{
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/2-add-pears.txt-containing-comice",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:10Z",
  "id": 2,
  "lease": "released",
  "lease_released": "2026-09-02T21:34:21Z",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/2/orchard",
  "ready": "2026-09-02T21:34:11Z",
  "request_id": null,
  "source_remote": "cws-source",
  "status": "ready",
  "strong": false,
  "task": "add pears.txt containing Comice",
  "workspace_id": "09a351954ded4dc7"
}
```

Command:

```text
clonegrown claim 2
```

Exact public output:

```json
{
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/2-add-pears.txt-containing-comice",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:10Z",
  "id": 2,
  "lease": "active",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/2/orchard",
  "ready": "2026-09-02T21:34:11Z",
  "request_id": null,
  "source_remote": "cws-source",
  "status": "ready",
  "strong": false,
  "task": "add pears.txt containing Comice",
  "workspace_id": "09a351954ded4dc7"
}
```

Only after that claim did I create `pears.txt` in worker 2.

### 4. Work and commits inside the returned workers

Each worker was inspected independently, given only its requested file, checked with `git diff --check`, committed, and confirmed clean.

Exact commit outputs:

```text
[agent/09a351954ded4dc7/1-add-apples.txt-containing-honeycrisp 7897109] Add Honeycrisp apples file
 1 file changed, 1 insertion(+)
 create mode 100644 apples.txt

[agent/09a351954ded4dc7/2-add-pears.txt-containing-comice e096ee5] Add Comice pears file
 1 file changed, 1 insertion(+)
 create mode 100644 pears.txt

[agent/09a351954ded4dc7/3-add-plums.txt-containing-damson 3fa39e5] Add Damson plums file
 1 file changed, 1 insertion(+)
 create mode 100644 plums.txt
```

Full worker commit SHAs and common parent established with `git show`:

```text
789710920e9ae090bfecbb3ca2f931f6cd1a3631
98f3e826e318c902ae57069fa01ec1dc091ef38e
Add Honeycrisp apples file

A	apples.txt

e096ee5303e41c1cb42538e7d4cdfc53123d34a5
98f3e826e318c902ae57069fa01ec1dc091ef38e
Add Comice pears file

A	pears.txt

3fa39e5d7696ea75ff44dc729000489e6f23c5fd
98f3e826e318c902ae57069fa01ec1dc091ef38e
Add Damson plums file

A	plums.txt
```

The actual file reads returned `Honeycrisp`, `Comice`, and `Damson`, respectively. No test suite existed in the stated scenario; the checks were exact content, clean worker status after commit, parent SHA, changed path, and whitespace-error checks.

### 5. Collection (preservation only)

Command:

```text
clonegrown collect 1
```

Exact public output:

```json
{
  "allow_rewrite": false,
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/1-add-apples.txt-containing-honeycrisp",
  "collected": "2026-09-02T21:35:07Z",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:06Z",
  "id": 1,
  "lease": "active",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/1/orchard",
  "ready": "2026-09-02T21:34:07Z",
  "request_id": null,
  "result_ref": "refs/cws/09a351954ded4dc7/workers/1/results/789710920e9ae090bfecbb3ca2f931f6cd1a3631",
  "result_sha": "789710920e9ae090bfecbb3ca2f931f6cd1a3631",
  "source_remote": "cws-source",
  "status": "collected",
  "strong": false,
  "task": "add apples.txt containing Honeycrisp",
  "workspace_id": "09a351954ded4dc7"
}
```

Command:

```text
clonegrown collect 2
```

Exact public output:

```json
{
  "allow_rewrite": false,
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/2-add-pears.txt-containing-comice",
  "collected": "2026-09-02T21:35:11Z",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:10Z",
  "id": 2,
  "lease": "active",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/2/orchard",
  "ready": "2026-09-02T21:34:11Z",
  "request_id": null,
  "result_ref": "refs/cws/09a351954ded4dc7/workers/2/results/e096ee5303e41c1cb42538e7d4cdfc53123d34a5",
  "result_sha": "e096ee5303e41c1cb42538e7d4cdfc53123d34a5",
  "source_remote": "cws-source",
  "status": "collected",
  "strong": false,
  "task": "add pears.txt containing Comice",
  "workspace_id": "09a351954ded4dc7"
}
```

Command:

```text
clonegrown collect 3
```

Exact public output:

```json
{
  "allow_rewrite": false,
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/3-add-plums.txt-containing-damson",
  "collected": "2026-09-02T21:35:15Z",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:14Z",
  "id": 3,
  "lease": "active",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/3/orchard",
  "ready": "2026-09-02T21:34:15Z",
  "request_id": null,
  "result_ref": "refs/cws/09a351954ded4dc7/workers/3/results/3fa39e5d7696ea75ff44dc729000489e6f23c5fd",
  "result_sha": "3fa39e5d7696ea75ff44dc729000489e6f23c5fd",
  "source_remote": "cws-source",
  "status": "collected",
  "strong": false,
  "task": "add plums.txt containing Damson",
  "workspace_id": "09a351954ded4dc7"
}
```

### 6. Explicit integration, separate from collection

Before integration, ordinary Git showed canonical `main` clean and all three result refs resolving to the collected SHAs:

```text
## main...origin/main
789710920e9ae090bfecbb3ca2f931f6cd1a3631 refs/cws/09a351954ded4dc7/workers/1/results/789710920e9ae090bfecbb3ca2f931f6cd1a3631
e096ee5303e41c1cb42538e7d4cdfc53123d34a5 refs/cws/09a351954ded4dc7/workers/2/results/e096ee5303e41c1cb42538e7d4cdfc53123d34a5
3fa39e5d7696ea75ff44dc729000489e6f23c5fd refs/cws/09a351954ded4dc7/workers/3/results/3fa39e5d7696ea75ff44dc729000489e6f23c5fd
```

Command (ordinary Git, deliberately after all collection calls):

```text
git cherry-pick refs/cws/09a351954ded4dc7/workers/1/results/789710920e9ae090bfecbb3ca2f931f6cd1a3631 refs/cws/09a351954ded4dc7/workers/2/results/e096ee5303e41c1cb42538e7d4cdfc53123d34a5 refs/cws/09a351954ded4dc7/workers/3/results/3fa39e5d7696ea75ff44dc729000489e6f23c5fd
```

Exact output:

```text
[main 93a331a] Add Honeycrisp apples file
 Date: Wed Sep 2 14:34:39 2026 -0700
 1 file changed, 1 insertion(+)
 create mode 100644 apples.txt
[main 5dc5efd] Add Comice pears file
 Date: Wed Sep 2 14:34:49 2026 -0700
 1 file changed, 1 insertion(+)
 create mode 100644 pears.txt
[main c15bd2e] Add Damson plums file
 Date: Wed Sep 2 14:34:58 2026 -0700
 1 file changed, 1 insertion(+)
 create mode 100644 plums.txt
```

Post-integration verification output:

```text
## main...origin/main [ahead 3]
c15bd2e (HEAD -> main) Add Damson plums file
5dc5efd Add Comice pears file
93a331a Add Honeycrisp apples file
98f3e82 (origin/main, origin/HEAD) Create orchestration fixture
Honeycrisp
Comice
Damson
A	apples.txt
A	pears.txt
A	plums.txt
```

`git diff --check origin/main..HEAD` produced no output and exited successfully. Thus the canonical integration was separate from collection and contained exactly the three requested paths.

### 7. Lease release and collected-worker discard

No writer, watcher, server, editor, or other persistent process was started in any worker; each Git/file command had exited. I then released each active lease.

Command:

```text
clonegrown release 1
```

Exact public output:

```json
{
  "allow_rewrite": false,
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/1-add-apples.txt-containing-honeycrisp",
  "collected": "2026-09-02T21:35:07Z",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:06Z",
  "id": 1,
  "lease": "released",
  "lease_released": "2026-09-02T21:35:38Z",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/1/orchard",
  "ready": "2026-09-02T21:34:07Z",
  "request_id": null,
  "result_ref": "refs/cws/09a351954ded4dc7/workers/1/results/789710920e9ae090bfecbb3ca2f931f6cd1a3631",
  "result_sha": "789710920e9ae090bfecbb3ca2f931f6cd1a3631",
  "source_remote": "cws-source",
  "status": "collected",
  "strong": false,
  "task": "add apples.txt containing Honeycrisp",
  "workspace_id": "09a351954ded4dc7"
}
```

Command:

```text
clonegrown release 2
```

Exact public output:

```json
{
  "allow_rewrite": false,
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/2-add-pears.txt-containing-comice",
  "collected": "2026-09-02T21:35:11Z",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:10Z",
  "id": 2,
  "lease": "released",
  "lease_released": "2026-09-02T21:35:42Z",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/2/orchard",
  "ready": "2026-09-02T21:34:11Z",
  "request_id": null,
  "result_ref": "refs/cws/09a351954ded4dc7/workers/2/results/e096ee5303e41c1cb42538e7d4cdfc53123d34a5",
  "result_sha": "e096ee5303e41c1cb42538e7d4cdfc53123d34a5",
  "source_remote": "cws-source",
  "status": "collected",
  "strong": false,
  "task": "add pears.txt containing Comice",
  "workspace_id": "09a351954ded4dc7"
}
```

Command:

```text
clonegrown release 3
```

Exact public output:

```json
{
  "allow_rewrite": false,
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/3-add-plums.txt-containing-damson",
  "collected": "2026-09-02T21:35:15Z",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:14Z",
  "id": 3,
  "lease": "released",
  "lease_released": "2026-09-02T21:35:45Z",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/3/orchard",
  "ready": "2026-09-02T21:34:15Z",
  "request_id": null,
  "result_ref": "refs/cws/09a351954ded4dc7/workers/3/results/3fa39e5d7696ea75ff44dc729000489e6f23c5fd",
  "result_sha": "3fa39e5d7696ea75ff44dc729000489e6f23c5fd",
  "source_remote": "cws-source",
  "status": "collected",
  "strong": false,
  "task": "add plums.txt containing Damson",
  "workspace_id": "09a351954ded4dc7"
}
```

Command:

```text
clonegrown discard 1
```

Exact public output:

```json
{
  "allow_rewrite": false,
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/1-add-apples.txt-containing-honeycrisp",
  "collected": "2026-09-02T21:35:07Z",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:06Z",
  "discarded": "2026-09-02T21:35:51Z",
  "id": 1,
  "lease": "released",
  "lease_released": "2026-09-02T21:35:38Z",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/1/orchard",
  "ready": "2026-09-02T21:34:07Z",
  "request_id": null,
  "result_ref": "refs/cws/09a351954ded4dc7/workers/1/results/789710920e9ae090bfecbb3ca2f931f6cd1a3631",
  "result_sha": "789710920e9ae090bfecbb3ca2f931f6cd1a3631",
  "source_remote": "cws-source",
  "status": "discarded",
  "strong": false,
  "task": "add apples.txt containing Honeycrisp",
  "workspace_id": "09a351954ded4dc7"
}
```

Command:

```text
clonegrown discard 2
```

Exact public output:

```json
{
  "allow_rewrite": false,
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/2-add-pears.txt-containing-comice",
  "collected": "2026-09-02T21:35:11Z",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:10Z",
  "discarded": "2026-09-02T21:35:54Z",
  "id": 2,
  "lease": "released",
  "lease_released": "2026-09-02T21:35:42Z",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/2/orchard",
  "ready": "2026-09-02T21:34:11Z",
  "request_id": null,
  "result_ref": "refs/cws/09a351954ded4dc7/workers/2/results/e096ee5303e41c1cb42538e7d4cdfc53123d34a5",
  "result_sha": "e096ee5303e41c1cb42538e7d4cdfc53123d34a5",
  "source_remote": "cws-source",
  "status": "discarded",
  "strong": false,
  "task": "add pears.txt containing Comice",
  "workspace_id": "09a351954ded4dc7"
}
```

Command:

```text
clonegrown discard 3
```

Exact public output:

```json
{
  "allow_rewrite": false,
  "alternates_detached": false,
  "base": "HEAD",
  "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
  "branch": "agent/09a351954ded4dc7/3-add-plums.txt-containing-damson",
  "collected": "2026-09-02T21:35:15Z",
  "compatibility_warnings": [],
  "copied_auxiliary_refs": {
    "notes": 0,
    "remote_tracking": 2,
    "replace": 0
  },
  "copied_local_config": [
    "user.name",
    "user.email",
    "filter.simulation-slow.clean",
    "filter.simulation-slow.smudge",
    "filter.simulation-slow.required"
  ],
  "copied_sparse_checkout": false,
  "created": "2026-09-02T21:34:14Z",
  "discarded": "2026-09-02T21:36:00Z",
  "id": 3,
  "lease": "released",
  "lease_released": "2026-09-02T21:35:45Z",
  "mode": "clone",
  "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/3/orchard",
  "ready": "2026-09-02T21:34:15Z",
  "request_id": null,
  "result_ref": "refs/cws/09a351954ded4dc7/workers/3/results/3fa39e5d7696ea75ff44dc729000489e6f23c5fd",
  "result_sha": "3fa39e5d7696ea75ff44dc729000489e6f23c5fd",
  "source_remote": "cws-source",
  "status": "discarded",
  "strong": false,
  "task": "add plums.txt containing Damson",
  "workspace_id": "09a351954ded4dc7"
}
```

Filesystem checks later returned:

```text
worker-1 path: absent
worker-2 path: absent
worker-3 path: absent
```

### 8. Deliberately interrupted fourth spawn and recovery

Immediately before the fourth spawn, I created the supplied `/tmp/clonegrown-step-7-3.bddNTg/pause-enabled` control. I then launched the installed command in the foreground through `exec`, printing the shell PID first so that the shell and Clonegrown would share a PID:

```text
echo $$
exec env PATH=/tmp/clonegrown-step-7-3.bddNTg/venv/bin:$PATH clonegrown spawn "interrupted disposable task"
```

The foreground session blocked and printed:

```text
2
```

That `2` was Clonegrown's PID inside the command's isolated PID namespace. The supplied smudge filter signaled that it had started:

```text
/tmp/clonegrown-step-7-3.bddNTg/filter-started 0 bytes
```

False start noted: an initial sandbox-local `ps -eo pid,ppid,comm,args` could see only its own sandbox process namespace, not the blocked spawn, so it could not target PID 2 from the other namespace. It returned only the local sandbox process and `ps`. I then used an approved host-visible read-only process listing. The relevant exact lines were:

```text
 685185  685184 clonegrown      /tmp/clonegrown-step-7-3.bddNTg/venv/bin/python /tmp/clonegrown-step-7-3.bddNTg/venv/bin/clonegrown spawn interrupted disposable task
 685260  685185 git             /usr/bin/git -c core.hooksPath=/tmp/cws-empty-hooks-uv28g1pw checkout -b agent/09a351954ded4dc7/4-interrupted-disposable-task c15bd2ece853a23bdf96c25c9602dc447051f3e7
 685262  685260 slow-smudge.sh  /bin/sh /tmp/clonegrown-step-7-3.bddNTg/fixture-tools/slow-smudge.sh
```

This established the Clonegrown parent as host PID 685185, with Git and the smudge filter as descendants. I sent `SIGKILL` only to PID 685185:

```text
kill -KILL 685185
```

The kill command exited 0 with no output. I did not signal PIDs 685260 or 685262. I then removed `pause-enabled`, allowed the child/session to settle, and observed the original foreground session exit 137 with no further stdout. The supplied `filter-started` evidence file remained present.

Command:

```text
clonegrown recover
```

Exact public output:

```json
[
  {
    "action": "spawn-cleaned",
    "id": 4
  }
]
```

Command immediately afterward:

```text
clonegrown status
```

Exact public output:

```json
{
  "canonical": "/tmp/clonegrown-step-7-3.bddNTg/orchard",
  "issues": [],
  "workers": [
    {
      "allow_rewrite": false,
      "alternates_detached": false,
      "base": "HEAD",
      "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
      "branch": "agent/09a351954ded4dc7/1-add-apples.txt-containing-honeycrisp",
      "collected": "2026-09-02T21:35:07Z",
      "compatibility_warnings": [],
      "copied_auxiliary_refs": {
        "notes": 0,
        "remote_tracking": 2,
        "replace": 0
      },
      "copied_local_config": [
        "user.name",
        "user.email",
        "filter.simulation-slow.clean",
        "filter.simulation-slow.smudge",
        "filter.simulation-slow.required"
      ],
      "copied_sparse_checkout": false,
      "created": "2026-09-02T21:34:06Z",
      "discarded": "2026-09-02T21:35:51Z",
      "id": 1,
      "lease": "released",
      "lease_released": "2026-09-02T21:35:38Z",
      "mode": "clone",
      "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/1/orchard",
      "ready": "2026-09-02T21:34:07Z",
      "request_id": null,
      "result_ref": "refs/cws/09a351954ded4dc7/workers/1/results/789710920e9ae090bfecbb3ca2f931f6cd1a3631",
      "result_sha": "789710920e9ae090bfecbb3ca2f931f6cd1a3631",
      "source_remote": "cws-source",
      "status": "discarded",
      "strong": false,
      "task": "add apples.txt containing Honeycrisp",
      "workspace_id": "09a351954ded4dc7"
    },
    {
      "allow_rewrite": false,
      "alternates_detached": false,
      "base": "HEAD",
      "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
      "branch": "agent/09a351954ded4dc7/2-add-pears.txt-containing-comice",
      "collected": "2026-09-02T21:35:11Z",
      "compatibility_warnings": [],
      "copied_auxiliary_refs": {
        "notes": 0,
        "remote_tracking": 2,
        "replace": 0
      },
      "copied_local_config": [
        "user.name",
        "user.email",
        "filter.simulation-slow.clean",
        "filter.simulation-slow.smudge",
        "filter.simulation-slow.required"
      ],
      "copied_sparse_checkout": false,
      "created": "2026-09-02T21:34:10Z",
      "discarded": "2026-09-02T21:35:54Z",
      "id": 2,
      "lease": "released",
      "lease_released": "2026-09-02T21:35:42Z",
      "mode": "clone",
      "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/2/orchard",
      "ready": "2026-09-02T21:34:11Z",
      "request_id": null,
      "result_ref": "refs/cws/09a351954ded4dc7/workers/2/results/e096ee5303e41c1cb42538e7d4cdfc53123d34a5",
      "result_sha": "e096ee5303e41c1cb42538e7d4cdfc53123d34a5",
      "source_remote": "cws-source",
      "status": "discarded",
      "strong": false,
      "task": "add pears.txt containing Comice",
      "workspace_id": "09a351954ded4dc7"
    },
    {
      "allow_rewrite": false,
      "alternates_detached": false,
      "base": "HEAD",
      "base_sha": "98f3e826e318c902ae57069fa01ec1dc091ef38e",
      "branch": "agent/09a351954ded4dc7/3-add-plums.txt-containing-damson",
      "collected": "2026-09-02T21:35:15Z",
      "compatibility_warnings": [],
      "copied_auxiliary_refs": {
        "notes": 0,
        "remote_tracking": 2,
        "replace": 0
      },
      "copied_local_config": [
        "user.name",
        "user.email",
        "filter.simulation-slow.clean",
        "filter.simulation-slow.smudge",
        "filter.simulation-slow.required"
      ],
      "copied_sparse_checkout": false,
      "created": "2026-09-02T21:34:14Z",
      "discarded": "2026-09-02T21:36:00Z",
      "id": 3,
      "lease": "released",
      "lease_released": "2026-09-02T21:35:45Z",
      "mode": "clone",
      "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/3/orchard",
      "ready": "2026-09-02T21:34:15Z",
      "request_id": null,
      "result_ref": "refs/cws/09a351954ded4dc7/workers/3/results/3fa39e5d7696ea75ff44dc729000489e6f23c5fd",
      "result_sha": "3fa39e5d7696ea75ff44dc729000489e6f23c5fd",
      "source_remote": "cws-source",
      "status": "discarded",
      "strong": false,
      "task": "add plums.txt containing Damson",
      "workspace_id": "09a351954ded4dc7"
    },
    {
      "base": "HEAD",
      "base_sha": "c15bd2ece853a23bdf96c25c9602dc447051f3e7",
      "branch": "agent/09a351954ded4dc7/4-interrupted-disposable-task",
      "created": "2026-09-02T21:36:19Z",
      "error": "interrupted spawn recovered",
      "failed": "2026-09-02T21:38:07Z",
      "id": 4,
      "mode": "clone",
      "path": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev/4/orchard",
      "request_id": null,
      "status": "spawn_failed",
      "strong": false,
      "task": "interrupted disposable task",
      "workspace_id": "09a351954ded4dc7"
    }
  ],
  "workspace": "/tmp/clonegrown-step-7-3.bddNTg/orchard-dev",
  "workspace_id": "09a351954ded4dc7"
}
```

Filesystem/accounting checks returned:

```text
worker-4 path: absent
worker-4 container: absent
pause-enabled: absent
filter-started: present
```

`git branch --list 'agent/09a351954ded4dc7/4-interrupted-disposable-task'` produced no output. Because recovery cleaned the unpublished fourth spawn and no recovered worker remained, there was no lease to release and no worker to discard or abandon.

## Human correction, uncertainty, and defects

- Human correction needed: **None**. The parent requested progress twice but supplied no correction. The host process listing and exact SIGKILL required explicit sandbox execution approvals; those were permissions to carry out the already-specified scenario, not corrections to the workflow.
- Active-writer uncertainty: None for workers 1–3; all commands had exited before release. For worker 4, only the Clonegrown parent received SIGKILL; after removing the pause, the originating execution session settled with exit 137 before recovery was run.
- Ignored-content uncertainty: no ignored-content refusal or warning appeared, and the requested results were tracked. No `--discard-ignored` or `--force` was used.
- Confirmed Clonegrown product defect: None observed.
- Suspected instruction/test-harness portability defect: the interruption instruction assumes the Clonegrown parent PID can be addressed from another command. Under this Codex shell runner, each ordinary command uses a separate PID namespace. The printed namespace PID (`2`) could not be signaled from a second sandbox command, so a host-visible process listing and host-level SIGKILL approval were required. This did not prevent recovery and is not evidence of a Clonegrown lifecycle defect.

## Final status

The final `clonegrown status` invocation returned the same complete JSON preserved in section 8: `issues` was still empty; workers 1–3 were `discarded` with released leases and preserved result refs; worker 4 was `spawn_failed` with `error: "interrupted spawn recovered"`. There was no retained recovered worker to release or discard.

The final ordinary Git check ran:

```text
git status --short --branch
git log --format='%H %s' -4
git diff --check origin/main..HEAD
git diff --name-status origin/main..HEAD
git show HEAD:apples.txt
git show HEAD:pears.txt
git show HEAD:plums.txt
git show-ref refs/cws/09a351954ded4dc7/workers/1/results/789710920e9ae090bfecbb3ca2f931f6cd1a3631 refs/cws/09a351954ded4dc7/workers/2/results/e096ee5303e41c1cb42538e7d4cdfc53123d34a5 refs/cws/09a351954ded4dc7/workers/3/results/3fa39e5d7696ea75ff44dc729000489e6f23c5fd
```

Exact output (`git diff --check` itself emitted nothing and succeeded):

```text
## main...origin/main [ahead 3]
c15bd2ece853a23bdf96c25c9602dc447051f3e7 Add Damson plums file
5dc5efd66e7592beb31e7593c91509b7025da48c Add Comice pears file
93a331a8dfb2c3ca37cfc2f766bb3ef3078283d2 Add Honeycrisp apples file
98f3e826e318c902ae57069fa01ec1dc091ef38e Create orchestration fixture
A	apples.txt
A	pears.txt
A	plums.txt
Honeycrisp
Comice
Damson
789710920e9ae090bfecbb3ca2f931f6cd1a3631 refs/cws/09a351954ded4dc7/workers/1/results/789710920e9ae090bfecbb3ca2f931f6cd1a3631
e096ee5303e41c1cb42538e7d4cdfc53123d34a5 refs/cws/09a351954ded4dc7/workers/2/results/e096ee5303e41c1cb42538e7d4cdfc53123d34a5
3fa39e5d7696ea75ff44dc729000489e6f23c5fd refs/cws/09a351954ded4dc7/workers/3/results/3fa39e5d7696ea75ff44dc729000489e6f23c5fd
```

This is a clean canonical worktree relative to `HEAD`; `main` is intentionally three commits ahead of the untouched disposable `origin/main` because integration was required and no push was requested.

<!-- End verbatim fresh-agent report. -->
