#!/usr/bin/env python3
from __future__ import annotations
import argparse, contextlib, json, os, random, shutil, subprocess, sys, time, traceback
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import clonegrown as cws
from clonegrown.state import summary_ref

ROOT=Path(os.environ.get('CWS_FUZZ_ROOT','/tmp/cws-final-state-machine-fuzz'))

def run(cmd,cwd=None,check=True):
    p=subprocess.run([str(x) for x in cmd],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if check and p.returncode:
        raise RuntimeError(f"command failed {cmd}: {p.stdout}\n{p.stderr}")
    return p

def git(repo,*args,check=True): return run(['git',*args],repo,check)

def setup(seed:int):
    b=ROOT/f'seed-{seed}'; shutil.rmtree(b,ignore_errors=True); b.mkdir(parents=True)
    origin=b/'origin.git'; git(b,'init','--bare',origin); c=b/'canonical'; git(b,'clone',origin,c)
    git(c,'config','user.name','Canonical'); git(c,'config','user.email','canonical@example.invalid')
    git(c,'config','fuzz.sentinel','canonical')
    (c/'README.md').write_text('base\n'); git(c,'add','.'); git(c,'commit','-m','init'); git(c,'branch','-M','main'); git(c,'push','-u','origin','main')
    w=b/'workspace'; cws.init_workspace(c,w)
    return b,c,w,str(origin)

def metas(w:Path):
    out={}
    for p in (w/'.cws/workers').glob('*.json'):
        if not p.stem.isdigit(): continue
        try: out[int(p.stem)]=json.loads(p.read_text())
        except Exception: pass
    return out

def commit(repo:Path,label:str,step:int):
    p=repo/'fuzz'/f'{step}.txt'; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(label+'\n')
    git(repo,'add',str(p.relative_to(repo))); git(repo,'commit','-m',label); return git(repo,'rev-parse','HEAD').stdout.strip()

def clean(repo:Path):
    git(repo,'reset','--hard','HEAD'); git(repo,'clean','-fd')

def invariant(c:Path,w:Path,origin_url:str,full=False):
    if full: git(c,'fsck','--full')
    assert git(c,'config','fuzz.sentinel').stdout.strip()=='canonical'
    assert git(c,'remote','get-url','origin').stdout.strip()==origin_url
    assert 'refs/heads/agent/' not in git(c,'show-ref','--heads').stdout
    st=json.loads((w/'.cws/state.json').read_text())
    for wid,m in metas(w).items():
        assert m['id']==wid
        assert m['workspace_id']==st['workspace_id']
        expected=w/str(wid)/st['repo_name']; assert Path(m['path'])==expected
        status=m['status']; repo=expected
        if status=='ready':
            assert repo.is_dir(); assert (repo/'.git').is_dir()
            marker=json.loads((repo/'.git'/'cws-worker.json').read_text())
            assert marker['worker_id']==wid
            assert marker['workspace_id']==st['workspace_id']
            assert marker['worker_token']==m['worker_token']
            assert git(repo,'show-ref','--verify',f"refs/heads/{m['branch']}").returncode==0
        elif status=='collected':
            ref=m['result_ref']; assert git(c,'rev-parse',ref).stdout.strip()==m['result_sha']
            assert git(c,'rev-parse',summary_ref(st,wid)).stdout.strip()==m['result_sha']
        elif status in ('discarded','abandoned'):
            assert not repo.parent.exists()
    return True

def one(seed:int,steps:int=100,strong_rate:float=.08):
    rng=random.Random(seed); b,c,w,origin=setup(seed); events=[]; counts={}
    def record(op,*detail):
        counts[op]=counts.get(op,0)+1; events.append([len(events),op,*detail])
    try:
        for step in range(steps):
            ms=metas(w)
            ready=[i for i,m in ms.items() if m['status']=='ready']
            collected=[i for i,m in ms.items() if m['status']=='collected']
            op=rng.choices(
                ['spawn','commit','dirty','collect','discard','abandon','retry','mismatch','advance','mutate','recover','summary_loss','post_collect_change'],
                [14,13,5,13,9,6,8,4,7,8,7,3,3]
            )[0]
            if op=='spawn' or (not ready and not collected and op in ('commit','dirty','collect','discard','abandon','mutate','post_collect_change')):
                req=f'{seed}-{step}-{rng.randrange(1<<40)}'; task=rng.choice(['normal','unicode Ω λ','../../escape;echo nope','x'*100]); strong=rng.random()<strong_rate
                m=cws.spawn(w,'main',task,strong=strong,request_id=req); record('spawn',m['id'],strong)
            elif op=='commit' and ready:
                wid=rng.choice(ready); repo=Path(ms[wid]['path']); clean(repo); sha=commit(repo,f'commit-{seed}-{step}',step); record('commit',wid,sha)
            elif op=='dirty' and ready:
                wid=rng.choice(ready); repo=Path(ms[wid]['path']); (repo/f'DIRTY-{step}').write_text('dirty'); record('dirty',wid)
            elif op=='collect' and ready:
                wid=rng.choice(ready); repo=Path(ms[wid]['path']); dirty=bool(git(repo,'status','--porcelain').stdout.strip())
                try:
                    cws.collect(w,wid)
                    assert not dirty
                    record('collect',wid)
                except cws.CWSError:
                    assert dirty
                    clean(repo); record('collect_refused_dirty',wid)
            elif op=='discard' and collected:
                wid=rng.choice(collected); repo=Path(ms[wid]['path']); changed=False
                if repo.exists():
                    changed=bool(git(repo,'status','--porcelain').stdout.strip())
                    bp=git(repo,'rev-parse','--verify',f"refs/heads/{ms[wid]['branch']}",check=False)
                    changed=changed or bp.returncode!=0 or bp.stdout.strip()!=ms[wid]['result_sha']
                try:
                    cws.discard(w,wid)
                    assert not changed
                    record('discard',wid)
                except cws.CWSError:
                    assert changed
                    record('discard_refused_changed',wid)
            elif op=='abandon' and (ready or collected):
                wid=rng.choice(ready+collected); m=ms[wid]; repo=Path(m['path']); changed=False
                if m['status']=='collected' and repo.exists():
                    changed=bool(git(repo,'status','--porcelain').stdout.strip())
                    bp=git(repo,'rev-parse','--verify',f"refs/heads/{m['branch']}",check=False)
                    changed=changed or bp.returncode!=0 or bp.stdout.strip()!=m['result_sha']
                try:
                    cws.discard(w,wid,abandon=True); assert not changed; record('abandon',wid)
                except cws.CWSError:
                    assert changed; record('abandon_refused_changed',wid)
                    if rng.random()<0.5:
                        cws.discard(w,wid,abandon=True,force=True); record('abandon_forced',wid)
            elif op=='retry' and ms:
                m=rng.choice(list(ms.values()))
                try:
                    got=cws.spawn(w,m['base'],m['task'],strong=bool(m['strong']),request_id=m.get('request_id'))
                    if m['status'] in ('spawn_failed','abandoned'):
                        assert got['id']!=m['id'] and got['id']>m['id']; record('retry_reallocated',m['id'],got['id'])
                    else:
                        assert got['id']==m['id']; record('retry',m['id'])
                except cws.CWSError:
                    # Broken/partial states are allowed to require recovery; no silent aliasing is allowed.
                    assert m['status'] in ('broken','collecting','discarding'); record('retry_refused',m['id'])
            elif op=='mismatch' and ms:
                m=rng.choice([x for x in ms.values() if x.get('request_id')] or list(ms.values()))
                if m.get('request_id'):
                    try: cws.spawn(w,m['base'],m['task']+'-different',strong=bool(m['strong']),request_id=m['request_id']); raise AssertionError('mismatched request accepted')
                    except cws.CWSError: record('mismatch_refused',m['id'])
            elif op=='advance':
                p=c/f'canon-{step}.txt'; p.write_text(str(step)); git(c,'add',p.name); git(c,'commit','-m',f'canon {step}'); record('advance')
            elif op=='mutate' and ready:
                wid=rng.choice(ready); repo=Path(ms[wid]['path']); choice=rng.choice(['config','remote','stash','reset'])
                if choice=='config': git(repo,'config','fuzz.sentinel','worker')
                elif choice=='remote' and 'origin' in git(repo,'remote').stdout.split(): git(repo,'remote','remove','origin')
                elif choice=='stash':
                    (repo/'scratch').write_text('x'); git(repo,'add','scratch'); git(repo,'stash','push','-m','w'); git(repo,'stash','clear')
                else: clean(repo)
                record('mutate',wid,choice)
            elif op=='recover':
                cws.recover(w); record('recover')
            elif op=='summary_loss' and collected:
                wid=rng.choice(collected); st=json.loads((w/'.cws/state.json').read_text()); sref=summary_ref(st,wid); git(c,'update-ref','-d',sref); cws.recover(w); assert git(c,'rev-parse',sref).stdout.strip()==ms[wid]['result_sha']; record('summary_repair',wid)
            elif op=='post_collect_change' and collected:
                wid=rng.choice(collected); repo=Path(ms[wid]['path'])
                if repo.exists():
                    clean(repo); commit(repo,f'post-collected-{seed}-{step}',step)
                    try: cws.discard(w,wid); raise AssertionError('discard accepted post-collection commit')
                    except cws.CWSError: record('post_collect_guard',wid)
            else:
                cws.recover(w); record('recover_fallback')
            if step%10==0: invariant(c,w,origin,full=True)
        invariant(c,w,origin,full=True)
        result={'seed':seed,'steps':steps,'ok':True,'events':len(events),'workers':len(metas(w)),'counts':counts}
        shutil.rmtree(b,ignore_errors=True)
        return result
    except Exception as e:
        return {'seed':seed,'steps':steps,'ok':False,'error':f'{type(e).__name__}: {e}','step':locals().get('step'),'op':locals().get('op'),'traceback':traceback.format_exc(),'events':events,'root':str(b),'counts':counts}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--start',type=int,default=0); ap.add_argument('--seeds',type=int,default=10); ap.add_argument('--steps',type=int,default=100); ap.add_argument('--output',required=True); a=ap.parse_args()
    ROOT.mkdir(parents=True,exist_ok=True); rows=[]; t=time.perf_counter()
    for seed in range(a.start,a.start+a.seeds):
        r=one(seed,a.steps); rows.append(r); print(('PASS' if r['ok'] else 'FAIL'),seed,json.dumps(r,sort_keys=True),flush=True)
        if not r['ok']: break
    out={'start':a.start,'requested_seeds':a.seeds,'steps_per_seed':a.steps,'passed':sum(x['ok'] for x in rows),'failed':sum(not x['ok'] for x in rows),'seconds':time.perf_counter()-t,'results':rows}
    Path(a.output).write_text(json.dumps(out,indent=2)+'\n'); return 1 if out['failed'] else 0
if __name__=='__main__': sys.exit(main())
