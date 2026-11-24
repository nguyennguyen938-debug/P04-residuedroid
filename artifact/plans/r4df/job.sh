#!/bin/bash
# One round-4 Device Farm job (plans/r4df-*-card.md): upload app + package + spec, run with run_df.sh (trial-minute guard),
# then, for pilots, C's gates.py and B's gate_b.py. ARNs and uploads.env stay outside the repo (~/.p04/r4df).
# Usage: job.sh <life|airguard|g3a> <job-name> <app.apk> <package.zip> <spec.yml> <timeout-min> <pilot|final> [gate schedules]
set -uo pipefail
cd "$(dirname "$0")/../../.." || exit 2
TASK=$1; JOB=$2; APK=$3; PKG=$4; SPEC=$5; TMO=$6; KIND=$7; GS=${8:-}
export AWS_PROFILE=p04 AWS_REGION=us-west-2
note() { echo "- $(date '+%Y-%m-%d %H:%M') r4df $TASK/$JOB: $*" >> artifact/results/RUNLOG.md; echo "$(date '+%H:%M') $*"; }
OUT=artifact/results/round3/phone-r4/aws/$TASK/$JOB; [ ! -e "$OUT" ] || { echo "refusing: $OUT exists"; exit 2; }
case $KIND in pilot) [[ $JOB == pilot-* ]] || { echo "pilot job names start with pilot-"; exit 2; };; final) ;; *) exit 2;; esac
PRJ=$(aws devicefarm list-projects --query "projects[?name=='P04-test6'].arn | [0]" --output text)
POOL=$(aws devicefarm list-device-pools --arn "$PRJ" --type PRIVATE --query "devicePools[?name=='pilot-pixel8a'].arn | [0]" --output text)
mkdir -p ~/.p04/r4df; ENV=~/.p04/r4df/uploads-$TASK-$JOB.env
note "upload (app $(basename "$APK"), package sha256 $(shasum -a 256 "$PKG" | cut -c1-12), spec $(basename "$SPEC"), timeout $TMO min)"
# 24/11: a curl PUT of the 59 MB AirGuard package stalled for 23 min (upload_df.sh has no timeout); watchdog + retries here
ok=0
for try in 1 2 3; do
  bash artifact/devicefarm/phone-r4/aws/upload_df.sh "$PRJ" "$POOL" "$APK" "$PKG" "$SPEC" > "$ENV" & up=$!
  for _ in $(seq 1 240); do kill -0 $up 2>/dev/null || break; sleep 5; done
  if kill -0 $up 2>/dev/null; then pkill -P $up 2>/dev/null; pkill -f "curl -sS -f -T $PKG" 2>/dev/null; kill $up 2>/dev/null; wait $up 2>/dev/null
    note "upload attempt $try stalled (> 20 min), killed"; continue; fi
  wait $up && { ok=1; break; }; note "upload attempt $try failed"
done
[ $ok = 1 ] || { note "upload FAILED after 3 attempts (no run scheduled)"; exit 3; }
note "scheduled on Device Farm (Pixel 8a pool)"
bash artifact/plans/test6/run_df.sh "$ENV" "r4df-$TASK-$JOB" "$OUT" "$TMO"; rc=$?
note "run_df exit $rc; $(cat "$OUT/minutes.txt" 2>/dev/null); run $(python3 -c "import json;r=json.load(open('$OUT/run.json'));print(r['status'],r['result'])" 2>/dev/null)"
[ $rc = 0 ] || exit 4
cp "$SPEC" "$OUT/testspec.yml"; shasum -a 256 "$PKG" "$APK" | sed 's#  .*/#  #' > "$OUT/inputs.sha256"
D=$(find "$OUT/unzipped" -maxdepth 7 -type d -name "$TASK" | head -1)
[ -n "$D" ] && [ -f "$D/schedule.jsonl" -o -f "$D/calibration.json" -o -f "$D/trials.jsonl" ] ||   # trials.jsonl: G3a finals { note "no $TASK results dir in the customer artifacts (environment failure)"; exit 5; }
echo "$D" > "$OUT/results_dir.txt"
if [ "$KIND" = pilot ]; then
  python3 artifact/devicefarm/phone-r4/gates.py "$TASK" "$D" ${GS:+--schedules "$GS"}; g1=$?
  g2=0; [ "$TASK" = g3a ] || { python3 artifact/plans/r4df/gate_b.py "$TASK" "$D"; g2=$?; }
  note "pilot gate: gates.py $([ $g1 = 0 ] && echo PASS || echo FAIL), gate_b $([ $g2 = 0 ] && echo PASS || echo FAIL)"
  [ $g1 = 0 ] && [ $g2 = 0 ] || exit 6
fi
note "done"
