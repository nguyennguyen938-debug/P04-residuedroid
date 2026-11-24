#!/usr/bin/env python3
"""G3a/G3b method audit — EXPLORATORY, not pre-registered (written 22/11 after the G3a/G3b outcomes were read, on the user's
request to check the method). It adds no trial, drops no trial and changes no pre-registered number; the same rules apply to
every arm. Uses the same trials as analyze_g3race.py (complete blocks, B10 validity, first N per (profile, mode)).

Checks:
  1. pairing: same u per (block, profile, size) in every arm; WRITE_ATTEMPT ties with W; process of the withdrawal.
  2. exposure: where W fell, on the device clock, relative to the request:
       before the first WRITE_ATTEMPT | during the writes (first WRITE_ATTEMPT <= W < REQUEST_HANDED_OFF, or no handoff) |
       after the handoff but before the end event | after the end event.
     "exposed" = during the writes; primary count (after W) split by exposed / not exposed.
     Timing components (medians): WITHDRAW_REQUEST - SOCKET_CONFIG, WITHDRAW_DURABLE - WITHDRAW_REQUEST, u*D (s).
  4. capture by phase (C, issue #7 22/11): per W phase, matched trials, TCP new bytes after the marker and, with
     capture-tls.jsonl, TLS application_data bytes after the marker (trials cut vs requests handed off before W).
  3. capture: matched trials whose after-marker bytes are all small (< 200 B, i.e. no full data segment; e.g. TLS alert or
     close records), so that "trials with bytes after the marker" can be read with and without them.
Output: results/round3/g3race/analysis/g3race-audit.json.
Usage: audit_g3race.py <final dir> [more dirs] [--out DIR] [--n 30] [--marker 8799]
"""
import argparse, collections, gzip, json, statistics, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ART / 'followup'), str(ART / 'scripts')]
import analyze_g3race as g  # noqa: E402
from analyze_race import validity  # noqa: E402
from analyze_g2close import first, own  # noqa: E402

SMALL = 200


def phase(r):
    ev = own(r); W = first(ev, 'WITHDRAW_DURABLE'); h = first(ev, 'REQUEST_HANDED_OFF')
    wa = [e['mono_ns'] for e in ev if e['kind'] == 'WRITE_ATTEMPT']
    end = next((e['mono_ns'] for e in ev if e['kind'] in ('SEND_OK', 'SEND_ERROR', 'EARLY_BLOCK')), None)
    if W is None: return 'no W'
    if not wa or W < wa[0]: return 'before writes'
    if h is None or W < h: return 'during writes'
    if end is None or W < end: return 'after handoff'
    return 'after end'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--out', default=str(ART / 'results/round3/g3race/analysis'))
    ap.add_argument('--n', type=int, default=30); ap.add_argument('--marker', type=int, default=8799); a = ap.parse_args()
    rows, caps, tlss = [], {}, {}
    for k, dd in enumerate(a.dirs):
        d = Path(dd); op = (lambda p: open(p)) if (d / 'trials.jsonl').exists() else (lambda p: gzip.open(str(p) + '.gz', 'rt'))
        rs = [dict(json.loads(l), _dir=k) for l in op(d / 'trials.jsonl') if l.strip()]
        meta = json.loads((d / 'meta.json').read_text())
        cells = len(meta['profiles']) * len(meta['modes']) * len(meta['sizes']); per = collections.Counter(r['block'] for r in rs)
        rows += [r for r in rs if per[r['block']] == cells]
        pc = d / 'capture.pcap' if (d / 'capture.pcap').exists() else d / 'capture-slim.pcap'
        caps[k] = g.capture(pc, a.marker) if pc.exists() else None
        tf = d / 'capture-tls-v2.jsonl' if (d / 'capture-tls-v2.jsonl').exists() else d / 'capture-tls.jsonl'; tlss[k] = g.tls_records.load(tf) if tf.exists() else None  # v2 (23/11): capture-tls.jsonl written by the autorun post step before the emulator closed the pcap; v2 from the complete pcap
    valid = sorted((r for r in rows if not validity(r)), key=lambda r: (r['block'], r['trial']))
    cells = collections.defaultdict(list)
    for r in valid: cells[r['profile'], r['mode']].append(r)
    used = [r for rs in cells.values() for r in rs[:a.n]]
    u = collections.defaultdict(set)
    for r in used: u[r['block'], r['profile'], r['size']].add(round(r['u'], 9))
    ties = sum(e['mono_ns'] == first(own(r), 'WITHDRAW_DURABLE') for r in used for e in own(r) if e['kind'] == 'WRITE_ATTEMPT')
    pid = collections.Counter()
    for r in used:
        ev = own(r); pid[r['mode'] + (': same process' if {e['pid'] for e in ev if e['kind'] == 'WITHDRAW_DURABLE'} == {e['pid'] for e in ev if e['kind'] == 'SOCKET_CONFIG'} else ': other process')] += 1
    med = lambda xs: round(statistics.median(xs), 4) if xs else None
    out = {}
    for (prof, mode), rs in sorted(cells.items()):
        rs = rs[:a.n]; ph = [phase(r) for r in rs]; w = [bool(g.after_w(r)) for r in rs]
        comp = []
        for r in rs:
            ev = own(r); sc, rq, W = first(ev, 'SOCKET_CONFIG'), first(ev, 'WITHDRAW_REQUEST'), first(ev, 'WITHDRAW_DURABLE')
            if None not in (sc, rq, W): comp.append(((rq - sc) / 1e9, (W - rq) / 1e9, r['u'] * r['D_s']))
        c = {'trials': len(rs), 'phase': dict(collections.Counter(ph)),
             'exposed': ph.count('during writes'),
             'exposed_by_size': {str(z): sum(p == 'during writes' for r, p in zip(rs, ph) if r['size'] == z) for z in sorted({r['size'] for r in rs})},
             'after_w_exposed_by_size': {str(z): sum(x for r, x, p in zip(rs, w, ph) if r['size'] == z and p == 'during writes') for z in sorted({r['size'] for r in rs})},
             'after_w_exposed': sum(x for x, p in zip(w, ph) if p == 'during writes'),
             'after_w_not_exposed': sum(x for x, p in zip(w, ph) if p != 'during writes'),
             'median_request_minus_socket_s': med([x[0] for x in comp]), 'median_durable_minus_request_s': med([x[1] for x in comp]),
             'median_uD_s': med([x[2] for x in comp])}
        if caps.get(rs[0]['_dir']) is not None or any(caps.values()):
            qp = [(phase(r), g.cap_measure(r, g.secondary(r, set()), *caps[r['_dir']], tls=tlss.get(r['_dir']))) for r in rs if caps[r['_dir']]]
            q = [x for _, x in qp]; m = [x for x in q if x['status'] == 'matched']
            byp = {}
            for ph_, x in qp:
                if x['status'] != 'matched': continue
                b = byp.setdefault(ph_, {'trials': 0, 'trials_new_bytes_after_marker': 0, 'after_marker_new_bytes': 0})
                b['trials'] += 1; b['trials_new_bytes_after_marker'] += x['after_marker_new_bytes'] > 0; b['after_marker_new_bytes'] += x['after_marker_new_bytes']
                if 'after_marker_app_bytes' in x: b['after_marker_app_bytes'] = b.get('after_marker_app_bytes', 0) + x['after_marker_app_bytes']
            c['capture_by_phase'] = dict(sorted(byp.items()))
            c['capture_trials_after_marker'] = sum(x['after_marker_bytes'] > 0 for x in m)
            c['capture_trials_after_marker_small_only'] = sum(0 < x['after_marker_bytes'] < SMALL for x in m)
            c['capture_trials_after_marker_ge_small'] = sum(x['after_marker_bytes'] >= SMALL for x in m)
        out[f'{prof}/{mode}'] = c
    Path(a.out).mkdir(parents=True, exist_ok=True)
    res = {'exploratory': True, 'dirs': a.dirs, 'trials': len(used),
           'cells_with_differing_u_across_arms': sum(len(v) > 1 for v in u.values()), 'paired_cells': len(u),
           'write_attempt_ties_with_W': ties, 'withdrawal_process': dict(sorted(pid.items())), 'small_bytes_threshold': SMALL, 'cells': out}
    (Path(a.out) / 'g3race-audit.json').write_text(json.dumps(res, indent=1) + '\n')
    print(json.dumps({k: v for k, v in res.items() if k != 'cells'}))
    for k, c in out.items(): print(k, {x: c[x] for x in ('exposed', 'after_w_exposed', 'after_w_not_exposed', 'median_request_minus_socket_s', 'median_uD_s', 'capture_trials_after_marker', 'capture_trials_after_marker_small_only') if x in c})


if __name__ == '__main__':
    main()
