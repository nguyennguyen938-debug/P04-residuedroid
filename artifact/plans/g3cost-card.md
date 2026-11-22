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
- Network: Wi-Fi. The receiver is a TLS 1.2 server on this Mac's LAN address (192.168.1.20 on 22/11), port 8800, using a test certificate with
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

## 6. Outcome (after the run)
