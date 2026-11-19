#!/bin/bash
# Download the artifacts of an already finished Device Farm run, found by its name (same output as run_df.sh after the
# poll loop). Used when the poller died before downloading (RUNLOG 2026-11-19 10:46). No device minutes are used.
# Usage: fetch_df.sh <uploads.env> <run-name> <fresh out dir>
set -euo pipefail
ENV=$1; NAME=$2; OUT=$3
export AWS_PROFILE=${AWS_PROFILE:-p04} AWS_REGION=us-west-2
source "$ENV"; : "${PRJ:?}"
[ ! -e "$OUT" ] || { echo "refusing: $OUT exists (fresh directory rule)"; exit 2; }
RUN=$(aws devicefarm list-runs --arn "$PRJ" --query "runs[?name=='$NAME'] | [0].arn" --output text)
case $RUN in arn:aws:devicefarm:*) ;; *) echo "no run named $NAME"; exit 3;; esac
st=$(aws devicefarm get-run --arn "$RUN" --query 'run.status' --output text); [ "$st" = COMPLETED ] || { echo "run $NAME is $st"; exit 4; }
mkdir -p "$OUT"
aws devicefarm get-run --arn "$RUN" --query 'run.{status:status,result:result,counters:counters,deviceMinutes:deviceMinutes,created:created,stopped:stopped}' --output json > "$OUT/run.json"
for J in $(aws devicefarm list-jobs --arn "$RUN" --query 'jobs[].arn' --output text); do
  aws devicefarm get-job --arn "$J" --query 'job.{device:device.name,os:device.os,status:status,result:result,minutes:deviceMinutes}' --output json >> "$OUT/jobs.json"
  for T in FILE LOG; do
    aws devicefarm list-artifacts --arn "$J" --type $T --query 'artifacts[].[name,extension,url]' --output text | while IFS=$'\t' read -r n e u; do
      curl -sS -f -o "$OUT/$(echo "$n" | tr ' /' '__').$e" "$u" || echo "download failed: $n"; done
  done
done
for z in "$OUT"/*.zip; do [ -e "$z" ] || continue
  d="$OUT/unzipped/$(basename "$z" .zip)"; mkdir -p "$d" && unzip -q "$z" -d "$d" && echo "extracted $(basename "$z")"
  find "$d" -maxdepth 6 -type d \( -name tls -o -name life \) | sed "s#^$OUT/#  found #"; done
echo "fetched $NAME (downloaded $(date '+%Y-%m-%d %H:%M'))" > "$OUT/fetched.txt"
