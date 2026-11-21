#!/bin/bash
# Group 2 unattended chain (g2close-card.md, g2layer-card.md), one emulator at a time:
#   G2a calibration pilot -> throttle gate -> mechanism pilot -> mechanism gate -> G2a final
#   -> G2b pilot -> pilot gate -> G2b final.
# Gates read harness and mechanism fields only (calibrated durations, validity, CANCEL events, warm-up, request counts per
# port); never violations, bytes after the ack, deficits or latencies. A failed gate stops the chain (reported in RUNLOG).
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "- $(date '+%Y-%m-%d %H:%M') g2-chain: $*" >> artifact/results/RUNLOG.md; echo "$(date '+%H:%M') $*"; }
waitfree() { for p in "$@"; do for _ in $(seq 1 60); do lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 || lsof -nP -i :"$p" >/dev/null 2>&1 || break; sleep 5; done; done; }
AR=".claude/skills/p04-autorun/scripts/autorun.py"; P=artifact/plans/autorun
note "start (G2a then G2b)"
python3 $AR $P/g2close-pilot.json || { note "G2a calibration pilot failed; chain stopped"; exit 3; }
python3 - <<'PY' || { note "G2a THROTTLE GATE FAIL; no G2a final (card §3)"; exit 4; }
import json, sys
m = json.load(open('artifact/results/round3/g2close/pilot-calib2/calibration.json'))['median_s']
e, u, l = m.get('edge:2097152'), m.get('umts:2097152'), m.get('lte:2097152')
print('2 MiB medians (s): edge', e, 'umts', u, 'lte', l)
sys.exit(0 if e and u and l and e >= 3 * l and u >= 1.5 * l else 1)
PY
note "G2a throttle gate passed; mechanism pilot next"
waitfree 5660 8798
python3 $AR $P/g2close-mech.json || { note "G2a mechanism pilot failed; chain stopped"; exit 3; }
python3 - <<'PY' || { note "G2a MECHANISM GATE FAIL; no G2a final (card §3)"; exit 5; }
import json, sys
sys.path.insert(0, 'artifact/followup'); from analyze_race import validity, fields
rows = [json.loads(l) for l in open('artifact/results/round3/g2close/pilot-mech/trials.jsonl') if l.strip()]
bad = [r['trial'] for r in rows if validity(r)]
close = [r for r in rows if r['mode'] == 'close']
nocancel = [r['trial'] for r in close if not any(e.get('trial') == r['trial'] and e['kind'] == 'CANCEL' for e in r.get('events', []))]
noreply = [r['trial'] for r in close if not any(e.get('trial') == r['trial'] and e['kind'] == 'CANCEL_DONE' and fields(e['detail']).get('reply') == 'ok' for e in r.get('events', []))]
print('trials', len(rows), 'invalid', bad, 'close', len(close), 'no CANCEL', nocancel, 'no ok reply', noreply)
sys.exit(0 if len(rows) == 27 and not bad and len(close) == 9 and not nocancel and not noreply else 1)
PY
note "G2a mechanism gate passed; starting G2a final"
waitfree 5660 8798
python3 $AR $P/g2close-final.json --confirm g2close-final; rc=$?; note "G2a final autorun exit $rc"
waitfree 5660 5666 8795 8796 8797
python3 $AR $P/g2layer-pilot.json || { note "G2b pilot failed; chain stopped"; exit 3; }
python3 - <<'PY' || { note "G2b PILOT GATE FAIL; no G2b final (card §3)"; exit 6; }
import json, sys
sys.path.insert(0, 'artifact/followup'); from analyze_airguard import validity
d = 'artifact/results/round3/g2layer/pilot'; meta = json.load(open(f'{d}/meta.json')); V = meta['variants']
plans = [json.loads(l) for l in open(f'{d}/schedule.jsonl') if l.strip()]
dev = {(x['trial'], x['variant']): x['events'] for x in (json.loads(l) for l in open(f'{d}/device_events.jsonl') if l.strip())}
sink = [json.loads(l) for l in open(f'{d}/sink/ingest.jsonl') if l.strip()]
valid = [p['trial'] for p in plans if not validity(p, dev, V)]
warm = all(meta['warmup'][v]['ok'] for v in V)
ports = {r['port'] for r in sink if r.get('path') == 'donate_data'}
print('valid', valid, 'warm-up', meta['warmup'], 'donate ports', sorted(ports))
sys.exit(0 if len(plans) == 4 and len(valid) == 4 and warm and ports >= {8795, 8796, 8797} else 1)
PY
note "G2b pilot gate passed; starting G2b final"
waitfree 5666 8795 8796 8797
python3 $AR $P/g2layer-final.json --confirm g2layer-final; rc=$?; note "G2b final autorun exit $rc"
note "done"
}
main "$@"; exit $?
