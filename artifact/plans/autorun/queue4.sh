#!/bin/bash
# Queue 4: after queue 3 (B4 v2), B10 v2 again with the radio-metadata fix in race_suite.py (b10-pilot2 aborted before any
# trial: `dumpsys | grep` exit 1 on no match). Same protocol v2 (radio path), fresh directories pilot-calib3 / final3.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') queue4: $*" | tee -a artifact/results/RUNLOG.md; }
free() { for _ in $(seq 1 60); do lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -qE ":($1) " || return 0; sleep 5; done; note "ports $1 still busy after 5 min"; return 1; }
run() { local m=$1 ports=$2; free "$ports" || return 1; python3 .claude/skills/p04-autorun/scripts/autorun.py "artifact/plans/autorun/$m.json" ${3:+--confirm $3}; local rc=$?; note "$m exit $rc"; return $rc; }
while pgrep -f "queue[23].sh|autorun.py artifact/plans/autorun/" >/dev/null; do sleep 30; done
if run b10-pilot3 "5660|8798"; then
  if python3 - <<'PY'
import json, sys
m = json.load(open('artifact/results/round3/b10/pilot-calib3/calibration.json'))['median_s']
e, u, l = m.get('edge:2097152'), m.get('umts:2097152'), m.get('lte:2097152'); print('2 MiB medians', e, u, l)
sys.exit(0 if e and u and l and e >= 3 * l and u >= 1.5 * l else 1)
PY
  then note "B10 v2 throttle gate passed"; run b10-final3 "5660|8798" b10-final3; else note "B10 v2 THROTTLE GATE FAIL (radio path); final not started — host shaper needed (sudo)"; fi
fi
note "done"
}
main "$@"; exit $?
