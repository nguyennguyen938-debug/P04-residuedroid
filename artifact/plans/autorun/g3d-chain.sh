#!/bin/bash
# Group 3 phone chain (g3cost-card.md): G3d pilot -> pilot gate -> final, on the single attached phone. Runs alongside
# g3-chain.sh (different device; receiver on the LAN address, port 8800). The gate reads harness fields only.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "- $(date '+%Y-%m-%d %H:%M') g3d-chain: $*" >> artifact/results/RUNLOG.md; echo "$(date '+%H:%M') $*"; }
AR=".claude/skills/p04-autorun/scripts/autorun.py"; P=artifact/plans/autorun
note "start (G3d on the phone)"
python3 $AR $P/g3cost-pilot.json || { note "G3d pilot failed; chain stopped"; exit 3; }
python3 - <<'PY' || { note "G3d PILOT GATE FAIL; no G3d final (card §3)"; exit 4; }
import json, sys
sys.path.insert(0, 'artifact/followup'); import analyze_g3cost as g
# pilot, pilot-2 stopped at setup; pilot-3 gate fail (adb transient, A15 batterystats format) -> G3d v2, pilot-4
d = 'artifact/results/round3/g3cost/pilot-4'; meta = json.load(open(f'{d}/meta.json'))
cells = [json.loads(l) for l in open(f'{d}/cells.jsonl') if l.strip()]
rec = {x['request'] for x in map(json.loads, open(f'{d}/receiver.jsonl')) if x.get('complete')}
ups = [u for c in cells for u in c['uploads']]
ok = [u for u in ups if u['end'] and u['end']['kind'] == 'SEND_OK' and u['id'] in rec]
bs = sum(g.mah(c.get('bs'), meta['uid'], c.get('bs_checkin')) is not None for c in cells)
print('cells', len(cells), 'valid', sum(g.valid(c) for c in cells), 'uploads ok+received', len(ok), '/', len(ups), 'cells with batterystats', bs)
sys.exit(0 if len(cells) == 9 and all(g.valid(c) for c in cells) and len(ok) == len(ups) == 18 and bs >= 1 else 1)
PY
note "G3d pilot gate passed; starting final"
python3 $AR $P/g3cost-final.json --confirm g3cost-final; rc=$?; note "G3d final autorun exit $rc"
note "done"
}
main "$@"; exit $?
