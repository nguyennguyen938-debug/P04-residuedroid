#!/usr/bin/env python3
import subprocess,time,json,sys
from pathlib import Path
from datetime import datetime
ART=Path(__file__).resolve().parents[1];ROOT=ART/'results/revision-20261115';deadline=datetime.fromisoformat(json.loads((ROOT/'execution.json').read_text())['started_utc']).timestamp()+28800
stages=[
 ('matched-A',['harness/campaign.py','--serial','emulator-5640','--port','8795','--variants','menqueue,mstart,mlayer,mfence,mboth','--trials','1','--start','6','--schedules','forcestop,reboot,revoke,netloss,inflight','--apkdir','fixture/build/revision-apk','--timeout','90','--seed','revision-20261115']),
 ('socket-A',['revision/socket_suite.py','--serial','emulator-5640','--port','8794','--blocks','9','--start','1','--deadline',str(deadline)])]
for name,args in stages:
 if time.time()>=deadline:break
 out=ROOT/name;out.mkdir(exist_ok=True)
 with (out/'stage.log').open('a') as log:
  p=subprocess.Popen([sys.executable,'-u',str(ART/args[0]),*args[1:],'--out',str(out)],stdout=log,stderr=subprocess.STDOUT)
  try:code=p.wait(timeout=max(1,deadline-time.time()))
  except subprocess.TimeoutExpired:p.terminate();code='budget';p.wait(timeout=30)
 with (ROOT/'stage-a.jsonl').open('a') as f:f.write(json.dumps(dict(stage=name,args=args,exit=code,time=time.time()))+'\n')
 if code!=0:break
