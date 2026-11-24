#!/bin/bash
# P3 protocol v5 (plans/g3lte-card.md Pilot log, 22/11 night): the v4 balance gate failed on its design (one trial per
# (size, arm) measures per-trial jitter; one adb stall), so v5 changes only the pilot size and the gate:
#   pilot-lte5 (3 blocks, 45 trials) -> mechanism + balance gate v5 -> final-lte5 (10 blocks).
# Gate v5 reads harness, mechanism and timing fields only, never outcomes. Balance metric per trial:
#   d = (WITHDRAW_REQUEST - SOCKET_CONFIG, device clock) - (withdraw host offset, host clock)
# (a difference of two durations, each on one clock): the withdrawal's delivery delay relative to the send's, which is what
# the :revision cold start inflated in v3. Trials whose host offset exceeds u*D by > 1 s (adb stall) are counted and left out
# of the balance metric. Pass: per-arm medians of d differ by <= 15 ms, plus every v4 mechanism field.
set -uo pipefail
main() {
cd "$(dirname "$0")/../../.." || exit 2
note() { echo "- $(date '+%Y-%m-%d %H:%M') g3-p3v5: $*" >> artifact/results/RUNLOG.md; echo "$(date '+%H:%M') $*"; }
waitfree() { for p in "$@"; do for _ in $(seq 1 60); do lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 5; done; done; }
AR=".claude/skills/p04-autorun/scripts/autorun.py"; P=artifact/plans/autorun
note "start (P3 v5: pilot 3 blocks, gate v5, final)"
waitfree 5660 8798 8799
python3 $AR $P/g3lte5-pilot.json || { note "P3 v5 pilot failed; stopped"; return 3; }
python3 - <<'PY' || { note "P3 v5 MECHANISM/BALANCE GATE FAIL; no P3 final (g3lte-card)"; return 5; }
import json, statistics, sys
sys.path.insert(0, 'artifact/followup'); from analyze_race import validity, fields; import analyze_g3race as g
d = 'artifact/results/round3/g3race/pilot-lte5'
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
stall, dd = [], {}
for r in rows:
    sc, rq = first(r, 'SOCKET_CONFIG'), first(r, 'WITHDRAW_REQUEST')
    if sc is None or rq is None or 'withdraw_host_offset_s' not in r: continue
    if r['withdraw_host_offset_s'] - r['u'] * r['D_s'] > 1.0: stall.append(r['trial']); continue
    dd.setdefault(r['mode'], []).append((rq - sc) / 1e9 - r['withdraw_host_offset_s'])
med = {m: round(statistics.median(v), 4) for m, v in sorted(dd.items())}; n = {m: len(v) for m, v in sorted(dd.items())}
spread = round(max(med.values()) - min(med.values()), 4) if len(med) == 5 and min(n.values()) >= 5 else None
print('trials', len(rows), 'invalid', bad, 'close bad', c_bad, 'close2 bad', c2_bad, 'marker_sent bad', mk_bad, 'marker log bad', ml_bad,
      'capture marker missing', cap_bad, 'request SYN missing', syn_bad, 'warm bad', warm_bad, 'qsnap bad', q_bad,
      'adb-stall trials (excluded from d)', stall, 'median d per arm (s)', med, 'n', n, 'spread', spread)
sys.exit(0 if len(rows) == 45 and not (bad or c_bad or c2_bad or mk_bad or ml_bad or cap_bad or syn_bad or warm_bad or q_bad)
         and len(close) == 9 and len(close2) == 9 and spread is not None and spread <= 0.015 else 1)
PY
note "P3 v5 gate passed; starting final-lte5"
waitfree 5660 8798 8799
python3 $AR $P/g3lte5-final.json --confirm g3lte5-final; rc=$?; note "P3 v5 final-lte5 autorun exit $rc"; return $rc
}
main "$@"; rc=$?; g=$(bash .claude/skills/p04-experiment/scripts/guard.sh 2>&1 | tail -1); echo "- $(date '+%Y-%m-%d %H:%M') g3-p3v5: done (exit $rc); final guard: $g" >> artifact/results/RUNLOG.md; exit $rc
