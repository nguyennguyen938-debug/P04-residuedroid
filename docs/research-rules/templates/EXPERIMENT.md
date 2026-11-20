# Experiment card — <id> (protocol v<N>)

Status: draft | frozen <YYYY-MM-DD HH:MM +07, commit> | running | done | abandoned
Owner (experimenter): <name>   Approved by (author): <name, date>

## 1. Question and claim
- Research question / hypothesis:
- Claim this can support (exact wording, scoped):
- Claims this cannot support (scope limits):
- Manuscript location and ledger rows (`others/notes.md`) it will feed:

## 2. Design
- Variants and comparator (same metadata? paired within trial?):
- Schedules / conditions and their fixed order (or randomization):
- Unit of analysis (tenant-trial, paired trial, request, attempt):
- Target N per cell, and why:
- Seed(s):
- Devices: AVD name, image/fingerprint, console/gRPC/sink ports, renderer:
- Build: freeze directory `results/<campaign>/frozen-<name>`, installed APK SHA-256 file:
- Observation window, timeouts, watchdogs:

## 3. Validity, exclusion, stopping, replacement (fixed before the final run)
- A trial is invalid if:
- Stopping rule (when the run ends; never outcome-dependent):
- Replacement rule (environment failures only, whole fixed blocks, all variants):
- Pilots and what they changed (→ `EXCLUSIONS.md`):

## 4. Analysis
- Oracle / script (unchanged? new tests?):
- Estimand and observation boundary (authorization vs acceptance vs receipt):
- Metrics with numerator/denominator:
- Uncertainty (Wilson CI / stratified cluster bootstrap, draws, seed, strata):
- Generated outputs (macros/tables) and render script:

## 5. Threats to validity (internal / construct / external / conclusion)

## 6. Outcome (filled after the run, never edited above this line)
- Logged / excluded by reason / valid / analyzed / unused:
- Results directory:
- Deviations from this card (with reason and impact):
- Negative or null results:
