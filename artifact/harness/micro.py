#!/usr/bin/env python3
"""Micro-experiments on one P04 emulator: (1) overhead bench, (2) serialization race, (3) label durability under SIGKILL.
Usage: micro.py --serial emulator-5600 --out results/raw/micro [--only bench,stress,crash]"""
import argparse, json, os, random, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); ART = os.path.dirname(HERE)
SDK = os.environ.get("ANDROID_HOME", os.path.abspath(os.path.join(ART, "..", "..", "shared-android", "sdk")))
ADB = os.path.join(SDK, "platform-tools", "adb")
ap = argparse.ArgumentParser()
ap.add_argument("--serial", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--port", type=int, default=8790); ap.add_argument("--only", default="bench,stress,crash")
ap.add_argument("--kills", type=int, default=100); ap.add_argument("--rounds", type=int, default=300)
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)


def sh(c, timeout=120):
    return subprocess.run([ADB, "-s", args.serial, "shell", c], capture_output=True, text=True, timeout=timeout).stdout


def bc(pkg, action, extras=""):
    return sh(f"am broadcast -n {pkg}/org.residuelab.Cmd -a {action} -f 0x20 --es sink_port {args.port} {extras}")


def wait_lines(name, n, timeout):
    p = os.path.join(args.out, "sink", name + ".jsonl")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(p) and sum(1 for _ in open(p)) >= n:
            return True
        time.sleep(2)
    return False


def count(name):
    p = os.path.join(args.out, "sink", name + ".jsonl")
    return sum(1 for _ in open(p)) if os.path.exists(p) else 0


def fresh(pkg):
    sh(f"pm clear {pkg} >/dev/null; am set-standby-bucket {pkg} active")
    sh(f"am start -W -n {pkg}/org.residuelab.Main >/dev/null; input keyevent HOME")


def main():
    subprocess.run([ADB, "-s", args.serial, "root"], capture_output=True); time.sleep(2)
    for v in ("none", "egress", "rd", "noser"):
        subprocess.run([ADB, "-s", args.serial, "install", "-r", "-g", f"{ART}/fixture/build/apk/rl-{v}.apk"], capture_output=True)
    sink = subprocess.Popen([sys.executable, os.path.join(HERE, "sink.py"), "--port", str(args.port), "--out",
                             os.path.join(args.out, "sink"), "--delay-ms", "0"], stdout=open(os.path.join(args.out, "sink.log"), "a"),
                            stderr=subprocess.STDOUT)
    time.sleep(1)
    sh("svc wifi enable; svc data enable")
    meta = {"serial": args.serial, "fingerprint": sh("getprop ro.build.fingerprint").strip(), "start": time.time()}
    try:
        if "bench" in args.only:
            for rep in range(3):
                for v in ("none", "egress", "rd"):
                    pkg = f"org.residuelab.{v}"
                    fresh(pkg); n0 = count("bench")
                    bc(pkg, "rl.BENCH", "--ei n 1000")
                    ok = wait_lines("bench", n0 + 1, 900)
                    print(time.strftime("%H:%M:%S"), "bench", v, rep, ok, flush=True)
        if "stress" in args.only:
            for v, delays in (("rd", (0, 1, 5)), ("noser", (0, 1, 5))):
                pkg = f"org.residuelab.{v}"
                for d in delays:
                    fresh(pkg); n0 = count("stress")
                    bc(pkg, "rl.STRESS", f"--ei rounds {args.rounds} --ei delay {d} --ei maxoff 40")
                    ok = wait_lines("stress", n0 + 1, 1800)
                    print(time.strftime("%H:%M:%S"), "stress", v, d, ok, flush=True)
        if "crash" in args.only:
            pkg = "org.residuelab.rd"
            fresh(pkg)
            rng = random.Random(4242)
            with open(os.path.join(args.out, "crash.jsonl"), "a") as f:
                for i in range(args.kills):
                    bc(pkg, "rl.CRASHWRITE")
                    dt = rng.uniform(0.3, 1.5); time.sleep(dt)
                    pid = sh(f"pidof {pkg}").strip()
                    sh(f"kill -9 {pid}")
                    time.sleep(0.5)
                    out = bc(pkg, "rl.CRASHCHECK")
                    res = out.split('data="')[1].split('"')[0] if 'data="' in out else "fail"
                    f.write(json.dumps({"i": i, "delay_s": dt, "pid": pid, "result": res}) + "\n"); f.flush()
                    sh(f"am force-stop {pkg}")
            print(time.strftime("%H:%M:%S"), "crash done", flush=True)
    finally:
        meta["end"] = time.time()
        json.dump(meta, open(os.path.join(args.out, "meta.json"), "w"), indent=1)
        sink.terminate()


if __name__ == "__main__":
    main()
