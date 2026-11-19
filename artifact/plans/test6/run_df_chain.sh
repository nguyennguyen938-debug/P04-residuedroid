#!/bin/bash
# Test 6 on Device Farm, unattended: pilot -> mechanism gates (check_gates.py) -> main job 1 -> main job 2 (test6-card.md).
# The chain stops only if the pilot gates fail; it never looks at outcomes. Main jobs always both run (replacements of
# invalid trials are decided afterwards from the validity rules). Needs the user's go-ahead (Device Farm minutes).
# Usage: run_df_chain.sh <env dir> <prefix of env files, e.g. uploads-p2> [--skip-pilot]
set -uo pipefail
ENVD=$1; PFX=$2; SKIP=${3:-}
HERE=$(cd "$(dirname "$0")" && pwd); ART=$(cd "$HERE/../.." && pwd); R=$ART/results/round3/test6
note() { echo "$(date '+%Y-%m-%d %H:%M') $*"; }
if [ "$SKIP" != --skip-pilot ]; then
  note "chain: pilot"
  bash "$HERE/run_df.sh" "$ENVD/$PFX-pilot.env" test6-pilot2-pixel8a "$R/pilot-df-pixel8a-2" 20 || { note "chain: pilot run failed"; exit 3; }
  python3 "$HERE/check_gates.py" "$R/pilot-df-pixel8a-2" || { note "chain: PILOT GATES FAIL, stopping"; exit 4; }
fi
note "chain: main job 1"
bash "$HERE/run_df.sh" "$ENVD/$PFX-j1.env" test6-main-j1-pixel8a "$R/pixel8a-j1" 100; note "chain: job 1 exit $?"
python3 "$HERE/check_gates.py" "$R/pixel8a-j1" --tls 140 --life 30; note "chain: job 1 gates exit $? (informational)"
note "chain: main job 2"
bash "$HERE/run_df.sh" "$ENVD/$PFX-j2.env" test6-main-j2-pixel8a "$R/pixel8a-j2" 100; note "chain: job 2 exit $?"
note "chain: done"
