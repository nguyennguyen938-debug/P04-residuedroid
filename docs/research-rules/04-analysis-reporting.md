# R4 — Analysis and statistical reporting

## R4.1 Oracle independence
- Ground truth comes from receiver/sink-visible tracer content and guest event order, never from the
  enforcement mechanism's own decisions (`scripts/oracle.py`, `revision/oracle_v2.py`,
  `revision/matched_oracle.py`, `followup/matched_oracle.py`).
- Keep the estimand explicit: historical stream-wrapper runs order by pre-write
  `AUTHORIZATION_LOGGED` (can undercount handoffs); channel runs use `WRITE_ATTEMPT` +
  `BYTES_ACCEPTED.n` + withdrawal transaction order. Do not reinterpret one as the other.
- An absent write return is `measurement_unknown`; `accepted_bytes` is then a lower bound.
  Receiver timestamps never infer guest withdrawal order.
- Changes to oracle logic require a unit test (`revision/test_oracle.py` pattern) for the new case.

## R4.2 Units and denominators
- State the unit for every rate: tenant-trial, paired trial, request, attempt, round.
- Give numerator and denominator (`26/100`, not just `26%`), per AVD and pooled.
- Throughput/CPU: say whether aggregate or per-upload; process CPU is not energy.

## R4.3 Uncertainty
- Proportions: Wilson 95% CI (or the cluster bootstrap below) — always with N.
- Clustered data: bootstrap whole paired trials (all tenants and variants together), stratified by
  AVD/configuration × schedule × rendering/instance phase; 10,000 draws; fixed seed (`20261115`
  for the revision). Strata with one trial cannot estimate within-stratum variation — say so.
- Tails: empirical nearest-rank p95, median (mean of the two middle values for even n), observed max.
  These are descriptive order statistics, not confidence bounds or service guarantees.
- No p-values or significance claims unless pre-registered with the test named.

## R4.4 Comparisons
- Paired, within-AVD comparisons are the only causal-style contrasts. Variant–AVD confounding in
  the historical c1 campaign makes cross-AVD comparisons descriptive.
- Fixed (non-randomized) cell order and shared host load are threats to validity for latency and
  cost; report them next to the numbers.
- Zero-versus-zero: report the paired counts; do not claim equivalence or superiority.

## R4.5 Threats to validity checklist (fill in for every new result)
Internal: order effects, shared host, emulator restarts/renderer changes, instrumentation overhead.
Construct: what the observation boundary actually measures (authorization vs acceptance vs receipt).
External: emulator vs phone, Android version, fixture mix vs real apps, cooperative/complete labels.
Conclusion: N, clustering, multiple comparisons, strata with no variance.
