from pathlib import Path
import json,subprocess,time,os
A=Path(__file__).resolve().parents[1];R=A/'results/review-followup-20261115';S=A.parents[1]/'shared-android'
for p in sorted(R.glob('matched-*/launch.json')):
 d=json.loads(p.read_text());cmd=d['command']
 cmd[cmd.index('--trials')+1]='5'
 out=p.parent
 log=(out/'campaign.log').open('a')
 q=subprocess.Popen(cmd,cwd=A,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 (out/'resume-launch.json').write_text(json.dumps({'pid':q.pid,'time':time.time(),'command':cmd,'reason':'instance-specific restart detection; completed attempts preserved'},indent=2)+'\n')
 print(out.name,q.pid)
