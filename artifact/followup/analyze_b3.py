#!/usr/bin/env python3
"""B3 analysis (split policy), fixed before the final run (artifact/plans/b3-card.md).

Validity (harness fields only): no harness_error; the end of the request (and of its split resubmission, if any) was
observed; for withdrawal conditions the barrier/first accepted chunk was seen before the withdrawal and WITHDRAW_ACK was
logged. Per valid trial, from the receiver's own log (completion) and the app's events:
  permitted_retained : item B (diagnostics) reached the receiver complete — in the original request (no denial) or in the
                       '<id>-split' resubmission;
  resubmit_ok        : a SPLIT event resubmitted items and the '<id>-split' request completed at the receiver;
  forbidden_after_ack: the original request (which carries A) completed at the receiver in a withdrawal condition
                       (safety check, expected 0).
Rates with Wilson 95% per (condition, split). Usage: analyze_b3.py <run dir>... [--out DIR] [--n 20]
"""
import argparse, collections, json, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART / 'scripts'))
from summarize import wilson  # noqa: E402


def validity(r):
    if r.get('harness_error'): return 'harness error'
    if not r.get('complete_wait'): return 'end not observed'
    if r['condition'] != 'control':
        if r.get('barrier_seen') is not True: return 'barrier not reached'
        if not any(e['trial'] == r['trial'] and e['kind'] == 'WITHDRAW_ACK' for e in r.get('events', [])): return 'no withdrawal ack'
    return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--out', default=str(ART / 'results/round3/b3/analysis'))
    ap.add_argument('--n', type=int, default=20); a = ap.parse_args()
    rows, done = [], set()
    for d in a.dirs:
        rows += [json.loads(l) for l in open(Path(d) / 'trials.jsonl') if l.strip()]
        rec = Path(d) / 'receiver.jsonl'
        for l in (open(rec) if rec.exists() else []):   # no connection at all -> no receiver file
            x = json.loads(l)
            if x.get('event') == 'body' and x.get('complete'): done.add(x['request'])
    invalid = [{'trial': r['trial'], 'reason': w} for r in rows if (w := validity(r))]
    cells = collections.defaultdict(list)
    for r in sorted((r for r in rows if not validity(r)), key=lambda r: r['block']): cells[r['condition'], r['split']].append(r)
    out = {}
    for (cond, split), rs in sorted(cells.items()):
        used = rs[:a.n]
        kept = sum(r['trial'] in done or r['trial'] + '-split' in done for r in used)
        res = sum(r['trial'] + '-split' in done and any(e['trial'] == r['trial'] and e['kind'] == 'SPLIT' and not e['detail'].endswith('resubmit=') for e in r['events']) for r in used)
        bad = sum(cond != 'control' and r['trial'] in done for r in used)
        out[f"{cond}/{'split' if split else 'nosplit'}"] = {'trials': len(used), 'unused': len(rs) - len(used),
            'permitted_retained': kept, 'retained_wilson95': list(wilson(kept, len(used))[1:]) if used else None,
            'resubmit_ok': res, 'forbidden_after_ack': bad}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'b3-summary.json').write_text(json.dumps({'logged': len(rows), 'invalid': invalid, 'cells': out}, indent=1) + '\n')
    print(f"logged {len(rows)}, invalid {len(invalid)}, cells {[(c, v['trials']) for c, v in out.items()]}")


if __name__ == '__main__':
    main()
