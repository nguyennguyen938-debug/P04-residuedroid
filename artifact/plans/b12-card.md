# Experiment card — b12 (test 2, label mutants; protocol v1)

Status: frozen at the commit that adds this card; pilot (base, 1 trial per schedule) → I0 gate → final (chain
`plans/autorun/b12-chain.sh`, after B4). Owner: B (Duy); mutants and label_check by A (A9, `artifact/mutation/README.md`).

## Design (as `artifact/mutation/README.md`)
- Builds (19/11): I0-labels-in-body applied to every build; base, M1-union-latest, M2-stale-epoch, M3-extras-drop on top;
  `VARIANTS=mfence OUTDIR=build/apk_mut_$m`; `git checkout -- artifact/fixture/src` after each (patches never committed).
  APK sha256 prefixes: base 5770afe4, M1 39348346, M2 88ec3c20, M3 0a0cf753 (SHA256SUMS in each build dir).
- Run per mutant, one at a time on P04AvdA (emulator-5600, sink 8795): `followup/campaign.py --variants mfence
  --schedules pending,reboot --trials 20 --apkdir fixture/build/apk_mut_$m --out results/mutation/$m` (README command;
  defaults for timeout/seed). N = 20 per schedule per mutant.
## Validity / analysis
- Oracle validity rules of `followup/matched_oracle.py` (unchanged). Pilot gate: base pilot trials valid and every
  label_check verdict `ok` (I0 puts labels in the body).
- `followup/analyze_mutation.py`: leaking trials (oracle), flagged items (label_check), wrong-label items (ground truth from
  the oracle tracer, independent of label_check), permitted deficit; keys mutTrials, mutOne*/mutTwo*, mutThreeDeficit.
  The README asked for a run-directory parameter in matched_oracle.py; done as a wrapper (analyze_test6.run_oracle executes
  matched_oracle.py unchanged with another directory) so the published script and its outputs stay byte-identical.
## Threats
- Fixture only; one AVD; T5 re-grant pattern drives M1/M2 (README); emulator.
## Outcome (19/11, final run 17:52–19:33, guard 0)
- Logged / excluded / valid (paired trials, 20 pending + 20 reboot per build): base 40/0/40; M1 40/1/39 (reb006);
  M2 40/1/39 (reb001); M3 40/2/38 (reb004, reb014). All exclusions: oracle reason "harness/device" (reboot step). The card
  has no replacement rule, so none were run; per-build N differs and `mutTrials` = minimum valid trials (38).
- Results (`results/mutation/analysis/mutation-summary.json`, `followup/analyze_mutation.py`; Wilson 95%):
  base: 0/40 leaking [0, 0.088], 0 flagged, 0 wrong-label, permitted deficit 44 items.
  M1-union-latest: 0/39 leaking [0, 0.090], 0 flagged, 0 wrong-label, deficit 52.
  M2-stale-epoch: 39/39 leaking [0.910, 1], 908 flagged = 908 wrong-label items (label_check and the independent tracer
  agree item for item in count), deficit 504.
  M3-extras-drop: 0/38 leaking [0, 0.092], 0 flagged, 0 wrong-label, deficit 116 (base 44).
- Negative / null results: M1 produced no leak, no flagged and no wrong-label item in pending + reboot; the README's T5
  trigger needs an aggregate holding both epochs, which these runs did not show (reported to A; no extra schedule run).
  Base also has a permitted deficit (44). 0/N is not an impossibility guarantee.
- Deviations: none from the card. Same trial ids (reb004, reb014) failed as on B11 Android 14: noted, not acted on.

## Protocol v2 (20/11, A approved in PR #2 (A1); written before any v2 build or trial; v1 kept and reported)
Reason (test implementation, not outcome): in v1 the fixture aggregated only at SETUP (Cmd.java "derivation happens before any
withdrawal"); after the T5 re-grant it collected epoch-1 records but never re-aggregated (0/39 re-grants followed by an AGG),
so the M1 trigger — an aggregate holding e0 and e1 records — could not occur.
- Change: fixture extra `regrant_agg` (default off: every earlier build behaves as before). With `regrant_agg=1` the re-grant
  thread calls `Work.aggregate` for a summary tenant after collecting the epoch-1 records (and the aggregator enqueues the
  summary upload as usual). Harness: `campaign.py --regrant-agg` (passes the extra; meta.json `regrant_agg: true`).
- Builds: as v1 (README loop: I0 on every build, base/M1/M2/M3 patches unchanged), from the commit that adds this section,
  into `fixture/build/apk_mut2_$m`; SHA256SUMS per build dir, recorded under "v2 builds" below before the pilot.
- Pilot `results/mutation-v2/pilot-base` (base, 1 trial per schedule). Gate (mechanical): both trials logged without
  trial_error/setup_fail; label_check verdicts all `ok`; and the mechanism is present: in each trial an AGG event for tenant 5
  after its REGRANT. Fail → no final; report.
- Final: base, M1, M2, M3 one at a time on P04AvdA (emulator-5600, sink 8795), `--schedules pending,reboot --trials 20
  --regrant-agg`, into `results/mutation-v2/<build>`. Validity as v1 (matched_oracle rules). No replacement rule (as v1).
- Analysis: `analyze_mutation.py --root results/mutation-v2 --out results/mutation-v2/analysis` (unchanged script).
- Key source (fixed now): `mut*` keys from v2 if its final completes; v1 reported next to v2. If v2 does not complete, keys stay v1.
- Threat added: the re-aggregation is a test-fixture behaviour chosen to reach T5 (A's README scenario), not observed in a real app.
- v2 builds (20/11, from commit 36127ed; `fixture/build/apk_mut2_$m/SHA256SUMS`): base 93b78d03, M1 f48529f9, M2 cef9d720,
  M3 889864a6 (sha256 prefixes of rl-mfence.apk); each contains the `regrant_agg` code path.

## Outcome v2 (20/11, final 21:44–23:29, guard 0; key source)
- Pilot-base: 2/2 trials valid, label_check 104/104 `ok`, AGG for tenant 5 after REGRANT in 2/2 trials → gate passed. The final's
  first launch was refused by autorun's preflight (port 5600 still held by the pilot emulator; no trial ran) and relaunched.
- Logged / excluded / valid (paired trials, 20 pending + 20 reboot per build): base 40/1/39 (reb003); M1 40/0/40; M2 40/1/39
  (reb000); M3 40/0/40. Exclusions: oracle reason "harness/device" (reboot step). No replacement rule; `mutTrials` = 39.
- Results (`results/mutation-v2/analysis/mutation-summary.json`; Wilson 95%):
  base: 0/39 leaking [0, 0.090], 0 flagged, 0 wrong-label, permitted deficit 80 items (v1 44).
  M1-union-latest: **24/40 leaking [0.446, 0.737]**, 24 flagged = 24 wrong-label items (label_check and the independent tracer
  agree in count), deficit 88 (v1: 0/39 leaking, not triggered).
  M2-stale-epoch: 39/39 leaking [0.910, 1], 924 flagged = 924 wrong-label, deficit 524 (v1 39/39, 908).
  M3-extras-drop: 0/40 leaking [0, 0.088], 0 flagged, 0 wrong-label, deficit 136 (base 80).
- Reading: with the re-aggregation reachable, the label checks catch M1 (the summary labelled only with the newest epoch). Not
  analysed here: why 16/40 M1 trials did not leak (no per-trial cause was pre-specified); why the base deficit rose from 44 to 80
  (candidate, not tested: the re-aggregated summary is correctly blocked and the oracle may count part of it as permitted).
- Report v1 and v2 together; the README statement that pending + reboot alone reach T5 does not hold for M1 without
  `regrant_agg` (told A in PR #2).
