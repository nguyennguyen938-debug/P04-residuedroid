#!/bin/bash
# Wait for both resume chains, then regenerate everything and shut down ONLY the P04 emulators (5600/5602).
source /Users/xuanbachle/Workstation/MobiSys2027/papers/shared-android/env.sh
cd /Users/xuanbachle/Workstation/MobiSys2027/papers/P04-residuedroid/artifact
while kill -0 72958 2>/dev/null || kill -0 72966 2>/dev/null || kill -0 73490 2>/dev/null || kill -0 73491 2>/dev/null; do sleep 60; done
echo "$(date +%H:%M:%S) chains finished; regenerating"
python3 scripts/summarize.py > results/raw/final_summarize.log 2>&1
python3 scripts/render.py > results/raw/final_render.log 2>&1
../manuscript/build.sh > results/raw/final_build.log 2>&1
for s in emulator-5600 emulator-5602; do timeout 20 adb -s $s shell "while iptables -D OUTPUT -d 10.0.2.2 -j REJECT 2>/dev/null; do :; done" 2>/dev/null; timeout 20 adb -s $s emu kill; done
pkill -f "P04-residuedroid/artifact/harness/sink.py"; pkill -f "harness/sink.py --port 87"
echo "- $(date +%H:%M) finish_watch: chains done; summarize/render/build run (logs results/raw/final_*.log); P04 emulators 5600/5602 shut down." >> results/RUNLOG.md
echo "$(date +%H:%M:%S) done"
