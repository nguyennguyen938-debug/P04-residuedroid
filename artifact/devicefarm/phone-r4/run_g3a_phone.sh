#!/bin/bash
# Own-phone round 4, priority 1: the G3a commit-point race on the user's phone (draft card: card-g3a-phone.md; B copies it
# to plans/g3a-phone-card.md, fills it and commits it before the final run). Receiver on EC2 exactly as Test 1 on the
# phone (followup/receiver_b.py, PROFILE_SET=b10v3, plans/test6/ec2/), the same five arms as G3a in shared blocks.
# No capture and no marker: a phone has no emulator -tcpdump; the primary (trials accepted after W) uses the app's log.
#   run_g3a_phone.sh pilot <ip> <serial>            calibration with the G3 build (3 fence sends per cell, no withdrawal)
#   run_g3a_phone.sh final <ip> <serial> <blocks>   needs the committed card and a passing pilot; freezes; final; analysis
# Never reads outcome fields (the gate and the N rule use calibration durations only).
set -uo pipefail
main() {
CMD=${1:?}; IP=${2:?}; S=${3:?}
cd "$(dirname "$0")/../.." || return 2            # artifact/
export ANDROID_HOME=${ANDROID_HOME:-$HOME/Library/Android/sdk}; export P04_TOKEN; P04_TOKEN=$(cat ~/.p04/ec2/token)
APK=fixture/build/g3-apk/rl-tls.apk
[ -f $APK ] || { echo "missing $APK: build the G3 TLS fixture (VARIANTS=tls) as for G3a (plans/g3race-card.md)"; return 2; }
D=results/round3/phone-r4/g3a; CERT=~/.p04/ec2/cert-$IP; CARD=plans/g3a-phone-card.md; mkdir -p $D
SUITE=(python3 followup/race_suite.py --serial "$S" --no-root --receiver "http://$IP:8800" --host "$IP" --certdir "$CERT"
       --apk $APK --g3 --warm-revision --sndbuf 16384 --seed g3a-phone-20261125)
log() { echo "- $(date '+%Y-%m-%d %H:%M') phone-r4 g3a: $*" >> results/RUNLOG.md; echo "$*"; }
doze() { "${ANDROID_HOME}/platform-tools/adb" -s "$S" shell dumpsys deviceidle "$1" >/dev/null; }
case $CMD in
pilot)
  n=1; while [ -e $D/pilot-calib-$n ]; do n=$((n+1)); done; OUT=$D/pilot-calib-$n
  log "LAUNCH pilot $OUT (own phone, receiver EC2 b10v3, G3 build)"; doze disable
  caffeinate -s -i "${SUITE[@]}" --calibrate 3 --out $OUT; rc=$?; doze enable; log "pilot $OUT exit $rc"; [ $rc = 0 ] || return $rc
  python3 - "$OUT" <<'PY'
import json, sys, statistics
from pathlib import Path
d = Path(sys.argv[1]); m = json.load(open(d / 'calibration.json'))['median_s']
e, u, l = m.get('edge:2097152'), m.get('umts:2097152'), m.get('lte:2097152')
gate = bool(e and u and l and e >= 3 * l and u >= 1.5 * l)                 # the link shaping separates the profiles
wall = {}
for x in (json.loads(s) for s in open(d / 'trials.jsonl') if s.strip()):
    wall.setdefault(f"{x['profile']}:{x['size']}", []).append(x['finished'] - x['start'])
block_upper_min = 5 * sum(statistics.median(v) for v in wall.values()) / 60  # 5 arms per cell; upper bound
blocks = min(10, int(300 // block_upper_min)) if block_upper_min else 0      # card §2: at most 5 h of phone time
print('2 MiB medians (s): edge', e, 'umts', u, 'lte', l, '| throttle gate', 'PASS' if gate else 'FAIL')
print(f'block upper bound {block_upper_min:.1f} min -> N rule: {blocks} blocks' + ('' if blocks >= 5 else ' (< 5: final not run)'))
(d / 'gate.json').write_text(json.dumps({'gate': gate, 'medians_2mib': [e, u, l], 'block_upper_min': block_upper_min, 'blocks': blocks}, indent=1) + '\n')
PY
  log "pilot gate: $(tr -d '\n ' < $OUT/gate.json)";;
final)
  B=${4:?blocks}; git ls-files --error-unmatch $CARD >/dev/null 2>&1 && git diff --quiet HEAD -- $CARD \
    || { echo "refusing: commit $CARD (N filled) first"; return 3; }
  P=$(ls -d $D/pilot-calib-* | sort -V | tail -1); python3 -c "import json,sys; sys.exit(0 if json.load(open('$P/gate.json'))['gate'] else 1)" \
    || { echo "refusing: last pilot $P did not pass the gate"; return 4; }
  F=$D/frozen-g3a-phone; [ -e $F ] || { mkdir -p $F; { git rev-parse HEAD; shasum -a 256 followup/race_suite.py followup/receiver_b.py followup/analyze_g3race.py $APK; } > $F/source-sha256.txt; }
  [ -e $D/final ] && { echo "refusing: $D/final exists (resume into final-r2 with --start, as G3a did)"; return 5; }
  log "LAUNCH final $D/final ($B blocks, durations $P/calibration.json, frozen $F)"; doze disable
  caffeinate -s -i "${SUITE[@]}" --modes early,close,close2,fence,fence-abort --trials "$B" --durations $P/calibration.json --out $D/final
  rc=$?; doze enable; log "final exit $rc"
  python3 followup/analyze_g3race.py $D/final --out $D/analysis --n $((3 * B)); log "analysis written to $D/analysis";;
*) echo "usage: run_g3a_phone.sh pilot|final <ip> <serial> [blocks]"; return 2;;
esac
}
main "$@"; exit $?
