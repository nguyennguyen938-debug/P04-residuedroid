#!/bin/bash
# Own-phone round 4, priority 2: matched lifecycle with reboot and netloss on the user's phone (draft card:
# card-lifecycle-phone.md -> plans/lifecycle-phone-card.md). Needs phone-faults.patch applied (B reviews and applies it).
# The five matched variants of Test 6 in every paired trial; sink on the Mac through adb reverse (127.0.0.1:8787).
#   run_lifecycle_phone.sh pilot <serial>             one paired trial per schedule; mechanical gate (harness fields only)
#   run_lifecycle_phone.sh final <serial> <trials>    needs the committed card and a passing pilot; final; analysis
set -uo pipefail
main() {
CMD=${1:?}; S=${2:?}
cd "$(dirname "$0")/../.." || return 2            # artifact/
export ANDROID_HOME=${ANDROID_HOME:-$HOME/Library/Android/sdk}; export ADB=${ADB:-$ANDROID_HOME/platform-tools/adb}
grep -q -- '--phone-faults' followup/campaign.py || { echo "apply devicefarm/phone-r4/phone-faults.patch first"; return 2; }
D=results/round3/phone-r4/lifecycle; CARD=plans/lifecycle-phone-card.md; mkdir -p $D
CAMP=(python3 followup/campaign.py --serial "$S" --port 8787 --variants menqueue,mstart,mlayer,mfence,mboth --no-root
      --sink-host 127.0.0.1 --phone-faults --timeout 90 --apkdir fixture/build/revision-apk --schedules reboot,netloss
      --seed lifecycle-phone-20261125)
log() { echo "- $(date '+%Y-%m-%d %H:%M') phone-r4 lifecycle: $*" >> results/RUNLOG.md; echo "$*"; }
doze() { "$ADB" -s "$S" shell dumpsys deviceidle "$1" >/dev/null; }
case $CMD in
pilot)
  n=1; while [ -e $D/pilot-$n ]; do n=$((n+1)); done; OUT=$D/pilot-$n
  log "LAUNCH pilot $OUT (own phone, adb reverse sink, reboot+netloss)"; doze disable
  caffeinate -s -i "${CAMP[@]}" --trials 1 --out $OUT; rc=$?; doze enable; log "pilot $OUT exit $rc"
  python3 - "$OUT" <<'PY'
import json, sys
from pathlib import Path
d = Path(sys.argv[1]); rows = [json.loads(l) for l in open(d / 'schedule.jsonl') if l.strip()]
acts = lambda r: [a['a'] for a in r.get('actions', [])]
chk = {}
for r in rows:
    s = r['schedule']; t = [a['t'] for a in r.get('actions', [])]
    gap = max((b - a for a, b in zip(t, t[1:])), default=0)
    ok = 'trial_error' not in acts(r) and 'setup_fail' not in acts(r) and gap <= 200 and r.get('device_alive_end', True) is not False
    if s == 'reboot': ok &= 'boot_completed' in acts(r)
    if s == 'netloss': ok &= r.get('net_verified_down') is True
    chk[s] = {'ok': bool(ok), 'max_action_gap_s': round(gap, 1)}
gate = set(chk) == {'reboot', 'netloss'} and all(v['ok'] for v in chk.values())
print(chk, '| gate', 'PASS' if gate else 'FAIL')
(d / 'gate.json').write_text(json.dumps({'gate': gate, 'per_schedule': chk}, indent=1) + '\n')
PY
  log "pilot gate: $(tr -d '\n ' < $OUT/gate.json)";;
final)
  T=${3:?trials}; git ls-files --error-unmatch $CARD >/dev/null 2>&1 && git diff --quiet HEAD -- $CARD \
    || { echo "refusing: commit $CARD first"; return 3; }
  P=$(ls -d $D/pilot-* | sort -V | tail -1); python3 -c "import json,sys; sys.exit(0 if json.load(open('$P/gate.json'))['gate'] else 1)" \
    || { echo "refusing: last pilot $P did not pass the gate"; return 4; }
  F=$D/frozen-lifecycle-phone; [ -e $F ] || { mkdir -p $F; { git rev-parse HEAD; shasum -a 256 followup/campaign.py followup/analyze_test6.py followup/matched_oracle.py fixture/build/revision-apk/*.apk; } > $F/source-sha256.txt; }
  [ -e $D/final ] && { echo "refusing: $D/final exists"; return 5; }
  log "LAUNCH final $D/final ($T trials per schedule, frozen $F)"; doze disable
  caffeinate -s -i "${CAMP[@]}" --trials "$T" --out $D/final; rc=$?; doze enable; log "final exit $rc"
  python3 followup/analyze_test6.py --manifest devicefarm/phone-r4/manifest-lifecycle-phone.json --out $D/analysis --n "$T"
  log "analysis written to $D/analysis";;
*) echo "usage: run_lifecycle_phone.sh pilot|final <serial> [trials]"; return 2;;
esac
}
main "$@"; exit $?
