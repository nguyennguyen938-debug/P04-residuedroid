# ResidueDroid artifact (P04, MobiSys 2027 submission)

Empirical table entries and evaluation macros are generated from files in `results/` by
`scripts/render.py` into `../manuscript/generated/`. `make all` regenerates them from the recorded raw data and rebuilds
the PDF. The revision additionally generates its tables from `revision/`; see `revision/INTEGRATION.md` for the audited boundary.

## What was actually run (real, not simulated)

| Experiment | Where | Raw data | Producer |
|---|---|---|---|
| Emulator campaign: 9 enforcement variants × 7 lifecycle schedules × ≥50 valid trials, 10 tenants | Android 13 emulator (android-33 google_apis arm64-v8a rev 17), AVDs P04AvdA (console 5600) and P04AvdB (5602) | `results/raw/c1/{A,B}/` (`schedule.jsonl` host actions, `device_events.jsonl` per-app SQLite event logs, `sink/ingest.jsonl` every submission) | `harness/campaign.py`, `harness/sink.py` |
| Micro-benchmarks: overhead, serialization race, label durability under SIGKILL | AVD A or B | `results/raw/micro/` | `harness/micro.py` |
| Real-library case: ACRA 5.14.2 stock vs fenced sender (protocol v3, 2026-11-09) | AVD A | `results/raw/acra/` (`trials.jsonl`, `attempts.jsonl` failed attempts, `diag.jsonl`); earlier invalid runs in `results/raw/acra_INVALID_*` (not analyzed) | `harness/acra_case.py`, `acra/` |
| Substrate runs: WorkManager 2.9.1 and AlarmManager, variants none/conv/rd × pen/kill/fstop/reb × 20 trials | AVD A (WorkManager), AVD B (AlarmManager) | `results/raw/sub_work/`, `results/raw/sub_alarm/` (`*_INVALID_short_window` = discarded first attempts) | `harness/campaign.py --substrate work|alarm`, `workmanager/`, `fixture/` |
| Static screen of 360 F-Droid APKs | host | `static/data/scan/*.json` (APKs in `static/data/apks/`, SHA-256 = index) | `static/dexscan.py`, `static/scan_corpus.py`, `static/static_summary.py` |
| Smoke test (mechanism-level toy model, not data) | host | `../others/smoke/` | `../others/smoke/smoke_test.py` |

The only modelled element is the fixture itself: `fixture/` is a purpose-built app (ResidueLab) whose ten tenants each
state a contract and whose enforcement variants encode common patterns (cancel, enqueue check, job-start check, ...).
Their behavior under lifecycle events is measured on the platform. ACRA is real, unmodified library code.

## Layout
- `fixture/` — ResidueLab + ResidueDroid library (framework-only Java; `build.sh` uses javac 17 + d8 + aapt2, no Gradle;
  one APK per variant via `--rename-manifest-package`). Core classes: `Fence` (egress wrapper, Algorithm 1),
  `Policy` (epochs, withdrawals, contract rule Eq. 1), `Work`/`Sched`/`UpJob` (persisted JobScheduler jobs), `Bench`.
- `acra/` — AcraLab: ACRA 5.14.2 AARs + kotlin-stdlib 2.4.20 (Maven Central, `deps/SHA256SUMS`); `FencedSender`.
- `harness/` — campaign driver, host sink, micro-benchmarks, ACRA case.
- `scripts/` — `oracle.py` (independent contract oracle), `summarize.py`, `render*.py`.
- `static/` — corpus selection, download (SHA-256 verified), DEX scanner, summary.
- `results/RUNLOG.md` — dated log of every run, failure, diagnosis and fix.

## Reproduce
```
export JAVA_HOME=/path/to/jdk-17
export ANDROID_HOME=/path/to/android-sdk
source env.sh                              # validate explicit toolchain paths
make apks                                  # rebuild historical fixture variants and ACRA
make campaign                              # historical campaign; creates results/rerun, needs two configured AVDs
make micro && make acra && make substrates  # ~1 h + ~2.5 h + ~2.5 h
make corpus                                # ~30 min download + 10 min scan
make all                                   # regenerate CSVs, tables, figures, macros, PDF
```
Setup conditions the harness enforces: apps are cleared, opened once and put in the `active` standby bucket before each
trial (never-opened apps sit in bucket NEVER and JobScheduler does not run their jobs); network loss is a guest
`iptables` REJECT rule toward 10.0.2.2 applied per app. Trial validity rules (host sleep, emulator restart, unreadable
device log, unverified net cut) are in `scripts/summarize.py` and §7.1 of the paper.

## Honesty notes
- Residual storage is never counted as a violation; the oracle judges each delivered item against its tenant's contract
  at its historical pre-write authorization marker (device sequence), which can undercount physical handoffs, using only sink-visible tracer tags for content.
- Encrypted bodies are reported as unknown, not clean. Historical outstanding counts are only authorization/response overlap; new socket tests distinguish accepted prefixes and receiver observations.
- The static screen is a candidate screen (over-approximate reachability, with two screening depths, not bounds, and a 20-entry
  manual plausibility check); it establishes no violation.

## 2026-11-15 revision

`results/revision-20261115/` keeps frozen source manifests, pilots, failed attempts, socket tests,
matched metadata campaigns, ACRA conformance, and Matomo runtime tests separately. Historical raw
logs and `review.md` are retained. `revision/oracle_v2.py` classifies missing write-return evidence as
unknown; `revision/matched_oracle.py` uses receiver tracer content and guest event order independently
of enforcement decisions. `revision/historical_uncertainty.py` resamples whole paired trials.

For a clean extraction, use Python 3.11+, JDK 17, Android SDK platform 33/build-tools 34.0.0, and
TeX Live with acmart and the packages in main.tex. Set JAVA_HOME and ANDROID_HOME explicitly, then run
`make all` to regenerate recorded results and the PDF. `make apks` builds the fixture and ACRA;
`bash matomo/build.sh` builds the second SDK embedding. Debug signing material is public test material,
not a production credential. APK bytes can differ with toolchain timestamps; dependency and recorded
APK hashes pin measured binaries.

The 5.7 GiB corpus APK cache and shared Android SDK/AVDs are excluded from the anonymous archive.
The corpus manifest and retrieval scripts remain. Numeric regeneration uses the included scan JSON;
rerunning the scanner requires fetching APKs first. Retrieval verification checks all 360 local hashes
and a declared remote sample, not fresh retrieval of the entire remote corpus. The package is local;
there is no claim of anonymous public-host availability or independent third-party reproduction.

Build the matched variants with `VARIANTS="menqueue mstart mlayer mfence mboth" bash fixture/build.sh`. Runtime revision protocols and measured-build mappings are in `revision/PROTOCOL.md` and `revision/EXCLUSIONS.md`. Historical experiment Makefile targets write to `results/rerun` by default; choose a fresh `RERUN` for each run. Recorded results are inputs to `make all`, not overwritten by these targets.

Use a fresh AVD data image for newly rebuilt APKs, or remove only the relevant `org.residuelab.*` test packages first: a rebuilt debug APK can have a different signing key from an older installed test app. Run new experiments in a scratch copy with fresh output directories. The archived stage commands record the exact measured protocols; `make all` regenerates the included results without launching devices.
