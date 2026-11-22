#!/bin/bash
# P04 B2: turn a clean AirGuard checkout (F-Droid commit d515c534) into the two test builds of b2-card.md.
# Applies to the clone only (never committed into the app's tree). Both variants get the same test hooks; they differ only
# in the donation send path (stock: Retrofit; fenced: ResidueDroid HttpTransport with chunk fence).
# Group 2 (21/11, g2layer-card.md): a third variant "layered" = the same HttpTransport path with one durable consent check
# under the lock before sending and no per-chunk check (layered early). Additive: stock and fenced builds are unchanged.
# Usage: apply.sh <airguard checkout> ; then build with
#   ./gradlew :app:assembleDebug -Presidue.variant=stock|fenced|layered -Presidue.base=http://10.0.2.2:<port>/
set -euo pipefail
# The app's network_security_config denies cleartext for every host, which overrides usesCleartextTraffic: the test sink
# (plain HTTP on the host, 10.0.2.2) would be unreachable for Retrofit (B2 pilot-1: no request reached the sink). Permit
# cleartext for 10.0.2.2 only, identically in both test builds.
nsc() {
  local f=$APP/res/xml/network_security_config.xml
  grep -q "10.0.2.2" "$f" && return 0
  python3 - "$f" <<'PY'
import sys
f = sys.argv[1]; s = open(f).read(); old = '</network-security-config>'
assert s.count(old) == 1, f
open(f, 'w').write(s.replace(old, '    <domain-config cleartextTrafficPermitted="true">\n        <domain includeSubdomains="false">10.0.2.2</domain>\n    </domain-config>\n' + old))
PY
  echo "network_security_config: cleartext permitted for 10.0.2.2"
}
main() {
SRC=$1; HERE=$(cd "$(dirname "$0")" && pwd); ART=$(cd "$HERE/../.." && pwd)
APP=$SRC/app/src/main; PKG=$APP/java/de/seemoo/at_tracking_detection
[ -f "$PKG/statistics/SendStatisticsWorker.kt" ] || { echo "not an AirGuard checkout"; exit 2; }
nsc   # idempotent; also brings clones patched before 19/11 22:30 up to date
grep -q "RESIDUE_FENCED" "$SRC/app/build.gradle" && { echo "already applied"; exit 0; }
mkdir -p "$APP/java/org/residuelab/transport" "$PKG/residue"
cp "$ART/transport/src/org/residuelab/transport/HttpTransport.java" "$ART/transport/src/org/residuelab/transport/Coordinator.java" "$APP/java/org/residuelab/transport/"
cp "$HERE"/src/de/seemoo/at_tracking_detection/residue/*.kt "$PKG/residue/"
python3 - "$SRC" <<'PY'
import sys, re
src = sys.argv[1]; app = src + '/app'; pkg = app + '/src/main/java/de/seemoo/at_tracking_detection'
def edit(path, pairs):
    s = open(path).read()
    for old, new, count in pairs:
        n = s.count(old); assert n == count, (path, old[:60], n); s = s.replace(old, new)
    open(path, 'w').write(s)
# worker: test builds keep the release behaviour (DEBUG early return off) and choose the send path by variant
edit(pkg + '/statistics/SendStatisticsWorker.kt', [
    ('BuildConfig.DEBUG', '(BuildConfig.DEBUG && !BuildConfig.RESIDUE_TEST)', 3),
    ('            if (!api.donateData(token = token, devices=devices).isSuccessful) {',
     '            de.seemoo.at_tracking_detection.residue.ResidueEvents.log(applicationContext, "WORKER_SEND", "variant=" + (if (BuildConfig.RESIDUE_FENCED) "fenced" else if (BuildConfig.RESIDUE_LAYERED) "layered" else "stock") + ";devices=" + devices.size)\n'
     '            if (BuildConfig.RESIDUE_FENCED || BuildConfig.RESIDUE_LAYERED) {\n'
     '                if (!de.seemoo.at_tracking_detection.residue.FencedDonation.send(applicationContext, devices)) return Result.retry()\n'
     '            } else if (!api.donateData(token = token, devices=devices).isSuccessful) {', 1)])
# build: variant, test flag, sink base address, side-by-side install
edit(app + '/build.gradle', [
    ('        buildConfigField "String", "API_BASE_ADDRESS", apiProperties["API_BASE_ADDRESS"]\n',
     '        def residueVariant = project.findProperty("residue.variant") ?: "none"\n'
     '        def residueBase = project.findProperty("residue.base")\n'
     '        buildConfigField "String", "API_BASE_ADDRESS", residueBase ? "\\"" + residueBase + "\\"" : apiProperties["API_BASE_ADDRESS"]\n'
     '        buildConfigField "boolean", "RESIDUE_TEST", residueVariant != "none" ? "true" : "false"\n'
     '        buildConfigField "boolean", "RESIDUE_FENCED", residueVariant == "fenced" ? "true" : "false"\n'
     '        buildConfigField "boolean", "RESIDUE_LAYERED", residueVariant == "layered" ? "true" : "false"\n'
     '        if (residueVariant != "none") { applicationIdSuffix ".p04" + residueVariant }\n', 1)])
# manifest: test receiver (exported for adb), cleartext to the local sink
edit(app + '/src/main/AndroidManifest.xml', [
    ('        <receiver\n            android:name=".worker.ScheduleWorkersReceiver"',
     '        <receiver android:name=".residue.TestHooks" android:exported="true">\n'
     '            <intent-filter><action android:name="p04.residue.HOOK" /></intent-filter>\n'
     '        </receiver>\n'
     '        <receiver\n            android:name=".worker.ScheduleWorkersReceiver"', 1),
    ('<application', '<application\n        android:usesCleartextTraffic="true"', 1)])
print('patched')
PY
echo "applied to $SRC"
}
main "$@"; exit $?
