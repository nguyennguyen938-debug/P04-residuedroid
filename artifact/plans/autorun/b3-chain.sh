#!/bin/bash
# B3 unattended chain (b3-card.md): after the B10 chain (one emulator run at a time), 1-block pilot, mechanism gate, final.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') b3-chain: $*" | tee -a artifact/results/RUNLOG.md; }
while pgrep -f "b10-chain.sh|autorun.py artifact/plans/autorun/b1[01]" >/dev/null; do sleep 60; done
note "B10 chain finished; starting B3 pilot"
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b3-pilot.json || { note "pilot failed; final not started"; exit 3; }
python3 - <<'PY' || { note "MECHANISM GATE FAIL; final not started"; exit 4; }
import json, sys
rs = [json.loads(l) for l in open('artifact/results/round3/b3/pilot-1/trials.jsonl') if l.strip()]
ok = True
for r in rs:
    ev = r.get('events', []); mine = [e for e in ev if e['trial'] == r['trial']]
    if r.get('harness_error') or not r.get('complete_wait'): ok = False; print('no end', r['trial'])
    if r['condition'] != 'control' and r.get('barrier_seen') is not True: ok = False; print('barrier', r['trial'])
    if r['condition'] == 'prefirst' and r['split']:
        sp = [e for e in mine if e['kind'] == 'SPLIT']
        if not sp or sp[0]['detail'].endswith('resubmit=') or not any(e['trial'] == r['trial'] + '-split' for e in ev): ok = False; print('split mechanism', r['trial'])
print('gate', ok); sys.exit(0 if ok else 1)
PY
note "mechanism gate passed; starting B3 final"
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b3-final.json --confirm b3-final; note "final autorun exit $?"
}
main "$@"; exit $?
