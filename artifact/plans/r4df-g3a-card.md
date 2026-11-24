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
- Seed: `g3a-phone-20261125`.
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

## 6. Outcome (after the run)
