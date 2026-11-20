#!/usr/bin/env python3
"""Operational metric for autoresearch Loop A: valid trials per emulator-hour on a PILOT directory.

Reads only host action logs (schedule.jsonl), launch metadata and device-log presence through the repo's own
validity rule (scripts/summarize.validity). It never opens sink/receiver files or oracle outputs, so the
metric is blind to scientific outcomes. Prints one number on the last line (autoresearch Verify contract).
"""
import json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, os.path.join(ROOT, "artifact/scripts"))


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: ops_metric.py <artifact/results/<campaign>/pilot-N>")
    d = os.path.abspath(sys.argv[1])
    if not os.path.basename(d).startswith("pilot"):
        sys.exit("refusing: Loop A may only score pilot-* directories (R2.2)")
    sched = os.path.join(d, "schedule.jsonl")
    rows = [json.loads(l) for l in open(sched) if l.strip()]
    if not rows:
        print("0"); return
    try:
        from summarize import validity
        bad = validity(d)
        valid = sum(1 for r in rows if not bad.get(r["trial"]))
    except Exception:                      # campaigns without device_events.jsonl: action-log rules only
        def ok(r):
            a = r.get("actions", [])
            gaps = [a[i + 1]["t"] - a[i]["t"] for i in range(len(a) - 1)]
            return a and not any(g > 200 for g in gaps) and not any(
                x.get("a") in ("emulator_restarted", "setup_fail", "trial_error") for x in a)
        valid = sum(1 for r in rows if ok(r))
    t0 = min(r["actions"][0]["t"] for r in rows if r.get("actions"))
    t1 = max(r["actions"][-1]["t"] for r in rows if r.get("actions"))
    meta = os.path.join(d, "meta.json")
    if os.path.exists(meta):
        t0 = min(t0, json.load(open(meta)).get("start", t0))
    hours = max(1e-6, (t1 - t0) / 3600)
    print(f"logged={len(rows)} valid={valid} yield={valid / len(rows):.2f} wall_h={hours:.2f}", file=sys.stderr)
    print(f"{valid / hours:.3f}")


if __name__ == "__main__":
    main()
