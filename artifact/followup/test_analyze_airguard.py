#!/usr/bin/env python3
"""Unit test for B2 oracle v3 (analyze_airguard.guest_order), R4.1: every new oracle case has a test."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_airguard import guest_order  # noqa: E402


def ev(kind, ms, detail=''): return {'kind': kind, 'wall_ms': ms, 'detail': detail}
def acc(ms, req, n=100): return ev('BYTES_ACCEPTED', ms, f'v=2;request={req};attempt=1;offset=0;n={n}')


class GuestOrder(unittest.TestCase):
    def test_before(self): self.assertEqual(guest_order([acc(10, 'R'), acc(20, 'R'), ev('WITHDRAW_ACK', 30)], 'R'), 'before')
    def test_after(self): self.assertEqual(guest_order([ev('WITHDRAW_ACK', 30), acc(31, 'R')], 'R'), 'after')
    def test_straddle(self): self.assertEqual(guest_order([acc(10, 'R'), ev('WITHDRAW_ACK', 30), acc(40, 'R')], 'R'), 'straddle')
    def test_equal_ms_is_straddle(self): self.assertEqual(guest_order([ev('WITHDRAW_ACK', 30), acc(30, 'R')], 'R'), 'straddle')
    def test_unmatched_no_event(self): self.assertEqual(guest_order([ev('WITHDRAW_ACK', 30), acc(40, 'X')], 'R'), 'unmatched')
    def test_unmatched_no_id(self): self.assertEqual(guest_order([ev('WITHDRAW_ACK', 30), acc(40, 'R')], None), 'unmatched')
    def test_unmatched_no_ack(self): self.assertEqual(guest_order([acc(40, 'R')], 'R'), 'unmatched')
    def test_zero_bytes_ignored(self): self.assertEqual(guest_order([acc(10, 'R'), ev('WITHDRAW_ACK', 30), acc(40, 'R', n=0)], 'R'), 'before')
    def test_first_ack_used(self): self.assertEqual(guest_order([ev('WITHDRAW_ACK', 30), acc(35, 'R'), ev('WITHDRAW_ACK', 50)], 'R'), 'after')


if __name__ == '__main__':
    unittest.main()
