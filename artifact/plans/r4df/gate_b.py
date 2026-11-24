#!/usr/bin/env python3
"""B's extra pilot gate for round 4 on Device Farm (24/11), run after C's devicefarm/phone-r4/gates.py: every pilot plan
must also pass the analysis validity rules for phone runs (harness and fault fields only, never an outcome):
  life:     followup/analyze_test6.phone_validity (kill/net/reboot confirmation, jobs observable);
  airguard: followup/analyze_airguard.validity (trial error, hooks, device alive, event logs, withdraw, phone fault checks).
Usage: gate_b.py life|airguard <dir with schedule.jsonl>; writes <dir>/gate_b.json; exit 0 = PASS."""
import json, sys
from pathlib import Path
ART = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ART / 'followup'))
kind, d = sys.argv[1], Path(sys.argv[2])
plans = [json.loads(l) for l in open(d / 'schedule.jsonl') if l.strip()]
if kind == 'life':
    sys.argv = [sys.argv[0]]; import analyze_test6 as t
    why = {p['trial']: t.phone_validity(p) for p in plans}
else:
    import analyze_airguard as g
    meta = json.loads((d / 'meta.json').read_text())
    dev = {(x['trial'], x['variant']): x['events'] for x in (json.loads(l) for l in open(d / 'device_events.jsonl') if l.strip())}
    why = {p['trial']: g.validity(p, dev, tuple(meta['variants'])) for p in plans}
res = {'gate': bool(plans) and not any(why.values()), 'plans': len(plans), 'invalid': {k: v for k, v in why.items() if v}}
(d / 'gate_b.json').write_text(json.dumps(res, indent=1) + '\n'); print(res); sys.exit(0 if res['gate'] else 1)
