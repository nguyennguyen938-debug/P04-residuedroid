# exec'd by render.py (shares its namespace: rd, jl, write, M, f0, f1, pct, RES, ART)
import csv as _csv, json as _json, os as _os, collections as _col, math as _math, re as _re, random as _random

VNAME = {"none": "none", "cancel": "cancel", "enqueue": "enqueue", "jobstart": "job-start", "conv": "conv",
         "egress": "egress (decl.)", "rd": "\\sys", "rdB": "\\sys (AVD B)", "volatile": "volatile labels", "taint": "taint rule"}
SCHEDS = ["pending", "kill", "forcestop", "reboot", "revoke", "netloss", "inflight"]
SLAB = {"pending": "pen", "kill": "kill", "forcestop": "fstop", "reboot": "reb", "revoke": "rev", "netloss": "net", "inflight": "infl"}
mat = rd("tab_matrix.csv")
summ = jl("summary_campaign.json")
outc = rd("outcomes.csv")


def _wil(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 3
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * _math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0, c - h), min(1, c + h)


if mat and summ and outc:
    M["nTrialsValid"] = summ["n_trials_valid"]; M["nTrialsTotal"] = summ["n_trials_total"]
    M["nValidAll"] = summ.get("n_trials_valid_all", MISSING); M["nValidUnused"] = summ.get("n_trials_valid_all", 0) - summ["n_trials_valid"]
    M["nInvalid"] = summ["n_trials_invalid"]; M["nSubmissions"] = f"{summ['n_submissions']:,}".replace(",", "{,}")
    order = ["none", "cancel", "enqueue", "jobstart", "conv", "egress", "rd", "rdB", "volatile", "taint"]
    byv = {r["variant"]: r for r in mat}
    body = []
    for v in order:
        r = byv[v]
        cells = []
        for s in SCHEDS:
            n = int(r[s + "_n"]); k = int(r[s + "_k"])
            if n == 0:
                cells.append("--"); continue
            val = f"{100*k/n:.0f}"
            cells.append(f"\\mgood{{\\textbf{{{val}}}}}" if k == 0 else val)
        body.append(f"{VNAME[v]} & " + " & ".join(cells) + " \\\\")
        if v in ("conv", "rdB"):
            body.append("\\midrule")
    ns = [int(byv["rd"][s + "_n"]) // 5 for s in SCHEDS]
    write("tab_matrix.tex", "\\begin{table}[t]\n\\centering\n\\caption{Stream-wrapper authorization-order violations (\\%), "
          "tenants T1, T8, T2, T5 and T4 (personalisation). Trials per schedule and AVD: "
          + ", ".join(f"{SLAB[s]} {n}" for s, n in zip(SCHEDS, ns)) + ".}\n\\label{tab:matrix}\n\\mtab\n"
          "\\begin{tabular}{@{}lrrrrrrr@{}}\n\\toprule\n"
          "\\mhead Variant & " + " & ".join(f"\\textsf{{{SLAB[s]}}}" for s in SCHEDS) + " \\\\\n\\midrule\n" + "\n".join(body)
          + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    M["minTrialsPerSched"] = min(ns)
    # ---- pooled scalars from outcomes
    O = [r for r in outc if r["valid"] == "1"]
    for r in O:
        for k in ("tenant", "violation", "prohibited_items", "submissions", "unknown_subs", "outstanding_subs",
                  "legit_expected", "legit_delivered", "opaque_gt_late_commits", "k"):
            r[k] = int(r[k])
    # cap to first 50 valid k per (run, schedule) as in summarize.py
    ks = _col.defaultdict(set)
    for r in O: ks[(r["run"], r["schedule"])].add(r["k"])
    keep = {key: set(sorted(v)[:50]) for key, v in ks.items()}
    O = [r for r in O if r["k"] in keep[(r["run"], r["schedule"])]]
    for r in O:
        r["v"] = "rdB" if (r["variant"] == "rd" and r["run"] == "B") else r["variant"]
    CORE = {1, 8, 2, 5, 4}

    def vr(v, scheds, tenants=CORE):
        rs = [r for r in O if r["v"] == v and r["schedule"] in scheds and r["tenant"] in tenants]
        k = sum(r["violation"] for r in rs); return k, len(rs)
    LIFE = ["pending", "kill", "forcestop", "reboot", "revoke"]
    for v in order:
        k, n = vr(v, SCHEDS); p, lo, hi = _wil(k, n)
        M[f"viol{v.capitalize()}Pct"] = f"{100*p:.0f}"; M[f"viol{v.capitalize()}N"] = n
        M[f"viol{v.capitalize()}Lo"] = f"{100*lo:.0f}"; M[f"viol{v.capitalize()}Hi"] = f"{100*hi:.0f}"
    M["convViolPct"] = M["violConvPct"]
    M["rdItems"] = sum(r["prohibited_items"] for r in O if r["v"] in ("rd", "rdB") and r["tenant"] in CORE)
    M["rdTenantTrials"] = sum(1 for r in O if r["v"] in ("rd", "rdB") and r["tenant"] in CORE)
    k, n = vr("conv", SCHEDS, {8, 2, 5, 4}); M["convNoLineagePct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("conv", ["netloss", "inflight"], {8, 2, 5, 4}); M["convRacePct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("jobstart", ["netloss"], {8, 2, 5, 4}); M["jobstartNetPct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("conv", ["netloss"], {8, 2, 5, 4}); M["convNetPct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("cancel", ["netloss"], {8, 2, 5, 4}); M["cancelNetPct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("egress", SCHEDS, {5}); M["egressTFivePct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("egress", SCHEDS, {1}); M["egressTOnePct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("conv", SCHEDS, {1}); M["convTOnePct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("conv", LIFE, {1}); M["convTOneLifePct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("conv", LIFE, {8, 2, 5, 4}); M["convOtherLifeK"] = k; M["convOtherLifeN"] = f"{n:,}".replace(",", "{,}")
    k, n = vr("enqueue", ["forcestop"]); M["enqueueFstopPct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("enqueue", ["pending", "kill", "reboot", "revoke"]); M["enqueueLifePct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("volatile", ["pending"]); M["volatilePenPct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("volatile", ["kill", "reboot", "forcestop"]); M["volatileLifePct"] = f"{100*k/max(n,1):.0f}"
    k, n = vr("none", ["pending", "kill", "reboot", "revoke"]); M["noneLifePct"] = f"{100*k/max(n,1):.0f}"
    # uncovered path (T9) and opaque (T10)
    for v in order:
        rs = [r for r in O if r["v"] == v and r["tenant"] == 9 and r["schedule"] in LIFE]
        M[f"tNine{v.capitalize()}Pct"] = f"{100*sum(r['violation'] for r in rs)/max(len(rs),1):.0f}"
    rs = [r for r in O if r["v"] in ("rd", "rdB") and r["tenant"] == 9]
    M["rdUnmedPct"] = f"{100*sum(r['violation'] for r in rs)/max(len(rs),1):.0f}"
    rs = [r for r in O if r["tenant"] == 10 and r["v"] in ("none", "enqueue")]
    M["opaqueUnknownSubs"] = sum(r["unknown_subs"] for r in rs)
    M["opaqueTrials"] = len(rs)
    rs = [r for r in O if r["tenant"] == 10 and r["v"] in ("rd", "rdB")]
    M["rdOpaqueUnknown"] = sum(r["unknown_subs"] for r in rs)
    M["outstandingSubs"] = sum(r["outstanding_subs"] for r in O if r["schedule"] in ("inflight", "netloss"))
    M["outstandingRd"] = sum(r["outstanding_subs"] for r in O if r["schedule"] in ("inflight", "netloss") and r["v"] in ("rd", "rdB"))
    # ---- FP / legit deficit table
    fp_rows = []
    for v in order:
        row = [VNAME[v]]
        tot_d = tot_e = 0
        for t, sc in ((3, SCHEDS), (4, SCHEDS), (6, SCHEDS), (7, ["revoke"])):
            rs = [r for r in O if r["v"] == v and r["tenant"] == t and r["schedule"] in sc]
            if t == 4:   # backup purpose: 12 legit items
                d = [r["legit_expected"] - r["legit_delivered"] for r in rs]
            else:
                d = [r["legit_expected"] - r["legit_delivered"] for r in rs]
            tot_d += sum(d); tot_e += sum(r["legit_expected"] for r in rs)
            row.append(f"{sum(d)/max(len(d),1):.2f}")
        row.append(f"{100*tot_d/max(tot_e,1):.1f}")
        M[f"deficit{v.capitalize()}Pct"] = f"{100*tot_d/max(tot_e,1):.1f}"
        fp_rows.append(" & ".join(row) + " \\\\")
    _need = _col.defaultdict(set)
    for r in O:
        if r["v"] != "taint" and r["tenant"] in (3, 4, 6, 7) and not (r["tenant"] == 7 and r["schedule"] != "revoke") \
                and r["legit_expected"] > r["legit_delivered"]:
            _need[(r["run"], r["trial"], r["variant"])].add(r["tenant"])
    M["defOtherTT"] = sum(len(x) for x in _need.values())
    M["defOtherReb"] = sum(len(x) for k, x in _need.items() if k[1].startswith("reb"))
    M["defOtherTsix"] = sum(1 for x in _need.values() if 6 in x)
    _conn = 0
    for _run in ("A", "B"):
        _pp = _os.path.join(RES, f"raw/c1/{_run}/device_events.jsonl")
        for l in open(_pp):
            d = _json.loads(l); key = (_run, d["trial"], d["pkg"].split(".")[-1])
            if key in _need:
                for t in _need[key]:
                    _conn += any(e[3] == t and e[4] == "ONSTOP" and e[5].endswith("reason=7") for e in d.get("events", []))
    M["defOtherConnStop"] = _conn
    # fence decisions of rd on the FP-control tenants (T3, T6, T7, T4 backup job 44): should never block
    _vt = {(r["run"], r["trial"]) for r in O}
    _fpb = 0
    for _run in ("A", "B"):
        for l in open(_os.path.join(RES, f"raw/c1/{_run}/device_events.jsonl")):
            d = _json.loads(l)
            if (_run, d["trial"]) in _vt and d["pkg"].endswith(".rd"):
                _fpb += sum(1 for e in d.get("events", []) if e[4] == "BLOCK" and (e[3] in (3, 6, 7) or (e[3] == 4 and "job=44;" in e[5])))
    M["rdFpBlocks"] = _fpb
    write("tab_fp.tex", "\\begin{table}[t]\n\\centering\n\\caption{Permitted items \\emph{not} delivered per tenant-trial "
          "(FP controls; T7 in \\textsf{rev} only). Last column: share of all permitted items. \\vname{none} enforces nothing, so its "
          "deficit is the availability loss that enforcement does not cause.}\n\\label{tab:fp}\n\\mtab\\setlength{\\tabcolsep}{3pt}\n"
          "\\begin{tabular}{@{}lrrrrr@{}}\n\\toprule\n\\mhead Variant & T3 flush & T4 backup & T6 none & T7 OS & \\% total \\\\\n\\midrule\n"
          + "\n".join(fp_rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    # ---- bar figure: mean prohibited items per core tenant-trial, lifecycle vs race
    def mean_items(v, scheds):
        rs = [r["prohibited_items"] for r in O if r["v"] == v and r["schedule"] in scheds and r["tenant"] in CORE]
        return sum(rs) / max(len(rs), 1)
    bv = ["none", "cancel", "enqueue", "jobstart", "conv", "egress", "rd", "volatile", "taint"]
    lab = {"none": "none", "cancel": "cancel", "enqueue": "enq", "jobstart": "start", "conv": "conv", "egress": "egress",
           "rd": "RD", "volatile": "volat.", "taint": "taint"}
    c1 = " ".join(f"({lab[v]},{mean_items(v, LIFE):.2f})" for v in bv)
    c2 = " ".join(f"({lab[v]},{mean_items(v, ['netloss', 'inflight']):.2f})" for v in bv)
    write("fig_bars.tex", "\\begin{figure}[t]\n\\centering\n\\begin{tikzpicture}\n\\begin{axis}[maturedbar,width=\\linewidth,height=3.5cm,"
          "bar width=4.5pt,ymin=0,ylabel={items / tenant-trial},"
          "symbolic x coords={" + ",".join(lab[v] for v in bv) + "},xtick=data,x tick label style={font=\\scriptsize},"
          "legend style={at={(0.5,1.0)},anchor=south,legend columns=2},"
          "enlarge x limits=0.07]\n"
          f"\\addplot[fill=mBrick,draw=mInk!75] coordinates {{{c1}}};\n\\addlegendentry{{lifecycle (pen, kill, fstop, reb, rev)}}\n"
          f"\\addplot[fill=mTeal,draw=mInk!75] coordinates {{{c2}}};\n\\addlegendentry{{race (net, infl)}}\n"
          "\\end{axis}\n\\end{tikzpicture}\n\\caption{Stream-wrapper prohibited authorizations per tenant-trial (T1, T8, T2, T5, T4), AVD~A and B pooled. "
          "\\sys (RD) authorizes none.}\n\\Description{Grouped bars compare authorization-order failures of enforcement variants across lifecycle and retry schedules.}\n\\label{fig:bars}\n\\end{figure}\n")
    # ---- in-flight curve + Eq.(2) prediction from measured commit offsets of the job-start variant
    inf = rd("fig_inflight.csv")
    dev_path = _os.path.join(RES, "raw/c1/A/device_events.jsonl")
    cmax = []
    pred_pairs = []
    if _os.path.exists(dev_path):
        sched_valid = {(r["trial"]) for r in O if r["run"] == "A" and r["schedule"] == "inflight"}
        for l in open(dev_path):
            d = _json.loads(l)
            if d["trial"] not in sched_valid or not d["pkg"].endswith(".jobstart"):
                continue
            ev = d.get("events", [])
            for t in (8, 2, 5):
                js = [e for e in ev if e[3] == t and e[4] == "JOBSTART" and e[5] == "kind=1"]
                if not js: continue
                t0 = js[0][2]
                # commits of the triggered job run (until its JOBDONE) and of the summary job: the commits a
                # job-start check made at t0 covers; later re-grant jobs carry new-epoch data and are excluded
                done = [e[2] for e in ev if e[3] == t and e[4] in ("JOBDONE", "JOB_RETRY_LATER") and e[5].startswith("kind=1") and e[2] >= t0]
                tend = done[0] if done else float("inf")
                cs = [e[2] - t0 for e in ev if e[3] == t and e[4] == "COMMIT" and
                      ((f"job={t*10+1};" in e[5] and e[2] <= tend) or f"job={t*10+3};" in e[5])]
                if cs:
                    cmax.append(max(cs))
                    rr = [x for x in O if x["run"] == "A" and x["trial"] == d["trial"] and x["variant"] == "jobstart" and x["tenant"] == t]
                    if rr and rr[0]["inj_offset_ms"] != "":
                        pred_pairs.append((int(rr[0]["inj_offset_ms"]) < max(cs), bool(rr[0]["violation"])))
    M["nCmax"] = len(cmax)
    M["predN"] = len(pred_pairs); M["predAgree"] = sum(1 for a, b in pred_pairs if a == b)
    if cmax:
        M["cmaxMedianMs"] = f"{sorted(cmax)[len(cmax)//2]:.0f}"
    plots = []
    styles = {"none": "mInk,mark=o", "cancel": "mOchre,mark=triangle*,mark size=1.7pt", "jobstart": "mBrick,mark=square*,mark size=1.3pt",
              "conv": "mPlum,mark=diamond*,mark size=1.7pt", "egress": "mNavy,mark=x", "rd": "mTeal,mark=*,mark size=1.4pt,line width=1.2pt"}
    if inf:
        for v in ["cancel", "jobstart", "conv", "rd"]:
            pts = " ".join(f"({float(r['mid'])/1000:.1f},{float(r['p']):.3f})" for r in inf if r["variant"] == v and int(r["n"]) > 0)
            plots.append(f"\\addplot[{styles[v]}] coordinates {{{pts}}};\n\\addlegendentry{{{ {'cancel':'cancel','jobstart':'job-start','conv':'conv','rd':'RD'}[v] }}}")
        if cmax:
            pred = " ".join(f"({u/1000:.2f},{sum(1 for c in cmax if c > u)/len(cmax):.3f})" for u in range(0, 1601, 50))
            plots.append(f"\\addplot[mSlate,dashed,line width=0.9pt,no marks] coordinates {{{pred}}};\n\\addlegendentry{{Eq.~(2), measured $c_k$}}")
        # agreement between prediction and the job-start curve
        diffs = []
        for r in inf:
            if r["variant"] == "jobstart" and int(r["n"]) > 0 and cmax:
                u = float(r["mid"]); pr = sum(1 for c in cmax if c > u) / len(cmax)
                diffs.append(abs(pr - float(r["p"])))
        M["predMaxAbsErr"] = f"{max(diffs):.2f}" if diffs else MISSING
        n_inf = sum(int(r["n"]) for r in inf if r["variant"] == "jobstart")
        M["nInflightTT"] = n_inf
    write("fig_inflight.tex", "\\begin{figure}[t]\n\\centering\n\\begin{tikzpicture}\n\\begin{axis}[matured,width=\\linewidth,height=3.4cm,"
          "xlabel={withdrawal offset after job start (s)},ylabel={P(violation)},xmin=0,xmax=1.6,ymin=-0.03,ymax=1.05,"
          "legend style={at={(0.5,1.03)},anchor=south,legend columns=2},transpose legend]\n" + "\n".join(plots) +
          "\n\\end{axis}\n\\end{tikzpicture}\n\\caption{In-flight schedule: share of tenant-trials (T8, T2, T5) with a prohibited authorization, by "
          "withdrawal offset (200\\,ms bins). The dashed line is Theorem~\\ref{thm:race}'s prediction from the job-start variant's measured "
          "last-authorization offsets.}\n\\Description{Observed authorization-order outcomes are compared with predictions over withdrawal offsets.}\n\\label{fig:inflight}\n\\end{figure}\n")
    # ---- CDF of enqueue-to-commit windows (variant none, upload jobs, by lifecycle schedule)
    win = _col.defaultdict(list)
    for run in ("A",):
        p = _os.path.join(RES, f"raw/c1/{run}/device_events.jsonl")
        if not _os.path.exists(p): continue
        valid = {r["trial"]: r["schedule"] for r in O if r["run"] == run}
        for d in {(_json.loads(l)["trial"], _json.loads(l)["pkg"]): _json.loads(l) for l in open(p)}.values():
            if d["trial"] not in valid or not d["pkg"].endswith(".none"): continue
            sc = valid[d["trial"]]
            if sc not in ("pending", "kill", "reboot", "forcestop", "revoke"): continue
            ev = d.get("events", [])
            for t in (8, 2, 5, 6):
                enq = [e for e in ev if e[3] == t and e[4] == "ENQUEUE" and "kind=1" in e[5] and "setup" in e[5]]
                cm = [e for e in ev if e[3] == t and e[4] == "COMMIT" and f"job={t*10+1};" in e[5]]
                if enq and cm:
                    win[sc].append((cm[0][1] - enq[0][1]) / 1000.0)
    if win["revoke"]: M["winRevokeMed"] = f"{_math.floor(statistics.median(win['revoke']) + .5)}"
    cdfp = []
    cst = {"pending": "mInk", "kill": "mBrick,dashed", "forcestop": "mOchre,densely dotted", "reboot": "mTeal,dashdotted"}
    for sc in ("pending", "kill", "forcestop", "reboot"):
        xs = sorted(win[sc])
        if not xs: continue
        pts = " ".join(f"({x:.1f},{(i+1)/len(xs):.3f})" for i, x in enumerate(xs) if i % max(1, len(xs)//40) == 0 or i == len(xs) - 1)
        cdfp.append(f"\\addplot[{cst[sc]},line width=1pt,no marks] coordinates {{{pts}}};\n\\addlegendentry{{\\textsf{{{SLAB[sc]}}}}}")
        M[f"win{sc.capitalize()}Med"] = f"{xs[len(xs)//2]:.0f}"
        M[f"win{sc.capitalize()}Max"] = f"{xs[-1]:.0f}"
    write("fig_windows.tex", "\\begin{figure}[t]\n\\centering\n\\begin{tikzpicture}\n\\begin{axis}[matured,width=\\linewidth,height=3.4cm,"
          "xlabel={enqueue-time check $\\to$ first authorization (s)},ylabel={CDF},ymin=0,ymax=1.02,xmin=0,"
          "legend style={at={(0.98,0.03)},anchor=south east}]\n" + "\n".join(cdfp) + "\n\\end{axis}\n\\end{tikzpicture}\n\\caption{Window an enqueue-time check leaves "
          "open: time from enqueue to the job's first authorization (\\vname{none}, T2/T5/T6/T8 uploads), by schedule.}\n\\Description{Cumulative distributions show enqueue-to-authorization delays across lifecycle schedules.}\n\\label{fig:windows}\n\\end{figure}\n")

# ---- measured lifecycle facts (variant none, AVD A): does the persisted job survive, or does the app's startup path re-enqueue it?
if outc:
    _p = _os.path.join(RES, "raw/c1/A/device_events.jsonl")
    validA = {r["trial"]: r["schedule"] for r in O if r["run"] == "A"}
    lc = _col.defaultdict(_col.Counter)
    for d in {(_json.loads(l)["trial"], _json.loads(l)["pkg"]): _json.loads(l) for l in open(_p)}.values():
        if d["trial"] not in validA or not d["pkg"].endswith(".none"): continue
        s = validA[d["trial"]]
        if s in ("netloss", "inflight"): continue
        ev = d.get("events", [])
        c = lc[s]; c["n"] += 1
        res = any(e[3] == 6 and e[4] == "ENQUEUE" and "proc-start" in e[5] and "kind=1" in e[5] for e in ev)
        ran = any(e[3] == 6 and e[4] == "JOBSTART" and e[5] == "kind=1" for e in ev)
        c["orig"] += ran and not res; c["res"] += res
        c["byval"] += any(e[3] == 2 and e[4] == "JOBSTART" and e[5] == "kind=3" for e in ev)
        c["deliv"] += sum(1 for e in ev if e[3] == 6 and e[4] == "COMMIT") > 0
    rows_lc = []
    for s in ("pending", "kill", "forcestop", "reboot", "revoke"):
        c = lc[s]
        if not c["n"]: continue
        med = M.get(f"win{s.capitalize()}Med", "--")
        rows_lc.append(f"\\textsf{{{SLAB[s]}}} & {c['n']} & {c['orig']} & {c['res']} & {c['byval']} & {med} \\\\")
        M[f"lc{s.capitalize()}N"] = c["n"]
    M["lcTrials"] = sum(lc[s]["n"] for s in lc)
    write("tab_lifecycle.tex", "\\begin{table}[t]\n\\centering\n\\caption{Measured lifecycle behavior of a persisted upload job "
          "(\\vname{none}, AVD~A). Counts of trials; ``by-value job'' is T2's summary job, whose data exists only in its extras.}\n"
          "\\label{tab:lifecycle}\n\\mtab\n\\begin{tabular}{@{}lrrrrr@{}}\n\\toprule\n"
          "\\mhead Schedule & trials & job ran & re-enqueued & by-value job ran & median s \\\\\n\\midrule\n" + "\n".join(rows_lc)
          + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")

# ---- substrate comparison: JobScheduler (main campaign, AVD A) vs WorkManager / AlarmManager runs (results/raw/sub_*)
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("oracle_mod", _os.path.join(ART, "scripts", "oracle.py"))
_or = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_or)
_subruns = {"WorkManager 2.9.1": _os.path.join(RES, "raw/sub_work"), "AlarmManager": _os.path.join(RES, "raw/sub_alarm")}
_srows = []
_SS = ["pending", "kill", "forcestop", "reboot"]
def _rate(rows, v, s):
    rs = [r for r in rows if r["v"] == v and r["schedule"] == s and int(r["tenant"]) in (1, 8, 2, 5, 4)]
    k = sum(int(r["violation"]) for r in rs); return k, len(rs)
if outc:
    _srows.append("\\mgroup{5}{JobScheduler}")
    for v in ("none", "conv", "rd"):
        cells = []
        for s in _SS:
            k, n = _rate(O, v, s); cells.append(f"{100*k/n:.0f}" if n else "--")
        _srows.append(f"{VNAME[v]} & " + " & ".join(f"\\mgood{{{c}}}" if v == "rd" and c == "0" else c for c in cells) + " \\\\")
for _lab, _d in _subruns.items():
    if not _os.path.exists(_os.path.join(_d, "schedule.jsonl")):
        continue
    _rows = _or.analyze_run(_d, _lab)
    # same validity rules as the main campaign (summarize.validity): host sleep, restart/setup failure/trial error,
    # unreadable device log, failed force-stop relaunch, device dead at the end
    _sspec = _ilu.spec_from_file_location("summ_mod", _os.path.join(ART, "scripts", "summarize.py"))
    _sm = _ilu.module_from_spec(_sspec); _sspec.loader.exec_module(_sm)
    _val = _sm.validity(_d)
    _bad = {t for t, why in _val.items() if why}
    _key = _lab.split()[0]
    M[f"sub{_key}Logged"] = len(_val); M[f"sub{_key}Invalid"] = len(_bad)
    _rows = [r for r in _rows if r["trial"] not in _bad]
    for r in _rows:
        r["v"] = r["variant"][2:]
    _srows.append(f"\\mgroup{{5}}{{{_lab.split()[0]}}}")
    for v in ("none", "conv", "rd"):
        cells = []
        for s in _SS:
            k, n = _rate(_rows, v, s); cells.append(f"{100*k/n:.0f}" if n else "--")
            M[f"sub{_lab.split()[0]}{v.capitalize()}{s.capitalize()}"] = f"{100*k/n:.0f}" if n else "--"
        _srows.append(f"{VNAME[v]} & " + " & ".join(f"\\mgood{{{c}}}" if v == "rd" and c == "0" else c for c in cells) + " \\\\")
    M[f"sub{_lab.split()[0]}Trials"] = len({r['trial'] for r in _rows})
    for v in ("none", "conv", "rd"):
        _fp = [r for r in _rows if r["v"] == v and int(r["tenant"]) in (3, 4, 6)]
        _e = sum(int(r["legit_expected"]) for r in _fp); _dd = sum(int(r["legit_expected"]) - int(r["legit_delivered"]) for r in _fp)
        M[f"sub{_key}{v.capitalize()}DefPct"] = f"{100*_dd/max(_e,1):.0f}"
        _t9 = [r for r in _rows if r["v"] == v and int(r["tenant"]) == 9]
        M[f"sub{_key}{v.capitalize()}TNinePct"] = f"{100*sum(int(r['violation']) for r in _t9)/max(len(_t9),1):.0f}"
    _rdi = [r for r in _rows if r["v"] == "rd" and int(r["tenant"]) in (1, 8, 2, 5, 4)]
    M[f"sub{_key}RdItems"] = sum(int(r["prohibited_items"]) for r in _rdi); M[f"sub{_key}RdTT"] = len(_rdi)
    _per = _col.Counter(r["schedule"] for r in _rows if r["v"] == "none" and int(r["tenant"]) == 1)
    M[f"sub{_key}MinPerSched"] = min(_per.get(s, 0) for s in _SS)
if _srows:
    write("tab_substrate.tex", "\\begin{table}[t]\n\\centering\n\\caption{Violation rate (\\%) by deferred-work substrate "
          "(tenants T1, T8, T2, T5, T4). WorkManager and AlarmManager runs use their own rescheduling; the fixture's startup "
          "re-enqueue path is disabled for WorkManager.}\n\\label{tab:substrate}\n\\mtab\n"
          "\\begin{tabular}{@{}lrrrr@{}}\n\\toprule\n\\mhead Variant & \\textsf{pen} & \\textsf{kill} & \\textsf{fstop} & \\textsf{reb} \\\\\n\\midrule\n"
          + "\n".join(_srows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
