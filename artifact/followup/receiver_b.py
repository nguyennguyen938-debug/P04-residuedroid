#!/usr/bin/env python3
"""Receiver mode B (artifact/devicefarm/README.md): the suite's receiver on a remote host (EC2 us-west-2), reached by the
phone over the real network, plus a token-protected control API so the harness can shape the link and fetch the log.

  :8798  TLS 1.2 receiver (same behaviour and log format as tls_suite.py / race_suite.py), cert with SAN = host IP
  :8799  plain HTTP receiver (same)
  :8800  control (HTTP, header X-Token): POST /profile/<edge|umts|lte|full>   -> tc shaping on the egress+ingress of --dev
                                         POST /mode/<normal|stall>             -> receiver stalls 12 s before reading
                                         GET  /log?from=N                      -> receiver.jsonl lines from line N (JSON list)
Link shaping uses Linux tc (tbf rate + netem delay) on --dev and an ifb device for ingress (uploads arrive as ingress).
Profiles follow the Android emulator's netspeed/netdelay presets (up/down kbit/s, delay ms). --no-tc for local tests.
Usage (EC2, root): receiver_b.py --cert DIR --dev ens5 --token $TOKEN --out /var/p04/receiver
"""
import argparse, json, os, socketserver, ssl, subprocess, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROFILES = {'edge': (118, 237, 400), 'umts': (128, 1920, 200), 'lte': (58000, 173000, 0), 'full': (None, None, 0)}  # up, down kbit/s; delay ms
p = argparse.ArgumentParser()
p.add_argument('--cert', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
p.add_argument('--dev', default='ens5'); p.add_argument('--token', default=os.environ.get('P04_TOKEN', ''))
p.add_argument('--bind', default='0.0.0.0'); p.add_argument('--no-tc', action='store_true')
p.add_argument('--profile-set', default='emu', choices=['emu', 'b10v3'],
               help='b10v3: same shaping as B10 protocol v3 (plans/b10-card.md): upload direction only, netem delay + rate '
                    '(edge 118.4 kbit/s 240 ms, umts 128 kbit/s 118 ms, lte 58 Mbit/s 0 ms); download unshaped')
a = p.parse_args()
assert a.token, 'set --token or P04_TOKEN'
a.out.mkdir(parents=True, exist_ok=True); LOG = a.out / 'receiver.jsonl'; GUARD = threading.Lock(); MODE = {'v': 'normal'}; STATE = {'profile': 'full'}


def log(r):
    with GUARD, LOG.open('a') as f: f.write(json.dumps({'host_ns': time.monotonic_ns(), 'host_wall': time.time(), **r}) + '\n')


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


V3 = {'edge': ('118400bit', '240ms'), 'umts': ('128kbit', '118ms'), 'lte': ('58mbit', '0ms')}   # = race_suite.py TC (B10 v3)


def shape(name):
    up, down, delay = PROFILES[name]
    d = a.dev
    if a.profile_set == 'b10v3':          # phone upload = ingress here -> ifb0 -> netem delay+rate, as the guest egress in B10 v3
        cmds = [f'tc qdisc del dev {d} root', f'tc qdisc del dev {d} ingress', 'tc qdisc del dev ifb0 root']
        if name in V3:
            cmds += ['modprobe ifb numifbs=1', 'ip link set dev ifb0 up', f'tc qdisc add dev {d} handle ffff: ingress',
                     f'tc filter add dev {d} parent ffff: protocol ip u32 match u32 0 0 action mirred egress redirect dev ifb0',
                     f'tc qdisc add dev ifb0 root netem delay {V3[name][1]} rate {V3[name][0]} limit 10000']
        STATE['profile'] = name
        if a.no_tc: return 'no-tc: ' + '; '.join(cmds)
        return '; '.join(f'{c} -> {sh(c).returncode}' for c in cmds)
    if a.no_tc: STATE['profile'] = name; return 'no-tc'
    sh(f'tc qdisc del dev {d} root; tc qdisc del dev {d} ingress; tc qdisc del dev ifb0 root')
    if up is None: STATE['profile'] = name; return 'cleared'
    out = []
    # phone upload = ingress on this host -> redirect to ifb0 and rate-limit there; phone download = egress on dev
    for c in ('modprobe ifb numifbs=1', 'ip link set dev ifb0 up', f'tc qdisc add dev {d} handle ffff: ingress',
              f'tc filter add dev {d} parent ffff: protocol ip u32 match u32 0 0 action mirred egress redirect dev ifb0',
              f'tc qdisc add dev ifb0 root handle 1: netem delay {delay}ms', f'tc qdisc add dev ifb0 parent 1: handle 2: tbf rate {up}kbit burst 16kbit latency 2s',
              f'tc qdisc add dev {d} root handle 1: netem delay {delay}ms', f'tc qdisc add dev {d} parent 1: handle 2: tbf rate {down}kbit burst 32kbit latency 2s'):
        r = sh(c); out.append(f'{c} -> {r.returncode}')
    STATE['profile'] = name
    return '; '.join(out)


ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.minimum_version = ctx.maximum_version = ssl.TLSVersion.TLSv1_2
ctx.load_cert_chain(a.cert / 'test-ca.pem', a.cert / 'test-key.pem')
class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True; daemon_threads = True
class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        id = None; total = 0; expected = None
        try:
            self.request.settimeout(600)
            tls = self.server.server_address[1] == 8798
            s = ctx.wrap_socket(self.request, server_side=True) if tls else self.request
            h = b''
            while not h.endswith(b'\r\n\r\n'):
                b = s.recv(1)
                if not b: raise EOFError('header')
                h += b
            hd = dict(l.split(': ', 1) for l in h.decode().split('\r\n')[1:] if ': ' in l); id = hd['X-Request-ID']; expected = int(hd['Content-Length'])
            log({'request': id, 'event': 'headers', 'expected': expected, 'tls': 'TLSv1.2' if tls else 'plain', 'profile': STATE['profile']})
            if MODE['v'] == 'stall': time.sleep(12)
            while total < expected:
                b = s.recv(min(65536, expected - total))
                if not b: break
                total += len(b)
            log({'request': id, 'event': 'body', 'received': total, 'expected': expected, 'complete': total == expected})
            if total == expected: s.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        except Exception as e: log({'request': id, 'event': 'error', 'error': repr(e), 'received': total, 'expected': expected})
for port in (8798, 8799):
    threading.Thread(target=Server((a.bind, port), Handler).serve_forever, daemon=True).start()


class Control(BaseHTTPRequestHandler):
    def _ok(self, body, code=200):
        b = json.dumps(body).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def _auth(self):
        if self.headers.get('X-Token') != a.token: self._ok({'error': 'forbidden'}, 403); return False
        return True
    def do_POST(self):
        if not self._auth(): return
        parts = self.path.strip('/').split('/')
        if len(parts) == 2 and parts[0] == 'profile' and parts[1] in PROFILES:
            r = shape(parts[1]); log({'event': 'profile', 'profile': parts[1], 'tc': r}); return self._ok({'profile': parts[1], 'tc': r})
        if len(parts) == 2 and parts[0] == 'mode' and parts[1] in ('normal', 'stall'):
            MODE['v'] = parts[1]; return self._ok({'mode': parts[1]})
        self._ok({'error': 'bad path'}, 404)
    def do_GET(self):
        if not self._auth(): return
        if self.path.startswith('/log'):
            start = int(self.path.split('from=')[1]) if 'from=' in self.path else 0
            lines = LOG.read_text().splitlines() if LOG.exists() else []
            return self._ok({'from': start, 'lines': [json.loads(l) for l in lines[start:]], 'total': len(lines)})
        self._ok({'profile': STATE['profile'], 'mode': MODE['v']})
    def log_message(self, *args): pass
print(f'receiver_b: TLS 8798, plain 8799, control 8800 on {a.bind}; tc {"off" if a.no_tc else "on " + a.dev}', flush=True)
ThreadingHTTPServer((a.bind, 8800), Control).serve_forever()
