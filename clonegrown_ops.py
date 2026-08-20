"""Clonegrown implementation layer."""
from clonegrown_worker import *  # noqa: F401,F403



def spawn(ws_path: Path, base: str, task: str, strong: bool = True,
          request_id: str | None = None, wait_seconds: float = 120.0) -> dict[str, Any]:
    ws = ws_path.resolve()
    meta, created = allocate_spawn(ws, base, task, strong, request_id)
    if not created:
        return wait_for_existing(ws, int(meta["id"]), wait_seconds)
    worker_id = int(meta["id"])
    stage = Path(meta["stage_root"])
    stage_repo: Path | None = None
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise CWSError("worker operation lock unexpectedly unavailable")
        try:
            failpoint("spawn.after_allocated")
            with workspace_lock(ws):
                current = load_json(worker_meta_path(ws, worker_id))
                current.update({"status": "cloning", **owner_fields()})
                atomic_json(worker_meta_path(ws, worker_id), current)
                meta = current
                state = read_state(ws)
                canonical = verify_canonical(state)
            shutil.rmtree(stage, ignore_errors=True)
            stage.mkdir(parents=True, exist_ok=False)
            stage_repo = stage / state["repo_name"]
            cmd: list[str | Path] = [GIT_BIN, "clone", "--no-checkout"]
            if strong:
                cmd.append("--no-hardlinks")
            cmd += [canonical, stage_repo]
            run(cmd, timeout=None)
            failpoint("spawn.after_clone")
            git(stage_repo, "cat-file", "-e", f"{meta['base_sha']}^{{commit}}")
            with workspace_lock(ws):
                current = load_json(worker_meta_path(ws, worker_id))
                current.update({"status": "configuring", **owner_fields()})
                atomic_json(worker_meta_path(ws, worker_id), current)
                meta = current
                state = read_state(ws)
                canonical = verify_canonical(state)
            detached, warnings = detach_alternates_if_needed(stage_repo, strong)
            source_remote = copy_remote_config(canonical, stage_repo)
            copied_config, cfg_warnings = copy_local_config(canonical, stage_repo)
            auxiliary_refs = copy_auxiliary_refs(canonical, stage_repo)
            copy_info_files(canonical, stage_repo)
            sparse = copy_sparse_policy(canonical, stage_repo)
            warnings += cfg_warnings + private_hook_warnings(canonical)
            checkout_without_hooks(stage_repo, meta["branch"], meta["base_sha"])
            write_worker_marker(stage_repo, meta)
            if git(stage_repo, "rev-parse", "HEAD").stdout.strip() != meta["base_sha"]:
                raise CWSError("worker checkout differs from immutable requested base")
            git(stage_repo, "fsck", "--connectivity-only")
            failpoint("spawn.after_checkout")
            spawn_details = {
                "source_remote": source_remote,
                "alternates_detached": detached,
                "copied_local_config": copied_config,
                "copied_sparse_checkout": sparse,
                "copied_auxiliary_refs": auxiliary_refs,
                "compatibility_warnings": sorted(set(warnings)),
            }
            with workspace_lock(ws):
                state = read_state(ws)
                verify_canonical(state)
                current = load_json(worker_meta_path(ws, worker_id))
                if current.get("worker_token") != meta["worker_token"] or current.get("status") not in ACTIVE_SPAWN:
                    raise CWSError("spawn metadata ownership changed")
                current.update({"status": "publishing", "pending_spawn_details": spawn_details, **owner_fields()})
                atomic_json(worker_meta_path(ws, worker_id), current)
                final = final_worker_root(ws, worker_id)
                if final.exists():
                    raise CWSError("worker final path already exists")
                os.replace(stage, final)
                failpoint("spawn.after_publish")
                current.update({"status": "ready", "ready": time.time(), **spawn_details})
                current.pop("pending_spawn_details", None)
                current.pop("owner_pid", None); current.pop("owner_start", None)
                atomic_json(worker_meta_path(ws, worker_id), current)
                git(verify_canonical(state), "update-ref", "-d", base_ref(state, worker_id))
                failpoint("spawn.after_ready")
                return current
        except BaseException as exc:
            # SIGKILL/os._exit bypasses this and is handled by recover.
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            with contextlib.suppress(Exception):
                with workspace_lock(ws):
                    state = read_state(ws)
                    current = load_json(worker_meta_path(ws, worker_id))
                    published = final_worker_root(ws, worker_id).exists()
                    if published or current.get("status") == "ready":
                        # A published directory is never downgraded to a disposable failure.
                        # Leave a recoverable transaction record; recover will authenticate it.
                        current["status"] = "publishing" if current.get("status") != "ready" else "ready"
                        current["interrupted_error"] = str(exc)[:1000]
                    else:
                        current.update({"status": "spawn_failed", "failed": time.time(), "error": str(exc)[:1000]})
                    current.pop("owner_pid", None); current.pop("owner_start", None)
                    atomic_json(worker_meta_path(ws, worker_id), current)
                    if not published:
                        git(verify_canonical(state), "update-ref", "-d", base_ref(state, worker_id), check=False)
            if not final_worker_root(ws, worker_id).exists():
                shutil.rmtree(stage, ignore_errors=True)
            raise


def load_worker_state(ws: Path, worker_id: int) -> tuple[dict[str, Any], dict[str, Any], Path]:
    state = read_state(ws)
    canonical = verify_canonical(state)
    mp = worker_meta_path(ws, worker_id)
    if not mp.exists():
        raise CWSError(f"unknown worker: {worker_id}")
    meta = load_json(mp)
    validate_worker_meta(ws, state, worker_id, meta)
    return state, meta, canonical


def rollback_collect_error(ws: Path, worker_id: int, worker_token: str, error: BaseException) -> None:
    """Return a live worker to ready after a normal collection failure.

    Any fetched immutable result ref is deliberately retained: preserving an
    extra candidate is safer than deleting evidence.  Crash failpoints use
    os._exit and therefore remain the responsibility of recover().
    """
    with workspace_lock(ws):
        _, current, _ = load_worker_state(ws, worker_id)
        if current.get("status") != "collecting" or current.get("worker_token") != worker_token:
            return
        current.update({
            "status": "ready",
            "collection_error": str(error)[:1000],
            "collection_failed": time.time(),
        })
        for key in ("owner_pid", "owner_start", "candidate_sha", "candidate_ref"):
            current.pop(key, None)
        atomic_json(worker_meta_path(ws, worker_id), current)


def collect(ws_path: Path, worker_id: int, allow_rewrite: bool = False) -> dict[str, Any]:
    ws = ws_path.resolve()
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise CWSError("worker is busy")
        with workspace_lock(ws):
            state, meta, canonical = load_worker_state(ws, worker_id)
            if meta["status"] == "collected":
                snap = worker_snapshot(state, meta, require_ancestry=not allow_rewrite)
                if snap["head"] != meta.get("result_sha"):
                    raise CWSError("worker changed after collection; refusing to hide newer work")
                ref = meta["result_ref"]
                got = git(canonical, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
                if got.returncode or got.stdout.strip() != meta["result_sha"]:
                    raise CWSError("collected result ref is missing or changed")
                git(canonical, "update-ref", summary_ref(state, worker_id), meta["result_sha"])
                return meta
            if meta["status"] != "ready":
                raise CWSError(f"worker is not collectable from state {meta['status']}")
        first = worker_snapshot(state, meta, require_ancestry=not allow_rewrite)
        candidate = first["head"]
        result_ref = immutable_result_ref(state, worker_id, candidate)
        with workspace_lock(ws):
            state, current, canonical = load_worker_state(ws, worker_id)
            if current["status"] != "ready" or current["worker_token"] != meta["worker_token"]:
                raise CWSError("worker state changed before collection")
            current.update({
                "status": "collecting", "candidate_sha": candidate, "candidate_ref": result_ref,
                "allow_rewrite": bool(allow_rewrite), "collect_started": time.time(), **owner_fields(),
            })
            atomic_json(worker_meta_path(ws, worker_id), current)
            meta = current
        try:
            failpoint("collect.after_mark")
            failpoint("collect.before_fetch")
            git(canonical, "fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
                str(Path(meta["path"])), f"+{candidate}:{result_ref}")
            failpoint("collect.after_fetch")
            got = git(canonical, "rev-parse", "--verify", f"{result_ref}^{{commit}}").stdout.strip()
            if got != candidate:
                raise CWSError("preserved result differs from candidate commit")
            git(canonical, "cat-file", "-e", f"{candidate}^{{commit}}")
            failpoint("collect.after_verify")
            second = worker_snapshot(state, meta, require_ancestry=not allow_rewrite)
            if second != first:
                with workspace_lock(ws):
                    state, current, _ = load_worker_state(ws, worker_id)
                    current.update({"status": "ready", "collection_race": {"candidate": candidate, "observed": second["head"], "time": time.time()}})
                    for k in ("owner_pid", "owner_start", "candidate_sha", "candidate_ref"):
                        current.pop(k, None)
                    atomic_json(worker_meta_path(ws, worker_id), current)
                raise CWSError("worker changed during collection; candidate preserved but not accepted")
            failpoint("collect.after_worker_recheck")
            with workspace_lock(ws):
                state, current, canonical = load_worker_state(ws, worker_id)
                if current.get("status") != "collecting" or current.get("candidate_sha") != candidate:
                    raise CWSError("collection metadata changed")
                git(canonical, "update-ref", summary_ref(state, worker_id), candidate)
                failpoint("collect.after_summary")
                current.update({
                    "status": "collected", "result_sha": candidate, "result_ref": result_ref,
                    "collected": time.time(), "collected_snapshot": second,
                })
                for k in ("owner_pid", "owner_start", "candidate_sha", "candidate_ref"):
                    current.pop(k, None)
                atomic_json(worker_meta_path(ws, worker_id), current)
                failpoint("collect.after_metadata")
                return current
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            with contextlib.suppress(Exception):
                rollback_collect_error(ws, worker_id, meta["worker_token"], exc)
            raise


def discard(ws_path: Path, worker_id: int, abandon: bool = False, force: bool = False) -> dict[str, Any]:
    ws = ws_path.resolve()
    with file_lock(worker_lock_path(ws, worker_id)) as acquired:
        if not acquired:
            raise CWSError("worker is busy")
        with workspace_lock(ws):
            state, meta, canonical = load_worker_state(ws, worker_id)
            if meta["status"] in {"discarded", "abandoned"}:
                return meta
            if meta["status"] in ACTIVE_SPAWN | ACTIVE_COLLECT | ACTIVE_DISCARD:
                raise CWSError(f"worker has an active operation: {meta['status']}")
            # Every destructive path authenticates the published worker first. In particular,
            # --abandon must not turn metadata tampering into an accepted deletion request.
            if final_worker_root(ws, worker_id).exists():
                verify_worker(state, meta)
            if meta["status"] == "collected":
                ref = meta.get("result_ref")
                got = git(canonical, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
                if got.returncode or got.stdout.strip() != meta.get("result_sha"):
                    raise CWSError("refusing deletion because collected result is not preserved")
                if Path(meta["path"]).exists() and not force:
                    snap = worker_snapshot(state, meta, require_ancestry=not meta.get("allow_rewrite", False))
                    if snap["head"] != meta["result_sha"]:
                        raise CWSError("worker changed after collection; use --force only to knowingly discard it")
            elif not abandon:
                raise CWSError("refusing to delete an uncollected worker; use explicit --abandon")
            previous = meta["status"]
            meta.update({
                "status": "discarding", "discard_intent": "abandoned" if abandon else "discarded",
                "discard_previous": previous, "discard_started": time.time(), **owner_fields(),
            })
            atomic_json(worker_meta_path(ws, worker_id), meta)
        failpoint("discard.after_mark")
        failpoint("discard.before_delete")
        shutil.rmtree(final_worker_root(ws, worker_id), ignore_errors=True)
        stage = Path(meta.get("stage_root", ""))
        if str(stage) and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        failpoint("discard.after_delete")
        with workspace_lock(ws):
            state, current, canonical = load_worker_state(ws, worker_id)
            current["status"] = current.get("discard_intent", "discarded")
            current["discarded"] = time.time()
            for k in ("owner_pid", "owner_start"):
                current.pop(k, None)
            atomic_json(worker_meta_path(ws, worker_id), current)
            failpoint("discard.after_metadata")
            return current
