#!/usr/bin/env python3
"""Exploratory check (post hoc, 24/11, not pre-registered) of the G3d batterystats proxy: per run, how many cells had a
non-zero app-UID estimate and a non-zero global CPU component on the Android 15 checkin line. Reads only cells.jsonl and
meta.json; writes <out>/batterystats-check.json.
Usage: bs_check_g3cost.py <run_dir>... --out DIR"""
import argparse, gzip, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import analyze_g3cost as g

p = argparse.ArgumentParser(); p.add_argument('runs', nargs='+', type=Path); p.add_argument('--out', type=Path, required=True); a = p.parse_args()
res = {}
for d in a.runs:
    meta = json.loads((d / 'meta.json').read_text()); cells = [json.loads(l) for l in (open(d / 'cells.jsonl') if (d / 'cells.jsonl').exists() else gzip.open(d / 'cells.jsonl.gz', 'rt')) if l.strip()]
    uid = [g.mah(c.get('bs'), meta['uid'], c.get('bs_checkin')) for c in cells]
    cpu = [re.search(r'^9,0,l,pwi,cpu,([0-9.]+)', c.get('bs_checkin') or '', re.M) for c in cells]
    drain = [re.search(r'Computed drain: ([0-9.]+)', c.get('bs') or '') for c in cells]
    res[d.name] = {'cells': len(cells), 'uid_mah_nonzero': sum(1 for x in uid if x), 'uid_mah_missing': sum(x is None for x in uid),
                   'uid_mah_max': max((x for x in uid if x is not None), default=None),
                   'global_cpu_nonzero': sum(1 for m in cpu if m and float(m.group(1)) > 0), 'global_cpu_missing': sum(m is None for m in cpu),
                   'computed_drain_nonzero': sum(1 for m in drain if m and float(m.group(1)) > 0)}
a.out.mkdir(parents=True, exist_ok=True); (a.out / 'batterystats-check.json').write_text(json.dumps(res, indent=1) + '\n'); print(json.dumps(res, indent=1))
