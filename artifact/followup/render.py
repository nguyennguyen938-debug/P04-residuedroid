from pathlib import Path
import json,csv,collections,statistics
A=Path(__file__).resolve().parents[1];P=A.parent;R=A/'results/review-followup-20261115';G=P/'manuscript/generated'
def first50(variant):  # AVD A, first 50 valid trials per schedule, as the stream-wrapper analysis
 rs=[r for r in csv.DictReader((A/'results/outcomes.csv').open()) if r['valid']=='1'and r['run']=='A'and r['variant']==variant];ks=collections.defaultdict(set)
 for r in rs:ks[r['schedule']].add(int(r['k']))
 keep={s:set(sorted(x)[:50])for s,x in ks.items()};return [r for r in rs if int(r['k'])in keep[r['schedule']]]
# Round-4 review (R3): conv's T5 failures are net-loss retries (conv purges T5's outbox on withdrawal), so the epoch row
# shows job-start outside net, whose boolean start check is what misses the epoch.
lines=[r'\begin{table}[t]\centering\mtab',r'\caption{Conventional-check failures by mechanism (AVD~A): violating tenant-trials/total, stream-wrapper authorization estimand. The epoch row uses \vname{jobstart} outside \textsf{net}, because \vname{conv} purges the outbox of T5 on withdrawal and its T5 failures in \textsf{net} are retries. The selected fixture mix determines these rates.}\label{tab:mechanisms}',r'\begin{tabular}{@{}llr@{}}\toprule\mhead Mechanism & Variant, tenant, schedules & Trials\\\midrule']
for variant,tenant,label,schedules in [('conv',1,'Lineage','all'),('jobstart',5,'Epoch after re-grant','all but net'),('conv',8,'Retry check','net')]:
 xs=[r for r in first50(variant) if int(r['tenant'])==tenant and{'all':True,'net':r['schedule']=='netloss','all but net':r['schedule']!='netloss'}[schedules]]
 lines.append(rf'{label} & \vname{{{variant}}}, T{tenant}, {schedules} & {sum(int(r["violation"])for r in xs)}/{len(xs)} '+r'\\')
lines+=[r'\bottomrule\end{tabular}\end{table}'];(G/'followup_mechanisms.tex').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
(G/'followup_support.tex').write_text(r'''\paragraph{Supporting checks.} The stream-wrapper substrate tests include \subWorkManagerLogged{} WorkManager attempts (\subWorkManagerInvalid{} invalid) and \subAlarmManagerLogged{} AlarmManager attempts, with no prohibited authorizations for the fenced mediated paths. Across \crashKills{} process kills, atomic row labels leave \crashOrphA{} unlabelled rows, compared with \crashOrphB{} when data and labels are written separately. The authorization-window prediction agrees in \predAgree{} of \predN{} cases. Stream-wrapper per-submit medians of \eeNoneMs{} and \eeRdMs{}\,ms apply only to that wrapper; they are not the cost of the 4\,KiB channel transport measured in \S\ref{sec:revision}.
''',encoding='utf-8',newline='\n')
s=json.loads((R/'transport-summary.json').read_text());by={x['case']:x for x in s['summary']}
lines=[r'\paragraph{HTTPS buffering and labels.} A separate Android~15 emulator runs TLS~1.2 over \texttt{SSLEngine} and \texttt{SocketChannel}. Each of eleven conditions has 20 trials. With withdrawal after the first encryption step but before its first socket write, the early-check arm completes 20/20 requests; the fenced arm blocks 20/20 and accepts zero application ciphertext after acknowledgement. The barrier isolates a possible interleaving; it is not a natural-schedule frequency estimate. With a syntactically valid label that deliberately omits the withdrawn source of a derived value, 20/20 requests pass; complete labels block 20/20. Malformed labels also block 20/20. Thus fail-closed validation cannot discover omitted provenance. A mixed-source request is blocked as a whole in 20/20 trials, suppressing its allowed contribution along with the forbidden one.']
# C 24/11: the cost table and its paragraph move to the appendix (followup_transport_cost.tex) to keep the body at 12 pages.
cost=[r'\begin{table}[t]\centering\mtab',r'\caption{Instrumented 1\,MiB uploads: median elapsed ms/MiB and process CPU ms/MiB on one Android~15 emulator. Twenty trials per cell; concurrent rows have two processes per trial. Handshake, logging and response are included; payload allocation is excluded.}\label{tab:transport-cost}',r'\begin{tabular}{@{}lrr@{}}\toprule\mhead Transport / policy & Elapsed & CPU\\\midrule']
for k,label in [('http-early','HTTP / early'),('http-control','HTTP / fence'),('http-concurrent','HTTP / two fences'),('early','TLS / early'),('control','TLS / fence'),('concurrent','TLS / two fences')]:
 r=by[k];assert r['trials']==20 and r['harness_errors']==0
 cost.append(f'{label} & {r["median_ms"]:.1f} & {r["median_cpu_ms"]:.1f} '+r'\\')
cost+=[r'\bottomrule\end{tabular}\end{table}',r'\paragraph{Transport cost on an emulator.} Table~\ref{tab:transport-cost} measures the implemented chunk path, with a matched early-check transport. Cells run in fixed block order on a shared host, so lower measured latency is not evidence that fencing accelerates uploads. Two-process cells include contention for the same policy lock. These CPU observations are not physical energy measurements.']
lines.append(r'With a stalled receiver, how much ciphertext the socket accepted before acknowledgement depends on the send buffer; neither buffer setting accepted application bytes after acknowledgement (Appendix~\ref{app:socket}).')
res=[]  # stalled-receiver residue details: Appendix app:socket (followup_residue.tex)
for k in ['stall-small','stall-large']:
 r=by[k];res.append(f'With a stalled TLS receiver and an actual send buffer of {r["sndbuf_values"][0]} bytes, median ciphertext accepted before withdrawal acknowledgement is {r["accepted_before_ack_median"]:.0f} bytes; acknowledgement p95/max is {r["ack_p95_ms"]:.2f}/{r["ack_max_ms"]:.2f}\\,ms (20 trials).')
res.append(r'Neither setting accepts application bytes after acknowledgement. Accepted ciphertext can already reside at the peer or in TLS/TCP buffers: it is not a measurement of bytes still unsent by the kernel. The post-acknowledgement kernel snapshots are delayed observations; an exact unsent-at-ack count remains unmeasured. Shrinking the send buffer reduces observed accepted exposure in this schedule, but cannot guarantee recall.')
(G/'followup_transport.tex').write_text('\n\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
(G/'followup_transport_cost.tex').write_text('\n\n'.join(cost)+'\n',encoding='utf-8',newline='\n')
(G/'followup_residue.tex').write_text('\n\n'.join(res)+'\n',encoding='utf-8',newline='\n')
