#!/bin/bash
# Queue 5: B10 protocol v3 (guest netem shaper, `--shaper tc`; b10-card.md v3) after the console preset failed the throttle
# gate twice (pilot-calib, pilot-calib3). Fresh directories pilot-calib4 / final4.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') queue5: $*" | tee -a artifact/results/RUNLOG.md; }
free() { for _ in $(seq 1 60); do lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -qE ":($1) " || return 0; sleep 5; done; note "ports $1 still busy after 5 min"; return 1; }
run() { local m=$1 ports=$2; free "$ports" || return 1; python3 .claude/skills/p04-autorun/scripts/autorun.py "artifact/plans/autorun/$m.json" ${3:+--confirm $3}; local rc=$?; note "$m exit $rc"; return $rc; }
while pgrep -f "queue[234].sh|autorun.py artifact/plans/autorun/" >/dev/null; do sleep 30; done
if run b10-pilot4 "5660|8798"; then
  if python3 - <<'PY'
import json, sys
m = json.load(open('artifact/results/round3/b10/pilot-calib4/calibration.json'))['median_s']
e, u, l = m.get('edge:2097152'), m.get('umts:2097152'), m.get('lte:2097152'); print('2 MiB medians', e, u, l)
sys.exit(0 if e and u and l and e >= 3 * l and u >= 1.5 * l else 1)
PY
  then note "B10 v3 throttle gate passed"; run b10-final4 "5660|8798" b10-final4; else note "B10 v3 THROTTLE GATE FAIL (guest netem); final not started — B10 stops (card v3)"; fi
fi
note "done"
}
main "$@"; exit $?
