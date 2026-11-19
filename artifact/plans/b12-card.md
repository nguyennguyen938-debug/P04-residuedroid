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
