# Test 6 — excluded runs (pilots) and protocol changes they caused

All directories below are pilots: kept as recorded, never analysed or pooled with the main runs (R2.2). Details and
timestamps: `artifact/results/RUNLOG.md` (18–19/11). Protocol: `artifact/plans/test6-card.md`.

| Directory | Where | What happened | Change caused |
|---|---|---|---|
| `pilot-local-1` | emulator (P04Avd15, Android 15) | TLS-only rehearsal of the Device Farm pilot spec | none |
| `pilot-local-2` | emulator (P04Avd15) | combined spec rehearsal; mechanism checks passed; lifecycle trials 104–166 s | lifecycle split into 2 Device Farm jobs per device |
| `pilot-rtl-1` | Samsung RTL, Galaxy M35, Android 14 | adb 37 hung on RDB; with r33 adb the TLS CA copy `run-as … sh -c` froze the RDB link; TLS_EXIT=1, no lifecycle trial | use platform-tools r33 adb on RDB |
| `pilot-rtl-2` | Samsung RTL | same command froze the link again (parallel echo probe confirmed); isolated: a shell started under run-as | `tls_suite.py:56` copies the CA with `run-as … tee` (no shell under run-as) |
| `pilot-rtl-3` | Samsung RTL | all mechanism checks passed (TLS 7/7, lifecycle 3/3, kill verified, run-as DB reads, sink) | none |
| (offline) | fake adb | harness checks before freeze | `tls_suite.py --start`; `campaign.py` records `seen_max` (dumpsys parser check, Android 17) |
