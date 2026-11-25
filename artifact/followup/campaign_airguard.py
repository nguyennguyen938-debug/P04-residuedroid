#!/usr/bin/env python3
"""B2: AirGuard end-to-end campaign, stock vs fenced test builds in the same trial (b2-card.md). Emulator, root.

Per trial, both packages in lockstep (identical hooks; they differ only in the donation send path):
  grant -> insert 'pre' beacons -> [net: cut link, run worker (fails, retried)] -> withdraw -> insert 'optout' beacons
  -> lifecycle (kill: SIGKILL both; reboot: emulator reboot) -> re-grant -> insert 'post' beacons -> [net: restore link,
  wait for the retry | else: run worker] -> wait for quiescence -> read each app's residue-events.jsonl (run-as/root).
Each INSERT event carries the exact LocalDateTime given to its beacons, so the oracle (analyze_airguard.py) maps every
uploaded beacon to its batch by value: 'pre' and 'optout' beacons uploaded after the withdrawal = violation (PENDING
contract: withdrawal invalidates data collected before it; nothing collected while opted out may be shared); missing 'post'
beacons = permitted deficit. The sink (airguard_sink.py) logs bodies per port: 8796 stock, 8797 fenced.
Group 2 (g2layer-card.md): --variants stock,fenced,layered adds the layered-early build (port 8795); default unchanged.
Usage: campaign_airguard.py --serial emulator-5666 --avd P04AvdA --apkdir DIR --out DIR --schedules pending,kill,reboot,netloss --trials 20
Own phone on USB (--phone; builds with -Presidue.base=http://127.0.0.1:<port>/ and cleartext for 127.0.0.1): no adb root;
events read with run-as; kill -9 as the app's uid via run-as; the sink ports go through `adb reverse`, which netloss
removes for the outage (connection refused, as the emulator's REJECT rule) and reboot re-adds after `adb reboot`.
The phone must have no screen lock, or its credential-encrypted storage stays locked after the reboot.
"""
import argparse, json, os, random, subprocess, sys, time
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
SDK = os.environ.get('ANDROID_HOME', str(ART.parents[1] / 'shared-android/sdk')); ADB = os.environ.get('ADB', f'{SDK}/platform-tools/adb')
PKGS = {'stock': 'de.seemoo.at_tracking_detection.p04stock', 'fenced': 'de.seemoo.at_tracking_detection.p04fenced',
        'layered': 'de.seemoo.at_tracking_detection.p04layered'}
PORTS = {'layered': 8795, 'stock': 8796, 'fenced': 8797}
HOOK = 'de.seemoo.at_tracking_detection.residue.TestHooks'
p = argparse.ArgumentParser()
p.add_argument('--serial', required=True); p.add_argument('--avd', default=''); p.add_argument('--apkdir', type=Path, required=True)
p.add_argument('--out', type=Path, required=True); p.add_argument('--schedules', default='pending,kill,reboot,netloss')
p.add_argument('--trials', type=int, default=20); p.add_argument('--start', type=int, default=0); p.add_argument('--seed', default='b2-20261119')
p.add_argument('--variants', default='stock,fenced'); p.add_argument('--nbeacons', type=int, default=4); p.add_argument('--wait', type=float, default=90)
p.add_argument('--phone', action='store_true', help='own phone on USB: no root, run-as, sink via adb reverse (see docstring)')
a = p.parse_args()
PKGS = {v: PKGS[v] for v in a.variants.split(',')}
assert not a.out.exists(), f'refusing: {a.out} exists (fresh directory rule)'
a.out.mkdir(parents=True)
LOG = (a.out / 'schedule.jsonl').open('a'); DEV = (a.out / 'device_events.jsonl').open('a')


def adb(*args, timeout=90, check=False):
    r = subprocess.run([ADB, '-s', a.serial, *map(str, args)], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode: raise RuntimeError(f'adb {args}: {r.stderr.strip()[:200]}')
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
                      '-gpu', 'host', '-no-snapshot'], stdout=open(a.out / f'emu{port}.log', 'a'), stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 300 and not alive(): time.sleep(3)
    if not alive(): raise RuntimeError('emulator did not boot')


def reverse(on):
    for v in PKGS:
        if on: adb('reverse', f'tcp:{PORTS[v]}', f'tcp:{PORTS[v]}')
        else: adb('reverse', '--remove', f'tcp:{PORTS[v]}')


def root():
    if a.phone:                               # no adb root on a phone; wait for boot and keep the sink reachable
        adb('wait-for-device', timeout=300); reverse(True)
        t0 = time.time()
        while not alive():
            if time.time() - t0 > 300: raise RuntimeError('phone did not finish boot')   # B 24/11: bounded (trial error)
            time.sleep(1)
        return
    adb('root'); time.sleep(2); adb('wait-for-device')
    while not alive(): time.sleep(1)


def hook(var, op, **kw):
    cmd = f'am broadcast -n {PKGS[var]}/{HOOK} --es op {op}'
    if a.phone: cmd += ' -f 0x20'             # B 24/11: include stopped packages (after pm clear), as campaign.py does
    for k, v in kw.items(): cmd += f" --{'ei' if isinstance(v, int) else 'es'} {k} {v}"
    out = sh(cmd); return 'data="ok"' in out, out.strip()[-160:]


def events(var):
    c = f'run-as {PKGS[var]} cat files/residue-events.jsonl' if a.phone else f'cat /data/data/{PKGS[var]}/files/residue-events.jsonl'
    return [json.loads(l) for l in sh(c + ' 2>/dev/null').splitlines() if l.startswith('{')]


def net(on):
    if a.phone: reverse(on); return
    if on: sh('while iptables -D OUTPUT -d 10.0.2.2 -j REJECT 2>/dev/null; do :; done')
    else: sh('iptables -I OUTPUT -d 10.0.2.2 -j REJECT')


def trial(sched, k):
    tid = f'{sched[:3]}{k:03d}'; rng = random.Random(f'{a.seed}-{sched}-{k}'); order = list(PKGS); rng.shuffle(order)
    log = {'trial': tid, 'schedule': sched, 'k': k, 'order': order, 'host_load': os.getloadavg(), 'actions': []}
    if a.phone: log['phone'] = True           # B 24/11: phone runs record fault verification (R2.4); emulator logs unchanged
    act = lambda name, **kw: log['actions'].append({'t': time.time(), 'a': name, **kw})
    try:
        boot(); root(); net(True)
        for v in order: sh(f'pm clear {PKGS[v]}'); sh(f'pm grant {PKGS[v]} android.permission.POST_NOTIFICATIONS 2>/dev/null')
        act('reset')
        for v in order: ok, out = hook(v, 'grant'); act('grant', variant=v, ok=ok, out=out)
        for v in order: ok, out = hook(v, 'insert', addr=f'AA:00:00:00:00:{k % 100:02d}', n=a.nbeacons, age_s=0); act('insert_pre', variant=v, ok=ok)
        time.sleep(1.5)
        if sched == 'netloss':
            if a.phone:                           # B 24/11: positive control, the sink ports must answer before the cut
                pre = {v: sh(f'echo x | nc -w 1 127.0.0.1 {PORTS[v]} >/dev/null 2>&1 && echo up || echo down').strip() for v in order}
                act('net_probe_before', state=pre)
            net(False); act('net_off')
            if a.phone:                           # B 24/11: confirm each sink port refuses from the phone before the outage counts
                st = {v: sh(f'echo x | nc -w 1 127.0.0.1 {PORTS[v]} >/dev/null 2>&1 && echo up || echo down').strip() for v in order}
                log['net_verified_down'] = all(x.endswith('up') for x in pre.values()) and all(x.endswith('down') for x in st.values()); act('net_probe', state=st)
            for v in order: hook(v, 'run'); act('run_during_outage', variant=v)
            time.sleep(8)
        for v in order: ok, out = hook(v, 'withdraw'); act('withdraw', variant=v, ok=ok, out=out)
        time.sleep(1.5)
        for v in order: ok, out = hook(v, 'insert', addr=f'AA:00:00:00:01:{k % 100:02d}', n=a.nbeacons, age_s=0); act('insert_optout', variant=v, ok=ok)
        time.sleep(1.5)
        if sched == 'kill':
            kv = []
            for v in order:
                before = sh(f'pidof {PKGS[v]}').strip()
                sh(f"{'run-as ' + PKGS[v] + ' ' if a.phone else ''}kill -9 $(pidof {PKGS[v]})")
                after = sh(f'pidof {PKGS[v]}').strip()
                act('kill', variant=v, pid_after=after, **({'pid_before': before} if a.phone else {})); kv.append(bool(before) and after != before)
            if a.phone: log['kill_verified'] = all(kv)   # B 24/11: the pid must have existed and changed or gone
        elif sched == 'reboot':
            up0 = sh('cat /proc/uptime').split()[:1]
            act('reboot'); adb('reboot'); time.sleep(5); adb('wait-for-device', timeout=300)
            t0 = time.time()
            while not alive() and time.time() - t0 < 300: time.sleep(2)
            root(); up1 = sh('cat /proc/uptime').split()[:1]
            act('boot_completed', s=round(time.time() - t0), **({'uptime_before': up0, 'uptime_after': up1} if a.phone else {}))
            if a.phone:                           # B 24/11: a reboot counts only if the uptime restarted (Device Farm ignored adb reboot)
                try: log['reboot_verified'] = float(up1[0]) < float(up0[0])
                except Exception: log['reboot_verified'] = False
        for v in order: ok, out = hook(v, 'grant'); act('regrant', variant=v, ok=ok, out=out)
        time.sleep(1.5)
        for v in order: ok, out = hook(v, 'insert', addr=f'AA:00:00:00:02:{k % 100:02d}', n=a.nbeacons, age_s=0); act('insert_post', variant=v, ok=ok)
        time.sleep(1.5)
        END = ('DONATION_OK', 'DONATION_BLOCKED', 'DONATION_ERROR', 'WORKER_SEND')
        n0 = {v: sum(e['kind'] in END for e in events(v)) for v in order}   # pilot-2: count only attempts after this point
        if sched == 'netloss': net(True); act('net_on')
        else:
            for v in order: hook(v, 'run'); act('run', variant=v)
        t0 = time.time()                          # quiescence: both workers ended a new donation attempt, or the wait expired
        while time.time() - t0 < a.wait:
            done = [sum(e['kind'] in END for e in events(v)) > n0[v] for v in order]
            if all(done): time.sleep(5); break
            time.sleep(3)
        act('quiesced', waited=round(time.time() - t0, 1))
        for v in order: DEV.write(json.dumps({'trial': tid, 'variant': v, 'events': events(v)}) + '\n')
        DEV.flush(); act('read_done'); log['device_alive_end'] = alive()
    except Exception as e:
        act('trial_error', err=repr(e)[:200])
    finally:
        try: net(True)
        except Exception: pass
    LOG.write(json.dumps(log) + '\n'); LOG.flush()
    print(time.strftime('%H:%M:%S'), tid, [x['a'] for x in log['actions'] if x['a'] == 'trial_error'] or 'ok', flush=True)


sink = subprocess.Popen([sys.executable, str(ART / 'followup/airguard_sink.py'), '--out', str(a.out / 'sink'), '--ports', ','.join(str(PORTS[v]) for v in sorted(PKGS, key=PORTS.get))],
                        stdout=open(a.out / 'sink.log', 'a'), stderr=subprocess.STDOUT)
try:
    boot(); root()
    for v, pkg in PKGS.items(): adb('install', '-r', '-g', a.apkdir / f'airguard-{v}.apk', timeout=180, check=True)
    if a.phone: reverse(True)
    warm = {}                                 # pilot-1: the first hook after install timed out (cold start + dexopt); one no-op
    for v in PKGS:                            # broadcast per app, generous timeout, recorded in meta.json
        t0 = time.time(); out = sh(f"am broadcast -n {PKGS[v]}/{HOOK} --es op noop{' -f 0x20' if a.phone else ''}", timeout=300); warm[v] = {'s': round(time.time() - t0, 1), 'ok': 'data="ok"' in out}
    (a.out / 'meta.json').write_text(json.dumps({'serial': a.serial, 'avd': a.avd, 'schedules': a.schedules, 'trials': a.trials, 'start': a.start,
        'seed': a.seed, 'variants': list(PKGS), 'nbeacons': a.nbeacons, 'warmup': warm, 'fingerprint': sh('getprop ro.build.fingerprint').strip(),
        **({'phone': True, 'model': sh('getprop ro.product.model').strip(), 'android': sh('getprop ro.build.version.release').strip(),
            'faults': {'netloss': 'adb reverse ports removed', 'reboot': 'adb reboot, reverse re-added'}} if a.phone else {}),
        'apks': {v: __import__('hashlib').sha256((a.apkdir / f'airguard-{v}.apk').read_bytes()).hexdigest() for v in PKGS}, 'started': time.time()}, indent=1) + '\n')
    for k in range(a.start, a.start + a.trials):
        for s in a.schedules.split(','): trial(s, k)
finally:
    sink.terminate()
