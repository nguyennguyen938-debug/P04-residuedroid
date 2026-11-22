# Experiment card — P3 (group 3 follow-up): G3a on lte with balanced withdrawal timing (protocol v4 of G3a/G3b)

Status: written 22/11 evening, before any P3 trial; frozen at the commit that adds it (`results/round3/g3/frozen-g3-v4b`).
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
    (C's review in issue #7) before any P3 trial; re-frozen as `frozen-g3-v4b`.

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
- **Construct:**
  - as G3a; the queue snapshot is taken after the ack, not at it;
  - every send uses `sndbuf=16384`, so bytes after the marker are measured with a 16 KiB send buffer.
- **External:** emulator, fixture, lte profile only.
- **Conclusion:** N = 30 per arm; zero-vs-zero reported as counts.

## Pilot log

## 6. Outcome (after the run)
