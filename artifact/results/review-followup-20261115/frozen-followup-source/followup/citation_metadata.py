from pathlib import Path
import re,json,urllib.request,urllib.parse,concurrent.futures,difflib,time
A=Path(__file__).resolve().parents[1];P=A.parent;OUT=A/'results/review-followup-20261115/citations';OUT.mkdir(exist_ok=True)
def fields(s):
 out={}
 for m in re.finditer(r'(\w+)\s*=\s*\{',s):
  start=m.end();depth=1;i=start
  while i<len(s)and depth:
   if s[i]=='{':depth+=1
   elif s[i]=='}':depth-=1
   i+=1
  out[m[1].lower()]=s[start:i-1]
 return out
def clean(x):return re.sub(r'[^a-z0-9]+',' ',x.lower()).strip()
entries=[]
for e in re.split(r'(?=@\w+\{)',(P/'manuscript/references.bib').read_text()):
 m=re.match(r'@(\w+)\{([^,]+)',e)
 if m:entries.append({'type':m[1],'key':m[2],**fields(e)})
def one(e):
 out=OUT/(e['key']+'.json')
 if out.exists():return json.loads(out.read_text())
 r={'entry':e,'checked':time.time()}
 try:
  url='https://api.crossref.org/works?'+urllib.parse.urlencode({'query.title':re.sub('[{}]','',e.get('title','')),'rows':3})
  req=urllib.request.Request(url,headers={'User-Agent':'ManuscriptBibliographyAudit/1.0'})
  with urllib.request.urlopen(req,timeout=30)as f:items=json.load(f)['message']['items']
  candidates=[]
  for x in items:
   title=' '.join(x.get('title',[]));score=difflib.SequenceMatcher(None,clean(title),clean(e.get('title',''))).ratio()
   candidates.append({'title':title,'match':score,**{k:x.get(k)for k in ['DOI','URL','author','container-title','published','page','type']}})
  r['candidates']=sorted(candidates,key=lambda x:-x['match']);r['status']='metadata match'if candidates and max(x['match']for x in candidates)>.93 else'needs primary verification'
 except Exception as ex:r['error']=repr(ex);r['status']='retrieval failed'
 out.write_text(json.dumps(r,indent=2)+'\n');return r
with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:rs=list(pool.map(one,entries))
(OUT/'summary.json').write_text(json.dumps(rs,indent=2)+'\n')
for r in rs:print(r['entry']['key'],r['status'],r.get('candidates',[{}])[0].get('title',''))
