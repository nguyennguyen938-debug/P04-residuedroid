#!/bin/bash
# After the rerun chains: WorkManager substrate (full redo) on A; AlarmManager top-up k=21-24 on B.
source /Users/xuanbachle/Workstation/MobiSys2027/papers/shared-android/env.sh
cd /Users/xuanbachle/Workstation/MobiSys2027/papers/P04-residuedroid/artifact
if [ "$1" = A ]; then
  while kill -0 72958 2>/dev/null; do sleep 30; done
  echo "$(date +%H:%M:%S) A: WorkManager substrate (redo)"
  python3 harness/campaign.py --serial emulator-5600 --avd P04AvdA --port 8792 --variants wmnone,wmconv,wmrd \
    --out results/raw/sub_work --schedules pending,kill,forcestop,reboot --start 0 --trials 20 --substrate work --apkdir workmanager/build/apk
  echo "$(date +%H:%M:%S) A: done"
else
  while kill -0 72966 2>/dev/null; do sleep 30; done
  echo "$(date +%H:%M:%S) B: AlarmManager top-up k=21.."
  python3 harness/campaign.py --serial emulator-5602 --avd P04AvdB --port 8791 --variants alnone,alconv,alrd \
    --out results/raw/sub_alarm --schedules pending,kill,forcestop,reboot --start 21 --trials 4 --substrate alarm --apkdir fixture/build/apk_alarm
  echo "$(date +%H:%M:%S) B: done"
fi
