#!/bin/bash
# Test 6 on a Samsung Remote Test Lab (RTL) phone: run the Device Farm package from this Mac over Remote Debug Bridge.
# Same steps as testspec-*.yml (adb reverse 8798/8799/8787, TLS suite, lifecycle --no-root, reverse --remove-all), plus:
# preflight checks before anything is installed, a link probe that stops the harness if the RDB link dies, and a cleanup
# that always runs. Needs the user's go-ahead for each session (RTL credits). See plans/test6/README.md and test6-card.md.
#
# Usage: run_rtl.sh --port P --pkg PKGDIR --out FRESHDIR --expect-model M --expect-android V [--adb R33ADB] [--end HH:MM]
#                   [--tls-start K --tls-n N] [--life-start K --life-trials N --schedules pending,kill,revoke]
# TLS runs only if --tls-n is given, lifecycle only if --life-trials is given.
set -uo pipefail
main() {
PORT=; PKG=; OUT=; MODEL=; ANDROID=; END=; TLS_START=0; TLS_N=; LIFE_START=0; LIFE_N=; SCHED=pending,kill,revoke; TLS_DL=
ADB=${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}
while [ $# -gt 0 ]; do case $1 in
  --port) PORT=$2;; --pkg) PKG=$2;; --out) OUT=$2;; --expect-model) MODEL=$2;; --expect-android) ANDROID=$2;;
  --adb) ADB=$2;; --end) END=$2;; --tls-start) TLS_START=$2;; --tls-n) TLS_N=$2;;
  --life-start) LIFE_START=$2;; --life-trials) LIFE_N=$2;; --schedules) SCHED=$2;; --tls-deadline-ms) TLS_DL=$2;;
  *) echo "unknown argument $1"; exit 2;; esac; shift 2; done
: "${PORT:?--port}" "${PKG:?--pkg}" "${OUT:?--out}" "${MODEL:?--expect-model}" "${ANDROID:?--expect-android}"
[ -n "$TLS_N$LIFE_N" ] || { echo "nothing to run: give --tls-n and/or --life-trials"; exit 2; }
case $SCHED in *reboot*|*netloss*) echo "reboot/netloss need root: emulator only"; exit 2;; esac
[ -d "$(dirname "$OUT")" ] || { echo "parent of $OUT does not exist"; exit 2; }
OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"; PKG="$(cd "$PKG" 2>/dev/null && pwd)"   # absolute: the run cd's into PKG
[ ! -e "$OUT" ] || { echo "refusing: $OUT exists (fresh directory rule)"; exit 2; }
if lsof -nP -iTCP:8787 -iTCP:8798 -iTCP:8799 -sTCP:LISTEN >/dev/null 2>&1; then   # fixed harness ports: one run at a time
  echo "refusing: host ports 8787/8798/8799 already in use (another run is active)"; exit 2; fi
[ -f "$PKG/artifact/followup/tls_suite.py" ] && [ -f "$PKG/artifact/followup/tls-cert/test-key.pem" ] || { echo "not a package dir: $PKG"; exit 2; }
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
[ -f "$HERE/rdb_probe.py" ] || { echo "refusing: $HERE/rdb_probe.py missing (no link watchdog)"; exit 2; }
export ANDROID_ADB_SERVER_PORT=${ANDROID_ADB_SERVER_PORT:-5038}   # own adb server; never the default one on 5037
export ADB
S=localhost:$PORT
"$ADB" version | grep -q "Version 33\." || { echo "use platform-tools r33 adb (adb 37 hung on RDB); got: $("$ADB" version | sed -n 2p)"; exit 2; }

# estimated duration (pilot-rtl-3: TLS block 36 s, lifecycle trial 75-99 s; +fixed setup); refuse if the session would end first
EST=$(( 150 + ${TLS_N:-0} * 40 + ${LIFE_N:-0} * $(echo "$SCHED" | tr ',' '\n' | wc -l) * 95 ))
if [ -n "$END" ]; then
  LEFT=$(( $(date -j -f "%H:%M" "$END" +%s) - $(date +%s) ))
  [ $(( EST + 300 )) -le $LEFT ] || { echo "refusing: needs ~$((EST/60)) min + 5 min margin, session has $((LEFT/60)) min"; exit 2; }
fi
mkdir -p "$OUT"; LOG=$OUT/run.log
log() { echo "$(date +%H:%M:%S) $*" | tee -a "$LOG"; }
t() { local c=$1 lim=${2:-20}; ( "$ADB" -s "$S" shell "$c" > "$OUT/.t" 2>&1 ) & local p=$!
  for _ in $(seq 1 "$lim"); do kill -0 $p 2>/dev/null || break; sleep 1; done
  kill $p 2>/dev/null && { echo "TIMEOUT"; return 1; }; tr -d '\r' < "$OUT/.t"; }
to() { local lim=$1; shift; "$@" & local p=$!   # run an adb call with a time limit (a dead RDB link hangs it)
  for _ in $(seq 1 "$lim"); do kill -0 $p 2>/dev/null || { wait $p; return $?; }; sleep 1; done; kill $p 2>/dev/null; return 124; }
PROBE=; HPID=; WATCH=
cleanup() {
  trap - EXIT INT TERM
  [ -n "$HPID" ] && kill "$HPID" 2>/dev/null
  pkill -f "followup/(tls_suite|campaign).py --serial $S" 2>/dev/null
  for p in $(lsof -tnP -iTCP:8787 -iTCP:8798 -iTCP:8799 -sTCP:LISTEN 2>/dev/null); do
    ps -p "$p" -o command= | grep -q "$PKG\|$OUT" && kill "$p"; done      # only listeners this run started
  [ -n "$WATCH" ] && kill "$WATCH" 2>/dev/null; [ -n "$PROBE" ] && kill "$PROBE" 2>/dev/null
  to 15 "$ADB" -s "$S" reverse --remove-all >/dev/null 2>&1
  local pk left=unknown
  if [ "$(t 'echo ok' 10)" = ok ] && pk=$(t "pm list packages" 15); then
    for p in $(echo "$pk" | grep -o 'org\.residuelab\.[a-z0-9]*'); do to 30 "$ADB" -s "$S" uninstall "$p" >/dev/null 2>&1; done
    t "rm -f /data/local/tmp/p04-test-ca.pem" 10 >/dev/null
    pk=$(t "pm list packages" 15) && left=$(echo "$pk" | grep -c residuelab)
  fi
  log "CLEANUP org.residuelab.* left on device: $left (unknown = link down; remove at the next connection)"
  to 10 "$ADB" disconnect "$S" >/dev/null 2>&1; rm -f "$OUT/.t"
  python3 - "$OUT" <<'EOF'
import json, sys, time, os
p = os.path.join(sys.argv[1], "session.json"); d = json.load(open(p)) if os.path.exists(p) else {}
d["ended_host"] = time.time(); json.dump(d, open(p, "w"), indent=1)
EOF
}
trap cleanup EXIT INT TERM

# --- preflight (nothing installed yet)
log "PREFLIGHT $S adb $("$ADB" version | sed -n 2p) server port $ANDROID_ADB_SERVER_PORT"
# the RDB relay serves one adb client: if the default adb server (5037) grabbed it (the RDB tool connects it), release
# only this device there, with the adb that matches that server (a mismatched client would restart the server)
DEFAULT_ADB=${DEFAULT_ADB:-$HOME/Library/Android/sdk/platform-tools/adb}
if lsof -nP -iTCP:5037 -sTCP:LISTEN >/dev/null 2>&1 && ANDROID_ADB_SERVER_PORT=5037 "$DEFAULT_ADB" devices | grep -q "^$S"; then
  log "default adb server holds $S: restarting that server (same SDK adb) to release the relay"
  ANDROID_ADB_SERVER_PORT=5037 to 15 "$DEFAULT_ADB" kill-server >> "$LOG" 2>&1; sleep 1
  ANDROID_ADB_SERVER_PORT=5037 to 15 "$DEFAULT_ADB" start-server >> "$LOG" 2>&1; fi
if "$ADB" devices | grep -q "^$S[[:space:]]*device"; then log "$S already attached to this server"
else to 15 "$ADB" connect "$S" | tee -a "$LOG"; sleep 2; fi
[ "$(t 'echo ok' 10)" = ok ] || { log "ABORT: shell does not answer"; exit 3; }
M=$(t "getprop ro.product.model"); V=$(t "getprop ro.build.version.release"); FP=$(t "getprop ro.build.fingerprint")
U=$(t "id -u"); RA=$(t "which run-as")
log "device model=$M android=$V uid=$U run-as=$RA fingerprint=$FP"
[ "$M" = "$MODEL" ] && [ "$V" = "$ANDROID" ] || { log "ABORT: expected $MODEL / Android $ANDROID"; exit 3; }
[ "$U" = 2000 ] && [ -n "$RA" ] || { log "ABORT: need adbd as shell (uid 2000) and run-as"; exit 3; }
for p in $(t "pm list packages" 15 | grep -o 'org\.residuelab\.[a-z0-9]*'); do log "removing leftover $p"; to 30 "$ADB" -s "$S" uninstall "$p" >> "$LOG" 2>&1; done
for p in 8798 8799 8787; do to 15 "$ADB" -s "$S" reverse tcp:$p tcp:$p >/dev/null || { log "ABORT: adb reverse $p failed"; exit 3; }; done
[ "$(to 15 "$ADB" -s "$S" reverse --list | grep -c 'tcp:87')" = 3 ] || { log "ABORT: reverse list incomplete"; exit 3; }
python3 - "$OUT" "$PKG" "$REPO" "$S" "$M" "$V" "$FP" "$*" <<'EOF'
import hashlib, json, os, subprocess, sys, time
out, pkg, repo, serial, model, android, fp, argv = sys.argv[1:]
files = sorted(os.path.join(r, f) for r, _, fs in os.walk(os.path.join(pkg, "artifact")) for f in fs
               if f.endswith((".apk", ".py", ".pem")) and "__pycache__" not in r and not f.endswith("test-key.pem"))
sha = {os.path.relpath(f, pkg): hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files}
json.dump(sha, open(os.path.join(out, "package-sha256.json"), "w"), indent=1)
git = lambda *a: subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True).stdout.strip()
json.dump({"environment": "Samsung Remote Test Lab via Remote Debug Bridge", "receiver_mode": "Mac host via adb reverse over the RDB relay",
           "serial": serial, "model": model, "android": android, "fingerprint": fp, "started_host": time.time(),
           "repo_commit": git("rev-parse", "HEAD"), "repo_dirty": bool(git("status", "--porcelain", "--", "artifact/followup")),
           "package": pkg, "adb_server_port": os.environ.get("ANDROID_ADB_SERVER_PORT")}, open(os.path.join(out, "session.json"), "w"), indent=1)
EOF

# --- link probe + watchdog
python3 "$HERE/rdb_probe.py" "$ADB" "$S" "$OUT/rdb_probe.log" & PROBE=$!; disown $PROBE
watchdog() { while sleep 5; do grep -q LINK_DOWN "$OUT/rdb_probe.log" 2>/dev/null && { log "WATCHDOG: RDB link down, stopping harness"
  touch "$OUT/LINK_DOWN"; [ -n "$(cat "$OUT/.hpid" 2>/dev/null)" ] && kill "$(cat "$OUT/.hpid")" 2>/dev/null
  pkill -f "followup/(tls_suite|campaign).py --serial $S"; return; }; done; }
watchdog & WATCH=$!; disown $WATCH
cd "$PKG" || exit 3
run() { "$@" >> "$LOG" 2>&1 & HPID=$!; echo $HPID > "$OUT/.hpid"; wait $HPID; local rc=$?; HPID=; rm -f "$OUT/.hpid"; return $rc; }
TLS_RC=skipped; LIFE_RC=skipped
if [ -n "$TLS_N" ] && [ ! -e "$OUT/LINK_DOWN" ]; then
  log "TLS start (blocks $TLS_START..$((TLS_START+TLS_N-1)))"
  run python3 artifact/followup/tls_suite.py --serial "$S" --no-root --host 127.0.0.1 --start "$TLS_START" --n "$TLS_N" \
    --cases control,early,buffered-fence,buffered-early,stall-small,stall-large,concurrent ${TLS_DL:+--deadline-ms "$TLS_DL"} --out "$OUT/tls"; TLS_RC=$?
  log "TLS_EXIT=$TLS_RC"
fi
if [ -n "$LIFE_N" ] && [ ! -e "$OUT/LINK_DOWN" ]; then
  log "LIFE start (k $LIFE_START..$((LIFE_START+LIFE_N-1)), $SCHED)"
  run python3 artifact/followup/campaign.py --serial "$S" --no-root --sink-host 127.0.0.1 --port 8787 \
    --variants menqueue,mstart,mlayer,mfence,mboth --apkdir fixture/build/revision-apk --timeout 90 \
    --schedules "$SCHED" --start "$LIFE_START" --trials "$LIFE_N" --seed test6-20261119 --out "$OUT/life"; LIFE_RC=$?
  log "LIFE_EXIT=$LIFE_RC"
fi
python3 - "$OUT" "$TLS_RC" "$LIFE_RC" <<'EOF'
import json, os, sys
out, tls, life = sys.argv[1:]; p = os.path.join(out, "session.json"); d = json.load(open(p))
d.update(tls_exit=tls, life_exit=life, link_down=os.path.exists(os.path.join(out, "LINK_DOWN"))); json.dump(d, open(p, "w"), indent=1)
EOF
log "DONE (cleanup follows)"
[ -e "$OUT/LINK_DOWN" ] && exit 4   # environment failure: affected trials are replaced per the card
exit 0
}
main "$@"; exit $?
