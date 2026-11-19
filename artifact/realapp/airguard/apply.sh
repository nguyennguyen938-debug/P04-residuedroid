#!/bin/bash
# P04 B2: turn a clean AirGuard checkout (F-Droid commit d515c534) into the two test builds of b2-card.md.
# Applies to the clone only (never committed into the app's tree). Both variants get the same test hooks; they differ only
# in the donation send path (stock: Retrofit; fenced: ResidueDroid HttpTransport with chunk fence).
# Usage: apply.sh <airguard checkout> ; then build with
#   ./gradlew :app:assembleDebug -Presidue.variant=stock|fenced -Presidue.base=http://10.0.2.2:<port>/
set -euo pipefail
main() {
SRC=$1; HERE=$(cd "$(dirname "$0")" && pwd); ART=$(cd "$HERE/../.." && pwd)
APP=$SRC/app/src/main; PKG=$APP/java/de/seemoo/at_tracking_detection
[ -f "$PKG/statistics/SendStatisticsWorker.kt" ] || { echo "not an AirGuard checkout"; exit 2; }
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
     '            de.seemoo.at_tracking_detection.residue.ResidueEvents.log(applicationContext, "WORKER_SEND", "variant=" + (if (BuildConfig.RESIDUE_FENCED) "fenced" else "stock") + ";devices=" + devices.size)\n'
     '            if (BuildConfig.RESIDUE_FENCED) {\n'
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
