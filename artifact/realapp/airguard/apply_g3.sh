#!/bin/bash
# P04 group 3 (g3app-card.md): additions on top of apply.sh for the G3c builds (withdrawal during an upload). Applied to the
# clone only. Every G3c build (stock, stockcancel, fenced, layered) gets the same additions; only stockcancel installs the
# in-flight call registry. Build: ./gradlew :app:assembleDebug -Presidue.variant=stock|stockcancel|fenced|layered
#   -Presidue.base=http://10.0.2.2:<port>/
#  - stock donation end logged (G3.stock wraps api.donateData; the call itself is unchanged);
#  - stockcancel: Retrofit/OkHttp Call.cancel() on every in-flight call when the switch is turned off (R1's deployable option);
#  - withdraw hook: after the app's own path, WITHDRAW_DONE and the marker connection (trial id) for the packet capture;
#  - hook op mark: the same marker connection on demand (the harness's start marker).
# apply.sh is unchanged (B2/G2b builds unaffected).
set -euo pipefail
SRC=$1; HERE=$(cd "$(dirname "$0")" && pwd)
APP=$SRC/app/src/main; PKG=$APP/java/de/seemoo/at_tracking_detection
grep -q "RESIDUE_FENCED" "$SRC/app/build.gradle" || { echo "run apply.sh first"; exit 2; }
grep -q "RESIDUE_CANCEL" "$SRC/app/build.gradle" && { echo "already applied"; exit 0; }
cp "$HERE"/src-g3/de/seemoo/at_tracking_detection/residue/*.kt "$PKG/residue/"
python3 - "$SRC" <<'PY'
import sys
src = sys.argv[1]; app = src + '/app'; pkg = app + '/src/main/java/de/seemoo/at_tracking_detection'
def edit(path, pairs):
    s = open(path).read()
    for old, new, count in pairs:
        n = s.count(old); assert n == count, (path, old[:60], n); s = s.replace(old, new)
    open(path, 'w').write(s)
edit(app + '/build.gradle', [
    ('        buildConfigField "boolean", "RESIDUE_LAYERED", residueVariant == "layered" ? "true" : "false"\n',
     '        buildConfigField "boolean", "RESIDUE_LAYERED", residueVariant == "layered" ? "true" : "false"\n'
     '        buildConfigField "boolean", "RESIDUE_CANCEL", residueVariant == "stockcancel" ? "true" : "false"\n', 1)])
edit(pkg + '/statistics/SendStatisticsWorker.kt', [
    ('            } else if (!api.donateData(token = token, devices=devices).isSuccessful) {',
     '            } else if (!de.seemoo.at_tracking_detection.residue.G3.stock(applicationContext) { api.donateData(token = token, devices=devices) }.isSuccessful) {', 1)])
edit(pkg + '/hilt/ApiModule.kt', [
    ('        return builder.build()',
     '        if (BuildConfig.RESIDUE_CANCEL) builder.addInterceptor(de.seemoo.at_tracking_detection.residue.G3.InFlight)\n        return builder.build()', 1)])
edit(pkg + '/residue/TestHooks.kt', [
    ('app.backgroundWorkScheduler.removeShareData() }',
     'app.backgroundWorkScheduler.removeShareData(); G3.afterWithdraw(context, intent) }', 1),
    ('                    "run" -> {', '                    "mark" -> G3.mark(context, intent)\n                    "run" -> {', 1)])
print('patched (g3)')
PY
echo "g3 applied to $SRC"
