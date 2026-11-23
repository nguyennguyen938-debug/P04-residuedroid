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
    'round3/test1-phone/pilot-calib-2': ('phone pilot, throttle gate failed: every 256 KiB/2 MiB send cut ~4.4–4.9 s in (connection abort; app process frozen in the background on Android 15)', 'race_suite keeps the app in the foreground on phones (launch Main before each send)'),
    'round3/test1-phone/pilot-calib-3': ('phone pilot, 27/27 sends ok, throttle gate passed; durations used by the final', 'none'),
    'round3/test1-phone/pilot-calib-1': ('phone pilot stopped after 3 sends: SocketException (connect abort) — the never-launched app had no network from a broadcast', 'race_suite wakes the app on phones (standby bucket active + launch once), as campaign.py'),
    'mutation-v2/pilot-base': ('B12 v2 base pilot (regrant_agg): labels ok, AGG after REGRANT in 2/2 trials, gate passed', 'none'),
    'round3/g2close/pilot-calib': ('G2a calibration aborted before any send: setup init broadcast timed out (cold start 83 s under host load)', 'setup init timeout 300 s (frozen-g2-v2)'),
    'round3/g2close/pilot-calib2': ('G2a calibration, 27/27 sends ok, throttle gate passed; durations used by the final', 'none'),
    'round3/g2close/pilot-mech': ('G2a mechanism pilot (1 block, 27 trials): all valid, every close trial CANCEL + reply ok; gate passed', 'none'),
    'round3/g3race/pilot-calib': ('G3a/G3b calibration (27 fence sends, no withdrawal); throttle gate passed; durations used by the final', 'none'),
    'round3/g3race/pilot-mech': ('G3a/G3b mechanism pilot (45 trials): MECHANISM GATE FAIL on the capture only (console `network capture start` takes bare filenames; no pcap)', 'protocol v2: emulator -tcpdump at launch'),
    'round3/g3race/pilot-mech2': ('G3a/G3b mechanism pilot v2 (45 trials): every gate field held', 'none'),
    'round3/g3app/pilot-calib': ('G3c calibration (3 per build): CALIBRATION GATE FAIL (stock 2/3 samples, median body 137,073 B < 200 KiB); the grant hook starts the app\'s periodic donation worker, which reads the DB during the insert', 'no G3c final under v3; fix needs protocol v4'),
    'round3/g3app/pilot-v4-calib': ('G3c v4 calibration (3 per build, startup-worker wait): 12/12 samples from the run hook; body below 200 KiB only, so the pre-registered body-only recalibration ran', 'none (N from the recalibration)'),
    'round3/g3app/pilot-v4-calib2': ('G3c v4 body-only recalibration: calibration gate passed; durations and N used by final-v4', 'none'),
    'round3/g3app/pilot-v4-mech': ('G3c v4 mechanism pilot: gate passed', 'none'),
    'round3/g3app/pilot-v5-calib': ('G3c v5 calibration (stockcancel16, stockcancel, fenced; 3 per build): gate passed', 'none (v5 stopped at the mechanism gate)'),
    'round3/g3app/pilot-v5-mech': ('G3c v5 mechanism pilot: MECHANISM GATE FAIL on actual_sndbuf only (getSendBufferSize units differ by API: java.net.Socket kernel value, NIO half)', 'no v5 final; protocol v5b'),
    'round3/g3app/pilot-v5b-calib': ('G3c v5b calibration (rebuilt APKs with in-app kernel_sndbuf): gate passed', 'none (v5b stopped at the mechanism gate)'),
    'round3/g3app/pilot-v5b-mech': ('G3c v5b mechanism pilot: MECHANISM GATE FAIL, kernel_sndbuf -1 in every build-trial (hidden getsockoptInt blocked on API 33)', 'no v5b final; protocol v5c (harness-side ss read)'),
    'round3/g3app/pilot-v5c-calib': ('G3c v5c calibration with guest ss kernel send-buffer read: gate passed (tb 32768 stockcancel16 and fenced, 2097152 stockcancel)', 'none'),
    'round3/g3app/pilot-v5c-mech': ('G3c v5c mechanism pilot: gate passed', 'none'),
    'round3/g3race/pilot-lte4': ('P3 (G3a on lte) v4 pilot (1 block, 15 trials): every mechanism field held; BALANCE GATE FAIL (per-size spread 337/42/19 ms > 15 ms; one adb stall, otherwise per-trial jitter with one trial per size and arm)', 'P3 protocol v5: 3-block pilot, gate on d = device delay minus host offset, adb-stall trials left out of d'),
    'round3/g3race/pilot-lte5': ('P3 v5 pilot (3 blocks, 45 trials): mechanism fields and balance gate v5 passed', 'none'),
    'round3/g3race/pilot-p4': ('P4 pilot (1 block, 12 trials): mechanism gate passed (sndbuf levels requested/actual 0/1048576, 16384/16384, 65536/65536)', 'none'),
    'round3/g3race/analysis-p4_INVALID_interrupted-partial': ('derived output of the P4 chain post steps on the partial final-p4 (user pause 23/11 04:58 after 16 complete blocks); not the pre-registered analysis', 'none (final-p4 resumes in a fresh directory)'),
    'round3/g3cost/pilot': ('G3d pilot: stopped at setup before any upload (Android 15 dumpsys prints appId=, UID regex failed); empty', 'UID regex accepts userId= or appId='),
    'round3/g3cost/pilot-2': ('G3d pilot-2: stopped at setup before any upload (fresh install has no files/ dir, CA copy failed); empty', 'run-as mkdir -p files before the CA copy'),
    'round3/g3cost/pilot-3': ('G3d pilot-3: PILOT GATE FAIL (8/9 cells valid; one transient adb error with empty stderr; Android 15 batterystats estimate only on the checkin line; chain gate line bug)', 'G3d protocol v2: one logged adb retry, Android 15 parser, gate line fixed'),
    'round3/g3cost/pilot-5': ('G3d v3 pilot (23/11 15:30): gate passed (1 block); the v3 final then dozed at the 10 min screen timeout under battery unplug (harness design fault)', 'G3d protocol v4: screen timeout 24 h + Doze off during the run, checked in meta and the pilot gate'),
    'round3/g3cost/pilot-4': ('G3d v2 pilot: gate passed (9/9 valid, 18/18 uploads ok and received)', 'none (the v2 final then failed on the environment: phone dozed, device lost; protocol v3)'),
    'round3/g2layer/pilot': ('G2b pilot (1 trial per schedule, three builds): 4/4 valid, warm-up ok, donate requests at all three ports; gate passed', 'none'),
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
    for ver, f in (('v1', 'mutation/analysis'), ('v2 (keys)', 'mutation-v2/analysis')):
        mut = load(f + '/mutation-summary.json')
        if mut:
            for m, v in mut['mutants'].items():
                inv = [f"{x['trial']}: {x['reason']}" for x in v['invalid']]
                out.append((f'Test 2 / B12 {ver} {m}', v['valid_trials'] + len(inv), inv, 0, f))
    for name, f in (('B3 split policy', 'round3/b3/analysis/b3-summary.json'), ('Test 5 / B4 v1', 'round3/b4/analysis/sweep-summary.json'),
                    ('Test 5 / B4 v2', 'round3/b4/analysis-v2/sweep-summary.json'), ('Test 5 / B4 v3 (keys; final-v3 + replacement blocks)', 'round3/b4/analysis-v3-repl/sweep-summary.json'), ('Test 1 / B10 v3', 'round3/b10/analysis/race-summary.json'), ('Test 1 phone (Galaxy A06, Android 15)', 'round3/test1-phone/analysis/race-summary.json'), ('G2a early check + socket close (group 2)', 'round3/g2close/analysis/g2close-summary.json')):
        d = load(f)
        if d: out.append((name, d['logged'], [f"{x['trial']}: {x['reason']}" for x in d['invalid']], sum(c.get('unused', 0) for c in d['cells'].values()), str(Path(f).parent.relative_to('round3'))))
    g3 = load('round3/g3race/analysis/g3race-summary.json')
    if g3: out.append(('G3a/G3b socket-close comparator + capture (group 3; final + resumed final-r2)', g3['logged'],
                       [f"{x['trial']}: {x['reason']}" for x in g3['invalid']] + [f"{x['trial']}: {x['reason']} (paused, operational)" for x in g3['interrupted_excluded']],
                       sum(c.get('unused', 0) for c in g3['cells'].values()), 'g3race/analysis'))
    g3c = load('round3/g3app/analysis-v4/g3app-summary.json')
    if g3c: out.append(('G3c AirGuard withdrawal mid-upload v4 (group 3)', g3c['logged'], [f"{x['trial']}: {x['reason']}" for x in g3c['invalid']],
                        sum(c.get('unused', 0) for c in g3c['builds'].values()), 'g3app/analysis-v4'))
    g3c5 = load('round3/g3app/analysis-v5c/g3app5-summary.json')
    if g3c5: out.append(('G3c v5c AirGuard stockcancel16 / stockcancel / fenced (group 3, leader request)', g3c5['logged'], [f"{x['trial']}: {x['reason']}" for x in g3c5['invalid']],
                         sum(c.get('unused', 0) for c in g3c5['builds'].values()), 'g3app/analysis-v5c'))
    p3 = load('round3/g3race/analysis-lte5/g3race-summary.json')
    if p3: out.append(('P3: G3a on lte, balanced exposure (protocol v5)', p3['logged'], [f"{x['trial']}: {x['reason']}" for x in p3['invalid']] + [f"{x['trial']}: {x['reason']} (paused, operational)" for x in p3['interrupted_excluded']],
                       sum(c.get('unused', 0) for c in p3['cells'].values()), 'g3race/analysis-lte5'))
    p4 = load('round3/g3race/analysis-p4/g3p4-summary.json')
    if p4: out.append(('P4: SO_SNDBUF x fence/fence-abort (final-p4 + resumed final-p4b, final-p4c)', p4['logged'], [f"{x['trial']}: {x['reason']}" for x in p4['invalid']] + [f"{x['trial']}: {x['reason']} (paused, operational)" for x in p4['interrupted_excluded']],
                       sum(c.get('unused', 0) for c in p4['cells'].values()), 'g3race/analysis-p4'))
    b2 = load('round3/b2/analysis/airguard-summary.json')
    if b2:
        out.append(('B2 AirGuard (real app)', len({r['trial'] for r in b2['rows']}) + len(b2['invalid']), [f"{x['trial']}: {x['reason']}" for x in b2['invalid']],
                    sum(c['unused'] for c in b2['cells'].values()), 'b2/analysis'))
    g2b = load('round3/g2layer/analysis/airguard-summary.json')
    if g2b:
        out.append(('G2b AirGuard layered early (group 2)', len({r['trial'] for r in g2b['rows']}) + len(g2b['invalid']), [f"{x['trial']}: {x['reason']}" for x in g2b['invalid']],
                    sum(c['unused'] for c in g2b['cells'].values()), 'g2layer/analysis'))
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
    dirs = sorted(str(p.relative_to(R)) for base in (R / 'round3', R / 'mutation', R / 'mutation-v2') for p in base.rglob('*')
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
