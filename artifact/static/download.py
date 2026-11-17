#!/usr/bin/env python3
"""Download corpus APKs from f-droid.org/repo and verify each SHA-256 against the signed index entry."""
import csv, hashlib, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data/apks")
rows = list(csv.DictReader(open(os.path.join(HERE, "corpus.csv"))))

def get(r):
    fn = os.path.join(OUT, r["url"].rsplit("/", 1)[1])
    for attempt in range(3):
        if os.path.exists(fn) and hashlib.sha256(open(fn, "rb").read()).hexdigest() == r["sha256"]:
            return (r["pkg"], "ok")
        subprocess.run(["curl", "-sS", "-L", "--fail", "-o", fn, r["url"]], timeout=900)
    return (r["pkg"], "FAIL")

with ThreadPoolExecutor(4) as ex:
    res = list(ex.map(get, rows))
bad = [p for p, s in res if s != "ok"]
with open(os.path.join(HERE, "data/download_status.csv"), "w") as f:
    for p, s in res: f.write(f"{p},{s}\n")
print(f"ok={len(res)-len(bad)} fail={len(bad)} {bad[:10]}")
