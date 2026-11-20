#!/bin/bash
# Guard for role-B work on b-exp (team plan PLAN-ROUND3.md / HUONG-DAN-B.md). Exit 0 = safe to commit / hand off.
#  1. files owned by A or C are unchanged on this branch (vs merge-base with origin/main)
#  2. core oracle/validity code unchanged unless declared in GUARD_ALLOW (it changes what is measured)
#  3. recorded evidence unchanged (new round3/ dirs and RUNLOG appends are fine)
#  4. oracle unit tests pass
#  5. regeneration (Makefile `revision` + paper renderers, no LaTeX) reproduces every tracked output byte-identically
# GUARD_ALLOW="path ..." declares intended changes to items in 2 or 5 (state why in the commit message).
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../../../.." && pwd)
cd "$ROOT" || exit 2
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git rev-parse HEAD)
allowed(){ [[ " ${GUARD_ALLOW:-} " == *" $1 "* ]]; }
fail=0
OTHERS=(  # owned by A or C (HUONG-DAN-B): read, never edit on b-exp
  artifact/scripts/render.py artifact/scripts/render_campaign.py artifact/scripts/render_micro.py
  artifact/scripts/render_tests.py artifact/revision/render_revision.py artifact/followup/render.py
  artifact/mutation artifact/triage artifact/survey artifact/devicefarm
)
for p in "${OTHERS[@]}"; do
  git diff --quiet "$BASE" -- "$p" || { echo "GUARD FAIL: $p is owned by A or C; ask the owner"; fail=1; }
done
CORE=( artifact/scripts/oracle.py artifact/scripts/summarize.py artifact/revision/oracle_v2.py
       artifact/revision/matched_oracle.py artifact/revision/historical_uncertainty.py artifact/revision/test_oracle.py )
for p in "${CORE[@]}"; do
  allowed "$p" && continue
  git diff --quiet "$BASE" -- "$p" || { echo "GUARD FAIL: core analysis code changed: $p (set GUARD_ALLOW if intended)"; fail=1; }
done
changed=$(git diff --name-only --diff-filter=MD "$BASE" -- artifact/results | grep -v '^artifact/results/RUNLOG.md$')
[ -z "$changed" ] || { echo "GUARD FAIL: recorded evidence modified or deleted:"; echo "$changed"; fail=1; }
git diff "$BASE" -- artifact/results/RUNLOG.md | grep -q '^-[^-]' && { echo "GUARD FAIL: RUNLOG lines removed (append-only)"; fail=1; }

(cd artifact/revision && python3 -m unittest -q test_oracle >/dev/null 2>&1) || { echo "GUARD FAIL: oracle unit tests"; fail=1; }

S=$(mktemp -d "${TMPDIR:-/tmp}/p04-guard.XXXXXX")
git ls-files -co --exclude-standard -z | tar --null -T - -cf - | tar -xf - -C "$S"
if ! (cd "$S/artifact" && make revision PY=python3 >"$S/guard-make.log" 2>&1 \
      && python3 followup/analyze_tls.py > results/review-followup-20261115/transport-analysis.log 2>>"$S/guard-make.log" \
      && python3 followup/render.py >>"$S/guard-make.log" 2>&1 && python3 scripts/render_tests.py >>"$S/guard-make.log" 2>&1); then
  echo "GUARD FAIL: regeneration failed (log: $S/guard-make.log)"; fail=1
else
  while IFS= read -r f; do
    allowed "$f" && continue
    if [ -f "$S/$f" ] && ! cmp -s "$S/$f" "$ROOT/$f"; then echo "GUARD FAIL: not reproduced: $f"; fail=1; fi
  done < <(git ls-files manuscript/generated artifact/results)
fi
[ $fail -eq 0 ] && { rm -rf "$S"; echo "GUARD OK"; }
exit $fail
