#!/usr/bin/env python3
"""Unit test (24/11, after the Device Farm reboot pilot pilot-preb ignored adb reboot): analyze_test6.phone_validity marks a
--phone-faults reboot plan invalid unless the uptime restarted (reboot_verified); plans without the field are as before."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.argv = sys.argv[:1]
import analyze_test6 as t

B = [{'a': 'reboot'}, {'a': 'boot_completed', 'boot_s': 0.5}]


class Reboot(unittest.TestCase):
    def test(self):
        self.assertEqual(t.phone_validity({'schedule': 'reboot', 'actions': B, 'reboot_verified': False}), 'reboot not verified')
        self.assertIsNone(t.phone_validity({'schedule': 'reboot', 'actions': B, 'reboot_verified': True}))
        self.assertIsNone(t.phone_validity({'schedule': 'reboot', 'actions': B}))              # earlier logs: unchanged
        self.assertEqual(t.phone_validity({'schedule': 'reboot', 'actions': [{'a': 'reboot'}]}), 'reboot not completed')


if __name__ == '__main__':
    unittest.main()
