#!/usr/bin/env python3
"""Receiver-side outcome of the natural-race runs (C, 21/11, answering round-3 review: "what did the server get?").

For every trial whose withdrawal was acknowledged before the request was fully handed off (WITHDRAW_ACK precedes
REQUEST_HANDED_OFF on the device clock, or the request was never handed off), report whether the receiver logged the
complete request. Device events are ordered on the device clock only; the receiver is matched by request id, never by
host time. Output: results/round3/c-analysis/receiver-race.json (keys for make_summary.py derived())."""
import gzip, json
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "results/round3"
RUNS = {"race": "b10/final4", "racePhone": "test1-phone/final"}


def analyse(run):
    d = R / run
    complete = {r["request"] for r in map(json.loads, (d / "receiver.jsonl").read_text(encoding="utf-8").splitlines())
                if r.get("event") == "body" and r.get("complete")}
    cells = {m: {"cut": 0, "cut_complete": 0, "trials": 0} for m in ("early", "fence")}
    with gzip.open(d / "trials.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            t = json.loads(line)
            ev = [e for e in t["events"] if e.get("trial") == t["trial"]]
            ack = min(e["mono_ns"] for e in ev if e["kind"] == "WITHDRAW_ACK")
            done = [e["mono_ns"] for e in ev if e["kind"] == "REQUEST_HANDED_OFF"]
            c = cells[t["mode"]]; c["trials"] += 1
            if not done or ack < min(done):
                c["cut"] += 1; c["cut_complete"] += t["trial"] in complete
    return cells


if __name__ == "__main__":
    out, keys = {}, {}
    for prefix, run in RUNS.items():
        cells = out[run] = analyse(run)
        keys.update({f"{prefix}CutEarly": cells["early"]["cut"], f"{prefix}CutEarlyComplete": cells["early"]["cut_complete"],
                     f"{prefix}CutFence": cells["fence"]["cut"], f"{prefix}CutFenceComplete": cells["fence"]["cut_complete"]})
    dest = R / "c-analysis/receiver-race.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps({"runs": out, "keys": keys}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(keys))
