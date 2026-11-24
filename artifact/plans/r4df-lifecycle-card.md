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

## 6. Outcome (after the run)
