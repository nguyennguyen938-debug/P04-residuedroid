#!/bin/bash
# Test 6, Galaxy on Samsung RTL, unattended (user go-ahead 19/11: "tự động fix và chạy"): runs the planned parts of
# test6-card.md one after another with run_rtl.sh, and owns the Samsung `rdb` relay so it can restart it when the link dies.
#   rdb is started with the r33 adb first on PATH and ANDROID_ADB_SERVER_PORT=5038, so its own `adb connect` attaches the
#   device to this run's adb server (rdb refuses to start without adb on PATH; with the SDK adb it grabbed 5037).
# Parts: s1 = TLS blocks 0-19 + lifecycle k 0-4; s2/s3/s4 = lifecycle k 5-9 / 10-14 / 15-19.
# If a part stops early (link down, exit 3/4), the relay is restarted and the part continues in a new directory
# (<part>b, <part>c, ...) from the first block / k after the last one recorded. A TLS block or a lifecycle k that was in
# progress is not repeated here: it is an environment failure, replaced later at index >= 20 (card §3). Never reads outcomes.
# Usage: rtl_auto.sh <scratch dir with rtl/pt33 and test6/pkg4> [parts, default "s1 s2 s3 s4"]
set -uo pipefail
SCR=$1; PARTS=${2:-"s1 s2 s3 s4"}
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd); R=$REPO/artifact/results/round3/test6
A=$SCR/rtl/pt33/platform-tools/adb; PKG=$SCR/test6/pkg4; RD=$SCR/rdbrun; mkdir -p "$RD"
export ANDROID_ADB_SERVER_PORT=5038
note() { echo "$(date '+%Y-%m-%d %H:%M:%S') rtl_auto: $*" | tee -a "$RD/auto.log"; }

rdb_port() { grep -o 'listening on port: [0-9]*' "$RD/rdb.cur.log" 2>/dev/null | tail -1 | awk '{print $4}'; }
rdb_start() {   # (re)start the relay and wait until the RTL web client has attached the device (max 10 min)
  pkill -f "Downloads/rdb/rdb" 2>/dev/null; sleep 2
  local log="$RD/rdb-$(date +%H%M%S).log"; ln -sf "$log" "$RD/rdb.cur.log"
  (cd "$RD" && PATH="$(dirname "$A"):$PATH" nohup "$HOME/Downloads/rdb/rdb" > "$log" 2>&1 &)
  for _ in $(seq 1 200); do
    grep -q "Connected device" "$log" 2>/dev/null && { sleep 5; note "relay up: $(tr '\n' ' ' < "$log")"; return 0; }
    sleep 3; done
  note "relay: device did not attach within 10 min: $(tr '\n' ' ' < "$log")"; return 1; }
link_ok() { local p; p=$(rdb_port); [ -n "$p" ] || return 1
  ( "$A" -s "localhost:$p" shell echo ok > "$RD/.probe" 2>&1 ) & local q=$!
  for _ in $(seq 1 10); do kill -0 $q 2>/dev/null || break; sleep 1; done; kill $q 2>/dev/null
  [ "$(tr -d '\r' < "$RD/.probe")" = ok ]; }

# planned range of each part
declare -A TLS0 TLSN LIFE0 LIFEN
TLS0[s1]=0; TLSN[s1]=20; LIFE0[s1]=0; LIFEN[s1]=5
for p in s2 s3 s4; do TLS0[$p]=0; TLSN[$p]=0; done
LIFE0[s2]=5; LIFE0[s3]=10; LIFE0[s4]=15; LIFEN[s2]=5; LIFEN[s3]=5; LIFEN[s4]=5

recorded() {   # last recorded TLS block / lifecycle k across all directories of a part ($1 part, $2 tls|life)
  python3 - "$R" "$1" "$2" <<'EOF'
import glob, json, os, sys
r, part, kind = sys.argv[1:]
best = -1
for d in sorted(glob.glob(os.path.join(r, f"galaxy-{part}*"))):
    if "_INVALID_" in d: continue
    f = os.path.join(d, "tls/trials.jsonl" if kind == "tls" else "life/schedule.jsonl")
    if os.path.exists(f):
        for l in open(f):
            if l.strip():
                x = json.loads(l); best = max(best, x["block"] if kind == "tls" else x["k"])
print(best)
EOF
}

for part in $PARTS; do
  for attempt in 1 2 3 4; do
    lt=$(recorded "$part" tls); ll=$(recorded "$part" life)
    ts=${TLS0[$part]}; tn=${TLSN[$part]}; ls_=${LIFE0[$part]}; ln_=${LIFEN[$part]}
    # continue after the last recorded index (an index in progress when a part stopped is skipped: env failure)
    if [ "$tn" -gt 0 ] && [ "$lt" -ge "$ts" ]; then tn=$(( ts + tn - lt - 1 )); ts=$(( lt + 1 )); fi
    if [ "$ll" -ge "$ls_" ]; then ln_=$(( ls_ + ln_ - ll - 1 )); ls_=$(( ll + 1 )); fi
    [ "$tn" -lt 0 ] && tn=0; [ "$ln_" -lt 0 ] && ln_=0
    if [ "$tn" -eq 0 ] && [ "$ln_" -eq 0 ]; then note "$part complete"; break; fi
    [ "$attempt" -eq 4 ] && { note "$part: giving up after 3 relay restarts"; exit 5; }
    link_ok || { note "link not usable: restarting relay"; rdb_start || { note "relay restart failed"; exit 6; }; }
    port=$(rdb_port); sfx=""; [ "$attempt" -gt 1 ] && sfx=$(printf "\\x$(printf %x $((96 + attempt)))")   # b, c, d
    out="$R/galaxy-$part$sfx"; while [ -e "$out" ]; do out="${out}x"; done
    args=(); [ "$tn" -gt 0 ] && args+=(--tls-start "$ts" --tls-n "$tn"); [ "$ln_" -gt 0 ] && args+=(--life-start "$ls_" --life-trials "$ln_")
    note "$part attempt $attempt → $(basename "$out") port $port ${args[*]}"
    caffeinate -s -i bash "$HERE/run_rtl.sh" --port "$port" --pkg "$PKG" --out "$out" --expect-model SM-M356B \
      --expect-android 14 --adb "$A" "${args[@]}" >> "$RD/auto.log" 2>&1
    rc=$?; note "$part attempt $attempt exit $rc"
    [ "$rc" -eq 0 ] && continue          # loop re-checks what is recorded; normally the part is complete now
    [ "$rc" -eq 2 ] && { note "$part: runner refused (exit 2), stopping"; exit 2; }
    rdb_start || { note "relay restart failed"; exit 6; }
  done
done
note "all parts done: $PARTS"
