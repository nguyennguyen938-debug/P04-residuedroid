#!/bin/bash
# B1: test build of AirGuard (de.seemoo.at_tracking_detection) at the F-Droid build commit, as F-Droid does it
# (prebuild: drop applicationIdSuffix), unsigned release, low priority. Source clone lives outside the repository.
# Usage: build_airguard.sh <airguard source dir> [gradle task] [-Pkey=value ...]   (default task :app:assembleRelease)
#   B2 test builds (after artifact/realapp/airguard/apply.sh): task :app:assembleDebug -Presidue.variant=stock|fenced -Presidue.base=URL
#   log: <dir>/../<dir name>-build.log
set -uo pipefail
main() {
SRC=$1; TASK=${2:-:app:assembleRelease}; shift; [ $# -gt 0 ] && shift; EXTRA=("$@"); [ -f "$SRC/gradlew" ] && [ -f "$SRC/app/build.gradle" ] || { echo "not an AirGuard checkout: $SRC"; exit 2; }
cd "$SRC" || exit 2
echo "sdk.dir=$HOME/Library/Android/sdk" > local.properties
sed -i '' -e '/applicationIdSuffix/{/p04/!d;}' app/build.gradle   # F-Droid prebuild; keeps the B2 test suffix
J21=/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home   # AirGuard: Java 21 toolchain, and Hilt compiles with the Gradle JVM
[ -x "$J21/bin/java" ] || { echo "JDK 21 missing: brew install openjdk@21"; exit 3; }
export JAVA_HOME=$J21
nice -n 19 ./gradlew --no-daemon --max-workers=2 -Dorg.gradle.jvmargs=-Xmx2g -Porg.gradle.java.installations.paths="$J21" \
  -Porg.gradle.java.installations.auto-detect=false "${EXTRA[@]}" "$TASK" > "../$(basename "$SRC")-build.log" 2>&1
rc=$?; L="../$(basename "$SRC")-build.log"; echo "exit=$rc" >> "$L"; tail -20 "$L"; exit $rc
}
main "$@"; exit $?
