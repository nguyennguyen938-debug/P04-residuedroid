# Test 6 (AWS Device Farm + Samsung Remote Test Lab) — B's run material

Devices (2026-11-19, C agreed): one Pixel on Device Farm (Pixel 8a, Android 17) and one Galaxy on Samsung Remote Test
Lab (RTL; Galaxy M35 SM-M356B, Android 14 in the pilots), i.e. two vendors and two Android versions. RTL replaces the second
Device Farm device; it departs from S0 (AWS only) and C agreed (RUNLOG 2026-11-19).

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
5. Current package: **v4** (zip sha256 8562abeb…09d7) = v2 + `tls_suite.py:56` CA copy via `run-as tee` + `tls_suite.py
   --start` + `campaign.py` `seen_max`. v2 (f46008ce…01ec, run-as shell CA copy) and v3 (e1777dad…e5ff) are superseded.
   The zip and `uploads.env` stay outside the repository.

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

## Main runs (test6-card.md)
`testspec-main-job1.yml` (TLS blocks 0–19 + lifecycle k 0–9) and `testspec-main-job2.yml` (lifecycle k 10–19), seed
`test6-20261119`, generated from the pilot spec (only ranges and seed differ). RTL sessions: `run_rtl.sh` (below).
Analysis: `followup/analyze_test6.py --manifest plans/test6/runs.json` (validity rules of the card; tests in
`followup/test_analyze_test6.py`).

## Run
`run_df.sh <uploads.env> <run-name> <fresh out dir> [timeout min]` — refuses existing out dirs, sets a job timeout,
polls to completion, downloads FILE/LOG artifacts, records trial minutes before/after. `uploads.env` holds account-specific
ARNs and stays outside the repository. Every run needs the user's go-ahead.

## Samsung Remote Test Lab (RTL) — same package, run from the Mac
- The user reserves the device and opens Test → Remote Debug Bridge in the browser; RDB listens on `localhost:<port>`.
- Use platform-tools **r33.0.3** adb on its own server port (`ANDROID_ADB_SERVER_PORT=5038`, `ADB=<r33 adb>`): with
  adb 37.0.1 every service request hung (RUNLOG 2026-11-19 08:20).
- Never start a shell under run-as (`run-as <pkg> sh …`): it froze the RDB link twice; `tls_suite.py:56` now copies the CA
  with `run-as <pkg> tee` (package v3). `campaign.py --no-root` never starts one.
- Receivers run on the Mac, the phone reaches them through `adb reverse` over the RDB relay (remote network path, not
  USB): record this mode for §7a.
- Runner: `run_rtl.sh --port P --pkg <package dir> --out <fresh dir> --expect-model SM-M356B --expect-android 14 --adb <r33 adb>
  [--end HH:MM] [--tls-start K --tls-n N] [--life-start K --life-trials N]`: the steps of the spec files plus preflight (model,
  Android, uid shell, run-as, reverse) before anything is installed, uninstall of `org.residuelab.*` before and after,
  `session.json` + `package-sha256.json`, link probe `rdb_probe.py` (stops the harness after 6 failed probes → `LINK_DOWN`,
  exit 4), cleanup that always runs. Checked offline against a fake phone (full run, and a link drop mid-lifecycle). Pilot 3 (`results/round3/test6/pilot-rtl-3`)
  passed all mechanism checks; pilots 1–2 are environment failures (kept).
- **Unattended (use this):** `END=HH:MM bash artifact/plans/test6/rtl_auto.sh <scratch>` owns the Samsung `rdb` relay
  (started with the r33 adb on PATH and server port 5038: rdb runs `adb connect` itself and needs adb on PATH) and fills
  the session: remaining TLS blocks 0–19 and lifecycle k 0–19 (after the last recorded index), then replacements for
  schedules short of 20 valid (validity counted by `analyze_test6.py`, cap 5), sized to the time left (TLS 40 s/block,
  95 s/trial, 150 s setup, 5 min margin); new dirs `galaxy-pNN`. Link drop → watchdog exit 4 → relay restart (log line
  NEED_CLICK: the RTL page must open Remote Debug Bridge again) → continue. Stops after 3 failed or 3 no-progress runs.
  Checked offline (fake rdb + fake phone, only when no live run uses ports 8787/8798/8799): fill, kill-only replacements up to
  the cap, link drop + restart + continuation.
- Lessons (RUNLOG 19/11): never edit a script a running process reads (scripts are now wrapped in main(); replace files
  atomically); one harness run per Mac at a time (fixed host ports; run_rtl.sh refuses otherwise); give absolute paths.
- Credits: 4 per 60 min (1 credit = 15 min); the user had 22 (330 min). Pilot 3 times: TLS block 36 s (+~15 s install),
  lifecycle pen+kill+rev block 251 s.

## Minute budget (from local rehearsal 2, emulator Android 15; Device Farm setup overhead still unmeasured)
| Run | Content | Expected | Job timeout |
|---|---|---|---|
| Pilot (Pixel 8a) | combined spec: TLS ×1 block + lifecycle pen, kill, rev ×1 | ~8–12 min | 20 min |
| Main, per device, job 1 | TLS ×20 + lifecycle blocks 0–9 (`--trials 10`) | ~70 min | 100 min |
| Main, per device, job 2 | lifecycle blocks 10–19 (`--start 10 --trials 10`, fresh out dir) | ~66 min | 100 min |
One Device Farm device (Pixel 8a): expected ≈ 150 min, worst case 20 + 2×100 = 220 min of the 1,000 trial minutes.
RTL (Galaxy), same content split into sessions: TLS ×20 ≈ 13 min, lifecycle 20 blocks ≈ 84 min, + ~5 min per session and
30% reserve ≈ 2–2.5 h ≈ 8–10 credits; test 1 (reduced) not yet sized (harness B10).
Lifecycle trial time on the emulator was 104–166 s (rehearsal 2); N per schedule on the phone: *plan không nêu* (20 proposed,
as B11/B12). summary.json has no lifecycle-on-phone key yet (C).
