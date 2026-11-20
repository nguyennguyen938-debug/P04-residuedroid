#!/usr/bin/env python3
"""B3: split policy for blocked mixed requests (S0 decision, paper §5 "Splitting blocked requests"), TLS fixture app.

Request = 2 items: A (analytics:0, withdrawn during the trial) + B (diagnostics:0, stays permitted). Conditions:
  prefirst : barrier after the TLS handshake (fault 'prelock'); the harness withdraws analytics, releases; the fence denies
             before any byte is handed off -> with split, A is retired and B is resent as a new fenced request.
  prefix   : receiver stalls (reads nothing for 12 s), 8 MiB body, small send buffer; withdrawal after the first accepted
             chunk -> denial after a handed-off prefix -> no split allowed (remainder withheld).
  control  : no withdrawal.
Variants: split on / off, paired (both run in every block). One block = 6 cells, order shuffled per block from the seed.
Outcome is read later by analyze_b3.py (receiver completions + app events), never here.
Usage: b3_suite.py --serial emulator-5662 [--avd P04AvdB] --out DIR --blocks 20 [--start 0] [--certdir DIR] [--apk PATH]
"""
from pathlib import Path
import argparse, contextlib, hashlib, json, os, random, socketserver, ssl, subprocess, threading, time, uuid

A = Path(__file__).resolve().parents[1]; PKG = 'org.residuelab.tls'
SDK = os.environ.get('ANDROID_HOME', str(A.parents[1] / 'shared-android/sdk'))
p = argparse.ArgumentParser()
p.add_argument('--serial', required=True); p.add_argument('--avd', default=''); p.add_argument('--out', type=Path, required=True)
p.add_argument('--blocks', type=int, required=True); p.add_argument('--start', type=int, default=0)
p.add_argument('--seed', default='b3-20261119'); p.add_argument('--certdir', type=Path, default=A / 'followup/tls-cert')
p.add_argument('--apk', type=Path, default=A / 'fixture/build/tls-b3-apk/rl-tls.apk')
a = p.parse_args()
assert not a.out.exists(), f'refusing: {a.out} exists (fresh directory rule)'
a.out.mkdir(parents=True)
ADB = os.environ.get('ADB', str(Path(SDK) / 'platform-tools/adb'))
ITEMS = 'analytics:0,diagnostics:0'


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


def bc(op, id, remote=False, **kw):
    cmd = ['shell', 'am', 'broadcast', '-n', PKG + '/org.residuelab.Revision' + ('Remote' if remote else ''), '-a', 'rl.REVISION',
           '--es', 'op', op, '--es', 'id', id]
    for k, v in kw.items():
        cmd += ['--ez' if isinstance(v, bool) else '--ei' if isinstance(v, int) else '--es', k, str(v).lower() if isinstance(v, bool) else str(v)]
    return adb(*cmd)


def events():
    rows = []
    for l in adb('shell', f'run-as {PKG} cat files/revision.jsonl').splitlines():
        with contextlib.suppress(ValueError): rows.append(json.loads(l))
    return rows


ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.minimum_version = ctx.maximum_version = ssl.TLSVersion.TLSv1_2
ctx.load_cert_chain(a.certdir / 'test-ca.pem', a.certdir / 'test-key.pem')
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True; daemon_threads = True
    def log(self, r):
        with self.guard, (a.out / 'receiver.jsonl').open('a') as f: f.write(json.dumps({'host_ns': time.monotonic_ns(), **r}) + '\n')
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        id = None; total = 0; expected = None; mode = self.server.mode
        try:
            self.request.settimeout(30)
            with ctx.wrap_socket(self.request, server_side=True) as s:
                h = b''
                while not h.endswith(b'\r\n\r\n'):
                    b = s.recv(1)
                    if not b: raise EOFError('header')
                    h += b
                hd = dict(l.split(': ', 1) for l in h.decode().split('\r\n')[1:] if ': ' in l); id = hd['X-Request-ID']; expected = int(hd['Content-Length'])
                self.server.log({'request': id, 'event': 'headers', 'expected': expected})
                if mode == 'stall': time.sleep(12)
                while total < expected:
                    b = s.recv(min(65536, expected - total))
                    if not b: break
                    total += len(b)
                self.server.log({'request': id, 'event': 'body', 'received': total, 'expected': expected, 'complete': total == expected})
                if total == expected: s.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        except Exception as e: self.server.log({'request': id, 'event': 'error', 'error': repr(e), 'received': total, 'expected': expected})
sink = Server(('127.0.0.1', 8798), Handler); sink.guard = threading.Lock(); sink.mode = 'normal'
threading.Thread(target=sink.serve_forever, daemon=True).start()

boot(); adb('root'); time.sleep(2); adb('wait-for-device')
adb('install', '-r', a.apk, timeout=120); bc('init', 'setup')
adb('push', a.certdir / 'test-ca.pem', '/data/local/tmp/p04-test-ca.pem')
adb('shell', f'run-as {PKG} tee files/test-ca.pem < /data/local/tmp/p04-test-ca.pem > /dev/null')
(a.out / 'meta.json').write_text(json.dumps({'serial': a.serial, 'avd': a.avd, 'seed': a.seed, 'blocks': a.blocks, 'start': a.start,
    'items': ITEMS, 'fingerprint': adb('shell', 'getprop', 'ro.build.fingerprint').strip(),
    'apk_sha256': hashlib.sha256(a.apk.read_bytes()).hexdigest(), 'started': time.time()}, indent=1) + '\n')


def wait_for(pred, secs, step=0.05):
    end = time.monotonic() + secs; ev = []
    while time.monotonic() < end:
        ev = events()
        if pred(ev): return True, ev
        time.sleep(step)
    return False, ev


def trial(block, cond, split):
    id = f'b3-{cond}-{"split" if split else "nosplit"}-{block}-{uuid.uuid4().hex[:6]}'
    r = {'trial': id, 'block': block, 'condition': cond, 'split': split, 'host_load': os.getloadavg(), 'start': time.time()}
    sink.mode = 'stall' if cond == 'prefix' else 'normal'
    try:
        adb('shell', f'am force-stop {PKG}'); adb('shell', f'run-as {PKG} rm -f files/revision.jsonl files/release')
        bc('init', id); bc('splitsetup', id)
        kw = dict(tls=True, mode='fence', items=ITEMS, split=split, port=8798, label='unused')
        if cond == 'prefirst': kw.update(fault='prelock', size=1048576, sndbuf=16384)
        elif cond == 'prefix': kw.update(fault='none', size=8 * 1048576, sndbuf=4096, deadline_ms=60000)
        else: kw.update(fault='none', size=1048576, sndbuf=16384)
        r['command'] = bc('send', id, **kw)
        if cond != 'control':
            target = 'TLS_HANDSHAKE' if cond == 'prefirst' else 'BYTES_ACCEPTED'
            seen, ev = wait_for(lambda ev: any(e['trial'] == id and e['kind'] == target and not e['detail'].endswith('n=0') for e in ev), 8)
            r['barrier_seen'] = seen
            r['withdraw'] = bc('withdraw', id, remote=True, scope='analytics')
            if cond == 'prefirst': adb('shell', f'run-as {PKG} touch files/release')
        ends = ('SEND_OK', 'SEND_ERROR', 'EARLY_BLOCK')
        def finished(ev):   # v2 (pilot-1): an end event is final unless a SPLIT resubmitted items, then wait for '<id>-split'
            mine = [e for e in ev if e['trial'] == id]
            if not any(e['kind'] in ends for e in mine): return False
            sp = [e for e in mine if e['kind'] == 'SPLIT']
            if sp and not sp[0]['detail'].endswith('resubmit=') and 'retired=;' not in sp[0]['detail']:
                return any(e['trial'] == id + '-split' and e['kind'] in ends for e in ev)
            if split and cond == 'prefirst' and not sp: return False   # the app logs SPLIT right after its SEND_ERROR: keep polling
            return True
        ok, ev = wait_for(finished, 75 if cond == 'prefix' else 25, step=0.3)
        r['events'] = ev; r['complete_wait'] = ok
    except Exception as e: r['harness_error'] = repr(e)
    r['finished'] = time.time()
    with (a.out / 'trials.jsonl').open('a') as f: f.write(json.dumps(r) + '\n')
    print(time.strftime('%H:%M:%S'), id, r.get('harness_error') or ('done' if r.get('complete_wait') else 'timeout'), flush=True)


for block in range(a.start, a.start + a.blocks):
    cells = [(c, s) for c in ('prefirst', 'prefix', 'control') for s in (True, False)]
    random.Random(f'{a.seed}-{block}').shuffle(cells)
    for c, s in cells: trial(block, c, s)
time.sleep(13); sink.shutdown()
