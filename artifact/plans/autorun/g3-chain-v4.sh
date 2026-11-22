#!/bin/bash
# Group 3 emulator chain v4 (22/11 evening; leader approved P3 and P4 in issue #7):
#   G3c protocol v4: calibration pilot-v4-calib -> calibration gate [-> one recalibration pilot-v4-calib2 if only the body
#   size failed] -> mechanism pilot pilot-v4-mech -> gate -> final-v4;
#   then, independent of the G3c outcome, P3 (plans/g3lte-card.md): pilot-lte4 (1 block) -> mechanism + balance gate -> final-lte4.
# Gates read harness and mechanism fields only (calibrated durations and body sizes, validity, hook and marker events,
# capture presence of markers and request SYNs, warm-up replies, withdrawal timing relative to the socket); never
# violations, bytes after W/ack/marker, placement or latencies. A failed gate stops that task (RUNLOG); P3 runs after G3c either way.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "- $(date '+%Y-%m-%d %H:%M') g3-chain: $*" >> artifact/results/RUNLOG.md; echo "$(date '+%H:%M') $*"; }
waitfree() { for p in "$@"; do for _ in $(seq 1 60); do lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 5; done; done; }
AR=".claude/skills/p04-autorun/scripts/autorun.py"; P=artifact/plans/autorun; R=artifact/results/round3
note "start v4 (G3c protocol v4, then P3 lte balanced)"
g3c; note "G3c v4 part ended (exit $?)"
p3; rc=$?; note "P3 part ended (exit $rc)"; note "done"
}
gate_cal() { python3 - "$1" <<'PY'
import json, statistics, sys
c = json.load(open(sys.argv[1])); V = ['stock', 'stockcancel', 'fenced', 'layered']
n_ok = all(len(c['samples_s'].get(v, [])) == 3 for v in V); D_ok = n_ok and all(c['median_s'][v] >= 5 for v in V)
b = [x for v in V for x in c['body_bytes'].get(v, []) if x]; body = statistics.median(b) if b else 0
print('calibrations per build', {v: len(c['samples_s'].get(v, [])) for v in V}, 'D', c['median_s'], 'median body bytes', body, 'nbeacons', c['nbeacons'])
sys.exit(0 if n_ok and D_ok and body >= 200 * 1024 else 2 if n_ok and body < 200 * 1024 else 1)
PY
}
g3c() {
waitfree 5660 5666 8793 8795 8796 8797 8799
python3 $AR $P/g3app4-pilot.json || { note "G3c v4 calibration pilot failed; G3c stopped"; return 3; }
CAL=$R/g3app/pilot-v4-calib/calibration.json; gate_cal $CAL; g=$?
if [ $g -eq 2 ]; then
  note "G3c v4 calibration gate: body size below 200 KiB only; one recalibration (card §3)"
  waitfree 5666 8793 8795 8796 8797 8799
  python3 $AR $P/g3app4-pilot2.json || { note "G3c v4 recalibration pilot failed; G3c stopped"; return 3; }
  CAL=$R/g3app/pilot-v4-calib2/calibration.json; gate_cal $CAL; g=$?
fi
[ $g -eq 0 ] || { note "G3c v4 CALIBRATION GATE FAIL; no G3c final (card §3)"; return 6; }
python3 -c "import json; c=json.load(open('$CAL')); c['source']='$CAL'; open('$R/g3app/calibration-used-v4.json','w').write(json.dumps(c, indent=1)+'\n')"
note "G3c v4 calibration gate passed ($CAL); mechanism pilot next"
waitfree 5666 8793 8795 8796 8797 8799
python3 $AR $P/g3app4-mech.json || { note "G3c v4 mechanism pilot failed; G3c stopped"; return 3; }
python3 - <<'PY' || { note "G3c v4 MECHANISM GATE FAIL; no G3c final (card §3)"; return 7; }
import json, sys
sys.path.insert(0, 'artifact/followup'); import analyze_g3app as g
d = 'artifact/results/round3/g3app/pilot-v4-mech'; meta = json.load(open(f'{d}/meta.json'))
rows = [json.loads(l) for l in open(f'{d}/trials.jsonl') if l.strip()]
bad = [(r['trial'], g.validity(r)) for r in rows if g.validity(r)]
mk_bad = [r['trial'] for r in rows if not any(e['kind'] == 'MARKER_SENT' and f"tid={r['trial']};" in e['detail'] and 'error=' not in e['detail'] for e in r.get('events', []))]
st_bad = [r['trial'] for r in rows if not next((x.get('ok') for x in r['actions'] if x['a'] == 'start_marker'), False)]
mlog = {json.loads(l)['id'] for l in open(f'{d}/marker.jsonl')}
need = {r['trial'] for r in rows} | {r['trial'] + '-start' for r in rows}
marks, _, _ = g.capture(f'{d}/capture.pcap', meta['marker'], set(meta['ports'].values()))
print('rows', len(rows), 'invalid', bad, 'marker_sent bad', mk_bad, 'start marker bad', st_bad, 'missing in marker log', sorted(need - mlog), 'missing in capture', sorted(need - set(marks)))
sys.exit(0 if len(rows) == 8 and not (bad or mk_bad or st_bad or need - mlog or need - set(marks)) else 1)
PY
note "G3c v4 mechanism gate passed; starting G3c final-v4"
waitfree 5666 8793 8795 8796 8797 8799
python3 $AR $P/g3app4-final.json --confirm g3app4-final; rc=$?; note "G3c final-v4 autorun exit $rc"; return $rc
}
p3() {
waitfree 5660 5666 8798 8799
python3 $AR $P/g3lte-pilot.json || { note "P3 pilot failed; P3 stopped"; return 3; }
python3 - <<'PY' || { note "P3 MECHANISM/BALANCE GATE FAIL; no P3 final (g3lte-card §3)"; return 5; }
import json, statistics, sys
sys.path.insert(0, 'artifact/followup'); from analyze_race import validity, fields; import analyze_g3race as g
d = 'artifact/results/round3/g3race/pilot-lte4'
rows = [json.loads(l) for l in open(f'{d}/trials.jsonl') if l.strip()]
own = lambda r: [e for e in r.get('events', []) if e.get('trial') == r['trial']]
first = lambda r, k: min((e['mono_ns'] for e in own(r) if e['kind'] == k), default=None)
bad = [r['trial'] for r in rows if validity(r)]
close = [r for r in rows if r['mode'] == 'close']; close2 = [r for r in rows if r['mode'] == 'close2']
c_bad = [r['trial'] for r in close if not (any(e['kind'] == 'CANCEL' for e in own(r)) and any(e['kind'] == 'CANCEL_DONE' and fields(e['detail']).get('reply') == 'ok' for e in own(r)))]
c2_bad = [r['trial'] for r in close2 if not any(e['kind'] == 'CANCEL_DONE' and e['detail'].startswith('inproc') for e in own(r))]
mk_bad = [r['trial'] for r in rows if not any(e['kind'] == 'MARKER_SENT' and 'error=' not in e['detail'] for e in own(r))]
mlog = {json.loads(l)['id'] for l in open(f'{d}/marker.jsonl')}
ml_bad = [r['trial'] for r in rows if r['trial'] not in mlog]
markers, conns, _ = g.capture(f'{d}/capture.pcap', 8799); ports = {sp for _, sp in conns}
cap_bad = [r['trial'] for r in rows if r['trial'] not in markers]
syn_bad = [r['trial'] for r in rows if (p := g.secondary(r, set())['local_port']) and p not in ports]
warm_bad = [r['trial'] for r in rows if 'data="ok"' not in r.get('warm', '')]
q_bad = [r['trial'] for r in rows if 'qdisc' not in r.get('qsnap', '')]
lag = {}
for r in rows:
    sc, rq = first(r, 'SOCKET_CONFIG'), first(r, 'WITHDRAW_REQUEST')
    if sc is not None and rq is not None: lag.setdefault(r['mode'], []).append((rq - sc) / 1e9)
med = {m: round(statistics.median(v), 4) for m, v in lag.items()}
spread = max(med.values()) - min(med.values()) if len(med) == 5 else None
print('trials', len(rows), 'invalid', bad, 'close bad', c_bad, 'close2 bad', c2_bad, 'marker_sent bad', mk_bad, 'marker log bad', ml_bad,
      'capture marker missing', cap_bad, 'request SYN missing', syn_bad, 'warm bad', warm_bad, 'qsnap bad', q_bad,
      'median WITHDRAW_REQUEST - SOCKET_CONFIG (s)', med, 'spread', spread)
sys.exit(0 if len(rows) == 15 and not (bad or c_bad or c2_bad or mk_bad or ml_bad or cap_bad or syn_bad or warm_bad or q_bad)
         and len(close) == 3 and len(close2) == 3 and spread is not None and spread <= 0.015 else 1)
PY
note "P3 mechanism/balance gate passed; starting P3 final-lte4"
waitfree 5660 8798 8799
python3 $AR $P/g3lte-final.json --confirm g3lte-final; rc=$?; note "P3 final-lte4 autorun exit $rc"; return $rc
}
main "$@"; exit $?
