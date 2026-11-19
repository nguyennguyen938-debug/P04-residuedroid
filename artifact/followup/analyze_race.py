#!/usr/bin/env python3
"""Test 1 (B10) analysis, fixed before the final run (artifact/plans/b10-card.md §3–4).

Trial validity (harness fields only): no harness_error; the withdrawal broadcast was sent; the app logged an end event
(SEND_OK / SEND_ERROR / EARLY_BLOCK) and a WITHDRAW_ACK. Invalid trials are listed by reason and never analysed.
Violation (oracle as followup/analyze_tls.py): BYTES_ACCEPTED with n > 0 after the first WITHDRAW_ACK (device monotonic
clock; host and device clocks are never mixed).
Eq. 2 prediction (Theorem race, single withdrawal W uniform over the upload window [0, D] of the cell): for a trial,
p = clip((c_k - q) / D, 0, 1) with q = the first transport event of the send (SOCKET_CONFIG, the check precedes it) and
c_k = the last BYTES_ACCEPTED with n > 0, both device time, D = calibrated upload time of the cell. Predicted rate =
mean p over the analysed early trials; compared with the observed early violation rate (racePredPct / raceObsPct).
Keys (render_tests.py SCHEMA): raceTrials, race{Edge,Threeg,Lte}{Layer,Fence}, racePredPct, raceObsPct.
Usage: analyze_race.py <final run dir> [more dirs] [--out results/round3/b10/analysis] [--n 30]
"""
import argparse, collections, json, os, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART / 'scripts'))
from summarize import wilson  # noqa: E402

KEY = {'edge': 'Edge', 'umts': 'Threeg', 'lte': 'Lte'}


def fields(s):
    return dict(x.split('=', 1) for x in (s or '').split(';') if '=' in x)


def validity(r):
    if r.get('harness_error'): return 'harness error'
    if 'withdraw' not in r: return 'withdrawal not sent'
    ev = [e for e in r.get('events', []) if e.get('trial') == r['trial']]
    if not any(e['kind'] in ('SEND_OK', 'SEND_ERROR', 'EARLY_BLOCK') for e in ev): return 'no end event'
    if not any(e['kind'] == 'WITHDRAW_ACK' for e in ev): return 'no withdrawal ack'
    return None


def measures(r):
    ev = [e for e in r['events'] if e.get('trial') == r['trial']]
    ack = min(e['mono_ns'] for e in ev if e['kind'] == 'WITHDRAW_ACK')
    acc = [(e['mono_ns'], int(fields(e['detail']).get('n', 0))) for e in ev if e['kind'] == 'BYTES_ACCEPTED']
    after = sum(n for t, n in acc if t > ack)
    starts = [e['mono_ns'] for e in ev if e['kind'] == 'SOCKET_CONFIG']
    last = max([t for t, n in acc if n > 0], default=None)
    p = None
    if starts and last is not None and r.get('D_s'):
        p = min(1.0, max(0.0, (last - starts[0]) / 1e9 / r['D_s']))
    return {'violation': after > 0, 'after_ack_bytes': after, 'p_eq2': p,
            'end': next((e['kind'] for e in ev if e['kind'] in ('SEND_OK', 'SEND_ERROR', 'EARLY_BLOCK')), None)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--out', default=str(ART / 'results/round3/b10/analysis'))
    ap.add_argument('--n', type=int, default=30, help='analysed trials per (profile, mode): first N valid in block order')
    a = ap.parse_args()
    rows = [json.loads(l) for d in a.dirs for l in open(Path(d) / 'trials.jsonl') if l.strip()]
    invalid = [{'trial': r['trial'], 'reason': why} for r in rows if (why := validity(r))]
    valid = sorted((r for r in rows if not validity(r)), key=lambda r: (r['block'], r['trial']))
    cells = collections.defaultdict(list)
    for r in valid: cells[r['profile'], r['mode']].append(r)
    out, keys = {}, {}
    for (prof, mode), rs in sorted(cells.items()):
        used, unused = rs[:a.n], rs[a.n:]
        ms = [measures(r) for r in used]; k = sum(m['violation'] for m in ms)
        ps = [m['p_eq2'] for m in ms if m['p_eq2'] is not None]
        out[f'{prof}/{mode}'] = {'trials': len(used), 'unused': len(unused), 'violations': k, 'wilson95': list(wilson(k, len(used))[1:]) if used else None,
                                 'ends': dict(collections.Counter(m['end'] for m in ms)), 'pred_eq2_mean': sum(ps) / len(ps) if ps else None,
                                 'by_size': {str(s): sum(m['violation'] for r, m in zip(used, ms) if r['size'] == s) for s in sorted({r['size'] for r in used})}}
        if prof in KEY: keys[f"race{KEY[prof]}{'Layer' if mode == 'early' else 'Fence'}"] = k
    early = [measures(r) for (prof, mode), rs in cells.items() if mode == 'early' for r in rs[:a.n]]
    ps = [m['p_eq2'] for m in early if m['p_eq2'] is not None]
    keys['raceTrials'] = min((v['trials'] for v in out.values()), default=0)
    keys['racePredPct'] = round(100 * sum(ps) / len(ps), 1) if ps else None
    keys['raceObsPct'] = round(100 * sum(m['violation'] for m in early) / len(early), 1) if early else None
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'race-summary.json').write_text(json.dumps({'logged': len(rows), 'invalid': invalid, 'cells': out, 'keys': keys}, indent=1) + '\n')
    print(f"logged {len(rows)}, invalid {len(invalid)}, cells {[(c, v['trials'], v['unused']) for c, v in out.items()]}")


if __name__ == '__main__':
    main()
