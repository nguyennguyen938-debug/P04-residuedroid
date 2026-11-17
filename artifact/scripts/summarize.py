#!/usr/bin/env python3
"""Aggregate oracle outcomes into result CSVs (one per table/figure) + summary.json scalars."""
import csv, json, math, os, random, sys, collections, re

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ART, "results")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle

VARIANTS = ["none", "cancel", "enqueue", "jobstart", "conv", "egress", "rd", "volatile", "taint"]
SCHED = ["pending", "kill", "forcestop", "reboot", "revoke", "netloss", "inflight"]
SHORT = {"pending": "pen", "kill": "kill", "forcestop": "fstop", "reboot": "reb", "revoke": "rev", "netloss": "net", "inflight": "infl"}
CORE = [1, 8, 2, 5]          # mediated, attributable, withdrawal covers pending data
FP = [3, 6, 7]               # all items permitted
RUNS = {"A": os.path.join(RES, "raw/c1/A"), "B": os.path.join(RES, "raw/c1/B")}


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def boot_mean(xs, B=2000, seed=7):
    if not xs:
        return (float("nan"),) * 3
    r = random.Random(seed)
    m = sum(xs) / len(xs)
    bs = sorted(sum(r.choice(xs) for _ in xs) / len(xs) for _ in range(B))
    return m, bs[int(0.025 * B)], bs[int(0.975 * B) - 1]


def validity(run_dir):
    bad = {}
    dev = collections.defaultdict(dict)
    procs = collections.defaultdict(dict)
    for l in open(os.path.join(run_dir, "device_events.jsonl")):
        r = json.loads(l)
        dev[r["trial"]][r["pkg"]] = bool(r.get("events"))
        procs[r["trial"]][r["pkg"]] = sum(1 for e in r.get("events", []) if e[4] == "PROC_START")
    for l in open(os.path.join(run_dir, "schedule.jsonl")):
        r = json.loads(l)
        a = r["actions"]
        gaps = [a[i + 1]["t"] - a[i]["t"] for i in range(len(a) - 1)]
        why = []
        if any(g > 200 for g in gaps):
            why.append("host_sleep")
        if any(x["a"] in ("emulator_restarted", "setup_fail", "trial_error") for x in a):
            why.append("restart_or_setup_fail")
        if not all(dev[r["trial"]].values()) or len(dev[r["trial"]]) < len(r["variants"]):
            why.append("device_log")
        if r["schedule"] == "forcestop" and any(n < 2 for n in procs[r["trial"]].values()):
            why.append("relaunch_failed")
        if r.get("device_alive_end") is False:
            why.append("device_dead")
        if r["schedule"] == "netloss" and (not r.get("net_verified_down") or r.get("net_mode") != "per-app-iptables"):
            why.append("net_unverified")
        bad[r["trial"]] = why
    return bad


def main():
    rows, invalid = [], {}
    for run, d in RUNS.items():
        if not os.path.exists(os.path.join(d, "schedule.jsonl")):
            continue
        v = validity(d)
        for t, why in v.items():
            invalid[(run, t)] = why
        for r in oracle.analyze_run(d, run):
            r["valid"] = int(not v.get(r["trial"]))
            rows.append(r)
    with open(os.path.join(RES, "outcomes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    val = [r for r in rows if r["valid"]]
    n_valid_all = len({(r["run"], r["trial"]) for r in val})
    # cap at 50 valid trials per (run, schedule): the first 50 valid k
    ks = collections.defaultdict(set)
    for r in val:
        ks[(r["run"], r["schedule"])].add(r["k"])
    keep = {key: set(sorted(v)[:50]) for key, v in ks.items()}
    val = [r for r in val if r["k"] in keep[(r["run"], r["schedule"])]]
    S = {}
    S["n_trials_total"] = len({(r["run"], r["trial"]) for r in rows})
    S["n_trials_invalid"] = sum(1 for k, w in invalid.items() if w)
    for reason in ("host_sleep", "restart_or_setup_fail", "device_log", "device_dead", "net_unverified", "relaunch_failed"):
        S[f"n_invalid_{reason}"] = sum(1 for w in invalid.values() if reason in w)
    S["n_trials_valid"] = len({(r["run"], r["trial"]) for r in val})
    S["n_trials_valid_all"] = n_valid_all
    S["n_submissions"] = sum(int(r["submissions"]) for r in val)
    per = collections.defaultdict(list)
    for r in val:
        vname = r["variant"] if not (r["variant"] == "rd" and r["run"] == "B") else "rdB"
        per[(vname, r["schedule"], r["tenant"])].append(r)
    # ---- matrix: violation rate over CORE tenants (+ T4 personalization) per variant x schedule
    mat = []
    for v in VARIANTS + ["rdB"]:
        row = {"variant": v}
        for s in SCHED:
            k = n = 0
            items = []
            for t in CORE + [4]:
                for r in per.get((v, s, t), []):
                    n += 1; k += r["violation"]; items.append(r["prohibited_items"])
            p, lo, hi = wilson(k, n)
            row[s] = p; row[s + "_lo"] = lo; row[s + "_hi"] = hi; row[s + "_n"] = n; row[s + "_k"] = k
            row[s + "_items"] = sum(items) / len(items) if items else float("nan")
        mat.append(row)
    write("tab_matrix.csv", mat)
    # ---- per-tenant (pooled over all schedules)
    pt = []
    for v in VARIANTS:
        row = {"variant": v}
        for t in [1, 8, 2, 5, 4, 9, 10]:
            rs = [r for s in SCHED for r in per.get((v, s, t), [])]
            k = sum(r["violation"] for r in rs); n = len(rs)
            p, lo, hi = wilson(k, n)
            row[f"T{t}"] = p; row[f"T{t}_n"] = n
            row[f"T{t}_items"] = sum(r["prohibited_items"] for r in rs) / n if n else float("nan")
        rs10 = [r for s in SCHED for r in per.get((v, s, 10), [])]
        row["T10_unknown"] = sum(r["unknown_subs"] for r in rs10) / len(rs10) if rs10 else float("nan")
        row["T10_gt"] = sum(1 for r in rs10 if r["opaque_gt_late_commits"] > 0) / len(rs10) if rs10 else float("nan")
        pt.append(row)
    write("tab_tenants.csv", pt)
    # ---- false positives: legit deficit vs none (same run, same trial)
    fp = []
    for v in VARIANTS + ["rdB"]:
        row = {"variant": v}
        tot_def = tot_exp = 0
        for t in FP + [4]:
            rs = [r for s in SCHED for r in per.get((v, s, t), []) if not (t == 7 and s != "revoke")]
            defs = [r["legit_expected"] - r["legit_delivered"] for r in rs]
            row[f"T{t}_deficit"] = sum(defs) / len(defs) if defs else float("nan")
            row[f"T{t}_n"] = len(defs)
            row[f"T{t}_anydef"] = sum(1 for x in defs if x > 0) / len(defs) if defs else float("nan")
            tot_def += sum(defs); tot_exp += sum(r["legit_expected"] for r in rs)
        row["deficit_total"] = tot_def
        row["expected_total"] = tot_exp
        row["deficit_frac"] = tot_def / tot_exp if tot_exp else float("nan")
        fp.append(row)
    write("tab_fp.csv", fp)
    # ---- in-flight: violation vs offset (T1,T8,T2,T5 pooled; raw-upload trigger) and theorem prediction
    bins = [(0, 200), (200, 400), (400, 600), (600, 800), (800, 1000), (1000, 1200), (1200, 1400), (1400, 1601)]
    curve = []
    for v in ["none", "cancel", "jobstart", "conv", "egress", "rd"]:
        for lo, hi in bins:
            rs = [r for t in [8, 2, 5] for r in per.get((v, "inflight", t), [])
                  if r["inj_offset_ms"] != "" and lo <= int(r["inj_offset_ms"]) < hi]
            k = sum(r["violation"] for r in rs); n = len(rs)
            p, a, b = wilson(k, n)
            curve.append({"variant": v, "bin_lo": lo, "bin_hi": hi, "mid": (lo + hi) / 2, "n": n, "k": k, "p": p, "lo": a, "hi": b})
    write("fig_inflight.csv", curve)
    S.update(scalars(mat, pt, fp, val, per))
    json.dump(S, open(os.path.join(RES, "summary_campaign.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps({k: S[k] for k in sorted(S)[:40]}, indent=0))


def scalars(mat, pt, fp, val, per):
    S = {}
    m = {r["variant"]: r for r in mat}
    for v in m:
        for s in SCHED:
            S[f"viol_{v}_{s}"] = m[v][s]
            S[f"n_{v}_{s}"] = m[v][s + "_n"]
    return S


def write(name, rows):
    with open(os.path.join(RES, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
