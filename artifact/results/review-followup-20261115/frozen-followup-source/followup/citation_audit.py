from pathlib import Path
import re,json,collections
A=Path(__file__).resolve().parents[1];P=A.parent;M=P/'manuscript';R=A/'results/review-followup-20261115/citations'
primary={
 'tang2012cleanos':'https://www.usenix.org/conference/osdi12/technical-sessions/presentation/tang',
 'spahn2014pebbles':'https://www.usenix.org/conference/osdi14/technical-sessions/presentation/spahn',
 'nadkarni2016weir':'https://www.usenix.org/conference/usenixsecurity16/technical-sessions/presentation/nadkarni',
 'backes2015boxify':'https://www.usenix.org/conference/usenixsecurity15/technical-sessions/presentation/backes',
 'fernandes2016flowfence':'https://www.usenix.org/conference/usenixsecurity16/technical-sessions/presentation/fernandes',
 'xu2012aurasium':'https://www.usenix.org/conference/usenixsecurity12/technical-sessions/presentation/xu_rubin',
 'reardon2019fiftyways':'https://www.usenix.org/conference/usenixsecurity19/presentation/reardon',
 'andow2020policheck':'https://www.usenix.org/conference/usenixsecurity20/presentation/andow',
 'andow2019policylint':'https://www.usenix.org/conference/usenixsecurity19/presentation/andow',
 'enck2010taintdroid':'https://www.usenix.org/conference/osdi10/legacy-presentation/taintdroid-information-flow-tracking-system-realtime-privacy',
 'nguyen2021sharefirst':'https://github.com/cispa/gdpr-consent',
 'nguyen2022freely':'https://cispa.saarland/group/stock/papers/nguyen2022consent.pdf',
 'zeldovich2006histar':'https://www.usenix.org/conference/osdi-06/making-information-flow-explicit-histar',
 'wang2019riverbed':'https://www.usenix.org/conference/nsdi19/presentation/wang-frank',
 'android_sdkruntime':'https://privacysandbox.google.com/private-advertising/sdk-runtime/architecture',
 'matomo_consent':'https://developer.matomo.org/guides/tracking-consent',
 'java_sslengine':'https://docs.oracle.com/en/java/javase/17/docs/api/java.base/javax/net/ssl/SSLEngine.html'}
(R/'primary-sources.json').write_text(json.dumps({'checked':'2026-11-15','scope':'primary metadata and background scope; not full theorem replication','sources':primary},indent=2)+'\n')
bib=M/'references.bib';entries={};body=bib.read_text()
for m in re.finditer(r'@\w+\{([^,]+),',body):entries[m[1]]=body[:m.start()].count('\n')+1
uses=collections.defaultdict(list)
for p in [M/'main.tex',*sorted((M/'sections').glob('*.tex')),*sorted((M/'generated').glob('*.tex'))]:
 for no,line in enumerate(p.read_text().splitlines(),1):
  line=line.split('%')[0]
  for m in re.finditer(r'\\cite\w*\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}',line):
   for key in m[1].split(','):uses[key.strip()].append((p,no,line.strip()))
missing=sorted(set(uses)-set(entries));unused=sorted(set(entries)-set(uses));lines=['# Citation audit — ResidueDroid','',f'Inventory covers {len(uses)} cited keys and {len(entries)} bibliography entries, including appendices and generated prose. {len(missing)} unresolved keys; {len(unused)} uncited entries.','', '## Findings','', '- **P1: verification remains partial.** Every entry is inventoried; primary-source metadata/background was checked for the sources linked below. Crossref title matches are discovery evidence, not claim verification. Retrieval failures and unmatched entries remain open.', '- **P1: avoid edition substitution.** Crossref returned the 2011 HiStar journal version and a 1992 Efron reprint for conference/original entries. The manuscript retains OSDI 2006 and Annals 1979; no DOI was imported from those mismatches.', '- **P2: background scope.** SDK Runtime isolation does not establish queued-data withdrawal semantics. Matomo consent documentation is for its JavaScript tracker, separate from the Android 4.4 integration. Riverbed concerns distributed services, not this Android transport.', '- **Unresolved:** '+(', '.join(missing)or'none')+'.','- **Uncited:** '+(', '.join(unused)or'none')+'.','', '## Evidence inventory','', '| Key | Manuscript | Bibliography | Verification / support scope |','|---|---|---|---|']
for key in sorted(entries):
 u=uses.get(key,[]);p,n,_=u[0]if u else(bib,entries[key],'');ml=f'[{p.name}:{n}]({p.resolve()}:{n})'if u else'uncited';bl=f'[entry]({bib.resolve()}:{entries[key]})';meta=R/(key+'.json')
 status='Not independently verified in this pass'
 if meta.exists():
  d=json.loads(meta.read_text());status=d['status']+'; external claim support not established'
 if key in primary:status=f'[Primary source]({primary[key]}); metadata and background scope checked'
 if key=='efron1979bootstrap':status='Crossref reprint mismatch; original-year entry retained; primary verification open'
 lines.append(f'| `{key}` | {ml} | {bl} | {status} |')
lines+=['','## Artifact-document check','']
for name in ['README.md','PROVENANCE.md','results/RUNLOG.md']:
 p=A/name
 if not p.exists():lines.append(f'- `{name}` is absent.');continue
 macros=re.findall(r'\\cite\w*\{[^}]+\}',p.read_text());lines.append(f'- [{name}]({p.resolve()}): {len(macros)} citation macros. Software URLs and provenance hashes are reproducibility evidence, not additional research-result claims.')
lines+=['','This is a complete local citation inventory with explicitly partial external verification. It does not certify every bibliography field or every cited paper’s full technical content.']
(P/'codex-citation.md').write_text('\n'.join(lines)+'\n');assert not missing
print(len(uses),len(entries),'unused',unused)
