# Role B: round-3 experiment results (final, data frozen 21/11)

For A and C. All B runs are done. The data freeze (B7) was declared on 21/11, and no device or emulator has run since.
Every number below comes from a script output under `artifact/results/`, and the per-task card in `artifact/plans/` gives the
protocol, exclusions and threats. Rates are trials with at least one violation out of analysed trials, with Wilson 95%
intervals. A 0/N result is not an impossibility guarantee. `summary.json` currently holds 32 of 44 SCHEMA keys; the 12
`promise*` keys belong to C.

## Summary

| Task | Question | Result | Card |
|---|---|---|---|
| B11 (test 4) | Lifecycle on Android 14 and 15 | `mfence` 0/80 and `menqueue` 80/80 on both AVDs. `mlayer` is also 0/80, so the two cannot be told apart here | `b11-card.md` |
| B10 (test 1) | Race against a withdrawal mid-upload, emulator | fence 0/30 in all 3 profiles; early 21, 20 and 10 of 30 | `b10-card.md` |
| Test 1, phone | Same race on a real Android 15 phone | fence 0/30 in all 3 profiles; early 16, 19 and 19 of 30 | `test1-phone-card.md` |
| Test 6 | Two rented phones (Pixel 8a, Galaxy M35) | fence 0/60 TLS trials per phone; lifecycle fence 0/20 in every cell | `test6-card.md`, `test6-card-v3.md` |
| B2 | Real app (AirGuard) | stock 20/20, fenced 0/20 in pending, kill and reboot | `b2-card.md` |
| B12 (test 2) | Mutation: do the label checks catch broken builds? | M1 24/40, M2 39/39 caught; M3 not leaking but loses items; base 0/39 | `b12-card.md` |
| B3 | Splitting a mixed batch | recovers 20/20 before any chunk is accepted, 0/20 after; 0 bytes accepted after ack | `b3-card.md` |
| B4 (test 5) | Cost of the transport | probe ack median 4.08 ms and 1.57 ms; CPU 188 and 23.5 ms per MiB | `b4-card.md` |
| B1, A10 | Real-app screening; caller triage | AirGuard builds and was used for B2; `find_callers` output sent to A | `b1-screening.md`, `results/round3/a10/` |

**Cross-cutting result:** no fenced trial accepted bytes after the withdrawal acknowledgement, in any of these settings:
- emulator, Android 13, 14 and 15;
- the real app;
- two rented phones;
- one personal phone.

The unfenced baselines leak in each setting.

## Per experiment

### B11: lifecycle, Android 14 and 15 (keys `life*`)
- 80 paired trials analysed per AVD (20 per schedule: pending, kill, reboot, netloss).
  - Android 14: 2 reboot trials excluded for an emulator boot timeout and replaced by the card's rule.
  - Android 15: no exclusions.
- Results, identical on both AVDs:

  | Variant | Violating trials | 95% CI | Permitted items missing |
  |---|---|---|---|
  | `menqueue` (weak baseline) | 80/80 | [0.954, 1] | 80 |
  | `mlayer` | 0/80 | [0, 0.046] | 0 |
  | `mfence` | 0/80 | [0, 0.046] | 0 |

  Unknown requests: 0.
- `mlayer` against `mfence` is zero against zero: no confirmed difference in 80 paired trials, which is not equivalence. These schedules do not create a race; the two variants are separated by B10 and Test 1.

### B10: race on the emulator (keys `race*`)
- Protocol v3 shapes the upload on the guest with netem. Earlier protocols failed their gate because the emulator presets did not shape the app's traffic; this is recorded in the card.
- 180/180 trials valid, 30 per (profile, variant).

  | Profile | early (layered) | 95% CI | fence | 95% CI |
  |---|---|---|---|---|
  | edge | 21/30 | [0.52, 0.83] | 0/30 | [0, 0.114] |
  | umts | 20/30 | [0.49, 0.81] | 0/30 | [0, 0.114] |
  | lte | 10/30 | [0.19, 0.51] | 0/30 | [0, 0.114] |

- Eq. 2 predicted 79.4% and 56.7% was observed (90 early trials); these are the keys.
- Post-hoc decomposition, exploratory (`b10/posthoc-eq2`):
  - starting the window at the layered check gives 65.7%;
  - adding the withdrawal delivery delay, estimated from fence trials only, gives 57.7%.

### Test 1 on a phone (Galaxy A06, Android 15, Wi-Fi; no SCHEMA keys yet)
- Receiver on EC2 (Singapore) with the B10 v3 shaping applied on its ingress.
- 180/180 trials valid, N = 10 blocks by the card's rule.

  | Profile | early (layered) | 95% CI | fence | 95% CI |
  |---|---|---|---|---|
  | edge | 16/30 | [0.361, 0.698] | 0/30 | [0, 0.114] |
  | umts | 19/30 | [0.455, 0.781] | 0/30 | [0, 0.114] |
  | lte | 19/30 | [0.455, 0.781] | 0/30 | [0, 0.114] |

- Eq. 2 predicted 68.2% and 60.0% was observed. The B10 corrections do not transfer: they give 52.4%. Not analysed further.
- Construct difference: on the phone the sending app is in the foreground. Android 15 freezes a background sender about 5 s in; this was found in a failed pilot, which is kept.
- Compared with B10 (descriptive only, not pooled): lte early is 19 here against 10 on the emulator. The real network path makes lte uploads longer: 2 MiB takes 9.4 s here against 0.32 s.

### Test 6: two rented phones (keys `dev*`, definitions pending C)
- Phones: Pixel 8a (Android 17) on Device Farm, and Galaxy M35 (Android 14) on Samsung RTL.
- TLS, 20 blocks per phone:
  - fence cases 0/60 trials with bytes accepted after the ack on each phone;
  - `buffered-early` 20/20 completed on each phone.
- v3 (raised deadline) fixed the Galaxy `concurrent` failure: 40/40 requests completed, against 1/40 in v2. Both versions are reported.
- Lifecycle, pending, kill and revoke, 20 paired trials each:
  - fence variants 0/20 in every cell on both phones;
  - `menqueue` 20/20 on Pixel, and on Galaxy 20/20 (kill), 19/20 (pending), 19/20 (revoke).
- Post-freeze diagnosis, exploratory (`test6/analysis-deficit`):
  - The Galaxy permitted-item deficit equals Pixel's (`mstart` tenant 5, by design) plus two trials, `pen009` and `rev017`. In those two, the harness declared quiescence before any job ran: a harness observation failure that the pre-registered rules do not catch.
  - Without those two trials: `menqueue` 19/19, fence 0/19. The pre-registered numbers stay primary.

### B2: real app, AirGuard (no SCHEMA keys)
- 80/80 trials valid, 20 per schedule, both builds in each trial.

  | Build | pending, kill, reboot | netloss |
  |---|---|---|
  | stock | 20/20 [0.839, 1] | 0/20 |
  | fenced | 0/20 [0, 0.161] | 0/20 |

- In netloss both builds lose every post-withdrawal beacon (deficit 80/80), because the app does not retry a failed run. This is a property of the app.
- Oracle v3 (post-hoc) orders requests on the guest clock. It brings the fenced unknown trials from 8, 9, 9 to 0; all of those were permitted requests made before the ack. Violations are unchanged. v2 is the pre-registered result.

### B12: mutation, protocol v2 (keys `mut*`)
- v2 adds the fixture extra `regrant_agg` (approved by A), so the M1 trigger can occur. v1 is reported alongside.

  | Build | Leaking trials, v2 | v1 |
  |---|---|---|
  | base | 0/39 [0, 0.090] | 0/40 |
  | M1 union-latest | 24/40 [0.446, 0.737]; 24 flagged = 24 wrong-label | 0/39 (not triggered) |
  | M2 stale-epoch | 39/39; 924 flagged = 924 wrong-label | 39/39; 908 |
  | M3 extras-drop | 0/40; permitted deficit 136 (base 80) | 0/38; 116 (base 44) |

- Post-freeze diagnosis, exploratory (`mutation-v2/analysis-m1`, `analysis-deficit`):
  - M1 leaked in 24/24 trials where the re-derived summary reached the sink, and 0/16 where it did not (all reboot trials). The non-leaks are trigger misses, not label-check misses.
  - The base deficit is entirely jobs stopped by the reboot and never restarted. This is a fixture property; the oracle is not at fault.

### B3: splitting a mixed batch (no SCHEMA keys)
- 120/120 trials valid, 20 per cell.

  | Condition | without split | with split |
  |---|---|---|
  | control | 20/20 | 20/20 |
  | prefirst (no chunk accepted yet) | 0/20 | **20/20** |
  | prefix (a chunk already accepted) | 0/20 | 0/20 |

- Bytes accepted after the ack: 0 in all 120 trials.
- The prefix result is a design limit: a request already partly on the wire is not split.

### B4: cost, protocol v3 (keys `sweep*`)
- 440 trials logged, 1 invalid, 400 analysed (20 per cell, 2 replacement blocks by the card's rule).
- Probe ack median:
  - 4.08 ms at 1 KiB with 1 sender;
  - 1.57 ms at 64 KiB with 16 senders.
- Process CPU per MiB (1 sender): 188 ms at 1 KiB, 23.5 ms at 64 KiB. These are descriptive order statistics; process CPU is not energy.
- v1 and v2 are reported in the card.
- Limit found: with 16 senders and 4 KiB chunks, one sender waited the full 120 s app deadline for the policy lock (1/440 trials). This is a fairness limit of the shared lock, not a harness artefact.

## Limits that stay in the paper as results
- B3 cannot recover items once a chunk was accepted.
- B11 cannot separate `mlayer` from `mfence`.
- B4 shows lock unfairness under 16 senders.
- Eq. 2 is off on both the emulator and the phone, in different directions.
- On Android 15 the sender had to stay in the foreground.
- AirGuard does not retry after netloss.
- Scope:
  - emulator results say nothing about energy or OEM behaviour;
  - the rented phones were one device per model;
  - the personal phone is one device on one network.

## Decisions needed (answer in PR #2)

**A**

| # | Item |
|---|---|
| A1 | Done: B12 v2, as above. |
| A3 | For information: the B12 post-freeze diagnosis above. The `mut*` keys are unchanged. |

**C**

| # | Item |
|---|---|
| C1 | Define the `dev*` keys. Also say whether lifecycle counts use the pre-registered denominator (Galaxy `menqueue` 19/20) or the sensitivity version (19/19). The pre-registered one is B's default. |
| C2 | Regenerate `macros.tex` (`\impLoc` changed with the fixture extras) and `tests_macros.tex`. |
| C3 | Add `racePhone*` SCHEMA keys if the paper should cite Test 1 on the phone; otherwise it stays in the card. |
| C4 | Acknowledge that `sweep*` (B4 v3) and `mut*` (B12 v2) changed in `summary.json`. |
| C5 | Decide how to cite post-hoc results (B2 oracle v3, B10 Eq. 2 decomposition, post-freeze diagnoses). All are labelled exploratory. |
| C6 | Review the B8 draft, then merge PR #2. |

**Outside person:** B9 (clone + `make -C artifact all`) by 2/12.

## Update after C's answers (21/11)
- C exports the requested keys through `derived()` in `make_summary.py` on branch `c-final` (commit eba8ba0), computed from these frozen analysis outputs. B's equivalent computation was withdrawn from `b-exp` so the two branches merge cleanly. All 60 keys B computed are identical in C's `summary.json`, which has 67 keys. C's 7 extra keys also match the cards: `lifeFourteenEnq` 80, `lifeFifteenEnq` 80, `mutBaseLeak` 0, `mutThreeLeak` 0, `splitAfterAck` 0, `sweepLogged` 440, `sweepLockStalls` 1.
- Static send-path audit of AirGuard (C's optional item): see `b2-card.md`, last section.
  - The donation path is mediated in the fenced build, at the direct-call level.
  - 23 other network call sites per build (maps, images, URL check, library internals) are not mediated. The paper keeps this as a limit.
