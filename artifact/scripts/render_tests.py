#!/usr/bin/env python3
"""Render round-3 test results (tests 1 to 6) into manuscript/generated/tests_macros.tex.

Input: artifact/results/round3/summary.json, a flat object {macro name: value}. B writes it at data freeze.
Every name in SCHEMA becomes a LaTeX macro; a missing key renders as \\textbf{??}, so the final PDF check
(no ?? allowed) catches any number that never arrived. LaTeX macro names cannot contain digits."""
import csv, json, os, re

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ART, "results", "round3", "summary.json")
OUT = os.path.join(os.path.dirname(ART), "manuscript", "generated", "tests_macros.tex")

# name: meaning. Counts are integers; "Pct" values are percentages without the % sign.
SCHEMA = {
    # Test 1: natural race, large payloads, throttled network (B10). Layer = layered early, Fence = chunk fence.
    "raceTrials": "trials per network profile and variant",
    "raceEdgeLayer": "EDGE: layered-early trials with bytes accepted after acknowledgement",
    "raceEdgeFence": "EDGE: fence trials with bytes accepted after acknowledgement",
    "raceThreegLayer": "3G: same, layered early", "raceThreegFence": "3G: same, fence",
    "raceLteLayer": "LTE: same, layered early", "raceLteFence": "LTE: same, fence",
    "racePredPct": "Eq. 2 predicted violation probability for layered early, pooled",
    "raceObsPct": "observed layered-early violation rate, pooled",
    # Test 2: label mutation (B12 runs artifact/mutation). Leak = trials with a confirmed violation.
    "mutTrials": "trials per mutant",
    "mutOneLeak": "M1 union-latest: leaking trials", "mutOneFlagged": "M1: items flagged by label_check.py",
    "mutOneWrong": "M1: items whose label omits a source (ground truth)",
    "mutTwoLeak": "M2 stale-epoch: leaking trials", "mutTwoFlagged": "M2: flagged items", "mutTwoWrong": "M2: wrong-label items",
    "mutThreeDeficit": "M3 extras-drop: permitted items undelivered",
    # Test 3: promises in the surveyed apps (C10), computed from survey/promise_coding.csv, not from summary.json.
    # Counts are of the sample, not of F-Droid.
    "promiseApps": "apps with a consent signal surveyed", "promiseCand": "of which deferred-egress candidates",
    "promisePending": "switch worded as sending or sharing", "promiseCandPending": "same, among candidates",
    "promiseCollectOnly": "switch worded as collection only", "promisePrompt": "per-report send action only",
    "promiseUnclear": "identifiers only or unclear wording", "promiseFalse": "scanner false positives",
    "promiseRestrict": "processing restriction", "promiseDelete": "deletion offer",
    "promiseFlagged": "apps the model coder flagged for review", "promiseRecoded": "flagged apps an author recoded",
    # Test 4: lifecycle on newer Android (B11).
    "lifeFourteenTrials": "Android 14 paired trials", "lifeFourteenLayer": "Android 14 layered-early violating trials",
    "lifeFourteenFence": "Android 14 fence violating trials",
    "lifeFifteenTrials": "Android 15 paired trials", "lifeFifteenLayer": "Android 15 layered-early violating trials",
    "lifeFifteenFence": "Android 15 fence violating trials",
    # Test 5: chunk size and sender sweep (B4).
    "sweepAckSmallMs": "median withdrawal ack, 1 KiB chunks, 1 sender (ms)",
    "sweepAckLargeMs": "median withdrawal ack, 64 KiB chunks, 16 senders (ms)",
    "sweepCpuSmall": "CPU ms/MiB, 1 KiB chunks", "sweepCpuLarge": "CPU ms/MiB, 64 KiB chunks",
    # Test 6: physical phone (B6 or C11).
    "devModel": "phone model(s)", "devAndroid": "Android version(s)", "devTrials": "TLS barrier trials",
    "devEarlyComplete": "early-check requests completed after withdrawal",
    "devFenceAfterAck": "fence trials accepting ciphertext after acknowledgement",
    # Added 21/11 (PR #2, answers C1 and C3). Lifecycle on the two rented phones, pooled over phones and the pending,
    # kill and revoke schedules, pre-registered denominators.
    "devLifeEnqViol": "menqueue violating trials", "devLifeEnqN": "menqueue analysed trials",
    "devLifeFenceViol": "mfence violating trials", "devLifeFenceN": "mfence analysed trials",
    # Test 1 on a personal phone, same meaning as race*.
    "racePhoneModel": "phone model", "racePhoneAndroid": "Android version", "racePhoneTrials": "trials per profile and variant",
    "racePhoneEdgeLayer": "EDGE: early violating trials", "racePhoneEdgeFence": "EDGE: fence violating trials",
    "racePhoneThreegLayer": "3G: early", "racePhoneThreegFence": "3G: fence",
    "racePhoneLteLayer": "LTE: early", "racePhoneLteFence": "LTE: fence",
    "racePhonePredPct": "Eq. 2 predicted early violation rate", "racePhoneObsPct": "observed early violation rate",
    # B12 per-build trial counts (mutTrials is the minimum and is not cited).
    "mutBaseTrials": "base trials", "mutOneTrials": "M1 trials", "mutTwoTrials": "M2 trials",
    "mutThreeTrials": "M3 trials", "mutBaseDeficit": "base permitted items undelivered",
    # B2, AirGuard real app, pending + kill + reboot pooled; unknowns from the pre-registered oracle v2 and post-hoc v3.
    "airN": "trials per build", "airStockViol": "stock violating trials", "airFenceViol": "fenced violating trials",
    "airFenceUnknownV": "fenced unknown trials, oracle v2", "airFenceUnknownVThree": "fenced unknown trials, oracle v3",
    # B3, split policy.
    "splitTrials": "trials per cell", "splitPreRecovered": "requests recovered when no chunk was accepted",
    "splitPostRecovered": "requests recovered after a chunk was accepted",
    "splitAfterAck": "B3 trials with bytes accepted after the acknowledgement",
    # Counts the paper cites that the first schema missed.
    "lifeFourteenEnq": "Android 14 menqueue violating trials", "lifeFifteenEnq": "Android 15 menqueue violating trials",
    "mutBaseLeak": "base build leaking trials", "mutThreeLeak": "M3 leaking trials",
    "sweepLogged": "B4 v3 trials logged", "sweepLockStalls": "B4 v3 trials where a sender waited the full deadline for the lock",
    # Receiver side of the natural races (scripts/receiver_race.py): trials acknowledged before the request was fully
    # handed off ("cut"), and how many of them the receiver still logged as complete.
    "raceCutEarly": "emulator early trials cut by the withdrawal", "raceCutEarlyComplete": "of which the receiver got complete",
    "raceCutFence": "emulator fence trials cut", "raceCutFenceComplete": "of which complete at the receiver",
    "racePhoneCutEarly": "phone early trials cut", "racePhoneCutEarlyComplete": "of which complete",
    "racePhoneCutFence": "phone fence trials cut", "racePhoneCutFenceComplete": "of which complete",
    # Group 2 (PR #5). G2a: B10 race with early, close (early check + socket close before the ack) and fence in the same
    # blocks, EDGE/3G/LTE pooled. Ack medians are per profile; Lo/Hi are the smallest and largest of the three.
    "gcloseN": "G2a trials per mode", "gcloseEarlyViol": "early violating trials", "gcloseCloseViol": "close violating trials",
    "gcloseFenceViol": "fence violating trials", "gcloseCut": "close trials cut by the withdrawal",
    "gcloseCutComplete": "of which complete at the receiver", "gcloseAckLo": "close median ack ms, lowest profile",
    "gcloseAckHi": "close median ack ms, highest profile", "gcloseFenceAck": "fence median ack ms, highest profile",
    "gcloseAbortDelivered": "exploratory: close trials not cut, receiver complete, app saw SEND_ERROR",
    "gcloseFenceDelivered": "exploratory: fence trials not cut, receiver complete",
    "gcloseFenceAbortDelivered": "exploratory: of which the app saw SEND_ERROR",
    # G2b: AirGuard stock, fenced and layered early in every trial; pending + kill + reboot pooled, oracle v2.
    "glayN": "trials per build", "glayStockViol": "stock violating trials", "glayFenceViol": "fenced violating trials",
    "glayLayerViol": "layered violating trials", "glayUnknown": "unknown trials, all builds",
    # Round-4 review (C, scripts/post_commit_race.py, exploratory): trials whose socket accepted bytes from a write attempted
    # after the withdrawal commit W (WITHDRAW_DURABLE), per arm; N per arm.
    "raceCommitEarly": "emulator early", "raceCommitFence": "emulator fence", "raceCommitN": "emulator trials per arm",
    "racePhoneCommitEarly": "phone early", "racePhoneCommitFence": "phone fence", "racePhoneCommitN": "phone trials per arm",
    "gcloseCommitEarly": "G2a early", "gcloseCommitClose": "G2a close", "gcloseCommitFence": "G2a fence",
    "gcloseCommitN": "G2a trials per arm", "gcloseCommitCloseKib": "G2a close: KiB accepted from post-commit writes",
    # Wilson 95% for the pooled race cells (percent): early arm per platform, and the upper bound of 0 of N.
    "raceObsLo": "emulator early lower", "raceObsHi": "emulator early upper", "racePhoneObsLo": "phone early lower",
    "racePhoneObsHi": "phone early upper", "raceZeroHi": "upper bound for 0 of N (N per arm, both platforms)",
    # Group 3 (issue #7, PR #8; make_summary.group3). G3a: five race arms in the same blocks, EDGE/3G/LTE pooled; W = the
    # withdrawal's commit (WITHDRAW_DURABLE). close = cancellation from the withdrawing process (another process); close2 =
    # withdrawal and cancellation in the sending process, requests not yet handed off; abort = fence with SO_LINGER 0.
    "gtrN": "G3a trials per arm", "gtrEarlyW": "early trials accepting a write attempted after W",
    "gtrCloseW": "close trials after W", "gtrCloseTwoW": "close2 trials after W", "gtrFenceW": "fence trials after W",
    "gtrAbortW": "fence-abort trials after W", "gtrCloseLte": "close trials after W on LTE",
    "gtrEarlyAck": "early trials with bytes accepted after the ack", "gtrCancelAck": "close + close2 trials after the ack",
    "gtrCapLo": "G3b: fewest trials per arm with request payload after the ack marker", "gtrCapHi": "most such trials",
    # P3: LTE, exposure balanced across arms (g3lte-card.md v5).
    "gpN": "P3 trials per arm", "gpEarlyW": "early after W", "gpCloseW": "close after W",
    "gpCloseExposed": "close trials with W during the writes", "gpEarlyExposed": "early trials with W during the writes", "gpCloseTwoW": "close2 after W", "gpFenceW": "fence after W",
    "gpAbortW": "fence-abort after W", "gpFenceAckP": "fence p95 ack ms", "gpAbortAckP": "fence-abort p95 ack ms",
    "gpCloseTwoAckP": "close2 p95 ack ms",
    # P4: send-buffer level x fence / fence-abort, EDGE and 3G; TLS application data after the ack marker, W during writes.
    "gsN": "P4 trials per cell", "gsAfterW": "P4 trials after W, all cells",
    "gsFenceSmallLo": "fence median KB after the marker at 16 KiB, lower profile", "gsFenceSmallHi": "same, higher profile",
    "gsFenceMidLo": "fence median KB at 64 KiB, lower", "gsFenceMidHi": "same, higher",
    "gsFenceDefLo": "fence median MB at the default buffer, lower", "gsFenceDefHi": "same, higher",
    "gsAbortMax": "fence-abort maximum bytes after the marker, any cell",
    "gsAbortMed": "largest per-cell median of fence-abort bytes after the marker", "gsPairs": "paired trials with W during writes",
    "gsAbortLess": "pairs where fence-abort sent fewer bytes than fence", "gsDefaultKib": "default SO_SNDBUF reported, KiB",
    # G3c v4 (AirGuard, in-upload withdrawal; receiver window corrected in analysis-v4-r2).
    "gaN": "G3c v4 trials per build", "gaSentMin": "fewest trials with payload after the ack marker, any build",
    "gaSentMax": "most such trials, any build", "gaStockRx": "stock: receiver logged the donation complete after the ack",
    "gaCancelRx": "stockcancel: same", "gaLayerRx": "layered: same", "gaFenceRx": "fenced: same",
    "gaFenceRxFirst": "fenced: same, first analysis before the receiver-window correction",
    # G3c v5c: equal send buffer. Sixteen = stockcancel with SO_SNDBUF 16 KiB; Cancel = stockcancel, default buffer.
    "gbSixteenN": "stockcancel16 trials", "gbSixteenRx": "stockcancel16 receiver-complete after the ack",
    "gbSixteenLo": "Wilson lower", "gbSixteenHi": "Wilson upper", "gbCancelN": "stockcancel trials",
    "gbCancelRx": "stockcancel receiver-complete", "gbCancelLo": "Wilson lower", "gbCancelHi": "Wilson upper",
    "gbFenceN": "fenced trials", "gbFenceRx": "fenced receiver-complete", "gbFenceLo": "Wilson lower", "gbFenceHi": "Wilson upper",
    "gbPairSixteenOnly": "pairs: stockcancel16 only", "gbPairFenceOnly": "pairs: fenced only", "gbPairBoth": "pairs: both",
    "gbPairNone": "pairs: neither", "gbKernSmallKib": "kernel send buffer of stockcancel16 and fenced, KiB",
    "gbKernDefKib": "kernel send buffer of stockcancel, KiB",
    "gbNoCallRx": "exploratory: stockcancel16, withdrawal during the donation, cancel found no call, body complete",
    # G3d v4: Galaxy A06, Wi-Fi, foreground; fence/early ratios of medians over 4 KiB, 256 KiB and 2 MiB.
    "gdCells": "valid cells", "gdUploads": "successful uploads", "gdUploadFail": "failed uploads",
    "gdCpuLo": "fence/early CPU per MiB, smallest ratio", "gdCpuHi": "largest", "gdTimeLo": "fence/early time, smallest",
    "gdTimeHi": "largest", "gdEnergyNonzero": "cells with a nonzero batterystats UID estimate", "gdEnergyCells": "cells read",
}


def esc(v):
    if isinstance(v, float):
        v = f"{v:.1f}"  # summary.json carries raw floats; the paper prints one decimal
    return re.sub(r"([%&#_$])", r"\\\1", str(v))


def main():
    data = json.load(open(SRC, encoding="utf-8")) if os.path.exists(SRC) else {}
    unknown = sorted(set(data) - set(SCHEMA))
    assert not unknown, f"summary.json has keys outside the schema: {unknown}"
    coding = os.path.join(ART, "survey", "promise_coding.csv")
    if os.path.exists(coding):
        rs = list(csv.DictReader(open(coding, encoding="utf-8")))
        n = lambda cat, xs=rs: sum(r["final_category"] == cat for r in xs)
        cand = [r for r in rs if r["candidate"] == "1"]
        data.update(promiseApps=len(rs), promiseCand=len(cand), promisePending=n("PENDING"),
                    promiseCandPending=n("PENDING", cand), promiseCollectOnly=n("COLLECT_ONLY"),
                    promisePrompt=n("PROMPT"), promiseUnclear=n("UNCLEAR"), promiseFalse=n("NOT_CONSENT"),
                    promiseRestrict=n("RESTRICT"), promiseDelete=n("DELETE"),
                    promiseFlagged=sum(r["flagged"] == "yes" for r in rs),
                    promiseRecoded=sum(bool(r["recode_reason"]) for r in rs))
    lines = ["% generated by artifact/scripts/render_tests.py; do not edit"]
    missing = "\\textbf{??}"
    for k in sorted(SCHEMA):
        v = esc(data[k]) if k in data else missing
        lines.append("\\newcommand{\\" + k + "}{" + v + "\\xspace}")
    open(OUT, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(f"tests macros: {len(SCHEMA)} defined; missing: {len(set(SCHEMA) - set(data))}")


if __name__ == "__main__":
    assert all(re.fullmatch(r"[A-Za-z]+", k) for k in SCHEMA), "macro names must be letters only"
    main()
