#!/usr/bin/env python3
"""Verify every available corpus APK; re-fetch two seeded small APKs per stratum and pinned ACRA deps."""
from pathlib import Path
import csv,hashlib,json,random,urllib.request,time
ART=Path(__file__).resolve().parents[1];OUT=ART/'results/revision-20261115/retrieval';OUT.mkdir(parents=True,exist_ok=True)
rows=list(csv.DictReader((ART/'static/corpus.csv').open()));records=[]
for r in rows:
 p=ART/'static/data/apks'/r['url'].rsplit('/',1)[-1]
 records.append(dict(kind='local_apk',file=p.name,expected=r['sha256'],observed=hashlib.file_digest(p.open('rb'),'sha256').hexdigest() if p.exists() else None))
chosen=[]
for stratum in ['tracking','random']:
 candidates=sorted([r for r in rows if r['stratum']==stratum],key=lambda r:int(r['size']))[:20]
 chosen+=random.Random(20261115).sample(candidates,2)
for r in chosen:
 try:
  data=urllib.request.urlopen(r['url'],timeout=30).read();observed=hashlib.sha256(data).hexdigest();records.append(dict(kind='remote_apk',url=r['url'],expected=r['sha256'],observed=observed))
 except Exception as e:records.append(dict(kind='remote_apk',url=r['url'],expected=r['sha256'],error=repr(e)))
for name in ['acra-core','acra-http','acra-advanced-scheduler']:
 url=f'https://repo.maven.apache.org/maven2/ch/acra/{name}/5.14.2/{name}-5.14.2.aar';p=ART/f'acra/deps/{name}-5.14.2.aar'
 try:
  data=urllib.request.urlopen(url,timeout=30).read();records.append(dict(kind='remote_acra',url=url,expected=hashlib.sha256(p.read_bytes()).hexdigest(),observed=hashlib.sha256(data).hexdigest()))
 except Exception as e:records.append(dict(kind='remote_acra',url=url,error=repr(e)))
(OUT/'verification.json').write_text(json.dumps({'checked_at':time.time(),'remote_sampling':'seed 20261115, two of smallest twenty APKs per stratum; not all remote APKs','records':records},indent=2)+'\n')
print('verified',sum(r.get('expected')==r.get('observed') and bool(r.get('expected')) for r in records),'of',len(records))
