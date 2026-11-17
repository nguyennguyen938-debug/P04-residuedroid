# Exclusions and provenance

Historical raw data and its original selection rule remain unchanged. The revision does not reinterpret pre-write COMMIT events as socket acceptance. No phone, HTTPS, current Android version, production trace, or public artifact hosting is claimed.

## Revision pilots (never pooled into final measurements)

- `pilot-socket-A`: the ordered broadcast command kept its PendingResult open for the send and serialized withdrawal behind it. Failed barriers expose this harness error. The revision sender command returns immediately; completion is observed from events.
- `pilot2-socket-A`: functional pilot after asynchronous command correction, before freezing the micro-experiment.
- `pilot-write-phase-comparator-{A,B}`: the first 51-case blocks held the comparator lock over connection/response as well as writes. These are excluded in full. Final `socket-{A,B}` use a write-phase-only comparator; a live-TCP regression test verifies that response waiting holds neither lock mode.
- `pilot-acra-B`: early unrestricted-collector SDK smoke tests, before the final restricted-collector embedding.
- `pilot-matomo-A-missing-timber`: missing transitive Timber dependency; the diagnostic and failed case are retained.
- `pilot-matomo-A-success`: successful functional smoke tests before the final source/dependency freeze. Final `matomo-A` is distinct.
- The first ACRA conformance launch failed APK installation because the old build script regenerated its debug key. It is retained in stage logs. Subsequent builds retain explicit public debug signing material.

## Main-run validity

A complete matched trial includes all five variants on the same AVD/schedule. Exclude a whole paired trial for a setup error, vanished emulator/restart, unreadable paired device logs, unverified network-loss injection, or a host action gap above 200 seconds. Keep the diagnostic, never call it a clean result. The AVD-A disappearance during the first reboot sequence is recorded in `diagnostics.jsonl` and `matched-A/schedule.jsonl`.

The first A block completed pending and kill before that failure; fixed block 5 attempted the affected remaining schedule cells but a second graphics-context failure interrupted it. A fixed block 6 attempted the five affected cells with software rendering but encountered the same EglContext cleanup crash; fixed block 7 repeats those cells with the host renderer and Vulkan disabled. Blocks 1–4 run the complete schedule matrix. The replacement attempts respond to recorded emulator failures, not measured policy outcomes; valid earlier trials are retained. AVD-A block 6 used SwiftShader; block 7 and subsequent socket runs use the host renderer with Vulkan disabled. Earlier AVD-A trials and AVD-B use guest rendering. Matched bootstrap strata include this environment phase. The replacement-renderer stratum has one trial per affected schedule and cannot estimate within-stratum variation. Final counts and per-stratum samples are generated from raw logs rather than assumed from targets.

Socket tests retain every attempt, barrier failure, missing return, timeout and missing acknowledgement. The final targets are ten blocks per AVD. Positive returned counts can be known, while an interrupted attempt remains unknown. Receiver prefixes and complete requests are independent observations; host time is never subtracted from guest time. No missing label, missing return or opaque body is silently classified as permitted.

## Build mapping

- Historical implementation: `pre-revision-source.tar.gz`; raw historical campaigns retain their original APK/source metadata.
- Matched experiments: measured `fixture/build/revision-apk` binaries and the original `frozen-v2` source manifest. Later source changes add the micro-experiment comparator without changing these measured APK files.
- Final socket micro-experiments: `fixture/build/socket-v3-apk` and `frozen-socket-v3`; each `socket-{A,B}/frozen-start*` also pins the harness before that run. Before installing this test, the harness stops other ResidueLab packages and clears the socket fixture to prevent leftover jobs from earlier stages. Host command round-trip timestamps are distinct from guest policy acknowledgement timestamps.
- ACRA normal-path revision trials: restricted-collector APK installed at `acra-v4-B` startup, pinned by `frozen-acra-v3`. Later recovery hardening and the pending-settings UI are pinned by `frozen-acra-final-ui` and checked by `acra-conformance-final` plus the separate `acra-final-A` smoke run; normal-path runs are not silently relabelled as recovery tests.
- Matomo final runs: `frozen-matomo-final`, including pinned binary dependencies and the final test APK.

Manifest creation times are recorded by the filesystem/package log; a later complete snapshot does not retroactively establish a pre-run freeze. The final artifact includes both measured sources and current corrected sources. Pilot/failed outputs are retained but excluded explicitly by final-run directory selection.

The SwiftShader replacement stage was terminated after the emulator disappeared before its schedule outcome was appended. Its start metadata and extracted crash stack remain as an incomplete attempt; it is not silently included among completed valid trials or assigned a policy outcome.

The first final AVD-A ACRA install encountered an older signing key inherited from the read-only base image. `acra-conformance-final-install-failure` preserves the failed install and source freeze. The two test packages were removed from that isolated overlay, then the final suite was rerun. Old and final installed APK hashes are retained; this repair does not modify the shared base AVD.
