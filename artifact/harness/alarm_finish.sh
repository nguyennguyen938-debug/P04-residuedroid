#!/bin/bash
# 2026-11-09: finish the AlarmManager substrate redo (fresh sub_alarm holds k=5..8 except reb008, which was cut off
# at 10:04 when the previous session ended). Target: k=5..24 = 20 trials per schedule, like sub_work.
source /Users/xuanbachle/Workstation/MobiSys2027/papers/shared-android/env.sh
cd /Users/xuanbachle/Workstation/MobiSys2027/papers/P04-residuedroid/artifact
echo "$(date +%H:%M:%S) B: AlarmManager reb008"
python3 harness/campaign.py --serial emulator-5602 --avd P04AvdB --port 8791 --variants alnone,alconv,alrd \
  --out results/raw/sub_alarm --schedules reboot --start 8 --trials 1 --substrate alarm --apkdir fixture/build/apk_alarm || exit $?
echo "$(date +%H:%M:%S) B: AlarmManager k=9..24"
python3 harness/campaign.py --serial emulator-5602 --avd P04AvdB --port 8791 --variants alnone,alconv,alrd \
  --out results/raw/sub_alarm --schedules pending,kill,forcestop,reboot --start 9 --trials 16 --no-install --substrate alarm --apkdir fixture/build/apk_alarm
echo "$(date +%H:%M:%S) B: done rc=$?"
