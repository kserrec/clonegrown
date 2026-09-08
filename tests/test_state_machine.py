"""The randomized model must reject unsafe success as well as accept safe refusal."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent / 'campaign'))
import state_machine_fuzz as campaign
import clonegrown as cws


class PrivateRefModelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        real_root = root / 'real'
        real_root.mkdir()
        alias_root = root / 'alias'
        alias_root.symlink_to(real_root, target_is_directory=True)
        for name, value in [('ROOT', alias_root), ('WORKTREE', False)]:
            patcher = patch.object(campaign, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        _, self.canonical, self.workspace, self.origin = campaign.setup(0)

    def worker_with_private_change(self, mutation):
        worker = cws.spawn(self.workspace, 'main', mutation)
        repo = Path(worker['path'])
        baseline = campaign.private_refs(repo, worker['branch'])
        if mutation == 'delete':
            campaign.git(repo, 'remote', 'remove', 'origin')
        else:
            tip = campaign.commit(repo, 'new commit', 1)
            name = 'refs/remotes/origin/main' if mutation == 'move' else 'refs/heads/private'
            campaign.git(repo, 'update-ref', name, tip)
        worker = cws.collect(self.workspace, worker['id'])
        return worker, baseline

    def test_created_moved_and_deleted_private_refs_require_acknowledgement(self):
        for mutation in ('create', 'move', 'delete'):
            with self.subTest(mutation=mutation):
                worker, baseline = self.worker_with_private_change(mutation)
                events = []
                campaign.discard_collected(self.workspace, worker, baseline,
                                           lambda *event: events.append(event[0]))
                self.assertEqual(events, ['discard_refused_private_refs',
                                          'discard_acknowledged_private_refs'])
                self.assertEqual(campaign.metas(self.workspace)[worker['id']]['status'], 'discarded')
        campaign.invariant(self.canonical, self.workspace, self.origin, full=True)

    def test_model_detects_a_discard_that_bypasses_private_ref_protection(self):
        worker, baseline = self.worker_with_private_change('delete')
        real_discard = cws.discard

        def unsafe_discard(workspace, worker_id, **kwargs):
            return real_discard(workspace, worker_id, discard_private_refs=True)

        with patch.object(cws, 'discard', unsafe_discard):
            with self.assertRaisesRegex(AssertionError, 'silently deleted changed private refs'):
                campaign.discard_collected(self.workspace, worker, baseline, lambda *event: None)

    def test_invariant_detects_an_unowned_canonical_task_branch(self):
        campaign.git(self.canonical, 'branch', 'agent/foreign/1-task')
        with self.assertRaises(AssertionError):
            campaign.invariant(self.canonical, self.workspace, self.origin)
