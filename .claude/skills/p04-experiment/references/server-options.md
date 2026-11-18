# Where each B task runs (team plan, round 3)

| Task | Host | Source |
|---|---|---|
| B0 smoke, B11 (Android 14/15), B4 + test 5, B10, B3, B12, B2 | B's Mac, Android emulators (arm64 images) | PLAN-ROUND3 hàng đợi emulator |
| A10 triage | B's Mac, host only | HUONG-DAN-B |
| Test 6 | **AWS Device Farm** (decision 18/11: rent AWS, not buy a phone); receiver mode A (Device Farm host via `adb reverse`) or B (EC2 us-west-2) | PLAN-ROUND3 §Quyết định; `artifact/devicefarm/README.md` |

Notes from the team plan:
- Keep arm64 images; if anything runs on x86_64, do not pool its timings with older campaigns.
- Device Farm: reboot and network cut unknown until the trial run; if unavailable, keep reb/net on the emulator and say so
  in §7a. A run may be capped (external source: 150 min) → split into batches. Phones on charge do not enter Doze →
  `dumpsys battery unplug`, `dumpsys deviceidle force-idle`, recorded in §7a.
- Device Farm price 0.17 USD per device minute; a one-time 1,000-minute trial may exist (check on the pricing page).
  The account and billing are created by the user, never by Claude.
- Never upload private material (no `review/`, no keys other than the public test CA/key in `followup/tls-cert/`).
