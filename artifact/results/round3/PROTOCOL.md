# Round 3 (role B) — protocol index

Each task's protocol is its card in `artifact/plans/` (filled from `PLAN-ROUND3.md` / `HUONG-DAN-B.md`; B decisions where the
plan is silent are marked there). Versions were changed only before any final trial of that version, after a pilot or a
mechanical gate, never after looking at outcomes; earlier versions' data stay in the results and are reported.
Exclusions: `EXCLUSIONS.md` (generated). Numbers to C only through `summary.json` (`make_summary.py`). Run history:
`artifact/results/RUNLOG.md`. Unattended runs: manifests in `artifact/plans/autorun/`.

| Test / task | Card | Version used for keys | Final data (`results/…`) | Analysis | Keys |
|---|---|---|---|---|---|
| Test 6, two phones | `plans/test6-card.md` (+ `test6-card-v3.md`) | v2 (lifecycle, TLS); v3 TLS rerun with 60 s deadline (Galaxy `concurrent`) reported alongside | `round3/test6/{pixel8a-j1,pixel8a-j2,galaxy-s1,galaxy-p02,galaxy-p03}`, v3 `pixel8a-v3-tls`, `galaxy3-tls`; freezes `frozen-test6-v1/v2/v3` | `followup/analyze_test6.py` → `test6/analysis`, `analysis-v3` | `dev*` |
| Test 4 / B11 | `plans/b11-card.md` | v1 | `round3/b11/{avd14-final,avd14-repl,avd15-final}` | `followup/analyze_b11.py` → `b11/analysis` | `life*` |
| Test 2 / B12 | `plans/b12-card.md` | v2 (fixture extra `regrant_agg`, A approved); v1 reported | `mutation-v2/{base,M1-union-latest,M2-stale-epoch,M3-extras-drop}` (v1 `mutation/…`) | `followup/analyze_mutation.py --root results/mutation-v2` → `mutation-v2/analysis` (v1 `mutation/analysis`) | `mut*` |
| B3 split policy | `plans/b3-card.md` | v2 (suite end predicate) | `round3/b3/final` | `followup/analyze_b3.py` → `b3/analysis` | — (raw, card §6) |
| Test 5 / B4 | `plans/b4-card.md` | v3 (receiver recv timeout 300 s, replacement rule); v1, v2 reported | `round3/b4/final-v3` + `final-v3-repl` (v2 `final-v2`, v1 `final`) | `followup/analyze_sweep.py` → `b4/analysis-v3-repl` (v2 `analysis-v2`, v1 `analysis`) | `sweep*` |
| Test 1 / B10 | `plans/b10-card.md` | v3 (guest netem shaper; v1/v2 gates failed, no final trial) | `round3/b10/final4`, calibration `pilot-calib4` | `followup/analyze_race.py` → `b10/analysis`; post-hoc Eq. 2 decomposition `followup/posthoc_race_eq2.py` → `b10/posthoc-eq2` (exploratory, keys unchanged) | `race*` |
| B2 AirGuard | `plans/b2-card.md` | v1 (frozen after pilot-2; oracle v2 with withdrawal bracket) | `round3/b2/final` | `followup/analyze_airguard.py` → `b2/analysis`; oracle v3 (post-hoc, guest-clock order) `--order device` → `b2/analysis-v3` | — (raw, card) |
| B1 screening | `plans/b1-screening.md` | — | (builds outside the repo; `plans/b1/build_airguard.sh`) | — | S1 decision |
| A10 callers | — | — | `round3/a10/find_callers-20261119.txt` | (A's `triage/find_callers.py`) | — |

Fixture/transport changes since tag `snapshot-20261117` (`git diff snapshot-20261117 -- artifact/fixture/src artifact/transport`):
optional `Revision` extras `deadline_ms`, `chunk`, `scope`, `split`, `splitsetup`, `items`, `prelock`, an `HttpTransport.postMode`
overload (chunk, deadline), and a settable sink host for real phones (`Fence.HOST`, meta `sink_host`; `App.java`, `Cmd.java`), and the SETUP extra `regrant_agg` (B12 v2; re-aggregation after the T5 re-grant, default off).
Defaults are unchanged; each card's Design section says which extras its runs use. `UpJob.onStopJob` was not changed. Large raw files are committed gzip-compressed (B4 v2 additionally split into byte parts) with the sha256 of the
original next to them; the analysis scripts read the compressed form and their outputs are byte-identical.

Data freeze (B7, 29/11): nothing runs after it; this index, `EXCLUSIONS.md`, `summary.json` and the raw data are committed.
