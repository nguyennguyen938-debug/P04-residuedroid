#!/usr/bin/env python3
"""Group 3 freeze (g3race-card.md, g3app-card.md, g3cost-card.md): pin every source, driver, analysis script, manifest and
APK the G3 runs use -> <out>/source-sha256.json + source.tar.gz (sources only; APKs by hash). The autorun `frozen` check compares them."""
import hashlib, json, sys, tarfile
from pathlib import Path
art = Path(__file__).resolve().parents[1]; out = art / sys.argv[1] if not Path(sys.argv[1]).is_absolute() else Path(sys.argv[1])
assert not out.exists(), f'{out} exists (fresh directory only)'
roots = ['fixture/src', 'fixture/src-cmp', 'fixture/build.sh', 'fixture/AndroidManifest.xml', 'fixture/build/g3-apk/rl-tls.apk', 'fixture/build/g3p4-apk/rl-tls.apk', 'followup/analyze_g3p4.py', 'plans/autorun/g3-p4-chain.sh', 'transport/src',
         'followup/race_suite.py', 'followup/race_airguard.py', 'followup/cost_suite.py', 'followup/airguard_sink.py', 'followup/analyze_race.py',
         'followup/analyze_g2close.py', 'followup/analyze_g3race.py', 'followup/analyze_g3app.py', 'followup/analyze_g3cost.py', 'followup/pcapmin.py',
         'followup/test_g3race.py', 'followup/test_g3app.py', 'followup/test_g3cost.py', 'realapp/airguard/apply.sh', 'realapp/airguard/apply_g3.sh',
         'realapp/airguard/build_g3.sh', 'realapp/airguard/src', 'realapp/airguard/src-g3', 'realapp/airguard/build/g3', 'plans/b1/build_airguard.sh',
         'scripts/summarize.py', 'plans/autorun/g3-chain.sh', 'plans/autorun/g3-chain-v2.sh', 'plans/autorun/g3-chain-v3.sh', 'plans/autorun/g3-chain-v4.sh', 'plans/autorun/g3d-chain.sh', 'followup/audit_g3race.py', 'followup/tls_records.py', 'followup/qsnap.py', 'followup/test_tls_records.py', 'followup/test_qsnap.py', 'plans/autorun/battery_guard.sh', 'plans/autorun/g3-tonight.sh', 'plans/autorun/g3-p3v5-chain.sh', 'followup/analyze_g3app5.py', 'followup/test_g3app5.py', 'realapp/airguard/build/g3v5', 'plans/autorun/g3-g3c5-chain.sh'] + [f'plans/autorun/{p.name}' for p in sorted((art / 'plans/autorun').glob('g3*.json'))]
files = []
for r in roots:
    b = art / r
    files += [b] if b.is_file() else sorted(p for p in b.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
man = {str(p.relative_to(art)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
out.mkdir(parents=True); (out / 'source-sha256.json').write_text(json.dumps(man, indent=2, sort_keys=True) + '\n')
with tarfile.open(out / 'source.tar.gz', 'w:gz') as t:
    for p in files:
        if p.suffix != '.apk': t.add(p, arcname=str(p.relative_to(art)))   # APKs: pinned by hash only (as frozen-g2), not archived
print(len(files), 'pinned files')
