#!/usr/bin/env python3
"""Exploratory (22/11, defined after the G2a final data were seen; g2close-card.md §6). Not a pre-registered estimand.
(1) For trials NOT cut (REQUEST_HANDED_OFF before the first WITHDRAW_ACK): end event x whether the receiver logged the request
    complete, per mode. (2) Close trials: withdrawal latency by segment WITHDRAW_REQUEST -> WITHDRAW_DURABLE -> CANCEL (sender
    process) -> CANCEL_DONE -> WITHDRAW_ACK, ms on the device clock (elapsedRealtimeNanos, shared by both app processes).
Usage: posthoc_g2close.py [--run results/round3/g2close/final] [--out results/round3/g2close/posthoc]
"""
import argparse, collections, json, statistics
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
SEG = ('WITHDRAW_REQUEST', 'WITHDRAW_DURABLE', 'CANCEL', 'CANCEL_DONE', 'WITHDRAW_ACK')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--run', default='results/round3/g2close/final')
    ap.add_argument('--out', default='results/round3/g2close/posthoc'); a = ap.parse_args()
    d = ART / a.run
    import gzip                            # raw committed as .gz (kept on disk, git-ignored), as B10
    f = open(d / 'trials.jsonl') if (d / 'trials.jsonl').exists() else gzip.open(d / 'trials.jsonl.gz', 'rt')
    rows = [json.loads(l) for l in f if l.strip()]
    comp = {x['request'] for x in map(json.loads, open(d / 'receiver.jsonl')) if x.get('event') == 'body' and x.get('complete')}
    uncut = collections.Counter(); seg = collections.defaultdict(list)
    for r in rows:
        ev = [e for e in r['events'] if e.get('trial') == r['trial']]
        first = {}
        for e in ev: first.setdefault(e['kind'], e['mono_ns'])
        ack = first['WITHDRAW_ACK']; h = [e['mono_ns'] for e in ev if e['kind'] == 'REQUEST_HANDED_OFF']
        end = next(e['kind'] for e in ev if e['kind'] in ('SEND_OK', 'SEND_ERROR', 'EARLY_BLOCK'))
        if h and min(h) < ack: uncut[f"{r['mode']}/{end}/{'receiver_complete' if r['trial'] in comp else 'receiver_incomplete'}"] += 1
        if r['mode'] == 'close' and all(k in first for k in SEG):
            for x, y in zip(SEG, SEG[1:]): seg[f'{x}->{y}'].append((first[y] - first[x]) / 1e6)
    res = {'estimand': 'exploratory, defined after the data were seen', 'trials': len(rows), 'uncut_end_by_receiver': dict(sorted(uncut.items())),
           'close_latency_segments_ms': {k: {'n': len(v), 'median': round(statistics.median(v), 3), 'max': round(max(v), 3)} for k, v in seg.items()}}
    out = ART / a.out; assert not out.exists(), f'{out} exists (fresh directory only)'; out.mkdir(parents=True)
    (out / 'posthoc.json').write_text(json.dumps(res, indent=1) + '\n'); print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
