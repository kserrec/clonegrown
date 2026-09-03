#!/usr/bin/env python3
"""Run Clonegrown lifecycle and recovery checks on pinned public repositories.

The public repositories are cloned without a checkout. Before Git materializes
their worktrees, non-cone sparse-checkout rules exclude dotenv filename
patterns at every depth. The qualification never initializes submodules or
searches public worktrees for excluded paths.

Timing is recorded as observational evidence only. It never decides whether a
scenario passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


CHECKOUT = Path(__file__).resolve().parents[2]
GIT = shutil.which("git") or "git"

# These are gitignore-style sparse-checkout exclusions. The positive patterns
# for each profile are supplied separately.
DOTENV_EXCLUSIONS = (
    "!/.env",
    "!/*.env",
    "!/.env.*",
    "!/*.env.*",
    "!/**/.env",
    "!/**/*.env",
    "!/**/.env.*",
    "!/**/*.env.*",
)
FULL_WORKTREE_PATTERNS = ("/*", *DOTENV_EXCLUSIONS)
FEATURE_WORKTREE_PATTERNS = (
    "/Documentation/",
    "/.gitmodules",
    "/sha1collisiondetection",
    *DOTENV_EXCLUSIONS,
)


@dataclass(frozen=True)
class Profile:
    key: str
    role: str
    source_url: str
    commit: str
    commit_url: str
    sparse_patterns: tuple[str, ...]
    included_paths: tuple[str, ...]
    excluded_paths: tuple[str, ...] = ()
    gitlink_path: str | None = None


CURL_HISTORY = Profile(
    key="curl-history",
    role="ordinary history-heavy repository",
    source_url="https://github.com/curl/curl.git",
    commit="8a2bb9ca241bbd82a0da536f6f39dca9037dd046",
    commit_url=(
        "https://github.com/curl/curl/commit/"
        "8a2bb9ca241bbd82a0da536f6f39dca9037dd046"
    ),
    sparse_patterns=FULL_WORKTREE_PATTERNS,
    included_paths=("README.md",),
)

GIT_REFS = Profile(
    key="git-refs",
    role="ref-heavy repository",
    source_url="https://github.com/git/git.git",
    commit="c73e85354c275c9d409b26445089bc16940fc527",
    commit_url=(
        "https://github.com/git/git/commit/"
        "c73e85354c275c9d409b26445089bc16940fc527"
    ),
    sparse_patterns=FULL_WORKTREE_PATTERNS,
    included_paths=("README.md",),
)

GIT_FEATURES = Profile(
    key="git-features",
    role="submodule gitlink plus narrow sparse checkout",
    source_url=GIT_REFS.source_url,
    commit=GIT_REFS.commit,
    commit_url=GIT_REFS.commit_url,
    sparse_patterns=FEATURE_WORKTREE_PATTERNS,
    included_paths=("Documentation/git.adoc", ".gitmodules"),
    excluded_paths=("Makefile",),
    gitlink_path="sha1collisiondetection",
)


class QualificationError(RuntimeError):
    """A command or an explicit qualification assertion failed."""


def clean_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if (name.startswith("GIT_") or name.startswith("CWS_")
                or name.startswith("CLONEGROWN_TEST_")):
            environment.pop(name, None)
    environment.pop("CLONEGROWN_GIT", None)
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["PYTHONPATH"] = str(CHECKOUT)
    if extra:
        environment.update(extra)
    return environment


def run(
    command: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    check: bool = True,
    environment: dict[str, str] | None = None,
    input_text: str | None = None,
    timeout: float = 1800,
) -> subprocess.CompletedProcess[str]:
    rendered = [str(part) for part in command]
    completed = subprocess.run(
        rendered,
        cwd=cwd,
        env=environment or clean_environment(),
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if check and completed.returncode:
        raise QualificationError(
            f"command failed with exit {completed.returncode}: {rendered!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def git(repo: Path, *arguments: str | Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run([GIT, *arguments], cwd=repo, check=check)


def git_output(repo: Path, *arguments: str | Path) -> str:
    return git(repo, *arguments).stdout.strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise QualificationError(message)


def cli(
    *arguments: str | Path,
    check: bool = True,
    extra_environment: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Any | None]:
    completed = run(
        [sys.executable, "-m", "clonegrown", *arguments],
        cwd=CHECKOUT,
        check=check,
        environment=clean_environment(extra_environment),
    )
    if completed.returncode:
        return completed, None
    try:
        return completed, json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise QualificationError(
            f"Clonegrown returned non-JSON stdout: {completed.stdout!r}"
        ) from exc


def elapsed_call(function: Any, *arguments: Any, **keywords: Any) -> tuple[float, Any]:
    started = time.perf_counter()
    value = function(*arguments, **keywords)
    return time.perf_counter() - started, value


def set_sparse_checkout(repo: Path, patterns: tuple[str, ...]) -> None:
    git(repo, "sparse-checkout", "init", "--no-cone")
    completed = run(
        [GIT, "sparse-checkout", "set", "--no-cone", "--stdin"],
        cwd=repo,
        environment=clean_environment(),
        input_text="\n".join(patterns) + "\n",
    )
    require(completed.returncode == 0, "sparse-checkout setup did not complete")


def verify_materialization(repo: Path, profile: Profile) -> dict[str, Any]:
    sparse = git_output(repo, "config", "--bool", "core.sparseCheckout")
    require(sparse == "true", f"{profile.key} did not retain sparse checkout")
    missing = [path for path in profile.included_paths if not (repo / path).exists()]
    present = [path for path in profile.excluded_paths if (repo / path).exists()]
    require(not missing, f"{profile.key} omitted expected included paths: {missing!r}")
    require(not present, f"{profile.key} materialized expected exclusions: {present!r}")

    result: dict[str, Any] = {
        "core_sparse_checkout": True,
        "included_paths_present": list(profile.included_paths),
        "excluded_paths_absent": list(profile.excluded_paths),
    }
    if profile.gitlink_path:
        line = git_output(repo, "ls-files", "--stage", "--", profile.gitlink_path)
        fields = line.split()
        require(
            len(fields) >= 4 and fields[0] == "160000" and fields[3] == profile.gitlink_path,
            f"{profile.key} did not retain its expected gitlink: {line!r}",
        )
        result["gitlink"] = {
            "path": profile.gitlink_path,
            "mode": fields[0],
            "commit": fields[1],
            "submodule_initialized": (repo / profile.gitlink_path / ".git").exists(),
        }
        require(
            result["gitlink"]["submodule_initialized"] is False,
            "qualification must not initialize the public submodule",
        )
    return result


def parse_count_objects(output: str) -> dict[str, int | str]:
    values: dict[str, int | str] = {}
    for line in output.splitlines():
        key, separator, value = line.partition(": ")
        if not separator:
            continue
        try:
            values[key] = int(value)
        except ValueError:
            values[key] = value
    return values


def repository_statistics(repo: Path, profile: Profile) -> dict[str, Any]:
    head = git_output(repo, "rev-parse", "HEAD")
    require(head == profile.commit, f"{profile.key} checked out {head}, not {profile.commit}")
    return {
        "head": head,
        "commit_date": git_output(repo, "show", "-s", "--format=%cI", head),
        "head_history_commits": int(git_output(repo, "rev-list", "--count", "HEAD")),
        "all_reachable_commits": int(git_output(repo, "rev-list", "--all", "--count")),
        "refs": len(git_output(repo, "for-each-ref", "--format=%(refname)").splitlines()),
        "tags": len(git_output(repo, "for-each-ref", "--format=%(refname)", "refs/tags").splitlines()),
        "object_database": parse_count_objects(git_output(repo, "count-objects", "-v")),
        "materialization": verify_materialization(repo, profile),
    }


def prepare_remote_profile(root: Path, profile: Profile) -> tuple[Path, dict[str, Any]]:
    repo = root / "sources" / profile.key
    repo.parent.mkdir(parents=True, exist_ok=True)
    print(f"PREPARE {profile.key}: cloning pinned public source", flush=True)
    seconds, _ = elapsed_call(
        run,
        [GIT, "clone", "--no-checkout", profile.source_url, repo],
        cwd=root,
    )
    set_sparse_checkout(repo, profile.sparse_patterns)
    git(repo, "checkout", "-q", "-B", "qualification-base", profile.commit)
    return repo, {
        "clone_kind": "full remote clone with checkout deferred",
        "clone_seconds_observed": seconds,
        "statistics": repository_statistics(repo, profile),
    }


def prepare_local_feature_profile(
    root: Path, source: Path, profile: Profile
) -> tuple[Path, dict[str, Any]]:
    repo = root / "sources" / profile.key
    print(f"PREPARE {profile.key}: cloning from pinned disposable Git source", flush=True)
    seconds, _ = elapsed_call(
        run,
        [GIT, "clone", "--no-checkout", "--local", source, repo],
        cwd=root,
    )
    git(repo, "remote", "set-url", "origin", profile.source_url)
    set_sparse_checkout(repo, profile.sparse_patterns)
    git(repo, "checkout", "-q", "-B", "qualification-base", profile.commit)
    return repo, {
        "clone_kind": "local full clone of the pinned disposable public-source clone",
        "clone_seconds_observed": seconds,
        "statistics": repository_statistics(repo, profile),
    }


def write_qualification_commit(worker: Path, profile: Profile, mode: str) -> tuple[str, str]:
    relative = (
        f"Documentation/clonegrown-qualification-{mode}.txt"
        if profile is GIT_FEATURES
        else f"clonegrown-qualification-{mode}.txt"
    )
    destination = worker / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        f"Clonegrown real-repository qualification: {profile.key} {mode}\n",
        encoding="utf-8",
    )
    git(worker, "add", "--", relative)
    git(
        worker,
        "-c",
        "user.name=Clonegrown Qualification",
        "-c",
        "user.email=qualification@example.invalid",
        "commit",
        "--no-verify",
        "--no-gpg-sign",
        "-m",
        f"Clonegrown qualification: {profile.key} {mode}",
    )
    return relative, git_output(worker, "rev-parse", "HEAD")


def run_scenario(root: Path, canonical: Path, profile: Profile, mode: str) -> dict[str, Any]:
    require(mode in {"clone", "worktree"}, f"unsupported mode: {mode}")
    workspace = root / "workspaces" / f"{profile.key}-{mode}"
    print(f"SCENARIO {profile.key} {mode}: init, interrupted spawn, recover, collect, discard", flush=True)
    scenario_started = time.perf_counter()
    timings: dict[str, float] = {}

    timings["init"], (_, initialized) = elapsed_call(
        cli, "init", canonical, "--workspace", workspace
    )
    require(isinstance(initialized, dict), "init did not return an object")
    require(initialized.get("status") == "ready", "workspace init did not become ready")

    spawn_arguments: list[str | Path] = [
        "spawn",
        "--workspace",
        workspace,
        "--task",
        f"qualify {profile.key} {mode}",
        "--base",
        profile.commit,
        "--request-id",
        f"qualification-{profile.key}-{mode}",
    ]
    if mode == "worktree":
        spawn_arguments.append("--worktree")
    timings["interrupted_spawn"], (interrupted, _) = elapsed_call(
        cli,
        *spawn_arguments,
        check=False,
        extra_environment={
            "CLONEGROWN_TEST_MODE": "1",
            "CLONEGROWN_TEST_FAILPOINT": "spawn.after_publish",
        },
    )
    require(
        interrupted.returncode == 88,
        f"spawn failpoint returned {interrupted.returncode}, expected 88",
    )

    timings["recover"], (_, recovered) = elapsed_call(
        cli, "recover", "--workspace", workspace
    )
    require(isinstance(recovered, list), "recover did not return a list")
    recovery_actions = [
        str(item.get("action"))
        for item in recovered
        if isinstance(item, dict) and item.get("id") == 1
    ]
    require(
        "spawn-publish-finished" in recovery_actions,
        f"recovery did not finish the published worker: {recovered!r}",
    )

    timings["idempotent_spawn_retry"], (_, worker) = elapsed_call(cli, *spawn_arguments)
    require(isinstance(worker, dict), "spawn retry did not return an object")
    require(worker.get("id") == 1, f"spawn retry allocated another worker: {worker!r}")
    require(worker.get("status") == "ready", f"recovered worker was not ready: {worker!r}")
    require(worker.get("base_sha") == profile.commit, "worker did not retain the pinned base")
    worker_path = Path(str(worker["path"]))
    require(git_output(worker_path, "rev-parse", "HEAD") == profile.commit, "worker HEAD moved")
    materialization = verify_materialization(worker_path, profile)

    relative_path, result_sha = write_qualification_commit(worker_path, profile, mode)
    timings["collect"], (_, collected) = elapsed_call(
        cli, "collect", str(worker["id"]), "--workspace", workspace
    )
    require(isinstance(collected, dict), "collect did not return an object")
    require(collected.get("result_sha") == result_sha, "collect retained a different commit")
    result_ref = str(collected["result_ref"])
    require(git_output(canonical, "rev-parse", result_ref) == result_sha, "result ref mismatch")

    timings["release"], (_, released) = elapsed_call(
        cli, "release", str(worker["id"]), "--workspace", workspace
    )
    require(isinstance(released, dict) and released.get("lease_released"), "release failed")
    timings["discard"], (_, discarded) = elapsed_call(
        cli, "discard", str(worker["id"]), "--workspace", workspace
    )
    require(isinstance(discarded, dict), "discard did not return an object")
    require(discarded.get("status") == "discarded", "worker was not discarded")
    require(not worker_path.exists(), "discard left the worker path behind")
    require(git_output(canonical, "rev-parse", result_ref) == result_sha, "discard lost result ref")

    _, status_result = cli("status", "--workspace", workspace)
    require(isinstance(status_result, dict), "status did not return an object")
    require(status_result.get("issues") == [], f"workspace audit found issues: {status_result!r}")
    workers = status_result.get("workers")
    require(
        isinstance(workers, list)
        and len(workers) == 1
        and workers[0].get("status") == "discarded",
        f"status did not retain one discarded record: {status_result!r}",
    )
    if mode == "worktree":
        branch_check = git(
            canonical,
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{worker['branch']}",
            check=False,
        )
        require(branch_check.returncode != 0, "discard left the worktree task branch behind")

    fsck = git(canonical, "fsck", "--connectivity-only")
    require(fsck.returncode == 0, "connectivity check failed")
    timings["total"] = time.perf_counter() - scenario_started
    return {
        "mode": mode,
        "passed": True,
        "base_sha": profile.commit,
        "spawn_failpoint": "spawn.after_publish",
        "spawn_failpoint_exit": interrupted.returncode,
        "recovery_actions": recovery_actions,
        "worker_id": worker["id"],
        "worker_status_after_recovery": worker["status"],
        "worker_head_after_recovery": profile.commit,
        "copied_sparse_checkout": worker.get("copied_sparse_checkout"),
        "compatibility_warnings": worker.get("compatibility_warnings", []),
        "materialization": materialization,
        "qualification_file": relative_path,
        "result_sha": result_sha,
        "result_ref": result_ref,
        "result_ref_survived_discard": True,
        "worker_path_removed": True,
        "final_worker_status": "discarded",
        "workspace_audit_issues": [],
        "connectivity_check": "passed",
        "seconds_observed": timings,
    }


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_sha256() -> str:
    digest = hashlib.sha256()
    for path in sorted((CHECKOUT / "clonegrown").glob("*.py")):
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def qualification(root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    curl_repo, curl_source = prepare_remote_profile(root, CURL_HISTORY)
    git_repo, git_source = prepare_remote_profile(root, GIT_REFS)
    feature_repo, feature_source = prepare_local_feature_profile(root, git_repo, GIT_FEATURES)

    rows = []
    for profile, canonical, source in (
        (CURL_HISTORY, curl_repo, curl_source),
        (GIT_REFS, git_repo, git_source),
        (GIT_FEATURES, feature_repo, feature_source),
    ):
        scenarios = [run_scenario(root, canonical, profile, mode) for mode in ("clone", "worktree")]
        rows.append(
            {
                "profile": profile.key,
                "role": profile.role,
                "source_url": profile.source_url,
                "public_commit": profile.commit,
                "public_commit_url": profile.commit_url,
                "checkout_safety": {
                    "clone_started_with_no_checkout": True,
                    "dotenv_filename_patterns_excluded_before_checkout": list(DOTENV_EXCLUSIONS),
                    "submodules_initialized": False,
                },
                "source_preparation": source,
                "scenarios": scenarios,
            }
        )

    return {
        "schema_version": 1,
        "qualification": "real-public-repositories",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": all(
            scenario["passed"] for row in rows for scenario in row["scenarios"]
        ),
        "scope": {
            "interpretation": "qualification evidence, not a universal performance policy",
            "agent_quality_claim": "none; this run does not measure whether coding agents make fewer mistakes",
            "timing_policy": "observational only; no duration or ratio decides pass/fail",
        },
        "environment": {
            "platform": platform.platform(),
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "python_build": sys.version.replace("\n", " "),
            "git_executable": str(Path(GIT).resolve()),
            "git_version": run([GIT, "--version"], cwd=CHECKOUT).stdout.strip(),
            "clonegrown_head": git_output(CHECKOUT, "rev-parse", "HEAD"),
            "clonegrown_package_sha256": package_sha256(),
            "harness_sha256": file_sha256(Path(__file__).resolve()),
        },
        "profiles": rows,
        "summary": {
            "profiles": len(rows),
            "scenarios": sum(len(row["scenarios"]) for row in rows),
            "passed_scenarios": sum(
                int(scenario["passed"]) for row in rows for scenario in row["scenarios"]
            ),
            "worker_modes": ["clone", "worktree"],
            "seconds_observed": time.perf_counter() - started,
        },
    }


def output_path(value: str, parser: argparse.ArgumentParser) -> Path:
    path = Path(value).expanduser().resolve()
    try:
        path.relative_to(CHECKOUT)
    except ValueError:
        return path
    parser.error("--output must be outside the repository checkout")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--keep-fixtures",
        action="store_true",
        help="retain the disposable root after a successful run for manual diagnosis",
    )
    arguments = parser.parse_args()
    destination = output_path(arguments.output, parser)
    root = Path(tempfile.mkdtemp(prefix="clonegrown-real-qualification-"))
    try:
        payload = qualification(root)
        payload["fixture_cleanup"] = {
            "retained_by_request": arguments.keep_fixtures,
            "path": str(root) if arguments.keep_fixtures else None,
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        destination.write_text(rendered, encoding="utf-8")
        print(f"PASS: wrote {destination}", flush=True)
        if not arguments.keep_fixtures:
            shutil.rmtree(root)
            require(not root.exists(), "fixture cleanup did not remove its disposable root")
        return 0
    except Exception:
        print(f"FAIL: retained disposable fixtures at {root}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
