#!/bin/bash
set -euo pipefail
D=$(cd "$(dirname "$0")" && pwd);cd "$D"
source ../env.sh
BT=$ANDROID_HOME/build-tools/34.0.0;AJAR=$ANDROID_HOME/platforms/android-33/android.jar
CP="deps/classes.jar:deps/logcat.jar:deps/timber.jar:../acra/deps/kotlin-stdlib-2.4.20.jar"
mkdir -p build/classes build/dex
"$JAVA_HOME/bin/javac" -Xlint:none -d build/classes -classpath "$AJAR:$CP" $(find src ../transport/src -name '*.java')
"$JAVA_HOME/bin/d8" --help >/dev/null 2>&1 || true
"$BT/d8" --min-api 26 --lib "$AJAR" --output build/dex $(find build/classes -name '*.class') ${CP//:/ }
[ -f build/k.jks ] || "$JAVA_HOME/bin/keytool" -genkeypair -keystore build/k.jks -alias k -storepass android -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=matomolab' >/dev/null 2>&1
"$BT/aapt2" link -o build/unsigned.apk -I "$AJAR" --manifest AndroidManifest.xml
(cd build/dex && "$JAVA_HOME/bin/jar" uf ../unsigned.apk classes*.dex)
"$BT/zipalign" -f 4 build/unsigned.apk build/aligned.apk
"$BT/apksigner" sign --ks build/k.jks --ks-pass pass:android --key-pass pass:android --out build/matomo.apk build/aligned.apk
shasum -a 256 build/matomo.apk
