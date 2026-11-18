# R5 — Reproducibility gate

## R5.1 The gate
After any change to analysis code, raw-data selection or generated outputs:
1. In a scratch copy (`git archive HEAD | tar -x -C <scratch>`), run `make -C artifact revision`
   (analysis only, no devices) and, if TeX is available, `make -C artifact all`.
2. Every file in `manuscript/generated/` and `artifact/results/` that you did not intend to change
   must be byte-identical to the committed version. Any unintended diff blocks the change.
3. Intended diffs are listed in the commit message with the reason and the ledger rows they affect.
4. `manuscript/build.sh`: 0 undefined references/citations, 0 LaTeX errors, no `??`; check pages
   (12-page body limit, ≥10pt) and overfull boxes.

## R5.2 Environment
Python 3.11+, JDK 17 (set `JAVA_HOME` explicitly), Android SDK platform 33 / build-tools 34.0.0,
emulator android-33 google_apis arm64-v8a rev 17, TeX Live with acmart. `artifact/env.sh` falls back
to a sibling `../../shared-android/sdk` that does **not** exist in this checkout; always export
`ANDROID_HOME` yourself. Paths like `/Users/xuanbachle/...` in `STATUS.md`/`codex-citation.md` are
the original author's machine and are historical.

## R5.3 Known issue (resolved on main, 2026-11-18)
`scripts/render.py` used to need the git-ignored `static/data/index/index-v2.json` for `eligibleN`; round 3 (main, C)
added `static/data/index/eligible.json`, so `make all` runs on a clean checkout. `guard.sh` regenerates and compares
byte-for-byte.

## R5.4 Runtime experiments are not reproduced by `make all`
`make all` regenerates numbers from recorded raw data. Re-running devices is a new experiment under
R2 with a fresh output directory; its results are compared against, never substituted for, the
recorded cohort.
