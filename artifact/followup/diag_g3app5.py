#!/usr/bin/env python3
"""G3c v5c exploratory diagnosis (post hoc, 23/11, NOT pre-registered; g3app5-card §6): for every valid build-trial whose
sink logged the donation complete after the marker, and for the same trials k of the other builds, payload bytes to the sink
before and after the app's marker (this build-trial's capture window), u, placement, cancel result and the device-clock gap
from DONATION_START to WITHDRAW_REQUEST and to the donation socket's SOCKET_CONFIG. Usage: diag_g3app5.py <run dir> --out F"""
import argparse, json, sys
from pathlib import Path
ART = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(ART / 'followup'), str(ART / 'scripts')]
import analyze_g3app as g, analyze_g3app5 as g5  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('--out', required=True); a = ap.parse_args()
d = Path(a.dir); meta = json.loads((d / 'meta.json').read_text()); P = meta['ports']
rows = [json.loads(l) for l in open(d / 'trials.jsonl') if l.strip()]; valid = [r for r in rows if not g.validity(r)]
mk = {}
for x in map(json.loads, open(d / 'marker.jsonl')): mk.setdefault(x['id'], x['host_ns'])
sink = [json.loads(l) for l in open(d / 'sink/ingest.jsonl') if l.strip()]
pc = d / 'capture.pcap' if (d / 'capture.pcap').exists() else d / 'capture-slim.pcap'
marks, starts, data = g.capture(pc, meta['marker'], set(P.values()))
comp = {r['trial'] for r in valid if r['trial'] in mk and g.receiver_complete(sink, P[r['variant']], r['variant'], mk[r['trial']], mk)}
ks = {r['k'] for r in valid if r['trial'] in comp}
out = []
for r in sorted((r for r in valid if r['k'] in ks), key=lambda r: (r['k'], r['variant'])):
    v, ev, m = r['variant'], r['events'], marks.get(r['trial'])
    lo = max([i for i in starts if m is not None and i < m] or [0]); hi = next((i for i in starts if m is not None and i > m), float('inf'))
    ms = lambda k: (lambda t, s: None if t is None or s is None else round((t - s) / 1e6, 1))(g.first(ev, k), g.first(ev, 'DONATION_START'))
    out.append({'trial': r['trial'], 'u': round(r['u'], 3), 'complete_after_ack': r['trial'] in comp, 'placement': g.placement(ev),
                'cancel_cut': g5.cancel_cut(ev), 'end': next((e['kind'] for e in g5.after_run(ev) if e['kind'] in g.END), None),
                'bytes_before_marker': sum(p['len'] for p in data[P[v]] if m is not None and lo < p['i'] < m),
                'bytes_after_marker': sum(p['len'] for p in data[P[v]] if m is not None and m < p['i'] < hi),
                'ms_donation_start_to_withdraw_request': ms('WITHDRAW_REQUEST'),
                'ms_donation_start_to_socket_config': next((round((e['mono_ns'] - g.first(ev, 'DONATION_START')) / 1e6, 1) for e in g5.after_run(ev)
                                                            if e['kind'] == 'SOCKET_CONFIG' and g.first(ev, 'DONATION_START') is not None
                                                            and ('path' not in g.fields(e['detail']) or 'donate_data' in g.fields(e['detail'])['path'])), None)})
Path(a.out).write_text(json.dumps({'note': 'exploratory, post hoc, not pre-registered', 'dir': a.dir, 'rows': out}, indent=1) + '\n')
for x in out: print(x)
