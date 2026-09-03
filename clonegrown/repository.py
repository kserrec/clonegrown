"""Git operations on repositories: provisioning a clone, creating and repairing worktrees.

Each function does one thing to one repository and knows nothing about
workers or records. The spawn transaction calls them in a fixed order.
"""
from __future__ import annotations

import contextlib
import os
import re
import secrets
import shutil
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import subprocess

from . import core as core_module
from .core import CommandFailure, ClonegrownError, git, git_common_dir, git_dir, git_path, lexical_abs
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
_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_CONFIG_SECTION = re.compile(r"[A-Za-z0-9.-]+")
_CONFIG_VARIABLE = re.compile(r"[A-Za-z][A-Za-z0-9-]*")


@dataclass(frozen=True)
class ConfigOccurrence:
    """One ordered Git-config occurrence; ``None`` means valueless, not empty."""

    key: str
    value: str | None


@dataclass(frozen=True)
class CloneConfigPlan:
    """The complete, validated remote and local-config intent for one clone."""

    source_remote: str
    remote_names: tuple[str, ...]
    occurrences: tuple[ConfigOccurrence, ...]
    copied_local_config: tuple[str, ...]
    compatibility_warnings: tuple[str, ...]

    def validate(self) -> None:
        if not self.source_remote or self.source_remote in self.remote_names:
            raise ClonegrownError("clone config plan has a colliding source remote")
        if len(set(self.remote_names)) != len(self.remote_names):
            raise ClonegrownError("clone config plan contains duplicate remote names")
        if any(not occurrence.key or "\0" in occurrence.key or "\n" in occurrence.key
               for occurrence in self.occurrences):
            raise ClonegrownError("clone config plan contains an invalid config key")
        for occurrence in self.occurrences:
            _split_config_key(occurrence.key)
        if any(occurrence.value is not None and "\0" in occurrence.value
               for occurrence in self.occurrences):
            raise ClonegrownError("clone config plan contains an invalid config value")

        remote_occurrences = {name: 0 for name in self.remote_names}
        local_keys: list[str] = []
        seen_local: set[str] = set()
        for occurrence in self.occurrences:
            remote = _remote_name_for_key(occurrence.key, self.remote_names)
            if occurrence.key.lower().startswith("remote.") and remote is None:
                raise ClonegrownError("clone config plan contains config for an unknown remote")
            if remote is not None:
                remote_occurrences[remote] += 1
            elif occurrence.key not in seen_local:
                seen_local.add(occurrence.key)
                local_keys.append(occurrence.key)
        if any(count == 0 for count in remote_occurrences.values()):
            raise ClonegrownError("canonical repository has an empty remote section that cannot be reproduced")
        if tuple(local_keys) != self.copied_local_config:
            raise ClonegrownError("clone config plan's local-key summary is inconsistent")


def local_config_occurrences(repo: Path, includes: bool = False) -> tuple[ConfigOccurrence, ...]:
    """Read local config exactly once, preserving order, repeats, empty, and valueless entries."""
    include_flag = "--includes" if includes else "--no-includes"
    p = git(repo, "config", "--local", include_flag, "--null", "--list")
    out: list[ConfigOccurrence] = []
    for item in p.stdout.split("\0"):
        if not item:
            continue
        if "\n" in item:
            key, value = item.split("\n", 1)
        else:
            key, value = item, None
        out.append(ConfigOccurrence(key, value))
    return tuple(out)


def _remote_name_for_key(key: str, remote_names: tuple[str, ...]) -> str | None:
    if not key.lower().startswith("remote."):
        return None
    remainder = key[len("remote."):]
    for name in sorted(remote_names, key=len, reverse=True):
        if remainder.startswith(name + "."):
            return name
    return None


def _split_config_key(key: str) -> tuple[str, str]:
    section, separator, variable = key.rpartition(".")
    if (not separator or not section or not _CONFIG_VARIABLE.fullmatch(variable)):
        raise ClonegrownError("clone config plan contains an invalid config key")
    if not _CONFIG_SECTION.fullmatch(section):
        # A subsection may contain any character except newline or NUL. In a
        # fully qualified key it follows the first dot; the leading section
        # name itself retains Git's restricted grammar.
        leading_section, subsection_separator, _subsection = section.partition(".")
        if (not subsection_separator
                or not _CONFIG_SECTION.fullmatch(leading_section)):
            raise ClonegrownError("clone config plan contains an invalid config key")
    if "\0" in section or "\n" in section:
        raise ClonegrownError("clone config plan contains an invalid config key")
    return section, variable


def _remote_key_suffix(key: str, remote: str) -> str:
    return key[len("remote.") + len(remote) + 1:].lower()


def _canonicalize_remote_url(canonical: Path, value: str) -> str:
    """Anchor only relative local-path syntax; transports retain their exact spelling."""
    if not value or os.path.isabs(value) or _URL_SCHEME.match(value):
        return value
    colon = value.find(":")
    slash = value.find("/")
    if colon > 0 and (slash < 0 or colon < slash):
        return value  # scp-like ``host:path`` or ``user@host:path`` syntax
    return str((canonical / value).resolve())


def build_clone_config_plan(canonical: Path) -> CloneConfigPlan:
    """Read canonical once into a mutation-free, self-validating clone plan."""
    canonical = canonical.resolve()
    raw = local_config_occurrences(canonical, includes=False)
    effective = local_config_occurrences(canonical, includes=True)
    remote_names = tuple(line for line in git(canonical, "remote").stdout.splitlines() if line)

    source = RESERVED_SOURCE_PREFIX
    n = 2
    while source in remote_names:
        source = f"{RESERVED_SOURCE_PREFIX}-{n}"
        n += 1

    grouped: dict[str, list[str | None]] = {}
    for occurrence in effective:
        grouped.setdefault(occurrence.key, []).append(occurrence.value)

    copied_keys: list[str] = []
    warnings: list[str] = []
    eligible_local: set[str] = set()
    for key, values in grouped.items():
        lower = key.lower()
        if lower in STRUCTURAL_CONFIG_EXACT or lower.startswith(STRUCTURAL_CONFIG_PREFIXES):
            continue
        strings = [value for value in values if value is not None]
        if lower == "core.hookspath" and any(os.path.isabs(value) for value in strings):
            # Relative tracked hook paths are portable. Absolute ones stay shared; the
            # value is still copied for compatibility and the warning makes that explicit.
            warnings.append("absolute core.hooksPath remains an external shared dependency")
        if any(str(canonical) in value for value in strings):
            warnings.append(f"path-bound local config omitted: {key}")
            continue
        eligible_local.add(key)
        copied_keys.append(key)

    planned: list[ConfigOccurrence] = []
    for occurrence in effective:
        remote = _remote_name_for_key(occurrence.key, remote_names)
        if remote is not None:
            value = occurrence.value
            if value is not None and _remote_key_suffix(occurrence.key, remote) in {"url", "pushurl"}:
                value = _canonicalize_remote_url(canonical, value)
            planned.append(ConfigOccurrence(occurrence.key, value))
        elif occurrence.key in eligible_local:
            planned.append(occurrence)

    # Include directives are not copied. Their effective values are represented
    # directly in ``planned``, so no include can bind the worker back to canonical.
    if any(occurrence.key.lower().startswith(("include.", "includeif.")) for occurrence in raw):
        warnings.append("repo-local config includes were flattened into private worker config")

    plan = CloneConfigPlan(
        source_remote=source,
        remote_names=remote_names,
        occurrences=tuple(planned),
        copied_local_config=tuple(copied_keys),
        compatibility_warnings=tuple(sorted(set(warnings))),
    )
    plan.validate()
    return plan


def _normalize_valueless_config(repo: Path, sentinel: str, expected: int) -> None:
    """Turn Git-serialized sentinel values into genuinely valueless entries atomically."""
    config_path = git_path(repo, "config")
    original = config_path.read_bytes()
    needle = f" = {sentinel}\n".encode()
    if original.count(needle) != expected:
        raise ClonegrownError("could not preserve valueless Git-config occurrences")
    replacement = original.replace(needle, b"\n")
    fd, temporary = tempfile.mkstemp(prefix="config.clonegrown-", dir=config_path.parent)
    try:
        os.fchmod(fd, config_path.stat().st_mode & 0o7777)
        with os.fdopen(fd, "wb") as handle:
            handle.write(replacement)
            handle.flush()
            os.fsync(handle.fileno())
        fd = -1
        os.replace(temporary, config_path)
        directory_fd = os.open(config_path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if fd >= 0:
            os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def apply_clone_config_plan(worker: Path, plan: CloneConfigPlan) -> tuple[str, list[str], list[str]]:
    """Apply one validated plan to the staged clone through a single imperative path."""
    plan.validate()
    for name in (plan.source_remote, *plan.remote_names):
        valid = git(worker, "check-ref-format", f"refs/remotes/{name}", check=False)
        if valid.returncode:
            raise ClonegrownError(f"clone config plan contains an invalid remote name: {name!r}")
    if "origin" not in set(git(worker, "remote").stdout.splitlines()):
        raise ClonegrownError("local clone did not create its source remote")
    git(worker, "remote", "rename", "origin", plan.source_remote)
    disabled_push = "cws-disabled://canonical"
    git(worker, "remote", "set-url", "--push", plan.source_remote, disabled_push,
        sensitive=(disabled_push,))

    # Let Git validate and create each named remote. The exact planned config is
    # written immediately afterwards, replacing any default fetch refspec it adds.
    for name in plan.remote_names:
        first_url = next((occurrence.value for occurrence in plan.occurrences
                          if _remote_name_for_key(occurrence.key, plan.remote_names) == name
                          and _remote_key_suffix(occurrence.key, name) == "url"), None)
        if any(_remote_name_for_key(occurrence.key, plan.remote_names) == name
               and _remote_key_suffix(occurrence.key, name) == "url"
               for occurrence in plan.occurrences):
            initial_url = first_url or ""
            git(worker, "remote", "add", "--", name, initial_url, sensitive=(initial_url,))

    existing = local_config_occurrences(worker, includes=False)
    planned_keys = {occurrence.key for occurrence in plan.occurrences}
    keys_to_clear = set(planned_keys)
    for occurrence in existing:
        if _remote_name_for_key(occurrence.key, plan.remote_names) is not None:
            keys_to_clear.add(occurrence.key)
    existing_keys = {occurrence.key for occurrence in existing}
    for key in sorted(keys_to_clear):
        if key in existing_keys:
            git(worker, "config", "--local", "--unset-all", key)

    valueless_count = sum(occurrence.value is None for occurrence in plan.occurrences)
    sentinel = "clonegrown-valueless-" + secrets.token_hex(24)
    existing_sections = {occurrence.key.rpartition(".")[0] for occurrence in existing}
    while (any(occurrence.value == sentinel for occurrence in plan.occurrences)
           or any(f"clonegrown-plan.{sentinel}-" in section for section in existing_sections)):
        sentinel = "clonegrown-valueless-" + secrets.token_hex(24)
    for index, occurrence in enumerate(plan.occurrences):
        section, variable = _split_config_key(occurrence.key)
        # Keeping the source section in this transient key makes a failed Git
        # command identify the setting being applied while each unique section
        # still preserves the plan's cross-key occurrence order.
        temporary_section = f"clonegrown-plan.{sentinel}-{index}-{section}"
        applied = sentinel if occurrence.value is None else occurrence.value
        git(worker, "config", "--local", "--add", f"{temporary_section}.{variable}", applied,
            sensitive=(applied,) if occurrence.value is not None else ())
        git(worker, "config", "--local", "--rename-section", temporary_section, section,
            sensitive=(section,))
    if valueless_count:
        _normalize_valueless_config(worker, sentinel, valueless_count)

    applied = local_config_occurrences(worker, includes=False)
    actual = tuple(occurrence for occurrence in applied if occurrence.key in planned_keys)
    if actual != plan.occurrences:
        raise ClonegrownError("applied clone config does not match its validated plan")
    installed_remotes = set(git(worker, "remote").stdout.splitlines())
    if not set(plan.remote_names).issubset(installed_remotes) or plan.source_remote not in installed_remotes:
        raise ClonegrownError("applied clone remotes do not match their validated plan")
    return (plan.source_remote, list(plan.copied_local_config),
            list(plan.compatibility_warnings))


def copy_auxiliary_refs(canonical: Path, worker: Path) -> dict[str, int]:
    """Snapshot local ref classes that an ordinary clone does not preserve.

    Remote-tracking refs matter when workers are offline and compare against
    origin/main. Notes can affect review tooling. Replace refs change how
    history is interpreted, so they are correctness-critical. Deliberately
    excluded: refs/stash, Clonegrown's private refs, and transient operation
    refs; those stay isolated.
    """
    classes = {"remote_tracking": "refs/remotes/", "notes": "refs/notes/", "replace": "refs/replace/"}
    counts = {label: 0 for label in classes}
    snapshot = git(
        canonical, "for-each-ref", "--format=%(refname)%00%(objectname)", *classes.values(),
    ).stdout.splitlines()
    refspecs: list[str] = []
    for row in snapshot:
        name, separator, object_id = row.partition("\0")
        labels = [label for label, prefix in classes.items() if name.startswith(prefix)]
        if not separator or not object_id or len(labels) != 1:
            raise ClonegrownError("canonical auxiliary-ref snapshot is malformed")
        label = labels[0]
        counts[label] += 1
        refspecs.append(f"+{object_id}:{name}")
    if refspecs:
        # Standard input avoids operating-system argv limits for large ref sets.
        # Explicit object IDs bind the fetch to the exact enumeration above: a
        # later canonical ref move cannot change the copied value or its count.
        git(
            worker, *_FETCH_FLAGS, "--stdin", str(canonical),
            input="\n".join(refspecs) + "\n", sensitive=(canonical,),
        )
        git(worker, "pack-refs", "--all")
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


def copy_sparse_policy(canonical: Path, worker: Path, *, linked_worktree: bool = False) -> bool:
    """Replicate canonical's sparse-checkout config and patterns. False if not sparse.

    Linked worktrees normally inherit repository config. When
    ``extensions.worktreeConfig`` is enabled, however, sparse-checkout flags
    belong to each worktree. Git 2.29 does not populate those flags for a new
    linked worktree, so install them explicitly before checkout.
    """
    if not sparse_checkout_enabled(canonical):
        return False
    worktree_config = git(canonical, "config", "--bool", "extensions.worktreeConfig", check=False)
    config_scope = ("--worktree",) if linked_worktree and (
        worktree_config.returncode == 0 and worktree_config.stdout.strip().lower() == "true"
    ) else ()
    if not linked_worktree or config_scope:
        git(worker, "config", *config_scope, "core.sparseCheckout", "true", sensitive=("true",))
        for key in ("core.sparseCheckoutCone", "index.sparse"):
            value = git(canonical, "config", "--get", key, check=False)
            if value.returncode == 0 and value.stdout.strip():
                copied_value = value.stdout.strip()
                git(worker, "config", *config_scope, key, copied_value, sensitive=(copied_value,))
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
        hook_override = f"core.hooksPath={empty}"
        if create:
            git(repo, "-c", hook_override, "checkout", "-b", branch, base_sha,
                sensitive=(empty,))
        else:
            git(repo, "-c", hook_override, "checkout", branch, sensitive=(empty,))


# --- task branches in shared refs (worktree mode) ------------------------------

def git_at_git_dir(canonical: Path, git_dir_fd: int, *args: str | Path,
                   check: bool = True, input: str | None = None,
                   sensitive: tuple[str | Path, ...] = ()) -> subprocess.CompletedProcess[str]:
    """Run Git against an already-open canonical Git directory, never its pathname occupant."""
    descriptor_path = Path("/dev/fd") / str(git_dir_fd)
    return git(
        canonical.parent, f"--git-dir={descriptor_path}", *args, check=check,
        input=input, sensitive=sensitive, pass_fds=(git_dir_fd,),
    )


def _repository_git(repo: Path, *args: str | Path, git_dir_fd: int | None = None,
                    check: bool = True, input: str | None = None,
                    sensitive: tuple[str | Path, ...] = ()) -> subprocess.CompletedProcess[str]:
    if git_dir_fd is None:
        return git(repo, *args, check=check, input=input, sensitive=sensitive)
    return git_at_git_dir(
        repo, git_dir_fd, *args, check=check, input=input, sensitive=sensitive,
    )


def _ref_transaction(repo: Path, lines: list[str], *,
                     git_dir_fd: int | None = None) -> subprocess.CompletedProcess[str]:
    """Run one atomic ``git update-ref --stdin`` transaction; all updates apply or none do.

    Every update is ``no-deref``: a symbolic ref planted under a name we own
    must never redirect the write onto the branch it points at.
    """
    script = "start\n" + "".join(f"option no-deref\n{line}\n" for line in lines) + "prepare\ncommit\n"
    return _repository_git(
        repo, "update-ref", "--stdin", check=False, input=script,
        git_dir_fd=git_dir_fd,
    )


@contextlib.contextmanager
def prepared_ref_transaction(repo: Path, lines: list[str], *,
                             git_dir_fd: int | None = None) -> Iterator[None]:
    """Prepare and lock a ref transaction, let the caller inspect, then commit.

    Git versions in the supported range resolve a symbolic ref when checking an
    expected object ID even with ``option no-deref``. Keeping the transaction in
    its prepared state lets the caller check raw ref types while Git holds every
    participating ref lock. Exiting normally commits; any exception aborts.
    """
    git_args = ([f"--git-dir=/dev/fd/{git_dir_fd}"] if git_dir_fd is not None else [])
    git_args += ["update-ref", "--stdin"]
    argv = [str(core_module.GIT_BIN), *git_args]
    cwd = repo.parent if git_dir_fd is not None else repo
    pass_fds = (git_dir_fd,) if git_dir_fd is not None else ()
    try:
        process = subprocess.Popen(
            argv, cwd=cwd, text=True, errors="surrogateescape", bufsize=1,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=core_module.clean_git_env(), pass_fds=pass_fds,
        )
    except OSError as exc:
        raise CommandFailure(
            returncode=None, operation="git update-ref", command=argv, cwd=cwd,
            stdout=None, stderr=str(exc), start_error=exc,
        ) from exc

    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None
    transcript: list[str] = []
    prepared = False

    def exchange(command: str, expected: str) -> None:
        try:
            process.stdin.write(command)
            process.stdin.flush()
            response = process.stdout.readline()
        except OSError as exc:
            raise ClonegrownError(f"git update-ref transaction I/O failed: {exc}") from exc
        transcript.append(response)
        if response.strip() != expected:
            raise ClonegrownError(
                f"git update-ref transaction did not report {expected!r}: "
                f"{response.strip() or 'no response'}"
            )

    def stop(abort: bool) -> tuple[int, str, str]:
        nonlocal prepared
        if abort and process.poll() is None:
            try:
                exchange("abort\n", "abort: ok")
            except Exception:
                pass
        prepared = False
        with contextlib.suppress(OSError):
            process.stdin.close()
        returncode = process.wait()
        stdout = "".join(transcript) + process.stdout.read()
        stderr = process.stderr.read()
        return returncode, stdout, stderr

    try:
        exchange("start\n", "start: ok")
        script = "".join(f"option no-deref\n{line}\n" for line in lines)
        exchange(script + "prepare\n", "prepare: ok")
        prepared = True
        try:
            yield
        except BaseException:
            stop(abort=True)
            raise
        exchange("commit\n", "commit: ok")
        prepared = False
        returncode, stdout, stderr = stop(abort=False)
        if returncode:
            raise CommandFailure(
                returncode=returncode, operation="git update-ref", command=argv,
                cwd=cwd, stdout=stdout, stderr=stderr,
            )
    except BaseException:
        if prepared or process.poll() is None:
            stop(abort=prepared)
        raise
    finally:
        with contextlib.suppress(OSError):
            process.stdin.close()
        if process.poll() is None:
            process.wait()
        process.stdout.close()
        process.stderr.close()


def _refuse_symbolic(repo: Path, ref: str, check: bool, *,
                     git_dir_fd: int | None = None) -> bool:
    """A symbolic ref under one of our names is never ours: neither written through nor deleted."""
    if not is_symbolic_ref(repo, ref, git_dir_fd=git_dir_fd):
        return False
    if check:
        raise ClonegrownError(f"refusing to touch a symbolic ref in Clonegrown's namespace: {ref}")
    return True


def write_ref(repo: Path, ref: str, new_sha: str, old_sha: str | None = None,
              check: bool = True, *, git_dir_fd: int | None = None) -> bool:
    """Point ``ref`` itself at ``new_sha``; optional compare-and-swap. A symbolic ref is refused."""
    if _refuse_symbolic(repo, ref, check, git_dir_fd=git_dir_fd):
        return False
    args = ["update-ref", "--no-deref", ref, new_sha] + ([old_sha] if old_sha is not None else [])
    return _repository_git(repo, *args, check=check, git_dir_fd=git_dir_fd).returncode == 0


def delete_ref(repo: Path, ref: str, old_sha: str | None = None,
               check: bool = True, *, git_dir_fd: int | None = None) -> bool:
    """Delete ``ref`` itself; optional compare-and-swap. A symbolic ref is refused."""
    if _refuse_symbolic(repo, ref, check, git_dir_fd=git_dir_fd):
        return False
    args = ["update-ref", "--no-deref", "-d", ref] + ([old_sha] if old_sha is not None else [])
    return _repository_git(repo, *args, check=check, git_dir_fd=git_dir_fd).returncode == 0


def is_symbolic_ref(repo: Path, ref: str, *, git_dir_fd: int | None = None) -> bool:
    return _repository_git(
        repo, "symbolic-ref", "-q", ref, check=False, git_dir_fd=git_dir_fd,
    ).returncode == 0


def create_task_branch(canonical: Path, branch: str, owner_ref: str, base_sha: str, *,
                       git_dir_fd: int | None = None) -> None:
    """Create the task branch and this worker's private ownership ref together, or neither.

    Both use create-only semantics (expected old value zero): a branch that
    already exists under the deterministic name aborts the whole transaction
    untouched. The ownership ref is what later proves this worker created the
    branch, even if the process dies before the record is updated.
    """
    outcome = _ref_transaction(canonical, [
        f"create refs/heads/{branch} {base_sha}",
        f"create {owner_ref} {base_sha}",
    ], git_dir_fd=git_dir_fd)
    if outcome.returncode:
        raise ClonegrownError(
            f"could not create task branch {branch}: it or its ownership ref already exists "
            f"({outcome.stderr.strip()})")


def absent_marker(like_sha: str) -> str:
    """The all-zero object id of the repository's format: how Git itself spells "no such ref"."""
    return "0" * len(like_sha)


def is_absent_marker(sha: str) -> bool:
    return bool(sha) and set(sha) == {"0"}


def resolve_ref(repo: Path, ref: str, *, git_dir_fd: int | None = None) -> str | None:
    """The commit ``ref`` names, or None if it does not exist."""
    got = _repository_git(
        repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}",
        check=False, git_dir_fd=git_dir_fd,
    )
    return got.stdout.strip() if got.returncode == 0 and got.stdout.strip() else None


@contextlib.contextmanager
def result_ref_transaction(repo: Path, result_ref: str, summary_ref: str,
                           candidate: str, *, update_summary: bool,
                           git_dir_fd: int | None = None) -> Iterator[None]:
    """Lock, value-check, and raw-type-check a result/summary pair atomically."""
    lines = [f"verify {result_ref} {candidate}"]
    if update_summary:
        current_summary = resolve_ref(repo, summary_ref, git_dir_fd=git_dir_fd)
        expected_summary = current_summary or absent_marker(candidate)
        lines.append(f"update {summary_ref} {candidate} {expected_summary}")
    else:
        lines.append(f"verify {summary_ref} {candidate}")
    with prepared_ref_transaction(repo, lines, git_dir_fd=git_dir_fd):
        # Git 2.29 can prepare an expected-object check against a symbolic ref.
        # The prepared transaction holds both locks while these raw-type reads
        # decide whether committing would preserve or replace a conflict.
        for ref in (result_ref, summary_ref):
            if is_symbolic_ref(repo, ref, git_dir_fd=git_dir_fd):
                raise ClonegrownError(
                    f"refusing to replace a symbolic ref in Clonegrown's namespace: {ref}"
                )
        yield


def branch_checkouts(canonical: Path, branch: str, *,
                     git_dir_fd: int | None = None) -> list[str]:
    """Working trees of ``canonical`` (itself included) that currently have ``branch`` checked out.

    The NUL-delimited listing is unambiguous for any path; an older Git
    without ``-z`` falls back to the line form, where a newline in a path
    cannot be told apart from a record boundary.
    """
    listing = _repository_git(
        canonical, "worktree", "list", "--porcelain", "-z",
        check=False, git_dir_fd=git_dir_fd,
    )
    if listing.returncode == 0:
        records = [record.split("\0") for record in listing.stdout.split("\0\0") if record]
    else:
        records = [record.split("\n") for record in _repository_git(
            canonical, "worktree", "list", "--porcelain", git_dir_fd=git_dir_fd,
        ).stdout.split("\n\n")
                   if record]
    paths: list[str] = []
    for lines in records:
        path = next((line[len("worktree "):] for line in lines if line.startswith("worktree ")), None)
        if path is not None and f"branch refs/heads/{branch}" in lines:
            paths.append(path)
    return paths


def release_task_branch(canonical: Path, branch: str, owner_ref: str, owner_sha: str,
                        expected_sha: str | None, own_paths: set[Path] = frozenset(), *,
                        git_dir_fd: int | None = None) -> str | None:
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
    current = resolve_ref(canonical, f"refs/heads/{branch}", git_dir_fd=git_dir_fd)
    ours = expected_sha is not None and not is_absent_marker(expected_sha) and current is not None
    lines = []
    if ours:
        elsewhere = [path for path in branch_checkouts(
            canonical, branch, git_dir_fd=git_dir_fd,
        ) if lexical_abs(path) not in own_paths]
        if elsewhere:
            return f"task branch retained: checked out at {', '.join(elsewhere)}"
        lines.append(f"delete refs/heads/{branch} {expected_sha}")
    lines.append(f"delete {owner_ref} {owner_sha}")
    outcome = _ref_transaction(canonical, lines, git_dir_fd=git_dir_fd)
    if outcome.returncode == 0:
        return None
    if ours and resolve_ref(
            canonical, f"refs/heads/{branch}", git_dir_fd=git_dir_fd) != expected_sha:
        return (f"task branch retained: expected {expected_sha}, found "
                f"{resolve_ref(canonical, f'refs/heads/{branch}', git_dir_fd=git_dir_fd) or 'no branch'}")
    return f"task branch retained: ownership ref changed ({outcome.stderr.strip()})"


# --- linked worktrees --------------------------------------------------------

WORKTREE_SHARING_WARNING = (
    "worktree worker shares canonical Git configuration, remotes, refs, stash, and hooks"
)


def add_worktree(canonical: Path, path: Path, base_sha: str, *,
                 git_dir_fd: int | None = None) -> Path:
    """Create a detached, unpopulated linked worktree; return its private admin directory."""
    _repository_git(
        canonical, "worktree", "add", "--no-checkout", "--detach", path, base_sha,
        git_dir_fd=git_dir_fd,
    )
    return git_dir(path)


def repair_worktree(canonical: Path, path: Path, *, git_dir_fd: int | None = None) -> None:
    """Fix Git's back-pointer after a worktree directory has been renamed."""
    _repository_git(canonical, "worktree", "repair", path, git_dir_fd=git_dir_fd)


def ref_points_at(repo: Path, ref: str | None, sha: str | None, *,
                  git_dir_fd: int | None = None) -> bool:
    """Does ``ref`` exist in ``repo`` and resolve to commit ``sha``?"""
    if not ref:
        return False
    got = _repository_git(
        repo, "rev-parse", "--verify", f"{ref}^{{commit}}",
        check=False, git_dir_fd=git_dir_fd,
    )
    return got.returncode == 0 and got.stdout.strip() == sha
