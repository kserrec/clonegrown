"""Clonegrown implementation layer."""
from clonegrown_repo import *  # noqa: F401,F403



def write_worker_marker(repo: Path, meta: dict[str, Any]) -> None:
    atomic_json(worker_marker_path(repo), {
        "workspace_id": meta["workspace_id"],
        "worker_id": meta["id"],
        "worker_token": meta["worker_token"],
        "canonical_token": meta["canonical_token"],
        "base_sha": meta["base_sha"],
        "branch": meta["branch"],
        "created": time.time(),
    })


def verify_worker(state: dict[str, Any], meta: dict[str, Any], require_exists: bool = True) -> Path:
    repo = Path(meta["path"])
    if not repo.exists():
        if require_exists:
            raise CWSError("worker repository is missing")
        return repo
    final_root = repo.parent
    for boundary, label in ((final_root, "worker slot"), (repo, "worker repository")):
        try:
            mode = os.lstat(boundary).st_mode
        except FileNotFoundError:
            raise CWSError(f"{label} is missing")
        if stat.S_ISLNK(mode):
            raise CWSError(f"{label} was replaced by a symlink")
        if not stat.S_ISDIR(mode):
            raise CWSError(f"{label} is not a directory")
    if repo_root(repo) != repo.resolve():
        raise CWSError("worker repository root changed")
    if git_dir(repo) != git_common_dir(repo):
        raise CWSError("worker was replaced with a linked worktree")
    marker = load_json(worker_marker_path(repo))
    checks = {
        "workspace_id": state["workspace_id"],
        "worker_id": meta["id"],
        "worker_token": meta["worker_token"],
        "canonical_token": state["canonical_token"],
        "base_sha": meta["base_sha"],
        "branch": meta["branch"],
    }
    for key, expected in checks.items():
        if marker.get(key) != expected:
            raise CWSError(f"worker identity marker mismatch: {key}")
    if object_format(repo) != state["object_format"]:
        raise CWSError("worker object format differs from canonical")
    return repo


def op_in_progress(repo: Path) -> list[str]:
    found = []
    for rel in OPERATION_GIT_PATHS:
        if git_path(repo, rel).exists():
            found.append(rel)
    return found


def worker_snapshot(state: dict[str, Any], meta: dict[str, Any], require_ancestry: bool = True) -> dict[str, Any]:
    repo = verify_worker(state, meta)
    dirty = git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout
    if dirty.strip():
        raise CWSError("worker has uncommitted or untracked changes")
    operations = op_in_progress(repo)
    if operations:
        raise CWSError("worker has an in-progress Git operation: " + ", ".join(operations))
    sym = git(repo, "symbolic-ref", "-q", "HEAD", check=False)
    expected_ref = f"refs/heads/{meta['branch']}"
    if sym.returncode or sym.stdout.strip() != expected_ref:
        raise CWSError("worker HEAD is detached or not on its assigned task branch")
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    branch = git(repo, "rev-parse", expected_ref).stdout.strip()
    if head != branch:
        raise CWSError("worker HEAD and assigned branch disagree")
    if require_ancestry:
        anc = git(repo, "merge-base", "--is-ancestor", meta["base_sha"], head, check=False)
        if anc.returncode != 0:
            raise CWSError("worker result does not descend from its assigned base")
    return {"head": head, "branch_ref": expected_ref, "status": dirty, "operations": operations}


def wait_for_existing(ws: Path, worker_id: int, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        meta = load_json(worker_meta_path(ws, worker_id))
        if meta.get("status") == "ready" or meta.get("status") in {"collected", "discarded", "abandoned"}:
            return meta
        if meta.get("status") in TERMINAL_SPAWN_FAILURE or meta.get("status") == "broken":
            raise CWSError(f"existing request failed in worker {worker_id}: {meta.get('error', meta.get('status'))}")
        if time.monotonic() >= deadline:
            raise CWSError(f"timed out waiting for existing request worker {worker_id}; run recover")
        if not process_alive(meta.get("owner_pid"), meta.get("owner_start")):
            recover(ws)
        time.sleep(0.05)


def allocate_spawn(ws: Path, base: str, task: str, strong: bool, request_id: str | None) -> tuple[dict[str, Any], bool]:
    with workspace_lock(ws):
        state = read_state(ws)
        canonical = verify_canonical(state)
        ph = params_hash(base, task, strong)
        if request_id:
            rp = request_path(ws, request_id)
            if rp.exists():
                req = load_json(rp)
                if req.get("request_id") != request_id:
                    raise CWSError("request index hash collision or corruption")
                if req.get("params_hash") != ph:
                    raise CWSError("request ID was reused with different base/task/isolation parameters")
                old = load_json(worker_meta_path(ws, int(req["worker_id"])))
                if old.get("status") not in TERMINAL_SPAWN_FAILURE:
                    return old, False
                # A failed incomplete spawn may be retried under the same idempotency key.
        resolved = git(canonical, "rev-parse", "--verify", f"{base}^{{commit}}", check=False)
        if resolved.returncode:
            raise CWSError(f"base does not resolve to a commit: {base}")
        base_sha = resolved.stdout.strip()
        worker_id = int(state["next_id"])
        state["next_id"] = worker_id + 1
        atomic_json(ws_paths(ws)["state"], state)
        token = secrets.token_hex(16)
        stage = staging_root(ws, worker_id, token)
        final = final_worker_root(ws, worker_id)
        repo = final / state["repo_name"]
        branch = f"agent/{state['workspace_id']}/{worker_id}-{sanitize_task(task)}"
        git(canonical, "update-ref", base_ref(state, worker_id), base_sha, "0" * len(base_sha))
        meta: dict[str, Any] = {
            "schema": SCHEMA,
            "id": worker_id,
            "workspace_id": state["workspace_id"],
            "canonical_token": state["canonical_token"],
            "worker_token": token,
            "status": "allocated",
            "path": str(repo),
            "stage_root": str(stage),
            "branch": branch,
            "base": base,
            "base_sha": base_sha,
            "strong": bool(strong),
            "task": task,
            "request_id": request_id,
            "params_hash": ph,
            "created": time.time(),
            **owner_fields(),
        }
        atomic_json(worker_meta_path(ws, worker_id), meta)
        if request_id:
            atomic_json(request_path(ws, request_id), {
                "request_id": request_id,
                "params_hash": ph,
                "worker_id": worker_id,
                "created": time.time(),
            })
        return meta, True
