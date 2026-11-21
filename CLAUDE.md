# P04 ResidueDroid — project instructions

Research artifact + manuscript for *ResidueDroid* (MobiSys 2027; abstract registration 27 Nov, submission 4 Dec 2026
AoE). Android apps keep outboxes/jobs that outlive a user's withdrawal; ResidueDroid carries durable source epochs and
labels with persisted data and serializes a policy check with each bounded socket write.

## Team and plan of record (round 3)
- Three roles: **A** theory (`artifact/mutation/**`, §2/§4/§5/§9), **B** experiments, **C** results and writing
  (`generated/*`, render scripts, `artifact/devicefarm/**`, §3/§7/§8/§10). **Who the user is depends on the
  session:** the repo owner does A and C, DuyDayy does B. If the session does not make the role clear, ask before
  editing. Put a personal role line in an untracked `CLAUDE.local.md` (git-ignored), not in this file.
- **Plan of record: `PLAN-ROUND3.md` + `HUONG-DAN-B.md`**, restated for B in `artifact/plans/B-run.md` and
  `artifact/plans/B-tracker.md`. `PLAN.md` describes the original (pre-round-3) campaign. Do not add tasks or protocol
  beyond the team plan; where it is silent, ask.
- B works on branch `b-exp` (from `origin/main`), merged by PR; pre-round-3 state is tag `snapshot-20261117`.
- B owns `artifact/**` except render scripts, `artifact/mutation/**`, `artifact/triage/`, `artifact/survey/`,
  `artifact/devicefarm/**`. B delivers numbers only via `artifact/results/round3/summary.json` (SCHEMA in
  `artifact/scripts/render_tests.py`). Data freeze 29/11.

## Where things are
| Path | What |
|---|---|
| `PLAN-ROUND3.md`, `HUONG-DAN-B.md` | team plan, B's guide |
| `PLAN.md`, `STATUS.md` | original campaign plan and history |
| `review.md` | AI-generated mock reviews + checklist; not peer review |
| `others/notes.md` | claim → macro → source ledger; claims deliberately NOT made |
| `manuscript/` | LaTeX; `generated/` is script output only; `build.sh` |
| `artifact/fixture/`, `artifact/transport/` | ResidueLab + ResidueDroid library; HTTP/TLS transports |
| `artifact/acra/`, `matomo/`, `workmanager/` | SDK embeddings and substrate builds |
| `artifact/harness/`, `artifact/followup/`, `artifact/revision/` | campaign drivers, oracles, protocols |
| `artifact/mutation/`, `triage/`, `survey/`, `devicefarm/` | round-3 material owned by A / C |
| `artifact/results/` | recorded evidence (append-only) + `RUNLOG.md`; round-3 outputs under `results/round3/` |

`make -C artifact all` regenerates every number and the PDF from recorded data without devices.

## Research rules (binding)
@docs/research-rules/01-integrity.md
@docs/research-rules/02-experiment-protocol.md
@docs/research-rules/03-data-provenance.md
@docs/research-rules/04-analysis-reporting.md
@docs/research-rules/05-reproducibility.md

## Skills
- `p04-experiment` (`.claude/skills/p04-experiment/`): role-B workflow for the team plan — task cards, sizing, pilots,
  delivering `summary.json`, data freeze. Scripts: `host_capacity.py`, `ops_metric.py`, `guard.sh` (ownership + evidence +
  oracle tests + byte-identical regeneration; must print `GUARD OK`), `preflight.sh`, `setup_avds.sh`.
- `p04-autorun` (`.claude/skills/p04-autorun/`): unattended emulator runs from `artifact/plans/autorun/*.json`, outcome-blind
  `status.py`. Test 6 runs on AWS Device Farm via `artifact/devicefarm/` (owned by C).

## Hard stops for Claude
- Never edit, move or delete recorded evidence under `artifact/results/` (only new run dirs and RUNLOG appends), never
  hand-edit `manuscript/generated/`, never edit files owned by A or C on `b-exp`.
- Never launch, kill or reconfigure an emulator or a Device Farm run without the user's go-ahead for that run; never
  touch devices or ports this project did not start. Never create AWS accounts or enter billing details.
- Never present a number that is not traceable to raw data via a script.

## graphify
Knowledge graph in `graphify-out/` (scope `.graphifyignore`). For architecture or "where/why" questions, read
`graphify-out/GRAPH_REPORT.md` or run `graphify query "<question>"`; after substantial changes run `/graphify . --update`.
