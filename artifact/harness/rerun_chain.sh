#!/bin/bash
# Re-run what the 18:04 resume left missing (audit 2026-11-08 ~20:40). Drivers now survive emulator deaths.
source /Users/xuanbachle/Workstation/MobiSys2027/papers/shared-android/env.sh
cd /Users/xuanbachle/Workstation/MobiSys2027/papers/P04-residuedroid/artifact
if [ "$1" = A ]; then
  echo "$(date +%H:%M:%S) A: campaign c1 top-up k=53.. (fstop, reb, rev, infl, net)"
  python3 harness/campaign.py --serial emulator-5600 --avd P04AvdA --port 8787 --variants none,cancel,enqueue,jobstart,conv,rd \
    --out results/raw/c1/A --start 53 --trials 16 --no-install --schedules forcestop,reboot,revoke,inflight,netloss
  echo "$(date +%H:%M:%S) A: done"
else
  echo "$(date +%H:%M:%S) B: ACRA k=4.."
  python3 harness/acra_case.py --serial emulator-5602 --avd P04AvdB --out results/raw/acra --start 4 --trials 26 --reboot-trials 7
  echo "$(date +%H:%M:%S) B: AlarmManager substrate k=6.."
  python3 harness/campaign.py --serial emulator-5602 --avd P04AvdB --port 8791 --variants alnone,alconv,alrd \
    --out results/raw/sub_alarm --schedules pending,kill,forcestop,reboot --start 5 --trials 16 --substrate alarm --apkdir fixture/build/apk_alarm
  echo "$(date +%H:%M:%S) B: done"
fi
