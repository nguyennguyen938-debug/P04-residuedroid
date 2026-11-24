#!/usr/bin/env python3
"""Round 4 on Device Farm (plans/r4df-*-card.md): pin every source, harness, analysis script, Device Farm kit file and APK the
three tasks use -> <out>/source-sha256.json + source.tar.gz (APKs by hash only), plus the git HEAD and the SHA-256 of the
Device Farm packages given on the command line (the exact bundles uploaded). Usage: freeze_r4df.py <out dir> [package.zip ...]"""
import hashlib, json, subprocess, sys, tarfile
from pathlib import Path
art = Path(__file__).resolve().parents[2]; out = Path(sys.argv[1]); out = out if out.is_absolute() else art.parent / out
assert not out.exists(), f'{out} exists (fresh directory only)'
roots = ['fixture/src', 'fixture/src-cmp', 'fixture/build.sh', 'fixture/AndroidManifest.xml', 'fixture/build/revision-apk', 'fixture/build/g3-apk/rl-tls.apk',
         'transport/src', 'harness', 'scripts/summarize.py', 'followup/campaign.py', 'followup/analyze_test6.py', 'followup/matched_oracle.py',
         'followup/campaign_airguard.py', 'followup/analyze_airguard.py', 'followup/airguard_sink.py', 'followup/race_suite.py', 'followup/analyze_g3race.py',
         'followup/test_campaign_phonefaults.py', 'followup/test_analyze_test6.py', 'followup/test_airguard_phone.py', 'followup/test_phone_reboot.py',
         'realapp/airguard/apply.sh', 'realapp/airguard/src', 'realapp/airguard/build/phone', 'plans/b1/build_airguard.sh', 'plans/r4df',
         'plans/test6/run_df.sh', 'devicefarm/phone-r4']
files = []
for r in roots:
    b = art / r
    files += [b] if b.is_file() else sorted(p for p in b.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
man = {str(p.relative_to(art)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
out.mkdir(parents=True); (out / 'source-sha256.json').write_text(json.dumps(man, indent=2, sort_keys=True) + '\n')
with tarfile.open(out / 'source.tar.gz', 'w:gz') as t:
    for p in files:
        if p.suffix != '.apk': t.add(p, arcname=str(p.relative_to(art)))
head = subprocess.run(['git', '-C', str(art), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
dirty = subprocess.run(['git', '-C', str(art), 'status', '--porcelain', '--', *roots], capture_output=True, text=True).stdout.strip()
pk = {Path(z).name: hashlib.sha256(Path(z).read_bytes()).hexdigest() for z in sys.argv[2:]}
(out / 'build.json').write_text(json.dumps({'git_head': head, 'tracked_roots_clean': not dirty, 'packages': pk}, indent=1) + '\n')
print(len(files), 'pinned files; HEAD', head[:7], 'clean' if not dirty else 'DIRTY', pk)
