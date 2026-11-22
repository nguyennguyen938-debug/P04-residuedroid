#!/bin/bash
# P04 group 3 (g3app-card.md): the four G3c builds from a fresh copy of the clean F-Droid checkout (commit d515c534).
# Usage: build_g3.sh <clean airguard checkout> <work dir outside the repo>
#   -> artifact/realapp/airguard/build/g3/airguard-{stock,stockcancel,fenced,layered}.apk + SHA256SUMS
# Ports (sink airguard_sink.py): stockcancel 8793, layered 8795, stock 8796, fenced 8797.
set -euo pipefail
CLEAN=$1; WORK=$2; HERE=$(cd "$(dirname "$0")" && pwd); ART=$(cd "$HERE/../.." && pwd)
[ "$(git -C "$CLEAN" rev-parse --short=8 HEAD)" = "d515c534" ] || { echo "not the F-Droid commit"; exit 2; }
rm -rf "$WORK/airguard-g3"; mkdir -p "$WORK"; cp -R "$CLEAN" "$WORK/airguard-g3"; rm -rf "$WORK/airguard-g3/app/build"
bash "$HERE/apply.sh" "$WORK/airguard-g3"; bash "$HERE/apply_g3.sh" "$WORK/airguard-g3"
OUT=$HERE/build/g3; mkdir -p "$OUT"
port() { case $1 in stockcancel) echo 8793;; layered) echo 8795;; stock) echo 8796;; fenced) echo 8797;; esac; }
for v in stock stockcancel fenced layered; do
  bash "$ART/plans/b1/build_airguard.sh" "$WORK/airguard-g3" :app:assembleDebug -Presidue.variant=$v -Presidue.base=http://10.0.2.2:$(port $v)/ >/dev/null
  cp "$(ls "$WORK"/airguard-g3/app/build/outputs/apk/debug/*.apk | head -1)" "$OUT/airguard-$v.apk"
  rm -rf "$WORK"/airguard-g3/app/build/outputs/apk
done
(cd "$OUT" && shasum -a 256 airguard-*.apk > SHA256SUMS && cat SHA256SUMS)
