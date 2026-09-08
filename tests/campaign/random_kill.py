#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from campaign_record import run, GIT_BIN, campaign_environment, random_kill_replay, write_json_atomic
HERE = Path(__file__).resolve().parent
CWS = HERE / 'legacy_cli.py'
WORKTREE = os.environ.get('CWS_SUITE_MODE') == 'worktree'
WORKER_FLAGS = ['--worktree'] if WORKTREE else ['--fast']
STRONG_WORKER_FLAGS = ['--worktree'] if WORKTREE else []


def git(r, *arguments, check=True):
    return run([GIT_BIN, *arguments], r, check)


def clonegrown(*arguments, check=True):
    return run([sys.executable, CWS, *arguments], check=check, timeout=180)


def make_case(tag, large_mb=12):
    case_root = Path(tempfile.mkdtemp(prefix=f'cws-random-kill-{tag}-'))
    origin = case_root / 'origin.git'
    git(case_root, 'init', '--bare', origin)
    canonical = case_root / 'canon'
    git(case_root, 'clone', origin, canonical)
    git(canonical, 'config', 'user.name', 'U')
    git(canonical, 'config', 'user.email', 'u@e')
    (canonical / 'src').mkdir()
    (canonical / 'src/a').write_text('a\n')
    (canonical / '.gitignore').write_text('build/\n')
    # Incompressible data makes strong local cloning and fetch genuinely nontrivial.
    (canonical / 'payload.bin').write_bytes(os.urandom(large_mb*1024*1024))
    git(canonical, 'add', '.')
    git(canonical, 'commit', '-m', 'base')
    git(canonical, 'branch', '-M', 'main')
    git(canonical, 'push', '-u', 'origin', 'main')
    git(canonical, 'gc', '--aggressive', '--prune=now')
    workspace = case_root / 'ws'
    clonegrown('init', canonical, workspace)
    return case_root, canonical, workspace


def json_result(p):
    return json.loads(p.stdout)


def meta(workspace, i):
    return json.loads((workspace / '.cws/workers' / f'{i}.json').read_text())


def state(workspace):
    return json.loads((workspace / '.cws/state.json').read_text())


def start_and_kill(args, delay):
    p = subprocess.Popen([sys.executable, str(CWS), *map(str, args)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    time.sleep(delay)
    killed = False
    if p.poll() is None:
        try:
            os.killpg(p.pid, signal.SIGKILL)
            killed = True
        except ProcessLookupError:
            pass
    out, err = p.communicate(timeout=10)
    result = {
        'rc': p.returncode,
        'killed': killed,
        'stdout': out[-400: ],
        'stderr': err[-400: ],
    }
    if not killed or p.returncode != -signal.SIGKILL:
        raise RuntimeError(f'random-kill target was not interrupted: killed={killed}, rc={p.returncode}')
    return result


def spawn_case(seed):
    rng = random.Random(seed)
    case_root, canonical, workspace = make_case(f'spawn-{seed}', large_mb=24)
    delay = rng.uniform(.005, .04)
    req = f'kill-{seed}'
    proc = start_and_kill(['spawn', workspace, '--task', req, '--base', 'main', '--request-id', req, *STRONG_WORKER_FLAGS], delay)
    reports = json_result(clonegrown('recover', workspace))
    ready = json_result(clonegrown('spawn', workspace, '--task', req, '--base', 'main', '--request-id', req, *STRONG_WORKER_FLAGS))
    r = Path(ready['path'])
    assert ready['status'] == 'ready'
    assert git(r, 'rev-parse', 'HEAD').stdout.strip() == ready['base_sha']
    git(canonical, 'fsck', '--full')
    clonegrown('release', workspace, str(ready['id']))
    clonegrown('discard', workspace, str(ready['id']), '--abandon')
    row = {
        'mode': 'spawn',
        'seed': seed,
        'delay': delay,
        'process': proc,
        'reports': reports,
        'ready_id': ready['id'],
        'ok': True,
    }
    shutil.rmtree(case_root, ignore_errors=True)
    return row


def collect_case(seed):
    rng = random.Random(seed)
    case_root, canonical, workspace = make_case(f'collect-{seed}', large_mb=4)
    worker = json_result(clonegrown('spawn', workspace, '--task', 'collect', '--request-id', f'c-{seed}', *WORKER_FLAGS))
    r = Path(worker['path'])
    (r / f'new-{seed}.bin').write_bytes(os.urandom(8*1024*1024))
    git(r, 'add', '.')
    git(r, 'commit', '-m', 'large result')
    sha = git(r, 'rev-parse', 'HEAD').stdout.strip()
    delay = rng.uniform(.005, .05)
    proc = start_and_kill(['collect', workspace, str(worker['id'])], delay)
    reports = json_result(clonegrown('recover', workspace))
    mm = meta(workspace, worker['id'])
    if mm['status'] == 'ready':
        mm = json_result(clonegrown('collect', workspace, str(worker['id'])))
    assert mm['status'] == 'collected' and mm['result_sha'] == sha
    workspace_state = state(workspace)
    ref = f"refs/cws/{workspace_state['workspace_id']}/workers/{worker['id']}/result"
    assert git(canonical, 'rev-parse', ref).stdout.strip() == sha
    git(canonical, 'fsck', '--full')
    clonegrown('release', workspace, str(worker['id']))
    clonegrown('discard', workspace, str(worker['id']))
    row = {
        'mode': 'collect',
        'seed': seed,
        'delay': delay,
        'process': proc,
        'reports': reports,
        'sha': sha,
        'ok': True,
    }
    shutil.rmtree(case_root, ignore_errors=True)
    return row


def discard_case(seed):
    rng = random.Random(seed)
    case_root, canonical, workspace = make_case(f'discard-{seed}', large_mb=2)
    worker = json_result(clonegrown('spawn', workspace, '--task', 'discard', '--request-id', f'd-{seed}', *WORKER_FLAGS))
    r = Path(worker['path'])
    (r / 'x').write_text('x')
    git(r, 'add', 'x')
    git(r, 'commit', '-m', 'result')
    sha = git(r, 'rev-parse', 'HEAD').stdout.strip()
    mm = json_result(clonegrown('collect', workspace, str(worker['id'])))
    build = r / 'build'
    build.mkdir()
    for i in range(3500):
        (build / f'{i:05d}.tmp').write_text('x'*256)
    clonegrown('release', workspace, str(worker['id']))
    delay = rng.uniform(.005, .035)
    proc = start_and_kill(['discard', workspace, str(worker['id']), '--discard-ignored'], delay)
    reports = json_result(clonegrown('recover', workspace))
    mm = meta(workspace, worker['id'])
    if Path(worker['path']).exists():
        mm = json_result(clonegrown('discard', workspace, str(worker['id']), '--discard-ignored'))
    assert mm['status'] == 'discarded' and not Path(worker['path']).exists()
    workspace_state = state(workspace)
    ref = f"refs/cws/{workspace_state['workspace_id']}/workers/{worker['id']}/result"
    assert git(canonical, 'rev-parse', ref).stdout.strip() == sha
    git(canonical, 'fsck', '--full')
    row = {
        'mode': 'discard',
        'seed': seed,
        'delay': delay,
        'process': proc,
        'reports': reports,
        'sha': sha,
        'ok': True,
    }
    shutil.rmtree(case_root, ignore_errors=True)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['spawn', 'collect', 'discard'])
    parser.add_argument('--start', type=int, default=0)
    parser.add_argument('--count', type=int, default=1)
    parser.add_argument('--output', required=True)
    arguments = parser.parse_args()
    if arguments.count < 1:
        parser.error('--count must be positive')
    worker = 'worktree' if WORKTREE else 'clone'
    environment = campaign_environment()
    started = time.perf_counter()
    rows = [{
        'mode': arguments.mode,
        'seed': seed,
        'ok': None,
        'status': 'pending',
        'replay_command': random_kill_replay(worker, arguments.mode, seed),
    } for seed in range(arguments.start, arguments.start+arguments.count)]
    def payload():
        return {
            'schema_version': 1,
            'campaign': 'random-kill',
            'mode': arguments.mode,
            'worker': worker,
            'start': arguments.start,
            'count': arguments.count,
            'environment': environment,
            'executed': sum(r['ok'] is not None for r in rows),
            'pending': sum(r['ok'] is None for r in rows),
            'passed': sum(r['ok'] is True for r in rows),
            'failed': sum(r['ok'] is False for r in rows),
            'seconds': time.perf_counter()-started,
            'results': rows,
        }
    write_json_atomic(arguments.output, payload())
    fn = {'spawn': spawn_case, 'collect': collect_case, 'discard': discard_case}[arguments.mode]
    for index, seed in enumerate(range(arguments.start, arguments.start+arguments.count)):
        t = time.perf_counter()
        try:
            row = fn(seed)
            row['seconds'] = time.perf_counter()-t
            row['status'] = 'passed'
        except Exception as e:
            row = {
                'mode': arguments.mode,
                'seed': seed,
                'ok': False,
                'status': 'failed',
                'error': repr(e),
                'seconds': time.perf_counter()-t,
            }
        row['replay_command'] = random_kill_replay('worktree' if WORKTREE else 'clone', arguments.mode, seed)
        rows[index] = row
        write_json_atomic(arguments.output, payload())
        print(('PASS' if row['ok'] else 'FAIL'), json.dumps(row, sort_keys=True), flush=True)
        if not row['ok']:
            break
    return int(any(r['ok'] is False for r in rows))
if __name__ == '__main__':
    raise SystemExit(main())
