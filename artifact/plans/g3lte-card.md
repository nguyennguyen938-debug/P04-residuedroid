# Experiment card — P3 (group 3 follow-up): G3a on lte with balanced withdrawal timing (protocol v4 of G3a/G3b)

Status: written 22/11 evening, before any P3 trial; frozen at the commit that adds it (`results/round3/g3/frozen-g3-v4d`).
The order is pilot (1 block) → mechanism + balance gate → final; chain `plans/autorun/g3-chain-v4.sh`, after G3c v4. Owner: B (Duy).

Source: B's request in issue #7 (22/11), approved by the leader (22/11 13:12 UTC: "Leader duyệt cả hai: P3 và P4"). The
request followed the exploratory method audit of G3a v3 (`followup/audit_g3race.py`, written after the v3 outcomes were
read). On lte, the withdrawal through `:revision` reached W about 0.1 s after SOCKET_CONFIG, against about 0.03 s for the
in-process `close2`. With a median u·D of 0.03 s, W fell during the writes in 16/30 close2 trials but in only 8–9/30 trials
of every other arm.

**The v3 numbers stay reported unchanged next to P3.** P3 is a new protocol version in new directories, and it is not
pooled with v3.

## 1. Question and claim
- Question: with the same withdrawal timing for every arm on lte, how many trials of each arm accept bytes after W?
- Can support: lte with exposure balanced across the five arms; the same build, seed and estimand as G3a.
- Cannot support:
  - a change to the v3 counts;
  - claims about edge or umts, which P3 does not run and which were balanced in v3;
  - other cancellation designs.

  0/N is not an impossibility guarantee. Zero-vs-zero is reported as counts.
- **No direction is assumed.** The audit suggests more exposure for early and close, which does not predict any count.

## 2. Design (as G3a v3 unless stated)
- **Arms:** early, close, close2, fence, fence-abort, all five in every block.
- **Build, data and seed:**
  - the build `fixture/build/g3-apk/rl-tls.apk` (same sha256 as G3a);
  - `--g3`, marker 8799, capture via `-tcpdump`, `--radio`, `--shaper tc`;
  - profile **lte only**, sizes 32 KiB / 256 KiB / 2 MiB;
  - seed `race-20261119`, so the same u per (block, lte, size) as G3a;
  - durations from `results/round3/g3race/pilot-calib/calibration.json` (as G3a; the send path is unchanged);
  - deadline max(10 s, 4·D + 20 s).
- **Change 1, `--warm-revision`:** after `init` and before the send of every trial of every arm (close2 included), one
  no-op broadcast to `RevisionRemote` (`op=noop`; the fixture ignores unknown ops) starts the `:revision` process. The
  reply is logged as `warm`.
- **Change 2, `--qsnap` (P2, leader-approved):** right after the withdraw broadcast returns, one host-timed snapshot of
  `tc -s qdisc` and of the guest TCP send queues to :8798 (`/proc/net/tcp{,6}`). It is taken after WITHDRAW_ACK and the
  marker, not at the ack, and is the same for every arm.
- **N:** 10 blocks of 15 cells → 30 trials per arm (10 per size), 150 trials. AVD P04AvdA on emulator-5660 (`-read-only`),
  receiver 8798, marker 8799. No other emulator runs at the same time.

## 3. Gates, validity, stopping, replacement
- **Pilot `pilot-lte4`:** 1 block (15 trials), excluded. The gate is mechanical and reads only harness, mechanism and
  timing fields, never violations, bytes or latencies:
  - all 15 trials valid (B10 rule);
  - close: CANCEL and CANCEL_DONE reply=ok;
  - close2: CANCEL_DONE `inproc`;
  - MARKER_SENT and a marker.jsonl line in every trial;
  - the marker and the request SYN in the capture;
  - `warm` reply ok and a `qsnap` present in every trial;
  - **balance, per payload size:** for each size, the arms' values of (WITHDRAW_REQUEST − SOCKET_CONFIG) on the device
    clock differ by at most 15 ms. The pilot has one trial per (size, arm), and the gate is checked per size because C
    found the v3 imbalance in one size: on lte, W fell during the writes at 256 KiB in close2 7/10 vs 0/10 for the other
    arms; at 2 MiB 8–9/10 in every arm; at 32 KiB 0/10 in every arm. In v3 the gap was about 70–80 ms. Added 22/11
    (C's review in issue #7) before any P3 trial; re-frozen as `frozen-g3-v4d`.

  Fail → no P3 final, reported in issue #7. A fix needs a new version and a new pilot.
- **Validity and selection:** B10 validity; first 30 valid per arm in block order.
- **Stopping and replacement:** stop after 10 blocks. Replacement for environment failures only: whole blocks from
  index 10, at most 3. A pause or interruption uses the G3a rule: a fresh directory, and only blocks complete within
  their directory are analysed.

## 4. Analysis (pre-registered)
- **Primary:** `analyze_g3race.py final-lte4`, the same primary as G3a. Per arm, trials accepted after W, with Wilson 95 %.
- **Secondary:** as G3a.
- **Exposure:** `audit_g3race.py final-lte4` gives the exposure table per arm and per size (W during the writes) and after
  W among exposed trials. Pre-registered here as secondary; it was exploratory in v3. **A size with no exposed trial in
  any arm (expected for 32 KiB, an upload of 4–5 ms) is reported as not testing the race** (C, issue #7).
- **Capture by phase** (C, issue #7): new bytes after the marker, and TLS application_data bytes, split by the W phase:
  before the writes / during the writes / after the handoff / after the end. Only the during-writes part is cut data;
  after-handoff bytes are permitted data that left late.
- **TLS records (P1a, leader-approved):**
  - `tls_records.py` on the full capture writes `capture-tls.jsonl`, committed with the pcap sha256;
  - from it, the capture counts trials and bytes of TLS **application_data** after the marker, next to the raw TCP counts;
  - unit test `test_tls_records.py`.
- **Queues (P2):** `qsnap.py` gives netem backlog and socket send queue per arm, descriptive (median, p95, max).
- **Output:** `results/round3/g3race/analysis-lte4/` (`g3race-summary.json`, `g3race-audit.json`, `qsnap-summary.json`).
  The report places v3 lte and P3 side by side; nothing from P3 replaces a v3 number.

## 5. Threats
- **Internal:**
  - one AVD; host-timed W;
  - the warm-up adds one broadcast per trial to every arm;
  - the snapshot adds one adb call after the ack;
  - runs at night on AC or battery as recorded.
  - G3d runs on the phone in parallel (`g3-tonight.sh`); its receiver and adb share the host, so host load is recorded per trial;
- **Construct:**
  - as G3a; the queue snapshot is taken after the ack, not at it;
  - every send uses `sndbuf=16384`, so bytes after the marker are measured with a 16 KiB send buffer.
- **External:** emulator, fixture, lte profile only.
- **Conclusion:** N = 30 per arm; zero-vs-zero reported as counts.

## Pilot log

- pilot-lte4 (22/11 22:46–22:47; excluded): **BALANCE GATE FAIL**, so no P3 final under v4. Every mechanism field held:
  15/15 valid, cancellations, markers, capture, warm replies and queue snapshots. The per-size spread of
  (WITHDRAW_REQUEST − SOCKET_CONFIG) was 337 / 42 / 19 ms against the 15 ms limit. Diagnosis (manual, timing fields only):
  - in one trial (32 KiB, fence) the send broadcast returned about 3.2 s late (an adb stall, host load 4.1);
  - with one trial per (size, arm), the gate measured per-trial delivery jitter of about ±20–40 ms, not a systematic
    arm difference;
  - in the other 14 trials, WITHDRAW_REQUEST − SOCKET_CONFIG followed the host offset to within about −25 to +23 ms in
    every arm, so the ~70–80 ms `:revision` cold-start gap of v3 did not appear.

  This is a gate design fault (B).
- **Protocol v5** (22/11 night, user decision, before any v5 trial; design, arms, N and analysis unchanged):
  - **pilot** `pilot-lte5`: 3 blocks (45 trials, 9 per arm), excluded;
  - **balance gate v5:** per trial, d = (WITHDRAW_REQUEST − SOCKET_CONFIG, device clock) − (the withdrawal's host offset,
    host clock). This is a difference of two durations, each on its own clock: the delivery delay of the withdrawal
    relative to that of the send, which is what the v3 cold start inflated;
  - trials whose host offset exceeds u·D by more than 1 s (adb stall) are counted and left out of d;
  - pass: per-arm medians of d (at least 5 trials per arm) differ by ≤ 15 ms, plus every v4 mechanism field;
  - **final** `final-lte5` (10 blocks), `analysis-lte5`; chain `plans/autorun/g3-p3v5-chain.sh`; freeze `frozen-g3-v5`;
  - the v4 pilot and its failed gate are reported. Code check: on the v4 pilot data, the v5 metric flags the stalled
    trial and computes per-arm medians.

## 6. Outcome (after the run)
- Written 23/11 after final-lte5 (22/11 22:59–23:02; lte trials last about 0.45 s each, as in v3). **v4 produced no
  final** (balance gate fail, Pilot log). Source: `results/round3/g3race/analysis-lte5/` (`analyze_g3race.py`,
  `audit_g3race.py`, `qsnap.py` on `final-lte5`). Raw: `trials.jsonl.gz` + sha256, `capture-slim.pcap` + sha256 of the
  full pcap, `capture-tls.jsonl` (from the full pcap).
- Trials: 150 logged, 0 invalid, 0 excluded, 30 per arm, 0 unused. Same u in all 30 paired cells; no write tie with W.
- **Exposure is balanced** (W during the writes): early 16, close 18, close2 17, fence 18, fence-abort 18 of 30; by size
  32 KiB 0 in every arm (**32 KiB does not test the race**), 256 KiB 8–9, 2 MiB 8–9. Median WITHDRAW_REQUEST −
  SOCKET_CONFIG 0.027–0.031 s per arm, median u·D 0.03 s (v3: about 0.1 s for the `:revision` arms).
- **Primary, trials accepted after W** (of 30), with G3a v3 lte unchanged next to it:

  | Arm | P3 v5 | Wilson 95 % | among exposed | v3 lte |
  |---|---|---|---|---|
  | early | 16 | 36.1–69.8 % | 16/16 | 9 |
  | close | 18 | 42.3–75.4 % | 18/18 | 8 |
  | close2 | 0 | 0–11.4 % | 0/17 | 0 |
  | fence | 0 | 0–11.4 % | 0/18 | 0 |
  | fence-abort | 0 | 0–11.4 % | 0/18 | 0 |

  By size: early 0 / 8 / 8, close 0 / 9 / 9 (32 KiB / 256 KiB / 2 MiB). Paired: close2 vs fence 30 both 0; fence-abort vs
  fence 30 both 0; close2 vs early 14 both 0, 16 early only; close2 vs close 12 both 0, 18 close only. Zero-vs-zero is
  counts, not equivalence; 0/30 is not an impossibility guarantee.
- With exposure balanced, the v3 lte reading "close2 cuts more requests than fence" does not hold: both have 0 accepted
  after W, and the cross-process `close` accepts after W in every exposed trial on lte.
- Secondary:
  - violations after the ack: early 16 (10,007,288 B), every other arm 0;
  - ack latency (ms, median / p95 / max): early 1.24 / 5.50 / 7.04; close 3.63 / 6.36 / 6.79; close2 1.10 / 2.99 / 3.14;
    fence 2.10 / 10.37 / 10.52; fence-abort 1.55 / 12.36 / 17.34 (descriptive order statistics);
  - uncut requests the receiver logged complete while the app ended SEND_ERROR: close 1, every other arm 0;
  - close2 `CANCEL_DONE inproc` 30/30 (1 already handed off); close CANCEL_DONE reply=ok 30/30; fence-abort ABORT_ARMED 18.
- **Capture** (all 150 matched; every after-marker byte is in the "during writes" phase; after-handoff and after-end 0):

  | Arm | trials TCP new bytes after marker | new bytes | trials TLS application_data after marker | app bytes | RST after marker |
  |---|---|---|---|---|---|
  | early | 16 | 10,079,465 | 16 | 10,079,465 | 0 |
  | close | 4 | 16,897 | 3 | 5,159 | 7 |
  | close2 | 10 | 86,421 | 10 | 61,845 | 14 |
  | fence | 3 | 13,623 | 2 | 4,765 | 19 |
  | fence-abort | 3 | 19,897 | 3 | 11,705 | 17 |

  Capture-only trials (bytes leave the NIC after the marker although the app logged no byte accepted after the ack):
  close 4, close2 10, fence 3, fence-abort 3. **Unfavourable for the fence:** with a 16 KiB send buffer, application data left
  after the marker in 2 of 18 exposed fence trials (4,765 B in total) and 3 of 18 fence-abort trials (11,705 B in total);
  close2 in 10 of 17 (61,845 B).
- Queues (snapshot after the ack): netem backlog and socket send queue 0 in every trial of close, close2, fence and
  fence-abort; early p95 9,084 B backlog and 15,581 B send queue (max 17,016).
- Threats as §5 (sndbuf 16 KiB in every send; snapshot after the ack, not at it).
