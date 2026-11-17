#!/usr/bin/env python3
"""Verify a fresh review extraction before regenerating its derived outputs."""
import argparse, hashlib, json, tarfile
from pathlib import Path

def sha(b): return hashlib.sha256(b).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('--forbid',action='append',default=[]);a=ap.parse_args()
    root=a.root;errors=[];checked=0;frozen=0
    manifest={}
    for line in (root/'MANIFEST.sha256').read_text().splitlines():
        h,name=line.split('  ',1);manifest[name]=h;p=root/name
        if not p.is_file() or sha(p.read_bytes())!=h:errors.append('manifest: '+name)
        checked+=1
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name!='MANIFEST.sha256'}
    if actual!=set(manifest):errors.append('manifest file-set mismatch')
    for p in sorted(root.rglob('*')):
        if not p.is_file():continue
        for marker in a.forbid:
            if marker.encode() in p.read_bytes():errors.append('identity marker: '+str(p.relative_to(root)))
        if p.name.endswith('.tar.gz'):
            hashes={}
            with tarfile.open(p) as t:
                for m in t.getmembers():
                    if not m.isfile():continue
                    if m.name in {'review.md','STATUS.md'}:errors.append('private historical review/status in archive: '+m.name)
                    if '..' in Path(m.name).parts or Path(m.name).is_absolute():errors.append('unsafe archive path: '+m.name)
                    b=t.extractfile(m).read();hashes[m.name]=sha(b)
                    if m.uid or m.gid or m.uname or m.gname:errors.append('archive ownership: '+m.name)
                    for marker in a.forbid:
                        if marker.encode() in b:errors.append('archive identity marker: '+m.name)
            if p.name=='source.tar.gz':
                frozen+=1
                if hashes!=json.loads((p.parent/'source-sha256.json').read_text()):errors.append('frozen source manifest: '+str(p.relative_to(root)))
    result=dict(files=checked,frozen_manifests=frozen,errors=errors)
    print(json.dumps(result,indent=2))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
