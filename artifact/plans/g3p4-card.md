# Experiment card — P4 (group 3 follow-up): send-buffer size × graceful/abortive fence close (protocol v1)

Status: written 22/11 23:50, before any P4 trial; frozen at the commit that adds it (`results/round3/g3/frozen-g3-v6b`).
The order is pilot (1 block) → mechanism gate → final; chain `plans/autorun/g3-p4-chain.sh`. Owner: B (Duy).

Source: B's request in issue #7 (22/11), approved by the leader (22/11 13:12 UTC; P4 on 23/11, run in the night of 22–23/11
on the user's decision). The leader's text fixes: fence and fence-abort × SO_SNDBUF, edge and umts, 2 MiB, 30 per cell,
"bytes leaving the NIC after the ack against throughput", the `tc`/`ss` queue state at the ack, and TLS application_data
counting. C's review (issue #7, 13:22 UTC) fixes:
- "default" means no `setSendBufferSize` (otherwise it equals 16 KiB);
- capture bytes are reported by W phase, as new bytes, with the TLS filter.

**Correction to B's request.** B estimated ~2.5 h and an APK rebuild. The real cost is about 8.3 h of emulator time: a
2 MiB send takes about 152 s on edge and 137 s on umts. The rebuild is needed only for the default level.

## 1. Question and claim
- Question: with the fence, how many request bytes leave the guest NIC after the ack (the marker), for each send-buffer
  size, with a graceful close (`fence`) and an abortive close (`fence-abort`, SO_LINGER 0)? What write throughput comes
  with each size?
- Can support: emulator, TLS fixture, edge/umts netem profiles, 2 MiB, these three buffer levels, N per cell; the
  trade-off between bytes after the ack and throughput.
- Cannot support: other links, real radios (the netem queue stands in for the modem/RAN queue), phones, servers.
  Packets already in the guest qdisc cannot be recalled by any user-space design, and they are reported. No p-values.

## 2. Design
- **Build** `fixture/build/g3p4-apk/rl-tls.apk` (sha256 in `SHA256SUMS`, meta.json and the freeze).
  - It is the G3 fixture with one change in `TlsTransport`, on the same line, so the line count is unchanged:
    `if(sendBuffer>0) setSendBufferSize(sendBuffer)`. A level of 0 therefore keeps the kernel default (autotuning).
  - Levels > 0 behave as before.
  - The G3a/G3d build `g3-apk` is untouched (8f723ead…).
- **Arms:** `fence`, `fence-abort`. **Levels** (`--sndbufs`): 0 (default), 16384 (as every earlier G3 run), 65536.
- **Network:** edge and umts profiles; size 2 MiB; seed `race-20261119`, with the same u per (block, profile, size) as G3a.
- **Durations:** D from `results/round3/g3race/pilot-calib/calibration.json`, the G3a calibration with fence at 16 KiB.
  The link rate dominates D; the same D is used for every level. Deadline max(10 s, 4·D + 20 s).
- **Cells:** a block holds all 12 cells (2 profiles × 2 arms × 3 levels), in an order shuffled per block from
  `race-20261119-<block>-p4`.
- **Instrumentation:**
  - `--g3`, marker 8799 in the unshaped band, capture via `-tcpdump`;
  - `--qsnap` (the queue snapshot right after the withdraw broadcast returns, i.e. after the ack and the marker, not at the
    ack);
  - SOCKET_CONFIG logs `requested_sndbuf` and `actual_sndbuf`.
- **N:** 30 blocks → 30 trials per (profile, arm, level), 360 trials. AVD P04AvdA, emulator-5660 (`-read-only`).
  - The phone run G3d v3 may run at the same time; host load is recorded per trial.

## 3. Gate, validity, stopping, replacement
- **Pilot `pilot-p4`:** 1 block (12 trials), excluded. The gate is mechanical and reads no bytes, violations or latencies:
  - all 12 valid (B10 rule);
  - every fence-abort trial has `ABORT_ARMED linger0=true` or no BLOCK;
  - MARKER_SENT and a marker.jsonl line in every trial;
  - marker and request SYN in the capture;
  - `qsnap` present;
  - `requested_sndbuf` in SOCKET_CONFIG equals the trial's level.

  Fail → no final, reported in issue #7.
- **Validity and selection:** B10 validity; first 30 valid per cell in block order.
- **Stopping and replacement:** stop after 30 blocks. Environment failures only: whole blocks from index 30, at most 3.
  A pause or interruption uses the G3a rule (fresh directory; only blocks complete within their directory).

## 4. Analysis (`followup/analyze_g3p4.py`, written before any trial)
- **Primary (descriptive), per (profile, arm, level), among trials with W during the writes:**
  - TCP new bytes after the marker and TLS application_data bytes after the marker (`tls_records.py` →
    `capture-tls.jsonl`, committed with the pcap sha256);
  - sum and per trial (median, nearest-rank p95, max);
  - trials with application_data after the marker.
- **Secondary:**
  - the same for the other W phases;
  - trials accepted after W (the G3a primary), as counts;
  - RST after the marker; `actual_sndbuf`;
  - write throughput before W = bytes accepted before W / (W − SOCKET_CONFIG) on the device clock;
  - queue snapshot (netem backlog, socket send queue; `qsnap.py`);
  - paired per (block, profile, level): fence-abort vs fence application_data bytes during the writes.
- **Output:** `results/round3/g3race/analysis-p4/` (`g3p4-summary.json`, `qsnap-summary.json`).

## 5. Threats
- **Internal:**
  - one AVD; host-timed W;
  - D is calibrated at 16 KiB only;
  - the G3d phone run shares the host;
  - snapshot after the ack;
  - order shuffled per block.
- **Construct:**
  - the capture boundary is the guest NIC, and the netem queue sits before it;
  - autotuning at level 0 is the emulator kernel's;
  - throughput before W is a write rate into the socket, not goodput at the server.
- **External:** emulator, fixture, two shaped profiles, one size.
- **Conclusion:** N = 30 per cell; descriptive.

## Pilot log
- pilot-p4 (22/11 23:48–23/11 00:03; excluded): mechanism gate passed (12/12 valid; sndbuf requested/actual 0/1,048,576,
  16,384/16,384, 65,536/65,536).
- **Pause (23/11 04:58, user decision):** final-p4 stopped after 195 logged trials (16 complete blocks 0–15 + 3 trials of
  block 16; 0 invalid). Per §3 only complete blocks count. The chain's post steps ran on the partial directory; that output
  is kept as `analysis-p4_INVALID_interrupted-partial` and is not the pre-registered analysis. Resume (if the user decides):
  a fresh directory from block 16, same freeze `frozen-g3-v6b`, analysed with blocks 0–15 of final-p4.

## 6. Outcome (after the run)
