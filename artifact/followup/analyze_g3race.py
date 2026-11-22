#!/usr/bin/env python3
"""Group 3, tests G3a + G3b analysis (g3race-card.md), written 22/11 before any G3 trial ran.

Run: race_suite.py --g3 --marker P --capture, modes early, close2, fence, fence-abort, close in the same blocks (B10 v3
protocol). Validity = B10 (`analyze_race.validity`), first N valid per (profile, mode) in block order. Per (profile, mode):
Primary (issue #7 definition): trial "accepted after W" = some BYTES_ACCEPTED n > 0 whose nearest preceding WRITE_ATTEMPT of
  the same trial (device clock, file order on ties) is later than W = the trial's first WITHDRAW_DURABLE. Wilson 95%.
Secondary: violation after the ack (B10 rule, analyze_race.measures); latency WITHDRAW_REQUEST -> WITHDRAW_ACK (median,
  nearest-rank p95, max, ms); uncut requests (handed off before the ack) that the receiver logged complete while the app
  ended SEND_ERROR; cut trials and how many the receiver logged complete; cancellation replies (close, close2); ABORT_ARMED
  (fence-abort). Paired 2x2 per (block, profile, size) for close2 vs fence, close2 vs early, fence-abort vs fence (after W).
G3b capture (capture.pcap; frame order only, host capture time never compared with device time):
  marker of a trial = the marker connection whose payload carries the trial id; its SYN frame = the ack position.
  request connection = SYN guest->:8798 with the trial's SOCKET_LOCAL port, latest before the marker; without SOCKET_LOCAL
  (cut before the handshake) the single SYN to :8798 between the previous marker and this one, else unmatched.
  after-marker = TCP payload bytes guest->receiver on that connection in frames after the marker SYN (all, and new bytes =
  advance of the highest sequence end); RST from the guest after the marker. Concordance per mode: capture after-marker bytes
  > 0 vs the app oracle (violation after the ack). Trials without a marker or without a matched connection are counted, not
  folded in.
Several run directories (a resumed final, g3race-card.md Pilot log): only blocks complete within one directory (every
(profile, mode, size) cell logged there, from that directory's meta.json) are used; others are listed as excluded
('interrupted block'). Each trial is matched against the capture of its own directory.
Usage: analyze_g3race.py <final run dir> [more dirs] [--out results/round3/g3race/analysis] [--n 30] [--marker 8799]
"""
import argparse, collections, gzip, json, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ART / 'followup'), str(ART / 'scripts')]
from analyze_race import fields, measures, validity  # noqa: E402
from analyze_g2close import first, order_stats, own  # noqa: E402
from summarize import wilson  # noqa: E402
import pcapmin  # noqa: E402

RECV = 8798


def after_w(r):
    ev = sorted(enumerate(own(r)), key=lambda x: (x[1]['mono_ns'], x[0]))
    w = first(own(r), 'WITHDRAW_DURABLE')
    if w is None: return None
    last = None
    for _, e in ev:
        if e['kind'] == 'WRITE_ATTEMPT': last = e['mono_ns']
        elif e['kind'] == 'BYTES_ACCEPTED' and int(fields(e['detail']).get('n', 0)) > 0 and last is not None and last > w: return True
    return False


def secondary(r, complete):
    ev = own(r); ack = first(ev, 'WITHDRAW_ACK'); req = first(ev, 'WITHDRAW_REQUEST'); handed = first(ev, 'REQUEST_HANDED_OFF')
    end = next((e['kind'] for e in ev if e['kind'] in ('SEND_OK', 'SEND_ERROR', 'EARLY_BLOCK')), None)
    cut = handed is None or ack < handed
    return {'cut': cut, 'cut_complete': cut and r['trial'] in complete,
            'uncut_complete_send_error': (not cut) and r['trial'] in complete and end == 'SEND_ERROR',
            'latency_ms': (ack - req) / 1e6 if req is not None else None,
            'cancel_done': next((e['detail'] for e in ev if e['kind'] == 'CANCEL_DONE'), None),
            'abort_armed': any(e['kind'] == 'ABORT_ARMED' and 'linger0=true' in e['detail'] for e in ev),
            'local_port': next((int(fields(e['detail'])['local_port']) for e in ev if e['kind'] == 'SOCKET_LOCAL' and int(fields(e['detail']).get('local_port', -1)) > 0), None),
            'marker_sent': any(e['kind'] == 'MARKER_SENT' and 'error=' not in e['detail'] for e in ev)}


def capture(path, marker, guest_to=RECV):
    """-> markers {trial id: frame index of the marker SYN}, conns [(syn frame, sport)], per-sport frames guest->receiver."""
    cur, done, conns, data = {}, [], [], collections.defaultdict(list)   # marker connections keyed by (sport, SYN frame): ports may be reused
    for p in pcapmin.frames(path):
        if p['dport'] == marker:
            if p['flags'] & pcapmin.SYN and not p['flags'] & pcapmin.ACK: cur[p['sport']] = [p['i'], None]
            elif p['len'] and p['sport'] in cur and cur[p['sport']][1] is None:
                cur[p['sport']][1] = p['payload'].split(b'\n')[0].decode(errors='replace'); done.append(cur[p['sport']])
        elif p['dport'] == guest_to:
            if p['flags'] & pcapmin.SYN and not p['flags'] & pcapmin.ACK: conns.append((p['i'], p['sport']))
            data[p['sport']].append(p)
    markers = {}
    for i, tid in done: markers.setdefault(tid, i)                      # an id seen twice: its first marker SYN
    return markers, conns, data


def cap_measure(r, x, markers, conns, data):
    m = markers.get(r['trial'])
    if m is None: return {'status': 'no marker'}
    prev = max((v for v in markers.values() if v < m), default=-1)
    if x['local_port']:
        cand = [(i, sp) for i, sp in conns if sp == x['local_port'] and i < m]
        syn = cand[-1] if cand else None
    else:
        cand = [(i, sp) for i, sp in conns if prev < i < m]; syn = cand[0] if len(cand) == 1 else None
    if syn is None: return {'status': 'no request in capture' if not r.get('events') or x['local_port'] is None and not cand else 'unmatched'}
    nxt = min((i for i, sp in conns if sp == syn[1] and i > syn[0]), default=float('inf'))   # port reuse: stop at the next SYN
    seg = [p for p in data[syn[1]] if syn[0] <= p['i'] < nxt]
    isn = next(p['seq'] for p in seg if p['i'] == syn[0])
    end = lambda p: (p['seq'] - isn) % 2 ** 32 + p['len']
    before = max((end(p) for p in seg if p['i'] < m and p['len']), default=0)
    post = [p for p in seg if p['i'] > m]
    allb = sum(p['len'] for p in post); hi = max((end(p) for p in post if p['len']), default=0)
    return {'status': 'matched', 'after_marker_bytes': allb, 'after_marker_new_bytes': max(0, hi - before),
            'rst_after_marker': any(p['flags'] & pcapmin.RST for p in post), 'fin_after_marker': any(p['flags'] & pcapmin.FIN for p in post)}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dirs', nargs='+'); ap.add_argument('--out', default=str(ART / 'results/round3/g3race/analysis'))
    ap.add_argument('--n', type=int, default=30); ap.add_argument('--marker', type=int, default=8799); a = ap.parse_args()
    rows, complete, caps, interrupted = [], set(), {}, []
    for k, dd in enumerate(a.dirs):
        d = Path(dd)
        op = (lambda p: open(p)) if (d / 'trials.jsonl').exists() else (lambda p: gzip.open(str(p) + '.gz', 'rt'))
        rs = [dict(json.loads(l), _dir=k) for l in op(d / 'trials.jsonl') if l.strip()]
        meta = json.loads((d / 'meta.json').read_text()) if (d / 'meta.json').exists() else {}
        cells = len(meta.get('profiles', [])) * len(meta.get('modes', [])) * len(meta.get('sizes', [])) or None
        per = collections.Counter(r['block'] for r in rs)
        for r in rs:
            if cells and per[r['block']] < cells: interrupted.append({'trial': r['trial'], 'dir': dd, 'reason': 'interrupted block'})
            else: rows.append(r)
        rec = d / 'receiver.jsonl'
        if rec.exists(): complete |= {x['request'] for x in (json.loads(l) for l in rec.read_text().splitlines() if l.strip()) if x.get('event') == 'body' and x.get('complete')}
        pc = d / 'capture.pcap' if (d / 'capture.pcap').exists() else d / 'capture-slim.pcap'   # slim: committed truncated copy (pcap_slim.py)
        caps[k] = capture(pc, a.marker) if pc.exists() else None
    cap = any(caps.values()); pc = Path(a.dirs[0])
    invalid = [{'trial': r['trial'], 'reason': why} for r in rows if (why := validity(r))]
    valid = sorted((r for r in rows if not validity(r)), key=lambda r: (r['block'], r['trial']))
    cells = collections.defaultdict(list)
    for r in valid: cells[r['profile'], r['mode']].append(r)
    out, w_all, viol_all = {}, {}, {}
    for (prof, mode), rs in sorted(cells.items()):
        used = rs[:a.n]; ms = [measures(r) for r in used]; ws = [after_w(r) for r in used]; xs = [secondary(r, complete) for r in used]
        kw = sum(bool(w) for w in ws); kv = sum(m['violation'] for m in ms)
        for r, w, m in zip(used, ws, ms): w_all[r['block'], prof, r['size'], mode] = bool(w); viol_all[r['trial']] = m['violation']
        c = {'trials': len(used), 'unused': len(rs) - len(used),
             'after_w': kw, 'after_w_wilson95': list(wilson(kw, len(used))[1:]) if used else None, 'after_w_no_durable': sum(w is None for w in ws),
             'after_w_by_size': {str(s): sum(bool(w) for r, w in zip(used, ws) if r['size'] == s) for s in sorted({r['size'] for r in used})},
             'violations_after_ack': kv, 'violations_wilson95': list(wilson(kv, len(used))[1:]) if used else None,
             'after_ack_bytes': sum(m['after_ack_bytes'] for m in ms), 'ends': dict(collections.Counter(m['end'] for m in ms)),
             'withdraw_latency_ms': order_stats([x['latency_ms'] for x in xs if x['latency_ms'] is not None]),
             'uncut_receiver_complete_send_error': sum(x['uncut_complete_send_error'] for x in xs),
             'uncut_receiver_complete': sum((not x['cut']) and r['trial'] in complete for r, x in zip(used, xs)),
             'cut': sum(x['cut'] for x in xs), 'cut_receiver_complete': sum(x['cut_complete'] for x in xs),
             'marker_sent': sum(x['marker_sent'] for x in xs)}
        if mode in ('close', 'close2'): c['cancel_done'] = dict(collections.Counter((x['cancel_done'] or '').split(';live')[0] for x in xs))
        if mode == 'close2': c['cancel_found'] = dict(collections.Counter(x['cancel_done'] for x in xs))
        if mode == 'fence-abort': c['abort_armed'] = sum(x['abort_armed'] for x in xs)
        if cap:
            cm = [cap_measure(r, x, *caps[r['_dir']]) if caps[r['_dir']] else {'status': 'no capture file'} for r, x in zip(used, xs)]
            ok = [(r, q) for r, q in zip(used, cm) if q['status'] == 'matched']
            conc = collections.Counter(f"capture={int(q['after_marker_bytes'] > 0)}/app={int(viol_all[r['trial']])}" for r, q in ok)
            c['capture'] = {'status': dict(collections.Counter(q['status'] for q in cm)),
                            'trials_after_marker': sum(q['after_marker_bytes'] > 0 for _, q in ok),
                            'after_marker_bytes': sum(q['after_marker_bytes'] for _, q in ok),
                            'after_marker_new_bytes': sum(q['after_marker_new_bytes'] for _, q in ok),
                            'trials_new_bytes_after_marker': sum(q['after_marker_new_bytes'] > 0 for _, q in ok),
                            'rst_after_marker': sum(q['rst_after_marker'] for _, q in ok),
                            'concordance_vs_app_after_ack': dict(sorted(conc.items()))}
        out[f'{prof}/{mode}'] = c
    paired = {}
    for x, y in (('close2', 'fence'), ('close2', 'early'), ('fence-abort', 'fence'), ('close2', 'close')):
        cnt = collections.Counter()
        for (b, p_, s, m), v in w_all.items():
            if m == x and (b, p_, s, y) in w_all: cnt[f'{x}={int(v)}/{y}={int(w_all[b, p_, s, y])}'] += 1
        if cnt: paired[f'{x}_vs_{y}_after_w'] = dict(sorted(cnt.items()))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'g3race-summary.json').write_text(json.dumps({'dirs': a.dirs, 'logged': len(rows) + len(interrupted), 'interrupted_excluded': interrupted,
        'invalid': invalid, 'capture_file': {dd: caps[k] is not None for k, dd in enumerate(a.dirs)},
        'cells': out, 'paired': paired}, indent=1) + '\n')
    print(f"logged {len(rows) + len(interrupted)}, interrupted {len(interrupted)}, invalid {len(invalid)}, capture {cap}, cells {[(c, v['trials'], v['unused']) for c, v in out.items()]}")


if __name__ == '__main__':
    main()
