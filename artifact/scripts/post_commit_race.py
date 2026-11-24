#!/usr/bin/env python3
"""Natural races measured at the withdrawal commit (C, 22/11, answering round-4 review R4: "the theorems speak about the
commit W, the experiments about the acknowledgement"). Exploratory: defined after the data were seen.

W is the first WITHDRAW_DURABLE of a trial (the withdrawal transaction has committed). A trial counts if the socket accepted
bytes (BYTES_ACCEPTED n > 0) from a write whose WRITE_ATTEMPT came after W, i.e. a write that started after the commit.
All events are on the device's elapsedRealtime clock, shared by the sending and withdrawing processes; host time is never
used. Valid trials only (analyze_race.validity, the rule of the primary analyses).
Output: results/round3/c-analysis/post-commit.json (keys for make_summary.py derived())."""
import collections, gzip, json, sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
R = ART / "results/round3"
sys.path.insert(0, str(ART / "followup"))
from analyze_race import fields, validity  # noqa: E402

RUNS = {"race": "b10/final4", "racePhone": "test1-phone/final", "gclose": "g2close/final"}


def trial(t):
    ev = [e for e in t["events"] if e.get("trial") == t["trial"]]
    w = min(e["mono_ns"] for e in ev if e["kind"] == "WITHDRAW_DURABLE")
    att = sorted(e["mono_ns"] for e in ev if e["kind"] == "WRITE_ATTEMPT")
    acc = [(e["mono_ns"], int(fields(e["detail"]).get("n", 0))) for e in ev if e["kind"] == "BYTES_ACCEPTED"]
    late = [n for ts, n in acc if n > 0 and ts > w and max((a for a in att if a <= ts), default=0) > w]
    return bool(late), sum(late)


def analyse(run):
    cells = collections.defaultdict(lambda: {"trials": 0, "after_commit": 0, "after_commit_bytes": 0})
    with gzip.open(R / run / "trials.jsonl.gz", "rt", encoding="utf-8") as f:
        for t in map(json.loads, f):
            if validity(t): continue
            hit, nbytes = trial(t)
            c = cells[t["mode"]]; c["trials"] += 1; c["after_commit"] += hit; c["after_commit_bytes"] += nbytes
    return dict(cells)


def selfcheck():
    ev = lambda k, ns, d="": {"trial": "x", "kind": k, "mono_ns": ns, "detail": d}
    t = {"trial": "x", "events": [ev("WRITE_ATTEMPT", 1), ev("BYTES_ACCEPTED", 2, "n=5"), ev("WITHDRAW_DURABLE", 3),
                                  ev("BYTES_ACCEPTED", 4, "n=7"), ev("WRITE_ATTEMPT", 5), ev("BYTES_ACCEPTED", 6, "n=9")]}
    assert trial(t) == (True, 9), trial(t)   # n=7 was attempted before W (in flight), only n=9 counts


if __name__ == "__main__":
    selfcheck()
    out, keys = {}, {}
    for prefix, run in RUNS.items():
        cells = out[run] = analyse(run)
        for mode, c in cells.items():
            keys[f"{prefix}Commit{mode.capitalize()}"] = c["after_commit"]
        keys[f"{prefix}CommitN"] = cells["fence"]["trials"]
        assert len({c["trials"] for c in cells.values()}) == 1, cells
    keys["gcloseCommitCloseKib"] = round(out[RUNS["gclose"]]["close"]["after_commit_bytes"] / 1024, 1)
    dest = R / "c-analysis/post-commit.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps({"runs": out, "keys": keys}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(keys))
