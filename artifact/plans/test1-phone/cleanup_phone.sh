#!/bin/bash
# Remove everything the test put on the user's phone: the test app (with its files) and the pushed CA file.
# Usage: cleanup_phone.sh <adb serial>
set -uo pipefail
main() {
S=${1:?usage: cleanup_phone.sh <adb serial>}; ADB=${ANDROID_HOME:-$HOME/Library/Android/sdk}/platform-tools/adb
$ADB -s "$S" uninstall org.residuelab.tls; $ADB -s "$S" shell rm -f /data/local/tmp/p04-test-ca.pem
$ADB -s "$S" shell pm list packages org.residuelab | grep -q . && echo "WARN residuelab package still installed" || echo "phone clean"
}
main "$@"; exit $?
