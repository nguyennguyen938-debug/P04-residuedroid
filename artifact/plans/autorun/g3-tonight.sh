#!/bin/bash
# 22/11 night launcher (user: charger plugged in, phone attached, everything in parallel). Operational only, never reads trial data.
#  1. power: refuses on battery unless ALLOW_BATTERY=1 (the battery guard then stops at 15 %);
#  2. phone: exactly one non-emulator adb device -> G3d runs; none -> emulator chain only (logged);
#  3. G3d receiver certificate: the app checks the hostname, so the self-signed test certificate must carry the Mac's current
#     LAN address (it moved on 22/11: 192.168.1.20 -> another address). If it does not, the old one is kept under
#     ~/.p04/g3dcert-<time> and a new 30-day one is generated (key never committed; its sha256 goes to meta.json as ca_sha256);
#  4. starts plans/autorun/g3-chain-v4.sh (G3c v4, then P3) and, with a phone, plans/autorun/g3d-chain.sh, each under caffeinate
#     with its own battery guard; logs under artifact/results/round3/g3/ (fresh names).
# Usage: bash artifact/plans/autorun/g3-tonight.sh   (from anywhere; returns when both chains end)
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 2
export ANDROID_HOME=$HOME/Library/Android/sdk ANDROID_SDK_ROOT=$HOME/Library/Android/sdk ANDROID_AVD_HOME=$HOME/.android/avd
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
ADB=$ANDROID_HOME/platform-tools/adb; L=artifact/results/round3/g3; TS=$(date +%Y%m%d-%H%M)
note() { echo "- $(date '+%Y-%m-%d %H:%M') g3-tonight: $*" >> artifact/results/RUNLOG.md; echo "$(date '+%H:%M') $*"; }
if ! pmset -g batt | grep -q "AC Power"; then
  [ "${ALLOW_BATTERY:-0}" = 1 ] || { echo "refusing: not on AC power (plug in the charger, or ALLOW_BATTERY=1)"; exit 2; }
fi
NPH=$($ADB devices | awk 'NR > 1 && $2 == "device" && $1 !~ /^emulator-/' | wc -l | tr -d ' ')
IP=$(ipconfig getifaddr en0 || ipconfig getifaddr en1 || true)
PHONE=0
if [ "$NPH" = 1 ] && [ -n "$IP" ]; then
  PHONE=1; C=$HOME/.p04/g3dcert
  if ! openssl x509 -in "$C/test-ca.pem" -noout -ext subjectAltName 2>/dev/null | grep -q "IP Address:$IP\$"; then
    [ -d "$C" ] && mv "$C" "$HOME/.p04/g3dcert-$TS"
    mkdir -m 700 "$C"
    openssl req -x509 -newkey rsa:2048 -nodes -days 30 -keyout "$C/test-key.pem" -out "$C/test-ca.pem" \
      -subj "/CN=$IP" -addext "subjectAltName=IP:$IP" >/dev/null 2>&1 || { echo "certificate generation failed"; exit 3; }
    chmod 600 "$C/test-key.pem"
    note "G3d receiver test certificate regenerated for the current LAN address (old kept aside); ca sha256 $(shasum -a 256 "$C/test-ca.pem" | cut -c1-16)…"
  fi
else
  note "no single attached phone (found $NPH) or no LAN address: G3d not started; emulator chain only"
fi
note "start: emulator chain g3-chain-v4.sh$([ $PHONE = 1 ] && echo ' + phone chain g3d-chain.sh in parallel') (AC: $(pmset -g batt | grep -q 'AC Power' && echo yes || echo no))"
[ -e "$L/chain-v4-$TS.log" ] && { echo "log exists"; exit 2; }
caffeinate -i -s bash artifact/plans/autorun/g3-chain-v4.sh > "$L/chain-v4-$TS.log" 2>&1 & E=$!
sleep 2; EC=$(pgrep -P $E bash | head -1); bash artifact/plans/autorun/battery_guard.sh "${EC:-$E}" 15 & GE=$!
if [ $PHONE = 1 ]; then
  caffeinate -i -s bash artifact/plans/autorun/g3d-chain.sh > "$L/g3d-chain-$TS.log" 2>&1 & D=$!
  sleep 2; DC=$(pgrep -P $D bash | head -1); bash artifact/plans/autorun/battery_guard.sh "${DC:-$D}" 15 & GD=$!
  wait $D; note "phone chain exited ($?)"
fi
wait $E; note "emulator chain exited ($?)"
wait 2>/dev/null; note "all chains ended"
