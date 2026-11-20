#!/usr/bin/env python3
"""Write artifact/results/round3/EXCLUSIONS.md (B7): every excluded trial, pilot and discarded run of round 3 (role B).

Trial-level part is generated from the analysis outputs only (logged / invalid with reason / unused per task); the pilot and
discarded-run table lists every `pilot-*` and `*_INVALID_*` directory found on disk with the reason recorded in the task
card and RUNLOG (text below, one line per directory; a directory without a line is reported as "reason missing").
Usage: python3 artifact/results/round3/make_exclusions.py
"""
import json
from pathlib import Path

ART = Path(__file__).resolve().parents[2]; R = ART / 'results'

WHY = {   # directory -> (what happened, protocol change it caused); sources: task cards and RUNLOG.md
    'round3/test6/pilot-local-1': ('emulator rehearsal of the Device Farm TLS spec', 'none'),
    'round3/test6/pilot-local-2': ('emulator rehearsal of the combined spec; lifecycle trials 104–166 s', 'lifecycle split into 2 Device Farm jobs'),
    'round3/test6/pilot-df-pixel8a': ('Device Farm pilot, Pixel 8a: lifecycle passed every gate; TLS ran no trial (pre-installed app, `adb install -r` failed)', 'protocol v2: pre_test uninstalls the app first'),
    'round3/test6/pilot-df-pixel8a-2': ('Device Farm pilot 2 (protocol v2): all gates passed', 'none'),
    'round3/test6/pilot-rtl-1': ('RTL: adb 37 hung; `run-as sh -c` froze the RDB link', 'platform-tools r33 adb'),
    'round3/test6/pilot-rtl-2': ('RTL: same freeze reproduced', 'CA copied with `run-as … tee`'),
    'round3/test6/pilot-rtl-3': ('RTL: all mechanism checks passed', 'none'),
    'round3/test6/galaxy-p01_INVALID_relpath': ('relative --out broke after cd; no valid data', 'absolute paths in run_rtl.sh'),
    'round3/test6/galaxy-s1_INVALID_rdb-connect': ('RDB relay not connected (environment)', 'preflight + relay ownership in rtl_auto.sh'),
    'round3/test6/galaxy-s1_INVALID_rdb-connect2': ('RDB relay not connected again (environment)', 'link_ok re-attaches before restart'),
    'round3/test6/galaxy-s1_INVALID_rdb-noanswer': ('RDB relay stopped answering (environment)', 'timed adb calls'),
    'round3/b3/pilot-1': ('gate failed on a harness bug (suite waited for a SPLIT the app correctly never emits)', 'protocol v2: end predicate'),
    'round3/b3/pilot-2': ('gate passed', 'none'),
    'round3/b4/pilot-1': ('mechanism check of the sweep', 'none'),
    'round3/b4/pilot-v3': ('protocol v3 pilot (receiver recv timeout 300 s), gate passed', 'none'),
    'round3/b10/pilot-calib': ('throttle gate failed: console netspeed did not shape the AVD Wi-Fi path', 'protocol v2: --radio'),
    'round3/b10/pilot-calib2': ('aborted before any send (metadata `dumpsys | grep` exit 1)', 'metadata line made non-fatal'),
    'round3/b10/pilot-calib3': ('throttle gate failed again: console preset does not shape eth0', 'protocol v3: guest netem shaper'),
    'round3/b10/pilot-calib4': ('calibration complete, gate passed; stage exit 1 at end-of-run cleanup', 'cleanup fixed; durations used by final4'),
    'round3/b2/pilot-1': ('first hook timed out (cold start); no sink request (app denies cleartext)', 'warm-up hook; cleartext for 10.0.2.2 only'),
    'round3/b2/pilot-1-analysis': ('analysis of pilot-1 (pilot)', '—'),
    'round3/b2/pilot-2': ('sink reached; app donates at consent time; quiescence predicate counted old events', 'oracle v2 bracket; quiescence fix; protocol v1 frozen'),
    'round3/b2/pilot-2-analysis': ('analysis of pilot-2 (pilot)', '—'),
    'round3/b2/pilot-3': ('check of the driver fix before the final (gate in b2-card.md)', 'none'),
    'round3/b2/pilot-3-analysis': ('analysis of pilot-3 (pilot)', '—'),
    'mutation/pilot-base': ('B12 base pilot, I0 gate', 'none'),
}


def load(p):
    p = R / p
    return json.loads(p.read_text()) if p.exists() else None


def trial_rows():
    out = []
    t6 = load('round3/test6/analysis/test6-summary.json')
    if t6:
        for dev, d in t6['devices'].items():
            tls = d.get('tls', {})
            out.append((f"Test 6 TLS ({d['label']})", tls.get('blocks_logged'), [str(x) for x in tls.get('blocks_invalid', [])], len(tls.get('blocks_unused', [])), 'test6/analysis'))
        lc = t6['lifecycle']
        inv = [f"{x.get('trial')}: {x.get('reason')}" for x in lc.get('invalid_oracle_rules', []) + lc.get('invalid_phone_rules', [])]
        out.append(('Test 6 lifecycle (both phones)', sum(lc['logged'].values()), inv, len(lc.get('unused_valid', [])), 'test6/analysis'))
    t6v3 = load('round3/test6/analysis-v3/test6-summary.json')
    if t6v3:
        for dev, d in t6v3['devices'].items():
            tls = d.get('tls', {})
            if tls: out.append((f"Test 6 TLS v3 ({d['label']})", tls.get('blocks_logged'), [str(x) for x in tls.get('blocks_invalid', [])], len(tls.get('blocks_unused', [])), 'test6/analysis-v3'))
    b11 = load('round3/b11/analysis/b11-summary.json')
    if b11:
        inv = [f"{x['instance']}/{x['trial']}: {x['reason']}" for x in b11['invalid_oracle_rules']] + [f"{x['instance']}/{x['trial']}: {x['reason']}" for x in b11['invalid_extra']]
        n = sum(v['analysed_paired_trials'] for v in b11['avds'].values()) + len(inv) + len(b11['unused_valid'])
        out.append(('Test 4 / B11 (Android 14 + 15)', n, inv, len(b11['unused_valid']), 'b11/analysis'))
    mut = load('mutation/analysis/mutation-summary.json')
    if mut:
        for m, v in mut['mutants'].items():
            inv = [f"{x['trial']}: {x['reason']}" for x in v['invalid']]
            out.append((f'Test 2 / B12 {m}', v['valid_trials'] + len(inv), inv, 0, 'mutation/analysis'))
    for name, f in (('B3 split policy', 'round3/b3/analysis/b3-summary.json'), ('Test 5 / B4 v1', 'round3/b4/analysis/sweep-summary.json'),
                    ('Test 5 / B4 v2', 'round3/b4/analysis-v2/sweep-summary.json'), ('Test 5 / B4 v3 (keys; final-v3 + replacement blocks)', 'round3/b4/analysis-v3-repl/sweep-summary.json'), ('Test 1 / B10 v3', 'round3/b10/analysis/race-summary.json')):
        d = load(f)
        if d: out.append((name, d['logged'], [f"{x['trial']}: {x['reason']}" for x in d['invalid']], sum(c.get('unused', 0) for c in d['cells'].values()), str(Path(f).parent.relative_to('round3'))))
    b2 = load('round3/b2/analysis/airguard-summary.json')
    if b2:
        out.append(('B2 AirGuard (real app)', len({r['trial'] for r in b2['rows']}) + len(b2['invalid']), [f"{x['trial']}: {x['reason']}" for x in b2['invalid']],
                    sum(c['unused'] for c in b2['cells'].values()), 'b2/analysis'))
    return out


def main():
    L = ['# Round 3 (role B) — exclusions', '',
         'Generated by `artifact/results/round3/make_exclusions.py` from the analysis outputs (trial level) and the directories on',
         'disk (pilots, discarded runs). Excluded data are kept as recorded and never analysed or pooled (R2.2, R2.6). Validity',
         'rules, replacement rules and protocol versions: the task cards in `artifact/plans/` (index: `PROTOCOL.md`).', '',
         '## Trial-level exclusions (final runs)', '', '| Task | Logged | Invalid (reason) | Unused valid | Analysis |', '|---|---|---|---|---|']
    for name, n, inv, unused, src in trial_rows():
        L.append(f"| {name} | {n} | {len(inv)}{': ' + '; '.join(inv) if inv else ''} | {unused} | `{src}` |")
    L += ['', '## Pilots and discarded runs', '', '| Directory | What happened | Change caused |', '|---|---|---|']
    dirs = sorted(str(p.relative_to(R)) for base in (R / 'round3', R / 'mutation') for p in base.rglob('*')
                  if p.is_dir() and (p.name.startswith('pilot') or '_INVALID_' in p.name))
    for d in dirs:
        what, change = WHY.get(d, ('reason missing', '—'))
        L.append(f'| `{d}` | {what} | {change} |')
    L += ['', 'Superseded (reported, not used for keys): B4 v1 final (`b4/final`, probes mostly outside the send window) and v2 final',
          '(`b4/final-v2`, 4 trials cut by the harness receiver\'s 30 s timeout; v3 is the key source) and Test 6 TLS v2 `concurrent` case on the Galaxy (fixed deadline; v3 rerun). Both stay in the results.', '']
    (R / 'round3/EXCLUSIONS.md').write_text('\n'.join(L))
    print(f"EXCLUSIONS.md: {len(trial_rows())} task rows, {len(dirs)} pilot/discarded dirs, {sum(d not in WHY for d in dirs)} without reason")


if __name__ == '__main__':
    main()
