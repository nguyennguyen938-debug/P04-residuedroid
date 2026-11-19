# Experiment card — b3 (split policy for blocked mixed requests; protocol v1)

Status: frozen at the commit that adds this card; pilot (1 block) → mechanism gate → final (chain `plans/autorun/b3-chain.sh`)
Owner: B (Duy). Plan-silent choices are B decisions (19/11).

Source `[R3]` B3: "Tách lô theo chính sách S0, chạy 3 điều kiện × 20 trial. Đo tỷ lệ giữ được thư hợp lệ và số lần gửi lại
thành công"; S0 policy (HUONG-DAN-B): if the fence blocks before any byte reaches the socket, split items by label: forbidden
items are retired, permitted items form a new request that passes the fence again; at most one split per attempt; once bytes
were accepted, no split. Paper §5 "Splitting blocked requests". No `summary.json` key in SCHEMA (raw + summary only).

## 1. Question and claim
- Does the split policy recover the permitted item of a mixed request blocked before any byte, while never sending the
  forbidden item, and correctly refrain from splitting once a prefix was handed off?
- Can support: emulator, TLS fixture, 2-item mixed request, N = 20 per cell. Cannot: real apps, other batch shapes.

## 2. Design
- Fixture (Revision send op, TLS): `items="analytics:0,diagnostics:0"` (A, B; label union checked per chunk), `split` flag,
  scoped withdrawal `scope=analytics`, `splitsetup` grants diagnostics, fault `prelock` = barrier after the TLS handshake
  (before the first record takes the policy lock). Split: on denial with 0 accepted chunks, retire blocked items, resend the
  rest once as `<id>-split` (fenced, new request). APK `fixture/build/tls-b3-apk/rl-tls.apk` sha256 fce0401a…566c.
- Conditions: prefirst (prelock barrier, withdraw, release; 1 MiB), prefix (receiver stalls 12 s, 8 MiB, sndbuf 4096,
  withdraw after the first accepted chunk), control (no withdrawal). Variants: split on/off, paired in each block.
- Blocks: 6 cells, order shuffled per block from seed `b3-20261119`; N = 20 blocks → 20 trials per (condition, variant).
- AVD P04AvdB (android-33, paper image) on emulator-5662, launched by the suite; receiver host 8798.

## 3. Validity, gate, stopping, replacement
- Pilot gate (mechanism, before final): prefirst trials reach the barrier; the prefirst/split trial logs SPLIT with a
  resubmission and its `-split` request ends; prefix trials see an accepted chunk before the withdrawal; control ends.
- Invalid trial: harness_error; end not observed; withdrawal conditions: barrier/first chunk not seen, or no WITHDRAW_ACK.
- First 20 valid per cell in block order. Replacement: environment failures only, new blocks from 20, cap 3.

## 4. Analysis
- `followup/analyze_b3.py` (synthetic test passed): permitted_retained (B complete at the receiver, original or `-split`),
  resubmit_ok, forbidden_after_ack (safety, expected 0); Wilson 95%.

## 5. Threats
- Fixture-level mechanism test (2 items, one shape); emulator only; barrier timing is synthetic (prelock). Construct:
  receiver completion = receipt of all bytes, not server processing.

## 6. Outcome (after the run)
- Final run 19/11 19:35–19:38 (protocol v2, autorun b3-final, guard 0): 120 logged, 0 invalid, 120 valid, 20 analysed per
  cell, 0 unused. Data `results/round3/b3/final`; analysis `results/round3/b3/analysis/b3-summary.json`.
- Permitted item B retained (Wilson 95%): control 20/20 [0.839, 1] with and without split; prefirst/nosplit 0/20 [0, 0.161]
  → prefirst/split 20/20 [0.839, 1] (20/20 `-split` resubmissions completed); prefix 0/20 [0, 0.161] with and without split.
- Safety: forbidden_after_ack 0 in every cell (120/120 trials).
- Negative result (kept): split recovers nothing once a chunk of the mixed request was accepted (prefix/split 0/20) — by
  design the fixture splits only on a denial with 0 accepted chunks; a request already partly on the wire is not split.
- Deviations: protocol v2 (end predicate only), recorded below before any final trial.

## Protocol v2 (19/11, after pilot-1; before any final trial)
Pilot-1 mechanism: prefirst+split retired analytics and resent diagnostics (`-split` SEND_OK); prefix denied; control sent.
Gate failed on a harness bug: for prefix+split the suite waited for a SPLIT that the app (correctly) never emits once bytes were
accepted, so the trial timed out. v2 fixes only the suite's end predicate (`b3_suite.py`); fixture, conditions, N, validity and
analysis unchanged. Pilot-2 → gate → final (queue2.sh).
