#!/bin/bash
# ResidueLab on WorkManager 2.9.1 (Google Maven AARs, deps/SHA256SUMS), no Gradle: aapt2 (+library R classes), javac, d8.
set -euo pipefail
source "$(dirname "$0")/../env.sh"
BT=$ANDROID_HOME/build-tools/34.0.0; AJAR=$ANDROID_HOME/platforms/android-33/android.jar
D=$(cd "$(dirname "$0")" && pwd); cd "$D"; F=$D/../fixture
VARIANTS="${VARIANTS:-wmnone wmconv wmrd}"
rm -rf build && mkdir -p build/res build/apk build/libjars build/meta
CP=""; for j in deps/*.jar; do CP="$CP:$D/$j"; done
for x in deps/x/*; do cp $x/classes.jar build/libjars/$(basename $x).jar; CP="$CP:$D/build/libjars/$(basename $x).jar"; done
EXTRA=""; RZ=""
for x in deps/x/*; do
  if [ -d $x/res ] && [ -n "$(find $x/res -type f)" ]; then
    n=$(basename $x); $BT/aapt2 compile --dir $x/res -o build/res/$n.zip
    RZ="$RZ -R build/res/$n.zip"; pk=$(grep -o 'package="[^"]*"' $x/AndroidManifest.xml | head -1 | cut -d'"' -f2); EXTRA="$EXTRA:$pk"
  fi
done
EXTRA=${EXTRA#:}
# coroutines Main dispatcher service file
(cd build/meta && unzip -oq "$D/deps/kotlinx-coroutines-android-1.7.1.jar" 'META-INF/services/*' 2>/dev/null || true)
[ -f build/k.jks ] || "$JAVA_HOME/bin/keytool" -genkeypair -keystore build/k.jks -alias k -storepass android -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=residuelab-wm" >/dev/null 2>&1
FIRST=1
for v in $VARIANTS; do
  W=build/w_$v; mkdir -p $W/gen $W/classes $W/dex
  sed "s/@PKG@/org.residuelab.$v/g" AndroidManifest.tmpl.xml > $W/AndroidManifest.xml
  $BT/aapt2 link -o $W/base.apk -I "$AJAR" --manifest $W/AndroidManifest.xml $RZ --auto-add-overlay --java $W/gen --extra-packages $EXTRA --non-final-ids
  $JAVA_HOME/bin/javac -Xlint:none -d $W/classes -classpath "$AJAR$CP" $(find $F/src $F/src-work $D/../transport/src $W/gen -name '*.java')
  (cd $W/classes && "$JAVA_HOME/bin/jar" cf ../app.jar .)
  $BT/d8 --min-api 26 --lib "$AJAR" --output $W/dex $W/app.jar build/libjars/*.jar $(ls deps/*.jar) > $W/d8.log 2>&1 || { cat $W/d8.log; exit 1; }
  cp $W/base.apk $W/unsigned.apk
  (cd $W/dex && "$JAVA_HOME/bin/jar" uf ../unsigned.apk classes*.dex)
  (cd build/meta && [ -d META-INF ] && "$JAVA_HOME/bin/jar" uf ../../$W/unsigned.apk META-INF/services || true)
  $BT/zipalign -f 4 $W/unsigned.apk $W/aligned.apk
  $BT/apksigner sign --ks build/k.jks --ks-pass pass:android --key-pass pass:android --out build/apk/rl-$v.apk $W/aligned.apk
done
(cd build/apk && shasum -a 256 *.apk > SHA256SUMS); cat build/apk/SHA256SUMS
