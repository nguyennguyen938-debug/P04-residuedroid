#!/usr/bin/env python3
"""Wait for this revision's stage queues, then run the missing socket block and final ACRA build checks."""
import subprocess,json,time,sys
from pathlib import Path
from datetime import datetime
ART=Path(__file__).resolve().parents[1];ROOT=ART/'results/revision-20261115';deadline=datetime.fromisoformat(json.loads((ROOT/'execution.json').read_text())['started_utc']).timestamp()+28800
side=sys.argv[1];serial='emulator-5640' if side=='A' else 'emulator-5642';stagefile=ROOT/f'stage-{side.lower()}.jsonl'
while time.time()<deadline:
 rows=[json.loads(l) for l in stagefile.read_text().splitlines()] if stagefile.exists() else []
 if rows and rows[-1]['stage']=='socket-'+side and rows[-1]['exit']==0:break
 time.sleep(10)
else:raise SystemExit('budget exhausted before final checks')
commands=[('socket-'+side,['revision/socket_suite.py','--serial',serial,'--port','8794' if side=='A' else '8797','--blocks','1','--start','0','--deadline',str(deadline)])]
if side=='A':commands += [('acra-conformance-final',['revision/acra_conformance.py','--serial',serial]),('acra-final-A',['revision/acra_case_v4.py','--serial',serial,'--avd','P04AvdA','--trials','1','--reboot-trials','0'])]
for name,args in commands:
 if time.time()>=deadline:break
 out=ROOT/name;out.mkdir(exist_ok=True)
 with (out/'final-stage.log').open('a') as log:
  p=subprocess.Popen([sys.executable,'-u',str(ART/args[0]),*args[1:],'--out',str(out)],stdout=log,stderr=subprocess.STDOUT)
  try:code=p.wait(timeout=max(1,deadline-time.time()))
  except subprocess.TimeoutExpired:p.terminate();code='budget';p.wait(timeout=30)
 with (ROOT/f'final-{side}.jsonl').open('a') as f:f.write(json.dumps(dict(stage=name,exit=code,time=time.time()))+'\n')
 if code!=0:break
