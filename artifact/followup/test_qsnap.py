#!/usr/bin/env python3
"""Unit test for qsnap.parse (P2)."""
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent)); import qsnap

SNAP = """qdisc prio 1: root refcnt 2 bands 3 priomap 1 1 1
 Sent 999 bytes 9 pkt (dropped 0, overlimits 0 requeues 0)
 backlog 3000b 2p requeues 0
qdisc pfifo 10: parent 1:1 limit 1000p
 Sent 60 bytes 1 pkt (dropped 0, overlimits 0 requeues 0)
 backlog 0b 0p requeues 0
qdisc netem 20: parent 1:2 limit 10000 delay 118ms rate 128Kbit
 Sent 900 bytes 8 pkt (dropped 0, overlimits 0 requeues 0)
 backlog 3000b 2p requeues 0
/proc/net/tcp:   5: 0F02000A:A1B2 0202000A:225E 01 00001000:00000000 01:00000014 00000000 10061 0 1 1 ffff 20 4 30 10 -1
/proc/net/tcp6:  1: 0000000000000000FFFF00000F02000A:A1B3 0000000000000000FFFF00000202000A:225E 08 00000200:00000000 00:00000000 00000000 10061 0 2 1 ffff
"""


class QSnap(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(qsnap.parse(SNAP), {'netem_backlog_bytes': 3000, 'netem_backlog_pkts': 2, 'tx_queue_bytes': 0x1000 + 0x200})
        self.assertIsNone(qsnap.parse(''))
        self.assertEqual(qsnap.parse('qdisc prio 1: root')['tx_queue_bytes'], 0)


if __name__ == '__main__':
    unittest.main()
