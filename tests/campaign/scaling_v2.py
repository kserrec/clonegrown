#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent; CWS=HERE/'legacy_cli.py'

def run(cmd,cwd=None,check=True,timeout=180):
 p=subprocess.run([str(x) for x in cmd],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
 if check and p.returncode: raise RuntimeError(f'{cmd}\n{p.stdout}\n{p.stderr}')
 return p

def git(r,*a,check=True): return run(['git',*a],r,check)
def du(p): return int(run(['du','-s','-B1',p]).stdout.split()[0]) if Path(p).exists() else 0

def source(profile:str,root:Path):
 s=root/'source'; s.mkdir(); git(s,'init','-b','main'); git(s,'config','user.name','U'); git(s,'config','user.email','u@e')
 if profile=='tiny':
  (s/'src').mkdir();
  for i in range(200): (s/'src'/f'f{i}.txt').write_text((f'hello {i}\n')*100)
  git(s,'add','.'); git(s,'commit','-m','tiny')
 elif profile=='manyfiles':
  (s/'tree').mkdir()
  for i in range(6000): (s/'tree'/f'f{i:05d}.txt').write_text(f'{i} '+('x'*240)+'\n')
  git(s,'add','.'); git(s,'commit','-m','many files')
 elif profile=='binary':
  (s/'bin').mkdir()
  for i in range(16): (s/'bin'/f'b{i}.bin').write_bytes(os.urandom(1024*1024))
  git(s,'add','.'); git(s,'commit','-m','16 MiB current tree')
 elif profile=='history':
  for i in range(28):
   (s/'blob.bin').write_bytes(os.urandom(1024*1024)); git(s,'add','blob.bin'); git(s,'commit','-m',f'v{i}')
 elif profile=='refs':
  (s/'a').write_text('a'); git(s,'add','.'); git(s,'commit','-m','base'); sha=git(s,'rev-parse','HEAD').stdout.strip()
  lines=[]
  for i in range(2500): lines += [f'update refs/heads/b-{i} {sha}',f'update refs/custom/r-{i} {sha}']
  run(['git','update-ref','--stdin'],s,input='\n'.join(lines)+'\n') if False else None
 else: raise ValueError(profile)
 git(s,'gc','--aggressive','--prune=now'); return s

def copy_source(profile,root):
 # refs profile needs stdin support separately to keep runner simple.
 s=root/'source'; s.mkdir(); git(s,'init','-b','main'); git(s,'config','user.name','U'); git(s,'config','user.email','u@e')
 if profile!='refs':
  shutil.rmtree(s); return source(profile,root)
 (s/'a').write_text('a'); git(s,'add','.'); git(s,'commit','-m','base'); sha=git(s,'rev-parse','HEAD').stdout.strip()
 proc=subprocess.run(['git','update-ref','--stdin'],cwd=s,text=True,input=''.join(f'update refs/heads/b-{i} {sha}\nupdate refs/custom/r-{i} {sha}\n' for i in range(2500)),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if proc.returncode: raise RuntimeError(proc.stderr)
 git(s,'gc','--aggressive','--prune=now'); return s

def bench(profile:str,n:int):
 outer=Path(tempfile.mkdtemp(prefix=f'cws-scale-{profile}-{n}-')); src=copy_source(profile,outer); rows=[]
 src_git=du(src/'.git'); src_work=du(src)-src_git
 for strategy in ('worktree','fast','strong'):
  root=outer/strategy; root.mkdir(); c=root/'canonical'; run(['git','clone','--no-hardlinks',src,c]); git(c,'config','user.name','U'); git(c,'config','user.email','u@e'); base=du(root); times=[]
  if strategy=='worktree':
   workers=root/'workers'; workers.mkdir()
   for i in range(1,n+1):
    t=time.perf_counter(); git(c,'worktree','add','-q','-b',f'wt-{i}',workers/str(i),'main'); times.append(time.perf_counter()-t)
  else:
   ws=root/'workers'; run([sys.executable,CWS,'init',c,ws])
   for i in range(1,n+1):
    cmd=[sys.executable,CWS,'spawn',ws,'--task',f'w{i}','--request-id',f'r{i}']
    if strategy=='fast': cmd.append('--fast')
    t=time.perf_counter(); run(cmd); times.append(time.perf_counter()-t)
  total=du(root); rows.append({'profile':profile,'workers':n,'strategy':strategy,'seconds_total':sum(times),'seconds_mean':sum(times)/len(times),'seconds_each':times,'base_bytes':base,'total_bytes':total,'worker_delta_bytes':total-base,'canonical_git_bytes':du(c/'.git'),'canonical_worktree_bytes':du(c)-du(c/'.git')})
 out={'profile':profile,'workers':n,'source_git_bytes':src_git,'source_worktree_bytes':src_work,'rows':rows}; shutil.rmtree(outer,ignore_errors=True); return out

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('profile',choices=['tiny','manyfiles','binary','history','refs']); ap.add_argument('--workers',type=int,default=4); ap.add_argument('--output',required=True); a=ap.parse_args(); out=bench(a.profile,a.workers); Path(a.output).write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2));
if __name__=='__main__': main()
