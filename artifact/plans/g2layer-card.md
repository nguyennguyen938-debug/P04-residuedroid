# Experiment card — G2b (group 2): AirGuard with a layered early check (protocol v1)

Status: written 21/11 23:xx, before any G2b trial; frozen at the commit that adds it (pilot → gate → final; chain
`plans/autorun/g2-chain.sh`, after G2a). Owner: B (Duy).
Source: PR #4 "Group 2 needs new runs by B: ... and a layered-early AirGuard build". Leader decision 21/11 (user). The plan
gives no design; every choice below is a B decision (standing grant), made before any data. The B2 protocol (b2-card.md
"Freeze") is reused unchanged except where stated. B7 freeze reopened for group 2 only; B2 data untouched.

## 1. Question and claim
- In the real app, on B2's lifecycle schedules, does a layered early consent check (one durable check under the lock before
  the donation is sent, no per-chunk check) prevent the stock residue as the fenced build does?
- Can support: AirGuard at the F-Droid commit, the B2 integration, the schedules pending/kill/reboot/netloss, N = 20 per
  schedule, the three builds in the same trials. Isolates what the fence adds over a durable early check on these schedules.
- Cannot support: withdrawals during an upload (no race schedule here; G2a and B10 cover the race), other apps, phones.
  A zero-vs-zero result between layered and fenced is reported as counts, not equivalence.

## 2. Design
- Builds (all side by side on one AVD):
  - stock and fenced: the frozen B2 APKs `realapp/airguard/build/airguard-{stock,fenced}.apk` (e53e5254…, 30eb823f…);
  - layered: new, from a fresh copy of the clean F-Droid checkout with `realapp/airguard/apply.sh` (additive third variant)
    and `FencedDonation.kt` (layered branch), `:app:assembleDebug -Presidue.variant=layered -Presidue.base=http://10.0.2.2:8795/`;
    package `de.seemoo.at_tracking_detection.p04layered`; copied to `realapp/airguard/build/airguard-layered.apk` (sha256 in
    SHA256SUMS and meta.json). Its donation goes through the same HttpTransport as fenced with `fenced=false`, after one
    `ConsentLog.permitted` check under the coordinator lock; a failed check logs DONATION_BLOCKED (`early=1`) and is not retried.
- Driver `followup/campaign_airguard.py --variants stock,fenced,layered` (default unchanged): per trial the three builds in
  lockstep, order shuffled per trial from seed `g2layer-20261121`; schedules pending, kill, reboot, netloss; **N = 20 per
  schedule**; 4 beacons per batch; quiescence as B2 (all builds ended a new donation attempt, max 90 s). Sink
  `airguard_sink.py` on 8795 (layered), 8796 (stock), 8797 (fenced). AVD P04AvdA on emulator-5666, after G2a (never in
  parallel with it).

## 3. Gate, validity, stopping, replacement (as B2)
- Pilot `pilot` (1 trial per schedule, excluded). Gate (mechanical): 4/4 trials valid, warm-up ok for all three builds,
  ≥ 1 donate request at each of the three ports. Fail → no final, reported.
- Validity (harness fields only): no trial_error; every hook ok; device alive at the end; all three event logs read; all
  three withdraw actions present. First 20 valid trials per schedule in k order.
- Replacement: environment failures only, k from 20 (`--start 20`), at most 3 per schedule.

## 4. Analysis
- `followup/analyze_airguard.py` (variants read from meta.json; B2 outputs reproduce byte for byte, checked 21/11):
  - primary: oracle v2 (host-clock withdrawal bracket, as B2's pre-registered result) → `results/round3/g2layer/analysis`;
  - also pre-registered here: oracle v3 (`--order device`; guest-clock order for the fenced and layered builds, which share
    the transport and its request ids) → `results/round3/g2layer/analysis-v3`.
- Per (schedule, build): violating trials (Wilson 95%), unknown trials (never folded in), deficit trials and beacons, blocked
  and error trials. Stock and fenced in this run are compared with B2 descriptively only (new run, new order seed).

## 5. Threats
As B2 (one AVD, emulator, synthetic beacons, HTTP sink, host-clock bracket in v2, mixed requests blocked whole). Three apps
per trial instead of two lengthen each trial and shift the apps' own worker timing; layered and fenced differ only in the
check point, so a race inside an upload is not exercised.

## 6. Outcome (after the run)
(to be filled)
