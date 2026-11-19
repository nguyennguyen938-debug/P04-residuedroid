#!/usr/bin/env python3
"""B2 analysis (AirGuard stock vs fenced), fixed before the pilot/final data were looked at (b2-card.md).

Oracle (sink side, independent of the app's decisions): every donated device keeps its uniqueId 'p04-AA:00:00:00:BB:KK'
(the app clears addresses, not uniqueId); batch BB = 00 'pre' (collected before the withdrawal), 01 'optout' (collected
while opted out), 02 'post' (collected after re-consent). Per trial and variant, from the sink log of that variant's port
within the trial's host window: violation = any 'pre' or 'optout' beacon donated (all donations in this design start after
the withdrawal); deficit = 'post' beacons expected (nbeacons) minus donated.
Validity (harness fields only): no trial_error; every hook call ok; device alive at the end; both variants' event logs read.
Usage: analyze_airguard.py <run dir>... [--out results/round3/b2/analysis] [--n 20]
"""
import argparse, collections, json, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART / 'scripts'))
from summarize import wilson  # noqa: E402

BATCH = {'00': 'pre', '01': 'optout', '02': 'post'}; PORT = {'stock': 8796, 'fenced': 8797}


def validity(plan, dev):
    acts = plan['actions']
    if any(x['a'] == 'trial_error' for x in acts): return 'trial error'
    if any(x.get('ok') is False for x in acts): return 'hook failed'
    if plan.get('device_alive_end') is not True: return 'device not alive'
    if any(not dev.get((plan['trial'], v)) for v in ('stock', 'fenced')): return 'missing event log'
    return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--out', default=str(ART / 'results/round3/b2/analysis'))
    ap.add_argument('--n', type=int, default=20); a = ap.parse_args()
    rows, invalid = [], []
    for d in map(Path, a.dirs):
        meta = json.loads((d / 'meta.json').read_text()); nb = meta.get('nbeacons', 4)
        plans = [json.loads(l) for l in open(d / 'schedule.jsonl') if l.strip()]
        dev = {(x['trial'], x['variant']): x['events'] for x in (json.loads(l) for l in open(d / 'device_events.jsonl') if l.strip())}
        sink = [json.loads(l) for l in open(d / 'sink/ingest.jsonl') if l.strip()] if (d / 'sink/ingest.jsonl').exists() else []
        for plan in plans:
            why = validity(plan, dev)
            if why: invalid.append({'trial': plan['trial'], 'reason': why}); continue
            t0, t1 = plan['actions'][0]['t'], plan['actions'][-1]['t']
            for v in ('stock', 'fenced'):
                got = collections.Counter()
                for r in sink:
                    if r.get('port') != PORT[v] or r.get('path') != 'donate_data' or not (t0 <= r['t_host'] <= t1) or not r.get('complete'): continue
                    for devc in r['body'] or []:
                        uid = devc.get('uniqueId') or ''
                        b = BATCH.get(uid.split(':')[-2] if uid.startswith('p04-') else '', 'other')
                        got[b] += len(devc.get('beacons') or [])
                ev = [e['kind'] for e in dev[(plan['trial'], v)]]
                rows.append({'trial': plan['trial'], 'schedule': plan['schedule'], 'k': plan['k'], 'variant': v, 'donated': dict(got),
                             'violation': got['pre'] + got['optout'] > 0, 'deficit': max(0, nb - got['post']),
                             'blocked': 'DONATION_BLOCKED' in ev, 'error': 'DONATION_ERROR' in ev})
    cells = collections.defaultdict(list)
    for r in sorted(rows, key=lambda r: r['k']): cells[r['schedule'], r['variant']].append(r)
    out = {}
    for (s, v), rs in sorted(cells.items()):
        used = rs[:a.n]; k = sum(r['violation'] for r in used); dtr = sum(r['deficit'] > 0 for r in used)
        out[f'{s}/{v}'] = {'trials': len(used), 'unused': len(rs) - len(used), 'violating_trials': k,
                           'violating_wilson95': list(wilson(k, len(used))[1:]) if used else None, 'deficit_trials': dtr,
                           'deficit_beacons': sum(r['deficit'] for r in used), 'blocked_trials': sum(r['blocked'] for r in used),
                           'error_trials': sum(r['error'] for r in used)}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'airguard-summary.json').write_text(json.dumps({'invalid': invalid, 'cells': out, 'rows': rows}, indent=1) + '\n')
    print(f"rows {len(rows)}, invalid {len(invalid)}, cells {[(c, v['trials']) for c, v in out.items()]}")


if __name__ == '__main__':
    main()
