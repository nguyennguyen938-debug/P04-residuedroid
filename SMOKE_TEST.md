# SMOKE TEST — P04 ResidueDroid (mechanism-level, NOT real data)

Run 2026-11-08 with `python3 others/smoke/smoke_test.py` (stdlib only, seeded, ~1 s).

**Method.** A toy model of one persisted upload job: queued at t=0, starts at R ~ U(2,8) s, commits 3 batches 350 ms apart;
a withdrawal arrives at W ~ U(0,10) s. Enforcement points: check at enqueue, check at job start, cancel at W (cooperative
between batches), a serialized egress check on the job's declared scope with a boolean flag (`egress_bool`), and
ResidueDroid (serialized, per-item epoch + source-scope label). Two perturbations: a derived item filed under another
scope (lineage) and a re-grant 0.5 s after the withdrawal (epochs). 20,000 draws per cell. This checks the *direction* of
each hypothesis under the paper's own assumptions only. Real results come from the emulator campaign (PLAN.md).

| Hypothesis | Claim | Observed (toy) | Verdict |
|---|---|---|---|
| H1 | Checks before submission leak after withdrawal | enqueue 0.606, job start 0.105, cancel 0.105 | HOLDS |
| H2 | Serialized late fence with labels never leaks | 0.000 in all three settings | HOLDS |
| H3 | Epochs needed after re-grant | egress_bool 0.552 vs ResidueDroid 0.000 | HOLDS |
| H4 | Lineage needed for misfiled derived data | egress_bool 0.512 (vs 0.000 plain) vs ResidueDroid 0.000 | HOLDS |
| H5 | Eq.(2) predicts the job-start leak rate | observed 0.105 = predicted 0.105 | HOLDS |

Console output:
```
enqueue       plain=0.606 lineage-misfiled=0.609 withdraw+regrant=0.604
jobstart      plain=0.105 lineage-misfiled=0.107 withdraw+regrant=0.107
cancel        plain=0.105 lineage-misfiled=0.132 withdraw+regrant=0.107
egress_bool   plain=0.000 lineage-misfiled=0.512 withdraw+regrant=0.552
residuedroid  plain=0.000 lineage-misfiled=0.000 withdraw+regrant=0.000
jobstart observed=0.105 Eq.(2) prediction=0.105
H1 earlier checks leak                        HOLDS
H2 serialized late fence never leaks          HOLDS
H3 epochs needed after re-grant               HOLDS
H4 lineage needed for misfiled derived data   HOLDS
H5 Eq.(2) predicts job-start leak rate        HOLDS
```

**Caveats.** H2 holds by construction in the toy model (the model encodes Theorem 1's assumptions); the emulator campaign
tests it against real lifecycle behavior. The toy says nothing about prevalence, overhead or uncovered paths. The cancel
rate equals the job-start rate here only because both leak exactly when W falls inside the batch window.
