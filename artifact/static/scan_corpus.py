#!/usr/bin/env python3
"""Scan every downloaded corpus APK with dexscan (parallel), writing data/scan/<pkg>.json."""
import csv, json, os, sys, traceback
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dexscan
OUT = os.path.join(HERE, "data/scan")

def one(r):
    fn = os.path.join(HERE, "data/apks", r["url"].rsplit("/", 1)[1])
    out = os.path.join(OUT, r["pkg"] + ".json")
    if os.path.exists(out):
        return r["pkg"], "cached"
    if not os.path.exists(fn):
        return r["pkg"], "missing"
    try:
        res = dexscan.analyze_apk(fn)
        res.update(pkg=r["pkg"], stratum=r["stratum"], sha256=r["sha256"], versionCode=r["versionCode"])
        json.dump(res, open(out, "w"))
        return r["pkg"], "ok"
    except Exception as e:
        json.dump({"pkg": r["pkg"], "stratum": r["stratum"], "error": repr(e)[:300]}, open(out, "w"))
        return r["pkg"], "error"

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    rows = list(csv.DictReader(open(os.path.join(HERE, "corpus.csv"))))
    with ProcessPoolExecutor(int(sys.argv[1]) if len(sys.argv) > 1 else 6) as ex:
        res = list(ex.map(one, rows))
    from collections import Counter
    print(Counter(s for _, s in res))
