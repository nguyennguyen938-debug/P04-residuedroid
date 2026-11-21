#!/usr/bin/env python3
"""Descriptive tallies for G2b (22/11, after the final; g2layer-card.md §6). Not a pre-registered estimand.
(1) Donated beacons and trials per (schedule, build, batch/order) from the pre-registered v2 analysis rows.
(2) Where each build stopped a donation (guest events): DONATION_BLOCKED with early=1 (layered check before sending) or
    from the transport (fenced, with a BLOCK event per stopped chunk).
Usage: posthoc_g2layer.py [--run results/round3/g2layer/final] [--analysis results/round3/g2layer/analysis] [--out results/round3/g2layer/posthoc]
"""
import argparse, collections, json
from pathlib import Path

ART = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--run', default='results/round3/g2layer/final')
    ap.add_argument('--analysis', default='results/round3/g2layer/analysis'); ap.add_argument('--out', default='results/round3/g2layer/posthoc')
    a = ap.parse_args()
    rows = json.loads((ART / a.analysis / 'airguard-summary.json').read_text())['rows']
    beacons, trials = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for r in rows:
        for k, n in r['donated'].items():
            beacons[f"{r['schedule']}/{r['variant']}"][k] += n; trials[f"{r['schedule']}/{r['variant']}"][k] += n > 0
    stops = collections.Counter()
    for x in map(json.loads, open(ART / a.run / 'device_events.jsonl')):
        for e in x['events']:
            if e['kind'] == 'DONATION_BLOCKED': stops[f"{x['variant']}/{'early_check' if 'early=1' in (e.get('detail') or '') else 'transport'}"] += 1
            if e['kind'] == 'BLOCK': stops[f"{x['variant']}/BLOCK_event"] += 1
    res = {'estimand': 'descriptive, after the data were seen', 'donated_beacons': {k: dict(v) for k, v in sorted(beacons.items())},
           'trials_with_donation': {k: dict(v) for k, v in sorted(trials.items())}, 'stop_points': dict(sorted(stops.items()))}
    out = ART / a.out; assert not out.exists(), f'{out} exists (fresh directory only)'; out.mkdir(parents=True)
    (out / 'posthoc.json').write_text(json.dumps(res, indent=1) + '\n'); print(res['stop_points'])


if __name__ == '__main__':
    main()
