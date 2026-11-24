#!/bin/bash
# Group 3 emulator chain, protocol v2 (22/11 after the failed pilot-mech gate: capture via emulator -tcpdump at launch).
# Calibration pilot-calib and its throttle gate (passed 14:35) are reused; from the mechanism pilot on as v1:
#   G3a/G3b calibration -> throttle gate -> mechanism pilot -> mechanism gate -> final
#   -> G3c calibration -> calibration gate [-> one recalibration if only the body size failed] -> mechanism pilot -> gate -> final.
# Gates read harness and mechanism fields only (calibrated durations and body sizes, validity, cancellation and marker
# events, capture presence of markers and request SYNs, tc band stats); never violations, bytes after W/ack/marker,
# placement or latencies. A failed gate stops the chain (RUNLOG).
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "- $(date '+%Y-%m-%d %H:%M') g3-chain: $*" >> artifact/results/RUNLOG.md; echo "$(date '+%H:%M') $*"; }
waitfree() { for p in "$@"; do for _ in $(seq 1 60); do lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 5; done; done; }
AR=".claude/skills/p04-autorun/scripts/autorun.py"; P=artifact/plans/autorun
note "start v2 (G3a/G3b mechanism pilot 2, then final, then G3c)"
note "v2 (capture via -tcpdump at launch): calibration pilot-calib and its throttle gate (passed 14:35) reused"
waitfree 5660 8798 8799
python3 $AR $P/g3race-mech2.json || { note "G3a mechanism pilot failed; chain stopped"; exit 3; }
python3 - <<'PY' || { note "G3a/G3b MECHANISM GATE FAIL; no final (card §3)"; exit 5; }
import json, sys
sys.path.insert(0, 'artifact/followup'); from analyze_race import validity, fields; import analyze_g3race as g
d = 'artifact/results/round3/g3race/pilot-mech2'
rows = [json.loads(l) for l in open(f'{d}/trials.jsonl') if l.strip()]
own = lambda r: [e for e in r.get('events', []) if e.get('trial') == r['trial']]
bad = [r['trial'] for r in rows if validity(r)]
close = [r for r in rows if r['mode'] == 'close']; close2 = [r for r in rows if r['mode'] == 'close2']
c_bad = [r['trial'] for r in close if not (any(e['kind'] == 'CANCEL' for e in own(r)) and any(e['kind'] == 'CANCEL_DONE' and fields(e['detail']).get('reply') == 'ok' for e in own(r)))]
c2_bad = [r['trial'] for r in close2 if not any(e['kind'] == 'CANCEL_DONE' and e['detail'].startswith('inproc') for e in own(r))]
mk_bad = [r['trial'] for r in rows if not any(e['kind'] == 'MARKER_SENT' and 'error=' not in e['detail'] for e in own(r))]
mlog = {json.loads(l)['id'] for l in open(f'{d}/marker.jsonl')}
ml_bad = [r['trial'] for r in rows if r['trial'] not in mlog]
markers, conns, _ = g.capture(f'{d}/capture.pcap', 8799)
cap_bad = [r['trial'] for r in rows if r['trial'] not in markers]
ports = {sp for _, sp in conns}
syn_bad = [r['trial'] for r in rows if (p := g.secondary(r, set())['local_port']) and p not in ports]
tc_ok = any('filter' in r.get('net', '') and 'u32' in r.get('net', '') for r in rows) and any(
    'pfifo 10:' in r.get('tc_stats_end', '') and 'Sent 0 bytes' not in r['tc_stats_end'].split('pfifo 10:')[1][:200] for r in rows)
print('trials', len(rows), 'invalid', bad, 'close bad', c_bad, 'close2 bad', c2_bad, 'marker_sent bad', mk_bad, 'marker log bad', ml_bad,
      'capture marker missing', cap_bad, 'request SYN missing', syn_bad, 'tc filter+band ok', tc_ok)
sys.exit(0 if len(rows) == 45 and not (bad or c_bad or c2_bad or mk_bad or ml_bad or cap_bad or syn_bad) and len(close) == 9 and len(close2) == 9 and tc_ok else 1)
PY
note "G3a/G3b mechanism gate passed; starting final"
waitfree 5660 8798 8799
python3 $AR $P/g3race-final.json --confirm g3race-final; rc=$?; note "G3a/G3b final autorun exit $rc"
waitfree 5660 5666 8793 8795 8796 8797 8799
python3 $AR $P/g3app-pilot.json || { note "G3c calibration pilot failed; chain stopped"; exit 3; }
gate_cal() { python3 - "$1" <<'PY'
import json, statistics, sys
c = json.load(open(sys.argv[1])); V = ['stock', 'stockcancel', 'fenced', 'layered']
n_ok = all(len(c['samples_s'].get(v, [])) == 3 for v in V); D_ok = n_ok and all(c['median_s'][v] >= 5 for v in V)
b = [x for v in V for x in c['body_bytes'].get(v, []) if x]; body = statistics.median(b) if b else 0
print('calibrations per build', {v: len(c['samples_s'].get(v, [])) for v in V}, 'D', c['median_s'], 'median body bytes', body, 'nbeacons', c['nbeacons'])
sys.exit(0 if n_ok and D_ok and body >= 200 * 1024 else 2 if n_ok and body < 200 * 1024 else 1)
PY
}
CAL=artifact/results/round3/g3app/pilot-calib/calibration.json
gate_cal $CAL; g=$?
if [ $g -eq 2 ]; then
  note "G3c calibration gate: body size below 200 KiB only; one recalibration (card §3)"
  waitfree 5666 8793 8795 8796 8797 8799
  python3 $AR $P/g3app-pilot2.json || { note "G3c recalibration pilot failed; chain stopped"; exit 3; }
  CAL=artifact/results/round3/g3app/pilot-calib2/calibration.json; gate_cal $CAL; g=$?
fi
[ $g -eq 0 ] || { note "G3c CALIBRATION GATE FAIL; no G3c final (card §3)"; exit 6; }
python3 -c "import json,sys; c=json.load(open('$CAL')); c['source']='$CAL'; open('artifact/results/round3/g3app/calibration-used.json','w').write(json.dumps(c, indent=1)+'\n')"
note "G3c calibration gate passed ($CAL); mechanism pilot next"
waitfree 5666 8793 8795 8796 8797 8799
python3 $AR $P/g3app-mech.json || { note "G3c mechanism pilot failed; chain stopped"; exit 3; }
python3 - <<'PY' || { note "G3c MECHANISM GATE FAIL; no G3c final (card §3)"; exit 7; }
import json, sys
sys.path.insert(0, 'artifact/followup'); import analyze_g3app as g
d = 'artifact/results/round3/g3app/pilot-mech'; meta = json.load(open(f'{d}/meta.json'))
rows = [json.loads(l) for l in open(f'{d}/trials.jsonl') if l.strip()]
bad = [r['trial'] for r in rows if g.validity(r)]
mk_bad = [r['trial'] for r in rows if not any(e['kind'] == 'MARKER_SENT' and f"tid={r['trial']};" in e['detail'] and 'error=' not in e['detail'] for e in r.get('events', []))]
st_bad = [r['trial'] for r in rows if not next((x.get('ok') for x in r['actions'] if x['a'] == 'start_marker'), False)]
mlog = {json.loads(l)['id'] for l in open(f'{d}/marker.jsonl')}
need = {r['trial'] for r in rows} | {r['trial'] + '-start' for r in rows}
marks, _, _ = g.capture(f'{d}/capture.pcap', meta['marker'], set(meta['ports'].values()))
print('rows', len(rows), 'invalid', bad, 'marker_sent bad', mk_bad, 'start marker bad', st_bad, 'missing in marker log', sorted(need - mlog), 'missing in capture', sorted(need - set(marks)))
sys.exit(0 if len(rows) == 8 and not (bad or mk_bad or st_bad or need - mlog or need - set(marks)) else 1)
PY
note "G3c mechanism gate passed; starting G3c final"
waitfree 5666 8793 8795 8796 8797 8799
python3 $AR $P/g3app-final.json --confirm g3app-final; rc=$?; note "G3c final autorun exit $rc"
note "done"
}
main "$@"; exit $?
