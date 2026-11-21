#!/usr/bin/env python3
"""Build artifact/results/round3/summary.json (B → C delivery) from the analysis outputs only; never typed by hand.

Sources (each optional; a missing analysis just leaves its keys absent, which renders as ?? in the PDF):
  test 6  results/round3/test6/analysis/test6-summary.json  summary_candidates (definitions: plans/test6-card.md §4)
  test 1  results/round3/b10/analysis/race-summary.json     keys
  test 4  results/round3/b11/analysis/b11-summary.json      keys
  test 5  results/round3/b4/analysis-v3-repl/sweep-summary.json  keys (protocol v3, final-v3 + replacement blocks; v1, v2 reported in b4-card.md)
  test 2  results/mutation-v2/analysis/mutation-summary.json   keys (protocol v2, regrant_agg; v1 reported in b12-card.md)
Keys requested by C in PR #2 (21/11), computed in extra_keys() from frozen analysis outputs:
  devLife*      test6/analysis/matched-outcomes.json: paired trials with >= 1 violation among affected tenants (1, 2, 4, 5, 8,
                as matched_oracle.py), both phones, schedules pending + kill + revoke, pre-registered denominator
  racePhone*    test1-phone/analysis/race-summary.json keys (same meaning as race*); model plans/test1-phone/device.json,
                Android release final/meta.json
  mut*Trials, mutBaseDeficit  mutation-v2/analysis/mutation-summary.json per build (valid_trials, permitted_deficit)
  air*          b2/analysis (oracle v2, pre-registered) and b2/analysis-v3 (unknowns only); pending + kill + reboot
  split*        b3/analysis/b3-summary.json (split cells: prefirst = no chunk accepted yet, prefix = a chunk accepted)
Names not yet in SCHEMA go to summary-pending.json (same format) until C adds them; summary.json holds SCHEMA names only.
Only names in SCHEMA (scripts/render_tests.py) are written; render_tests.py asserts this too.
Usage: python3 artifact/results/round3/make_summary.py
"""
import ast, json
from pathlib import Path

ART = Path(__file__).resolve().parents[2]
R = ART / 'results'
SRC = [(R / 'round3/test6/analysis/test6-summary.json', 'summary_candidates'), (R / 'round3/b10/analysis/race-summary.json', 'keys'),
       (R / 'round3/b11/analysis/b11-summary.json', 'keys'), (R / 'round3/b4/analysis-v3-repl/sweep-summary.json', 'keys'),
       (R / 'mutation-v2/analysis/mutation-summary.json', 'keys')]


def schema():
    tree = ast.parse((ART / 'scripts/render_tests.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'SCHEMA' for t in node.targets):
            return set(ast.literal_eval(node.value))
    raise SystemExit('SCHEMA not found')


def jload(p):
    return json.loads(Path(p).read_text())


def extra_keys():
    k = {}
    t6 = R / 'round3/test6/analysis/matched-outcomes.json'
    if t6.exists():
        by = {}
        for r in jload(t6)['rows']:
            if r['tenant'] in (1, 2, 4, 5, 8) and r['schedule'] in ('pending', 'kill', 'revoke'):
                key = (r['variant'], r['instance'], r['schedule'], r['trial'])
                by[key] = by.get(key, 0) | int(r['violation'])
        for name, v in (('Enq', 'menqueue'), ('Fence', 'mfence')):
            xs = [x for (var, *_), x in by.items() if var == v]
            k[f'devLife{name}Viol'], k[f'devLife{name}N'] = sum(xs), len(xs)
    ph = R / 'round3/test1-phone/analysis/race-summary.json'
    if ph.exists():
        k.update({'racePhone' + n[4:]: v for n, v in jload(ph)['keys'].items()})
        k['racePhoneModel'] = jload(ART / 'plans/test1-phone/device.json')['label']
        k['racePhoneAndroid'] = jload(R / 'round3/test1-phone/final/meta.json')['phone']['release']
    mu = R / 'mutation-v2/analysis/mutation-summary.json'
    if mu.exists():
        m = jload(mu)['mutants']
        for n, b in (('Base', 'base'), ('One', 'M1-union-latest'), ('Two', 'M2-stale-epoch'), ('Three', 'M3-extras-drop')):
            k[f'mut{n}Trials'] = m[b]['valid_trials']
        k['mutBaseDeficit'] = m['base']['permitted_deficit']
    a2, a3 = R / 'round3/b2/analysis/airguard-summary.json', R / 'round3/b2/analysis-v3/airguard-summary.json'
    if a2.exists() and a3.exists():
        c2, c3, S = jload(a2)['cells'], jload(a3)['cells'], ('pending', 'kill', 'reboot')
        assert all(c2[f'{s}/stock']['trials'] == c2[f'{s}/fenced']['trials'] for s in S), 'paired builds per trial'
        k['airN'] = sum(c2[f'{s}/stock']['trials'] for s in S)
        k['airStockViol'] = sum(c2[f'{s}/stock']['violating_trials'] for s in S)
        k['airFenceViol'] = sum(c2[f'{s}/fenced']['violating_trials'] for s in S)
        k['airFenceUnknownV'] = sum(c2[f'{s}/fenced']['unknown_trials'] for s in S)
        k['airFenceUnknownVThree'] = sum(c3[f'{s}/fenced']['unknown_trials'] for s in S)
    b3 = R / 'round3/b3/analysis/b3-summary.json'
    if b3.exists():
        c = jload(b3)['cells']
        assert c['prefirst/split']['trials'] == c['prefix/split']['trials']
        k['splitTrials'] = c['prefirst/split']['trials']
        k['splitPreRecovered'] = c['prefirst/split']['permitted_retained']
        k['splitPostRecovered'] = c['prefix/split']['permitted_retained']
    return k


def main():
    names, out, used = schema(), {}, []
    for path, field in SRC:
        if not path.exists(): continue
        vals = json.loads(path.read_text()).get(field, {})
        out.update({k: v for k, v in vals.items() if k in names and v is not None}); used.append(str(path.relative_to(ART)))
    extra = extra_keys()
    out.update({n: v for n, v in extra.items() if n in names})
    pending = {n: v for n, v in extra.items() if n not in names}
    dest = R / 'round3/summary.json'
    dest.write_text(json.dumps(dict(sorted(out.items())), indent=1, ensure_ascii=False) + '\n')
    (R / 'round3/summary-pending.json').write_text(json.dumps(dict(sorted(pending.items())), indent=1, ensure_ascii=False) + '\n')
    print(f'summary.json: {len(out)} keys from {used}; missing {len(names - set(out))} of {len(names)}; '
          f'{len(pending)} requested keys not yet in SCHEMA -> summary-pending.json')


if __name__ == '__main__':
    main()
