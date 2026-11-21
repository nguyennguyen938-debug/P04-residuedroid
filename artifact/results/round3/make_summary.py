#!/usr/bin/env python3
"""Build artifact/results/round3/summary.json (B → C delivery) from the analysis outputs only; never typed by hand.

Sources (each optional; a missing analysis just leaves its keys absent, which renders as ?? in the PDF):
  test 6  results/round3/test6/analysis/test6-summary.json  summary_candidates (definitions: plans/test6-card.md §4)
  test 1  results/round3/b10/analysis/race-summary.json     keys
  test 4  results/round3/b11/analysis/b11-summary.json      keys
  test 5  results/round3/b4/analysis-v3-repl/sweep-summary.json  keys (protocol v3, final-v3 + replacement blocks; v1, v2 reported in b4-card.md)
  test 2  results/mutation-v2/analysis/mutation-summary.json   keys (protocol v2, regrant_agg; v1 reported in b12-card.md)
Only names in SCHEMA (scripts/render_tests.py) are written; render_tests.py asserts this too.
Usage: python3 artifact/results/round3/make_summary.py
"""
import ast, collections, json
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


def load(rel):
    return json.loads((R / rel).read_text(encoding='utf-8'))


def derived():
    """Keys added at C's request on PR #2 (21/11), computed from the frozen analysis outputs; nothing is re-run.
    Structural assumptions (equal cell sizes, both builds paired) are asserted; values were checked once against
    plans/B-report.md when this was added."""
    k = {}
    # Test 1 on a phone: same analyser as B10, keys renamed race* -> racePhone*. The model label comes from
    # plans/test1-phone-card.md (the meta.json fingerprint is samsung/a06...); the Android release from meta.json.
    ph = load('round3/test1-phone/analysis/race-summary.json')['keys']
    k.update({'racePhone' + name[len('race'):]: v for name, v in ph.items()})
    k['racePhoneModel'] = 'Galaxy A06'
    k['racePhoneAndroid'] = load('round3/test1-phone/final/meta.json')['phone']['release']
    # B2 AirGuard: pending, kill and reboot pooled; netloss is reported separately in the card.
    v2, v3 = load('round3/b2/analysis/airguard-summary.json')['cells'], load('round3/b2/analysis-v3/airguard-summary.json')['cells']
    sched = ['pending', 'kill', 'reboot']
    n_stock, n_fence = (sum(v2[f'{s}/{b}']['trials'] for s in sched) for b in ('stock', 'fenced'))
    assert n_stock == n_fence
    k.update(airN=n_stock, airStockViol=sum(v2[f'{s}/stock']['violating_trials'] for s in sched),
             airFenceViol=sum(v2[f'{s}/fenced']['violating_trials'] for s in sched),
             airFenceUnknownV=sum(v2[f'{s}/fenced']['unknown_trials'] for s in sched),
             airFenceUnknownVThree=sum(v3[f'{s}/fenced']['unknown_trials'] for s in sched))
    # B3 split policy. forbidden_after_ack is summed over every cell; 0 means no trial accepted bytes after the ack.
    b3 = load('round3/b3/analysis/b3-summary.json')['cells']
    assert len({c['trials'] for c in b3.values()}) == 1
    k.update(splitTrials=b3['prefirst/split']['trials'], splitPreRecovered=b3['prefirst/split']['permitted_retained'],
             splitPostRecovered=b3['prefix/split']['permitted_retained'],
             splitAfterAck=sum(c['forbidden_after_ack'] for c in b3.values()))
    # B12 v2 per-build counts (mutTrials stays the minimum and is not cited).
    mu = load('mutation-v2/analysis/mutation-summary.json')['mutants']
    k.update(mutBaseTrials=mu['base']['valid_trials'], mutOneTrials=mu['M1-union-latest']['valid_trials'],
             mutTwoTrials=mu['M2-stale-epoch']['valid_trials'], mutThreeTrials=mu['M3-extras-drop']['valid_trials'],
             mutBaseDeficit=mu['base']['permitted_deficit'], mutBaseLeak=mu['base']['leaking_trials'],
             mutThreeLeak=mu['M3-extras-drop']['leaking_trials'])
    # B11: the enqueue-time baseline per AVD.
    av = load('round3/b11/analysis/b11-summary.json')['avds']
    k.update(lifeFourteenEnq=av['Fourteen']['violating_trials']['menqueue'],
             lifeFifteenEnq=av['Fifteen']['violating_trials']['menqueue'])
    # B4 v3: trials logged; the one invalid trial is the sender that waited its full deadline for the lock.
    sw = load('round3/b4/analysis-v3-repl/sweep-summary.json')
    k.update(sweepLogged=sw['logged'], sweepLockStalls=sum(x['reason'] == 'sender did not complete' for x in sw['invalid']))
    # Test 6 lifecycle on the rented phones: a paired trial violates if any affected tenant (T1, T2, T4, T5, T8) does,
    # as in the matched campaign; pooled over both phones and the pending, kill and revoke schedules.
    rows = load('round3/test6/analysis/matched-outcomes.json')['rows']
    trial = collections.defaultdict(bool)
    for r in rows:
        if r['tenant'] in (1, 2, 4, 5, 8):
            trial[r['run'], r['schedule'], r['instance'], r['trial'], r['variant']] |= r['violation'] > 0
    for key, v in (('Enq', 'menqueue'), ('Fence', 'mfence')):
        hits = [viol for t, viol in trial.items() if t[4] == v]
        k[f'devLife{key}Viol'], k[f'devLife{key}N'] = sum(hits), len(hits)
    return k


def main():
    names, out, used = schema(), {}, []
    for path, field in SRC:
        if not path.exists(): continue
        vals = json.loads(path.read_text()).get(field, {})
        out.update({k: v for k, v in vals.items() if k in names and v is not None}); used.append(str(path.relative_to(ART)))
    extra = derived()
    out.update({k: v for k, v in extra.items() if k in names}); used.append('derived() keys (C, 21/11)')
    dest = R / 'round3/summary.json'
    dest.write_text(json.dumps(dict(sorted(out.items())), indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(f'summary.json: {len(out)} keys from {used}; missing {len(names - set(out))} of {len(names)}')


if __name__ == '__main__':
    main()
