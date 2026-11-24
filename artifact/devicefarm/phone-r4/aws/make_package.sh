#!/bin/bash
# Build an AWS Device Farm test package (Appium Python layout, as Test 6) for one round-4 task. Never edits the repo:
# sources come from `git archive HEAD`; C's patches are applied to that copy when HEAD does not have them yet.
# Usage: make_package.sh g3a|life|airguard <out.zip> [--cert DIR] [--token-file F] [--calib calibration.json]
#   g3a: --cert = directory with the EC2 receiver's test-ca.pem (~/.p04/ec2/cert-<ip>), --token-file = ~/.p04/ec2/token;
#        finals also --calib (the pilot's calibration.json). The zip then holds the EC2 control token: keep it outside
#        the repo, delete it after the round, and tear the EC2 host down (the token dies with it).
#   life: needs fixture/build/revision-apk/rl-{menqueue,mstart,mlayer,mfence,mboth}.apk (as Test 6).
#   airguard: needs realapp/airguard/build/phone/airguard-{stock,fenced,layered}.apk (../build_airguard_phone.sh).
set -euo pipefail
main() {
TASK=${1:?task}; OUT=${2:?out.zip}; shift 2; CERT=; TOK=; CAL=
while [ $# -gt 0 ]; do case $1 in --cert) CERT=$2; shift 2;; --token-file) TOK=$2; shift 2;; --calib) CAL=$2; shift 2;;
  *) echo "unknown option $1"; return 2;; esac; done
case $OUT in /*) ;; *) OUT=$PWD/$OUT;; esac
[ ! -e "$OUT" ] || { echo "refusing: $OUT exists"; return 2; }
HERE=$(cd "$(dirname "$0")" && pwd); KIT=$(dirname "$HERE"); REPO=$(git -C "$HERE" rev-parse --show-toplevel); ART=$REPO/artifact
STAGE=$(mktemp -d); trap 'rm -rf "$STAGE"' EXIT
git -C "$REPO" archive HEAD artifact | tar -x -C "$STAGE"
P=$STAGE/pkg; mkdir -p "$P/tests" "$P/artifact/followup"
printf 'def test_placeholder():\n    pass\n' > "$P/tests/test_placeholder.py"; echo pytest > "$P/requirements.txt"
need() { [ -f "$1" ] || { echo "missing $1"; exit 3; }; }
patched() { grep -q -- "$1" "$STAGE/$2" || (cd "$STAGE" && git apply "$KIT/$3" && echo "applied $3 to the package copy"); }
case $TASK in
g3a)
  need "$ART/fixture/build/g3-apk/rl-tls.apk"; need "${CERT:?--cert}/test-ca.pem"; need "${TOK:?--token-file}"
  cp "$STAGE/artifact/followup/race_suite.py" "$P/artifact/followup/"
  mkdir -p "$P/artifact/fixture/build/g3-apk" "$P/cert" "$P/secrets" "$P/calib"
  cp "$ART/fixture/build/g3-apk/rl-tls.apk" "$P/artifact/fixture/build/g3-apk/"
  cp "$CERT/test-ca.pem" "$P/cert/"                     # the CA only; the key stays on the EC2 host
  cp "$TOK" "$P/secrets/p04_token"
  if [ -n "$CAL" ]; then need "$CAL"; cp "$CAL" "$P/calib/calibration.json"; fi;;
life)
  patched --phone-faults artifact/followup/campaign.py phone-faults.patch
  mkdir -p "$P/artifact/harness" "$P/artifact/fixture/build/revision-apk"
  cp "$STAGE/artifact/followup/campaign.py" "$P/artifact/followup/"; cp "$STAGE/artifact/harness/sink.py" "$P/artifact/harness/"
  for v in menqueue mstart mlayer mfence mboth; do need "$ART/fixture/build/revision-apk/rl-$v.apk"
    cp "$ART/fixture/build/revision-apk/rl-$v.apk" "$P/artifact/fixture/build/revision-apk/"; done;;
airguard)
  patched "'--phone'" artifact/followup/campaign_airguard.py airguard-phone.patch
  mkdir -p "$P/artifact/realapp/airguard/build/phone"
  cp "$STAGE/artifact/followup/campaign_airguard.py" "$STAGE/artifact/followup/airguard_sink.py" "$P/artifact/followup/"
  for v in stock fenced layered; do need "$ART/realapp/airguard/build/phone/airguard-$v.apk"
    cp "$ART/realapp/airguard/build/phone/airguard-$v.apk" "$P/artifact/realapp/airguard/build/phone/"; done;;
*) echo "task: g3a|life|airguard"; return 2;;
esac
(cd "$P" && zip -qr "$OUT" . && find . -type f | sort | sed 's#^\./#  #')
echo "package $OUT sha256 $(shasum -a 256 "$OUT" | cut -d' ' -f1) (HEAD $(git -C "$REPO" rev-parse --short HEAD))"
}
main "$@"
