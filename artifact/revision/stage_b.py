#!/usr/bin/env python3
"""Sequential device-B stages, capped by the original eight-hour wall-clock deadline."""
import subprocess,time,json,sys
from pathlib import Path
ART=Path(__file__).resolve().parents[1];ROOT=ART/'results/revision-20261115'
from datetime import datetime
start=datetime.fromisoformat(json.loads((ROOT/'execution.json').read_text())['started_utc']).timestamp();deadline=start+28800
stages=[
 ('acra-conformance-B',['revision/acra_conformance.py','--serial','emulator-5642']),
 ('acra-v4-B',['revision/acra_case_v4.py','--serial','emulator-5642','--avd','P04AvdB','--trials','10','--reboot-trials','3']),
 ('matched-B',['harness/campaign.py','--serial','emulator-5642','--port','8796','--variants','menqueue,mstart,mlayer,mfence,mboth','--trials','4','--start','1','--apkdir','fixture/build/revision-apk','--timeout','90','--seed','revision-20261115']),
 ('socket-B',['revision/socket_suite.py','--serial','emulator-5642','--port','8797','--blocks','9','--start','1','--deadline',str(deadline)])]
for name,args in stages:
 if time.time()>=deadline:break
 out=ROOT/name;out.mkdir(exist_ok=True)
 with (out/'stage.log').open('a') as log:
  p=subprocess.Popen([sys.executable,'-u',str(ART/args[0]),*args[1:],'--out',str(out)],stdout=log,stderr=subprocess.STDOUT)
  try:code=p.wait(timeout=max(1,deadline-time.time()))
  except subprocess.TimeoutExpired:p.terminate();code='budget';p.wait(timeout=30)
 with (ROOT/'stage-b.jsonl').open('a') as f:f.write(json.dumps(dict(stage=name,exit=code,time=time.time()))+'\n')
 if code!=0:break
