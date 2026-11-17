# exec'd by render.py: micro-benchmarks (results/raw/micro) and ACRA case (results/raw/acra)
import json as _j, os as _o, statistics as _st, random as _r, math as _m

def _boot_med(xs, B=1000, seed=11):
    rr = _r.Random(seed); n = len(xs)
    meds = sorted(_st.median([xs[rr.randrange(n)] for _ in range(n)]) for _ in range(B))
    return _st.median(xs), meds[int(0.025 * B)], meds[int(0.975 * B) - 1]

def _wil(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * _m.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0, c - h), min(1, c + h)

_md = _o.path.join(RES, "raw/micro")
_bench = _o.path.join(_md, "sink/bench.jsonl")
_stress = _o.path.join(_md, "sink/stress.jsonl")
_crash = _o.path.join(_md, "crash.jsonl")
rows = []
if _o.path.exists(_bench):
    B = [_j.loads(l)["body"] for l in open(_bench)]
    B = [b for b in B if "error" not in b]
    agg = {}
    for b in B:
        for key in ("ins_nolabel_ns", "ins_label_ns", "commit_none_ns", "commit_conv_ns", "commit_rd_ns"):
            agg.setdefault(key, []).extend(x / 1000 for x in b[key][50:])   # µs, drop warm-up
        agg.setdefault("e2e_" + b["variant"], []).extend(x / 1e6 for x in b["e2e_ns"][20:])  # ms
        M["extrasDelta"] = b["extras_label_bytes"] - b["extras_plain_bytes"]
    def cell(key, fmt="{:.0f}"):
        m, lo, hi = _boot_med(agg[key]); return fmt.format(m) + " [" + fmt.format(lo) + ", " + fmt.format(hi) + "]", m
    s_no, m_no = cell("ins_nolabel_ns"); s_lab, m_lab = cell("ins_label_ns")
    s_cn, m_cn = cell("commit_none_ns"); s_cc, m_cc = cell("commit_conv_ns"); s_cr, m_cr = cell("commit_rd_ns")
    s_en, m_en = cell("e2e_none", "{:.1f}"); s_ee, m_ee = cell("e2e_egress", "{:.1f}"); s_er, m_er = cell("e2e_rd", "{:.1f}")
    M.update(insNoUs=f"{m_no:.0f}", insLabUs=f"{m_lab:.0f}", insDeltaUs=f"{m_lab-m_no:.0f}", fenceNoneUs=f"{m_cn:.0f}",
             fenceRdUs=f"{m_cr:.0f}", fenceConvUs=f"{m_cc:.0f}", eeNoneMs=f"{m_en:.1f}", eeRdMs=f"{m_er:.1f}", eeEgressMs=f"{m_ee:.1f}",
             benchReps=len(B) // 3, benchN=len(agg["ins_nolabel_ns"]))
    rows += ["\\mgroup{2}{Overhead (median [bootstrap 95\\% CI])}",
             f"Row insert, no label / label (\\textmu{{}}s) & {s_no} / {s_lab} \\\\",
             f"Critical section: log only (\\textmu{{}}s) & {s_cn} \\\\",
             f"\\quad + declared check / + \\sys rule (\\textmu{{}}s) & {s_cc} / {s_cr} \\\\",
             f"Submission e2e: none / egress (ms) & {s_en} / {s_ee} \\\\",
             f"Submission e2e: \\sys (ms) & {s_er} \\\\",
             f"Job extras growth (bytes) & {M['extrasDelta']} \\\\"]
if _o.path.exists(_stress):
    S = [_j.loads(l)["body"] for l in open(_stress)]
    rows.append("\\mgroup{2}{Serialization: authorization after withdrawal}")
    for b in sorted(S, key=lambda b: (b["variant"] != "rd", b["delay_ms"])):
        k, n = b["violating_rounds"], b["rounds"]; p, lo, hi = _wil(k, n)
        name = "\\sys (serialized)" if b["variant"] == "rd" else "\\vname{noser}"
        _cell = f"{k}/{n} ({100*p:.0f}\\% [{100*lo:.0f}, {100*hi:.0f}])"
        rows.append(f"{name}, gap {b['delay_ms']}\\,ms & " + (f"\\mgood{{{_cell}}}" if k == 0 else f"\\mbad{{{_cell}}}") + " \\\\")
        if b["variant"] == "noser":
            M[{0: "noserZeroPct", 1: "noserOnePct", 5: "noserFivePct"}[b["delay_ms"]]] = f"{100*p:.0f}"
        else:
            M.setdefault("rdStressViol", 0); M["rdStressViol"] += k
    M["stressRounds"] = S[0]["rounds"] if S else MISSING
if _o.path.exists(_crash):
    C = [_j.loads(l) for l in open(_crash)]
    C = [c for c in C if "orphanB" in c["result"]]
    prevA = 0; orphB = []; orphA = 0
    for c in C:
        d = dict(kv.split("=") for kv in c["result"].split(";"))
        orphA = int(d["orphanA"]); orphB.append(int(d["orphanB"]))
    M.update(crashKills=len(C), crashOrphA=orphA, crashOrphB=sum(orphB), crashOrphBPct=f"{100*sum(1 for x in orphB if x>0)/max(len(C),1):.0f}")
    rows += ["\\mgroup{2}{Durability under SIGKILL (" + str(len(C)) + " kills)}",
             f"Label in same row: unlabelled rows & {orphA} \\\\",
             f"Label in separate store: unlabelled rows & {sum(orphB)} ({M['crashOrphBPct']}\\% of kills) \\\\"]
_mm = _o.path.join(_md, "meta.json")
_avd = {"emulator-5600": "A", "emulator-5602": "B"}.get(_j.load(open(_mm)).get("serial", ""), "?") if _o.path.exists(_mm) else "?"
M["microAvd"] = _avd
if rows:
    write("tab_cost.tex", "\\begin{table}[t]\n\\centering\n\\caption{Stream-wrapper cost, serialization and durability (on-device, AVD~" + _avd + ").}\n"
          "\\label{tab:cost}\n\\mtab\n\\begin{tabular}{@{}>{\\raggedright\\arraybackslash}p{.43\\linewidth}>{\\raggedleft\\arraybackslash}p{.53\\linewidth}@{}}\n\\toprule\n"
          + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
_ac = _o.path.join(RES, "raw/acra/trials.jsonl")
if _o.path.exists(_ac):
    T = [_j.loads(l) for l in open(_ac)]
    T = [t for t in T if t.get("protocol") == "v3"]          # 2026-11-09 clean run only
    _seen = set(); _T = []
    for t in T:                                               # a resumed run may repeat a trial: keep the first record
        if (t["variant"], t["schedule"], t["k"]) not in _seen:
            _seen.add((t["variant"], t["schedule"], t["k"])); _T.append(t)
    T = _T
    M["acraLogged"] = len(T)
    T = [t for t in T if t.get("net_off") and t.get("net_on")]
    M["acraValid"] = len(T); M["acraExcluded"] = M["acraLogged"] - len(T)
    def _kn(v, s):
        rs = [t for t in T if t["variant"] == v and t["schedule"] == s]
        return f"{sum(t['delivered'] for t in rs)}/{len(rs)}"
    M.update(acraStockLeak=_kn("acra", "disable"), acraFenceLeak=_kn("acrafence", "disable"),
             acraStockCtl=_kn("acra", "control"), acraFenceCtl=_kn("acrafence", "control"),
             acraStockReb=_kn("acra", "reboot"), acraFenceReb=_kn("acrafence", "reboot"),
             acraStockRebCtl=_kn("acra", "rebootctl"), acraFenceRebCtl=_kn("acrafence", "rebootctl"))
    _blk = [t for t in T if t["variant"] == "acrafence" and t["schedule"] == "disable"]
    M["acraFenceBlockLogged"] = f"{sum('BLOCK' in t.get('fence_log', '') for t in _blk)}/{len(_blk)}"
    _ja = [t for t in T if t["schedule"] in ("reboot", "rebootctl")]
    M["acraJobGoneReb"] = f"{sum(not str(t.get('jobs_after_reboot', '')).startswith(('waiting', 'ready', 'active')) for t in _ja)}/{len(_ja)}"
    lat = [t["latency_s"] for t in T if t["delivered"] and t["latency_s"] is not None and t["schedule"] == "disable"]
    if lat: M["acraLatencyMed"] = f"{_st.median(lat):.1f}"
if not rows:
    write("tab_cost.tex", "\\begin{table}[t]\n\\centering\n\\caption{Cost, serialization and durability (pending run).}\n\\label{tab:cost}\n"
          "\\begin{tabular}{l}\\toprule \\textbf{??} \\\\ \\bottomrule\\end{tabular}\n\\end{table}\n")
