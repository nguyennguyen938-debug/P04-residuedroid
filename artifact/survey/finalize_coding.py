#!/usr/bin/env python3
"""Test 3 (C10): turn the model's first-pass labels into the final coding.

First pass: one language-model coder (lane C, Sonnet) applied the written rules in README.md to every app
file produced by collect_promises.py; its raw table is lanec_rows.json. An author then re-read the source
strings of every flagged app. RECODE lists each change and why. Output: promise_coding.csv."""
import csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
# Per-report send buttons and dialogs are not standing switches, so they create no withdrawal over queued data.
PROMPT = "per-report send action or dialog, not a standing switch"
RECODE = {
    "com.drnoob.datamonitor": ("PROMPT", PROMPT),
    "com.furthersecrets.chemsearch": ("PROMPT", PROMPT),
    "com.mirfatif.permissionmanagerx": ("PROMPT", PROMPT),
    "de.schildbach.oeffi": ("PROMPT", PROMPT),
    "info.metadude.android.datenspuren.schedule": ("PROMPT", PROMPT),
    "info.metadude.android.foss4g.schedule": ("PROMPT", PROMPT),
    "com.trikset.gamepad2": ("PROMPT", "share action with no switch key; " + PROMPT),
    "org.thunderdog.challegram": ("UNCLEAR", "short label with no switch key; switch or action cannot be told apart"),
    "jp.nonbili.meron": ("UNCLEAR", "Gravatar sharing belongs to a display feature, not a telemetry switch"),
    "fr.gouv.etalab.mastodon": ("COLLECT_ONLY", "switch reads 'Enable crash reports', coded like 'Enable anonymous crash reporting'"),
}


def main(rows_json):
    rows = json.load(open(rows_json, encoding="utf-8"))
    sample = {r["pkg"]: r for r in csv.DictReader(open(os.path.join(HERE, "apps.csv"), encoding="utf-8"))}
    assert {r["pkg"] for r in rows} == set(sample), "coding must cover exactly the collected sample"
    assert set(RECODE) <= set(sample)
    out = []
    for r in rows:
        pkg, cat, ev, flag = r["pkg"], r["category"], r["evidence"], r["flag"]
        final, why = RECODE.get(pkg, (cat, ""))
        out.append(dict(pkg=pkg, candidate=sample[pkg]["candidate"], candidate3=sample[pkg]["candidate3"],
                        model_category=cat, final_category=final, evidence=ev, flagged=flag, recode_reason=why))
    with open(os.path.join(HERE, "promise_coding.csv"), "w", encoding="utf-8", newline="") as w:
        c = csv.DictWriter(w, list(out[0])); c.writeheader(); c.writerows(out)
    for scope, rs in (("all", out), ("candidates", [r for r in out if r["candidate"] == "1"])):
        n = {k: sum(r["final_category"] == k for r in rs) for k in
             ("DELETE", "PENDING", "RESTRICT", "COLLECT_ONLY", "PROMPT", "UNCLEAR", "NOT_CONSENT")}
        print(scope, len(rs), n)


if __name__ == "__main__":
    main(sys.argv[1])
