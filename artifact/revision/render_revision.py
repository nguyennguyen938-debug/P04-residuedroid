#!/usr/bin/env python3
"""Deterministically render revision evidence; pilots never enter final tables."""
from pathlib import Path
import json,collections,statistics,math
ART=Path(__file__).resolve().parents[1];ROOT=ART/'results/revision-20261115';OUT=ART.parent/'manuscript/generated'
def load(p,default):return json.loads(p.read_text()) if p.exists() else default
def jl(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def fmt(x):return '--' if x is None else f'{x:.1f}'
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
   ts=[r['ack_ms'] for r in rs if r['mode']==mode and r['ack_ms'] is not None];cells.append(f'{statistics.median(ts):.1f} / {max(ts):.1f}' if ts else '--')
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
 data=load(FOLLOW/'matched-outcomes.json',{});rs=data.get('rows',[]);text.append(f"The analysis excludes {len(data.get('invalid_trials',[]))} failed paired trials and retains their diagnostics. Among the fixed permitted-flow controls (T3, T4 backup, T6, T7), "+', '.join(f"{names[v]} leaves {sum(r['legit_missing'] for r in rs if r['variant']==v and r['tenant'] in [3,4,6,7])}/{sum(r['legit_expected'] for r in rs if r['variant']==v and r['tenant'] in [3,4,6,7])} permitted items undelivered" for v in ['mlayer','mfence','mboth'])+'. Per-trial availability diagnostics remain in the artifact. In the separate 35-trial-per-AVD cohort, all 56 fence and 52 layered-plus-fence control-item deficits follow reboot stop callbacks and cooperative exits; no policy-block or send-failure event occurs in those affected traces. Those counts describe that cohort, not the enlarged campaign. The matched layered-early versus fence contrast and trial-level intervals are reported below.')
 contrasts=load(FOLLOW/'matched-paired-contrasts.json',[])
 for c in contrasts:
  if c['early']=='mlayer' and c['fenced']=='mfence':
   text.append(f"AVD {c['run']}: paired confirmed-violation difference (layered early minus fence) {100*c['difference']:.2f} percentage points, percentile interval [{100*c['percentile95'][0]:.2f}, {100*c['percentile95'][1]:.2f}], across {c['paired_trials']} complete paired trials.")
 text.append('Layered early checks also have no confirmed violations in these schedules; the enlarged campaign does not demonstrate a natural-schedule advantage for final placement. A zero-event percentile interval is descriptive, not a population zero-risk bound. The forced HTTP and TLS barriers isolate the narrower residual race. Unknowns remain separate from confirmed violations.')
(OUT/'revision_results.tex').write_text('\n\n'.join(text)+'\n')
acra=jl(ROOT/'acra-v4-B/trials.jsonl');conf=load(ROOT/'acra-conformance-final/conformance.json',load(ROOT/'acra-conformance-B/conformance.json',[]));m=jl(ROOT/'matomo-A/trials.jsonl');s=[]
if acra:
 s.append('In the restricted-collector embedding, '+', '.join(f"{v} delivered {sum(r['delivered'] for r in acra if r['variant']==v and r['schedule']==sc)}/{sum(1 for r in acra if r['variant']==v and r['schedule']==sc)} {sc} reports" for sc in ['disable','control'] for v in ['acra','acrafence'])+'. Reboot outcomes and report-retirement states remain in the raw log. These runs use the policy-path build (ACRA-P); the recovery-enabled build (ACRA-R) has a separate cohort.')
if acra:
 reboot=[r for r in acra if r['schedule']=='reboot'];controls=[r for r in acra if r['schedule']=='rebootctl']
 s.append(f"After reboot, {sum(r['delivered'] for r in reboot)}/{len(reboot)} disabled reports reached the receiver, while {sum('approved=1' in r.get('state_end','') for r in reboot)}/{len(reboot)} remained stored. Non-delivery here is not deletion. Reboot controls delivered {sum(r['delivered'] for r in controls)}/{len(controls)} reports; storage retirement was complete at observation-window closure in {sum('approved=0;unapproved=0' in r.get('state_end','') for r in controls)}/{len(controls)} cases.")
final=jl(ROOT/'acra-final-A/trials.jsonl');ui=load(ROOT/'acra-conformance-final/settings-contract-trace.json',[])
if final:s.append(f"Build ACRA-R's normal-path smoke run delivered {sum(r['delivered'] for r in final if r['schedule']=='control')}/{sum(r['schedule']=='control' for r in final)} allowed controls; disabled stock/fenced delivery was "+'/'.join(str(sum(r['delivered'] for r in final if r['schedule']=='disable' and r['variant']==v)) for v in ['acra','acrafence'])+'. This small smoke run does not establish lifecycle results for ACRA-R.')
if ui:s.append(f"The actual settings-button trace observed the expected acknowledgement and re-grant text in {sum(r['observed'] for r in ui)}/{len(ui)} transitions; UI hierarchies, pixels and policy events are included.")
if conf:s.append(f"The adapter/store conformance suite passed {sum(r['pass_'] for r in conf)}/{len(conf)} cases, covering collection labels, missing/malformed/future labels, withdrawal, re-grant and unavailable or migrated stores. Missing labels suppress an otherwise permitted synthetic report; the valid-label control is delivered. This is explicit availability loss, not proof that all production copies are labelled.")
if m:
 s.append(r'\paragraph{Second SDK.} The pinned Matomo 4.4 AAR~\cite{matomo} was retrieved through JitPack and executed with its real cache, packet builder and dispatcher. '+', '.join(f"{'fenced' if f else 'stock'} sent {sum(r['delivered_requests']>0 for r in m if r['fenced']==f and r['withdraw']==w)}/{sum(1 for r in m if r['fenced']==f and r['withdraw']==w)} {'withdrawn' if w else 'control'} batches" for w in [True,False] for f in [False,True])+'. The embedding promises to invalidate queued events. Its deterministic pre-send barrier isolates an in-flight dispatcher path; this does not test durable-cache recovery, HTTPS, or a production app.')
(OUT/'revision_acra.tex').write_text('\n\n'.join(s)+'\n')
h=load(ROOT/'historical-cluster-bootstrap.json',{});r=next((r for r in h.get('rows',[]) if r.get('run')=='A' and r.get('variant')=='conv'),None)
if r:(OUT/'revision_uncertainty.tex').write_text(f"Trial uncertainty uses 10,000 trial-cluster bootstrap resamples (seed 20261115), stratified by AVD and schedule. The {r['trials']} stream-wrapper AVD-A trials give a conventional-baseline authorization rate of {100*r['estimate']:.1f}\\% (percentile interval {100*r['percentile95'][0]:.1f}--{100*r['percentile95'][1]:.1f}\\%). This is not a socket-handoff rate. A zero-event percentile interval is descriptive, not a zero-risk bound. All tenants and paired variants exposed to a trial remain one resampling unit.\n")
print('revision rendered',len(rows),'socket,',len(summary),'matched groups,',len(acra),'ACRA,',len(m),'Matomo')
