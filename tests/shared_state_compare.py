#!/usr/bin/env python3
from __future__ import annotations
import json,shutil,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent; CWS=HERE/'legacy_cli.py'
def run(cmd,cwd=None,check=True):
 p=subprocess.run([str(x) for x in cmd],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if check and p.returncode: raise RuntimeError(f'{cmd}\n{p.stdout}\n{p.stderr}')
 return p
def git(r,*a,check=True): return run(['git',*a],r,check)
def fixture(root,name):
 b=root/name; b.mkdir(); origin=b/'origin.git'; git(b,'init','--bare',origin); c=b/'canonical'; git(b,'clone',origin,c); git(c,'config','user.name','U'); git(c,'config','user.email','u@e'); (c/'a').write_text('a'); git(c,'add','.'); git(c,'commit','-m','base'); git(c,'branch','-M','main'); git(c,'push','-u','origin','main'); git(c,'config','agent.sentinel','canonical'); git(c,'branch','dormant'); (c/'stash').write_text('s'); git(c,'add','stash'); git(c,'stash','push','-m','canonical'); return b,c

def snapshot(c): return {'config':git(c,'config','agent.sentinel').stdout.strip(),'origin':('origin' in git(c,'remote').stdout.split()),'stash':git(c,'stash','list').stdout.strip(),'dormant':git(c,'show-ref','--verify','refs/heads/dormant',check=False).returncode==0}
def mutate(r):
 git(r,'config','agent.sentinel','worker'); git(r,'remote','remove','origin'); git(r,'stash','clear'); git(r,'branch','-D','dormant')
def main():
 root=Path(tempfile.mkdtemp(prefix='cws-shared-state-')); rows=[]
 b,c=fixture(root,'wt'); wt=b/'worker'; git(c,'worktree','add','-q','-b','task',wt,'main'); before=snapshot(c); mutate(wt); after=snapshot(c); rows.append({'strategy':'worktree','before':before,'after_worker_mutation':after,'canonical_changed':before!=after})
 b,c=fixture(root,'clone'); ws=b/'workers'; run([sys.executable,CWS,'init',c,ws]); m=json.loads(run([sys.executable,CWS,'spawn',ws,'--fast','--task','task','--request-id','r']).stdout); r=Path(m['path']); git(r,'branch','dormant',f"{m['source_remote']}/dormant"); before=snapshot(c); mutate(r); after=snapshot(c); rows.append({'strategy':'clone-fast','before':before,'after_worker_mutation':after,'canonical_changed':before!=after})
 out={'rows':rows}; (HERE/'shared-state-comparison.json').write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2)); shutil.rmtree(root,ignore_errors=True)
if __name__=='__main__': main()
