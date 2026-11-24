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
- 2026-11-19 08:20 TEST6-ALT RTL CHECK (no install, user go-ahead): Samsung Remote Test Lab, Galaxy M35 (SM-M356B,
  product m35xxx), Remote Debug Bridge on localhost:52011, host adb platform-tools 37.0.1. `adb devices` shows the device
  as `device` and `get-state` answers, but every service request hung with no output (`shell echo`, `shell -x`,
  `exec-out`, `reverse --list`; 20–30 s caps, plus one 120 s getprop batch, stopped). The RDB log then printed "ADB disconnected
  from RDB". Nothing was installed and no reverse was set. `adb disconnect` done. Suspected incompatibility between the new
  adb client and the RDB relay (not verified). Next: retry with platform-tools r33.0.3 (dl.google.com) on its own server port.
- 2026-11-19 08:28 TEST6-ALT RTL CHECK 2: same session (RDB localhost:52011, reconnected) with platform-tools r33.0.3 adb on
  its own server port 5038: shell answers (5 × `shell true` 0.09–0.16 s). Device: Galaxy M35 SM-M356B, Android 14 / SDK 34,
  fingerprint samsung/m35xxx/m35x:14/UP1A.231005.007/M356BXXS4AYB6:user/release-keys, arm64-v8a; adbd uid 2000 shell (no
  root); run-as and pidof present; adb reverse 8798/8799/8787 accepted; no org.residuelab.* packages present before install.
- 2026-11-19 08:30 LAUNCH TEST6-ALT RTL pilot (PILOT, excluded; user asked B/Claude to run it all): package v2 (commit
  400f62e harness, same APKs as the Device Farm package) run as testspec-pilot-combined.yml runs it, against the RTL device
  over RDB (ADB = r33 adb, server port 5038): TLS --n 1 (7 cases), then campaign.py --no-root --sink-host 127.0.0.1
  pen,kill,rev × 1 → results/round3/test6/pilot-rtl-1/{tls,life}. Receivers on this Mac; phone reaches them through adb
  reverse over the RTL relay (remote network path, not USB).
- 2026-11-19 08:27 ABORT TEST6-ALT RTL pilot (PILOT, excluded) → results/round3/test6/pilot-rtl-1 kept as is. Timeline
  from rehearsal.log: pre_test and TLS start 08:25:54; rl-tls.apk install and the CA push went through; the next command
  (`shell cat …pem | run-as org.residuelab.tls sh -c "cat > files/test-ca.pem"`) hit the harness's 40 s adb timeout →
  traceback, TLS_EXIT=1, no TLS trial ran. The user reported at the same time that the RDB log showed a disconnect. Lifecycle
  started 08:26:37 and wrote nothing (schedule/device_events empty); stopped by B/Claude. Afterwards the device is still
  listed as `device`, but `shell echo` gets no answer within 15 s. Sink on 8787 (started by campaign.py) killed; no host
  listeners remain. Left on the device until the next connection: org.residuelab.tls installed,
  /data/local/tmp/p04-test-ca.pem. Cause of the drop not known (relay or session side; nothing on the host side
  except hung streams). Correction: the two entries above labelled 08:28 and 08:30 actually happened ~08:24–08:25
  (times were estimated, not read from the clock; rehearsal.log has the real ones).
- 2026-11-19 08:39 TEST6-ALT RTL STABILITY PROBE (no install): same session, RDB localhost:52011 reconnected, r33 adb (port 5038);
  `shell echo ok` every 2 s for 10 min (08:28:53–08:38:5x): 300/300 OK, 0 timeouts (10 s cap); round trip median 0.10 s,
  nearest-rank p95 0.18 s, max 0.31 s. Log kept in B's scratch (diagnostic, not data). Leftovers of the aborted pilot
  removed (uninstall org.residuelab.tls, rm /data/local/tmp/p04-test-ca.pem); /data/local/tmp also holds app.apk and
  sep.apk, not ours, untouched.
- 2026-11-19 08:39 LAUNCH TEST6-ALT RTL pilot 2 (PILOT, excluded; user: "ok thử lại", run if 10-min probe passes): same runner
  and package as pilot 1 → results/round3/test6/pilot-rtl-2/{tls,life}; the echo probe runs alongside so that a hang can be
  told apart from a relay drop.
- 2026-11-19 08:41 ABORT TEST6-ALT RTL pilot 2 (PILOT, excluded) → results/round3/test6/pilot-rtl-2 kept as is. Same
  failure point as pilot 1: TLS start 08:39:25, install and push fine, then `shell cat …pem | run-as org.residuelab.tls sh -c
  "cat > files/test-ca.pem"` hung (40 s harness timeout, TLS_EXIT=1). The parallel echo probe went OK, OK, then TIMEOUT
  from 08:39:39 on, i.e. the whole adb link froze while that one command was in flight and did not recover after it was
  killed. Lifecycle then failed at start ("device not alive", LIFE_EXIT=1, nothing written). Probe and sink stopped.
- 2026-11-19 08:44 DIAGNOSIS (RTL, after reconnect; each command 10 s cap, then an echo check): OK and link alive after
  `pm list packages`, `echo hi | cat`, `run-as org.residuelab.tls id` (uid 10293, runas_app), `run-as … ls -la`. Hung and
  froze the link: `run-as org.residuelab.tls sh -c "echo x > files/p04probe.txt; …"` (no stdin pipe). So the trigger is a
  shell started under run-as, not the pipe and not run-as itself. Why the RDB relay dies on it is unknown. Harness use:
  only tls_suite.py:56 starts `run-as … sh -c`; campaign.py --no-root uses `exec-out run-as <pkg> cat` and
  `run-as <pkg> kill -9 $(pidof <pkg>)` (no shell under run-as), tls_suite also uses run-as cat/rm/touch. Left on the device:
  org.residuelab.tls (with files/p04probe.txt, if it was written). After this the relay refused `adb connect` until the
  RDB side is restarted.
- 2026-11-19 08:45 HARNESS FIX (pilot stage, before freeze): followup/tls_suite.py:56 CA copy no longer starts a shell under
  run-as: `run-as <pkg> tee files/test-ca.pem < /data/local/tmp/p04-test-ca.pem > /dev/null` (the device shell opens the
  file, tee runs as the app). Same bytes land in files/test-ca.pem (checked on RTL: sha256 of the device copy = the
  package's test-ca.pem). Applies to all later TLS runs (emulator default mode too); earlier runs unaffected (same file
  content). Device Farm package v2 does not have it → needs v3. Noted: package v2's followup/tls-cert/test-ca.pem
  (9abca707…) differs from the committed one (849f6d65…); origin to be traced (package internally consistent:
  rehearsal 2 passed).
- 2026-11-19 08:45 LAUNCH TEST6-ALT RTL pilot 3 (PILOT, excluded): package v2 + the line-56 fix, same runner, RDB localhost:52011
  (restarted by the user), device cleaned first (uninstall org.residuelab.tls, rm pem) → results/round3/test6/pilot-rtl-3;
  echo probe alongside. Session has ~30 min left; stop at ~10 min before the end if not done.
- 2026-11-19 08:51 DONE TEST6-ALT RTL pilot 3 (PILOT, excluded) → results/round3/test6/pilot-rtl-3. Mechanism checks only:
  device Galaxy M35 SM-M356B, Android 14, user build, adbd uid shell (no root); TLS 08:45:46–08:46:38, TLS_EXIT=0, 7/7 cases
  logged, barrier_seen present in the 4 withdraw cases, receiver 15 lines over adb reverse through the RDB relay; lifecycle
  08:46:38–08:50:54, LIFE_EXIT=0, 3/3 trials (pen000 75 s, kil000 99 s, rev000 77 s) quiesced with remaining 0, no "could not
  read"/"changed during", kill via run-as with kill_verified true, meta root=false / db_read run-as copy / model + android
  recorded, sink reached via sink_host 127.0.0.1 (ingest 297, ack 135 lines). Echo probe alongside 155/155 OK (median 0.10 s,
  p95 0.19 s, max 0.39 s). Cleanup: 6 org.residuelab.* packages uninstalled, CA file removed, reverse list empty, adb
  disconnect, r33 adb server killed; no host listeners or harness processes left. RTL session closed by the user.
  Open: RTL as a Test 6 environment departs from S0 (AWS) → needs C/team agreement; tls_suite.py:56 fix needs a new
  Device Farm package (v3); package CA vs committed CA mismatch to be traced.
- 2026-11-19 08:52 CORRECTION to the 08:51 entry: "RTL session closed by the user" is not confirmed; B/Claude only disconnected adb. The user ends the RTL session in the browser.
- 2026-11-19 08:55 RESOLVED (CA mismatch noted 08:44): the Device Farm package build generates a fresh 30-day test CA/key pair into the package (openssl req -x509 … SAN 10.0.2.2,127.0.0.1,localhost; the tls-cert instructions; private key never committed), so package test-ca.pem ≠ committed one by design. Not an error.
- 2026-11-19 08:53 TEST6 DECISION (reported by the user): C agrees to Samsung Remote Test Lab as a Test 6 environment. Device mix and N per environment still open. User has 22 RTL credits; minutes per credit not yet confirmed.
- 2026-11-19 08:55 TEST6 DEVICES (user): one Device Farm device + one RTL device → Pixel 8a (Device Farm, Android 17, default: the pilot device) + Galaxy (RTL, Android 14). Package v3 built locally = v2 + tls_suite.py:56 fix only (diff checked), zip sha256 e1777dad…e5ff, not uploaded. plans/test6/README.md updated (devices, RTL procedure, budget).
- 2026-11-19 09:13 TEST6 PREP (no device; user: N=20, prepare and debug before any run): card artifact/plans/test6-card.md (protocol v1,
  draft until committed + frozen). Harness: tls_suite.py --start (default 0, same behaviour); campaign.py records seen_max in the
  quiesced action (largest job count parsed while waiting; no new adb command: emulator command trace still identical, 87).
  New: plans/test6/run_rtl.sh + rdb_probe.py (RTL runner: preflight before install, link probe + watchdog, cleanup),
  testspec-main-job1/2.yml (from the pilot spec; ranges and seed only), runs.json (analysis manifest), run_df.sh extracts
  customer-artifact zips; followup/analyze_test6.py (card validity rules; lifecycle = matched_oracle.py executed unchanged
  except paths/run list) + test_analyze_test6.py; results/round3/test6/EXCLUSIONS.md (pilots). Offline checks: no-root read
  test PASS; analysis tests PASS; tls_suite --start and job-2 spec command run against a fake phone; run_rtl.sh full dry run
  and simulated link drop (watchdog stopped harness after ~60 s, no orphan process/port, exit 4); pilot data only used as
  well-formed input, no outcome inspected. Package v4 built (zip sha256 8562abeb…09d7; = v2 + the three harness changes),
  not uploaded. Guard OK (macros.tex allowed: \impLoc, C regenerates).
- 2026-11-19 09:31 TEST6 FREEZE (protocol v1): card committed 7b2b523; freeze.py → results/round3/test6/frozen-test6-v1 (104 files) + package-sha256.json (v4, 20 files, key excluded; package scripts == commit). From here a harness change = protocol v2.
- 2026-11-19 09:34 LAUNCH TEST6 Device Farm pilot (PILOT, excluded; user go-ahead "bạn tự làm, chạy auto"): Pixel 8a (Android 17, pool pilot-pixel8a), package v4 + testspec-pilot-combined (uploaded 09:32 as -v4), job timeout 20 min, receiver mode A → results/round3/test6/pilot-df-pixel8a. Trial minutes before: 1000.
- 2026-11-19 09:41 DONE TEST6 Device Farm pilot (PILOT, excluded) → results/round3/test6/pilot-df-pixel8a. Job PASSED (spec
  ran), 4.42 metered min (1000 → 995.58). Gates (plans/test6/check_gates.py): lifecycle all pass on Pixel 8a Android 17
  (fingerprint google/akita/akita:17/CP2A.260605.012; 3/3 trials 56/95/94 s, remaining 0, seen_max 67/65/67 → dumpsys parser
  works on 17, kill_verified true, 15/15 run-as DB reads, sink 297 lines, root=false). TLS FAIL: TLS_EXIT=1 at
  `adb install -r rl-tls.apk` (rc≠0, empty stderr; Device Farm adb 1.0.39), no TLS trial. Likely cause: Device Farm
  pre-installs the uploaded app (rl-tls.apk) and Android 14+ update ownership refuses the shell update (not verified; logcat
  starts after that step). Customer artifacts extracted to unzipped/ (zip kept).
- 2026-11-19 09:42 PROTOCOL v2 (Test 6, before any main run): Device Farm specs (pilot-combined, main-job1, main-job2) pre_test now
  prints installer/updateOwner of org.residuelab.tls and uninstalls it, so tls_suite.py installs it fresh (as on RTL and
  emulator). Harness, analysis, N, validity unchanged. Card → protocol v2. Re-pilot → pilot-df-pixel8a-2.
- 2026-11-19 09:43 TEST6 FREEZE v2: results/round3/test6/frozen-test6-v2 (source pins identical to v1; package v4 unchanged; run_material = sha256 of plans/test6 specs/scripts at 2ec2551). Specs uploaded as *-v2proto.yml. runs.json Device Farm paths set to the customer-artifact layout. LAUNCH TEST6 Device Farm chain (user go-ahead "bạn tự làm, chạy auto"): plans/test6/run_df_chain.sh = pilot-df-pixel8a-2 (timeout 20) → check_gates.py (stop if fail) → pixel8a-j1 (TLS 0–19 + life k 0–9, timeout 100) → pixel8a-j2 (life k 10–19, timeout 100); receiver mode A.
- 2026-11-19 09:51 DONE TEST6 Device Farm pilot 2 (PILOT, excluded; protocol v2) → results/round3/test6/pilot-df-pixel8a-2.
  4.9 metered min (995.58 → 990.73). check_gates.py: ALL GATES PASS (TLS 7/7, TLS_EXIT=0, barrier_seen 4/4, receiver 15
  lines; lifecycle 3/3, remaining 0, seen_max 67/65/67, kill_verified true, 15/15 DB reads, sink 297 lines, root=false,
  Pixel 8a Android 17). Diagnostic: the pre-installed org.residuelab.tls had installer=null (installerPackageUid -1,
  versionCode 0), so the update-ownership guess for pilot 1 is NOT supported; why `adb install -r` failed there stays
  unknown; uninstall-then-install works. Chain continued to main job 1 (09:51).
- 2026-11-19 09:52 LAUNCH TEST6 RTL session 1 (main, protocol v2; user go-ahead "bạn tự làm, chạy auto"; RDB localhost:52011): run_rtl.sh package v4, TLS blocks 0–19 + lifecycle k 0–4 (pending,kill,revoke) → results/round3/test6/galaxy-s1. Session end time not given (assumed 60 min from now). Runs in parallel with Device Farm job 1 (separate device and host).
- 2026-11-19 09:53 ABORT TEST6 RTL session 1 attempt (environment): `adb connect localhost:52011` → failed to connect (RDB relay refused), preflight ABORT before anything was installed; dir renamed galaxy-s1_INVALID_rdb-connect (R2.6). run_rtl.sh cleanup now checks the link first (it reported 'left 0' instead of 'unknown' when not connected; run-time logic unchanged). Waiting for the user to restart RDB; retry → galaxy-s1.
- 2026-11-19 09:55 LAUNCH TEST6 RTL session 1 retry (main, protocol v2): RDB localhost:41654 (restarted by the user), same arguments → results/round3/test6/galaxy-s1. End time not given (assumed 60 min).
- 2026-11-19 09:56 ABORT TEST6 RTL session 1 attempt 2 (environment): failed to connect to localhost:41654; cause found: the default adb server (5037, not this run's 5038) held the RDB connection (lsof: adb pid on 5037 ESTABLISHED to the rdb listener; device listed offline there) — the RDB tool's own 'ADB connected to RDB'. Released only that device on 5037 (adb disconnect with the matching SDK adb). Dir renamed galaxy-s1_INVALID_rdb-connect2. run_rtl.sh preflight now does this release itself (logged). Possibly also explains the adb-37 hangs of pilot-rtl-1 (two adb servers on one relay); not verified.
- 2026-11-19 09:57 RTL: default adb server (5037; no device attached, no emulator running) stopped with its own adb kill-server so it cannot auto-connect (mDNS, suspected) to the RDB relay; this run's r33 server stays on 5038. Waiting for the user to restart RDB.
- 2026-11-19 10:38 RTL: default adb server had restarted (09:58:27, SDK adb 37, parent launchd) and grabbed the new RDB port 49195 again. Restarted it with the same SDK adb and ADB_MDNS=0 ADB_MDNS_AUTO_CONNECT=0 (suspected mDNS auto-connect), no device attached to it.
- 2026-11-19 10:38 Correction: on 5037 the RDB device was listed as 'localhost:49195' (an explicit adb connect, apparently by the rdb tool), not an mDNS name; the mDNS guess is not supported. After the default server restart, r33 on 5038 connected and answered (model SM-M356B). LAUNCH TEST6 RTL session 1 (main, protocol v2; user: "làm lại rtl"): RDB localhost:49195 → results/round3/test6/galaxy-s1, TLS 0–19 + lifecycle k 0–4.
- 2026-11-19 10:47 INCIDENT TEST6 Device Farm job 1: the job finished (PASSED, 53.78 metered min, trial minutes 990.73 →
  936.95) but its poller died with "run_df.sh: line 19: syntax error" because B/Claude edited run_df.sh (cost guard) while
  that bash process was still reading it; no artifact was downloaded by it. Fix: new plans/test6/fetch_df.sh downloads a
  finished run by name (no device minutes); fetched → results/round3/test6/pixel8a-j1 (fetched.txt). Gates (check_gates.py
  --tls 140 --life 30): ALL PASS (TLS 140/140, barrier_seen 80/80, receiver 300 lines; lifecycle 30/30, remaining 0,
  seen_max 65–67, kill_verified 10/10, 150/150 DB reads, sink 2970 lines). No data lost. Job 2 was scheduled by the new
  run_df.sh (trial minutes before 936.95; guard passed). Rule for B/Claude: never edit a script a running process uses.
- 2026-11-19 10:47 ABORT TEST6 RTL session 1 attempt 3 (environment): preflight at 10:38:44 'shell does not answer' on
  localhost:49195 (a probe one minute earlier answered); cleanup then hung on an untimed `reverse --remove-all` until killed
  at 10:45. run_rtl.sh: every device adb call now time-limited (to N), connect skipped if already attached, a default-server
  hold is released by restarting that server (what worked at 10:37); re-checked offline (fake phone: normal run; dead link →
  abort + cleanup in 25 s). Dir galaxy-s1 → galaxy-s1_INVALID_rdb-noanswer.
- 2026-11-19 10:55 RTL relay now owned by B/Claude (user: "connect từ terminal của bạn … tự động fix và chạy"): stopped the
  user's rdb; ~/Downloads/rdb/rdb refuses to start without adb on PATH ("Could not find adb in PATH") — so rdb runs
  `adb connect` itself, which is what kept attaching the device to the default 5037 server. Started rdb with the r33 adb first on
  PATH and ANDROID_ADB_SERVER_PORT=5038 (this run's server). Relay listening (adb port 55977, web port 8888); waiting for the
  RTL web page to attach the device (desktop notification sent to the user). New plans/test6/rtl_auto.sh runs the Galaxy parts
  s1–s4 unattended: restarts the relay when the link dies, continues a part in a new dir after the last recorded index (the
  index in progress = environment failure, replaced at ≥ 20 per card §3), max 3 relay restarts per part.
- 2026-11-19 10:58 LAUNCH TEST6 RTL unattended (user clicked RDB; relay owned by B/Claude, device attached to the 5038 r33 server by rdb itself, probe answered): plans/test6/rtl_auto.sh parts s1 s2 s3 s4 → results/round3/test6/galaxy-s*.
- 2026-11-19 10:58 rtl_auto.sh failed to start (bash 3.2: no declare -A); fixed (part specs as strings). User: RTL session has 37 min left → this session runs part s1 = TLS 0–19 + lifecycle k 0–2 (PSPEC s1:0:20:0:3), END=11:34; lifecycle k 3–19 in later sessions (chunking only; N and rules unchanged).
- 2026-11-19 10:59 run_rtl refused s1 with k 0–2 (estimate 32 + 5 min > 36 left; nothing created or installed). Rerun as s1 = TLS 0–19 + lifecycle k 0–1.
- 2026-11-19 11:20 INCIDENT (offline test collided with the live RTL run; no effect on data): an offline check of the new
  rtl_auto.sh (fake rdb + fake phone, results in scratch) started 11:06:55 while galaxy-s1 was live. The harness binds fixed
  host ports (TLS receivers 8798/8799, sink 8787), so the fake runs competed for them: every fake TLS start before 11:12:51
  failed with "Address already in use" (fake TLS never ran); one fake TLS bound at 11:12:51, after the live TLS receivers had
  closed (last live TLS trial 11:12:31, TLS_EXIT 11:12:45); the only fake sink ran 11:07–11:09, before the live sink started
  (11:12:46); fake cleanups only touch processes/listeners of their own scratch paths and serial localhost:1. Live galaxy-s1
  TLS: 140/140 trials, 0 harness errors, barrier_seen 80/80, receiver 300 lines; lifecycle continuing. Fixes: run_rtl.sh
  refuses to start when 8787/8798/8799 already have listeners; rtl_auto.sh stops after 3 runs that add no recorded index
  (the test exposed a loop of 19 TLS-only runs when TLS could not start); offline tests only when no live run is active.
- 2026-11-19 11:20 DONE TEST6 RTL galaxy-s1 (main): TLS blocks 0–19 + lifecycle k 0–1; check_gates ALL PASS (TLS 140/140, barrier_seen 80/80, receiver 300; lifecycle 6/6, remaining 0, seen_max 53–67, kill_verified 2/2, 30/30 DB reads, sink 594). LAUNCH galaxy-p01 = lifecycle k 2 (fits the ~14 min left, END 11:34).
- 2026-11-19 11:21 ABORT galaxy-p01 attempt (B/Claude error, nothing ran on the device): run_rtl.sh was given a relative --out; after its cd into the package the log redirect failed, so campaign.py never started (no install, no trial); the final session.json update raised. Dir renamed galaxy-p01_INVALID_relpath. Fix (new version): --out and --pkg made absolute at start. RTL session ended (~11:34); Galaxy done so far: TLS 0–19, lifecycle k 0–1; remaining lifecycle k 2–19 in later sessions.
- 2026-11-19 11:32 DONE TEST6 Device Farm job 2 → results/round3/test6/pixel8a-j2: PASSED, 41.93 metered min (936.95 → 895.02); lifecycle gates all pass (30/30, remaining 0, seen_max 64–67, kill_verified 10/10, 150/150 DB reads, sink 2970). Device Farm total for Test 6: 104.98 of 1000 trial minutes (0 USD). Chain done 11:32.
- 2026-11-19 12:10 TEST6 TOOLING v3 (after the 19/11 failures; no change to harness, specs, N or validity): run_rtl.sh (absolute --out/--pkg, port guard, rdb_probe.py required, timed adb calls, measured estimates), rtl_auto.sh fill mode (session-sized runs, continuation, replacements only for short schedules via analyze_test6.py, relay ownership, no-progress stop), run_df.sh/run_df_chain.sh wrapped in main(); analyze_test6.py manifest globs (runs.json G = galaxy-* except _INVALID_). Offline tests (fake rdb/phone, no live run): A fill + kill-only replacements to cap 5 → DONE; C link drop → watchdog 61 s → exit 4 → relay restart → continue → revoke-only replacement → DONE; no leftover listeners. Leftover fake-rdb wrapper processes from the tests killed.
- 2026-11-19 12:11 SHUTDOWN (RTL session over): stopped the rdb relay started by B/Claude; no harness process or listener left (8787/8798/8799/8888 free). adb servers 5037 (SDK, mDNS off) and 5038 (r33) left running without devices.
- 2026-11-19 12:14 LAUNCH TEST6 RTL session 2 (user opened a 90-min Galaxy M35 session; end not stated, assumed 13:42): rtl_auto.sh fill mode → results/round3/test6/galaxy-pNN.
- 2026-11-19 13:23 galaxy-p02 done (lifecycle k 2–17, exit 0, probe 0 failures). rtl_auto then judged the link unusable because run_rtl.sh's cleanup had run `adb disconnect`, and restarted the relay (NEED_CLICK). Fix (installed atomically; the running instance keeps its old copy): link_ok re-attaches with adb connect before probing.
- 2026-11-19 13:40 DONE TEST6 RTL session 2 → galaxy-p02 (k 2–17, 48 trials) and galaxy-p03 (k 18–19, 6 trials): gates pass
  (remaining 0, seen_max 51–67, kill_verified 18/18, 270/270 DB reads, sinks 4554 + 594), probe without failures; rtl_auto DONE
  (no replacement needed). Relay stopped. ANALYSIS (followup/analyze_test6.py → results/round3/test6/analysis): both devices TLS
  20/20 valid blocks, lifecycle 20/20 valid paired trials per schedule, 0 invalid, 0 unused. Card §6 filled; B-tracker T6 → data
  done. summary.json not written yet (C to confirm the dev* definitions; candidates in test6-summary.json).
- 2026-11-19 14:00 B0 DONE (record): environment + `make apks` (18/11); emulator smoke covered by the Test 6 rehearsals on
  P04Avd15 (pilot-local-1/2: fixture campaign trials and TLS suite ran end to end, RUNLOG 18/11 22:33–22:47).
- 2026-11-19 14:01 A10 (B part) DONE: `triage/find_callers.py` on acrafence.apk (sha256 fe77d7ec…a061) and matomo.apk
  (ed3b2017…a061… see file) → results/round3/a10/find_callers-20261119.txt. Direct callers of kotlin TextStreamsKt.readBytes
  in both APKs: only kotlin TextStreamsKt.readText(+$default); one more level: readText is called by kotlin Paths/Files
  readText in both, and by org.acra.util.StreamReader.readFully in acrafence; readText$default has no caller. To A for triage.
- 2026-11-19 14:02 NOTE: real-phone-only work listed in artifact/plans/real-phone-pending.md (Test 1 reduced on phone; optional
  Galaxy v3). Everything else of B runs on the emulator/Mac.
- 2026-11-19 14:03 Correction to 14:01: matomo.apk sha256 is ed3b2017…7c87b (full value in the a10 output file).
- 2026-11-19 14:27 B11 PREP: card artifact/plans/b11-card.md (B decisions where the plan is silent: variants menqueue/mlayer/mfence, N=20, key definitions), manifest plans/autorun/b11-final.json (P04Avd14 emulator-5650 sink 8790, then P04Avd15 emulator-5654 sink 8791; schedules pending,kill,reboot,netloss ×20; seed b11-20261119; --timeout 90). Revision APKs copied from the pinned Test 6 package v4 (sha256 verified). preflight 18 ok (warn ~1 GB free RAM; runs sequential). dry-run OK.
- 2026-11-19 14:27 LAUNCH autorun b11-final (final) card artifact/plans/b11-card.md; stages ['avd14', 'avd15']; owned ['emulator-5650', 'emulator-5654']; log artifact/results/round3/b11/autorun-b11-final.log.
- 2026-11-19 14:34 B1 SCREENING (source reading, no build yet): sources at the F-Droid build commits (fdroiddata metadata fetched 19/11) → artifact/plans/b1-screening.md. Proposal for S1: AirGuard (WorkManager SendStatisticsWorker → Retrofit POST donate_data; worker does not re-check share_data; promise PENDING) as the real app; CastBay backup (HttpURLConnection, but NDK build); drop Fedilab (crash reports by email). Test build of AirGuard deferred until B11 finishes (≈1 GB free RAM; a Gradle build could stall the emulator).
- 2026-11-19 14:39 TEST6 NOTE (mechanism, from source; no data change): the TLS suite's app passes a fixed 10 000 ms deadline to TlsTransport.post (fixture Revision.java) and the coordinator's lock waits share it. On Galaxy a 1 MiB send took median 5.9 s over the RDB relay (Pixel 2.5 s), so the two concurrent requests (sharing one policy lock) exceed 10 s → 'TLS deadline' / 'process|policy lock deadline' (39/40). This is the mechanism behind the Galaxy concurrent negative result; report with §7a.
- 2026-11-19 14:43 B10 PREP: card artifact/plans/b10-card.md; new followup/race_suite.py (natural race, W=u·D, paired u, emulator network speed/delay, blocks shuffled), followup/analyze_race.py (validity, violation oracle, Eq. 2 prediction; synthetic test PASS); fixture Revision.java: optional deadline_ms extra (default 10000 unchanged; same line count); TLS APK rebuilt (rl-tls.apk ca313b94…ef15); test cert outside the repo (~/.p04/racecert). Offline dry run with a fake phone OK (paired u, network commands, deadlines). Manifests b10-pilot/b10-final + chain b10-chain.sh (waits for B11, calibration, throttle gate, final).
- 2026-11-19 14:56 B3 PREP: card artifact/plans/b3-card.md (3 conditions prefirst/prefix/control × split on/off, 20 blocks; B decisions); fixture Revision.java: scoped withdrawal, splitsetup, items/split extras, prelock barrier after the TLS handshake, split-once on denial with 0 accepted chunks (all defaults unchanged; adds lines → \impLoc changes again, C regenerates); APK fixture/build/tls-b3-apk (fce0401a…566c; the B10 APK untouched). followup/b3_suite.py + analyze_b3.py (synthetic test PASS; offline dry run with a fake phone OK). Chain b3-chain.sh queued after the B10 chain (pilot 1 block → mechanism gate → final).
- 2026-11-19 15:02 TEST6 PROTOCOL v3 (TLS only, both phones; user: fix concurrent): card artifact/plans/test6-card-v3.md; tls_suite.py --deadline-ms (default trace identical to v2, 26/26 commands with a fake adb); run_rtl.sh --tls-deadline-ms; testspec-v3-tls.yml (TLS 0–19, deadline 60000); package v5 (zip 67080b89…6a2c = v4 + new tls_suite.py + rl-tls.apk ca313b94); frozen-test6-v3/package-sha256.json; runs-v3.json (galaxy3-* prefix keeps v3 out of the v2 glob). v2 data unchanged; both to be reported.
- 2026-11-19 15:03 LAUNCH TEST6 v3 Pixel 8a TLS (Device Farm, package v5, testspec-v3-tls, timeout 40 min) → results/round3/test6/pixel8a-v3-tls.
- 2026-11-19 15:09 LAUNCH TEST6 v3 Galaxy TLS (RTL session opened by the user; relay owned by B/Claude, port 47055): run_rtl.sh package v5, TLS 0–19 with --tls-deadline-ms 60000 → results/round3/test6/galaxy3-tls.
- 2026-11-19 15:15 DONE TEST6 v3 Pixel 8a TLS → results/round3/test6/pixel8a-v3-tls: PASSED, 9.9 trial min (895.02 → 885.13); gates: TLS 140/140, TLS_EXIT=0, barrier_seen 80/80, receiver 300 lines.
- 2026-11-19 15:17 B4 PREP: card artifact/plans/b4-card.md (chunk 1/4/16/64 KiB × 1/2/4/8/16 senders, random order per block, 20 blocks; tenant-2 lock probes; B decisions); transport HttpTransport.postMode overload with chunk and deadline (defaults 4 KiB / 5 s unchanged); fixture Revision.java passes extras; APK tls-b4-apk (1afdfda3…); followup/sweep_suite.py + analyze_sweep.py (synthetic test PASS); chain b4-chain.sh after B3 (pilot 1 block → gate → final). Fake-phone dry run deferred until the live Galaxy v3 run frees port 8799.
- 2026-11-19 15:23 DONE TEST6 v3 Galaxy TLS → results/round3/test6/galaxy3-tls (RTL 15:09–15:22; gates: 140/140, TLS_EXIT=0, barrier_seen 80/80, receiver 300; cleanup 0 packages left; relay stopped). ANALYSIS v3 (runs-v3.json → analysis-v3): both phones 20/20 valid blocks; Galaxy concurrent 40/40 completed (v2 1/40); all other cases equal to v2. Card v3 outcome filled.
- 2026-11-19 15:26 B12 PREP: four mutant builds per artifact/mutation/README.md (I0 on all; base 5770afe4, M1 39348346, M2 88ec3c20, M3 0a0cf753; fixture/src restored with git checkout, nothing committed from the patches); card artifact/plans/b12-card.md; followup/analyze_mutation.py (oracle via analyze_test6.run_oracle = matched_oracle.py unchanged with another directory; label_check flags; independent wrong-label ground truth; mechanics checked on recorded data); manifests + chain b12-chain.sh after B4 (base pilot → I0 gate → 4 mutants × pending,reboot × 20).
- 2026-11-19 15:31 DELIVERY: artifact/results/round3/make_summary.py builds summary.json from analysis outputs only (SCHEMA-filtered); first version has the 5 Test 6 keys (devModel 'Pixel 8a, Galaxy M35', devAndroid '17, 14', devTrials 80, devEarlyComplete 40, devFenceAfterAck 0; definitions test6-card.md §4, v2 runs; identical under v3). render_tests.py accepted it (no unknown keys); its tests_macros.tex output was restored (C regenerates). followup/analyze_b11.py written before looking at B11 data (mechanics checked on pilot-local-2).
- 2026-11-19 15:32 B8 (docs, partial): PLAN.md 'review anonymous' → 'review (not anonymous)' (main.tex has sigconf,review); STATUS.md round-3 note (page count is the 15/11 build's; phone/newer-Android validation now exists: Test 6, Test 4); revision/INTEGRATION.md: TLS transport exists in the fixture, round-3 phone/Android 14–15 runs noted, ACRA/Matomo HTTPS still outside. artifact-revision-audit.md lives in review/ (not committed, R3.5) → not editable in the repo.
- 2026-11-19 15:34 TEST1-PHONE PREP (code only, nothing created in AWS): followup/receiver_b.py (receiver mode B: TLS 8798 / plain 8799 + token control API 8800 for tc link profiles, stall mode, log download; local test with --no-tc OK: plain+TLS 200, bad token 403, log with profile); plans/test6/ec2/{setup.sh (dry unless --create), start.sh, teardown.sh, user-data.sh, README.md}. race_suite.py remote-receiver option deferred until B10 has run (its harness is frozen).
- 2026-11-19 15:35 B11 replacement chain b11-repl-chain.sh queued after B12 (counts valid trials with analyze_b11.py; short schedules → k ≥ 20, cap 5, fresh avd1x-repl dirs; card §3).
- 2026-11-19 16:25 B1 BUILD AirGuard (user added a permission rule for plans/b1/build_airguard.sh and installed JDK 21):
  attempt 1 failed (no Java 21 toolchain on the machine), attempt 2 failed (hiltJavaCompileRelease: "invalid source release: 21",
  Hilt compiles with the Gradle JVM = JDK 17), attempt 3 with Gradle on JDK 21: BUILD SUCCESSFUL → app-release-unsigned.apk
  9.2 MB (sha256 2125bacd…), de.seemoo.at_tracking_detection 3.1.3 (69), minSdk 28, targetSdk 37. S1 proposal: go with AirGuard
  (b1-screening.md). Source clone and build outputs stay outside the repository.
- 2026-11-19 16:43 DONE autorun b11-final: DONE; guard exit 1; SHUTDOWN ['emulator-5650', 'emulator-5654']. Outcomes not inspected by the runner.
2026-11-19 16:44 b10-chain: B11 finished; starting B10 calibration pilot
- 2026-11-19 16:44 LAUNCH autorun b10-pilot (pilot) card artifact/plans/b10-card.md; stages ['calibrate']; owned ['emulator-5660']; log artifact/results/round3/b10/autorun-b10-pilot.log.
- 2026-11-19 16:44 B11 DONE (data): avd14-final 78/80 valid (reboot 18/20: reb004, reb014 = emulator reboot timeouts, environment), avd15-final 80/80. Runner guard exit 1 = the known generated diff manuscript/generated/tests_macros.tex (summary.json now has the Test 6 keys; C regenerates). Queued manifests' GUARD_ALLOW extended with tests_macros.tex (written atomically before the B10 pilot started) so that diff does not stop the chains; replacement for avd14 reboot ×2 comes from b11-repl-chain at the end of the queue.
- 2026-11-19 16:45 DONE autorun b10-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
2026-11-19 16:45 b10-chain: THROTTLE GATE FAIL: emulator link shaping not effective; final not started (protocol v2 needed)
2026-11-19 16:46 b3-chain: B10 chain finished; starting B3 pilot
- 2026-11-19 16:46 LAUNCH autorun b3-pilot (pilot) card artifact/plans/b3-card.md; stages ['pilot']; owned ['emulator-5662']; log artifact/results/round3/b3/autorun-b3-pilot.log.
- 2026-11-19 16:49 DONE autorun b3-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5662']. Outcomes not inspected by the runner.
2026-11-19 16:49 b3-chain: MECHANISM GATE FAIL; final not started
2026-11-19 16:49 b4-chain: previous chains finished; starting B4 pilot
- 2026-11-19 16:49 LAUNCH autorun b4-pilot (pilot) card artifact/plans/b4-card.md; stages ['pilot']; owned ['emulator-5664']; log artifact/results/round3/b4/autorun-b4-pilot.log.
- 2026-11-19 16:51 DONE autorun b4-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5664']. Outcomes not inspected by the runner.
2026-11-19 16:51 b4-chain: gate passed; starting B4 final
2026-11-19 16:51 b4-chain: final autorun exit 3
2026-11-19 16:51 b12-chain: previous chains finished; starting B12 base pilot
- 2026-11-19 16:51 LAUNCH autorun b12-pilot (pilot) card artifact/plans/b12-card.md; stages ['base']; owned ['emulator-5600']; log artifact/results/mutation/autorun-b12-pilot.log.
- 2026-11-19 16:53 DONE autorun b12-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5600']. Outcomes not inspected by the runner.
2026-11-19 16:53 b12-chain: I0 gate passed; starting B12 final (4 mutants)
2026-11-19 16:53 b12-chain: final autorun exit 3
2026-11-19 16:54 b11-repl: replacement plan {"Fourteen": {"avd": "P04Avd14", "serial": "emulator-5650", "port": 8790, "schedules": "reboot", "trials": 2}}
- 2026-11-19 16:54 LAUNCH autorun b11-repl (final) card artifact/plans/b11-card.md; stages ['repl-Fourteen']; owned ['emulator-5650', 'emulator-5654']; log artifact/results/round3/b11/autorun-b11-repl.log.
- 2026-11-19 16:56 DONE autorun b11-repl: DONE; guard exit 0; SHUTDOWN ['emulator-5650', 'emulator-5654']. Outcomes not inspected by the runner.
2026-11-19 16:56 b11-repl: replacement autorun exit 0
- 2026-11-19 17:04 B2 DESIGN: artifact/plans/b2-card.md (draft): AirGuard SendStatisticsWorker fenced through HttpTransport; durable consent log keyed by collection time (no Room schema change); identical debug test hooks in stock and fenced builds; oracle sink-side. Implementation next; emulator slot 26–27/11.
- 2026-11-19 17:20 QUEUE RESULTS + FIXES: B10 pilot-calib (16:44–16:45) THROTTLE GATE FAIL (2 MiB medians edge 0.34 / umts 0.32
  / lte 0.32 s: emulator netspeed not applied over the AVD's Wi-Fi) → protocol v2 `--radio`. B3 pilot-1 (16:46–16:49) mechanism
  worked (split resent diagnostics; prefix denied) but gate failed on a suite bug (prefix+split waited for a SPLIT that cannot
  come) → v2 end predicate. B4 pilot passed its gate, but B4 final and B12 final (pilot I0 gate passed) did not start: preflight
  saw the pilot's emulator port (5664 / 5600) still busy → no final trial ran, no data affected. B11 replacement ran
  (avd14-repl, reboot k 20–21, 16:54–16:56). New plans/autorun/queue2.sh waits for owned ports to be free and runs B4 final,
  B12 final, B3 v2 (pilot-2 → gate → final), B10 v2 (radio calibration → gate → final2).
- 2026-11-19 17:37 LAUNCH autorun b4-final (final) card artifact/plans/b4-card.md; stages ['final']; owned ['emulator-5664']; log artifact/results/round3/b4/autorun-b4-final.log.
- 2026-11-19 17:41 B2 BUILD: artifact/realapp/airguard/apply.sh applied to a separate AirGuard copy (clean F-Droid checkout kept); test APKs via plans/b1/build_airguard.sh (:app:assembleDebug, Gradle on JDK 21): de.seemoo.at_tracking_detection.p04stock (base http://10.0.2.2:8796/, sha256 9822b740…) and .p04fenced (8797, sha256 0067bc1c…), installable side by side; APKs kept outside the repo. followup/airguard_sink.py (ping/get_token/donate_data, per-variant port, body logged) tested locally. Next: campaign driver + pilot when the emulator queue frees (plan slot 26–27/11).
- 2026-11-19 17:52 DONE autorun b4-final: DONE; guard exit 0; SHUTDOWN ['emulator-5664']. Outcomes not inspected by the runner.
2026-11-19 17:52 queue2: b4-final exit 0
- 2026-11-19 17:52 LAUNCH autorun b12-final (final) card artifact/plans/b12-card.md; stages ['base', 'M1-union-latest', 'M2-stale-epoch', 'M3-extras-drop']; owned ['emulator-5600']; log artifact/results/mutation/autorun-b12-final.log.
- 2026-11-19 17:54 B4 v1 final DONE (17:37–17:52): 400 trials, 0 invalid, 20 cells × 20. Timestamp check: fixed-delay probes often outside the send window for few senders → B4 v2 (overlap probes, 4 MiB, analysis counts only probes under load; card §v2). queue3.sh runs b4-final-v2 after queue2. v1 kept and reported.
- 2026-11-19 17:55 STORAGE: results/round3/b4/final/trials.jsonl is 482 MB (all chunk events, GitHub limit 100 MB): kept on disk unchanged, committed as trials.jsonl.gz (27.9 MB, lossless) + trials.jsonl.sha256 of the original (636fdf5f…); git-ignored raw path; analyze_sweep.py reads .gz when the raw file is absent (R3.5: documented fallback).
- 2026-11-19 18:29 B2: analysis script artifact/followup/analyze_airguard.py fixed before any B2 data (sink-side oracle by donated uniqueId batch pre/optout/post; validity from harness fields only); synthetic test PASS. No device run.
- 2026-11-19 18:31 B11 ANALYSIS: analyze_b11.py on avd14-final+avd14-repl / avd15-final → 80/80 analysed per AVD, 2 excluded (reb004, reb014 harness/device). Fix: the exclusion list was taken from the filtered second pass (empty); now from the first pass; keys unchanged (checked). Card §6 filled.
- 2026-11-19 19:33 DONE autorun b12-final: DONE; guard exit 0; SHUTDOWN ['emulator-5600']. Outcomes not inspected by the runner.
2026-11-19 19:33 queue2: b12-final exit 0
- 2026-11-19 19:33 LAUNCH autorun b3-pilot2 (pilot) card artifact/plans/b3-card.md; stages ['pilot']; owned ['emulator-5662']; log artifact/results/round3/b3/autorun-b3-pilot2.log.
- 2026-11-19 19:34 B12 ANALYSIS: analyze_mutation.py → valid base 40, M1 39, M2 39, M3 38 (4 reboot trials harness/device; no replacement rule in card). M2 39/39 leaking, 908 flagged = 908 wrong-label; M1 null (0/0/0); M3 deficit 116 vs base 44. Card Outcome filled.
- 2026-11-19 19:35 DONE autorun b3-pilot2: DONE; guard exit 0; SHUTDOWN ['emulator-5662']. Outcomes not inspected by the runner.
2026-11-19 19:35 queue2: b3-pilot2 exit 0
2026-11-19 19:35 queue2: B3 v2 gate passed
- 2026-11-19 19:35 LAUNCH autorun b3-final (final) card artifact/plans/b3-card.md; stages ['final']; owned ['emulator-5662']; log artifact/results/round3/b3/autorun-b3-final.log.
- 2026-11-19 19:38 DONE autorun b3-final: DONE; guard exit 0; SHUTDOWN ['emulator-5662']. Outcomes not inspected by the runner.
2026-11-19 19:38 queue2: b3-final exit 0
- 2026-11-19 19:38 LAUNCH autorun b10-pilot2 (pilot) card artifact/plans/b10-card.md; stages ['calibrate']; owned ['emulator-5660']; log artifact/results/round3/b10/autorun-b10-pilot2.log.
- 2026-11-19 19:38 B3 v2 final DONE: 120 logged/0 invalid; retained B: control 20/20 both, prefirst 0/20→20/20 with split, prefix 0/20 both; forbidden_after_ack 0 everywhere. Card §6 filled.
- 2026-11-19 19:39 ABORT autorun b10-pilot2: ABORT(calibrate exit 1); guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
2026-11-19 19:39 queue2: b10-pilot2 exit 1
2026-11-19 19:39 queue2: done
- 2026-11-19 19:39 LAUNCH autorun b4-final-v2 (final) card artifact/plans/b4-card.md; stages ['final']; owned ['emulator-5664']; log artifact/results/round3/b4/autorun-b4-final-v2.log.
- 2026-11-19 19:40 B10 v2 pilot2 ABORT diagnosis: race_suite.py died before any trial on the radio metadata line (`dumpsys connectivity | grep -m2` exits 1 when nothing matches → adb() raised). Fix: '; true' on that metadata-only command (atomic replace). Protocol v2 unchanged. Fresh dirs: manifests b10-pilot3 (pilot-calib3) / b10-final3 (final3), queued as queue4.sh after queue3 (B4 v2). pilot-calib2 holds only the emulator log.
- 2026-11-19 20:08 DONE autorun b4-final-v2: DONE; guard exit 0; SHUTDOWN ['emulator-5664']. Outcomes not inspected by the runner.
2026-11-19 20:08 queue3: b4-final-v2 exit 0
- 2026-11-19 20:08 LAUNCH autorun b10-pilot3 (pilot) card artifact/plans/b10-card.md; stages ['calibrate']; owned ['emulator-5660']; log artifact/results/round3/b10/autorun-b10-pilot3.log.
- 2026-11-19 20:10 DONE autorun b10-pilot3: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
2026-11-19 20:10 queue4: b10-pilot3 exit 0
2026-11-19 20:10 queue4: B10 v2 THROTTLE GATE FAIL (radio path); final not started — host shaper needed (sudo)
2026-11-19 20:10 queue4: done
- 2026-11-19 20:10 B4 v2 final DONE (19:39–20:06): 400 logged, 4 invalid (sender Broken pipe after ~31–35 s: 3× 4 KiB/16, 1× 64 KiB/8; no replacement rule → 17 and 19 valid in those cells). Raw 1.94 GB kept on disk; gzip 110 MB > GitHub limit → committed as byte parts part-aa/ab (cat = original gzip, sha256 a5f995f2…); analyze_sweep.py reads parts, output byte-identical. summary.json rebuilt (23 keys; sweep* from analysis-v2). Card Outcome filled.
- 2026-11-19 20:13 B10 v2 pilot-calib3: throttle gate FAIL again (2 MiB medians edge 0.27 / umts 0.31 / lte 0.32 s; routes: eth0 only, console preset not shaping). Feasibility check on P04AvdA emulator-5660 (started and killed by B, no trial data): guest tc tbf/netem accepted on eth0. Protocol v3 (b10-card): race_suite.py --shaper tc = guest netem egress at the emulator's nominal uplink rates + delay midpoints; manifests b10-pilot4/final4, queue5.sh (pilot → same gate → final). Gate fail again → B10 stops.
- 2026-11-19 20:13 LAUNCH autorun b10-pilot4 (pilot) card artifact/plans/b10-card.md; stages ['calibrate']; owned ['emulator-5660']; log artifact/results/round3/b10/autorun-b10-pilot4.log.
- 2026-11-19 20:31 ABORT autorun b10-pilot4: ABORT(calibrate exit 1); guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
2026-11-19 20:31 queue5: b10-pilot4 exit 1
2026-11-19 20:31 queue5: done
- 2026-11-19 20:31 B10 v3 pilot-calib4: calibration complete (calibration.json written; 2 MiB medians edge 151.2 / umts 137.4 / lte 0.32 s) → throttle gate PASS (same mechanical rule). The stage then exited 1 on the end-of-run cleanup net('full') (KeyError: no TC entry) → autorun ABORT after the data were written; fix: a profile without a TC entry removes the qdiscs. lte at 58 Mbit/s equals the unshaped link (0.32 s) — reported as is. Launching b10-final4 (durations from pilot-calib4).
- 2026-11-19 20:31 LAUNCH autorun b10-final4 (final) card artifact/plans/b10-card.md; stages ['final']; owned ['emulator-5660']; log artifact/results/round3/b10/autorun-b10-final4.log.
- 2026-11-19 21:16 CORRECTION to the 17:41 B2 BUILD line: the two sha256 were swapped in that note. Verified from the APKs (aapt2 package name + base URL in dex): airguard-stock.apk = .p04stock, :8796, sha256 0067bc1c…; airguard-fenced.apk = .p04fenced, :8797, sha256 9822b740…. Copies kept in artifact/realapp/airguard/build/ (git-ignored) with SHA256SUMS; the campaign records the installed hashes in meta.json.
- 2026-11-19 21:17 B2: pilot manifest b2-pilot (P04AvdA emulator-5666, sinks 8796/8797, 1 trial × pending,kill,reboot,netloss, APKs artifact/realapp/airguard/build) queued as queue6.sh after B10 final4. Final not queued: N/seed/timeouts frozen in b2-card.md after reviewing the pilot.
- 2026-11-19 22:01 DONE autorun b10-final4: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-19 22:02 LAUNCH autorun b2-pilot (pilot) card artifact/plans/b2-card.md; stages ['pilot']; owned ['emulator-5666']; log artifact/results/round3/b2/autorun-b2-pilot.log.
- 2026-11-19 22:02 B10 v3 final4 DONE (20:33–21:59, guard 0): 180 logged, 0 invalid; early violating 21/30 edge, 20/30 umts, 10/30 lte; fence 0/30 each; Eq.2 pred 79.4% vs obs 56.7%. Raw trials.jsonl 119 MB kept on disk, committed .gz (4.9 MB) + sha256; analyze_race.py reads .gz (output byte-identical). summary.json rebuilt: 32 keys (race* added). Card §6 filled.
- 2026-11-19 22:17 DONE autorun b2-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
2026-11-19 22:17 queue6: b2-pilot exit 0
- 2026-11-19 22:25 B2 pilot-1 review (mechanism only): pen000 trial_error = first hook after install timed out (cold start); other 3 trials: hooks/consent events OK in both builds but no WORKER_SEND and 0 sink requests — cause: app network_security_config denies cleartext for all hosts (overrides usesCleartextTraffic). Fixes: apply.sh nsc (cleartext for 10.0.2.2 only, both builds), rebuilt APKs stock e53e5254… / fenced 30eb823f… (old builds kept in build/v1-20261119-1740), driver warm-up no-op hook (300 s) recorded in meta. Launching b2-pilot2 (fresh dir pilot-2).
- 2026-11-19 22:25 LAUNCH autorun b2-pilot2 (pilot) card artifact/plans/b2-card.md; stages ['pilot']; owned ['emulator-5666']; log artifact/results/round3/b2/autorun-b2-pilot2.log.
- 2026-11-19 22:36 DONE autorun b2-pilot2: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-19 22:39 B2 pilot-2 review (mechanism only): sink reached (36 requests), warm-up ok; AirGuard runs its worker at consent time (pre beacons can be donated legitimately before the withdrawal) → oracle v2 with a host-clock withdrawal bracket (before / after / ambiguous=unknown), synthetic test PASS; driver quiescence now counts only donation events after the harness run. Netloss: app does not retry a failed run (kept, reported). B2 protocol v1 FROZEN in b2-card.md (N=20 per schedule, seed b2-20261119). queue7.sh: pilot-3 → mechanical gate → b2-final.
- 2026-11-19 22:39 LAUNCH autorun b2-pilot3 (pilot) card artifact/plans/b2-card.md; stages ['pilot']; owned ['emulator-5666']; log artifact/results/round3/b2/autorun-b2-pilot3.log.
- 2026-11-19 22:45 B7 prep: results/round3/PROTOCOL.md (protocol index per task: card, version used for keys, final dirs, analysis, keys; fixture changes since snapshot-20261117) and results/round3/EXCLUSIONS.md generated by make_exclusions.py (trial-level exclusions from analysis outputs + every pilot/_INVALID_ dir with its recorded reason). B2 rows appear after the B2 final; regenerate at freeze.
- 2026-11-19 22:48 B8 draft: manuscript §6 gets one sentence pointing to a new appendix section "Round-3 Implementation and Harness" (split policy, AirGuard embedding, phone/throttled harnesses; no numbers); - 2026-11-19 22:49 DONE autorun b2-pilot3: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
2026-11-19 22:49 queue7: b2-pilot3 exit 0
2026-11-19 22:49 queue7: B2 gate passed
- 2026-11-19 22:49 LAUNCH autorun b2-final (final) card artifact/plans/b2-card.md; stages ['final']; owned ['emulator-5666']; log artifact/results/round3/b2/autorun-b2-final.log.
- 2026-11-19 22:50 Test 1 on phones (real-phone-pending #1) prep: race_suite.py remote-receiver mode (--receiver/--token/--host/--no-root; shaping and log via receiver_b.py control API; token never stored; defaults unchanged, B10 data unaffected). Control API checked locally (receiver_b --no-tc on 127.0.0.1: profile edge/full, log fetch, bad token 403; stopped). Waiting for user: EC2 go-ahead + RTL session.
- 2026-11-19 23:11 User decision: Test 1 on phones deferred (before 28/11); no EC2 created.
- 2026-11-19 23:53 DONE autorun b2-final: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
2026-11-19 23:53 queue7: b2-final exit 0
2026-11-19 23:53 queue7: done
- 2026-11-19 23:54 B2 final DONE (22:50–23:53, guard 0): 80/80 valid; stock violating 20/20 in pending/kill/reboot (optout beacons after re-consent; +2 pre/after in pending), fenced 0/20 everywhere (blocked 20/20, post delivered, deficit 0); netloss: no donation after link restore in both (deficit 80 beacons each); fenced unknown 8/9/9 of 20 (pre beacons in ambiguous requests). Card Outcome filled; EXCLUSIONS.md regenerated; summary.json unchanged (B2 has no SCHEMA keys).
- 2026-11-19 23:56 B9 self-check (not the outside-person run the plan asks for): git archive HEAD → scratch, make -C artifact all. Attempt 1 failed: Makefile ran ../manuscript/build.sh, which is mode 100644 in git (also on origin/main) → Permission denied. Fix: Makefile calls 'bash ../manuscript/build.sh' (and 'bash' for fixture/acra build.sh in 'apks'). Attempt 2: exit 0, 21 pages, 0 overfull, 0 undefined; every tracked file under artifact/results byte-identical; manuscript/generated differs only in \impLoc 1,230→1,250 (fixture extras added since snapshot) and tests_macros.tex (32 macros now filled from summary.json) — both regenerated by C. Log: results/round3/b9/make-all-selfcheck-20261120.log.
2026-11-20 20:52 B4 v3 LAUNCH queue8 (pilot-v3 → gate → final-v3 → repl if a cell < 20 valid); emulator-5664 P04AvdA, receiver 8799; card b4-card.md Protocol v3; user go-ahead 20/11 ("optimize nó")
- 2026-11-20 20:52 LAUNCH autorun b4-pilot-v3 (pilot) card artifact/plans/b4-card.md; stages ['pilot']; owned ['emulator-5664']; log artifact/results/round3/b4/autorun-b4-pilot-v3.log.
- 2026-11-20 21:05 Analysis only (no device), user request "optimize" implementation-caused gaps: (1) B10 post-hoc Eq. 2 decomposition, defined in b10-card.md before computing (commit 35465b2): P0 79.4 (= key) → P1 65.7 (window from the layered check, not SOCKET_CONFIG) → P2 57.7 (+ withdrawal delivery shift δ̄ from fence trials, ~0.1 s) vs observed 56.7; keys unchanged; `b10/posthoc-eq2`. (2) B2 oracle v3 (post-hoc, guest-clock order via X-Request-ID; b2-card.md "Oracle v3"; unit test 9/9; default output byte-identical to `b2/analysis`): fenced unknown 8/9/9 → 0 (all 'pre/before'), violations unchanged; `b2/analysis-v3`. (3) B12 M1 diagnosis: in 39/39 re-grants no AGG after REGRANT (fixture aggregates only at SETUP, Cmd.java:35), so the M1 trigger is unreachable; proposal to A (optional fixture extra regrant_agg), nothing built or run.
- 2026-11-20 20:57 DONE autorun b4-pilot-v3: DONE; guard exit 0; SHUTDOWN ['emulator-5664']. Outcomes not inspected by the runner.
2026-11-20 20:57 queue8: b4-pilot-v3 exit 0
2026-11-20 20:57 queue8: B4 v3 gate passed
- 2026-11-20 20:57 LAUNCH autorun b4-final-v3 (final) card artifact/plans/b4-card.md; stages ['final']; owned ['emulator-5664']; log artifact/results/round3/b4/autorun-b4-final-v3.log.
- 2026-11-20 21:03 User decisions: Test 1 on phones (real-phone-pending #1) and Galaxy v3 via EC2 (#2) not run ("test 1 trôi"); no EC2 created. B12 M1 rerun waits for A's approval. B7 freeze to run now ("B7 chạy đi"), after the B4 v3 final completes.
- 2026-11-20 21:05 User decision B7: prepare and commit everything (EXCLUSIONS, summary.json, PROTOCOL, raw) after the B4 v3 final; declare the freeze when A answers on the M1 rerun (no → freeze at once; yes → run M1 first) or on 29/11 at the latest.
- 2026-11-20 21:08 User decision reversed: Test 1 on phones (real-phone-pending #1) is kept and runs on 21/11 (EC2 confirmed by the user at creation; RTL Galaxy session). B7 freeze now waits for #1 and for A's M1 answer (29/11 at the latest).
- 2026-11-20 21:28 DONE autorun b4-final-v3: DONE; guard exit 1; SHUTDOWN ['emulator-5664']. Outcomes not inspected by the runner.
2026-11-20 21:28 queue8: b4-final-v3 exit 1
- 2026-11-20 21:35 B4 v3 final complete (20:57–21:28): 400 logged, 1 invalid (sw-c4-s16-3-fd82de, "sender did not complete": one of 16 senders ended `IOException: policy lock deadline` after 120.0 s = the app's deadline_ms; diagnosis read only the failed sender's end event). Cell 4KiB/16 has 19 valid → card v3 replacement rule applies (2 whole blocks, --start 20, regardless of outcome). Queue8 stopped before that check because the autorun guard failed: false positive — after PR #1 was merged the merge-base moved, so B's maintained files under results/round3 (PROTOCOL.md, make_exclusions.py, .gitignore) counted as "recorded evidence modified". Fix: guard.sh exempts B's round-3 deliverables (PROTOCOL, EXCLUSIONS, summary.json, make_summary.py, make_exclusions.py, .gitignore); raw data stay protected. Guard rerun: GUARD OK (incl. byte-identical regeneration). Observation for the card: with the 30 s receiver cut removed, a sender can wait up to the 120 s app deadline for the policy lock at 16 senders × 4 KiB (v2's ~31–35 s failures were the receiver cut).
- 2026-11-20 21:30 LAUNCH autorun b4-repl-v3 (final) card artifact/plans/b4-card.md; stages ['final']; owned ['emulator-5664']; log artifact/results/round3/b4/autorun-b4-repl-v3.log.
- 2026-11-20 21:32 Stopped the project's stale RTL adb server (r33, port 5038, started 19/11 09:52 by run_rtl/rtl_auto) that had claimed the user's phone over USB; default adb server (5037, used by B4) untouched.
- 2026-11-20 21:35 DONE autorun b4-repl-v3: DONE; guard exit 0; SHUTDOWN ['emulator-5664']. Outcomes not inspected by the runner.
2026-11-20 21:35 b4-repl-v3 exit 0
- 2026-11-20 21:38 B4 v3 DONE: final-v3 + 2 replacement blocks → every cell 20 valid (440 logged, 1 invalid, 39 unused); sweep* keys now from analysis-v3-repl (only these 4 keys changed in summary.json); EXCLUSIONS regenerated; guard OK. Card 'Outcome v3'.
- 2026-11-20 21:42 B12 v2 LAUNCH b12v2-chain (pilot-base → gate incl. AGG after REGRANT → base/M1/M2/M3 × pending,reboot × 20, --regrant-agg); emulator-5600 P04AvdA, sink 8795; A approved in PR #2 (A1); card b12-card.md Protocol v2.
- 2026-11-20 21:42 LAUNCH autorun b12v2-pilot (pilot) card artifact/plans/b12-card.md; stages ['base']; owned ['emulator-5600']; log artifact/results/mutation-v2/autorun-b12v2-pilot.log.
- 2026-11-20 21:44 DONE autorun b12v2-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5600']. Outcomes not inspected by the runner.
2026-11-20 21:44 b12v2-chain: B12 v2 gate passed; starting final (4 builds, --regrant-agg)
2026-11-20 21:44 b12v2-chain: final autorun exit 3
- 2026-11-20 21:44 B12 v2 final not started at 21:44: autorun pre-check failed (preflight 'port 5600 in use' right after the pilot emulator shut down; environment, no final trial ran). Relaunching b12v2-final after the ports are free (chain lacked the port wait the queues have).
- 2026-11-20 21:44 LAUNCH autorun b12v2-final (final) card artifact/plans/b12-card.md; stages ['base', 'M1-union-latest', 'M2-stale-epoch', 'M3-extras-drop']; owned ['emulator-5600']; log artifact/results/mutation-v2/autorun-b12v2-final.log.
- 2026-11-20 23:29 DONE autorun b12v2-final: DONE; guard exit 0; SHUTDOWN ['emulator-5600']. Outcomes not inspected by the runner.
2026-11-20 23:29 b12v2-final exit 0
- 2026-11-20 23:31 B12 v2 DONE: M1 24/40 leaking (24 flagged = 24 wrong-label), M2 39/39, M3 0/40, base 0/39; mut* keys now from mutation-v2/analysis (7 keys changed); EXCLUSIONS regenerated; guard OK. Card 'Outcome v2'.
- 2026-11-20 23:38 Test 1 on phone: EC2 created with the user's go-ahead ("ok ec2"): t3.micro ap-southeast-1, instance i-0c0bdf67836f90494, receiver IP 13.212.160.250 (delete with teardown.sh). Phone: Samsung Galaxy A06 5G (SM-A066B), Android 15, Wi-Fi; preflight OK; power saving found ON → user asked to turn it off before the pilot.
- 2026-11-20 23:43 Test 1 phone: receiver_b (b10v3) deployed on EC2; two fixes before any trial (ifb0 not created by modprobe on AL2023; an ingress line I had commented out by mistake); all three profiles verified (netem on ifb0 + ingress mirred filter); control API rejects a wrong token (403).
- 2026-11-20 23:44 test1-phone: LAUNCH pilot results/round3/test1-phone/pilot-calib-1 (own phone, receiver EC2 b10v3)
- 2026-11-20 23:46 Test 1 phone pilot-calib-1 stopped by B after 3 sends (all SEND_ERROR connect abort at 5 s; path OK from phone shell and Mac). Cause: never-launched app (standby bucket 50) gets no network from a broadcast; manual check after set-standby-bucket active + one launch → SEND_OK. Fix: race_suite wakes the app on phones (as campaign.py). Next: pilot-calib-2.
- 2026-11-20 23:46 test1-phone: LAUNCH pilot results/round3/test1-phone/pilot-calib-2 (own phone, receiver EC2 b10v3)
- 2026-11-20 23:49 test1-phone: pilot results/round3/test1-phone/pilot-calib-2 exit 0
- 2026-11-20 23:49 test1-phone: pilot gate: {"gate":false,"medians_2mib":[null,null,null],"block_upper_min":1.9244615157445273,"blocks":10}
- 2026-11-20 23:50 Test 1 phone pilot-calib-2: throttle gate FAIL — 256 KiB/2 MiB sends cut 4.3–4.9 s in (connection abort) on every profile; cause: Android 15 freezes the cached broadcast process (manual check with Main foreground: 2 MiB lte SEND_OK 9.6 s). Fix: race_suite launches Main before each send on phones. Card §3 allows one more pilot: pilot-calib-3.
- 2026-11-20 23:50 test1-phone: LAUNCH pilot results/round3/test1-phone/pilot-calib-3 (own phone, receiver EC2 b10v3)
- 2026-11-21 00:08 test1-phone: pilot results/round3/test1-phone/pilot-calib-3 exit 0
- 2026-11-21 00:08 test1-phone: pilot gate: {"gate":true,"medians_2mib":[151.19129447,139.263035316,9.405375309],"block_upper_min":12.117157117525737,"blocks":10}
- 2026-11-21 00:09 Test 1 phone pilot-calib-3: 27/27 SEND_OK; 2 MiB medians edge 151.2 s, umts 139.3 s, lte 9.41 s → gate PASS; N rule → 10 blocks (card). Launching final next.
- 2026-11-21 00:09 test1-phone: LAUNCH final results/round3/test1-phone/final (10 blocks, durations results/round3/test1-phone/pilot-calib-3/calibration.json, frozen results/round3/test1-phone/frozen-test1-phone)
- 2026-11-21 01:46 test1-phone: final exit 0
- 2026-11-21 01:46 test1-phone: analysis written to results/round3/test1-phone/analysis
- 2026-11-21 01:48 Test 1 phone close-out: final complete (00:09–01:46, 180 logged, 0 invalid, 30 per (profile, variant)); test app uninstalled and CA file removed from the phone (0 org.residuelab packages for user 0); EC2 i-0c0bdf67836f90494 terminated, security group and key pair deleted; 0 instances, 0 addresses, 0 volumes left in ap-southeast-1.
- 2026-11-21 01:49 Test 1 phone DONE: fence 0/30 in every profile; early edge 16, umts 19, lte 19 of 30; Eq. 2 68.2 vs 60.0 (post-hoc P2 52.4, does not transfer from B10); card §6, EXCLUSIONS, PROTOCOL, tracker. No SCHEMA keys (asked C in PR #2, C3); summary.json unchanged.
- 2026-11-21 01:50 B7 DATA FREEZE declared (user decision 20/11: freeze once A answered and Test 1 on the phone ran; both done). No device/emulator run after this point. make_summary.py and make_exclusions.py rerun (no change); guard OK. Later: only script-computed summary.json keys from frozen data (C1 dev*, C3 phone keys), each with a RUNLOG entry.
- 2026-11-21 (post-freeze, analysis only, no device) Exploratory diagnosis of three unexplained items on frozen data; new scripts followup/deficit_causes_runs.py (selftest = deficit_causes.py causes) and followup/m1_trigger.py; outputs in new dirs results/mutation{,-v2}/analysis-deficit, results/mutation-v2/analysis-m1, results/round3/test6/analysis-deficit. (1) Test 6 Galaxy deficit: = Pixel's (mstart T5) + two trials G-p02 pen009/rev017 where quiescence was declared before any job ran (harness observation failure); sensitivity menqueue 19/20 → 19/19, fence 0/20 → 0/19. (2) B12 base deficit 44/80: all stopped_no_restart in reboot trials (fixture property), not oracle. (3) B12 M1: leak 24/24 when the re-derived summary reached the sink, 0/16 when not (reboot); trigger misses. No key, rule or summary.json change. Cards b12 and test6 updated.
- 2026-11-21 (post-freeze, no device) C answered C1–C6 in PR #2. make_summary.py: extra_keys() computes the 28 keys C requested (devLife*, racePhone*, mut*Trials, mutBaseDeficit, air*, split*) from frozen analysis outputs; names not yet in SCHEMA go to results/round3/summary-pending.json (summary.json unchanged at 32 keys until C adds the names to render_tests.py SCHEMA and make_summary.py is rerun). New plans/test1-phone/device.json (model label only). Static send-path audit of the B2 AirGuard APKs (C's optional item): followup/mediation_check_apk.py → results/round3/b2/mediation; donation path mediated in the fenced build at direct-call level; 23 other network sites per build unmediated (b2-card).
- 2026-11-21 B HANDOFF: all B runs done (data frozen 21/11), final report plans/B-report.md, every key C requested computed (summary.json 32 + summary-pending.json 28, pending C's SCHEMA change); B8 reviewed by C; open for B: B9 outside person by 2/12. PR #2 handed to C for SCHEMA, renderer and merge.
- 2026-11-21 C exported the requested keys via derived() in make_summary.py on c-final (eba8ba0). B checked: all 60 keys B computed are identical in C's summary.json (67 keys; C's 7 extra match the cards). B withdrew its extra_keys()/summary-pending.json (and the guard DELIV entry, and plans/test1-phone/device.json) from b-exp so PR #2 and c-final merge without conflict; summary.json on b-exp unchanged.
- 2026-11-21 23:2x GROUP 2 accepted (user: "nhận luôn, leader đã quyết, chạy 2 thí nghiệm mới"; PR #4 "Group 2 needs new runs by B"). B7 freeze reopened for G2a and G2b only; frozen round-3 data untouched; new dirs results/round3/g2close, g2layer. Cards plans/g2close-card.md, g2layer-card.md written before any trial (all design choices are B decisions; plan gives none).
- 2026-11-21 23:2x G2 BUILD: (a) TLS fixture with the close comparator: TlsTransport.post overload with onOpen (old signature unchanged), fixture/src-cmp/CancelPath.java (token registered before the early check; withdrawal → durable commit → synchronous ordered broadcast closes in-flight sockets → ack; 5 s timeout logged), Revision.java call sites appended to existing lines (impLoc 1,251 unchanged), build.sh compiles src-cmp; APK fixture/build/g2close-apk/rl-tls.apk a11de8ba…; transport unit test PASS. (b) AirGuard layered: apply.sh third variant (additive), FencedDonation.kt layered branch (one ConsentLog check under the lock, then HttpTransport fenced=false), built from a fresh copy of the clean F-Droid checkout → realapp/airguard/build/airguard-layered.apk f450a506…; static check: doWork → FencedDonation.send. Driver/analysis changes: race_suite --apk + cancel flag for close; campaign_airguard --variants (default unchanged); sink port 8795; analyze_airguard reads variants (B2 analysis and analysis-v3 reproduce byte for byte); new followup/analyze_g2close.py (code-checked on B10 final4: early 21/20/10, cut 51/53, receiver complete 51/0 = C's receiver_race). Freeze results/round3/g2close/frozen-g2 (40 files incl. APK hashes).
- 2026-11-21 22:59 g2-chain: start (G2a then G2b)
- 2026-11-21 22:59 LAUNCH autorun g2close-pilot (pilot) card artifact/plans/g2close-card.md; stages ['calibration']; owned ['emulator-5660']; log artifact/results/round3/g2close/autorun-g2close-pilot.log.
- 2026-11-21 23:04 ABORT autorun g2close-pilot: ABORT(calibration exit 1); guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-21 23:04 g2-chain: G2a calibration pilot failed; chain stopped
- 2026-11-21 23:04 G2a pilot-calib ABORT before any send: setup `init` broadcast timed out (60 s). Diagnostic boot of P04AvdA on 5660 (23:05–23:07, stopped after): init ok, cold start 83 s; host load 10–12 from other user applications (not touched). Fix: race_suite setup init timeout 300 s + setup_init_s in meta (harness only; B2 pilot-1 precedent). New freeze results/round3/g2close/frozen-g2-v2; calibration rerun as pilot-calib2. pilot-calib kept (excluded).
- 2026-11-21 23:23 g2-chain relaunch after pilot-calib fix; user closed the games; host load 1-min 3.87
- 2026-11-21 23:23 g2-chain: start (G2a then G2b)
- 2026-11-21 23:23 LAUNCH autorun g2close-pilot (pilot) card artifact/plans/g2close-card.md; stages ['calibration']; owned ['emulator-5660']; log artifact/results/round3/g2close/autorun-g2close-pilot.log.
- 2026-11-21 23:42 DONE autorun g2close-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-21 23:42 g2-chain: G2a throttle gate passed; mechanism pilot next
- 2026-11-21 23:42 LAUNCH autorun g2close-mech (pilot) card artifact/plans/g2close-card.md; stages ['mechanism']; owned ['emulator-5660']; log artifact/results/round3/g2close/autorun-g2close-mech.log.
- 2026-11-21 23:53 DONE autorun g2close-mech: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-21 23:53 g2-chain: G2a mechanism gate passed; starting G2a final
- 2026-11-21 23:53 LAUNCH autorun g2close-final (final) card artifact/plans/g2close-card.md; stages ['final']; owned ['emulator-5660']; log artifact/results/round3/g2close/autorun-g2close-final.log.
- 2026-11-22 01:50 DONE autorun g2close-final: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-22 01:50 g2-chain: G2a final autorun exit 0
- 2026-11-22 01:50 LAUNCH autorun g2layer-pilot (pilot) card artifact/plans/g2layer-card.md; stages ['pilot']; owned ['emulator-5666']; log artifact/results/round3/g2layer/autorun-g2layer-pilot.log.
- 2026-11-22 01:54 DONE autorun g2layer-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-22 01:54 g2-chain: G2b pilot gate passed; starting G2b final
- 2026-11-22 01:55 LAUNCH autorun g2layer-final (final) card artifact/plans/g2layer-card.md; stages ['final']; owned ['emulator-5666']; log artifact/results/round3/g2layer/autorun-g2layer-final.log.
- 2026-11-22 03:00 DONE autorun g2layer-final: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-22 03:00 g2-chain: G2b final autorun exit 0
- 2026-11-22 03:00 g2-chain: done
- 2026-11-22 03:0x G2a DONE (final 21/11 23:53 – 22/11 01:50, 270 logged, 0 invalid, 30 per (profile, mode)): violating trials early 20/21/9 of 30 (edge/umts/lte), close 0/30, fence 0/30; receiver complete among cut trials early 50/50, close 0/48, fence 0/52; close ack latency median 2.5–3.5 ms vs fence ~0.9 ms; 90/90 cancel replies ok. Exploratory (posthoc_g2close.py): close ended SEND_ERROR on 18 uncut requests the receiver had logged complete; fence 0. Raw trials.jsonl (176 MB) committed as .gz + sha256 (pilots too); analysis from the gzip byte-identical.
- 2026-11-22 03:0x G2b DONE (final 01:55–03:00, 80 logged, 0 invalid): stock 20/20 violating in pending/kill/reboot, fenced 0/20, layered 0/20; netloss 0 for all (deficit 80/80 beacons each); unknown 0 (v2 and v3). Stop points: layered 60 at the early check, fenced 60 in the transport (posthoc_g2layer.py). Close-out: no emulator, sink or caffeinate left (adb devices empty); EXCLUSIONS regenerated (G2 rows, 0 without reason); summary.json unchanged (no SCHEMA keys for G2). B7 data freeze RE-DECLARED: no device or emulator run after this point.
- 2026-11-22 13:55 G3 BUILD (issue #7; no device used): (a) fixture: src-cmp G3.java (SOCKET_LOCAL after the handshake, close2 handed-off marking, fence-abort SO_LINGER 0 at BLOCK, marker connection after WITHDRAW_ACK, platform client HttpsURLConnection) and CancelPath close2 methods; Revision.java call sites appended to existing lines (101 lines, impLoc unchanged; guard OK); build fixture/build/g3-apk/rl-tls.apk 8f723ead…. (b) race_suite.py --g3/--marker/--capture (close2 withdrawal to Revision in the sending process with cancel2; prio root with the marker port unshaped; emulator console capture); defaults unchanged. (c) AirGuard G3 builds: realapp/airguard/apply_g3.sh + src-g3/G3.kt (stock donation end events, stockcancel OkHttp in-flight registry + Call.cancel() on switch-off, WITHDRAW_DONE + marker, hook op mark) on top of apply.sh (unchanged); build_g3.sh from a fresh copy of the clean checkout d515c534 → realapp/airguard/build/g3/airguard-{stock,stockcancel,fenced,layered}.apk (sink ports 8796/8793/8797/8795; airguard_sink.py adds 8793). First build replaced before any trial: the start marker moved from guest `toybox nc` (unverified on the image) into the app hook. (d) drivers race_airguard.py (G3c), cost_suite.py (G3d; --serial auto, the phone serial never written); analyses analyze_g3race.py (checked on G2a final: after-W close 10/90, fence 0/90, early 50/90 = C's counts), analyze_g3app.py, analyze_g3cost.py, pcapmin.py, pcap_slim.py; unit tests test_g3race/test_g3app/test_g3cost OK (one capture bug found and fixed by them: reused marker ports). Device-free harness checks with a fake adb (scratch, not committed): all three drivers end to end, every chain gate passes on well-formed fake data and fails on malformed data. Test certificate for the phone receiver: ~/.p04/g3dcert (SAN 192.168.1.20; key not committed).
- 2026-11-22 14:16 g3-launch(emu): scheduled start of plans/autorun/g3-chain.sh (user go-ahead 22/11, started early on request)
- 2026-11-22 14:16 g3-chain: start (G3a/G3b then G3c)
- 2026-11-22 14:16 LAUNCH autorun g3race-pilot (pilot) card artifact/plans/g3race-card.md; stages ['pilot']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3race-pilot.log.
- 2026-11-22 14:29 g3-launch(phone): stopped while waiting for a phone (nothing ran on a phone); user 22/11: emulator tests first, G3d later on request
- 2026-11-22 14:35 DONE autorun g3race-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-22 14:35 g3-chain: G3a throttle gate passed; mechanism pilot next
- 2026-11-22 14:35 LAUNCH autorun g3race-mech (pilot) card artifact/plans/g3race-card.md; stages ['mech']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3race-mech.log.
- 2026-11-22 14:51 DONE autorun g3race-mech: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-22 14:51 g3-chain: G3a/G3b MECHANISM GATE FAIL; no final (card §3)
- 2026-11-22 14:52 G3a/G3b pilot-mech MECHANISM GATE FAIL (capture only): the console `network capture start <path>` replied "KO: <file> must be a bare filename (written under the AVD content directory)", so no pcap. Other gate fields held (45/45 MARKER_SENT and SOCKET_LOCAL, 45 marker lines, u32 filter listed, marker band pfifo 10 sent > 0). Diagnostic boot of P04AvdA on 5660 (14:52–14:54, no trial, emulator stopped after, the two test pcaps under the AVD's console_out removed): `-tcpdump <absolute path>` at launch writes guest frames (10.0.2.15, Ethernet); the console capture with a bare name wrote only a header. Protocol v2 (capture method only; design, arms, N and analysis unchanged): race_suite.py and race_airguard.py pass -tcpdump at emulator launch; calibration pilot-calib + throttle gate reused; new mechanism pilot pilot-mech2; freeze results/round3/g3/frozen-g3-v2; chain plans/autorun/g3-chain-v2.sh. pilot-mech is retained and excluded.
- 2026-11-22 14:55 g3-chain: start v2 (G3a/G3b mechanism pilot 2, then final, then G3c)
- 2026-11-22 14:55 g3-chain: v2 (capture via -tcpdump at launch): calibration pilot-calib and its throttle gate (passed 14:35) reused
- 2026-11-22 14:55 LAUNCH autorun g3race-mech2 (pilot) card artifact/plans/g3race-card.md; stages ['mech']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3race-mech2.log.
- 2026-11-22 15:11 DONE autorun g3race-mech2: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-22 15:11 g3-chain: G3a/G3b mechanism gate passed; starting final
- 2026-11-22 15:11 LAUNCH autorun g3race-final (final) card artifact/plans/g3race-card.md; stages ['final']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3race-final.log.
- 2026-11-22 15:52 ABORT autorun g3race-final: ABORT(final exit -15); guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-22 15:52 G3a/G3b final PAUSED on user request ("tạm ngưng"): chain g3-chain-v2.sh stopped first (G3c not started), then race_suite (SIGTERM) → autorun ABORT(final exit -15), guard 0, emulator-5660 shut down; no emulator, harness, listener or caffeinate left. Logged so far: blocks 0 and 1 complete (45 + 45 trials), block 2 partial (10 of 45). Outcomes not inspected. Resume rule fixed now, before any outcome is read (card Pilot log): resume in a fresh directory `final-r2` with `--start 2 --trials 8` (blocks 2–9, same seed, so the same cell order and u per block); analysis uses only blocks complete within one directory (final: 0–1; final-r2: 2–9); the partial block 2 in `final` is retained and excluded (reason: interrupted by the user's pause, operational).
- 2026-11-22 16:35 G3 resume prepared (user: "tiếp tục, không cắm sạc"): analyze_g3race.py accepts several directories and uses only blocks complete within one directory (checked: G2a cells identical; synthetic interrupted block excluded); manifest g3race-final-r2 (--start 2 --trials 8 → final-r2); chain plans/autorun/g3-chain-v3.sh (final-r2, then G3c as v2); battery guard plans/autorun/battery_guard.sh (stops at 15 % discharging; power state only); freeze results/round3/g3/frozen-g3-v3. Host on battery (100 % at start).
- 2026-11-22 16:35 g3-chain: start v3 (resume after the pause: G3a/G3b final-r2 blocks 2-9, then G3c)
- 2026-11-22 16:35 LAUNCH autorun g3race-final-r2 (final) card artifact/plans/g3race-card.md; stages ['final']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3race-final-r2.log.
- 2026-11-22 18:58 DONE autorun g3race-final-r2: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-22 18:58 g3-chain: G3a/G3b final-r2 (blocks 2-9) autorun exit 0
- 2026-11-22 18:58 LAUNCH autorun g3app-pilot (pilot) card artifact/plans/g3app-card.md; stages ['pilot']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app-pilot.log.
- 2026-11-22 19:03 DONE autorun g3app-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-22 19:03 g3-chain: G3c CALIBRATION GATE FAIL; no G3c final (card §3)
- 2026-11-22 19:15 G3c calibration gate diagnosis (manual, harness fields of pilot-calib only; no G3c final ran): stock has 2/3 calibration samples and the median donate_data body is 137,073 B (< 200 KiB), so the gate exits 1 (not body-only) and the chain stopped as pre-registered. Cause, from the event order: the grant hook launches AirGuard and its own SendStatisticsWorker starts (WORKER_SEND, DONATION_START) before INSERT in 10/12 calibration sends, i.e. the upload is not started by the `run` hook; in g3app-000-stock it finished (sink donate_data 18:59:08) before `run` (18:59:20), so no sample after t_run. W = u·D from t_run would therefore not fall in the measured upload. Harness design fault, not an environment failure; G3c needs protocol v4 and new pilots (no G3c data under v3). Battery guard and chain exited; no emulator running. G3a/G3b analysis run (analyze_g3race.py final final-r2): 460 logged, 10 interrupted excluded, 0 invalid, 30 per (profile, arm).
- 2026-11-22 19:45 G3a/G3b method audit (user request after the outcomes were read; EXPLORATORY, followup/audit_g3race.py → results/round3/g3race/analysis/g3race-audit.json; no trial added, dropped or re-labelled, pre-registered numbers unchanged). Pairing holds (same u in all 90 paired cells, no WRITE_ATTEMPT tie with W, close2 withdraws in the sender process as designed). Finding 1: on lte the withdrawal to `:revision` reaches W ~0.1 s after SOCKET_CONFIG vs ~0.03 s for close2 (in-process), while u·D median is 0.03 s, so close2 had 16/30 trials with W during the writes vs 8–9/30 for the other arms; edge/umts exposure is balanced (13–20 per arm). Finding 2: a few matched capture trials (0–3 per cell) have only small (<200 B) after-marker payload (likely TLS alert/close records, not request data). Neither changes a pre-registered count; both go to the card §6 and the issue reply as threats.
- 2026-11-22 21:00 Leader approved P3 and P4 (issue #7, 13:12 UTC) plus the P2 queue snapshot and the P1a TLS application_data count; order G3c v4 → P3 tonight, P4 on 23/11. Prepared before any v4/P3 trial: G3c protocol v4 (race_airguard.py waits for the app's startup worker's get_token + 3 s before insert/run; end event and calibration sample only from the run hook's upload; analyze_g3app.validity adds run-order rules; on v3 pilot-calib the rule flags 10/12 sends), P3 card plans/g3lte-card.md (race_suite.py --warm-revision no-op broadcast to RevisionRemote before every send, --qsnap after the withdraw broadcast, --sndbuf flag for P4, default 16384 unchanged), followup/tls_records.py (+pcapmin full-payload option, default unchanged), followup/qsnap.py, tests (test_g3app v4, test_tls_records, test_qsnap) OK; device-free checks with fake adb (G3c v4 normal: 3/3 samples per build, 8/8 mech valid; v3 fault simulated: 0 samples → gate fails; P3 flags recorded, gate logic exercised). Freeze results/round3/g3/frozen-g3-v4 (81 files); manifests g3app4-{pilot,pilot2,mech,final}, g3lte-{pilot,final} dry-run OK; chain plans/autorun/g3-chain-v4.sh (G3c v4, then P3 regardless of the G3c outcome). Not launched: waits for the user's go-ahead tonight.
- 2026-11-22 21:25 C's review of G3a/G3b (issue #7, 13:22 UTC): numbers confirmed; four notes handled before any v4/P3 trial: (1) 16 KiB send-buffer threat added to g3race-card; P4 "default" = no setSendBufferSize (for the P4 card); (2) P3 balance gate now per payload size (chain v4), card notes 32 KiB does not test the race; audit adds exposure by size; (3) audit adds capture by W phase (during writes: fence 751,490 B/40, fence-abort 88,429 B/44); (4) cap_measure off-by-one fixed (before defaults to 1) + unit test; g3race-summary.json regenerated: only after_marker_new_bytes −1..−2 B in 7 cells (listed in the card). Re-frozen results/round3/g3/frozen-g3-v4b; manifests point to it; dry-runs OK. Not launched.
- 2026-11-22 21:45 G3d prepared for tonight's parallel run (before any G3d run): the Mac's LAN address changed after the move (cert SAN was 192.168.1.20), so cost_suite.py --host auto (en0/en1 at launch) and refuses unless the receiver certificate SAN carries that address (the app verifies the hostname); g3cost manifests use --host auto. Launcher plans/autorun/g3-tonight.sh: refuses on battery unless ALLOW_BATTERY=1; with exactly one attached phone it regenerates the test certificate for the current address if needed (old kept aside, key never committed) and runs g3d-chain.sh in parallel with g3-chain-v4.sh, each under caffeinate with a battery guard. Device-free check: G3d fake adb 9/9 cells valid with TLS over the LAN address; old certificate refused as intended; launcher syntax checked (not executed). Re-frozen results/round3/g3/frozen-g3-v4c (82 files); all 8 manifests dry-run OK; preflight with the G3d env 15 ok. Not launched.
- 2026-11-22 21:55 Harness logic review before tonight's run (user request; nothing running): (1) cost_suite.py did not check `adb install -r`; an older rl-tls build left on the phone would have run silently and treated the `platform` arm as fenced → now asserts Success and installed base.apk sha256 == frozen APK (meta installed_apk_sha256); fake-adb cases: correct → runs, mismatch → stops, failed install → stops. (2) G3d stages set guard_after=false so the ~33 s CPU-heavy guard does not overlap emulator timing; g3-tonight.sh runs one guard after both chains. Other checks held: G3c v4 startup wait/end/validity paths, P3 warm/qsnap/sndbuf flags and per-size gate, shared adb server (no kill-server; G3d picks the single non-emulator device), RevisionRemote is :revision. Re-frozen results/round3/g3/frozen-g3-v4d; all 8 manifests dry-run OK. Not launched.
- 2026-11-22 21:37 g3-tonight: no single attached phone (found 0) or no LAN address: G3d not started; emulator chain only
- 2026-11-22 21:37 g3-tonight: start: emulator chain g3-chain-v4.sh (AC: yes)
- 2026-11-22 21:37 g3-chain: start v4 (G3c protocol v4, then P3 lte balanced)
- 2026-11-22 21:37 LAUNCH autorun g3app4-pilot (pilot) card artifact/plans/g3app-card.md; stages ['pilot']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app4-pilot.log.
- 2026-11-22 21:43 DONE autorun g3app4-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-22 21:43 g3-chain: G3c v4 calibration gate: body size below 200 KiB only; one recalibration (card §3)
- 2026-11-22 21:43 LAUNCH autorun g3app4-pilot2 (pilot) card artifact/plans/g3app-card.md; stages ['pilot2']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app4-pilot2.log.
- 2026-11-22 21:51 DONE autorun g3app4-pilot2: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-22 21:51 g3-chain: G3c v4 calibration gate passed (artifact/results/round3/g3app/pilot-v4-calib2/calibration.json); mechanism pilot next
- 2026-11-22 21:51 LAUNCH autorun g3app4-mech (pilot) card artifact/plans/g3app-card.md; stages ['mech']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app4-mech.log.
- 2026-11-22 21:55 DONE autorun g3app4-mech: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-22 21:55 g3-chain: G3c v4 mechanism gate passed; starting G3c final-v4
- 2026-11-22 21:56 LAUNCH autorun g3app4-final (final) card artifact/plans/g3app-card.md; stages ['final']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app4-final.log.
- 2026-11-22 22:46 DONE autorun g3app4-final: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-22 22:46 g3-chain: G3c final-v4 autorun exit 0
- 2026-11-22 22:46 g3-chain: G3c v4 part ended (exit 0)
- 2026-11-22 22:46 LAUNCH autorun g3lte-pilot (pilot) card artifact/plans/g3lte-card.md; stages ['pilot']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3lte-pilot.log.
- 2026-11-22 22:47 DONE autorun g3lte-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-22 22:47 g3-chain: P3 MECHANISM/BALANCE GATE FAIL; no P3 final (g3lte-card §3)
- 2026-11-22 22:47 g3-chain: P3 part ended (exit 5)
- 2026-11-22 22:47 g3-chain: done
- 2026-11-22 22:47 g3-tonight: emulator chain exited (0)
- 2026-11-22 22:48 g3-tonight: all chains ended
- 2026-11-22 22:55 P3 gate diagnosis (manual, timing fields of pilot-lte4 only; no P3 final ran): every mechanism field held (15/15 valid, cancellations, markers, capture, warm replies, qsnap). The balance gate failed: per-size spread of (WITHDRAW_REQUEST − SOCKET_CONFIG) 337 ms (32 KiB), 42 ms (256 KiB), 19 ms (2 MiB) vs ≤ 15 ms. Cause 1: in race-lte-32768-fence the send broadcast returned about 3.2 s late (host offset of the withdrawal 3.237 s vs u·D 0.016 s; adb stall, host load 4.1 while G3c post-analysis/guard had just run), so that one value is a host delay, not a process path. Cause 2: with one trial per (size, arm) the gate measures per-trial delivery jitter (±20–40 ms) rather than the v3 systematic gap; in the other 14 trials WITHDRAW_REQUEST − SOCKET_CONFIG tracks the host offset within about −25..+23 ms in every arm, i.e. the ~70–80 ms :revision cold-start gap of v3 did not reappear. Gate design fault (B), not an environment failure of the fixture; per card no P3 final; a fix needs a new version and a new pilot.
- 2026-11-22 22:49 g3-tonight: final guard: GUARD OK
- 2026-11-22 23:05 P3 protocol v5 prepared (user decision after the v4 balance-gate failure; before any v5 trial): pilot 3 blocks; gate v5 on d = (WITHDRAW_REQUEST − SOCKET_CONFIG) − withdrawal host offset per trial, adb-stall trials (host offset − u·D > 1 s) counted and excluded from d, per-arm medians within 15 ms; final-lte5 10 blocks; chain plans/autorun/g3-p3v5-chain.sh; freeze results/round3/g3/frozen-g3-v5; manifests g3lte5-{pilot,final} dry-run OK.
- 2026-11-22 22:57 g3d-chain: start (G3d on the phone)
- 2026-11-22 22:57 LAUNCH autorun g3cost-pilot (pilot) card artifact/plans/g3cost-card.md; stages ['pilot']; owned []; log artifact/results/round3/g3cost/autorun-g3cost-pilot.log.
- 2026-11-22 22:57 g3-p3v5: start (P3 v5: pilot 3 blocks, gate v5, final)
- 2026-11-22 22:57 ABORT autorun g3cost-pilot: ABORT(pilot exit 1); guard exit None; SHUTDOWN []. Outcomes not inspected by the runner.
- 2026-11-22 22:57 g3d-chain: G3d pilot failed; chain stopped
- 2026-11-22 22:57 LAUNCH autorun g3lte5-pilot (pilot) card artifact/plans/g3lte-card.md; stages ['pilot']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3lte5-pilot.log.
- 2026-11-22 22:59 DONE autorun g3lte5-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-22 22:59 g3-p3v5: P3 v5 gate passed; starting final-lte5
- 2026-11-22 22:59 LAUNCH autorun g3lte5-final (final) card artifact/plans/g3lte-card.md; stages ['final']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3lte5-final.log.
- 2026-11-22 23:02 G3d pilot (22:57) stopped at setup before any upload: install check passed, but Android 15 `dumpsys package` prints appId= (not userId=), so the UID regex failed (harness parsing fault). Fixed (either key; checked on the phone: uid found); pilot reruns as results/round3/g3cost/pilot-2 (the stopped `pilot` dir is retained, excluded); g3d-chain.sh gate reads pilot-2; g3cost manifests frozen against results/round3/g3/frozen-g3-v5b (re-frozen after P3 final-lte5 had launched under v5, so its freeze check was unaffected). P3 v5 gate passed 22:59 (spread of per-arm median delivery delay 2.2 ms; no adb stall); final-lte5 running.
- 2026-11-22 23:00 g3d-chain: start (G3d on the phone)
- 2026-11-22 23:00 LAUNCH autorun g3cost-pilot (pilot) card artifact/plans/g3cost-card.md; stages ['pilot']; owned []; log artifact/results/round3/g3cost/autorun-g3cost-pilot.log.
- 2026-11-22 23:00 ABORT autorun g3cost-pilot: ABORT(pilot exit 1); guard exit None; SHUTDOWN []. Outcomes not inspected by the runner.
- 2026-11-22 23:00 g3d-chain: G3d pilot failed; chain stopped
- 2026-11-22 23:06 G3d pilot-2 (23:00) stopped at setup before any upload: a fresh install has no files/ dir, so the CA copy failed (harness ordering fault). Fixed (run-as mkdir -p files); every remaining setup step checked by hand on the phone (CA copy, standby bucket, am start Main, init broadcast, getprop, Wi-Fi) → all ok. Rerun as pilot-3; g3cost manifests frozen against results/round3/g3/frozen-g3-v5c (P3 final-lte5 already running under v5). Directories pilot, pilot-2 retained, excluded.
- 2026-11-22 23:01 g3d-chain: start (G3d on the phone)
- 2026-11-22 23:01 LAUNCH autorun g3cost-pilot (pilot) card artifact/plans/g3cost-card.md; stages ['pilot']; owned []; log artifact/results/round3/g3cost/autorun-g3cost-pilot.log.
- 2026-11-22 23:01 DONE autorun g3cost-pilot: DONE; guard exit None; SHUTDOWN []. Outcomes not inspected by the runner.
- 2026-11-22 23:01 g3d-chain: G3d PILOT GATE FAIL; no G3d final (card §3)
- 2026-11-22 23:02 DONE autorun g3lte5-final: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-22 23:02 g3-p3v5: P3 v5 final-lte5 autorun exit 0
- 2026-11-22 23:02 g3-p3v5: done (exit 0); final guard: GUARD OK
- 2026-11-22 23:04 Correction (append-only): B's hand-written entries tonight "22:55 P3 gate diagnosis", "23:02 G3d pilot", "23:05 P3 protocol v5", "23:06 G3d pilot-2" carry estimated times; the machine-written autorun/chain lines are authoritative (P3 v5 pilot 22:57–22:59, gate passed 22:59, final-lte5 22:59–23:02 exit 0 with final guard OK; G3d pilot 22:57, pilot-2 23:00, pilot-3 23:01 all stopped/failed). From here on entries use the shell clock.
- 2026-11-22 23:04 G3d pilot-3 gate fail diagnosed (setup ok; 8/9 cells valid, 16/16 uploads ok+received; one transient adb error with empty stderr before the first upload; Android 15 batterystats estimate only in the checkin pwi,uid line, 0 mAh per pilot cell; B's chain edit had commented out meta= so the gate crashed — fixed, rerun on pilot-3 data reproduces only the transient cell). G3d protocol v2: one logged retry of an adb command failing with empty stderr (never of an upload), parser reads the checkin pwi,uid value (0 is a reading), unit test test_mah_android15, fake-adb end-to-end ok. Rerun as pilot-4; freeze results/round3/g3/frozen-g3-v5d; dry-runs OK.
- 2026-11-22 23:04 g3d-chain: start (G3d on the phone)
- 2026-11-22 23:05 LAUNCH autorun g3cost-pilot (pilot) card artifact/plans/g3cost-card.md; stages ['pilot']; owned []; log artifact/results/round3/g3cost/autorun-g3cost-pilot.log.
- 2026-11-22 23:05 DONE autorun g3cost-pilot: DONE; guard exit None; SHUTDOWN []. Outcomes not inspected by the runner.
- 2026-11-22 23:05 g3d-chain: G3d pilot gate passed; starting final
- 2026-11-22 23:05 LAUNCH autorun g3cost-final (final) card artifact/plans/g3cost-card.md; stages ['final']; owned []; log artifact/results/round3/g3cost/autorun-g3cost-final.log.
- 2026-11-22 23:27 DONE autorun g3cost-final: DONE; guard exit None; SHUTDOWN []. Outcomes not inspected by the runner.
- 2026-11-22 23:27 g3d-chain: G3d final autorun exit 0
- 2026-11-22 23:27 g3d-chain: done
- 2026-11-22 23:28 G3d final (v2, 23:05–23:27) ENVIRONMENT FAILURE, not usable: from about 23:15 (block 5) every upload ended SEND_ERROR (ConnectException / "Software caused connection abort") because the phone screen went off and the phone dozed (dumpsys power: mWakefulness=Dozing, mStayOn=false). Cause, harness design (B): `svc power stayon usb` keeps the screen on only while USB counts as plugged, but `dumpsys battery unplug` (for batterystats) makes it count as unplugged; the 1-minute pilots did not reach the screen timeout. At about 23:27 the phone left adb ("device not found"); the harness ran the remaining cells into errors (180 logged, 115 invalid by the analysis) and ended; its restore commands (battery reset, stayon false) could not reach the phone. The user noticed the phone "off". No G3d result is taken from this directory (retained, excluded). Fix needs G3d protocol v3 and the phone reconnected.
- 2026-11-22 23:29 G3d protocol v3 prepared (before any v3 trial): svc power stayon true; per-cell mWakefulness at start/end, cell valid only if both Awake (analyze_g3cost.valid + unit test); adb device-loss stops the run; fake-adb: normal 18/18 valid, dozing 0/18, device lost stops. Rerun pilot-5 → final-v3 (all 20 blocks), analysis-v3; freeze results/round3/g3/frozen-g3-v5e; dry-runs OK. Waits for the phone to be reconnected (it left adb at ~23:27).
- 2026-11-22 23:48 P4 prepared before any P4 trial (leader-approved; user: run tonight): card plans/g3p4-card.md (fence, fence-abort × SO_SNDBUF {0 = kernel default, 16384, 65536} × edge/umts, 2 MiB, 30 blocks = 360 trials, ~8.3 h; B's earlier estimate of ~2.5 h corrected); TlsTransport keeps the default when sendBuffer<=0 (same line; impLoc unchanged, guard OK) → build fixture/build/g3p4-apk (fa46f01d…; g3-apk 8f723ead… untouched); race_suite --sndbufs (12 cells per block, same u per (block, profile, size)); analyze_g3p4.py (by W phase, TLS application_data, throughput before W, actual sndbuf, paired abort vs fence) smoke-tested on P3 data; fake-adb harness check (12 cells, levels passed); chain plans/autorun/g3-p4-chain.sh; freeze results/round3/g3/frozen-g3-v6b, also used by G3d (its v5e freeze pinned the old transport line). An unused freeze dir frozen-g3-v6 (created minutes earlier, never referenced) was removed before commit.
- 2026-11-22 23:48 g3-p4: start (P4: pilot 1 block, gate, final 30 blocks)
- 2026-11-22 23:48 LAUNCH autorun g3p4-pilot (pilot) card artifact/plans/g3p4-card.md; stages ['pilot']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3p4-pilot.log.
- 2026-11-22 23:59 G3d v3 on hold (user decision: "d tạm treo"); phone not connected; nothing launched for G3d. P4 pilot running.
- 2026-11-23 00:03 DONE autorun g3p4-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-23 00:03 g3-p4: P4 mechanism gate passed; starting final-p4
- 2026-11-23 00:04 LAUNCH autorun g3p4-final (final) card artifact/plans/g3p4-card.md; stages ['final']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3p4-final.log.
- 2026-11-23 05:06 ABORT autorun g3p4-final: ABORT(final exit -2); guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-23 05:06 g3-p4: P4 final-p4 autorun exit 1
- 2026-11-23 05:06 g3-p4: done (exit 1); final guard: GUARD OK
- 2026-11-23 05:06 P4 final-p4 **paused by the user** ("tạm dừng", 04:58): B sent SIGINT to race_suite at 195 logged trials (16 complete blocks 0–15 + 3 trials of block 16), no invalid trial; autorun recorded ABORT(final exit -2), guard OK, emulator-5660 shut down; the Mac was on battery (100 %) at the time. The chain's post steps ran on the partial directory before the abort was recorded: their output is renamed `g3race/analysis-p4_INVALID_interrupted-partial` (derived, not the pre-registered analysis; nothing decided from it). Per g3p4-card §3 (G3a pause rule) only complete blocks of final-p4 count; a resume, if the user wants one, is a fresh directory starting at block 16, analysed together with blocks 0–15 into a new analysis directory.
- 2026-11-23 08:25 G3 package for the leader (user: send finished parts now, P4 later): raw of G3c final-v4, P3 final-lte5, pilots pilot-v4-*, pilot-lte4/5, pilot-p4 and G3d pilots committed (g3race trials as trials.jsonl.gz + sha256; captures as capture-slim.pcap + sha256 of the full pcap; full files stay on disk, git-ignored); EXCLUSIONS rows added; card §6 written for G3c (g3app-card) and P3 (g3lte-card), P4 pause in g3p4-card. **Not committed:** final-p4 (paused, goes with P4) and g3cost final / analysis / autorun-g3cost-final.log, which contain the phone's adb serial in error strings (privacy rule); a redacted copy will be made by script before committing. An edit to analyze_g3cost.py (gzip fallback) was reverted at once because frozen-g3-v6b pins it (checked: 0 mismatches).
- 2026-11-23 08:27 G3 package check: analyze_g3race / audit_g3race / qsnap on final-lte5 and analyze_g3app on final-v4, run in a clean git archive of 4516210 (committed gz + slim pcap + capture-tls only), give the same JSON as the committed analysis-lte5 / analysis-v4 (g3race-summary byte-identical; others equal after dropping the dirs path). guard: GUARD OK.
- 2026-11-23 11:10 Correction (append-only): the G3 package was never pushed as 4516210 (push failed on a large pack); the unpushed commits were split into 7217452, d44577a, 7978605, ab0c4c7 with the same tree (git diff 4516210 ab0c4c7 --stat on the package paths: empty except this RUNLOG). The clean-archive check above was run on that tree.
- 2026-11-23 13:14 P4 resume prepared (user: "tiếp tục p4"), before any resumed trial: manifest plans/autorun/g3p4-final2.json = g3p4-final with `--start 16 --trials 14` → fresh dir `final-p4b` (blocks 16–29, same seed, so the same u and cell order per block), same build and freeze frozen-g3-v6b; post step tls_records only. Analysis after the run: final-p4 blocks 0–15 + final-p4b blocks 16–29; the 3 trials of the interrupted block 16 in final-p4 are excluded by the g3p4-card §3 rule (only blocks complete within their directory). analyze_g3p4.py does not yet apply that rule; it will get the rule (as analyze_g3race 'interrupted block') with a unit test before it is run on the final data. Mac on battery (96 %), battery guard at 15 % runs with it.
- 2026-11-23 13:14 LAUNCH autorun g3p4-final2 (final) card artifact/plans/g3p4-card.md; stages ['final']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3p4-final2.log.
- 2026-11-23 15:30 G3d v3 launch (user: phone attached, go-ahead after B's recommendation to run v3 on the Galaxy A06): phone model SM-A066B, Android 15 (serial not recorded); restored the v2 leftovers first (dumpsys battery reset; svc power stayon false); receiver cert SAN matches the current LAN address; chain plans/autorun/g3d-chain.sh (pilot-5 → gate → final-v3, freeze frozen-g3-v6b) in parallel with the P4 resume (host load recorded per cell).
- 2026-11-23 15:30 g3d-chain: start (G3d on the phone)
- 2026-11-23 15:30 LAUNCH autorun g3cost-pilot (pilot) card artifact/plans/g3cost-card.md; stages ['pilot']; owned []; log artifact/results/round3/g3cost/autorun-g3cost-pilot.log.
- 2026-11-23 15:31 DONE autorun g3cost-pilot: DONE; guard exit None; SHUTDOWN []. Outcomes not inspected by the runner.
- 2026-11-23 15:31 g3d-chain: G3d pilot gate passed; starting final
- 2026-11-23 15:31 LAUNCH autorun g3cost-final (final) card artifact/plans/g3cost-card.md; stages ['final']; owned []; log artifact/results/round3/g3cost/autorun-g3cost-final.log.
- 2026-11-23 15:50 ABORT autorun g3cost-final: ABORT(final exit -2); guard exit None; SHUTDOWN []. Outcomes not inspected by the runner.
- 2026-11-23 15:50 g3d-chain: G3d final autorun exit 1
- 2026-11-23 15:50 g3d-chain: done
- 2026-11-23 15:52 G3d final-v3 stopped by B at 15:50 (SIGINT; 64 cells logged): harness design fault, not the receiver. From cell 53 (block 5, 15:41:25) the phone was Dozing at cell start and every upload ended ConnectException. `battery unplug` makes the phone count as unplugged, so `svc power stayon true` (stay on while plugged in) did not hold; the screen went off at the 10 min screen_off_timeout and deep Doze (mState=IDLE) blocked the app's network, while adb shell still reached the Mac (ping 10 ms, TCP 8800 ok) and the receiver was listening. Phone restored (battery reset, stayon false). final-v3 kept as recorded, not pooled. G3d protocol v4 prepared before any v4 trial: screen_off_timeout 24 h + deviceidle disable all for the run (both restored; values read back into meta power_check, checked by the pilot gate); pilot-6 → final-v4 (20 blocks from 0) → analysis-v4; freeze frozen-g3-v7 (g3cost-card Pilot log). Launch waits for the user's go-ahead.
- 2026-11-23 15:53 G3d v4 launch deferred to tonight (user decision: "tối chạy"); nothing launched; phone left restored (battery reset, stayon false).
- 2026-11-23 16:26 ABORT autorun g3p4-final2: ABORT(final exit -15); guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-23 16:26 P4 final-p4b paused (user: "tạm dừng p4"): B sent SIGINT at about 15:57 with a pattern that also matched the caffeinate wrapper; race_suite did not exit but kept running with abnormal trial durations (11 and 15 min against ~80 s; trial content normal), so B sent SIGTERM to race_suite at 16:25; autorun ABORT(-15), guard 0, emulator-5660 shut down. final-p4b: 113 trials, blocks 16–24 complete (all ended before the signal), block 25 partial (5 trials, incl. the slow ones after the signal) → excluded by the g3p4-card §3 rule. Operational lesson: pause by SIGTERM to the race_suite pid only.
- 2026-11-23 16:26 P4 resume 2 (user: "tiếp tục p4"): manifest g3p4-final3.json = g3p4-final2 with `--start 25 --trials 5` → fresh dir final-p4c (blocks 25–29). Freeze frozen-g3-v7: it differs from v6b only in G3d files (cost_suite.py, g3cost manifests, g3d-chain.sh; checked), every P4 file (race_suite, transport, g3p4 APK, analyze_g3p4, chain) identical, so the P4 protocol is unchanged. Analysis: final-p4 0–15 + final-p4b 16–24 + final-p4c 25–29, complete blocks only.
- 2026-11-23 16:27 LAUNCH autorun g3p4-final3 (final) card artifact/plans/g3p4-card.md; stages ['final']; owned ['emulator-5660']; log artifact/results/round3/g3race/autorun-g3p4-final3.log.
- 2026-11-23 17:25 DONE autorun g3p4-final3: DONE; guard exit 0; SHUTDOWN ['emulator-5660']. Outcomes not inspected by the runner.
- 2026-11-23 17:29 DONE P4 resume 2 (final-p4c, blocks 25–29, 16:27–17:25): 60/60 logged, guard 0, emulator shut down. P4 complete: final-p4 0–15 + final-p4b 16–24 + final-p4c 25–29 → 368 logged, 8 interrupted excluded (blocks 16 and 25, operational), 0 invalid, 30 per cell.
- 2026-11-23 17:29 Before the P4 analysis ran: complete-block rule added to analyze_g3p4.py (split_blocks, as analyze_g3race; unit test followup/test_g3p4.py).
- 2026-11-23 17:29 **TLS file correction (append-only):** autorun runs post steps before SHUTDOWN, so tls_records.py read each capture before the emulator closed it; every post-step capture-tls.jsonl (final-lte5 [committed], final-p4, final-p4b, final-p4c) carries the sha256 of an unfinished pcap (checked: mismatch in all 4). capture-tls-v2.jsonl written next to each from the complete pcap (sha256 matches); analyze_g3race, audit_g3race and analyze_g3p4 read v2 when present. P3 rerun with v2 (scratch): 0 differences in g3race-summary and g3race-audit, so analysis-lte5 stands. The old files are kept. Operational lesson: post steps that read a capture must run after SHUTDOWN.
- 2026-11-23 17:29 P4 analysis: analyze_g3p4.py + qsnap.py on the three dirs → g3race/analysis-p4 (outcome in g3p4-card §6). G3d re-frozen as frozen-g3-v7b (analysis files changed; no G3d code change since v7; manifests repointed; a first v7b dir made before the manifest edit was removed unused); G3d v4 still waits for tonight.
- 2026-11-23 17:31 P4 package check: in a clean git archive of 4213b0a, analyze_g3p4 + qsnap (final-p4/-p4b/-p4c) and analyze_g3race + audit_g3race (final-lte5, with capture-tls-v2) give the committed analysis-p4 / analysis-lte5 JSON (equal after dropping the dirs path); unit tests OK; guard: GUARD OK. P4 raw commits 5c6cc45, e15689d, 4213b0a; analysis 3b5b1e0.
- 2026-11-23 21:27 G3c v5 PREP (leader's request in issue #7 23/11 13:20 UTC; user: run now, G3d v4 after it): card plans/g3app5-card.md; build stockcancel16 (OkHttp SocketFactory SO_SNDBUF 16384 before connect) + SOCKET_CONFIG actual_sndbuf logging in every build (OkHttp network interceptor; fenced: emit on the connect line of the clone's HttpTransport copy, artifact/transport unchanged); build_g3.sh VARIANTS/OUTDIR → realapp/airguard/build/g3v5 (sha256 stockcancel16 051fd322…, stockcancel 42fd5eca…, fenced 685fec5b…); race_airguard.py/airguard_sink.py port 8794; analyze_g3app5.py + test_g3app5.py; chain g3-g3c5-chain.sh; manifests g3app5-{pilot,mech,final}.json; freeze frozen-g3-v8 (G3d manifests repointed to v8, G3d files unchanged). CORRECTION found by the new unit test: analyze_g3app.py v4 "sink logged complete after marker" used marker+600 s and also counted a later same-build trial; fixed (window ends at the same build's next start marker; test_g3app.test_receiver_window fails without the fix); rerun on final-v4 → new dir analysis-v4-r2: fenced 5 → 1, other builds unchanged (30); analysis-v4 kept. Affects the G3c v4 report in issue #7 (fenced 5/30 → 1/30) and g3app-card §6 (note appended). guard GUARD OK.
- 2026-11-23 21:27 g3c5-chain: start G3c v5 (stockcancel16, stockcancel, fenced)
- 2026-11-23 21:27 LAUNCH autorun g3app5-pilot (pilot) card artifact/plans/g3app5-card.md; stages ['calib']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app5-pilot.log.
- 2026-11-23 21:33 DONE autorun g3app5-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-23 21:33 g3c5-chain: G3c v5 calibration gate passed; mechanism pilot next
- 2026-11-23 21:33 LAUNCH autorun g3app5-mech (pilot) card artifact/plans/g3app5-card.md; stages ['mech']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app5-mech.log.
- 2026-11-23 21:36 DONE autorun g3app5-mech: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-23 21:36 g3c5-chain: G3c v5 MECHANISM GATE FAIL; no final (card §3)
- 2026-11-23 21:41 G3c v5 STOPPED at the mechanism gate (chain 21:27–21:36): pilot-v5-calib passed (D stockcancel16 24.0 s, stockcancel 18.2 s, fenced 18.0 s; body 262,625 B); pilot-v5-mech failed only on actual_sndbuf (fenced 16384, stockcancel16 32768, stockcancel 2097152). Diagnosis: getSendBufferSize() units differ by API (java.net.Socket returns the kernel value = 2 × requested; NIO SocketChannel returns half), so the gate compared different units — gate design fault, not environment. No v5 final; v5 dirs kept, not pooled. Fix = protocol v5b (g3app5-card Pilot log): kernel_sndbuf logged by the same getsockopt call in every build (G3.kern, reflection; first attempt with android.system.Os.getsockoptInt did not compile, not in the public SDK), rebuilt APKs build/g3v5b, gate kernel_sndbuf 32768 for stockcancel16 and fenced, new calibration; analyze_g3app5 reports both units (test updated); chain g3-g3c5b-chain.sh, manifests g3app5b-*.json, freeze frozen-g3-v8b (G3d manifests repointed, G3d files unchanged). guard GUARD OK. Launching the v5b chain now.
- 2026-11-23 21:41 g3c5b-chain: start G3c v5b (stockcancel16, stockcancel, fenced)
- 2026-11-23 21:41 LAUNCH autorun g3app5b-pilot (pilot) card artifact/plans/g3app5-card.md; stages ['calib']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app5b-pilot.log.
- 2026-11-23 21:47 DONE autorun g3app5b-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-23 21:47 g3c5b-chain: G3c v5b calibration gate passed; mechanism pilot next
- 2026-11-23 21:47 LAUNCH autorun g3app5b-mech (pilot) card artifact/plans/g3app5-card.md; stages ['mech']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app5b-mech.log.
- 2026-11-23 21:51 DONE autorun g3app5b-mech: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-23 21:51 g3c5b-chain: G3c v5b MECHANISM GATE FAIL; no final (card §3)
- 2026-11-23 21:52 G3c v5b STOPPED at the mechanism gate (chain 21:41–21:51): calibration passed (D 18.2 / 18.3 / 18.0 s); mechanism gate failed only on kernel_sndbuf: every build-trial logged kernel_sndbuf=-1;kernel_err=NoSuchMethodException (hidden API getsockoptInt blocked by reflection on API 33) — harness measurement fault. No final; v5b dirs kept. Check (B, 21:5x): booted own P04AvdA on emulator-5666 (-read-only, no APK installed) to confirm /system/bin/ss (iproute2-ss171113) reports skmem tb; emulator killed. Next: protocol v5c with a harness-side kernel read (ss) independent of the app.
- 2026-11-23 21:54 G3c protocol v5c ready (g3app5-card Pilot log): harness-side kernel send-buffer read race_airguard.py --sockdiag (guest ss skmem tb of the first sink socket with Send-Q >= 4096), checked in the calibration gate (tb 32768 for stockcancel16 and fenced); APKs = build/g3v5b; analyze_g3app5 adds donation_sockdiag_tb (test); chain g3-g3c5c-chain.sh, manifests g3app5c-*.json, freeze frozen-g3-v8c (G3d manifests repointed, G3d files unchanged); guard GUARD OK. Launching.
- 2026-11-23 21:54 g3c5c-chain: start G3c v5c (stockcancel16, stockcancel, fenced)
- 2026-11-23 21:54 LAUNCH autorun g3app5c-pilot (pilot) card artifact/plans/g3app5-card.md; stages ['calib']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app5c-pilot.log.
- 2026-11-23 22:00 DONE autorun g3app5c-pilot: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-23 22:00 g3c5c-chain: G3c v5c calibration gate passed; mechanism pilot next
- 2026-11-23 22:00 LAUNCH autorun g3app5c-mech (pilot) card artifact/plans/g3app5-card.md; stages ['mech']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app5c-mech.log.
- 2026-11-23 22:04 DONE autorun g3app5c-mech: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-23 22:04 g3c5c-chain: G3c v5c mechanism gate passed; starting final-v5c
- 2026-11-23 22:04 LAUNCH autorun g3app5c-final (final) card artifact/plans/g3app5-card.md; stages ['final']; owned ['emulator-5666']; log artifact/results/round3/g3app/autorun-g3app5c-final.log.
- 2026-11-23 22:39 DONE autorun g3app5c-final: DONE; guard exit 0; SHUTDOWN ['emulator-5666']. Outcomes not inspected by the runner.
- 2026-11-23 22:39 g3c5c-chain: G3c final-v5c autorun exit 0
- 2026-11-23 22:43 G3c v5c DONE (final-v5c 22:04–22:39): 90 logged, 2 invalid (trial 10 stockcancel and stockcancel16: withdrawal before the worker ran, no donation end; validity rule, no replacement). analysis-v5c via the manifest post step; slim pcaps (pcap_slim.py) for pilot-v5-mech, pilot-v5b-mech, pilot-v5c-mech, final-v5c — analysis on the slim copy equals the full one. Seed actually used g3app5c-20261123 (text replacement when making the v5b/v5c manifests; before any trial; card §6). Exploratory diagnosis script diag_g3app5.py → analysis-v5c/diag-v5c.json (post hoc, labelled). Card §6, EXCLUSIONS (28 task rows, 56 dirs, 0 without reason), tracker updated. Emulator shut down by autorun. guard GUARD OK.
- 2026-11-23 23:01 G3c v5c checked by C (issue #7 comment 7106433587): reruns identical, C's independent count matches every primary/paired count and the v4 correction. C's card fix: the donation body is not always 262,625 B — followup/body_sizes_g3app.py → analysis-v5c/body-sizes.json (final-v5c 33/37 complete bodies 262,625 B, 3 × 260,390, 1 × 258,155; final-v4 80/91, 11 × 260,390); card §6 note added; no count changes.
- 2026-11-24 00:13 g3d: phone attached (SM-A066B, Android 15, USB power, Awake), LAN 192.168.1.20 = cert SAN (to 22/12), Mac on AC; user go-ahead 24/11 for the G3d v4 chain (pilot-6 -> gate -> final-v4, frozen v8c). Prior autorun summaries copied to *.summary-v3.json / *.summary-pilot5.json before the overwrite.
- 2026-11-24 00:14 g3d-chain: start (G3d on the phone)
- 2026-11-24 00:14 LAUNCH autorun g3cost-pilot (pilot) card artifact/plans/g3cost-card.md; stages ['pilot']; owned []; log artifact/results/round3/g3cost/autorun-g3cost-pilot.log.
- 2026-11-24 00:14 DONE autorun g3cost-pilot: DONE; guard exit None; SHUTDOWN []. Outcomes not inspected by the runner.
- 2026-11-24 00:14 g3d-chain: G3d pilot gate passed; starting final
- 2026-11-24 00:14 LAUNCH autorun g3cost-final (final) card artifact/plans/g3cost-card.md; stages ['final']; owned []; log artifact/results/round3/g3cost/autorun-g3cost-final.log.
- 2026-11-24 01:10 DONE autorun g3cost-final: DONE; guard exit None; SHUTDOWN []. Outcomes not inspected by the runner.
- 2026-11-24 01:10 g3d-chain: G3d final autorun exit 0
- 2026-11-24 01:10 g3d-chain: done
- 2026-11-24 01:14 g3d: final-v4 DONE (chain exit 0, 01:10). Harness-only check: 180/180 cells valid, 1800/1800 uploads SEND_OK and received, batterystats record in 180/180; phone restored (screen_off_timeout 600000, Doze enabled, battery reset); no serial in pilot-6, final-v4, analysis-v4 or the new logs. Pre-registered analysis-v4 written by the manifest. Found after the run: the batterystats estimate is 0 mAh in every cell of every G3d run (also global CPU and computed drain 0; exploratory `followup/bs_check_g3cost.py` -> analysis-v4/batterystats-check.json); a property of the proxy, not a harness fault; no rerun. Packaging: final-v4/cells.jsonl (359 MB, mostly event logs) git-ignored, committed as cells.jsonl.gz + sha256 (same convention as trials.jsonl.gz); analyze_g3cost.py / bs_check read the .gz when the raw file is absent; analysis on the .gz alone and on the raw file both byte-identical to analysis-v4. autorun-g3cost-final-v4.{log,jsonl}: the v4 part of the shared autorun log (the shared file also holds v2 lines with the serial and stays uncommitted). Card §6, tracker, EXCLUSIONS (pilot-6 row, G3d task row).
- 2026-11-24 05:01 g3d: G3d v4 outcome posted to issue #7 (comment 7115229087, user go-ahead), with the note to C on the G3c body sizes.
- 2026-11-24 21:39 r4df prep (no device, no AWS change): b-exp fast-forwarded to main 9c483a9; applied C's phone-faults.patch and airguard-phone.patch (tests pass); B added phone fault checks to campaign_airguard.py --phone (net probe, kill_verified, bounded boot) and the matching phone-only validity rules in analyze_airguard.py (test_airguard_phone.py; guard byte-identical), and a bounded post-reboot boot wait in campaign.py --phone-faults. Rebuilt fixture/build/revision-apk (5 APKs from main; the 3 earlier APKs kept in build/revision-apk-20261119). Cards plans/r4df-{lifecycle,g3a,airguard}-card.md (approval pending leader). G3d card §6 threats (leader 23/11, C 24/11). Device Farm account check: 885.13/1000 trial minutes left; pool pilot-pixel8a = Pixel 8a Android 17, HIGHLY_AVAILABLE.
- 2026-11-24 21:50 r4df prep: logic review before any job. campaign_airguard.py --phone: hooks add -f 0x20 (include stopped packages after pm clear, as campaign.py), kill records pid_before. C's gates.py does not read the new AirGuard fault fields, so B adds plans/r4df/gate_b.py (analysis validity on pilot plans, harness fields only) and plans/r4df/job.sh (upload -> run_df.sh with the trial-minute guard -> gates.py + gate_b.py; ARNs in ~/.p04/r4df). User decision 24/11: use the existing account (profile p04).
- 2026-11-24 21:57 r4df: user reports the leader's go-ahead (outside GitHub) for round 4 on Device Farm; plan posted to issue #7 (comment 7135206854). Starting the lifecycle reboot pilot.
- 2026-11-24 21:57 r4df life/pilot-preb: upload (app rl-mfence.apk, package sha256 4d11627bd452, spec life-preb.yml, timeout 20 min)
- 2026-11-24 21:57 r4df life/pilot-preb: scheduled on Device Farm (Pixel 8a pool)
- 2026-11-24 22:03 r4df life/pilot-preb: run_df exit 0; trial minutes after: 883.32 (used 1.8); run COMPLETED PASSED
- 2026-11-24 22:03 r4df life/pilot-preb: pilot gate: gates.py PASS, gate_b PASS
- 2026-11-24 22:03 r4df life/pilot-preb: done
- 2026-11-24 22:06 r4df life/pilot-preb: Device Farm job COMPLETED PASSED (1.8 trial min; 883.32 left); gates.py + gate_b PASS, but diagnosis shows no reboot happened (boot_s 0.55 s; monotonic clock continuous in all 5 apps; plans/r4df/reboot_evidence.py -> reboot-evidence.json): Device Farm ignores adb reboot. Per the card, the reboot schedule is dropped on Device Farm (lifecycle and AirGuard; no AirGuard reboot pilot). Harness v1.1 before any further job: reboot records /proc/uptime before/after, reboot_verified, analysis rule 'reboot not verified' (test_phone_reboot.py, test_airguard_phone.py); emulator path unchanged (guard OK). Next: lifecycle netloss pilot.
- 2026-11-24 22:08 r4df harness v1.1 (before the netloss pilot): positive control for the network cut in phone mode (probe up before the cut; net_verified_down = up before and down after), campaign.py --phone-faults and campaign_airguard.py --phone; emulator path unchanged (guard OK).
- 2026-11-24 22:08 r4df life/pilot-pnet: upload (app rl-mfence.apk, package sha256 30ca8e056e3c, spec life-pnet.yml, timeout 20 min)
- 2026-11-24 22:09 r4df life/pilot-pnet: scheduled on Device Farm (Pixel 8a pool)
- 2026-11-24 22:14 r4df life/pilot-pnet: run_df exit 0; trial minutes after: 881.75 (used 1.6); run COMPLETED PASSED
- 2026-11-24 22:14 r4df life/pilot-pnet: pilot gate: gates.py PASS, gate_b PASS
- 2026-11-24 22:14 r4df life/pilot-pnet: done
- 2026-11-24 22:15 r4df life/pilot-pnet: COMPLETED PASSED (1.6 trial min; 881.75 left); gates.py + gate_b PASS; cut confirmed in every app (probe up before, down after; net_verified_down true); NET_FAIL events in all five app logs (mechanism check). Protocol frozen: frozen-life-df (plans/r4df/freeze_r4df.py; HEAD 1bf77cd, package sha256 abba818f). Starting the netloss final (START=0 N=20, timeout 80 min).
- 2026-11-24 22:15 r4df life/net: upload (app rl-mfence.apk, package sha256 abba818f270b, spec life-net.yml, timeout 80 min)
- 2026-11-24 22:16 r4df life/net: scheduled on Device Farm (Pixel 8a pool)
- 2026-11-24 22:47 r4df life/net: run_df exit 0; trial minutes after: 854.25 (used 27.5); run COMPLETED PASSED
- 2026-11-24 22:47 r4df life/net: done
- 2026-11-24 22:48 r4df life/net (final, netloss START=0 N=20): COMPLETED PASSED (27.5 trial min; 854.25 left). Harness check: 20 plans, 0 phone-invalid, 0 trial/setup errors, net_verified_down in all, max action gap 9.6 s. Pre-registered analysis: analyze_test6.py --manifest plans/r4df/manifest-life-df.json (B copy of C's manifest, reboot dropped) -> life/analysis: 20 analysed, 0 invalid, 0 unused.
- 2026-11-24 22:48 r4df airguard: starting pilot-p1 (pending,kill,netloss N=1; no reboot pilot, reboot dropped on Device Farm).
- 2026-11-24 22:48 r4df airguard/pilot-p1: upload (app airguard-fenced.apk, package sha256 a6d75ac453f6, spec ag-p1.yml, timeout 20 min)
- 2026-11-24 22:49 r4df airguard/pilot-p1: scheduled on Device Farm (Pixel 8a pool)
- 2026-11-24 22:54 r4df airguard/pilot-p1: run_df exit 0; trial minutes after: 851.08 (used 3.2); run COMPLETED PASSED
- 2026-11-24 22:55 r4df airguard/pilot-p1: pilot gate: gates.py PASS, gate_b PASS
- 2026-11-24 22:55 r4df airguard/pilot-p1: done
- 2026-11-24 22:55 r4df airguard/pilot-p1: COMPLETED PASSED (3.2 trial min; 851.08 left); gates.py + gate_b PASS; kill_verified (pids existed and gone), cut verified (up before, down after), hooks ok, warm-up ok; netloss quiescence wait 90.8 s as on the emulator (B2/G2b netloss 20/20 at about 92 s). Frozen: frozen-airguard-df (HEAD 57e726c; package sha256 a6d75ac4, built at adfe463, same harness). Starting finals f1 (START=0 N=10) then f2 (START=10 N=10), timeout 70 min each.
- 2026-11-24 22:56 r4df airguard/f1: upload (app airguard-fenced.apk, package sha256 a6d75ac453f6, spec ag-f1.yml, timeout 70 min)
- 2026-11-24 23:21 r4df airguard/f1: the S3 PUT of the AirGuard package (curl in upload_df.sh, no timeout) stalled from 22:56 to 23:20; B stopped the f1/f2 chain before any run was scheduled (no Device Farm run, no minutes used, no results dir). Fix in plans/r4df/job.sh: upload watchdog (20 min per attempt, 3 attempts). f1 and f2 restart with the same names (nothing was recorded under them).
