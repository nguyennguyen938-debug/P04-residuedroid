#!/bin/bash
# Own-phone round 4, priority 3: AirGuard lifecycle (stock, fenced, layered in every trial, as G2b) on the user's phone
# (draft card: card-airguard-phone.md -> plans/airguard-phone-card.md). Needs airguard-phone.patch applied and the phone
# builds from build_airguard_phone.sh. Sink on the Mac (airguard_sink.py) through adb reverse.
#   run_airguard_phone.sh pilot <serial>             one trial per schedule; mechanical gate (harness fields only)
#   run_airguard_phone.sh final <serial> <trials>    needs the committed card and a passing pilot; final; analysis
set -uo pipefail
main() {
CMD=${1:?}; S=${2:?}
cd "$(dirname "$0")/../.." || return 2            # artifact/
export ANDROID_HOME=${ANDROID_HOME:-$HOME/Library/Android/sdk}; export ADB=${ADB:-$ANDROID_HOME/platform-tools/adb}
grep -q -- "'--phone'" followup/campaign_airguard.py || { echo "apply devicefarm/phone-r4/airguard-phone.patch first"; return 2; }
APKS=realapp/airguard/build/phone; [ -f $APKS/airguard-fenced.apk ] || { echo "build the phone APKs: devicefarm/phone-r4/build_airguard_phone.sh"; return 2; }
D=results/round3/phone-r4/airguard; CARD=plans/airguard-phone-card.md; mkdir -p $D
RUN=(python3 followup/campaign_airguard.py --serial "$S" --apkdir $APKS --phone --variants stock,fenced,layered
     --schedules pending,kill,reboot,netloss --seed airguard-phone-20261125)
log() { echo "- $(date '+%Y-%m-%d %H:%M') phone-r4 airguard: $*" >> results/RUNLOG.md; echo "$*"; }
doze() { "$ADB" -s "$S" shell dumpsys deviceidle "$1" >/dev/null; }
case $CMD in
pilot)
  n=1; while [ -e $D/pilot-$n ]; do n=$((n+1)); done; OUT=$D/pilot-$n
  log "LAUNCH pilot $OUT (own phone, adb reverse sink)"; doze disable
  caffeinate -s -i "${RUN[@]}" --trials 1 --out $OUT; rc=$?; doze enable; log "pilot $OUT exit $rc"
  python3 devicefarm/phone-r4/gates.py airguard $OUT
  log "pilot gate: $(tr -d '\n ' < $OUT/gate.json)";;
final)
  T=${3:?trials}; git ls-files --error-unmatch $CARD >/dev/null 2>&1 && git diff --quiet HEAD -- $CARD \
    || { echo "refusing: commit $CARD first"; return 3; }
  P=$(ls -d $D/pilot-* | sort -V | tail -1); python3 -c "import json,sys; sys.exit(0 if json.load(open('$P/gate.json'))['gate'] else 1)" \
    || { echo "refusing: last pilot $P did not pass the gate"; return 4; }
  F=$D/frozen-airguard-phone; [ -e $F ] || { mkdir -p $F; { git rev-parse HEAD; shasum -a 256 followup/campaign_airguard.py followup/airguard_sink.py followup/analyze_airguard.py $APKS/*.apk; } > $F/source-sha256.txt; }
  [ -e $D/final ] && { echo "refusing: $D/final exists"; return 5; }
  log "LAUNCH final $D/final ($T trials per schedule, frozen $F)"; doze disable
  caffeinate -s -i "${RUN[@]}" --trials "$T" --out $D/final; rc=$?; doze enable; log "final exit $rc"
  python3 followup/analyze_airguard.py $D/final --out $D/analysis --n "$T"; log "analysis written to $D/analysis";;
*) echo "usage: run_airguard_phone.sh pilot|final <serial> [trials]"; return 2;;
esac
}
main "$@"; exit $?
