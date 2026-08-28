"""Git operations on repositories: provisioning a clone, creating and repairing worktrees.

Each function does one thing to one repository and knows nothing about
workers or records. The spawn transaction calls them in a fixed order.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import subprocess

from .core import ClonegrownError, git, git_common_dir, git_dir, git_path, lexical_abs
from .state import RESERVED_SOURCE_PREFIX

# Local config that describes *this* repository's shape rather than user intent;
# a clone must derive its own values, never inherit canonical's.
STRUCTURAL_CONFIG_EXACT = {
    "core.repositoryformatversion", "core.filemode", "core.bare", "core.logallrefupdates",
    "core.worktree", "core.ignorecase", "core.precomposeunicode", "core.symlinks",
    "core.sparsecheckout", "core.sparsecheckoutcone", "index.sparse",
    # A filesystem-monitor hook is a program Git would run on every status inside the worker.
    "core.fsmonitor", "core.fsmonitorhookversion",
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
    # canonical. Values are not put in durable Clonegrown metadata, although a
    # failing Git command can currently repeat them in its public error text.
    if any(k.lower().startswith(("include.", "includeif.")) for k in raw):
        warnings.append("repo-local config includes were flattened into private worker config")
    return copied, sorted(set(warnings))


def copy_remote_config(canonical: Path, worker: Path) -> str:
    """Rename the clone's source remote out of the way, then mirror canonical's remotes.

    Returns the name given to the canonical-source remote. Its push URL uses an
    invalid transport as an accident guard; this is not a security boundary.
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


def sparse_checkout_enabled(canonical: Path) -> bool:
    enabled = git(canonical, "config", "--bool", "core.sparseCheckout", check=False)
    return enabled.returncode == 0 and enabled.stdout.strip().lower() == "true"


def copy_sparse_patterns(canonical: Path, worker: Path) -> None:
    """Copy the per-repository sparse-checkout pattern file (per-worktree for linked worktrees)."""
    src = git_path(canonical, "info/sparse-checkout")
    if not src.exists():
        raise ClonegrownError("sparse checkout is enabled but its pattern file is missing")
    dst = git_path(worker, "info/sparse-checkout")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_sparse_policy(canonical: Path, worker: Path) -> bool:
    """For a clone: replicate canonical's sparse-checkout config and patterns. False if not sparse."""
    if not sparse_checkout_enabled(canonical):
        return False
    git(worker, "config", "core.sparseCheckout", "true")
    for key in ("core.sparseCheckoutCone", "index.sparse"):
        value = git(canonical, "config", "--get", key, check=False)
        if value.returncode == 0 and value.stdout.strip():
            git(worker, "config", key, value.stdout.strip())
    copy_sparse_patterns(canonical, worker)
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


def checkout_without_hooks(repo: Path, branch: str, base_sha: str, create: bool = True) -> None:
    """Populate the checkout without running repository hooks.

    The worker keeps its configured hooks for the agent's later commands; only
    this provisioning checkout is suppressed. With ``create`` the branch is
    made here (a clone's private refs); otherwise it must already exist at
    ``base_sha`` (a worktree's branch lives in the shared refs and is created
    by :func:`create_task_branch` first).
    """
    with tempfile.TemporaryDirectory(prefix="cws-empty-hooks-") as empty:
        if create:
            git(repo, "-c", f"core.hooksPath={empty}", "checkout", "-b", branch, base_sha)
        else:
            git(repo, "-c", f"core.hooksPath={empty}", "checkout", branch)


# --- task branches in shared refs (worktree mode) ------------------------------

def _ref_transaction(repo: Path, lines: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one atomic ``git update-ref --stdin`` transaction; all updates apply or none do.

    Every update is ``no-deref``: a symbolic ref planted under a name we own
    must never redirect the write onto the branch it points at.
    """
    script = "start\n" + "".join(f"option no-deref\n{line}\n" for line in lines) + "prepare\ncommit\n"
    return git(repo, "update-ref", "--stdin", check=False, input=script)


def _refuse_symbolic(repo: Path, ref: str, check: bool) -> bool:
    """A symbolic ref under one of our names is never ours: neither written through nor deleted."""
    if not is_symbolic_ref(repo, ref):
        return False
    if check:
        raise ClonegrownError(f"refusing to touch a symbolic ref in Clonegrown's namespace: {ref}")
    return True


def write_ref(repo: Path, ref: str, new_sha: str, old_sha: str | None = None, check: bool = True) -> bool:
    """Point ``ref`` itself at ``new_sha``; optional compare-and-swap. A symbolic ref is refused."""
    if _refuse_symbolic(repo, ref, check):
        return False
    args = ["update-ref", "--no-deref", ref, new_sha] + ([old_sha] if old_sha is not None else [])
    return git(repo, *args, check=check).returncode == 0


def delete_ref(repo: Path, ref: str, old_sha: str | None = None, check: bool = True) -> bool:
    """Delete ``ref`` itself; optional compare-and-swap. A symbolic ref is refused."""
    if _refuse_symbolic(repo, ref, check):
        return False
    args = ["update-ref", "--no-deref", "-d", ref] + ([old_sha] if old_sha is not None else [])
    return git(repo, *args, check=check).returncode == 0


def is_symbolic_ref(repo: Path, ref: str) -> bool:
    return git(repo, "symbolic-ref", "-q", ref, check=False).returncode == 0


def create_task_branch(canonical: Path, branch: str, owner_ref: str, base_sha: str) -> None:
    """Create the task branch and this worker's private ownership ref together, or neither.

    Both use create-only semantics (expected old value zero): a branch that
    already exists under the deterministic name aborts the whole transaction
    untouched. The ownership ref is what later proves this worker created the
    branch, even if the process dies before the record is updated.
    """
    outcome = _ref_transaction(canonical, [
        f"create refs/heads/{branch} {base_sha}",
        f"create {owner_ref} {base_sha}",
    ])
    if outcome.returncode:
        raise ClonegrownError(
            f"could not create task branch {branch}: it or its ownership ref already exists "
            f"({outcome.stderr.strip()})")


def absent_marker(like_sha: str) -> str:
    """The all-zero object id of the repository's format: how Git itself spells "no such ref"."""
    return "0" * len(like_sha)


def is_absent_marker(sha: str) -> bool:
    return bool(sha) and set(sha) == {"0"}


def resolve_ref(repo: Path, ref: str) -> str | None:
    """The commit ``ref`` names, or None if it does not exist."""
    got = git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    return got.stdout.strip() if got.returncode == 0 and got.stdout.strip() else None


def branch_checkouts(canonical: Path, branch: str) -> list[str]:
    """Working trees of ``canonical`` (itself included) that currently have ``branch`` checked out.

    The NUL-delimited listing is unambiguous for any path; an older Git
    without ``-z`` falls back to the line form, where a newline in a path
    cannot be told apart from a record boundary.
    """
    listing = git(canonical, "worktree", "list", "--porcelain", "-z", check=False)
    if listing.returncode == 0:
        records = [record.split("\0") for record in listing.stdout.split("\0\0") if record]
    else:
        records = [record.split("\n") for record in git(canonical, "worktree", "list", "--porcelain").stdout.split("\n\n")
                   if record]
    paths: list[str] = []
    for lines in records:
        path = next((line[len("worktree "):] for line in lines if line.startswith("worktree ")), None)
        if path is not None and f"branch refs/heads/{branch}" in lines:
            paths.append(path)
    return paths


def release_task_branch(canonical: Path, branch: str, owner_ref: str, owner_sha: str,
                        expected_sha: str | None, own_paths: set[Path] = frozenset()) -> str | None:
    """Delete the task branch only while it still points where we recorded, and only if we own it.

    Nothing of ours is deleted when the branch was recorded as absent, or is
    absent now: only the ownership ref goes, and any branch someone else has
    since put under the name is left alone. Otherwise one transaction deletes
    the branch at its recorded tip and the ownership ref at its recorded
    value; each ``delete`` with an old value is itself a compare-and-swap. A
    branch that moved, or that some working tree other than the worker's own
    (``own_paths``) has checked out, is retained and the conflict is returned
    as text.
    """
    current = resolve_ref(canonical, f"refs/heads/{branch}")
    ours = expected_sha is not None and not is_absent_marker(expected_sha) and current is not None
    lines = []
    if ours:
        elsewhere = [path for path in branch_checkouts(canonical, branch) if lexical_abs(path) not in own_paths]
        if elsewhere:
            return f"task branch retained: checked out at {', '.join(elsewhere)}"
        lines.append(f"delete refs/heads/{branch} {expected_sha}")
    lines.append(f"delete {owner_ref} {owner_sha}")
    outcome = _ref_transaction(canonical, lines)
    if outcome.returncode == 0:
        return None
    if ours and resolve_ref(canonical, f"refs/heads/{branch}") != expected_sha:
        return (f"task branch retained: expected {expected_sha}, found "
                f"{resolve_ref(canonical, f'refs/heads/{branch}') or 'no branch'}")
    return f"task branch retained: ownership ref changed ({outcome.stderr.strip()})"


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


def ref_points_at(repo: Path, ref: str | None, sha: str | None) -> bool:
    """Does ``ref`` exist in ``repo`` and resolve to commit ``sha``?"""
    if not ref:
        return False
    got = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    return got.returncode == 0 and got.stdout.strip() == sha
