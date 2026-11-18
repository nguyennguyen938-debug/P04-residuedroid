# R2 — Experiment protocol (experimenter workflow)

Lifecycle of every runtime experiment. Steps are in order; none is optional.

## R2.1 Pre-register (before touching a device)
Round 3: the team plan (`PLAN-ROUND3.md`, `HUONG-DAN-B.md`) defines the tasks; for each B task copy
`docs/research-rules/templates/EXPERIMENT.md` to `artifact/plans/<task>-card.md` and fill in **all** fields from the team plan
(unspecified = ask):
question/hypothesis, the claim it can support and the claim it cannot, variants and comparator,
schedules, unit of analysis, target N per cell, seed, observation window, validity/exclusion rules,
stopping rule, replacement rule, analysis script and estimand. Commit it before the final run.

## R2.2 Pilot ≠ final
- Pilots go to `results/<campaign>/pilot-*` and are **never** pooled with final data.
- Each pilot that changes the protocol is recorded in `EXCLUSIONS.md` with what failed and why.
- Freeze the protocol only after the last pilot.

## R2.3 Freeze the build
- Before the final run, pin source and executables:
  `python3 artifact/revision/freeze.py results/<campaign>/frozen-<name>` (writes `source-sha256.json` +
  `source.tar.gz`). Record installed APK SHA-256 in the run directory.
- A rebuilt APK is a new build: new freeze directory, new protocol version.
- Use a fresh AVD data image or remove only the relevant `org.residuelab.*` packages before
  installing rebuilt debug APKs (signing keys can differ).

## R2.4 Run
- Always a **fresh** output directory (`--out results/<campaign>/<run-id>`, Makefile `RERUN=`).
  Never write into an existing results directory; never overwrite raw evidence.
- Fixed seeds: schedule parameters derive from `seed-schedule-k` so all AVDs replay identical
  schedules (`harness/campaign.py`). State the seed in `meta.json`.
- Run every variant inside the same trial/block when the design is paired (matched campaigns);
  cross-AVD comparisons are descriptive only.
- Own your devices: only drive emulators/ports you started for this run; never kill or reconfigure
  other agents' instances. Record AVD name, console/gRPC port and sink port.
- Keep the host awake for the harness process only (`caffeinate -s -i -w <pid>`); do not change
  global power settings.
- Verify each injected fault (e.g. network loss must be confirmed down via per-app iptables, not
  assumed from `svc wifi disable`).

## R2.5 Log as you go
- Append to `artifact/results/RUNLOG.md` (local time, +07) for every launch, stop, crash, diagnosis,
  fix and resume: what happened → evidence → fix → which trials are affected. Use
  `templates/RUNLOG_ENTRY.md`.
- A harness fix mid-campaign must state from which trial index it applies and how earlier trials are
  treated (excluded or retained, with reason).

## R2.6 Validity and exclusion
- Apply the pre-registered rules mechanically from logs (e.g. `summarize.validity`: host gap > 200 s,
  emulator restart/setup failure, unreadable device log, failed relaunch, dead device, unverified
  net cut). Validity code must not read outcome fields.
- Excluded or failed attempts are retained, renamed `*_INVALID_<reason>` or listed in
  `attempts.jsonl`/`diagnostics.jsonl`; never deleted.
- Report logged, excluded (by reason, reasons may overlap), valid, analyzed and unused counts.
  "First N valid per cell" selection must be stated.

## R2.8 Automated tuning (autoresearch)
- Allowed only before freeze, only on `pilot-*` data, only on harness operations (timeouts, polling,
  restarts, sequencing, instance count), with metric = valid trials per emulator-hour
  (`ops_metric.py`) and Guard = `guard.sh`. Details: `.claude/skills/p04-experiment/references/autoresearch-integration.md`.
- Never optimize, select or rerun by any outcome (violations, deficits, leaks, latencies reported as results).
- Every accepted change is a RUNLOG entry; after freeze, any change means a new protocol version.

## R2.7 Close out
- Stop everything you started (harness, sinks, caffeinate, emulators, guest iptables rules); record it.
- Run the analysis pipeline, then the reproducibility gate (R5). Update the claim ledger and the
  status file. Hand results to the author with the ledger diff; do not edit manuscript prose claims
  yourself unless asked.
