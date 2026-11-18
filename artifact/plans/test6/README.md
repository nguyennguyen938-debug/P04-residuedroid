# Test 6 (AWS Device Farm) — B's run material

Source of truth: `artifact/devicefarm/README.md` and `testspec.yml` (owned by C). This folder holds B's pilot run
configuration and run script; it does not change C's files.

## Package (rebuilt per run, not committed)
1. Scratch copy of `HEAD` (`git archive`). Since 2026-11-18 (`b-exp`) C's `real-device.patch` is applied in B's files on
   the branch (its README: "B xem và áp"), so the copy needs no patching; earlier packages applied it in the copy only.
2. `VARIANTS=tls OUTDIR=build/tls-apk bash fixture/build.sh` → `rl-tls.apk` (package `org.residuelab.tls`, debuggable,
   minSdk 26, targetSdk 33).
3. Fresh test certificate per `artifact/followup/tls-cert/README.md`, written into the package staging copy (the tracked
   `test-ca.pem` stays untouched; `test-key.pem` is never committed).
4. Zip layout (Appium Python package): `tests/test_placeholder.py`, `requirements.txt` (`pytest`), `artifact/followup/tls_suite.py`,
   `artifact/followup/tls-cert/{test-ca.pem,test-key.pem}`, `artifact/fixture/build/tls-apk/rl-tls.apk`; for lifecycle also
   `artifact/followup/campaign.py`, `artifact/harness/sink.py` and `artifact/fixture/build/revision-apk/rl-m*.apk`
   (`VARIANTS="menqueue mstart mlayer mfence mboth" OUTDIR=build/revision-apk bash fixture/build.sh`).

## Lifecycle on a phone without root (`followup/campaign.py --no-root --sink-host 127.0.0.1`)
The two blockers named in `artifact/devicefarm/README.md` are removed in B's files; emulator runs are unchanged
(same 87 adb commands for pen, kill, fstop, rev, infl with the default flags; checked with a recorded fake adb).
| Root use on the emulator | On a phone (`--no-root`) |
|---|---|
| `Fence.HOST` fixed to `10.0.2.2` | meta `sink_host` (SETUP extra, like `sink_port`); default stays `10.0.2.2` |
| `adb root` | skipped |
| `sqlite3` on the device as root | `run-as` copies `rl.db` + `rl.db-wal` until two copies match, queried on the host; text identical to the CLI (`followup/test_campaign_noroot.py`) |
| `kill -9 $(pidof p)` | `run-as p kill -9 …` (same SIGKILL, app's own uid); pids before/after recorded as `kill_verified` |
| `iptables`, `svc` (netloss), `adb reboot` + root | refused under `--no-root`; reb and net stay on the emulator |

## Pilot specs
`testspec-pilot-combined.yml`: one job, TLS `--n 1` then lifecycle pen, kill, rev × 1 trial (matched variant set of
`followup/start_matched.py`), receiver mode A for both; supersedes `testspec-pilot.yml` (TLS only) for the first run.

`testspec-pilot.yml` = C's `testspec.yml` with `--n 1`, `devicefarm-cli use python 3.12` (pin; supported on amazon_linux_2)
and `adb reverse --list` for diagnostics. Receiver mode A (Device Farm host via `adb reverse`, i.e. over USB).

## Run
`run_df.sh <uploads.env> <run-name> <fresh out dir> [timeout min]` — refuses existing out dirs, sets a job timeout,
polls to completion, downloads FILE/LOG artifacts, records trial minutes before/after. `uploads.env` holds account-specific
ARNs and stays outside the repository. Every run needs the user's go-ahead.

## Minute budget (from local rehearsal 2, emulator Android 15; Device Farm setup overhead still unmeasured)
| Run | Content | Expected | Job timeout |
|---|---|---|---|
| Pilot (Pixel 8a) | combined spec: TLS ×1 block + lifecycle pen, kill, rev ×1 | ~8–12 min | 20 min |
| Main, per device, job 1 | TLS ×20 + lifecycle blocks 0–9 (`--trials 10`) | ~70 min | 100 min |
| Main, per device, job 2 | lifecycle blocks 10–19 (`--start 10 --trials 10`, fresh out dir) | ~66 min | 100 min |
Two devices (Pixel 8a, Pixel 10): expected ≈ 290 min, worst case 20 + 4×100 = 420 min of the 1,000 trial minutes.
Lifecycle trial time on the emulator was 104–166 s (rehearsal 2); N per schedule on the phone: *plan không nêu* (20 proposed,
as B11/B12). summary.json has no lifecycle-on-phone key yet (C).
