"""Clonegrown implementation layer."""
from clonegrown_ops import *  # noqa: F401,F403



def recover(ws_path: Path) -> list[dict[str, Any]]:
    ws = ws_path.resolve()
    reports: list[dict[str, Any]] = []
    with workspace_lock(ws):
        state = read_state(ws)
        canonical = verify_canonical(state)
        worker_files = []
        for candidate in ws_paths(ws)["workers"].glob("*.json"):
            try:
                int(candidate.stem)
            except ValueError:
                reports.append({"path": str(candidate), "action": "unknown-metadata-file"})
                continue
            worker_files.append(candidate)
        worker_files.sort(key=lambda p: int(p.stem))
        known_ids = {int(p.stem) for p in worker_files}
        canonical_slot = state.get("canonical_slot")
        for child in ws.iterdir():
            if not child.is_dir() or not child.name.isdigit():
                continue
            wid = int(child.name)
            if wid == canonical_slot or wid in known_ids:
                continue
            reports.append({"id": wid, "path": str(child), "action": "orphan-worker-directory"})
    for mp in worker_files:
        worker_id = int(mp.stem)
        with file_lock(worker_lock_path(ws, worker_id), blocking=False) as acquired:
            if not acquired:
                reports.append({"id": worker_id, "action": "active-lock-held"})
                continue
            with workspace_lock(ws):
                try:
                    state, meta, canonical = load_worker_state(ws, worker_id)
                except CWSError as exc:
                    reports.append({"id": worker_id, "path": str(mp), "action": "corrupt-or-unreadable-metadata", "error": str(exc)[:1000]})
                    continue
                status = meta["status"]
                if status in ACTIVE_SPAWN and process_alive(meta.get("owner_pid"), meta.get("owner_start")):
                    reports.append({"id": worker_id, "action": "active-spawn-alive"})
                    continue
                if status == "collecting" and process_alive(meta.get("owner_pid"), meta.get("owner_start")):
                    reports.append({"id": worker_id, "action": "active-collect-alive"})
                    continue
                if status == "discarding" and process_alive(meta.get("owner_pid"), meta.get("owner_start")):
                    reports.append({"id": worker_id, "action": "active-discard-alive"})
                    continue

                if status in ACTIVE_SPAWN:
                    final_repo = Path(meta["path"])
                    final_root = final_worker_root(ws, worker_id)
                    # A crash after atomic publish but before ready metadata can be completed safely.
                    try:
                        if final_repo.exists():
                            verify_worker(state, meta)
                            snap = worker_snapshot(state, meta)
                            if snap["head"] == meta["base_sha"]:
                                details = meta.pop("pending_spawn_details", {})
                                if not isinstance(details, dict):
                                    details = {}
                                meta.update({"status": "ready", "ready": time.time(), **details})
                                meta.pop("owner_pid", None); meta.pop("owner_start", None)
                                atomic_json(mp, meta)
                                git(canonical, "update-ref", "-d", base_ref(state, worker_id), check=False)
                                reports.append({"id": worker_id, "action": "spawn-publish-finished"})
                                continue
                    except Exception:
                        pass
                    shutil.rmtree(Path(meta.get("stage_root", "")), ignore_errors=True)
                    if final_root.exists() and not final_repo.exists():
                        meta["status"] = "broken"
                        meta["error"] = "allocated worker slot is occupied by an unrecognized path"
                        meta.pop("owner_pid", None); meta.pop("owner_start", None)
                        atomic_json(mp, meta)
                        reports.append({"id": worker_id, "action": "spawn-broken-slot-collision"})
                        continue
                    # Never delete a published final path unless identity verifies as this incomplete worker.
                    if final_repo.exists():
                        try:
                            verify_worker(state, meta)
                            shutil.rmtree(final_worker_root(ws, worker_id), ignore_errors=True)
                        except Exception:
                            meta["status"] = "broken"
                            meta["error"] = "unverified path exists after interrupted spawn"
                            atomic_json(mp, meta)
                            reports.append({"id": worker_id, "action": "spawn-broken-unverified-path"})
                            continue
                    git(canonical, "update-ref", "-d", base_ref(state, worker_id), check=False)
                    meta["status"] = "spawn_failed"; meta["failed"] = time.time(); meta["error"] = "interrupted spawn recovered"
                    meta.pop("owner_pid", None); meta.pop("owner_start", None)
                    atomic_json(mp, meta)
                    reports.append({"id": worker_id, "action": "spawn-cleaned"})
                    continue

                if status == "collecting":
                    candidate = meta.get("candidate_sha")
                    ref = meta.get("candidate_ref")
                    got = git(canonical, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False) if ref else None
                    can_finish = bool(candidate and got and got.returncode == 0 and got.stdout.strip() == candidate)
                    if can_finish:
                        try:
                            snap = worker_snapshot(state, meta, require_ancestry=not meta.get("allow_rewrite", False))
                            can_finish = snap["head"] == candidate
                        except Exception:
                            can_finish = False
                    if can_finish:
                        git(canonical, "update-ref", summary_ref(state, worker_id), candidate)
                        meta.update({"status": "collected", "result_sha": candidate, "result_ref": ref, "collected": time.time()})
                        reports.append({"id": worker_id, "action": "collect-finished"})
                    else:
                        meta["status"] = "ready"
                        meta["collection_recovered"] = time.time()
                        reports.append({"id": worker_id, "action": "collect-reset-ready"})
                    for k in ("owner_pid", "owner_start", "candidate_sha", "candidate_ref"):
                        meta.pop(k, None)
                    atomic_json(mp, meta)
                    continue

                if status == "discarding":
                    final_root = final_worker_root(ws, worker_id)
                    intent = meta.get("discard_intent", "discarded")
                    if not final_root.exists():
                        meta["status"] = intent
                        meta["discarded"] = time.time()
                        reports.append({"id": worker_id, "action": "discard-finished"})
                    elif intent == "abandoned":
                        # Explicit abandonment is the durable transaction intent. After the owner
                        # dies, verify this is still our worker before completing destructive cleanup.
                        try:
                            verify_worker(state, meta)
                            shutil.rmtree(final_root)
                            meta["status"] = "abandoned"
                            meta["discarded"] = time.time()
                            reports.append({"id": worker_id, "action": "abandon-finished"})
                        except Exception as exc:
                            meta["status"] = "broken"
                            meta["error"] = f"could not safely finish abandonment: {exc}"[:1000]
                            reports.append({"id": worker_id, "action": "abandon-marked-broken"})
                    else:
                        # For a collected result, rollback is conservative: keep the worker if the
                        # filesystem deletion never happened; a caller may retry discard.
                        meta["status"] = meta.get("discard_previous", "collected")
                        reports.append({"id": worker_id, "action": "discard-reset"})
                    meta.pop("owner_pid", None); meta.pop("owner_start", None)
                    atomic_json(mp, meta)
                    continue

                if status == "ready":
                    try:
                        repo = verify_worker(state, meta)
                        # Dirty files and detached HEAD can be ordinary in-progress agent work. Recovery
                        # must not relabel or destroy them; only structural identity/branch loss is fatal.
                        branch = git(repo, "rev-parse", "--verify", f"refs/heads/{meta['branch']}^{{commit}}", check=False)
                        if branch.returncode:
                            raise CWSError("assigned task branch is missing")
                    except Exception as exc:
                        meta["status"] = "broken"; meta["error"] = str(exc)[:1000]
                        atomic_json(mp, meta)
                        reports.append({"id": worker_id, "action": "ready-marked-broken"})
                    continue

                if status == "collected":
                    ref = meta.get("result_ref")
                    got = git(canonical, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False) if ref else None
                    if not got or got.returncode or got.stdout.strip() != meta.get("result_sha"):
                        meta["status"] = "broken"; meta["error"] = "preserved result ref missing"
                        atomic_json(mp, meta)
                        reports.append({"id": worker_id, "action": "collected-marked-broken"})
                    else:
                        git(canonical, "update-ref", summary_ref(state, worker_id), meta["result_sha"])
                    continue

                if status in {"discarded", "abandoned", "spawn_failed"}:
                    stage = Path(meta.get("stage_root", ""))
                    if str(stage) and stage.exists():
                        shutil.rmtree(stage, ignore_errors=True)
                    # Only tombstone states own no published worker except an explicitly abandoned ready worker.
                    if status in {"discarded", "abandoned"} and final_worker_root(ws, worker_id).exists():
                        try:
                            verify_worker(state, meta)
                            shutil.rmtree(final_worker_root(ws, worker_id), ignore_errors=True)
                            reports.append({"id": worker_id, "action": "tombstone-path-cleaned"})
                        except Exception:
                            reports.append({"id": worker_id, "action": "tombstone-unverified-path-left"})
                    git(canonical, "update-ref", "-d", base_ref(state, worker_id), check=False)
    return reports


def status(ws_path: Path) -> dict[str, Any]:
    ws = ws_path.resolve()
    with workspace_lock(ws):
        state = read_state(ws)
        canonical = verify_canonical(state)
        workers = []
        issues: list[dict[str, Any]] = []
        files: list[Path] = []
        for mp in ws_paths(ws)["workers"].glob("*.json"):
            try:
                int(mp.stem)
            except ValueError:
                issues.append({"path": str(mp), "issue": "unexpected-metadata-file"})
                continue
            files.append(mp)
        known_ids = {int(p.stem) for p in files}
        canonical_slot = state.get("canonical_slot")
        for child in ws.iterdir():
            if child.is_dir() and child.name.isdigit():
                wid = int(child.name)
                if wid != canonical_slot and wid not in known_ids:
                    issues.append({"id": wid, "path": str(child), "issue": "orphan-worker-directory"})
        for mp in sorted(files, key=lambda p: int(p.stem)):
            worker_id = int(mp.stem)
            try:
                _, meta, _ = load_worker_state(ws, worker_id)
            except CWSError as exc:
                issues.append({"id": worker_id, "path": str(mp), "issue": "invalid-worker-metadata", "error": str(exc)})
                continue
            drift = None
            if meta.get("status") in {"ready", "collected"} and Path(meta.get("path", "")).exists():
                try:
                    snap = worker_snapshot(state, meta, require_ancestry=not meta.get("allow_rewrite", False))
                    if meta.get("status") == "collected" and snap["head"] != meta.get("result_sha"):
                        drift = "changed-after-collection"
                except Exception as exc:
                    drift = str(exc)
            item = dict(meta)
            if drift:
                item["drift"] = drift
            workers.append(item)
        return {"workspace": str(ws), "canonical": str(canonical), "workspace_id": state["workspace_id"], "workers": workers, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description="Clonegrown isolated Git workspaces")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init"); p.add_argument("canonical"); p.add_argument("workspace")
    p = sub.add_parser("spawn"); p.add_argument("workspace"); p.add_argument("--base", default="main"); p.add_argument("--task", required=True); p.add_argument("--fast", action="store_true"); p.add_argument("--request-id"); p.add_argument("--wait-seconds", type=float, default=120.0)
    p = sub.add_parser("collect"); p.add_argument("workspace"); p.add_argument("id", type=int); p.add_argument("--allow-rewrite", action="store_true")
    p = sub.add_parser("discard"); p.add_argument("workspace"); p.add_argument("id", type=int); p.add_argument("--abandon", action="store_true"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("recover"); p.add_argument("workspace")
    p = sub.add_parser("status"); p.add_argument("workspace")
    args = parser.parse_args()
    try:
        if args.command == "init":
            result = init_workspace(Path(args.canonical), Path(args.workspace))
        elif args.command == "spawn":
            result = spawn(Path(args.workspace), args.base, args.task, not args.fast, args.request_id, args.wait_seconds)
        elif args.command == "collect":
            result = collect(Path(args.workspace), args.id, args.allow_rewrite)
        elif args.command == "discard":
            result = discard(Path(args.workspace), args.id, args.abandon, args.force)
        elif args.command == "recover":
            result = recover(Path(args.workspace))
        else:
            result = status(Path(args.workspace))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except CWSError as exc:
        print(f"clonegrown: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
