#!/usr/bin/env python3
"""B11 / test 4 analysis (artifact/plans/b11-card.md §3–4), fixed before the data were looked at.

Matched oracle (`followup/matched_oracle.py`, executed unchanged via analyze_test6.run_oracle) per AVD; its validity rules
plus the card's extra rule seen_max <= 0 (no job of ours parsed while waiting). First N valid paired trials per
(AVD, schedule) in k order; later valid ones unused. Keys (render_tests.py): lifeFourteenTrials / lifeFifteenTrials =
analysed paired trials (all schedules) per AVD; lifeXLayer / lifeXFence = analysed paired trials in which mlayer / mfence
has >= 1 confirmed violation among affected tenants (1, 2, 4, 5, 8). Unknown requests are reported, never folded in.
Usage: analyze_b11.py [--avd14 DIR ...] [--avd15 DIR ...] [--out results/round3/b11/analysis] [--n 20]
"""
import argparse, collections, contextlib, io, json, sys, tempfile
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART / 'followup'))
import analyze_test6 as T6  # noqa: E402

AFFECTED = [1, 2, 4, 5, 8]


def run(instdir, out, flt):
    with contextlib.redirect_stdout(io.StringIO()):
        return T6.run_oracle(instdir, out, flt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--avd14', nargs='*', default=[str(ART / 'results/round3/b11/avd14-final')])
    ap.add_argument('--avd15', nargs='*', default=[str(ART / 'results/round3/b11/avd15-final')])
    ap.add_argument('--out', default=str(ART / 'results/round3/b11/analysis')); ap.add_argument('--n', type=int, default=20)
    a = ap.parse_args()
    instdir = {}
    for letter, dirs in (('F', a.avd14), ('V', a.avd15)):          # F = Android 14, V = Android 15 (oracle run = 1 letter)
        for i, d in enumerate(dirs):
            if (Path(d) / 'schedule.jsonl').exists(): instdir[f'{letter}-{i}'] = Path(d)
    extra = []
    def seen(inst, plans):
        keep = []
        for p in plans:
            q = [x for x in p.get('actions', []) if x.get('a') == 'quiesced']
            if q and q[-1].get('seen_max', 1) <= 0: extra.append({'instance': inst, 'trial': p['trial'], 'reason': 'jobs not observable'})
            else: keep.append(p)
        return keep
    with tempfile.TemporaryDirectory() as tmp: first = run(instdir, tmp, seen)
    valid = collections.defaultdict(set)
    for r in first['rows']: valid[r['instance'][0], r['schedule']].add((r['k'], r['instance'], r['trial']))
    chosen, unused = set(), []
    for key, ts in valid.items():
        o = sorted(ts); chosen |= {(i, t) for _, i, t in o[:a.n]}; unused += [dict(avd=key[0], schedule=key[1], trial=t) for _, _, t in o[a.n:]]
    extra.clear()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    final = run(instdir, out, lambda inst, plans: [p for p in seen(inst, plans) if (inst, p['trial']) in chosen])
    rows = final['rows']; res, keys = {}, {}
    for letter, name in (('F', 'Fourteen'), ('V', 'Fifteen')):
        rs = [r for r in rows if r['instance'][0] == letter]
        if not rs: continue
        trials = {(r['instance'], r['trial']) for r in rs}
        per_sched = collections.Counter(r['schedule'] for r in rs if r['variant'] == 'mfence' and r['tenant'] == 1)
        viol = lambda v: len({(r['instance'], r['trial']) for r in rs if r['variant'] == v and r['tenant'] in AFFECTED and r['violation']})
        res[name] = {'analysed_paired_trials': len(trials), 'per_schedule': dict(per_sched),
                     'violating_trials': {v: viol(v) for v in ('menqueue', 'mlayer', 'mfence')},
                     'unknown_requests': {v: sum(r['unknown_requests'] for r in rs if r['variant'] == v) for v in ('menqueue', 'mlayer', 'mfence')},
                     'legit_missing': {v: sum(r['legit_missing'] for r in rs if r['variant'] == v) for v in ('menqueue', 'mlayer', 'mfence')}}
        keys.update({f'life{name}Trials': len(trials), f'life{name}Layer': viol('mlayer'), f'life{name}Fence': viol('mfence')})
    (out / 'b11-summary.json').write_text(json.dumps({'invalid_oracle_rules': final['invalid_trials'], 'invalid_extra': extra,
                                                      'unused_valid': unused, 'avds': res, 'keys': keys}, indent=1) + '\n')
    print({k: (v['analysed_paired_trials'], v['per_schedule']) for k, v in res.items()}, 'invalid', len(final['invalid_trials']) + len(extra))


if __name__ == '__main__':
    main()
