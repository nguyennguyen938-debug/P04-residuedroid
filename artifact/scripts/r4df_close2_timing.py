#!/usr/bin/env python3
"""Round 4 on Device Farm (Pixel 8a), exploratory (C, 25/11, defined after the data): in the same-process cancellation
(close2) trials whose socket accepted a write attempted after the withdrawal commit W, when that write started and when
the cancellation took effect, both relative to W on the device's monotonic clock. Same counting rule as the pre-registered
primary (analyze_g3race.after_w): BYTES_ACCEPTED n > 0 after W whose latest WRITE_ATTEMPT is after W.
Reads the frozen trial logs only. Writes results/round3/c-analysis/r4df-close2-timing.json (keys read by make_summary).
Usage: python3 artifact/scripts/r4df_close2_timing.py
"""
import glob, gzip, json
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
RUN = ART / 'results/round3/phone-r4/aws/g3a'
OUT = ART / 'results/round3/c-analysis/r4df-close2-timing.json'


def fields(s):
    return dict(x.split('=', 1) for x in (s or '').split(';') if '=' in x)


def trials():
    for d in sorted(glob.glob(str(RUN / 'f*/unzipped/Customer_Artifacts/Host_Machine_Files/$DEVICEFARM_LOG_DIR/g3a'))):
        p = Path(d) / 'trials.jsonl'
        f = open(p, encoding='utf-8') if p.exists() else gzip.open(Path(d) / 'trials.jsonl.gz', 'rt', encoding='utf-8')
        with f:
            yield from (json.loads(l) for l in f if l.strip())


def main():
    rows = []
    for t in trials():
        if t.get('mode') != 'close2' or t.get('harness_error'): continue
        ev = sorted((e for e in t.get('events', []) if e.get('trial') == t['trial']), key=lambda e: e['mono_ns'])
        ws = [e['mono_ns'] for e in ev if e['kind'] == 'WITHDRAW_DURABLE']
        if not ws: continue
        w = ws[0]; att = [e['mono_ns'] for e in ev if e['kind'] == 'WRITE_ATTEMPT']
        late = [e for e in ev if e['kind'] == 'BYTES_ACCEPTED' and int(fields(e['detail']).get('n', 0)) > 0 and e['mono_ns'] > w
                and max((a for a in att if a <= e['mono_ns']), default=0) > w]
        if not late: continue
        cd = next(e for e in ev if e['kind'] == 'CANCEL_DONE')
        rows.append({'trial': t['trial'], 'profile': t['profile'], 'size': t['size'],
                     'post_w_write_ms': (min(a for a in att if a > w) - w) / 1e6, 'cancel_after_w_ms': (cd['mono_ns'] - w) / 1e6,
                     'late_bytes': sum(int(fields(e['detail'])['n']) for e in late), 'cancel_detail': cd['detail']})
    assert rows and all(r['post_w_write_ms'] < r['cancel_after_w_ms'] for r in rows), 'every late write precedes the cancellation'
    pw = [r['post_w_write_ms'] for r in rows]; cw = [r['cancel_after_w_ms'] for r in rows]
    keys = {'dfCloseTwoTimed': len(rows), 'dfCloseTwoPostWLo': round(min(pw), 1), 'dfCloseTwoPostWHi': round(max(pw), 1),
            'dfCloseTwoCancelLo': round(min(cw), 1), 'dfCloseTwoCancelHi': round(max(cw), 1)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'note': 'exploratory, defined after the data', 'rows': rows, 'keys': keys}, indent=1) + '\n',
                   encoding='utf-8', newline='\n')
    print(keys)


if __name__ == '__main__':
    main()
