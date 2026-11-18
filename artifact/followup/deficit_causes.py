#!/usr/bin/env python3
"""Attribute every undelivered permitted item (T3, T4 backup, T6, T7) in the enlarged matched campaign
to one cause, from the device trace of that tenant in that trial. Causes are checked in this order, so
they are mutually exclusive: fence block, send failure, job stopped and process not restarted before
the observation window closed, job stopped and process restarted, other."""
import collections, json, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "results/review-followup-20261115"
INSTANCES = ["A", "A-s1", "A-s2", "A-s3", "B", "B-s1", "B-s2", "B-s3"]


def jl(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


rows = json.loads((ROOT / "matched-outcomes.json").read_text(encoding="utf-8"))["rows"]
dev, plans = {}, {}
for inst in INSTANCES:
    for d in jl(ROOT / f"matched-{inst}/device_events.jsonl"):
        dev[inst, d["trial"], d["pkg"].split(".")[-1]] = d["events"]
    for p in jl(ROOT / f"matched-{inst}/schedule.jsonl"):
        plans[inst, p["trial"]] = p


def kv(detail):
    return dict(x.split("=", 1) for x in detail.split(";") if "=" in x)


# Fixture event names (fixture/src, transport/src). UpJob.onStopJob returns false, so a stopped job is not rescheduled.
POLICY = {"BLOCK", "RETRY_ENTRY_BLOCK", "ENQ_SKIP", "COLLECT_DENIED", "COLLECT_SKIPPED"}
FAILURE = {"SEND_FAILED", "NET_FAIL", "JOB_CRASH", "JOB_RETRY_LATER"}


out, windows, stop_reasons, cancel_hits = [], [], collections.Counter(), 0
for r in rows:
    if r["tenant"] not in (3, 4, 6, 7) or r["legit_missing"] == 0:
        continue
    ev = dev[r["instance"], r["trial"], r["variant"]]
    mine = [e for e in ev if e[3] == r["tenant"]]
    kinds = {e[4] for e in mine}
    stops = [e for e in mine if e[4] == "JOB_STOPPED"]
    stopped_kinds = {kv(e[5]).get("kind") for e in stops}
    # JOB_SKIP and CANCEL count only when they hit the job kind that left items behind.
    hit = any(e[4] == "JOB_SKIP" and kv(e[5]).get("kind") in stopped_kinds or
              e[4] == "CANCEL" and stopped_kinds & set(kv(e[5]).get("kinds", "").split(",")) for e in mine)
    if kinds & POLICY or hit:
        cause = "policy"
    elif kinds & FAILURE:
        cause = "failure"
    elif stops:
        last = max(e[0] for e in stops)
        restarted = any(e[0] > last and e[4] == "PROC_START" for e in ev)
        cause = "stopped_restarted" if restarted else "stopped_no_restart"
        for e in mine:
            if e[4] == "ONSTOP":
                stop_reasons[kv(e[5]).get("reason")] += 1
    else:
        cause = "other"
    cancel_hits += hit
    a = {x["a"]: x["t"] for x in plans[r["instance"], r["trial"]]["actions"]}
    if "boot_completed" in a and "read_done" in a:
        windows.append(a["read_done"] - a["boot_completed"])
    out.append(dict(instance=r["instance"], trial=r["trial"], schedule=r["schedule"], variant=r["variant"],
                    tenant=r["tenant"], missing=r["legit_missing"], cause=cause))

by_variant = {}
for v in ["menqueue", "mstart", "mlayer", "mfence", "mboth"]:
    rs = [o for o in out if o["variant"] == v]
    by_variant[v] = dict(tenant_trials=len(rs), items=sum(o["missing"] for o in rs),
                         causes=dict(collections.Counter(o["cause"] for o in rs)),
                         reboot_tenant_trials=sum(1 for r in rows if r["variant"] == v and r["schedule"] == "reboot" and r["tenant"] in (3, 4, 6, 7)))
summary = dict(
    estimand="cause of each undelivered permitted item, enlarged matched campaign",
    tenant_trials=len(out), items=sum(o["missing"] for o in out),
    schedules=dict(collections.Counter(o["schedule"] for o in out)),
    causes=dict(collections.Counter(o["cause"] for o in out)),
    onstop_reasons=dict(stop_reasons), policy_hits_on_stopped_job=cancel_hits,
    stopped_without_deficit=dict(collections.Counter(
        r["schedule"] for r in rows if r["tenant"] in (3, 4, 6, 7) and r["legit_missing"] == 0 and
        any(e[3] == r["tenant"] and e[4] == "JOB_STOPPED" for e in dev.get((r["instance"], r["trial"], r["variant"]), [])))),
    window_after_boot_s=dict(median=statistics.median(windows), min=min(windows), max=max(windows)) if windows else None,
    by_variant=by_variant, rows=out)
(ROOT / "permitted-deficit-causes.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
print("deficits", summary["tenant_trials"], "tenant-trials,", summary["items"], "items; causes", summary["causes"])

if __name__ == "__main__":
    # Self-check: every deficit gets exactly one cause and the per-variant totals match the oracle output.
    assert sum(sum(b["causes"].values()) for b in by_variant.values()) == len(out)
    for v, b in by_variant.items():
        assert b["items"] == sum(r["legit_missing"] for r in rows if r["variant"] == v and r["tenant"] in (3, 4, 6, 7)), v
