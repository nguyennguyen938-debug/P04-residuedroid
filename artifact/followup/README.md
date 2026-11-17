# Follow-up evidence, 2026-11-15–16

All new runtime measurements use emulators on one shared host. The author deferred physical-device work. No production deployment, physical-energy measurement or external artifact retrieval is claimed.

## Matched campaign

`campaign.py` runs five variants with identical durable lineage/epochs and transport. Two AVD configurations each contribute 20 valid trials in each of seven schedules, 140 paired trials per configuration. Four read-only instances per configuration run disjoint seeded ranges; they are not eight independent devices. Every variant participates in each trial. The host renderer is used with Vulkan disabled.

All recorded failed attempts remain in `results/review-followup-20261115/matched-*`. Failures are replaced using new trial IDs, never overwritten. Restart handling matches AVD and port and reinstalls the frozen APKs because a fresh read-only instance loses installed packages. Earlier harness failures are retained and excluded. Incomplete, unrecorded attempts can leave receiver records: the oracle requires receipt time to lie within the completed trial's host interval. `matched-outcomes.json` lists exclusions. `matched-summary.json` and `matched-paired-contrasts.json` preserve whole-trial pairing and bootstrap within configuration, schedule and instance; a zero empirical interval is not a population impossibility guarantee.

## HTTPS and cost

`tls_suite.py` records eleven TLS conditions with 20 trials each, plus three HTTP cost conditions with 20 trials each. Android 15 runs TLS 1.2 using SSLEngine and SocketChannel. Test CA/key files are public fixture credentials, not user secrets. Each socket handoff is at most 4 KiB and fenced under the same cross-process coordinator. Handshakes and response waits occur outside that lock. The prototype does not implement pooling, proxies, early data or renegotiation; socket close is abortive, not an orderly TLS close-notify exchange.

`tls-final` and `http-cost` are the analyzed cohorts; all pilots remain excluded. The raw case name `labels-missing` actually delivered a malformed value after shell expansion and is reported as malformed, not as evidence about absent labels. Valid but incomplete provenance passes, demonstrating the boundary of fail-closed checks. Mixed-source blocking suppresses the entire request, including its permitted contribution.

Elapsed/CPU cost includes handshake, logging and response, but excludes payload allocation. Fixed cell order and shared host load limit comparisons. Process CPU is not physical energy. Accepted ciphertext before acknowledgement is not exact kernel-unsent residue at acknowledgement; delayed queue snapshots cannot establish that quantity.

## Regeneration and source

`make -C artifact all` regenerates recorded statistics/tables/figures and builds the paper without running devices. `followup/analyze_tls.py`, `followup/matched_oracle.py` and `followup/render.py` are the follow-up analysis entry points. Frozen measured APK hashes, launch manifests and raw logs accompany each campaign; compiled APKs are omitted from the review ZIP. Build them using the fixture build script and pinned SDK/JDK configuration. Set explicit JAVA_HOME to Java 17 when building Android components.

For a new runtime campaign, use a fresh `--out` path; never overwrite the recorded evidence. `tls_suite.py --out <new-directory> --serial <owned-emulator>` requires the TLS fixture and reverse port mapping described in its source. The matched campaign accepts explicit serial, AVD, receiver port, trial range and APK directory. Independently implement an oracle using raw receiver receipts, device write-attempt/return records, policy requests/acknowledgements and source epochs to cross-check the supplied analysis.

The mediation scanner flags potential network bypasses; it does not prove reachability or cover reflection/native code/IPC. The citation inventory is complete for local keys, while external bibliographic verification is partial. See `codex-citation.md` and the execution report.
