#!/usr/bin/env python3
"""Test-time label checker for the mutation study (test 2).

For every item the receiver got, the label the fence checked (exposed by patch I0) must cover every
source the tracer finds in the item's content: one `scope:epoch` per source record, with the source's
collection epoch. Items without a label are `missing`; items whose label omits a source are `incomplete`.
The runtime oracle decides violations separately; this script only judges labels.

Usage: label_check.py --name M1 RUN_DIR [RUN_DIR ...]   (RUN_DIR contains sink/ingest.jsonl)
"""
import argparse, collections, json, re, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART / "scripts"))
from oracle import item_sources  # noqa: E402  (tracer: raw tag, or the srcs= list of a summary)

# Tenant scopes come from the fixture itself, so the checker cannot drift from Model.java.
SCOPES = {int(i): s for i, s in re.findall(r'new Tenant\((\d+),\s*"[^"]*",\s*"([^"]*)"',
                                            (ART / "fixture/src/org/residuelab/Model.java").read_text(encoding="utf-8"))}
UNCOVERED = {9, 10}  # raw-socket and encrypted tenants: no mediated label by design


def verdict(item):
    need = {f"{SCOPES[t]}:{e}" for t, e, _ in item_sources(item)}
    have = set(filter(None, (item.get("labels") or "").split(",")))
    if not have:
        return "missing", need
    return ("incomplete", need - have) if need - have else ("ok", set())


def check(receipts):
    out = collections.Counter(); bad = []
    for r in receipts:
        b = r.get("body", {})
        if b.get("tenant") in UNCOVERED:
            continue
        for it in b.get("items", []):
            v, gap = verdict(it)
            out[b.get("variant"), v] += 1
            if v != "ok" and len(bad) < 20:
                bad.append(dict(trial=b.get("trial"), tenant=b.get("tenant"), tag=it["tag"], verdict=v, uncovered=sorted(gap)))
    return out, bad


def demo():
    raw = {"tag": "RD-pen000-T5-e0-03", "kind": "raw", "srcs": "", "payload": "evt=x;v=1"}
    assert verdict(dict(raw, labels="analytics:0"))[0] == "ok"
    assert verdict(dict(raw, labels="analytics:1")) == ("incomplete", {"analytics:0"})  # M2 shape
    assert verdict(raw)[0] == "missing"                                                  # M3 shape
    summ = {"tag": "RD-pen000-T5-sum-16", "kind": "derived", "srcs": "",
            "payload": "count=2;sum=3;srcs=RD-pen000-T5-e0-00|RD-pen000-T5-e1-12"}
    assert verdict(dict(summ, labels="analytics:0,analytics:1"))[0] == "ok"
    assert verdict(dict(summ, labels="analytics:1")) == ("incomplete", {"analytics:0"})  # M1 shape
    assert SCOPES[4] == "profile" and SCOPES[7] == "location"


if __name__ == "__main__":
    demo()
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="mutant or baseline name recorded in the output")
    ap.add_argument("--out", help="write the JSON summary here")
    ap.add_argument("runs", nargs="*")
    a = ap.parse_args()
    if not a.runs:
        print("self-check passed"); sys.exit(0)
    receipts = [json.loads(l) for d in a.runs for l in (Path(d) / "sink/ingest.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    counts, bad = check(receipts)
    res = dict(name=a.name, runs=a.runs, counts={f"{v}/{k}": n for (v, k), n in sorted(counts.items())}, examples=bad)
    print(json.dumps(res, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
