#!/bin/bash
# G3c protocol v5c chain (v5/v5b mechanism gates failed on the in-app send-buffer reads; card Pilot log) (plans/g3app5-card.md; leader's request in issue #7, 23/11): builds stockcancel16, stockcancel, fenced.
#   calibration pilot-v5c-calib (N fixed at v4's 2233 beacons) -> calibration gate -> mechanism pilot pilot-v5c-mech -> gate
#   (incl. send buffer of the donation socket) -> final-v5c -> analysis-v5c (manifest post step).
# Gates read harness and mechanism fields only (calibrated durations, body sizes, validity, hook/marker events, marker
# presence in log and capture, in the calibration gate the kernel send buffer of the donation socket from guest ss: tb 32768 = 2 x 16384 for stockcancel16 and fenced); never bytes after the marker, sink completion,
# placement, cancel outcome or latencies. A failed gate stops the chain (RUNLOG); no automatic rerun.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "- $(date '+%Y-%m-%d %H:%M') g3c5c-chain: $*" >> artifact/results/RUNLOG.md; echo "$(date '+%H:%M') $*"; }
waitfree() { for p in "$@"; do for _ in $(seq 1 60); do lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 5; done; done; }
AR=".claude/skills/p04-autorun/scripts/autorun.py"; P=artifact/plans/autorun; R=artifact/results/round3
note "start G3c v5c (stockcancel16, stockcancel, fenced)"
waitfree 5666 8793 8794 8797 8799
python3 $AR $P/g3app5c-pilot.json || { note "G3c v5c calibration pilot failed; stopped"; return 3; }
CAL=$R/g3app/pilot-v5c-calib/calibration.json
python3 - "$CAL" <<'PY' || { note "G3c v5c CALIBRATION GATE FAIL; no final (card §3)"; return 6; }
import json, statistics, sys
c = json.load(open(sys.argv[1])); V = ['stockcancel16', 'stockcancel', 'fenced']
n_ok = all(len(c['samples_s'].get(v, [])) == 3 for v in V); D_ok = n_ok and all(c['median_s'][v] >= 5 for v in V)
b = [x for v in V for x in c['body_bytes'].get(v, []) if x]; body = statistics.median(b) if b else 0
print('calibrations per build', {v: len(c['samples_s'].get(v, [])) for v in V}, 'D', c.get('median_s'), 'median body bytes', body, 'nbeacons', c['nbeacons'])
import os
rows = [json.loads(l) for l in open(os.path.join(os.path.dirname(sys.argv[1]), 'trials.jsonl')) if l.strip()]
tb = {r['trial']: ((r.get('sockdiag') or {}).get('first') or {}).get('tb') for r in rows}
tb_bad = [t for t, x in tb.items() if x is None or (('-stockcancel16' in t or '-fenced' in t) and x != 32768)]
print('kernel sndbuf (ss tb) per calibration send', tb, 'tb bad', tb_bad)
sys.exit(0 if n_ok and D_ok and body >= 200 * 1024 and len(rows) == 9 and not tb_bad else 1)
PY
python3 -c "import json; c=json.load(open('$CAL')); c['source']='$CAL'; open('$R/g3app/calibration-used-v5c.json','w').write(json.dumps(c, indent=1)+'\n')"
note "G3c v5c calibration gate passed; mechanism pilot next"
waitfree 5666 8793 8794 8797 8799
python3 $AR $P/g3app5c-mech.json || { note "G3c v5c mechanism pilot failed; stopped"; return 3; }
python3 - <<'PY' || { note "G3c v5c MECHANISM GATE FAIL; no final (card §3)"; return 7; }
import json, sys
sys.path.insert(0, 'artifact/followup'); import analyze_g3app as g, analyze_g3app5 as g5
d = 'artifact/results/round3/g3app/pilot-v5c-mech'; meta = json.load(open(f'{d}/meta.json'))
rows = [json.loads(l) for l in open(f'{d}/trials.jsonl') if l.strip()]
bad = [(r['trial'], g.validity(r)) for r in rows if g.validity(r)]
mk_bad = [r['trial'] for r in rows if not any(e['kind'] == 'MARKER_SENT' and f"tid={r['trial']};" in e['detail'] and 'error=' not in e['detail'] for e in r.get('events', []))]
st_bad = [r['trial'] for r in rows if not next((x.get('ok') for x in r['actions'] if x['a'] == 'start_marker'), False)]
mlog = {json.loads(l)['id'] for l in open(f'{d}/marker.jsonl')}
need = {r['trial'] for r in rows} | {r['trial'] + '-start' for r in rows}
marks, _, _ = g.capture(f'{d}/capture.pcap', meta['marker'], set(meta['ports'].values()))
sb = {r['trial']: g5.donation_sndbuf(r.get('events', [])) for r in rows}
kb = {r['trial']: (r.get('sockdiag') or {}).get('polls', 0) for r in rows}   # v5c: the ss read ran (its value is checked in the calibration gate)
sb_bad = [t for t, x in kb.items() if not x]
print('rows', len(rows), 'invalid', bad, 'marker_sent bad', mk_bad, 'start marker bad', st_bad, 'missing in marker log', sorted(need - mlog),
      'missing in capture', sorted(need - set(marks)), 'donation sndbuf (API)', sb, 'sockdiag polls', kb, 'sndbuf bad', sb_bad)
sys.exit(0 if len(rows) == 6 and not (bad or mk_bad or st_bad or need - mlog or need - set(marks) or sb_bad) else 1)
PY
note "G3c v5c mechanism gate passed; starting final-v5c"
waitfree 5666 8793 8794 8797 8799
python3 $AR $P/g3app5c-final.json --confirm g3app5c-final; rc=$?; note "G3c final-v5c autorun exit $rc"; return $rc
}
main "$@"; exit $?
