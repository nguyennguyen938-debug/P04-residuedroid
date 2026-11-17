#!/usr/bin/env python3
"""Independent observation oracle. Never consult BLOCK or enforcement labels to classify sends.
Known handoffs require matching attempt + positive return. Interrupted attempts stay unknown.
No comparison of host clocks with guest clocks. Receiver confirmation is a separate fact.
"""
import collections,json,re,sys,statistics,math
from pathlib import Path

def fields(detail):return dict(p.split('=',1) for p in detail.split(';') if '=' in p)
def classify(events,withdraw_scope=1):
 request=[e for e in events if e['kind']=='WITHDRAW_REQUEST']
 durable=[e for e in events if e['kind']=='WITHDRAW_DURABLE']
 ack=[e for e in events if e['kind']=='WITHDRAW_ACK']
 # The test contract invalidates source tenant 1. Tenant 6 withdrawal is unrelated.
 a=ack[0]['mono_ns'] if ack and withdraw_scope==1 else None
 w=request[0]['mono_ns'] if request and withdraw_scope==1 else None
 attempts={};accepted=late=unknown=0
 for e in events:
  f=fields(e.get('detail',''));key=(f.get('request'),f.get('attempt'),f.get('offset'))
  if e['kind']=='WRITE_ATTEMPT':attempts[key]=e
  if e['kind']=='BYTES_ACCEPTED':
   start=attempts.pop(key,None);n=int(f.get('n',0));accepted+=n
   if not n:continue
   if start is None:unknown+=n
   elif a is not None and start['mono_ns']>a:late+=n
   elif w is not None and e['mono_ns']>=w:unknown+=n
 unknown_attempts=len(attempts)
 auth=[e for e in events if e['kind']=='AUTHORIZATION_LOGGED']
 handed=[e for e in events if e['kind']=='REQUEST_HANDED_OFF']
 attempted=[e for e in events if e['kind']=='WRITE_ATTEMPT']
 return dict(write_phase_incomplete_at_request=bool(request and (not handed or request[0]['mono_ns']<handed[0]['mono_ns'])),first_write_before_request=bool(request and attempted and attempted[0]['mono_ns']<request[0]['mono_ns']),accepted_bytes=accepted,known_after_ack_bytes=late,ambiguous_returned_bytes=unknown,
             interrupted_attempts=unknown_attempts,authorization_before_ack=bool(auth and a and auth[0]['mono_ns']<a),
             ack_ms=(ack[0]['mono_ns']-request[0]['mono_ns'])/1e6 if ack and request else None,
             acknowledged=bool(ack),send_timeout=any(e['kind']=='SEND_ERROR' and ('deadline' in e.get('detail','').lower() or 'timeout' in e.get('detail','').lower()) for e in events),measurement_unknown=bool(unknown or unknown_attempts))

def main():
 root=Path(sys.argv[1]);rows=[]
 for p in sorted(root.glob('socket-*/trials.jsonl')):
  observed=collections.defaultdict(list)
  receiver=p.parent/'receiver.jsonl'
  if receiver.exists():
   for line in receiver.read_text().splitlines():
    e=json.loads(line)
    if e.get('request'):observed[e['request']].append(e)
  for line in p.read_text().splitlines():
   r=json.loads(line);events=[e for e in r.get('events',[]) if e['trial']==r['trial']]
   obs=observed[r['trial']]
   rows.append({k:r.get(k) for k in ['trial','serial','block','group','mode','load','remote','tenant','fault','label','barrier_seen','harness_error','withdraw_command_ms']}|classify(events,r.get('tenant',1))|dict(receiver_body_prefix=max([e.get('received_body',0) for e in obs] or [0]),receiver_complete=any(e['event']=='complete_request' for e in obs)))
 for row in rows:
  row['measurement_unknown'] = row['measurement_unknown'] or not row['barrier_seen'] or bool(row['harness_error']) or row['receiver_body_prefix']>row['accepted_bytes']
 (root/'socket-outcomes.json').write_text(json.dumps(rows,indent=2)+'\n')
 summary=[];groups=collections.defaultdict(list)
 for r in rows:groups[tuple(r.get(k) for k in ['group','mode','load','remote','tenant','fault','label'])].append(r)
 for key,rs in sorted(groups.items(),key=lambda x:str(x[0])):
  times=sorted(r['ack_ms'] for r in rs if r['ack_ms'] is not None)
  host=sorted(r['withdraw_command_ms'] for r in rs if r.get('withdraw_command_ms') is not None)
  summary.append(dict(zip(['group','mode','load','remote','tenant','fault','label'],key))|dict(n=len(rs),write_phase_incomplete_at_request=sum(r['write_phase_incomplete_at_request'] for r in rs),first_write_before_request=sum(r['first_write_before_request'] for r in rs),barriers=sum(bool(r['barrier_seen']) for r in rs),harness_errors=sum(bool(r['harness_error']) for r in rs),
    known_late=sum(r['known_after_ack_bytes']>0 for r in rs),unknown=sum(r['measurement_unknown'] for r in rs),acks=len(times),send_timeouts=sum(r['send_timeout'] for r in rs),
    median_ms=statistics.median(times) if times else None,p95_ms=times[max(0,math.ceil(.95*len(times))-1)] if times else None,max_ms=max(times) if times else None,
    command_median_ms=statistics.median(host) if host else None,command_p95_ms=host[max(0,math.ceil(.95*len(host))-1)] if host else None,command_max_ms=max(host) if host else None))
 (root/'socket-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 per_avd=[]
 for serial in sorted({r['serial'] for r in rows}):
  for key,rs in sorted(groups.items(),key=lambda x:str(x[0])):
   rs=[r for r in rs if r['serial']==serial]
   if not rs:continue
   times=sorted(r['ack_ms'] for r in rs if r['ack_ms'] is not None)
   host=sorted(r['withdraw_command_ms'] for r in rs if r.get('withdraw_command_ms') is not None)
   per_avd.append(dict(zip(['group','mode','load','remote','tenant','fault','label'],key))|dict(serial=serial,n=len(rs),write_phase_incomplete_at_request=sum(r['write_phase_incomplete_at_request'] for r in rs),first_write_before_request=sum(r['first_write_before_request'] for r in rs),acks=len(times),send_timeouts=sum(r['send_timeout'] for r in rs),unknown=sum(r['measurement_unknown'] for r in rs),median_ms=statistics.median(times) if times else None,p95_ms=times[max(0,math.ceil(.95*len(times))-1)] if times else None,max_ms=max(times) if times else None,command_median_ms=statistics.median(host) if host else None,command_p95_ms=host[max(0,math.ceil(.95*len(host))-1)] if host else None,command_max_ms=max(host) if host else None))
 (root/'socket-summary-by-avd.json').write_text(json.dumps(per_avd,indent=2)+'\n');print('socket trials',len(rows))

if __name__=='__main__':main()
