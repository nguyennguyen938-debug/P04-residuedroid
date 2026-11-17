#!/bin/bash
# Chain the post-campaign experiments onto whichever P04 emulator becomes free.
source /Users/xuanbachle/Workstation/MobiSys2027/papers/shared-android/env.sh
cd /Users/xuanbachle/Workstation/MobiSys2027/papers/P04-residuedroid/artifact
side=$1
if [ "$side" = B ]; then
  while kill -0 6850 2>/dev/null; do sleep 30; done
  echo "$(date +%H:%M:%S) B free: micro"; python3 harness/micro.py --serial emulator-5602 --out results/raw/micro
  echo "$(date +%H:%M:%S) B: acra"; python3 harness/acra_case.py --serial emulator-5602 --out results/raw/acra --trials 30 --reboot-trials 10
  echo "$(date +%H:%M:%S) B: alarm substrate"; python3 harness/campaign.py --serial emulator-5602 --avd P04AvdB --port 8791 --variants alnone,alconv,alrd \
     --out results/raw/sub_alarm --schedules pending,kill,forcestop,reboot --trials 20 --substrate alarm --apkdir fixture/build/apk_alarm
  echo "$(date +%H:%M:%S) B: done"
else
  while kill -0 6808 2>/dev/null; do sleep 30; done
  echo "$(date +%H:%M:%S) A free: workmanager substrate"; python3 harness/campaign.py --serial emulator-5600 --avd P04AvdA --port 8792 --variants wmnone,wmconv,wmrd \
     --out results/raw/sub_work --schedules pending,kill,forcestop,reboot --trials 20 --substrate work --apkdir workmanager/build/apk
  echo "$(date +%H:%M:%S) A: done"
fi
