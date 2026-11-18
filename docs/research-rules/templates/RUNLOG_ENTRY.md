# RUNLOG entry format (append to `artifact/results/RUNLOG.md`)

```
## YYYY-MM-DD
- HH:MM <EVENT> <campaign/run-id> on <AVD> (console <port>, sink <port>), protocol v<N>, seed <seed>.
  Observation: <what happened, with the evidence path: log file, trial ids, dumpsys output>.
  Diagnosis: <cause, or "not reproduced">.
  Fix: <code/config change, commit or file>, applies from trial k=<k>.
  Affected trials: <ids> → <excluded as <reason> | retained because ...>.
```

EVENT ∈ LAUNCH, PILOT, FREEZE, CRASH, STOP, RESUME, FIX, EXCLUDE, INVALIDATE, DONE, SHUTDOWN.
Bold the headline of incidents that change validity (e.g. `**Host sleep stalls.**`). Never rewrite
older entries; add a dated correction instead.
