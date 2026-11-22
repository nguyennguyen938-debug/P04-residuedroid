#!/usr/bin/env python3
"""Group 3, test G3d (g3cost-card.md): upload cost on one physical phone, TLS fence vs TLS early vs the platform client.

Arms (one TLS fixture build, org.residuelab.tls): fence (TlsTransport, per-write check under the lock), early (TlsTransport,
no per-write check), platform (HttpsURLConnection, fixed-length streaming, no per-write check). Sizes 4 KiB / 256 KiB / 2 MiB.
No withdrawal: every upload is permitted. Design: blocks; a block = every (arm, size) cell once, cell order shuffled per block
from the seed. A cell = R uploads one after another, with batterystats reset before the cell and read after it.
Per upload (app log, device clock): SEND_OK elapsed_ns and process_cpu_ms (Process.getElapsedCpuTime difference).
Per cell (platform model, an estimate, not a measurement): `dumpsys batterystats` lines of the app's UID (estimated power use,
mAh) and its --checkin lines. The phone stays on USB for adb; `dumpsys battery unplug` makes batterystats count as on battery
(restored with `dumpsys battery reset` at the end); `svc power stayon usb` keeps the screen on (restored at the end); the app
runs in the foreground (am start Main before every cell).
Network: Wi-Fi; receiver = TLS server on this host's LAN address (cert SAN = that address; CA pushed into the app's files).
Privacy: no hardware serial, IMEI, phone number or account in the results.
Usage: cost_suite.py --serial auto|<adb serial> --host 192.168.x.y --certdir DIR --apk APK --out DIR --blocks 20 [--repeats 10]
"""
import argparse, contextlib, hashlib, json, os, random, re, socketserver, ssl, subprocess, threading, time, uuid
from pathlib import Path

A = Path(__file__).resolve().parents[1]; PKG = 'org.residuelab.tls'
SDK = os.environ.get('ANDROID_HOME', str(A.parents[1] / 'shared-android/sdk')); ADB = os.environ.get('ADB', str(Path(SDK) / 'platform-tools/adb'))
p = argparse.ArgumentParser()
p.add_argument('--serial', required=True); p.add_argument('--host', required=True, help="this host LAN address (receiver); 'auto' = the address of en0/en1 at launch")
p.add_argument('--port', type=int, default=8798); p.add_argument('--certdir', type=Path, required=True); p.add_argument('--apk', type=Path, required=True)
p.add_argument('--out', type=Path, required=True); p.add_argument('--blocks', type=int, default=20); p.add_argument('--start', type=int, default=0)
p.add_argument('--repeats', type=int, default=10); p.add_argument('--arms', default='fence,early,platform')
p.add_argument('--sizes', default='4096,262144,2097152'); p.add_argument('--seed', default='g3cost-20261122')
a = p.parse_args()
assert not a.out.exists(), f'refusing: {a.out} exists (fresh directory rule)'
a.out.mkdir(parents=True)
ARMS, SIZES = a.arms.split(','), [int(x) for x in a.sizes.split(',')]
HOST_SOURCE = 'given'
if a.host == 'auto':                              # 22/11: the Mac's LAN address changed after a move; resolve it at launch
    a.host = next((ip for i in ('en0', 'en1') if (ip := subprocess.run(['ipconfig', 'getifaddr', i], capture_output=True, text=True).stdout.strip())), '')
    assert a.host, 'no LAN address on en0/en1'; HOST_SOURCE = 'auto (ipconfig getifaddr)'
# the app verifies the hostname (HTTPS endpoint identification): the receiver certificate must carry this address
_san = subprocess.run(['openssl', 'x509', '-in', str(a.certdir / 'test-ca.pem'), '-noout', '-ext', 'subjectAltName'], capture_output=True, text=True).stdout
assert f'IP Address:{a.host}' in _san, f'receiver certificate SAN does not contain {a.host} (regenerate with plans/autorun/g3-tonight.sh)'
if a.serial == 'auto':                            # the single attached physical device; its serial is never written to the results
    devs = [l.split()[0] for l in subprocess.run([ADB, 'devices'], capture_output=True, text=True).stdout.splitlines()[1:]
            if l.strip().endswith('device') and not l.startswith('emulator-')]
    assert len(devs) == 1, f'expected exactly one attached phone, found {len(devs)}'
    a.serial = devs[0]


def adb(*args, timeout=60):
    r = subprocess.run([ADB, '-s', a.serial, *map(str, args)], capture_output=True, text=True, timeout=timeout)
    if r.returncode: raise RuntimeError(r.stderr.strip()[:300])
    return r.stdout


def sh(c, timeout=60): return adb('shell', c, timeout=timeout)


def bc(op, id, timeout=60, **kw):
    cmd = ['shell', 'am', 'broadcast', '-n', PKG + '/org.residuelab.Revision', '-a', 'rl.REVISION', '--es', 'op', op, '--es', 'id', id]
    for k, v in kw.items(): cmd += ['--ez' if isinstance(v, bool) else '--ei' if isinstance(v, int) else '--es', k, str(v).lower() if isinstance(v, bool) else str(v)]
    return adb(*cmd, timeout=timeout)


def events():
    rows = []
    for l in sh(f'run-as {PKG} cat files/revision.jsonl 2>/dev/null').splitlines():
        with contextlib.suppress(ValueError): rows.append(json.loads(l))
    return rows


# receiver: TLS 1.2 on the LAN address, as race_suite.py (independent log of what arrived)
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.minimum_version = ctx.maximum_version = ssl.TLSVersion.TLSv1_2
ctx.load_cert_chain(a.certdir / 'test-ca.pem', a.certdir / 'test-key.pem')
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True; daemon_threads = True
    def log(self, r):
        with self.guard, (a.out / 'receiver.jsonl').open('a') as f: f.write(json.dumps({'host_ns': time.monotonic_ns(), **r}) + '\n')
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        id = None; total = 0; expected = None
        try:
            self.request.settimeout(120)
            with ctx.wrap_socket(self.request, server_side=True) as s:
                h = b''
                while not h.endswith(b'\r\n\r\n'):
                    b = s.recv(1)
                    if not b: raise EOFError('header')
                    h += b
                hd = {k.lower(): v for k, v in (l.split(': ', 1) for l in h.decode().split('\r\n')[1:] if ': ' in l)}
                id = hd.get('x-request-id'); expected = int(hd['content-length'])
                while total < expected:
                    b = s.recv(min(65536, expected - total))
                    if not b: break
                    total += len(b)
                self.server.log({'request': id, 'event': 'body', 'received': total, 'expected': expected, 'complete': total == expected})
                if total == expected: s.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        except Exception as e: self.server.log({'request': id, 'event': 'error', 'error': repr(e), 'received': total, 'expected': expected})
sink = Server((a.host, a.port), Handler); sink.guard = threading.Lock(); threading.Thread(target=sink.serve_forever, daemon=True).start()

restore = []
try:
    out = adb('install', '-r', a.apk, timeout=180)
    assert 'Success' in out, f'adb install failed: {out.strip()[-200:]}'   # 22/11: never run on a previously installed build
    inst = sh(f'pm path {PKG}').strip().splitlines()[0].split(':', 1)[1]
    INSTALLED = sh(f'sha256sum {inst}').split()[0]
    assert INSTALLED == hashlib.sha256(a.apk.read_bytes()).hexdigest(), f'installed APK {INSTALLED[:12]} differs from {a.apk}'
    uid = re.search(r'(?:userId|appId)=(\d+)', sh(f'dumpsys package {PKG}')).group(1)   # Android 15 prints appId= (pilot 22/11)
    adb('push', a.certdir / 'test-ca.pem', '/data/local/tmp/p04-test-ca.pem')
    sh(f'run-as {PKG} tee files/test-ca.pem < /data/local/tmp/p04-test-ca.pem > /dev/null')
    sh(f'am set-standby-bucket {PKG} active; am start -W -n {PKG}/org.residuelab.Main >/dev/null; true')
    t0 = time.monotonic(); bc('init', 'setup', timeout=300); setup_s = round(time.monotonic() - t0, 1)
    sh('svc power stayon usb'); restore.append('svc power stayon false')
    sh('dumpsys battery unplug'); restore.append('dumpsys battery reset')
    phone = {'release': sh('getprop ro.build.version.release').strip(), 'sdk': sh('getprop ro.build.version.sdk').strip(),
             'model': sh('getprop ro.product.model').strip(), 'wifi': sh('dumpsys wifi | grep -m1 -E "^Wi-Fi is|mWifiInfo" | cut -c1-60; true').strip()[:60]}
    meta = {'phone': phone, 'serial': 'physical (not recorded)', 'uid': int(uid), 'host': a.host, 'host_source': HOST_SOURCE, 'installed_apk_sha256': INSTALLED, 'arms': ARMS, 'sizes': SIZES, 'repeats': a.repeats,
            'blocks': a.blocks, 'start': a.start, 'seed': a.seed, 'apk_sha256': hashlib.sha256(a.apk.read_bytes()).hexdigest(),
            'ca_sha256': hashlib.sha256((a.certdir / 'test-ca.pem').read_bytes()).hexdigest(), 'setup_init_s': setup_s,
            'foreground': True, 'battery_unplug_override': True, 'started': time.time()}
    (a.out / 'meta.json').write_text(json.dumps(meta, indent=1) + '\n')
    U = f'u0a{int(uid) - 10000}'
    for block in range(a.start, a.start + a.blocks):
        cells = [(m, s) for m in ARMS for s in SIZES]; random.Random(f'{a.seed}-{block}').shuffle(cells)
        for mode, size in cells:
            cell = f'cost-{mode}-{size}-{block}-{uuid.uuid4().hex[:6]}'
            r = {'cell': cell, 'block': block, 'mode': mode, 'size': size, 'host_load': os.getloadavg(), 'start': time.time(), 'uploads': []}
            try:
                sh(f'am start -W -n {PKG}/org.residuelab.Main >/dev/null; true'); sh(f'run-as {PKG} rm -f files/revision.jsonl')
                r['battery_level_start'] = sh('dumpsys battery | grep -m1 " level:"').strip()
                sh('dumpsys batterystats --reset')
                for k in range(a.repeats):
                    id = f'{cell}-{k}'; t = time.monotonic()
                    bc('send', id, tls=True, mode=mode, fault='none', size=size, port=a.port, host=a.host, sndbuf=16384, label='analytics:0', deadline_ms=60000)
                    while time.monotonic() - t < 90:
                        ev = [e for e in events() if e.get('trial') == id and e['kind'] in ('SEND_OK', 'SEND_ERROR', 'EARLY_BLOCK')]
                        if ev: break
                        time.sleep(0.2)
                    r['uploads'].append({'id': id, 'end': ev[0] if ev else None, 'host_s': round(time.monotonic() - t, 3)})
                r['bs'] = sh(f'dumpsys batterystats | grep -E "Estimated power use|Capacity:|Computed drain|Global|UID {U}:|  {U}:" ; true', 120).strip()[:4000]
                r['bs_checkin'] = sh(f'dumpsys batterystats --checkin | grep -E "^9,{uid},|,pwi,|^9,0,l,(pws|bt)," ; true', 120).strip()[:30000]
                r['events'] = events()
            except Exception as e: r['harness_error'] = repr(e)
            r['finished'] = time.time()
            with (a.out / 'cells.jsonl').open('a') as f: f.write(json.dumps(r) + '\n')
            print(time.strftime('%H:%M:%S'), cell, r.get('harness_error') or [u['end']['kind'] if u['end'] else None for u in r['uploads']].count('SEND_OK'), flush=True)
finally:
    for c in restore:
        with contextlib.suppress(Exception): sh(c)
    sink.shutdown()
