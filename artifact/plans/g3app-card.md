# Experiment card — G3c (group 3): AirGuard with the withdrawal during a donation upload (protocol v1; v4 from 22/11 evening, see Pilot log)

Status: written 22/11, before any G3c trial; frozen at the commit that adds it (calibration pilot → gate → mechanism pilot →
gate → final; chain `plans/autorun/g3-chain.sh`, after G3a/G3b). Owner: B (Duy).
Source: issue #7, "G3c: AirGuard với lệnh rút giữa lúc upload". The issue fixes the question, the builds (stock, layered,
fenced, and stock-cancel if a small patch), the design outline (a donation of a few hundred KiB, a B10 v3 link, the app's own
switch-off path at a seeded point of the upload), the oracle (G3b capture and marker), and N ≈ 30 per build. Everything else is
a B decision, made before any data. B7 freeze reopened for group 3 only.

## 1. Question and claim
- In a real app, when the withdrawal falls during a donation upload, which builds still send data after the acknowledgement?
- Can support: AirGuard at the F-Droid commit with the B2 integration, the donation path, one shaped link (umts), these four
  builds, N per build, on an emulator.
- Cannot support: the app's other network paths, other cancellation designs, phones, HTTPS in production (the test sink is
  plain HTTP as in B2). 0/N is not an impossibility guarantee.

## 2. Design
- Builds: all four from a fresh copy of the clean checkout (commit d515c534), `realapp/airguard/build_g3.sh`
  (`apply.sh`, then `apply_g3.sh`). All four get the same G3 hooks; the frozen B2/G2b APKs are not used, because the hooks
  change the APK. Outputs `realapp/airguard/build/g3/airguard-<build>.apk`; sha256 in meta.json and the freeze directory.

  | Build | Package suffix | Sink port | Donation path |
  |---|---|---|---|
  | `stock` | `.p04stock` | 8796 | Retrofit/OkHttp, unchanged |
  | `stockcancel` | `.p04stockcancel` | 8793 | stock, plus an OkHttp interceptor registry of in-flight calls; `Call.cancel()` on every call when the switch is turned off |
  | `fenced` | `.p04fenced` | 8797 | B2 design: ResidueDroid HttpTransport, chunk fence |
  | `layered` | `.p04layered` | 8795 | G2b design: one durable check under the lock, then HttpTransport without a per-chunk check |
- G3 hooks, identical in every build:
  - the stock donation logs DONATION_START, then DONATION_OK or DONATION_ERROR (the call itself is unchanged);
  - the withdraw hook runs the app's own path (consent log, `SharedPrefs.shareData = false`, scheduler removal), then cancels
    in-flight calls (stockcancel only), then logs WITHDRAW_DONE (the acknowledgement), then opens one TCP connection to the
    host marker port 8799 carrying the trial id (MARKER_SENT).
- Driver `followup/race_airguard.py`. Per trial k, the four builds run one after another, in an order shuffled from seed
  `g3app-20261122`, with one u ~ U(0,1) per trial shared by every build (paired). Per build:
  1. pm clear, then grant;
  2. insert **1,500 'pre' beacons** for one device. G2b had about 1.4 KB per 4 beacons; the gate checks the body size;
  3. start marker: hook op `mark`, the app connects to 8799 with id `<tid>-start`;
  4. run the donation worker;
  5. at W = u · D_build after the run hook (host monotonic clock), the withdraw hook;
  6. wait for a donation end event (at most 4·D + 30 s), read the events, then force-stop.
- D_build comes from calibration `pilot-calib`: 3 runs per build without withdrawal. D_build is the median host time from the
  run hook to the sink's donate_data log, so it includes the worker start, ping and token.
- Network: as G3a/G3b, umts profile only (128 kbit/s, 118 ms), prio root with the marker port unshaped, data over the radio.
  Capture: emulator console capture for the trial phase.
- N: **30 trials per build** (120 build-trials). AVD P04AvdA on emulator-5666; sink ports 8793/8795/8796/8797; marker 8799.
  Runs after G3a/G3b, never in parallel with them.

## 3. Gates, validity, stopping, replacement
- Calibration gate (mechanical):
  - every build has 3 calibration donations at the sink;
  - the median donate_data body is ≥ 200 KiB;
  - every D_build is ≥ 5 s, so that W can fall inside the upload.

  If only the body size fails, one recalibration `pilot-calib2` runs with N_beacons = ceil(1500 · 262144 / median body
  bytes), at most 6,000 (the insert hook must stay inside the 60 s broadcast limit), then the same gate. This is a harness parameter, fixed here. The final uses the N of the calibration
  that passed (`calibration.json` `nbeacons`). Any other failure → no final, reported in issue #7.
- Mechanism pilot `pilot-mech`: 2 trials (8 build-trials), excluded. Gate:
  - every build-trial valid;
  - MARKER_SENT without error;
  - start marker hook ok;
  - every app marker and start marker is in marker.jsonl and in the pcap.

  It never reads bytes after the marker, placement or the sink's post-ack log.
- Validity (harness fields only):
  - no trial error;
  - grant, insert, run and withdraw hooks ok;
  - events read; device alive at the end;
  - a donation end event logged.

  First 30 valid per build in k order. Stop after 30 trials. Replacement: environment failures only, whole trials (all four
  builds) from k = 30, at most 3.

## 4. Analysis (`followup/analyze_g3app.py`, unit test `followup/test_g3app.py`)
- **Primary (pre-registered):** per build, trials "sent after the ack". These are TCP payload bytes guest → the build's sink
  port in capture frames after the SYN of the app's marker connection and before the next start marker. Reported with Wilson
  95% over trials with the marker in the capture; the others are counted by status.
- **Secondary (pre-registered):**
  - payload bytes after the marker;
  - the sink logged donate_data complete after the marker arrived (host clock on both sides);
  - end events;
  - placement of the withdrawal on the device clock: before DONATION_START, during, or after the donation end. This is
    reported, never used for selection;
  - stop points: fenced BLOCK, layered early=1, stockcancel CANCEL_DONE calls;
  - fenced and layered: the app oracle (BYTES_ACCEPTED n > 0 after WITHDRAW_DONE);
  - paired 2×2 per trial: fenced vs each other build.
- Output `results/round3/g3app/analysis/g3app-summary.json`.

## 5. Threats
- **Internal:**
  - D includes the worker start, ping and token, so some withdrawals fall before the donation starts (reported as
    placement);
  - builds run one after another inside a trial, not at the same time;
  - the debug builds keep AirGuard's HttpLoggingInterceptor (BODY), as in B2;
  - the umts profile only;
  - G3d runs on the phone at the same time (host load recorded).
- **Construct:**
  - the capture boundary is the guest NIC;
  - the ack is WITHDRAW_DONE, the end of the app's own withdrawal path in the test hook;
  - the sink is plain HTTP.
- **External:** one app, one path, emulator; stockcancel is one cancellation design (interceptor registry).
- **Conclusion:** N = 30 per build.

## Pilot log
- 22/11, before any G3c trial: the capture method changed with G3a/G3b protocol v2 (`-tcpdump` at emulator launch; see
  g3race-card.md Pilot log). Applies to every G3c trial; nothing else changed. Freeze `frozen-g3-v2`.
- 22/11: G3c runs after the G3a/G3b resume, on battery power (user decision); the battery guard (15 %) applies. A stop by the
  guard before the final ends is resumed as G3a/G3b: a fresh directory from the next whole trial k, analysing only trials
  complete in their directory.

- pilot-calib (22/11 18:58–19:03; excluded): **CALIBRATION GATE FAIL**, so no G3c final under v3 (stopped by the chain as
  pre-registered). Stock has 2/3 calibration samples and the median body is 137,073 B (< 200 KiB); this is not a body-only
  failure, so no recalibration. Diagnosis (manual, harness fields and event order only):
  - the grant hook calls `scheduleShareData()`, so the app's periodic SendStatisticsWorker runs at once (ping, get_token);
  - it read the beacon table while the insert hook was still inserting (WORKER_SEND and DONATION_START before INSERT in
    10/12 sends, bodies 101,920–176,131 B);
  - in g3app-000-stock it finished (sink 18:59:08) before the run hook (18:59:20), so there was no sample after t_run;
  - the upload was therefore not started by the run hook, and W = u·D from t_run would not fall in it.

  This is a harness design fault, not an environment failure. A fix needs protocol v4 and new pilots.

- **Protocol v4** (22/11 evening, before any v4 trial; only the harness and the validity rule change; builds, design, N,
  gates and analysis are as v1 otherwise). Freeze `results/round3/g3/frozen-g3-v4b` (re-frozen after C's review, before any v4 trial); chain `plans/autorun/g3-chain-v4.sh`;
  manifests `g3app4-*.json`. The new directories are `pilot-v4-calib`, `pilot-v4-calib2` (if body-only), `pilot-v4-mech`
  and `final-v4`; `calibration-used-v4.json`; `analysis-v4`.
  1. **Startup worker** (`race_airguard.py`): after the grant hook, wait until the sink logs this build's `get_token`
     (at most 30 s), then 3 s more, and only then insert, start marker and run. The app's periodic worker therefore reads
     an empty beacon table (the app's own "nothing to send"), and the donation is the run hook's. The action is logged as
     `startup_worker` (`seen`, `waited`).
  2. **Wait loop:** the donation end must be logged after RUN_ENQUEUED (file order).
  3. **Calibration sample:** counted only if no DONATION_START precedes RUN_ENQUEUED (`donation_before_run` false).
  4. **Validity** (`analyze_g3app.validity`, harness fields only), added to the v1 rules:
     - a RUN_ENQUEUED event exists;
     - no DONATION_START before it;
     - a donation end event after it.

     Unit test `test_g3app.py test_v4_validity`. On the v3 pilot-calib this rule flags 10/12 sends ("donation started
     before run"), the fault above.
  5. **Device-free check** (fake adb, 22/11):
     - normal app behaviour → 3/3 calibration samples per build, 8/8 mechanism trials valid, markers present;
     - with the v3 fault simulated → 0 samples, so the gate fails as intended.
  - Expected body: one undisturbed send of 1,500 beacons was 176,131 B in v3, below 200 KiB, so the pre-registered
    body-only recalibration (N = ceil(1500 · 262144 / median body)) is likely. It runs automatically, and the final
    uses the N of the calibration that passed.

## 6. Outcome (after the run)
