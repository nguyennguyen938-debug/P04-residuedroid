#!/usr/bin/env python3
"""Build artifact/results/round3/summary.json (B → C delivery) from the analysis outputs only; never typed by hand.

Sources (each optional; a missing analysis just leaves its keys absent, which renders as ?? in the PDF):
  test 6  results/round3/test6/analysis/test6-summary.json  summary_candidates (definitions: plans/test6-card.md §4)
  test 1  results/round3/b10/analysis/race-summary.json     keys
  test 4  results/round3/b11/analysis/b11-summary.json      keys
  test 5  results/round3/b4/analysis-v3-repl/sweep-summary.json  keys (protocol v3, final-v3 + replacement blocks; v1, v2 reported in b4-card.md)
  test 2  results/mutation-v2/analysis/mutation-summary.json   keys (protocol v2, regrant_agg; v1 reported in b12-card.md)
Only names in SCHEMA (scripts/render_tests.py) are written; render_tests.py asserts this too.
Usage: python3 artifact/results/round3/make_summary.py
"""
import ast, collections, json, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[2]
R = ART / 'results'
SRC = [(R / 'round3/test6/analysis/test6-summary.json', 'summary_candidates'), (R / 'round3/b10/analysis/race-summary.json', 'keys'),
       (R / 'round3/b11/analysis/b11-summary.json', 'keys'), (R / 'round3/b4/analysis-v3-repl/sweep-summary.json', 'keys'),
       (R / 'mutation-v2/analysis/mutation-summary.json', 'keys')]


def schema():
    tree = ast.parse((ART / 'scripts/render_tests.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == 'SCHEMA' for t in node.targets):
            return set(ast.literal_eval(node.value))
    raise SystemExit('SCHEMA not found')


def load(rel):
    return json.loads((R / rel).read_text(encoding='utf-8'))


def derived():
    """Keys added at C's request on PR #2 (21/11), computed from the frozen analysis outputs; nothing is re-run.
    Structural assumptions (equal cell sizes, both builds paired) are asserted; values were checked once against
    plans/B-report.md when this was added."""
    k = {}
    # Test 1 on a phone: same analyser as B10, keys renamed race* -> racePhone*. The model label comes from
    # plans/test1-phone-card.md (the meta.json fingerprint is samsung/a06...); the Android release from meta.json.
    ph = load('round3/test1-phone/analysis/race-summary.json')['keys']
    k.update({'racePhone' + name[len('race'):]: v for name, v in ph.items()})
    k['racePhoneModel'] = 'Galaxy A06'
    k['racePhoneAndroid'] = load('round3/test1-phone/final/meta.json')['phone']['release']
    # B2 AirGuard: pending, kill and reboot pooled; netloss is reported separately in the card.
    v2, v3 = load('round3/b2/analysis/airguard-summary.json')['cells'], load('round3/b2/analysis-v3/airguard-summary.json')['cells']
    sched = ['pending', 'kill', 'reboot']
    n_stock, n_fence = (sum(v2[f'{s}/{b}']['trials'] for s in sched) for b in ('stock', 'fenced'))
    assert n_stock == n_fence
    k.update(airN=n_stock, airStockViol=sum(v2[f'{s}/stock']['violating_trials'] for s in sched),
             airFenceViol=sum(v2[f'{s}/fenced']['violating_trials'] for s in sched),
             airFenceUnknownV=sum(v2[f'{s}/fenced']['unknown_trials'] for s in sched),
             airFenceUnknownVThree=sum(v3[f'{s}/fenced']['unknown_trials'] for s in sched))
    # B3 split policy. forbidden_after_ack is summed over every cell; 0 means no trial accepted bytes after the ack.
    b3 = load('round3/b3/analysis/b3-summary.json')['cells']
    assert len({c['trials'] for c in b3.values()}) == 1
    k.update(splitTrials=b3['prefirst/split']['trials'], splitPreRecovered=b3['prefirst/split']['permitted_retained'],
             splitPostRecovered=b3['prefix/split']['permitted_retained'],
             splitAfterAck=sum(c['forbidden_after_ack'] for c in b3.values()))
    # B12 v2 per-build counts (mutTrials stays the minimum and is not cited).
    mu = load('mutation-v2/analysis/mutation-summary.json')['mutants']
    k.update(mutBaseTrials=mu['base']['valid_trials'], mutOneTrials=mu['M1-union-latest']['valid_trials'],
             mutTwoTrials=mu['M2-stale-epoch']['valid_trials'], mutThreeTrials=mu['M3-extras-drop']['valid_trials'],
             mutBaseDeficit=mu['base']['permitted_deficit'], mutBaseLeak=mu['base']['leaking_trials'],
             mutThreeLeak=mu['M3-extras-drop']['leaking_trials'])
    # B11: the enqueue-time baseline per AVD.
    av = load('round3/b11/analysis/b11-summary.json')['avds']
    k.update(lifeFourteenEnq=av['Fourteen']['violating_trials']['menqueue'],
             lifeFifteenEnq=av['Fifteen']['violating_trials']['menqueue'])
    # B4 v3: trials logged; the one invalid trial is the sender that waited its full deadline for the lock.
    sw = load('round3/b4/analysis-v3-repl/sweep-summary.json')
    k.update(sweepLogged=sw['logged'], sweepLockStalls=sum(x['reason'] == 'sender did not complete' for x in sw['invalid']))
    # Test 6 lifecycle on the rented phones: a paired trial violates if any affected tenant (T1, T2, T4, T5, T8) does,
    # as in the matched campaign; pooled over both phones and the pending, kill and revoke schedules.
    rows = load('round3/test6/analysis/matched-outcomes.json')['rows']
    trial = collections.defaultdict(bool)
    for r in rows:
        if r['tenant'] in (1, 2, 4, 5, 8):
            trial[r['run'], r['schedule'], r['instance'], r['trial'], r['variant']] |= r['violation'] > 0
    # Layered early (mlayer) and job-start (mstart) added 24/11 (C): the same paired trials, already in the frozen output.
    for key, v in (('Enq', 'menqueue'), ('Fence', 'mfence'), ('Layer', 'mlayer'), ('Start', 'mstart')):
        hits = [viol for t, viol in trial.items() if t[4] == v]
        k[f'devLife{key}Viol'], k[f'devLife{key}N'] = sum(hits), len(hits)
    assert len({k[f'devLife{key}N'] for key in ('Enq', 'Fence', 'Layer', 'Start')}) == 1   # the paper cites one N
    # Group 2 (PR #5, C 22/11). G2a: pooled over EDGE/3G/LTE; the delivered-abort counts are B's exploratory post-hoc.
    g = load('round3/g2close/analysis/g2close-summary.json')['cells']
    mode = lambda m, f: [c[f] for name, c in sorted(g.items()) if name.endswith('/' + m)]
    n = {sum(mode(m, 'trials')) for m in ('early', 'close', 'fence')}
    assert len(n) == 1
    ack = lambda m: [x['median'] for x in mode(m, 'withdraw_latency_ms')]
    ph = load('round3/g2close/posthoc/posthoc.json')['uncut_end_by_receiver']
    k.update(gcloseN=n.pop(), gcloseEarlyViol=sum(mode('early', 'violations')), gcloseCloseViol=sum(mode('close', 'violations')),
             gcloseFenceViol=sum(mode('fence', 'violations')), gcloseCut=sum(mode('close', 'cut')),
             gcloseCutComplete=sum(mode('close', 'cut_receiver_complete')), gcloseAckLo=min(ack('close')),
             gcloseAckHi=max(ack('close')), gcloseFenceAck=max(ack('fence')),
             gcloseAbortDelivered=ph.get('close/SEND_ERROR/receiver_complete', 0),
             gcloseFenceAbortDelivered=ph.get('fence/SEND_ERROR/receiver_complete', 0),
             gcloseFenceDelivered=sum(v for key, v in ph.items() if key.startswith('fence/') and key.endswith('/receiver_complete')))
    # G2b: same pooling as B2 (pending, kill, reboot), pre-registered oracle v2.
    gl = load('round3/g2layer/analysis/airguard-summary.json')['cells']
    cnt = lambda b, f: sum(gl[f'{s}/{b}'][f] for s in sched)
    nl = {cnt(b, 'trials') for b in ('stock', 'fenced', 'layered')}
    assert len(nl) == 1
    k.update(glayN=nl.pop(), glayStockViol=cnt('stock', 'violating_trials'), glayFenceViol=cnt('fenced', 'violating_trials'),
             glayLayerViol=cnt('layered', 'violating_trials'),
             glayUnknown=sum(cnt(b, 'unknown_trials') for b in ('stock', 'fenced', 'layered')))
    # Round-4 review (C, 22/11): Wilson 95% for the pooled race cells (percent, as raceObsPct).
    sys.path.insert(0, str(ART / 'scripts'))
    from summarize import wilson
    ns = set()
    for p, rel in (('race', 'round3/b10/analysis/race-summary.json'), ('racePhone', 'round3/test1-phone/analysis/race-summary.json')):
        rk = load(rel)['keys']   # both analyses name their keys race*; the phone's are renamed racePhone* above
        n = 3 * rk['raceTrials']; ns.add(n)
        lo, hi = wilson(sum(rk[f'race{prof}Layer'] for prof in ('Edge', 'Threeg', 'Lte')), n)[1:]
        k[p + 'ObsLo'], k[p + 'ObsHi'] = round(100 * lo, 1), round(100 * hi, 1)
        assert sum(rk[f'race{prof}Fence'] for prof in ('Edge', 'Threeg', 'Lte')) == 0   # raceZeroHi applies to the fence arms
    assert len(ns) == 1
    k['raceZeroHi'] = round(100 * wilson(0, ns.pop())[2], 1)
    k.update(group3(wilson))
    k.update(round4_df())
    # Commit-relative race outcomes (C, scripts/post_commit_race.py, exploratory).
    pc = R / 'round3/c-analysis/post-commit.json'
    if pc.exists():
        k.update(json.loads(pc.read_text(encoding='utf-8'))['keys'])
    # Receiver side of the natural races (C, scripts/receiver_race.py, from the same frozen raw logs).
    rr = R / 'round3/c-analysis/receiver-race.json'
    if rr.exists():
        k.update(json.loads(rr.read_text(encoding='utf-8'))['keys'])
    return k


def group3(wilson):
    """Group 3 (issue #7, PR #8; C 24/11), read from B's frozen analysis outputs; nothing is re-run. Card per run in plans/.
    Floats that the paper prints with two decimals are returned as strings (render_tests.esc prints floats with one)."""
    k, pct = {}, lambda x: round(100 * x, 1)
    # G3a (g3race-card.md): five arms in the same blocks, EDGE/3G/LTE pooled; primary = trials accepted after W.
    c = load('round3/g3race/analysis/g3race-summary.json')['cells']
    arm = lambda a, f: sum(x[f] for name, x in c.items() if name.split('/')[1] == a)
    n = {arm(a, 'trials') for a in ('early', 'close', 'close2', 'fence', 'fence-abort')}
    assert len(n) == 1
    k.update(gtrN=n.pop(), gtrEarlyW=arm('early', 'after_w'), gtrCloseW=arm('close', 'after_w'),
             gtrCloseTwoW=arm('close2', 'after_w'), gtrFenceW=arm('fence', 'after_w'), gtrAbortW=arm('fence-abort', 'after_w'),
             gtrCloseLte=c['lte/close']['after_w'], gtrEarlyAck=arm('early', 'violations_after_ack'),
             gtrCancelAck=arm('close', 'violations_after_ack') + arm('close2', 'violations_after_ack'))
    # G3b, same trials: request payload in the host capture after the ack marker (any phase), per arm; all 90 matched.
    cap = {a: sum(x['capture']['trials_after_marker'] for name, x in c.items() if name.split('/')[1] == a)
           for a in ('early', 'close', 'close2', 'fence', 'fence-abort')}
    assert all(x['capture']['status'] == {'matched': x['trials']} for x in c.values())
    k.update(gtrCapLo=min(cap.values()), gtrCapHi=max(cap.values()))
    # P3 (g3lte-card.md, protocol v5): LTE only, exposure balanced; same primary. Ack p95 = nearest-rank, ms.
    p = load('round3/g3race/analysis-lte5/g3race-summary.json')['cells']
    au = load('round3/g3race/analysis-lte5/g3race-audit.json')['cells']
    n = {x['trials'] for x in p.values()}
    assert len(n) == 1
    k.update(gpN=n.pop(), gpEarlyW=p['lte/early']['after_w'], gpCloseW=p['lte/close']['after_w'],
             gpCloseExposed=au['lte/close']['exposed'], gpEarlyExposed=au['lte/early']['exposed'], gpCloseTwoW=p['lte/close2']['after_w'], gpFenceW=p['lte/fence']['after_w'],
             gpAbortW=p['lte/fence-abort']['after_w'], gpFenceAckP=p['lte/fence']['withdraw_latency_ms']['p95'],
             gpAbortAckP=p['lte/fence-abort']['withdraw_latency_ms']['p95'],
             gpCloseTwoAckP=p['lte/close2']['withdraw_latency_ms']['p95'])
    # P4 (g3p4-card.md): SO_SNDBUF level x fence / fence-abort, EDGE and 3G. Primary: TLS application data after the ack
    # marker in trials whose W fell during the writes; level 0 = no setSendBufferSize (kernel autotuning).
    s = load('round3/g3race/analysis-p4/g3p4-summary.json')
    cells, pr = s['cells'], s['paired_during_writes_app_bytes']
    n = {x['trials'] for x in cells.values()}
    assert len(n) == 1
    med = lambda lvl: [x['by_phase']['during writes']['app_bytes']['median'] for name, x in cells.items()
                       if name.split('/')[1] == 'fence' and name.endswith(f'sndbuf={lvl}')]
    ab = [x['by_phase']['during writes']['app_bytes'] for name, x in cells.items() if name.split('/')[1] == 'fence-abort']
    dflt = {v for name, x in cells.items() if name.endswith('sndbuf=0') for v in x['actual_sndbuf']}
    assert len(dflt) == 1
    k.update(gsN=n.pop(), gsAfterW=sum(x['after_w'] for x in cells.values()),
             gsFenceSmallLo=round(min(med(16384)) / 1000, 1), gsFenceSmallHi=round(max(med(16384)) / 1000, 1),
             gsFenceMidLo=round(min(med(65536)) / 1000, 1), gsFenceMidHi=round(max(med(65536)) / 1000, 1),
             gsFenceDefLo=f"{min(med(0)) / 1e6:.2f}", gsFenceDefHi=f"{max(med(0)) / 1e6:.2f}",
             gsAbortMax=f"{max(a['max'] for a in ab):,}", gsAbortMed=int(max(a['median'] for a in ab)), gsPairs=sum(x['pairs'] for x in pr.values()),
             gsAbortLess=sum(x['abort_less'] for x in pr.values()), gsDefaultKib=int(dflt.pop()) // 1024)
    # G3c v4 (g3app-card.md, analysis-v4-r2 = receiver window corrected 23/11). Primary: payload sent after the ack (capture);
    # receiver-complete after the ack is secondary.
    b = load('round3/g3app/analysis-v4-r2/g3app-summary.json')['builds']
    n = {x['trials'] for x in b.values()}
    assert len(n) == 1
    # Before the 23/11 correction (analysis-v4, window marker + 600 s), reported next to the corrected count.
    k['gaFenceRxFirst'] = load('round3/g3app/analysis-v4/g3app-summary.json')['builds']['fenced']['receiver_complete_after_ack']
    k.update(gaN=n.pop(), gaSentMin=min(x['sent_after_ack'] for x in b.values()),
             gaSentMax=max(x['sent_after_ack'] for x in b.values()),
             gaStockRx=b['stock']['receiver_complete_after_ack'], gaCancelRx=b['stockcancel']['receiver_complete_after_ack'],
             gaLayerRx=b['layered']['receiver_complete_after_ack'], gaFenceRx=b['fenced']['receiver_complete_after_ack'])
    # G3c v5c (g3app5-card.md): stockcancel16 / stockcancel / fenced in the same trials; primary = receiver-complete after
    # the ack, Wilson 95%; kernel send buffer from guest ss (skmem tb).
    v = load('round3/g3app/analysis-v5c/g3app5-summary.json')
    bb, pp = v['builds'], v['paired']['stockcancel16_vs_fenced']['receiver_complete_after_ack']
    tb = lambda x: {int(t) for t in bb[x]['donation_sockdiag_tb'] if t != 'missing'}
    assert len(tb('stockcancel16') | tb('fenced')) == 1 and len(tb('stockcancel')) == 1
    for key, x in (('Sixteen', 'stockcancel16'), ('Cancel', 'stockcancel'), ('Fence', 'fenced')):
        lo, hi = bb[x]['receiver_complete_after_ack_wilson95']
        k.update({f'gb{key}N': bb[x]['receiver_trials'], f'gb{key}Rx': bb[x]['receiver_complete_after_ack'],
                  f'gb{key}Lo': pct(lo), f'gb{key}Hi': pct(hi)})
    k.update(gbPairSixteenOnly=pp.get('stockcancel16=1/fenced=0', 0), gbPairFenceOnly=pp.get('stockcancel16=0/fenced=1', 0),
             gbPairBoth=pp.get('stockcancel16=1/fenced=1', 0), gbPairNone=pp.get('stockcancel16=0/fenced=0', 0),
             gbKernSmallKib=tb('fenced').pop() // 1024, gbKernDefKib=tb('stockcancel').pop() // 1024)
    # Exploratory (followup/diag_g3app5.py, after the data): stockcancel16 trials where the withdrawal fell during the
    # donation, Call.cancel() found no registered call, and the sink still logged the body complete.
    d = load('round3/g3app/analysis-v5c/diag-v5c.json')['rows']
    k['gbNoCallRx'] = sum(r['trial'].endswith('-stockcancel16') and r['placement'] == 'during' and r['cancel_cut'] == 'no call'
                          and r['complete_after_ack'] for r in d)
    # G3d v4 (g3cost-card.md): Galaxy A06, Wi-Fi, foreground; ratios of medians fence/early per size.
    g = load('round3/g3cost/analysis-v4/g3cost-summary.json')
    r = [x for key, x in g['ratios_of_medians'].items() if key.startswith('fence/early/')]
    bs = load('round3/g3cost/analysis-v4/batterystats-check.json')['final-v4']
    k.update(gdCells=g['logged_cells'] - len(g['invalid']), gdUploads=sum(x['uploads_ok'] for x in g['cells'].values()),
             gdUploadFail=sum(x['uploads_failed'] for x in g['cells'].values()),
             gdCpuLo=f"{min(x['cpu_ms_per_mib'] for x in r):.2f}", gdCpuHi=f"{max(x['cpu_ms_per_mib'] for x in r):.2f}",
             gdTimeLo=f"{min(x['elapsed_ms'] for x in r):.2f}", gdTimeHi=f"{max(x['elapsed_ms'] for x in r):.2f}",
             gdEnergyNonzero=bs['uid_mah_nonzero'], gdEnergyCells=bs['cells'])
    return k


def round4_df():
    """Round 4 on AWS Device Farm, Pixel 8a (PR #13; cards plans/r4df-*-card.md), read from B's frozen analysis outputs.
    C 25/11. Reboot was dropped (Device Farm ignored adb reboot), so there are no reboot keys."""
    k = {}
    D = 'round3/phone-r4/aws'
    c = load(f'{D}/g3a/analysis/g3race-summary.json')['cells']
    n = {x['trials'] for x in c.values()}
    assert len(n) == 1
    k['dfN'] = n.pop(); k['dfArmN'] = 3 * k['dfN']
    arms = {'Early': 'early', 'Close': 'close', 'CloseTwo': 'close2', 'Fence': 'fence', 'Abort': 'fence-abort'}
    profs = {'Edge': 'edge', 'Umts': 'umts', 'Lte': 'lte'}
    for ak, a in arms.items():
        for pk, p in profs.items():
            k[f'df{ak}{pk}'] = c[f'{p}/{a}']['after_w']
        k[f'df{ak}All'] = sum(k[f'df{ak}{pk}'] for pk in profs)
    k['dfEarlyAck'] = sum(c[f'{p}/early']['violations_after_ack'] for p in profs.values())
    k['dfCancelAck'] = sum(c[f'{p}/{a}']['violations_after_ack'] for p in profs.values() for a in ('close', 'close2'))
    lat = lambda a: c[f'lte/{a}']['withdraw_latency_ms']
    k.update(dfCloseLteAckMed=lat('close')['median'], dfFenceAckP=lat('fence')['p95'], dfAbortAckP=lat('fence-abort')['p95'],
             dfCloseTwoAckP=lat('close2')['p95'])
    # Lifecycle under network loss: a paired trial violates if any affected tenant does (as devLife*).
    rows = load(f'{D}/life/analysis/matched-outcomes.json')['rows']
    trial = collections.defaultdict(bool)
    for r in rows:
        if r['tenant'] in (1, 2, 4, 5, 8):
            trial[r['schedule'], r['instance'], r['trial'], r['variant']] |= r['violation'] > 0
    assert {t[0] for t in trial} == {'netloss'}
    nn = collections.Counter(t[3] for t in trial)
    assert len(set(nn.values())) == 1
    k['dfNetN'] = next(iter(nn.values()))
    for key, v in (('Enq', 'menqueue'), ('Start', 'mstart'), ('Layer', 'mlayer'), ('Fence', 'mfence'), ('Both', 'mboth')):
        k[f'dfNet{key}'] = sum(x for t, x in trial.items() if t[3] == v)
    # AirGuard: stock/fenced/layered in every trial; pending, kill, netloss.
    ag = load(f'{D}/airguard/analysis/airguard-summary.json')['cells']
    n = {x['trials'] for x in ag.values()}
    assert len(n) == 1
    k['dfAirN'] = n.pop()
    k['dfAirStockPK'] = ag['pending/stock']['violating_trials'] + ag['kill/stock']['violating_trials']
    k['dfAirPKN'] = 2 * k['dfAirN']
    k['dfAirFence'] = sum(ag[f'{s}/fenced']['violating_trials'] for s in ('pending', 'kill', 'netloss'))
    k['dfAirLayer'] = sum(ag[f'{s}/layered']['violating_trials'] for s in ('pending', 'kill', 'netloss'))
    k['dfAirNetStock'] = ag['netloss/stock']['violating_trials']
    k['dfAirUnknown'] = sum(x['unknown_trials'] for x in ag.values())
    k['dfAirNetDeficitMin'] = min(ag[f'netloss/{b}']['deficit_trials'] for b in ('stock', 'fenced', 'layered'))
    # Exploratory timing of the same-process cancellation cases (C, scripts/r4df_close2_timing.py).
    tp = R / 'round3/c-analysis/r4df-close2-timing.json'
    if tp.exists():
        t = json.loads(tp.read_text(encoding='utf-8'))['keys']
        assert t['dfCloseTwoTimed'] == k['dfCloseTwoAll']
        k.update(t)
    return k


def main():
    names, out, used = schema(), {}, []
    for path, field in SRC:
        if not path.exists(): continue
        vals = json.loads(path.read_text()).get(field, {})
        out.update({k: v for k, v in vals.items() if k in names and v is not None}); used.append(str(path.relative_to(ART)))
    extra = derived()
    out.update({k: v for k, v in extra.items() if k in names}); used.append('derived() keys (C, 21/11)')
    dest = R / 'round3/summary.json'
    dest.write_text(json.dumps(dict(sorted(out.items())), indent=1, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    print(f'summary.json: {len(out)} keys from {used}; missing {len(names - set(out))} of {len(names)}')


if __name__ == '__main__':
    main()
