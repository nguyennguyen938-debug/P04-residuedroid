#!/usr/bin/env python3
"""B4 + test 5 analysis (artifact/plans/b4-card.md), fixed before the final run.

Valid trial: no harness_error; every sender ended with SEND_OK (tenant 2 probes never affect tenant 1, so a SEND_ERROR is
an environment failure); all 3 probes logged WITHDRAW_REQUEST and WITHDRAW_ACK. First N valid per cell in block order.
Per cell: probe ack latency (device clock, ms) median / nearest-rank p95 / max over all probes; CPU ms per MiB from the
SEND_OK detail of 1-sender cells only (process CPU is process-wide, so it is not attributable per sender when S > 1).
Keys (render_tests.py): sweepAckSmallMs (1 KiB, 1 sender), sweepAckLargeMs (64 KiB, 16 senders), sweepCpuSmall /
sweepCpuLarge (1 KiB / 64 KiB, 1 sender). Descriptive order statistics, not bounds. Process CPU is not energy.
Usage: analyze_sweep.py <run dir>... [--out DIR] [--n 20]
"""
import argparse, collections, json, math, statistics
from pathlib import Path

ART = Path(__file__).resolve().parents[1]


def fields(s): return dict(x.split('=', 1) for x in (s or '').split(';') if '=' in x)
def p95(xs): xs = sorted(xs); return xs[min(len(xs) - 1, max(0, math.ceil(.95 * len(xs)) - 1))] if xs else None


def senders_of(r): return [f"{r['trial']}-{k}" for k in range(r['senders'])]


def validity(r):
    if r.get('harness_error'): return 'harness error'
    ev = r.get('events', [])
    for s in senders_of(r):
        if not any(e['trial'] == s and e['kind'] == 'SEND_OK' for e in ev): return 'sender did not complete'
    for k in range(len(r.get('probes', [])) or 3):
        pid = f"{r['trial']}-probe{k}"
        if not all(any(e['trial'] == pid and e['kind'] == kind for e in ev) for kind in ('WITHDRAW_REQUEST', 'WITHDRAW_ACK')): return 'probe incomplete'
    if r.get('probe_mode') == 'overlap' and not acks(r): return 'no probe under load'
    return None


def acks(r):
    """v1 (fixed): all 3 probes. v2 (overlap): only probes whose request lies inside the send window (first sender event to
    last SEND_OK, device clock) — the load the estimand is about."""
    ev = r['events']; out = []
    ids = senders_of(r); start = min((e['mono_ns'] for e in ev if e['trial'] in ids), default=0)
    end = max((e['mono_ns'] for e in ev if e['trial'] in ids and e['kind'] == 'SEND_OK'), default=0)
    for k in range(len(r.get('probes', [])) or 3):
        pid = f"{r['trial']}-probe{k}"
        req = [e['mono_ns'] for e in ev if e['trial'] == pid and e['kind'] == 'WITHDRAW_REQUEST']
        ack = [e['mono_ns'] for e in ev if e['trial'] == pid and e['kind'] == 'WITHDRAW_ACK']
        if not req or not ack: continue
        if r.get('probe_mode') == 'overlap' and not (start <= min(req) <= end): continue
        out.append((min(ack) - min(req)) / 1e6)
    return out


def cpu_per_mib(r):
    ok = next(e for e in r['events'] if e['trial'] == senders_of(r)[0] and e['kind'] == 'SEND_OK'); f = fields(ok['detail'])
    return int(f['process_cpu_ms']) / (int(f['payload_bytes']) / 1048576)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--out', default=str(ART / 'results/round3/b4/analysis'))
    ap.add_argument('--n', type=int, default=20); a = ap.parse_args()
    import gzip, io, subprocess
    def op(d):                             # raw file if present; else the committed gzip, whole or split into byte parts
        d = Path(d); parts = sorted(d.glob('trials.jsonl.gz.part-*'))
        if (d / 'trials.jsonl').exists(): return open(d / 'trials.jsonl')
        if (d / 'trials.jsonl.gz').exists() or not parts: return gzip.open(d / 'trials.jsonl.gz', 'rt')
        return io.TextIOWrapper(gzip.GzipFile(fileobj=subprocess.Popen(['cat', *map(str, parts)], stdout=subprocess.PIPE).stdout))
    rows = [json.loads(l) for d in a.dirs for l in op(d) if l.strip()]   # large raw files are committed gzip-compressed
    invalid = [{'trial': r['trial'], 'reason': w} for r in rows if (w := validity(r))]
    cells = collections.defaultdict(list)
    for r in sorted((r for r in rows if not validity(r)), key=lambda r: r['block']): cells[r['chunk_kib'], r['senders']].append(r)
    out = {}
    for (c, s), rs in sorted(cells.items()):
        used = rs[:a.n]; lat = [x for r in used for x in acks(r)]
        cpu = [cpu_per_mib(r) for r in used] if s == 1 else []
        out[f'{c}KiB/{s}'] = {'trials': len(used), 'unused': len(rs) - len(used), 'ack_ms_median': statistics.median(lat) if lat else None,
                              'ack_ms_p95': p95(lat), 'ack_ms_max': max(lat) if lat else None,
                              'cpu_ms_per_mib_median': statistics.median(cpu) if cpu else None}
    g = lambda k, f: out.get(k, {}).get(f)
    keys = {'sweepAckSmallMs': g('1KiB/1', 'ack_ms_median'), 'sweepAckLargeMs': g('64KiB/16', 'ack_ms_median'),
            'sweepCpuSmall': g('1KiB/1', 'cpu_ms_per_mib_median'), 'sweepCpuLarge': g('64KiB/1', 'cpu_ms_per_mib_median')}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'sweep-summary.json').write_text(json.dumps({'logged': len(rows), 'invalid': invalid, 'cells': out, 'keys': keys}, indent=1) + '\n')
    print(f"logged {len(rows)}, invalid {len(invalid)}, cells {len(out)}")


if __name__ == '__main__':
    main()
