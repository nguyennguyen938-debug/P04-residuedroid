#!/usr/bin/env python3
"""Offline tests of analyze_test6.py validity and selection rules (no device). Exit 0 = pass.

Uses synthetic TLS records; the lifecycle selection test reuses the recorded pilot-rtl-3 run (a pilot, excluded from
analysis) only as well-formed input, twice, and checks which trials are analysed vs unused; no outcome is inspected.
"""
import json, os, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_test6 as A  # noqa: E402


def tls_trial(block, case, **kw):
    r = {"trial": f"tls-{case}-{block}-x", "case": case, "block": block, "events": []}
    if case in A.BARRIER:
        r["barrier_seen"] = True
    r.update(kw)
    return r


def test_tls():
    assert A.tls_validity(tls_trial(0, "control")) is None
    assert A.tls_validity(tls_trial(0, "control", harness_error="TimeoutExpired")) == "harness error"
    assert A.tls_validity(tls_trial(0, "stall-small", barrier_seen=False)) == "barrier not reached"
    assert A.tls_validity({k: v for k, v in tls_trial(0, "buffered-early").items() if k != "barrier_seen"}) == "barrier not reached"
    with tempfile.TemporaryDirectory() as d:
        recs = [tls_trial(b, c) for b in range(25) for c in A.CASES]
        recs = [r for r in recs if not (r["block"] == 3 and r["case"] == "early")]          # block 3: case missing
        for r in recs:
            if r["block"] == 5 and r["case"] == "stall-large": r["barrier_seen"] = False   # block 5: barrier
            if r["block"] == 7 and r["case"] == "control": r["harness_error"] = "x"         # block 7: harness
        recs.append(tls_trial(1, "control"))                                                 # duplicate record
        Path(d, "trials.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
        t = A.analyse_tls([d], 20)
        assert [x["block"] for x in t["blocks_invalid"]] == [3, 5, 7], t["blocks_invalid"]
        assert t["blocks_invalid"][0]["reasons"] == {"early": "missing"}
        assert t["blocks_analyzed"] == [b for b in range(25) if b not in (3, 5, 7)][:20]
        assert t["blocks_unused"] == [23, 24] and t["blocks_valid"] == 22 and len(t["duplicate_records"]) == 1
        assert all(v["trials"] == 20 for v in t["per_case"].values())
    # a fence trial accepting bytes after the acknowledgement is counted, not raised (analyze_tls asserts instead)
    r = tls_trial(0, "buffered-fence", events=[{"kind": "WITHDRAW_REQUEST", "mono_ns": 1, "detail": ""},
                                               {"kind": "WITHDRAW_ACK", "mono_ns": 2, "detail": ""},
                                               {"kind": "BYTES_ACCEPTED", "mono_ns": 3, "detail": "n=7"}])
    assert A.tls_row(r)["after_ack_accepted"] == 7


def test_phone_rules():
    q = lambda m: {"a": "quiesced", "seen_max": m}
    assert A.phone_validity({"schedule": "kill", "kill_verified": True, "actions": [q(3)]}) is None
    assert A.phone_validity({"schedule": "kill", "kill_verified": False, "actions": [q(3)]}) == "kill not verified"
    assert A.phone_validity({"schedule": "kill", "actions": [q(3)]}) == "kill not verified"
    assert A.phone_validity({"schedule": "pending", "actions": [q(0)]}) == "jobs not observable"
    assert A.phone_validity({"schedule": "revoke", "actions": [q(-1)]}) == "jobs not observable"
    assert A.phone_validity({"schedule": "pending", "actions": [{"a": "quiesced"}]}) is None   # pre-seen_max records
    A.oracle_source()      # substitutions into matched_oracle.py still apply exactly


def test_life_selection():
    pilot = HERE.parent / "results/round3/test6/pilot-rtl-3/life"
    if not (pilot / "schedule.jsonl").exists():
        print("SKIP lifecycle selection: pilot-rtl-3 not present"); return
    with tempfile.TemporaryDirectory() as d:
        L = A.analyse_life({"G-a": pilot, "G-b": pilot}, d, 1)
        assert L["analyzed_paired_trials"] == {"G/kill": 1, "G/pending": 1, "G/revoke": 1}, L["analyzed_paired_trials"]
        assert sorted((u["instance"], u["schedule"]) for u in L["unused_valid"]) == \
            [("G-b", "kill"), ("G-b", "pending"), ("G-b", "revoke")], L["unused_valid"]
        assert not L["invalid_oracle_rules"] and not L["invalid_phone_rules"]
        # a kill trial with an unverified fault is removed before the oracle and listed
        bad = Path(d, "bad"); shutil.copytree(pilot, bad)
        rows = [json.loads(l) for l in (bad / "schedule.jsonl").read_text().splitlines()]
        for r in rows:
            if r["schedule"] == "kill": r["kill_verified"] = False
        (bad / "schedule.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        L = A.analyse_life({"G-c": bad}, Path(d, "o2"), 20)
        assert [x["reason"] for x in L["invalid_phone_rules"]] == ["kill not verified"]
        assert "G/kill" not in L["analyzed_paired_trials"]


if __name__ == "__main__":
    test_tls(); test_phone_rules(); test_life_selection()
    print("PASS: TLS validity/blocks/selection, phone validity rules, oracle substitutions, lifecycle selection")
