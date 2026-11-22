#!/usr/bin/env python3
"""Group 3 P4 analysis (plans/g3p4-card.md), written 22/11 before any P4 trial. Leader-approved in issue #7.
Run: race_suite.py --g3 --marker --capture --qsnap --sndbufs 0,16384,65536 (P4 build), modes fence, fence-abort, profiles
edge and umts, size 2 MiB, seed race-20261119. Per (profile, mode, sndbuf), trials valid by B10, first N in block order:
  Primary (descriptive): among trials whose W fell during the writes (audit_g3race.phase), TCP new bytes and TLS
    application_data bytes guest -> receiver after the marker (capture-tls.jsonl from tls_records.py), summed and per trial
    (median, nearest-rank p95, max); trials with application_data after the marker.
  Secondary: the same for the other phases; trials accepted after W (G3a primary; expected 0 for both arms, reported as
    counts); RST after the marker; actual_sndbuf from SOCKET_CONFIG; write throughput before W =
    BYTES_ACCEPTED before W / (W - SOCKET_CONFIG) on the device clock (bytes/s); queue snapshot (qsnap.parse) netem backlog
    and socket send queue. Paired per (block, profile): fence-abort vs fence application_data bytes, per sndbuf.
No p-values. Output: <out>/g3p4-summary.json. Usage: analyze_g3p4.py <run dir> [more] [--out DIR] [--n 30]
"""
import argparse, collections, gzip, json, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ART / 'followup'), str(ART / 'scripts')]
import analyze_g3race as g  # noqa: E402
import qsnap  # noqa: E402
import tls_records  # noqa: E402
from analyze_g2close import first, order_stats, own  # noqa: E402
from analyze_race import fields, validity  # noqa: E402
from audit_g3race import phase  # noqa: E402


def throughput(r):
    ev = own(r); W = first(ev, 'WITHDRAW_DURABLE'); sc = first(ev, 'SOCKET_CONFIG')
    if W is None or sc is None or W <= sc: return None
    acc = sum(int(fields(e['detail']).get('n', 0)) for e in ev if e['kind'] == 'BYTES_ACCEPTED' and e['mono_ns'] <= W)
    return acc / ((W - sc) / 1e9)


def actual_sndbuf(r):
    e = next((e for e in own(r) if e['kind'] == 'SOCKET_CONFIG'), None)
    return int(fields(e['detail']).get('actual_sndbuf', -1)) if e else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--out', required=True)
    ap.add_argument('--n', type=int, default=30); ap.add_argument('--marker', type=int, default=8799); a = ap.parse_args()
    rows, caps, tlss = [], {}, {}
    for k, dd in enumerate(a.dirs):
        d = Path(dd); op = (lambda p: open(p)) if (d / 'trials.jsonl').exists() else (lambda p: gzip.open(str(p) + '.gz', 'rt'))
        rows += [dict(json.loads(l), _dir=k) for l in op(d / 'trials.jsonl') if l.strip()]
        pc = d / 'capture.pcap' if (d / 'capture.pcap').exists() else d / 'capture-slim.pcap'
        caps[k] = g.capture(pc, a.marker) if pc.exists() else None
        tf = d / 'capture-tls.jsonl'; tlss[k] = tls_records.load(tf) if tf.exists() else None
    invalid = [{'trial': r['trial'], 'reason': why} for r in rows if (why := validity(r))]
    cells = collections.defaultdict(list)
    for r in sorted((r for r in rows if not validity(r)), key=lambda r: (r['block'], r['trial'])): cells[r['profile'], r['mode'], r.get('sndbuf', 16384)].append(r)
    out, app_by = {}, {}
    for (prof, mode, sb), rs in sorted(cells.items()):
        used = rs[:a.n]; byp = collections.defaultdict(lambda: {'trials': 0, 'new': [], 'app': [], 'rst': 0})
        for r in used:
            ph = phase(r); q = g.cap_measure(r, g.secondary(r, set()), *caps[r['_dir']], tls=tlss.get(r['_dir'])) if caps[r['_dir']] else {'status': 'no capture'}
            b = byp[ph]; b['trials'] += 1
            if q['status'] == 'matched':
                b['new'].append(q['after_marker_new_bytes']); b['rst'] += q['rst_after_marker']
                if 'after_marker_app_bytes' in q: b['app'].append(q['after_marker_app_bytes']); app_by[r['block'], prof, mode, sb, ph] = q['after_marker_app_bytes']
        qs = [x for r in used if (x := qsnap.parse(r.get('qsnap')))]
        out[f'{prof}/{mode}/sndbuf={sb}'] = {
            'trials': len(used), 'unused': len(rs) - len(used), 'after_w': sum(bool(g.after_w(r)) for r in used),
            'actual_sndbuf': dict(collections.Counter(str(actual_sndbuf(r)) for r in used)),
            'throughput_before_w_Bps': order_stats([t for r in used if (t := throughput(r)) is not None]),
            'by_phase': {ph: {'trials': b['trials'], 'matched': len(b['new']), 'new_bytes_sum': sum(b['new']), 'new_bytes': order_stats(b['new']),
                              'app_trials': len(b['app']), 'trials_app_after_marker': sum(x > 0 for x in b['app']), 'app_bytes_sum': sum(b['app']),
                              'app_bytes': order_stats(b['app']), 'rst_after_marker': b['rst']} for ph, b in sorted(byp.items())},
            'qsnap': {'n': len(qs), 'netem_backlog_bytes': order_stats([x['netem_backlog_bytes'] for x in qs if x['netem_backlog_bytes'] is not None]),
                      'tx_queue_bytes': order_stats([x['tx_queue_bytes'] for x in qs])}}
    paired = collections.defaultdict(lambda: {'pairs': 0, 'abort_less': 0, 'equal': 0, 'abort_more': 0})
    for (blk, prof, mode, sb, ph), v in app_by.items():
        if mode != 'fence-abort' or ph != 'during writes' or (blk, prof, 'fence', sb, ph) not in app_by: continue
        w = app_by[blk, prof, 'fence', sb, ph]; p = paired[f'{prof}/sndbuf={sb}']; p['pairs'] += 1
        p['abort_less' if v < w else 'equal' if v == w else 'abort_more'] += 1
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'g3p4-summary.json').write_text(json.dumps({'dirs': a.dirs, 'logged': len(rows), 'invalid': invalid, 'cells': out,
        'paired_during_writes_app_bytes': dict(sorted(paired.items()))}, indent=1) + '\n')
    print(f"logged {len(rows)}, invalid {len(invalid)}, cells {[(c, v['trials']) for c, v in out.items()]}")


if __name__ == '__main__':
    main()
