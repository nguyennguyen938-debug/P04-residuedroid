#!/usr/bin/env python3
"""Aggregate per-APK scan JSON into corpus tables (results/static_*.csv) and summary scalars."""
import csv, glob, json, math, os, random, collections
HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(os.path.dirname(HERE), "results")


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 3
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0, c - h), min(1, c + h)


apps = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(HERE, "data/scan/*.json")))]
apps = [a for a in apps if "error" not in a]
for a in apps:
    api, jobs = a["api"], a["jobs"]
    a["f_workmanager"] = api["workmanager"] or any(j["kind"] == "worker" for j in jobs)
    a["f_job_persisted"] = api["job_persisted"]
    a["f_persisted"] = a["f_workmanager"] or api["job_persisted"] or api["syncadapter"] or api["legacy_dispatch"]
    a["f_entry_net"] = any(j["reach_network"] for j in jobs)
    a["f_consent"] = bool(a["consent_keys"]) or bool(a["consent_ui"])
    a["f_entry_net3"] = any(j["reach_network"] and j["net_depth"] is not None and j["net_depth"] <= 3 for j in jobs)
    a["f_cand"] = a["f_persisted"] and a["f_entry_net"]
    a["f_cand3"] = a["f_persisted"] and a["f_entry_net3"]
    a["f_cand3_consent"] = a["f_cand3"] and (bool(a["consent_keys"]) or bool(a["consent_ui"]))
    a["f_cand_consent"] = a["f_cand"] and a["f_consent"]
    a["f_telemetry_sdk"] = any(a["sdk"][k] for k in ("acra", "sentry", "matomo", "firebase_analytics", "crashlytics",
                                                    "mapbox_telemetry", "bugsnag", "countly", "appcenter", "yandex_metrica",
                                                    "mixpanel", "amplitude", "segment", "flurry", "adjust", "appsflyer",
                                                    "opentelemetry", "facebook_sdk"))
    a["f_native"] = api["native"]

FEATS = [("network", lambda a: a["api"]["network"]), ("jobscheduler", lambda a: a["api"]["jobscheduler"]),
         ("job_persisted", lambda a: a["f_job_persisted"]), ("workmanager", lambda a: a["f_workmanager"]),
         ("alarmmanager", lambda a: a["api"]["alarmmanager"]), ("syncadapter", lambda a: a["api"]["syncadapter"]),
         ("persisted_any", lambda a: a["f_persisted"]), ("entry_net", lambda a: a["f_entry_net"]), ("entry_net3", lambda a: a["f_entry_net3"]),
         ("candidate3", lambda a: a["f_cand3"]), ("candidate3_consent", lambda a: a["f_cand3_consent"]),
         ("consent_key", lambda a: bool(a["consent_keys"])), ("consent_ui", lambda a: bool(a["consent_ui"])),
         ("candidate", lambda a: a["f_cand"]), ("consent", lambda a: a["f_consent"]),
         ("candidate_consent", lambda a: a["f_cand_consent"]), ("telemetry_sdk", lambda a: a["f_telemetry_sdk"]),
         ("acra", lambda a: a["sdk"]["acra"]), ("sentry", lambda a: a["sdk"]["sentry"]), ("native", lambda a: a["f_native"])]
rows = []
for name, sel in [("tracking", lambda a: a["stratum"] == "tracking"), ("random", lambda a: a["stratum"] == "random"),
                  ("all", lambda a: True)]:
    sub = [a for a in apps if sel(a)]
    r = {"stratum": name, "n": len(sub)}
    for f, fn in FEATS:
        k = sum(1 for a in sub if fn(a))
        p, lo, hi = wilson(k, len(sub))
        if name != "random": lo = hi = None # descriptive census/oversampled mixture, not random-sample CIs
        r[f] = k; r[f + "_pct"] = 100 * p; r[f + "_lo"] = None if lo is None else 100 * lo; r[f + "_hi"] = None if hi is None else 100 * hi
    rows.append(r)
with open(os.path.join(RES, "static_corpus.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# job-entry level
J = []
for a in apps:
    for j in a["jobs"]:
        J.append({**j, "pkg": a["pkg"], "stratum": a["stratum"], "app_consent": a["f_consent"]})
jr = []
for name, sel in [("app_code", lambda j: not j["library"]), ("library", lambda j: j["library"]), ("all", lambda j: True)]:
    sub = [j for j in J if sel(j)]
    net = [j for j in sub if j["reach_network"]]
    netc = [j for j in net if j["app_consent"]]
    wk = [j for j in sub if j["kind"] == "worker"]
    jr.append({"group": name, "entries": len(sub), "workers": sum(1 for j in sub if j["kind"] == "worker"),
               "jobservices": sum(1 for j in sub if j["kind"] == "jobservice"),
               "syncadapters": sum(1 for j in sub if j["kind"] == "syncadapter"),
               "reach_net": len(net), "reach_net_pct": 100 * len(net) / len(sub) if sub else float("nan"),
               "net_in_consent_apps": len(netc),
               "reach_net3": sum(1 for j in net if j["net_depth"] is not None and j["net_depth"] <= 3),
               "reach_net3_pct": 100 * sum(1 for j in net if j["net_depth"] is not None and j["net_depth"] <= 3) / len(sub) if sub else float("nan"),
               "median_depth": sorted(j["net_depth"] for j in net)[len(net) // 2] if net else float("nan"),
               "net_consent_key_reachable": sum(1 for j in netc if j["reach_consent_key"]),
               "net_consent_key_pct": 100 * sum(1 for j in netc if j["reach_consent_key"]) / len(netc) if netc else float("nan"),
               "net_pref_read_pct": 100 * sum(1 for j in net if j["reach_pref_read"]) / len(net) if net else float("nan"),
               "workers_poll_stop_pct": 100 * sum(1 for j in wk if j["polls_stop"]) / len(wk) if wk else float("nan"),
               "truncated_pct": 100 * sum(1 for j in sub if j["truncated"]) / len(sub) if sub else float("nan")})
with open(os.path.join(RES, "static_jobs.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(jr[0].keys())); w.writeheader(); w.writerows(jr)
# validation sample for manual inspection (seeded)
cand = [j for j in J if j["reach_network"] and j["app_consent"] and not j["library"]]
samp = random.Random(42).sample(cand, min(20, len(cand)))
with open(os.path.join(RES, "static_validation_sample.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["pkg", "cls", "kind", "net_depth", "consent_keys", "net_api", "truncated"])
    for j in samp:
        w.writerow([j["pkg"], j["cls"], j["kind"], j["net_depth"], "|".join(j["consent_keys"]), "|".join(j["net_api"]), j["truncated"]])
json.dump({"rows": rows, "jobs": jr}, open(os.path.join(RES, "static_summary.json"), "w"), indent=1)
for r in rows:
    print(r["stratum"], r["n"], {f: f"{r[f]} ({r[f+'_pct']:.0f}%)" for f, _ in FEATS})
for r in jr:
    print(r)
