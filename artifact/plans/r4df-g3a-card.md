# Experiment card — round 4 on AWS Device Farm: G3a commit-point race on a rented phone (protocol v1)

Status: written 24/11 by B from C's draft (`devicefarm/phone-r4/card-g3a-phone.md`) and the Device Farm kit (PR #12);
committed before any Device Farm job of this task. N is written here after the calibration pilot and before the final.
Owner (experimenter): B (Duy). Approved by: **pending leader** (issue #7), including opening EC2 port 8800 to any address
for the run.

## 1. Question and claim
- On a real phone, does the socket accept a write that started after the withdrawal commit W, in the five G3a arms
  (early, cross-process cancel `close`, same-process cancel `close2`, fence, abortive fence `fence-abort`)?
- Can support: the paper's commit table repeated (or not) on one rented phone with the upload link limited at the receiver.
- Cannot support: other phones; an unlimited real radio path; bytes leaving the phone after the ack (no capture).
- Paper: §7.3 (commit table, a real-phone column), abstract if the result differs from the emulator.

## 2. Design
- Device: Pixel 8a, Android 17, AWS Device Farm (pool `pilot-pixel8a`), harness on the Device Farm host.
- Receiver: EC2 receiver B (`plans/test6/ec2/`, `PROFILE_SET=b10v3`, upload limited at EC2: edge, umts, lte), as Test 1 on
  the phone. Port 8800 opened to 0.0.0.0/0 for the run only (the Device Farm host address is not known in advance);
  the control API needs the token; the instance is deleted right after the run (`teardown.sh`).
- Arms: `early, close, close2, fence, fence-abort` in the same block, same `u` per (block, profile, size) as G3a.
- Sizes 32 KiB, 256 KiB, 2 MiB; `--sndbuf 16384` as G3a; `--warm-revision` as P3.
- Unit: trial. Block = 5 arms × 3 profiles × 3 sizes = 45 trials, order shuffled per block.
- N: from the calibration pilot, `min(10, floor(300 min / upper bound of one block))`; fewer than 5 blocks → no final.
  Final jobs of 3 blocks each (`--start 0/3/6 --trials 3`, then `--start 9 --trials 1` for N = 10), timeout 100 min each.
- Seed: `g3a-df-20261125` (as in `specs/g3a.yml.in`).
- Build: `fixture/build/g3-apk/rl-tls.apk` (the G3a binary, frozen in `frozen-g3-v8c`).
- Freeze: `results/round3/phone-r4/aws/g3a/frozen-g3a-df` before the final jobs.
- Package secrets: the G3a package holds the EC2 CA (no key) and the control token; packages and `uploads-*.env` stay
  outside the repo and are deleted after the run.

## 3. Validity, exclusion, stopping, replacement
- Invalid trial: rules of `analyze_g3race.py` (harness_error, missing end event), as G3a.
- Stop after N blocks; never stop or extend by outcome.
- Replacement: environment failures only (adb lost, EC2 unreachable, job timeout), whole blocks, in a new job directory.
- Pilot `g3a-pilot` (calibration, `--calibrate 3`, timeout 40 min), excluded. Gate: `gates.py g3a <dir>/g3a` (profiles
  separated: edge ≥ 3 × lte, umts ≥ 1.5 × lte; N from the block time).

## 4. Analysis
- `followup/analyze_g3race.py <g3a dir of each job> --out results/round3/phone-r4/aws/g3a/analysis --n <3N>`.
- Primary (as G3a): trials with `BYTES_ACCEPTED n>0` whose nearest `WRITE_ATTEMPT` is after W, per arm and profile; Wilson 95 %.
- Secondary: trials accepting after the ack; ack latency (median, p95).

## 5. Threats
- Internal: remote receiver (real latency plus the limit); `:revision` may be frozen on Android 17; job splits.
- Construct: socket acceptance only; bytes leaving the phone are not measured.
- External: one rented phone model, one network.
- Conclusion: N may be below G3a's; 0/N is not a guarantee.

## Pilot log and N (written 25/11 00:52, after the calibration pilot, before any final job)
- `pilot-calib` (24/11 00:30–00:50, `--calibrate 3`): gates.py PASS. 2 MiB medians edge 150.6 s, umts 138.8 s,
  lte 1.56 s (shaping separates the profiles); block upper bound 29.7 min → **N = 10 blocks** (450 trials, 90 per arm).
  Calibration used by the finals: `results/round3/phone-r4/aws/g3a/calibration-used.json`.
- Job timeout **130 min** (account maximum 150) instead of 100: three blocks may take up to about 89 min plus setup,
  and a timeout would cut the last block. Operational only, fixed before any final. Jobs: `f1 --start 0 --trials 3`,
  `f2 --start 3 --trials 3`, `f3 --start 6 --trials 3`, `f4 --start 9 --trials 1`.

## 6. Outcome (after the run)
Source: `results/round3/phone-r4/aws/g3a/analysis/g3race-summary.json` (pre-registered `analyze_g3race.py` on f1–f4, `--n 30`)
and `results/round3/phone-r4/aws/r4df-report.json`.

- **Run:** f1 (blocks 0–2) 00:53–02:12, f2 (3–5) 02:17–03:22, f3 (6–8) 03:29–04:36, f4 (9) 04:42–04:58 on 25/11; Pixel 8a,
  Android 17; receiver B on EC2 (`b10v3`); 216.9 trial minutes. EC2 receiver log kept in `g3a/receiver-ec2/`; the instance,
  its security group and key pair were deleted after the run.
- **Validity:** 450 trials logged (10 blocks × 45), 0 invalid, 0 interrupted, 0 unused; 30 per (profile, arm).
- **Primary: trials whose socket accepted a write that started after W** (per profile and arm, N = 30; Wilson 95 %):

  | arm | edge | umts | lte | all |
  |---|---|---|---|---|
  | early | 22 (55.6–85.8 %) | 18 (42.3–75.4 %) | 22 (55.6–85.8 %) | 62/90 |
  | close (cross-process cancel) | 4 (5.3–29.7 %) | 3 (3.5–25.6 %) | 20 (48.8–80.8 %) | 27/90 |
  | close2 (same-process cancel) | 0 (0–11.4 %) | 0 (0–11.4 %) | **6 (9.5–37.3 %)** | 6/90 |
  | fence | 0 (0–11.4 %) | 0 (0–11.4 %) | 0 (0–11.4 %) | 0/90 |
  | fence-abort | 0 (0–11.4 %) | 0 (0–11.4 %) | 0 (0–11.4 %) | 0/90 |

  close2 on lte by size: 32 KiB 0, 256 KiB 2, 2 MiB 4. Paired per trial (counts, no p-values): close2 vs fence 84 both 0,
  6 close2 only; fence-abort vs fence 90 both 0; close2 vs close 63 / 0 / 21 / 6 (both 0 / close2 only / close only / both).
- **Secondary:** violations after the ack: early 22 / 18 / 22 (edge / umts / lte), every other arm 0. Withdrawal-to-ack latency
  medians: fence 14.5 / 12.4 / 12.1 ms, close2 7.8 / 7.7 / 4.6 ms, close 33.7 / 30.9 / 28.4 ms (edge / umts / lte; p95 and
  max in the summary).
- **Reading (descriptive, one rented phone):**
  - the fence and the abortive fence: no socket acceptance after W in 90 trials each (not a guarantee; 0–11.4 % per cell);
  - **unfavourable for the emulator result:** same-process cancellation (close2) was 0/90 on the emulator (G3a) and 0 on
    lte in P3, but here it let the socket accept a write started after W in 6/30 lte trials (all 256 KiB or 2 MiB). So the
    claim "same-process cancellation 0" does not carry over to this phone; unserialized cancellation can lag W here too;
  - cross-process cancellation lags W far more on lte (20/30) than under edge / umts shaping (4, 3);
  - the early check accepts after W in 18–22/30 per profile, as on the emulator.
- **Threats (in addition to §5):** remote receiver over the internet (latency and shaping at EC2); one device model; the
  close2 difference from the emulator is one cell (lte) of 30 trials; why it lags (scheduling on the phone, the faster link)
  is not diagnosed here.
