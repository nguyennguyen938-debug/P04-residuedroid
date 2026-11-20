#!/bin/bash
# Test 1 on the user's own Android 15 phone (plans/test1-phone-card.md). Receiver on EC2 (receiver_b.py, PROFILE_SET=b10v3).
#   run_phone.sh pilot <ip> <serial>            calibration (3 sends per cell, no withdrawal) + throttle gate + N rule
#   run_phone.sh final <ip> <serial> <blocks>   needs the card committed; pins sources; final run; analysis
# Never reads outcome fields (the gate and the N rule use calibration durations only).
set -uo pipefail
main() {
CMD=${1:?}; IP=${2:?}; S=${3:?}
cd "$(dirname "$0")/../.." || return 2            # artifact/
export ANDROID_HOME=${ANDROID_HOME:-$HOME/Library/Android/sdk}; export P04_TOKEN; P04_TOKEN=$(cat ~/.p04/ec2/token)
D=results/round3/test1-phone; CERT=~/.p04/ec2/cert-$IP; mkdir -p $D
SUITE=(python3 followup/race_suite.py --serial "$S" --no-root --receiver "http://$IP:8800" --host "$IP" --certdir "$CERT")
log() { echo "- $(date '+%Y-%m-%d %H:%M') test1-phone: $*" >> results/RUNLOG.md; echo "$*"; }
case $CMD in
pilot)
  n=1; while [ -e $D/pilot-calib-$n ]; do n=$((n+1)); done; OUT=$D/pilot-calib-$n
  log "LAUNCH pilot $OUT (own phone, receiver EC2 b10v3)"
  caffeinate -s -i "${SUITE[@]}" --calibrate 3 --out $OUT; rc=$?; log "pilot $OUT exit $rc"; [ $rc = 0 ] || return $rc
  python3 - "$OUT" <<'PY'
import json, sys, statistics
from pathlib import Path
d = Path(sys.argv[1]); m = json.load(open(d / 'calibration.json'))['median_s']
e, u, l = m.get('edge:2097152'), m.get('umts:2097152'), m.get('lte:2097152')
gate = bool(e and u and l and e >= 3 * l and u >= 1.5 * l)
wall = {}
for x in (json.loads(s) for s in open(d / 'trials.jsonl') if s.strip()):
    wall.setdefault(f"{x['profile']}:{x['size']}", []).append(x['finished'] - x['start'])
block_upper_min = 2 * sum(statistics.median(v) for v in wall.values()) / 60      # 2 modes per cell; upper bound (early runs to the end)
blocks = min(10, int(180 // block_upper_min)) if block_upper_min else 0
print('2 MiB medians (s): edge', e, 'umts', u, 'lte', l, '| throttle gate', 'PASS' if gate else 'FAIL')
print(f'block upper bound {block_upper_min:.1f} min -> N rule (card §2): {blocks} blocks' + ('' if blocks >= 5 else ' (< 5: final not run)'))
(d / 'gate.json').write_text(json.dumps({'gate': gate, 'medians_2mib': [e, u, l], 'block_upper_min': block_upper_min, 'blocks': blocks}, indent=1) + '\n')
PY
  log "pilot gate: $(tr -d '\n ' < $OUT/gate.json)";;
final)
  B=${4:?blocks}; git ls-files --error-unmatch plans/test1-phone-card.md >/dev/null 2>&1 && git diff --quiet HEAD -- plans/test1-phone-card.md \
    || { echo "refusing: commit plans/test1-phone-card.md (N filled) first"; return 3; }
  P=$(ls -d $D/pilot-calib-* | sort -V | tail -1); python3 -c "import json,sys; sys.exit(0 if json.load(open('$P/gate.json'))['gate'] else 1)" \
    || { echo "refusing: last pilot $P did not pass the gate"; return 4; }
  F=$D/frozen-test1-phone; [ -e $F ] || { mkdir -p $F; { git rev-parse HEAD; shasum -a 256 followup/race_suite.py followup/receiver_b.py followup/analyze_race.py fixture/build/tls-apk/rl-tls.apk; } > $F/source-sha256.txt; }
  [ -e $D/final ] && { echo "refusing: $D/final exists"; return 5; }
  log "LAUNCH final $D/final ($B blocks, durations $P/calibration.json, frozen $F)"
  caffeinate -s -i "${SUITE[@]}" --trials "$B" --durations $P/calibration.json --out $D/final; rc=$?; log "final exit $rc"
  python3 followup/analyze_race.py $D/final --out $D/analysis --n $((3 * B)); log "analysis written to $D/analysis";;
*) echo "usage: run_phone.sh pilot|final <ip> <serial> [blocks]"; return 2;;
esac
}
main "$@"; exit $?
