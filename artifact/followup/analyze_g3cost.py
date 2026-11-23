#!/usr/bin/env python3
"""Group 3, test G3d analysis (g3cost-card.md), written 22/11 before any G3d run.

Cell validity (harness fields only): no harness_error and every upload of the cell logged an end event. Upload: SEND_OK =
used; SEND_ERROR / no end = failed (counted, not used). First N valid cells per (arm, size) in block order.
Per (arm, size), descriptive (nearest-rank p95; median = mean of the two middle values for even n):
  process CPU per MiB (process_cpu_ms / payload MiB, per upload): median, p95;
  elapsed per upload (SEND_OK elapsed_ns, device clock, ms): median, p95, max;
  energy estimate per MiB (batterystats model: the app UID's "Estimated power use" mAh of the cell / (uploads x size MiB)):
  median over cells, cells with a reading, cells without (never imputed).
Ratios of medians fence/early and fence/platform per size (descriptive). No p-values.
Usage: analyze_g3cost.py <run dir> [--out results/round3/g3cost/analysis] [--n 20]
"""
import gzip, argparse, collections, json, math, re
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
MIB = 1 << 20


def fields(s): return dict(x.split('=', 1) for x in (s or '').split(';') if '=' in x)


def stats(xs):
    xs = sorted(xs)
    if not xs: return None
    n = len(xs); med = xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2
    return {'n': n, 'median': round(med, 4), 'p95': round(xs[math.ceil(0.95 * n) - 1], 4), 'max': round(xs[-1], 4)}


def mah(bs, uid, checkin=None):
    """The UID's batterystats estimate (mAh): 'UID u0aN: x' (Android <= 13 text), else the Android 15 checkin line
    9,<uid>,l,pwi,uid,<mAh>,... (pilot-3 22/11: the text shows only '  u0aN:'). 0 is a reading; None = no record."""
    m = re.search(rf'UID u0a{uid - 10000}: ([0-9.]+)', bs or '')
    if m: return float(m.group(1))
    m = re.search(rf'^9,{uid},l,pwi,uid,([0-9.]+)', checkin or '', re.M)
    return float(m.group(1)) if m else None


def valid(c):
    """Harness fields only. v3 (22/11): when recorded, the phone must be Awake at the cell's start and end."""
    if c.get('harness_error') or not c['uploads'] or not all(u['end'] for u in c['uploads']): return False
    return all(c[k] == 'mWakefulness=Awake' for k in ('wake_start', 'wake_end') if k in c)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('--out', default=str(ART / 'results/round3/g3cost/analysis'))
    ap.add_argument('--n', type=int, default=20); a = ap.parse_args()
    d = Path(a.dir); meta = json.loads((d / 'meta.json').read_text()); uid = meta['uid']
    op = (lambda p: open(p)) if (d / 'cells.jsonl').exists() else (lambda p: gzip.open(str(p) + '.gz', 'rt'))   # 24/11: large raw committed gzip-compressed
    cells = [json.loads(l) for l in op(d / 'cells.jsonl') if l.strip()]
    by = collections.defaultdict(list)
    for c in sorted(cells, key=lambda c: (c['block'], c['cell'])):
        if valid(c): by[c['mode'], c['size']].append(c)
    out, med = {}, {}
    for (mode, size), cs in sorted(by.items()):
        used = cs[:a.n]; ok = [u['end'] for c in used for u in c['uploads'] if u['end']['kind'] == 'SEND_OK']
        failed = sum(u['end']['kind'] != 'SEND_OK' for c in used for u in c['uploads'])
        cpu = [int(fields(e['detail'])['process_cpu_ms']) / (int(fields(e['detail'])['payload_bytes']) / MIB) for e in ok]
        el = [int(fields(e['detail'])['elapsed_ns']) / 1e6 for e in ok]
        en = [(x / (len(c['uploads']) * size / MIB)) for c in used if (x := mah(c.get('bs'), uid, c.get('bs_checkin'))) is not None]
        out[f'{mode}/{size}'] = {'cells': len(used), 'unused_cells': len(cs) - len(used), 'uploads_ok': len(ok), 'uploads_failed': failed,
                                 'cpu_ms_per_mib': stats(cpu), 'elapsed_ms': stats(el), 'energy_mah_per_mib_est': stats(en),
                                 'cells_with_energy': len(en), 'cells_without_energy': len(used) - len(en)}
        med[mode, size] = {k: (out[f'{mode}/{size}'][k] or {}).get('median') for k in ('cpu_ms_per_mib', 'elapsed_ms', 'energy_mah_per_mib_est')}
    ratios = {}
    for size in sorted({s for _, s in med}):
        for o in ('early', 'platform'):
            if ('fence', size) in med and (o, size) in med:
                ratios[f'fence/{o}/{size}'] = {k: round(med['fence', size][k] / med[o, size][k], 3) if med['fence', size][k] is not None and med[o, size][k] else None for k in med['fence', size]}
    invalid = [{'cell': c['cell'], 'reason': c.get('harness_error') or 'upload without end event'} for c in cells if not valid(c)]
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'g3cost-summary.json').write_text(json.dumps({'logged_cells': len(cells), 'invalid': invalid, 'phone': meta.get('phone'),
        'cells': out, 'ratios_of_medians': ratios}, indent=1) + '\n')
    print(f"cells {len(cells)}, invalid {len(invalid)}, {[(k, v['cells']) for k, v in out.items()]}")


if __name__ == '__main__':
    main()
