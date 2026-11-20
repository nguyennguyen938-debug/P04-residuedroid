---
name: p04-autorun
description: Run role-B emulator tasks of the P04 round-3 team plan unattended and watch them to completion — launch from a stage manifest, outcome-blind progress checks, notify on finish/abort, then hand off to p04-experiment Phase 5 (summary.json for C). Use when the user wants to start, schedule, watch or wrap up an automatic B run (B0 smoke, B11, B4, B10, B3, B12, B2).
---

# P04 autorun (role B, team plan round 3)

Executes and watches; never decides from outcomes. Plan of record: `PLAN-ROUND3.md` (Vai B, hàng đợi emulator) +
`HUONG-DAN-B.md`, restated in `artifact/plans/B-run.md`. Test 6 runs on AWS Device Farm (its own test spec in
`artifact/devicefarm/`, owned by C), not through this runner.

## Files
- `scripts/autorun.py <manifest.json> [--dry-run] [--confirm <id>]` — refuses existing output dirs, pilot output outside
  `pilot-*`, outputs outside `artifact/results/`, and `kind: final` without `--confirm <id>`; optional `frozen` hash check;
  runs `pre` checks, stages under `caffeinate -s -i`, stops at the first failure or deadline, appends LAUNCH/DONE/ABORT to
  RUNLOG, runs `guard.sh`, shuts down only `emulator-*` serials listed in `owned_serials`.
- `scripts/status.py <run_dir>... [--target N] [--serial S...]` — valid trials per schedule (repo validity rule), stale
  detector, emulator health; never opens receiver/oracle files.
- Manifests: `artifact/plans/autorun/<task>-<run>.json` (template `TEMPLATE.json`); outputs under `artifact/results/round3/<task>/`.

## Procedure
1. The task is in `B-tracker.md`, its queue slot is today (or the user moved it), and its parameters come from the team
   plan / task README (anything unspecified was confirmed by the user). `preflight.sh` exits 0.
2. `autorun.py <manifest> --dry-run` → `dry-run OK`.
3. Pilots: run when the user asks. Final runs: show stages, devices, ports, expected hours; get the user's go-ahead; pass
   `--confirm <id>`.
4. Launch with Bash `run_in_background: true`; you are re-invoked on exit.
5. Watch with Monitor or `/loop` (ScheduleWakeup 1200–1800 s) on `status.py ... --target <N> --serial <owned>`. Act only on
   machine-checkable facts; never inspect outcomes or edit code mid-run.
6. On exit: read `autorun-<id>.summary.json` + RUNLOG lines; PushNotification "<id>: DONE/ABORT, guard <code>"; continue
   with `p04-experiment` Phase 5 (compute keys → `artifact/results/round3/summary.json` → tell C).
7. On ABORT: report; any rerun uses a new manifest and a new directory; never re-run a completed trial or change N to
   chase an outcome. Respect the 29/11 data freeze and the cut order (test 5 → test 6 lifecycle → test 4 one version).
