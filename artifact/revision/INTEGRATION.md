# Audited integration protocol (2026-11-15)

This revision is a cooperative test embedding, not a production deployment or a general HTTP-client interceptor. Only the shared nonblocking plain-HTTP sender is covered. Android 13 AVDs exercise it; a phone and newer Android are not tested. HTTPS, native sockets, redirects, proxies, pooled writers, WebViews, system-mediated IPC, arbitrary ACRA collectors and other SDK senders are outside the audited path.

## Observation and policy contract

`AUTHORIZATION_LOGGED` expresses intent. `WRITE_ATTEMPT` precedes a native write; a positive `BYTES_ACCEPTED.n` records the accepted prefix. `WRITE_RETURN_BOUNDARY` is a fault-injection observation without an accepted count. `REQUEST_HANDED_OFF` means the entire wire request was accepted locally. The independent receiver records prefixes and complete requests; `RESPONSE_RECEIVED` is separate. An absent return never proves zero acceptance. Wire counts include HTTP headers as well as the body; the request-wide label union is conservative for every prefix. Each write has at most 4096 requested bytes; one channel has one writer. Readiness waits and response reads occur outside the coordinator. The coordinator combines a canonical-file local mutex and an OS file lock across processes.

A withdrawal is requested, durably changes the epoch/flag, and only then is acknowledged. An operation timeout does not acknowledge success. Five seconds is an operation deadline with best-effort checks, not a hard latency guarantee for Android scheduling or SQLite. Requests retain original source epochs across retries. No exactly-once or server deletion guarantee is provided. Already accepted prefixes can arrive after acknowledgement. Conservative union labels can abort the remaining permitted portion of a mixed request when any source becomes invalid.

The Android API documents nonblocking SocketChannel writes and returned byte counts. Pinned AOSP android-13.0.0_r1 files in `transport-source/` trace SocketChannelImpl -> IOUtil -> SocketDispatcher -> FileDispatcherImpl.write0 -> native write(fd,buf,len). Heap-buffer copying is synchronous within that call; the returned count updates the input position. This source audit supports the chosen boundary, but is not a binary equivalence proof for every Android vendor build. API reference: https://developer.android.com/reference/java/nio/channels/SocketChannel . Retrieval URLs and hashes accompany the source.

## ACRA call-site map

| Path | Change / retained behavior |
|---|---|
| `AcraApp.attachBaseContext` | Initialize policy before ACRA; use ACRA 5.14.2 AdvancedSenderScheduler with network constraint. Restrict collectors to REPORT_ID, CUSTOM_DATA, STACK_TRACE. Historical logcat and arbitrary collectors are not covered. |
| `Cmd` crash collection | Store `crash:<original epoch>` and synthetic source tag inside CUSTOM_DATA in the persisted report. Conservative race with withdrawal may suppress a report; it cannot relabel an old report as new. |
| `Main` settings UI | Explicit queued-report contract, pending state, acknowledgement/error, enable-new-reports control. Both setting buttons are disabled while an operation is pending, preventing overlapping UI requests. UI uses the same `Fence.setEnabled` path as harness commands. |
| `Fence.initialize/read/write` | SQLite `policy(id=1,epoch,allowed)`, full synchronous transaction, marker before first initialization, guarded legacy text migration. Missing/corrupt state reads (-1,0); no implicit allow fallback. |
| `Fence.setEnabled` | Shared coordinator; transaction increments epoch on disable; preference commit in same serialized operation. Failed preference save reports no acknowledgement even if policy is already stricter. |
| `FencedSenderFactory` + build ServiceLoader registration | Replace ACRA's HttpSender for the fenced package. Separate `:acra` sender process uses same coordinator file. Stock package retains SDK sender for comparison. |
| `FencedSender.send` | Require syntactically valid and exactly current source epoch; serialize checks with each chunk. Normal denied return retires the report; IO exception delegates retry to ACRA, preserving stored custom data. Each invocation receives a new request UUID; attempt field is local to that invocation, not ACRA's global retry count. |

The migration never reconstructs a report label from the current grant. An existing legacy epoch file is imported only when valid. Malformed legacy state leaves policy unavailable and cannot be re-enabled without explicit trusted repair. Existing approved/unapproved reports without a policy store also leave initialization unavailable. Reports lacking trusted labels are retired, including otherwise permitted legacy reports; this availability loss is explicit. A missing policy database after initialization cannot be recreated automatically. Repair requires an explicit trusted recovery decision; re-grant cannot repair corrupt state.

No schema change is made inside ACRA's own report format beyond custom data. Report deletion and delivery are different outcomes. Tests must inspect both sink receipt and remaining report state. `TEST_SEND` is a debug-only adapter conformance entry, not an SDK lifecycle test. All exported harness receivers and debug flags must be removed before deployment.

## Fixture and matched metadata

All five matched variants persist the same source epochs in SQLite rows, derived label unions, and copied job extras. `menqueue` checks those labels at enqueue; `mstart` at job start; `mlayer` adds cancellation and retry-entry checks; `mfence` checks each socket chunk; `mboth` combines layers and final fencing. Conservative early checks can suppress an entire job when any selected source is invalid. The old boolean-only variants remain historical controls and are not used to isolate final placement.

Unlabelled, malformed, unknown-scope and future-epoch data fail closed on revision paths. Legacy historical variants retain their recorded behavior. T9 remains an intentional raw-socket bypass; T10 is opaque to receiver content attribution and must not be called clean.

## Matomo boundary

The second embedding uses the pinned Matomo 4.4 binary, actual EventCache/EventDiskCache, PacketFactory and DefaultDispatcher. A PacketSender adapter parses the original `rd_epoch` stored in each event query; its conservative union is rechecked for every chunk. A single-event GET packet is normalized to the SDK's bulk-POST JSON format. Missing labels retire the packet. Network failure returns false so Matomo can requeue original events. The paired comparator uses the stock PacketSender behind the same test-only pre-send barrier.

The runtime test exercises already queued events in the running dispatcher, not durable-cache crash recovery, mixed epochs, or arbitrary application identifiers. The test embedding promises to invalidate queued analytics events; stock Matomo behavior is not called a violation of a different app's wording. The Matomo policy initialization is a fixture setup path, not a general legacy-store migration implementation. Its runtime result must not inherit the broader ACRA conformance claims.

The oracle field `accepted_bytes` sums recorded positive native returns. When `measurement_unknown` is true it is an observed lower bound, not a total or a zero-handoff assertion. Receiver body prefixes and complete requests are joined by request ID; a receiver prefix larger than the recorded acceptance sum marks missing evidence. Receiver timestamps are never used to infer guest withdrawal order.
