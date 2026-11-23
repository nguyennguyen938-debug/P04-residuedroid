#!/usr/bin/env python3
"""Unit test for analyze_g3app5.py (G3c v5) on a synthetic run; written before any v5 trial."""
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import pcapmin as pc
import analyze_g3app5 as g

G, H, M = '10.0.2.15', '10.0.2.2', 8799
e = lambda t, k, det='': {'kind': k, 'mono_ns': t, 'detail': det}


class G3App5(unittest.TestCase):
    def test_cancel_cut(self):
        self.assertIsNone(g.cancel_cut([e(1, 'DONATION_OK')]))
        self.assertEqual(g.cancel_cut([e(1, 'CANCEL_DONE', 'calls=0'), e(2, 'DONATION_OK')]), 'no call')
        self.assertTrue(g.cancel_cut([e(1, 'CANCEL_DONE', 'calls=1'), e(2, 'DONATION_ERROR', 'stock=1;error=java.io.IOException: Canceled')]))
        self.assertFalse(g.cancel_cut([e(1, 'CANCEL_DONE', 'calls=1'), e(2, 'DONATION_OK')]))
        self.assertFalse(g.cancel_cut([e(0, 'DONATION_ERROR'), e(1, 'CANCEL_DONE', 'calls=1')]))   # ended before the cancel, no end after

    def test_sndbuf(self):
        ok = [e(0, 'SOCKET_CONFIG', 'path=/get_token;actual_sndbuf=1'), e(1, 'RUN_ENQUEUED'), e(2, 'SOCKET_CONFIG', 'path=/ping;actual_sndbuf=2'),
              e(3, 'SOCKET_CONFIG', 'path=/donate_data;requested_sndbuf=16384;actual_sndbuf=16384')]
        self.assertEqual(g.donation_sndbuf(ok), 16384)
        self.assertEqual(g.donation_sndbuf([e(1, 'RUN_ENQUEUED'), e(2, 'SOCKET_CONFIG', 'v=2;request=x;attempt=1;requested_sndbuf=16384;actual_sndbuf=16384')]), 16384)
        self.assertIsNone(g.donation_sndbuf([e(0, 'SOCKET_CONFIG', 'path=/donate_data;actual_sndbuf=9'), e(1, 'RUN_ENQUEUED')]))

    def test_run(self):
        d = Path(tempfile.mkdtemp()); (d / 'sink').mkdir()
        P = {'stockcancel16': 8794, 'fenced': 8797}
        (d / 'meta.json').write_text(json.dumps({'ports': P, 'variants': ['stockcancel16', 'fenced'], 'marker': M}))
        acts = [{'a': h, 'ok': True} for h in ('grant', 'insert', 'run', 'withdraw')]
        tr = lambda k, v, ev: {'trial': f'g3app-{k:03d}-{v}', 'k': k, 'variant': v, 'actions': acts, 'events': ev, 'device_alive_end': True}
        sc = lambda: [e(0, 'RUN_ENQUEUED'), e(1, 'DONATION_START'), e(2, 'SOCKET_CONFIG', 'path=/donate_data;actual_sndbuf=16384'), e(3, 'WITHDRAW_REQUEST'),
                      e(4, 'CANCEL_DONE', 'calls=1'), e(5, 'WITHDRAW_DONE'), e(6, 'DONATION_ERROR', 'error=Canceled')]
        fe = lambda: [e(0, 'RUN_ENQUEUED'), e(1, 'DONATION_START'), e(2, 'SOCKET_CONFIG', 'v=2;actual_sndbuf=16384'), e(3, 'WITHDRAW_REQUEST'),
                      e(5, 'WITHDRAW_DONE'), e(6, 'BLOCK'), e(7, 'DONATION_BLOCKED')]
        rows = [tr(0, 'stockcancel16', sc()), tr(0, 'fenced', fe()), tr(1, 'stockcancel16', sc()), tr(1, 'fenced', fe())]
        (d / 'trials.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        (d / 'marker.jsonl').write_text(''.join(json.dumps({'id': r['trial'] + '-start', 'host_ns': 100 * (i + 1) - 50}) + '\n' + json.dumps({'id': r['trial'], 'host_ns': 100 * (i + 1)}) + '\n' for i, r in enumerate(rows)))
        # sink: stockcancel16 trial 0 complete after its marker (100); fenced trial 1 complete after its marker (400)
        (d / 'sink/ingest.jsonl').write_text(json.dumps({'port': 8794, 'path': 'donate_data', 'complete': True, 'host_ns': 150}) + '\n'
                                             + json.dumps({'port': 8797, 'path': 'donate_data', 'complete': True, 'host_ns': 450}) + '\n')
        F = []
        def mark(sp, tid): F.extend([dict(src=G, dst=H, sport=sp, dport=M, flags=pc.SYN), dict(src=G, dst=H, sport=sp, dport=M, flags=pc.ACK, payload=(tid + '\n').encode())])
        for i, r in enumerate(rows):
            mark(50000 + 2 * i, r['trial'] + '-start'); F.append(dict(src=G, dst=H, sport=40000 + i, dport=P[r['variant']], payload=b'x' * 1000))
            mark(50001 + 2 * i, r['trial'])
            if i == 0: F.append(dict(src=G, dst=H, sport=40000 + i, dport=P[r['variant']], payload=b'x' * 300))
        pc.write(d / 'capture.pcap', F)
        subprocess.run([sys.executable, str(HERE / 'analyze_g3app5.py'), str(d), '--out', str(d / 'ana')], check=True, capture_output=True)
        s = json.loads((d / 'ana/g3app5-summary.json').read_text()); b = s['builds']
        self.assertEqual((b['stockcancel16']['receiver_complete_after_ack'], b['stockcancel16']['receiver_trials']), (1, 2))
        self.assertEqual(b['fenced']['receiver_complete_after_ack'], 1)
        self.assertEqual((b['stockcancel16']['sent_after_ack'], b['stockcancel16']['after_marker_bytes_sum']), (1, 300))
        self.assertEqual(b['stockcancel16']['after_marker_by_placement']['during']['bytes_sum'], 300)
        self.assertEqual(b['stockcancel16']['cancel'], {'cut_in_flight': 2, 'not_cut': 0, 'no_call': 0})
        self.assertEqual(b['stockcancel16']['donation_sndbuf'], {'16384': 2}); self.assertEqual(b['fenced']['donation_sndbuf'], {'16384': 2})
        self.assertEqual(s['paired']['stockcancel16_vs_fenced']['receiver_complete_after_ack'],
                         {'stockcancel16=0/fenced=1': 1, 'stockcancel16=1/fenced=0': 1})


if __name__ == '__main__':
    unittest.main()
