#!/usr/bin/env python3
"""Pilot gates for the round-4 phone runs (own phone and AWS Device Farm). Mechanism only: reads harness and fault
fields, never an outcome (violations, accepted bytes, sink contents). Writes <dir>/gate.json; exit 0 = PASS.
Usage: gates.py g3a <pilot dir with calibration.json> [--budget-min 300]
       gates.py life <pilot dir with schedule.jsonl> [--schedules reboot,netloss]
       gates.py airguard <pilot dir with schedule.jsonl> [--schedules pending,kill,reboot,netloss]
"""
import argparse, json, statistics, sys
from pathlib import Path


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()] if Path(p).exists() else []


def g3a(d, budget_min):
    m = json.load(open(d / 'calibration.json'))['median_s']
    e, u, l = m.get('edge:2097152'), m.get('umts:2097152'), m.get('lte:2097152')
    shaped = bool(e and u and l and e >= 3 * l and u >= 1.5 * l)           # the receiver's shaping separates the profiles
    wall = {}
    for x in jl(d / 'trials.jsonl'):
        wall.setdefault(f"{x['profile']}:{x['size']}", []).append(x['finished'] - x['start'])
    block_upper_min = 5 * sum(statistics.median(v) for v in wall.values()) / 60   # five arms per cell; upper bound
    blocks = min(10, int(budget_min // block_upper_min)) if block_upper_min else 0
    print('2 MiB medians (s): edge', e, 'umts', u, 'lte', l, '| shaping', 'PASS' if shaped else 'FAIL')
    print(f'block upper bound {block_upper_min:.1f} min -> N rule: {blocks} blocks' + ('' if blocks >= 5 else ' (< 5: no final)'))
    return {'gate': shaped and blocks >= 5, 'medians_2mib': [e, u, l], 'block_upper_min': block_upper_min, 'blocks': blocks}


def life(d, schedules):
    chk = {}
    for r in jl(d / 'schedule.jsonl'):
        names = [a['a'] for a in r.get('actions', [])]; t = [a['t'] for a in r.get('actions', [])]
        gap = max((b - a for a, b in zip(t, t[1:])), default=0)
        ok = 'trial_error' not in names and 'setup_fail' not in names and gap <= 200 and r.get('device_alive_end', True) is not False
        if r['schedule'] == 'reboot': ok &= 'boot_completed' in names
        if r['schedule'] == 'netloss': ok &= r.get('net_verified_down') is True
        chk[r['schedule']] = {'ok': bool(ok), 'max_action_gap_s': round(gap, 1)}
    print(chk)
    return {'gate': set(chk) == set(schedules) and all(v['ok'] for v in chk.values()), 'per_schedule': chk}


def airguard(d, schedules):
    chk = {}
    for r in jl(d / 'schedule.jsonl'):
        a = r.get('actions', []); names = [x['a'] for x in a]
        hooks = all(x.get('ok', True) for x in a if x['a'] in ('grant', 'insert_pre', 'withdraw', 'insert_optout', 'regrant', 'insert_post'))
        ok = 'trial_error' not in names and hooks and r.get('device_alive_end') is True
        if r['schedule'] == 'reboot': ok &= 'boot_completed' in names
        chk[r['schedule']] = {'ok': bool(ok), 'quiesced_s': next((x.get('waited') for x in a if x['a'] == 'quiesced'), None)}
    read = [bool(x['events']) for x in jl(d / 'device_events.jsonl')]
    print(chk, '| app logs read' if read and all(read) else '| app log missing or empty')
    return {'gate': set(chk) == set(schedules) and all(v['ok'] for v in chk.values()) and bool(read) and all(read), 'per_schedule': chk}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('kind', choices=['g3a', 'life', 'airguard']); ap.add_argument('dir', type=Path)
    ap.add_argument('--budget-min', type=float, default=300); ap.add_argument('--schedules'); a = ap.parse_args()
    if a.kind == 'g3a': res = g3a(a.dir, a.budget_min)
    elif a.kind == 'life': res = life(a.dir, (a.schedules or 'reboot,netloss').split(','))
    else: res = airguard(a.dir, (a.schedules or 'pending,kill,reboot,netloss').split(','))
    (a.dir / 'gate.json').write_text(json.dumps(res, indent=1) + '\n')
    print('gate', 'PASS' if res['gate'] else 'FAIL')
    return 0 if res['gate'] else 1


if __name__ == '__main__':
    sys.exit(main())
