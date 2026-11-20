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
- Final (protocol v3, 19/11 20:33–21:59, autorun b10-final4, guard 0): 180 logged, 0 invalid, 180 valid, 30 analysed per
  (profile, variant), 0 unused; no replacement. Data `results/round3/b10/final4` (raw trials.jsonl 119 MB kept on disk,
  committed as `.gz` + sha256 of the original); calibration `pilot-calib4`; analysis `results/round3/b10/analysis/race-summary.json`.
- Violating trials (bytes accepted after WITHDRAW_ACK; Wilson 95%): early (layered) edge 21/30 [0.52, 0.83], umts 20/30
  [0.49, 0.81], lte 10/30 [0.19, 0.51]; fence 0/30 [0, 0.114] for every profile. By size (early, 10 each): edge 4/8/9,
  umts 2/8/10, lte 0/0/10 for 32 KiB / 256 KiB / 2 MiB. Fence trial ends: SEND_ERROR (denied mid-send) 21 / 20 / 12, SEND_OK 9 /
  10 / 18 (edge / umts / lte); early trials all ended SEND_OK.
- Eq. 2: predicted 79.4% vs observed 56.7% early violations (pooled, 90 trials): the prediction overestimates by 22.7
  points. Not explained here; a candidate (not tested) is the host→device withdrawal delivery delay, which makes the
  effective W later than u·D, so fewer windows overlap the remaining upload.
- Deviations: protocol v2 then v3 before any final trial (shaper: guest netem; see below). lte at its nominal 58 Mbit/s is
  as fast as the unshaped link (2 MiB in 0.32 s).
- Negative or null results: the Eq. 2 gap above; fence 0/30 is not an impossibility guarantee (upper bound 11.4%).

## Protocol v2 (19/11, after pilot-calib; no final trial ran)
Throttle gate failed: calibrated 2 MiB medians edge 0.34 s, umts 0.32 s, lte 0.32 s — the emulator console `network speed`
did not shape the app's traffic (the AVD routes data over its virtual Wi-Fi). v2: `race_suite.py --radio` turns Wi-Fi off and
data on before the run (routes and active network recorded in meta.json), so traffic uses the emulated cellular link the presets
apply to; everything else unchanged. New dirs pilot-calib2 / final2; same mechanical gate. If it fails again, a host-side shaper
(macOS dnctl/pf, needs sudo) is the next step (protocol v3).

## Protocol v3 (19/11 20:2x, after pilot-calib3; no final trial ran)
pilot-calib2 aborted before any send (metadata line `dumpsys | grep` exit 1; fixed with `; true`). pilot-calib3 ran: the throttle
gate failed again — 2 MiB medians edge 0.27 s, umts 0.31 s, lte 0.32 s; meta.json routes show the data going over `eth0`
(10.0.2.15) with Wi-Fi off, and the console preset still does not shape it. v3 replaces the console preset by a guest-side
shaper instead of the host dnctl/pf named above (it needs no sudo, touches nothing outside the AVD, and is recorded per trial):
`race_suite.py --radio --shaper tc` applies netem on the guest's egress (upload direction, the one the race is about) of eth0
and wlan0 before every trial, at the emulator's own nominal uplink rate and the midpoint of its delay range: edge 118.4 kbit/s
+ 240 ms, umts 128 kbit/s + 118 ms, lte 58 Mbit/s + 0 ms (`tc qdisc show` stored in each trial's `net`). Feasibility checked on
P04AvdA (tbf and netem accepted on eth0; no trial data). Same profiles, sizes, modes, seed, N, deadline rule, validity rules,
gate and analysis. Construct note: one-way delay only on egress; download direction unshaped (responses are headers only).
New dirs pilot-calib4 / final4. If the gate fails again, B10 stops and is reported as not run on a shaped link.
