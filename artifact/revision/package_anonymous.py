#!/usr/bin/env python3
"""Create a local anonymous review ZIP without changing original evidence.

Text paths and TAR ownership are normalized; measurement values are untouched.
Original-to-packaged hashes make every byte transformation explicit.
"""
import argparse, hashlib, io, json, re, shutil, tarfile, zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
def digest(b): return hashlib.sha256(b).hexdigest()
def sanitize(b):
    try: s = b.decode('utf-8')
    except UnicodeDecodeError: return b
    s = re.sub(r'/Users/[^/\s"\'<>]+/Workstation/MobiSys2027/papers/P04-residuedroid', '/artifact/P04-residuedroid', s)
    s = re.sub(r'/Users/[^/\s"\'<>]+/Workstation/MobiSys2027', '/workspace', s)
    s = re.sub(r'/Users/[^/\s"\'<>]+', '/home/anonymous', s)
    s = re.sub(r'/var/folders/[^/\s]+/[^/\s]+/T/', '/tmp/', s)
    # The current workspace owner can also occur in emulator temporary paths.
    owner = PROJECT.parts[2] if PROJECT.parts[:2] == ('/', 'Users') else None
    if owner: s = s.replace(owner, 'anonymous')
    return s.encode('utf-8')

def archive(data):
    output = io.BytesIO(); hashes = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as src, tarfile.open(fileobj=output, mode='w:gz') as dst:
        for m in src.getmembers():
            if not m.isfile() or m.name in {'review.md','STATUS.md'} or any(x in Path(m.name).parts for x in ['__pycache__','test-build']) or m.name.endswith('.pyc'): continue
            if '..' in Path(m.name).parts or Path(m.name).is_absolute(): raise ValueError('unsafe tar member')
            b = sanitize(src.extractfile(m).read())
            m.uid = m.gid = 0; m.uname = m.gname = ''; m.mtime = 0; m.pax_headers = {}; m.size = len(b)
            dst.addfile(m, io.BytesIO(b)); hashes[m.name] = digest(b)
    return output.getvalue(), hashes

def include(p):
    rel = p.relative_to(PROJECT); parts = rel.parts
    if any(x in parts for x in ['.git','__pycache__','test-build','.DS_Store']): return False
    if rel.as_posix().startswith('artifact/static/data/apks/'): return False
    if 'build' in parts:
        allowed = ['artifact/fixture/build/apk/', 'artifact/fixture/build/apk_alarm/',
                   'artifact/fixture/build/revision-apk/', 'artifact/fixture/build/socket-v3-apk/',
                   'artifact/acra/build/apk/', 'artifact/workmanager/build/apk/']
        if not any(rel.as_posix().startswith(a) for a in allowed) and rel.as_posix() != 'artifact/matomo/build/matomo.apk': return False
    if parts[0] == 'manuscript' and (p.suffix in ['.aux','.log','.blg','.bbl','.out','.fls','.fdb_latexmk']): return False
    return True

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True); target = args.out/'P04-residuedroid'
    if target.exists(): shutil.rmtree(target)
    target.mkdir(); changes = []; tar_manifests = {}
    roots = ['artifact','manuscript','others/smoke']
    files = [p for root in roots for p in (PROJECT/root).rglob('*') if p.is_file() and include(p)]
    for name in ['review/revision-execution-report.md','review/artifact-revision-audit.md']:
        p = PROJECT/name
        if p.exists(): files.append(p)
    for p in sorted(files):
        rel = p.relative_to(PROJECT); dest = target/rel; dest.parent.mkdir(parents=True,exist_ok=True)
        raw = p.read_bytes()
        if p.name.endswith('.tar.gz'):
            b, hashes = archive(raw)
            if p.name == 'source.tar.gz': tar_manifests[dest.parent/'source-sha256.json'] = hashes
        else: b = sanitize(raw)
        dest.write_bytes(b); dest.chmod(p.stat().st_mode & 0o777)
        if raw != b: changes.append(dict(file=str(rel),original_sha256=digest(raw),packaged_sha256=digest(b),reason='anonymous text paths, normalized archive metadata, private review/status removal, and build-cache exclusions from historical snapshots'))
    for p, hashes in tar_manifests.items():
        raw = p.read_bytes(); b = (json.dumps(hashes,indent=2,sort_keys=True)+'\n').encode(); p.write_bytes(b)
        changes.append(dict(file=str(p.relative_to(target)),original_sha256=digest(raw),packaged_sha256=digest(b),reason='manifest of packaged anonymous source members'))
    (target/'ANONYMIZATION.json').write_text(json.dumps(changes,indent=2)+'\n')
    (target/'README.md').write_text('''# ResidueDroid local review package

Start with `artifact/README.md`, `artifact/revision/INTEGRATION.md`, and the revision report.
Run `make -C artifact all` to regenerate recorded results and the paper. Android SDK/JDK
are external requirements for APK rebuilds and new device experiments; corpus APKs must
be retrieved to rerun the static scanner. This is a local package, not a public release.

`ANONYMIZATION.json` maps original hashes to packaged hashes. Only host paths and archive
ownership metadata are anonymized; measurement outcomes are preserved. Source manifests
beside frozen TAR files refer to their packaged members. Older raw metadata may reference
original hashes; use the mapping to resolve those references. Historical shell orchestration
scripts are retained as provenance; use the documented Python entry points for new runs.
The original review and private repository metadata are excluded. Debug signing keys are
public test material. `MANIFEST.sha256` covers every other file in this package.
''')
    manifest = {str(p.relative_to(target)):digest(p.read_bytes()) for p in sorted(target.rglob('*')) if p.is_file()}
    (target/'MANIFEST.sha256').write_text(''.join(f'{h}  {n}\n' for n,h in manifest.items()))
    zip_path = args.out/'P04-residuedroid-review.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(target.rglob('*')):
            if p.is_file(): z.write(p,str(p.relative_to(args.out)))
    (args.out/'P04-residuedroid-review.zip.sha256').write_text(digest(zip_path.read_bytes())+'  '+zip_path.name+'\n')
    print(json.dumps(dict(files=len(manifest)+1,transformed=len(changes),zip=str(zip_path),bytes=zip_path.stat().st_size)))
if __name__ == '__main__': main()
