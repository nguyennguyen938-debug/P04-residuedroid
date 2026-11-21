#!/bin/bash
# B12 protocol v2 (b12-card.md "Protocol v2"): base pilot with --regrant-agg → mechanical gate (valid trials, labels ok,
# AGG for tenant 5 after its REGRANT in every pilot trial) → four builds. Never reads outcome fields.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') b12v2-chain: $*" | tee -a artifact/results/RUNLOG.md; }
while pgrep -f "queue[0-9].sh|-chain.sh .*b(4|10|3)|autorun.py artifact/plans/autorun/" | grep -v $$ >/dev/null; do sleep 30; done
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b12v2-pilot.json || { note "pilot failed; final not started"; exit 3; }
python3 artifact/mutation/label_check.py --name pilot-base --out artifact/results/mutation-v2/pilot-base/labels.json artifact/results/mutation-v2/pilot-base > /dev/null
python3 - <<'PY' || { note "B12 v2 GATE FAIL; final not started"; exit 4; }
import ast, json, sys
d = 'artifact/results/mutation-v2/pilot-base/'
c = json.load(open(d + 'labels.json'))['counts']
sc = [json.loads(l) for l in open(d + 'schedule.jsonl') if l.strip()]
bad = [x for r in sc for x in r['actions'] if x['a'] in ('trial_error', 'setup_fail')]
mech = []
for l in open(d + 'device_events.jsonl'):
    x = json.loads(l); ev = x['events'] if isinstance(x['events'], list) else ast.literal_eval(x['events'])
    rg = [e[0] for e in ev if e[4] == 'REGRANT' and e[3] == 5]
    mech.append(bool(rg) and any(e[4] == 'AGG' and e[3] == 5 and e[0] > rg[0] for e in ev))
print('labels', c, 'trials', len(sc), 'errors', len(bad), 'AGG after REGRANT per trial', mech)
sys.exit(0 if c and all(k.endswith('/ok') for k in c) and len(sc) == 2 and not bad and len(mech) == 2 and all(mech) else 1)
PY
note "B12 v2 gate passed; starting final (4 builds, --regrant-agg)"
for _ in $(seq 1 60); do lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -qE ":(5600|5601|8795) " || break; sleep 5; done   # pilot emulator releases its ports
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b12v2-final.json --confirm b12v2-final; note "final autorun exit $?"
}
main "$@"; exit $?
