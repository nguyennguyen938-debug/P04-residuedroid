#!/usr/bin/env python3
"""Unit tests for the group-3 race oracles (analyze_g3race.py, pcapmin.py) on synthetic data; written before any G3 trial."""
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_g3race as g, pcapmin as pc

G, H, M = '10.0.2.15', '10.0.2.2', 8799


def ev(t, kind, detail='', trial='T'): return {'trial': trial, 'kind': kind, 'detail': detail, 'mono_ns': t}


class AfterW(unittest.TestCase):
    def row(self, evs): return {'trial': 'T', 'events': evs}
    def test_write_started_before_w_is_not_after_w(self):
        self.assertFalse(g.after_w(self.row([ev(1, 'WRITE_ATTEMPT'), ev(2, 'WITHDRAW_DURABLE'), ev(3, 'BYTES_ACCEPTED', 'n=10')])))
    def test_write_started_after_w(self):
        self.assertTrue(g.after_w(self.row([ev(1, 'WITHDRAW_DURABLE'), ev(2, 'WRITE_ATTEMPT'), ev(3, 'BYTES_ACCEPTED', 'n=10')])))
    def test_zero_bytes_after_w_is_not_counted(self):
        self.assertFalse(g.after_w(self.row([ev(1, 'WITHDRAW_DURABLE'), ev(2, 'WRITE_ATTEMPT'), ev(3, 'BYTES_ACCEPTED', 'n=0')])))
    def test_no_durable_is_unknown(self):
        self.assertIsNone(g.after_w(self.row([ev(2, 'WRITE_ATTEMPT'), ev(3, 'BYTES_ACCEPTED', 'n=5')])))
    def test_other_trial_events_ignored(self):
        self.assertFalse(g.after_w(self.row([ev(1, 'WITHDRAW_DURABLE'), ev(2, 'WRITE_ATTEMPT', trial='X'), ev(3, 'BYTES_ACCEPTED', 'n=5', trial='X')])))


class Capture(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()); P = []
        def syn(sp, dp, seq=100): P.append(dict(src=G, dst=H, sport=sp, dport=dp, seq=seq, flags=pc.SYN))
        def data(sp, dp, seq, n, fl=pc.ACK): P.append(dict(src=G, dst=H, sport=sp, dport=dp, seq=seq, flags=fl, payload=b'x' * n))
        # trial A: request port 40000, 3 segments before the marker, 2 after (one retransmission of old data)
        syn(40000, 8798); data(40000, 8798, 101, 1000); data(40000, 8798, 1101, 1000)
        syn(50000, M); data(50000, M, 1, 0); P.append(dict(src=G, dst=H, sport=50000, dport=M, seq=1, flags=pc.ACK, payload=b'A\n'))
        data(40000, 8798, 1101, 1000); data(40000, 8798, 2101, 500, pc.ACK | pc.FIN)
        # trial B: request port 40001 closed with RST after the marker, no payload after it
        syn(40001, 8798, 7); data(40001, 8798, 8, 300)
        syn(50001, M); P.append(dict(src=G, dst=H, sport=50001, dport=M, seq=1, flags=pc.ACK, payload=b'B\n'))
        P.append(dict(src=G, dst=H, sport=40001, dport=8798, seq=308, flags=pc.RST))
        # trial C: no SOCKET_LOCAL (cut before the handshake): the single SYN between markers B and C
        syn(40002, 8798, 0); syn(50002, M); P.append(dict(src=G, dst=H, sport=50002, dport=M, seq=1, flags=pc.ACK, payload=b'C\n'))
        pc.write(self.d / 'c.pcap', P)
        self.cap = g.capture(self.d / 'c.pcap', M)

    def m(self, tid, port): return g.cap_measure({'trial': tid, 'events': [1]}, {'local_port': port}, *self.cap)

    def test_markers_by_payload_id(self): self.assertEqual(sorted(self.cap[0]), ['A', 'B', 'C'])
    def test_bytes_after_marker_all_and_new(self):
        q = self.m('A', 40000); self.assertEqual((q['after_marker_bytes'], q['after_marker_new_bytes'], q['fin_after_marker']), (1500, 500, True))
    def test_rst_and_zero_bytes(self):
        q = self.m('B', 40001); self.assertEqual((q['after_marker_bytes'], q['rst_after_marker']), (0, True))
    def test_fallback_without_local_port(self):
        q = self.m('C', None); self.assertEqual((q['status'], q['after_marker_bytes']), ('matched', 0))
    def test_missing_marker(self): self.assertEqual(self.m('Z', 40000)['status'], 'no marker')

    def test_reused_marker_port(self):
        P = []
        for tid in ('R1', 'R2'):
            P += [dict(src=G, dst=H, sport=50009, dport=M, flags=pc.SYN), dict(src=G, dst=H, sport=50009, dport=M, flags=pc.ACK, payload=(tid + '\n').encode())]
        pc.write(self.d / 'r.pcap', P); self.assertEqual(sorted(g.capture(self.d / 'r.pcap', M)[0]), ['R1', 'R2'])


if __name__ == '__main__':
    unittest.main()
