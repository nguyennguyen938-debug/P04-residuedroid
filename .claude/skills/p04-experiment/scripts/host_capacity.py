#!/usr/bin/env python3
"""Size a P04 emulator campaign for this host and recommend local vs server.

Concurrency comes from host RAM/CPU; wall time comes from per-schedule median trial durations recorded in
the repo's own schedule.jsonl files (no outcome fields are read).

Example:
  host_capacity.py --schedules pending,kill,forcestop,reboot,revoke,netloss,inflight \
      --trials 20 --lanes 2 --budget-hours 10
  --trials : valid trials needed per schedule per lane (lane = one AVD configuration / paired stream)
  --lanes  : independent AVD configurations that must each reach the target
"""
import argparse, glob, json, os, platform, statistics, subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
RES = os.path.join(ROOT, "artifact/results")
SOURCES = ["raw/c1/A", "raw/c1/B", "revision-20261115/matched-A", "revision-20261115/matched-B",
           "review-followup-20261115/matched-A*", "review-followup-20261115/matched-B*"]


def host():
    cores = os.cpu_count() or 1
    try:
        if platform.system() == "Darwin":
            mem = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"])) / 2**30
            chip = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        else:
            mem = int(open("/proc/meminfo").read().split()[1]) / 2**20
            chip = platform.processor() or platform.machine()
    except Exception:
        mem, chip = 8.0, "unknown"
    return cores, mem, chip, platform.machine()


def medians():
    durs, excluded, logged = {}, 0, 0
    for pat in SOURCES:
        for d in glob.glob(os.path.join(RES, pat)):
            p = os.path.join(d, "schedule.jsonl")
            if not os.path.exists(p):
                continue
            for line in open(p):
                r = json.loads(line)
                a = r.get("actions", [])
                if len(a) < 2:
                    continue
                logged += 1
                gaps = [a[i + 1]["t"] - a[i]["t"] for i in range(len(a) - 1)]
                bad = any(g > 200 for g in gaps) or any(x.get("a") in ("emulator_restarted", "setup_fail", "trial_error") for x in a)
                excluded += bad
                if not bad:
                    durs.setdefault(r.get("schedule", "?"), []).append(a[-1]["t"] - a[0]["t"])
    med = {k: statistics.median(v) for k, v in durs.items() if v}
    return med, (excluded / logged if logged else 0.1), logged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedules", default="pending,kill,forcestop,reboot,revoke,netloss,inflight")
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--lanes", type=int, default=2)
    ap.add_argument("--guest-ram-gb", type=float, default=2.0)
    ap.add_argument("--budget-hours", type=float, default=12.0)
    a = ap.parse_args()

    cores, mem, chip, arch = host()
    per_emu_gb = a.guest_ram_gb + 1.3            # QEMU + emulator UI/gRPC overhead
    reserve_gb = max(4.0, 0.25 * mem)            # host OS, sinks, Python, IDE
    by_mem = int((mem - reserve_gb) // per_emu_gb)
    by_cpu = max(1, (cores - 2) // 2)            # ~2 busy vCPU per emulator at boot/reboot peaks
    max_inst = max(0, min(by_mem, by_cpu))

    med, excl, logged = medians()
    scheds = [s.strip() for s in a.schedules.split(",") if s.strip()]
    default = statistics.median(med.values()) if med else 60.0
    per_lane_s = sum(med.get(s, default) for s in scheds) * a.trials / max(1e-9, 1 - excl)
    parallel = max(1, min(max_inst, a.lanes))
    waves = -(-a.lanes // parallel)
    wall_h = per_lane_s * waves / 3600 * 1.15    # +15 % setup, installs, emulator boots

    print(f"host            : {chip} ({arch}), {cores} cores, {mem:.0f} GB RAM")
    print(f"safe instances  : {max_inst}  (memory limit {by_mem}, CPU limit {by_cpu}; {per_emu_gb:.1f} GB/emulator, {reserve_gb:.0f} GB reserved)")
    print(f"history         : {logged} logged trials, exclusion rate {excl:.1%}")
    print("median trial s  : " + ", ".join(f"{s}={med.get(s, default):.0f}" for s in scheds))
    print(f"campaign        : {len(scheds)} schedules x {a.trials} valid trials x {a.lanes} lane(s), {parallel} in parallel")
    print(f"estimated wall  : {wall_h:.1f} h  (budget {a.budget_hours:.1f} h)")
    arm = arch in ("arm64", "aarch64")
    if max_inst == 0:
        rec = "SERVER: this host cannot safely run an emulator."
    elif wall_h <= a.budget_hours:
        rec = "LOCAL: fits the budget on this host."
    else:
        need = -(-a.lanes * per_lane_s * 1.15 // (a.budget_hours * 3600))
        rec = (f"SERVER: exceeds budget; need ~{int(need)} parallel instances. Use an Apple-silicon Mac host to keep "
               "the arm64 image identical (see references/server-options.md), or extend the budget.")
    if not arm:
        rec += " NOTE: non-arm64 host needs an x86_64 image = different configuration (new stratum)."
    print("recommendation  : " + rec)


if __name__ == "__main__":
    main()
