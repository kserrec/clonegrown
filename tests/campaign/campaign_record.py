"""Shared metadata and exact replay commands for generated campaigns."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence


REPOSITORY = Path(__file__).resolve().parents[2]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from clonegrown.core import GIT_BIN  # noqa: E402

GITHUB_FIELDS = (
    "GITHUB_EVENT_NAME",
    "GITHUB_RUN_ATTEMPT",
    "GITHUB_RUN_ID",
    "GITHUB_RUN_NUMBER",
    "GITHUB_SHA",
    "GITHUB_WORKFLOW",
    "RUNNER_ARCH",
    "RUNNER_OS",
)


def command_output(arguments: Sequence[str | Path], cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            [str(argument) for argument in arguments],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def write_json_atomic(path: str | Path, payload: dict[str, object]) -> None:
    """Replace a campaign artifact without exposing a partial JSON document."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def campaign_environment() -> dict[str, object]:
    """Return explicit, non-secret provenance fields for a campaign artifact."""
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_build": sys.version.replace("\n", " "),
        "git_executable": str(GIT_BIN),
        "git_version": command_output((GIT_BIN, "--version")),
        "platform": platform.platform(),
        "commit_sha": os.environ.get("GITHUB_SHA")
        or command_output((GIT_BIN, "rev-parse", "HEAD"), cwd=REPOSITORY),
        "github": {name.lower(): os.environ[name] for name in GITHUB_FIELDS if name in os.environ},
    }


def checked_mode(mode: str) -> str:
    if mode not in {"clone", "worktree"}:
        raise ValueError(f"unsupported worker mode: {mode}")
    return mode


def checked_seed(seed: int) -> int:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed must be an integer")
    return seed


def random_kill_replay(mode: str, operation: str, seed: int) -> str:
    mode = checked_mode(mode)
    seed = checked_seed(seed)
    if operation not in {"spawn", "collect", "discard"}:
        raise ValueError(f"unsupported random-kill operation: {operation}")
    output = f"/tmp/clonegrown-random-kill-{mode}-{operation}-{seed}.json"
    return (
        f"CWS_SUITE_MODE={mode} python3 tests/campaign/random_kill.py {operation} "
        f"--start {seed} --count 1 --output {output}"
    )


def state_machine_replay(mode: str, seed: int, steps: int) -> str:
    mode = checked_mode(mode)
    seed = checked_seed(seed)
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
        raise ValueError("steps must be a positive integer")
    root = f"/tmp/clonegrown-state-machine-{mode}-{seed}"
    output = f"/tmp/clonegrown-state-machine-{mode}-{seed}.json"
    return (
        f"CWS_FUZZ_ROOT={root} CWS_SUITE_MODE={mode} "
        "python3 tests/campaign/state_machine_fuzz.py "
        f"--start {seed} --seeds 1 --steps {steps} --output {output}"
    )
