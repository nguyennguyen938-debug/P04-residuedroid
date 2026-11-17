#!/usr/bin/env python3
"""Real-library case study: ACRA 5.14.2 (AdvancedSenderScheduler, network required) with its stock HttpSender
(`acra`) vs. a fenced ReportSender (`acrafence`).

Schedules per trial (each variant): connectivity off -> crash (ACRA writes + approves the report and schedules its
sender job, which waits for network) -> app restarted ->
  disable   : user turns "send crash reports" off, then connectivity returns
  control   : no toggle change, connectivity returns (the report SHOULD be sent)
  reboot    : user turns reporting off, device reboots, connectivity returns, user opens the app
  rebootctl : no toggle change, device reboots, connectivity returns, user opens the app (the report SHOULD be sent)
  (reboot schedules: the app is opened >= 70 s after the crash, because ACRA's StartupProcessorExecutor ignores reports
   younger than one minute)
A report counts as delivered when the sink (10.0.2.2:8789) receives a report whose CUSTOM_DATA.rd_tag equals the trial's
tag within 45 s of reconnecting (reboot schedules: of opening the app). Later reports quote earlier tags in their LOGCAT
field, so the tag is matched only in CUSTOM_DATA.

Robustness (2026-11-09 rewrite after a 13 h adb-timeout loop on 2026-11-08): every adb call has a short timeout and
errors name the full command; a failed attempt writes a diagnostic snapshot to diag.jsonl and attempts.jsonl; after 2
consecutive failed attempts the emulator is cold-restarted; after --abort-after consecutive failures the run aborts
(exit 3) instead of spinning. Failed attempts are never recorded as trials."""
import argparse, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__)); ART = os.path.dirname(HERE)
SA = os.environ.get("RESIDUE_ANDROID_ROOT", os.path.abspath(os.path.join(ART, "..", "..", "shared-android")))
SDK = os.environ.get("ANDROID_HOME", f"{SA}/sdk")
AVD_HOME = os.environ.get("ANDROID_AVD_HOME", f"{SA}/avd")
ADB = f"{SDK}/platform-tools/adb"
ap = argparse.ArgumentParser()
ap.add_argument("--serial", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--trials", type=int, default=30); ap.add_argument("--reboot-trials", type=int, default=10)
ap.add_argument("--start", type=int, default=0)
ap.add_argument("--avd", default="P04AvdA")
ap.add_argument("--abort-after", type=int, default=6)
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
PORT = 8789
WINDOW = 45
OPEN_AFTER_S = 70


class AdbTimeout(Exception):
    pass


def adb(*a, timeout=30):
    try:
        return subprocess.run([ADB, "-s", args.serial, *a], capture_output=True, text=True, timeout=timeout).stdout
    except subprocess.TimeoutExpired:
        raise AdbTimeout(f"adb {' '.join(a)[:160]} (>{timeout}s)")


def sh(c, timeout=30):
    return adb("shell", c, timeout=timeout)


def bc(pkg, action, extras=""):
    return sh(f"am broadcast -n {pkg}/org.residuelab.acra.Cmd -a {action} -f 0x20 {extras}")


def reach():
    return sh(f"timeout 4 sh -c 'echo x | nc -w 1 10.0.2.2 {PORT}' >/dev/null 2>&1 && echo up || echo down").strip().endswith("up")


def net(on):
    v = "enable" if on else "disable"
    sh(f"svc wifi {v}; svc data {v}")
    t0 = time.time()
    while time.time() - t0 < 20 and reach() != on:
        time.sleep(0.3)
    return reach() == on


def alive():
    try:
        r = subprocess.run([ADB, "-s", args.serial, "shell", "getprop", "sys.boot_completed"], capture_output=True, text=True, timeout=15)
        return r.stdout.strip() == "1"
    except Exception:
        return False


def wait_boot(limit=240):
    t0 = time.time()
    while time.time() - t0 < limit and not alive():
        time.sleep(2)
    if not alive():
        raise AdbTimeout(f"boot not completed within {limit}s")
    adb("root"); time.sleep(3)
    t1 = time.time()
    while time.time() - t1 < 60 and not alive():
        time.sleep(1)
    if not alive():
        raise AdbTimeout("device gone after adb root")


def qemu_running():
    return bool(subprocess.run(["pgrep", "-f", f"qemu-system.*-avd {args.avd} "], capture_output=True, text=True).stdout.strip())


def launch():
    port = int(args.serial.split("-")[1])
    subprocess.Popen([f"{SDK}/emulator/emulator", "-avd", args.avd, "-port", str(port), "-grpc", str(port + 3000), "-no-window",
                      "-no-audio", "-no-boot-anim", "-gpu", "guest", "-no-snapshot"], stdout=open(os.path.join(args.out, "emu_restart.log"), "a"),
                     stderr=subprocess.STDOUT, start_new_session=True,
                     env={**os.environ, "ANDROID_AVD_HOME": AVD_HOME, "ANDROID_SDK_ROOT": SDK, "ANDROID_HOME": SDK})
    wait_boot(300)
    print(time.strftime("%H:%M:%S"), "launched", args.avd, "on", args.serial, flush=True)


def install():
    for v in ("acra", "acrafence"):
        adb("install", "-r", "-g", f"{ART}/acra/build/apk/{v}.apk", timeout=120)


def cold_restart():
    """Kill OUR emulator instance only (our console port / our AVD name) and boot it from scratch."""
    try:
        adb("emu", "kill", timeout=20)
    except Exception:
        pass
    t0 = time.time()
    while qemu_running() and time.time() - t0 < 60:
        time.sleep(2)
    if qemu_running():
        subprocess.run(["pkill", "-9", "-f", f"qemu-system.*-avd {args.avd} "]); time.sleep(5)
    print(time.strftime("%H:%M:%S"), "cold restart", args.serial, flush=True)
    launch(); install()


def ensure_device():
    if alive():
        return
    for _ in range(6):            # an overloaded but running instance gets 60 s
        time.sleep(10)
        if alive():
            return
    if qemu_running():
        cold_restart()
    else:
        launch(); install()


def tag_arrived(tag):
    p = os.path.join(args.out, "sink", "ingest.jsonl")
    if not os.path.exists(p):
        return None
    for l in open(p):
        if tag not in l:
            continue
        try:
            r = json.loads(l); b = r.get("body")
            if isinstance(b, dict) and (b.get("CUSTOM_DATA") or {}).get("rd_tag") == tag:
                return r["t_host"]
        except Exception:
            pass
    return None


def diag(variant, sched, k, err):
    d = {"t": time.time(), "variant": variant, "schedule": sched, "k": k, "err": err, "alive": alive(), "qemu": qemu_running()}
    for key, c in (("power", "dumpsys power | grep -E 'mWakefulness=|mHoldingDisplaySuspendBlocker'"),
                   ("focus", "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp' | head -3"),
                   ("procs", "ps -A | grep -E 'residuelab|svc|nc ' | head"),
                   ("wifi", "cmd wifi status | head -3")):
        try:
            d[key] = sh(c, timeout=10).strip()[-400:]
        except Exception as e:
            d[key] = repr(e)
    with open(os.path.join(args.out, "diag.jsonl"), "a") as f:
        f.write(json.dumps(d) + "\n")


def trial(variant, sched, k):
    pkg = f"org.residuelab.{variant}"
    tag = f"RD-acra-{variant}-{sched}-{k:03d}"
    rec = {"variant": variant, "schedule": sched, "k": k, "tag": tag, "t0": time.time(), "serial": args.serial, "protocol": "v3"}
    net(True)
    sh(f"pm clear {pkg} >/dev/null; am set-standby-bucket {pkg} active")
    sh(f"am start -W -n {pkg}/org.residuelab.acra.Main >/dev/null", timeout=30); sh("input keyevent HOME")
    rec["net_off"] = net(False)
    rec["t_crash"] = time.time()
    rec["crash"] = bc(pkg, "rl.CRASH", f"--es tag {tag}").strip().split("\n")[-1]
    time.sleep(4)
    rec["state_after_crash"] = bc(pkg, "rl.STATE").split('data="')[-1].rstrip('"\n')
    rec["jobs_after_crash"] = sh(f"cmd jobscheduler get-job-state {pkg} 0").strip()
    if sched in ("disable", "reboot"):
        rec["disable"] = bc(pkg, "rl.DISABLE").split('data="')[-1].rstrip('"\n')
        rec["t_disable"] = time.time()
    time.sleep(2)
    if sched in ("reboot", "rebootctl"):
        rec["t_reboot"] = time.time()
        adb("reboot", timeout=30); time.sleep(5); wait_boot()
        sh("svc wifi disable; svc data disable"); time.sleep(3)
        rec["jobs_after_reboot"] = sh(f"cmd jobscheduler get-job-state {pkg} 0").strip()
    rec["net_on"] = net(True)
    rec["t_net_on"] = time.time()
    if sched in ("reboot", "rebootctl"):   # the user opens the app after the reboot: ACRA's startup path runs
        # StartupProcessorExecutor ignores reports younger than one minute, so the user opens the app >= 70 s after the crash
        time.sleep(max(0.0, rec["t_crash"] + OPEN_AFTER_S - time.time()))
        sh(f"am start -W -n {pkg}/org.residuelab.acra.Main >/dev/null", timeout=30); sh("input keyevent HOME")
        rec["t_open"] = time.time()
    t_ref = rec.get("t_open", rec["t_net_on"])
    t_arr = None
    while time.time() - t_ref < WINDOW:
        t_arr = tag_arrived(tag)
        if t_arr:
            break
        time.sleep(1)
    rec["delivered"] = t_arr is not None
    rec["latency_s"] = (t_arr - t_ref) if t_arr else None
    rec["state_end"] = bc(pkg, "rl.STATE").split('data="')[-1].rstrip('"\n')
    rec["fence_log"] = sh(f"cat /data/data/{pkg}/files/rd_events.log 2>/dev/null")[-600:]
    return rec


def main():
    ensure_device(); install()
    sink = subprocess.Popen([sys.executable, os.path.join(HERE, "sink.py"), "--port", str(PORT), "--out",
                             os.path.join(args.out, "sink"), "--delay-ms", "0"], stdout=open(os.path.join(args.out, "sink.log"), "a"),
                            stderr=subprocess.STDOUT)
    time.sleep(1)
    with open(os.path.join(args.out, "meta.json" if args.start == 0 else f"meta_start{args.start}.json"), "w") as f:
        json.dump({"serial": args.serial, "avd": args.avd, "fingerprint": sh("getprop ro.build.fingerprint").strip(),
                   "start": args.start, "trials": args.trials, "reboot_trials": args.reboot_trials, "window_s": WINDOW, "open_after_s": OPEN_AFTER_S,
                   "protocol": "v3", "t": time.time()}, f, indent=1)
    streak = 0
    try:
        with open(os.path.join(args.out, "trials.jsonl"), "a") as f, open(os.path.join(args.out, "attempts.jsonl"), "a") as fa:
            for k in range(args.start, args.start + args.trials):
                scheds = ("disable", "control") + (("reboot", "rebootctl") if k < args.reboot_trials else ())
                for sched in scheds:
                    for v in ("acra", "acrafence"):
                        r = None
                        for attempt in range(3):
                            try:
                                ensure_device(); r = trial(v, sched, k); streak = 0; break
                            except Exception as e:
                                streak += 1
                                err = repr(e)[:300]
                                print(time.strftime("%H:%M:%S"), "TRIAL_ERROR", v, sched, k, err, flush=True)
                                fa.write(json.dumps({"t": time.time(), "variant": v, "schedule": sched, "k": k, "attempt": attempt,
                                                     "err": err}) + "\n"); fa.flush()
                                diag(v, sched, k, err)
                                if streak >= args.abort_after:
                                    print(time.strftime("%H:%M:%S"), f"ABORT: {streak} consecutive failed attempts", flush=True)
                                    sys.exit(3)
                                if streak >= 2:
                                    try:
                                        cold_restart()
                                    except Exception as e2:
                                        print(time.strftime("%H:%M:%S"), "cold restart failed", repr(e2)[:200], flush=True)
                                time.sleep(5)
                        if r is None:
                            continue
                        f.write(json.dumps(r) + "\n"); f.flush()
                        print(time.strftime("%H:%M:%S"), v, sched, k, "delivered" if r["delivered"] else "not-delivered",
                              r["jobs_after_crash"], flush=True)
    finally:
        try:
            net(True)
        except Exception:
            pass
        sink.terminate()


if __name__ == "__main__":
    main()
