#!/usr/bin/env python3
"""Minimal pcap reader (group 3, g3race-card.md / g3app-card.md): classic libpcap, link type Ethernet (1) or raw IPv4 (101),
IPv4 + TCP only, no dependencies. Yields frames in capture order; the frame index is the order used by the analyses (the
capture timestamps are host clock and are never compared with device time)."""
import struct


def frames(path):
    with open(path, 'rb') as f:
        gh = f.read(24)
        if len(gh) < 24: return
        magic = gh[:4]
        if magic in (b'\xd4\xc3\xb2\xa1', b'\x4d\x3c\xb2\xa1'): e = '<'
        elif magic in (b'\xa1\xb2\xc3\xd4', b'\xa1\xb2\x3c\x4d'): e = '>'
        else: raise ValueError('not a classic pcap file')
        link = struct.unpack(e + 'I', gh[20:24])[0]
        idx = -1
        while True:
            h = f.read(16)
            if len(h) < 16: return
            ts, tf, incl, orig = struct.unpack(e + 'IIII', h); data = f.read(incl); idx += 1
            if link == 1:
                if len(data) < 14: continue
                et = struct.unpack('>H', data[12:14])[0]; off = 14
                if et == 0x8100: et = struct.unpack('>H', data[16:18])[0]; off = 18
                if et != 0x0800: continue
                ip = data[off:]
            elif link == 101: ip = data
            else: raise ValueError(f'link type {link} not supported')
            if len(ip) < 20 or ip[0] >> 4 != 4 or ip[9] != 6: continue
            ihl = (ip[0] & 15) * 4; tot = struct.unpack('>H', ip[2:4])[0]; tcp = ip[ihl:tot] if tot >= ihl else ip[ihl:]
            if len(tcp) < 20: continue
            sp, dp, seq, ack = struct.unpack('>HHII', tcp[:12]); doff = (tcp[12] >> 4) * 4; fl = tcp[13]
            yield {'i': idx, 'ts': ts + tf / 1e6, 'src': '.'.join(map(str, ip[12:16])), 'dst': '.'.join(map(str, ip[16:20])),
                   'sport': sp, 'dport': dp, 'seq': seq, 'flags': fl, 'len': max(0, (tot - ihl) - doff) if tot >= ihl else max(0, len(tcp) - doff),
                   'payload': bytes(tcp[doff:doff + 64])}


SYN, FIN, RST, ACK = 0x02, 0x01, 0x04, 0x10


def write(path, pkts):
    """Test helper: write a raw-IPv4 pcap (link 101) from dicts {src,dst,sport,dport,seq,flags,payload}."""
    with open(path, 'wb') as f:
        f.write(struct.pack('<IHHiIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 101))
        for k, p in enumerate(pkts):
            pl = p.get('payload', b''); tcp = struct.pack('>HHIIBBHHH', p['sport'], p['dport'], p.get('seq', 0), 0, 5 << 4, p.get('flags', ACK), 65535, 0, 0) + pl
            ip = struct.pack('>BBHHHBBH4s4s', 0x45, 0, 20 + len(tcp), 0, 0, 64, 6, 0, bytes(map(int, p['src'].split('.'))), bytes(map(int, p['dst'].split('.')))) + tcp
            f.write(struct.pack('<IIII', 1000 + k, 0, len(ip), len(ip)) + ip)
