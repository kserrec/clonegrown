"""Unsupported ref backends are refused before lifecycle mutation."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clonegrown import ClonegrownError, collect, discard, init_workspace, recover, release, spawn
from clonegrown.core import validate_primary_repo
from support import commit, git_out, make_repo, run_git


class RefStorageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def require_reftable(self):
        probe = self.root / 'probe'
        result = run_git(self.root, 'init', '-q', '--ref-format=reftable', str(probe), check=False)
        if result.returncode:
            self.skipTest('this Git cannot create reftable repositories')
        return probe

    def test_files_backend_is_supported(self):
        repo = make_repo(self.root)
        self.assertEqual(validate_primary_repo(repo), repo)
        workspace = self.root / 'workspace'
        init_workspace(repo, workspace)
        for mode in ('clone', 'worktree'):
            worker = spawn(workspace, 'HEAD', mode, mode=mode)
            collect(workspace, worker['id'])
            release(workspace, worker['id'])
            self.assertEqual(discard(workspace, worker['id'])['status'], 'discarded')

    def test_reftable_init_refuses_before_creating_workspace_or_marker(self):
        repo = self.require_reftable()
        commit(repo, 'README.md')
        self.assertEqual(git_out(repo, 'rev-parse', '--show-ref-format'), 'reftable')
        before = git_out(repo, 'for-each-ref')
        workspace = self.root / 'workspace'
        with self.assertRaisesRegex(ClonegrownError, 'requires the files ref backend.*reftable'):
            init_workspace(repo, workspace)
        self.assertFalse(workspace.exists())
        self.assertFalse((repo / '.git/cws').exists())
        self.assertEqual(git_out(repo, 'for-each-ref'), before)

    def test_migrated_canonical_is_refused_before_record_or_ref_changes(self):
        self.require_reftable()
        repo = make_repo(self.root)
        workspace = self.root / 'workspace'
        init_workspace(repo, workspace)
        worker = spawn(workspace, 'HEAD', 'existing')
        release(workspace, worker['id'])
        run_git(repo, 'refs', 'migrate', '--ref-format=reftable')
        record = workspace / '.cws/workers/1.json'
        state = workspace / '.cws/state.json'
        before = (record.read_bytes(), state.read_bytes(), git_out(repo, 'for-each-ref'))
        operations = [lambda mode=mode: spawn(workspace, 'HEAD', 'new', mode=mode)
                      for mode in ('clone', 'worktree')]
        operations += [lambda: collect(workspace, 1), lambda: discard(workspace, 1, abandon=True),
                       lambda: recover(workspace)]
        for operation in operations:
            with self.assertRaisesRegex(ClonegrownError, 'requires the files ref backend.*reftable'):
                operation()
            self.assertEqual((record.read_bytes(), state.read_bytes(), git_out(repo, 'for-each-ref')), before)
            self.assertTrue(Path(worker['path']).is_dir())

    def test_migrated_clone_is_refused_before_collection_or_deletion(self):
        self.require_reftable()
        repo = make_repo(self.root)
        workspace = self.root / 'workspace'
        init_workspace(repo, workspace)
        worker = spawn(workspace, 'HEAD', 'existing')
        release(workspace, worker['id'])
        clone = Path(worker['path'])
        run_git(clone, 'refs', 'migrate', '--ref-format=reftable')
        record = workspace / '.cws/workers/1.json'
        before = (record.read_bytes(), git_out(repo, 'for-each-ref'), git_out(clone, 'for-each-ref'))
        for operation in (lambda: collect(workspace, 1), lambda: discard(workspace, 1, abandon=True)):
            with self.assertRaisesRegex(ClonegrownError, 'requires the files ref backend.*reftable'):
                operation()
            self.assertEqual((record.read_bytes(), git_out(repo, 'for-each-ref'),
                              git_out(clone, 'for-each-ref')), before)
            self.assertTrue(clone.is_dir())
