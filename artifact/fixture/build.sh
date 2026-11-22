#!/bin/bash
# Build one ResidueLab APK per enforcement variant (framework-only; javac17 + d8 + aapt2 + apksigner, no Gradle).
set -e
source "$(dirname "$0")/../env.sh"
BT=$ANDROID_HOME/build-tools/34.0.0; AJAR=$ANDROID_HOME/platforms/android-33/android.jar
D=$(cd "$(dirname "$0")" && pwd); cd "$D"
VARIANTS="${VARIANTS:-none cancel enqueue jobstart conv egress rd volatile taint noser}"
OUTDIR="${OUTDIR:-build/apk}"; MANIFEST="${MANIFEST:-AndroidManifest.xml}"
rm -rf build/classes build/dex && mkdir -p build/classes build/dex "$OUTDIR"
$JAVA_HOME/bin/javac -Xlint:none -d build/classes -classpath "$AJAR" $(find src src-cmp ../transport/src -name '*.java')
$BT/d8 --min-api 26 --lib "$AJAR" --output build/dex $(find build/classes -name '*.class')
[ -f build/k.jks ] || "$JAVA_HOME/bin/keytool" -genkeypair -keystore build/k.jks -alias k -storepass android -keypass android \
    -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=residuelab" >/dev/null 2>&1
for v in $VARIANTS; do
  W=build/w_$v; rm -rf $W; mkdir -p $W
  $BT/aapt2 link -o $W/base.apk -I "$AJAR" --manifest "$MANIFEST" --rename-manifest-package org.residuelab.$v
  cp $W/base.apk $W/unsigned.apk
  (cd build/dex && "$JAVA_HOME/bin/jar" uf ../../$W/unsigned.apk classes.dex)
  $BT/zipalign -f 4 $W/unsigned.apk $W/aligned.apk
  $BT/apksigner sign --ks build/k.jks --ks-pass pass:android --key-pass pass:android --out "$OUTDIR/rl-$v.apk" $W/aligned.apk
  rm -rf $W
done
(cd "$OUTDIR" && shasum -a 256 *.apk > SHA256SUMS)
echo BUILT $(ls "$OUTDIR"/*.apk | wc -l) APKs in $OUTDIR
