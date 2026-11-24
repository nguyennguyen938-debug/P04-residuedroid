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

- **Pause 2 and resume 2 (23/11):** final-p4b (blocks 16–29, 13:14) was paused by the user; B's SIGINT matched the caffeinate
  wrapper too and race_suite kept running with abnormal trial durations, so B sent SIGTERM at 16:25 (blocks 16–24 complete,
  all before the signal; block 25 partial, 5 trials). Resume 2: final-p4c, blocks 25–29 (16:27–17:25), freeze `frozen-g3-v7`
  (differs from v6b only in G3d files; every P4 file identical).
- **Analysis rule added before the analysis ran (23/11):** `analyze_g3p4.split_blocks` keeps only blocks complete within
  their directory (§3), as `analyze_g3race`; unit test `followup/test_g3p4.py`.
- **TLS file correction (23/11):** the autorun post step ran `tls_records.py` before the emulator shut down and closed the
  pcap, so every `capture-tls.jsonl` written by a post step (final-lte5, final-p4, final-p4b, final-p4c) carries the sha256 of
  an unfinished pcap. `capture-tls-v2.jsonl` was written next to each from the complete pcap (sha256 matches); the analyses
  read v2 when present. P3 (`analysis-lte5`) rerun with v2: 0 differences in g3race-summary and g3race-audit.

## 6. Outcome (after the run)
- Written 23/11 after final-p4c. Source: `results/round3/g3race/analysis-p4/` (`analyze_g3p4.py final-p4 final-p4b
  final-p4c`, `qsnap.py`). Raw: `trials.jsonl.gz` + sha256, `capture-slim.pcap` + sha256 of the full pcap, `capture-tls-v2.jsonl`.
- Trials: 368 logged; 8 excluded (interrupted blocks 16 in final-p4 and 25 in final-p4b, operational); 0 invalid; 30 per
  (profile, arm, level), 0 unused. `actual_sndbuf` 1,048,576 / 16,384 / 65,536 in 30/30 trials of each level.
- **Trials accepted after W: 0/30 in every cell** (both arms, all levels, both profiles).
- **Primary: TLS application_data bytes after the marker, trials with W during the writes** (per trial median / max; trials
  with any application data after the marker):

  | Profile | Level | fence: exposed | fence median / max | fence-abort: exposed | fence-abort median / max | fence-abort trials > 0 |
  |---|---|---|---|---|---|---|
  | edge | default (1 MiB) | 8 | 1,618,027.5 / 1,619,750 | 8 | 0 / 1,365 | 3/8 |
  | edge | 16 KiB | 30 | 21,042.5 / 24,445 | 29 | 0 / 1,535 | 12/29 |
  | edge | 64 KiB | 27 | 97,195 / 100,710 | 28 | 0 / 1,570 | 3/28 |
  | umts | default (1 MiB) | 10 | 1,618,845 / 1,621,235 | 9 | 0 / 810 | 1/9 |
  | umts | 16 KiB | 30 | 20,817.5 / 24,745 | 30 | 0 / 2,170 | 11/30 |
  | umts | 64 KiB | 30 | 97,065 / 100,545 | 30 | 0 / 2,305 | 11/30 |

  fence: application data after the marker in every exposed trial at every level. Paired per (block, profile, level),
  fence-abort had fewer application-data bytes than fence in every pair (edge 7 / 29 / 27, umts 9 / 30 / 30 pairs for
  default / 16 KiB / 64 KiB). Descriptive; no p-values.
- **Reading (B, descriptive):** with the graceful close, the bytes that leave after the ack are about the send-buffer size
  (fence medians 20,817.5–21,042.5 B at 16 KiB, 97,065–97,195 B at 64 KiB, 1,618,027.5–1,618,845 B at the 1 MiB default). The abortive close (SO_LINGER 0, RST)
  leaves at most 2,305 B per trial of application data (median 0) at every level.
- **Exposure depends on the level:** with the default buffer, W fell during the writes in only 8–10/30 trials; in 20–22/30
  the request had been handed off before W, and permitted data then left after the marker (after-handoff app bytes,
  fence median 836,942 edge / 1,039,882 umts). This is permitted data leaving late, not cut data (card §4).
- **Secondary:**
  - write rate into the socket before W (median, bytes/s): default 27,502 / 27,510 (edge fence / fence-abort), 36,297 / 36,414
    (umts); 16 KiB 14,262 / 14,133 and 15,559 / 14,956; 64 KiB 15,122 / 14,676 and 16,286 / 16,250. This is a write rate into
    the socket, not goodput: a larger buffer accepts writes ahead of the link;
  - RST after the marker in every during-writes trial of both arms;
  - queue snapshot after the ack (median netem backlog 9,084–9,138 B in every cell; socket send queue median 1,072,469 edge and
    1,337,723 umts for fence at the default, 23,360.5 / 22,846 at 16 KiB and 99,281 / 99,281 at 64 KiB for fence (edge / umts), 0 at 16 and 64 KiB for
    fence-abort; full table in `qsnap-summary.json`).
- **Threats** as §5; in addition, the snapshot mixes phases (after-handoff trials still have permitted data queued), and the
  1 MiB default is this emulator kernel's autotuning.
