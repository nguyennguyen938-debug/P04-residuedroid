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
J21=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home   # AirGuard: Java 21 toolchain, and Hilt compiles with the Gradle JVM
[ -x "$J21/bin/java" ] || { echo "JDK 21 missing: brew install openjdk@21"; exit 3; }
export JAVA_HOME=$J21
nice -n 19 ./gradlew --no-daemon --max-workers=2 -Dorg.gradle.jvmargs=-Xmx2g -Porg.gradle.java.installations.paths="$J21" \
  -Porg.gradle.java.installations.auto-detect=false :app:assembleRelease > ../airguard-build.log 2>&1
rc=$?; echo "exit=$rc" >> ../airguard-build.log; tail -20 ../airguard-build.log; exit $rc
}
main "$@"; exit $?
