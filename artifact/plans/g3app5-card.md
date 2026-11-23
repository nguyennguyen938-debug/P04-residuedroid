# Experiment card — G3c protocol v5: stockcancel with a 16 KiB send buffer (stockcancel16) vs stockcancel vs fenced

Status: written 23/11, before any v5 trial; frozen at the commit that adds it (`results/round3/g3/frozen-g3-v8`). Chain
`plans/autorun/g3-g3c5-chain.sh` (calibration pilot → gate → mechanism pilot → gate → final). Owner: B (Duy).
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

## 6. Outcome (after the run)
