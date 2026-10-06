#!/usr/bin/env bash
# Сборка APK Donatix без Android Studio. Нужны: JDK 17+, aapt2, android.jar (API 36), d8 или dx, apksigner.
#   AAPT2=/path/aapt2 ANDROID_JAR=/path/android.jar DX_JAR=/path/dx.jar ./build.sh
set -euo pipefail
cd "$(dirname "$0")"
rm -rf build && mkdir -p build/gen build/classes
"$AAPT2" compile --dir res -o build/res.zip
"$AAPT2" link -o build/base.apk -I "$ANDROID_JAR" --manifest AndroidManifest.xml -R build/res.zip \
  --java build/gen --auto-add-overlay --min-sdk-version 23 --target-sdk-version 36
javac --release 8 -cp "$ANDROID_JAR" -d build/classes -encoding UTF-8 src/tj/donatix/app/*.java build/gen/tj/donatix/app/R.java
java -cp "$DX_JAR" com.android.dx.command.Main --dex --min-sdk-version=23 --output=build/classes.dex build/classes
cp build/base.apk build/unaligned.apk && (cd build && zip -q unaligned.apk classes.dex)
zipalign -f -p 4 build/unaligned.apk build/donatix-unsigned.apk
echo "Готово: build/donatix-unsigned.apk — подпишите: apksigner sign --ks ваш.jks --out donatix.apk build/donatix-unsigned.apk"
