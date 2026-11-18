# Test 6 (AWS Device Farm) — B's run material

Source of truth: `artifact/devicefarm/README.md` and `testspec.yml` (owned by C). This folder holds B's pilot run
configuration and run script; it does not change C's files.

## Package (rebuilt per run, not committed)
1. Scratch copy of `HEAD` (`git archive`), `git apply artifact/devicefarm/real-device.patch` there (never in the working tree).
2. `VARIANTS=tls OUTDIR=build/tls-apk bash fixture/build.sh` → `rl-tls.apk` (package `org.residuelab.tls`, debuggable,
   minSdk 26, targetSdk 33).
3. Fresh test certificate per `artifact/followup/tls-cert/README.md`, written into the package staging copy (the tracked
   `test-ca.pem` stays untouched; `test-key.pem` is never committed).
4. Zip layout (Appium Python package): `tests/test_placeholder.py`, `requirements.txt` (`pytest`), `artifact/followup/tls_suite.py`
   (patched), `artifact/followup/tls-cert/{test-ca.pem,test-key.pem}`, `artifact/fixture/build/tls-apk/rl-tls.apk`.

## Pilot spec
`testspec-pilot.yml` = C's `testspec.yml` with `--n 1`, `devicefarm-cli use python 3.12` (pin; supported on amazon_linux_2)
and `adb reverse --list` for diagnostics. Receiver mode A (Device Farm host via `adb reverse`, i.e. over USB).

## Run
`run_df.sh <uploads.env> <run-name> <fresh out dir> [timeout min]` — refuses existing out dirs, sets a job timeout,
polls to completion, downloads FILE/LOG artifacts, records trial minutes before/after. `uploads.env` holds account-specific
ARNs and stays outside the repository. Every run needs the user's go-ahead.
