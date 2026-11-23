#!/usr/bin/env python3
"""B2 sink: stands in for AirGuard's study server for the two test builds (b2-card.md). Port 8796 = stock build, 8797 =
fenced build (base addresses compiled into the test APKs). Endpoints as statistics/api/Api.kt: GET /ping -> {"response":
"pong"}, GET /get_token -> {"token": ...}, POST /donate_data -> 200 after reading the whole body. Every request is logged
(host clock only, never compared with device time) to <out>/ingest.jsonl with the parsed body, for the sink-side oracle.
Usage: airguard_sink.py --out DIR [--ports 8796,8797] [--delay-ms 300]
"""
import argparse, json, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True)
p.add_argument('--ports', default='8796,8797'); p.add_argument('--delay-ms', type=int, default=300)
a = p.parse_args(); a.out.mkdir(parents=True, exist_ok=True); LOCK = threading.Lock()
VARIANT = {8793: 'stockcancel', 8794: 'stockcancel16', 8795: 'layered', 8796: 'stock', 8797: 'fenced'}   # 8795: group-2 layered-early build (g2layer-card.md); 8793: group-3 stock-cancel build (g3app-card.md); 8794: G3c v5 stockcancel16 (g3app5-card.md)


def log(r):
    with LOCK, (a.out / 'ingest.jsonl').open('a') as f: f.write(json.dumps({'t_host': time.time(), 'host_ns': time.monotonic_ns(), **r}) + '\n')


class H(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def _reply(self, obj, code=200):
        b = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b))); self.send_header('Connection', 'close'); self.end_headers(); self.wfile.write(b)

    def _body(self):
        if self.headers.get('Transfer-Encoding', '').lower() == 'chunked':
            out = b''
            while True:
                n = int(self.rfile.readline().strip() or b'0', 16)
                if n == 0: self.rfile.readline(); return out
                out += self.rfile.read(n); self.rfile.readline()
        return self.rfile.read(int(self.headers.get('Content-Length', 0)))

    def do_GET(self):
        port = self.server.server_address[1]; path = self.path.split('?')[0].rstrip('/').rsplit('/', 1)[-1]
        log({'variant': VARIANT.get(port), 'port': port, 'method': 'GET', 'path': path})
        if path == 'ping': return self._reply({'response': 'pong'})
        if path == 'get_token': return self._reply({'token': f'p04-{VARIANT.get(port)}'})
        self._reply({'error': 'not found'}, 404)

    def do_POST(self):
        port = self.server.server_address[1]; path = self.path.split('?')[0].rstrip('/').rsplit('/', 1)[-1]
        raw = self._body(); time.sleep(a.delay_ms / 1000)
        try: body = json.loads(raw.decode('utf-8'))
        except Exception: body = None
        log({'variant': VARIANT.get(port), 'port': port, 'method': 'POST', 'path': path, 'bytes': len(raw), 'request': self.headers.get('X-Request-ID'),
             'body': body, 'complete': body is not None})
        self._reply({}) if path == 'donate_data' else self._reply({'error': 'not found'}, 404)

    def do_DELETE(self):
        log({'variant': VARIANT.get(self.server.server_address[1]), 'method': 'DELETE', 'path': self.path}); self._reply({})

    def log_message(self, *args): pass


for port in (int(x) for x in a.ports.split(',')):
    threading.Thread(target=ThreadingHTTPServer(('127.0.0.1', port), H).serve_forever, daemon=True).start()
print(f'airguard_sink on {a.ports} -> {a.out}', flush=True)
while True: time.sleep(3600)
