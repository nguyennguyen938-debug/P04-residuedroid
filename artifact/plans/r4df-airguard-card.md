# Experiment card — round 4 on AWS Device Farm: AirGuard lifecycle on a rented phone (protocol v1)

Status: written 24/11 by B from C's draft (`devicefarm/phone-r4/card-airguard-phone.md`) and the Device Farm kit (PR #12);
committed before any Device Farm job of this task.
Owner (experimenter): B (Duy). Approved by: **pending leader** (issue #7).

## 1. Question and claim
- On a real phone, does stock AirGuard share beacons collected during opt-out after the user opts in again, and what do
  the fenced and layered builds do? This is B2 / G2b on a real phone.
- Can support: the real app's behaviour on one rented phone model, under the team's reading of the switch (paper caveat).
- Cannot support: real Bluetooth (beacons come from the test hook); a real server; other vendors.
- Paper: §7.4 (AirGuard sentence), abstract if there is a real-phone number.

## 2. Design
- Device: Pixel 8a, Android 17, AWS Device Farm (pool `pilot-pixel8a`), harness on the Device Farm host.
- Builds: `stock, fenced, layered` in the same trial (as G2b), built 24/11 by `devicefarm/phone-r4/build_airguard_phone.sh`
  from a clean F-Droid checkout at d515c534 (sink `http://127.0.0.1:<port>/`, cleartext also for 127.0.0.1); sources and
  hooks unchanged. SHA-256 in `realapp/airguard/build/phone/SHA256SUMS` and in the freeze.
- Schedules: `pending, kill, netloss` in one job pair and `reboot` in its own jobs. kill via `run-as`; reboot and netloss
  through adb reverse as in the lifecycle card.
- Harness: `campaign_airguard.py --phone` (`airguard-phone.patch` by C, applied 24/11) plus B's fault checks for phone runs:
  - netloss: each sink port is probed from the phone (`nc 127.0.0.1:<port>`) after the cut; `net_verified_down`;
  - kill: the app pid must exist before and be gone or changed after; `kill_verified`;
  - reboot: bounded wait for boot (300 s), then `boot_completed`.
- Unit: trial; oracle of B2 (`analyze_airguard.py`, host order).
- N: 20 trials per schedule (as B2 / G2b). Jobs: `SCHED=pending,kill,netloss` as `START=0 N=10` and `START=10 N=10`
  (timeout 70 min each); reboot (only if its pilot passes) `START=0 N=10` and `START=10 N=10` (timeout 80 min each).
- Seed: `airguard-df-20261125` (as in `specs/airguard.yml.in`); nbeacons 4, wait 90 s (B2 defaults).
- Freeze: `results/round3/phone-r4/aws/airguard/frozen-airguard-df` (incl. the three APK hashes) before the final jobs.

## 3. Validity, exclusion, stopping, replacement
- Rules of `analyze_airguard.py` (as B2), plus for plans recorded with `--phone` (unit test `followup/test_airguard_phone.py`):
  netloss without `net_verified_down` → "net cut not verified"; kill without `kill_verified` → "kill not verified";
  reboot without `boot_completed` → "reboot not completed". Emulator plans are judged as before (guard byte-identical).
- Stop after N. Replacement: environment failures only, whole trials, new job directory.
- Pilots (`pilot-*`, excluded): `SCHED=pending,kill,netloss START=0 N=1` and `SCHED=reboot START=0 N=1` (timeout 20 min each).
  Gate: `gates.py airguard <dir>/airguard --schedules ...` (no trial_error, hooks ok, device alive, app log readable, boot done).
- Risks to watch in the pilot: on Android 17 a broadcast to an app after `pm clear` may not arrive; the worker may be
  frozen in the background.

## 4. Analysis
- `followup/analyze_airguard.py <airguard dirs> --out results/round3/phone-r4/aws/airguard/analysis --n 20`.
- Estimand: violating trials per build, unknown apart, valid deficit (as B2).

## 5. Threats
- Construct: fake beacons through the hook; sink through adb reverse (USB) on the Device Farm host.
- External: one rented phone model; the reading of the switch (Appendix round3impl).
- Conclusion: N = 20 per schedule; 0/N is not a guarantee.

## Pilot log
- 24/11: the lifecycle reboot pilot showed that Device Farm ignores `adb reboot` (`plans/r4df-lifecycle-card.md`, Pilot
  log). **The reboot schedule is dropped on Device Farm**; AirGuard runs `pending, kill, netloss` only (pilot N = 1, then
  `START=0 N=10` and `START=10 N=10`). The uptime check (`reboot_verified`) is in the harness for a later own-phone run.

## 6. Outcome (after the run)
