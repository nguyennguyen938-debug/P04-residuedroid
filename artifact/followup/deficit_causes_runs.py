#!/usr/bin/env python3
"""Exploratory (written 21/11, after the B7 freeze, on frozen data): attribute undelivered permitted items in round-3
lifecycle runs to one cause, with the same cause rules as `deficit_causes.py` (fence/policy block, send failure, job
stopped and process not restarted, job stopped and restarted, other) plus one descriptive field per tenant-trial:
`jobs_started` = number of JOBSTART events of that variant in that trial (0 = the observation window closed before
any job ran). Tenants 3, 4, 6, 7 as in `deficit_causes.py`; tenant 5 (re-grant) and mstart are listed separately.
Does not change any analysis, key or validity rule; outputs go to new directories only.

Usage:
  deficit_causes_runs.py mutation --root results/mutation-v2 --out results/mutation-v2/analysis-deficit
  deficit_causes_runs.py test6 --out results/round3/test6/analysis-deficit
  deficit_causes_runs.py selftest   # same causes as deficit_causes.py on the review-followup cohort
"""
import argparse, collections, contextlib, io, json, sys, tempfile
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ART / 'followup'), str(ART / 'scripts')]

POLICY = {"BLOCK", "RETRY_ENTRY_BLOCK", "ENQ_SKIP", "COLLECT_DENIED", "COLLECT_SKIPPED"}   # = deficit_causes.py
FAILURE = {"SEND_FAILED", "NET_FAIL", "JOB_CRASH", "JOB_RETRY_LATER"}
UNAFFECTED = (3, 4, 6, 7)


def jl(p):
    p = Path(p)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def kv(detail):
    return dict(x.split("=", 1) for x in (detail or "").split(";") if "=" in x)


def cause_of(r, ev):
    """deficit_causes.py rule, unchanged."""
    mine = [e for e in ev if e[3] == r["tenant"]]
    kinds = {e[4] for e in mine}
    stops = [e for e in mine if e[4] == "JOB_STOPPED"]
    stopped_kinds = {kv(e[5]).get("kind") for e in stops}
    hit = any(e[4] == "JOB_SKIP" and kv(e[5]).get("kind") in stopped_kinds or
              e[4] == "CANCEL" and stopped_kinds & set(kv(e[5]).get("kinds", "").split(",")) for e in mine)
    if kinds & POLICY or hit:
        return "policy"
    if kinds & FAILURE:
        return "failure"
    if stops:
        last = max(e[0] for e in stops)
        return "stopped_restarted" if any(e[0] > last and e[4] == "PROC_START" for e in ev) else "stopped_no_restart"
    return "other"


def attribute(rows, dev, tenants=UNAFFECTED):
    out = []
    for r in rows:
        if r["tenant"] not in tenants or r["legit_missing"] == 0:
            continue
        ev = dev[r["instance"], r["trial"], r["variant"]]
        out.append(dict(instance=r["instance"], trial=r["trial"], schedule=r["schedule"], variant=r["variant"],
                        tenant=r["tenant"], missing=r["legit_missing"], cause=cause_of(r, ev),
                        jobs_started=sum(e[4] == "JOBSTART" for e in ev)))
    return out


def summarise(out, rows, estimand):
    trials = collections.defaultdict(int)
    for o in out:
        trials[o["instance"], o["trial"]] += o["missing"]
    return dict(estimand=estimand, tenant_trials=len(out), items=sum(o["missing"] for o in out),
                schedules=dict(collections.Counter(o["schedule"] for o in out)),
                causes=dict(collections.Counter(o["cause"] for o in out)),
                items_by_cause={c: sum(o["missing"] for o in out if o["cause"] == c) for c in sorted({o["cause"] for o in out})},
                items_with_no_job_started=sum(o["missing"] for o in out if o["jobs_started"] == 0),
                trials_with_deficit=len(trials), items_by_trial={f"{i}/{t}": n for (i, t), n in sorted(trials.items())},
                by_variant={v: dict(items=sum(o["missing"] for o in out if o["variant"] == v),
                                    causes=dict(collections.Counter(o["cause"] for o in out if o["variant"] == v)))
                            for v in sorted({r["variant"] for r in rows})},
                rows=out)


def devices(instdir):
    dev, plans = {}, {}
    for inst, d in instdir.items():
        for x in jl(Path(d) / "device_events.jsonl"):
            dev[inst, x["trial"], x["pkg"].split(".")[-1]] = x.get("events", [])
        for p in jl(Path(d) / "schedule.jsonl"):
            plans[inst, p["trial"]] = p
    return dev, plans


def run_mutation(root, outdir):
    import analyze_test6 as T6
    res = {}
    for m in ("base", "M1-union-latest", "M2-stale-epoch", "M3-extras-drop"):
        d = Path(root) / m
        if not (d / "schedule.jsonl").exists():
            continue
        inst = f"X-{m}"                                 # = analyze_mutation.py
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            o = T6.run_oracle({inst: d}, tmp, lambda i, plans: plans)
        dev, _ = devices({inst: d})
        out = attribute(o["rows"], dev)
        s = summarise(out, o["rows"], f"cause of each undelivered permitted item (tenants 3, 4, 6, 7), {Path(root).name}/{m}")
        s["permitted_deficit_all_tenants"] = sum(r["legit_missing"] for r in o["rows"])   # = analyze_mutation.py key source
        res[m] = s
    return res


def run_test6(outdir):
    import analyze_test6 as T6
    man = json.loads((ART / "plans/test6/runs.json").read_text())
    instdir = {}
    for dev_key, spec in man["devices"].items():
        _, life = T6.expand(dev_key, spec)
        instdir.update({k: Path(v) for k, v in life.items()})
    rows = json.loads((ART / "results/round3/test6/analysis/matched-outcomes.json").read_text())["rows"]   # frozen analysis
    dev, plans = devices(instdir)
    res = {}
    for d in sorted({r["instance"][0] for r in rows}):
        rs = [r for r in rows if r["instance"][0] == d]
        out = attribute(rs, dev, tenants=(3, 4, 5, 6, 7))
        s = summarise(out, rs, f"cause of each undelivered permitted item (tenants 3-7), Test 6 device {d}")
        nojob = sorted({(o["instance"], o["trial"]) for o in out if o["jobs_started"] == 0})
        s["trials_no_job_started"] = [dict(instance=i, trial=t, quiesced=next((x for x in plans[i, t]["actions"] if x["a"] == "quiesced"), None),
                                           receipts=0) for i, t in nojob]
        s["mstart_tenant5_items"] = sum(o["missing"] for o in out if o["variant"] == "mstart" and o["tenant"] == 5)
        # sensitivity (exploratory, not a validity rule): violating paired trials per (schedule, variant), affected tenants
        # 1, 2, 4, 5, 8 as matched_oracle.py, as analysed vs without the trials where no job started in any variant
        drop = {(i, t) for i, t in nojob}
        for name, skip in (("violating_trials_as_analysed", set()), ("violating_trials_without_no_job_trials", drop)):
            by = collections.defaultdict(int)
            for r in rs:
                if r["tenant"] in (1, 2, 4, 5, 8) and (r["instance"], r["trial"]) not in skip:
                    by[r["schedule"], r["variant"], r["instance"], r["trial"]] |= r["violation"]
            cell = collections.defaultdict(lambda: [0, 0])
            for (sch, v, _, _), x in by.items():
                cell[sch, v][0] += x; cell[sch, v][1] += 1
            s[name] = {f"{sch}/{v}": f"{a}/{n}" for (sch, v), (a, n) in sorted(cell.items())}
        res[d] = s
    return res


def selftest():
    root = ART / "results/review-followup-20261115"
    ref = json.loads((root / "permitted-deficit-causes.json").read_text())["rows"]
    rows = json.loads((root / "matched-outcomes.json").read_text())["rows"]
    dev, _ = devices({i: root / f"matched-{i}" for i in ["A", "A-s1", "A-s2", "A-s3", "B", "B-s1", "B-s2", "B-s3"]})
    mine = [{k: v for k, v in o.items() if k != "jobs_started"} for o in attribute(rows, dev)]
    assert mine == ref, "cause rules differ from deficit_causes.py"
    print(f"selftest OK: {len(mine)} tenant-trials, causes identical to deficit_causes.py")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("mode", choices=["mutation", "test6", "selftest"])
    ap.add_argument("--root"); ap.add_argument("--out"); a = ap.parse_args()
    if a.mode == "selftest":
        return selftest()
    res = run_mutation(ART / a.root, a.out) if a.mode == "mutation" else run_test6(a.out)
    out = ART / a.out; assert not out.exists(), f"{out} exists (fresh directory only)"
    out.mkdir(parents=True)
    (out / "deficit-causes.json").write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8")
    for k, s in res.items():
        print(k, "items", s["items"], "by cause", s["items_by_cause"], "no-job-started items", s["items_with_no_job_started"])


if __name__ == "__main__":
    main()
