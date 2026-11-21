# Experiment card — G2a (group 2): early check that closes the socket on withdrawal (protocol v1)

Status: written 21/11 23:xx, before any G2a trial; frozen at the commit that adds it (calibration pilot → throttle gate →
mechanism pilot → mechanism gate → final; chain `plans/autorun/g2-chain.sh`). Owner: B (Duy).
Source: PR #4 "Not in this PR: Group 2 needs new runs by B: an early check that closes the socket on withdrawal" and
§7b ("We did not measure an early check that closes the socket on withdrawal; it would stop like the fence, but needs a
cancellation path to every in-flight request"). Leader decision 21/11 (user: "nhận luôn, leader đã quyết, chạy 2 thí nghiệm
mới"). The plan gives no design; every choice below is a B decision (standing grant), made before any data.
B7 freeze: reopened for group 2 only; frozen round-3 data are untouched; G2 outputs go to new directories.

## 1. Question and claim
- With the B10 natural race (no barrier, withdrawal at a uniform point of a real-size upload on a shaped link), does a
  layered early check plus a cancellation path that closes in-flight sockets before the withdrawal is acknowledged keep
  bytes from being accepted after the acknowledgement, as the chunk fence does? What does it cost (lost permitted part,
  acknowledgement latency)?
- Can support: emulator, TLS fixture app, the B10 v3 profiles and sizes, this cancellation design, N trials per cell; a
  paired comparison of close with early and fence inside the same blocks.
- Cannot support: other cancellation designs (e.g. an asynchronous cancel that does not wait before acknowledging, OkHttp
  `Call.cancel()`), cancellation paths in real apps, phones, server processing, energy. 0/N is not an impossibility guarantee.

## 2. Design (B10 protocol v3 unless stated)
- Modes, all three in every block: `early` (layered early check, B10), `close` (the same early check + cancellation path),
  `fence` (ChunkFence per socket write, B10).
- `close` (comparator code `fixture/src-cmp/org/residuelab/CancelPath.java`, not ResidueDroid, not counted by impLoc):
  1. the request registers a cancellation token before its early check;
  2. the transport hands the socket channel to the token right after opening it (new `TlsTransport.post` overload with an
     `onOpen` callback; the old signature is unchanged and passes null);
  3. the withdrawal (in the `:revision` process, as in B10) commits durably under the policy lock, then sends a synchronous
     ordered broadcast (foreground queue) to the sending process, which closes every registered socket (or marks the token so
     the socket is closed the moment it opens). The ack is emitted after the reply, or after a 5 s timeout (logged
     `CANCEL_DONE reply=timeout`; the trial stays valid and the timeout is reported);
  4. a request whose check runs after the commit is blocked by the check itself (EARLY_BLOCK).
  The withdrawal broadcast carries `cancel=true` only in close trials, so early and fence withdrawals are as in B10.
- Build: `fixture/build/g2close-apk/rl-tls.apk` (package `org.residuelab.tls`, `VARIANTS=tls`), one build for all three
  modes; sha256 recorded in meta.json and in the freeze directory. Revision.java call sites appended to existing lines
  (B10 precedent), impLoc unchanged (1,251).
- Profiles, shaping, payloads, deadline rule: as B10 v3 (`--radio --shaper tc`; edge/umts/lte; 32 KiB / 256 KiB / 2 MiB;
  deadline max(10 s, 4·D + 20 s)). Seed `race-20261119` (the B10 seed, so W = u·D uses the same u per (block, profile,
  size) as B10; the block order differs because each block now has 27 cells).
- Calibration (pilot `pilot-calib`): 3 sends per (profile, size), fence, no withdrawal, deadline 600 s → D per cell.
- N: 10 blocks → **30 trials per (profile, mode)**, 10 per size; 270 trials. AVD P04AvdA (android-33 google_apis arm64)
  on emulator-5660 (`-read-only`), receiver on host 8798. Run alone on the Mac (no other emulator during G2a).

## 3. Gates, validity, stopping, replacement
- Throttle gate (after calibration; as B10 v3): median D(edge, 2 MiB) ≥ 3 × D(lte, 2 MiB) and D(umts) ≥ 1.5 × D(lte).
  Fail → no final, reported.
- Mechanism pilot `pilot-mech`: 1 block (27 trials) with the calibrated D; excluded from analysis. Gate (mechanical,
  harness/mechanism fields only, no violation or byte count read): every trial valid by the B10 rule, and every close trial
  has a CANCEL event and `CANCEL_DONE reply=ok`. Fail → no final, reported; a fix needs protocol v2 and a new pilot.
- Trial validity, first-N selection: as B10 (`analyze_race.validity`; first 30 valid per (profile, mode) in block order).
- Replacement: environment failures only, whole blocks from index 10 (`--start 10`), at most 3. Never outcome-driven.

## 4. Analysis (`followup/analyze_g2close.py`, written and code-checked on B10 data before any G2a trial)
- Primary: violating trials per (profile, mode) = BYTES_ACCEPTED n > 0 after the first WITHDRAW_ACK (device clock),
  Wilson 95%. Close is compared with fence and with early as paired 2×2 counts per (block, profile, size). No p-values.
- Secondary (descriptive): bytes accepted after the ack; end events; cut trials and receiver-complete requests among them
  (as C's `receiver_race.py`); withdrawal latency WITHDRAW_REQUEST → WITHDRAW_ACK (median, nearest-rank p95, max);
  in-flight write at the ack; close only: cancellation replies and sockets found open.
- Output `results/round3/g2close/analysis/g2close-summary.json`. No SCHEMA keys exist; numbers reach C only if C adds keys
  (then through `make_summary.py`).

## 5. Threats
- Internal: one AVD; host-timed W; guest shaping as B10; the cancellation crosses processes (the fixture withdraws in a
  separate process), which adds broadcast latency that a same-process cancel would not have; fixed block design with
  shuffled cell order; shared host (nothing else runs).
- Construct: acceptance by the device socket, not server receipt (receiver completeness reported separately); a write that
  is inside the kernel when the socket is closed is counted by its BYTES_ACCEPTED event time.
- External: emulator, fixture, one cancellation design. Conclusion: N = 30 per cell; zero-vs-zero is reported as counts.

## Pilot log
- pilot-calib (21/11 22:59–23:04; excluded, no send ran): setup aborted, the first `init` broadcast after install timed out
  at 60 s. Diagnosis (manual, same AVD, 23:05–23:07): the app works (`init` → ok) but its cold start right after boot took
  83 s; host load average 10–12 (other user applications running). Fix (harness only, before any trial, protocol unchanged):
  `race_suite.py` gives that one setup broadcast 300 s and records its duration (`setup_init_s` in meta.json), as B2 pilot-1.
  New freeze `frozen-g2-v2` (only race_suite.py changed); next calibration `pilot-calib2`.

## 6. Outcome (after the run)
- Runs: pilot-calib2 (23:23–23:42, 27/27 SEND_OK; throttle gate passed), pilot-mech (23:42–23:53; mechanism gate passed: 27
  valid, every close trial CANCEL + reply ok), final 21/11 23:53 – 22/11 01:50 (autorun g2close-final, guard 0). Logged /
  invalid / valid / analysed / unused: 270 / 0 / 270 / 30 per (profile, mode) / 0; no replacement. Data `results/round3/g2close/final`,
  analysis `results/round3/g2close/analysis/g2close-summary.json`.
- Violating trials (bytes accepted after WITHDRAW_ACK; Wilson 95%):

  | Profile | early | close | fence |
  |---|---|---|---|
  | edge | 20/30 [0.488, 0.808] | 0/30 [0, 0.114] | 0/30 [0, 0.114] |
  | umts | 21/30 [0.521, 0.833] | 0/30 [0, 0.114] | 0/30 [0, 0.114] |
  | lte | 9/30 [0.167, 0.479] | 0/30 [0, 0.114] | 0/30 [0, 0.114] |

  Paired per (block, profile, size): close vs fence 0/0 in all 90 pairs (zero vs zero: no confirmed difference in 90 paired
  trials, not equivalence); close vs early: 50 pairs early violated and close did not, 40 neither, none the other way.
  Bytes accepted after the ack: early 12.1 MB / 11.0 MB / 5.8 MB (edge / umts / lte), close and fence 0.
- Receiver side, cut trials (ack before the request was handed off): early 20/20, 21/21, 9/9 logged complete; close 0/19,
  0/20, 0/9; fence 0/21, 0/22, 0/9.
- Cost (descriptive):
  - Ends: close SEND_ERROR 27 / 30 / 9 of 30 (edge / umts / lte) vs fence 21 / 22 / 9; early all SEND_OK.
  - Withdrawal latency WITHDRAW_REQUEST → WITHDRAW_ACK, median / p95 / max in ms: close 3.46 / 8.66 / 9.35 (edge), 3.23 / 8.85 /
    10.01 (umts), 2.53 / 3.57 / 4.76 (lte); fence 0.93 / 1.43 / 2.40, 0.93 / 1.54 / 1.85, 0.95 / 3.58 / 3.80; early 0.91 / 1.45 /
    1.55, 0.99 / 1.32 / 1.33, 0.86 / 1.21 / 1.54. Cancellation replies: 90/90 ok, 0 timeouts; sockets found open 66/90.
  - In-flight write at the ack (first post-ack chunk attempted before the ack): early 13 / 14 / 2; close and fence 0.
- Exploratory (`followup/posthoc_g2close.py` → `results/round3/g2close/posthoc/posthoc.json`; defined after the data were seen; not a pre-registered estimand): among trials **not** cut (request handed off
  before the ack), close ended SEND_ERROR in 18 trials whose request the receiver had logged complete (24 others SEND_OK);
  fence 38/38 and early 40/40 such trials ended SEND_OK. Closing the socket also aborts requests that already reached the
  server while the app waits for the response, so the app sees a failure for delivered data (a retry would duplicate it).
  Latency by segment (close, ms, median / max): request → durable 0.85 / 2.47, durable → socket closed in the sender 1.43 /
  7.10, closed → reply 0.52 / 4.26, reply → ack 0.09 / 0.33.
- Comparison with B10 (descriptive, different build and block order, same u per cell): early 20 / 21 / 9 here vs 21 / 20 / 10
  in B10; fence 0/30 in both.
- Reading: with the withdrawal waiting for the cancellation, an early check plus socket close stopped bytes after the ack as
  the fence did, in these 270 trials. It needs a cancellation path to every in-flight request (here a cross-process
  broadcast and a token registered before the check), adds a few ms to the acknowledgement, and aborts requests already
  handed off. Not tested: an asynchronous cancel that does not hold the ack, or cancellation in a real app.
- Deviations: one harness fix after the failed pilot-calib (setup timeout), before any trial (Pilot log). Negative or null:
  close 0/30 and fence 0/30 are not impossibility guarantees (upper bound 11.4% per cell).
