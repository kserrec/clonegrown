#!/usr/bin/env python3
from __future__ import annotations
import json,os,shutil,sys,tempfile,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import hardening_suite as h
mode,fp=sys.argv[1:3]
root=Path(tempfile.mkdtemp(prefix=f'cws-final-{mode}-{fp.replace(".","-")}-'))
h.ROOT=root
started=time.perf_counter()
try:
    b,c,w,_=h.mkcase('case')
    m=h.spawn(w,request='r'); r=Path(m['path']); sha=h.commit(r,'result')
    if mode=='collect':
        p=h.cws('collect',w,str(m['id']),env={'CWS_FAILPOINT':fp},check=False)
        assert p.returncode==88,(p.returncode,p.stdout,p.stderr)
        reports=h.jload(h.cws('recover',w)); mm=h.meta(w,m['id'])
        if mm['status']=='ready': h.cws('collect',w,str(m['id'])); mm=h.meta(w,m['id'])
        assert mm['status']=='collected' and mm['result_sha']==sha,mm
        h.git(c,'fsck','--full')
    elif mode=='discard':
        h.cws('collect',w,str(m['id']))
        p=h.cws('discard',w,str(m['id']),env={'CWS_FAILPOINT':fp},check=False)
        assert p.returncode==88,(p.returncode,p.stdout,p.stderr)
        reports=h.jload(h.cws('recover',w)); mm=h.meta(w,m['id'])
        if Path(m['path']).exists(): h.cws('discard',w,str(m['id'])); mm=h.meta(w,m['id'])
        assert mm['status']=='discarded' and not Path(m['path']).exists(),mm
        st=h.state(w); ref=f"refs/cws/{st['workspace_id']}/workers/{m['id']}/result"
        assert h.git(c,'rev-parse',ref).stdout.strip()==sha
    else: raise ValueError(mode)
    row={'mode':mode,'failpoint':fp,'ok':True,'seconds':time.perf_counter()-started,'sha':sha,'reports':reports}
except Exception as e:
    row={'mode':mode,'failpoint':fp,'ok':False,'seconds':time.perf_counter()-started,'error':repr(e),'root':str(root)}
finally:
    if row.get('ok'): shutil.rmtree(root,ignore_errors=True)
with (HERE/'crash-results.jsonl').open('a') as f: f.write(json.dumps(row,sort_keys=True)+'\n')
print(json.dumps(row,indent=2,sort_keys=True))
raise SystemExit(0 if row['ok'] else 1)
