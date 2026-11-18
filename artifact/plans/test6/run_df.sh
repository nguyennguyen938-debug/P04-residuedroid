#!/bin/bash
# Schedule one Device Farm run for Test 6 and download its artifacts. Needs the user's go-ahead (costs device minutes).
# Usage: run_df.sh <uploads.env> <run-name> <out-dir> [job-timeout-minutes, default 15]
# uploads.env (kept outside the repo; holds account-specific ARNs): APP=..., PKG=..., SPEC=..., POOL=..., PRJ file via PRJ=...
set -euo pipefail
ENV=$1; NAME=$2; OUT=$3; TMO=${4:-15}
export AWS_PROFILE=${AWS_PROFILE:-p04} AWS_REGION=us-west-2
source "$ENV"; : "${PRJ:?}" "${APP:?}" "${PKG:?}" "${SPEC:?}" "${POOL:?}"
[ ! -e "$OUT" ] || { echo "refusing: $OUT exists (fresh directory rule)"; exit 2; }
before=$(aws devicefarm get-account-settings --query 'accountSettings.trialMinutes.remaining' --output text)
RUN=$(aws devicefarm schedule-run --project-arn "$PRJ" --app-arn "$APP" --device-pool-arn "$POOL" --name "$NAME" \
  --test "type=APPIUM_PYTHON,testPackageArn=$PKG,testSpecArn=$SPEC" \
  --execution-configuration "jobTimeoutMinutes=$TMO,videoCapture=false" --query run.arn --output text)
echo "scheduled $NAME (timeout $TMO min); trial minutes before: $before"
while :; do
  read -r st res < <(aws devicefarm get-run --arn "$RUN" --query 'run.[status,result]' --output text)
  echo "$(date +%H:%M:%S) $st $res"; [ "$st" = COMPLETED ] && break; sleep 30
done
mkdir -p "$OUT"
aws devicefarm get-run --arn "$RUN" --query 'run.{status:status,result:result,counters:counters,deviceMinutes:deviceMinutes,created:created,stopped:stopped}' --output json > "$OUT/run.json"
for J in $(aws devicefarm list-jobs --arn "$RUN" --query 'jobs[].arn' --output text); do
  aws devicefarm get-job --arn "$J" --query 'job.{device:device.name,os:device.os,status:status,result:result,minutes:deviceMinutes}' --output json >> "$OUT/jobs.json"
  for T in FILE LOG; do
    aws devicefarm list-artifacts --arn "$J" --type $T --query 'artifacts[].[name,extension,url]' --output text | while IFS=$'\t' read -r n e u; do
      curl -sS -f -o "$OUT/$(echo "$n" | tr ' /' '__').$e" "$u" || echo "download failed: $n"; done
  done
done
after=$(aws devicefarm get-account-settings --query 'accountSettings.trialMinutes.remaining' --output text)
echo "trial minutes after: $after (used $(python3 -c "print(round($before-$after,1))"))" | tee "$OUT/minutes.txt"
