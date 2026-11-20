---
name: p04-experiment
description: Plan, size, run and hand off P04 ResidueDroid round-3 experiments as role B (experimenter) of the team plan PLAN-ROUND3.md / HUONG-DAN-B.md. Use when the user wants to start or check a B task (B0–B12, Test 6), size emulator or Device Farm runs, pilot, deliver summary.json to C, or prepare the data freeze.
---

# P04 role-B experiment workflow (team plan, round 3)

**Plan of record:** `PLAN-ROUND3.md` (section "Vai B") + `HUONG-DAN-B.md`, restated as `artifact/plans/B-run.md` and
`artifact/plans/B-tracker.md`. These replace `PLAN.md` for round-3 work. Do not add tasks, arms, trial counts or
schedules beyond them; where they are silent, say so and ask the user. Research rules: `docs/research-rules/`.

**Hard facts from the team plan**
- Branch `b-exp` from `origin/main`, merged by PR. Pre-round-3 state: tag `snapshot-20261117`.
- B owns `artifact/**` except render scripts (`scripts/render*.py`, `revision/render_revision.py`, `followup/render.py`)
  and `artifact/mutation/**` (A), `artifact/triage/`, `artifact/survey/`, `artifact/devicefarm/**` (C). Read them; to change
  them, tell the owner. `guard.sh` fails if the branch modifies them.
- B keeps the emulator queue; nobody else runs emulators on B's Mac.
- Numbers go to C only through `artifact/results/round3/summary.json` (flat `{name: value}`, names = `SCHEMA` in
  `artifact/scripts/render_tests.py`). Never type numbers into `.tex`.
- Data freeze **29/11** (B7): raw, `summary.json`, PROTOCOL, EXCLUSIONS committed; nothing runs afterwards.
- Cut order when late: test 5 → lifecycle part of test 6 → test 4 down to one Android version. Tests 1–3 stay.
  A test that misses 29/11 leaves the body; no catch-up runs.

**Integrity boundary.** Tuning may target operational goals only (valid trials within the queue slot). Never steer, rerun
or select by outcomes (violations, deficits, accepted-after-ack bytes, latencies reported in the paper). See
`references/autoresearch-integration.md`.

## Phase 0 — Load context
Read `HUONG-DAN-B.md`, `PLAN-ROUND3.md` (Vai B, hàng đợi, rủi ro, quyết định), `artifact/plans/B-run.md`, the tracker, and
the README of the task's folder (`artifact/mutation/README.md`, `artifact/devicefarm/README.md`, `artifact/triage/`). State
which B task, its deadline, its `summary.json` keys, and its slot in the emulator queue.

## Phase 1 — Task card
For a B task, write `artifact/plans/<task>-card.md` from `docs/research-rules/templates/EXPERIMENT.md`, filled **only** from
the team plan and the task README; mark every unspecified parameter "plan không nêu" and ask the user (or the owning role)
before choosing. `experiment-plan` / `experimental-design` may be used for layout or for randomizing order where the team
plan asks for it (B4: "thứ tự ngẫu nhiên"); they do not add scope.

## Phase 2 — Size and place in the queue
- Emulator: `scripts/host_capacity.py --schedules <list> --trials <n> --lanes <k>`; ≤ 3 emulators on this Mac (16 GB).
  Respect the queue in `B-run.md` (B11 nights 20–21/11, B4 22/11, B10 23/11, B3 24/11, B12 25/11, B2 26–27/11).
- Device Farm (Test 6): budget from `artifact/devicefarm/README.md` (~100 min TLS/backpressure) vs PLAN-ROUND3 (~1,100 min
  with test 1 and lifecycle); 0.17 USD/min after the one-time trial. Record the receiver mode (A: host via `adb reverse`;
  B: EC2 us-west-2) for every run. See `references/server-options.md`.
- Readiness: `scripts/preflight.sh` (AVDS / PORTS / IMAGES env) must exit 0 before any emulator run.

## Phase 3 — Pilot
Pilot output only to `artifact/results/round3/<task>/pilot-<n>/`; pilots are excluded. Optional autoresearch Loop A on
operational metric (`ops_metric.py`) with `guard.sh`. Log every pilot and harness change in RUNLOG.

## Phase 4 — Run
- Fresh `--out` under `artifact/results/round3/<task>/`; own ports only; `caffeinate -s -i`; RUNLOG LAUNCH entry.
- Unattended runs via `p04-autorun` (manifest in `artifact/plans/autorun/`), with the user's go-ahead.
- Behaviour changes that affect comparability (e.g. `UpJob.onStopJob` returning `true`) go into PROTOCOL.

## Phase 5 — Deliver to C
1. Compute the task's keys from raw data with a script under `artifact/results/round3/` or the task folder (no hand-typed
   numbers); merge into `artifact/results/round3/summary.json` (flat, SCHEMA names only — `render_tests.py` asserts this).
2. `guard.sh` → `GUARD OK`; update `B-tracker.md`; RUNLOG DONE entry; commit on `b-exp`; tell C which keys arrived.

## Phase 6 — Data freeze (B7, 29/11) and after
Commit raw, `summary.json`, PROTOCOL, EXCLUSIONS; then B8 (§6, appendix Artifact, stale docs listed in HUONG-DAN-B) and
B9 (independent clone + `make all`).
