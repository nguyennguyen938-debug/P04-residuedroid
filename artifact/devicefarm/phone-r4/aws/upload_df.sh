#!/bin/bash
# Upload one job's app, package and spec to Device Farm and write the uploads.env that plans/test6/run_df.sh reads.
# Usage: upload_df.sh <project-arn> <device-pool-arn> <app.apk> <package.zip> <spec.yml> > uploads-<job>.env
# Keep the .env files outside the repository (they hold account ARNs). Uploads cost nothing; runs cost device minutes.
set -euo pipefail
PRJ=${1:?project-arn}; POOL=${2:?pool-arn}; APK=${3:?app}; ZIP=${4:?package}; SPEC=${5:?spec}
export AWS_PROFILE=${AWS_PROFILE:-p04} AWS_REGION=us-west-2
up() {   # <type> <file> -> prints the upload ARN once Device Farm has processed it
  local arn url st
  read -r arn url < <(aws devicefarm create-upload --project-arn "$PRJ" --name "$(basename "$2")" --type "$1" \
    --query 'upload.[arn,url]' --output text)
  curl -sS -f -T "$2" "$url" >&2
  for _ in $(seq 1 120); do
    st=$(aws devicefarm get-upload --arn "$arn" --query upload.status --output text)
    case $st in SUCCEEDED) echo "$arn"; return 0;;
      FAILED) aws devicefarm get-upload --arn "$arn" --query upload.metadata --output text >&2; return 1;; esac
    sleep 5
  done
  echo "upload $2 not processed in 10 min" >&2; return 1
}
echo "PRJ=$PRJ"; echo "POOL=$POOL"
echo "APP=$(up ANDROID_APP "$APK")"
echo "PKG=$(up APPIUM_PYTHON_TEST_PACKAGE "$ZIP")"
echo "SPEC=$(up APPIUM_PYTHON_TEST_SPEC "$SPEC")"
