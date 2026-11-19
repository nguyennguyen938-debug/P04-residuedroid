# Experiment card — b10 (test 1, natural race; protocol v1)

Status: frozen at the commit that adds this card; calibration pilot → throttle gate → final (chain `plans/autorun/b10-chain.sh`)
Owner: B (Duy). Plan-silent choices are B decisions (19/11, user: "các quyết định khác bạn chọn").

Source `[R3]` B10: "Payload theo kích thước thật (báo cáo ACRA vài trăm KB, lô analytics, backup vài MB). Giới hạn mạng
emulator ở mức EDGE, 3G, LTE. Thời điểm rút chọn ngẫu nhiên đều trong suốt quá trình upload, không dùng barrier. So layered
early với fence: tỷ lệ trial có byte được nhận sau ack, đối chiếu với Eq. 2". Keys `[RT]`: raceTrials, raceEdgeLayer,
raceEdgeFence, raceThreegLayer, raceThreegFence, raceLteLayer, raceLteFence, racePredPct, raceObsPct.

## 1. Question and claim
- Without a barrier, how often does a withdrawal that lands during a real-size upload on a slow link let bytes be accepted
  after its acknowledgement, under a layered early check vs the chunk fence; does the early rate match Eq. 2?
- Can support: emulator, TLS fixture app, three emulator link profiles, the stated payload sizes, N trials per cell.
- Cannot support: real radios/phones (Test 6 part), real apps, server receipt/processing, energy.

## 2. Design
- App: TLS fixture (`org.residuelab.tls`, `Revision` send op, TLS 1.2 to the in-process receiver on host 8798 via 10.0.2.2).
  Fixture change for B10: optional extra `deadline_ms` (default 10 000 ms unchanged) so long uploads are not cut by the
  fixed deadline; line count unchanged. APK `fixture/build/tls-apk/rl-tls.apk` sha256 ca313b94…ef15 (built 19/11).
- Variants: `early` (layered early: one policy check before sending) vs `fence` (ChunkFence per socket chunk).
- Profiles: emulator console `network speed`/`network delay` = edge/edge, umts/umts (3G), lte/none; set before each trial.
- Payloads (B decision for "real sizes"): 32 KiB (analytics batch), 256 KiB (ACRA report), 2 MiB (backup).
- Withdrawal: W = u·D after the send broadcast, u ~ U(0,1) from seed `race-20261119` (per block, profile, size; the same u
  for early and fence → paired), D = calibrated median upload time of the (profile, size) cell.
- Deadline per trial: max(10 s, 4·D + 20 s). Calibration: 3 sends per (profile, size), fence, no withdrawal, deadline 600 s.
- Blocks: one block = all 18 cells (3 profiles × 2 variants × 3 sizes) once, order shuffled per block from the seed.
- N: 10 blocks → **30 trials per (profile, variant)** (`raceTrials`), 10 per size. AVD P04AvdA (android-33 google_apis arm64,
  the paper's image) on emulator-5660, launched by the suite (`-read-only`).

## 3. Validity, gate, stopping, replacement
- Throttle gate (after calibration, before final; mechanical): for 2 MiB, median D(edge) ≥ 3 × D(lte) and
  D(umts) ≥ 1.5 × D(lte). Fail → no final run; report and switch to a host-side shaper (protocol v2).
- Trial invalid: harness_error; withdrawal not sent; no end event (SEND_OK/SEND_ERROR/EARLY_BLOCK); no WITHDRAW_ACK.
- Analyse the first 30 valid trials per (profile, variant) in block order; later valid ones unused (reported).
- Replacement: environment failures only, new blocks from index 10 (`--start 10`), cap 3 blocks. Never outcome-driven.

## 4. Analysis
- `followup/analyze_race.py` (synthetic test passed 19/11). Violation = BYTES_ACCEPTED n>0 after the first WITHDRAW_ACK
  (device clock). Wilson 95% per cell. Eq. 2: p = clip((c_k − q)/D) per early trial (q = SOCKET_CONFIG, c_k = last accepted
  chunk); racePredPct = mean p; raceObsPct = observed early violation rate, pooled. `race*Layer/Fence` = violating trials.

## 5. Threats
- Internal: emulator link shaping fidelity (gate); host load; fixed receiver; one AVD. Construct: acceptance by the device
  socket, not server receipt; W is host-timed (u·D) while c_k/q are device-timed — only their ratio to D is used.
- External: emulator only; fixture app; three profiles. Conclusion: N = 30 per cell; no p-values.

## 6. Outcome (after the run)
- Logged / excluded / valid / analysed / unused:
- Results directory:
- Deviations:
- Negative or null results:
