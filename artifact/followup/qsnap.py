#!/usr/bin/env python3
"""Group 3 P2 (leader-approved 22/11, pre-registered for P3/P4): parse the queue snapshot race_suite.py --qsnap takes right
after the withdraw broadcast returns (host-timed, after WITHDRAW_ACK and the marker; not at the ack itself).
Per trial: netem band backlog (bytes, packets) of qdisc 20: and the send queue (tx_queue, bytes) of guest TCP sockets to
:8798 from /proc/net/tcp{,6}. Descriptive per (profile, mode[, sndbuf]): median, nearest-rank p95, max; trials without a
snapshot are counted. Usage: qsnap.py <run dir> [more dirs] [--out DIR]
"""
import argparse, collections, gzip, json, re, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ART / 'followup'), str(ART / 'scripts')]
from analyze_g2close import order_stats  # noqa: E402


def parse(snap):
    """-> {'netem_backlog_bytes', 'netem_backlog_pkts', 'tx_queue_bytes'} or None (no snapshot)."""
    if not snap: return None
    m = re.search(r'qdisc netem 20:.*?backlog (\d+)b (\d+)p', snap, re.S)
    tx = 0
    for line in snap.splitlines():
        f = line.split(':', 1)[-1].split() if line.startswith('/proc/') else line.split()
        if len(f) > 4 and re.fullmatch(r'[0-9A-Fa-f]+:[0-9A-Fa-f]+', f[4] or '') and f[2].upper().endswith(':225E'):
            tx += int(f[4].split(':')[0], 16)
    return {'netem_backlog_bytes': int(m[1]) if m else None, 'netem_backlog_pkts': int(m[2]) if m else None, 'tx_queue_bytes': tx}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--out', required=True); a = ap.parse_args()
    cells = collections.defaultdict(list); missing = collections.Counter()
    for dd in a.dirs:
        d = Path(dd); op = (lambda p: open(p)) if (d / 'trials.jsonl').exists() else (lambda p: gzip.open(str(p) + '.gz', 'rt'))
        sb = json.loads((d / 'meta.json').read_text()).get('sndbuf', 16384)
        for l in op(d / 'trials.jsonl'):
            r = json.loads(l); k = f"{r['profile']}/{r['mode']}/sndbuf={r.get('sndbuf', sb)}"; q = parse(r.get('qsnap'))
            if q is None: missing[k] += 1
            else: cells[k].append(q)
    out = {k: {'trials': len(v), 'missing': missing[k], **{f: order_stats([x[f] for x in v if x[f] is not None]) for f in ('netem_backlog_bytes', 'tx_queue_bytes')}}
           for k, v in sorted(cells.items())}
    Path(a.out).mkdir(parents=True, exist_ok=True); (Path(a.out) / 'qsnap-summary.json').write_text(json.dumps({'dirs': a.dirs, 'cells': out}, indent=1) + '\n')
    print(json.dumps(out)[:600])


if __name__ == '__main__':
    main()
