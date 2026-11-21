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
- pilot-calib-3 (21/11 00:0x): 27/27 calibration sends SEND_OK. 2 MiB medians edge 151.2 s, umts 139.3 s, lte 9.41 s → throttle
  gate PASS. N rule: block upper bound 12.1 min → min(10, ⌊180/12.1⌋) = **10 blocks** (30 trials per (profile, variant), 10 per
  size; same N as B10). Durations: `pilot-calib-3/calibration.json`. Final: `run_phone.sh final <ip> <serial> 10` → `final`.

## 6. Outcome (after the run)
- Logged / invalid / valid / analysed / unused: 180 / 0 / 180 / 30 per (profile, variant) / 0; no replacement. Final 21/11
  00:09–01:46 (`results/round3/test1-phone/final`; raw 118 MB on disk, committed as `.gz` + sha256 of the original; analysis
  from the gzip is byte-identical). Sources and APK pinned in `frozen-test1-phone/source-sha256.txt`. Phone: Samsung Galaxy A06
  5G (SM-A066B), Android 15, Wi-Fi; receiver EC2 t3.micro ap-southeast-1 (terminated after the run; app uninstalled).
- Violating trials (bytes accepted after WITHDRAW_ACK; Wilson 95%): early (layered) edge 16/30 [0.361, 0.698], umts 19/30
  [0.455, 0.781], lte 19/30 [0.455, 0.781]; **fence 0/30 [0, 0.114] for every profile**. By size (early, 10 each, 32 KiB /
  256 KiB / 2 MiB): edge 3/5/8, umts 2/7/10, lte 1/8/10. Fence ends: SEND_ERROR (denied mid-send) 16 / 20 / 17, SEND_OK 14 / 10 /
  13 (edge / umts / lte); early all SEND_OK.
- Eq. 2: predicted 68.2% vs observed 60.0% (pooled, 90 early trials). B10 post-hoc decomposition (exploratory): P1 55.3%, P2 52.4%
  — on the phone the corrections overshoot (below observed by 4.7 and 7.6 points); δ (fence trials, median) ≈ 0.25–0.27 s per
  profile (B10 emulator ≈ 0.08–0.12 s). The B10 explanation does not transfer cleanly; not analysed further.
- Comparison with B10 (emulator, descriptive only; different device and path, not pooled): fence 0/30 in all 6 cells of both;
  early edge 16 vs 21, umts 19 vs 20, lte 19 vs 10 of 30 — lte differs most, consistent with the real path's RTT making lte
  uploads longer on the phone (lte 2 MiB D 9.4 s vs 0.32 s on the emulator).
- Deviations: two harness fixes after failed pilots, before any final trial (app wake; app kept foreground) — see Pilot. Negative
  or null: fence 0/30 is not an impossibility guarantee (upper bound 11.4%); one phone, one network.
