from pathlib import Path
import json,collections,statistics,math
A=Path(__file__).resolve().parents[1];R=A/'results/review-followup-20261115'
def fields(s):
 return dict(x.split('=',1)for x in s.split(';')if'='in x)
def pct(xs,q):
 xs=sorted(xs);return xs[min(len(xs)-1,max(0,math.ceil(q*len(xs))-1))]if xs else None
rows=[]
for cohort in ['tls-final','http-cost']:
 p=R/cohort/'trials.jsonl'
 if not p.exists():continue
 for line in p.read_text().splitlines():
  r=json.loads(line);es=r.get('events',[]);acks=[e['mono_ns']for e in es if e['kind']=='WITHDRAW_ACK'];req=[e['mono_ns']for e in es if e['kind']=='WITHDRAW_REQUEST'];accepted=[(e['mono_ns'],int(fields(e['detail'])['n']))for e in es if e['kind']=='BYTES_ACCEPTED'];done=[fields(e['detail'])for e in es if e['kind']=='SEND_OK'];config=[fields(e['detail'])for e in es if e['kind']=='SOCKET_CONFIG']
  row={'cohort':cohort,'trial':r['trial'],'case':r['case'],'block':r['block'],'harness_error':r.get('harness_error'),'successful_sends':len(done),'early_blocks':sum(e['kind']=='EARLY_BLOCK'for e in es),'policy_blocks':sum(e['kind']=='BLOCK'for e in es),'acks':len(acks),'after_ack_accepted':sum(n for t,n in accepted if acks and t>acks[0]),'accepted_before_ack':sum(n for t,n in accepted if acks and t<acks[0]),'ack_ms':(acks[0]-req[0])/1e6 if acks and req else None,'sndbuf':int(config[0]['actual_sndbuf'])if config else None,'elapsed_ms':[int(d['elapsed_ns'])/1e6 for d in done],'process_cpu_ms':[int(d['process_cpu_ms'])for d in done],'payload_bytes':[int(d['payload_bytes'])for d in done]}
  if row['case']in['buffered-fence','stall-small','stall-large']:assert row['acks']==1 and row['after_ack_accepted']==0,row
  rows.append(row)
summary=[]
for case in sorted({r['case']for r in rows}):
 rs=[r for r in rows if r['case']==case];lat=[x for r in rs for x in r['elapsed_ms']];cpu=[x for r in rs for x in r['process_cpu_ms']];ack=[r['ack_ms']for r in rs if r['ack_ms']is not None]
 summary.append({'case':case,'trials':len(rs),'harness_errors':sum(bool(r['harness_error'])for r in rs),'successful_sends':sum(r['successful_sends']for r in rs),'blocked_trials':sum(r['policy_blocks']+r['early_blocks']>0 for r in rs),'after_ack_accepted_total':sum(r['after_ack_accepted']for r in rs),'median_ms':statistics.median(lat)if lat else None,'p95_ms':pct(lat,.95),'median_cpu_ms':statistics.median(cpu)if cpu else None,'ack_p50_ms':statistics.median(ack)if ack else None,'ack_p95_ms':pct(ack,.95),'ack_max_ms':max(ack)if ack else None,'accepted_before_ack_median':statistics.median([r['accepted_before_ack']for r in rs]),'sndbuf_values':sorted({r['sndbuf']for r in rs if r['sndbuf']is not None})})
(R/'transport-summary.json').write_text(json.dumps({'rows':rows,'summary':summary,'claims':['ciphertext counts are not plaintext counts','accepted minus receiver reads is not kernel unsent bytes','process CPU is instrumented elapsed CPU, not energy','fixed 1 MiB cost excludes payload allocation; includes handshake, logging and response','concurrent latency is per request with two processes sharing one policy lock']},indent=2)+'\n')
for r in summary:print(r)
