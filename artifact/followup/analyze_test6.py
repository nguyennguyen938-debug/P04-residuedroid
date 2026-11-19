#!/usr/bin/env python3
"""Test 6 (physical phones) analysis, per device: TLS suite and fixture lifecycle without reboot.

Written before the final runs (artifact/plans/test6-card.md, section 3/4); validity code reads no outcome field.

Lifecycle: the matched-campaign oracle `followup/matched_oracle.py` is executed unchanged except for its input/output
locations and its run list (string substitutions, each asserted to match exactly), so violations, unknowns, deficits,
the paired bootstrap and the contrasts are computed by the same code as the published matched campaign. On top of its
own validity rules (trial_error/setup_fail/emulator_restarted, action gap > 200 s, device not alive at the end, missing
paired log) phone runs add, before the oracle sees a trial:
  - kill schedule without kill_verified == true (fault not confirmed, R2.4)        -> 'kill not verified'
  - no job of ours ever parsed while waiting (seen_max <= 0)                        -> 'jobs not observable'
Then the first N valid paired trials per (device, schedule) in k order are analysed; later valid ones are 'unused'.

TLS: a trial is invalid if it has harness_error, or if a buffered/stall case did not reach its barrier (barrier_seen is
not true). A block (one pass over the 7 cases) is valid only if all its cases are valid; the first N valid blocks per
device in block order are analysed. Per-trial quantities follow followup/analyze_tls.py (without its assertion: a
fence trial accepting bytes after the acknowledgement is reported, not raised).

Usage: analyze_test6.py [--manifest plans/test6/runs.json] [--out results/round3/test6/analysis] [--n 20]
"""
import argparse, collections, json, os, re, sys, tempfile
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART / "scripts"))
from summarize import wilson  # noqa: E402

CASES = ["control", "early", "buffered-fence", "buffered-early", "stall-small", "stall-large", "concurrent"]
BARRIER = {"buffered-fence", "buffered-early", "stall-small", "stall-large"}
FENCE = ["buffered-fence", "stall-small", "stall-large"]
SCHEDULES = ["pending", "kill", "revoke"]


def jl(p):
    p = Path(p)
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def fields(s):
    return dict(x.split("=", 1) for x in (s or "").split(";") if "=" in x)


# ---------------------------------------------------------------- TLS
def tls_row(r):
    es = r.get("events", [])
    acks = [e["mono_ns"] for e in es if e["kind"] == "WITHDRAW_ACK"]
    req = [e["mono_ns"] for e in es if e["kind"] == "WITHDRAW_REQUEST"]
    accepted = [(e["mono_ns"], int(fields(e["detail"]).get("n", 0))) for e in es if e["kind"] == "BYTES_ACCEPTED"]
    done = [fields(e["detail"]) for e in es if e["kind"] == "SEND_OK"]
    return {"trial": r["trial"], "case": r["case"], "block": r["block"], "successful_sends": len(done),
            "early_blocks": sum(e["kind"] == "EARLY_BLOCK" for e in es), "policy_blocks": sum(e["kind"] == "BLOCK" for e in es),
            "acks": len(acks), "after_ack_accepted": sum(n for t, n in accepted if acks and t > acks[0]),
            "ack_ms": (acks[0] - req[0]) / 1e6 if acks and req else None,
            "elapsed_ms": [int(d["elapsed_ns"]) / 1e6 for d in done if "elapsed_ns" in d]}


def tls_validity(r):
    """Reason string or None. Reads only harness fields (harness_error, barrier_seen), never outcome events."""
    if r.get("harness_error"):
        return "harness error"
    if r["case"] in BARRIER and r.get("barrier_seen") is not True:
        return "barrier not reached"
    return None


def analyse_tls(dirs, n):
    trials, dup = {}, []
    for d in dirs:
        for r in jl(Path(d) / "trials.jsonl"):
            key = (r["block"], r["case"])
            if key in trials:
                dup.append(r["trial"]); continue      # first record kept (directory order), duplicates listed
            trials[key] = r
    blocks = sorted({b for b, _ in trials})
    invalid, valid_blocks = [], []
    for b in blocks:
        reasons = {c: (tls_validity(trials[b, c]) if (b, c) in trials else "missing") for c in CASES}
        bad = {c: why for c, why in reasons.items() if why}
        if bad:
            invalid.append({"block": b, "reasons": bad})
        else:
            valid_blocks.append(b)
    used, unused = valid_blocks[:n], valid_blocks[n:]
    rows = [tls_row(trials[b, c]) for b in used for c in CASES]
    per_case = {}
    for c in CASES:
        rs = [r for r in rows if r["case"] == c]
        k_after = sum(r["after_ack_accepted"] > 0 for r in rs)
        per_case[c] = {"trials": len(rs), "successful_sends": sum(r["successful_sends"] for r in rs),
                       "blocked_trials": sum(r["policy_blocks"] + r["early_blocks"] > 0 for r in rs),
                       "trials_after_ack_accepted": k_after, "after_ack_wilson95": list(wilson(k_after, len(rs))[1:]) if rs else None,
                       "after_ack_bytes_total": sum(r["after_ack_accepted"] for r in rs)}
    return {"blocks_logged": len(blocks), "blocks_invalid": invalid, "blocks_valid": len(valid_blocks),
            "blocks_analyzed": used, "blocks_unused": unused, "duplicate_records": dup, "per_case": per_case, "rows": rows}


# ---------------------------------------------------------------- lifecycle
def phone_validity(plan):
    """Extra phone rules; reason string or None. Reads only harness/fault fields."""
    if plan.get("schedule") == "kill" and plan.get("kill_verified") is not True:
        return "kill not verified"
    q = [a for a in plan.get("actions", []) if a.get("a") == "quiesced"]
    if q and q[-1].get("seen_max", 1) <= 0:
        return "jobs not observable"
    return None


def oracle_source():
    src = (ART / "followup" / "matched_oracle.py").read_text()
    subs = [("ROOT=ART/'results/review-followup-20261115'\n", "ROOT=OUTDIR\n", 1),
            ("for instance in ['A','A-s1','A-s2','A-s3','B','B-s1','B-s2','B-s3']:", "for instance in INSTANCES:", 1),
            ("root=ROOT/f'matched-{instance}';schedules=jl(root/'schedule.jsonl')",
             "root=INSTDIR[instance];schedules=PLAN_FILTER(instance,jl(root/'schedule.jsonl'))", 1),
            ("for run in ['A','B']:", "for run in RUNS:", 2)]
    for old, new, count in subs:
        assert src.count(old) == count, f"matched_oracle.py changed: {old!r} found {src.count(old)} times"
        src = src.replace(old, new)
    return src


def run_oracle(instdir, outdir, plan_filter):
    Path(outdir).mkdir(parents=True, exist_ok=True)
    g = {"__name__": "matched_oracle_test6", "__file__": str(ART / "followup" / "matched_oracle.py"),
         "OUTDIR": Path(outdir), "INSTANCES": list(instdir), "INSTDIR": {k: Path(v) for k, v in instdir.items()},
         "RUNS": sorted({i[0] for i in instdir}), "PLAN_FILTER": plan_filter}
    exec(compile(oracle_source(), "matched_oracle.py(test6)", "exec"), g)
    return json.loads((Path(outdir) / "matched-outcomes.json").read_text())


def analyse_life(instdir, outdir, n):
    extra = []

    def pass1(instance, plans):
        keep = []
        for p in plans:
            why = phone_validity(p)
            if why:
                extra.append({"run": instance[0], "instance": instance, "trial": p["trial"], "reason": why})
            else:
                keep.append(p)
        return keep

    with tempfile.TemporaryDirectory() as tmp:
        first = run_oracle(instdir, tmp, pass1)
    valid = collections.defaultdict(set)
    for r in first["rows"]:
        valid[r["instance"][0], r["schedule"]].add((r["k"], r["instance"], r["trial"]))
    chosen, unused = set(), []
    for key, trials in valid.items():
        ordered = sorted(trials)
        chosen |= {(i, t) for _, i, t in ordered[:n]}
        unused += [{"run": key[0], "schedule": key[1], "k": k, "instance": i, "trial": t} for k, i, t in ordered[n:]]
    extra.clear()
    final = run_oracle(instdir, outdir, lambda inst, plans: [p for p in pass1(inst, plans) if (inst, p["trial"]) in chosen])
    logged = collections.Counter()
    for inst, d in instdir.items():
        for p in jl(Path(d) / "schedule.jsonl"):
            logged[inst[0], p["schedule"]] += 1
    analysed = collections.Counter((r["instance"][0], r["schedule"]) for r in final["rows"]
                                   if r["tenant"] == 1 and r["variant"] == "mboth")
    return {"logged": {f"{a}/{b}": c for (a, b), c in sorted(logged.items())},
            "invalid_oracle_rules": final["invalid_trials"], "invalid_phone_rules": extra, "unused_valid": unused,
            "analyzed_paired_trials": {f"{a}/{b}": c for (a, b), c in sorted(analysed.items())}}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(ART / "plans/test6/runs.json"))
    ap.add_argument("--out", default=str(ART / "results/round3/test6/analysis"))
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    man = json.loads(Path(a.manifest).read_text())
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    res = {"n_target": a.n, "devices": {}}
    instdir = {}
    for dev, spec in man["devices"].items():
        assert len(dev) == 1, "device keys are one letter (the oracle takes run = instance[0])"
        res["devices"][dev] = {k: spec.get(k) for k in ("label", "model", "android", "environment", "receiver_mode")}
        res["devices"][dev]["tls"] = analyse_tls([ART / p for p in spec.get("tls", [])], a.n)
        for inst, p in spec.get("life", {}).items():
            assert inst[0] == dev, f"instance {inst} must start with device key {dev}"
            instdir[inst] = ART / p
    if instdir:
        res["lifecycle"] = analyse_life(instdir, out, a.n)
    used = lambda dev: res["devices"][dev]["tls"]["per_case"]
    devs = list(res["devices"])
    res["summary_candidates"] = {      # definitions proposed in test6-card.md §4; C confirms before summary.json
        "devModel": ", ".join(str(res["devices"][d]["label"]) for d in devs),
        "devAndroid": ", ".join(str(res["devices"][d]["android"]) for d in devs),
        "devTrials": sum(used(d)[c]["trials"] for d in devs for c in ("buffered-fence", "buffered-early")),
        "devEarlyComplete": sum(used(d)["buffered-early"]["successful_sends"] for d in devs),
        "devFenceAfterAck": sum(used(d)[c]["trials_after_ack_accepted"] for d in devs for c in FENCE),
        "devFenceTrials": sum(used(d)[c]["trials"] for d in devs for c in FENCE)}
    (out / "test6-summary.json").write_text(json.dumps(res, indent=1, default=list) + "\n")
    for d in devs:
        t = res["devices"][d]["tls"]
        print(f"{d} TLS: blocks logged {t['blocks_logged']}, invalid {len(t['blocks_invalid'])}, valid {t['blocks_valid']}, "
              f"analyzed {len(t['blocks_analyzed'])}, unused {len(t['blocks_unused'])}")
    if instdir:
        L = res["lifecycle"]
        print("lifecycle logged", L["logged"], "| invalid (oracle rules)", len(L["invalid_oracle_rules"]),
              "| invalid (phone rules)", len(L["invalid_phone_rules"]), "| unused", len(L["unused_valid"]),
              "| analyzed", L["analyzed_paired_trials"])


if __name__ == "__main__":
    main()
