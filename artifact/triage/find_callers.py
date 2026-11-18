#!/usr/bin/env python3
"""List every direct caller of one method in an APK's DEX files (A10 follow-up).

Default target is Kotlin's URL.readBytes, the one flagged site per SDK build left unresolved in
mediation-triage.csv. No caller means the flagged sink is dead code in that build (direct calls only;
reflection is not covered). Usage: find_callers.py APK [APK ...] [--target 'Lpkg/Cls;->method']"""
import argparse, re, sys, zipfile
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ART / "static"))
from dexscan import Dex  # noqa: E402


def callers(apk, target):
    out = []
    with zipfile.ZipFile(apk) as z:
        for name in sorted(n for n in z.namelist() if re.fullmatch(r"classes\d*\.dex", n)):
            d = Dex(z.read(name))
            for cls, _, _, methods in d.classes():
                for method, off in methods:
                    if target in d.code_refs(off)[0]:
                        out.append(f"{cls}->{method}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("apks", nargs="+")
    ap.add_argument("--target", default="Lkotlin/io/TextStreamsKt;->readBytes")
    a = ap.parse_args()
    t = tuple(a.target.split("->"))
    for apk in a.apks:
        cs = callers(apk, t)
        print(f"{apk}: {len(cs)} caller(s) of {a.target}")
        for c in cs:
            print("  ", c)
