# Experiment card — test6, protocol v3 (TLS suite with a longer deadline; both phones)

Status: frozen at the commit that adds this card. Amends `test6-card.md` (v2) for the TLS part only; v2 data stay as
recorded and are reported next to v3 (R1.4: new protocol version, new directories, both outcomes reported).

## Why (mechanism found 19/11, RUNLOG)
The TLS fixture passed a fixed 10 000 ms deadline to `TlsTransport.post`, shared by the coordinator's lock waits. On the
Galaxy (RTL, receiver over the RDB relay) a 1 MiB send took median 5.9 s, so the two `concurrent` requests that share one
policy lock exceeded 10 s → 39/40 SEND_ERROR (TLS / process / policy lock deadline). This is a harness limit, not a property
of the fence. v3 removes the artificial limit for all cases.

## Change (everything else as v2 §2–§4)
- `followup/tls_suite.py --deadline-ms 60000`: every send carries `deadline_ms=60000` (fixture extra added for B10; default
  10 000 ms unchanged); the per-case wait is max(13 s, deadline + 5 s). Without the flag the adb command trace is identical
  to v2 (checked with a fake adb, 26/26 commands).
- APK `fixture/build/tls-apk/rl-tls.apk` sha256 ca313b94…ef15 (adds only the `deadline_ms` extra vs v2's APK).
- All 7 cases × 20 blocks on both phones (not only `concurrent`, to avoid a selective rerun).
  Pixel 8a: Device Farm `testspec-v3-tls.yml` → `results/round3/test6/pixel8a-v3-tls`.
  Galaxy M35: RTL `run_rtl.sh --tls-start 0 --tls-n 20 --tls-deadline-ms 60000` → `results/round3/test6/galaxy3-tls`
  (prefix galaxy3- so v3 never mixes into the v2 `galaxy-*` analysis glob).
- Validity, replacement (blocks from 20, cap 5), analysis (`analyze_test6.py` with `plans/test6/runs-v3.json`) as v2.

## Outcome (19/11, `analyze_test6.py --manifest plans/test6/runs-v3.json` → `results/round3/test6/analysis-v3/`)
- Logged / invalid / analysed / unused: Pixel 20/0/20/0 blocks, Galaxy 20/0/20/0 blocks (140 TLS trials each).
- `concurrent`: Galaxy 40/40 requests completed (v2: 1/40); Pixel 40/40 (v2: 40/40). Every other case equal to v2 on both
  phones: fence cases 0/60 trials with bytes accepted after acknowledgement per phone; `buffered-early` 20/20; `control`,
  `early` 20/20 completed. Report v2 and v3 together; the v2 Galaxy `concurrent` failure is explained by the 10 s deadline.
- Runs: Pixel `pixel8a-v3-tls` (Device Farm, 9.9 trial min), Galaxy `galaxy3-tls` (RTL 15:09–15:22, gates pass).
