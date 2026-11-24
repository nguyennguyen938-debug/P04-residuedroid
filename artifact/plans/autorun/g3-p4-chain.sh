#!/bin/bash
# P4 (plans/g3p4-card.md): pilot-p4 (1 block) -> mechanism gate -> final-p4 (30 blocks). The gate reads harness and
# mechanism fields only (validity, ABORT_ARMED, markers, capture SYNs, qsnap, requested_sndbuf), never bytes or latencies.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "- $(date '+%Y-%m-%d %H:%M') g3-p4: $*" >> artifact/results/RUNLOG.md; echo "$(date '+%H:%M') $*"; }
waitfree() { for p in "$@"; do for _ in $(seq 1 60); do lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 5; done; done; }
AR=".claude/skills/p04-autorun/scripts/autorun.py"; P=artifact/plans/autorun
note "start (P4: pilot 1 block, gate, final 30 blocks)"
waitfree 5660 8798 8799
python3 $AR $P/g3p4-pilot.json || { note "P4 pilot failed; stopped"; return 3; }
python3 - <<'PY' || { note "P4 MECHANISM GATE FAIL; no P4 final (g3p4-card §3)"; return 5; }
import json, sys
sys.path.insert(0, 'artifact/followup'); from analyze_race import validity, fields; import analyze_g3race as g
d = 'artifact/results/round3/g3race/pilot-p4'
rows = [json.loads(l) for l in open(f'{d}/trials.jsonl') if l.strip()]
own = lambda r: [e for e in r.get('events', []) if e.get('trial') == r['trial']]
bad = [r['trial'] for r in rows if validity(r)]
ab_bad = [r['trial'] for r in rows if r['mode'] == 'fence-abort' and any(e['kind'] == 'BLOCK' for e in own(r)) and not any(e['kind'] == 'ABORT_ARMED' and 'linger0=true' in e['detail'] for e in own(r))]
mk_bad = [r['trial'] for r in rows if not any(e['kind'] == 'MARKER_SENT' and 'error=' not in e['detail'] for e in own(r))]
mlog = {json.loads(l)['id'] for l in open(f'{d}/marker.jsonl')}
ml_bad = [r['trial'] for r in rows if r['trial'] not in mlog]
markers, conns, _ = g.capture(f'{d}/capture.pcap', 8799); ports = {sp for _, sp in conns}
cap_bad = [r['trial'] for r in rows if r['trial'] not in markers]
syn_bad = [r['trial'] for r in rows if (p := g.secondary(r, set())['local_port']) and p not in ports]
q_bad = [r['trial'] for r in rows if 'qdisc' not in r.get('qsnap', '')]
sb_bad = [r['trial'] for r in rows if not any(e['kind'] == 'SOCKET_CONFIG' and fields(e['detail']).get('requested_sndbuf') == str(r['sndbuf']) for e in own(r))]
actual = sorted({(r['sndbuf'], fields(e['detail']).get('actual_sndbuf')) for r in rows for e in own(r) if e['kind'] == 'SOCKET_CONFIG'})
print('trials', len(rows), 'invalid', bad, 'abort bad', ab_bad, 'marker_sent bad', mk_bad, 'marker log bad', ml_bad, 'capture marker missing', cap_bad,
      'request SYN missing', syn_bad, 'qsnap bad', q_bad, 'sndbuf bad', sb_bad, 'levels (requested, actual)', actual)
sys.exit(0 if len(rows) == 12 and not (bad or ab_bad or mk_bad or ml_bad or cap_bad or syn_bad or q_bad or sb_bad) else 1)
PY
note "P4 mechanism gate passed; starting final-p4"
waitfree 5660 8798 8799
python3 $AR $P/g3p4-final.json --confirm g3p4-final; rc=$?; note "P4 final-p4 autorun exit $rc"; return $rc
}
main "$@"; rc=$?; g=$(bash .claude/skills/p04-experiment/scripts/guard.sh 2>&1 | tail -1); echo "- $(date '+%Y-%m-%d %H:%M') g3-p4: done (exit $rc); final guard: $g" >> artifact/results/RUNLOG.md; exit $rc
