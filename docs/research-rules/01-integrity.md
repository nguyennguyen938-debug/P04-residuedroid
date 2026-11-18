# R1 — Scientific integrity

These rules are non-negotiable. They restate and extend the honesty gate in `PLAN.md` and the
"Claims deliberately NOT made" list in `others/notes.md`.

## R1.1 Every number is generated, never typed
- Every number in the manuscript comes from a macro or table in `manuscript/generated/`, written by
  a script (`artifact/scripts/render*.py`, `artifact/revision/render_revision.py`,
  `artifact/followup/render.py`). Never hand-edit `manuscript/generated/*`.
- A new number needs: raw data → analysis script → generated macro → one row in the claim→evidence
  ledger (`others/notes.md`). No ledger row, no claim.
- No simulated, illustrative, extrapolated or "expected" numbers anywhere in the paper or results.
  The smoke test (`others/smoke/`) is a mechanism check, not data; never cite it as a result.

## R1.2 Report what happened, including what hurts
- Negative results stay in: uncovered-path leaks (T9), volatile/taint failures, permitted-item
  deficits, zero-vs-zero contrasts, failed pilots, excluded trials and their reasons.
- A null difference is reported as "no confirmed difference in N paired trials", never as
  equivalence. A 0/N observation is not an impossibility guarantee; give N and the interval.
- Unknown is not clean: missing write returns, opaque bodies (T10), missing labels and unreadable logs
  are counted as `unknown`/`unattributable`, never folded into "permitted" or "no violation".

## R1.3 Scope discipline (claims that must not appear)
- No "first withdrawal measurement" (MowChecker is prior art).
- Residual storage is never a violation; accepted bytes are not delivery, server processing or recall.
- No transparent enforcement for arbitrary apps; claims are limited to mediated paths.
- No legal conclusions; ACRA/Matomo behaviour is configuration- and contract-specific, not a bug.
- Emulator results do not establish physical-device energy, OEM behaviour or production deployment.
- Two AVD labels or bootstrap resampling are not independent-hardware replication.

## R1.4 Outcome-blind decisions
- Validity rules, exclusion rules, sample sizes, seeds, observation windows and analysis choices are
  fixed in a protocol **before** the final run (see R2). They are never changed after looking at
  outcomes to make a result look better.
- A trial is never extended, repeated or dropped because its outcome is unfavourable. Replacements
  are allowed only for recorded environment failures, as whole fixed blocks covering all variants.
- If a rule must change after data exist, write a new protocol version, a new output directory, and
  report both the old and new outcome.

## R1.5 Provenance of non-experimental content
- Manual judgments (e.g. static validation sample) are labelled as manual, with the judge and criteria.
- Citations: metadata checked against a primary source; a Crossref title match is discovery, not
  verification. Do not substitute editions (see `codex-citation.md`).
- LLM-assisted text must stay disclosed per the venue CFP. AI-generated reviews (`review.md`) are
  author feedback, not peer review; never describe them as independent.
