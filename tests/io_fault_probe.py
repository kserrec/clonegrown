#!/usr/bin/env python3
from __future__ import annotations
import json,os,resource,shutil,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent; CWS=HERE.parent/'clonegrown.py'
def run(cmd,cwd=None,check=True,timeout=300,preexec_fn=None):
 p=subprocess.run([str(x) for x in cmd],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,preexec_fn=preexec_fn)
 if check and p.returncode: raise RuntimeError(f'{cmd}\n{p.stdout}\n{p.stderr}')
 return p
def git(r,*a,check=True): return run(['git',*a],r,check)
def cws(*a,check=True): return run(['python3',CWS,*a],check=check)
def limit_files():
 resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024,16*1024))
def main():
 root=Path(tempfile.mkdtemp(prefix='cws-io-fault-')); c=root/'canonical'; git(root,'init','-b','main',c); git(c,'config','user.name','U'); git(c,'config','user.email','u@e'); (c/'large.bin').write_bytes(os.urandom(4*1024*1024)); git(c,'add','.'); git(c,'commit','-m','large'); git(c,'gc','--aggressive','--prune=now')
 ws=root/'ws'; cws('init',c,ws)
 failed=run(['python3',CWS,'spawn',ws,'--task','io fault','--request-id','io-fault'],check=False,preexec_fn=limit_files)
 reports=json.loads(cws('recover',ws).stdout)
 retry=json.loads(cws('spawn',ws,'--task','io fault','--request-id','io-fault').stdout); r=Path(retry['path'])
 status=json.loads(cws('status',ws).stdout); ready=[x for x in status['workers'] if x['status']=='ready' and x.get('request_id')=='io-fault']
 fsck=git(c,'fsck','--full',check=False)
 out={'ok':failed.returncode!=0 and len(ready)==1 and r.exists() and fsck.returncode==0,'fault_returncode':failed.returncode,'fault_stderr_tail':failed.stderr[-800:],'recover_reports':reports,'retry_worker':retry['id'],'ready_count':len(ready),'canonical_fsck_rc':fsck.returncode}
 (HERE/'io-fault-result.json').write_text(json.dumps(out,indent=2)+'\n'); print(json.dumps(out,indent=2)); shutil.rmtree(root,ignore_errors=True); return 0 if out['ok'] else 1
if __name__=='__main__': raise SystemExit(main())
