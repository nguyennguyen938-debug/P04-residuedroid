#!/usr/bin/env python3
"""Exploratory (21/11, after the B7 freeze, frozen data): why M1-union-latest leaked in 24/40 B12 v2 trials.
Per trial, from the guest trace of tenant 5 (the re-grant tenant) and the sink receipts only:
  reaggregated : an AGG event after REGRANT (the re-derived summary that M1 labels with the newest epoch only)
  uploaded     : the sink received that summary's tag (RD-<trial>-T5-sum-16)
  post_reboot_summary_job_sent_nothing : a K_SUMMARY JOBSTART after the second PROC_START whose PREPARED is followed by
                 JOBDONE without any WRITE_ATTEMPT in between (ChunkFence filters a blocked item without an event)
and the matched oracle's violation for the trial (as analyze_mutation.py). Keys and analyses are unchanged.
Usage: m1_trigger.py [--run results/mutation-v2/M1-union-latest] [--out results/mutation-v2/analysis-m1]
"""
import argparse, collections, contextlib, io, json, sys, tempfile
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ART / 'followup'), str(ART / 'scripts')]
AFFECTED = [1, 2, 4, 5, 8]          # = analyze_mutation.py


def jl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def trial_facts(t, ev, received):
    m = [e for e in ev if e[3] == 5]
    rg = [e[0] for e in m if e[4] == 'REGRANT']
    agg2 = [e for e in m if e[4] == 'AGG' and rg and e[0] > rg[0]]
    tag2 = agg2[0][5].split(';')[0].split('=', 1)[1] if agg2 else None
    procs = [e[0] for e in ev if e[4] == 'PROC_START']
    silent = False
    if len(procs) > 1:
        after = [e for e in m if e[0] > procs[1]]
        for i, e in enumerate(after):
            if e[4] == 'JOBSTART' and e[5] == 'kind=3':
                rest = after[i + 1:]
                done = next((j for j, x in enumerate(rest) if x[4] == 'JOBDONE' and x[5] == 'kind=3'), None)
                if done is not None and not any(x[4] == 'WRITE_ATTEMPT' for x in rest[:done]):
                    silent = True
    return dict(trial=t, schedule='reboot' if t.startswith('reb') else 'pending', reaggregated=bool(agg2), reagg_tag=tag2,
                uploaded=bool(tag2 and tag2 in received), post_reboot_summary_job_sent_nothing=silent)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--run', default='results/mutation-v2/M1-union-latest')
    ap.add_argument('--out', default='results/mutation-v2/analysis-m1'); a = ap.parse_args()
    import analyze_test6 as T6
    d = ART / a.run
    with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
        o = T6.run_oracle({'X-M1': d}, tmp, lambda i, plans: plans)
    valid = {r['trial'] for r in o['rows']}
    leak = {r['trial'] for r in o['rows'] if r['tenant'] in AFFECTED and r['violation']}
    received = collections.defaultdict(set)
    for r in jl(d / 'sink/ingest.jsonl'):
        b = r.get('body', {})
        for it in b.get('items', []):
            received[b.get('trial')].add(it['tag'])
    rows = []
    for x in jl(d / 'device_events.jsonl'):
        if x['trial'] in valid:
            f = trial_facts(x['trial'], x['events'], received[x['trial']]); f['leaking'] = x['trial'] in leak; rows.append(f)
    cells = collections.Counter((r['schedule'], r['uploaded'], r['leaking'], r['post_reboot_summary_job_sent_nothing']) for r in rows)
    res = dict(estimand='M1 leak vs whether the re-derived (newest-epoch-labelled) summary reached the sink; exploratory',
               trials=len(rows), leaking=len(leak & valid), reaggregated=sum(r['reaggregated'] for r in rows),
               uploaded=sum(r['uploaded'] for r in rows), leaking_given_uploaded=f"{sum(r['leaking'] and r['uploaded'] for r in rows)}/{sum(r['uploaded'] for r in rows)}",
               leaking_given_not_uploaded=f"{sum(r['leaking'] and not r['uploaded'] for r in rows)}/{sum(not r['uploaded'] for r in rows)}",
               by_schedule={s: dict(trials=sum(r['schedule'] == s for r in rows), uploaded=sum(r['schedule'] == s and r['uploaded'] for r in rows),
                                    leaking=sum(r['schedule'] == s and r['leaking'] for r in rows),
                                    post_reboot_summary_job_sent_nothing=sum(r['schedule'] == s and r['post_reboot_summary_job_sent_nothing'] for r in rows))
                            for s in ('pending', 'reboot')},
               cells={f'{s}/uploaded={u}/leaking={l}/silent_summary_job={q}': n for (s, u, l, q), n in sorted(cells.items())},
               rows=rows)
    out = ART / a.out; assert not out.exists(), f'{out} exists (fresh directory only)'; out.mkdir(parents=True)
    (out / 'm1-trigger.json').write_text(json.dumps(res, indent=1) + '\n')
    print({k: v for k, v in res.items() if k not in ('rows',)})


if __name__ == '__main__':
    main()
