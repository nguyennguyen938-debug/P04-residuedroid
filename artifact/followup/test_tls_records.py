#!/usr/bin/env python3
"""Unit test for tls_records.py (P1a): application_data vs other records, a record split over frames, a retransmission,
port reuse, and a gap (unknown)."""
import sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import pcapmin as pc, tls_records as tr

G, H = '10.0.2.15', '10.0.2.2'
rec = lambda t, n: bytes([t, 3, 3, n >> 8, n & 255]) + b'x' * n


class TLSRecords(unittest.TestCase):
    def test_annotate(self):
        d = Path(tempfile.mkdtemp()); hs, app, alert = rec(22, 40), rec(23, 300), rec(21, 26)
        s = hs + app + alert   # offsets: hs 0-45, app 45-350, alert 350-381
        P = [dict(src=G, dst=H, sport=40000, dport=8798, seq=999, flags=pc.SYN),
             dict(src=G, dst=H, sport=40000, dport=8798, seq=1000, payload=s[:100]),          # frame 1: hs 45 + app 55
             dict(src=G, dst=H, sport=40000, dport=8798, seq=1100, payload=s[100:350]),       # frame 2: app 250
             dict(src=G, dst=H, sport=40000, dport=8798, seq=1100, payload=s[100:350]),       # frame 3: retransmission
             dict(src=G, dst=H, sport=40000, dport=8798, seq=1350, payload=s[350:]),          # frame 4: alert 31
             dict(src=G, dst=H, sport=40000, dport=8798, seq=4999, flags=pc.SYN),             # frame 5: port reused
             dict(src=G, dst=H, sport=40000, dport=8798, seq=5000, payload=rec(23, 10)),      # frame 6: app 15
             dict(src=G, dst=H, sport=40001, dport=8798, seq=99, flags=pc.SYN),
             dict(src=G, dst=H, sport=40001, dport=8798, seq=150, payload=b'y' * 20)]         # frame 8: gap -> unknown
        pc.write(d / 'c.pcap', P); a = tr.annotate(d / 'c.pcap')
        self.assertEqual(a[1], {'app': 55, 'other': 45, 'unknown': 0})
        self.assertEqual(a[2], {'app': 250, 'other': 0, 'unknown': 0}); self.assertEqual(a[3], a[2])
        self.assertEqual(a[4], {'app': 0, 'other': 31, 'unknown': 0})
        self.assertEqual(a[6], {'app': 15, 'other': 0, 'unknown': 0})
        self.assertEqual(a[8], {'app': 0, 'other': 0, 'unknown': 20})


if __name__ == '__main__':
    unittest.main()
