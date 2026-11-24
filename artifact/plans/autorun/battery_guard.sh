#!/bin/bash
# Operational stop when the Mac runs on battery (user 22/11: resume without the charger). Every 60 s: if discharging and the
# charge is <= LIMIT %, stop the chain (no next stage starts), then the running harness (SIGTERM; autorun aborts, runs guard and
# shuts down its own emulator), and log it. Reads only the power state, never trial data. Usage: battery_guard.sh <chain pid> [LIMIT]
set -u
cd "$(dirname "$0")/../../.." || exit 2
CHAIN=$1; LIMIT=${2:-15}
while kill -0 "$CHAIN" 2>/dev/null; do
  b=$(pmset -g batt | tail -1); pct=$(echo "$b" | grep -oE '[0-9]+%' | tr -d '%')
  if echo "$b" | grep -q discharging && [ -n "$pct" ] && [ "$pct" -le "$LIMIT" ]; then
    echo "- $(date '+%Y-%m-%d %H:%M') battery_guard: battery ${pct}% discharging (limit ${LIMIT}%); chain and harness stopped (operational, as the 15:52 pause)" >> artifact/results/RUNLOG.md
    pkill -P "$CHAIN" caffeinate 2>/dev/null; kill "$CHAIN" 2>/dev/null
    pkill -TERM -f "followup/race_suite.py|followup/race_airguard.py"; exit 0
  fi
  sleep 60
done
