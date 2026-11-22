#!/usr/bin/env python3
"""Group 3, test G3c analysis (g3app-card.md), written 22/11 before any G3c trial ran.

Validity (harness fields only): no trial_error; grant, insert, run and withdraw hooks ok; events read; device alive at the
end; a donation end event (DONATION_OK / DONATION_ERROR / DONATION_BLOCKED) logged. First N valid per build in k order.
Primary (packet capture, independent of the app's log): a trial "sent after the ack" = TCP payload bytes guest -> the
  build's sink port in capture frames after the SYN of the app's marker connection (id = trial id, opened after
  WITHDRAW_DONE) and before the next harness start marker (id <tid>-start of the next build-trial). Wilson 95% per build.
Secondary: payload bytes after the marker; receiver: donate_data logged complete by the sink after the marker arrived (host
  clock on both sides); end events; where the withdrawal fell (device clock: WITHDRAW_REQUEST before DONATION_START, during,
  or after the donation end); stop points (fenced BLOCK, layered early=1, stockcancel CANCEL_DONE calls=n); for fenced and
  layered also the app oracle (BYTES_ACCEPTED n > 0 after WITHDRAW_DONE, device clock). Paired per trial k: 2x2 of
  "sent after the ack" for fenced vs each other build. No p-values.
Usage: analyze_g3app.py <final run dir> [--out results/round3/g3app/analysis] [--n 30]
"""
import argparse, collections, json, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ART / 'followup'), str(ART / 'scripts')]
from summarize import wilson  # noqa: E402
import pcapmin  # noqa: E402

END = ('DONATION_OK', 'DONATION_ERROR', 'DONATION_BLOCKED')


def fields(s): return dict(x.split('=', 1) for x in (s or '').split(';') if '=' in x)


def validity(r):
    acts = {x['a']: x for x in r.get('actions', [])}
    if 'trial_error' in acts: return 'trial error'
    for h in ('grant', 'insert', 'run', 'withdraw'):
        if not acts.get(h, {}).get('ok'): return f'{h} hook failed'
    if not r.get('events'): return 'events not read'
    if not r.get('device_alive_end'): return 'device dead'
    if not any(e['kind'] in END for e in r['events']): return 'no donation end event'
    # protocol v4 (g3app-card Pilot log): the measured upload must be the run hook's (event file order)
    ks = [e['kind'] for e in r['events']]
    if 'RUN_ENQUEUED' not in ks: return 'no run event'
    i = ks.index('RUN_ENQUEUED')
    if 'DONATION_START' in ks[:i]: return 'donation started before run'
    if not any(k in END for k in ks[i + 1:]): return 'no donation end after run'
    return None


def first(ev, kind, pred=lambda e: True): return min((e['mono_ns'] for e in ev if e['kind'] == kind and pred(e)), default=None)


def placement(ev):
    w = first(ev, 'WITHDRAW_REQUEST'); s = first(ev, 'DONATION_START'); e = min((x['mono_ns'] for x in ev if x['kind'] in END), default=None)
    if w is None or s is None: return 'unknown'
    return 'before_start' if w < s else 'after_end' if e is not None and e < w else 'during'


def capture(path, marker, ports):
    cur, done, data = {}, [], collections.defaultdict(list)   # marker connections keyed by (sport, SYN frame): ports may be reused
    for p in pcapmin.frames(path):
        if p['dport'] == marker:
            if p['flags'] & pcapmin.SYN and not p['flags'] & pcapmin.ACK: cur[p['sport']] = [p['i'], None]
            elif p['len'] and p['sport'] in cur and cur[p['sport']][1] is None:
                cur[p['sport']][1] = p['payload'].split(b'\n')[0].decode(errors='replace'); done.append(cur[p['sport']])
        elif p['dport'] in ports and p['len']: data[p['dport']].append(p)
    marks = {}
    for i, tid in done: marks.setdefault(tid, i)
    starts = sorted(i for tid, i in marks.items() if tid.endswith('-start'))
    return marks, starts, data


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dir'); ap.add_argument('--out', default=str(ART / 'results/round3/g3app/analysis'))
    ap.add_argument('--n', type=int, default=30); a = ap.parse_args()
    d = Path(a.dir); meta = json.loads((d / 'meta.json').read_text()); ports = meta['ports']; V = meta['variants']
    rows = [json.loads(l) for l in open(d / 'trials.jsonl') if l.strip()]
    mk = {}
    if (d / 'marker.jsonl').exists():
        for x in map(json.loads, open(d / 'marker.jsonl')): mk.setdefault(x['id'], x['host_ns'])
    sink = [json.loads(l) for l in open(d / 'sink/ingest.jsonl') if l.strip()] if (d / 'sink/ingest.jsonl').exists() else []
    pc = d / 'capture.pcap' if (d / 'capture.pcap').exists() else d / 'capture-slim.pcap'   # slim: committed truncated copy (pcap_slim.py)
    cap = capture(pc, meta['marker'], set(ports.values())) if pc.exists() else None
    invalid = [{'trial': r['trial'], 'reason': why} for r in rows if (why := validity(r))]
    valid = sorted((r for r in rows if not validity(r)), key=lambda r: (r['k'], r['trial']))
    by = collections.defaultdict(list)
    for r in valid: by[r['variant']].append(r)
    out, sent = {}, {}
    for v in V:
        used = by[v][:a.n]; port = ports[v]; res = []
        for r in used:
            ev = r['events']; q = {'placement': placement(ev), 'end': next((e['kind'] for e in ev if e['kind'] in END), None)}
            wd = first(ev, 'WITHDRAW_DONE')
            q['app_after_done'] = wd is not None and any(e['kind'] == 'BYTES_ACCEPTED' and e['mono_ns'] > wd and int(fields(e['detail']).get('n', 0)) > 0 for e in ev)
            q['blocks'] = sum(e['kind'] == 'BLOCK' for e in ev); q['early_block'] = any(e['kind'] == 'DONATION_BLOCKED' and 'early=1' in e['detail'] for e in ev)
            q['cancel_calls'] = next((fields(e['detail']).get('calls') for e in ev if e['kind'] == 'CANCEL_DONE'), None)
            hm = mk.get(r['trial'])
            q['receiver_complete_after_ack'] = hm is not None and any(s.get('port') == port and s.get('path') == 'donate_data' and s.get('complete') and s['host_ns'] > hm for s in sink if s['host_ns'] < hm + 600e9)
            if cap:
                marks, starts, data = cap; m = marks.get(r['trial'])
                if m is None: q['capture'] = 'no marker'
                else:
                    end = next((i for i in starts if i > m), float('inf'))
                    post = [p for p in data[port] if m < p['i'] < end]
                    q['capture'] = 'ok'; q['after_marker_bytes'] = sum(p['len'] for p in post)
            res.append(q); sent[r['k'], v] = q.get('after_marker_bytes', 0) > 0 if q.get('capture') == 'ok' else None
        ok = [q for q in res if q.get('capture') == 'ok']; k = sum(q['after_marker_bytes'] > 0 for q in ok)
        out[v] = {'trials': len(used), 'unused': len(by[v]) - len(used),
                  'capture_status': dict(collections.Counter(q.get('capture', 'no capture file') for q in res)),
                  'sent_after_ack': k, 'sent_after_ack_wilson95': list(wilson(k, len(ok))[1:]) if ok else None, 'capture_trials': len(ok),
                  'after_marker_bytes': sum(q['after_marker_bytes'] for q in ok),
                  'receiver_complete_after_ack': sum(q['receiver_complete_after_ack'] for q in res),
                  'ends': dict(collections.Counter(q['end'] for q in res)), 'placement': dict(collections.Counter(q['placement'] for q in res)),
                  'app_bytes_after_withdraw_done': sum(q['app_after_done'] for q in res) if v in ('fenced', 'layered') else None,
                  'trials_with_block_event': sum(q['blocks'] > 0 for q in res), 'early_blocked': sum(q['early_block'] for q in res),
                  'cancel_calls': dict(collections.Counter(q['cancel_calls'] for q in res)) if v == 'stockcancel' else None}
    paired = {}
    for o in V:
        if o == 'fenced': continue
        c = collections.Counter(f'fenced={int(sent[k_, "fenced"])}/{o}={int(sent[k_, o])}' for (k_, v) in sent if v == 'fenced' and sent.get((k_, o)) is not None and sent[k_, v] is not None)
        if c: paired[f'fenced_vs_{o}'] = dict(sorted(c.items()))
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / 'g3app-summary.json').write_text(json.dumps({'logged': len(rows), 'invalid': invalid, 'capture_file': cap is not None, 'builds': out, 'paired': paired}, indent=1) + '\n')
    print(f"logged {len(rows)}, invalid {len(invalid)}, capture {cap is not None}, builds {[(v, x['trials'], x['unused']) for v, x in out.items()]}")


if __name__ == '__main__':
    main()
