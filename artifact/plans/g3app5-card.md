# Experiment card — G3c protocol v5: stockcancel with a 16 KiB send buffer (stockcancel16) vs stockcancel vs fenced

Status: written 23/11, before any v5 trial; frozen at the commit that adds it (`results/round3/g3/frozen-g3-v8`). Chain
`plans/autorun/g3-g3c5-chain.sh` (v5c: `g3-g3c5c-chain.sh`; calibration pilot → gate → mechanism pilot → gate → final). Owner: B (Duy).
Source: the leader's request in issue #7 (23/11 13:20 UTC, relayed by C). The request fixes the new build (`stockcancel16`:
stockcancel with OkHttp `SO_SNDBUF` 16 KiB set by a `SocketFactory` before connect), the three builds in the same trials
(stockcancel16, stockcancel, fenced), "as G3c v4" (body ≈ 256 KiB, umts, the app's own withdrawal path at u·D from a fixed
seed, capture and marker oracle, 30 trials per build), logging `getSendBufferSize()` after connect for every build, the
primary and secondary estimands, and that every result is reported. G3c v4 data stay unchanged. The user moved G3d v4 to
after this run (23/11). Everything else below is a B decision made before any v5 data.

## 1. Question and claim
- Question: in AirGuard on the emulator, with the same 16 KiB send buffer as fenced, does cancelling the in-flight call
  (`Call.cancel()`) stop the sink from receiving the whole donation, compared with the fence?
- Can support: AirGuard at commit d515c534 with the B2/G3 test integration, the donation path, umts, these three builds,
  N = 30 per build, emulator.
- Cannot support: other buffer levels, the app's other network paths, other cancellation designs, phones. 0/N is not an
  impossibility guarantee. No p-values.

## 2. Design
- **Builds** (`realapp/airguard/build_g3.sh` with `VARIANTS='stockcancel16 stockcancel fenced' OUTDIR=build/g3v5`, from a
  fresh copy of the clean checkout; sha256 in `build/g3v5/SHA256SUMS`, meta.json and the freeze):

  | Build | Package suffix | Sink port | Donation path |
  |---|---|---|---|
  | `stockcancel16` | `.p04stockcancel16` | 8794 | stockcancel + `OkHttpClient.Builder.socketFactory(G3.SndBuf16)`: `setSendBufferSize(16384)` on the unconnected socket |
  | `stockcancel` | `.p04stockcancel` | 8793 | as v4 (OkHttp, kernel default buffer; in-flight registry + `Call.cancel()`) |
  | `fenced` | `.p04fenced` | 8797 | as v4 (ResidueDroid HttpTransport, 16 KiB, chunk fence) |

- **Change against the v4 builds, identical for all three (logging only):** every build logs `SOCKET_CONFIG` with
  `actual_sndbuf = getSendBufferSize()` after connect:
  - OkHttp builds: a network interceptor `G3.SockLog` (one event per request, with the path);
  - fenced: one `events.emit` appended to the connect line of the app clone's copy of HttpTransport (`apply_g3.sh`);
    `artifact/transport` itself is unchanged.

  Because of this the v5 stockcancel and fenced APKs differ from v4; v5 compares builds only within v5.
- **Driver** `followup/race_airguard.py --variants stockcancel16,stockcancel,fenced --apkdir realapp/airguard/build/g3v5`,
  seed `g3app5-20261123` (new seed: a new run, so the u values and build order are new), per trial k the three builds in an
  order shuffled from the seed, one u per trial shared by the builds. Per build exactly as v4 (startup worker wait, insert,
  start marker, run, withdrawal at u·D_build, wait for the end event, force-stop).
- **N beacons** fixed at 2,233 (the N of v4's passed calibration, body 262,625 B). **D_build** from the v5 calibration
  `pilot-v5-calib` (3 sends per build without withdrawal; median host time run hook → sink donate_data).
- Network umts (128 kbit/s, 118 ms), marker port 8799 unshaped; capture `-tcpdump` at emulator launch. AVD P04AvdA on
  emulator-5666 (`-read-only`). Nothing else runs on the host's emulators during v5.
- **N:** 30 trials (90 build-trials).

## 3. Gates, validity, stopping, replacement
- **Calibration gate (mechanical):** every build has 3 calibration samples; every D_build ≥ 5 s; median body ≥ 200 KiB. No
  recalibration (N is fixed); any failure → no final, reported in issue #7.
- **Mechanism pilot `pilot-v5-mech`:** 2 trials (6 build-trials), excluded. Gate: as v4 (every build-trial valid,
  MARKER_SENT without error, start marker ok, every marker in marker.jsonl and in the pcap) plus: every build-trial has a
  donation `SOCKET_CONFIG`, and `actual_sndbuf` = 16384 for stockcancel16 and fenced. If stockcancel16 does not show 16384
  (e.g. OkHttp ignored the factory), there is no final and B reports it in issue #7.
  The gates never read bytes after the marker, sink completion, placement, cancel outcome or latencies.
- **Validity:** v4 rules (`analyze_g3app.validity`). First 30 valid per build in k order.
- **Stopping and replacement:** stop after 30 trials. Environment or harness failures only (emulator crash, failed hook,
  dead device), whole trials (all three builds) from k = 30, at most 3; a harness fix means a new protocol version and a
  fresh directory, and the old directory is kept and reported. Never because of an outcome.

## 4. Analysis (`followup/analyze_g3app5.py`, unit test `followup/test_g3app5.py`, written before any v5 trial)
- **Primary:** per build, trials in which the sink logged donate_data complete after the app's marker arrived and before
  the same build's next start marker (host clock on both sides), Wilson 95 % over trials whose marker reached the log.
  Paired per trial k (2×2 counts): stockcancel16 vs fenced; also stockcancel16 vs stockcancel.
- **Secondary:**
  - capture: trials with TCP payload to the build's sink port after the marker SYN (v4 primary) with Wilson 95 %, payload
    bytes after the marker (sum, per trial median / nearest-rank p95 / max), split by where the withdrawal fell (device
    clock: before the donation start, during, after its end);
  - `Call.cancel()` cut an in-flight call: CANCEL_DONE calls ≥ 1 and DONATION_ERROR after it; calls = 0 counted apart;
  - fenced: the app oracle (BYTES_ACCEPTED n > 0 after WITHDRAW_DONE) and BLOCK events;
  - `actual_sndbuf` of the donation socket per build; end events; placement.
- Output `results/round3/g3app/analysis-v5/g3app5-summary.json`.

## 5. Threats
- **Internal:** builds run one after another within a trial; host-timed W; D includes the worker start, ping and token, so
  some withdrawals fall before the donation (reported as placement); logging adds one event per request.
- **Construct:** the capture boundary is the guest NIC; "complete" is the sink reading the whole body (plain HTTP sink);
  the ack is WITHDRAW_DONE in the test hook.
- **External:** one app, one path, one link, emulator; stockcancel16 is one way to bound OkHttp's buffer.
- **Conclusion:** N = 30 per build; descriptive.

## Correction found while writing this analysis (23/11, before any v5 trial)
The unit test for the primary showed that `analyze_g3app.py` (v4) counted "sink logged complete after the marker" with a
window of marker + 600 s. The sink port is per build and the next trial of the same build starts about 75–100 s later, so
a later trial's completed donation could count for earlier trials. Fixed (`analyze_g3app.receiver_complete`: window ends
at the same build's next start marker; unit test `test_g3app.test_receiver_window`, fails without the fix). Rerun on
final-v4 into a new directory `results/round3/g3app/analysis-v4-r2` (analysis-v4 kept): the only change is
**fenced 5 → 1** (stock, stockcancel, layered stay 30). Over the whole v4 run the sink logged exactly one complete fenced
donation, the trial with DONATION_OK. The v4 reading "at least 4 blocked trials whose last bytes were already in flight"
is withdrawn. Reported in issue #7.

## Pilot log
- pilot-v5-calib (23/11 21:27–21:33; excluded): calibration gate passed (3 samples per build; D stockcancel16 24.0 s,
  stockcancel 18.2 s, fenced 18.0 s; body 262,625 B).
- pilot-v5-mech (21:33–21:36; excluded): **MECHANISM GATE FAIL**, so no v5 final. Every other check passed (6/6 valid,
  markers in log and capture). `actual_sndbuf` of the donation socket was 16384 for fenced, **32768** for stockcancel16 and
  2097152 for stockcancel. Diagnosis (B, from the logged values, not outcomes): `getSendBufferSize()` reports different
  units by API. Linux stores twice the requested SO_SNDBUF; `java.net.Socket` (OkHttp) returns the kernel value, while the
  NIO `SocketChannel` adaptor (HttpTransport) returns half of it (OpenJDK behaviour on Linux). stockcancel's 2097152 is the
  1 MiB that P4 saw through NIO. So the factory worked, but the gate compared values in different units: a gate design
  fault, not an environment failure. v5 directories are kept and not pooled.
- **Protocol v5b** (23/11, before any v5b trial; builds, design, N, seed, analysis otherwise as v5):
  - every build also logs `kernel_sndbuf`, read by the same call in every build (getsockopt on a dup of the socket fd via
    reflection, `G3.kern`; on failure `-1;kernel_err=<class>`); new APKs `realapp/airguard/build/g3v5b` (sha256 stockcancel16
    266d26b4…, stockcancel 5061f227…, fenced bcd96ab4…);
  - mechanism gate: every build-trial has `kernel_sndbuf` > 0, and stockcancel16 and fenced both have 32768 (= 2 × 16384);
  - a new calibration (the APKs changed); directories `pilot-v5b-calib`, `pilot-v5b-mech`, `final-v5b`,
    `calibration-used-v5b.json`, `analysis-v5b`; chain `plans/autorun/g3-g3c5b-chain.sh`; manifests `g3app5b-*.json`; freeze
    `frozen-g3-v8b` (G3d manifests repointed to it; G3d files unchanged).
  - The analysis reports both `donation_sndbuf` (API units) and `donation_kernel_sndbuf`.
- pilot-v5b-calib (23/11 21:41–21:47; excluded): calibration gate passed (D 18.2 / 18.3 / 18.0 s; body 262,625 B).
- pilot-v5b-mech (21:47–21:51; excluded): **MECHANISM GATE FAIL**, no v5b final. All other checks passed; every build-trial
  logged `kernel_sndbuf=-1;kernel_err=NoSuchMethodException`: API 33 blocks the hidden `getsockoptInt` through reflection.
  A harness measurement fault. (API units again: fenced 16384, stockcancel16 32768, stockcancel 2097152.)
- **Protocol v5c** (23/11, before any v5c trial; builds = the v5b APKs `build/g3v5b`, whose in-app `kernel_sndbuf` is -1 by
  construction and is not used; design, N, seed and analysis otherwise as v5):
  - the harness reads the kernel send buffer itself (`race_airguard.py --sockdiag`): from the run hook until the build-trial
    quiesces it polls guest `ss -tmn dport = :<sink port>` (iproute2, checked on the image) every 1 s and keeps the first
    socket with Send-Q ≥ 4096 (the donation body; ping and token requests are small); `skmem tb` is the kernel sndbuf. Same
    read for every build, independent of the app; used in every v5c stage;
  - calibration gate (no withdrawal there, so every send has a body socket): in addition to v5's checks, all 9 calibration
    sends have a `tb`, and it is 32768 (= 2 × 16384, Linux doubles the requested value) for every stockcancel16 and fenced send;
  - mechanism gate: v4 checks, and the ss poller ran in every build-trial (its value is not re-checked: a withdrawal can fall
    before the donation starts);
  - analysis adds `donation_sockdiag_tb`; directories `pilot-v5c-calib`, `pilot-v5c-mech`, `final-v5c`,
    `calibration-used-v5c.json`, `analysis-v5c`; chain `g3-g3c5c-chain.sh`; manifests `g3app5c-*.json`; freeze `frozen-g3-v8c`
    (G3d manifests repointed; G3d files unchanged).
  - Threat (internal): the poll adds one adb shell call per second during each build-trial, the same for every build.

## 6. Outcome (after the run)
- Written 23/11 after final-v5c (22:04–22:39; chain `g3-g3c5c-chain.sh`, calibration and mechanism gates passed). Source:
  `results/round3/g3app/analysis-v5c/g3app5-summary.json` (`analyze_g3app5.py final-v5c`; the committed slim capture gives the
  same JSON). Raw: `trials.jsonl`, `sink/ingest.jsonl`, `marker.jsonl`, `capture-slim.pcap` + sha256 of the full pcap.
- **Seed actually used: `g3app5c-20261123`**, not `g3app5-20261123` as §2 says. The v5b and v5c manifests were made by text
  replacement of `g3app5-` and that also changed the seed string. It was fixed in the frozen manifest before any trial and was
  not chosen by any outcome; it only changes the u values and build orders.
- Trials: 90 logged; **2 invalid** (`g3app-010-stockcancel`, `g3app-010-stockcancel16`: no donation end event). In trial 10,
  u < 0.01, so the withdrawal ran about 0.1 s after the run hook, before the app's worker started; the stock worker then did
  not donate at all. This is the validity rule, not an environment failure, so there is no replacement (§3): 29 trials for
  stockcancel16 and stockcancel, 30 for fenced; 0 unused. (In the same trial the fenced worker still started and was blocked
  at its first chunk.)
- **Kernel send buffer of the donation socket** (guest `ss`, skmem tb): stockcancel16 32768 in 29/29, fenced 32768 in 27/30
  (3 missing: the withdrawal fell before the donation started and the fence blocked at the first chunk, so no socket ever had
  Send-Q ≥ 4096), stockcancel 2097152 in 29/29. stockcancel16 and fenced had the same buffer.
- **Primary, sink logged the donation complete after the marker:**

  | Build | complete after ack | Wilson 95 % |
  |---|---|---|
  | stockcancel16 | 4/29 | 5.5–30.6 % |
  | stockcancel | 28/29 | 82.8–99.4 % |
  | fenced | 2/30 | 1.8–21.3 % |

  Paired per trial (29 pairs): stockcancel16 vs fenced 23 both 0, 4 stockcancel16 only, 2 fenced only; stockcancel16 vs
  stockcancel 24 stockcancel only, 4 both, 1 both 0. Counts, no p-values.
- **Secondary:**
  - capture, trials with payload to the sink after the marker: stockcancel16 27/29 (78.0–98.1 %), stockcancel 27/29
    (78.0–98.1 %), fenced 28/30 (78.7–98.2 %);
  - payload bytes after the marker, sum / per-trial median / p95 / max: stockcancel16 727,501 / 17,520 / 26,280 / 262,953;
    stockcancel 3,418,126 / 122,465 / 183,960 / 262,951; fenced 566,532 / 21,900 / 24,536 / 24,921;
  - placement: stockcancel16 during 27, after the end 2; stockcancel during 29; fenced during 27, before the start 3;
  - `Call.cancel()` cut an in-flight call: stockcancel16 26/29 (3 with calls = 0), stockcancel 28/29 (1 with calls = 0);
  - fenced: BLOCK in 28/30, app oracle 0/30, end events DONATION_BLOCKED 28, DONATION_OK 2.
- **Reading (B, descriptive):** with the same 32 KiB kernel buffer, Call.cancel() and the fence give about the same result on
  the primary (4/29 vs 2/30), and both leave about one buffer of payload after the ack (medians 17,520 B and 21,900 B). With
  the default buffer (2 MiB here) cancel does not stop the sink from receiving the body (28/29). The v4 gap between
  stockcancel (30/30) and fenced (1/30) therefore came mainly from the send buffer size, not from where the check sits.

- **Correction (C's independent check, issue #7, 23/11):** the donation body is not always 262,625 B. Among the bodies the
  sink logged complete (`followup/body_sizes_g3app.py` → `analysis-v5c/body-sizes.json`): final-v5c 262,625 B in 33 of 37
  records, 260,390 B in 3 (stockcancel 2, stockcancel16 1) and 258,155 B in 1 (stockcancel); final-v4 262,625 B in 80 of
  91, 260,390 B in 11 (stock 2, stockcancel 4, layered 5). The sizes differ by multiples of 2,235 B; the cause was not
  examined. No count above changes. Where this card and the v4 card say "body 262,625 B", read "262,625 B in most sends".
  C's own script reproduced every primary count, the paired tables and the v4 correction.

### Exploratory diagnosis (post hoc, B, 23/11; not pre-registered; from event order and the capture)
Per-trial table: `followup/diag_g3app5.py final-v5c` → `results/round3/g3app/analysis-v5c/diag-v5c.json`.
- The 4 stockcancel16 and 2 fenced trials with the sink complete:
  - stockcancel16 trials 1, 2, 5 (u 0.87–0.93): `Call.cancel()` closed the socket ("Socket closed"), but 245,765–261,825 B
    had left before the marker and the remaining 1,285–17,345 B were already in the kernel buffer, so they still left after
    the ack and the sink had the whole body;
  - fenced trials 13 and 20 (u 0.96–0.97): DONATION_OK, the fence's last chunk had been written before the withdrawal; 0 and
    1,747 B after the marker;
  - stockcancel16 trial 12 (u 0.02): the withdrawal came 40 ms after DONATION_START but before the call reached OkHttp's
    interceptor (SOCKET_CONFIG 190 ms later), so the in-flight registry was empty (calls = 0), the call then ran to the end
    and the whole body (262,953 B) left after the ack. In the three fenced trials with the withdrawal before the donation
    start, the fence blocked at the first chunk.
- So "complete at the sink" here mostly means that the withdrawal fell inside the last buffer-worth of the upload, which no
  user-space design can recall. The one structural difference seen is the registration window of the cancel design (1 trial).
  In the same trials k (1, 2, 5) fenced was not complete; at the same u each build was at a different point of its upload
  (D and progress differ per build), so this is timing, not a measured design effect.
