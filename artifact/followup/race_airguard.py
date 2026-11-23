#!/usr/bin/env python3
"""Group 3, test G3c (g3app-card.md): AirGuard with the withdrawal during a donation upload. Emulator, root.

Builds (realapp/airguard/build_g3.sh): stock (Retrofit), stockcancel (Retrofit + Call.cancel() on switch-off), fenced (B2
design), layered (G2b design), each with the G3 hooks (donation end, WITHDRAW_DONE, marker). Sink airguard_sink.py ports
stockcancel 8793, layered 8795, stock 8796, fenced 8797.
G3c v5 (g3app5-card.md, 23/11): build stockcancel16 (stockcancel + OkHttp SO_SNDBUF 16384), sink port 8794; run with
--variants stockcancel16,stockcancel,fenced --apkdir realapp/airguard/build/g3v5. Every v5 build logs SOCKET_CONFIG actual_sndbuf.
Per trial k: the builds one after another in an order shuffled from the seed; one u ~ U(0,1) per trial (same for every build).
Per build: pm clear -> grant -> [v4: wait for the app's startup donation worker (its get_token at the sink, max 30 s) + 3 s]
-> insert N 'pre' beacons (one device) -> start marker (hook op mark: the app connects to the
marker port with id <tid>-start) -> run the donation worker -> at W = u * D (host monotonic, from the run hook) the app's own withdrawal path
(hook withdraw: consent log, preference, scheduler [, cancel]; then WITHDRAW_DONE and the app's marker connection with the
trial id) -> wait for the donation end event (max 4 D + 30 s) -> read events -> force-stop.
D per build = calibrated host time from the run hook to the sink's donate_data log (median of --calibrate sends, no withdrawal).
Network: guest netem egress on eth0 (B10 v3 profile, default umts) inside a prio root; the marker port goes through the
unshaped band. Capture: `-tcpdump <run>/capture.pcap` at emulator launch (pcap, guest frames; the console command takes bare names only).
Outcomes are read only by analyze_g3app.py.
Usage: race_airguard.py --serial emulator-5666 --avd P04AvdA --apkdir realapp/airguard/build/g3 --out DIR
       (--calibrate 3 | --trials 30 --durations F) [--variants stock,stockcancel,fenced,layered] [--nbeacons 1500]
"""
import argparse, contextlib, hashlib, json, os, random, socketserver, statistics, subprocess, sys, threading, time
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
SDK = os.environ.get('ANDROID_HOME', str(ART.parents[1] / 'shared-android/sdk')); ADB = os.environ.get('ADB', f'{SDK}/platform-tools/adb')
PKG = 'de.seemoo.at_tracking_detection.p04'; HOOK = 'de.seemoo.at_tracking_detection.residue.TestHooks'
PORTS = {'stockcancel': 8793, 'stockcancel16': 8794, 'layered': 8795, 'stock': 8796, 'fenced': 8797}
TC = {'edge': ('118400bit', '240ms'), 'umts': ('128kbit', '118ms'), 'lte': ('58mbit', '0ms')}
p = argparse.ArgumentParser()
p.add_argument('--serial', required=True); p.add_argument('--avd', default=''); p.add_argument('--apkdir', type=Path, required=True)
p.add_argument('--out', type=Path, required=True); p.add_argument('--variants', default='stock,stockcancel,fenced,layered')
p.add_argument('--profile', default='umts'); p.add_argument('--nbeacons', type=int, default=1500)
p.add_argument('--calibrate', type=int, default=0); p.add_argument('--trials', type=int, default=0); p.add_argument('--start', type=int, default=0)
p.add_argument('--durations', type=Path); p.add_argument('--seed', default='g3app-20261122')
p.add_argument('--nbeacons-auto', type=Path, help='recalibration (g3app-card §3): N = ceil(N_F * 262144 / median body bytes of F)')
p.add_argument('--marker', type=int, default=8799); p.add_argument('--capture', action='store_true')
a = p.parse_args()
assert bool(a.calibrate) != bool(a.trials), 'give exactly one of --calibrate / --trials'
assert a.trials == 0 or a.durations, '--trials needs --durations'
assert not a.out.exists(), f'refusing: {a.out} exists (fresh directory rule)'
a.out.mkdir(parents=True)
V = a.variants.split(','); PK = {v: PKG + v for v in V}
if a.nbeacons_auto:
    import math; F = json.loads(a.nbeacons_auto.read_text())
    a.nbeacons = min(6000, math.ceil(F['nbeacons'] * 262144 / statistics.median(b for xs in F['body_bytes'].values() for b in xs)))   # cap: insert time
if a.durations and 'nbeacons' in json.loads(a.durations.read_text()): a.nbeacons = json.loads(a.durations.read_text())['nbeacons']   # final: the calibrated N
LOG = (a.out / 'trials.jsonl').open('a')


def adb(*args, timeout=90, check=False):
    r = subprocess.run([ADB, '-s', a.serial, *map(str, args)], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode: raise RuntimeError(f'adb {args[:3]}: {r.stderr.strip()[:200]}')
    return r.stdout


def sh(c, timeout=90): return adb('shell', c, timeout=timeout)
def alive():
    try: return sh('getprop sys.boot_completed', 20).strip() == '1'
    except Exception: return False


def boot():
    if alive(): return
    if not a.avd: raise RuntimeError('device not alive and no --avd')
    port = a.serial.split('-')[1]
    subprocess.Popen([f'{SDK}/emulator/emulator', '-avd', a.avd, '-port', port, '-read-only', '-no-window', '-no-audio', '-no-boot-anim',
                      '-gpu', 'host', '-no-snapshot'] + (['-tcpdump', str((a.out / 'capture.pcap').resolve())] if a.capture else []),
                     stdout=open(a.out / f'emu{port}.log', 'a'), stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 300 and not alive(): time.sleep(3)
    if not alive(): raise RuntimeError('emulator did not boot')


def hook(v, op, timeout=90, **kw):
    cmd = f'am broadcast -n {PK[v]}/{HOOK} --es op {op}'
    for k, x in kw.items(): cmd += f" --{'ei' if isinstance(x, int) else 'es'} {k} {x}"
    out = sh(cmd, timeout); return 'data="ok"' in out, out.strip()[-160:]


def events(v):
    return [json.loads(l) for l in sh(f'cat /data/data/{PK[v]}/files/residue-events.jsonl 2>/dev/null').splitlines() if l.startswith('{')]


def net(profile):
    add = ''
    if profile in TC:
        r, d = TC[profile]
        add = (f'; tc qdisc add dev eth0 root handle 1: prio bands 3 priomap 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1'
               f'; tc qdisc add dev eth0 parent 1:1 handle 10: pfifo limit 1000'
               f'; tc qdisc add dev eth0 parent 1:2 handle 20: netem delay {d} rate {r} limit 10000'
               f'; tc filter add dev eth0 parent 1: protocol ip prio 1 u32 match ip dport {a.marker} 0xffff flowid 1:1')
    sh(f'tc qdisc del dev eth0 root 2>/dev/null{add}; true')
    return sh('tc -s qdisc show dev eth0; tc filter show dev eth0; true').replace('\r', '').replace('\n', ' | ').strip()[:4000]


# marker listener (host): logs host arrival and the id the guest writes; host clock only
GUARD = threading.Lock()
class Srv(socketserver.ThreadingTCPServer): allow_reuse_address = True; daemon_threads = True
class Marker(socketserver.BaseRequestHandler):
    def handle(self):
        t = time.monotonic_ns(); self.request.settimeout(10); d = b''
        with contextlib.suppress(Exception):
            while not d.endswith(b'\n') and len(d) < 200:
                b = self.request.recv(200)
                if not b: break
                d += b
        with GUARD, (a.out / 'marker.jsonl').open('a') as f:
            f.write(json.dumps({'host_ns': t, 'peer_port': self.client_address[1], 'id': d.decode(errors='replace').strip()}) + '\n')
msrv = Srv(('127.0.0.1', a.marker), Marker); threading.Thread(target=msrv.serve_forever, daemon=True).start()
sink = subprocess.Popen([sys.executable, str(ART / 'followup/airguard_sink.py'), '--out', str(a.out / 'sink'), '--ports', ','.join(str(PORTS[v]) for v in sorted(V, key=PORTS.get))],
                        stdout=open(a.out / 'sink.log', 'a'), stderr=subprocess.STDOUT)


def sink_after(port, t0_ns, path):
    f = a.out / 'sink/ingest.jsonl'
    if not f.exists(): return None
    for l in f.read_text().splitlines():
        with contextlib.suppress(ValueError):
            x = json.loads(l)
            if x.get('port') == port and x.get('path') == path and x['host_ns'] > t0_ns: return x['host_ns'], x.get('bytes')
    return None


def sink_donate_after(port, t0_ns): return sink_after(port, t0_ns, 'donate_data')


def after_run(ev):
    """v4: events logged after RUN_ENQUEUED (file order), so only the run hook's donation counts."""
    i = next((j for j, e in enumerate(ev) if e['kind'] == 'RUN_ENQUEUED'), None)
    return [] if i is None else ev[i + 1:]


STARTUP_WAIT_S, STARTUP_SETTLE_S = 30, 3


END = ('DONATION_OK', 'DONATION_ERROR', 'DONATION_BLOCKED')


def one(k, v, u, D):
    tid = f'g3app-{k:03d}-{v}'
    r = {'trial': tid, 'k': k, 'variant': v, 'u': u, 'D_s': D, 'host_load': os.getloadavg(), 'start': time.time(), 'actions': []}
    act = lambda name, **kw: r['actions'].append({'t': time.time(), 'a': name, **kw})
    try:
        sh(f'pm clear {PK[v]}'); sh(f'pm grant {PK[v]} android.permission.POST_NOTIFICATIONS 2>/dev/null'); act('reset')
        t_g = time.monotonic_ns(); ok, out = hook(v, 'grant'); act('grant', ok=ok, out=out)
        # v4 (g3app-card Pilot log): the grant hook schedules the app's periodic donation worker, which runs at once (ping,
        # get_token, then reads the beacon table). Wait for its get_token at the sink, then settle, so it reads an empty table
        # before the insert and the upload is started by the run hook.
        t1 = time.monotonic(); seen = None
        while time.monotonic() - t1 < STARTUP_WAIT_S and not (seen := sink_after(PORTS[v], t_g, 'get_token')): time.sleep(0.5)
        time.sleep(STARTUP_SETTLE_S); act('startup_worker', seen=bool(seen), waited=round(time.monotonic() - t1, 1))
        ok, out = hook(v, 'insert', timeout=300, addr=f'AA:00:00:03:{k // 100 % 100:02d}:{k % 100:02d}', n=a.nbeacons, age_s=0); act('insert', ok=ok, out=out)
        time.sleep(1.5)
        ok, out = hook(v, 'mark', tid=f'{tid}-start', marker=a.marker); act('start_marker', ok=ok, out=out)
        t_run = time.monotonic_ns(); ok, out = hook(v, 'run'); act('run', ok=ok, out=out)
        deadline = 4 * D + 30 if D else 120
        if u is not None:
            time.sleep(max(0.0, (t_run + u * D * 1e9 - time.monotonic_ns()) / 1e9))
            r['withdraw_host_offset_s'] = (time.monotonic_ns() - t_run) / 1e9
            ok, out = hook(v, 'withdraw', tid=tid, marker=a.marker); act('withdraw', ok=ok, out=out)
        t0 = time.monotonic(); ev = []
        while time.monotonic() - t0 < deadline:
            ev = events(v)
            if any(e['kind'] in END for e in after_run(ev)) and (u is None or any(e['kind'] == 'MARKER_SENT' and f'tid={tid};' in e['detail'] for e in ev)): time.sleep(3); ev = events(v); break
            time.sleep(1)
        act('quiesced', waited=round(time.monotonic() - t0, 1)); r['events'] = ev
        ks = [e['kind'] for e in ev]; r['donation_before_run'] = 'DONATION_START' in ks[:ks.index('RUN_ENQUEUED')] if 'RUN_ENQUEUED' in ks else None
        if u is None and r['donation_before_run'] is False:   # v4: a calibration sample only from a run-hook upload
            got = sink_donate_after(PORTS[v], t_run); r['calib_s'] = (got[0] - t_run) / 1e9 if got else None; r['calib_bytes'] = got[1] if got else None
        sh(f'am force-stop {PK[v]}'); act('stopped'); r['device_alive_end'] = alive()
    except Exception as e: act('trial_error', err=repr(e)[:200])
    r['finished'] = time.time(); LOG.write(json.dumps(r) + '\n'); LOG.flush()
    print(time.strftime('%H:%M:%S'), tid, [x['a'] for x in r['actions'] if x['a'] == 'trial_error'] or [e['kind'] for e in r.get('events', []) if e['kind'] in END], flush=True)
    return r


try:
    boot(); adb('root'); time.sleep(2); adb('wait-for-device')
    sh('svc wifi disable; svc data enable'); time.sleep(8)
    radio = {'routes': sh('ip route').strip()[:400]}
    for v in V: adb('install', '-r', '-g', a.apkdir / f'airguard-{v}.apk', timeout=180, check=True)
    warm = {}
    for v in V:
        t0 = time.time(); out = sh(f'am broadcast -n {PK[v]}/{HOOK} --es op noop', timeout=300); warm[v] = {'s': round(time.time() - t0, 1), 'ok': 'data="ok"' in out}
    durations = json.loads(a.durations.read_text())['median_s'] if a.durations else {}
    meta = {'serial': a.serial, 'avd': a.avd, 'variants': V, 'ports': {v: PORTS[v] for v in V}, 'profile': a.profile, 'nbeacons': a.nbeacons,
            'calibrate': a.calibrate, 'trials': a.trials, 'start': a.start, 'seed': a.seed, 'durations': durations, 'marker': a.marker,
            'capture': a.capture, 'warmup': warm, 'radio': radio, 'fingerprint': sh('getprop ro.build.fingerprint').strip(),
            'apks': {v: hashlib.sha256((a.apkdir / f'airguard-{v}.apk').read_bytes()).hexdigest() for v in V}, 'started': time.time()}
    (a.out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    meta_net = net(a.profile); (a.out / 'net.json').write_text(json.dumps({'tc': meta_net}) + '\n')
    if a.calibrate:
        res, nb = {}, {}
        for k in range(a.calibrate):
            for v in V:
                r_ = one(k, v, None, 0)
                if r_.get('calib_s'): res.setdefault(v, []).append(r_['calib_s']); nb.setdefault(v, []).append(r_.get('calib_bytes'))
        (a.out / 'calibration.json').write_text(json.dumps({'samples_s': res, 'median_s': {v: statistics.median(x) for v, x in res.items()},
                                                            'body_bytes': nb, 'nbeacons': a.nbeacons}, indent=1) + '\n')
    else:
        if a.capture:
            (a.out / 'capture.json').write_text(json.dumps({'mode': 'emulator -tcpdump at launch', 'trials_start': time.time()}) + '\n')
        for k in range(a.start, a.start + a.trials):
            order = list(V); random.Random(f'{a.seed}-{k}').shuffle(order); u = random.Random(f'{a.seed}-{k}-u').random()
            for v in order: one(k, v, u, durations.get(v, 0.0))
        if a.capture:
            c0 = json.loads((a.out / 'capture.json').read_text()); c0.update(trials_end=time.time())
            (a.out / 'capture.json').write_text(json.dumps(c0) + '\n')
        (a.out / 'net_end.json').write_text(json.dumps({'tc': sh('tc -s qdisc show dev eth0; true').strip()[:4000]}) + '\n')
finally:
    with contextlib.suppress(Exception): net('full'); sh('svc wifi enable')
    sink.terminate(); msrv.shutdown()
