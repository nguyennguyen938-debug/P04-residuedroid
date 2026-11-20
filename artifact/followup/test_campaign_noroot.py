#!/usr/bin/env python3
"""Offline check of campaign.py --no-root database reading (no device needed).

The run-as path copies rl.db + rl.db-wal and queries the copy on the host. It must hand parse_device() exactly the text
the sqlite3 CLI prints on the device (root path), including rows that still live only in the WAL. The reference here is
the host sqlite3 CLI run on the same files with the same queries and separators.
Usage: python3 artifact/followup/test_campaign_noroot.py   (exit 0 = pass)
"""
import importlib.util, os, shutil, sqlite3, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = [  # fixture Db.onCreate (tables read by the harness)
    "CREATE TABLE records(tag TEXT PRIMARY KEY, tenant INT, scope TEXT, epoch INT, payload TEXT, t_wall INT)",
    "CREATE TABLE derived(tag TEXT PRIMARY KEY, tenant INT, labels TEXT, srcs TEXT, payload TEXT, t_wall INT)",
    "CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, t_wall INT, t_el INT, tenant INT, kind TEXT, detail TEXT)",
]


def load_campaign(out):
    argv = sys.argv
    sys.argv = ["campaign.py", "--serial", "emulator-0", "--port", "1", "--variants", "egress", "--out", out, "--no-root",
                "--schedules", "pending,kill"]
    try:
        spec = importlib.util.spec_from_file_location("campaign_under_test", os.path.join(HERE, "campaign.py"))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    finally:
        sys.argv = argv
    return m


def make_db(d):
    """WAL database whose last transactions stay in rl.db-wal (no checkpoint), like a live app."""
    path = os.path.join(d, "rl.db")
    con = sqlite3.connect(path, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL"); con.execute("PRAGMA wal_autocheckpoint=0")
    for s in SCHEMA:
        con.execute(s)
    con.execute("PRAGMA wal_checkpoint(TRUNCATE)")            # schema in the main file, rows below only in the WAL
    details = ["job=11;sid=ab12;n=3;unknown=0", "", None, "a^^b|c", "x y\tz", "ü 漢字", "elapsed_ns=123;payload_bytes=9"]
    for i in range(200):
        con.execute("INSERT INTO events(t_wall,t_el,tenant,kind,detail) VALUES(?,?,?,?,?)",
                    (1763450000000 + i, 987654321 + i * 7, i % 11, ["COMMIT", "BLOCK", "SEND_OK", "PROC_START"][i % 4],
                     details[i % len(details)]))
    for t in range(1, 11):
        for j in range(t):
            con.execute("INSERT INTO records VALUES(?,?,?,?,?,?)", (f"r{t}-{j}", t, "s", 1, "p", 1))
        if t % 2:
            con.execute("INSERT INTO derived VALUES(?,?,?,?,?,?)", (f"d{t}", t, "L", "S", "p", 1))
    return con, path   # keep the connection open so the WAL is not checkpointed on close


def main():
    cli = shutil.which("sqlite3")
    if not cli:
        print("SKIP: no sqlite3 CLI on host"); return 0
    with tempfile.TemporaryDirectory() as d:
        m = load_campaign(os.path.join(d, "out"))
        con, path = make_db(d)
        assert os.path.getsize(path + "-wal") > 0, "test DB has no WAL frames"
        files = {"databases/rl.db": open(path, "rb").read(), "databases/rl.db-wal": open(path + "-wal", "rb").read()}
        m.pull_run_as = lambda pkg, rel: files.get(rel)
        got = m.read_device("org.residuelab.egress")
        # reference: what the root path does on the device, run with the host CLI on a copy of the same two files
        ref_dir = os.path.join(d, "ref"); os.makedirs(ref_dir)
        for rel, b in files.items():
            open(os.path.join(ref_dir, os.path.basename(rel)), "wb").write(b)
        ref_db = os.path.join(ref_dir, "rl.db")
        run = lambda *a: subprocess.run([cli, *a], capture_output=True, text=True, check=True).stdout
        out = run("-separator", "^^", ref_db, "select seq,t_wall,t_el,tenant,kind,detail from events order by seq")
        res = run(ref_db, "select tenant, count(*) from records group by tenant")
        der = run(ref_db, "select tenant, count(*) from derived group by tenant")
        want = m.parse_device(out, res, der)
        assert len(want["events"]) == 200, len(want["events"])
        assert got == want, "run-as copy path differs from sqlite3 CLI path"
        # a database that keeps changing between copies must be reported, never read half-written
        flip = iter(range(10**6))
        m.pull_run_as = lambda pkg, rel: files[rel] + bytes([next(flip) % 256]) if rel.endswith("-wal") else files.get(rel)
        try:
            m.read_device("org.residuelab.egress"); raise AssertionError("unstable copy was accepted")
        except RuntimeError as e:
            assert "changed during" in str(e)
        m.pull_run_as = lambda pkg, rel: None
        try:
            m.read_device("org.residuelab.egress"); raise AssertionError("missing database was accepted")
        except RuntimeError as e:
            assert "could not read" in str(e)
        con.close()
    print("PASS: --no-root read == sqlite3 CLI read (200 events incl. NULL, separators, unicode; WAL-only rows); "
          "unstable and missing copies rejected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
