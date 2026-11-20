#!/bin/bash
# Queue 3: after queue 2, B4 v2 (probes under load). One emulator run at a time; waits for the owned ports.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') queue3: $*" | tee -a artifact/results/RUNLOG.md; }
while pgrep -f "queue2.sh|autorun.py artifact/plans/autorun/" >/dev/null; do sleep 30; done
for _ in $(seq 1 60); do lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -qE ":(5664|8799) " || break; sleep 5; done
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b4-final-v2.json --confirm b4-final-v2; note "b4-final-v2 exit $?"
}
main "$@"; exit $?
