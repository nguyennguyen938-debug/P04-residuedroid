#!/usr/bin/env python3
"""Mechanism gates of test6-card.md §3 for one run directory (pilot or a main run's first trials). Outcome-blind: reads
exit lines, harness fields (harness_error, barrier_seen, remaining, seen_max, kill_verified, device_alive_end), read
errors and line counts only; never violations, accepted-after-ack bytes or latencies.
Usage: check_gates.py <run dir> [--tls N --life N]   (finds tls/ and life/ anywhere below the run dir)
Exit 0 = all gates pass.
"""
import argparse, json, os, re, sys

ap = argparse.ArgumentParser()
ap.add_argument("dir"); ap.add_argument("--tls", type=int, default=7, help="expected TLS trials")
ap.add_argument("--life", type=int, default=3, help="expected lifecycle trials")
a = ap.parse_args()


def find(name):
    hits = [os.path.join(r, name) for r, ds, _ in os.walk(a.dir) if name in ds]
    return sorted(hits, key=len)[0] if hits else None


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()] if p and os.path.exists(p) else []


gates = []
def gate(name, ok, info=""):
    gates.append((name, bool(ok), info))

logs = "".join(open(os.path.join(r, f), errors="ignore").read() for r, _, fs in os.walk(a.dir) for f in fs
               if f.endswith((".log", ".txt")) or "Test_spec_output" in f)
for part in ("TLS", "LIFE"):
    m = re.findall(rf"{part}_EXIT=(\d+)", logs)
    gate(f"{part}_EXIT=0", m and all(x == "0" for x in m), f"found {m}")

tls = find("tls")
tr = jl(tls and os.path.join(tls, "trials.jsonl"))
gate("TLS trials logged", len(tr) == a.tls, f"{len(tr)}/{a.tls}")
gate("TLS no harness_error", tr and not any(r.get("harness_error") for r in tr),
     str([r["case"] for r in tr if r.get("harness_error")]))
bar = [r for r in tr if r["case"].startswith(("buffered", "stall"))]
gate("TLS barrier_seen true in barrier cases", bar and all(r.get("barrier_seen") is True for r in bar),
     f"{sum(r.get('barrier_seen') is True for r in bar)}/{len(bar)}")
rcv = jl(tls and os.path.join(tls, "receiver.jsonl"))
gate("TLS receiver has lines", len(rcv) > 0, f"{len(rcv)} lines")

life = find("life")
sc = jl(life and os.path.join(life, "schedule.jsonl"))
dev = jl(life and os.path.join(life, "device_events.jsonl"))
gate("LIFE trials logged", len(sc) == a.life, f"{len(sc)}/{a.life}")
gate("LIFE no trial_error/setup_fail", sc and not any(x["a"] in ("trial_error", "setup_fail") for r in sc for x in r["actions"]))
q = [x for r in sc for x in r["actions"] if x["a"] == "quiesced"]
gate("LIFE remaining 0", q and all(x.get("remaining") == 0 for x in q), str([x.get("remaining") for x in q]))
gate("LIFE seen_max > 0 (dumpsys parsed)", q and all(x.get("seen_max", 0) > 0 for x in q), str([x.get("seen_max") for x in q]))
kills = [r for r in sc if r["schedule"] == "kill"]
gate("LIFE kill_verified true", kills and all(r.get("kill_verified") is True for r in kills), str([r.get("kill_verified") for r in kills]))
gate("LIFE device_alive_end true", sc and all(r.get("device_alive_end") is True for r in sc))
gate("LIFE DB read without error", dev and not any("error" in d for d in dev), f"{sum('error' in d for d in dev)}/{len(dev)} errors")
mp = life and os.path.join(life, "meta.json")
meta = json.load(open(mp)) if mp and os.path.exists(mp) else {}
gate("LIFE meta root=false, run-as read", meta.get("root") is False and "run-as" in str(meta.get("db_read")), f"{meta.get('model')} Android {meta.get('android')}")
ing = jl(life and os.path.join(life, "sink", "ingest.jsonl"))
gate("LIFE sink received lines", len(ing) > 0, f"{len(ing)} lines")

for name, ok, info in gates:
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {info}")
bad = [g for g in gates if not g[1]]
print("ALL GATES PASS" if not bad else f"{len(bad)} GATE(S) FAIL")
sys.exit(1 if bad else 0)
