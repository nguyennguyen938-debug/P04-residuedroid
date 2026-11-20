# Experiment card — b11 (test 4, protocol v1)

Status: frozen at the commit that adds this card (manifest `plans/autorun/b11-final.json`)
Owner (experimenter): B (Duy)   Approved by: B decisions 19/11 where the plan is silent (user: "các quyết định khác bạn chọn")

Sources: `[R3]` PLAN-ROUND3.md (B11: "Dựng AVD Android 14 và 15 arm64, chạy pen, kill, reb, net với một baseline yếu, layered
early và ResidueDroid. Không cần viết code mới"), `[HB]` HUONG-DAN-B.md (keys), `[RT]` render_tests.py SCHEMA.

## 1. Question and claim
- Question: do the lifecycle results of the matched campaign (recorded on Android 13 / API 33) hold on Android 14 and 15?
- Claim it can support: "On Android 14 and 15 emulators (arm64, google_apis), with identical injected schedules (pending,
  kill, reboot, netloss), the weak baseline / layered early / ResidueDroid variants show … in N valid paired trials".
- Cannot support: physical-device behaviour, OEM changes, other API levels, independent-hardware replication (one AVD per
  version), forcestop/revoke/inflight (not run here).
- Keys [RT]: `lifeFourteenTrials`, `lifeFourteenLayer`, `lifeFourteenFence`, `lifeFifteenTrials`, `lifeFifteenLayer`,
  `lifeFifteenFence` (definitions §4). Section: §7 one paragraph, table in appendix [R3].

## 2. Design
- Variants (B decision, plan names roles only): `menqueue` = weak baseline (checks at enqueue), `mlayer` = layered early,
  `mfence` = ResidueDroid (fence at each socket chunk); matched set, same metadata, run inside the same trial (paired).
- Schedules: pending, kill, reboot, netloss [R3]; fixed order inside each block k (harness: k outer, schedules inner).
- Unit: paired trial (3 variants in one trial); affected tenants 1, 2, 4, 5, 8 (as `matched_oracle.py`).
- N = 20 valid paired trials per schedule per AVD (B decision; same N as Test 6 and the plan's other tests).
- Seed `b11-20261119`; `--timeout 90` and `--apkdir fixture/build/revision-apk` as `followup/start_matched.py`; sink delay 300 ms.
- Devices: P04Avd14 (android-34 google_apis arm64-v8a rev 14) on emulator-5650, sink 8790; P04Avd15 (android-35) on
  emulator-5654, sink 8791. Run sequentially (14 then 15) to avoid shared-host load. Harness launches/relaunches its own
  emulator (`--avd`), `-read-only`.
- Build: revision APKs = the Test 6 package v4 APKs (fixture source unchanged since 400f62e; sha256 in
  `results/round3/test6/frozen-test6-v2/package-sha256.json`), copied to `artifact/fixture/build/revision-apk/`.
- Harness: `followup/campaign.py` (root mode on the emulator; unchanged except the `seen_max` field added 19/11).

## 3. Validity, exclusion, stopping, replacement
- Invalid paired trial (rules of `followup/matched_oracle.py`, unchanged): trial_error / setup_fail / emulator_restarted; an
  action gap > 200 s; device not alive at the end; a variant without device log; netloss without `net_verified_down`.
  Plus: `seen_max` ≤ 0 (no job of ours parsed while waiting).
- Analyse the first 20 valid paired trials per (AVD, schedule) in k order; later valid ones are unused (reported).
- Replacement (environment failures only): new k ≥ 20 for the short schedule, fresh directory; cap 5 per cell.
- Stopping: planned k 0–19 done plus needed replacements, or the 29/11 freeze. Never outcome-dependent.
- Pilots: none new; the harness ran on P04Avd15 in the Test 6 rehearsals (pilot-local-1/2).

## 4. Analysis
- `followup/matched_oracle.py` logic (executed unchanged via the Test 6 wrapper approach), per AVD.
- Key definitions (B decision): `lifeXTrials` = valid paired trials analysed for that AVD (all four schedules);
  `lifeXLayer` / `lifeXFence` = paired trials in which `mlayer` / `mfence` has ≥ 1 confirmed violation among affected
  tenants. Unknown requests reported separately, never folded into "no violation". Wilson 95% intervals with N.
- Comparison with the API-33 matched campaign is descriptive (different AVD/version), not causal.

## 5. Threats to validity
- Internal: fixed schedule order; one AVD per version; sequential runs at different times; shared host.
- Construct: receiver acceptance via the host sink (10.0.2.2) — same boundary as the matched campaign.
- External: emulator only; google_apis images; fixture app, not real apps.
- Conclusion: N = 20 per cell; zero-vs-zero reported as paired counts; no p-values.

## 6. Outcome (filled after the run)
- Logged / excluded by reason / valid / analyzed / unused (paired trials): Android 14: 82 logged (80 in `avd14-final`, 2
  replacements reb020–reb021 in `avd14-repl`), 2 excluded (reb004, reb014: emulator reboot timeout → trial_error, oracle
  reason "harness/device"), 80 valid, 80 analysed (20 per schedule), 0 unused. Android 15: 80 logged, 0 excluded, 80 valid,
  80 analysed, 0 unused. Extra rule `seen_max ≤ 0`: 0 trials.
- Results directory: `results/round3/b11/{avd14-final,avd14-repl,avd15-final}`; analysis
  `results/round3/b11/analysis/b11-summary.json` (`followup/analyze_b11.py`).
- Outcome per AVD (paired trials with ≥ 1 confirmed violation among affected tenants; Wilson 95%): menqueue 80/80
  [0.954, 1] on both AVDs (380/400 affected tenant-trials); mlayer 0/80 [0, 0.046]; mfence 0/80 [0, 0.046]. Unknown
  requests: 0 for every variant. Permitted items missing (`legit_missing`, summed): menqueue 80 per AVD, mlayer 0, mfence 0.
- Deviations: replacements as in §3 (2 reboot trials on Android 14, new k ≥ 20, fresh directory). Exclusion list in the
  first analysis output omitted the two excluded trials (reporting bug: taken from the second, filtered pass); fixed in
  `analyze_b11.py` on 19/11, keys and per-AVD results byte-identical before/after.
- Negative or null results: mlayer vs mfence is zero-versus-zero on both AVDs (no confirmed difference in 80 paired trials
  each; not equivalence). The weak baseline also loses permitted items. 0/80 is not an impossibility guarantee (upper
  Wilson bound 4.6%). Emulator only, one AVD per Android version; not compared causally with the API-33 campaign.
