#!/bin/bash
# Test 6, Galaxy on Samsung RTL, unattended (user go-ahead 19/11: "tự động fix và chạy"). Fill mode: given the RTL session
# end (END=HH:MM), run as much of the remaining planned work as fits, in fresh directories galaxy-pNN, until done.
#   Planned work (test6-card.md §2): TLS blocks 0..19, lifecycle k 0..19 (pending, kill, revoke). Then replacements
#   (card §3): if fewer than 20 valid TLS blocks / valid paired trials per schedule exist, run new indices from 20 up
#   (cap 5 per cell). Validity is counted with followup/analyze_test6.py (harness/fault fields only, never outcomes).
#   An index that was in progress when a run stopped is not repeated; it is an environment failure, replaced as above.
# Relay: owns Samsung `rdb`, started with the r33 adb first on PATH and ANDROID_ADB_SERVER_PORT=5038, so rdb's own
#   `adb connect` attaches the device to this run's adb server. After a relay restart the RTL web page must attach the
#   device again; the script logs NEED_CLICK and waits up to 10 min.
# Usage: END=HH:MM rtl_auto.sh <scratch dir with rtl/pt33 and test6/pkg4>
# Test knobs (offline checks only): RDB_BIN, RESULTS, TOTAL_TLS, TOTAL_LIFE, RUN_RTL.
set -uo pipefail
main() {
SCR=$1; : "${END:?set END=HH:MM (RTL session end)}"
HERE=$(cd "$(dirname "$0")" && pwd); REPO=${REPO:-$(cd "$HERE/../../.." && pwd)}
[ -f "$REPO/artifact/followup/analyze_test6.py" ] || { echo "rtl_auto: STOP: repo not found at $REPO"; return 2; }
R=${RESULTS:-$REPO/artifact/results/round3/test6}; RUN_RTL=${RUN_RTL:-$HERE/run_rtl.sh}
RDB_BIN=${RDB_BIN:-$HOME/Downloads/rdb/rdb}; TOTAL_TLS=${TOTAL_TLS:-20}; TOTAL_LIFE=${TOTAL_LIFE:-20}
A=$SCR/rtl/pt33/platform-tools/adb; PKG=$SCR/test6/pkg4; RD=$SCR/rdbrun; mkdir -p "$RD"
export ANDROID_ADB_SERVER_PORT=5038
SCHED=pending,kill,revoke; TLS_S=40; TRIAL_S=95; FIX_S=150; MARGIN_S=300; CAP=5

note() { echo "$(date '+%Y-%m-%d %H:%M:%S') rtl_auto: $*" | tee -a "$RD/auto.log"; }
left_s() { echo $(( $(date -j -f "%H:%M" "$END" +%s) - $(date +%s) )); }
rdb_port() { grep -o 'listening on port: [0-9]*' "$RD/rdb.cur.log" 2>/dev/null | tail -1 | awk '{print $4}'; }
rdb_start() {
  pkill -f "$RDB_BIN" 2>/dev/null; sleep 2
  local log; log="$RD/rdb-$(date +%H%M%S).log"; ln -sf "$log" "$RD/rdb.cur.log"
  (cd "$RD" && PATH="$(dirname "$A"):$PATH" nohup "$RDB_BIN" > "$log" 2>&1 &)
  note "NEED_CLICK: relay restarted; the RTL web page must open Test -> Remote Debug Bridge again"
  for _ in $(seq 1 200); do
    grep -q "Connected device" "$log" 2>/dev/null && { sleep 5; note "relay up: $(tr '\n' ' ' < "$log")"; return 0; }
    sleep 3; done
  note "relay: device did not attach within 10 min"; return 1; }
link_ok() { local p; p=$(rdb_port); [ -n "$p" ] || return 1
  ( "$A" -s "localhost:$p" shell echo ok > "$RD/.probe" 2>&1 ) & local q=$!
  for _ in $(seq 1 10); do kill -0 $q 2>/dev/null || break; sleep 1; done; kill $q 2>/dev/null
  [ "$(tr -d '\r' < "$RD/.probe")" = ok ]; }

# what is still needed: "tls_start tls_n life_start life_n" for the next run, from recorded data (+ validity for replacements)
needed() {
  python3 - "$R" "$TOTAL_TLS" "$TOTAL_LIFE" "$CAP" "$REPO/artifact/followup" <<'EOF'
import glob, json, os, sys
r, nt, nl, cap, fol = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
sys.path.insert(0, fol)
dirs = [d for d in sorted(glob.glob(os.path.join(r, "galaxy-*"))) if "_INVALID_" not in d and os.path.isdir(d)]
jl = lambda p: [json.loads(l) for l in open(p) if l.strip()] if os.path.exists(p) else []
tls = [x for d in dirs for x in jl(os.path.join(d, "tls/trials.jsonl"))]
life = [x for d in dirs for x in jl(os.path.join(d, "life/schedule.jsonl"))]
maxb = max([x["block"] for x in tls], default=-1); maxk = max([x["k"] for x in life], default=-1)
# planned range first (continue after the last recorded index)
ts, tn = (maxb + 1, nt - maxb - 1) if maxb < nt - 1 else (0, 0)
ls, ln = (maxk + 1, nl - maxk - 1) if maxk < nl - 1 else (0, 0)
sched = "pending,kill,revoke"
if tn == 0 and ln == 0:      # planned range done: replacements for invalid indices (validity rules of the card)
    import analyze_test6 as A
    t = A.analyse_tls([os.path.join(d, "tls") for d in dirs], nt)
    need_t = max(0, nt - t["blocks_valid"])
    if need_t and maxb + 1 < nt + cap: ts, tn = maxb + 1, min(need_t, nt + cap - maxb - 1)
    inst = {f"G-{os.path.basename(d)[len('galaxy-'):]}": os.path.join(d, "life") for d in dirs if os.path.exists(os.path.join(d, "life/schedule.jsonl"))}
    if inst:
        import tempfile
        import contextlib
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(sys.stderr):   # oracle prints go to stderr
            L = A.analyse_life(inst, tmp, nl)
        valid = {s: L["analyzed_paired_trials"].get(f"G/{s}", 0) + sum(u["schedule"] == s for u in L["unused_valid"]) for s in ("pending", "kill", "revoke")}
        short = {s: nl - v for s, v in valid.items() if v < nl}          # replacement trials only for schedules short of N
        if short and maxk + 1 < nl + cap:
            ls, ln = maxk + 1, min(max(short.values()), nl + cap - maxk - 1); sched = ",".join(s for s in valid if s in short)
print(ts, tn, ls, ln, sched)
EOF
}

note "start (END $END, $(( $(left_s) / 60 )) min left)"
n=$(ls -d "$R"/galaxy-p[0-9][0-9]* 2>/dev/null | wc -l | tr -d ' '); fails=0
while :; do
  NEED=$(needed)
  [[ "$NEED" =~ ^[0-9]+\ [0-9]+\ [0-9]+\ [0-9]+\ [a-z,]+$ ]] || { note "STOP: could not compute what is left (got: $NEED)"; return 8; }
  if [ "$NEED" = "${PREV_NEED:-}" ]; then stuck=$(( ${stuck:-0} + 1 )); else stuck=0; fi; PREV_NEED=$NEED
  if [ "$stuck" -ge 3 ]; then note "STOP: 3 runs added no recorded index"; return 7; fi
  read -r ts tn ls_ ln_ SCHED <<< "$NEED"; NS=$(echo "$SCHED" | tr ',' '\n' | wc -l | tr -d ' ')
  [ "$tn" -eq 0 ] && [ "$ln_" -eq 0 ] && { note "DONE: nothing left to run (planned range and replacements)"; return 0; }
  budget=$(( $(left_s) - MARGIN_S - FIX_S ))
  # fit TLS first (blocks), then whole lifecycle k (3 trials each) into the remaining time
  ft=$(( budget / TLS_S )); [ "$ft" -gt "$tn" ] && ft=$tn; [ "$ft" -lt 0 ] && ft=0
  rest=$(( budget - ft * TLS_S )); fl=$(( rest / (NS * TRIAL_S) )); [ "$fl" -gt "$ln_" ] && fl=$ln_; [ "$fl" -lt 0 ] && fl=0
  [ "$tn" -gt 0 ] && [ "$ft" -lt "$tn" ] && fl=0          # finish TLS before starting lifecycle
  if [ "$ft" -eq 0 ] && [ "$fl" -eq 0 ]; then note "STOP: session too short for the next block (left $(( $(left_s) / 60 )) min); still needed tls $ts+$tn life $ls_+$ln_"; return 0; fi
  link_ok || { note "link not usable: restarting relay"; rdb_start || { note "STOP: relay restart failed"; return 6; }; }
  n=$(( n + 1 )); out=$(printf "%s/galaxy-p%02d" "$R" "$n"); while [ -e "$out" ]; do n=$(( n + 1 )); out=$(printf "%s/galaxy-p%02d" "$R" "$n"); done
  args=(); [ "$ft" -gt 0 ] && args+=(--tls-start "$ts" --tls-n "$ft"); [ "$fl" -gt 0 ] && args+=(--life-start "$ls_" --life-trials "$fl" --schedules "$SCHED")
  note "run $(basename "$out") port $(rdb_port) ${args[*]}"
  caffeinate -s -i bash "$RUN_RTL" --port "$(rdb_port)" --pkg "$PKG" --out "$out" --expect-model SM-M356B --expect-android 14 \
    --adb "$A" --end "$END" "${args[@]}" >> "$RD/auto.log" 2>&1
  rc=$?; note "$(basename "$out") exit $rc"
  case $rc in
    0) fails=0;;
    2) note "STOP: runner refused (exit 2)"; return 2;;
    *) fails=$(( fails + 1 )); [ "$fails" -ge 3 ] && { note "STOP: 3 failed runs in a row"; return 5; }
       rdb_start || { note "STOP: relay restart failed"; return 6; };;
  esac
done
}
main "$@"; exit $?
