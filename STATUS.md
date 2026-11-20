> Round 3 note (2026-11-19, B): the page count below is that of the 2026-11-15 build; round-3 builds differ (see the
> latest `manuscript/build.sh` output; 12-page body limit). Phone and newer-Android validation now exists in round 3:
> Test 6 (Pixel 8a Android 17 via AWS Device Farm, Galaxy M35 Android 14 via Samsung Remote Test Lab; TLS suite and
> fixture lifecycle without reboot) and Test 4 (Android 14/15 emulators, B11). See `artifact/results/RUNLOG.md` and
> `artifact/plans/*-card.md`; the plan of record is `PLAN-ROUND3.md`.

# Revision complete — 2026-11-15

Implemented the approved P04 revision plan. The PDF uses explicit 10pt, has an 11-page main body
(17 pages total), and passes page-by-page inspection with no overflow or unresolved references.
All planned emulator/SDK runs and clean-extraction checks pass; 31 generated outputs reproduce exactly.
The local review ZIP is in `output/review-package/`. See `review/revision-execution-report.md`
for the checklist and `review/artifact-revision-audit.md` for evidence and limitations.
Phone/current-Android validation remains unavailable under the agreed scope. All task-owned
emulators and queues are stopped; historical reviews, raw results and measured APKs are preserved.

---

The following is the preserved pre-revision status history, not the current submission state.

# STATUS — P04 ResidueDroid (MobiSys 2027)

One line (2026-11-09 13:15): first build COMPLETE. All experiments finished on real emulators; the paper builds with no
placeholders (12 pp, body ends p.9, refs from p.10; 0 overfull, 0 undefined). Ready for a fresh-context review.

## Current state (2026-11-09)

No P04 process is running; emulator-5600 and emulator-5602 are shut down (other agents' ports untouched).

### Experiments (all real; every number in the PDF comes from scripts/render.py)
- Campaign c1 (JobScheduler, AVDs A+B): 825 trials logged, 55 invalid (host_sleep 17, restart/setup/trial_error 15,
  device_log 17, relaunch_failed 14, device_dead 14, net_unverified 7; reasons overlap), 770 valid; every AVD x schedule
  >= 50 valid (A: pen 52, kill 50, fstop 54, reb 56, rev 59, net 61, infl 60; B: pen 50, kill 61, fstop 53, reb 54,
  rev 52, net 55, infl 53). The paper analyzes the first 50 valid per AVD x schedule = 700 trials (70 valid unused).
- Micro (results/raw/micro, AVD B, 2026-11-08): bench 9/9, stress 6/6 x 300 rounds, crash 100/100. Valid.
- WorkManager 2.9.1 substrate (results/raw/sub_work, AVD A): 80 logged, 2 invalid (for015, reb015) -> 78 valid.
- AlarmManager substrate (results/raw/sub_alarm, AVD B): k=5..24, 80 logged, 0 invalid.
- ACRA 5.14.2 case, protocol v3 (results/raw/acra, AVD A, 2026-11-09): k=0..29 disable+control and k=0..9
  reboot+reboot-control, both variants = 160 trials, all valid (net verified). One record (acra disable 23) was repeated
  by the resume; render keeps the first. 2 failed attempts (attempts.jsonl: acrafence disable 20, acra disable 25; adb
  shell timeout in the reach probe; retried; no duplicate report reached the sink for either tag); never recorded as trials.
- Discarded, kept, not analyzed: sub_work/sub_alarm_INVALID_short_window, acra_INVALID_v1_wedged (2026-11-08: 23 trials
  then a 13 h adb-timeout loop; substring tag matching), acra_INVALID_v2_early_open (2026-11-09 10:30-10:37: app reopened
  < 60 s after the crash, which ACRA's StartupProcessorExecutor ignores).
- Static screen (360 F-Droid APKs): complete since 2026-11-08.

### Headline numbers in the PDF
- ResidueDroid: 0 prohibited items over 3,500 mediated tenant-trials (both AVDs); its fence logged 0 blocks for the
  FP-control tenants. conv (cancel+enqueue+job-start): 26% of tenant-trials. taint ablation withholds 55.6% of permitted
  items. Eq.(2): per-trial prediction 149/150, max abs error 0.06. noser: 39%/33%/46% of rounds (0/1/5 ms gap); rd 0/900.
- ACRA: stock uploaded the queued report after the user disabled reporting in 30/30 trials (median 0.2 s after reconnect);
  fenced 0/30 (fence logged a block 30/30); control 30/30 both; after reboot with reporting off 0/10 both, with it on 10/10
  both (sender job gone after reboot 40/40; startup path re-checks the flag).
- Substrates: WorkManager none 100% in pen/kill/fstop/reb, conv 20% (T1 only), rd 0; AlarmManager none 100/100/4/0%,
  conv 20/20/5/0%, rd 0.
- Negative results reported: unmediated T9 leaks under ResidueDroid (c1 78% pooled; WorkManager 100%, AlarmManager 69%);
  AlarmManager loses ~49% of FP tenants' permitted items (dropped alarms, all variants); after reboot no alarm app logged a
  process start in 60/60 trials although a manual reboot delivered BOOT_COMPLETED (stated as uncontrolled timing); non-taint
  FP deficits up to 1.1% (all in reb trials, JobScheduler stop reason connectivity).

### Harness fixes made today
- campaign.py: error-streak watchdog (cold restart of OUR emulator after 2 consecutive failed trials, abort exit 3 after
  --abort-after=5); resume launches no longer overwrite meta.json (meta_start<k>_<schedules>.json).
- acra_case.py rewritten (protocol v3): 30 s timeouts on every adb call with the full command in the error; reach probe
  wrapped in toybox `timeout 4`; tag matched only in CUSTOM_DATA.rd_tag (later reports quote earlier tags in LOGCAT);
  diag.jsonl + attempts.jsonl on failure; cold restart after 2 consecutive failures, abort after 6; never launches a
  duplicate emulator; new `rebootctl` schedule; reboot schedules reopen the app >= 70 s after the crash; reboot trials by
  absolute k (< --reboot-trials). Diagnosis of the 13 h loop: not reproduced in isolation; the same symptom (adb shell
  call never returning while the device answers other calls) recurred once today and the new retry recovered it.
- render: substrate validity now uses summarize.validity (same rules as c1); new macros (nValidAll/nValidUnused,
  defOther*, convTOneLifePct, convOtherLife*, sub*DefPct/TNinePct/RdItems/RdTT/MinPerSched, acra*RebCtl, acraJobGoneReb,
  acraFenceBlockLogged, microAvd).

### Write-up (done)
- tab_substrate + "Other deferred-work substrates" paragraph (§7.2); ACRA paragraph for protocol v3; RQ3 deficit paragraph
  corrected; legit-deficit definition matches the oracle; trial accounting in §7.1; abstract/intro/conclusion claims made
  exact for both AVDs (fence blocked no FP-control item; T9 leaks under ResidueDroid and every variant without an early
  check); external validity updated; tab_cost caption reads the AVD from micro/meta.json.
- others/notes.md ledger: no VERIFY-FINAL left. review/self-review.md finalized. review/citation-audit.md: 49 OK, 2 minor
  fixed, 51/51 cited.

### Re-run / regenerate
```
source /Users/xuanbachle/Workstation/MobiSys2027/papers/shared-android/env.sh
cd /Users/xuanbachle/Workstation/MobiSys2027/papers/P04-residuedroid/artifact
python3 scripts/summarize.py && python3 scripts/render.py && ../manuscript/build.sh     # or: make all
# experiments: make campaign / make micro / make acra / make substrates (see Makefile)
```

### AVDs and ports (P04 only)
- `P04AvdA`: console 5600, gRPC 8600; sinks 8787 (c1), 8792 (WorkManager), 8789 (ACRA v3)
- `P04AvdB`: console 5602, gRPC 8602; sinks 8788 (c1), 8790 (micro), 8791 (AlarmManager)

### Build status (2026-11-09 13:15)
`manuscript/build.sh`: 12 pages total, body ends on p.9, references from p.10 (body <= 12), 0 overfull boxes, 0 undefined
references/citations, 0 LaTeX errors, no ?? in the PDF. Macros: 232 defined, 0 missing.

## REAL vs PLACEHOLDER
All numbers in the PDF come from the artifact (render.py). Real: static corpus screen, emulator campaign c1 (complete),
micro-benchmarks, WorkManager and AlarmManager substrate runs, ACRA case (protocol v3, 160 trials). No simulated,
illustrative or invented numbers; no ?? placeholders remain.

Last updated: 2026-11-09 13:15 (+07)
