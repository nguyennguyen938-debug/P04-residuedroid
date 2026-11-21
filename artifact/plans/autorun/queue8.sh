#!/bin/bash
# Queue 8: B4 protocol v3 (b4-card.md "Protocol v3"): pilot-v3 → mechanical gate → final-v3 → replacement blocks only if a
# cell has < 20 valid trials (validity counts only; no outcome field is read).
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') queue8: $*" | tee -a artifact/results/RUNLOG.md; }
free() { for _ in $(seq 1 60); do lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -qE ":($1) " || return 0; sleep 5; done; note "ports $1 still busy after 5 min"; return 1; }
run() { local m=$1 ports=$2; free "$ports" || return 1; python3 .claude/skills/p04-autorun/scripts/autorun.py "artifact/plans/autorun/$m.json" ${3:+--confirm $3}; local rc=$?; note "$m exit $rc"; return $rc; }
while pgrep -f "queue[2-7].sh|autorun.py artifact/plans/autorun/" >/dev/null; do sleep 30; done
run b4-pilot-v3 "5664|8799" || { note "pilot-v3 failed; final not started"; return 1; }
if python3 - <<'PY'
import json, sys
d = 'artifact/results/round3/b4/pilot-v3/'
rows = [json.loads(l) for l in open(d + 'trials.jsonl') if l.strip()]
meta = json.load(open(d + 'meta.json'))
bad = [r['trial'] for r in rows if r.get('harness_error')]
ok = len(rows) == 20 and not bad and meta.get('recv_timeout_s') == 300 and meta.get('apk_sha256', '').startswith('1afdfda3')
print('pilot-v3 trials', len(rows), 'harness errors', bad, 'recv_timeout_s', meta.get('recv_timeout_s'), 'gate', ok)
sys.exit(0 if ok else 1)
PY
then note "B4 v3 gate passed"; else note "B4 v3 GATE FAIL; final not started"; return 1; fi
run b4-final-v3 "5664|8799" b4-final-v3 || return 1
if python3 - <<'PY'
import json, sys
s = json.load(open('artifact/results/round3/b4/analysis-v3/sweep-summary.json'))
short = {c: v['trials'] for c, v in s['cells'].items() if v['trials'] < 20}
short.update({f'{c}KiB/{n}': 0 for c in (1, 4, 16, 64) for n in (1, 2, 4, 8, 16) if f'{c}KiB/{n}' not in s['cells']})
print('cells below 20 valid:', short); sys.exit(1 if short else 0)
PY
then note "B4 v3: every cell has 20 valid; no replacement"; else note "B4 v3: replacement blocks 20-21"; run b4-repl-v3 "5664|8799" b4-repl-v3; fi
note "done"
}
main "$@"; exit $?
