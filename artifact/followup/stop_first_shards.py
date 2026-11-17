from pathlib import Path
import time,json,os,signal
R=Path(__file__).resolve().parents[1]/'results/review-followup-20261115'
remaining={'A','B'}
while remaining:
 for n in list(remaining):
  p=R/('matched-'+n);xs=[]
  for l in(p/'schedule.jsonl').read_text().splitlines():
   try:xs.append(json.loads(l))
   except ValueError:pass
  if any(x.get('k')==4 and x.get('schedule')=='inflight'for x in xs):
   launch=json.loads((p/'launch.json').read_text());os.kill(launch['campaign_pid'],signal.SIGINT)
   (p/'shard-boundary.json').write_text(json.dumps({'planned_k':[0,1,2,3,4],'other_k_excluded':True,'reason':'planned parallel read-only instance partition, independent of outcomes','stopped':time.time()},indent=2)+'\n');remaining.remove(n);print('stopped first shard',n,flush=True)
 time.sleep(.25)
