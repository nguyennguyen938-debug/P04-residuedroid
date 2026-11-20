#!/bin/bash
# B10 unattended chain (b10-card.md): wait for the B11 run to finish (one emulator run at a time on this Mac), calibration
# pilot, mechanical throttle gate, then the final run. Never reads outcomes.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') b10-chain: $*" | tee -a artifact/results/RUNLOG.md; }
while pgrep -f "autorun.py artifact/plans/autorun/b11-final.json" >/dev/null; do sleep 60; done
note "B11 finished; starting B10 calibration pilot"
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b10-pilot.json || { note "pilot failed (see autorun-b10-pilot.log), final not started"; exit 3; }
python3 - <<'PY' || { note "THROTTLE GATE FAIL: emulator link shaping not effective; final not started (protocol v2 needed)"; exit 4; }
import json, sys
m = json.load(open('artifact/results/round3/b10/pilot-calib/calibration.json'))['median_s']
e, u, l = m.get('edge:2097152'), m.get('umts:2097152'), m.get('lte:2097152')
print('2 MiB medians (s): edge', e, 'umts', u, 'lte', l)
sys.exit(0 if e and u and l and e >= 3 * l and u >= 1.5 * l else 1)
PY
note "throttle gate passed; starting B10 final"
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b10-final.json --confirm b10-final; note "final autorun exit $?"
}
main "$@"; exit $?
