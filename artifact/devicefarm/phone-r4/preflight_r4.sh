#!/bin/bash
# Own-phone round 4 preflight (read-only: changes nothing on the phone). Usage: preflight_r4.sh <adb serial>
# Prints each check; PREFLIGHT OK only if every required check passes. The USER fixes what fails (README §1).
set -uo pipefail
S=${1:?serial}; ADB=${ADB:-adb}; fail=0
a() { "$ADB" -s "$S" shell "$@" 2>/dev/null | tr -d '\r'; }
req() { if [ "$2" = ok ]; then echo "OK    $1"; else echo "FAIL  $1 ($3)"; fail=1; fi; }
"$ADB" devices | grep -q "^$S[[:space:]]*device$" && req "adb sees $S" ok || req "adb sees $S" no "USB debugging on, RSA prompt accepted"
echo "INFO  model $(a getprop ro.product.model), Android $(a getprop ro.build.version.release)"
v=$(a cmd lock_settings verify); case "$v" in *"verified successfully"*) req "no screen-lock credential (reboot runs)" ok;;
  *) req "no screen-lock credential (reboot runs)" no "set the lock to None or Swipe for the run: $v";; esac
s=$(a settings get global stay_on_while_plugged_in); [ "${s:-0}" != 0 ] && req "Stay awake while charging" ok || req "Stay awake while charging" no "Developer options -> Stay awake"
p=$(a dumpsys battery | grep -E 'USB powered|AC powered' | grep -c true); [ "$p" -ge 1 ] && req "charger connected" ok || req "charger connected" no "plug the phone in"
a 'echo | nc -w 1 127.0.0.1 9 >/dev/null 2>&1; command -v nc || toybox nc --help >/dev/null 2>&1 && echo yes' | grep -q . \
  && req "nc on the phone (netloss check)" ok || req "nc on the phone (netloss check)" no "no nc: netloss cannot be verified"
echo "INFO  Doze enabled: $(a dumpsys deviceidle enabled) (run scripts disable it for the run and restore it after)"
echo "INFO  battery $(a dumpsys battery | grep level | tr -d ' ')"
[ $fail = 0 ] && echo "PREFLIGHT OK" || { echo "PREFLIGHT FAIL"; exit 1; }
