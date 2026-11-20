#!/usr/bin/env python3
"""Test 1 (B10): natural race on a throttled emulator network, layered early vs fence (TLS fixture app).

No barrier: the withdrawal is sent at W = u * D after the send starts, u ~ U(0,1) from the seed, D = the calibrated upload
time of that (profile, payload) cell. Outcome (read later by analyze_race.py, never here): bytes accepted after the
withdrawal acknowledgement, from the app's own event log (as followup/analyze_tls.py).
Modes:  --calibrate N  : N sends per (profile, size) without withdrawal → calibration.json (median upload time per cell)
        --trials N     : N trials per (profile, mode, size) cell with --durations calibration.json
Design: blocks; one block = every (profile, mode, size) cell once, order shuffled per block from the seed.
Network: emulator console `network speed <p>` / `network delay <p>` set before every trial (verified by calibration).
         v3 `--shaper tc`: the console setting does not throttle this image (pilot-calib2/3), so the same profiles are applied
         in the guest instead: netem egress (upload direction) on eth0 and wlan0 at the emulator's nominal uplink rate and
         the midpoint of its delay range (edge 118.4 kbit/s 240 ms, umts 128 kbit/s 118 ms, lte 58 Mbit/s 0 ms).
Phones: --receiver http://IP:8800 --host IP --no-root --certdir DIR (CA of the receiver cert) [--serial <adb serial>]
Usage: race_suite.py --serial emulator-5650 [--avd P04Avd14] --out DIR (--calibrate 3 | --trials 10 --durations F)
       [--profiles edge,umts,lte] [--sizes 32768,262144,2097152] [--seed race-20261119]
"""
from pathlib import Path
import argparse, contextlib, hashlib, json, os, random, socketserver, ssl, statistics, subprocess, threading, time, uuid

A = Path(__file__).resolve().parents[1]; PKG = 'org.residuelab.tls'
SDK = os.environ.get('ANDROID_HOME', str(A.parents[1] / 'shared-android/sdk'))
p = argparse.ArgumentParser()
p.add_argument('--serial', required=True); p.add_argument('--avd', default=''); p.add_argument('--out', type=Path, required=True)
p.add_argument('--profiles', default='edge,umts,lte'); p.add_argument('--sizes', default='32768,262144,2097152')
p.add_argument('--modes', default='early,fence'); p.add_argument('--calibrate', type=int, default=0)
p.add_argument('--trials', type=int, default=0); p.add_argument('--start', type=int, default=0)
p.add_argument('--durations', type=Path); p.add_argument('--seed', default='race-20261119')
p.add_argument('--certdir', type=Path, default=A / 'followup/tls-cert')
p.add_argument('--receiver', help='phones: receiver mode B control URL (http://IP:8800, followup/receiver_b.py); shaping via its tc API')
p.add_argument('--token', default=os.environ.get('P04_TOKEN', ''), help='control API token (env P04_TOKEN; never stored)')
p.add_argument('--host', help='phones: sink address passed to the app with each send (receiver host IP)')
p.add_argument('--no-root', action='store_true', help='phones: no adb root (debuggable app, run-as only)')
p.add_argument('--shaper', default='emu', choices=['emu', 'tc'], help='v3 tc: guest netem egress shaping (see Network)')
p.add_argument('--radio', action='store_true', help='v2: Wi-Fi off, data over the emulated cellular radio (where netspeed applies)')   # test-ca.pem + test-key.pem (key never committed)
a = p.parse_args()
assert bool(a.calibrate) != bool(a.trials), 'give exactly one of --calibrate / --trials'
assert a.trials == 0 or a.durations, '--trials needs --durations (calibration.json)'
assert not a.out.exists(), f'refusing: {a.out} exists (fresh directory rule)'
a.out.mkdir(parents=True)
ADB = os.environ.get('ADB', str(Path(SDK) / 'platform-tools/adb'))
PROFILES, SIZES, MODES = a.profiles.split(','), [int(x) for x in a.sizes.split(',')], a.modes.split(',')
DELAY = {'edge': 'edge', 'umts': 'umts', 'lte': 'none', 'gprs': 'gprs', 'full': 'none'}


def adb(*args, timeout=60):
    r = subprocess.run([ADB, '-s', a.serial, *map(str, args)], capture_output=True, text=True, timeout=timeout)
    if r.returncode: raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout


def alive():
    try: return adb('shell', 'getprop', 'sys.boot_completed', timeout=20).strip() == '1'
    except Exception: return False


def boot():
    if alive() or not a.avd: return
    port = a.serial.split('-')[1]
    subprocess.Popen([f'{SDK}/emulator/emulator', '-avd', a.avd, '-port', port, '-read-only', '-no-window', '-no-audio',
                      '-no-boot-anim', '-gpu', 'host', '-no-snapshot'], stdout=open(a.out / f'emu{port}.log', 'a'),
                     stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 300 and not alive(): time.sleep(3)
    if not alive(): raise RuntimeError('emulator did not boot')
    adb('root'); time.sleep(3); adb('wait-for-device')


def bc(op, id, remote=False, **kw):
    cmd = ['shell', 'am', 'broadcast', '-n', PKG + '/org.residuelab.Revision' + ('Remote' if remote else ''), '-a', 'rl.REVISION',
           '--es', 'op', op, '--es', 'id', id]
    if op == 'send' and a.host: kw['host'] = a.host
    for k, v in kw.items():
        cmd += ['--ez' if isinstance(v, bool) else '--ei' if isinstance(v, int) else '--es', k, str(v).lower() if isinstance(v, bool) else str(v)]
    return adb(*cmd)


def events():
    rows = []
    for l in adb('shell', f'run-as {PKG} cat files/revision.jsonl').splitlines():
        with contextlib.suppress(ValueError): rows.append(json.loads(l))
    return rows


TC = {'edge': ('118400bit', '240ms'), 'umts': ('128kbit', '118ms'), 'lte': ('58mbit', '0ms')}


def ctl(method, path):
    import urllib.request
    req = urllib.request.Request(a.receiver.rstrip('/') + path, method=method, headers={'X-Token': a.token})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read().decode()


def net(profile):
    if a.receiver: return ctl('POST', f'/profile/{profile}')[:300]   # remote receiver shapes its ingress (upload) and egress
    if a.shaper == 'tc':
        adb('emu', 'network', 'speed', 'full'); adb('emu', 'network', 'delay', 'none')
        for dev in ('eth0', 'wlan0'):                 # a profile without a TC entry ('full', end of run) = shaping removed
            add = f'; tc qdisc replace dev {dev} root netem delay {TC[profile][1]} rate {TC[profile][0]} limit 10000' if profile in TC else ''
            adb('shell', f'tc qdisc del dev {dev} root 2>/dev/null{add}; true')
        return adb('shell', 'tc qdisc show dev eth0; tc qdisc show dev wlan0; true').replace('\r', '').replace('\n', ' | ').strip()[:300]
    o1 = adb('emu', 'network', 'speed', profile); o2 = adb('emu', 'network', 'delay', DELAY.get(profile, 'none'))
    return (o1 + o2).replace('\r', '').replace('\n', ' ').strip()


# receiver (as tls_suite.py): TLS on 8798, independent log of what arrived
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.minimum_version = ctx.maximum_version = ssl.TLSVersion.TLSv1_2
if not a.receiver: ctx.load_cert_chain(a.certdir / 'test-ca.pem', a.certdir / 'test-key.pem')
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True; daemon_threads = True
    def log(self, r):
        with self.guard, (a.out / 'receiver.jsonl').open('a') as f: f.write(json.dumps({'host_ns': time.monotonic_ns(), **r}) + '\n')
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        id = None; total = 0; expected = None
        try:
            self.request.settimeout(600)
            with ctx.wrap_socket(self.request, server_side=True) as s:
                h = b''
                while not h.endswith(b'\r\n\r\n'):
                    b = s.recv(1)
                    if not b: raise EOFError('header')
                    h += b
                hd = dict(l.split(': ', 1) for l in h.decode().split('\r\n')[1:] if ': ' in l); id = hd['X-Request-ID']; expected = int(hd['Content-Length'])
                self.server.log({'request': id, 'event': 'headers', 'expected': expected})
                while total < expected:
                    b = s.recv(min(65536, expected - total))
                    if not b: break
                    total += len(b)
                self.server.log({'request': id, 'event': 'body', 'received': total, 'expected': expected, 'complete': total == expected})
                if total == expected: s.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        except Exception as e: self.server.log({'request': id, 'event': 'error', 'error': repr(e), 'received': total, 'expected': expected})
sink = None
if not a.receiver:                                # phones: the receiver runs remotely (receiver_b.py)
    sink = Server(('127.0.0.1', 8798), Handler); sink.guard = threading.Lock(); threading.Thread(target=sink.serve_forever, daemon=True).start()

boot()
if not a.no_root: adb('root'); time.sleep(2)
adb('wait-for-device')
RADIO = {}
if a.radio:
    adb('shell', 'svc wifi disable'); adb('shell', 'svc data enable'); time.sleep(8)
    RADIO = {'routes': adb('shell', 'ip route').strip()[:400], 'active': adb('shell', 'dumpsys connectivity | grep -m2 -i "Active default network\\|NetworkAgentInfo"; true').strip()[:400]}   # metadata only: no match must not abort
apk = A / 'fixture/build/tls-apk/rl-tls.apk'
adb('install', '-r', apk, timeout=120); bc('init', 'setup')
adb('push', a.certdir / 'test-ca.pem', '/data/local/tmp/p04-test-ca.pem')
adb('shell', f'run-as {PKG} tee files/test-ca.pem < /data/local/tmp/p04-test-ca.pem > /dev/null')
if a.no_root:   # phones: a never-launched app has no network from a broadcast (pilot-calib-1); wake it as campaign.py does
    adb('shell', f'am set-standby-bucket {PKG} active; am start -W -n {PKG}/org.residuelab.Main >/dev/null; input keyevent HOME; true')
durations = json.loads(a.durations.read_text())['median_s'] if a.durations else {}
PHONE = {} if a.serial.startswith('emulator-') else {   # physical phone: no hardware serial in the results (privacy)
    'release': adb('shell', 'getprop', 'ro.build.version.release').strip(), 'sdk': adb('shell', 'getprop', 'ro.build.version.sdk').strip(),
    'transport': adb('shell', 'id=$(dumpsys connectivity 2>/dev/null | grep -m1 "Active default network" | grep -oE "[0-9]+"); dumpsys connectivity 2>/dev/null | grep -m1 "network{$id}" | grep -oE "ni\\{[A-Z_]+(\\[[A-Za-z0-9 ]*\\])?"; true').strip()[:40]}
meta = {'serial': a.serial if a.serial.startswith('emulator-') else 'physical (not recorded)', 'phone': PHONE, 'avd': a.avd, 'fingerprint': adb('shell', 'getprop', 'ro.build.fingerprint').strip(), 'seed': a.seed,
        'profiles': PROFILES, 'sizes': SIZES, 'modes': MODES, 'calibrate': a.calibrate, 'trials': a.trials, 'start': a.start,
        'durations': durations, 'radio': RADIO, 'shaper': a.shaper, 'receiver': a.receiver, 'host': a.host, 'apk_sha256': hashlib.sha256(apk.read_bytes()).hexdigest(), 'started': time.time()}
(a.out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')


def trial(block, profile, size, mode, u):
    id = f'race-{profile}-{size}-{mode}-{block}-{uuid.uuid4().hex[:6]}'
    D = durations.get(f'{profile}:{size}', 0.0)
    deadline = 600000 if a.calibrate else int(max(10000, (4 * D + 20) * 1000))   # calibration: no deadline pressure
    r = {'trial': id, 'block': block, 'profile': profile, 'size': size, 'mode': mode, 'u': u, 'D_s': D, 'deadline_ms': deadline,
         'host_load': os.getloadavg(), 'start': time.time()}
    try:
        r['net'] = net(profile)
        adb('shell', f'am force-stop {PKG}'); adb('shell', f'run-as {PKG} rm -f files/revision.jsonl files/release'); bc('init', id)
        if a.no_root:   # phones (Android 14+): a cached broadcast process is frozen ~5 s in and its sockets are cut (pilot-calib-2); keep it foreground
            adb('shell', f'am start -W -n {PKG}/org.residuelab.Main >/dev/null; true')
        t_send = time.monotonic()
        r['command'] = bc('send', id, tls=True, mode=mode, fault='none', size=size, port=8798, sndbuf=16384,
                          label='analytics:0', deadline_ms=deadline)
        if u is not None:                       # no barrier: withdraw at W = u * D after the send was issued
            time.sleep(max(0.0, t_send + u * D - time.monotonic()))
            r['withdraw_host_offset_s'] = time.monotonic() - t_send
            r['withdraw'] = bc('withdraw', id, remote=True)
        end = time.monotonic() + deadline / 1000 + 20
        while time.monotonic() < end:
            ev = events()
            if any(e['trial'] == id and e['kind'] in ('SEND_OK', 'SEND_ERROR', 'EARLY_BLOCK') for e in ev): break
            time.sleep(0.5)
        r['events'] = ev
    except Exception as e: r['harness_error'] = repr(e)
    r['finished'] = time.time()
    with (a.out / 'trials.jsonl').open('a') as f: f.write(json.dumps(r) + '\n')
    done = [e['kind'] for e in r.get('events', []) if e['trial'] == id and e['kind'] in ('SEND_OK', 'SEND_ERROR', 'EARLY_BLOCK')]
    print(time.strftime('%H:%M:%S'), id, r.get('harness_error') or done, flush=True)
    return r


if a.calibrate:
    res = {}
    for profile in PROFILES:
        for size in SIZES:
            for k in range(a.calibrate):
                r = trial(k, profile, size, 'fence', None)
                ok = [e for e in r.get('events', []) if e['kind'] == 'SEND_OK']
                if ok: res.setdefault(f'{profile}:{size}', []).append(int(dict(x.split('=', 1) for x in ok[0]['detail'].split(';') if '=' in x)['elapsed_ns']) / 1e9)
    (a.out / 'calibration.json').write_text(json.dumps({'samples_s': res, 'median_s': {k: statistics.median(v) for k, v in res.items()}}, indent=1) + '\n')
else:
    for block in range(a.start, a.start + a.trials):
        cells = [(p_, m, s) for p_ in PROFILES for m in MODES for s in SIZES]
        brng = random.Random(f'{a.seed}-{block}'); brng.shuffle(cells)
        for p_, m, s in cells:
            u = random.Random(f'{a.seed}-{block}-{p_}-{s}').random()   # same u for early and fence: paired cells
            trial(block, p_, s, m, u)
net('full')
if a.radio: adb('shell', 'svc wifi enable')
if a.receiver: (a.out / 'receiver.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in json.loads(ctl('GET', '/log?from=0'))['lines']))
if sink: sink.shutdown()
