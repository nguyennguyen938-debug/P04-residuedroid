#!/usr/bin/env python3
"""Deterministically render revision evidence; pilots never enter final tables."""
from pathlib import Path
import json,collections,statistics,math
ART=Path(__file__).resolve().parents[1];ROOT=ART/'results/revision-20261115';OUT=ART.parent/'manuscript/generated'
def load(p,default):return json.loads(p.read_text()) if p.exists() else default
def jl(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def fmt(x):return 'n/a' if x is None else f'{x:.1f}'
rows=load(ROOT/'socket-outcomes.json',[])
text=[r'''The channel protocol records authorization, each write attempt, its returned byte count,
complete receiver requests, and response receipt separately. A five-second operation deadline
bounds intended waits; a thirty-second harness watchdog detects stuck commands. It is not a
hard Android scheduling or storage bound. Controlled barriers test authorization-before-withdrawal
followed by writing, and process death after logging, after a positive prefix, after a native
write but before its count is logged, and before response receipt. Retries retain source epochs.
Pilots with a serialized broadcast queue or an incorrectly broad comparator lock are excluded.
The comparator in the final runs holds the same coordinator only over the write phase; both
variants connect and wait for responses outside it.''']
if rows:
 order=[r for r in rows if r['group']=='ordering'];early=[r for r in order if r['mode']=='early'];fence=[r for r in order if r['mode']=='fence']
 text.append(f"The forced ordering test produced confirmed post-acknowledgement byte acceptance in {sum(r['known_after_ack_bytes']>0 for r in early)}/{len(early)} early-check attempts, versus {sum(r['known_after_ack_bytes']>0 for r in fence)}/{len(fence)} fenced attempts. The authorization marker preceded acknowledgement in these early-check races, exposing handoffs that the stream-wrapper authorization-marker estimand would miss. This forced schedule does not estimate its natural frequency.")
 crash=[r for r in rows if r['group']=='crash'];unlogged=[r for r in crash if r['fault']=='unlogged']
 text.append(f"There were {len(crash)} crash-point attempts. In the {len(unlogged)} native-return-before-log cases, {sum(r['measurement_unknown'] for r in unlogged)} retained unknown handoff counts; absence of a count was never converted to zero. Receiver prefix logs, restart ordering, collection-epoch retry and re-grant outcomes are preserved separately.")
 text.append(r'''\begin{table}[t]\centering
\caption{Device-policy acknowledgement under backpressure, ms: median / observed maximum (acknowledged samples). W: whole-write lock; C: per-chunk fence. Both include same/unrelated scopes and same/cross-process cases. Timeouts remain separate.}
\label{tab:revision-latency}\mtab
\begin{tabular}{@{}lrrr@{}}\toprule\mhead Load & W & C & Ack./attempts\\\midrule''')
 for loadname in ['normal','slow','stalled','response','long']:
  rs=[r for r in rows if r['group']=='backpressure' and r['load']==loadname];cells=[]
  for mode in ['whole','fence']:
   ts=[r['ack_ms'] for r in rs if r['mode']==mode and r['ack_ms'] is not None];cells.append(f'{statistics.median(ts):.1f} / {max(ts):.1f}' if ts else 'n/a')
  text.append(f"{loadname} & {' & '.join(cells)} & {sum(r['acknowledged'] for r in rs)}/{len(rs)} \\\\")
 text.append(r'\bottomrule\end{tabular}\end{table}')
 bp=[r for r in rows if r['group']=='backpressure'];unrelated=[r['ack_ms'] for r in bp if r['tenant']==6 and r['mode']=='fence' and r['ack_ms'] is not None]
 text.append(f"Table~\\ref{{tab:revision-latency}} summarizes {len(bp)} backpressure attempts. Slow and stalled receivers use 8 MiB requests; the long-batch case uses 1 MiB. The largest observed unrelated-scope delay with chunk fencing was {fmt(max(unrelated) if unrelated else None)} ms. There were {sum(r.get('send_timeout',False) for r in bp)} sender deadline expirations and {sum(not r['acknowledged'] for r in bp)} attempts without withdrawal acknowledgement. Another {sum(r['measurement_unknown'] for r in bp)} attempts retain ambiguous acceptance ordering within the request-to-acknowledgement interval; they are not counted as clean outcomes. The separate ADB command round-trip includes process startup and IPC; it is recorded on one host clock, not mixed with guest timestamps. Per-cell empirical tails and all failures are in the artifact. Fast requests may finish writing before withdrawal; phase-coverage counts accompany the raw observations. Timing includes in-lock instrumentation. The fixed cell order, shared host and different renderer phases limit generalization. Small cell counts do not establish a population p99; any unacknowledged operation is reported as such rather than omitted from the denominator.")
else:text.append('Socket measurements are not yet available in the final-run directories.')
FOLLOW=ART/'results/review-followup-20261115'
summary=load(FOLLOW/'matched-summary.json',[])
if summary:
 verified=load(FOLLOW/'matched-outcomes.json',{})
 counts=collections.Counter((r['run'],r['schedule']) for r in verified['rows'] if r['variant']=='mlayer' and r['tenant']==1)
 assert len(counts)==14 and set(counts.values())=={20}, counts
 assert all(r['trials']==140 for r in summary), summary
 text.append(r'''\paragraph{Matched metadata.} Five variants share durable lineage, epochs, copied job extras
and the same HTTP transport. Each of seven schedules has 20 valid trials per AVD configuration (140 per configuration), with all five variants paired in each trial. Four read-only instances per configuration run disjoint seeded trial ranges on the same host; these are not independent devices. Table~\ref{tab:matched}
reports confirmed violations and ambiguous requests separately; neither unknowns nor delivery deficits
are counted as successful suppression. Tenants within each trial remain paired in uncertainty analysis.
\begin{table}[t]\centering\caption{Matched-metadata results. TT: affected tenant-trials; V: confirmed violating TT; U: requests with unknown handoff/content evidence. Counts aggregate two AVD configurations; uncertainty resamples complete paired trials within configuration, schedule and instance. All instances use the host renderer with Vulkan disabled.}
\label{tab:matched}\mtab
\begin{tabular}{@{}lrrr@{}}\toprule\mhead Variant & TT & V & U\\\midrule''')
 names={'menqueue':'enqueue','mstart':'job start','mlayer':'layered early','mfence':'chunk fence','mboth':'layered + fence'}
 for v in names:
  rs=[r for r in summary if r['variant']==v];_kv=sum(r['known_violations'] for r in rs);_kc=(r'\mgood{%d}' if _kv==0 else r'\mbad{%d}')%_kv;text.append(f"{names[v]} & {sum(r['tenant_trials'] for r in rs)} & {_kc} & {sum(r['unknown_requests'] for r in rs)} \\\\")
 text.append(r'\bottomrule\end{tabular}\end{table}')
 data=load(FOLLOW/'matched-outcomes.json',{});rs=data.get('rows',[]);text.append(f"The analysis excludes {len(data.get('invalid_trials',[]))} failed paired trials and retains their diagnostics. Among the fixed permitted-flow controls (T3, T4 backup, T6, T7), "+', '.join(f"{names[v]} leaves {sum(r['legit_missing'] for r in rs if r['variant']==v and r['tenant'] in [3,4,6,7])}/{sum(r['legit_expected'] for r in rs if r['variant']==v and r['tenant'] in [3,4,6,7])} permitted items undelivered" for v in ['mlayer','mfence','mboth'])+'.')
 dc=load(FOLLOW/'permitted-deficit-causes.json',{});app=[]  # app: detail paragraphs for Appendix app:matched-trials
 if dc and set(dc['causes'])=={'stopped_no_restart'} and set(dc['schedules'])=={'reboot'}:
  bv=dc['by_variant'];w=dc['window_after_boot_s']
  text[-1]+=f" All {dc['items']} such items across the five variants come from reboot trials in which JobScheduler stopped an upload at shutdown and the fixture declined rescheduling; no affected trace shows a policy block or send failure (Appendix~\\ref{{app:matched-trials}})."
  app.append(f"\\paragraph{{Permitted-flow deficits.}} Across all five variants, the {dc['items']} undelivered permitted items lie in {dc['tenant_trials']} reboot tenant-trials. In each, JobScheduler stopped a running upload at shutdown (connectivity stop reason), the worker exited at a batch boundary, the fixture's stop callback declines rescheduling, and the app process did not restart before the observation window closed (median {w['median']:.0f}\\,s after boot completion). No affected trace contains a policy block, a send failure, or a skip or cancellation of the stopped job. The variants differ only in how many permitted jobs were mid-upload at shutdown ("+', '.join(f"{names[v]} {bv[v]['tenant_trials']}" for v in ['mlayer','mstart','mfence','mboth','menqueue'])+f" of {bv['mlayer']['reboot_tenant_trials']} reboot tenant-trials each). We attribute these deficits to the fixture's reboot handling, not to check placement.")
 else:text.append('Per-trial availability diagnostics remain in the artifact.')
 text.append('The matched layered-early versus fence contrast and trial-level intervals are reported below.')
 contrasts=load(FOLLOW/'matched-paired-contrasts.json',[])
 for c in contrasts:
  if c['early']=='mlayer' and c['fenced']=='mfence':
   text.append(f"AVD {c['run']}: paired confirmed-violation difference (layered early minus fence) {100*c['difference']:.2f} percentage points, percentile interval [{100*c['percentile95'][0]:.2f}, {100*c['percentile95'][1]:.2f}], across {c['paired_trials']} complete paired trials.")
 text.append('Layered early checks also have no confirmed violations in these schedules; the enlarged campaign does not demonstrate a natural-schedule advantage for final placement. A zero-event percentile interval is descriptive, not a population zero-risk bound. The forced HTTP and TLS barriers isolate the narrower residual race. Unknowns remain separate from confirmed violations.')
 # Trial level: a trial counts once if any affected tenant (T1, T2, T4, T5, T8) has a confirmed violation (V) or an unknown request (U).
 tl=collections.defaultdict(lambda:[0,0]);usched=collections.Counter()
 for r in rs:
  if r['tenant'] in [1,2,4,5,8]:
   k=(r['variant'],r['instance'],r['trial']);tl[k][0]|=r['violation']>0;tl[k][1]|=r['unknown_requests']>0
   if r['unknown_requests']:usched[r['variant'],r['schedule']]+=1
 def upper(k,n,a=0.05):
  # One-sided exact (Clopper-Pearson) upper bound: largest p with P(X<=k | n,p) >= a.
  lo,hi=0.0,1.0
  for _ in range(60):
   p=(lo+hi)/2;cdf=sum(math.comb(n,i)*p**i*(1-p)**(n-i) for i in range(k+1));lo,hi=(p,hi) if cdf>=a else (lo,p)
  return 100*lo
 trow={}
 for v in names:
  ts=[x for k,x in tl.items() if k[0]==v];n=len(ts);V=sum(a for a,_ in ts);U=sum(b for _,b in ts);VU=sum(a or b for a,b in ts);trow[v]=(n,V,U,VU,upper(V,n),upper(VU,n))
 tt=[r'''\begin{table}[h]\centering
\caption{Matched campaign at trial level. A paired trial counts once if any affected tenant has a confirmed violation (V) or a request with unknown handoff/content evidence (U). Bounds are one-sided exact 95\% upper bounds, in \%, and assume independent trials; the trials share one host and two AVD configurations.}
\label{tab:matched-trials}\mtab
\begin{tabular}{@{}lrrrrrr@{}}\toprule\mhead Variant & Trials & V & U & V or U & Bound V & Bound V or U\\\midrule''']
 for v,(n,V,U,VU,bV,bVU) in trow.items():tt.append(f"{names[v]} & {n} & {V} & {U} & {VU} & {bV:.1f} & {bVU:.1f} \\\\")
 tt.append(r'\bottomrule\end{tabular}\end{table}')
 z=[v for v in ['mlayer','mfence','mboth'] if trow[v][1]==0];zs={s for (v,s) in usched if v in z}
 andj=lambda xs:', '.join(xs[:-1])+' and '+xs[-1] if len(xs)>1 else xs[0]
 if z:text.append(f"At the trial level, "+andj([names[v] for v in z])+f" have no confirmed violation in {trow[z[0]][0]} paired trials each; counting unknowns as violations, the one-sided 95\\% bounds stay at or below {max(trow[v][5] for v in z):.1f}\\% if trials were independent (Appendix~\\ref{{app:matched-trials}}).")
 if z:app.append(f"\\paragraph{{Trial level.}} In Table~\\ref{{tab:matched-trials}}, "+andj([names[v] for v in z])+f" have no trial with a confirmed violation among {trow[z[0]][0]} paired trials each; if trials were independent, the one-sided 95\\% upper bound on the violating-trial rate would be {trow[z[0]][4]:.1f}\\%. Counting every trial with an unknown request as violating gives bounds of "+andj([f"{trow[v][5]:.1f}\\%" for v in z])+', respectively. '+('All unknown requests in these variants occur in the in-flight schedule.' if zs=={'inflight'} else 'Unknown requests in these variants occur in the '+andj(sorted(zs))+' schedules.')+f" Enqueue-time and job-start checks have confirmed violations in {trow['menqueue'][1]} and {trow['mstart'][1]} of {trow['menqueue'][0]} trials.")
 (OUT/'followup_trials.tex').write_text('\n'.join(tt)+'\n\n'+'\n\n'.join(app)+'\n',encoding='utf-8',newline='\n')
(OUT/'revision_results.tex').write_text('\n\n'.join(text)+'\n',encoding='utf-8',newline='\n')
acra=jl(ROOT/'acra-v4-B/trials.jsonl');conf=load(ROOT/'acra-conformance-final/conformance.json',load(ROOT/'acra-conformance-B/conformance.json',[]));m=jl(ROOT/'matomo-A/trials.jsonl');s=[]
if acra:
 c=lambda v,sc:f"{sum(r['delivered'] for r in acra if r['variant']==v and r['schedule']==sc)}/{sum(1 for r in acra if r['variant']==v and r['schedule']==sc)}"
 s.append(f"In the restricted-collector embedding, stock ACRA delivered {c('acra','disable')} reports after reporting was disabled, while the fenced build delivered {c('acrafence','disable')}; for control reports, the stock and fenced builds delivered {c('acra','control')} and {c('acrafence','control')}."+' Reboot outcomes and report-retirement states remain in the raw log. These runs use the policy-path build (ACRA-P); the recovery-enabled build (ACRA-R) has a separate cohort.')
if acra:
 reboot=[r for r in acra if r['schedule']=='reboot'];controls=[r for r in acra if r['schedule']=='rebootctl']
 s.append(f"After reboot, {sum(r['delivered'] for r in reboot)}/{len(reboot)} disabled reports reached the receiver, while {sum('approved=1' in r.get('state_end','') for r in reboot)}/{len(reboot)} remained stored. Non-delivery here is not deletion. Reboot controls delivered {sum(r['delivered'] for r in controls)}/{len(controls)} reports; storage retirement was complete at observation-window closure in {sum('approved=0;unapproved=0' in r.get('state_end','') for r in controls)}/{len(controls)} cases.")
final=jl(ROOT/'acra-final-A/trials.jsonl');ui=load(ROOT/'acra-conformance-final/settings-contract-trace.json',[])
if final:
 d=lambda v:sum(r['delivered'] for r in final if r['schedule']=='disable' and r['variant']==v)
 s.append(f"Build ACRA-R's normal-path smoke run delivered {sum(r['delivered'] for r in final if r['schedule']=='control')}/{sum(r['schedule']=='control' for r in final)} allowed controls; with reporting disabled, the stock and fenced builds delivered {d('acra')} and {d('acrafence')} reports."+' This small smoke run does not establish lifecycle results for ACRA-R.')
if ui:s.append(f"The actual settings-button trace observed the expected acknowledgement and re-grant text in {sum(r['observed'] for r in ui)}/{len(ui)} transitions; UI hierarchies, pixels and policy events are included.")
if conf:s.append(f"The adapter/store conformance suite passed {sum(r['pass_'] for r in conf)}/{len(conf)} cases, covering collection labels, missing/malformed/future labels, withdrawal, re-grant and unavailable or migrated stores. Missing labels suppress an otherwise permitted synthetic report; the valid-label control is delivered. This is explicit availability loss, not proof that all production copies are labelled.")
if m:
 b=lambda f,w:f"{sum(r['delivered_requests']>0 for r in m if r['fenced']==f and r['withdraw']==w)}/{sum(1 for r in m if r['fenced']==f and r['withdraw']==w)}"
 s.append(r'\paragraph{Second SDK.} The pinned Matomo 4.4 AAR~\cite{matomo} was retrieved through JitPack and executed with its real cache, packet builder and dispatcher. '+f"After withdrawal, the stock build sent {b(False,True)} batches and the fenced build sent {b(True,True)}; for control batches, the stock and fenced builds sent {b(False,False)} and {b(True,False)}."+' The embedding promises to invalidate queued events. Its deterministic pre-send barrier isolates an in-flight dispatcher path; this does not test durable-cache recovery, HTTPS, or a production app.')
(OUT/'revision_acra.tex').write_text('\n\n'.join(s)+'\n',encoding='utf-8',newline='\n')
h=load(ROOT/'historical-cluster-bootstrap.json',{});r=next((r for r in h.get('rows',[]) if r.get('run')=='A' and r.get('variant')=='conv'),None)
if r:(OUT/'revision_uncertainty.tex').write_text(f"Trial uncertainty uses 10,000 trial-cluster bootstrap resamples (seed 20261115), stratified by AVD and schedule. The {r['trials']} stream-wrapper AVD-A trials give a conventional-baseline authorization rate of {100*r['estimate']:.1f}\\% (percentile interval [{100*r['percentile95'][0]:.1f}\\%, {100*r['percentile95'][1]:.1f}\\%]). This is not a socket-handoff rate. A zero-event percentile interval is descriptive, not a zero-risk bound. All tenants and paired variants exposed to a trial remain one resampling unit.\n",encoding='utf-8',newline='\n')
print('revision rendered',len(rows),'socket,',len(summary),'matched groups,',len(acra),'ACRA,',len(m),'Matomo')
