#!/usr/bin/env python3
from __future__ import annotations
import concurrent.futures as cf,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent; CWS=HERE/'legacy_cli.py'
def run(cmd,cwd=None,check=True,timeout=180):
 p=subprocess.run([str(x) for x in cmd],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
 if check and p.returncode: raise RuntimeError(f'{cmd}\n{p.stdout}\n{p.stderr}')
 return p
def git(r,*a,check=True): return run(['git',*a],r,check)
def main(n=8):
 root=Path(tempfile.mkdtemp(prefix='cws-gc-compare-')); src=root/'src'; git(root,'init','-b','main',src); git(src,'config','user.name','U'); git(src,'config','user.email','u@e')
 for i in range(18):
  (src/f'f{i}.bin').write_bytes(os.urandom(256*1024)); git(src,'add','.'); git(src,'commit','-m',f'c{i}')
 rows=[]
 # worktrees
 wr=root/'worktree'; wr.mkdir(); wc=wr/'canonical'; run(['git','clone','--no-hardlinks',src,wc]); wd=wr/'workers'; wd.mkdir(); wrepos=[]
 for i in range(n): p=wd/str(i); git(wc,'worktree','add','-q','-b',f'wt-{i}',p,'main'); wrepos.append(p)
 def gc(r): return git(r,'gc','--prune=now',check=False)
 t=time.perf_counter();
 with cf.ThreadPoolExecutor(max_workers=n) as ex: ps=list(ex.map(gc,wrepos))
 rows.append({'strategy':'worktree','n':n,'seconds':time.perf_counter()-t,'successes':sum(p.returncode==0 for p in ps),'failures':sum(p.returncode!=0 for p in ps),'errors':[p.stderr.strip()[-500:] for p in ps if p.returncode]})
 # clones
 cr=root/'clones'; cr.mkdir(); cc=cr/'canonical'; run(['git','clone','--no-hardlinks',src,cc]); git(cc,'config','user.name','U'); git(cc,'config','user.email','u@e'); ws=cr/'workers'; run([sys.executable,CWS,'init',cc,ws]); crepos=[]
 for i in range(n): m=json.loads(run([sys.executable,CWS,'spawn',ws,'--fast','--task',f'w{i}','--request-id',f'r{i}']).stdout); crepos.append(Path(m['path']))
 t=time.perf_counter();
 with cf.ThreadPoolExecutor(max_workers=n) as ex: qs=list(ex.map(gc,crepos))
 rows.append({'strategy':'clone-fast','n':n,'seconds':time.perf_counter()-t,'successes':sum(p.returncode==0 for p in qs),'failures':sum(p.returncode!=0 for p in qs),'errors':[p.stderr.strip()[-500:] for p in qs if p.returncode]})
 out={'rows':rows}; (HERE/'gc-concurrency.json').write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2)); shutil.rmtree(root,ignore_errors=True)
if __name__=='__main__': main()
