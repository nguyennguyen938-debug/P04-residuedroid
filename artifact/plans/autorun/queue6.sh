#!/bin/bash
# Queue 6: after B10 final4, the B2 pilot (AirGuard stock vs fenced, 1 trial per schedule; b2-card.md). Pilot only: the final
# is frozen in the card after the pilot is reviewed.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') queue6: $*" | tee -a artifact/results/RUNLOG.md; }
while pgrep -f "queue[2345].sh|autorun.py artifact/plans/autorun/" >/dev/null; do sleep 30; done
for _ in $(seq 1 60); do lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -qE ":(5666|8796|8797) " || break; sleep 5; done
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b2-pilot.json; note "b2-pilot exit $?"
}
main "$@"; exit $?
