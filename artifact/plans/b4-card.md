# Experiment card — b4 (transport cost + test 5 sweep; protocol v1)

Status: frozen at the commit that adds this card; pilot (1 block) → final (chain `plans/autorun/b4-chain.sh`, after B3)
Owner: B (Duy). Plan-silent choices are B decisions (19/11). Cut first if late (plan cut order: test 5 first).

Source `[R3]` B4: "Chi phí transport với thứ tự ngẫu nhiên và tải đồng thời, gộp test 5: chunk 1, 4, 16, 64 KiB × 1, 2, 4, 8,
16 sender. Thiếu giờ máy thì thu lưới lại". Keys `[RT]`: sweepAckSmallMs (1 KiB, 1 sender), sweepAckLargeMs (64 KiB,
16 senders), sweepCpuSmall, sweepCpuLarge (CPU ms/MiB at 1 / 64 KiB).

## Design
- Fixture: fenced plain-HTTP send (Revision op), chunk size and deadline as extras (`HttpTransport.postMode` overload;
  defaults 4 KiB and 5 s unchanged). APK `fixture/build/tls-b4-apk/rl-tls.apk` sha256 1afdfda3…; receiver host 8799.
- Cells: chunk {1,4,16,64} KiB × senders {1,2,4,8,16}; S concurrent sends of 1 MiB in one app process, shared policy lock.
- Load probe: 3 withdrawals of tenant 2 (unrelated; remote process) 0.2 s apart during the sends: they take the same lock
  without stopping tenant 1. Ack latency = WITHDRAW_REQUEST→WITHDRAW_ACK (device clock).
- Blocks: all 20 cells once, order shuffled per block (seed `sweep-20261119`); N = 20 blocks (B decision). AVD P04AvdA
  (android-33) on emulator-5664. Grid may be thinned only by a pre-stated rule if machine time runs out (drop 2 and 8 senders).

## Validity, analysis
- Invalid: harness_error; a sender without SEND_OK; a probe without request/ack. First 20 valid per cell.
- `followup/analyze_sweep.py` (synthetic test passed): ack median / nearest-rank p95 / max; CPU/MiB from 1-sender cells
  (process CPU is process-wide). Descriptive; process CPU is not energy; fixed host, shared load = threats.

## Protocol v2 (19/11, after the v1 final; v1 kept and reported)
Timestamp check of v1 (device clock, no outcome field): the 3 fixed-delay probes often fell outside the send window when few
senders were active (median 0–1 of 3 probes inside for 2–8 senders at 4–64 KiB, 1 of 3 at 1 sender), so those cells measured
an unloaded lock; 16-sender cells had 3/3 inside. v2: `sweep_suite.py --probe-mode overlap --size 4194304` (probes start at the
first accepted chunk and repeat until every sender ended, max 12; 4 MiB per sender), and `analyze_sweep.py` counts only probes
whose request lies inside the send window (v2 trials without one are invalid: "no probe under load"). Same cells, order, N.
Output `final-v2`, `analysis-v2`; v1 (`final`, `analysis`) reported alongside.

## Outcome (19/11)
- v1 final (17:37–17:52, `final`, `analysis`): 400 logged, 0 invalid, 20 valid per cell. Superseded as the estimand by v2
  (probes mostly outside the send window, see above); kept and reported.
- v2 final (19:39–20:06, `final-v2`, `analysis-v2`, guard 0): 400 logged, 4 invalid ("sender did not complete": one sender
  ended with `IOException: Broken pipe` after ~31–35 s; 3 in 4 KiB/16 senders, 1 in 64 KiB/8). The card has no replacement
  rule, so none were run: 4 KiB/16 has 17 valid trials, 64 KiB/8 has 19, every other cell 20. Likely mechanism (not
  verified): the host receiver's 30 s per-recv timeout closed a connection whose sender was idle that long under 16-way
  contention — reported as a harness limit, and as a sign that a sender can wait > 30 s with 16 concurrent senders.
- Keys from v2 (descriptive order statistics, device clock; process CPU is not energy): probe ack median 4.12 ms at
  1 KiB/1 sender (p95 23.4, max 52.4) and 1.23 ms at 64 KiB/16 senders (p95 3.98, max 7.41); CPU per MiB (1 sender)
  159 ms at 1 KiB, 22.2 ms at 64 KiB. v1 for comparison (probes mostly on an unloaded lock): 0.96 / 1.00 ms, 244 / 18.0 ms.
  All per-cell values in `analysis-v2/sweep-summary.json`. Threats: one AVD, shared host, fixed seed order per block.
- Storage: v2 raw `trials.jsonl` is 1.94 GB (on disk, git-ignored); committed as `trials.jsonl.gz` split into byte parts
  `trials.jsonl.gz.part-aa/ab` (< 100 MB each; `cat` restores the gzip, sha256 in `trials.jsonl.gz.sha256`; the original's
  sha256 in `trials.jsonl.sha256`). `analyze_sweep.py` reads the parts; output from parts is byte-identical.
