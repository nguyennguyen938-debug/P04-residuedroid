#!/usr/bin/env python3
"""Matched campaign oracle: content from receiver tracers, order from attempt/return intervals.
Missing receipt or interrupted acceptance remains unknown. No host/device clock subtraction.
A withdrawal is certainly complete by WITHDRAW_ACK and may begin at WITHDRAW_REQUEST.
"""
import collections,csv,json,re,sys,random
from pathlib import Path
ART=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ART/'scripts'))
from oracle import item_sources,prohibited_source,final_legit
sys.path.insert(0,str(ART/'revision'))
from oracle_v2 import fields
ROOT=ART/'results/review-followup-20261115'
def jl(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
rows=[];invalid=[]
for instance in ['A','A-s1','A-s2','A-s3','B','B-s1','B-s2','B-s3']:
 run=instance[0];root=ROOT/f'matched-{instance}';schedules=jl(root/'schedule.jsonl');devices={(r['trial'],r['pkg'].split('.')[-1]):r for r in jl(root/'device_events.jsonl')}
 receipts=collections.defaultdict(list)
 for r in jl(root/'sink/ingest.jsonl'):
  b=r.get('body',{})
  if 'items' in b:receipts[b['trial'],b['variant']].append(r)
 for plan in schedules:
  trial=plan['trial'];errors=[a for a in plan['actions'] if a['a'] in ['trial_error','setup_fail','emulator_restarted']]
  gaps=[b['t']-a['t'] for a,b in zip(plan['actions'],plan['actions'][1:])]
  if errors or any(g>200 for g in gaps) or not plan.get('device_alive_end',False):invalid.append(dict(run=run,instance=instance,trial=trial,reason='harness/device'));continue
  if plan['schedule']=='forcestop' and any(sum(e[4]=='PROC_START' for e in devices.get((trial,v),{}).get('events',[]))<2 for v in plan['variants']):invalid.append(dict(run=run,instance=instance,trial=trial,reason='relaunch failed'));continue
  if plan['schedule']=='netloss' and not plan.get('net_verified_down'):invalid.append(dict(run=run,instance=instance,trial=trial,reason='unverified outage'));continue
  if any(not devices.get((trial,v),{}).get('events') for v in plan['variants']):invalid.append(dict(run=run,instance=instance,trial=trial,reason='missing paired log'));continue
  for v in plan['variants']:
   events=devices[trial,v]['events'];requests=collections.defaultdict(list);acks=collections.defaultdict(list);starts=collections.defaultdict(list)
   for seq,tw,tel,t,kind,detail in events:
    if kind=='WITHDRAW_ACK':acks[t].append(seq)
    if kind=='WITHDRAW_REQUEST':starts[t].append(seq)
    f=fields(detail)
    if f.get('request'):requests[f['request']].append((seq,t,kind,f))
   seen=set();out={t:dict(run=run,trial=trial,k=plan['k'],schedule=plan['schedule'],phase=instance,variant=v,tenant=t,violation=0,unknown_requests=0,delivered_requests=0,duplicates=0,legit_delivered=set()) for t in [1,2,3,4,5,6,7,8]}
   ids=set()
   for receipt in receipts[trial,v]:
    if not plan['actions'][0]['t'] <= receipt['t_host'] <= plan['actions'][-1]['t']:continue
    body=receipt['body'];t=body['tenant'];sid=body['sid'];ids.add(sid)
    if t not in out:continue
    row=out[t];row['delivered_requests']+=1;purpose=body['purpose'];attempts={};intervals=[]
    for seq,_,kind,f in requests.get(sid,[]):
     key=f.get('attempt'),f.get('offset')
     if kind=='WRITE_ATTEMPT':attempts[key]=seq
     if kind=='BYTES_ACCEPTED':
      begin=attempts.pop(key,None)
      if int(f.get('n',0))>0:intervals.append((begin,seq))
    ambiguous=not intervals or bool(attempts)
    for item in body['items']:
     unique=purpose,item['tag'];row['duplicates']+=int(unique in seen);seen.add(unique);row['legit_delivered'].add(unique)
     for st,epoch,_ in item_sources(item):
      for begin,end in intervals:
       if begin is None:ambiguous=True;continue
       before=sum(w<begin for w in acks[st]);possible=sum(w<end for w in starts[st])
       if prohibited_source(st,epoch,purpose,before):row['violation']=1
       elif prohibited_source(st,epoch,purpose,possible):ambiguous=True
    row['unknown_requests']+=int(ambiguous)
   for id,es in requests.items():
    if id not in ids and any(kind=='WRITE_ATTEMPT' for _,_,kind,_ in es):
     t=es[0][1]
     if t in out:out[t]['unknown_requests']+=1
   for t,row in out.items():
    legit=final_legit(t,trial,12,4 if t==5 else 0);row['legit_missing']=len(legit-row['legit_delivered']);
    if t==5:row['legit_missing']=max(0,4-len({tag for purpose,tag in row['legit_delivered'] if re.match(r'^RD-\w+-T5-e1-\d+$',tag)}))
    row['legit_expected']=len(legit);row['instance']=instance;del row['legit_delivered'];rows.append(row)
(ROOT/'matched-outcomes.json').write_text(json.dumps({'invalid_trials':invalid,'rows':rows},indent=2)+'\n')
# Paired bootstrap on whole trials within schedule and AVD, including all affected tenants.
summary=[]
for run in ['A','B']:
 variants=sorted({r['variant'] for r in rows if r['run']==run})
 for v in variants:
  rs=[r for r in rows if r['run']==run and r['variant']==v and r['tenant'] in [1,2,4,5,8]]
  by=collections.defaultdict(list)
  for r in rs:by[r['schedule'],r['phase'],r['trial']].append(r)
  strata=collections.defaultdict(list)
  for (schedule,phase,trial),xs in by.items():strata[schedule,phase].append(sum(r['violation'] for r in xs)/len(xs))
  rng=random.Random(20261115);boot=[]
  for _ in range(10000):
   vals=[x for s,xs in sorted(strata.items()) for x in rng.choices(xs,k=len(xs))];boot.append(sum(vals)/len(vals))
  boot.sort();summary.append(dict(estimand='confirmed violating affected-tenant fraction; unknown requests separate',run=run,variant=v,trials=len(by),tenant_trials=len(rs),known_violations=sum(r['violation'] for r in rs),unknown_requests=sum(r['unknown_requests'] for r in rs),percentile95=[boot[249],boot[9749]],legit_missing=sum(r['legit_missing'] for r in rows if r['run']==run and r['variant']==v)))
(ROOT/'matched-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('matched',len(rows),'tenant rows;',len(invalid),'invalid paired trials')

# Paired contrasts: sample whole trial differences, retaining tenants and common schedules.
contrasts=[]
for run in ['A','B']:
 for early in ['menqueue','mstart','mlayer']:
  for fenced in ['mfence','mboth']:
   paired=collections.defaultdict(dict)
   for r in rows:
    if r['run']==run and r['variant'] in [early,fenced] and r['tenant'] in [1,2,4,5,8]:
     key=(r['schedule'],r['phase'],r['trial'])
     paired[key].setdefault(r['variant'],[]).append(r['violation'])
   strata=collections.defaultdict(list)
   for (schedule,phase,trial),vs in sorted(paired.items()):
    if set(vs)=={early,fenced} and all(len(v)==5 for v in vs.values()):
     strata[schedule,phase].append((sum(vs[early])-sum(vs[fenced]))/5)
   rng=random.Random(20261115);boot=[];observed=[v for xs in strata.values() for v in xs]
   if not observed:continue
   for _ in range(10000):
    vals=[v for _,xs in sorted(strata.items()) for v in rng.choices(xs,k=len(xs))];boot.append(sum(vals)/len(vals))
   boot.sort();contrasts.append(dict(estimand='paired difference in confirmed violating affected-tenant fractions',run=run,early=early,fenced=fenced,paired_trials=len(observed),difference=sum(observed)/len(observed),percentile95=[boot[249],boot[9749]],strata={str(k):len(v) for k,v in strata.items()}))
(ROOT/'matched-paired-contrasts.json').write_text(json.dumps(contrasts,indent=2)+'\n')
