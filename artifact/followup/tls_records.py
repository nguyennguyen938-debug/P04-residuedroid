#!/usr/bin/env python3
"""Group 3 (P1a, approved by the leader 22/11; pre-registered for the P3/P4 runs, exploratory on G3a/G3b v3): per guest ->
receiver TCP frame of a capture, how many of its payload bytes belong to TLS application_data records (content type 23),
to other TLS records (handshake, alert, change_cipher_spec) or to an unknown part of the stream.

Method: per connection (SYN guest -> :8798; a new SYN on the same port starts a new connection) the payload is placed at
its sequence offset from the ISN (retransmissions overwrite the same offsets); the reassembled stream is parsed as TLS
records from offset 0 (5-byte header: type, version, length). Parsing stops at the first gap (bytes not in the capture,
e.g. a truncated snap length); later bytes are 'unknown'. Each frame's [offset, offset + len) is split by record type.
Needs full payloads: run on the full capture.pcap (git-ignored), write capture-tls.jsonl (committed, with the pcap sha256).
Usage: tls_records.py <capture.pcap> [--port 8798] [--out capture-tls.jsonl]
"""
import argparse, bisect, collections, hashlib, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pcapmin  # noqa: E402

APP = 23


def annotate(path, port=8798):
    """-> {frame index: {'app': n, 'other': n, 'unknown': n}} for guest -> port frames with payload."""
    conns, cur = [], {}                                   # per sport: current connection [isn, frames]
    for p in pcapmin.frames(path, full=True):
        if p['dport'] != port: continue
        if p['flags'] & pcapmin.SYN and not p['flags'] & pcapmin.ACK:
            cur[p['sport']] = c = {'isn': p['seq'], 'frames': []}; conns.append(c); continue
        if p['len'] and p['sport'] in cur: cur[p['sport']]['frames'].append(p)
    out = {}
    for c in conns:
        span = max(((p['seq'] - c['isn'] - 1) % 2 ** 32 + p['len'] for p in c['frames']), default=0)
        buf, have = bytearray(span), bytearray(span)       # reassembled stream and coverage (1 = byte in the capture)
        for p in c['frames']:
            off = (p['seq'] - c['isn'] - 1) % 2 ** 32; pl = p['payload'][:p['len']]
            buf[off:off + len(pl)] = pl; have[off:off + len(pl)] = b'\x01' * len(pl)
        full = lambda a, n: a + n <= span and have.find(0, a, a + n) == -1
        ranges, off = [], 0                               # (start, end, type)
        while full(off, 5):
            t, n = buf[off], (buf[off + 3] << 8) | buf[off + 4]
            if not full(off + 5, n): break
            ranges.append((off, off + 5 + n, t)); off += 5 + n
        known = off; starts = [r[0] for r in ranges]
        for p in c['frames']:
            a = (p['seq'] - c['isn'] - 1) % 2 ** 32; b = a + p['len']; cnt = collections.Counter()
            j = max(0, bisect.bisect_right(starts, a) - 1)
            while j < len(ranges) and ranges[j][0] < b:
                s, e, t = ranges[j]; ov = max(0, min(b, e) - max(a, s))
                if ov: cnt['app' if t == APP else 'other'] += ov
                j += 1
            cnt['unknown'] += max(0, b - max(a, known))
            out[p['i']] = {k: cnt.get(k, 0) for k in ('app', 'other', 'unknown')}
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('pcap', type=Path); ap.add_argument('--port', type=int, default=8798); ap.add_argument('--out', type=Path)
    a = ap.parse_args(); out = a.out or a.pcap.with_name('capture-tls.jsonl'); assert not out.exists(), f'{out} exists'
    h = hashlib.sha256(a.pcap.read_bytes()).hexdigest(); ann = annotate(a.pcap, a.port)
    with open(out, 'w') as f:
        f.write(json.dumps({'pcap': a.pcap.name, 'pcap_sha256': h, 'port': a.port}) + '\n')
        for i in sorted(ann): f.write(json.dumps({'i': i, **ann[i]}) + '\n')
    tot = collections.Counter()
    for v in ann.values(): tot.update(v)
    print(out, len(ann), 'frames', dict(tot))


def load(path):
    """capture-tls.jsonl -> {frame index: {'app', 'other', 'unknown'}} (first line is the header)."""
    ls = Path(path).read_text().splitlines()
    return {x['i']: x for x in map(json.loads, ls[1:])}


if __name__ == '__main__':
    main()
