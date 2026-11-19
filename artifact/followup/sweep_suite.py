#!/usr/bin/env python3
"""B4 + test 5: transport cost sweep, chunk size × concurrent senders (fenced HTTP, fixture app), random cell order.

Cell = (chunk KiB in 1,4,16,64; senders in 1,2,4,8,16). One trial: S concurrent fenced sends of 1 MiB each (same app
process, one thread each, shared policy lock); while they run, 3 probe withdrawals of an unrelated tenant (tenant 2,
from the remote process) take the same lock without stopping the senders. Read later by analyze_sweep.py: probe ack
latency (WITHDRAW_REQUEST -> WITHDRAW_ACK, device clock) and, for 1 sender, process CPU per MiB (SEND_OK detail).
Blocks: one block = all 20 cells once, order shuffled per block from the seed (plan: "thứ tự ngẫu nhiên, tải đồng thời").
Usage: sweep_suite.py --serial emulator-5664 [--avd P04AvdA] --out DIR --blocks 20 [--start 0] [--apk PATH]
"""
from pathlib import Path
import argparse, contextlib, hashlib, json, os, random, socketserver, subprocess, threading, time, uuid

A = Path(__file__).resolve().parents[1]; PKG = 'org.residuelab.tls'
SDK = os.environ.get('ANDROID_HOME', str(A.parents[1] / 'shared-android/sdk'))
p = argparse.ArgumentParser()
p.add_argument('--serial', required=True); p.add_argument('--avd', default=''); p.add_argument('--out', type=Path, required=True)
p.add_argument('--blocks', type=int, required=True); p.add_argument('--start', type=int, default=0)
p.add_argument('--chunks', default='1,4,16,64'); p.add_argument('--senders', default='1,2,4,8,16')
p.add_argument('--size', type=int, default=1048576); p.add_argument('--seed', default='sweep-20261119')
p.add_argument('--apk', type=Path, default=A / 'fixture/build/tls-b4-apk/rl-tls.apk')
p.add_argument('--probe-mode', default='fixed', choices=['fixed', 'overlap'],
               help='v2 overlap: probes start at the first accepted chunk and repeat until every sender ended (max 12)')
a = p.parse_args()
assert not a.out.exists(), f'refusing: {a.out} exists (fresh directory rule)'
a.out.mkdir(parents=True)
ADB = os.environ.get('ADB', str(Path(SDK) / 'platform-tools/adb'))
CHUNKS = [int(x) for x in a.chunks.split(',')]; SENDERS = [int(x) for x in a.senders.split(',')]


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


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True; daemon_threads = True
class Handler(socketserver.BaseRequestHandler):      # plain HTTP receiver: reads the whole body, answers 200
    def handle(self):
        with contextlib.suppress(Exception):
            s = self.request; s.settimeout(30); h = b''
            while not h.endswith(b'\r\n\r\n'):
                b = s.recv(1)
                if not b: return
                h += b
            n = int(dict(l.split(': ', 1) for l in h.decode().split('\r\n')[1:] if ': ' in l)['Content-Length']); got = 0
            while got < n:
                b = s.recv(min(65536, n - got))
                if not b: break
                got += len(b)
            if got == n: s.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
sink = Server(('127.0.0.1', 8799), Handler); threading.Thread(target=sink.serve_forever, daemon=True).start()

boot(); adb('root'); time.sleep(2); adb('wait-for-device')
adb('install', '-r', a.apk, timeout=120); bc('init', 'setup')
(a.out / 'meta.json').write_text(json.dumps({'serial': a.serial, 'avd': a.avd, 'seed': a.seed, 'blocks': a.blocks, 'start': a.start,
    'chunks_kib': CHUNKS, 'senders': SENDERS, 'size': a.size, 'fingerprint': adb('shell', 'getprop', 'ro.build.fingerprint').strip(),
    'apk_sha256': hashlib.sha256(a.apk.read_bytes()).hexdigest(), 'started': time.time()}, indent=1) + '\n')


def trial(block, chunk, senders):
    id = f'sw-c{chunk}-s{senders}-{block}-{uuid.uuid4().hex[:6]}'
    r = {'trial': id, 'block': block, 'chunk_kib': chunk, 'senders': senders, 'host_load': os.getloadavg(), 'start': time.time()}
    try:
        adb('shell', f'am force-stop {PKG}'); adb('shell', f'run-as {PKG} rm -f files/revision.jsonl'); bc('init', id)
        ids = [f'{id}-{k}' for k in range(senders)]
        for sid in ids:
            bc('send', sid, tls=False, mode='fence', fault='none', size=a.size, port=8799, chunk=chunk * 1024, deadline_ms=120000, label='analytics:0')
        r['probes'] = []; r['probe_mode'] = a.probe_mode
        if a.probe_mode == 'fixed':
            for k in range(3):                    # v1: unrelated tenant 2: same lock, senders keep going
                time.sleep(0.2); r['probes'].append(bc('withdraw', f'{id}-probe{k}', remote=True, tenant=2))
        else:                                     # v2: probes while the senders are in flight
            t0 = time.monotonic()
            while time.monotonic() - t0 < 20 and not any(e['trial'] in ids and e['kind'] == 'BYTES_ACCEPTED' for e in events()): time.sleep(0.05)
            for k in range(12):
                r['probes'].append(bc('withdraw', f'{id}-probe{k}', remote=True, tenant=2))
                if all(any(e['trial'] == s and e['kind'] in ('SEND_OK', 'SEND_ERROR') for e in events()) for s in ids): break
        end = time.monotonic() + 150
        while time.monotonic() < end:
            ev = events()
            if all(any(e['trial'] == s and e['kind'] in ('SEND_OK', 'SEND_ERROR') for e in ev) for s in ids): break
            time.sleep(0.5)
        r['events'] = ev
    except Exception as e: r['harness_error'] = repr(e)
    r['finished'] = time.time()
    with (a.out / 'trials.jsonl').open('a') as f: f.write(json.dumps(r) + '\n')
    print(time.strftime('%H:%M:%S'), id, r.get('harness_error') or 'done', flush=True)


for block in range(a.start, a.start + a.blocks):
    cells = [(c, s) for c in CHUNKS for s in SENDERS]
    random.Random(f'{a.seed}-{block}').shuffle(cells)
    for c, s in cells: trial(block, c, s)
sink.shutdown()
