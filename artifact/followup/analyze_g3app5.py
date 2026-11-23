#!/usr/bin/env python3
"""G3c protocol v5 analysis (plans/g3app5-card.md), written 23/11 before any v5 trial. Leader's request in issue #7 (23/11):
stockcancel with a 16 KiB send buffer (stockcancel16) against stockcancel (kernel default) and fenced, in the same trials.

Validity and selection as v4 (analyze_g3app.validity; first N valid per build in k order).
Primary (pre-registered): per build, trials in which the sink logged donate_data complete after the app's marker arrived
  and before the same build's next start marker (host clock on both sides; analyze_g3app.receiver_complete, corrected 23/11), Wilson 95% over trials whose marker reached marker.jsonl (the others
  are counted as 'no marker'). Paired per trial k (2x2 counts): stockcancel16 vs fenced; also stockcancel16 vs stockcancel.
Secondary:
  - capture: trials with TCP payload guest -> the build's sink port after the marker SYN (v4 primary, Wilson 95%), payload
    bytes after the marker, total and per trial (median, nearest-rank p95, max), split by where the withdrawal fell
    (device clock: before the donation start, during, after its end);
  - Call.cancel() cut an in-flight call (cancel builds): CANCEL_DONE calls >= 1 and the donation ended DONATION_ERROR after
    CANCEL_DONE (device clock); CANCEL_DONE calls = 0 counted separately;
  - fenced: app oracle, BYTES_ACCEPTED n > 0 after WITHDRAW_DONE; BLOCK events;
  - send buffer of the donation socket: actual_sndbuf of the SOCKET_CONFIG event of the donation (OkHttp: path ending
    donate_data; HttpTransport: the only SOCKET_CONFIG) after RUN_ENQUEUED; counts per value, 'missing' if absent;
  - end events and placement.
No p-values. Output: <out>/g3app5-summary.json. Usage: analyze_g3app5.py <run dir> [--out DIR] [--n 30]
"""
import argparse, collections, json, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ART / 'followup'), str(ART / 'scripts')]
from analyze_g3app import END, capture, fields, first, placement, receiver_complete, validity  # noqa: E402
from analyze_g2close import order_stats  # noqa: E402
from summarize import wilson  # noqa: E402


def after_run(ev):
    ks = [e['kind'] for e in ev]
    return ev[ks.index('RUN_ENQUEUED') + 1:] if 'RUN_ENQUEUED' in ks else []


def donation_sndbuf(ev):
    for e in after_run(ev):
        if e['kind'] != 'SOCKET_CONFIG': continue
        f = fields(e['detail'])
        if 'path' not in f or f['path'].rstrip('/').endswith('donate_data'): return int(f.get('actual_sndbuf', -1))
    return None


def cancel_cut(ev):
    """None: no CANCEL_DONE; 'no call': calls=0; True: calls>=1 and DONATION_ERROR after CANCEL_DONE; False otherwise."""
    c = next((e for e in ev if e['kind'] == 'CANCEL_DONE'), None)
    if c is None: return None
    if int(fields(c['detail']).get('calls', 0) or 0) < 1: return 'no call'
    end = min((e for e in ev if e['kind'] in END and e['mono_ns'] >= c['mono_ns']), key=lambda e: e['mono_ns'], default=None)
    return end is not None and end['kind'] == 'DONATION_ERROR'


def pair(res, x, y, key):
    ks = sorted({k for (k, v) in res if v == x} & {k for (k, v) in res if v == y})
    c = collections.Counter(f'{x}={int(res[k, x][key])}/{y}={int(res[k, y][key])}' for k in ks
                            if res[k, x].get(key) is not None and res[k, y].get(key) is not None)
    return dict(sorted(c.items()))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('--out', default=str(ART / 'results/round3/g3app/analysis-v5'))
    ap.add_argument('--n', type=int, default=30); a = ap.parse_args()
    d = Path(a.dir); meta = json.loads((d / 'meta.json').read_text()); ports = meta['ports']; V = meta['variants']
    rows = [json.loads(l) for l in open(d / 'trials.jsonl') if l.strip()]
    mk = {}
    if (d / 'marker.jsonl').exists():
        for x in map(json.loads, open(d / 'marker.jsonl')): mk.setdefault(x['id'], x['host_ns'])
    sink = [json.loads(l) for l in open(d / 'sink/ingest.jsonl') if l.strip()] if (d / 'sink/ingest.jsonl').exists() else []
    pc = d / 'capture.pcap' if (d / 'capture.pcap').exists() else d / 'capture-slim.pcap'
    cap = capture(pc, meta['marker'], set(ports.values())) if pc.exists() else None
    invalid = [{'trial': r['trial'], 'reason': why} for r in rows if (why := validity(r))]
    by = collections.defaultdict(list)
    for r in sorted((r for r in rows if not validity(r)), key=lambda r: (r['k'], r['trial'])): by[r['variant']].append(r)
    out, res = {}, {}
    for v in V:
        used = by[v][:a.n]; port = ports[v]; qs = []
        for r in used:
            ev = r['events']; q = {'placement': placement(ev), 'end': next((e['kind'] for e in after_run(ev) if e['kind'] in END), None)}
            wd = first(ev, 'WITHDRAW_DONE')
            q['app_after_done'] = wd is not None and any(e['kind'] == 'BYTES_ACCEPTED' and e['mono_ns'] > wd and int(fields(e['detail']).get('n', 0)) > 0 for e in ev)
            q['blocks'] = sum(e['kind'] == 'BLOCK' for e in ev); q['cancel_cut'] = cancel_cut(ev); q['sndbuf'] = donation_sndbuf(ev)
            hm = mk.get(r['trial'])
            q['complete_after_ack'] = None if hm is None else receiver_complete(sink, port, v, hm, mk)
            q['sent_after_ack'] = None
            if cap:
                marks, starts, data = cap; m = marks.get(r['trial'])
                if m is None: q['capture'] = 'no marker'
                else:
                    end = next((i for i in starts if i > m), float('inf'))
                    q['capture'] = 'ok'; q['after_marker_bytes'] = sum(p['len'] for p in data[port] if m < p['i'] < end)
                    q['sent_after_ack'] = q['after_marker_bytes'] > 0
            qs.append(q); res[r['k'], v] = q
        rc = [q for q in qs if q['complete_after_ack'] is not None]; k = sum(q['complete_after_ack'] for q in rc)
        ok = [q for q in qs if q.get('capture') == 'ok']; ks = sum(q['sent_after_ack'] for q in ok)
        byph = {}
        for ph in sorted({q['placement'] for q in ok}):
            b = [q['after_marker_bytes'] for q in ok if q['placement'] == ph]
            byph[ph] = {'trials': len(b), 'trials_bytes_after_marker': sum(x > 0 for x in b), 'bytes_sum': sum(b), 'bytes': order_stats(b)}
        cancel = [q['cancel_cut'] for q in qs if q['cancel_cut'] is not None]
        out[v] = {'trials': len(used), 'unused': len(by[v]) - len(used),
                  'receiver_complete_after_ack': k, 'receiver_trials': len(rc), 'receiver_no_marker': len(qs) - len(rc),
                  'receiver_complete_after_ack_wilson95': list(wilson(k, len(rc))[1:]) if rc else None,
                  'capture_status': dict(collections.Counter(q.get('capture', 'no capture file') for q in qs)),
                  'sent_after_ack': ks, 'capture_trials': len(ok), 'sent_after_ack_wilson95': list(wilson(ks, len(ok))[1:]) if ok else None,
                  'after_marker_bytes_sum': sum(q['after_marker_bytes'] for q in ok), 'after_marker_bytes': order_stats([q['after_marker_bytes'] for q in ok]),
                  'after_marker_by_placement': byph,
                  'cancel': {'cut_in_flight': sum(x is True for x in cancel), 'not_cut': sum(x is False for x in cancel), 'no_call': sum(x == 'no call' for x in cancel)} if cancel else None,
                  'app_bytes_after_withdraw_done': sum(q['app_after_done'] for q in qs) if v == 'fenced' else None,
                  'trials_with_block_event': sum(q['blocks'] > 0 for q in qs),
                  'donation_sndbuf': dict(collections.Counter('missing' if q['sndbuf'] is None else str(q['sndbuf']) for q in qs)),
                  'ends': dict(collections.Counter(q['end'] for q in qs)), 'placement': dict(collections.Counter(q['placement'] for q in qs))}
    paired = {}
    for x, y in (('stockcancel16', 'fenced'), ('stockcancel16', 'stockcancel'), ('stockcancel', 'fenced')):
        if x in V and y in V:
            paired[f'{x}_vs_{y}'] = {'receiver_complete_after_ack': pair(res, x, y, 'complete_after_ack'), 'sent_after_ack': pair(res, x, y, 'sent_after_ack')}
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'g3app5-summary.json').write_text(json.dumps({'dir': a.dir, 'logged': len(rows), 'invalid': invalid, 'capture_file': cap is not None,
                                                                  'builds': out, 'paired': paired}, indent=1) + '\n')
    print(f"logged {len(rows)}, invalid {len(invalid)}, capture {cap is not None}, builds {[(v, x['trials'], x['unused']) for v, x in out.items()]}")


if __name__ == '__main__':
    main()
