# Experiment card — G3a + G3b (group 3): fairer socket-close comparator, packet capture, abortive close (protocol v1)

Status: written 22/11, before any G3 trial; frozen at the commit that adds it (calibration pilot → throttle gate →
mechanism pilot → mechanism gate → final; chain `plans/autorun/g3-chain.sh`). Owner: B (Duy).
Source: issue #7 (leader, 22/11) "G3a: comparator đóng socket công bằng hơn" and "G3b: bắt gói tin độc lập, thêm abortive
close (chung block với G3a)". The issue fixes the questions, the arms, the protocol (B10 v3, 30 trials per (profile, arm)), the
shared definition of W and the primary count; every other choice below is a B decision, made before any data. Schedule: user
decision 22/11 (two-day speedrun, runs from 22/11 23:59). B7 freeze reopened for group 3 only; earlier data untouched.

## 1. Question and claim
- G3a: if the early check has the best cancellation path we can write (withdrawal in the sending process, only requests not yet
  handed off are closed, the ack after the close), does the socket still accept writes that start after W? What does it cost?
- G3b: (1) does the order taken from the device log agree with the packets that actually left the guest? (2) after the ack,
  how many request bytes still leave because they were already in the send buffer, and does an abortive close (RST,
  SO_LINGER 0) stop that part?
- Can support: emulator, TLS fixture app, B10 v3 profiles and sizes, these cancellation and close designs, N per cell; fence vs
  an in-process cancellation; oracle agreement with an independent capture at the guest NIC; bytes after the ack per arm.
- Cannot support: other cancellation designs, real apps, phones, real networks, server processing. 0/N is not an impossibility
  guarantee. A zero-vs-zero result is reported as counts, not equivalence.

## 2. Design (B10 protocol v3 unless stated)
- Arms, all five in every block: `early` (B10), `close2` (new), `fence` (B10), `fence-abort` (new), `close` (G2a, kept for a
  direct comparison). Not tested: the optional `HttpsURLConnection.disconnect()` arm. The platform client buffers writes, so
  WRITE_ATTEMPT would be a stream write, not a socket write, and the W estimand would not be comparable. It is used in G3d.
- `close2` (comparator code in `fixture/src-cmp`, not ResidueDroid, not counted by impLoc):
  1. the request registers a token before its early check, as in `close`;
  2. the withdrawal broadcast goes to `Revision` in the sending process, not to `RevisionRemote` (`:revision`), with
     `cancel2=true`;
  3. after the durable commit under the policy lock, `CancelPath.cancelUnhanded()` runs in the same process. It closes the
     socket of every live request without REQUEST_HANDED_OFF, or marks a token that has no socket yet so the socket closes
     when it opens. Requests already handed off are left alone. Logged `CANCEL_DONE inproc;live;closed;nosocket;handed`;
  4. WITHDRAW_ACK follows.
- `fence-abort`: the fence, but at the fence's BLOCK the token sets SO_LINGER 0 on the channel (`ABORT_ARMED`). The
  transport's close is then an RST, and unsent send-buffer data is discarded. Packets already in the guest qdisc cannot be
  recalled; they are counted by the capture.
- Every send carries `g3=true`. The app logs `SOCKET_LOCAL local_port` after the TLS handshake (issue: "ghi local port"; logged
  as its own event because SOCKET_CONFIG precedes connect).
- After WITHDRAW_ACK, the withdrawing process opens one TCP connection to the host marker port 8799 and writes the trial id
  (`MARKER_SENT`).
- Build: `fixture/build/g3-apk/rl-tls.apk` (`VARIANTS=tls`), one build for all arms. sha256 in meta.json and in
  `results/round3/g3race/frozen-g3`. Revision.java call sites are appended to existing lines (impLoc unchanged, 1,251).
- Network: guest egress on eth0, data over the emulated radio (`--radio`). The root qdisc is `prio`; band 1:2 (every packet
  by priomap) carries the B10 v3 netem profile (edge 118.4 kbit/s 240 ms, umts 128 kbit/s 118 ms, lte 58 Mbit/s 0 ms).
  A u32 filter on dport 8799 sends the marker to band 1:1 (pfifo, unshaped), so the marker SYN does not queue behind request
  data.
- Capture: the emulator console `network capture start <run>/capture.pcap` for the whole trial phase. It records guest frames
  of the emulated LAN after the guest shaper, independently of the app's log. The full pcap stays on disk (git-ignored,
  sha256 committed).
- Profiles, sizes (32 KiB / 256 KiB / 2 MiB), seed `race-20261119` (same u per (block, profile, size) as B10/G2a), deadline
  max(10 s, 4·D + 20 s). Calibration `pilot-calib`: 3 sends per (profile, size), fence, no withdrawal → D per cell.
- N: 10 blocks of 45 cells → **30 trials per (profile, arm)**, 10 per size, 450 trials. AVD P04AvdA on emulator-5660
  (`-read-only`), receiver 8798, marker 8799. Only emulator on the Mac during G3a/G3b. G3d runs at the same time on the phone;
  its receiver is on this host's LAN address, and host load is recorded per trial.

## 3. Gates, validity, stopping, replacement
- Throttle gate (as B10 v3, G2a): median D(edge, 2 MiB) ≥ 3 × D(lte, 2 MiB) and D(umts, 2 MiB) ≥ 1.5 × D(lte, 2 MiB).
- Mechanism pilot `pilot-mech`: 1 block (45 trials), excluded from analysis. The gate is mechanical and reads only harness and
  mechanism fields, never violations, bytes or latencies:
  - all 45 trials valid by the B10 rule;
  - every `close` trial has CANCEL and CANCEL_DONE reply=ok;
  - every `close2` trial has CANCEL_DONE `inproc`;
  - every trial has MARKER_SENT without error and a marker.jsonl line;
  - the pcap exists and contains the marker connection (by id) of every trial;
  - for every trial with SOCKET_LOCAL, that port's SYN to 8798 is in the pcap;
  - the tc filter is listed, and band 10: (pfifo) shows sent packets.

  Fail → no final, reported in issue #7; a fix needs protocol v2 and a new pilot.
- Validity and first-N rule: B10 (`analyze_race.validity`); first 30 valid per (profile, arm) in block order. Missing markers
  or unmatched capture connections do not invalidate a trial; they are counted in the capture analysis.
- Stop after the 10 blocks. Replacement: environment failures only, whole blocks from index 10 (`--start 10`), at most 3.

## 4. Analysis (`followup/analyze_g3race.py`, unit tests `followup/test_g3race.py`; checked on G2a data before any G3 trial:
after-W close 10/90, fence 0/90, early 50/90, the counts C reported in issue #7)
- **Primary (pre-registered, issue #7):** per (profile, arm), trials "accepted after W": some BYTES_ACCEPTED n > 0 whose
  nearest preceding WRITE_ATTEMPT of the same trial is later than W (the first WITHDRAW_DURABLE), on the device clock.
  Reported with Wilson 95%.
- **Secondary (pre-registered):**
  - violations after the ack (B10 rule) and bytes accepted after the ack;
  - latency WITHDRAW_REQUEST → WITHDRAW_ACK (median, nearest-rank p95, max);
  - uncut requests that the receiver logged complete while the app ended SEND_ERROR (pre-registered here, exploratory in G2a);
  - cut trials, and the receiver completeness of those;
  - cancellation replies (close, close2); ABORT_ARMED (fence-abort);
  - paired 2×2 per (block, profile, size), after W: close2 vs fence, close2 vs early, close2 vs close, fence-abort vs fence.
- **G3b, from the capture** (frame order only; capture time is never compared with device time):
  - the marker SYN of the trial (marker connection whose payload is the trial id) is the ack position;
  - the request connection is the SYN to 8798 with the trial's SOCKET_LOCAL port, latest before the marker. Without
    SOCKET_LOCAL, the single SYN to 8798 between the previous marker and this one; otherwise unmatched;
  - per arm: trials and TCP payload bytes guest → receiver after the marker (all bytes, and new bytes = advance of the
    highest sequence end); RST after the marker;
  - concordance of capture "bytes after the marker" with the app oracle "accepted after the ack".

  Graceful-close fence trials may show bytes after the marker (data already in the buffer or the qdisc). That is a result to
  report, not a reason to change the design.
- Output `results/round3/g3race/analysis/g3race-summary.json`. Numbers reach C only via that file (C adds SCHEMA keys).

## 5. Threats
- **Internal:**
  - one AVD; host-timed W;
  - close2 withdraws in the sending process while early, fence, fence-abort and close withdraw in `:revision` (as issue #7
    specifies), so ack latencies differ partly by process path;
  - the prio root replaces B10's bare netem root (same netem on the data band; new calibration);
  - G3d runs on the same host at the same time (host load recorded).
- **Construct:**
  - the capture boundary is the guest NIC → emulator, not the server;
  - TLS records are counted as TCP payload;
  - the marker SYN marks the ack only up to the time it takes to open a socket after WITHDRAW_ACK;
  - packets queued in the guest qdisc have left the socket but appear after the marker.
- **External:** emulator, fixture, one design per arm.
- **Conclusion:** N = 30 per cell; zero-vs-zero reported as counts.

## Pilot log
- pilot-calib (22/11 14:16–14:35; excluded): 27/27 calibration sends; throttle gate passed.
- pilot-mech (14:35–14:51; excluded): MECHANISM GATE FAIL on the capture only. The emulator console `network capture start
  <path>` answered `KO: <file> must be a bare filename (written under the AVD content directory)`, so no pcap was written.
  Every other gate field held: 45/45 trials with MARKER_SENT and SOCKET_LOCAL, 45 marker lines, the u32 filter listed, and
  marker packets in the unshaped band (pfifo 10: sent > 0).

  Diagnosis (manual, 14:52–14:54, same AVD, no trial; emulator stopped after):
  - `-tcpdump <absolute path>` at emulator launch writes guest frames (10.0.2.15, Ethernet pcap);
  - the console capture with a bare name wrote only a pcap header.

  **Protocol v2** (before any final; capture method only; design, arms, N and analysis unchanged): race_suite.py and
  race_airguard.py pass `-tcpdump <run>/capture.pcap` when they launch the emulator. The calibration pilot-calib and its passed
  throttle gate are reused, since calibration never captured in v1 either. A new mechanism pilot `pilot-mech2` runs with the
  same gate. New freeze `results/round3/g3/frozen-g3-v2`; chain `plans/autorun/g3-chain-v2.sh`.
- final (15:11–15:52): paused on the user's request. Blocks 0–1 were complete and block 2 partial (10/45) when the chain and
  harness were stopped; no outcome was read. **Resume rule**, fixed before any outcome is read:
  - resume in a fresh directory `final-r2` with `--start 2 --trials 8`, i.e. blocks 2–9 with the same seed, so the same cell
    order and u per block;
  - the analysis uses only blocks that are complete within one directory (`final` 0–1, `final-r2` 2–9);
  - the partial block 2 in `final` is retained and excluded (interrupted by the pause, operational);
  - first-N and every other rule as above.

## 6. Outcome (after the run)
