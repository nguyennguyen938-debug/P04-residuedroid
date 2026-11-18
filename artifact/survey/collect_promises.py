#!/usr/bin/env python3
"""Test 3 (C10): collect, for each app with a consent signal, the public text that states its promise.

Sources, all offline: the toggle-like strings and consent keys the scanner extracted from the APK
(static/data/scan/*.json) and the app's F-Droid listing (static/data/index/index-v2.json).
Privacy policies are not collected. Writes one markdown file per app into OUT_DIR for labelling,
plus artifact/survey/apps.csv listing the sample. Usage: collect_promises.py OUT_DIR"""
import csv, glob, json, os, re, sys

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ART, "static"))
SCAN = sorted(glob.glob(os.path.join(ART, "static/data/scan/*.json")))
INDEX = os.path.join(ART, "static/data/index/index-v2.json")


def flags(a):
    # Same definitions as static/static_summary.py.
    api, jobs = a["api"], a["jobs"]
    persisted = api["workmanager"] or any(j["kind"] == "worker" for j in jobs) or api["job_persisted"] \
        or api["syncadapter"] or api["legacy_dispatch"]
    net = any(j["reach_network"] for j in jobs)
    net3 = any(j["reach_network"] and j["net_depth"] is not None and j["net_depth"] <= 3 for j in jobs)
    consent = bool(a["consent_keys"]) or bool(a["consent_ui"])
    return dict(consent=consent, cand=persisted and net and consent, cand3=persisted and net3 and consent)


def en(v):
    if isinstance(v, dict):
        return v.get("en-US") or v.get("en") or next(iter(v.values()), "")
    return v or ""


def main(out):
    os.makedirs(out, exist_ok=True)
    idx = json.load(open(INDEX, encoding="utf-8"))["packages"] if os.path.exists(INDEX) else {}
    rows = []
    for f in SCAN:
        a = json.load(open(f, encoding="utf-8"))
        if "error" in a:
            continue
        fl = flags(a)
        if not fl["consent"]:
            continue
        md = idx.get(a["pkg"], {}).get("metadata", {})
        desc = re.sub(r"<[^>]+>", " ", en(md.get("description")))
        rows.append(dict(pkg=a["pkg"], stratum=a["stratum"], candidate=int(fl["cand"]), candidate3=int(fl["cand3"])))
        with open(os.path.join(out, a["pkg"] + ".md"), "w", encoding="utf-8", newline="\n") as w:
            w.write(f"# {a['pkg']}\n\nName: {en(md.get('name'))}\nSummary: {en(md.get('summary'))}\n")
            w.write(f"Source: {md.get('sourceCode', '')}\n\n## Toggle-like strings in the APK\n")
            w.writelines(f"- {s}\n" for s in a["consent_ui"]) if a["consent_ui"] else w.write("(none)\n")
            w.write("\n## Consent-like identifiers in the code\n")
            w.writelines(f"- {s}\n" for s in a["consent_keys"][:30]) if a["consent_keys"] else w.write("(none)\n")
            w.write(f"\n## F-Droid description\n{desc.strip()[:4000]}\n")
    with open(os.path.join(ART, "survey", "apps.csv"), "w", encoding="utf-8", newline="") as w:
        c = csv.DictWriter(w, ["pkg", "stratum", "candidate", "candidate3"]); c.writeheader(); c.writerows(rows)
    print(len(rows), "consent apps;", sum(r["candidate"] for r in rows), "candidates;", sum(r["candidate3"] for r in rows), "three-hop")


if __name__ == "__main__":
    main(sys.argv[1])
