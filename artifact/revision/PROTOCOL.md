# Frozen revision protocol

Scope: P04 only; eight-hour setup/experiment cap from the UTC start in `execution.json`; editing and final document validation are outside that cap. No handset. ACRA first; Matomo if feasible. Two existing Android 13 AVD images run in isolated read-only overlays on ports 5640 and 5642, distinct from historical ports.

## Targets

- Matched metadata: five paired blocks × seven schedules × five variants on each AVD; the schedule seed is `revision-20261115`. Preserve the first paired block before repetitions. Bootstrap whole paired trials, stratified by AVD/schedule/rendering phase, 10,000 draws, seed 20261115.
- Socket matrix per AVD/block: two authorization barriers (early/fenced), four crash observations (after authorization, positive prefix, native-return-before-count, full handoff before response), five label cases, and 40 backpressure combinations (five loads × same/unrelated scope × same/cross-process withdrawal × whole-write/chunk lock). Target ten blocks. Native-return-before-count is an added measurement-loss control, not a claim to hit an arbitrary instruction inside the syscall.
- Loads: normal and withheld response use 16 KiB payloads; slow and stalled reads use 8 MiB; long batch uses 1 MiB. Slow reads drain at 1 KiB/s; stall and delayed response wait six seconds. Sender deadline five seconds; receiver observation window is bounded; harness command watchdog thirty seconds. Report actual tail samples and no-ack counts, not a population p99 bound.
- ACRA: ten disable/control trials per package, with three reboot/reboot-control trials per package; 45-second observation window and 70-second report-age requirement. Direct adapter/store conformance is separate.
- Matomo: five blocks × stock/fenced × control/withdrawal with a deterministic pre-send barrier. This validates a running dispatcher path; disk-cache recovery and production deployment remain outside this test.

No trial is extended or repeated because its outcome is unfavorable. The explicitly recorded AVD failure permits a fixed replacement schedule block, applied to all variants together. Failed pilot protocols are frozen and excluded before final runs. Changed protocol versions receive distinct directories/manifests.

## Source boundary

The shared transport has no hidden asynchronous stream below its check. One SocketChannel owns one writer. A positive native write return is local acceptance; neither it nor an authorization marker establishes remote receipt. A pending write with no return is unknown. Cancellation and retry-entry checks are layered optimizations; only supported, mediated chunks carry the stated serialized guarantee.

AVD-A graphics failures triggered fixed replacement cells at blocks 5, 6 and 7; block 6 tried software rendering and block 7 uses the host renderer with Vulkan disabled. See EXCLUSIONS.md. This is an environment change, not another device or a claim of independent hardware replication.

Tail summaries use the empirical nearest-rank p95, median of the two middle observations when sample size is even, and observed maximum. Guest policy latency and host command round-trip are reported in separate fields. They are descriptive order statistics, not confidence bounds or population service guarantees.

Socket load/process/scope/lock cells run in a fixed documented order within each block, rather than a randomized counterbalanced order. Treat the latency comparison as controlled stress observations; device/rendering-phase differences and potential order effects limit generalization. Per-AVD summaries accompany the pooled descriptive table.

The timing build emits attempt/return observations inside the write critical section. Reported latencies therefore include this instrumentation and policy-store work; they are not an estimate of an uninstrumented production client. The same transport event hooks are used by both lock modes.

Both AVDs share one host and some stages overlap (including matched trials on one AVD while socket trials run on the other). The retained stage timestamps describe that load. Neither two AVD labels nor bootstrap resampling provide independent-hardware replication or remove temporal/shared-host dependence.

Normal and long-batch requests can finish their write phase before the harness issues withdrawal. They are fast-path controls, not evidence that every withdrawal overlaps a native write. `write_phase_incomplete_at_request` and `first_write_before_request` expose the observed phase coverage. The slow/stalled conditions exercise continuing write phases; response-only waiting is tested separately.
