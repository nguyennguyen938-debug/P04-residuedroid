#!/bin/bash
# AcraLab: real ACRA 5.14.2 AARs (Maven Central) + kotlin-stdlib 2.4.20, dexed without Gradle.
set -euo pipefail
source "$(dirname "$0")/../env.sh"
BT=$ANDROID_HOME/build-tools/34.0.0; AJAR=$ANDROID_HOME/platforms/android-33/android.jar
D=$(cd "$(dirname "$0")" && pwd); cd "$D"; X=deps/x
CP="$X/acra-core-5.14.2/classes.jar:$X/acra-http-5.14.2/classes.jar:$X/acra-advanced-scheduler-5.14.2/classes.jar:deps/kotlin-stdlib-2.4.20.jar"
rm -rf build && mkdir -p build/classes build/dex build/apk build/res
$JAVA_HOME/bin/javac -Xlint:none -d build/classes -classpath "$AJAR:$CP" $(find src ../transport/src -name '*.java')
(cd build/classes && "$JAVA_HOME/bin/jar" cf ../app.jar .)
$BT/d8 --min-api 26 --lib "$AJAR" --output build/dex build/app.jar ${CP//:/ }
[ -f debug.keystore ] || "$JAVA_HOME/bin/keytool" -genkeypair -keystore debug.keystore -alias k -storepass android -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=acralab" >/dev/null 2>&1
for v in acra acrafence; do
  W=build/w_$v; mkdir -p $W/META-INF/services
  sed "s/@PKG@/org.residuelab.$v/g" AndroidManifest.tmpl.xml > $W/AndroidManifest.xml
  $BT/aapt2 link -o $W/unsigned.apk -I "$AJAR" --manifest $W/AndroidManifest.xml
  (cd build/dex && "$JAVA_HOME/bin/jar" uf ../../$W/unsigned.apk classes*.dex)
  # ServiceLoader plugin registrations (ACRA loads collectors/senders/schedulers this way)
  for j in $X/acra-core-5.14.2/classes.jar $X/acra-advanced-scheduler-5.14.2/classes.jar $X/acra-http-5.14.2/classes.jar; do
    (cd $W && unzip -oq "$D/$j" 'META-INF/services/*' 2>/dev/null || true)
  done
  if [ $v = acrafence ]; then echo org.residuelab.acra.FencedSenderFactory > $W/META-INF/services/org.acra.sender.ReportSenderFactory; fi
  (cd $W && "$JAVA_HOME/bin/jar" uf unsigned.apk META-INF/services)
  $BT/zipalign -f 4 $W/unsigned.apk $W/aligned.apk
  $BT/apksigner sign --ks debug.keystore --ks-pass pass:android --key-pass pass:android --out build/apk/$v.apk $W/aligned.apk
done
(cd build/apk && shasum -a 256 *.apk > SHA256SUMS); cat build/apk/SHA256SUMS
