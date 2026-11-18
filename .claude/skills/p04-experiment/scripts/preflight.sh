#!/bin/bash
# Host readiness check for P04 runtime experiments. Read-only. Exit 0 only if every REQUIRED item passes.
set -u
ok=0; bad=0
pass(){ printf "  [ OK ] %s\n" "$1"; ok=$((ok+1)); }
fail(){ printf "  [FAIL] %s\n" "$1"; bad=$((bad+1)); }
warn(){ printf "  [WARN] %s\n" "$1"; }
echo "== toolchain"
J=${JAVA_HOME:-$(/usr/libexec/java_home -v 17 2>/dev/null)}
if [ -n "$J" ] && "$J/bin/java" -version 2>&1 | grep -q '"17'; then pass "JDK 17 at $J"; else fail "JDK 17 not found (export JAVA_HOME=<jdk-17>)"; fi
python3 -c 'import sys; sys.exit(0 if sys.version_info>=(3,11) else 1)' && pass "python3 $(python3 -V 2>&1)" || fail "python3 >= 3.11"
command -v pdflatex >/dev/null && pass "pdflatex" || warn "pdflatex missing (only needed for make all)"
echo "== Android SDK"
A=${ANDROID_HOME:-$HOME/Library/Android/sdk}
[ -d "$A" ] && pass "ANDROID_HOME=$A" || fail "ANDROID_HOME not set / $A missing"
[ -x "$A/platform-tools/adb" ] && pass "adb $("$A/platform-tools/adb" version | head -1 | awk '{print $5}')" || fail "platform-tools (adb)"
if [ -x "$A/emulator/emulator" ]; then
  v=$("$A/emulator/emulator" -version 2>/dev/null | head -1 | sed 's/.*version //'); pass "emulator $v"
  echo "$v" | grep -q '^37\.2\.13' || warn "emulator != 37.2.13 (historical); record version as a stratum"
else fail "emulator package"; fi
[ -d "$A/platforms/android-33" ] && pass "platforms;android-33" || fail "platforms;android-33"
[ -x "$A/build-tools/34.0.0/aapt2" ] && pass "build-tools;34.0.0" || fail "build-tools;34.0.0"
[ -d "${ANDROID_AVD_HOME:-}" ] && pass "ANDROID_AVD_HOME=$ANDROID_AVD_HOME" || fail "export ANDROID_AVD_HOME=$HOME/.android/avd (harness default points to a missing shared-android/avd)"
SI="$A/system-images/android-33/google_apis/arm64-v8a"
if [ -f "$SI/source.properties" ]; then
  rev=$(grep Pkg.Revision "$SI/source.properties" | cut -d= -f2); pass "system image android-33 google_apis arm64-v8a rev $rev"
  [ "$rev" = "17" ] || warn "image rev $rev != 17 (historical); new configuration stratum, disclose, never pool"
else fail "system-images;android-33;google_apis;arm64-v8a"; fi
for api in ${IMAGES:-}; do   # e.g. IMAGES="34 35" for B11 (Android 14, 15)
  d="$A/system-images/android-$api/google_apis/arm64-v8a"
  [ -f "$d/source.properties" ] && pass "system image android-$api arm64 rev $(grep Pkg.Revision "$d/source.properties" | cut -d= -f2)" || fail "system-images;android-$api;google_apis;arm64-v8a (needed for B11)"
done
echo "== AVDs"
for n in ${AVDS:-P04AvdA P04AvdB}; do [ -f "${ANDROID_AVD_HOME:-$HOME/.android/avd}/$n.avd/config.ini" ] && pass "AVD $n" || fail "AVD $n (run setup_avds.sh)"; done
echo "== host"
mem=$(( $(sysctl -n hw.memsize) / 1073741824 )); free_pages=$(vm_stat | awk '/Pages free/{gsub("\\.","",$3);print $3}')
inact=$(vm_stat | awk '/Pages inactive/{gsub("\\.","",$3);print $3}'); avail=$(( (free_pages+inact)*16384/1073741824 ))
[ "$avail" -ge 8 ] && pass "~${avail} GB available of ${mem} GB" || warn "only ~${avail} GB available; close apps before 2 emulators"
disk=$(df -g / | awk 'NR==2{print $4}'); [ "$disk" -ge 20 ] && pass "${disk} GB disk free" || fail "need >= 20 GB disk"
pmset -g batt | grep -q "AC Power" && pass "on AC power" || warn "on battery: connect AC before long runs"
PORTS=${PORTS:-5600 5602 8787 8788 8791}; for p in $PORTS; do lsof -i :$p >/dev/null 2>&1 && fail "port $p in use" ; done; pass "ports $PORTS free (unless listed)"
echo "== repo"
ROOT=$(cd "$(dirname "$0")/../../../.." && pwd)
(cd "$ROOT/artifact/revision" && python3 -m unittest -q test_oracle >/dev/null 2>&1) && pass "oracle unit tests" || fail "oracle unit tests"
echo "summary: $ok ok, $bad failed"; [ $bad -eq 0 ]
