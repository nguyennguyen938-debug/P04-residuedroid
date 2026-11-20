# Experiment card — Test 1 on a real phone (C11 phone part; real-phone-pending #1)

Status: written 20/11, before any phone trial. The N rule is fixed here and applied mechanically after the pilot; the chosen N
is added under "Pilot" and committed before the final (`run_phone.sh final` refuses an uncommitted card).
Owner: B (Duy). Plan: `PLAN-ROUND3.md` C11 / Test 1 ("Test 1 rút gọn trên điện thoại"); device and receiver choices are B
decisions (user 20/11: own Android 15 phone instead of the RTL Galaxy; plan silent on the device).

## 1. Question and claim
- Same question as B10 (`b10-card.md` §1) on real phone hardware and a real network path: without a barrier, how often are
  bytes accepted after the withdrawal acknowledgement under a layered early check vs the chunk fence?
- Can support: one physical Android 15 phone, its real Wi-Fi/cellular radio and the Internet path to the receiver, the three
  B10 link profiles applied at the receiver, N trials per cell.
- Cannot support: other phones/OEMs/Android versions; real cellular EDGE/3G (profiles are emulated at the receiver on top of
  the real path); server processing; energy. Not pooled with B10 (different device and path): reported side by side.

## 2. Design (as B10 protocol v3 unless stated)
- App: TLS fixture `org.residuelab.tls`, APK sha256 ca313b94…ef15 (the B10 build), installed with `adb install -r`, no root
  (`race_suite.py --no-root`, run-as). Variants `early` vs `fence`; sizes 32 KiB / 256 KiB / 2 MiB; seed `race-20261119`;
  W = u·D after the send broadcast, u from the seed (same u for early and fence); deadline max(10 s, 4·D + 20 s).
- Receiver: `receiver_b.py --profile-set b10v3` on an EC2 t3.micro (region chosen by the user; recorded in RUNLOG), cert with
  SAN = its IP, CA copied into the app's files. Profiles at the receiver's ingress (the phone's upload), as B10 v3: edge
  118.4 kbit/s + 240 ms, umts 128 kbit/s + 118 ms, lte 58 Mbit/s + 0 ms; download unshaped. The real path adds its own RTT.
- Phone network: the user's choice (Wi-Fi or mobile data), kept for the whole run; transport recorded in meta.json. The
  harness changes no phone setting. No hardware serial or account data are recorded (meta: release, SDK, fingerprint).
- Calibration (pilot): 3 sends per (profile, size), fence, no withdrawal, deadline 600 s → D per cell.
- **N rule (fixed now):** block upper bound = 2 × Σ over the 9 (profile, size) cells of the median calibration trial wall time;
  blocks = min(10, ⌊180 min / bound⌋); if < 5 blocks fit, no final (reported). N per (profile, variant) = 3 × blocks.
- Blocks, shuffle, pairing: as B10 (one block = 18 cells, order from the seed).

## 3. Validity, gate, stopping, replacement
- Throttle gate (pilot, mechanical, as B10): median D(edge, 2 MiB) ≥ 3 × D(lte, 2 MiB) and D(umts) ≥ 1.5 × D(lte). Fail → one
  more pilot after an environment check (receiver up, profile applied, network unchanged); fail again → no final, reported.
- Trial validity, analysis selection: as B10 (`analyze_race.py`; first N valid per (profile, variant) in block order).
- Replacement: environment failures only (USB/adb disconnect, receiver unreachable), whole blocks from the next block index
  (`--start`), at most 2. Never outcome-driven. Stopping: after the last block or at the session end; partial blocks reported.

## 4. Analysis
- `followup/analyze_race.py <final> --n 3·blocks` → `results/round3/test1-phone/analysis/race-summary.json`; violation = bytes
  accepted after the first WITHDRAW_ACK (phone clock); Wilson 95%; Eq. 2 as B10 §4, plus the B10 post-hoc decomposition
  (`posthoc_race_eq2.py`, exploratory) for comparison.
- Keys: none in SCHEMA today; numbers reach C only through `summary.json` if C adds keys (asked in PR #2, C3).

## 5. Threats
- Internal: shaping at the receiver, not on the radio; real-path RTT and jitter vary during the run; one phone; host-timed W
  delivered over USB adb. Construct: acceptance by the phone's socket, not server receipt.
- External: one device, one Android version, one network; receiver region. Conclusion: N per cell from the rule; no p-values.

## Pilot (filled after the pilot)
- pilot-calib-1 (20/11 23:5x): stopped after 3 calibration sends, all `SocketException: Software caused connection abort`
  after 5 s before the TLS handshake; network path fine (phone shell and the Mac reach the receiver). Cause: the freshly installed,
  never-launched app (standby bucket 50) had no network from a broadcast; a manual send after `am set-standby-bucket active` + one
  launch of Main gave SEND_OK. Fix (harness only, before any final trial): `race_suite.py` wakes the app once at setup on phones,
  as `campaign.py` does for Test 6. Kept as a failed pilot (EXCLUSIONS); next pilot pilot-calib-2.
- pilot-calib-2 (23:4x): 27 sends; 32 KiB sends and lte 256 KiB completed, every other 256 KiB / 2 MiB send ended `connection abort`
  4.3–4.9 s after it started, with bytes still being accepted, on every profile → throttle gate FAIL (no 2 MiB medians). Environment
  check (receiver up, profiles applied, Wi-Fi unchanged) passed. Cause: Android 15 freezes the cached broadcast process a few
  seconds after the broadcast returns and its sockets are cut (the emulator image, Android 13, does not). Manual check: with Main in
  the foreground a 2 MiB lte send completed (9.6 s). Fix (harness only, before any final trial): on phones `race_suite.py` launches
  Main before each send so the app stays foreground. Construct note: on the phone the sending app is foreground; in B10 it was a
  background process without freezing. Per §3 this allows one more pilot (pilot-calib-3); if its gate fails, no final.

## 6. Outcome (after the run)
