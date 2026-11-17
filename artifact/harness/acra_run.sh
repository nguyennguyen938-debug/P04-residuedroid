#!/bin/bash
# 2026-11-09: clean ACRA rerun (protocol v3) on AVD A; earlier runs (results/raw/acra_INVALID_*) are not analyzed.
source /Users/xuanbachle/Workstation/MobiSys2027/papers/shared-android/env.sh
cd /Users/xuanbachle/Workstation/MobiSys2027/papers/P04-residuedroid/artifact
echo "$(date +%H:%M:%S) A: ACRA v3 k=0..29 (reboot+rebootctl k<10)"
python3 harness/acra_case.py --serial emulator-5600 --avd P04AvdA --out results/raw/acra --trials 30 --reboot-trials 10
echo "$(date +%H:%M:%S) A: done rc=$?"
