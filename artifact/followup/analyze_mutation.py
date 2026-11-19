#!/usr/bin/env python3
"""B12 / test 2 analysis (artifact/plans/b12-card.md), fixed before the final run.

Per mutant run directory (campaign.py, variant mfence, schedules pending + reboot):
  leaking trials   : paired trials with >= 1 confirmed violation among affected tenants (1, 2, 4, 5, 8), by the matched
                     oracle (`followup/matched_oracle.py`, executed unchanged through analyze_test6.run_oracle; its own
                     validity rules apply);
  flagged items    : items `label_check.py` (A9) marks incomplete or missing;
  wrong-label items: ground truth, independent of label_check's code: an item whose label set does not contain every
                     source the oracle's tracer (`scripts/oracle.item_sources`) finds in its content (scope:epoch);
  permitted deficit: legit_missing summed over rows (oracle).
Keys (render_tests.py): mutTrials, mutOneLeak/Flagged/Wrong (M1), mutTwoLeak/Flagged/Wrong (M2), mutThreeDeficit (M3).
Usage: analyze_mutation.py [--root results/mutation] [--out results/mutation/analysis]
"""
import argparse, collections, contextlib, io, json, sys, tempfile
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ART / 'followup'), str(ART / 'scripts'), str(ART / 'mutation')]
import analyze_test6 as T6  # noqa: E402
from oracle import item_sources  # noqa: E402
import label_check as LC  # noqa: E402

MUTANTS = {'base': None, 'M1-union-latest': 'One', 'M2-stale-epoch': 'Two', 'M3-extras-drop': 'Three'}
AFFECTED = [1, 2, 4, 5, 8]


def wrong_items(receipts):
    n = 0
    for r in receipts:
        b = r.get('body', {})
        if b.get('tenant') in LC.UNCOVERED: continue
        for it in b.get('items', []):
            need = {f"{LC.SCOPES[st]}:{ep}" for st, ep, _ in item_sources(it)}
            have = set((it.get('labels') or '').split(',')) - {''}
            n += bool(need - have)
    return n


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default=str(ART / 'results/mutation'))
    ap.add_argument('--out', default=str(ART / 'results/mutation/analysis')); a = ap.parse_args()
    res, keys = {}, {}
    for m, k in MUTANTS.items():
        d = Path(a.root) / m
        if not (d / 'schedule.jsonl').exists(): continue
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            o = T6.run_oracle({f'X-{m}': d}, tmp, lambda inst, plans: plans)
        rows = o['rows']
        trials = sorted({r['trial'] for r in rows})
        leak = sorted({r['trial'] for r in rows if r['tenant'] in AFFECTED and r['violation']})
        receipts = [json.loads(l) for l in (d / 'sink/ingest.jsonl').read_text().splitlines() if l.strip()]
        counts, _ = LC.check(receipts)
        flagged = sum(n for (v, verdict), n in counts.items() if verdict != 'ok')
        res[m] = {'valid_trials': len(trials), 'invalid': o['invalid_trials'], 'leaking_trials': len(leak), 'flagged_items': flagged,
                  'wrong_label_items': wrong_items(receipts), 'permitted_deficit': sum(r['legit_missing'] for r in rows),
                  'label_check_counts': {f'{v}/{verdict}': n for (v, verdict), n in sorted(counts.items())}}
        if k in ('One', 'Two'):
            keys[f'mut{k}Leak'] = len(leak); keys[f'mut{k}Flagged'] = flagged; keys[f'mut{k}Wrong'] = res[m]['wrong_label_items']
        if k == 'Three': keys['mutThreeDeficit'] = res[m]['permitted_deficit']
    if res: keys['mutTrials'] = min(v['valid_trials'] for v in res.values())
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'mutation-summary.json').write_text(json.dumps({'mutants': res, 'keys': keys}, indent=1) + '\n')
    print({m: (v['valid_trials'], len(v['invalid'])) for m, v in res.items()})


if __name__ == '__main__':
    main()
