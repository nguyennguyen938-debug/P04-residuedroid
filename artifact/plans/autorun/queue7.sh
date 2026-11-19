#!/bin/bash
# Queue 7: B2 pilot-3 (driver quiescence fix) → mechanical gate (b2-card.md Freeze) → B2 final (20 trials per schedule).
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') queue7: $*" | tee -a artifact/results/RUNLOG.md; }
free() { for _ in $(seq 1 60); do lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -qE ":($1) " || return 0; sleep 5; done; note "ports $1 still busy after 5 min"; return 1; }
run() { local m=$1 ports=$2; free "$ports" || return 1; python3 .claude/skills/p04-autorun/scripts/autorun.py "artifact/plans/autorun/$m.json" ${3:+--confirm $3}; local rc=$?; note "$m exit $rc"; return $rc; }
while pgrep -f "queue[2-6].sh|autorun.py artifact/plans/autorun/" >/dev/null; do sleep 30; done
if run b2-pilot3 "5666|8796|8797"; then
  if python3 - <<'PY'
import json, sys
d = 'artifact/results/round3/b2/pilot-3/'
plans = [json.loads(l) for l in open(d + 'schedule.jsonl') if l.strip()]
bad = [p['trial'] for p in plans if any(x['a'] == 'trial_error' or x.get('ok') is False for x in p['actions']) or p.get('device_alive_end') is not True]
warm = json.load(open(d + 'meta.json')).get('warmup', {})
ports = {json.loads(l).get('port') for l in open(d + 'sink/ingest.jsonl') if '"donate_data"' in l}
print('pilot-3 trials', len(plans), 'bad', bad, 'warm', warm, 'donate ports', sorted(p for p in ports if p))
sys.exit(0 if len(plans) == 4 and not bad and all(w.get('ok') for w in warm.values()) and len(warm) == 2 and {8796, 8797} <= ports else 1)
PY
  then note "B2 gate passed"; run b2-final "5666|8796|8797" b2-final; else note "B2 GATE FAIL; final not started"; fi
fi
note "done"
}
main "$@"; exit $?
