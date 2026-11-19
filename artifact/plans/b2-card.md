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

## Open items before the pilot
- Implement patches (worker, consent log, receiver, Gradle flavor for stock/fenced) and a `campaign_airguard.py` driver.
- Pilot on P04AvdA (one trial per schedule), then freeze N/seed/timeouts here. Emulator slot per plan: 26–27/11.
