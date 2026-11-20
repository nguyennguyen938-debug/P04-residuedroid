#!/bin/bash
# Test 1 on the user's own phone: read-only readiness check (changes no setting; installs only the test APK to check run-as).
# Usage: preflight_phone.sh <adb serial>
set -uo pipefail
main() {
S=${1:?usage: preflight_phone.sh <adb serial>}
export ANDROID_HOME=${ANDROID_HOME:-$HOME/Library/Android/sdk}; ADB=$ANDROID_HOME/platform-tools/adb
ART=$(cd "$(dirname "$0")/../.." && pwd); APK=$ART/fixture/build/tls-apk/rl-tls.apk; PKG=org.residuelab.tls; fail=0
chk() { if eval "$2" >/dev/null 2>&1; then echo "OK   $1"; else echo "FAIL $1"; fail=1; fi; }
case $S in emulator-*) echo "FAIL $S is an emulator"; return 1;; esac
chk "device $S attached and authorised" "[ \"\$($ADB -s $S get-state)\" = device ]"
REL=$($ADB -s $S shell getprop ro.build.version.release | tr -d '\r'); SDK=$($ADB -s $S shell getprop ro.build.version.sdk | tr -d '\r')
echo "INFO Android $REL (SDK $SDK), model $($ADB -s $S shell getprop ro.product.model | tr -d '\r')"
[ "$SDK" = 35 ] && echo "OK   Android 15 (SDK 35)" || { echo "FAIL SDK $SDK is not 35 (Android 15)"; fail=1; }
chk "test APK is the B10 build (sha256 ca313b94…ef15)" "shasum -a 256 '$APK' | grep -q ^ca313b94fd89c9e3"
chk "test APK installs (adb install -r)" "$ADB -s $S install -r '$APK'"
chk "run-as works for $PKG (debuggable, no root needed)" "$ADB -s $S shell run-as $PKG id"
echo "INFO network: $($ADB -s $S shell 'dumpsys connectivity | grep -m1 -o "TRANSPORT_[A-Z]*"' | tr -d '\r') (WIFI or CELLULAR; keep it the same for the whole run)"
echo "INFO battery: $($ADB -s $S shell dumpsys battery | grep -m1 level | tr -d '\r ') ; stay-awake: $($ADB -s $S shell settings get global stay_on_while_plugged_in | tr -d '\r') (3 or 7 = on while charging)"
[ $fail = 0 ] && echo "PREFLIGHT OK" || echo "PREFLIGHT FAIL"
return $fail
}
main "$@"; exit $?
