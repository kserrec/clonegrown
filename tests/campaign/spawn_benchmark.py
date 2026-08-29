#!/usr/bin/env python3
"""Informational multi-sample benchmark for single and concurrent spawns.

Timing never decides this program's exit status. Command, JSON, or integrity
failures still abort because their timings would not be valid measurements.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


CHECKOUT = Path(__file__).resolve().parents[2]


def run(command: Sequence[str | Path], *, cwd: Path | None = None,
        timeout: float = 240) -> subprocess.CompletedProcess[str]:
    rendered = [str(part) for part in command]
    completed = subprocess.run(
        rendered,
        cwd=cwd,
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


def git(repo: Path, *args: str | Path) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=repo)


def clonegrown(*args: str | Path) -> dict[str, Any]:
    completed = run([sys.executable, "-m", "clonegrown", *args], cwd=CHECKOUT)
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("Clonegrown command did not return a JSON object")
    return value


def make_fixture(root: Path) -> Path:
    root.mkdir(parents=True)
    canonical = root / "canonical"
    git(root, "init", "-b", "main", canonical)
    git(canonical, "config", "user.name", "Benchmark User")
    git(canonical, "config", "user.email", "benchmark@example.invalid")
    (canonical / "README.md").write_text("benchmark fixture\n", encoding="utf-8")
    source = canonical / "src"
    source.mkdir()
    for index in range(100):
        (source / f"file-{index:03}.txt").write_text("x" * 1000 + "\n", encoding="utf-8")
    git(canonical, "add", ".")
    git(canonical, "commit", "-m", "benchmark fixture")
    workspace = root / "workspace"
    clonegrown("init", canonical, "--workspace", workspace)
    return workspace


def timed_spawn(workspace: Path, mode: str, task: str, request_id: str) -> tuple[float, dict[str, Any]]:
    args: list[str | Path] = [
        "spawn", "--workspace", workspace, "--task", task,
        "--base", "main", "--request-id", request_id,
    ]
    if mode == "worktree":
        args.append("--worktree")
    started = time.perf_counter()
    result = clonegrown(*args)
    return time.perf_counter() - started, result


def measure_sample(root: Path, mode: str, parallelism: int, sample: int) -> dict[str, Any]:
    single_workspace = make_fixture(root / "single")
    single_seconds, single = timed_spawn(single_workspace, mode, "single", "single")
    if single.get("id") != 1 or single.get("status") != "ready":
        raise RuntimeError(f"single-spawn sample returned an invalid worker: {single!r}")

    parallel_workspace = make_fixture(root / "parallel")

    def spawn_one(index: int) -> tuple[float, dict[str, Any]]:
        return timed_spawn(parallel_workspace, mode, f"parallel-{index}", f"parallel-{index}")

    started = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=parallelism) as executor:
        parallel_results = list(executor.map(spawn_one, range(parallelism)))
    parallel_seconds = time.perf_counter() - started
    worker_seconds = [seconds for seconds, _ in parallel_results]
    worker_ids = [int(result["id"]) for _, result in parallel_results]
    if set(worker_ids) != set(range(1, parallelism + 1)):
        raise RuntimeError(f"parallel sample returned invalid worker IDs: {worker_ids!r}")
    if any(result.get("status") != "ready" for _, result in parallel_results):
        raise RuntimeError("parallel sample returned a worker that was not ready")

    return {
        "sample": sample,
        "single_seconds": single_seconds,
        "parallel_seconds": parallel_seconds,
        "parallel_over_single": parallel_seconds / max(single_seconds, 1e-9),
        "parallel_worker_seconds": worker_seconds,
        "parallel_worker_ids": sorted(worker_ids),
    }


def distribution(values: list[float]) -> dict[str, Any]:
    center = statistics.median(values)
    return {
        "raw": values,
        "median": center,
        "spread": {
            "median_absolute_deviation": statistics.median(abs(value - center) for value in values),
            "minimum": min(values),
            "maximum": max(values),
        },
    }


def benchmark(mode: str, samples: int, parallelism: int) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix=f"clonegrown-spawn-benchmark-{mode}-") as temporary:
        root = Path(temporary)
        for sample in range(1, samples + 1):
            rows.append(measure_sample(root / f"sample-{sample}", mode, parallelism, sample))

    return {
        "schema": 1,
        "benchmark": "spawn-concurrency",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "samples": samples,
        "parallelism": parallelism,
        "timing_policy": "informational only; no timing or ratio changes the exit status",
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "git": run(["git", "--version"], cwd=CHECKOUT).stdout.strip(),
            "logical_cpus": os.cpu_count(),
        },
        "raw_samples": rows,
        "summary": {
            "single_seconds": distribution([float(row["single_seconds"]) for row in rows]),
            "parallel_seconds": distribution([float(row["parallel_seconds"]) for row in rows]),
            "parallel_over_single": distribution([float(row["parallel_over_single"]) for row in rows]),
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
    parser.add_argument("--mode", choices=("clone", "worktree"), required=True)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--parallelism", type=int, default=8)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.samples < 3:
        parser.error("--samples must be at least 3 so median spread is meaningful")
    if args.parallelism < 2:
        parser.error("--parallelism must be at least 2")
    destination = output_path(args.output, parser)
    payload = benchmark(args.mode, args.samples, args.parallelism)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    destination.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
