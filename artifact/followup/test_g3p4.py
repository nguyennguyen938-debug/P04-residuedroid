#!/usr/bin/env python3
"""Unit test for the P4 complete-block rule (analyze_g3p4.split_blocks; g3p4-card §3), added 23/11 before the P4 analysis ran."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import analyze_g3p4 as a


class T(unittest.TestCase):
    def test_cells_per_block(self):
        m = {'profiles': ['edge', 'umts'], 'modes': ['fence', 'fence-abort'], 'sizes': [2097152], 'sndbufs': '0,16384,65536'}
        self.assertEqual(a.cells_per_block(m), 12)
        self.assertEqual(a.cells_per_block({**m, 'sndbufs': None}), 4)
        self.assertIsNone(a.cells_per_block({}))

    def test_split(self):
        rs = [{'block': 15, 'trial': f'a{i}'} for i in range(12)] + [{'block': 16, 'trial': f'b{i}'} for i in range(3)]
        keep, cut = a.split_blocks(rs, 12)
        self.assertEqual(len(keep), 12); self.assertEqual({r['block'] for r in keep}, {15})
        self.assertEqual([r['trial'] for r in cut], ['b0', 'b1', 'b2'])
        self.assertEqual(a.split_blocks(rs, None), (rs, []))


if __name__ == '__main__':
    unittest.main()
