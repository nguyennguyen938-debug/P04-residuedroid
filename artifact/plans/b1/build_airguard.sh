#!/bin/bash
# B1: test build of AirGuard (de.seemoo.at_tracking_detection) at the F-Droid build commit, as F-Droid does it
# (prebuild: drop applicationIdSuffix), unsigned release, low priority. Source clone lives outside the repository.
# Usage: build_airguard.sh <airguard source dir>   (log: <dir>/../airguard-build.log)
set -uo pipefail
main() {
SRC=$1; [ -f "$SRC/gradlew" ] && [ -f "$SRC/app/build.gradle" ] || { echo "not an AirGuard checkout: $SRC"; exit 2; }
cd "$SRC" || exit 2
echo "sdk.dir=$HOME/Library/Android/sdk" > local.properties
sed -i '' -e '/applicationIdSuffix/d' app/build.gradle
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
nice -n 19 ./gradlew --no-daemon --max-workers=2 -Dorg.gradle.jvmargs=-Xmx2g :app:assembleRelease > ../airguard-build.log 2>&1
rc=$?; echo "exit=$rc" >> ../airguard-build.log; tail -20 ../airguard-build.log; exit $rc
}
main "$@"; exit $?
