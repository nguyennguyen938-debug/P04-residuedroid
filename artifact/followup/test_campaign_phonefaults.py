#!/usr/bin/env python3
"""Offline check of campaign.py --phone-faults (no device needed): argument rules, and that netloss and reboot act on the
adb reverse port only (no iptables, no radios, no adb root).
Usage: python3 artifact/followup/test_campaign_phonefaults.py   (exit 0 = pass)
"""
import importlib.util, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def load(extra):
    argv = sys.argv
    sys.argv = ["campaign.py", "--serial", "phone-0", "--port", "8787", "--variants", "mfence", "--out", tempfile.mkdtemp(),
                "--schedules", "reboot,netloss"] + extra
    try:
        spec = importlib.util.spec_from_file_location("campaign_under_test", os.path.join(HERE, "campaign.py"))
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        return m
    finally:
        sys.argv = argv


def refused(extra):
    try:
        load(extra)
    except SystemExit:
        return True
    return False


def main():
    assert refused(["--no-root"]), "--no-root without --phone-faults must refuse reboot/netloss"
    assert refused(["--phone-faults"]), "--phone-faults without --no-root must be refused"
    assert refused(["--phone-faults", "--no-root"]), "--phone-faults needs --sink-host 127.0.0.1"
    m = load(["--no-root", "--sink-host", "127.0.0.1", "--phone-faults"])
    calls = []
    m.adb = lambda *a, **kw: calls.append(a) or ""
    m.sh = lambda cmd, timeout=60: calls.append(("shell", cmd)) or ""
    m.net(False); m.net(True)
    assert calls == [("reverse", "--remove", "tcp:8787"), ("reverse", "tcp:8787", "tcp:8787")], calls
    assert m.SINK_HOST == "127.0.0.1"
    calls.clear()
    m.subprocess = type("S", (), {"run": staticmethod(lambda *a, **kw: None)})
    m.sh = lambda cmd, timeout=60: (calls.append(("shell", cmd)), "1")[1]
    m.wait_boot(limit=5)
    assert ("reverse", "tcp:8787", "tcp:8787") in calls, calls
    assert not any(c[0] == "root" for c in calls), "adb root must not be called under --no-root"
    assert not any("iptables" in " ".join(c) or "svc " in " ".join(c) for c in calls), calls
    print("PASS: --phone-faults argument rules; netloss and reboot touch only the adb reverse port")
    return 0


if __name__ == "__main__":
    sys.exit(main())
