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
