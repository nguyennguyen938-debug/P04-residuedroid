#!/usr/bin/env python3
"""Mechanism-level smoke test for ResidueDroid hypotheses (stdlib only, seeded, NOT real data).

Model: a persisted upload job queued at t=0 runs at t=R (queue delay) and commits k batches at R+c_i.
A withdrawal arrives at W ~ U(0, T). Enforcement points: enqueue (t=0), job start (t=R), cancel at W (cooperative
between batches), serialized egress (at each commit, atomic with the withdrawal). Derived items may be filed under
another scope (lineage) and a re-grant may follow the withdrawal (epochs)."""
import random, statistics

def run(policy, rng, lineage_mis=False, regrant=False, n=20000):
    viol = 0
    for _ in range(n):
        T, R = 10.0, rng.uniform(2, 8)
        c = [R + 0.35 * (i + 1) for i in range(3)]            # 3 batches, 350 ms apart
        W = rng.uniform(0, T)
        G = W + 0.5 if regrant else None                        # re-grant 0.5 s after withdrawal
        bad = False
        for ci in c + ([R + 0.1] if lineage_mis else []):
            derived = lineage_mis and ci == R + 0.1
            allowed_now = not (W < ci) or (G is not None and G < ci)   # boolean consent flag at time ci
            invalid = W < ci                                    # item from epoch 0 is invalid after W
            if policy == "enqueue":
                sent = not (W < 0)
            elif policy == "jobstart":
                sent = not (W < R)
            elif policy == "cancel":
                sent = not (W < ci - 0.35)                      # stops only between batches
            elif policy == "egress_bool":
                sent = True if derived else allowed_now         # declared scope, boolean flag
            elif policy == "residuedroid":
                sent = not invalid                              # label carries epoch + source scope
            bad |= sent and invalid
        viol += bad
    return viol / n

rng = random.Random(20271204)
res = {}
for pol in ["enqueue", "jobstart", "cancel", "egress_bool", "residuedroid"]:
    res[pol] = (run(pol, random.Random(1)), run(pol, random.Random(2), lineage_mis=True), run(pol, random.Random(3), regrant=True))
    print(f"{pol:13s} plain={res[pol][0]:.3f} lineage-misfiled={res[pol][1]:.3f} withdraw+regrant={res[pol][2]:.3f}")
H1 = res["enqueue"][0] > 0 and res["jobstart"][0] > 0 and res["cancel"][0] > 0
H2 = all(v == 0 for v in res["residuedroid"])
H3 = res["egress_bool"][2] > 0 and res["residuedroid"][2] == 0
H4 = res["egress_bool"][1] > res["egress_bool"][0] and res["residuedroid"][1] == 0
# race theorem check: P(viol | jobstart) should equal P(R < W < R + c_k)
pred = statistics.mean(1 if (lambda R, W: R < W < R + 1.05)(r.uniform(2, 8), r.uniform(0, 10)) else 0
                       for r in [random.Random(1)] for _ in range(20000))
print(f"jobstart observed={res['jobstart'][0]:.3f} Eq.(2) prediction={pred:.3f}")
H5 = abs(res["jobstart"][0] - pred) < 0.01
for h, v in [("H1 earlier checks leak", H1), ("H2 serialized late fence never leaks", H2), ("H3 epochs needed after re-grant", H3),
             ("H4 lineage needed for misfiled derived data", H4), ("H5 Eq.(2) predicts job-start leak rate", H5)]:
    print(f"{h:45s} {'HOLDS' if v else 'DOES-NOT-HOLD'}")
