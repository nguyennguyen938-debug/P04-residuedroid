#!/bin/bash
# Create PLAN.md AVDs (default P04AvdA P04AvdB; role B: AVDS=P04AvdB) with the historical hardware profile (RUNLOG 2026-11-08 00:05: pixel_6, 2 GB RAM, 3 GB data,
# android-33 google_apis arm64-v8a). Idempotent: existing AVDs are left untouched. Does not start emulators.
set -euo pipefail
A=${ANDROID_HOME:?export ANDROID_HOME first}
AVDM="$A/cmdline-tools/latest/bin/avdmanager"
[ -x "$AVDM" ] || { echo "missing $AVDM (install cmdline-tools;latest)"; exit 1; }
API=${API:-33}; IMG="system-images;android-$API;google_apis;arm64-v8a"   # API=34/35 for B11
for n in ${AVDS:-P04AvdA P04AvdB}; do
  if [ -d "$HOME/.android/avd/$n.avd" ]; then echo "exists: $n"; continue; fi
  echo no | "$AVDM" create avd -n "$n" -k "$IMG" -d pixel_6 >/dev/null
  cfg="$HOME/.android/avd/$n.avd/config.ini"
  python3 - "$cfg" <<'EOF'
import sys, re
p = sys.argv[1]; s = open(p).read()
def put(k, v):
    global s
    s = re.sub(rf"^{re.escape(k)}=.*$", f"{k}={v}", s, flags=re.M) if re.search(rf"^{re.escape(k)}=", s, re.M) else s + f"\n{k}={v}"
put("hw.ramSize", "2048"); put("disk.dataPartition.size", "3G"); put("hw.keyboard", "yes")
open(p, "w").write(s.strip() + "\n")
EOF
  echo "created: $n ($(grep -E '^(hw.ramSize|disk.dataPartition.size)=' "$cfg" | tr '\n' ' '))"
done
rev=$(grep Pkg.Revision "$A/system-images/android-$API/google_apis/arm64-v8a/source.properties" | cut -d= -f2)
echo "image android-$API revision: $rev (historical android-33 rev 17). Record in RUNLOG."
echo "the harness launches its own AVD (harness/campaign.py ensure_device); role B = P04AvdB on console 5602"
