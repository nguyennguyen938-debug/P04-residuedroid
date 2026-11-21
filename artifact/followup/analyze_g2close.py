#!/usr/bin/env python3
"""Group 2, test G2a analysis (g2close-card.md), written 21/11 before any G2a trial ran.

Run: race_suite.py with modes early, close, fence in the same blocks (B10 v3 protocol: guest netem shaping, same profiles,
sizes, seed and deadline rule). Validity and the violation oracle are B10's (`analyze_race.validity` / `measures`): bytes
accepted (BYTES_ACCEPTED n > 0) after the first WITHDRAW_ACK on the device clock. First N valid per (profile, mode) in block
order. Reported per (profile, mode), never pooled across modes:
  violations (Wilson 95%), by size, end events, bytes accepted after the ack;
  cut trials (WITHDRAW_ACK before REQUEST_HANDED_OFF, or never handed off) and how many of them the receiver logged as a
  complete request (receiver.jsonl, matched by request id; device and host clocks are never mixed);
  withdrawal latency WITHDRAW_REQUEST -> WITHDRAW_ACK (device clock, ms): median, nearest-rank p95, max (descriptive);
  in-flight write at the ack: trials whose first post-ack accepted chunk was attempted (WRITE_ATTEMPT) before the ack;
  close only: cancellation replies (CANCEL_DONE reply) and sockets found open (CANCEL live/closed).
Paired (descriptive): per (block, profile, size), the 2x2 counts of (violation in mode A, violation in mode B) for
close vs fence and close vs early. No p-values.
Usage: analyze_g2close.py <final run dir> [--out results/round3/g2close/analysis] [--n 30]
"""
import argparse, collections, gzip, json, math, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ART / 'followup'), str(ART / 'scripts')]
from analyze_race import fields, measures, validity  # noqa: E402
from summarize import wilson  # noqa: E402


def own(r): return [e for e in r.get('events', []) if e.get('trial') == r['trial']]


def first(ev, kind): return min((e['mono_ns'] for e in ev if e['kind'] == kind), default=None)


def order_stats(xs):
    xs = sorted(xs)
    if not xs: return None
    n = len(xs); med = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    return {'n': n, 'median': round(med, 3), 'p95': round(xs[math.ceil(0.95 * n) - 1], 3), 'max': round(xs[-1], 3)}


def extra(r, complete):
    ev = own(r); ack = first(ev, 'WITHDRAW_ACK'); req = first(ev, 'WITHDRAW_REQUEST'); handed = first(ev, 'REQUEST_HANDED_OFF')
    cut = handed is None or ack < handed
    post = sorted((e['mono_ns'], fields(e['detail'])) for e in ev if e['kind'] == 'BYTES_ACCEPTED' and e['mono_ns'] > ack and int(fields(e['detail']).get('n', 0)) > 0)
    inflight = False
    if post:
        t, d = post[0]
        key = (d.get('record'), d.get('offset'))
        inflight = any(e['kind'] == 'WRITE_ATTEMPT' and e['mono_ns'] < ack and (fields(e['detail']).get('record'), fields(e['detail']).get('offset')) == key for e in ev)
    return {'cut': cut, 'cut_complete': cut and r['trial'] in complete, 'latency_ms': (ack - req) / 1e6 if req is not None else None,
            'inflight_at_ack': inflight, 'cancel_reply': next((fields(e['detail']).get('reply') for e in ev if e['kind'] == 'CANCEL_DONE'), None),
            'cancel': next((e['detail'] for e in ev if e['kind'] == 'CANCEL'), None)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('--out', default=str(ART / 'results/round3/g2close/analysis'))
    ap.add_argument('--n', type=int, default=30); a = ap.parse_args()
    d = Path(a.dir)
    op = (lambda p: open(p)) if (d / 'trials.jsonl').exists() else (lambda p: gzip.open(str(p) + '.gz', 'rt'))
    rows = [json.loads(l) for l in op(d / 'trials.jsonl') if l.strip()]
    rec = d / 'receiver.jsonl'
    complete = {x['request'] for x in (json.loads(l) for l in rec.read_text().splitlines() if l.strip()) if x.get('event') == 'body' and x.get('complete')} if rec.exists() else set()
    invalid = [{'trial': r['trial'], 'reason': why} for r in rows if (why := validity(r))]
    valid = sorted((r for r in rows if not validity(r)), key=lambda r: (r['block'], r['trial']))
    cells = collections.defaultdict(list)
    for r in valid: cells[r['profile'], r['mode']].append(r)
    out, used_all = {}, {}
    for (prof, mode), rs in sorted(cells.items()):
        used = rs[:a.n]; ms = [measures(r) for r in used]; xs = [extra(r, complete) for r in used]; k = sum(m['violation'] for m in ms)
        for r, m in zip(used, ms): used_all[r['block'], prof, r['size'], mode] = m['violation']
        c = {'trials': len(used), 'unused': len(rs) - len(used), 'violations': k, 'wilson95': list(wilson(k, len(used))[1:]) if used else None,
             'by_size': {str(s): sum(m['violation'] for r, m in zip(used, ms) if r['size'] == s) for s in sorted({r['size'] for r in used})},
             'ends': dict(collections.Counter(m['end'] for m in ms)), 'after_ack_bytes': sum(m['after_ack_bytes'] for m in ms),
             'cut': sum(x['cut'] for x in xs), 'cut_receiver_complete': sum(x['cut_complete'] for x in xs),
             'withdraw_latency_ms': order_stats([x['latency_ms'] for x in xs if x['latency_ms'] is not None]),
             'inflight_write_at_ack': sum(x['inflight_at_ack'] for x in xs)}
        if mode == 'close':
            c['cancel_replies'] = dict(collections.Counter(x['cancel_reply'] for x in xs))
            c['cancel_found'] = dict(collections.Counter(x['cancel'] for x in xs))
        out[f'{prof}/{mode}'] = c
    paired = {}
    for other in ('fence', 'early'):
        cnt = collections.Counter()
        for (b, p_, s, m), v in used_all.items():
            if m == 'close' and (b, p_, s, other) in used_all: cnt[f'close={int(v)}/{other}={int(used_all[b, p_, s, other])}'] += 1
        paired[f'close_vs_{other}'] = dict(sorted(cnt.items()))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'g2close-summary.json').write_text(json.dumps({'logged': len(rows), 'invalid': invalid, 'cells': out, 'paired': paired}, indent=1) + '\n')
    print(f"logged {len(rows)}, invalid {len(invalid)}, cells {[(c, v['trials'], v['unused']) for c, v in out.items()]}")


if __name__ == '__main__':
    main()
