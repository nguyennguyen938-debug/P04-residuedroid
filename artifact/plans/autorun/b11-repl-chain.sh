#!/bin/bash
# B11 replacements (b11-card.md §3): after the queue (B12 chain) finishes, count valid paired trials per (AVD, schedule)
# with analyze_b11.py (validity only), and for every schedule short of 20 run new k >= 20 (cap 5) in a fresh directory.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "$(date '+%Y-%m-%d %H:%M') b11-repl: $*" | tee -a artifact/results/RUNLOG.md; }
while pgrep -f "b12-chain.sh|b4-chain.sh|b3-chain.sh|b10-chain.sh|autorun.py artifact/plans/autorun/b" >/dev/null; do sleep 60; done
python3 artifact/followup/analyze_b11.py --out /tmp/p04-b11-count >/dev/null 2>&1
python3 - <<'PY' > /tmp/p04-b11-repl.json
import json
d = json.load(open('/tmp/p04-b11-count/b11-summary.json'))['avds']; plan = {}
for name, avd, serial, port in (('Fourteen', 'P04Avd14', 'emulator-5650', 8790), ('Fifteen', 'P04Avd15', 'emulator-5654', 8791)):
    per = d.get(name, {}).get('per_schedule', {}); short = {s: 20 - per.get(s, 0) for s in ('pending', 'kill', 'reboot', 'netloss') if per.get(s, 0) < 20}
    if short: plan[name] = dict(avd=avd, serial=serial, port=port, schedules=','.join(short), trials=min(5, max(short.values())))
print(json.dumps(plan))
PY
[ "$(cat /tmp/p04-b11-repl.json)" = "{}" ] && { note "no replacement needed (all cells have 20 valid)"; exit 0; }
note "replacement plan $(cat /tmp/p04-b11-repl.json)"
python3 - <<'PY'
import json
plan = json.load(open('/tmp/p04-b11-repl.json'))
env = json.load(open('artifact/plans/autorun/b11-final.json'))['env']
stages = [{"name": f"repl-{n}", "cwd": "artifact", "cmd": ["python3", "followup/campaign.py", "--serial", p['serial'], "--avd", p['avd'], "--port", str(p['port']),
           "--variants", "menqueue,mlayer,mfence", "--apkdir", "fixture/build/revision-apk", "--timeout", "90", "--schedules", p['schedules'],
           "--start", "20", "--trials", str(p['trials']), "--seed", "b11-20261119", "--out", f"results/round3/b11/{'avd14' if n == 'Fourteen' else 'avd15'}-repl"],
           "out": f"artifact/results/round3/b11/{'avd14' if n == 'Fourteen' else 'avd15'}-repl"} for n, p in plan.items()]
json.dump({"id": "b11-repl", "kind": "final", "card": "artifact/plans/b11-card.md", "deadline_hours": 3, "env": env,
           "owned_serials": ["emulator-5650", "emulator-5654"], "pre": ["bash .claude/skills/p04-experiment/scripts/preflight.sh"],
           "stages": stages, "post": [], "guard_after": True}, open('artifact/plans/autorun/b11-repl.json', 'w'), indent=2)
PY
python3 .claude/skills/p04-autorun/scripts/autorun.py artifact/plans/autorun/b11-repl.json --confirm b11-repl; note "replacement autorun exit $?"
}
main "$@"; exit $?
