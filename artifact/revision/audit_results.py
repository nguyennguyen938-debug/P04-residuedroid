#!/usr/bin/env python3
"""Read-only consistency audit plus generated revision evidence summary."""
from pathlib import Path
import collections, json, statistics
ROOT = Path(__file__).resolve().parents[1]/'results/revision-20261115'
def jl(p): return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
def load(p, default): return json.loads(p.read_text()) if p.exists() else default
raw = [r for p in sorted(ROOT.glob('socket-*/trials.jsonl')) for r in jl(p)]
receipts = [r for p in sorted(ROOT.glob('socket-*/receiver.jsonl')) for r in jl(p)]
print('receiver files', [str(p.relative_to(ROOT)) for p in ROOT.glob('socket-*/*jsonl')])
by_request = collections.defaultdict(list)
for r in receipts:
    if r.get('request'): by_request[r['request']].append(r)
def events(r, suffix=''): return [e for e in r.get('events',[]) if e['trial']==r['trial']+suffix]
def kinds(r,suffix=''): return [e['kind'] for e in events(r,suffix)]
crashes=[];labels=[];process=[]
for r in raw:
    obs=by_request[r['trial']]
    if r['group']=='crash':
        crashes.append(dict(trial=r['trial'],fault=r['fault'],barrier=r.get('barrier_seen'),
            receiver_prefix=max([e.get('received_body',0) for e in obs] or [0]),
            receiver_complete=any(e['event']=='complete_request' for e in obs),
            retry_blocked='EARLY_BLOCK' in kinds(r,'-retry'),old_epoch_blocked='EARLY_BLOCK' in kinds(r,'-old'),
            new_epoch_send_ok='SEND_OK' in kinds(r,'-new'),
            new_epoch_received=any(e['event']=='complete_request' for e in by_request[r['trial']+'-new'])))
    if r['group']=='labels':
        labels.append(dict(trial=r['trial'],label=r['label'],blocked='EARLY_BLOCK' in kinds(r),
            send_ok='SEND_OK' in kinds(r),receiver_complete=any(e['event']=='complete_request' for e in obs)))
    if r['group']=='backpressure':
        writes={e['pid'] for e in events(r) if e['kind']=='AUTHORIZATION_LOGGED'}
        withdrawals={e['pid'] for e in events(r) if e['kind']=='WITHDRAW_REQUEST'}
        process.append(dict(trial=r['trial'],remote=r['remote'],observed=bool(writes and withdrawals),
            matches=bool(writes and withdrawals) and (writes.isdisjoint(withdrawals)==r['remote'])))
matched=load(ROOT/'matched-outcomes.json',{});groups=collections.Counter((r['run'],r['trial'],r['variant']) for r in matched.get('rows',[]))
acra=jl(ROOT/'acra-v4-B/trials.jsonl');acra_summary=[]
for variant,schedule in sorted({(r['variant'],r['schedule']) for r in acra}):
    rs=[r for r in acra if (r['variant'],r['schedule'])==(variant,schedule)]
    acra_summary.append(dict(variant=variant,schedule=schedule,n=len(rs),delivered=sum(r['delivered'] for r in rs),
        retired=sum('approved=0;unapproved=0' in r.get('state_end','') for r in rs),
        queued_before=sum('approved=1' in r.get('state_after_crash','') for r in rs)))
summary=dict(socket_attempts=len(raw),unique_socket_ids=len({r['trial'] for r in raw}),
    socket_blocks={s:dict(collections.Counter(str(r['block']) for r in raw if r['serial']==s)) for s in sorted({r['serial'] for r in raw})},
    socket_harness_errors=[dict(trial=r['trial'],error=r['harness_error']) for r in raw if r.get('harness_error')],
    socket_barrier_failures=[r['trial'] for r in raw if not r.get('barrier_seen')],
    process_cases=len(process),process_mismatches=[r for r in process if not r['matches']],
    crashes=crashes,labels=labels,matched_invalid=matched.get('invalid_trials',[]),
    matched_incomplete_tenant_groups=[list(k)+[n] for k,n in groups.items() if n!=8],
    acra_lifecycle=acra_summary,acra_final_smoke=jl(ROOT/'acra-final-A/trials.jsonl'),
    acra_conformance=load(ROOT/'acra-conformance-final/conformance.json',[]),
    acra_ui_trace=load(ROOT/'acra-conformance-final/settings-contract-trace.json',[]),
    matomo_attempts=len(jl(ROOT/'matomo-A/trials.jsonl')),
    matomo_failures=[r['trial'] for r in jl(ROOT/'matomo-A/trials.jsonl') if not r['pass']])
(ROOT/'evidence-audit.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['crashes','labels','acra_final_smoke','acra_conformance','acra_ui_trace']},indent=2))
