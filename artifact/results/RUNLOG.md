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
