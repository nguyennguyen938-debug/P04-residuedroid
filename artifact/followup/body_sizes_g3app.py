#!/usr/bin/env python3
"""G3c: sizes of the donation bodies the sink logged complete, per build (C's check on issue #7, 23/11: the body is not
always 262,625 B). Counts (build, bytes) over sink/ingest.jsonl donate_data records with complete=true; descriptive only.
Usage: body_sizes_g3app.py <run dir> [more] --out F"""
import argparse, collections, json
from pathlib import Path
ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--out', required=True); a = ap.parse_args()
res = {}
for d in a.dirs:
    c = collections.Counter(f"{x.get('variant')}/{x.get('bytes')}" for x in map(json.loads, open(Path(d) / 'sink/ingest.jsonl'))
                            if x.get('path') == 'donate_data' and x.get('complete'))
    res[d] = dict(sorted(c.items()))
Path(a.out).write_text(json.dumps(res, indent=1) + '\n'); print(json.dumps(res))
