#!/usr/bin/env python3
"""Select the F-Droid corpus: every app whose latest version requests INTERNET and carries the Tracking
anti-feature, plus a seeded random sample of other INTERNET apps. Writes corpus.csv (pkg, version, url, sha256, size, stratum)."""
import csv, json, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
idx = json.load(open(os.path.join(HERE, "data/index/index-v2.json")))
N_RANDOM, SEED, MAXSIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 300, 20271204, 80 * 2**20
rows = []
for pkg, p in idx["packages"].items():
    vs = sorted(p["versions"].values(), key=lambda v: v["manifest"].get("versionCode", 0))
    if not vs:
        continue
    v = vs[-1]
    perms = {x["name"] for x in (v["manifest"].get("usesPermission") or [])}
    if "android.permission.INTERNET" not in perms or v["file"]["size"] > MAXSIZE:
        continue
    af = sorted((v.get("antiFeatures") or {}).keys())
    rows.append(dict(pkg=pkg, versionCode=v["manifest"].get("versionCode"), versionName=v["manifest"].get("versionName"),
                     url="https://f-droid.org/repo" + v["file"]["name"], sha256=v["file"]["sha256"], size=v["file"]["size"],
                     antifeatures="|".join(af), categories="|".join(p["metadata"].get("categories", [])),
                     targetSdk=(v["manifest"].get("usesSdk") or {}).get("targetSdkVersion", "")))
track = [r for r in rows if "Tracking" in r["antifeatures"].split("|")]
rest = sorted([r for r in rows if r not in track], key=lambda r: r["pkg"])
rnd = random.Random(SEED).sample(rest, min(N_RANDOM, len(rest)))
for r in track: r["stratum"] = "tracking"
for r in rnd: r["stratum"] = "random"
sel = sorted(track, key=lambda r: r["pkg"]) + sorted(rnd, key=lambda r: r["pkg"])
with open(os.path.join(HERE, "corpus.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(sel[0].keys())); w.writeheader(); w.writerows(sel)
print(f"eligible INTERNET apps={len(rows)} tracking={len(track)} random={len(rnd)} total_bytes={sum(r['size'] for r in sel)/2**30:.2f}GiB")
