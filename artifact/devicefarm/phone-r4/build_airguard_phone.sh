#!/bin/bash
# Own-phone round 4, priority 3: the three B2/G2b AirGuard test builds (stock, fenced, layered) for a phone. Same sources and
# hooks as the emulator builds; only the sink address differs (adb reverse, http://127.0.0.1:<port>/) and cleartext is
# also permitted for 127.0.0.1. Needs airguard-phone.patch applied (apply.sh reads CLEARTEXT_HOSTS).
# Usage: build_airguard_phone.sh <clean airguard checkout at d515c534> <work dir outside the repo>
#   -> artifact/realapp/airguard/build/phone/airguard-{stock,fenced,layered}.apk + SHA256SUMS
set -euo pipefail
CLEAN=$1; WORK=$2; HERE=$(cd "$(dirname "$0")" && pwd); ART=$(cd "$HERE/../.." && pwd); AG=$ART/realapp/airguard
grep -q CLEARTEXT_HOSTS "$AG/apply.sh" || { echo "apply devicefarm/phone-r4/airguard-phone.patch first"; exit 2; }
[ "$(git -C "$CLEAN" rev-parse --short=8 HEAD)" = "d515c534" ] || { echo "not the F-Droid commit"; exit 2; }
rm -rf "$WORK/airguard-phone"; mkdir -p "$WORK"; cp -R "$CLEAN" "$WORK/airguard-phone"; rm -rf "$WORK/airguard-phone/app/build"
CLEARTEXT_HOSTS="10.0.2.2 127.0.0.1" bash "$AG/apply.sh" "$WORK/airguard-phone"
OUT=$AG/build/phone; mkdir -p "$OUT"
port() { case $1 in layered) echo 8795;; stock) echo 8796;; fenced) echo 8797;; esac; }
for v in stock fenced layered; do
  bash "$ART/plans/b1/build_airguard.sh" "$WORK/airguard-phone" :app:assembleDebug -Presidue.variant=$v -Presidue.base=http://127.0.0.1:$(port $v)/ >/dev/null
  cp "$(ls "$WORK"/airguard-phone/app/build/outputs/apk/debug/*.apk | head -1)" "$OUT/airguard-$v.apk"
  rm -rf "$WORK"/airguard-phone/app/build/outputs/apk
done
(cd "$OUT" && shasum -a 256 airguard-*.apk > SHA256SUMS && cat SHA256SUMS)
