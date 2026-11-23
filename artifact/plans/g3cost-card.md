# Experiment card — G3d (group 3): upload cost on a real phone (protocol v1)

Status: written 22/11, before any G3d run; frozen at the commit that adds it (pilot → gate → final; chain
`plans/autorun/g3d-chain.sh`). Owner: B (Duy).
Source: issue #7, "G3d: chi phí trên điện thoại thật". The issue fixes the question, the phone (the Galaxy A06 of Test 1),
the arms (TLS fence, TLS early, the platform client `HttpsURLConnection` without extra dependency, one body), the sizes
(4 KiB / 256 KiB / 2 MiB), shuffled cell order per block, and the measures (process CPU ms/MiB, time per upload, a
batterystats proxy labelled as a model estimate, foreground or background stated). Everything else is a B decision, made
before any data. The user's own phone; no rental, no cost.

## 1. Question and claim
- On a real phone, how much CPU, time and (estimated) energy does the fence cost compared with the early check and the
  platform client?
- Can support: relative cost on one phone (Samsung Galaxy A06 5G, Android 15), Wi-Fi, this receiver, these sizes, N per cell.
- Cannot support: energy measured by an instrument (batterystats is the platform's power model); other phones or networks;
  background execution.

## 2. Design
- Build: the G3 TLS fixture `fixture/build/g3-apk/rl-tls.apk`, the same APK as G3a/G3b, debuggable, installed with run-as.
  Arms:
  - `fence`: TlsTransport, per-write check under the lock;
  - `early`: TlsTransport, no per-write check;
  - `platform`: HttpsURLConnection, fixed-length streaming, no per-write check.

  The same early check runs before each send in every arm. No withdrawal; every upload is permitted.
- Driver `followup/cost_suite.py`. A block = all 9 (arm, size) cells, in an order shuffled per block from seed
  `g3cost-20261122`. A cell = **10 uploads** one after another. Before the cell, `am start` Main (foreground) and
  `dumpsys batterystats --reset`. After the cell, the app UID's lines of `dumpsys batterystats` (Estimated power use, mAh)
  and its `--checkin` lines.
- Phone state: USB connected for adb.
  - `dumpsys battery unplug` makes batterystats count as on battery;
  - `svc power stayon usb` keeps the screen on;
  - both are restored at the end (`dumpsys battery reset`, `svc power stayon false`).

  The app runs in the **foreground**.
- Network: Wi-Fi. The receiver is a TLS 1.2 server on this Mac's LAN address (resolved at launch, `--host auto`; see Pilot log), port 8800, using a test certificate with
  SAN = that address. Key in `~/.p04/g3dcert`, never committed; the CA sha256 is in meta.json.
- N: **20 blocks** → 20 cells and 200 uploads per (arm, size). Runs at the same time as the emulator chain on the same Mac;
  host load is recorded per cell.
- Privacy: no serial, IMEI, number or account in the results; model and Android version only.

## 3. Gate, validity, stopping, replacement
- Pilot `pilot`: 1 block with 2 uploads per cell, excluded. Gate (mechanical):
  - 9/9 cells valid;
  - every upload ended SEND_OK, with the receiver logging it complete;
  - a batterystats UID line in at least one cell;
  - the restore commands ran.

  Fail → no final, reported in issue #7.
- Cell validity (harness fields only): no harness error, and every upload logged an end event. SEND_ERROR uploads are
  counted, not used. First 20 valid cells per (arm, size) in block order.
- Stop after 20 blocks. Replacement: environment failures only (adb disconnect), whole blocks from 20, at most 3.

## 4. Analysis (`followup/analyze_g3cost.py`, unit test `followup/test_g3cost.py`)
- Per (arm, size), descriptive:
  - process CPU per MiB (median, nearest-rank p95), per upload;
  - elapsed per upload (median, p95, max), device clock;
  - estimated energy per MiB: the cell's UID mAh / (uploads × MiB), median over cells; cells without a reading are counted,
    never imputed.
- Ratios of medians fence/early and fence/platform per size. No p-values.
- Output `results/round3/g3cost/analysis/g3cost-summary.json`.

## 5. Threats
- **Internal:**
  - shuffled cell order within blocks;
  - the adb broadcast and the event polling run between uploads;
  - the screen is on;
  - USB power is present (the unplug override only changes accounting);
  - the host also runs the emulator chain;
  - Wi-Fi rate varies.
- **Construct:**
  - process CPU is the whole app process, not the transport alone;
  - batterystats is a model estimate, not measured energy;
  - CPU time is in ms steps (coarse for 4 KiB).
- **External:** one phone, one Android version, one network, foreground only.
- **Conclusion:** N = 20 cells per (arm, size); medians and ratios are descriptive.

## Pilot log
- 22/11 evening, before any G3d run (protocol v1 otherwise unchanged): the Mac moved, so its LAN address is no longer
  192.168.1.20. Two changes:
  - `cost_suite.py --host auto` takes the address of en0/en1 at launch. It refuses to start unless the receiver
    certificate's SAN carries that address, because the app checks the hostname. `meta.json` records `host` and
    `host_source`;
  - the launcher `plans/autorun/g3-tonight.sh` regenerates the self-signed 30-day test certificate for the current
    address when the SAN differs. The old one is kept aside and the key is never committed; the CA sha256 is in
    `meta.json`.

  G3d runs in parallel with the emulator chain `g3-chain-v4.sh` (G3c v4, then P3) on the same Mac. Host load is recorded
  per cell. Freeze `frozen-g3-v4c`.
- 22/11, harness review before any G3d run:
  - `cost_suite.py` now checks that `adb install -r` printed Success and that the installed base.apk sha256 equals the
    frozen APK (`installed_apk_sha256` in meta). Otherwise it stops. Without the check, an older rl-tls build left on the
    phone could have run silently, and in that build an unknown mode such as `platform` is treated as fenced;
  - G3d stages run without the per-stage guard, so that its CPU load does not coincide with emulator timing. The launcher
    runs one guard at the end;
  - fake-adb checks: correct install → runs; mismatching installed hash → stops; failed install → stops.
- Device-free check (fake adb, 22/11): `--host auto` resolved the LAN address. With a matching certificate, 9/9 cells were
  valid and the receiver logged 9 TLS uploads over the LAN address. With the old certificate the harness refused, as
  intended.
- pilot (22/11 22:57; excluded, no upload ran): the harness stopped at setup. The install check passed (Success, installed
  sha256 = frozen APK), but `dumpsys package` on Android 15 prints `appId=` and not `userId=`, so the UID lookup failed.
  This is a harness parsing fault, not an environment failure. Fix: accept either key. Rerun as `pilot-2` with the same
  gate; protocol otherwise unchanged; freeze `frozen-g3-v5b`.
- pilot-2 (22/11 23:00; excluded, no upload ran): stopped at setup again. On a fresh install the app's `files/`
  directory does not exist until the app first runs, so writing the CA there failed. This is a harness ordering fault.
  Fix: `run-as mkdir -p files` before the copy. B then checked every remaining setup step by hand on the phone (CA copy,
  standby bucket, `am start` Main, init broadcast, `getprop`, Wi-Fi state), and all succeeded. Rerun as `pilot-3`; freeze
  `frozen-g3-v5c`.
- pilot-3 (22/11 23:01; excluded): **PILOT GATE FAIL**. Setup worked; 8/9 cells were valid and 16/16 of their uploads
  ended SEND_OK with the receiver logging them complete. Three causes:
  1. **Transient adb error.** The first cell had a harness error before its first upload: an adb command returned non-zero
     with an empty stderr, and the harness did not record which command. The same sequence run by hand on the phone
     succeeded at every step.
  2. **Batterystats format on Android 15.** The text shows only `  u0a405:`; the UID's estimate is in the checkin line
     `9,<uid>,l,pwi,uid,<mAh>,…`, which the parser did not read. In every pilot cell the estimate was 0 mAh.
  3. **B's own error in the chain.** Editing the gate's pilot path commented out the `meta = …` statement, so the gate
     crashed before printing. Fixed, and the corrected gate was run on the pilot-3 data: 9 cells, 8 valid, 16/16 uploads
     ok and received, 8 cells with a batterystats record. It fails only on item 1.
- **G3d protocol v2** (22/11 23:04, before any final; arms, cells, N, measures and gate items unchanged):
  - **adb retry:** an adb command that fails with an empty stderr is retried once after 1 s, and the retry is logged per
    cell (`adb_retries`). Any other failure raises with the command and its stderr recorded. Uploads are never retried;
    each upload is still one send;
  - **parser:** `analyze_g3cost.mah` reads the old text format, else the checkin `pwi,uid` value. **0 counts as a reading
    and is reported as 0.** The gate's "batterystats UID line" item uses this parser;
  - unit test `test_mah_android15`. Fake-adb end-to-end check ok;
  - rerun as `pilot-4`; freeze `frozen-g3-v5d`;
  - **expected limitation, stated before the final:** the per-cell energy estimate may be 0 mAh at this cell length. If
    so, it is reported as such (counts of zero cells), never imputed or replaced by another proxy after the fact.
- pilot-4 (v2, 22/11 23:05; excluded): gate passed (9/9 valid, 18/18 uploads ok and received, 9 cells with a
  batterystats record).
- final (v2, 23:05–23:27): **ENVIRONMENT FAILURE, not used** (retained, excluded; its `analysis/` output is not a result).
  - From about 23:15 (block 5) every upload failed to reach the receiver (ConnectException, "connection abort"). The phone
    screen was off and the phone dozing (`mWakefulness=Dozing`, `mStayOn=false`).
  - The cause is B's harness design: `svc power stayon usb` holds the screen only while USB counts as plugged, and
    `dumpsys battery unplug` makes it count as unplugged. The 1-minute pilots ended before the screen timeout.
  - At about 23:27 the phone left adb, and the harness ran the remaining cells into errors (115/180 invalid). Its restore
    commands could not reach the phone.
- **G3d protocol v3** (22/11 night, before any v3 trial; arms, cells, N, measures unchanged):
  - **stay-on:** `svc power stayon true`, restored to false at the end;
  - **validity:** each cell records `mWakefulness` at its start and end, and a cell is valid only if both are Awake
    (`analyze_g3cost.valid`, harness field; unit test `test_valid_v3_wakefulness`);
  - **device loss:** an adb error "not found / offline / no devices" stops the run (DeviceLost) instead of running cells
    into errors;
  - fake-adb checks: normal 18/18 valid; dozing 0/18 valid; device lost stops after the current cell;
  - **rerun:** pilot `pilot-5` (same gate) → final `final-v3`, all 20 blocks from block 0, the v2 final not pooled;
    analysis `analysis-v3`; freeze `frozen-g3-v5e`, then `frozen-g3-v6b` (shared with P4, whose transport line change touches no G3d file; same APK g3-apk 8f723ead…).

- final-v3 (v3, 23/11 15:31–15:50; **not usable, harness design fault (B)**): blocks 0–4 and the first 8 cells of block 5
  (53 cells) ran with the phone Awake at start and end; from cell 53 (block 5, 15:41:25) the phone was Dozing at cell start,
  and every upload ended `ConnectException` to the receiver. Diagnosis (manual, harness and phone state only):
  - `dumpsys battery unplug` makes the phone count as unplugged (`USB powered: false`), so `svc power stayon true`
    (stay on *while plugged in*, any source) did not hold;
  - the screen went off at the phone's 10 min `screen_off_timeout` (600,000 ms) and the phone entered deep Doze
    (`mState=IDLE`), which blocks the app's network; adb shell still reached the Mac (ping 10 ms, TCP 8800 ok) and the
    receiver was listening, so the receiver was not at fault;
  - the v3 validity rule flags these cells (Dozing at start); 10 such cells were logged before B stopped the run at 15:50 (SIGINT).
  The phone was restored (`dumpsys battery reset`, `svc power stayon false`). final-v3 is kept as recorded and not pooled.
- **G3d protocol v4** (23/11, before any v4 trial; arms, cells, N, measures and analysis unchanged):
  - `cost_suite.py`: after `battery unplug`, `settings put system screen_off_timeout 86400000` and
    `dumpsys deviceidle disable all`, restored at the end (the previous timeout value is read first);
  - the applied values are read back into `meta.json` `power_check`;
  - pilot gate (`g3d-chain.sh`) additionally requires `power_check` = timeout 86400000 and light/deep idle disabled;
  - rerun: pilot `pilot-6` → final `final-v4`, all 20 blocks from block 0; analysis `analysis-v4`; freeze `frozen-g3-v7`;
  - Threat (construct): with Doze off and the screen kept on, the cost is measured with the app in the foreground and the
    screen on, as the card already states; background or idle cost is not measured.
- **Order and freeze (23/11, user decision):** G3c v5 (`plans/g3app5-card.md`) runs first and G3d v4 after it. The G3d
  manifests now point to `frozen-g3-v8b` (made for G3c v5b); every G3d file (cost_suite.py, analyze_g3cost.py, g3d-chain.sh,
  receiver) is identical to v7b, so G3d protocol v4 is unchanged.

## 6. Outcome (after the run)
