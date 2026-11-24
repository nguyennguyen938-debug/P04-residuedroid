#!/bin/bash
# Fill a spec template (specs/*.yml.in) for one Device Farm job. Refuses to leave any @PLACEHOLDER@ unfilled.
# Usage: make_spec.sh <g3a|life|airguard> <out.yml> KEY=VALUE ...
#   g3a pilot:  make_spec.sh g3a g3a-pilot.yml IP=1.2.3.4 RUNARGS="--calibrate 3"
#   g3a job:    make_spec.sh g3a g3a-j1.yml IP=1.2.3.4 RUNARGS="--modes early,close,close2,fence,fence-abort --start 0 --trials 3 --durations calib/calibration.json"
#   life:       make_spec.sh life life-net.yml SCHED=netloss START=0 N=20
#   airguard:   make_spec.sh airguard ag-a.yml SCHED=pending,kill,netloss START=0 N=10
set -euo pipefail
T=${1:?template}; OUT=${2:?out}; shift 2
HERE=$(cd "$(dirname "$0")" && pwd); SRC=$HERE/specs/$T.yml.in
[ -f "$SRC" ] || { echo "no template $SRC"; exit 2; }
[ ! -e "$OUT" ] || { echo "refusing: $OUT exists"; exit 2; }
python3 - "$SRC" "$OUT" "$@" <<'PY'
import re, sys
src, out, kv = sys.argv[1], sys.argv[2], dict(a.split('=', 1) for a in sys.argv[3:])
s = open(src).read()
for k, v in kv.items():
    assert f'@{k}@' in s, f'template has no @{k}@'
    s = s.replace(f'@{k}@', v)
left = sorted(set(re.findall(r'@[A-Z]+@', s)))
assert not left, f'unfilled: {left}'
open(out, 'w').write(s); print('wrote', out)
PY
