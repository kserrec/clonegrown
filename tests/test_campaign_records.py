"""Artifact provenance and exact one-seed replay command tests."""

from __future__ import annotations

import contextlib
import io
import json
import os
import platform
import re
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch


CAMPAIGN_DIRECTORY = Path(__file__).resolve().parent / "campaign"
REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CAMPAIGN_DIRECTORY))

import campaign_record  # noqa: E402
import blocking_git  # noqa: E402
import hardening_suite  # noqa: E402
import random_kill  # noqa: E402
import state_machine_fuzz  # noqa: E402
from campaign_record import (  # noqa: E402
    campaign_environment,
    random_kill_replay,
    state_machine_replay,
    write_json_atomic,
)


def yaml_code_lines(path: Path) -> list[str]:
    """Return active YAML source lines without comments that could shadow assertions."""
    lines: list[str] = []
    for raw_line in path.read_text().splitlines():
        single_quoted = False
        double_quoted = False
        escaped = False
        comment_at: int | None = None
        for index, character in enumerate(raw_line):
            if escaped:
                escaped = False
            elif double_quoted and character == "\\":
                escaped = True
            elif not double_quoted and character == "'":
                single_quoted = not single_quoted
            elif not single_quoted and character == '"':
                double_quoted = not double_quoted
            elif not single_quoted and not double_quoted and character == "#" and (
                index == 0 or raw_line[index - 1].isspace()
            ):
                comment_at = index
                break
        code = raw_line[:comment_at].rstrip() if comment_at is not None else raw_line.rstrip()
        if code.strip():
            lines.append(code)
    return lines


def workflow_job(path: Path, name: str) -> str:
    """Return one active top-level job block from the constrained workflows."""
    source = "\n".join(yaml_code_lines(path))
    yaml_direct_keys(source, 0)
    jobs = yaml_block(source, "jobs:")
    yaml_direct_keys(jobs, 2)
    return yaml_block(jobs, f"  {name}:")


def yaml_block(source: str, marker: str) -> str:
    """Return one uniquely marked indentation-owned YAML block."""
    lines = source.splitlines()
    if lines.count(marker) != 1:
        raise AssertionError(f"expected one active YAML marker {marker!r}")
    start = lines.index(marker)
    indentation = len(marker) - len(marker.lstrip(" "))
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if len(lines[index]) - len(lines[index].lstrip(" ")) <= indentation
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def yaml_direct_entries(source: str, indentation: int) -> list[tuple[str, str]]:
    """Return simple direct mappings, failing closed on other active key syntax."""
    pattern = re.compile(
        rf"^{' ' * indentation}(?:(['\"])([A-Za-z_][A-Za-z0-9_-]*)\1|([A-Za-z_][A-Za-z0-9_-]*))[ \t]*:[ \t]*(.*)$"
    )
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in source.splitlines():
        if len(line) - len(line.lstrip(" ")) != indentation:
            continue
        match = pattern.match(line)
        if match is None:
            raise AssertionError(f"unsupported active YAML mapping syntax: {line!r}")
        key = match.group(2) or match.group(3)
        if key in seen:
            raise AssertionError(f"duplicate active YAML mapping key: {key!r}")
        seen.add(key)
        entries.append((key, match.group(4).strip()))
    return entries


def yaml_direct_values(source: str, indentation: int, key: str) -> list[str]:
    """Return values assigned to one key at exactly the requested indentation."""
    return [value for entry_key, value in yaml_direct_entries(source, indentation) if entry_key == key]


def yaml_direct_keys(source: str, indentation: int) -> list[str]:
    """Return mapping keys declared at exactly the requested indentation."""
    return [key for key, _ in yaml_direct_entries(source, indentation)]


def workflow_trigger_keys(path: Path) -> set[str]:
    """Return active event names from this repository's block-style `on` mapping."""
    lines = yaml_code_lines(path)
    yaml_direct_keys("\n".join(lines), 0)
    if lines.count("on:") != 1:
        raise AssertionError("expected one active top-level on mapping")
    start = lines.index("on:") + 1
    end = next((index for index in range(start, len(lines)) if not lines[index].startswith(" ")), len(lines))
    return set(yaml_direct_keys("\n".join(lines[start:end]), 2))


class CampaignRecordTests(unittest.TestCase):
    def test_blocking_git_recognizes_fd_backed_commands_and_preserves_the_fd(self) -> None:
        args = ["--git-dir=/dev/fd/71", "worktree", "repair", "/tmp/worker"]
        self.assertEqual(blocking_git.command_arguments(args), args[1:])
        self.assertEqual(blocking_git.inherited_descriptor_fds(args), (71,))
        self.assertEqual(
            blocking_git.command_arguments([
                "-c", "safe.directory=/tmp/repo", "-C", "/tmp/repo", "fetch", "source",
            ]),
            ["fetch", "source"],
        )

        with tempfile.TemporaryDirectory() as directory:
            control = Path(directory)
            (control / "release").touch()
            environment = {
                "CLONEGROWN_TEST_REAL_GIT": "/usr/bin/git",
                "CLONEGROWN_TEST_GIT_CONTROL": str(control),
                "CLONEGROWN_TEST_GIT_TARGET": "worktree-repair",
            }
            completed = blocking_git.subprocess.CompletedProcess(
                args=["/usr/bin/git", *args], returncode=0, stdout="", stderr="",
            )
            with (
                patch.dict(os.environ, environment, clear=True),
                patch.object(sys, "argv", ["blocking_git.py", *args]),
                patch.object(blocking_git.subprocess, "run", return_value=completed) as run,
            ):
                self.assertEqual(blocking_git.main(), 0)

            self.assertEqual(json.loads((control / "started.json").read_text())["args"], args[1:])
            self.assertEqual(run.call_args.kwargs["pass_fds"], (71,))

    def test_random_kill_replay_is_one_exact_seed_in_the_recorded_mode(self) -> None:
        for mode in ("clone", "worktree"):
            for operation in ("spawn", "collect", "discard"):
                with self.subTest(mode=mode, operation=operation):
                    self.assertEqual(
                        random_kill_replay(mode, operation, 42),
                        f"CWS_SUITE_MODE={mode} python3 tests/campaign/random_kill.py {operation} "
                        f"--start 42 --count 1 --output "
                        f"/tmp/clonegrown-random-kill-{mode}-{operation}-42.json",
                    )

    def test_state_machine_replay_is_one_exact_seed_and_step_count(self) -> None:
        for mode in ("clone", "worktree"):
            with self.subTest(mode=mode):
                self.assertEqual(
                    state_machine_replay(mode, 17, 50),
                    f"CWS_FUZZ_ROOT=/tmp/clonegrown-state-machine-{mode}-17 "
                    f"CWS_SUITE_MODE={mode} python3 tests/campaign/state_machine_fuzz.py "
                    f"--start 17 --seeds 1 --steps 50 --output "
                    f"/tmp/clonegrown-state-machine-{mode}-17.json",
                )

    def test_replay_parts_reject_shell_text_and_invalid_bounds(self) -> None:
        with self.assertRaises(ValueError):
            random_kill_replay("clone;echo nope", "spawn", 0)
        with self.assertRaises(ValueError):
            random_kill_replay("clone", "spawn;echo nope", 0)
        with self.assertRaises(TypeError):
            random_kill_replay("clone", "spawn", "0")  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            state_machine_replay("clone", 0, 0)

    def test_environment_records_exact_python_git_and_commit_provenance(self) -> None:
        environment = campaign_environment()
        self.assertEqual(environment["python_version"], platform.python_version())
        self.assertEqual(environment["python_implementation"], platform.python_implementation())
        self.assertEqual(environment["git_executable"], str(campaign_record.GIT_BIN))
        self.assertRegex(str(environment["git_version"]), r"^git version \S+")
        self.assertRegex(str(environment["commit_sha"]), r"^[0-9a-f]{40}$")
        self.assertNotRegex(str(environment["python_build"]), re.compile(r"[\r\n]"))
        self.assertIsInstance(environment["github"], dict)

    def test_environment_uses_selected_git_and_only_the_github_allowlist(self) -> None:
        selected_git = Path("/selected/git")
        controlled_environment = {
            "GITHUB_RUN_ID": "123",
            "RUNNER_OS": "ControlledOS",
            "UNRELATED_SECRET_SENTINEL": "must-not-be-recorded",
        }
        outputs = ["git version 9.9.9", "a" * 40]
        with (
            patch.dict(os.environ, controlled_environment, clear=True),
            patch.object(campaign_record, "GIT_BIN", selected_git),
            patch.object(campaign_record, "command_output", side_effect=outputs) as command,
        ):
            environment = campaign_environment()

        self.assertEqual(environment["git_executable"], str(selected_git))
        self.assertEqual(environment["git_version"], "git version 9.9.9")
        self.assertEqual(environment["commit_sha"], "a" * 40)
        self.assertEqual(environment["github"], {"github_run_id": "123", "runner_os": "ControlledOS"})
        self.assertNotIn("must-not-be-recorded", json.dumps(environment))
        self.assertEqual(
            command.call_args_list,
            [
                call((selected_git, "--version")),
                call((selected_git, "rev-parse", "HEAD"), cwd=campaign_record.REPOSITORY),
            ],
        )

    def test_campaign_fixture_git_helpers_use_the_product_selected_binary(self) -> None:
        selected_git = Path("/selected/git")
        for module in (random_kill, state_machine_fuzz):
            with self.subTest(module=module.__name__):
                marker = object()
                with patch.object(module, "GIT_BIN", selected_git), patch.object(module, "run", return_value=marker) as run:
                    self.assertIs(module.git(Path("/repo"), "status"), marker)
                self.assertEqual(run.call_args.args[0], [selected_git, "status"])

        marker = object()
        with (
            patch.object(hardening_suite, "GIT_BIN", selected_git),
            patch.object(hardening_suite, "run", return_value=marker) as run,
        ):
            self.assertIs(hardening_suite.git(Path("/repo"), "status"), marker)
        self.assertEqual(run.call_args.args[0], [selected_git, "status"])
        self.assertEqual(run.call_args.kwargs["cwd"], Path("/repo"))

    def test_atomic_artifact_write_preserves_the_last_complete_document(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "result.json"
            write_json_atomic(output, {"generation": 1})
            with patch.object(campaign_record.json, "dump", side_effect=RuntimeError("interrupted")):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    write_json_atomic(output, {"generation": 2})
            self.assertEqual(json.loads(output.read_text()), {"generation": 1})
            self.assertEqual(list(output.parent.glob(f".{output.name}.*.tmp")), [])

    def test_random_kill_rejects_a_target_that_was_not_killed_by_sigkill(self) -> None:
        cases = ((0, 0, False), (-signal.SIGKILL, -signal.SIGKILL, False), (None, 0, True))
        for poll_result, returncode, kill_called in cases:
            with self.subTest(poll_result=poll_result, returncode=returncode):
                process = MagicMock()
                process.pid = 123
                process.returncode = returncode
                process.poll.return_value = poll_result
                process.communicate.return_value = ("", "")
                with (
                    patch.object(random_kill.subprocess, "Popen", return_value=process) as popen,
                    patch.object(random_kill.time, "sleep"),
                    patch.object(random_kill.os, "killpg") as killpg,
                ):
                    with self.assertRaisesRegex(RuntimeError, "was not interrupted"):
                        random_kill.start_and_kill(["status"], 0)
                self.assertIs(popen.call_args.kwargs.get("start_new_session"), True)
                if kill_called:
                    killpg.assert_called_once_with(process.pid, signal.SIGKILL)
                else:
                    killpg.assert_not_called()

        process = MagicMock()
        process.pid = 123
        process.returncode = -signal.SIGKILL
        process.poll.return_value = None
        process.communicate.return_value = ("out", "err")
        with (
            patch.object(random_kill.subprocess, "Popen", return_value=process) as popen,
            patch.object(random_kill.time, "sleep"),
            patch.object(random_kill.os, "killpg") as killpg,
        ):
            result = random_kill.start_and_kill(["status"], 0)
        self.assertIs(popen.call_args.kwargs.get("start_new_session"), True)
        killpg.assert_called_once_with(process.pid, signal.SIGKILL)
        self.assertEqual((result["killed"], result["rc"]), (True, -signal.SIGKILL))

    def test_random_kill_main_prewrites_and_updates_the_artifact_contract(self) -> None:
        for worker, worktree in (("clone", False), ("worktree", True)):
            for operation in ("spawn", "collect", "discard"):
                with self.subTest(worker=worker, operation=operation), tempfile.TemporaryDirectory() as td:
                    output = Path(td) / "random-kill.json"
                    replay = (
                        f"CWS_SUITE_MODE={worker} python3 tests/campaign/random_kill.py {operation} "
                        "--start 7 --count 1 --output "
                        f"/tmp/clonegrown-random-kill-{worker}-{operation}-7.json"
                    )

                    def successful_case(seed: int) -> dict[str, object]:
                        pending = json.loads(output.read_text())
                        self.assertEqual((pending["executed"], pending["pending"]), (0, 1))
                        self.assertEqual(pending["environment"], {"provenance": "controlled"})
                        self.assertEqual(pending["results"][0]["replay_command"], replay)
                        return {
                            "mode": operation,
                            "seed": seed,
                            "ok": True,
                            "process": {"killed": True, "rc": -9},
                        }

                    arguments = [
                        "random_kill.py",
                        operation,
                        "--start",
                        "7",
                        "--count",
                        "1",
                        "--output",
                        str(output),
                    ]
                    with (
                        patch.object(random_kill, "WORKTREE", worktree),
                        patch.object(
                            random_kill,
                            "campaign_environment",
                            return_value={"provenance": "controlled"},
                        ),
                        patch.object(random_kill, f"{operation}_case", side_effect=successful_case),
                        patch.object(random_kill, "write_json_atomic", wraps=write_json_atomic) as atomic_write,
                        patch.object(sys, "argv", arguments),
                        contextlib.redirect_stdout(io.StringIO()),
                    ):
                        self.assertEqual(random_kill.main(), 0)

                    self.assertEqual(atomic_write.call_count, 2)
                    self.assertTrue(all(Path(item.args[0]) == output for item in atomic_write.call_args_list))
                    self.assertEqual(
                        [
                            (item.args[1]["executed"], item.args[1]["pending"])
                            for item in atomic_write.call_args_list
                        ],
                        [(0, 1), (1, 0)],
                    )
                    result = json.loads(output.read_text())
                    self.assertEqual((result["worker"], result["executed"], result["pending"]), (worker, 1, 0))
                    self.assertEqual((result["passed"], result["failed"]), (1, 0))
                    self.assertEqual(result["environment"], {"provenance": "controlled"})
                    self.assertEqual(result["results"][0]["status"], "passed")
                    self.assertEqual(result["results"][0]["replay_command"], replay)

    def test_state_machine_main_preserves_replay_for_unexecuted_seeds(self) -> None:
        for mode in ("clone", "worktree"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                output = root / "state-machine.json"
                replays = [
                    f"CWS_FUZZ_ROOT=/tmp/clonegrown-state-machine-{mode}-{seed} "
                    f"CWS_SUITE_MODE={mode} python3 tests/campaign/state_machine_fuzz.py "
                    f"--start {seed} --seeds 1 --steps 25 --output "
                    f"/tmp/clonegrown-state-machine-{mode}-{seed}.json"
                    for seed in (11, 12)
                ]

                def failing_case(seed: int, steps: int) -> dict[str, object]:
                    pending = json.loads(output.read_text())
                    self.assertEqual((pending["executed"], pending["pending"]), (0, 2))
                    self.assertEqual(pending["environment"], {"provenance": "controlled"})
                    self.assertEqual([row["replay_command"] for row in pending["results"]], replays)
                    return {"seed": seed, "steps": steps, "ok": False, "error": "controlled failure"}

                arguments = [
                    "state_machine_fuzz.py",
                    "--start",
                    "11",
                    "--seeds",
                    "2",
                    "--steps",
                    "25",
                    "--output",
                    str(output),
                ]
                with (
                    patch.object(state_machine_fuzz, "ROOT", root / "fixtures"),
                    patch.object(state_machine_fuzz, "MODE", mode),
                    patch.object(
                        state_machine_fuzz,
                        "campaign_environment",
                        return_value={"provenance": "controlled"},
                    ),
                    patch.object(state_machine_fuzz, "one", side_effect=failing_case),
                    patch.object(state_machine_fuzz, "write_json_atomic", wraps=write_json_atomic) as atomic_write,
                    patch.object(sys, "argv", arguments),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(state_machine_fuzz.main(), 1)

                self.assertEqual(atomic_write.call_count, 2)
                self.assertTrue(all(Path(item.args[0]) == output for item in atomic_write.call_args_list))
                self.assertEqual(
                    [
                        (item.args[1]["executed"], item.args[1]["pending"])
                        for item in atomic_write.call_args_list
                    ],
                    [(0, 2), (1, 1)],
                )
                result = json.loads(output.read_text())
                self.assertEqual((result["executed"], result["pending"], result["failed"]), (1, 1, 1))
                self.assertEqual(result["environment"], {"provenance": "controlled"})
                self.assertEqual([row["status"] for row in result["results"]], ["failed", "pending"])
                self.assertEqual([row["replay_command"] for row in result["results"]], replays)

    def test_state_machine_invariant_rejects_corrupt_worker_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td, patch.object(state_machine_fuzz, "ROOT", Path(td)), patch.object(state_machine_fuzz, "WORKTREE", False):
            _, canonical, workspace, origin = state_machine_fuzz.setup(0)
            worker = state_machine_fuzz.cws.spawn(workspace, "main", "corrupt", strong=False, mode="clone")
            (workspace / ".cws" / "workers" / f"{worker['id']}.json").write_text("{")
            with self.assertRaisesRegex(AssertionError, "invalid-worker-metadata"):
                state_machine_fuzz.invariant(canonical, workspace, origin)

    def test_hardening_reports_conditional_checks_as_skipped_not_passed(self) -> None:
        with patch.dict(
            hardening_suite.TESTS,
            {"conditional": ("compat", lambda: {"skipped": "feature unavailable"})},
            clear=True,
        ):
            row = hardening_suite.run_one("conditional")
        self.assertTrue(row["ok"])
        self.assertTrue(row["skipped"])
        self.assertEqual(
            hardening_suite.result_counts([row, {"ok": True}, {"ok": False}]),
            {"total": 3, "passed": 1, "skipped": 1, "failed": 1},
        )

    def test_hardening_driver_preserves_skips_and_rejects_nonzero_children(self) -> None:
        cases = (
            (
                "skip",
                0,
                {"name": "probe", "group": "compat", "mode": "clone", "ok": True, "skipped": True, "details": {"skipped": "unavailable"}},
                0,
                {"total": 1, "passed": 0, "skipped": 1, "failed": 0},
            ),
            (
                "nonzero",
                137,
                {"name": "probe", "group": "compat", "mode": "clone", "ok": True, "skipped": False, "details": {}},
                1,
                {"total": 1, "passed": 0, "skipped": 0, "failed": 1},
            ),
        )
        for label, child_rc, child_result, expected_rc, expected_counts in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as td:
                output = Path(td) / "hardening.json"
                child = hardening_suite.subprocess.CompletedProcess(
                    args=["hardening_suite.py"],
                    returncode=child_rc,
                    stdout="RESULT_JSON=" + json.dumps(child_result) + "\n",
                    stderr="",
                )
                with (
                    patch.dict(hardening_suite.TESTS, {"probe": ("compat", lambda: {})}, clear=True),
                    patch.object(hardening_suite, "OUT", output),
                    patch.object(hardening_suite.subprocess, "run", return_value=child),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(hardening_suite.driver(names=["probe"]), expected_rc)
                payload = json.loads(output.read_text())
                self.assertEqual({name: payload[name] for name in expected_counts}, expected_counts)
                self.assertEqual(payload["results"][0]["child_rc"], child_rc)
                if child_rc:
                    self.assertIn("child exited 137", payload["results"][0]["error"])

    def test_randomized_jobs_bound_setup_campaign_and_artifact_upload_separately(self) -> None:
        workflow = REPOSITORY / ".github" / "workflows" / "randomized-campaigns.yml"
        source = "\n".join(yaml_code_lines(workflow))
        self.assertEqual(workflow_trigger_keys(workflow), {"workflow_dispatch", "schedule"})
        schedule = yaml_block(source, "  schedule:")
        self.assertEqual(schedule.splitlines(), ["  schedule:", "    - cron: '37 9 * * *'"])

        dispatch = yaml_block(source, "  workflow_dispatch:")
        yaml_direct_keys(dispatch, 4)
        inputs = yaml_block(dispatch, "    inputs:")
        input_contracts = (
            ("seed_start", "'0'", "string", None),
            ("random_kill_seed_count", "'2'", "choice", "['1', '2', '3', '5']"),
            ("state_machine_seed_count", "'2'", "choice", "['1', '2', '3', '5']"),
            ("state_machine_steps", "'50'", "choice", "['25', '50', '75', '100']"),
        )
        self.assertEqual(yaml_direct_keys(inputs, 6), [contract[0] for contract in input_contracts])
        for input_name, default, input_type, options in input_contracts:
            with self.subTest(input=input_name):
                input_block = yaml_block(inputs, f"      {input_name}:")
                self.assertEqual(yaml_direct_values(input_block, 8, "required"), ["true"])
                self.assertEqual(yaml_direct_values(input_block, 8, "default"), [default])
                self.assertEqual(yaml_direct_values(input_block, 8, "type"), [input_type])
                self.assertEqual(yaml_direct_values(input_block, 8, "options"), [] if options is None else [options])

        global_env = yaml_block(source, "env:")
        self.assertEqual(
            global_env.splitlines(),
            [
                "env:",
                "  CAMPAIGN_SEED_START: ${{ inputs.seed_start || github.run_number }}",
                "  RANDOM_KILL_SEED_COUNT: ${{ inputs.random_kill_seed_count || '2' }}",
                "  STATE_MACHINE_SEED_COUNT: ${{ inputs.state_machine_seed_count || '2' }}",
                "  STATE_MACHINE_STEPS: ${{ inputs.state_machine_steps || '50' }}",
            ],
        )
        jobs = (
            (
                "random-kill",
                "Run bounded random-kill seeds",
                "Retain random-kill result",
                ["      matrix:", "        mode: [clone, worktree]", "        operation: [spawn, collect, discard]"],
                ["        env:", "          CWS_SUITE_MODE: ${{ matrix.mode }}"],
                [
                    "        run: >-",
                    "          python3 tests/campaign/random_kill.py ${{ matrix.operation }}",
                    '          --start "$CAMPAIGN_SEED_START"',
                    '          --count "$RANDOM_KILL_SEED_COUNT"',
                    '          --output "${{ runner.temp }}/random-kill-${{ matrix.mode }}-${{ matrix.operation }}.json"',
                ],
                "random-kill-${{ matrix.mode }}-${{ matrix.operation }}-${{ github.run_id }}-${{ github.run_attempt }}",
                "${{ runner.temp }}/random-kill-${{ matrix.mode }}-${{ matrix.operation }}.json",
            ),
            (
                "state-machine",
                "Run bounded state-machine seeds",
                "Retain state-machine result",
                ["      matrix:", "        mode: [clone, worktree]"],
                [
                    "        env:",
                    "          CWS_FUZZ_ROOT: ${{ runner.temp }}/state-machine-${{ matrix.mode }}",
                    "          CWS_SUITE_MODE: ${{ matrix.mode }}",
                ],
                [
                    "        run: >-",
                    "          python3 tests/campaign/state_machine_fuzz.py",
                    '          --start "$CAMPAIGN_SEED_START"',
                    '          --seeds "$STATE_MACHINE_SEED_COUNT"',
                    '          --steps "$STATE_MACHINE_STEPS"',
                    '          --output "${{ runner.temp }}/state-machine-${{ matrix.mode }}.json"',
                ],
                "state-machine-${{ matrix.mode }}-${{ github.run_id }}-${{ github.run_attempt }}",
                "${{ runner.temp }}/state-machine-${{ matrix.mode }}.json",
            ),
        )
        for name, campaign_step, upload_step, expected_matrix, expected_env, expected_run, artifact_name, artifact_path in jobs:
            with self.subTest(job=name):
                job = workflow_job(workflow, name)
                job_keys = yaml_direct_keys(job, 4)
                self.assertNotIn("if", job_keys)
                self.assertNotIn("env", job_keys)
                self.assertEqual(yaml_direct_values(job, 4, "timeout-minutes"), ["45"])

                strategy = yaml_block(job, "    strategy:")
                self.assertEqual(yaml_direct_values(strategy, 6, "fail-fast"), ["false"])
                self.assertEqual(yaml_block(strategy, "      matrix:").splitlines(), expected_matrix)

                checkout = yaml_block(job, "      - uses: actions/checkout@v7")
                self.assertEqual(yaml_direct_values(checkout, 8, "timeout-minutes"), ["5"])
                setup = yaml_block(job, "      - uses: actions/setup-python@v7")
                self.assertEqual(yaml_direct_values(setup, 8, "timeout-minutes"), ["5"])

                campaign = yaml_block(job, f"      - name: {campaign_step}")
                self.assertEqual(yaml_direct_values(campaign, 8, "timeout-minutes"), ["25"])
                self.assertEqual(yaml_block(campaign, "        env:").splitlines(), expected_env)
                self.assertEqual(yaml_block(campaign, "        run: >-").splitlines(), expected_run)

                upload = yaml_block(job, f"      - name: {upload_step}")
                self.assertEqual(yaml_direct_values(upload, 8, "if"), ["${{ always() }}"])
                self.assertEqual(yaml_direct_values(upload, 8, "uses"), ["actions/upload-artifact@v7"])
                self.assertEqual(yaml_direct_values(upload, 8, "timeout-minutes"), ["5"])
                upload_with = yaml_block(upload, "        with:")
                self.assertEqual(yaml_direct_values(upload_with, 10, "name"), [artifact_name])
                self.assertEqual(yaml_direct_values(upload_with, 10, "path"), [artifact_path])
                self.assertEqual(yaml_direct_values(upload_with, 10, "if-no-files-found"), ["error"])
                self.assertEqual(yaml_direct_values(upload_with, 10, "retention-days"), ["30"])
                self.assertNotIn("continue-on-error", job)
                self.assertNotIn("||", job)
                self.assertNotIn("set +e", job)
                self.assertNotIn("shell:", job)

    def test_ci_hardening_retains_each_structured_result_without_matrix_cancellation(self) -> None:
        workflow = REPOSITORY / ".github" / "workflows" / "ci.yml"
        job = workflow_job(workflow, "hardening")
        self.assertNotIn("if", yaml_direct_keys(job, 4))
        strategy = yaml_block(job, "    strategy:")
        self.assertEqual(yaml_direct_values(strategy, 6, "fail-fast"), ["false"])
        matrix = yaml_block(strategy, "      matrix:")
        self.assertEqual(yaml_direct_values(matrix, 8, "mode"), ["[clone, worktree]"])

        campaign = yaml_block(job, "      - name: Adversarial suite (${{ matrix.mode }} workers)")
        self.assertEqual(yaml_direct_values(campaign, 8, "run"), ["python tests/campaign/hardening_suite.py"])
        campaign_env = yaml_block(campaign, "        env:")
        result_path = "${{ runner.temp }}/hardening-${{ matrix.mode }}.json"
        self.assertEqual(yaml_direct_values(campaign_env, 10, "CWS_SUITE_MODE"), ["${{ matrix.mode }}"])
        self.assertEqual(yaml_direct_values(campaign_env, 10, "CWS_RESULTS_PATH"), [result_path])

        upload = yaml_block(job, "      - name: Retain hardening result (${{ matrix.mode }} workers)")
        self.assertEqual(yaml_direct_values(upload, 8, "if"), ["${{ always() }}"])
        self.assertEqual(yaml_direct_values(upload, 8, "uses"), ["actions/upload-artifact@v7"])
        upload_with = yaml_block(upload, "        with:")
        artifact_name = "hardening-${{ matrix.mode }}-${{ github.run_id }}-${{ github.run_attempt }}"
        self.assertEqual(yaml_direct_values(upload_with, 10, "name"), [artifact_name])
        self.assertEqual(yaml_direct_values(upload_with, 10, "path"), [result_path])
        self.assertEqual(yaml_direct_values(upload_with, 10, "if-no-files-found"), ["error"])
        self.assertEqual(yaml_direct_values(upload_with, 10, "retention-days"), ["30"])
        self.assertNotIn("continue-on-error", job)
        self.assertNotIn("||", job)
        self.assertNotIn("set +e", job)
        self.assertNotIn("shell:", job)


if __name__ == "__main__":
    unittest.main()
