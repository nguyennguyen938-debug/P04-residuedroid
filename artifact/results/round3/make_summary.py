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


def main():
    names, out, used = schema(), {}, []
    for path, field in SRC:
        if not path.exists(): continue
        vals = json.loads(path.read_text()).get(field, {})
        out.update({k: v for k, v in vals.items() if k in names and v is not None}); used.append(str(path.relative_to(ART)))
    dest = R / 'round3/summary.json'
    dest.write_text(json.dumps(dict(sorted(out.items())), indent=1, ensure_ascii=False) + '\n')
    print(f'summary.json: {len(out)} keys from {used}; missing {len(names - set(out))} of {len(names)}')


if __name__ == '__main__':
    main()
