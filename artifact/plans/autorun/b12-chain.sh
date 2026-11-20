#!/bin/bash
# B12 unattended chain (b12-card.md): after the B4 chain, base pilot, I0 gate (labels present), then the four mutants.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') b12-chain: $*" | tee -a artifact/results/RUNLOG.md; }
while pgrep -f "b4-chain.sh|b3-chain.sh|b10-chain.sh|autorun.py artifact/plans/autorun/b(1[01]|3|4)" >/dev/null; do sleep 60; done
note "previous chains finished; starting B12 base pilot"
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b12-pilot.json || { note "pilot failed; final not started"; exit 3; }
python3 artifact/mutation/label_check.py --name pilot-base --out artifact/results/mutation/pilot-base/labels.json artifact/results/mutation/pilot-base > /dev/null
python3 - <<'PY' || { note "I0 GATE FAIL (labels not in body or invalid pilot trials); final not started"; exit 4; }
import json, sys
c = json.load(open('artifact/results/mutation/pilot-base/labels.json'))['counts']
sc = [json.loads(l) for l in open('artifact/results/mutation/pilot-base/schedule.jsonl') if l.strip()]
bad = [x for r in sc for x in r['actions'] if x['a'] in ('trial_error', 'setup_fail')]
print('counts', c, 'trials', len(sc), 'errors', len(bad))
sys.exit(0 if c and all(k.endswith('/ok') for k in c) and len(sc) == 2 and not bad else 1)
PY
note "I0 gate passed; starting B12 final (4 mutants)"
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b12-final.json --confirm b12-final; note "final autorun exit $?"
}
main "$@"; exit $?
