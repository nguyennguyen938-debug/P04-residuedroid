#!/usr/bin/env python3
"""Pin all source and executable APKs before a revision measurement run."""
from pathlib import Path
import hashlib,json,sys,tarfile,time
art=Path(__file__).resolve().parents[1];out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
files=[]
for root in ['matomo/src','matomo/build/matomo.apk','matomo/deps','fixture/src','fixture/build/revision-apk','fixture/build/socket-v3-apk','acra/src','acra/build/apk','transport','revision','harness','scripts']:
 base=art/root
 for p in ([base] if base.is_file() else sorted(base.rglob('*'))):
  if p.is_file() and '__pycache__' not in p.parts and 'test-build' not in p.parts:files.append(p)
for p in [art/'fixture/build.sh',art/'fixture/AndroidManifest.xml',art/'acra/build.sh',art/'acra/AndroidManifest.tmpl.xml',art/'matomo/build.sh',art/'matomo/AndroidManifest.xml',art/'env.sh']:files.append(p)
manifest={str(p.relative_to(art)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(out/'source-sha256.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
with tarfile.open(out/'source.tar.gz','w:gz') as tar:
 for p in files:tar.add(p,arcname=str(p.relative_to(art)))
print(len(files),'pinned files')
