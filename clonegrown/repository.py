"""Git operations on repositories: provisioning a clone, creating and repairing worktrees.

Each function does one thing to one repository and knows nothing about
workers or records. The spawn transaction calls them in a fixed order.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from .core import ClonegrownError, git, git_common_dir, git_dir, git_path
from .state import RESERVED_SOURCE_PREFIX

# Local config that describes *this* repository's shape rather than user intent;
# a clone must derive its own values, never inherit canonical's.
STRUCTURAL_CONFIG_EXACT = {
    "core.repositoryformatversion", "core.filemode", "core.bare", "core.logallrefupdates",
    "core.worktree", "core.ignorecase", "core.precomposeunicode", "core.symlinks",
    "core.sparsecheckout", "core.sparsecheckoutcone", "index.sparse",
}
STRUCTURAL_CONFIG_PREFIXES = ("remote.", "branch.", "extensions.", "include.", "includeif.")

_FETCH_FLAGS = ("fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance")


def local_config_items(repo: Path, includes: bool = False) -> dict[str, list[str]]:
    include_flag = "--includes" if includes else "--no-includes"
    p = git(repo, "config", "--local", include_flag, "--null", "--list", check=False)
    if p.returncode:
        return {}
    out: dict[str, list[str]] = {}
    for item in p.stdout.split("\0"):
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


def _set_config_values(repo: Path, key: str, values: list[str]) -> None:
    git(repo, "config", "--local", "--unset-all", key, check=False)
    for value in values:
        git(repo, "config", "--local", "--add", key, value)


def copy_local_config(canonical: Path, worker: Path) -> tuple[list[str], list[str]]:
    """Copy user-intent local config; return (copied keys, compatibility warnings)."""
    copied: list[str] = []
    warnings: list[str] = []
    raw = local_config_items(canonical, includes=False)
    effective = local_config_items(canonical, includes=True)
    for key, values in effective.items():
        lower = key.lower()
        if lower in STRUCTURAL_CONFIG_EXACT or lower.startswith(STRUCTURAL_CONFIG_PREFIXES):
            continue
        if lower == "core.hookspath" and any(os.path.isabs(v) for v in values):
            # Relative tracked hook paths are portable. Absolute ones stay shared; the
            # value is still copied for compatibility and the warning makes that explicit.
            warnings.append("absolute core.hooksPath remains an external shared dependency")
        if any(str(canonical) in value for value in values):
            warnings.append(f"path-bound local config omitted: {key}")
            continue
        _set_config_values(worker, key, values)
        copied.append(key)
    # Include directives are not copied. Their *effective* values were flattened in
    # above, so a relative or conditional include cannot bind the worker back to
    # canonical. Values are never recorded in Clonegrown metadata.
    if any(k.lower().startswith(("include.", "includeif.")) for k in raw):
        warnings.append("repo-local config includes were flattened into private worker config")
    return copied, sorted(set(warnings))


def copy_remote_config(canonical: Path, worker: Path) -> str:
    """Rename the clone's source remote out of the way, then mirror canonical's remotes.

    Returns the name given to the canonical-source remote. Its push URL is an
    invalid transport so an accidental push fails; this is not a sandbox.
    """
    canonical_remotes = set(git(canonical, "remote").stdout.split())
    source = RESERVED_SOURCE_PREFIX
    n = 2
    while source in canonical_remotes:
        source = f"{RESERVED_SOURCE_PREFIX}-{n}"
        n += 1
    if "origin" not in set(git(worker, "remote").stdout.split()):
        raise ClonegrownError("local clone did not create its source remote")
    git(worker, "remote", "rename", "origin", source)
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
            if low.startswith(prefix) and low not in {prefix + "url", prefix + "pushurl"}:
                _set_config_values(worker, key, values)
    return source


def copy_auxiliary_refs(canonical: Path, worker: Path) -> dict[str, int]:
    """Snapshot local ref classes that an ordinary clone does not preserve.

    Remote-tracking refs matter when workers are offline and compare against
    origin/main. Notes can affect review tooling. Replace refs change how
    history is interpreted, so they are correctness-critical. Deliberately
    excluded: refs/stash, Clonegrown's private refs, and transient operation
    refs; those stay isolated.
    """
    classes = {"remote_tracking": "refs/remotes/", "notes": "refs/notes/", "replace": "refs/replace/"}
    counts: dict[str, int] = {}
    for label, prefix in classes.items():
        refs = [r for r in git(canonical, "for-each-ref", "--format=%(refname)", prefix).stdout.splitlines()
                if r.startswith(prefix)]
        counts[label] = len(refs)
        if refs:
            git(worker, *_FETCH_FLAGS, str(canonical), f"+{prefix}*:{prefix}*")
    return counts


def copy_info_files(canonical: Path, worker: Path) -> None:
    for rel in ("info/exclude", "info/attributes"):
        src = git_path(canonical, rel)
        if src.exists():
            dst = git_path(worker, rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


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
    if not src.exists():
        raise ClonegrownError("sparse checkout is enabled but its pattern file is missing")
    dst = git_path(worker, "info/sparse-checkout")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def private_hook_warnings(canonical: Path) -> list[str]:
    hooks = git_common_dir(canonical) / "hooks"
    if not hooks.exists():
        return []
    active = [p.name for p in hooks.iterdir()
              if p.is_file() and not p.name.endswith(".sample") and os.access(p, os.X_OK)]
    return ["private .git hooks are not copied: " + ", ".join(sorted(active))] if active else []


def detach_alternates_if_needed(worker: Path, strong: bool) -> tuple[bool, list[str]]:
    """Strong workers must own their objects; fast workers may borrow and are told so."""
    alt = git_common_dir(worker) / "objects" / "info" / "alternates"
    if not alt.exists():
        return False, []
    if not strong:
        return False, ["fast worker depends on an alternate object database"]
    git(worker, "repack", "-a", "-d")
    alt.unlink(missing_ok=True)
    git(worker, "fsck", "--connectivity-only")
    return True, []


def checkout_without_hooks(repo: Path, branch: str, base_sha: str) -> None:
    """Populate the checkout without running repository hooks.

    The worker keeps its configured hooks for the agent's later commands; only
    this provisioning checkout is suppressed.
    """
    with tempfile.TemporaryDirectory(prefix="cws-empty-hooks-") as empty:
        git(repo, "-c", f"core.hooksPath={empty}", "checkout", "-b", branch, base_sha)


# --- linked worktrees --------------------------------------------------------

WORKTREE_SHARING_WARNING = (
    "worktree worker shares canonical Git configuration, remotes, refs, stash, and hooks"
)


def add_worktree(canonical: Path, path: Path, base_sha: str) -> Path:
    """Create a detached, unpopulated linked worktree; return its private admin directory."""
    git(canonical, "worktree", "add", "--no-checkout", "--detach", path, base_sha)
    return git_dir(path)


def repair_worktree(canonical: Path, path: Path) -> None:
    """Fix Git's back-pointer after a worktree directory has been renamed."""
    git(canonical, "worktree", "repair", path)


def delete_branch(canonical: Path, branch: str) -> bool:
    """Remove a worker's task branch from the shared refs; False if it was already gone."""
    return git(canonical, "branch", "-D", branch, check=False).returncode == 0
