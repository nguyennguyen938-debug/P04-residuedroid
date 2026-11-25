#!/usr/bin/env python3
"""Round 4 on Device Farm: one summary of the pre-registered analysis outputs with Wilson 95 % intervals (R4.3), next to the
emulator cohorts it repeats (G2b for AirGuard). Reads only analysis outputs. Writes results/round3/phone-r4/aws/r4df-report.json."""
import json, sys
from pathlib import Path
ART = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ART / 'scripts')); from summarize import wilson
R = ART / 'results/round3/phone-r4/aws'; out = {}
def w(k, n): _, lo, hi = wilson(k, n); return {'k': k, 'n': n, 'wilson95': [round(lo, 4), round(hi, 4)]}
m = json.loads((R / 'life/analysis/matched-summary.json').read_text())
out['lifecycle_netloss'] = {r['variant']: {'violating_tenant_trials': w(r['known_violations'], r['tenant_trials']), 'paired_trials': r['trials'],
    'unknown_requests': r['unknown_requests'], 'legit_missing': r['legit_missing'], 'bootstrap_p95': r.get('percentile95')} for r in m}
out['lifecycle_reboot'] = 'dropped on Device Farm: adb reboot ignored (life/pilot-preb/reboot-evidence.json)'
for name, f in (('airguard', R / 'airguard/analysis/airguard-summary.json'), ('airguard_emulator_g2b', ART / 'results/round3/g2layer/analysis/airguard-summary.json')):
    s = json.loads(f.read_text())
    out[name] = {c: {'violating_trials': w(v['violating_trials'], v['trials']), 'deficit_trials': v['deficit_trials'], 'deficit_beacons': v['deficit_beacons'],
                     'blocked_trials': v['blocked_trials'], 'unknown_trials': v['unknown_trials']} for c, v in sorted(s['cells'].items()) if c.split('/')[0] in ('pending', 'kill', 'netloss')}
g = R / 'g3a/analysis/g3race-summary.json'
if g.exists(): out['g3a'] = json.loads(g.read_text())
(R / 'r4df-report.json').write_text(json.dumps(out, indent=1) + '\n'); print(json.dumps({k: v for k, v in out.items() if k != 'g3a'}, indent=1)[:3000])
