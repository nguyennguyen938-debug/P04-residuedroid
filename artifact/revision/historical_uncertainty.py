#!/usr/bin/env python3
"""Stratified, paired trial-cluster bootstrap; legacy authorization estimand only.
Sampling units are whole AVD/schedule trials; all tenants and variants stay together.
Zero-event percentile intervals are descriptive and not upper safety bounds.
"""
import collections,csv,json,random
from pathlib import Path
ART=Path(__file__).resolve().parents[1];OUT=ART/'results/revision-20261115'
rows=[r for r in csv.DictReader((ART/'results/outcomes.csv').open()) if r['valid']=='1']
ks=collections.defaultdict(set)
for r in rows:ks[r['run'],r['schedule']].add(int(r['k']))
keep={key:set(sorted(v)[:50]) for key,v in ks.items()}
rows=[r for r in rows if int(r['k']) in keep[r['run'],r['schedule']] and int(r['tenant']) in [1,2,4,5,8]]
trials=collections.defaultdict(lambda:collections.defaultdict(list))
for r in rows:trials[r['run'],r['schedule'],r['trial']][r['variant']].append(int(r['violation']))
result=[];rng=random.Random(20261115)
for run in ['A','B']:
 strata=collections.defaultdict(list)
 for (a,s,t),vs in trials.items():
  if a==run:strata[s].append({v:sum(xs)/len(xs) for v,xs in vs.items()})
 variants=sorted(next(iter(strata.values()))[0]);boot={v:[] for v in variants};diff=[];comparison='conv' if run=='A' else 'egress'
 for _ in range(10000):
  sums={v:0 for v in variants};n=0
  for s,block in sorted(strata.items()):
   for trial in rng.choices(block,k=len(block)):
    for v in variants:sums[v]+=trial[v]
    n+=1
  for v in variants:boot[v].append(sums[v]/n)
  diff.append((sums[comparison]-sums['rd'])/n)
 def interval(xs):
  xs=sorted(xs);return [xs[249],xs[9749]]
 for v in variants:
  values=[t[v] for block in strata.values() for t in block]
  result.append(dict(run=run,variant=v,trials=len(values),estimate=sum(values)/len(values),percentile95=interval(boot[v])))
 result.append(dict(run=run,comparison=comparison+'-rd',paired_percentile95=interval(diff)))
(OUT/'historical-cluster-bootstrap.json').write_text(json.dumps({'resamples':10000,'seed':20261115,'estimand':'historical pre-write authorization; not socket handoff','rows':result},indent=2)+'\n')
print(json.dumps(result,indent=2))
