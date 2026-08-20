"""Clonegrown implementation layer."""
from clonegrown_core import *  # noqa: F401,F403



def process_alive(pid: Any, fingerprint: Any = None) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM
    if fingerprint is not None:
        return pid_fingerprint(pid) == str(fingerprint)
    return True


def owner_fields() -> dict[str, Any]:
    return {"owner_pid": os.getpid(), "owner_start": pid_fingerprint(os.getpid()), "heartbeat": time.time()}


def canonical_ref_prefix(state: dict[str, Any]) -> str:
    return f"refs/cws/{state['workspace_id']}"


def base_ref(state: dict[str, Any], worker_id: int) -> str:
    return f"{canonical_ref_prefix(state)}/bases/{worker_id}"


def summary_ref(state: dict[str, Any], worker_id: int) -> str:
    return f"{canonical_ref_prefix(state)}/workers/{worker_id}/result"


def immutable_result_ref(state: dict[str, Any], worker_id: int, sha: str) -> str:
    return f"{canonical_ref_prefix(state)}/workers/{worker_id}/results/{sha}"


def sanitize_task(task: str) -> str:
    s = task.strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"[-_.]{2,}", "-", s).strip("-._")
    return (s or "task")[:48]


def params_hash(base: str, task: str, strong: bool) -> str:
    raw = json.dumps({"base": base, "task": task, "strong": bool(strong)}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def init_workspace(canonical_path: Path, ws_path: Path) -> dict[str, Any]:
    canonical = validate_primary_repo(canonical_path)
    ws = ws_path.resolve()
    if ws == canonical or inside(ws, canonical):
        raise CWSError("workspace cannot be the canonical repository or live inside its working tree")
    paths = ws_paths(ws)
    for p in (paths["workers"], paths["requests"], paths["locks"], paths["staging"]):
        p.mkdir(parents=True, exist_ok=True)
    with workspace_lock(ws):
        if paths["state"].exists():
            state = load_json(paths["state"])
            validate_state(ws, state, require_ready=False)
            if Path(state.get("canonical", "")).resolve() != canonical:
                raise CWSError("workspace is already initialized for a different canonical path")
            if state.get("schema") != SCHEMA:
                raise CWSError("unsupported workspace metadata schema")
            if state.get("status") == "initializing":
                # Complete either crash window: after state write or after marker write.
                marker_path = canonical_marker_path(canonical, state["workspace_id"])
                if marker_path.exists():
                    marker = load_json(marker_path)
                    if marker.get("token") != state.get("canonical_token"):
                        raise CWSError("initializing workspace has a conflicting canonical marker")
                else:
                    atomic_json(marker_path, {"workspace_id": state["workspace_id"], "token": state["canonical_token"], "canonical": str(canonical), "created": time.time()})
                state["status"] = "ready"
                atomic_json(paths["state"], state)
            verify_canonical(state)
            return state
        workspace_id = uuid.uuid4().hex[:16]
        token = secrets.token_hex(24)
        marker = canonical_marker_path(canonical, workspace_id)
        state = {
            "schema": SCHEMA,
            "status": "initializing",
            "workspace_id": workspace_id,
            "canonical_token": token,
            "workspace": str(ws),
            "canonical": str(canonical),
            "canonical_git_dir": str(git_common_dir(canonical)),
            "object_format": object_format(canonical),
            "repo_name": canonical.name,
            "next_id": 1,
            "created": time.time(),
        }
        # If canonical already lives under a numeric top-level workspace slot, reserve it.
        if inside(canonical, ws):
            rel = canonical.relative_to(ws)
            if rel.parts and rel.parts[0].isdigit():
                state["next_id"] = max(state["next_id"], int(rel.parts[0]) + 1)
                state["canonical_slot"] = int(rel.parts[0])
        atomic_json(paths["state"], state)
        failpoint("init.after_state")
        atomic_json(marker, {"workspace_id": workspace_id, "token": token, "canonical": str(canonical), "created": time.time()})
        failpoint("init.after_marker")
        state["status"] = "ready"
        atomic_json(paths["state"], state)
        return state


def read_state(ws: Path) -> dict[str, Any]:
    validate_control_dir(ws, require_state=True)
    state = load_json(ws_paths(ws)["state"])
    validate_state(ws, state, require_ready=True)
    return state


def validate_state(ws: Path, state: dict[str, Any], require_ready: bool = True) -> None:
    if state.get("schema") != SCHEMA:
        raise CWSError("unsupported workspace metadata schema")
    if require_ready and state.get("status") != "ready":
        raise CWSError(f"workspace is not ready: {state.get('status')}")
    if state.get("status") not in {"initializing", "ready"}:
        raise CWSError(f"unknown workspace state: {state.get('status')!r}")
    workspace_id = state.get("workspace_id")
    token = state.get("canonical_token")
    if not isinstance(workspace_id, str) or not re.fullmatch(r"[0-9a-f]{16}", workspace_id):
        raise CWSError("workspace ID is malformed")
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{48}", token):
        raise CWSError("canonical identity token is malformed")
    if lexical_abs(state.get("workspace", "")) != lexical_abs(ws):
        raise CWSError("workspace path identity changed")
    repo_name = state.get("repo_name")
    if (not isinstance(repo_name, str) or not repo_name or repo_name in {".", ".."}
            or Path(repo_name).is_absolute() or Path(repo_name).name != repo_name
            or "/" in repo_name or "\\" in repo_name):
        raise CWSError("repository name in workspace state is unsafe")
    if state.get("object_format") not in {"sha1", "sha256"}:
        raise CWSError("unsupported object format in workspace state")
    if type(state.get("next_id")) is not int or state["next_id"] < 1:
        raise CWSError("workspace next worker ID is malformed")
    canonical = state.get("canonical")
    canonical_git = state.get("canonical_git_dir")
    if not isinstance(canonical, str) or lexical_abs(canonical) != Path(canonical):
        raise CWSError("canonical path in workspace state is not normalized")
    if not isinstance(canonical_git, str) or lexical_abs(canonical_git) != Path(canonical_git):
        raise CWSError("canonical Git path in workspace state is not normalized")
    slot = state.get("canonical_slot")
    if slot is not None and (type(slot) is not int or slot < 1):
        raise CWSError("canonical slot metadata is malformed")


def verify_canonical(state: dict[str, Any]) -> Path:
    canonical = validate_primary_repo(Path(state["canonical"]))
    if str(canonical) != str(Path(state["canonical"]).resolve()):
        raise CWSError("canonical root changed")
    common = git_common_dir(canonical)
    if common != Path(state["canonical_git_dir"]).resolve():
        raise CWSError("canonical Git directory identity changed")
    if object_format(canonical) != state.get("object_format"):
        raise CWSError("canonical object format changed")
    marker_path = canonical_marker_path(canonical, state["workspace_id"])
    marker = load_json(marker_path)
    if (marker.get("token") != state.get("canonical_token")
            or marker.get("workspace_id") != state.get("workspace_id")
            or lexical_abs(marker.get("canonical", "")) != lexical_abs(canonical)):
        raise CWSError("canonical repository identity marker mismatch")
    return canonical


def local_config_items(repo: Path, includes: bool = False) -> dict[str, list[str]]:
    include_flag = "--includes" if includes else "--no-includes"
    p = git(repo, "config", "--local", include_flag, "--null", "--list", check=False)
    if p.returncode:
        return {}
    parts = p.stdout.split("\0")
    out: dict[str, list[str]] = {}
    for item in parts:
        if not item:
            continue
        if "\n" in item:
            key, value = item.split("\n", 1)
        elif "=" in item:
            key, value = item.split("=", 1)
        else:
            key, value = item, ""
        out.setdefault(key, []).append(value)
    return out


def copy_local_config(canonical: Path, worker: Path) -> tuple[list[str], list[str]]:
    copied: list[str] = []
    warnings: list[str] = []
    raw = local_config_items(canonical, includes=False)
    effective = local_config_items(canonical, includes=True)
    for key, values in effective.items():
        lower = key.lower()
        if lower in STRUCTURAL_CONFIG_EXACT or lower.startswith(STRUCTURAL_CONFIG_PREFIXES):
            continue
        if lower == "core.hookspath":
            # Relative tracked hook paths are portable. Absolute/outside paths remain shared and are surfaced.
            for value in values:
                if os.path.isabs(value):
                    warnings.append("absolute core.hooksPath remains an external shared dependency")
            # It is still copied for compatibility; the warning makes the boundary explicit.
        if any(str(canonical) in value for value in values):
            warnings.append(f"path-bound local config omitted: {key}")
            continue
        git(worker, "config", "--local", "--unset-all", key, check=False)
        for value in values:
            git(worker, "config", "--local", "--add", key, value)
        copied.append(key)
    # Include directives themselves are not copied. Their *effective local-scope values* above
    # are flattened into the worker, so relative/conditional include paths cannot bind the
    # worker back to canonical. Values are never recorded in CWS metadata.
    if any(k.lower().startswith(("include.", "includeif.")) for k in raw):
        warnings.append("repo-local config includes were flattened into private worker config")
    return copied, sorted(set(warnings))
