#!/usr/bin/env python3
"""Contract oracle for the ResidueDroid campaign.

The oracle never uses the app's enforcement decisions or labels. It uses:
  * the sink log (what crossed the network; tags are synthetic tracer strings visible in plaintext payloads,
    derived summaries carry their source tags in their content),
  * the per-tenant stated contract (re-implemented here independently of the Java code),
  * the device event log only for ORDERING: one persistent sequence shared by withdrawals and egress commits.

Output: one row per (run, trial, schedule, variant, tenant) in outcomes.csv.
"""
import csv, json, os, re, sys, collections

# ---- stated contracts (one per fixture tenant) -------------------------------------------------------------
# revoked: purposes covered by the withdrawal ("*" = all); pending: does the withdrawal also cover data collected
# BEFORE it (stop use of existing data) or only future collection.
CONTRACT = {
    1: dict(name="optout-misdecl", kind="in-app opt-out", revoked="*", pending=True, withdrawn=True),
    2: dict(name="delete", kind="deletion request", revoked="*", pending=True, withdrawn=True),
    3: dict(name="optout-flush", kind="in-app opt-out (flush allowed)", revoked="*", pending=False, withdrawn=True),
    4: dict(name="restrict", kind="processing restriction", revoked={"personalization"}, pending=True, withdrawn=True),
    5: dict(name="reconsent", kind="opt-out then re-consent", revoked="*", pending=True, withdrawn=True),
    6: dict(name="control", kind="no withdrawal", revoked="*", pending=True, withdrawn=False),
    7: dict(name="os-location", kind="OS permission revocation", revoked=set(), pending=False, withdrawn=False),
    8: dict(name="optout-decl", kind="in-app opt-out", revoked="*", pending=True, withdrawn=True),
    9: dict(name="unmediated", kind="in-app opt-out (raw socket)", revoked="*", pending=True, withdrawn=True),
    10: dict(name="opaque", kind="in-app opt-out (encrypted body)", revoked="*", pending=True, withdrawn=True),
}
# purposes each tenant uploads for, and number of records per purpose that exist by the end of a trial
UPLOADS = {t: ["analytics"] for t in (1, 2, 3, 5, 6, 8, 9, 10)}
UPLOADS[4] = ["backup", "personalization"]
UPLOADS[7] = ["history"]
SUMMARY_PURPOSE = {1: "diagnostics", 2: "analytics", 3: "analytics", 5: "analytics", 6: "analytics", 8: "analytics"}

SINK_DELAY_S = 0.3
TAG_RAW = re.compile(r"^RD-(\w+)-T(\d+)-e(\d+)-(\d+)$")
TAG_SUM = re.compile(r"^RD-(\w+)-T(\d+)-sum-(\d+)$")


def revokes(t, purpose):
    r = CONTRACT[t]["revoked"]
    return r == "*" or purpose in r


def prohibited_source(t, epoch, purpose, n_withdrawals_before):
    """A source record collected in `epoch` is prohibited for `purpose` at a commit preceded by n withdrawals."""
    c = CONTRACT[t]
    if not revokes(t, purpose) or not c["pending"]:
        return False
    return epoch < n_withdrawals_before


def item_sources(it):
    tag = it["tag"]
    m = TAG_RAW.match(tag)
    if m:
        return [(int(m.group(2)), int(m.group(3)), tag)]
    m = TAG_SUM.match(tag)
    if m:
        p = it.get("payload", "")
        srcs = p.split("srcs=", 1)[1].split("|") if "srcs=" in p else []
        out = []
        for s in srcs:
            mm = TAG_RAW.match(s)
            if mm:
                out.append((int(mm.group(2)), int(mm.group(3)), s))
        return out
    return []


def final_legit(t, trial, n_rec, n_new):
    """Tags (per purpose) the contract permits to be delivered at ANY time after the trial's withdrawal."""
    out = set()
    c = CONTRACT[t]
    for p in UPLOADS[t]:
        if not c["withdrawn"] or not revokes(t, p) or not c["pending"]:
            for i in range(n_rec):
                out.add((p, f"RD-{trial}-T{t}-e0-{i:02d}"))
        if t == 5:
            for i in range(n_new):
                out.add((p, f"RD-{trial}-T{t}-e1-{n_rec + i:02d}"))
    if t in SUMMARY_PURPOSE:
        p = SUMMARY_PURPOSE[t]
        if not c["withdrawn"] or not c["pending"]:
            out.add((p, f"RD-{trial}-T{t}-sum-{n_rec:02d}"))
    return out


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(l) for l in f if l.strip()]


def analyze_run(run_dir, run_name):
    sched = {r["trial"]: r for r in load_jsonl(os.path.join(run_dir, "schedule.jsonl"))}
    dev = collections.defaultdict(dict)
    for r in load_jsonl(os.path.join(run_dir, "device_events.jsonl")):
        dev[r["trial"]][r["pkg"].split(".")[-1]] = r
    ingest = load_jsonl(os.path.join(run_dir, "sink", "ingest.jsonl"))
    acks = load_jsonl(os.path.join(run_dir, "sink", "ack.jsonl"))
    ack_t = {}
    for a in acks:
        b = a["body"]
        if b.get("kind") == "WITHDRAW":
            key = (b["trial"], b["pkg"].split(".")[-1], b["tenant"])
            ack_t[key] = min(ack_t.get(key, 1e18), a["t_host"])
    by = collections.defaultdict(list)
    for r in ingest:
        b = r["body"]
        if "opaque" in b:
            by[(r.get("x_trial"), (r.get("x_app") or "?").split(".")[-1], "opaque")].append(r)
        elif "items" in b:
            by[(b["trial"], b["variant"], b["tenant"])].append(r)
    rows = []
    for trial, lg in sched.items():
        quiesce_t = [a["t"] for a in lg["actions"] if a["a"] == "quiesced"][-1]
        for v in lg["variants"]:
            vb = v[2:] if v.startswith(("al", "wm")) else v   # substrate builds report the base variant name
            d = dev.get(trial, {}).get(v, {})
            ev = d.get("events", [])
            wseq = collections.defaultdict(list)
            sid_seq, commits_after = {}, collections.Counter()
            jobstarts = collections.Counter()
            for e in ev:
                seq, tw, tel, ten, kind, det = e
                if kind == "WITHDRAW":
                    wseq[ten].append(seq)
                if kind in ("COMMIT", "UNMEDIATED_COMMIT"):
                    m = re.search(r"sid=([\w-]+)", det)
                    if m:
                        sid_seq[m.group(1)] = seq
                if kind == "JOBSTART":
                    jobstarts[ten] += 1
            inj = (lg.get("inj") or {})
            for t in range(1, 11):
                c = CONTRACT[t]
                subs = by.get((trial, vb, t), [])
                n_new = 4 if t == 5 else 0
                legit = final_legit(t, trial, 12, n_new)
                delivered = set()
                prohib_tags, prohib_subs, outstanding, total_subs = set(), 0, 0, 0
                order_fallback = 0
                for r in subs:
                    b = r["body"]
                    if r["t_host"] > quiesce_t + 1.0:
                        continue  # outside the observation window
                    total_subs += 1
                    purpose = r["path"].split("/")[-1]
                    cs = b.get("commit_seq", "")
                    seq = int(cs) if cs.isdigit() else sid_seq.get(b.get("sid"))
                    if seq is not None:
                        nW = sum(1 for w in wseq.get(t, []) if w < seq)
                    else:  # no device ordering: conservative host-time ordering
                        order_fallback += 1
                        at = ack_t.get((trial, v, t))
                        nW = 1 if (at is not None and r["t_hdr"] > at) else 0
                    sub_prohib = False
                    for it in b["items"]:
                        delivered.add((purpose, it["tag"]))
                        for (st, ep, stag) in item_sources(it):
                            if prohibited_source(t, ep, purpose, nW):
                                prohib_tags.add((purpose, it["tag"]))
                                sub_prohib = True
                    prohib_subs += sub_prohib
                    # committed before the withdrawal but arrived after its ack: in flight, cannot be recalled
                    at = ack_t.get((trial, v, t))
                    # in flight at the withdrawal: committed before it, but the HTTP exchange (server response after
                    # the sink's fixed delay) completed only after the withdrawal was acknowledged
                    if seq is not None and nW == 0 and at is not None and wseq.get(t) and r["t_host"] + SINK_DELAY_S > at:
                        outstanding += 1
                unknown = 0
                if t == 10:
                    at = ack_t.get((trial, v, t))
                    for r in by.get((trial, v, "opaque"), []) + by.get((trial, vb, "opaque"), []):
                        if r["t_host"] > quiesce_t + 1.0:
                            continue
                        total_subs += 1
                        if at is not None and r["t_hdr"] > at:
                            unknown += 1
                # device-side ground truth for the opaque tenant (never visible to the sink oracle)
                gt_late = 0
                if t == 10 and wseq.get(t):
                    w0 = wseq[t][0]
                    gt_late = sum(1 for e in ev if e[3] == t and e[4] == "COMMIT" and e[0] > w0)
                rows.append(dict(
                    run=run_name, trial=trial, schedule=lg["schedule"], k=lg["k"], variant=v, tenant=t,
                    tenant_name=c["name"], contract=c["kind"], submissions=total_subs,
                    prohibited_items=len(prohib_tags), prohibited_subs=prohib_subs,
                    violation=int(len(prohib_tags) > 0), unknown_subs=unknown, opaque_gt_late_commits=gt_late,
                    legit_expected=len(legit), legit_delivered=len(legit & delivered),
                    legit_missing=len(legit - delivered), outstanding_subs=outstanding,
                    order_fallback=order_fallback, inj_offset_ms=inj.get(str(t), inj.get(t, "")),
                    jobstarts=jobstarts.get(t, 0), device_log=int(bool(ev))))
    return rows


def main():
    out = sys.argv[1]
    rows = []
    for spec in sys.argv[2:]:
        name, path = spec.split("=", 1)
        rows += analyze_run(path, name)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
