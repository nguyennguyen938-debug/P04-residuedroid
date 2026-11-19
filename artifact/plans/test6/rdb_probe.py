#!/usr/bin/env python3
"""Link probe for Samsung Remote Test Lab runs: `adb shell echo ok` every 2 s, one line per probe.

Diagnostic only (never read by the analysis). After --down consecutive failed probes it prints LINK_DOWN once, so the
runner can stop the harness instead of letting every remaining trial time out.
Usage: rdb_probe.py <adb> <serial> <log> [--down 6]
"""
import argparse, subprocess, time

ap = argparse.ArgumentParser()
ap.add_argument("adb"); ap.add_argument("serial"); ap.add_argument("log")
ap.add_argument("--down", type=int, default=6)
a = ap.parse_args()
fails = 0
with open(a.log, "a") as f:
    i = 0
    while True:
        t0 = time.time()
        try:
            r = subprocess.run([a.adb, "-s", a.serial, "shell", "echo", "ok"], capture_output=True, text=True, timeout=10)
            st = "OK" if r.stdout.strip() == "ok" else f"BAD rc={r.returncode} {r.stderr.strip()[:80]}"
        except subprocess.TimeoutExpired:
            st = "TIMEOUT"
        dt = time.time() - t0
        fails = 0 if st == "OK" else fails + 1
        f.write(f"{time.strftime('%H:%M:%S')} {i} {st} {dt:.2f}\n")
        if fails == a.down:
            f.write(f"{time.strftime('%H:%M:%S')} LINK_DOWN after {fails} failed probes\n")
        f.flush()
        i += 1
        time.sleep(max(0, 2 - dt))
