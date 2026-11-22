#!/usr/bin/env python3
"""Unit test for analyze_g3app.py on a synthetic run (capture windows, receiver after ack, validity); before any G3c trial."""
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import pcapmin as pc

G, H, M = '10.0.2.15', '10.0.2.2', 8799


class G3App(unittest.TestCase):
    def test_run(self):
        d = Path(tempfile.mkdtemp()); (d / 'sink').mkdir()
        (d / 'meta.json').write_text(json.dumps({'ports': {'stock': 8796, 'fenced': 8797}, 'variants': ['stock', 'fenced'], 'marker': M}))
        ok = lambda a: {'a': a, 'ok': True}
        def trial(tid, v, ev, err=False):
            acts = [ok('grant'), ok('insert'), ok('run'), ok('withdraw')] + ([{'a': 'trial_error'}] if err else [])
            return {'trial': tid, 'k': 0, 'variant': v, 'actions': acts, 'events': ev, 'device_alive_end': True}
        e = lambda t, k, det='': {'kind': k, 'mono_ns': t, 'detail': det}
        rows = [trial('g3app-000-stock', 'stock', [e(1, 'DONATION_START'), e(2, 'WITHDRAW_REQUEST'), e(3, 'WITHDRAW_DONE'), e(9, 'DONATION_OK')]),
                trial('g3app-000-fenced', 'fenced', [e(1, 'DONATION_START'), e(2, 'WITHDRAW_REQUEST'), e(3, 'WITHDRAW_DONE'), e(4, 'BLOCK'), e(5, 'DONATION_BLOCKED')]),
                trial('g3app-001-fenced', 'fenced', [e(1, 'DONATION_OK')], err=True)]
        (d / 'trials.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        (d / 'marker.jsonl').write_text(json.dumps({'id': 'g3app-000-stock', 'host_ns': 100}) + '\n' + json.dumps({'id': 'g3app-000-fenced', 'host_ns': 300}) + '\n')
        (d / 'sink/ingest.jsonl').write_text(json.dumps({'port': 8796, 'path': 'donate_data', 'complete': True, 'host_ns': 200}) + '\n')
        P = []
        def mark(sp, tid): P.extend([dict(src=G, dst=H, sport=sp, dport=M, flags=pc.SYN), dict(src=G, dst=H, sport=sp, dport=M, flags=pc.ACK, payload=(tid + '\n').encode())])
        mark(50000, 'g3app-000-stock-start'); P.append(dict(src=G, dst=H, sport=40000, dport=8796, payload=b'x' * 1000))
        mark(50001, 'g3app-000-stock'); P.append(dict(src=G, dst=H, sport=40000, dport=8796, payload=b'x' * 700))
        mark(50002, 'g3app-000-fenced-start'); P.append(dict(src=G, dst=H, sport=40000, dport=8796, payload=b'y' * 50))   # next window: not stock's
        P.append(dict(src=G, dst=H, sport=40001, dport=8797, payload=b'x' * 4096)); mark(50003, 'g3app-000-fenced')
        pc.write(d / 'capture.pcap', P)
        subprocess.run([sys.executable, str(HERE / 'analyze_g3app.py'), str(d), '--out', str(d / 'ana')], check=True, capture_output=True)
        s = json.loads((d / 'ana/g3app-summary.json').read_text()); b = s['builds']
        self.assertEqual(len(s['invalid']), 1)
        self.assertEqual((b['stock']['sent_after_ack'], b['stock']['after_marker_bytes'], b['stock']['receiver_complete_after_ack']), (1, 700, 1))
        self.assertEqual((b['fenced']['sent_after_ack'], b['fenced']['after_marker_bytes'], b['fenced']['receiver_complete_after_ack']), (0, 0, 0))
        self.assertEqual(b['stock']['placement'], {'during': 1}); self.assertEqual(s['paired'], {'fenced_vs_stock': {'fenced=0/stock=1': 1}})


if __name__ == '__main__':
    unittest.main()
