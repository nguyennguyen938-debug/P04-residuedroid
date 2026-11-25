# Experiment card — round 4 on AWS Device Farm: matched lifecycle with reboot and network loss (protocol v1)

Status: written 24/11 by B from C's draft (`devicefarm/phone-r4/card-lifecycle-phone.md`) and the Device Farm kit
(`devicefarm/phone-r4/aws/README.md`, PR #12); committed before any Device Farm job of this task.
Owner (experimenter): B (Duy). Approved by: **pending leader** (issue #7). No job runs without the leader's go-ahead.

## 1. Question and claim
- On a real phone, after a reboot and during a lost connection to the server, do the matched variants (same metadata)
  violate the withdrawal contract? Test 6 had only pending, kill and revoke, because no reboot or network cut was available.
- Can support: "layered early and the fence do not violate" extended to reboot and network loss on one rented phone model.
- Cannot support: real Doze or standby buckets (the harness forces the bucket active); other vendors; a radio-level outage
  (the cut is the adb reverse port, see §2).
- Paper: §7.5 (real phone sentence), §8 threats (the sentence "reboot and network loss only on the emulator" if this runs).

## 2. Design
- Device: Pixel 8a, Android 17, AWS Device Farm (`us-west-2`, private pool `pilot-pixel8a` of project `P04-test6`, as Test 6);
  no screen lock. Harness on the Device Farm host (`amazon_linux_2`, custom environment testspec from `make_spec.sh life`).
- Variants: `menqueue, mstart, mlayer, mfence, mboth` in the same paired trial (as Test 6).
- Schedules: `netloss` and `reboot`, in separate jobs (a lost device in a reboot job does not take other trials with it).
  - reboot: `adb reboot` (no root); the `adb reverse` port is re-added as soon as adbd is back.
  - netloss: the `adb reverse` port is removed for the 6 s outage (the app gets connection refused), the analogue of the
    emulator's REJECT rule to 10.0.2.2. Radios and firewall are untouched. This is a different fault mechanism from the
    emulator and is stated as such.
- Unit: paired trial; affected tenants T1, T2, T4, T5, T8 as Test 6.
- N: 20 paired trials per schedule (as Test 6). Jobs: netloss `START=0 N=20` (timeout 80 min); reboot `START=0 N=10` and
  `START=10 N=10` (timeout 100 min each).
- Seed: `lifecycle-df-20261125` (as in the testspec template `specs/life.yml.in`; campaign seed-schedule-k derivation).
- Window: `--timeout 90` as Test 6.
- Build: `fixture/build/revision-apk/rl-{menqueue,mstart,mlayer,mfence,mboth}.apk`, rebuilt 24/11 from `main` (9c483a9 +
  the patches below). They are **not** the Test 6 binaries (Test 6 APK hashes are in its results); source changes since
  19/11 (G3 transport hooks) are recorded in the freeze.
- Harness: `campaign.py --no-root --sink-host 127.0.0.1 --phone-faults` (`phone-faults.patch` by C, applied 24/11, plus B's
  bound on the post-reboot boot wait: a phone that does not finish boot within limit + 120 s ends the trial as an error).
- Freeze: `results/round3/phone-r4/aws/life/frozen-life-df` (`revision/freeze.py`) before the final jobs; APK SHA-256 in it.

## 3. Validity, exclusion, stopping, replacement
- Rules of `analyze_test6.py` (incl. matched_oracle rules) plus, for phone runs: netloss without `net_verified_down == true`
  → "net cut not verified"; reboot without `boot_completed` → "reboot not completed".
- The "action gap > 200 s" rule may exclude reboot trials if the phone boots slowly; the pilot records the gap.
- Stop after N. Replacement: environment failures only (device lost, job timeout), whole paired trials, new IDs via resume.
- Pilots (`pilot-*`, excluded): `life-pnet` (netloss, N=1) and `life-preb` (reboot, N=1), timeout 20 min each.
  Gate: `devicefarm/phone-r4/gates.py life <dir> --schedules netloss|reboot`. If the reboot pilot loses the device or has no
  `boot_completed`, the reboot schedule is dropped on Device Farm and reported in issue #7 (no retry on the same protocol).

## 4. Analysis
- `followup/analyze_test6.py --manifest devicefarm/phone-r4/aws/manifest-life-df.json --out
  results/round3/phone-r4/aws/life/analysis --n 20` (job dirs filled in the manifest after the runs).
- Estimand as Test 6: trials where an affected tenant violates, per variant; unknown reported apart; valid deficit.
- Keys: C adds them, reported next to Test 6 and the emulator, never replacing them.

## 5. Threats
- Internal: netloss by adb reverse differs from the emulator's iptables; real boot time; job splits.
- Construct: the socket ends at adbd over USB on the Device Farm host, as Test 6; no network path is measured.
- External: one rented phone model, Android 17.
- Conclusion: N = 20 per schedule; 0/N is not a guarantee.

## Pilot log
- **pilot-preb (24/11 21:57, reboot, N = 1): Device Farm does not reboot the phone.** The job passed both gates
  (`gates.py`, `gate_b.py`), but the logged `boot_s` was 0.55 s and the device's monotonic clock in all five apps' event logs
  ran on across the `adb reboot` (about 5,420 s before and 5,470–5,493 s after; `plans/r4df/reboot_evidence.py` →
  `pilot-preb/reboot-evidence.json`). The command was ignored; `sys.boot_completed` stayed 1, so the old check could not
  tell. Following §3, **the reboot schedule is dropped on Device Farm** for this task and for AirGuard (no AirGuard reboot
  pilot is run). Harness fix (protocol v1.1, before any further job): with `--phone-faults` / `--phone`, the reboot action
  records `/proc/uptime` before and after, `reboot_verified` = uptime restarted, and the analysis marks a plan with
  `reboot_verified` false as "reboot not verified" (`followup/test_phone_reboot.py`, `test_airguard_phone.py`). This keeps
  the check for a later own-phone run, where `adb reboot` works.
- Also before the netloss pilot (24/11): positive control for the cut. With `--phone-faults` / `--phone`, the probe must see
  the sink up right before each cut (`net_probe_before`), and `net_verified_down` needs up-before and down-after (a missing
  `nc` would otherwise read as down). The probe's one-line `x` gets HTTP 400 from the sinks and is not logged.
- Remaining lifecycle work on Device Farm: netloss pilot, then the netloss final (`START=0 N=20`).

## 6. Outcome (after the run)
Source: `results/round3/phone-r4/aws/life/analysis/` (pre-registered `analyze_test6.py`, manifest `plans/r4df/manifest-life-df.json`)
and `results/round3/phone-r4/aws/r4df-report.json` (`plans/r4df/report_r4df.py`, Wilson intervals).

- **Run:** netloss final `life/net`, 24/11 22:16–22:45, Pixel 8a, Android 17; 27.5 trial minutes. Reboot: dropped (Pilot log).
- **Validity:** 20 paired trials logged, 0 invalid (oracle rules 0, phone rules 0), 0 unused, 20 analysed. The cut was
  confirmed in every trial (up before, down after).
- **Affected-tenant trials with a confirmed violation** (5 affected tenants × 20 paired trials = 100 per variant; unknown 0):

  | variant | violating | Wilson 95 % (tenant-trials as independent) | cluster bootstrap p95 (analysis) | permitted deficit |
  |---|---|---|---|---|
  | menqueue | 80/100 | 71.1–86.7 % | 0.8–0.8 | 80 |
  | mstart | 80/100 | 71.1–86.7 % | 0.8–0.8 | 80 |
  | mlayer | 0/100 | 0–3.7 % | 0–0 | 0 |
  | mfence | 0/100 | 0–3.7 % | 0–0 | 44 |
  | mboth | 0/100 | 0–3.7 % | 0–0 | 0 |

  The bootstrap interval has no width because every paired trial gave the same count; Wilson treats the 100 tenant-trials
  as independent, which they are not (5 per paired trial).
- **Reading (descriptive, one rented phone, netloss through the adb reverse port):** layered early, the fence and both show
  no confirmed violation in 20 paired trials (not a guarantee); enqueue-time and job-start checks violate in 80/100. mfence
  withholds 44 permitted items, mlayer and mboth none. Compared with the emulator and Test 6 by C; never substituted.
- **Threats (in addition to §5):** the network cut removes the adb reverse port (connection refused), not a radio outage;
  rebuilt APKs (not the Test 6 binaries); one device model.
