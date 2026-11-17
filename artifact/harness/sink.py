#!/usr/bin/env python3
"""Host HTTP sink reached from the emulator at 10.0.2.2:<port>. Logs every request as one JSON line.

/ingest/<purpose>  application egress (delayed by --delay-ms to emulate a WAN server)
/ack /report /bench /stress   measurement control channel (no delay)
GET /ctl?delay=<ms>           change the ingest delay at run time
"""
import argparse, json, os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=8787)
ap.add_argument("--out", required=True)
ap.add_argument("--delay-ms", type=int, default=300)
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
LOCK = threading.Lock()
STATE = {"delay": args.delay_ms / 1000.0}


def log(name, rec):
    with LOCK:
        with open(os.path.join(args.out, name + ".jsonl"), "a") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _ok(self, body=b"ok"):
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/ctl":
            q = parse_qs(u.query)
            if "delay" in q:
                STATE["delay"] = int(q["delay"][0]) / 1000.0
            self._ok(json.dumps({"delay_ms": int(STATE["delay"] * 1000)}).encode())
        else:
            self._ok(b"residue-sink")

    def do_POST(self):
        t_recv = time.time()
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n else b""
        t_body = time.time()
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {"_raw": raw.decode("latin-1")}
        path = urlparse(self.path).path
        rec = {"t_host": t_body, "t_hdr": t_recv, "port": args.port, "path": path,
               "request_id": self.headers.get("X-Request-ID"), "x_app": self.headers.get("X-App"), "x_trial": self.headers.get("X-Trial"), "len": n, "body": body}
        if path.startswith("/ingest/"):
            log("ingest", rec)
            time.sleep(STATE["delay"])
        else:
            log(path.strip("/").split("/")[0] or "other", rec)
        self._ok()


ThreadingHTTPServer.daemon_threads = True
srv = ThreadingHTTPServer(("127.0.0.1", args.port), H)
print(f"sink on :{args.port} -> {args.out} delay={args.delay_ms}ms", flush=True)
srv.serve_forever()
