# Experiment card — b2 (real app end-to-end: AirGuard; protocol v0 = design draft)

Status: DRAFT (design; freeze after the pilot). Owner: B (Duy). Plan `[R3]` B2: "Tích hợp app thật từ đầu đến cuối, chạy pen,
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
