# Experiment card — b2 (real app end-to-end: AirGuard; protocol v0 = design draft)

Status: FROZEN 19/11 (protocol v1, section "Freeze" below) after pilot-2; pilot-3 checks the driver fix, then the final. Owner: B (Duy). Plan `[R3]` B2: "Tích hợp app thật từ đầu đến cuối, chạy pen,
kill, reb, net (thêm fstop nếu kịp), mỗi lịch 20 trial; so bản gốc với bản có fence, kèm luồng được phép làm đối chứng".
S1 proposal: AirGuard (`b1-screening.md`), builds from source at the F-Droid commit (`plans/b1/build_airguard.sh`).

## Why AirGuard fits
`SendStatisticsWorker` (WorkManager, periodic, retry with backoff) reads beacons/notifications from Room since
`lastDataDonation` and POSTs them (Retrofit/OkHttp) to the study server. Opting out (`share_data` off) only cancels the
periodic work: a run already in progress, or one retried later, is not re-checked, and scanning continues while opted out,
so after re-consent the next upload can include data collected outside consent. Promise coded PENDING by C10.

## Integration design (B decisions; patches applied to the clone, never committed into the app's tree)
1. **Durable epochs without a schema change:** a durable consent log (app-private file/SQLite table owned by the
   integration) records `(epoch, granted_at, withdrawn_at)`. Withdrawal = one transaction under the coordinator lock
   (same `Coordinator` file lock as the fixture) that closes the open interval and increments the epoch. An item's source
   label = the consent interval containing its timestamp (`receivedAt` / `createdAt`); none → forbidden. This is the
   "equivalent representation" of Proposition (Information needed by the check): retained epochs keyed by collection time.
2. **Fenced send:** the worker's `api.donateData(...)` is replaced (fenced variant) by serialising the same body with the
   app's own converter and posting it through ResidueDroid's `HttpTransport.postMode` (chunk fence; policy = every item's
   label is the current open epoch). Stock variant keeps Retrofit. Both point to the experiment sink (base URL override,
   cleartext allowed only in the test build).
3. **Test hooks (both variants, identical):** a debug-only broadcast receiver to insert synthetic beacons/notifications
   with given timestamps (the emulator has no BLE), toggle `share_data` (grant / withdraw through the app's own preference
   path), and run the worker now (WorkManager test driver / `cmd jobscheduler run`). `BuildConfig.DEBUG` early-return removed
   in the test build only.
4. **Permitted-flow control:** items collected inside the current consent interval must still be delivered (deficit check).

## Schedules and oracle (to fix at freeze)
- pen, kill, reb, net (+fstop) × 20 trials, stock vs fenced in the same trial (two packages: applicationIdSuffix kept per
  variant so both install side by side).
- Oracle (sink-side, independent of the app's decisions): an uploaded beacon/notification whose timestamp lies outside a
  consent interval, or inside a withdrawn interval when the upload attempt began after WITHDRAW_ACK, is a violation;
  permitted items missing = deficit. Unknown when write returns are missing (as matched oracle).

## Driver (19/11): `followup/campaign_airguard.py`
Per trial, both builds in lockstep (order shuffled per trial from the seed): grant → insert 'pre' → [netloss: link cut, worker
run fails and is retried] → withdraw → insert 'optout' (scanning continues while opted out) → lifecycle (kill: SIGKILL; reboot)
→ re-grant → insert 'post' → [netloss: link restored, retry runs | else: run worker] → quiescence → read residue-events. Oracle:
an uploaded 'pre' or 'optout' beacon = violation; a missing 'post' beacon = permitted deficit (a fenced request mixing old and
new items is blocked whole — the split policy of B3 would recover the 'post' items; reported, not hidden).

## Open items before the pilot
- Implement patches (worker, consent log, receiver, Gradle flavor for stock/fenced) and a `campaign_airguard.py` driver.
- Pilot on P04AvdA (one trial per schedule), then freeze N/seed/timeouts here. Emulator slot per plan: 26–27/11.

## Pilot-1 (19/11 22:02–22:17, P04AvdA, 1 trial × 4 schedules; excluded) and fixes before pilot-2
- pen000: first hook broadcast after install timed out (90 s; cold start) → trial_error. Fix: one no-op hook per app after
  install with a 300 s timeout, recorded in meta.json (`warmup`).
- kil000, reb000, net000: hooks and consent events fine (GRANT/WITHDRAW/INSERT/RUN_ENQUEUED in both builds), but no
  WORKER_SEND and **no request at the sink** (not even ping): the app's `network_security_config.xml` denies cleartext for
  every host, which overrides the patch's `usesCleartextTraffic`, so Retrofit refused http://10.0.2.2 (an IOException,
  which the worker's `catch (e: Error)` does not catch → worker failure, no event). Fix (apply.sh `nsc`): cleartext permitted
  for 10.0.2.2 only, both builds identical. Rebuilt test APKs (stock e53e5254…, fenced 30eb823f…; previous builds kept
  in `realapp/airguard/build/v1-20261119-1740/`). App behaviour not changed: the worker's own error handling is kept as is.
- Pilot-2: same driver/schedules, fresh dir `results/round3/b2/pilot-2`.

## Pilot-2 (19/11 22:28–22:35; excluded) — mechanism review, no outcome used
Network reached the sink (36 requests, both ports), warm-up ok (stock 29.8 s, fenced 8.8 s), 4/4 trials ran. Two design
assumptions were wrong for the real app: (1) AirGuard runs its worker as soon as consent is granted (periodic work
scheduling), so 'pre' beacons can be donated legitimately *before* the withdrawal — the oracle needs a time bracket, not
"every donation is after the withdrawal"; (2) the driver's quiescence predicate counted donation events from earlier in the
trial, so it waited only 5 s after the harness 'run'. Also observed: on netloss the app does not retry a failed run (the
worker's `catch (e: Error)` lets the IOException fail the work), so no donation follows the link restore — app behaviour,
kept and reported.

## Freeze (protocol v1, 19/11, before pilot-3 and the final)
- Builds: `realapp/airguard/build/airguard-{stock,fenced}.apk` (stock e53e5254…, fenced 30eb823f…; SHA256SUMS there;
  installed hashes in meta.json). AVD P04AvdA (android-33), emulator-5666, sinks 8796 (stock) / 8797 (fenced).
- Driver `followup/campaign_airguard.py` (as above; quiescence = a new donation-end event after the harness run, max 90 s).
  Schedules pending, kill, reboot, netloss; **N = 20 trials per schedule**, both builds in every trial (order shuffled per
  trial), seed `b2-20261119`, 4 beacons per batch. fstop not run (plan: "nếu kịp"; not added).
- Oracle `followup/analyze_airguard.py` v2 (synthetic test passed): batch by uniqueId; host-clock withdrawal bracket
  [ws, we] per build; violation = any 'optout' beacon donated, or a 'pre' beacon in a request whose worker-run ping reached
  the sink after we; 'pre' in a request neither before ws nor after we = unknown (reported per cell, never folded in);
  deficit = 4 − 'post' beacons donated. Wilson 95% on violating trials per (schedule, build).
- Validity (harness fields only): no trial_error; every hook ok; device alive at the end; both event logs read; both
  withdraw actions present. First 20 valid trials per schedule in k order; later valid ones unused.
- Replacement: environment failures only (trial_error / device not alive), new k from 20 (`--start 20`), cap 3 per schedule.
- Gate pilot-3 → final (mechanical): 4/4 trials valid, warm-up ok for both builds, ≥ 1 donate request at each port.
- Threats: one AVD, emulator, synthetic beacons (no BLE), the host sink replaces the study server (HTTP, not HTTPS),
  host-clock bracket leaves some requests unknown; the fence blocks a mixed request whole (split policy of B3 not applied).

## Outcome (final 19/11 22:50–23:53, protocol v1, autorun b2-final, guard 0)
- Logged / excluded / valid / analysed / unused: 80 trials (20 per schedule, both builds in each) / 0 / 80 / 80 / 0.
  Data `results/round3/b2/final`; analysis `results/round3/b2/analysis/airguard-summary.json` (oracle v2).
- Violating trials (Wilson 95%): stock 20/20 [0.839, 1] in pending, kill and reboot; fenced 0/20 [0, 0.161] in every
  schedule; netloss 0/20 for both. Stock violations: 'optout' beacons (collected while opted out) donated after re-consent
  in 20/20 trials of pending, kill and reboot (80 beacons each), plus 'pre' beacons in an 'after' request in 2/20 pending
  trials. The fenced build blocked a donation in 20/20 trials of pending, kill and reboot and delivered all 'post' beacons
  in a later run (deficit 0).
- Unknown (reported, never folded in): fenced 8/20 (pending), 9/20 (kill), 9/20 (reboot) trials had 'pre' beacons in an
  'ambiguous' request (completed after ws, worker run opened before we); stock had such requests in 10–11/20 trials too, all
  in trials that also violate. These are the app's own consent-time run racing the withdrawal; the host-clock bracket
  cannot order them.
- Negative / null results: netloss — no donation after the link returned in either build (the app does not retry a failed
  run), so every 'post' beacon is missing: deficit 80/80 beacons for stock and for fenced (20/20 trials). 'pre' beacons
  were donated before the withdrawal (permitted) in 8–19 of 20 trials per cell.
- Deviations: none from the frozen protocol. Threats as in Freeze (one AVD, synthetic beacons, HTTP sink, host-clock bracket).

## Oracle v3 (20/11; post-hoc, written before it was computed; v2 stays the pre-registered result)
Reason (measurement, not outcome): v2 orders a sink request against the withdrawal with the host clock only, which leaves
8–9/20 fenced trials per schedule 'unknown'. The fenced build sends `X-Request-ID` (logged by the sink for 135/135 donate
requests) and logs guest transport events per request (BYTES_ACCEPTED with `request=`), so the order can be taken on the
guest clock alone — the channel estimand of R4.1 (WRITE_ATTEMPT/BYTES_ACCEPTED vs withdrawal transaction order).
- Fenced variant: for a complete sink donate request with id R, take the guest events of that trial and variant: the first
  WITHDRAW_ACK and the BYTES_ACCEPTED (n > 0) with request R; compare `wall_ms` (guest wall clock; mono_ns resets at reboot).
  'before' if the last accepted chunk of R is strictly before the ack; 'after' if the first is strictly after; 'straddle'
  otherwise; 'unmatched' if R has no guest event. Content (which beacons) still comes only from the sink body.
- Violation = an 'optout' beacon donated, or a 'pre' beacon in an 'after' request (as v2). 'pre' in 'straddle' or
  'unmatched' = unknown. Stock build (no request id, no guest transport events): v2 host bracket unchanged.
- Validity, first-N, cells as v2. Output `results/round3/b2/analysis-v3` (`analyze_airguard.py --order device`); the default
  (`--order host`) reproduces `analysis` byte for byte. Unit test `followup/test_analyze_airguard.py`. Reported next to v2.
- Result (20/11, `results/round3/b2/analysis-v3/airguard-summary.json`; unit test 9/9): fenced unknown trials 8 → 0
  (pending), 9 → 0 (kill), 9 → 0 (reboot); every one of those 'pre' requests was fully accepted on the guest before the
  withdrawal ack ('pre/before' 75 requests, 'post/after' 60; no 'straddle', no 'unmatched'), so they are the app's permitted
  consent-time run. Violating trials unchanged: fenced 0/20 [0, 0.161] in every schedule, stock 20/20 in pending/kill/reboot.
  Stock is not re-ordered (no request id). Report v2 (pre-registered) and v3 (post-hoc) together.

## Static send-path audit (post-freeze, 21/11; requested by C in PR #2; no device)
- `followup/mediation_check_apk.py` (same sink set, OkHttp rule and approved classes as `mediation_check.py`, which is fixed to
  the recorded review-followup APKs and is not rerun) on the B2 final APKs (fenced 30eb823f…, stock e53e5254…) →
  `results/round3/b2/mediation/mediation.json`. Direct DEX calls only (no native, reflection, dynamic loading or IPC).
- Donation path: in the fenced build `SendStatisticsWorker.doWork` calls `FencedDonation.send` → `HttpTransport.postMode`
  (approved), and no app method calls the Retrofit `Api.donateData` (only its generated default-args stub); in the stock build
  `doWork` calls `Api.donateData$default` (Retrofit) and nothing calls `FencedDonation.send`. The donation send path is
  mediated in the fenced build at the direct-call level.
- Other network sites: 25 sink call sites per build, 2 approved (HttpTransport), 23 flagged in both builds, by package:
  osmdroid tile provider 7 + bonuspack 1, Glide 2, OkHttp internals 3, Retrofit `OkHttpCall` 2, okio 3, the app's
  `Utility.isValidURL` 2, kotlin `readBytes` 1, coroutines 1, constraintlayout 1. These paths are not mediated; whether any of
  them can carry the statistics data is not established here (would need a manual review). Claims stay limited to the
  mediated donation path.
