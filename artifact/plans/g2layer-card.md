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
- Runs: pilot 22/11 01:50–01:54 (gate passed: 4/4 valid, warm-up ok for the three builds, donate requests at 8795/8796/8797);
  final 01:55–03:00 (autorun g2layer-final, guard 0). Installed hashes in meta.json: stock e53e5254…, fenced 30eb823f… (the B2
  builds), layered f450a506…. Logged / excluded / valid / analysed / unused: 80 trials (three builds each) / 0 / 80 / 80 / 0.
  Data `results/round3/g2layer/final`; analyses `analysis` (v2, primary) and `analysis-v3` (device order).
- Violating trials (v2; Wilson 95%), 20 per cell; v3 gives the same counts:

  | Schedule | stock | fenced | layered |
  |---|---|---|---|
  | pending | 20/20 [0.839, 1] | 0/20 [0, 0.161] | 0/20 [0, 0.161] |
  | kill | 20/20 [0.839, 1] | 0/20 [0, 0.161] | 0/20 [0, 0.161] |
  | reboot | 20/20 [0.839, 1] | 0/20 [0, 0.161] | 0/20 [0, 0.161] |
  | netloss | 0/20 [0, 0.161] | 0/20 [0, 0.161] | 0/20 [0, 0.161] |

  Unknown trials: 0 in every cell (v2 and v3). Deficit: 0 in pending/kill/reboot for every build; netloss 80/80 beacons
  (20/20 trials) for every build, as in B2 (the app does not retry a failed run).
- layered vs fenced: zero vs zero in every schedule (no confirmed difference in 20 paired trials per schedule, not
  equivalence). Both delivered every 'post' beacon in a later run (80 per schedule). Stop points (`followup/posthoc_g2layer.py`
  → `results/round3/g2layer/posthoc/posthoc.json`, descriptive): layered stopped 60 donations at the early check (`early=1`),
  fenced 60 in the transport (60 BLOCK events), i.e. both stopped the mixed request before any of it was sent.
- Stock (descriptive): 'optout' beacons donated after re-consent in 20/20 trials of pending, kill and reboot (80 each), plus
  'pre' beacons in an 'after' request in 10/20 trials of each of those schedules.
- Comparison with B2 (descriptive; new run, three apps per trial, new order seed): violations identical (stock 20/20, fenced
  0/20 in pending/kill/reboot; netloss 0 for all); B2 fenced had 8, 9, 9 unknown trials under v2, here 0; B2 stock had 'pre'
  in an 'after' request in 2/20 pending trials, here 10/20 per lifecycle schedule. Not analysed further.
- Reading: on these lifecycle schedules the withdrawal precedes the next donation, so one durable consent check before
  sending is enough; the fence adds nothing measurable here. The fence's advantage needs a withdrawal during an upload
  (B10, G2a, Test 1 on the phone), which this schedule set does not create.
- Deviations: none from this card. Negative or null: 0/20 is not an impossibility guarantee (upper bound 16.1%).
