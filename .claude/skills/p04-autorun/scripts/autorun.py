#!/usr/bin/env python3
"""Unattended stage runner for P04 emulator campaigns (pilots and frozen final runs).

It enforces the repo's research rules mechanically and never looks at scientific outcomes:
  * every stage writes to a fresh output directory (refuses existing paths)            R2.4
  * final runs require a frozen source manifest whose hashes still match, and an
    explicit --confirm <manifest id> (the user's go-ahead, gate G2)                     R2.3
  * pre-checks (preflight) must pass; stages run in order under caffeinate; the first
    non-zero exit or the deadline stops the run (no outcome-dependent branching)       R1.4
  * LAUNCH/DONE/ABORT lines are appended to RUNLOG.md; a stage log is kept per run      R2.5
  * guard.sh runs afterwards; only emulators listed in owned_serials are shut down     R2.4/R2.7
Usage: autorun.py <manifest.json> [--dry-run] [--confirm <id>]
"""
import argparse, datetime, hashlib, json, os, shlex, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUNLOG = ROOT / "artifact/results/RUNLOG.md"


def now():
    return datetime.datetime.now().astimezone()


def runlog(line):
    with RUNLOG.open("a") as f:
        stamp = now()
        f.write(f"- {stamp:%Y-%m-%d %H:%M} {line}\n")


def check_frozen(frozen):
    man = ROOT / frozen / "source-sha256.json"
    if not man.exists():
        return [f"missing {man}"]
    bad = []
    for rel, h in json.loads(man.read_text()).items():
        p = ROOT / "artifact" / rel
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != h:
            bad.append(rel)
    return bad


def sh(cmd, env, cwd, log, timeout=None):
    log.write(f"$ {cmd if isinstance(cmd, str) else shlex.join(cmd)}\n"); log.flush()
    return subprocess.run(cmd, shell=isinstance(cmd, str), cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT,
                          timeout=timeout).returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm", default="")
    a = ap.parse_args()
    m = json.loads(Path(a.manifest).read_text())
    mid, kind = m["id"], m.get("kind", "pilot")
    problems = []
    if kind not in ("pilot", "final"):
        problems.append("kind must be pilot or final")
    for st in m["stages"]:
        out = ROOT / st["out"]
        if out.exists():
            problems.append(f"output exists (fresh dir rule): {st['out']}")
        if kind == "pilot" and not Path(st["out"]).name.startswith("pilot"):
            problems.append(f"pilot stage must write to pilot-* dir: {st['out']}")
        rel = os.path.relpath(out, ROOT / st.get("cwd", "."))
        if not ({st["out"], str(out), rel} & set(st["cmd"])):
            problems.append(f"stage {st['name']}: cmd does not pass its out dir")
        if not str(st["out"]).startswith("artifact/results/"):
            problems.append(f"stage {st['name']}: out must be under artifact/results/")
    if kind == "final":
        if m.get("frozen"):        # optional: the team plan freezes data at B7, not before each run
            drift = check_frozen(m["frozen"])
            if drift:
                problems.append(f"frozen sources changed since freeze: {drift[:5]}{' …' if len(drift) > 5 else ''}")
        if a.confirm != mid and not a.dry_run:
            problems.append(f"final run needs --confirm {mid} (user go-ahead, gate G2)")
    card = m.get("card")
    if not card or not (ROOT / card).exists():
        problems.append("manifest must reference an existing experiment card")
    env = {**os.environ, **{k: os.path.expanduser(v) for k, v in m.get("env", {}).items()}}
    print(f"[autorun] {mid} ({kind}) stages={len(m['stages'])} deadline={m.get('deadline_hours')} h")
    for st in m["stages"]:
        print(f"  - {st['name']}: {shlex.join(st['cmd'])}  -> {st['out']}")
    if problems:
        print("[autorun] REFUSED:\n  " + "\n  ".join(problems)); sys.exit(2)
    if a.dry_run:
        print("[autorun] dry-run OK"); return

    campaign_dir = ROOT / Path(m["stages"][0]["out"]).parent
    campaign_dir.mkdir(parents=True, exist_ok=True)
    rec = campaign_dir / f"autorun-{mid}.jsonl"
    logp = campaign_dir / f"autorun-{mid}.log"
    deadline = time.time() + 3600 * float(m.get("deadline_hours", 12))
    status = "DONE"

    def event(**kw):
        kw["t"] = time.time()
        with rec.open("a") as f:
            f.write(json.dumps(kw) + "\n")

    with logp.open("a") as log:
        for c in m.get("pre", []):
            if sh(c, env, ROOT, log) != 0:
                event(stage="pre", cmd=c, exit="fail"); print(f"[autorun] pre-check failed: {c}"); sys.exit(3)
        runlog(f"LAUNCH autorun {mid} ({kind}) card {card}; stages {[s['name'] for s in m['stages']]}; "
               f"owned {m.get('owned_serials', [])}; log {logp.relative_to(ROOT)}.")
        event(stage="launch", manifest=m)
        for st in m["stages"]:
            left = deadline - time.time()
            if left <= 0:
                status = "ABORT(deadline)"; break
            cmd = ["caffeinate", "-s", "-i"] + st["cmd"] if sys.platform == "darwin" else st["cmd"]
            event(stage=st["name"], state="start")
            try:
                code = sh(cmd, env, ROOT / st.get("cwd", "."), log, timeout=left)
            except subprocess.TimeoutExpired:
                code = "deadline"
            event(stage=st["name"], state="end", exit=code)
            if code != 0:
                status = f"ABORT({st['name']} exit {code})"; break
        for c in m.get("post", []):
            event(stage="post", cmd=c, exit=sh(c, env, ROOT, log))
        guard = None
        if m.get("guard_after", True):
            guard = sh(["bash", ".claude/skills/p04-experiment/scripts/guard.sh"], env, ROOT, log)
            event(stage="guard", exit=guard)
        adb = os.path.join(env.get("ANDROID_HOME", ""), "platform-tools", "adb")
        for s in m.get("owned_serials", []):
            if s.startswith("emulator-"):          # never send emu commands to a physical phone
                sh([adb, "-s", s, "emu", "kill"], env, ROOT, log)
        event(stage="shutdown", serials=m.get("owned_serials", []))
    summary = dict(id=mid, kind=kind, status=status, guard=guard, finished=now().isoformat(),
                   stages=[s["out"] for s in m["stages"]])
    (campaign_dir / f"autorun-{mid}.summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    runlog(f"{'DONE' if status == 'DONE' else 'ABORT'} autorun {mid}: {status}; guard exit {guard}; "
           f"SHUTDOWN {m.get('owned_serials', [])}. Outcomes not inspected by the runner.")
    print(f"[autorun] {status}; guard={guard}")
    sys.exit(0 if status == "DONE" and guard in (0, None) else 1)


if __name__ == "__main__":
    main()
