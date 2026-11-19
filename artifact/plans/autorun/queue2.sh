#!/bin/bash
# Queue 2 (19/11 evening), one emulator run at a time. Fixes the pilot→final race of the first chains (the pilot's emulator
# port was still busy when the final's preflight ran): wait until every port the next manifest owns is free.
# Order: B4 final, B12 final, B3 v2 (pilot-2 → gate → final), B10 v2 (radio path: calibration → throttle gate → final2).
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') queue2: $*" | tee -a artifact/results/RUNLOG.md; }
free() { for _ in $(seq 1 60); do lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -qE ":($1) " || return 0; sleep 5; done; note "ports $1 still busy after 5 min"; return 1; }
run() { local m=$1 ports=$2; free "$ports" || return 1; python3 .claude/skills/p04-autorun/scripts/autorun.py "artifact/plans/autorun/$m.json" ${3:+--confirm $3}; local rc=$?; note "$m exit $rc"; return $rc; }
while pgrep -f "autorun.py artifact/plans/autorun/|chain.sh" >/dev/null; do sleep 30; done
run b4-final "5664|8799" b4-final
run b12-final "5600|8795" b12-final
if run b3-pilot2 "5662|8798"; then
  if python3 - <<'PY'
import json, sys
rs = [json.loads(l) for l in open('artifact/results/round3/b3/pilot-2/trials.jsonl') if l.strip()]
bad = [(r['trial'], r['condition'], r['split']) for r in rs if r.get('harness_error') or not r.get('complete_wait') or (r['condition'] != 'control' and r.get('barrier_seen') is not True)]
sp = [r for r in rs if r['condition'] == 'prefirst' and r['split'] and any(e['trial'] == r['trial'] + '-split' for e in r.get('events', []))]
print('pilot-2', len(rs), 'bad', bad, 'split resubmitted', len(sp)); sys.exit(0 if len(rs) == 6 and not bad and sp else 1)
PY
  then note "B3 v2 gate passed"; run b3-final "5662|8798" b3-final; else note "B3 v2 GATE FAIL; final not started"; fi
fi
if run b10-pilot2 "5660|8798"; then
  if python3 - <<'PY'
import json, sys
m = json.load(open('artifact/results/round3/b10/pilot-calib2/calibration.json'))['median_s']
e, u, l = m.get('edge:2097152'), m.get('umts:2097152'), m.get('lte:2097152'); print('2 MiB medians', e, u, l)
sys.exit(0 if e and u and l and e >= 3 * l and u >= 1.5 * l else 1)
PY
  then note "B10 v2 throttle gate passed"; run b10-final2 "5660|8798" b10-final2; else note "B10 v2 THROTTLE GATE FAIL (radio path); final not started — host shaper needed (sudo)"; fi
fi
note "done"
}
main "$@"; exit $?
