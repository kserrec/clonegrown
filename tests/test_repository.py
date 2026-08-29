"""Exact clone-fidelity behavior for remotes and repository-local configuration."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clonegrown import ClonegrownError, spawn
from clonegrown.core import CommandFailure
from clonegrown.lifecycle import init_workspace
from clonegrown.repository import (
    CloneConfigPlan, ConfigOccurrence, apply_clone_config_plan, build_clone_config_plan,
    local_config_occurrences,
)
from support import make_repo, run_git


class CloneConfigPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.repo = make_repo(self.root, name="canonical space ü")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_plan_is_pure_and_preserves_valueless_empty_repeats_and_includes(self) -> None:
        included = self.root / "included config 雪"
        included.write_text(
            "[agent]\n"
            "\tvalueless\n"
            "\tempty =\n"
            "\trepeated = first value\n"
            "[other]\n"
            "\tmiddle = between repeated values\n"
            "[agent]\n"
            "\trepeated = second ☃\n"
            "\tunicode = café 🚀\n",
            encoding="utf-8",
        )
        run_git(self.repo, "config", "--local", "include.path", str(included))
        config_path = self.repo / ".git" / "config"
        config_before = config_path.read_bytes()
        config_mtime_before = config_path.stat().st_mtime_ns
        refs_before = run_git(self.repo, "for-each-ref").stdout

        plan = build_clone_config_plan(self.repo)

        self.assertEqual(config_path.read_bytes(), config_before)
        self.assertEqual(config_path.stat().st_mtime_ns, config_mtime_before)
        self.assertEqual(run_git(self.repo, "for-each-ref").stdout, refs_before)
        agent = [occurrence for occurrence in plan.occurrences
                 if occurrence.key.startswith("agent.")]
        self.assertEqual(agent, [
            ConfigOccurrence("agent.valueless", None),
            ConfigOccurrence("agent.empty", ""),
            ConfigOccurrence("agent.repeated", "first value"),
            ConfigOccurrence("agent.repeated", "second ☃"),
            ConfigOccurrence("agent.unicode", "café 🚀"),
        ])
        ordered = [occurrence for occurrence in plan.occurrences
                   if occurrence.key.startswith(("agent.", "other."))]
        self.assertEqual(ordered, [
            ConfigOccurrence("agent.valueless", None),
            ConfigOccurrence("agent.empty", ""),
            ConfigOccurrence("agent.repeated", "first value"),
            ConfigOccurrence("other.middle", "between repeated values"),
            ConfigOccurrence("agent.repeated", "second ☃"),
            ConfigOccurrence("agent.unicode", "café 🚀"),
        ])
        self.assertFalse(any(occurrence.key.startswith("include.")
                             for occurrence in plan.occurrences))
        self.assertIn("repo-local config includes were flattened into private worker config",
                      plan.compatibility_warnings)

        workspace = self.root / "far away" / "nested" / "workspace"
        init_workspace(self.repo, workspace)
        worker = spawn(workspace, "HEAD", "config fidelity", strong=False)
        worker_repo = Path(worker["path"])
        actual = [occurrence for occurrence in local_config_occurrences(worker_repo)
                  if occurrence.key.startswith(("agent.", "other."))]
        self.assertEqual(actual, ordered)
        self.assertEqual(run_git(worker_repo, "config", "--bool", "--get",
                                 "agent.valueless").stdout.strip(), "true")
        self.assertEqual(run_git(worker_repo, "config", "--bool", "--get",
                                 "agent.empty").stdout.strip(), "false")
        self.assertNotIn("include.path", {occurrence.key
                                          for occurrence in local_config_occurrences(worker_repo)})
        self.assertIn("agent.repeated", worker["copied_local_config"])

    def test_config_read_failure_is_an_error_and_does_not_change_the_repository(self) -> None:
        config_path = self.repo / ".git" / "config"
        malformed = config_path.read_bytes() + b"\n[unfinished-section\n"
        config_path.write_bytes(malformed)

        with self.assertRaises(CommandFailure) as caught:
            build_clone_config_plan(self.repo)

        self.assertEqual(caught.exception.operation, "git config")
        self.assertEqual(config_path.read_bytes(), malformed)

    def test_invalid_plan_is_rejected_before_worker_mutation(self) -> None:
        worker = self.root / "unpublished worker"
        run_git(self.root, "clone", "--no-checkout", str(self.repo), str(worker))
        config_path = worker / ".git" / "config"
        config_before = config_path.read_bytes()
        invalid = CloneConfigPlan(
            source_remote="origin",
            remote_names=("origin",),
            occurrences=(ConfigOccurrence("remote.origin.url", "local"),),
            copied_local_config=(),
            compatibility_warnings=(),
        )

        with self.assertRaisesRegex(ClonegrownError, "colliding source remote"):
            apply_clone_config_plan(worker, invalid)

        self.assertEqual(config_path.read_bytes(), config_before)
        self.assertEqual(run_git(worker, "remote").stdout.splitlines(), ["origin"])

    def test_git_invalid_config_keys_are_rejected_before_worker_mutation(self) -> None:
        for index, key in enumerate(("bad key.value", "agent.1value", "agent.value_name")):
            with self.subTest(key=key):
                worker = self.root / f"unpublished invalid-key worker {index}"
                run_git(self.root, "clone", "--no-checkout", str(self.repo), str(worker))
                config_path = worker / ".git" / "config"
                config_before = config_path.read_bytes()
                remotes_before = run_git(worker, "remote").stdout.splitlines()
                invalid = CloneConfigPlan(
                    source_remote="cws-source",
                    remote_names=(),
                    occurrences=(ConfigOccurrence(key, "visible"),),
                    copied_local_config=(key,),
                    compatibility_warnings=(),
                )

                with self.assertRaisesRegex(ClonegrownError, "invalid config key"):
                    apply_clone_config_plan(worker, invalid)

                self.assertEqual(config_path.read_bytes(), config_before)
                self.assertEqual(run_git(worker, "remote").stdout.splitlines(), remotes_before)

    def test_git_config_subsection_characters_remain_supported(self) -> None:
        worker = self.root / "unpublished subsection worker"
        run_git(self.root, "clone", "--no-checkout", str(self.repo), str(worker))
        key = "http.https://example.test/path with space.extraheader"
        plan = CloneConfigPlan(
            source_remote="cws-source",
            remote_names=(),
            occurrences=(ConfigOccurrence(key, "visible"),),
            copied_local_config=(key,),
            compatibility_warnings=(),
        )

        apply_clone_config_plan(worker, plan)

        self.assertEqual(run_git(worker, "config", "--get", key).stdout.strip(), "visible")

    def test_git_invalid_canonical_remote_name_is_rejected_before_worker_mutation(self) -> None:
        config_path = self.repo / ".git" / "config"
        config_path.write_text(
            config_path.read_text(encoding="utf-8")
            + '\n[remote "bad name"]\n\turl = ../target.git\n',
            encoding="utf-8",
        )
        plan = build_clone_config_plan(self.repo)
        self.assertIn("bad name", plan.remote_names)

        worker = self.root / "unpublished invalid-remote worker"
        run_git(self.root, "clone", "--no-checkout", str(self.repo), str(worker))
        worker_config = worker / ".git" / "config"
        config_before = worker_config.read_bytes()
        remotes_before = run_git(worker, "remote").stdout.splitlines()

        with self.assertRaisesRegex(ClonegrownError, "invalid remote name"):
            apply_clone_config_plan(worker, plan)

        self.assertEqual(worker_config.read_bytes(), config_before)
        self.assertEqual(run_git(worker, "remote").stdout.splitlines(), remotes_before)

    def test_leading_dash_remote_is_preserved_as_a_valid_literal_name(self) -> None:
        run_git(self.repo, "remote", "add", "--", "-literal", "../dash-target.git")
        plan = build_clone_config_plan(self.repo)
        self.assertIn("-literal", plan.remote_names)

        workspace = self.root / "dash-remote workspace"
        init_workspace(self.repo, workspace)
        worker = spawn(workspace, "HEAD", "leading dash remote")
        worker_repo = Path(worker["path"])

        self.assertIn("-literal", run_git(worker_repo, "remote").stdout.splitlines())
        self.assertEqual(
            run_git(worker_repo, "remote", "get-url", "--", "-literal").stdout.strip(),
            str((self.repo / "../dash-target.git").resolve()),
        )

    def test_relative_fetch_and_push_paths_are_anchored_while_transports_are_unchanged(self) -> None:
        fetch_one = self.root / "fetch target 雪.git"
        fetch_two = self.root / "fetch target two.git"
        push_one = self.root / "push target 雪.git"
        push_two = self.root / "push target two.git"
        absolute = self.root / "absolute target.git"
        for target in (fetch_one, fetch_two, push_one, push_two, absolute):
            run_git(self.root, "init", "--bare", "-q", str(target))

        relative_fetches = ("../fetch target 雪.git", "../fetch target two.git")
        relative_pushes = ("../push target 雪.git", "../push target two.git")
        run_git(self.repo, "remote", "add", "origin", relative_fetches[0])
        run_git(self.repo, "remote", "set-url", "--add", "origin", relative_fetches[1])
        for value in relative_pushes:
            run_git(self.repo, "config", "--local", "--add", "remote.origin.pushurl", value)
        run_git(self.repo, "remote", "add", "cws-source", "https://example.invalid/collision.git")
        credential_url = "https://agent:password@example.invalid/private.git"
        run_git(self.repo, "remote", "add", "web", credential_url)
        scp_url = "agent@example.invalid:org/repository.git"
        run_git(self.repo, "remote", "add", "scp", scp_url)
        run_git(self.repo, "remote", "add", "absolute", str(absolute))
        config_path = self.repo / ".git" / "config"
        config_before = config_path.read_bytes()

        plan = build_clone_config_plan(self.repo)
        planned_origin_urls = [occurrence.value for occurrence in plan.occurrences
                               if occurrence.key == "remote.origin.url"]
        planned_origin_pushes = [occurrence.value for occurrence in plan.occurrences
                                 if occurrence.key == "remote.origin.pushurl"]
        self.assertEqual(planned_origin_urls, [str(fetch_one), str(fetch_two)])
        self.assertEqual(planned_origin_pushes, [str(push_one), str(push_two)])
        self.assertEqual(plan.source_remote, "cws-source-2")
        self.assertEqual(config_path.read_bytes(), config_before)

        workspace = self.root / "a distant area" / "more levels" / "workspace"
        init_workspace(self.repo, workspace)
        worker = spawn(workspace, "HEAD", "remote fidelity", strong=False)
        worker_repo = Path(worker["path"])

        self.assertEqual(worker["source_remote"], "cws-source-2")
        self.assertEqual(run_git(worker_repo, "remote", "get-url", "--all", "origin").stdout.splitlines(),
                         [str(fetch_one), str(fetch_two)])
        self.assertEqual(run_git(worker_repo, "remote", "get-url", "--push", "--all",
                                 "origin").stdout.splitlines(), [str(push_one), str(push_two)])
        self.assertEqual(run_git(worker_repo, "remote", "get-url", "web").stdout.strip(),
                         credential_url)
        self.assertEqual(run_git(worker_repo, "remote", "get-url", "scp").stdout.strip(), scp_url)
        self.assertEqual(run_git(worker_repo, "remote", "get-url", "absolute").stdout.strip(),
                         str(absolute))
        self.assertEqual(run_git(worker_repo, "remote", "get-url", "--push",
                                 "cws-source-2").stdout.strip(), "cws-disabled://canonical")
        self.assertEqual(config_path.read_bytes(), config_before)


if __name__ == "__main__":
    unittest.main()
