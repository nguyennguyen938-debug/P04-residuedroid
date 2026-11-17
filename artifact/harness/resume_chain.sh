#!/bin/bash
# Resume after the 2026-11-08 checkpoint: finish campaign c1, then the follow-on experiments on the same AVD.
source /Users/xuanbachle/Workstation/MobiSys2027/papers/shared-android/env.sh
cd /Users/xuanbachle/Workstation/MobiSys2027/papers/P04-residuedroid/artifact
if [ "$1" = A ]; then
  echo "$(date +%H:%M:%S) A: campaign c1 k=39.."
  python3 harness/campaign.py --serial emulator-5600 --avd P04AvdA --port 8787 --variants none,cancel,enqueue,jobstart,conv,rd \
    --out results/raw/c1/A --start 39 --trials 26 --no-install --schedules netloss,pending,kill,forcestop,reboot,revoke,inflight
  echo "$(date +%H:%M:%S) A: WorkManager substrate"
  python3 harness/campaign.py --serial emulator-5600 --avd P04AvdA --port 8792 --variants wmnone,wmconv,wmrd \
    --out results/raw/sub_work --schedules pending,kill,forcestop,reboot --trials 20 --substrate work --apkdir workmanager/build/apk
  echo "$(date +%H:%M:%S) A: done"
else
  echo "$(date +%H:%M:%S) B: campaign c1 k=51.. (pending already has 50 valid)"
  python3 harness/campaign.py --serial emulator-5602 --avd P04AvdB --port 8788 --variants egress,rd,volatile,taint \
    --out results/raw/c1/B --start 51 --trials 12 --no-install --schedules netloss,kill,forcestop,reboot,revoke,inflight
  echo "$(date +%H:%M:%S) B: micro"; python3 harness/micro.py --serial emulator-5602 --out results/raw/micro
  echo "$(date +%H:%M:%S) B: acra"; python3 harness/acra_case.py --serial emulator-5602 --out results/raw/acra --trials 30 --reboot-trials 10
  echo "$(date +%H:%M:%S) B: alarm substrate"
  python3 harness/campaign.py --serial emulator-5602 --avd P04AvdB --port 8791 --variants alnone,alconv,alrd \
    --out results/raw/sub_alarm --schedules pending,kill,forcestop,reboot --trials 20 --substrate alarm --apkdir fixture/build/apk_alarm
  echo "$(date +%H:%M:%S) B: done"
fi
