#!/usr/bin/env python3
"""Group 3: write a committed, truncated copy of a large capture (classic pcap) keeping the first SNAP bytes of every frame
(link, IP and TCP headers plus the first payload bytes, enough for the marker id). pcapmin reads payload lengths from the IP
header, so the G3 analyses give the same result on the slim copy. The full capture stays on disk (git-ignored); its sha256
is written next to the copy. Usage: pcap_slim.py <capture.pcap> [--snap 200]  -> capture-slim.pcap, capture.pcap.sha256"""
import argparse, hashlib, struct
from pathlib import Path

ap = argparse.ArgumentParser(); ap.add_argument('pcap', type=Path); ap.add_argument('--snap', type=int, default=200); a = ap.parse_args()
out = a.pcap.with_name(a.pcap.stem + '-slim.pcap'); assert not out.exists(), f'{out} exists'
h = hashlib.sha256()
with open(a.pcap, 'rb') as f, open(out, 'wb') as g:
    gh = f.read(24); h.update(gh); e = '<' if gh[:4] in (b'\xd4\xc3\xb2\xa1', b'\x4d\x3c\xb2\xa1') else '>'
    g.write(gh[:16] + struct.pack(e + 'I', a.snap) + gh[20:24])
    while True:
        rh = f.read(16)
        if len(rh) < 16: break
        h.update(rh); ts, tf, incl, orig = struct.unpack(e + 'IIII', rh); d = f.read(incl); h.update(d)
        g.write(struct.pack(e + 'IIII', ts, tf, min(incl, a.snap), orig) + d[:a.snap])
a.pcap.with_name(a.pcap.name + '.sha256').write_text(f'{h.hexdigest()}  {a.pcap.name}\n'); print(out, h.hexdigest())
