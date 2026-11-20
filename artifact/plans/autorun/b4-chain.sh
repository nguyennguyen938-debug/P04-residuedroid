#!/bin/bash
# B4 unattended chain (b4-card.md): after the B3 chain, 1-block pilot (mechanism: every trial valid-shaped), then final.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') b4-chain: $*" | tee -a artifact/results/RUNLOG.md; }
while pgrep -f "b3-chain.sh|b10-chain.sh|autorun.py artifact/plans/autorun/b(1[01]|3)" >/dev/null; do sleep 60; done
note "previous chains finished; starting B4 pilot"
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b4-pilot.json || { note "pilot failed; final not started"; exit 3; }
python3 - <<'PY' || { note "MECHANISM GATE FAIL; final not started"; exit 4; }
import json, sys
sys.path.insert(0, 'artifact/followup'); import analyze_sweep as A
rs = [json.loads(l) for l in open('artifact/results/round3/b4/pilot-1/trials.jsonl') if l.strip()]
bad = [(r['trial'], A.validity(r)) for r in rs if A.validity(r)]
print('pilot trials', len(rs), 'invalid', bad); sys.exit(0 if len(rs) == 20 and len(bad) <= 2 else 1)
PY
note "gate passed; starting B4 final"
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b4-final.json --confirm b4-final; note "final autorun exit $?"
}
main "$@"; exit $?
