#!/usr/bin/env python3
"""Render artifact results into manuscript/generated/: macros.tex, tab_*.tex, fig_*.tex.
Every number in the paper's results comes from here. Missing inputs render as \\textbf{??} so they are visible."""
import csv, glob, json, math, os, statistics

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ART, "results")
OUT = os.path.join(os.path.dirname(ART), "manuscript", "generated")
os.makedirs(OUT, exist_ok=True)
M = {}
MISSING = "\\textbf{??}"


def rd(name):
    p = os.path.join(RES, name)
    return list(csv.DictReader(open(p))) if os.path.exists(p) else None


def jl(name):
    p = os.path.join(RES, name)
    return json.load(open(p)) if os.path.exists(p) else None


def f0(x): return f"{float(x):.0f}"
def f1(x): return f"{float(x):.1f}"
def pct(x): return f"{100*float(x):.0f}"


def write(name, text):
    open(os.path.join(OUT, name), "w").write(text)


# ------------------------------------------------------------------ static corpus
sc = rd("static_corpus.csv")
sj = rd("static_jobs.csv")
corpus_csv = os.path.join(ART, "static", "corpus.csv")
if sc:
    by = {r["stratum"]: r for r in sc}
    A, T, R = by["all"], by["tracking"], by["random"]
    M.update(corpusN=A["n"], trackN=T["n"], randN=R["n"], pctPersistAll=f0(A["persisted_any_pct"]),
             pctAlarmAll=f0(A["alarmmanager_pct"]), pctCandLo=f0(A["candidate3_pct"]), pctCandHi=f0(A["candidate_pct"]),
             pctCandConsentLo=f0(A["candidate3_consent_pct"]), pctCandConsentHi=f0(A["candidate_consent_pct"]),
             candConsentLoN=A["candidate3_consent"], candConsentHiN=A["candidate_consent"],
             pctConsentTrack=f0(T["consent_pct"]), pctConsentRand=f0(R["consent_pct"]),
             pctSdkTrack=f0(T["telemetry_sdk_pct"]), pctSdkRand=f0(R["telemetry_sdk_pct"]),
             pctNativeAll=f0(A["native_pct"]), acraApps=A["acra"], pctNetAll=f0(A["network_pct"]))
    _mat = [json.load(open(f)) for f in glob.glob(os.path.join(ART, "static", "data", "scan", "*.json"))]
    M["matomoApps"] = sum(1 for d in _mat if d.get("sdk", {}).get("matomo"))
    feats = [("Network API", "network"), ("\\texttt{JobScheduler}", "jobscheduler"), ("\\quad \\texttt{setPersisted}", "job_persisted"),
             ("WorkManager", "workmanager"), ("AlarmManager", "alarmmanager"), ("SyncAdapter", "syncadapter"),
             ("Persisted deferred work (any)", "persisted_any"), ("Entry $\\to$ network, $\\le$3 hops", "entry_net3"),
             ("Entry $\\to$ network, any depth", "entry_net"), ("Persisted + entry$\\to$net, $\\le$3", "candidate3"), ("Persisted + entry$\\to$net, any", "candidate"), ("Consent/telemetry signal", "consent"),
             ("Candidate, $\\le$3 hops$^\\dagger$", "candidate3_consent"), ("Candidate, any depth$^\\dagger$", "candidate_consent"),
             ("Telemetry/crash SDK", "telemetry_sdk"), ("Native libraries", "native")]
    body = []
    for lab, k in feats:
        body.append(f"{lab} & {T[k]} ({f0(T[k+'_pct'])}) & {R[k]} ({f0(R[k+'_pct'])}) [{f0(R[k+'_lo'])}, {f0(R[k+'_hi'])}] \\\\")
    write("tab_corpus.tex", "\\begin{table}[t]\n\\centering\n\\caption{F-Droid corpus screen: apps (\\%). Random-stratum percentages carry Wilson 95\\% intervals conditional on the screen. Tracking is a census of eligible tracking apps. "
          "$^\\dagger$persisted deferred work + entry$\\to$network + consent signal.}\n\\label{tab:corpus}\n\\mtab\n"
          "\\begin{tabular}{@{}lrr@{}}\n\\toprule\n"
          f"\\mhead Feature & Tracking ($n{{=}}${T['n']}) & Random ($n{{=}}${R['n']}) \\\\\n\\midrule\n"
          + "\n".join(body) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
if sj:
    j = {r["group"]: r for r in sj}
    M.update(pctPollStop=f0(j["app_code"]["workers_poll_stop_pct"]), jobEntries=j["all"]["entries"],
             jobEntriesApp=j["app_code"]["entries"], medianDepth=j["all"]["median_depth"])
if os.path.exists(corpus_csv):
    idx = json.load(open(os.path.join(ART, "static", "data", "index", "index-v2.json")))
    n = 0
    for pkg, p in idx["packages"].items():
        vs = sorted(p["versions"].values(), key=lambda v: v["manifest"].get("versionCode", 0))
        if not vs: continue
        v = vs[-1]
        perms = {x["name"] for x in (v["manifest"].get("usesPermission") or [])}
        if "android.permission.INTERNET" in perms and v["file"]["size"] <= 80 * 2**20:
            n += 1
    M["eligibleN"] = n
vj = rd("static_validation_judged.csv")
if vj:
    sh = [r for r in vj if int(r["net_depth"]) <= 4]; dp = [r for r in vj if int(r["net_depth"]) >= 5]
    M.update(valN=len(vj), valShallowN=len(sh), valShallowNo=sum(r["judgment"] == "no" for r in sh),
             valShallowYes=sum(r["judgment"] == "yes" for r in sh), valDeepN=len(dp), valDeepNo=sum(r["judgment"] == "no" for r in dp))

# ------------------------------------------------------------------ implementation size
loc = 0
for f in glob.glob(os.path.join(ART, "fixture", "src", "**", "*.java"), recursive=True):
    loc += sum(1 for l in open(f) if l.strip() and not l.strip().startswith(("//", "*", "/*")))
M["impLoc"] = f"{loc:,}".replace(",", "{,}")

# ------------------------------------------------------------------ campaign (filled by later sections of this script)
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_campaign.py")).read()) \
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_campaign.py")) else None

_rm = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_micro.py")
if os.path.exists(_rm):
    exec(open(_rm).read())

# ------------------------------------------------------------------ macros
NEEDED = ["corpusN", "eligibleN", "trackN", "randN", "pctPersistAll", "pctAlarmAll", "pctCandLo", "pctCandHi",
          "pctCandConsentLo", "pctCandConsentHi", "candConsentLoN", "candConsentHiN", "pctConsentTrack", "pctConsentRand",
          "pctSdkTrack", "pctSdkRand", "pctPollStop", "pctNativeAll", "acraApps", "impLoc", "valN", "valShallowN",
          "valShallowNo", "valShallowYes", "valDeepN", "valDeepNo",
          "nTrialsValid", "convViolPct", "acraStockLeak", "acraFenceLeak", "acraStockCtl", "acraFenceCtl",
          "acraStockReb", "acraFenceReb", "acraStockRebCtl", "acraFenceRebCtl", "insNoUs", "insLabUs", "insDeltaUs", "fenceNoneUs", "fenceRdUs", "eeNoneMs", "eeRdMs",
          "extrasDelta", "noserZeroPct", "noserFivePct", "crashKills", "crashOrphA", "crashOrphB", "crashOrphBPct",
          "nInvalid", "nTrialsTotal"]
lines = []
for k in sorted(set(NEEDED) | set(M)):
    v = M.get(k, MISSING)
    lines.append(f"\\newcommand{{\\{k}}}{{{v}\\xspace}}")
write("macros.tex", "% generated by artifact/scripts/render.py -- do not edit\n" + "\n".join(lines) + "\n")
missing = [k for k in NEEDED if k not in M]
print(f"macros: {len(M)} defined; missing: {missing}")
