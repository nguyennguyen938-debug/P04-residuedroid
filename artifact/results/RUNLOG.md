# RUNLOG — P04 ResidueDroid

All times local (+07). Host: macOS 26 arm64, 18 CPUs. Emulator 37.2.13, image android-33 google_apis arm64-v8a rev 17
(fingerprint google/sdk_gphone64_arm64/emu64a:13/TE1A.240213.009/12342917:userdebug/dev-keys).
P04 instances only: P04AvdA on console 5600 (gRPC 8600), P04AvdB on 5602 (gRPC 8602).

## 2026-11-08

- 00:05 Created AVDs P04AvdA/P04AvdB (pixel_6, 2 GB RAM, 3 GB data) with the shared system image. Booted 5600 (16 s cold boot).
- 00:10 Built ResidueLab fixture (javac 17 + d8 + aapt2, no Gradle): one APK per enforcement variant via
  `--rename-manifest-package` (none, cancel, enqueue, jobstart, conv, egress, rd, volatile, taint, noser).
- 00:15 First trial: **no job ran in 49 s**. Diagnosis: `dumpsys jobscheduler` showed `Standby bucket: NEVER`,
  unsatisfied `WITHIN_QUOTA` (app installed but never opened). Fix: the harness opens each app's activity once and sets
  the standby bucket to `active` (state after recent use). Documented as a setup condition.
- 00:20 Second trial: 3 s-latency aggregator job ran only at 28.8 s (after the withdrawal at 9.3 s); summary jobs ran
  ~30 s after their minimum latency. JobScheduler batching makes fixed timelines unreliable, so (a) derivation now
  happens inline at setup (before any withdrawal, by design) and (b) the harness polls `dumpsys jobscheduler` until no
  job of ours is registered.
- 00:25 Verified `svc wifi disable; svc data disable` makes 10.0.2.2 unreachable from the guest (nc: Network is unreachable).
- 00:31–00:40 Smoke run (1 trial × 7 schedules, variants none+rd). Observations (real platform behavior):
  * **force-stop removes the app's JobScheduler jobs** (Android 13); on relaunch the app's startup flush path
    re-enqueues from its SQLite outbox; the by-value summary job of the deletion tenant is lost with it.
  * reboot: persisted jobs are restored and run (~32 s after reboot command incl. 22 s boot).
  * `pm revoke ACCESS_FINE_LOCATION` kills the process; persisted jobs still run afterwards.
  * net-loss and in-flight trials hit the 170 s timeout because the re-consent tenant's re-enqueued job was held by the
    manual-mode 600 s latency. Fix: only setup/aggregator jobs are held; harness force-runs leftovers after 60 s.
  * net-loss ordering changed: connectivity is cut immediately before the jobs are force-run and restored 6 s later.
- 00:41 Campaign c1 launched: A=5600 {none,cancel,enqueue,jobstart,conv,rd}, B=5602 {egress,rd,volatile,taint};
  7 schedules × 50 trials, identical seeded schedule parameters on both emulators; sink delay 300 ms.
- 02:15 **Host sleep stalls.** Trials from ~00:44 to 01:58 took 500–1000 s instead of 30–70 s; both emulators stalled at
  the same wall times. `pmset -g` shows system idle sleep after 1 min; `pmset -g log` shows sleep/dark-wake cycles
  (incl. "Dark Wake Thermal Emergency" sleep at 01:58:28). The host (and hence both emulators) was asleep mid-trial.
  Fix: a process-scoped `caffeinate -i -w <harness pid>` assertion for each campaign process (no power settings changed).
  Analysis flags any trial with an inter-action gap > 200 s as `host_sleep` and excludes it; extra trials are run so each
  schedule keeps >= 50 valid trials.
- 02:15 AcraLab built: real ACRA 5.14.2 (acra-core/http/advanced-scheduler AARs) + kotlin-stdlib 2.4.20 from Maven
  Central (SHA-256 in acra/deps/SHA256SUMS). Variants: `acra` (stock HttpSender) and `acrafence` (fenced ReportSender).
  Source reading (ACRA 5.14.2): JobSenderService -> SendingConductor.sendReports does not consult the enable toggle;
  StartupProcessorExecutor schedules approved reports only if enabled (check-at-enqueue). To run after campaign c1
  (it toggles device connectivity).
- 02:58/03:01 **Both emulators crashed** (qemu processes gone; crashpad warnings in emu logs) during host sleep/dark-wake
  cycling. The harness saw `dumpsys` output without a job list and wrongly treated it as quiesced. Fixes:
  `our_jobs()` returns -1 when the job list is missing; the harness relaunches its own AVD (same port) when the device
  is not booted; trials with an emulator restart, setup failure or unreadable device log are invalid.
  Switched the sleep assertion to `caffeinate -s -i` wrapped around each harness (system sleep on AC prevented; the OS
  keeps its thermal protections). No host sleep since 02:58.
- 03:06 **Net-loss schedule bug**: `svc wifi/data disable` takes >1 s to make 10.0.2.2 unreachable, so in net001 the
  jobs finished before connectivity dropped (all commits succeeded at +19..655 ms). Fix: after disabling, the harness
  polls `nc 10.0.2.2:<port>` from the guest until it fails (max 15 s) before force-running jobs, and polls again after
  re-enabling. Net-loss trials without `net_verified_down` are excluded. Campaign resumed at k=4.
- 03:14 B was relaunched while merely unresponsive (duplicate on port 5603). ensure_device now never launches while a qemu process for the AVD exists. Resumed both at k=5 (to k=56).
- 03:18 Emulator A crashed again (crashpad dumps; 'DisplaySurfaceGlContextHelper context was preempted'). Switched both P04 instances to -gpu guest (no host GL context). Restarted both harnesses at k=6 (to k=57).
- 03:21 **Net-loss schedule bug #2**: even when `nc` from the adb shell reported 10.0.2.2 unreachable after
  `svc wifi/data disable`, the app's uploads in net004 still succeeded (commits at +8..647 ms): per-UID routing kept
  the app on a working network. Fix: network loss is now a guest firewall rule (`iptables -I OUTPUT -d 10.0.2.2 -j
  REJECT`, root), verified on rd: three ConnectException attempts during the outage, commits right after removal.
  All net-loss trials with k < 7 are excluded. Harnesses restarted at k=7 (to k=58).
- 03:29 **Net-loss confound**: in net007 (A) the forced jobs of six apps exceeded JobScheduler's concurrency limit; the
  `jobstart` app's T8 job started only at +23 s, after connectivity had returned, while earlier apps' jobs held slots
  in their retry loops. Variant order thus decided who experienced the outage. Fix: net-loss now cuts connectivity
  per app, sequentially (6 s outage each), force-running only the trigger uploads of T8, T2, T5, T4 inside that app's
  outage; the rest run afterwards. Only trials with `net_mode=per-app-iptables` count. Restarted at k=8 (netloss first).
- 03:35 AcraLab functional check on B (network on): both `acra` (stock HttpSender) and `acrafence` (fenced ReportSender) delivered the crash report with rd_tag/rd_label custom data to the sink.
- 03:35 Campaign APK SHA-256: b7b2b158db9b5359d9b4a06dce9701634667b701a99948988fbc0f7b51388bf9  rl-cancel.apk 45cbbf304777e96696f31fb3eb5675b8bf5f23d91155c55389be138807ac26c4  rl-conv.apk 243bad2df275f34a6ec6643354141e305034ca92bcf81f324e68b7de0950e60a  rl-egress.apk 780a90af295073c53c061583fe413a788a202f5c4654452dd2f716656fbb48bb  rl-enqueue.apk 761c02ebba0a2fcdff06e03c5670d6b7355883c68e0087c465ea163e6d013f35  rl-jobstart.apk 0f5b2bfe3b20a44ec7e96d968cfd6a14017100fc8112ac56d2caa79b220d8472  rl-none.apk f9daf5a83d73486e01d5573670d17751e7fea0ef7af3c40839d85b54c4d0b487  rl-noser.apk f7bd78f0fade96c5995489b4a32849b331e94a763d4b42c203523152485e61fa  rl-rd.apk 919c38cbf5c207ef5976d69405e6436ebd5e6039312934648367f9a8a548821a  rl-taint.apk 198b3a4b0ce25a02ccd35d897fea2e7e0d9af315fdd117e76cb3b31a2fade199  rl-volatile.apk 
- 03:45 Model.variant() now strips an 'al' prefix so AlarmManager-substrate builds (org.residuelab.al{none,conv,rd}, manifest + USE_EXACT_ALARM, in fixture/build/apk_alarm) cannot overwrite campaign packages. Campaign APKs (hashes above) unchanged.
- 03:58 Post-campaign chain armed (harness/post_runs.sh): B -> micro, ACRA (30 disable/30 control/10 reboot per variant), AlarmManager substrate (alnone/alconv/alrd x 4 schedules x 20); A -> WorkManager 2.9.1 substrate (wmnone/wmconv/wmrd x 4 x 20). WorkManager build: Google Maven AARs, deps/SHA256SUMS; functional check uploaded 4 submissions.
- 04:20 fstop relaunch now uses 'am start -W' + pidof verification with one retry (2 of 9 A fstop trials had an app whose relaunch never started a process). Harnesses restarted at A k=15, B k=17; post-run chain re-armed on new PIDs.
- 07:25 **STOP request (checkpoint).** Killed post-run chain, both harnesses, sinks and caffeinate wrappers; removed guest
  iptables rules; `adb emu kill` on emulator-5600 and emulator-5602; no P04 qemu processes remain. Campaign c1 is PARTIAL:
  last completed trials A for038 (07:21:39), B reb050 (07:21:56); the trial in progress on each AVD at kill time was not
  logged to schedule.jsonl and is therefore absent (device_events/sink may hold a few lines for it, which the analysis ignores
  because they lack a schedule entry). Micro-benchmarks, ACRA case, WorkManager and AlarmManager substrate runs were NOT started.
- 18:04 RESUME: harness/resume_chain.sh A (pid 20618: c1 A k=39..64, then WorkManager substrate) and B (pid 20676: c1 B k=51..62 without pending, then micro, ACRA, AlarmManager substrate); each wrapped in caffeinate -i -w <pid>.
- 18:05 Handback forced while runs in progress; harness/finish_watch.sh will regenerate and shut down P04 emulators when both chains end.
- 20:31 finish_watch: chains done; summarize/render/build run (logs results/raw/final_*.log); P04 emulators 5600/5602 shut down.
- 20:34 **Audit of the 18:04 resume.** Complete: c1 B k=51-62; micro (bench 9/9, stress 6/6, crash 100/100);
  WorkManager substrate k=0-19. Partial: c1 A stopped at k=52 (wait_boot TimeoutExpired after an emulator crash during a
  reboot trial); ACRA stopped after 22 trials (adb TimeoutExpired); AlarmManager stopped after k=5 (wait_boot timeout).
  Fix: campaign.py records a failed trial as 'trial_error' (excluded), relaunches the AVD and continues; acra_case.py
  relaunches the AVD and retries the trial (failed attempts are never recorded). Rerun: harness/rerun_chain.sh A (pid 72958:
  c1 A k=53-68 for fstop/reb/rev/infl/net) and B (pid 72966: ACRA k=4-29 + reboot k=4-10, AlarmManager k=5-20), caffeinate -i -w.
  Note: ACRA "offline" uses svc wifi/data disable; per-trial records show ACRA's sender job in JobScheduler state
  'waiting' with the approved report on disk, i.e. the job's network constraint held it, which is what this case tests.
- 20:50 **Substrate runs invalid (observation window too short).** WorkManager (k=0-19) and AlarmManager (k=0-5) trials
  quiesced ~12 s after the withdrawal: neither WorkManager's delayed work nor the alarms appeared in the harness's
  quiescence check, so trials ended before the 15 s-delayed uploads ran (T8 upload ran in 0/20 WorkManager pen/kill/reb
  trials and 0/23 AlarmManager trials; only fstop exercised them). Moved to results/raw/*_INVALID_short_window (kept, not
  analyzed). Fix: substrate runs keep a minimum 75 s window after the lifecycle event (cap 240 s); WorkManager quiescence is
  read from its own WorkSpec table (states ENQUEUED/RUNNING/BLOCKED). Both substrate runs are redone in full.
- 20:36 followup_chain.sh armed: A -> WorkManager redo k=0-19 after rerun A; B -> AlarmManager k=21-24 after rerun B (rerun B writes k=5-20 into the fresh sub_alarm).
- 20:37 Second forced handback while rerun/follow-up chains run; harness/finish_watch2.sh regenerates and shuts down P04 emulators when all four chains end.
- 12:14 2026-11-09 session: AlarmManager finished (k=5..24, 80/80 valid); ACRA rewritten (protocol v3) and rerun on AVD A, stopped on user request after acra disable 23 (133 records); all P04 processes stopped, emulators 5600/5602 shut down. Details: ../STATUS.md Checkpoint (2026-11-09).
- 13:09 ACRA v3 resume k=23..29 done (161 records; acra disable 23 recorded twice, render keeps the first); 2 failed attempts total in attempts.jsonl; emulator-5600 shut down.

## 2026-11-18 (round 3, role B host)
- 15:44 SETUP role B (B0, PLAN-ROUND3.md). Host: Apple M4, 10 cores, 16 GB RAM, macOS 26.6.2.
  Toolchain: OpenJDK 17.0.21.1 (Homebrew openjdk@17), Android SDK cmdline-tools + platform-tools (adb 1.0.41), emulator 37.2.13,
  platforms;android-33, build-tools;34.0.0, system image android-33 google_apis arm64-v8a rev 17 (same as historical).
  AVD P04AvdB created by setup_avds.sh (pixel_6, hw.ramSize=2048, data 3G). preflight (AVDS=P04AvdB): 14 ok, 0 failed.
  fixture/build.sh: 10 APKs (build/apk); AlarmManager build reconstructed as MANIFEST=AndroidManifest.alarm.xml
  OUTDIR=build/apk_alarm VARIANTS="alnone alconv alrd" (3 APKs). Rebuilt APKs differ in bytes from the 2026-11-08 campaign
  APKs (toolchain/signing); hashes in each build dir's SHA256SUMS. No emulator started yet.
- 15:44 CORRECTION to the SETUP entry: all 10 rebuilt APK hashes differ from the 2026-11-08 campaign hashes (verified
  against the 03:35 list). Causes are not only toolchain/signing: the current fixture/src is the post-revision source; the
  historical c1 implementation is in pre-revision-source.tar.gz (excluded from this repository). INTEGRATION.md states legacy
  variants retain their recorded behaviour, but this rerun uses a different source snapshot: report it as such.
- 20:00 TEST6 PREP (B, Device Farm). AWS profile p04 (us-west-2): trial minutes 1000/1000, maxJobTimeout 150 min,
  no unmetered slots; budget alert 5 USD present. Patched TLS APK built in a scratch copy (real-device.patch applied there
  only): sha256 40631e6e…5ab879. Package zip sha256 71cb60df…0cc95d (fresh test cert, SAN 10.0.2.2/127.0.0.1/localhost, expires
  2026-12-18). Local rehearsal of the pilot spec on emulator-5644 (P04Avd15, Android 15, fingerprint AE3A.240806.043), no root,
  adb reverse 8798/8799, --n 1 × 7 cases → results/round3/test6/pilot-local-1 (PILOT, excluded): 0 harness errors,
  barrier_seen true in all 4 barrier cases, receiver complete for control, /proc/net/tcp readable. Device Farm project
  P04-test6 created (default job timeout 30 min); app, package and pilot spec uploads all SUCCEEDED; static pool
  pilot-pixel8a compatible. Device Farm Android fleet lists only Google Pixel models (Android 17); no Samsung → the plan's
  "Pixel + Samsung" pair is not available (decision needed with C). No device minutes used. Emulator shut down.
- 20:2x INCIDENT: artifact/results/raw/c1/A/sink/ingest.jsonl (52 MB, tracked) was found deleted from the working tree;
  directory mtime 19:48, coinciding with ~65 GB freed on the host disk; no harness or Claude command touches that path.
  Restored from git (blob 3496aee4…, identical). guard.sh rerun afterwards.
- 22:0x TEST6 DECISION (user): devices = Pixel 8a + Pixel 10 (Device Farm has no Samsung; plan's "2 máy khác hãng" not
  available → two Pixel generations, same vendor; to report to C for §7a).
- 22:0x TEST6 LIFECYCLE-ON-PHONE PREP (code only, no device, no minutes). Applied C's `devicefarm/real-device.patch` to B's
  files (Revision.java host extra; tls_suite.py --no-root/--host/ADB) — identical to the copy used for the uploaded TLS
  APK. Fixture: `Fence.HOST` now meta `sink_host` (SETUP extra, like sink_port), default 10.0.2.2. followup/campaign.py:
  `--no-root` (no adb root; run-as copy of rl.db+WAL queried on host; run-as kill -9 with pid check `kill_verified`;
  reboot/netloss refused; net() no-op) and `--sink-host`; `ADB` env override. Checks: default-mode adb command trace
  identical to HEAD (87 commands, 5 schedules, fake adb); no-root read == sqlite3 CLI text
  (`followup/test_campaign_noroot.py` PASS); fixture builds (OUTDIR=build/apk_dev). Side effect: `\impLoc` (render.py
  counts fixture/src Java lines) 1,230 → 1,233; manuscript/generated is C's, not committed here — C regenerates.
  Not yet run on any device (emulator rehearsal and Device Farm pilot need the user's go-ahead).
- 22:33 B11 PREP: AVD P04Avd14 created (android-34 google_apis arm64-v8a rev 14, pixel_6, 2 GB RAM, data 3G); config
  equals P04Avd15 except disk.dataPartition.size (P04Avd15 shows 6442450944 = 6 GiB in its config, apparently raised by the emulator
  at first boot; not verified). preflight IMAGES="34 35": 18 ok, 0 failed (warn: ~2 GB RAM free).
- 22:33 LAUNCH TEST6 local rehearsal 2 (PILOT, excluded; user go-ahead): emulator-5644 P04Avd15 -wipe-data, gpu guest;
  package v2 (zip sha256 f46008ce…01ec, rl-tls.apk 49ae92ac…341d, commit 400f62e) run as the combined pilot spec would run it:
  adb reverse 8798/8799/8787, TLS --n 1 then campaign.py --no-root --sink-host 127.0.0.1 pen,kill,rev × 1 →
  results/round3/test6/pilot-local-2/{tls,life}.
- 22:47 DONE TEST6 local rehearsal 2 (PILOT, excluded) → results/round3/test6/pilot-local-2. Mechanism checks only:
  adbd uid shell (no root used); TLS TLS_EXIT=0, barrier_seen true in both buffered cases, receiver 14 lines; lifecycle
  LIFE_EXIT=0, 3/3 trials quiesced (remaining 0), run-as DB read 15/15 without error, kill_verified true (5/5 pids gone),
  sink reached via sink_host 127.0.0.1 + adb reverse (325 lines). Timing: TLS part 174 s incl. install; lifecycle trials
  166/104/127 s (reset 34–49 s; pen/rev waited ~72–76 s, backstop force-run at 60 s) vs 55/43/34 s medians of the android-33
  matched campaign → 20 blocks ≈ 130 min per device, near the 150-min job cap: split lifecycle into 2 jobs per device
  (plan risk "chia thành nhiều lô nhỏ"). SHUTDOWN emulator-5644; adb reverse and listeners cleared. No Device Farm minutes used.
