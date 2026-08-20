#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,random,shutil,signal,subprocess,sys,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent; CWS=HERE.parent/'clonegrown.py'

def run(cmd,cwd=None,check=True,timeout=120):
 p=subprocess.run([str(x) for x in cmd],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
 if check and p.returncode: raise RuntimeError(f'{cmd} rc={p.returncode}\n{p.stdout}\n{p.stderr}')
 return p

def git(r,*a,check=True): return run(['git',*a],r,check)
def cw(*a,check=True): return run([sys.executable,CWS,*a],check=check,timeout=180)

def make_case(tag,large_mb=12):
 b=Path(tempfile.mkdtemp(prefix=f'cws-random-kill-{tag}-')); origin=b/'origin.git'; git(b,'init','--bare',origin); c=b/'canon'; git(b,'clone',origin,c)
 git(c,'config','user.name','U'); git(c,'config','user.email','u@e'); (c/'src').mkdir(); (c/'src/a').write_text('a\n'); (c/'.gitignore').write_text('build/\n')
 # Incompressible data makes strong local cloning and fetch genuinely nontrivial.
 (c/'payload.bin').write_bytes(os.urandom(large_mb*1024*1024)); git(c,'add','.'); git(c,'commit','-m','base'); git(c,'branch','-M','main'); git(c,'push','-u','origin','main'); git(c,'gc','--aggressive','--prune=now')
 w=b/'ws'; cw('init',c,w); return b,c,w

def j(p): return json.loads(p.stdout)
def meta(w,i): return json.loads((w/'.cws/workers'/f'{i}.json').read_text())
def state(w): return json.loads((w/'.cws/state.json').read_text())

def start_and_kill(args,delay):
 p=subprocess.Popen([sys.executable,str(CWS),*map(str,args)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
 time.sleep(delay); killed=False
 if p.poll() is None:
  os.killpg(p.pid,signal.SIGKILL); killed=True
 out,err=p.communicate(timeout=10)
 return {'rc':p.returncode,'killed':killed,'stdout':out[-400:],'stderr':err[-400:]}

def spawn_case(seed):
 rng=random.Random(seed); b,c,w=make_case(f'spawn-{seed}',large_mb=10); delay=rng.uniform(0.0,1.25); req=f'kill-{seed}'
 proc=start_and_kill(['spawn',w,'--task',req,'--base','main','--request-id',req],delay)
 reports=j(cw('recover',w)); ready=j(cw('spawn',w,'--task',req,'--base','main','--request-id',req))
 r=Path(ready['path']); assert ready['status']=='ready'; assert git(r,'rev-parse','HEAD').stdout.strip()==ready['base_sha']; git(c,'fsck','--full')
 cw('discard',w,str(ready['id']),'--abandon'); row={'mode':'spawn','seed':seed,'delay':delay,'process':proc,'reports':reports,'ready_id':ready['id'],'ok':True}; shutil.rmtree(b,ignore_errors=True); return row

def collect_case(seed):
 rng=random.Random(seed); b,c,w=make_case(f'collect-{seed}',large_mb=4); m=j(cw('spawn',w,'--task','collect','--request-id',f'c-{seed}','--fast')); r=Path(m['path']); (r/f'new-{seed}.bin').write_bytes(os.urandom(8*1024*1024)); git(r,'add','.'); git(r,'commit','-m','large result'); sha=git(r,'rev-parse','HEAD').stdout.strip(); delay=rng.uniform(0.0,.22)
 proc=start_and_kill(['collect',w,str(m['id'])],delay); reports=j(cw('recover',w)); mm=meta(w,m['id'])
 if mm['status']=='ready': mm=j(cw('collect',w,str(m['id'])))
 assert mm['status']=='collected' and mm['result_sha']==sha; st=state(w); ref=f"refs/cws/{st['workspace_id']}/workers/{m['id']}/result"; assert git(c,'rev-parse',ref).stdout.strip()==sha; git(c,'fsck','--full')
 cw('discard',w,str(m['id'])); row={'mode':'collect','seed':seed,'delay':delay,'process':proc,'reports':reports,'sha':sha,'ok':True}; shutil.rmtree(b,ignore_errors=True); return row

def discard_case(seed):
 rng=random.Random(seed); b,c,w=make_case(f'discard-{seed}',large_mb=2); m=j(cw('spawn',w,'--task','discard','--request-id',f'd-{seed}','--fast')); r=Path(m['path']); (r/'x').write_text('x'); git(r,'add','x'); git(r,'commit','-m','result'); sha=git(r,'rev-parse','HEAD').stdout.strip(); mm=j(cw('collect',w,str(m['id'])))
 build=r/'build'; build.mkdir();
 for i in range(3500): (build/f'{i:05d}.tmp').write_text('x'*256)
 delay=rng.uniform(0.0,.08); proc=start_and_kill(['discard',w,str(m['id'])],delay); reports=j(cw('recover',w)); mm=meta(w,m['id'])
 if Path(m['path']).exists(): mm=j(cw('discard',w,str(m['id'])))
 assert mm['status']=='discarded' and not Path(m['path']).exists(); st=state(w); ref=f"refs/cws/{st['workspace_id']}/workers/{m['id']}/result"; assert git(c,'rev-parse',ref).stdout.strip()==sha; git(c,'fsck','--full')
 row={'mode':'discard','seed':seed,'delay':delay,'process':proc,'reports':reports,'sha':sha,'ok':True}; shutil.rmtree(b,ignore_errors=True); return row

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('mode',choices=['spawn','collect','discard']); ap.add_argument('--start',type=int,default=0); ap.add_argument('--count',type=int,default=1); ap.add_argument('--output',required=True); a=ap.parse_args(); rows=[]
 fn={'spawn':spawn_case,'collect':collect_case,'discard':discard_case}[a.mode]
 for seed in range(a.start,a.start+a.count):
  t=time.perf_counter()
  try: row=fn(seed); row['seconds']=time.perf_counter()-t
  except Exception as e: row={'mode':a.mode,'seed':seed,'ok':False,'error':repr(e),'seconds':time.perf_counter()-t}
  rows.append(row); print(('PASS' if row['ok'] else 'FAIL'),json.dumps(row,sort_keys=True),flush=True)
  if not row['ok']: break
 Path(a.output).write_text(json.dumps({'mode':a.mode,'start':a.start,'count':a.count,'passed':sum(r['ok'] for r in rows),'failed':sum(not r['ok'] for r in rows),'results':rows},indent=2)+'\n')
 return int(any(not r['ok'] for r in rows))
if __name__=='__main__': raise SystemExit(main())
