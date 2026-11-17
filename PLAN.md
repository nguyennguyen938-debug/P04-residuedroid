# PLAN — P04 ResidueDroid (MobiSys 2027)

Venue: MobiSys 2027, `acmart` sigconf review anonymous, 12-page body. Abstract Nov 27, paper Dec 4 2026 (AoE).
Authoritative scope: proposal_v3.md §5 + novelty_audit_v2.md §5 (no RiskSync, no lease calculus, no remote deletion,
no knapsack ratio; no "first withdrawal measurement"; residual storage is not a violation; no recall claim).

## Artifact inventory (every table/figure → producer)

| Manuscript item | Content | Producer | Input |
|---|---|---|---|
| Fig. 1 `fig:overview` | cartoon overview (no numbers) | hand-drawn TikZ | — |
| Tab. `tab:contracts` | contract taxonomy (descriptive) | static text | audit §5 |
| Tab. `tab:corpus` | F-Droid screen | `static/static_summary.py` → `scripts/render.py` | `static/data/scan/*.json` |
| Tab. `tab:tenants` | fixture tenants (descriptive) | static text | `fixture/src/.../Model.java` |
| Tab. `tab:matrix` | violation rate variant × schedule | `scripts/summarize.py` → `render_campaign.py` | `results/raw/c1/{A,B}` |
| Tab. `tab:fp` | legit deficit / FP controls | same | same |
| Fig. `fig:bars` | prohibited items per tenant-trial | same | same |
| Fig. `fig:inflight` | P(violation) vs withdrawal offset + Eq.(2) prediction | same | same |
| Tab. `tab:cost` | overhead, race ablation, durability | `scripts/micro.py` | `results/raw/micro/*` |
| §ACRA numbers | real-library case study | `harness/acra_case.py` | `results/raw/acra/*` |
| inline macros | all prose numbers | `scripts/render.py` | `results/*.csv` |

## Data acquisition
- F-Droid index-v2 (SHA-256 in `static/data/index/`), 60 Tracking + 300 seeded-random INTERNET apps, APK SHA-256 verified.
- ACRA 5.14.2 AARs + kotlin-stdlib 2.4.20 from Maven Central (SHA-256 in `acra/deps/SHA256SUMS`).
- Emulator: android-33 google_apis arm64 rev 17; AVDs P04AvdA (5600) and P04AvdB (5602).

## Baselines / variants
none, cancel(+purge), enqueue, jobstart, conv(cancel+enqueue+jobstart), egress(declared scope, boolean, serialized),
rd (ResidueDroid), ablations volatile (in-memory labels, fail-open), taint (contract-unaware), noser (no serialization).

## Protocol and metrics
7 schedules (pen, kill, fstop, reb, rev, net, infl) × ≥50 valid trials, identical seeded parameters on both AVDs.
Oracle: sink-visible tracer tags + per-tenant contract; device sequence only for ordering. Metrics: violation rate
(Wilson 95% CI), prohibited items, legit deficit, unattributable, outstanding. Exclusions: host sleep, emulator restart,
unreadable device log, unverified net cut.

## Pipeline
1. `fixture/build.sh` → 10 APKs. 2. `harness/campaign.py` (A and B). 3. `scripts/summarize.py` → CSVs.
4. `harness/micro.py` (bench, stress, crash) and `harness/acra_case.py`. 5. `static/*` corpus screen.
6. `scripts/render.py` → `manuscript/generated/`. 7. `manuscript/build.sh`.

## Risks
Host sleep (mitigated: caffeinate -s around harness), emulator crashes (auto-relaunch + exclusion), JobScheduler
batching latency (poll until quiesced), static over-approximation (report depth-bounded lower bound + validation sample).

## Definition of done / honesty gate
Every number in the PDF comes from `generated/`; negative results (uncovered path leaks; volatile/taint failures) are
reported; no violation claimed from storage residue; ACRA behavior reported as configuration-specific, not as a bug.
