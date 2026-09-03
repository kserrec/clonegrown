#!/usr/bin/env python3
"""Measure Clonegrown's auxiliary-ref snapshot and a packing candidate.

The synthetic canonical repository carries remote-tracking, notes, and replace
refs together. Every sample uses a fresh canonical/workspace pair, validates
the current package's offline semantics, records ref/storage counts, and then
simulates ``git pack-refs --all`` in clone workers without changing product
code. Timing is observational and never decides this program's exit status.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from unittest import mock


CHECKOUT = Path(__file__).resolve().parents[2]
if str(CHECKOUT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT))

from clonegrown import init_workspace, spawn  # noqa: E402
from clonegrown import lifecycle as lifecycle_module  # noqa: E402
from clonegrown.core import git as clonegrown_git  # noqa: E402


AUXILIARY_PREFIXES = {
    "remote_tracking": "refs/remotes/",
    "notes": "refs/notes/",
    "replace": "refs/replace/",
}
SINGLE_FETCH_PACK = "single-fetch-pack"


def clean_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in tuple(environment):
        if (name.startswith("GIT_") or name.startswith("CWS_")
                or name.startswith("CLONEGROWN_TEST_")):
            environment.pop(name, None)
    environment.pop("CLONEGROWN_GIT", None)
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["PYTHONPATH"] = str(CHECKOUT)
    return environment


def run(
    command: Sequence[str | Path],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
    timeout: float = 900,
) -> subprocess.CompletedProcess[str]:
    rendered = [str(part) for part in command]
    completed = subprocess.run(
        rendered,
        cwd=cwd,
        env=clean_environment(),
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed with exit {completed.returncode}: {rendered!r}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def git(repo: Path, *arguments: str | Path) -> subprocess.CompletedProcess[str]:
    return run(["git", *arguments], cwd=repo)


def git_output(repo: Path, *arguments: str | Path) -> str:
    return git(repo, *arguments).stdout.strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def is_dotenv_name(name: str) -> bool:
    """Exclude every prohibited dotenv filename pattern from recursive walks."""
    return (name == ".env" or name.endswith(".env") or name.startswith(".env.")
            or ".env." in name)


def tree_usage(path: Path) -> dict[str, int]:
    """Return logical and allocated bytes without reading file contents."""
    logical = 0
    allocated = 0
    pending = [path]
    while pending:
        current = pending.pop()
        if is_dotenv_name(current.name):
            continue
        metadata = current.lstat()
        logical += metadata.st_size
        allocated += metadata.st_blocks * 512
        if current.is_dir() and not current.is_symlink():
            pending.extend(
                child for child in current.iterdir()
                if not is_dotenv_name(child.name)
            )
    return {"logical_bytes": logical, "allocated_bytes": allocated}


def resolved_git_path(repo: Path, *arguments: str) -> Path:
    value = Path(git_output(repo, "rev-parse", *arguments))
    if not value.is_absolute():
        value = repo / value
    return value.resolve()


def selected_refs(repo: Path) -> dict[str, str]:
    lines = git_output(repo, "for-each-ref", "--format=%(refname) %(objectname)").splitlines()
    return {
        name: object_id
        for line in lines
        for name, object_id in [line.split(" ", 1)]
        if any(name.startswith(prefix) for prefix in AUXILIARY_PREFIXES.values())
    }


def classify_refs(refs: dict[str, str]) -> dict[str, int]:
    return {
        label: sum(name.startswith(prefix) for name in refs)
        for label, prefix in AUXILIARY_PREFIXES.items()
    }


def copy_auxiliary_refs_single_fetch_pack(canonical: Path, worker: Path) -> dict[str, int]:
    """Candidate policy: preserve every current namespace, fetch once, then pack."""
    counts: dict[str, int] = {}
    refspecs: list[str] = []
    for label, prefix in AUXILIARY_PREFIXES.items():
        refs = [
            ref for ref in clonegrown_git(
                canonical, "for-each-ref", "--format=%(refname)", prefix,
            ).stdout.splitlines()
            if ref.startswith(prefix)
        ]
        counts[label] = len(refs)
        if refs:
            refspecs.append(f"+{prefix}*:{prefix}*")
    if refspecs:
        clonegrown_git(
            worker,
            "fetch", "--no-tags", "--no-write-fetch-head", "--no-auto-maintenance",
            str(canonical), *refspecs,
            sensitive=(canonical,),
        )
        clonegrown_git(worker, "pack-refs", "--all")
    return counts


def loose_ref_names(git_dir: Path) -> set[str]:
    root = git_dir / "refs"
    if not root.exists():
        return set()
    names: set[str] = set()
    pending = [root]
    while pending:
        current = pending.pop()
        for child in current.iterdir():
            if is_dotenv_name(child.name):
                continue
            if child.is_dir() and not child.is_symlink():
                pending.append(child)
            elif child.is_file() and not child.is_symlink():
                names.add(child.relative_to(git_dir).as_posix())
    return names


def packed_ref_names(git_dir: Path) -> set[str]:
    packed = git_dir / "packed-refs"
    if not packed.exists():
        return set()
    names: set[str] = set()
    for line in packed.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith(("#", "^")):
            continue
        _, separator, name = line.partition(" ")
        if separator:
            names.add(name)
    return names


def ref_statistics(repo: Path) -> dict[str, Any]:
    git_dir = resolved_git_path(repo, "--git-common-dir")
    refs = selected_refs(repo)
    all_refs = git_output(repo, "for-each-ref", "--format=%(refname)").splitlines()
    loose = loose_ref_names(git_dir)
    packed = packed_ref_names(git_dir)
    loose_auxiliary = {name for name in loose if any(
        name.startswith(prefix) for prefix in AUXILIARY_PREFIXES.values()
    )}
    packed_auxiliary = {name for name in packed if any(
        name.startswith(prefix) for prefix in AUXILIARY_PREFIXES.values()
    )}
    packed_path = git_dir / "packed-refs"
    return {
        "total_refs": len(all_refs),
        "auxiliary_refs": len(refs),
        "auxiliary_refs_by_class": classify_refs(refs),
        "loose_refs": len(loose),
        "loose_auxiliary_refs": len(loose_auxiliary),
        "packed_refs": len(packed),
        "packed_auxiliary_refs": len(packed_auxiliary),
        "git_directory": tree_usage(git_dir),
        "refs_directory": tree_usage(git_dir / "refs"),
        "packed_refs_file": (
            tree_usage(packed_path)
            if packed_path.exists()
            else {"logical_bytes": 0, "allocated_bytes": 0}
        ),
    }


def make_template(
    root: Path,
    remote_count: int,
    notes_count: int,
    replace_count: int,
) -> tuple[Path, dict[str, Any]]:
    canonical = root / "template"
    git(root, "init", "-b", "main", canonical)
    git(canonical, "config", "user.name", "Auxiliary Ref Benchmark")
    git(canonical, "config", "user.email", "benchmark@example.invalid")
    (canonical / "README.md").write_text("auxiliary ref benchmark\n", encoding="utf-8")
    replacements = canonical / "replacement-sources"
    replacements.mkdir()
    for index in range(max(0, replace_count - 1)):
        (replacements / f"source-{index:06d}.txt").write_text(
            f"original replacement source {index}\n",
            encoding="utf-8",
        )
    git(canonical, "add", ".")
    git(canonical, "commit", "-m", "auxiliary ref benchmark base")
    base = git_output(canonical, "rev-parse", "HEAD")
    tree = git_output(canonical, "show", "-s", "--format=%T", base)
    replacement_commit = run(
        ["git", "commit-tree", tree, "-m", "replacement history"],
        cwd=canonical,
    ).stdout.strip()
    replacement_blob = run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=canonical,
        input_text="replacement blob content\n",
    ).stdout.strip()
    source_blobs = git_output(
        canonical,
        "ls-tree", "-r", "--format=%(objectname)", base, "--", "replacement-sources",
    ).splitlines()
    require(len(source_blobs) == max(0, replace_count - 1), "replacement source count changed")

    remote_target = "refs/remotes/upstream/bench-000000"
    updates = [
        f"update refs/remotes/upstream/bench-{index:06d} {base}\n"
        for index in range(remote_count - 1)
    ]
    git(canonical, "notes", "--ref=refs/notes/bench-000000", "add", "-m", "benchmark note", base)
    note_tip = git_output(canonical, "rev-parse", "refs/notes/bench-000000")
    updates.extend(
        f"update refs/notes/bench-{index:06d} {note_tip}\n"
        for index in range(1, notes_count)
    )
    replacement_sources = [base, *source_blobs]
    replacement_targets = [replacement_commit, *([replacement_blob] * len(source_blobs))]
    updates.extend(
        f"update refs/replace/{source} {target}\n"
        for source, target in zip(replacement_sources, replacement_targets, strict=True)
    )
    run(["git", "update-ref", "--stdin"], cwd=canonical, input_text="".join(updates))
    git(canonical, "pack-refs", "--all")
    git(canonical, "symbolic-ref", "refs/remotes/upstream/HEAD", remote_target)

    refs = selected_refs(canonical)
    expected_counts = {
        "remote_tracking": remote_count,
        "notes": notes_count,
        "replace": replace_count,
    }
    require(classify_refs(refs) == expected_counts, "template auxiliary-ref counts changed")
    return canonical, {
        "base": base,
        "remote_ref": remote_target,
        "note_ref": "refs/notes/bench-000000",
        "replace_commit_ref": f"refs/replace/{base}",
        "replacement_commit": replacement_commit,
        "replace_blob_source": source_blobs[0] if source_blobs else None,
        "replace_blob_ref": f"refs/replace/{source_blobs[0]}" if source_blobs else None,
        "replacement_blob": replacement_blob,
        "expected_counts": expected_counts,
        "refs": refs,
    }


def validate_semantics(repo: Path, facts: dict[str, Any]) -> None:
    base = str(facts["base"])
    require(git_output(repo, "rev-parse", facts["remote_ref"]) == base,
            "remote-tracking ref no longer resolves to the canonical tip")
    require(git_output(repo, "notes", f"--ref={facts['note_ref']}", "show", base) == "benchmark note",
            "notes ref no longer supplies the canonical note")
    require(git_output(repo, "log", "-1", "--format=%s", base) == "replacement history",
            "replace ref no longer changes history interpretation")
    require(git_output(repo, "--no-replace-objects", "log", "-1", "--format=%s", base)
            == "auxiliary ref benchmark base",
            "unreplaced history no longer identifies the original commit")
    if facts["replace_blob_source"]:
        require(git_output(repo, "cat-file", "-p", facts["replace_blob_source"])
                == "replacement blob content",
                "blob replace ref no longer changes object interpretation")


def validate_offline_clone(repo: Path, canonical: Path, facts: dict[str, Any]) -> None:
    disconnected = canonical.with_name(canonical.name + "-offline")
    canonical.rename(disconnected)
    try:
        validate_semantics(repo, facts)
    finally:
        disconnected.rename(canonical)


def validate_packed_updates(repo: Path, facts: dict[str, Any]) -> None:
    refs = [facts["remote_ref"], facts["note_ref"], facts["replace_commit_ref"]]
    originals = {ref: git_output(repo, "rev-parse", ref) for ref in refs}
    for ref in refs:
        git(repo, "update-ref", "-d", ref, originals[ref])
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=repo,
            env=clean_environment(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        require(completed.returncode != 0, f"packed ref deletion did not remove {ref}")
        git(repo, "update-ref", ref, originals[ref], "0" * len(originals[ref]))
    validate_semantics(repo, facts)


def measure_sample(
    template: Path,
    facts: dict[str, Any],
    root: Path,
    mode: str,
    strategy: str,
    sample: int,
) -> dict[str, Any]:
    canonical = root / "canonical"
    shutil.copytree(template, canonical)
    workspace = root / "workspace"
    candidate_patch = (
        mock.patch.object(
            lifecycle_module,
            "copy_auxiliary_refs",
            copy_auxiliary_refs_single_fetch_pack,
        )
        if strategy == SINGLE_FETCH_PACK
        else contextlib.nullcontext()
    )
    with mock.patch.dict(os.environ, clean_environment(), clear=True):
        init_workspace(canonical, workspace)
        with candidate_patch:
            started = time.perf_counter()
            worker = spawn(
                workspace,
                "main",
                f"auxiliary-ref-{mode}-{strategy}-{sample}",
                request_id=f"auxiliary-ref-{mode}-{strategy}-{sample}",
                mode=mode,
            )
            spawn_seconds = time.perf_counter() - started
    require(worker.get("status") == "ready", "spawn did not return a ready worker")
    repo = Path(str(worker["path"]))

    actual_refs = selected_refs(repo)
    expected_refs = facts["refs"]
    missing_refs = sorted(set(expected_refs) - set(actual_refs))
    extra_refs = sorted(set(actual_refs) - set(expected_refs))
    changed_refs = sorted(
        name for name in set(expected_refs) & set(actual_refs)
        if expected_refs[name] != actual_refs[name]
    )
    require(
        not missing_refs and not changed_refs,
        "worker auxiliary refs differ from the canonical snapshot: "
        f"missing={missing_refs!r}, extra={extra_refs!r}, changed={changed_refs!r}",
    )
    if mode == "clone":
        require(worker.get("copied_auxiliary_refs") == facts["expected_counts"],
                "clone metadata does not report the exact copied ref counts")
        validate_offline_clone(repo, canonical, facts)
    else:
        require(worker.get("copied_auxiliary_refs") == {},
                "worktree metadata should report shared refs, not copied refs")
        validate_semantics(repo, facts)

    before = ref_statistics(repo)
    candidate: dict[str, Any] | None = None
    if mode == "clone" and strategy == "current":
        pack_started = time.perf_counter()
        git(repo, "pack-refs", "--all")
        pack_seconds = time.perf_counter() - pack_started
        packed_refs = selected_refs(repo)
        require(
            all(packed_refs.get(name) == object_id for name, object_id in expected_refs.items()),
            "packing changed a canonical auxiliary-ref snapshot value",
        )
        validate_offline_clone(repo, canonical, facts)
        after = ref_statistics(repo)
        validate_packed_updates(repo, facts)
        restored_refs = selected_refs(repo)
        require(
            all(restored_refs.get(name) == object_id for name, object_id in expected_refs.items()),
            "packed ref update probe did not restore the canonical snapshot",
        )
        candidate = {
            "command": ["git", "pack-refs", "--all"],
            "seconds": pack_seconds,
            "projected_spawn_seconds": spawn_seconds + pack_seconds,
            "statistics": after,
            "offline_semantics": "passed",
            "remote_notes_replace_update_restore": "passed",
        }
    elif mode == "clone":
        validate_packed_updates(repo, facts)
        restored_refs = selected_refs(repo)
        require(
            all(restored_refs.get(name) == object_id for name, object_id in expected_refs.items()),
            "single-fetch packing update probe did not restore the canonical snapshot",
        )

    return {
        "sample": sample,
        "mode": mode,
        "strategy": strategy,
        "spawn_seconds": spawn_seconds,
        "worker_id": worker["id"],
        "copied_auxiliary_refs": worker.get("copied_auxiliary_refs"),
        "worker_only_auxiliary_refs": extra_refs,
        "current_statistics": before,
        "offline_semantics": "passed" if mode == "clone" else "shared canonical semantics passed",
        "packing_candidate": candidate,
    }


def distribution(values: list[float | int]) -> dict[str, Any]:
    center = statistics.median(values)
    return {
        "raw": values,
        "median": center,
        "median_absolute_deviation": statistics.median(abs(value - center) for value in values),
        "minimum": min(values),
        "maximum": max(values),
    }


def summarize(rows: list[dict[str, Any]], mode: str, strategy: str) -> dict[str, Any]:
    current = [row["current_statistics"] for row in rows]
    summary: dict[str, Any] = {
        "mode": mode,
        "strategy": strategy,
        "spawn_seconds": distribution([row["spawn_seconds"] for row in rows]),
        "total_refs": distribution([stats["total_refs"] for stats in current]),
        "auxiliary_refs": distribution([stats["auxiliary_refs"] for stats in current]),
        "loose_refs": distribution([stats["loose_refs"] for stats in current]),
        "loose_auxiliary_refs": distribution([stats["loose_auxiliary_refs"] for stats in current]),
        "git_directory_allocated_bytes": distribution([
            stats["git_directory"]["allocated_bytes"] for stats in current
        ]),
    }
    if mode == "clone" and strategy == "current":
        candidates = [row["packing_candidate"] for row in rows]
        require(all(candidate is not None for candidate in candidates), "clone packing candidate is missing")
        packed = [candidate for candidate in candidates if candidate is not None]
        summary["packing_candidate"] = {
            "seconds": distribution([candidate["seconds"] for candidate in packed]),
            "projected_spawn_seconds": distribution([
                candidate["projected_spawn_seconds"] for candidate in packed
            ]),
            "loose_refs": distribution([
                candidate["statistics"]["loose_refs"] for candidate in packed
            ]),
            "loose_auxiliary_refs": distribution([
                candidate["statistics"]["loose_auxiliary_refs"] for candidate in packed
            ]),
            "packed_auxiliary_refs": distribution([
                candidate["statistics"]["packed_auxiliary_refs"] for candidate in packed
            ]),
            "git_directory_allocated_bytes": distribution([
                candidate["statistics"]["git_directory"]["allocated_bytes"] for candidate in packed
            ]),
        }
    return summary


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_sha256() -> str:
    digest = hashlib.sha256()
    for path in sorted((CHECKOUT / "clonegrown").glob("*.py")):
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def benchmark(samples: int, remote_count: int, notes_count: int, replace_count: int) -> dict[str, Any]:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="clonegrown-auxiliary-ref-benchmark-") as temporary:
        root = Path(temporary)
        template, facts = make_template(root, remote_count, notes_count, replace_count)
        template_statistics = ref_statistics(template)
        cases = (
            ("clone_current", "clone", "current"),
            ("clone_single_fetch_pack", "clone", SINGLE_FETCH_PACK),
            ("worktree_current", "worktree", "current"),
        )
        rows: dict[str, list[dict[str, Any]]] = {key: [] for key, _, _ in cases}
        execution_order: list[dict[str, Any]] = []
        for sample in range(1, samples + 1):
            offset = (sample - 1) % len(cases)
            ordered_cases = cases[offset:] + cases[:offset]
            execution_order.append({"sample": sample, "cases": [key for key, _, _ in ordered_cases]})
            for key, mode, strategy in ordered_cases:
                rows[key].append(measure_sample(
                    template,
                    facts,
                    root / f"sample-{sample}-{key}",
                    mode,
                    strategy,
                    sample,
                ))

    return {
        "schema_version": 1,
        "benchmark": "auxiliary-ref-policy",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": True,
        "timing_policy": "observational only; no duration or ratio decides pass/fail",
        "candidate_policy": (
            "benchmark-only simulation; fetch all nonempty auxiliary namespaces in one Git command, "
            "then run git pack-refs --all"
        ),
        "fixture": {
            "remote_tracking_refs": remote_count,
            "notes_refs": notes_count,
            "replace_refs": replace_count,
            "total_auxiliary_refs": remote_count + notes_count + replace_count,
            "canonical_statistics": template_statistics,
        },
        "environment": {
            "platform": platform.platform(),
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
            "git_version": run(["git", "--version"], cwd=CHECKOUT).stdout.strip(),
            "clonegrown_head": git_output(CHECKOUT, "rev-parse", "HEAD"),
            "clonegrown_package_sha256": package_sha256(),
            "harness_sha256": file_sha256(Path(__file__).resolve()),
        },
        "samples": samples,
        "execution_order": execution_order,
        "raw_samples": rows,
        "summary": {
            key: summarize(mode_rows, mode_rows[0]["mode"], mode_rows[0]["strategy"])
            for key, mode_rows in rows.items()
        },
        "seconds_observed": time.perf_counter() - started,
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
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--remote-refs", type=int, default=4096)
    parser.add_argument("--notes-refs", type=int, default=256)
    parser.add_argument("--replace-refs", type=int, default=256)
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    if arguments.samples < 3:
        parser.error("--samples must be at least 3")
    if arguments.remote_refs < 2:
        parser.error("--remote-refs must be at least 2")
    if arguments.notes_refs < 1:
        parser.error("--notes-refs must be at least 1")
    if arguments.replace_refs < 1:
        parser.error("--replace-refs must be at least 1")
    destination = output_path(arguments.output, parser)
    payload = benchmark(
        arguments.samples,
        arguments.remote_refs,
        arguments.notes_refs,
        arguments.replace_refs,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    destination.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
