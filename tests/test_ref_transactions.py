"""Ref custody across concurrent Git writes and unsafe enumeration entries."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from clonegrown import ClonegrownError, collect, discard, init_workspace, recover, release, spawn
from clonegrown import lifecycle, repository
from clonegrown.state import WorkerRecord, WorkspaceState
from support import commit, git_out, make_repo, run_git

ROOT = Path(__file__).resolve().parents[1]


class RefTransactionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repo = make_repo(self.root)
        self.ws = self.root / 'workspace'
        init_workspace(self.repo, self.ws)
        self.state = WorkspaceState.load(self.ws)

    def test_failed_spawn_preserves_a_base_pin_that_another_writer_moved(self):
        base = git_out(self.repo, 'rev-parse', 'HEAD')
        foreign = commit(self.repo, 'foreign.txt')
        for mode in ('clone', 'worktree'):
            with self.subTest(mode=mode):
                worker_id = WorkspaceState.load(self.ws).next_id
                pin = self.state.base_ref(worker_id)

                def fail_after_move(point):
                    if point == 'spawn.after_clone':
                        run_git(self.repo, 'update-ref', pin, foreign)
                        raise ClonegrownError('ordinary provisioning failure')

                with mock.patch.object(lifecycle, 'failpoint', fail_after_move):
                    with self.assertRaises(ClonegrownError):
                        spawn(self.ws, base, 'failed pin', mode=mode)
                self.assertEqual(git_out(self.repo, 'rev-parse', pin), foreign)
                recover(self.ws)
                self.assertEqual(git_out(self.repo, 'rev-parse', pin), foreign)

    def test_ref_mutations_preserve_symbolic_refs_inserted_after_preflight(self):
        base = git_out(self.repo, 'rev-parse', 'HEAD')
        candidate = commit(self.repo, 'candidate.txt')
        ref = self.state.result_ref(1, candidate)
        loose = self.repo / '.git' / ref
        original_popen = subprocess.Popen
        for operation in ('create', 'update', 'delete'):
            for target in ('refs/heads/trunk', 'refs/heads/absent-target'):
                for check in (True, False):
                    with self.subTest(operation=operation, target=target, check=check):
                        if operation != 'create':
                            run_git(self.repo, 'update-ref', ref, candidate)
                        planted = False

                        def interleave(argv, *args, **kwargs):
                            nonlocal planted
                            if 'update-ref' in argv and not planted:
                                planted = True
                                run_git(self.repo, 'symbolic-ref', ref, target)
                            return original_popen(argv, *args, **kwargs)

                        try:
                            with mock.patch.object(subprocess, 'Popen', interleave):
                                def mutate():
                                    if operation == 'delete':
                                        return repository.delete_ref(self.repo, ref, candidate, check=check)
                                    old = '0' * len(candidate) if operation == 'create' else candidate
                                    return repository.write_ref(self.repo, ref, base, old, check=check)
                                if check:
                                    with self.assertRaises(ClonegrownError):
                                        mutate()
                                else:
                                    self.assertFalse(mutate())
                            self.assertTrue(planted)
                            self.assertEqual(loose.read_bytes(), f'ref: {target}\n'.encode())
                            self.assertEqual(git_out(self.repo, 'rev-parse', 'trunk'), candidate)
                            self.assertNotEqual(run_git(self.repo, 'rev-parse', '--verify',
                                                        'refs/heads/absent-target', check=False).returncode, 0)
                        finally:
                            loose.unlink(missing_ok=True)

    def test_worktree_cleanup_preserves_both_refs_when_either_becomes_symbolic(self):
        for changed in ('branch', 'owner'):
            with self.subTest(changed=changed):
                worker = spawn(self.ws, 'HEAD', changed, mode='worktree')
                collected = collect(self.ws, worker['id'])
                release(self.ws, worker['id'])
                branch = 'refs/heads/' + worker['branch']
                owner = self.state.branch_owner_ref(worker['id'])
                changed_ref = branch if changed == 'branch' else owner
                original = repository._ref_transaction
                planted = False

                def interleave(repo, lines, **kwargs):
                    nonlocal planted
                    if any(line.startswith('delete ' + branch + ' ') for line in lines) and not planted:
                        planted = True
                        run_git(self.repo, 'symbolic-ref', changed_ref, 'refs/heads/trunk')
                    return original(repo, lines, **kwargs)

                with mock.patch.object(repository, '_ref_transaction', interleave):
                    with self.assertRaises(ClonegrownError):
                        discard(self.ws, worker['id'])
                result = WorkerRecord.load(self.ws, worker['id']).to_json()
                self.assertTrue(planted)
                self.assertEqual(result['status'], 'discarding')
                self.assertEqual((self.repo / '.git' / changed_ref).read_bytes(), b'ref: refs/heads/trunk\n')
                untouched = owner if changed == 'branch' else branch
                self.assertEqual(git_out(self.repo, 'rev-parse', untouched), worker['base_sha'])
                self.assertEqual(git_out(self.repo, 'rev-parse', result['result_ref']), collected['result_sha'])

    def test_direct_unsafe_namespace_entries_refuse_clone_worktree_and_fetch_promptly(self):
        worker = spawn(self.ws, 'HEAD', 'ready to collect')
        commit(Path(worker['path']), 'result.txt')
        external = self.root / 'external-fifo'
        os.mkfifo(external)
        refs = (self.state.summary_ref(99), 'refs/heads/' + self.state.worker_branch(99, 'foreign'))
        for ref in refs:
            for kind in ('fifo', 'symlink'):
                loose = self.repo / '.git' / ref
                loose.parent.mkdir(parents=True, exist_ok=True)
                os.mkfifo(loose) if kind == 'fifo' else loose.symlink_to(external)
                before = loose.lstat()
                try:
                    for arguments in (['spawn', 'blocked clone'], ['spawn', 'blocked worktree', '--worktree'],
                                      ['collect', str(worker['id'])]):
                        with self.subTest(ref=ref, kind=kind, arguments=arguments):
                            process = subprocess.Popen(
                                [sys.executable, '-m', 'clonegrown', *arguments, '--workspace', str(self.ws)],
                                env=dict(os.environ, PYTHONPATH=str(ROOT)), cwd=self.root,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                            try:
                                stdout, stderr = process.communicate(timeout=10)
                            except subprocess.TimeoutExpired:
                                os.killpg(process.pid, signal.SIGKILL)
                                process.communicate()
                                self.fail('canonical Git enumeration blocked on a non-regular namespace entry')
                            self.assertEqual(process.returncode, 2, stderr)
                            self.assertEqual(stdout, '')
                            self.assertIn(ref, stderr)
                            self.assertEqual((loose.lstat().st_dev, loose.lstat().st_ino),
                                             (before.st_dev, before.st_ino))
                            self.assertTrue(Path(worker['path']).is_dir())
                finally:
                    loose.unlink()
