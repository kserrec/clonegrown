#!/usr/bin/env python3
from __future__ import annotations
import argparse, concurrent.futures as cf, hashlib, json, os, random, shutil, signal, subprocess, sys, time
from pathlib import Path
from typing import Callable, Any

HERE=Path(__file__).resolve().parent
CWS=HERE.parent/'clonegrown.py'
ROOT=Path(os.environ.get('CWS_TEST_ROOT','/tmp/cws-v2-hardening-suite'))
OUT=Path(os.environ.get('CWS_RESULTS_PATH',str(HERE/'hardening-results.json')))


def run(cmd,cwd=None,check=True,env=None,timeout=45):
    e=os.environ.copy()
    if env: e.update({str(k):str(v) for k,v in env.items()})
    p=subprocess.run([str(x) for x in cmd],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=e,timeout=timeout)
    if check and p.returncode:
        raise AssertionError(f"command failed rc={p.returncode}: {cmd}\nout={p.stdout}\nerr={p.stderr}")
    return p

def git(repo,*args,check=True,env=None,timeout=30): return run(['/usr/bin/git',*args],cwd=repo,check=check,env=env,timeout=timeout)
def cws(*args,check=True,env=None,timeout=90): return run(['python3',CWS,*args],check=check,env=env,timeout=timeout)
def jload(p): return json.loads(p.stdout)
def meta(ws,wid): return json.loads((ws/'.cws'/'workers'/f'{wid}.json').read_text())
def state(ws): return json.loads((ws/'.cws'/'state.json').read_text())

def mkcase(name,origin=False,object_format=None,ref_format=None):
    b=ROOT/name; shutil.rmtree(b,ignore_errors=True); b.mkdir(parents=True)
    c=b/'canon'
    args=['init','-b','main']
    if object_format: args += [f'--object-format={object_format}']
    if ref_format: args += [f'--ref-format={ref_format}']
    git(b,*args,c)
    git(c,'config','user.name','Canonical User'); git(c,'config','user.email','canonical@example.invalid')
    (c/'README.md').write_text('base\n'); (c/'src').mkdir(); (c/'src'/'a.txt').write_text('a\n')
    git(c,'add','.'); git(c,'commit','-m','init')
    bare=None
    if origin:
        bare=b/'origin.git'; git(b,'init','--bare',bare); git(c,'remote','add','origin',bare); git(c,'push','-u','origin','main')
    w=b/'ws'; cws('init',c,w)
    return b,c,w,bare

def spawn(ws,task='task',request=None,base='main',strong=False,env=None,check=True):
    args=['spawn',ws,'--task',task,'--base',base]
    if request is not None: args += ['--request-id',request]
    if not strong: args += ['--fast']
    p=cws(*args,env=env,check=check,timeout=120)
    return jload(p) if p.returncode==0 else p

def commit(repo,msg='work',file='work.txt'):
    p=repo/file; p.parent.mkdir(parents=True,exist_ok=True); p.write_text((p.read_text() if p.exists() else '')+msg+'\n')
    git(repo,'add',file); git(repo,'commit','-m',msg); return git(repo,'rev-parse','HEAD').stdout.strip()

def assert_true(x,msg='assertion failed'):
    if not x: raise AssertionError(msg)

def result(**kw): return kw

# ----- Core integrity -----
def t_exact_base_dirty():
    b,c,w,_=mkcase('exact-base'); main=git(c,'rev-parse','main').stdout.strip(); git(c,'switch','-c','accidental'); commit(c,'acc','acc.txt'); (c/'README.md').write_text('DIRTY')
    m=spawn(w,request='r'); r=Path(m['path'])
    assert_true(git(r,'rev-parse','HEAD').stdout.strip()==main); assert_true((r/'README.md').read_text()=='base\n'); assert_true(not (r/'acc.txt').exists())
    return result(base=main)

def t_request_parameter_mismatch():
    b,c,w,_=mkcase('request-mismatch'); first=spawn(w,task='first',request='same'); commit(c,'advance','advance')
    p=cws('spawn',w,'--task','different','--base','main','--request-id','same','--fast',check=False)
    assert_true(p.returncode!=0 and 'reused with different' in p.stderr); return result(worker=first['id'])

def t_detached_head_refused():
    b,c,w,_=mkcase('detached'); m=spawn(w,request='r'); r=Path(m['path']); git(r,'checkout','--detach'); lost=commit(r,'detached')
    p=cws('collect',w,str(m['id']),check=False); assert_true(p.returncode!=0 and 'detached' in p.stderr)
    assert_true(git(c,'cat-file','-e',lost,check=False).returncode!=0); return result(detached=lost)

def t_post_collect_drift_guard():
    b,c,w,_=mkcase('post-collect'); m=spawn(w,request='r'); r=Path(m['path']); a=commit(r,'A'); cws('collect',w,str(m['id'])); bsha=commit(r,'B')
    p=cws('discard',w,str(m['id']),check=False); assert_true(p.returncode!=0 and r.exists())
    p2=cws('collect',w,str(m['id']),check=False); assert_true(p2.returncode!=0 and 'changed after collection' in p2.stderr)
    return result(collected=a,newer=bsha)

def t_worker_replacement_guard():
    b,c,w,_=mkcase('worker-replace'); m=spawn(w,request='r'); r=Path(m['path']); shutil.rmtree(r); git(r.parent,'init','-b',m['branch'],r); git(r,'config','user.name','X'); git(r,'config','user.email','x@e'); (r/'x').write_text('x'); git(r,'add','.'); git(r,'commit','-m','replacement')
    p=cws('collect',w,str(m['id']),check=False); assert_true(p.returncode!=0); return result(rc=p.returncode,error=p.stderr.strip()[-200:])

def t_canonical_replacement_guard():
    b,c,w,_=mkcase('canonical-replace'); c.rename(b/'old'); git(b,'init','-b','main',c); git(c,'config','user.name','X'); git(c,'config','user.email','x@e'); (c/'x').write_text('x'); git(c,'add','.'); git(c,'commit','-m','other')
    p=cws('spawn',w,'--task','x','--base','main','--request-id','x','--fast',check=False); assert_true(p.returncode!=0); return result(rc=p.returncode,error=p.stderr.strip()[-200:])

def t_unrelated_history_policy():
    b,c,w,_=mkcase('unrelated'); m=spawn(w,request='r'); r=Path(m['path']); git(r,'checkout','--orphan','tmp'); git(r,'rm','-rf','.'); (r/'new').write_text('new'); git(r,'add','.'); git(r,'commit','-m','orphan'); sha=git(r,'rev-parse','HEAD').stdout.strip(); git(r,'branch','-f',m['branch'],sha); git(r,'checkout',m['branch']); git(r,'branch','-D','tmp')
    p=cws('collect',w,str(m['id']),check=False); assert_true(p.returncode!=0 and 'does not descend' in p.stderr)
    ok=cws('collect',w,str(m['id']),'--allow-rewrite'); got=jload(ok); assert_true(got['result_sha']==sha); return result(orphan=sha)

def t_workspace_nesting_rules():
    b=ROOT/'nesting'; shutil.rmtree(b,ignore_errors=True); b.mkdir(parents=True); c=b/'canon'; git(b,'init','-b','main',c); git(c,'config','user.name','U'); git(c,'config','user.email','u@e'); (c/'a').write_text('a'); git(c,'add','.'); git(c,'commit','-m','i')
    p=cws('init',c,c/'.dev',check=False); assert_true(p.returncode!=0)
    umbrella=b/'umbrella'; slot=umbrella/'1'/'canon'; slot.parent.mkdir(parents=True); shutil.move(c,slot); st=jload(cws('init',slot,umbrella)); m=spawn(umbrella,request='nested')
    assert_true(m['id']==2 and Path(m['path']).parts[-2]=='2'); return result(first_worker=m['id'])

def t_git_environment_sanitized():
    b,c,w,_=mkcase('env'); hooks=b/'hooks'; hooks.mkdir(); marker=b/'ran'; h=hooks/'post-checkout'; h.write_text(f'#!/bin/sh\ntouch {marker}\n'); h.chmod(0o755)
    env={'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'core.hooksPath','GIT_CONFIG_VALUE_0':str(hooks)}; m=spawn(w,request='e',env=env)
    assert_true(not marker.exists()); return result(worker=m['id'])

def t_hostile_task_and_unicode_paths():
    b=ROOT/'weird path Ω'; shutil.rmtree(b,ignore_errors=True); b.mkdir(parents=True); c=b/'repo ü'; git(b,'init','-b','main',c); git(c,'config','user.name','U'); git(c,'config','user.email','u@e'); (c/'a').write_text('a'); git(c,'add','.'); git(c,'commit','-m','i'); w=b/'workspace λ'; cws('init',c,w)
    marker=Path('/tmp/CWS_V2_PWN'); marker.unlink(missing_ok=True); m=spawn(w,task='../../x; touch /tmp/CWS_V2_PWN $(oops) Ω',request='x'); assert_true(not marker.exists()); assert_true('..' not in m['branch'] and ' ' not in m['branch'] and ';' not in m['branch']); return result(branch=m['branch'])

def t_remote_semantics_and_push_guard():
    b,c,w,origin=mkcase('remotes',origin=True); up=b/'up.git'; push=b/'push.git'; collision=b/'collision.git'; [git(b,'init','--bare',x) for x in (up,push,collision)]; git(c,'remote','add','upstream',up); git(c,'remote','set-url','--add','--push','upstream',push); git(c,'remote','add','cws-source',collision)
    m=spawn(w,request='r'); r=Path(m['path']); assert_true(m['source_remote']=='cws-source-2');
    for name in ('origin','upstream','cws-source'): assert_true(git(r,'remote','get-url',name).stdout.strip()==git(c,'remote','get-url',name).stdout.strip())
    p=git(r,'push',m['source_remote'],'HEAD:refs/heads/nope',check=False); assert_true(p.returncode!=0 and git(c,'show-ref','--verify','refs/heads/nope',check=False).returncode!=0)
    commit(r,'push-real'); git(r,'push','origin','HEAD:refs/heads/worker'); assert_true(git(origin,'show-ref','--verify','refs/heads/worker').returncode==0)
    return result(source_remote=m['source_remote'])

def t_config_and_stash_isolation():
    b,c,w,_=mkcase('config'); git(c,'config','agent.sentinel','canonical'); (c/'stash').write_text('s'); git(c,'add','stash'); git(c,'stash','push','-m','canon'); before=git(c,'stash','list').stdout
    m=spawn(w,request='r'); r=Path(m['path']); assert_true(git(r,'config','agent.sentinel').stdout.strip()=='canonical'); git(r,'config','agent.sentinel','worker'); git(r,'stash','clear'); assert_true(git(c,'config','agent.sentinel').stdout.strip()=='canonical' and git(c,'stash','list').stdout==before); return result(stash_lines=len(before.splitlines()))

def t_private_hook_boundary():
    b,c,w,_=mkcase('hooks'); hp=c/'.git'/'hooks'/'pre-commit'; hp.write_text('#!/bin/sh\nexit 31\n'); hp.chmod(0o755); m=spawn(w,request='r'); r=Path(m['path']); wh=r/'.git'/'hooks'/'pre-commit'; assert_true(not wh.exists()); assert_true(any('private .git hooks' in x for x in m['compatibility_warnings'])); return result(warnings=m['compatibility_warnings'])

def t_dirty_and_operation_collect_refusal():
    b,c,w,_=mkcase('dirty-op'); m=spawn(w,request='r'); r=Path(m['path']); (r/'dirty').write_text('x'); p=cws('collect',w,str(m['id']),check=False); assert_true(p.returncode!=0); (r/'dirty').unlink(); (r/'.git'/'MERGE_HEAD').write_text(m['base_sha']+'\n'); p=cws('collect',w,str(m['id']),check=False); assert_true(p.returncode!=0 and 'in-progress' in p.stderr); (r/'.git'/'MERGE_HEAD').unlink(); return result()

def t_collect_idempotent():
    b,c,w,_=mkcase('collect-idem'); m=spawn(w,request='r'); r=Path(m['path']); sha=commit(r); a=jload(cws('collect',w,str(m['id']))); b2=jload(cws('collect',w,str(m['id']))); assert_true(a['result_sha']==sha==b2['result_sha']); return result(sha=sha)

def t_collect_concurrent_mutation():
    b,c,w,_=mkcase('collect-race'); m=spawn(w,request='r'); r=Path(m['path']); a=commit(r,'A'); marker=b/'pause'; env={**os.environ,'CWS_PAUSEPOINT':'collect.after_mark','CWS_PAUSE_SECONDS':'1.0','CWS_PAUSE_MARKER':str(marker)}
    p=subprocess.Popen(['python3',str(CWS),'collect',str(w),str(m['id'])],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env); deadline=time.time()+10
    while time.time()<deadline and not marker.exists(): time.sleep(.01)
    assert_true(marker.exists(),'collect did not reach pause'); bsha=commit(r,'B'); out,err=p.communicate(timeout=20); mm=meta(w,m['id']); assert_true(p.returncode!=0 and mm['status']=='ready' and 'result_sha' not in mm); return result(candidate=a,new_head=bsha,stderr=err.strip()[-120:])

def t_status_reports_post_collect_drift():
    b,c,w,_=mkcase('status-drift'); m=spawn(w,request='r'); r=Path(m['path']); commit(r,'A'); cws('collect',w,str(m['id'])); commit(r,'B'); s=jload(cws('status',w)); item=s['workers'][0]; assert_true(item.get('drift')=='changed-after-collection'); return result(drift=item['drift'])

# ----- Concurrency / transaction -----
def t_parallel_spawns_unique():
    b,c,w,_=mkcase('parallel'); t=time.perf_counter(); one=spawn(w,request='single'); single=time.perf_counter()-t
    def f(i): return spawn(w,task=f't{i}',request=f'r{i}')
    t=time.perf_counter();
    with cf.ThreadPoolExecutor(max_workers=8) as ex: ms=list(ex.map(f,range(8)))
    elapsed=time.perf_counter()-t; ids=[m['id'] for m in ms]; assert_true(len(set(ids))==8); ratio=elapsed/max(single,0.001); assert_true(ratio<5.5,f'too serialized ratio={ratio}')
    return result(single_seconds=single,eight_seconds=elapsed,ratio=ratio,ids=ids)

def t_same_request_concurrent():
    b,c,w,_=mkcase('same-request')
    def f(_): return spawn(w,task='same',request='same')
    with cf.ThreadPoolExecutor(max_workers=8) as ex: ms=list(ex.map(f,range(8)))
    ids={m['id'] for m in ms}; assert_true(ids=={1}); assert_true(len(list((w/'.cws'/'workers').glob('*.json')))==1); return result(ids=list(ids))

def t_base_pin_survives_gc():
    b,c,w,_=mkcase('base-pin'); git(c,'checkout','-b','temp'); sha=commit(c,'unique','unique'); git(c,'checkout','main'); marker=b/'pause'; env={**os.environ,'CWS_PAUSEPOINT':'spawn.after_allocated','CWS_PAUSE_SECONDS':'1.0','CWS_PAUSE_MARKER':str(marker)}
    p=subprocess.Popen(['python3',str(CWS),'spawn',str(w),'--task','gc','--base','temp','--request-id','gc','--fast'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env); deadline=time.time()+10
    while time.time()<deadline and not marker.exists(): time.sleep(.01)
    assert_true(marker.exists()); git(c,'branch','-D','temp'); git(c,'reflog','expire','--expire=now','--all'); git(c,'gc','--prune=now'); out,err=p.communicate(timeout=30); assert_true(p.returncode==0,err); m=json.loads(out); assert_true(m['base_sha']==sha and git(Path(m['path']),'rev-parse','HEAD').stdout.strip()==sha); return result(base=sha)

def t_collect_discard_race():
    b,c,w,_=mkcase('collect-discard'); m=spawn(w,request='r'); r=Path(m['path']); sha=commit(r)
    def col(): return cws('collect',w,str(m['id']),check=False)
    def dis(): return cws('discard',w,str(m['id']),check=False)
    with cf.ThreadPoolExecutor(max_workers=2) as ex: a=ex.submit(col); d=ex.submit(dis); pc,pd=a.result(),d.result()
    if pc.returncode!=0: pc=cws('collect',w,str(m['id']),check=False)
    if Path(m['path']).exists(): pd=cws('discard',w,str(m['id']),check=False)
    st=state(w); ref=f"refs/cws/{st['workspace_id']}/workers/{m['id']}/result"; assert_true(git(c,'rev-parse',ref).stdout.strip()==sha); return result(collect_rc=pc.returncode,discard_rc=pd.returncode)

def t_canonical_advance_does_not_move_worker():
    b,c,w,_=mkcase('advance'); old=git(c,'rev-parse','main').stdout.strip(); m=spawn(w,request='old'); new=commit(c,'new','new'); assert_true(git(Path(m['path']),'rev-parse','HEAD').stdout.strip()==old); m2=spawn(w,request='new'); assert_true(m2['base_sha']==new); return result(old=old,new=new)

def t_two_workspaces_ref_isolation():
    b,c,w1,_=mkcase('two-workspaces'); w2=b/'ws2'; cws('init',c,w2); a=spawn(w1,request='a'); b2=spawn(w2,request='b'); ra=Path(a['path']); rb=Path(b2['path']); sa=commit(ra,'A'); sb=commit(rb,'B'); cws('collect',w1,str(a['id'])); cws('collect',w2,str(b2['id'])); s1=state(w1); s2=state(w2); assert_true(s1['workspace_id']!=s2['workspace_id']); assert_true(git(c,'rev-parse',f"refs/cws/{s1['workspace_id']}/workers/1/result").stdout.strip()==sa); assert_true(git(c,'rev-parse',f"refs/cws/{s2['workspace_id']}/workers/1/result").stdout.strip()==sb); return result(workspaces=[s1['workspace_id'],s2['workspace_id']])

def t_worker_gc_concurrency():
    b,c,w,_=mkcase('worker-gc'); ms=[spawn(w,request=f'r{i}') for i in range(8)]
    def gc(m): return git(Path(m['path']),'gc','--prune=now',check=False)
    with cf.ThreadPoolExecutor(max_workers=8) as ex: ps=list(ex.map(gc,ms))
    assert_true(all(p.returncode==0 for p in ps)); assert_true(git(c,'fsck','--full').returncode==0); return result(success=sum(p.returncode==0 for p in ps))

# ----- Crash recovery -----
def t_init_crash_matrix():
    out=[]
    for i,fp in enumerate(('init.after_state','init.after_marker')):
        b=ROOT/f'init-crash-{i}'; shutil.rmtree(b,ignore_errors=True); b.mkdir(parents=True); c=b/'canon'; git(b,'init','-b','main',c); git(c,'config','user.name','U'); git(c,'config','user.email','u@e'); (c/'a').write_text('a'); git(c,'add','.'); git(c,'commit','-m','i'); w=b/'ws'
        p=cws('init',c,w,env={'CWS_FAILPOINT':fp},check=False); assert_true(p.returncode==88); st=jload(cws('init',c,w)); assert_true(st['status']=='ready'); out.append(fp)
    return result(failpoints=out)

def t_spawn_crash_matrix():
    fps=('spawn.after_allocated','spawn.after_clone','spawn.after_checkout','spawn.after_publish','spawn.after_ready'); actions=[]
    for i,fp in enumerate(fps):
        b,c,w,_=mkcase(f'spawn-crash-{i}'); p=cws('spawn',w,'--task','x','--base','main','--request-id','r','--fast',env={'CWS_FAILPOINT':fp},check=False); assert_true(p.returncode==88); rep=jload(cws('recover',w)); mm=meta(w,1)
        if fp in ('spawn.after_publish','spawn.after_ready'): assert_true(mm['status']=='ready')
        else:
            assert_true(mm['status']=='spawn_failed'); m2=spawn(w,task='x',request='r'); assert_true(m2['status']=='ready' and m2['id']>1)
        assert_true(git(c,'fsck','--full').returncode==0); actions.append([fp,mm['status'],rep])
    return result(cases=actions)

def t_collect_crash_matrix():
    fps=('collect.after_mark','collect.before_fetch','collect.after_fetch','collect.after_verify','collect.after_worker_recheck','collect.after_summary','collect.after_metadata'); rows=[]
    for i,fp in enumerate(fps):
        b,c,w,_=mkcase(f'collect-crash-{i}'); m=spawn(w,request='r'); r=Path(m['path']); sha=commit(r); p=cws('collect',w,str(m['id']),env={'CWS_FAILPOINT':fp},check=False); assert_true(p.returncode==88); rep=jload(cws('recover',w)); mm=meta(w,m['id'])
        if mm['status']=='ready': cws('collect',w,str(m['id'])); mm=meta(w,m['id'])
        assert_true(mm['status']=='collected' and mm['result_sha']==sha); rows.append([fp,rep])
    return result(cases=rows)

def t_discard_crash_matrix():
    fps=('discard.after_mark','discard.before_delete','discard.after_delete','discard.after_metadata'); rows=[]
    for i,fp in enumerate(fps):
        b,c,w,_=mkcase(f'discard-crash-{i}'); m=spawn(w,request='r'); r=Path(m['path']); sha=commit(r); cws('collect',w,str(m['id'])); p=cws('discard',w,str(m['id']),env={'CWS_FAILPOINT':fp},check=False); assert_true(p.returncode==88); rep=jload(cws('recover',w)); mm=meta(w,m['id']);
        if mm['status']=='collected': cws('discard',w,str(m['id'])); mm=meta(w,m['id'])
        assert_true(mm['status']=='discarded' and not r.exists()); assert_true(git(c,'cat-file','-e',sha).returncode==0); rows.append([fp,rep])
    return result(cases=rows)

def t_recover_preserves_dirty_ready_worker():
    b,c,w,_=mkcase('recover-dirty'); m=spawn(w,request='r'); r=Path(m['path']); (r/'dirty').write_text('valuable uncommitted'); rep=jload(cws('recover',w)); assert_true(meta(w,m['id'])['status']=='ready' and (r/'dirty').read_text()=='valuable uncommitted'); return result(recovery=rep)

# ----- Git compatibility -----
def object_inodes(repo):
    gd=Path(git(repo,'rev-parse','--git-dir').stdout.strip()); gd=gd if gd.is_absolute() else (repo/gd).resolve(); return {(p.stat().st_dev,p.stat().st_ino):str(p) for p in (gd/'objects').rglob('*') if p.is_file()}

def t_strong_object_isolation():
    b,c,w,_=mkcase('strong'); m=spawn(w,request='r',strong=True); r=Path(m['path']); shared=set(object_inodes(c))&set(object_inodes(r)); assert_true(not shared); return result(shared_inodes=len(shared))

def t_fast_object_sharing_is_explicit():
    b,c,w,_=mkcase('fast-sharing'); m=spawn(w,request='r',strong=False); r=Path(m['path']); shared=set(object_inodes(c))&set(object_inodes(r)); assert_true(len(shared)>0); return result(shared_inodes=len(shared),mode='known tradeoff')

def t_alternates_detached_strong():
    b=ROOT/'alternates'; shutil.rmtree(b,ignore_errors=True); b.mkdir(parents=True); source=b/'source'; git(b,'init','-b','main',source); git(source,'config','user.name','U'); git(source,'config','user.email','u@e'); (source/'a').write_text('a'); git(source,'add','.'); git(source,'commit','-m','i'); c=b/'canon'; run(['/usr/bin/git','clone','--shared',source,c]); git(c,'config','user.name','U'); git(c,'config','user.email','u@e'); w=b/'ws'; cws('init',c,w); m=spawn(w,request='r',strong=True); r=Path(m['path']); alt=r/'.git'/'objects'/'info'/'alternates'; assert_true(not alt.exists()); shutil.rmtree(source); assert_true(git(r,'fsck','--full').returncode==0); return result(detached=m['alternates_detached'])

def t_sha256_repository():
    p=git(ROOT,'init','--object-format=sha256','-b','main',ROOT/'sha256-probe',check=False)
    if p.returncode!=0: return result(skipped='git lacks sha256 support')
    shutil.rmtree(ROOT/'sha256-probe'); b,c,w,_=mkcase('sha256',object_format='sha256'); m=spawn(w,request='r'); r=Path(m['path']); sha=commit(r); got=jload(cws('collect',w,str(m['id']))); assert_true(len(sha)==64 and got['result_sha']==sha); return result(sha_length=len(sha))

def t_reftable_repository():
    probe=ROOT/'reftable-probe'; shutil.rmtree(probe,ignore_errors=True); p=git(ROOT,'init','--ref-format=reftable','-b','main',probe,check=False)
    if p.returncode!=0: return result(skipped='git lacks reftable support')
    shutil.rmtree(probe); b,c,w,_=mkcase('reftable',ref_format='reftable'); m=spawn(w,request='r'); sha=commit(Path(m['path'])); got=jload(cws('collect',w,str(m['id']))); assert_true(got['result_sha']==sha); return result(ref_format='reftable')

def t_shallow_repository():
    b=ROOT/'shallow'; shutil.rmtree(b,ignore_errors=True); b.mkdir(parents=True); bare=b/'up.git'; git(b,'init','--bare',bare); src=b/'src'; git(b,'clone',bare,src); git(src,'config','user.name','U'); git(src,'config','user.email','u@e')
    for i in range(6): (src/'a').write_text(str(i)); git(src,'add','a'); git(src,'commit','-m',f'c{i}')
    git(src,'branch','-M','main'); git(src,'push','-u','origin','main'); c=b/'canon'; run(['/usr/bin/git','clone','--depth','2','--branch','main',f'file://{bare}',c]); git(c,'config','user.name','U'); git(c,'config','user.email','u@e'); w=b/'ws'; cws('init',c,w); m=spawn(w,request='r'); r=Path(m['path']); assert_true(git(r,'rev-parse','HEAD').stdout.strip()==m['base_sha']); return result(worker_shallow=(r/'.git'/'shallow').exists())

def t_sparse_checkout():
    b,c,w,_=mkcase('sparse'); (c/'keep').mkdir(); (c/'drop').mkdir(); (c/'keep'/'k').write_text('k'); (c/'drop'/'d').write_text('d'); git(c,'add','.'); git(c,'commit','-m','tree'); git(c,'sparse-checkout','init','--cone'); git(c,'sparse-checkout','set','keep'); m=spawn(w,request='r'); r=Path(m['path']); assert_true((r/'keep'/'k').exists() and not (r/'drop'/'d').exists()); return result(sparse=m['copied_sparse_checkout'])

def t_submodule_baseline():
    b=ROOT/'submodule'; shutil.rmtree(b,ignore_errors=True); b.mkdir(parents=True); sub=b/'sub'; git(b,'init','-b','main',sub); git(sub,'config','user.name','U'); git(sub,'config','user.email','u@e'); (sub/'s').write_text('s'); git(sub,'add','.'); git(sub,'commit','-m','s'); c=b/'canon'; git(b,'init','-b','main',c); git(c,'config','user.name','U'); git(c,'config','user.email','u@e'); (c/'a').write_text('a'); git(c,'add','.'); git(c,'commit','-m','i'); run(['/usr/bin/git','-c','protocol.file.allow=always','submodule','add',sub,'vendor/sub'],cwd=c); git(c,'commit','-am','sub'); w=b/'ws'; cws('init',c,w); m=spawn(w,request='r'); r=Path(m['path']); assert_true(git(r,'ls-files','-s','vendor/sub').stdout.startswith('160000 ')); assert_true(not (r/'vendor'/'sub'/'s').exists()); return result(note='submodule intentionally uninitialized; bootstrap required')

def t_symlink_and_executable_bits():
    b,c,w,_=mkcase('symlink-exec'); script=c/'run.sh'; script.write_text('#!/bin/sh\n'); script.chmod(0o755); os.symlink('README.md',c/'link'); git(c,'add','.'); git(c,'commit','-m','modes'); m=spawn(w,request='r'); r=Path(m['path']); assert_true((r/'link').is_symlink() and os.readlink(r/'link')=='README.md'); assert_true(os.access(r/'run.sh',os.X_OK)); return result()

def t_detached_canonical_and_no_remote():
    b,c,w,_=mkcase('detached-canon'); sha=git(c,'rev-parse','main').stdout.strip(); git(c,'checkout','--detach',sha); m=spawn(w,request='r'); assert_true(m['base_sha']==sha); rem=git(Path(m['path']),'remote').stdout.split(); assert_true(m['source_remote'] in rem and 'origin' not in rem); return result(remotes=rem)

def t_path_bound_config_warning():
    b,c,w,_=mkcase('path-config'); git(c,'config','agent.path',str(c)+'/tool'); m=spawn(w,request='r'); r=Path(m['path']); assert_true(git(r,'config','agent.path',check=False).returncode!=0); assert_true(any('path-bound' in x for x in m['compatibility_warnings'])); return result(warnings=m['compatibility_warnings'])

def t_info_exclude_copied():
    b,c,w,_=mkcase('info'); (c/'.git'/'info'/'exclude').write_text('local-secret\n'); m=spawn(w,request='r'); r=Path(m['path']); (r/'local-secret').write_text('x'); assert_true(git(r,'status','--porcelain').stdout.strip()==''); return result()

def t_marker_tamper_detection():
    b,c,w,_=mkcase('marker-tamper'); m=spawn(w,request='r'); r=Path(m['path']); wm=r/'.git'/'cws-worker.json'; data=json.loads(wm.read_text()); data['worker_token']='tampered'; wm.write_text(json.dumps(data)); p=cws('collect',w,str(m['id']),check=False); assert_true(p.returncode!=0 and 'marker mismatch' in p.stderr); return result()

def t_canonical_marker_loss_detection():
    b,c,w,_=mkcase('canon-marker-loss'); st=state(w); (c/'.git'/'cws'/f"{st['workspace_id']}.json").unlink(); p=cws('status',w,check=False); assert_true(p.returncode!=0 and 'cannot read metadata' in p.stderr); return result()

# ----- Metadata / boundary red team -----
def t_metadata_path_tamper_guards():
    b,c,w,_=mkcase('meta-path-tamper'); m=spawn(w,request='r'); victim=b/'victim'; victim.mkdir(); (victim/'KEEP').write_text('keep')
    mp=w/'.cws'/'workers'/f"{m['id']}.json"; mm=json.loads(mp.read_text()); mm['path']=str(victim/'fake'); mp.write_text(json.dumps(mm))
    pc=cws('collect',w,str(m['id']),check=False); pd=cws('discard',w,str(m['id']),'--abandon',check=False)
    assert_true(pc.returncode!=0 and pd.returncode!=0); assert_true((victim/'KEEP').read_text()=='keep')
    return result(collect_error=pc.stderr.strip()[-160:],discard_error=pd.stderr.strip()[-160:])

def t_worker_slot_symlink_guard():
    b,c,w,_=mkcase('slot-symlink'); m=spawn(w,request='r'); slot=Path(m['path']).parent; saved=b/'saved'; slot.rename(saved)
    victim=b/'victim'; victim.mkdir(); (victim/'KEEP').write_text('keep'); os.symlink(victim,slot)
    p=cws('discard',w,str(m['id']),'--abandon',check=False)
    assert_true(p.returncode!=0 and (victim/'KEEP').exists()); return result(error=p.stderr.strip()[-160:])

def t_metadata_identity_validation():
    b,c,w,_=mkcase('meta-identity'); m=spawn(w,request='r'); mp=w/'.cws'/'workers'/f"{m['id']}.json"; original=json.loads(mp.read_text())
    outcomes={}
    for key,value in [('id',999),('branch','agent/wrong'),('stage_root',str(b/'elsewhere')),('params_hash','0'*64),('status','quantum')]:
        bad=dict(original); bad[key]=value; mp.write_text(json.dumps(bad)); p=cws('status',w,check=False); outcomes[key]=p.returncode
        assert_true(p.returncode==0, f'status should diagnose {key} without crashing')
        payload=jload(p); assert_true(any(i.get('id')==m['id'] for i in payload['issues']))
    mp.write_text(json.dumps(original)); return result(diagnosed=sorted(outcomes))

def t_recovery_resilience_and_orphans():
    b,c,w,_=mkcase('recover-resilience'); a=spawn(w,request='a'); b2=spawn(w,request='b')
    (w/'.cws'/'workers'/f"{a['id']}.json").write_text('{not json')
    (w/'.cws'/'workers'/'unexpected.json').write_text('{}')
    orphan=w/'999'; orphan.mkdir(); (orphan/'KEEP').write_text('orphan')
    p=cws('recover',w,check=False); assert_true(p.returncode==0,p.stderr); reports=jload(p)
    text=json.dumps(reports); assert_true('corrupt-or-unreadable-metadata' in text); assert_true('unknown-metadata-file' in text); assert_true('orphan-worker-directory' in text)
    assert_true(meta(w,b2['id'])['status']=='ready' and (orphan/'KEEP').exists()); return result(reports=reports)

def t_provisioning_hooks_suppressed_but_preserved():
    b,c,w,_=mkcase('hook-suppression'); hooks=b/'hooks'; hooks.mkdir(); marker=b/'HOOK_RAN'; hook=hooks/'post-checkout'
    hook.write_text(f'#!/bin/sh\necho ran >> "{marker}"\n'); hook.chmod(0o755); git(c,'config','core.hooksPath',str(hooks))
    m=spawn(w,request='r'); r=Path(m['path']); assert_true(not marker.exists(),'helper provisioning executed post-checkout hook')
    git(r,'checkout','-b','agent-manual'); assert_true(marker.exists(),'worker did not preserve configured hook for later agent commands')
    return result(warnings=m['compatibility_warnings'])

def t_remote_tracking_notes_and_replace_refs():
    b,c,w,origin=mkcase('aux-refs',origin=True); base=git(c,'rev-parse','HEAD').stdout.strip()
    git(c,'notes','add','-m','local note',base)
    # Replacement commit with same tree but different message; replace refs affect history interpretation.
    tree=git(c,'show','-s','--format=%T',base).stdout.strip(); replacement=git(c,'commit-tree',tree,'-m','replacement').stdout.strip(); git(c,'replace',base,replacement)
    m=spawn(w,request='r'); r=Path(m['path'])
    assert_true(git(r,'rev-parse','refs/remotes/origin/main').stdout.strip()==base)
    assert_true(git(r,'notes','show',base).stdout.strip()=='local note')
    assert_true(git(r,'rev-parse',f'refs/replace/{base}').stdout.strip()==replacement)
    return result(aux=m['copied_auxiliary_refs'])

def t_normal_failure_rollbacks():
    b,c,w,_=mkcase('ordinary-errors')
    p=cws('spawn',w,'--task','spawn-error','--base','main','--request-id','spawn-error','--fast',env={'CWS_ERRORPOINT':'spawn.after_publish'},check=False)
    assert_true(p.returncode!=0); rep=jload(cws('recover',w)); mm=meta(w,1); assert_true(mm['status']=='ready' and Path(mm['path']).exists())
    sha=commit(Path(mm['path']),'collectable'); p2=cws('collect',w,'1',env={'CWS_ERRORPOINT':'collect.after_fetch'},check=False)
    assert_true(p2.returncode!=0 and meta(w,1)['status']=='ready'); got=jload(cws('collect',w,'1')); assert_true(got['result_sha']==sha)
    return result(recovery=rep,result=sha)

def t_final_path_collision_is_never_deleted():
    b,c,w,_=mkcase('slot-collision'); victim=w/'1'; victim.mkdir(); (victim/'KEEP').write_text('keep')
    p=cws('spawn',w,'--task','collision','--base','main','--request-id','collision','--fast',check=False); assert_true(p.returncode!=0)
    rep=jload(cws('recover',w)); assert_true((victim/'KEEP').exists()); assert_true(meta(w,1)['status']=='broken')
    return result(reports=rep)

def t_branch_rename_and_gitdir_substitution_refused():
    b,c,w,_=mkcase('branch-gitdir'); m=spawn(w,request='r'); r=Path(m['path']); git(r,'branch','-m','renamed')
    p=cws('collect',w,str(m['id']),check=False); assert_true(p.returncode!=0)
    # Restore the expected branch, then redirect .git to a different bare repository.
    git(r,'branch','-m',m['branch']); real=r/'.git-real'; (r/'.git').rename(real); fake=b/'fake.git'; git(b,'init','--bare',fake); os.symlink(fake,r/'.git')
    p2=cws('collect',w,str(m['id']),check=False); assert_true(p2.returncode!=0)
    return result(branch_error=p.stderr.strip()[-120:],gitdir_error=p2.stderr.strip()[-120:])

def t_result_survives_discard_and_gc():
    b,c,w,_=mkcase('result-gc'); m=spawn(w,request='r'); sha=commit(Path(m['path']),'valuable'); got=jload(cws('collect',w,str(m['id']))); cws('discard',w,str(m['id']))
    git(c,'reflog','expire','--expire=now','--all'); git(c,'gc','--prune=now'); assert_true(git(c,'cat-file','-e',f'{sha}^{{commit}}',check=False).returncode==0)
    assert_true(git(c,'rev-parse',got['result_ref']).stdout.strip()==sha); return result(ref=got['result_ref'],sha=sha)

def t_workspace_state_path_tamper_rejected():
    b,c,w,_=mkcase('state-path-tamper'); m=spawn(w,request='r'); victim=b/'victim'; victim.mkdir(); (victim/'KEEP').write_text('keep')
    sp=w/'.cws'/'state.json'; st=json.loads(sp.read_text()); st['repo_name']=str(victim/'repo'); sp.write_text(json.dumps(st))
    mp=w/'.cws'/'workers'/f"{m['id']}.json"; mm=json.loads(mp.read_text()); mm['path']=str(victim/'repo'); mp.write_text(json.dumps(mm))
    p=cws('recover',w,check=False); assert_true(p.returncode!=0); assert_true((victim/'KEEP').exists())
    return result(error=p.stderr.strip()[-200:])

def t_control_and_lock_symlink_rejected():
    b,c,w,_=mkcase('control-symlink'); real=b/'control-real'; (w/'.cws').rename(real); os.symlink(real,w/'.cws')
    p=cws('spawn',w,'--task','x','--base','main','--request-id','x','--fast',check=False); assert_true(p.returncode!=0)
    # Restore control directory, then attack the lock itself.
    (w/'.cws').unlink(); real.rename(w/'.cws'); victim=b/'LOCK_VICTIM'; victim.write_text('keep'); lock=w/'.cws'/'lock'; lock.unlink(missing_ok=True); os.symlink(victim,lock)
    p2=cws('status',w,check=False); assert_true(p2.returncode!=0 and victim.read_text()=='keep')
    return result(control_error=p.stderr.strip()[-120:],lock_error=p2.stderr.strip()[-120:])

def t_late_commit_after_crashed_discard_survives():
    b,c,w,_=mkcase('late-discard'); m=spawn(w,request='r'); r=Path(m['path']); first=commit(r,'first')
    cws('collect',w,str(m['id'])); p=cws('discard',w,str(m['id']),env={'CWS_FAILPOINT':'discard.before_delete'},check=False); assert_true(p.returncode==88)
    late=commit(r,'late'); reports=jload(cws('recover',w)); assert_true(r.exists()); mm=meta(w,m['id']); assert_true(mm['status']=='collected')
    s=jload(cws('status',w)); assert_true(s['workers'][0].get('drift')=='changed-after-collection')
    return result(first=first,late=late,reports=reports)

TESTS: dict[str, tuple[str, Callable[[],dict[str,Any]]]] = {
    # group, function
    'exact_base_dirty':('core',t_exact_base_dirty),'request_parameter_mismatch':('core',t_request_parameter_mismatch),'detached_head_refused':('core',t_detached_head_refused),'post_collect_drift_guard':('core',t_post_collect_drift_guard),'worker_replacement_guard':('core',t_worker_replacement_guard),'canonical_replacement_guard':('core',t_canonical_replacement_guard),'unrelated_history_policy':('core',t_unrelated_history_policy),'workspace_nesting_rules':('core',t_workspace_nesting_rules),'git_environment_sanitized':('core',t_git_environment_sanitized),'hostile_task_unicode':('core',t_hostile_task_and_unicode_paths),'remote_semantics_push_guard':('core',t_remote_semantics_and_push_guard),'config_stash_isolation':('core',t_config_and_stash_isolation),'private_hook_boundary':('core',t_private_hook_boundary),'dirty_operation_refusal':('core',t_dirty_and_operation_collect_refusal),'collect_idempotent':('core',t_collect_idempotent),'collect_concurrent_mutation':('core',t_collect_concurrent_mutation),'status_drift':('core',t_status_reports_post_collect_drift),
    'parallel_spawns_unique':('concurrency',t_parallel_spawns_unique),'same_request_concurrent':('concurrency',t_same_request_concurrent),'base_pin_survives_gc':('concurrency',t_base_pin_survives_gc),'collect_discard_race':('concurrency',t_collect_discard_race),'canonical_advance':('concurrency',t_canonical_advance_does_not_move_worker),'two_workspaces_refs':('concurrency',t_two_workspaces_ref_isolation),'worker_gc_concurrency':('concurrency',t_worker_gc_concurrency),
    'init_crash_matrix':('crash',t_init_crash_matrix),'spawn_crash_matrix':('crash',t_spawn_crash_matrix),'collect_crash_matrix':('crash',t_collect_crash_matrix),'discard_crash_matrix':('crash',t_discard_crash_matrix),'recover_dirty_ready':('crash',t_recover_preserves_dirty_ready_worker),
    'strong_object_isolation':('compat',t_strong_object_isolation),'fast_object_sharing':('compat',t_fast_object_sharing_is_explicit),'alternates_detached':('compat',t_alternates_detached_strong),'sha256_repository':('compat',t_sha256_repository),'reftable_repository':('compat',t_reftable_repository),'shallow_repository':('compat',t_shallow_repository),'sparse_checkout':('compat',t_sparse_checkout),'submodule_baseline':('compat',t_submodule_baseline),'symlink_executable':('compat',t_symlink_and_executable_bits),'detached_canonical_no_remote':('compat',t_detached_canonical_and_no_remote),'path_bound_config_warning':('compat',t_path_bound_config_warning),'info_exclude':('compat',t_info_exclude_copied),'worker_marker_tamper':('compat',t_marker_tamper_detection),'canonical_marker_loss':('compat',t_canonical_marker_loss_detection),
    'metadata_path_tamper':('redteam',t_metadata_path_tamper_guards),'worker_slot_symlink':('redteam',t_worker_slot_symlink_guard),'metadata_identity':('redteam',t_metadata_identity_validation),'recovery_resilience':('redteam',t_recovery_resilience_and_orphans),'provisioning_hooks':('redteam',t_provisioning_hooks_suppressed_but_preserved),'auxiliary_refs':('redteam',t_remote_tracking_notes_and_replace_refs),'ordinary_failure_rollbacks':('redteam',t_normal_failure_rollbacks),'final_path_collision':('redteam',t_final_path_collision_is_never_deleted),'branch_gitdir_substitution':('redteam',t_branch_rename_and_gitdir_substitution_refused),'result_survives_gc':('redteam',t_result_survives_discard_and_gc),
    'state_path_tamper':('redteam',t_workspace_state_path_tamper_rejected),'control_lock_symlink':('redteam',t_control_and_lock_symlink_rejected),'late_commit_crashed_discard':('redteam',t_late_commit_after_crashed_discard_survives),
}

def run_one(name):
    started=time.perf_counter()
    try:
        details=TESTS[name][1](); return {'name':name,'group':TESTS[name][0],'ok':True,'seconds':time.perf_counter()-started,'details':details}
    except Exception as e:
        return {'name':name,'group':TESTS[name][0],'ok':False,'seconds':time.perf_counter()-started,'error':repr(e)}

def driver(group=None,names=None):
    selected=names or [n for n,(g,_) in TESTS.items() if group is None or g==group]
    results=[]
    for name in selected:
        try:
            p=subprocess.run([sys.executable,__file__,'--one',name],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=150)
            lines=[x for x in p.stdout.splitlines() if x.startswith('RESULT_JSON=')]
            if not lines: r={'name':name,'group':TESTS[name][0],'ok':False,'error':f'no result; rc={p.returncode}; stderr={p.stderr[-500:]}'}
            else: r=json.loads(lines[-1].split('=',1)[1]); r['child_rc']=p.returncode
        except subprocess.TimeoutExpired:
            r={'name':name,'group':TESTS[name][0],'ok':False,'error':'test timed out after 150s'}
        results.append(r)
        print(('PASS' if r['ok'] else 'FAIL'),name,f"{r.get('seconds',0):.2f}s",r.get('error',''),flush=True)
    existing=[]
    if OUT.exists():
        try: existing=json.loads(OUT.read_text()).get('results',[])
        except Exception: existing=[]
    by={r['name']:r for r in existing}; by.update({r['name']:r for r in results}); merged=list(by.values())
    payload={'generated':time.time(),'total':len(merged),'passed':sum(r['ok'] for r in merged),'failed':sum(not r['ok'] for r in merged),'results':sorted(merged,key=lambda x:x['name'])}
    OUT.write_text(json.dumps(payload,indent=2))
    return 1 if any(not r['ok'] for r in results) else 0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--one'); ap.add_argument('--group',choices=['core','concurrency','crash','compat','redteam']); ap.add_argument('names',nargs='*'); a=ap.parse_args()
    ROOT.mkdir(parents=True,exist_ok=True)
    if a.one:
        r=run_one(a.one); print('RESULT_JSON='+json.dumps(r,separators=(',',':'))); return 0 if r['ok'] else 1
    return driver(a.group,a.names or None)

if __name__=='__main__': raise SystemExit(main())
