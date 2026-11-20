#!/usr/bin/env python3
"""Machine-checkable progress of P04 run directories (for /loop, Monitor, ScheduleWakeup).

Reads only host action logs, launch metadata, device-log presence (validity rule) and the autorun stage log.
Never opens sink/receiver files or oracle outputs. Last line is one JSON object.
Usage: status.py <run_dir> [<run_dir> ...] [--target N] [--serial emulator-5660 ...]
"""
import argparse, json, os, subprocess, sys, time
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
sys.path.insert(0, os.path.join(ROOT, "artifact/scripts"))


def one(d, target):
    p = os.path.join(d, "schedule.jsonl")
    rows = [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []
    try:
        from summarize import validity
        bad = validity(d) if rows else {}
    except Exception:
        bad = {r["trial"]: [] if not any(x.get("a") in ("emulator_restarted", "setup_fail", "trial_error")
                                         for x in r.get("actions", [])) else ["restart_or_setup_fail"] for r in rows}
    logged = Counter(r.get("schedule") for r in rows)
    valid = Counter(r.get("schedule") for r in rows if not bad.get(r["trial"]))
    reasons = Counter(w for r in rows for w in bad.get(r["trial"], []))
    last = max((r["actions"][-1]["t"] for r in rows if r.get("actions")), default=None)
    done = bool(target) and valid and all(v >= target for v in valid.values())
    return dict(dir=os.path.relpath(d, ROOT), logged=sum(logged.values()), valid=sum(valid.values()),
                valid_by_schedule=dict(valid), invalid_reasons=dict(reasons),
                last_action_age_s=round(time.time() - last) if last else None, target_met=done)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--target", type=int, default=0)
    ap.add_argument("--serial", nargs="*", default=[])
    a = ap.parse_args()
    out = [one(os.path.abspath(d), a.target) for d in a.dirs]
    alive = {}
    adb = os.path.join(os.environ.get("ANDROID_HOME", ""), "platform-tools", "adb")
    for s in a.serial:
        try:
            r = subprocess.run([adb, "-s", s, "shell", "getprop", "sys.boot_completed"], capture_output=True, text=True, timeout=10)
            alive[s] = r.stdout.strip() == "1"
        except Exception:
            alive[s] = False
    for o in out:
        stale = o["last_action_age_s"] is not None and o["last_action_age_s"] > 600
        print(f"{o['dir']}: valid {o['valid']}/{o['logged']} {o['valid_by_schedule']} last action {o['last_action_age_s']} s"
              f"{'  STALE>600s' if stale else ''}{'  TARGET MET' if o['target_met'] else ''}", file=sys.stderr)
    print(json.dumps(dict(runs=out, emulators=alive, t=round(time.time()))))


if __name__ == "__main__":
    main()
