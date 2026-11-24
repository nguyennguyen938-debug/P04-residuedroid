#!/usr/bin/env python3
"""B2 analysis (AirGuard stock vs fenced), fixed before the pilot/final data were looked at (b2-card.md).

Oracle (sink side, independent of the app's decisions): every donated device keeps its uniqueId 'p04-AA:00:00:00:BB:KK'
(the app clears addresses, not uniqueId); batch BB = 00 'pre' (collected before the withdrawal), 01 'optout' (collected
while opted out), 02 'post' (collected after re-consent). Per trial and variant, from the sink log of that variant's port
within the trial's host window. Withdrawal bracket (host clock only, pilot-2): ws = time of the harness action just before
that variant's withdraw hook was issued, we = time the hook returned (after the app's WITHDRAW_ACK). A donate request is
'before' if it completed at the sink before ws; 'after' if the ping that opened its worker run reached the sink after we
(the whole request began after the ack); otherwise 'ambiguous'. Violation = an 'optout' beacon donated (any time), or a
'pre' beacon in an 'after' request. A 'pre' beacon in an 'ambiguous' request = unknown (never folded into no-violation).
'pre' beacons donated 'before' are permitted (the app's own worker run at consent time). Deficit = nbeacons - 'post' donated.
Validity (harness fields only): no trial_error; every hook call ok; device alive at the end; both variants' event logs read.
Oracle v3 (`--order device`, post-hoc, b2-card.md "Oracle v3"): for the fenced build, a request with X-Request-ID R is ordered
against the trial's first WITHDRAW_ACK on the guest clock (wall_ms of R's BYTES_ACCEPTED n>0): 'before' / 'after' / 'straddle'
/ 'unmatched'; 'pre' in straddle/unmatched = unknown. Stock build and the default (`--order host`) are v2 unchanged.
Group 2 (g2layer-card.md): variants are read from meta.json (default stock, fenced); the layered build (port 8795) is
analysed like the others, and under `--order device` it is ordered on the guest clock like the fenced build (same transport).
Usage: analyze_airguard.py <run dir>... [--out results/round3/b2/analysis] [--n 20] [--order host|device]
"""
import argparse, collections, json, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART / 'scripts'))
from summarize import wilson  # noqa: E402

BATCH = {'00': 'pre', '01': 'optout', '02': 'post'}; PORT = {'stock': 8796, 'fenced': 8797, 'layered': 8795}


def validity(plan, dev, variants=('stock', 'fenced')):
    acts = plan['actions']
    if any(x['a'] == 'trial_error' for x in acts): return 'trial error'
    if any(x.get('ok') is False for x in acts): return 'hook failed'
    if plan.get('device_alive_end') is not True: return 'device not alive'
    if any(not dev.get((plan['trial'], v)) for v in variants): return 'missing event log'
    if any(not any(x['a'] == 'withdraw' and x.get('variant') == v for x in acts) for v in variants): return 'no withdraw action'
    if plan.get('phone'):                   # own phone / Device Farm (campaign_airguard.py --phone, 24/11): faults must be confirmed (R2.4)
        if plan['schedule'] == 'netloss' and plan.get('net_verified_down') is not True: return 'net cut not verified'
        if plan['schedule'] == 'kill' and plan.get('kill_verified') is not True: return 'kill not verified'
        if plan['schedule'] == 'reboot' and not any(x['a'] == 'boot_completed' for x in acts): return 'reboot not completed'
    return None


def guest_order(events, req):
    """Oracle v3: order request `req` against the first WITHDRAW_ACK on the guest wall clock (ms)."""
    def f(e): return dict(x.split('=', 1) for x in (e.get('detail') or '').split(';') if '=' in x)
    acks = [e['wall_ms'] for e in events if e['kind'] == 'WITHDRAW_ACK']
    acc = [e['wall_ms'] for e in events if e['kind'] == 'BYTES_ACCEPTED' and req and f(e).get('request') == req and int(f(e).get('n', 0)) > 0]
    if not acks or not acc: return 'unmatched'
    ack = min(acks)
    return 'before' if max(acc) < ack else 'after' if min(acc) > ack else 'straddle'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--out', default=str(ART / 'results/round3/b2/analysis'))
    ap.add_argument('--n', type=int, default=20); ap.add_argument('--order', choices=['host', 'device'], default='host'); a = ap.parse_args()
    rows, invalid = [], []
    for d in map(Path, a.dirs):
        meta = json.loads((d / 'meta.json').read_text()); nb = meta.get('nbeacons', 4); variants = meta.get('variants', ['stock', 'fenced'])
        plans = [json.loads(l) for l in open(d / 'schedule.jsonl') if l.strip()]
        dev = {(x['trial'], x['variant']): x['events'] for x in (json.loads(l) for l in open(d / 'device_events.jsonl') if l.strip())}
        sink = [json.loads(l) for l in open(d / 'sink/ingest.jsonl') if l.strip()] if (d / 'sink/ingest.jsonl').exists() else []
        for plan in plans:
            why = validity(plan, dev, variants)
            if why: invalid.append({'trial': plan['trial'], 'reason': why}); continue
            acts = plan['actions']; t0, t1 = acts[0]['t'], acts[-1]['t']
            for v in variants:
                i = next(j for j, x in enumerate(acts) if x['a'] == 'withdraw' and x.get('variant') == v)
                ws, we = acts[i - 1]['t'], acts[i]['t']
                mine = [r for r in sink if r.get('port') == PORT[v] and t0 <= r['t_host'] <= t1]
                got = collections.Counter()
                for r in mine:
                    if r.get('path') != 'donate_data' or not r.get('complete'): continue
                    ping = max((x['t_host'] for x in mine if x.get('path') == 'ping' and x['t_host'] <= r['t_host']), default=None)
                    when = 'before' if r['t_host'] < ws else 'after' if ping is not None and ping > we else 'ambiguous'
                    if a.order == 'device' and v in ('fenced', 'layered'): when = guest_order(dev[(plan['trial'], v)], r.get('request'))
                    for devc in r['body'] or []:
                        uid = devc.get('uniqueId') or ''
                        b = BATCH.get(uid.split(':')[-2] if uid.startswith('p04-') else '', 'other')
                        got[f'{b}/{when}'] += len(devc.get('beacons') or [])
                post = sum(n for k, n in got.items() if k.startswith('post/'))
                viol = sum(n for k, n in got.items() if k.startswith('optout/')) + got['pre/after'] > 0
                unk = got['pre/ambiguous'] + got['pre/straddle'] + got['pre/unmatched'] > 0
                ev = [e['kind'] for e in dev[(plan['trial'], v)]]
                rows.append({'trial': plan['trial'], 'schedule': plan['schedule'], 'k': plan['k'], 'variant': v, 'donated': dict(got),
                             'violation': viol, 'unknown': not viol and unk, 'deficit': max(0, nb - post),
                             'blocked': 'DONATION_BLOCKED' in ev, 'error': 'DONATION_ERROR' in ev})
    cells = collections.defaultdict(list)
    for r in sorted(rows, key=lambda r: r['k']): cells[r['schedule'], r['variant']].append(r)
    out = {}
    for (s, v), rs in sorted(cells.items()):
        used = rs[:a.n]; k = sum(r['violation'] for r in used); dtr = sum(r['deficit'] > 0 for r in used)
        out[f'{s}/{v}'] = {'trials': len(used), 'unused': len(rs) - len(used), 'violating_trials': k,
                           'violating_wilson95': list(wilson(k, len(used))[1:]) if used else None, 'deficit_trials': dtr, 'unknown_trials': sum(r['unknown'] for r in used),
                           'deficit_beacons': sum(r['deficit'] for r in used), 'blocked_trials': sum(r['blocked'] for r in used),
                           'error_trials': sum(r['error'] for r in used)}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'airguard-summary.json').write_text(json.dumps({'invalid': invalid, 'cells': out, 'rows': rows}, indent=1) + '\n')
    print(f"rows {len(rows)}, invalid {len(invalid)}, cells {[(c, v['trials']) for c, v in out.items()]}")


if __name__ == '__main__':
    main()
