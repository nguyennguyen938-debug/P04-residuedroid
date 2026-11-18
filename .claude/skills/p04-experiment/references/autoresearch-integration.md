# Autoresearch integration (allowed and forbidden loops)

The autoresearch skill keeps or discards code changes by a metric. In a measurement study that is safe only
when the metric cannot see scientific outcomes and the change cannot alter what is measured.

## Loop A — Harness operational tuning (pilot data only)
Goal: reach the plan's valid-trial target faster and more reliably on this host.

```
/autoresearch
Goal: raise valid trials per emulator-hour on pilot runs without changing what is measured
Scope: artifact/harness/campaign.py, artifact/followup/campaign.py, artifact/revision/socket_suite.py,
       artifact/harness/*.sh   (timeouts, polling intervals, restart/relaunch logic, boot waits, retries)
Metric: valid trials per emulator-hour (higher_is_better)
Verify: python3 .claude/skills/p04-experiment/scripts/ops_metric.py artifact/results/<campaign>/pilot-<n>
Guard: bash .claude/skills/p04-experiment/scripts/guard.sh
Iterations: 8
Forks: 2
```
Rules:
- Each iteration that changes harness code needs a **new** pilot directory (`pilot-<n+1>`); Verify reads only pilots.
- Allowed knobs: adb/boot timeouts, quiescence polling, watchdog thresholds, relaunch retries, sequencing of
  emulator start/stop, sink port allocation, number of concurrent instances up to `host_capacity.py`'s limit.
- Not allowed (guard.sh blocks most of these): oracle and validity code, fixture enforcement code
  (Fence/Policy/ChunkFence/Revision/transport), tenant/variant definitions, schedule semantics, observation
  window shorter than the protocol, seeds, N targets, exclusion thresholds (e.g. the 200 s gap rule).
- `Forks: 2` because the emulator is a shared, slow resource; never fork more emulators than the host allows.
- After freezing (Phase 4) Loop A is closed. Harness changes after freeze = new protocol version + new freeze.

## Loop B — Plan critique (no data)
`/autoresearch:probe` or `/autoresearch:reason` on `artifact/plans/<id>.md`: personas = MobiSys reviewer 1–4 from
`review.md`; output = list of design weaknesses and the minimal design change for each. Changes go into the card
before freezing. No metric, no code edits.

## Loop C — Reproducibility fix loop (analysis code, no new data)
`/autoresearch:fix` with Verify = `bash .claude/skills/p04-experiment/scripts/guard.sh; echo $?` (target 0).
Use for build/regeneration failures (e.g. the `index-v2.json` dependency). Any intended change to a generated
number must be listed and approved; guard reports unintended diffs.

## Forbidden in every loop
- Metrics computed from violation rates, prohibited items, legit deficit, unattributable/outstanding counts,
  accepted-after-ack bytes, acknowledgement latencies reported in the paper, or any oracle output.
- Re-running, extending or discarding trials to change an outcome.
- Editing anything under `artifact/results/` other than creating new pilot/run directories and appending RUNLOG.
- `ship`, push, publish, or launching devices without the user's go-ahead for that run.
