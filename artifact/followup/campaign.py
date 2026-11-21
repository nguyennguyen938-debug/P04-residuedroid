#!/usr/bin/env python3
"""ResidueDroid emulator campaign: identical injected schedules across enforcement variants.

Each trial: reset every variant app -> collect tagged records + derive a summary + enqueue persisted jobs ->
inject the schedule (explicit withdrawal, then a lifecycle event) -> wait until no job of ours is registered ->
read each app's durable event log with sqlite3 (root; does not start the app) -> next trial.
All submissions are logged by a host sink (sink.py) reached via 10.0.2.2.

Usage: campaign.py --serial emulator-5600 --port 8787 --variants none,cancel --out DIR --schedules pending,kill --trials 50

Real phone without root (--no-root, e.g. AWS Device Farm): no `adb root`; each app's database files (rl.db + WAL) are
copied with `run-as` (debuggable APKs) and queried on the host, printed exactly as the sqlite3 CLI would print them;
kill -9 is sent as the app's own uid via `run-as`; reboot and netloss need root and are refused. --sink-host tells the
apps where the sink is (default stays 10.0.2.2, the emulator host alias); with `adb reverse tcp:P tcp:P` use 127.0.0.1.
"""
import argparse, hashlib, json, os, random, re, sqlite3, subprocess, sys, tempfile, time

HERE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "harness"))
ART = os.path.dirname(HERE)
SA = os.environ.get("RESIDUE_ANDROID_ROOT", os.path.abspath(os.path.join(ART, "..", "..", "shared-android")))
SDK = os.environ.get("ANDROID_HOME", f"{SA}/sdk")
AVD_HOME = os.environ.get("ANDROID_AVD_HOME", f"{SA}/avd")
ADB = os.environ.get("ADB", f"{SDK}/platform-tools/adb")   # Device Farm host: ADB=adb
TENANTS = list(range(1, 11))
WITHDRAWN = "1,2,3,4,5,8,9,10"          # explicit in-app withdrawals (T6 control, T7 OS-permission tenant excluded)
JOBS = [11, 13, 21, 23, 31, 33, 44, 45, 51, 53, 61, 63, 71, 81, 83, 91, 101]
TRIGGER = {t: (45 if t == 4 else t * 10 + 1) for t in TENANTS}

ap = argparse.ArgumentParser()
ap.add_argument("--serial", required=True)
ap.add_argument("--port", type=int, required=True)
ap.add_argument("--variants", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--schedules", default="pending,kill,forcestop,reboot,revoke,netloss,inflight")
ap.add_argument("--trials", type=int, default=50)
ap.add_argument("--start", type=int, default=0)
ap.add_argument("--seed", default="residue-2027")
ap.add_argument("--substrate", default="job")
ap.add_argument("--sink-delay", type=int, default=300)
ap.add_argument("--timeout", type=float, default=170.0)
ap.add_argument("--no-install", action="store_true")
ap.add_argument("--avd", default="")
ap.add_argument("--apkdir", default="fixture/build/apk")
ap.add_argument("--abort-after", type=int, default=5)   # watchdog: abort after N consecutive failed trials
ap.add_argument("--no-root", action="store_true")       # real phone: run-as instead of root (see module docstring)
ap.add_argument("--sink-host", default="")              # empty = app default 10.0.2.2 (emulator)
ap.add_argument("--regrant-agg", action="store_true")   # B12 v2: app re-aggregates after the T5 re-grant (fixture extra regrant_agg)
args = ap.parse_args()
if args.no_root and {"reboot", "netloss"} & set(args.schedules.split(",")):
    sys.exit("--no-root: reboot and netloss need root (iptables, adb root after boot); run them on the emulator")
VARS = args.variants.split(",")
PKGS = [f"org.residuelab.{v}" for v in VARS]
os.makedirs(args.out, exist_ok=True)
SCHED_LOG = open(os.path.join(args.out, "schedule.jsonl"), "a")
DEV_LOG = open(os.path.join(args.out, "device_events.jsonl"), "a")


def adb(*a, timeout=60, check=False):
    r = subprocess.run([ADB, "-s", args.serial, *a], capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"adb {a}: {r.stderr}")
    return r.stdout


def sh(cmd, timeout=60):
    return adb("shell", cmd, timeout=timeout)


def bc(pkg, action, extras=""):
    return sh(f"am broadcast -n {pkg}/org.residuelab.Cmd -a {action} -f 0x20 {extras}")


def wait_boot(limit=240):
    t0 = time.time()
    subprocess.run([ADB, "-s", args.serial, "wait-for-device"], timeout=limit)
    while time.time() - t0 < limit:
        if sh("getprop sys.boot_completed").strip() == "1":
            break
        time.sleep(1)
    if not args.no_root:
        adb("root"); time.sleep(2)
    subprocess.run([ADB, "-s", args.serial, "wait-for-device"], timeout=60)
    while sh("getprop sys.boot_completed").strip() != "1":
        time.sleep(1)
    return time.time() - t0


def our_jobs():
    out = sh("dumpsys jobscheduler", timeout=60)
    if "Registered " not in out:
        return -1  # dumpsys failed (device gone?): never treat as quiesced
    reg = out.split("Registered ")[1]
    reg = reg.split("ConnectivityController:")[0]
    n = 0
    for line in reg.splitlines():
        m = re.match(r"\s+JOB #u0a\d+/(\d+): \S+ (org\.residuelab\.\w+)/", line)
        if m and m.group(2) in PKGS:
            n += 1
    return n


def alive():
    try:
        r = subprocess.run([ADB, "-s", args.serial, "shell", "getprop", "sys.boot_completed"], capture_output=True,
                           text=True, timeout=20)
        return r.stdout.strip() == "1"
    except Exception:
        return False


def qemu_running():
    r = subprocess.run(["pgrep", "-f", f"qemu-system.*-avd {args.avd} -port {args.serial.split(chr(45))[-1]} "], capture_output=True, text=True)
    return bool(r.stdout.strip())


def ensure_device():
    """Relaunch OUR emulator instance (same AVD/port) only if its qemu process is gone; returns True on restart."""
    for _ in range(10):                       # tolerate a slow/overloaded but running instance
        if alive():
            return False
        if not qemu_running():
            break
        time.sleep(6)
    if alive():
        return False
    if not args.avd:
        raise RuntimeError("device not alive and no --avd given")
    if qemu_running():
        raise RuntimeError("emulator process present but unresponsive for 60 s; not launching a duplicate")
    port = int(args.serial.split("-")[1])
    log = os.path.join(args.out, f"emu{port}_restart.log")
    subprocess.Popen([f"{SDK}/emulator/emulator", "-avd", args.avd, "-port", str(port), "-grpc", str(port + 3000),
                      "-read-only", "-no-window", "-no-audio", "-no-boot-anim", "-gpu", "host", "-feature", "-Vulkan", "-no-snapshot"],
                     stdout=open(log, "a"), stderr=subprocess.STDOUT, start_new_session=True,
                     env={**os.environ, "ANDROID_AVD_HOME": AVD_HOME, "ANDROID_SDK_ROOT": SDK,
                          "ANDROID_HOME": SDK})
    t0 = time.time()
    while time.time() - t0 < 300 and not alive():
        time.sleep(3)
    adb("root"); time.sleep(3)
    subprocess.run([ADB, "-s", args.serial, "wait-for-device"], timeout=120)
    for variant in VARS:
        adb("install", "-r", "-g", f"{ART}/{args.apkdir}/rl-{variant}.apk", timeout=120, check=True)
    print(f"{time.strftime('%H:%M:%S')} restarted {args.serial} in {time.time()-t0:.0f}s", flush=True)
    return True


def cold_restart():
    """Kill OUR emulator instance (console port of args.serial / our AVD only) and relaunch it from scratch."""
    if not args.serial.startswith("emulator-"):     # never send emulator console commands to a phone
        ensure_device(); return
    try:
        subprocess.run([ADB, "-s", args.serial, "emu", "kill"], capture_output=True, timeout=30)
    except Exception:
        pass
    t0 = time.time()
    while qemu_running() and time.time() - t0 < 60:
        time.sleep(2)
    if qemu_running() and args.avd:
        subprocess.run(["pkill", "-9", "-f", f"qemu-system.*-avd {args.avd} -port {args.serial.split(chr(45))[-1]} "])
        time.sleep(5)
    print(f"{time.strftime('%H:%M:%S')} cold restart of {args.serial}", flush=True)
    ensure_device()


def our_alarms():
    out = sh("dumpsys alarm", timeout=60)
    if "pending alarms" not in out:
        return -1
    return sum(1 for line in out.splitlines() if "Alarm{" in line and any(line.rstrip().endswith(p + "}") for p in PKGS))


def our_work():
    """WorkManager quiescence from its own database: work items still ENQUEUED(0)/RUNNING(1)/BLOCKED(4)."""
    n = 0
    for p in PKGS:
        q = "select count(*) from WorkSpec where state in (0,1,4)"
        out = (copy_query(p, "no_backup/androidx.work.workdb", [q])[0] if args.no_root else
               sh(f"sqlite3 /data/data/{p}/no_backup/androidx.work.workdb '{q}'"))
        try:
            n += int(out.strip().splitlines()[-1])
        except Exception:
            return -1
    return n


def net(on):
    """Network loss toward the server, applied to every UID: a guest firewall REJECT rule for 10.0.2.2.
    (svc wifi/data disable did not cut app traffic reliably: per-UID routing kept apps connected.)"""
    if args.no_root:            # netloss is refused under --no-root; never touch a phone's radios or firewall
        return
    if on:
        sh("svc wifi enable; svc data enable; while iptables -D OUTPUT -d 10.0.2.2 -j REJECT 2>/dev/null; do :; done")
    else:
        sh("iptables -I OUTPUT -d 10.0.2.2 -j REJECT")


def reset_apps():
    cmds = []
    for p in PKGS:
        cmds += [f"pm clear {p} >/dev/null", f"pm grant {p} android.permission.ACCESS_FINE_LOCATION",
                 f"am set-standby-bucket {p} active"]
    sh("; ".join(cmds), timeout=120)
    for p in PKGS:
        sh(f"am start -W -n {p}/org.residuelab.Main >/dev/null")
    sh("input keyevent HOME")


def cli_text(rows, sep):
    """Rows as the sqlite3 CLI prints them in its default list mode: NULL -> '', one line per row."""
    return "".join(sep.join("" if v is None else str(v) for v in r) + "\n" for r in rows)


def pull_run_as(pkg, rel):
    r = subprocess.run([ADB, "-s", args.serial, "exec-out", "run-as", pkg, "cat", rel], capture_output=True, timeout=60)
    return r.stdout if r.returncode == 0 else None


def copy_query(pkg, rel, queries, seps=None, tries=3):
    """Copy <rel> and its -wal from the app's data dir with run-as (no root, does not start the app), retrying until two
    consecutive copies are byte-identical (no write in between), then run the queries on the copy with sqlite3."""
    seps = seps or ["|"] * len(queries)
    prev = None
    for _ in range(tries):
        snap = {sfx: pull_run_as(pkg, rel + sfx) for sfx in ("", "-wal")}
        if not snap[""]:
            raise RuntimeError(f"run-as could not read {pkg}/{rel}")
        digest = hashlib.sha256(snap[""] + b"\0" + (snap["-wal"] or b"")).hexdigest()
        if digest == prev:
            break
        prev = digest
    else:
        raise RuntimeError(f"{pkg}/{rel} changed during {tries} consecutive copies")
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "db")
        open(f, "wb").write(snap[""])
        if snap["-wal"]:
            open(f + "-wal", "wb").write(snap["-wal"])
        con = sqlite3.connect(f)
        try:
            return [cli_text(con.execute(q).fetchall(), sep) for q, sep in zip(queries, seps)]
        finally:
            con.close()


def read_device(pkg):
    db = f"/data/data/{pkg}/databases/rl.db"
    q = "select seq,t_wall,t_el,tenant,kind,detail from events order by seq"
    qr = "select tenant, count(*) from records group by tenant"
    qd = "select tenant, count(*) from derived group by tenant"
    if args.no_root:
        out, res, der = copy_query(pkg, "databases/rl.db", [q, qr, qd], ["^^", "|", "|"])
        return parse_device(out, res, der)
    out = sh(f"sqlite3 -separator '^^' {db} '{q}'", timeout=60)
    res = sh(f"sqlite3 {db} '{qr}'")
    der = sh(f"sqlite3 {db} '{qd}'")
    return parse_device(out, res, der)


def parse_device(out, res, der):
    ev = []
    for line in out.splitlines():
        f = line.split("^^")
        if len(f) >= 6:
            ev.append([int(f[0]), int(f[1]), int(f[2]), int(f[3]), f[4], "^^".join(f[5:])])
    return {"events": ev, "residual_records": res.split(), "residual_derived": der.split()}


def run_trial(sched, k):
    trial = f"{sched[:3]}{k:03d}"
    rng = random.Random(f"{args.seed}-{sched}-{k}")
    log = {"trial": trial, "schedule": sched, "k": k, "serial": args.serial, "variants": VARS,
           "substrate": args.substrate, "host_load": os.getloadavg(), "actions": []}

    def act(name, **kw):
        log["actions"].append({"t": time.time(), "a": name, **kw})

    if ensure_device():
        act("emulator_restarted")
    net(True)
    act("reset_start"); reset_apps(); act("reset_done")
    manual = sched in ("inflight", "netloss")
    inj = ""
    if sched == "inflight":
        offs = {t: rng.randint(0, 1600) for t in (1, 2, 3, 4, 5, 8, 9, 10)}
        inj = ",".join(f"{t}:{o}" for t, o in offs.items()); log["inj"] = offs
    elif sched == "netloss":
        offs = {t: 1500 + rng.randint(0, 300) for t in (1, 2, 3, 4, 5, 8, 9, 10)}
        inj = ",".join(f"{t}:{o}" for t, o in offs.items()); log["inj"] = offs
    ex = (f"--es trial {trial} --es tenants {','.join(map(str, TENANTS))} --es substrate {args.substrate} "
          f"--es up_delay 15000 --es sum_delay 15000 --es resurrect_delay 5000 --es regrant_ms 1500 --es nrec 12 "
          f"--es manual {1 if manual else 0} --es sink_port {args.port}" + (f" --es inj {inj}" if inj else "")
          + (f" --es sink_host {args.sink_host}" if args.sink_host else "") + (" --es regrant_agg 1" if args.regrant_agg else ""))
    for p in PKGS:
        r = bc(p, "rl.SETUP", ex)
        if 'data="ok"' not in r:
            act("setup_fail", pkg=p, out=r[-200:])
    act("setup_done")
    t_life = None
    if not manual:
        time.sleep(5)
        for p in PKGS:
            bc(p, "rl.WITHDRAW", f"--es tenants {WITHDRAWN}")
        act("withdraw_sent")
        time.sleep(2)
        t_life = time.time()
        if sched == "kill":
            if args.no_root:     # shell may not signal another uid; run-as sends the same SIGKILL as the app's own uid
                before = {p: sh(f"pidof {p}").split() for p in PKGS}
                kout = sh("; ".join(f"run-as {p} kill -9 $(pidof {p})" for p in PKGS))
                after = {p: sh(f"pidof {p}").split() for p in PKGS}
                ok = all(before[p] and not set(before[p]) & set(after[p]) for p in PKGS)   # fault verified (R2.4)
                act("kill", via="run-as", verified=ok, pids_before=before, pids_after=after, out=kout[-200:])
                log["kill_verified"] = ok
            else:
                sh("; ".join(f"kill -9 $(pidof {p})" for p in PKGS)); act("kill")
        elif sched == "forcestop":
            sh("; ".join(f"am force-stop {p}" for p in PKGS)); act("force_stop")
            time.sleep(3)
            for p in PKGS:   # the user reopens each app; verify that its process started, retry once
                sh(f"am start -W -n {p}/org.residuelab.Main >/dev/null")
                if not sh(f"pidof {p}").strip():
                    time.sleep(1); sh(f"am start -W -n {p}/org.residuelab.Main >/dev/null"); act("relaunch_retry", pkg=p)
            sh("input keyevent HOME"); act("relaunch")
        elif sched == "revoke":
            sh("; ".join(f"pm revoke {p} android.permission.ACCESS_FINE_LOCATION" for p in PKGS)); act("pm_revoke")
        elif sched == "reboot":
            act("reboot"); adb("reboot")
            time.sleep(5)
            bt = wait_boot(); act("boot_completed", boot_s=bt)
    else:
        time.sleep(3)
        runs = "; ".join(f"cmd jobscheduler run -f {p} {j} >/dev/null" for p in PKGS for j in JOBS if j % 10 != 2)
        if sched == "inflight":
            act("force_run_start"); sh(runs); act("force_run_done")
        else:
            # net-loss: one app at a time, so that JobScheduler's concurrency limit cannot reorder variants.
            # During each app's own 6 s outage only the trigger uploads of T8, T2, T5, T4 are started.
            ok_all = True
            for p in PKGS:
                net(False); act("net_off", pkg=p)
                t_cut = time.time(); st = "up"
                while time.time() - t_cut < 15:
                    st = sh(f"echo x | nc -w 1 10.0.2.2 {args.port} >/dev/null 2>&1 && echo up || echo down").strip()
                    if st.endswith("down"):
                        break
                    time.sleep(0.3)
                ok_all &= st.endswith("down")
                sh("; ".join(f"cmd jobscheduler run -f {p} {j} >/dev/null" for j in (81, 21, 51, 45)))
                act("force_run_triggers", pkg=p)
                time.sleep(6.0)
                net(True); act("net_on", pkg=p)
                time.sleep(4.0)
            log["net_verified_down"] = ok_all; log["net_mode"] = "per-app-iptables"
            sh(runs); act("force_run_rest")
    # wait until none of our jobs is registered (or timeout)
    t0 = time.time()
    backstop = 0
    seen_max = -1        # largest job count parsed while waiting: 0 throughout means the dumpsys parser saw none of ours
    min_wait = 0 if args.substrate == "job" else 75      # substrate runs: alarms/WorkManager need a fixed minimum window
    limit = args.timeout if args.substrate == "job" else 240
    while time.time() - t0 < limit:
        time.sleep(3)
        try:
            n = our_jobs() if args.substrate == "job" else (our_work() if args.substrate == "work" else our_alarms())
        except Exception as e:
            n = -1
        seen_max = max(seen_max, n)
        if n == 0 and time.time() - t0 >= min_wait:
            break
        # backstop: after 60 s, let the scheduled time of any remaining job arrive (force-run, once per 15 s)
        if time.time() - t0 > 60 and time.time() - backstop > 15:
            backstop = time.time()
            sh("; ".join(f"cmd jobscheduler run -f {p} {j} >/dev/null 2>&1" for p in PKGS for j in JOBS if j % 10 != 2))
            act("backstop_force_run")
    time.sleep(3)
    act("quiesced", waited=time.time() - t0, remaining=n, seen_max=seen_max)
    for p in PKGS:
        try:
            d = read_device(p)
        except Exception as e:
            d = {"error": str(e)}
        DEV_LOG.write(json.dumps({"trial": trial, "schedule": sched, "pkg": p, **d}) + "\n")
    DEV_LOG.flush()
    act("read_done")
    log["device_alive_end"] = alive()
    SCHED_LOG.write(json.dumps(log) + "\n"); SCHED_LOG.flush()
    return log


def main():
    sink = subprocess.Popen([sys.executable, os.path.join(HERE, "sink.py"), "--port", str(args.port),
                             "--out", os.path.join(args.out, "sink"), "--delay-ms", str(args.sink_delay)],
                            stdout=open(os.path.join(args.out, "sink.log"), "a"), stderr=subprocess.STDOUT)
    time.sleep(1)
    try:
        ensure_device()
        if not args.no_root:
            adb("root"); time.sleep(2)
        if not args.no_install:
            for v in VARS:
                adb("install", "-r", "-g", f"{ART}/{args.apkdir}/rl-{v}.apk", timeout=120)
        meta = {"serial": args.serial, "fingerprint": sh("getprop ro.build.fingerprint").strip(),
                "variants": VARS, "schedules": args.schedules, "trials": args.trials, "seed": args.seed,
                "sink_delay_ms": args.sink_delay, "substrate": args.substrate, "start": time.time()}
        if args.no_root or args.sink_host:      # keys added only for real-phone runs; emulator meta.json unchanged
            meta.update(root=not args.no_root, sink_host=args.sink_host or "10.0.2.2",
                        db_read="run-as copy + host sqlite3" if args.no_root else "sqlite3 as root",
                        model=sh("getprop ro.product.model").strip(), android=sh("getprop ro.build.version.release").strip())
        if args.regrant_agg: meta["regrant_agg"] = True   # B12 v2 only; other runs' meta.json unchanged
        mp = os.path.join(args.out, "meta.json")
        if os.path.exists(mp):      # keep the first launch's meta; later (resume) launches get their own file
            mp = os.path.join(args.out, f"meta_start{args.start}_{args.schedules.replace(',', '-')}.json")
        with open(mp, "w") as f:
            json.dump(meta, f, indent=1)
        completed = {(r["k"],r["schedule"]) for r in (json.loads(l) for l in open(os.path.join(args.out,"schedule.jsonl")) if l.strip())}
        streak = 0          # resume skips every recorded attempt; failed attempts need a new trial ID
        for k in range(args.start, args.start + args.trials):
            for s in args.schedules.split(","):
                if (k,s) in completed: continue
                t = time.time()
                try:
                    lg = run_trial(s, k)
                    streak = 0
                except Exception as e:
                    streak += 1   # emulator died mid-trial: record the trial as failed, relaunch, continue
                    err = {"trial": f"{s[:3]}{k:03d}", "schedule": s, "k": k, "serial": args.serial, "variants": VARS,
                           "substrate": args.substrate, "actions": [{"t": t, "a": "reset_start"}, {"t": time.time(), "a": "trial_error", "err": repr(e)[:200]}]}
                    SCHED_LOG.write(json.dumps(err) + "\n"); SCHED_LOG.flush()
                    print(f"{time.strftime('%H:%M:%S')} {args.serial} {err['trial']} TRIAL_ERROR {repr(e)[:120]}", flush=True)
                    if streak >= args.abort_after:
                        print(f"{time.strftime('%H:%M:%S')} ABORT: {streak} consecutive failed trials", flush=True)
                        sys.exit(3)
                    for _ in range(3):
                        try:
                            if streak >= 2:
                                cold_restart()
                            else:
                                ensure_device()
                            break
                        except Exception as e2:
                            print(f"ensure_device failed: {e2!r}", flush=True); time.sleep(30)
                    continue
                print(f"{time.strftime('%H:%M:%S')} {args.serial} {lg['trial']} {time.time()-t:.0f}s", flush=True)
    finally:
        net(True)
        sink.terminate()


if __name__ == "__main__":
    main()
