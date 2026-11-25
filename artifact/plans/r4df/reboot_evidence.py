#!/usr/bin/env python3
"""Was the phone rebooted? (24/11, diagnosis of Device Farm pilot-preb.) Uses the app event logs only: field 3 of every
event is the device's monotonic clock (ms since boot). A real reboot restarts it near 0, so the monotonic clock of events
after the trial's reboot action must drop below the one before it. Reads schedule.jsonl and device_events.jsonl; prints and
writes <out>. Usage: reboot_evidence.py <life dir> <out.json>"""
import json, sys
d, out = sys.argv[1], sys.argv[2]
plans = {p['trial']: p for p in map(json.loads, open(f'{d}/schedule.jsonl'))}
res = {}
for x in map(json.loads, open(f'{d}/device_events.jsonl')):
    p = plans[x['trial']]; tr = next(a['t'] for a in p['actions'] if a['a'] == 'reboot')
    ev = x['events']; before = [e[2] for e in ev if e[1] / 1000 < tr]; after = [e[2] for e in ev if e[1] / 1000 > tr + 5]
    res.setdefault(x['trial'], {})[x['pkg']] = {'mono_ms_last_before': max(before, default=None), 'mono_ms_first_after': min(after, default=None),
        'restarted': bool(before and after and min(after) < max(before)),
        'boot_s_logged': next((a.get('boot_s') for a in p['actions'] if a['a'] == 'boot_completed'), None)}
s = json.dumps(res, indent=1); open(out, 'w').write(s + '\n'); print(s)
