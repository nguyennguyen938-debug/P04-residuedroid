#!/usr/bin/env python3
"""Unit test for analyze_g3cost.py on synthetic cells; before any G3d run."""
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
HERE = Path(__file__).resolve().parent


class G3Cost(unittest.TestCase):
    def test_run(self):
        d = Path(tempfile.mkdtemp()); (d / 'meta.json').write_text(json.dumps({'uid': 10123, 'phone': {}}))
        ok = lambda cpu, ns, b: {'id': 'x', 'end': {'kind': 'SEND_OK', 'detail': f'elapsed_ns={ns};process_cpu_ms={cpu};payload_bytes={b}'}}
        cells = [{'cell': 'c1', 'block': 0, 'mode': 'fence', 'size': 1 << 20, 'uploads': [ok(20, 2000000, 1 << 20), ok(40, 4000000, 1 << 20)], 'bs': '  UID u0a123: 0.5 ( cpu=0.4 )'},
                 {'cell': 'c2', 'block': 0, 'mode': 'early', 'size': 1 << 20, 'uploads': [ok(10, 1000000, 1 << 20), ok(10, 1000000, 1 << 20)], 'bs': 'no reading'},
                 {'cell': 'c3', 'block': 1, 'mode': 'early', 'size': 1 << 20, 'uploads': [{'id': 'y', 'end': None}]}]
        (d / 'cells.jsonl').write_text(''.join(json.dumps(c) + '\n' for c in cells))
        subprocess.run([sys.executable, str(HERE / 'analyze_g3cost.py'), str(d), '--out', str(d / 'a')], check=True, capture_output=True)
        s = json.loads((d / 'a/g3cost-summary.json').read_text()); f = s['cells'][f'fence/{1 << 20}']; e = s['cells'][f'early/{1 << 20}']
        self.assertEqual((f['cpu_ms_per_mib']['median'], f['elapsed_ms']['median'], f['energy_mah_per_mib_est']['median']), (30.0, 3.0, 0.25))
        self.assertEqual((e['cells'], e['cells_without_energy'], len(s['invalid'])), (1, 1, 1))
        self.assertEqual(s['ratios_of_medians'][f'fence/early/{1 << 20}']['cpu_ms_per_mib'], 3.0)


if __name__ == '__main__':
    unittest.main()
