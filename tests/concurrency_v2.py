#!/usr/bin/env python3
from __future__ import annotations
import argparse,concurrent.futures as cf,json,shutil,subprocess,sys,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent; CWS=HERE.parent/'clonegrown.py'
def run(cmd,cwd=None,check=True,timeout=180):
 p=subprocess.run([str(x) for x in cmd],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
 if check and p.returncode: raise RuntimeError(f'{cmd}\n{p.stdout}\n{p.stderr}')
 return p
def git(r,*a,check=True): return run(['git',*a],r,check)
def bench(n):
 root=Path(tempfile.mkdtemp(prefix=f'cws-concurrency-{n}-')); src=root/'source'; git(root,'init','-b','main',src); git(src,'config','user.name','U'); git(src,'config','user.email','u@e'); (src/'src').mkdir();
 for i in range(100): (src/'src'/f'f{i}').write_text('x'*1000)
 git(src,'add','.'); git(src,'commit','-m','base'); out=[]
 # clone-helper parallel spawn
 croot=root/'clones'; croot.mkdir(); c=croot/'canonical'; run(['git','clone','--no-hardlinks',src,c]); git(c,'config','user.name','U'); git(c,'config','user.email','u@e'); ws=croot/'workers'; run([sys.executable,CWS,'init',c,ws])
 def clone_one(i): return run([sys.executable,CWS,'spawn',ws,'--fast','--task',f'w{i}','--request-id',f'r{i}'],check=False)
 t=time.perf_counter()
 with cf.ThreadPoolExecutor(max_workers=n) as ex: ps=list(ex.map(clone_one,range(n)))
 dt=time.perf_counter()-t; ids=[]
 for p in ps:
  if p.returncode==0: ids.append(json.loads(p.stdout)['id'])
 out.append({'strategy':'clone-fast','n':n,'seconds':dt,'successes':sum(p.returncode==0 for p in ps),'failures':sum(p.returncode!=0 for p in ps),'unique_ids':len(set(ids)),'stderr_tails':[p.stderr[-200:] for p in ps if p.returncode]})
 # concurrent worktree adds from one shared repo
 wroot=root/'worktrees'; wroot.mkdir(); wc=wroot/'canonical'; run(['git','clone','--no-hardlinks',src,wc]); dest=wroot/'workers'; dest.mkdir()
 def wt_one(i): return run(['git','worktree','add','-q','-b',f'wt-{i}',dest/str(i),'main'],cwd=wc,check=False)
 t=time.perf_counter()
 with cf.ThreadPoolExecutor(max_workers=n) as ex: qs=list(ex.map(wt_one,range(n)))
 dt=time.perf_counter()-t
 out.append({'strategy':'worktree','n':n,'seconds':dt,'successes':sum(p.returncode==0 for p in qs),'failures':sum(p.returncode!=0 for p in qs),'stderr_tails':[p.stderr[-300:] for p in qs if p.returncode]})
 shutil.rmtree(root,ignore_errors=True); return {'n':n,'rows':out}
if __name__=='__main__':
 ap=argparse.ArgumentParser(); ap.add_argument('n',type=int); ap.add_argument('--output',required=True); a=ap.parse_args(); x=bench(a.n); Path(a.output).write_text(json.dumps(x,indent=2)+'\n'); print(json.dumps(x,indent=2))
