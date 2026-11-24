#!/usr/bin/env python3
"""Unit test (24/11, before any phone-r4 AirGuard run) for the phone fault rules in analyze_airguard.validity:
plans recorded with --phone need net_verified_down (netloss), kill_verified (kill) and a boot_completed action (reboot);
plans without the phone flag (emulator B2 / G2b) are judged exactly as before."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import analyze_airguard as g

V = ('stock', 'fenced')
def plan(sched, phone=True, **kw):
    acts = [{'a': 'withdraw', 'variant': v, 'ok': True} for v in V] + kw.pop('acts', [])
    p = {'trial': f'{sched[:3]}000', 'schedule': sched, 'actions': acts, 'device_alive_end': True, **kw}
    if phone: p['phone'] = True
    return p
DEV = {('net000', v): [1] for v in V} | {('kil000', v): [1] for v in V} | {('reb000', v): [1] for v in V} | {('pen000', v): [1] for v in V}


class Phone(unittest.TestCase):
    def test_netloss(self):
        self.assertEqual(g.validity(plan('netloss'), DEV), 'net cut not verified')
        self.assertEqual(g.validity(plan('netloss', net_verified_down=False), DEV), 'net cut not verified')
        self.assertIsNone(g.validity(plan('netloss', net_verified_down=True), DEV))
        self.assertIsNone(g.validity(plan('netloss', phone=False), DEV))          # emulator: unchanged

    def test_kill(self):
        self.assertEqual(g.validity(plan('kill', kill_verified=False), DEV), 'kill not verified')
        self.assertIsNone(g.validity(plan('kill', kill_verified=True), DEV))
        self.assertIsNone(g.validity(plan('kill', phone=False), DEV))

    def test_reboot(self):
        self.assertEqual(g.validity(plan('reboot'), DEV), 'reboot not completed')
        self.assertIsNone(g.validity(plan('reboot', acts=[{'a': 'boot_completed', 's': 30}]), DEV))
        self.assertIsNone(g.validity(plan('reboot', phone=False), DEV))

    def test_pending(self):
        self.assertIsNone(g.validity(plan('pending'), DEV))


if __name__ == '__main__':
    unittest.main()
