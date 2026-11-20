#!/usr/bin/env python3
"""B10 post-hoc (exploratory) decomposition of the Eq. 2 gap; definitions in plans/b10-card.md "Post-hoc analysis".

Keys are not touched (they stay in results/round3/b10/analysis). Uses the same validity rule and first-N selection as
analyze_race.py. Device times (mono_ns) relative to q = SOCKET_CONFIG; D = calibrated D of the cell.
P0 = clip((c_k - q)/D); P1 = |[(a - q)/D, (c_k - q)/D] ∩ [0,1]| with a = AUTHORIZATION_LOGGED;
P2 = as P1 shifted by delta_bar, the median over the cell's fence trials of delta = (first WITHDRAW_ACK - q) - u*D.
Usage: posthoc_race_eq2.py <final run dir> [--out results/round3/b10/posthoc-eq2] [--n 30]
"""
import argparse, collections, json, statistics, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_race import fields, measures, validity  # noqa: E402

ART = Path(__file__).resolve().parents[1]


def times(r):
    ev = [e for e in r['events'] if e.get('trial') == r['trial']]
    first = lambda k: min((e['mono_ns'] for e in ev if e['kind'] == k), default=None)
    acc = [e['mono_ns'] for e in ev if e['kind'] == 'BYTES_ACCEPTED' and int(fields(e['detail']).get('n', 0)) > 0]
    return {'q': first('SOCKET_CONFIG'), 'a': first('AUTHORIZATION_LOGGED'), 'ack': first('WITHDRAW_ACK'), 'ck': max(acc, default=None)}


def overlap(lo, hi):
    return max(0.0, min(1.0, hi) - max(0.0, lo))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--out', default=str(ART / 'results/round3/b10/posthoc-eq2'))
    ap.add_argument('--n', type=int, default=30); a = ap.parse_args()
    import gzip
    op = lambda d: open(Path(d) / 'trials.jsonl') if (Path(d) / 'trials.jsonl').exists() else gzip.open(Path(d) / 'trials.jsonl.gz', 'rt')
    rows = [json.loads(l) for d in a.dirs for l in op(d) if l.strip()]
    valid = sorted((r for r in rows if not validity(r)), key=lambda r: (r['block'], r['trial']))
    cells = collections.defaultdict(list)
    for r in valid: cells[r['profile'], r['mode']].append(r)
    used = {k: rs[:a.n] for k, rs in cells.items()}

    def delta(r):
        t = times(r)
        return None if t['q'] is None or t['ack'] is None else (t['ack'] - t['q']) / 1e9 - r['u'] * r['D_s']

    dbar = {}
    for (prof, mode), rs in used.items():
        if mode != 'fence': continue
        for size in sorted({r['size'] for r in rs}):
            ds = [d for r in rs if r['size'] == size and (d := delta(r)) is not None]
            dbar[f'{prof}:{size}'] = statistics.median(ds) if ds else None

    per = []
    for (prof, mode), rs in sorted(used.items()):
        if mode != 'early': continue
        for r in rs:
            t, D = times(r), r['D_s']; m = measures(r)
            if None in (t['q'], t['a'], t['ck']) or not D:
                per.append({'trial': r['trial'], 'profile': prof, 'size': r['size'], 'violation': m['violation'], 'p0': None, 'p1': None, 'p2': None}); continue
            lo, hi = (t['a'] - t['q']) / 1e9 / D, (t['ck'] - t['q']) / 1e9 / D
            sh = (dbar.get(f"{prof}:{r['size']}") or 0.0) / D
            per.append({'trial': r['trial'], 'profile': prof, 'size': r['size'], 'violation': m['violation'],
                        'p0': min(1.0, max(0.0, hi)), 'p1': overlap(lo, hi), 'p2': overlap(lo - sh, hi - sh), 'delta_s': delta(r)})

    def agg(rs):
        mean = lambda k: (lambda xs: round(100 * sum(xs) / len(xs), 1) if xs else None)([x[k] for x in rs if x[k] is not None])
        return {'trials': len(rs), 'observed_pct': round(100 * sum(x['violation'] for x in rs) / len(rs), 1) if rs else None,
                'P0_pct': mean('p0'), 'P1_pct': mean('p1'), 'P2_pct': mean('p2')}

    def dstats(mode):
        out = {}
        for prof in sorted({p for p, _ in used}):
            ds = [d for r in used.get((prof, mode), []) if (d := delta(r)) is not None]
            out[prof] = {'n': len(ds), 'median_s': statistics.median(ds) if ds else None, 'min_s': min(ds, default=None), 'max_s': max(ds, default=None)}
        return out

    res = {'note': 'post-hoc, exploratory (b10-card.md); keys unchanged', 'pooled': agg(per),
           'by_profile': {p: agg([x for x in per if x['profile'] == p]) for p in sorted({x['profile'] for x in per})},
           'by_profile_size': {f'{p}:{s}': agg([x for x in per if x['profile'] == p and x['size'] == s]) for p, s in sorted({(x['profile'], x['size']) for x in per})},
           'delta_bar_fence_s': dbar, 'delta_fence': dstats('fence'), 'delta_early_check_only': dstats('early'), 'trials': per}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'posthoc-summary.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({k: res[k] for k in ('pooled', 'by_profile', 'delta_fence')}, indent=1))


if __name__ == '__main__':
    main()
