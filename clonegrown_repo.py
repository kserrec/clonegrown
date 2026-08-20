"""Clonegrown implementation layer."""
from clonegrown_state import *  # noqa: F401,F403



def copy_remote_config(canonical: Path, worker: Path) -> str:
    canonical_remotes = set(git(canonical, "remote").stdout.split())
    source = RESERVED_SOURCE_PREFIX
    n = 2
    while source in canonical_remotes:
        source = f"{RESERVED_SOURCE_PREFIX}-{n}"
        n += 1
    clone_remotes = set(git(worker, "remote").stdout.split())
    if "origin" not in clone_remotes:
        raise CWSError("local clone did not create its source remote")
    git(worker, "remote", "rename", "origin", source)
    # Invalid transport helper name prevents accidental push. This is not a security sandbox: an agent can still
    # address the canonical filesystem path directly if the harness lets it escape its directory.
    git(worker, "remote", "set-url", "--push", source, "cws-disabled://canonical")

    config = local_config_items(canonical, includes=True)
    for name in sorted(canonical_remotes):
        urls = git(canonical, "remote", "get-url", "--all", name, check=False).stdout.splitlines()
        if not urls:
            continue
        git(worker, "remote", "add", name, urls[0])
        for url in urls[1:]:
            git(worker, "remote", "set-url", "--add", name, url)
        push_urls = git(canonical, "remote", "get-url", "--push", "--all", name, check=False).stdout.splitlines()
        if push_urls and push_urls != urls:
            git(worker, "remote", "set-url", "--delete", "--push", name, ".*", check=False)
            for url in push_urls:
                git(worker, "remote", "set-url", "--add", "--push", name, url)
        prefix = f"remote.{name}.".lower()
        for key, values in config.items():
            low = key.lower()
            if not low.startswith(prefix) or low in {prefix + "url", prefix + "pushurl"}:
                continue
            git(worker, "config", "--local", "--unset-all", key, check=False)
            for value in values:
                git(worker, "config", "--local", "--add", key, value)
    return source



def copy_replace_refs(canonical: Path, worker: Path) -> int:
    """Preserve refs/replace semantics because they can change commit/tree interpretation."""
    refs = git(canonical, "for-each-ref", "--format=%(refname)", "refs/replace/").stdout.splitlines()
    refs = [r for r in refs if r.startswith("refs/replace/")]
    if not refs:
        return 0
    git(worker, "fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
        str(canonical), "+refs/replace/*:refs/replace/*")
    return len(refs)


def copy_auxiliary_refs(canonical: Path, worker: Path) -> dict[str, int]:
    """Snapshot local ref classes that ordinary clone does not preserve.

    Remote-tracking refs matter when workers are offline and compare against
    origin/main. Notes can affect review tooling. Replace refs can change how
    commit/tree history is interpreted, so they are correctness-critical.
    Deliberately excluded: refs/stash, CWS private refs, and transient
    operation refs. Those should remain isolated.
    """
    classes = {
        "remote_tracking": "refs/remotes/",
        "notes": "refs/notes/",
        "replace": "refs/replace/",
    }
    counts: dict[str, int] = {}
    for label, prefix in classes.items():
        refs = [r for r in git(canonical, "for-each-ref", "--format=%(refname)", prefix).stdout.splitlines()
                if r.startswith(prefix)]
        counts[label] = len(refs)
        if refs:
            git(worker, "fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
                str(canonical), f"+{prefix}*:{prefix}*")
    return counts


def checkout_without_hooks(repo: Path, branch: str, base_sha: str) -> None:
    """Populate the helper-owned checkout without executing repository hooks.

    The resulting worker keeps its configured hooks for later agent commands;
    only the provisioning checkout is suppressed.
    """
    empty = git_common_dir(repo) / "cws-provisioning-empty-hooks"
    empty.mkdir(parents=True, exist_ok=True)
    try:
        git(repo, "-c", f"core.hooksPath={empty}", "checkout", "-b", branch, base_sha)
    finally:
        shutil.rmtree(empty, ignore_errors=True)

def git_path(repo: Path, rel: str) -> Path:
    out = git(repo, "rev-parse", "--git-path", rel).stdout.strip()
    p = Path(out)
    return p if p.is_absolute() else (repo / p).resolve()


def copy_info_files(canonical: Path, worker: Path) -> None:
    for rel in ("info/exclude", "info/attributes"):
        src = git_path(canonical, rel)
        dst = git_path(worker, rel)
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def private_hook_warnings(canonical: Path) -> list[str]:
    hooks = git_common_dir(canonical) / "hooks"
    if not hooks.exists():
        return []
    active = [p.name for p in hooks.iterdir() if p.is_file() and not p.name.endswith(".sample") and os.access(p, os.X_OK)]
    return ["private .git hooks are not copied: " + ", ".join(sorted(active))] if active else []


def copy_sparse_policy(canonical: Path, worker: Path) -> bool:
    enabled = git(canonical, "config", "--bool", "core.sparseCheckout", check=False)
    if enabled.returncode or enabled.stdout.strip().lower() != "true":
        return False
    git(worker, "config", "core.sparseCheckout", "true")
    for key in ("core.sparseCheckoutCone", "index.sparse"):
        value = git(canonical, "config", "--get", key, check=False)
        if value.returncode == 0 and value.stdout.strip():
            git(worker, "config", key, value.stdout.strip())
    src = git_path(canonical, "info/sparse-checkout")
    dst = git_path(worker, "info/sparse-checkout")
    if not src.exists():
        raise CWSError("sparse checkout is enabled but its pattern file is missing")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def detach_alternates_if_needed(worker: Path, strong: bool) -> tuple[bool, list[str]]:
    alt = git_common_dir(worker) / "objects" / "info" / "alternates"
    if not alt.exists():
        return False, []
    if not strong:
        return False, ["fast worker depends on an alternate object database"]
    git(worker, "repack", "-a", "-d")
    alt.unlink(missing_ok=True)
    git(worker, "fsck", "--connectivity-only")
    return True, []
