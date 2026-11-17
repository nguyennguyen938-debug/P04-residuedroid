#!/usr/bin/env python3
"""Second SDK: real Matomo queue/dispatcher, pre-send barrier, stock vs fenced PacketSender.
No claim of durable-cache recovery, HTTPS, or production deployment from this experiment.
"""
import argparse,json,subprocess,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from socket_suite import Device,ART
p=argparse.ArgumentParser();p.add_argument('--serial',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--blocks',type=int,default=5);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
d=Device(a.serial,a.out);pkg='org.residuelab.matomo'
def bc(op,*args):return d.adb('shell','am','broadcast','-n',pkg+'/org.residuelab.matomo.Cmd','-a','rl.MATOMO','--es','op',op,*args)
sink=subprocess.Popen([sys.executable,str(ART/'harness/sink.py'),'--port','8798','--out',str(a.out/'sink'),'--delay-ms','0'],stdout=open(a.out/'sink.log','w'),stderr=subprocess.STDOUT)
try:
 d.adb('install','-r','-g',str(ART/'matomo/build/matomo.apk'),timeout=120);time.sleep(.5)
 for block in range(a.blocks):
  for withdraw in [False,True]:
   for fenced in [False,True]:
    tag=f'RD-matomo-{block}-{int(withdraw)}-{int(fenced)}';r=dict(trial=tag,block=block,withdraw=withdraw,fenced=fenced)
    d.sh(f'pm clear {pkg}');d.sh(f'am start -W -n {pkg}/org.residuelab.matomo.Main')
    r['setup']=bc('setup','--es','trial',tag,'--ez','fenced',str(fenced).lower());r['dispatch']=bc('dispatch')
    end=time.monotonic()+5;r['barrier_seen']=False
    while time.monotonic()<end:
     log=d.sh(f'run-as {pkg} cat files/events.log 2>/dev/null')
     if 'PRE_SEND' in log:r['barrier_seen']=True;break
     time.sleep(.1)
    if withdraw:r['withdraw_result']=bc('withdraw')
    r['release']=bc('release');time.sleep(1)
    sinkfile=a.out/'sink/ingest.jsonl';receipts=[]
    if sinkfile.exists():receipts=[json.loads(l) for l in sinkfile.read_text().splitlines() if tag in l]
    r['delivered_requests']=len(receipts);r['receipts']=receipts;r['log']=d.sh(f'run-as {pkg} cat files/events.log 2>/dev/null');r['expected_delivery']=not(withdraw and fenced)
    r['pass']=r['barrier_seen'] and bool(receipts)==r['expected_delivery']
    with (a.out/'trials.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
    print(tag,r['pass'],r['delivered_requests'],flush=True)
finally:sink.terminate();sink.wait(timeout=10)
