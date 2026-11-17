# Claim → evidence ledger (P04 ResidueDroid)

All numbers in the PDF are macros from `manuscript/generated/macros.tex` (written by `artifact/scripts/render.py`).
This ledger maps each claim to its source. "VERIFY-FINAL" = re-check wording against the final run.

| Claim (where) | Macro(s) | Source |
|---|---|---|
| Corpus size, strata (§3) | corpusN, trackN, randN, eligibleN | static/corpus.csv, index-v2.json |
| Persisted deferred work prevalence (§3, Tab corpus) | pctPersistAll, pctAlarmAll | results/static_corpus.csv |
| Candidate range conservative/over-approx (§1, §3) | pctCandLo/Hi, pctCandConsentLo/Hi | static_corpus.csv (candidate3/candidate) |
| Validation sample: shallow plausible, deep implausible (§3) | valShallowN, valShallowNo, valDeepN, valDeepNo | results/static_validation_judged.csv (manual judgments by the author, class name + app purpose) |
| Workers polling isStopped (§3) | pctPollStop | static_jobs.csv |
| ACRA prevalence (§1, §3) | acraApps | static_corpus.csv |
| ACRA source behavior (§7.7) | — | ACRA 5.14.2 sources: StartupProcessorExecutor.kt, JobSenderService.kt, SendingConductor.kt, AdvancedSenderScheduler.kt (fetched 2026-11-08) |
| ACRA emulator outcomes (§1, §7.7) | acraStockLeak, acraFenceLeak, acraStockCtl, acraFenceCtl, acraStockReb, acraFenceReb, acraStockRebCtl, acraFenceRebCtl, acraJobGoneReb, acraFenceBlockLogged, acraLatencyMed | results/raw/acra/trials.jsonl (protocol v3 only, 2026-11-09 clean rerun on AVD A; earlier runs in acra_INVALID_* not analyzed) — VERIFIED 2026-11-09 (see STATUS) |
| Substrates WorkManager/AlarmManager (§7.2 "Other substrates", Tab substrate) | sub{Work,Alarm}Manager* | results/raw/sub_work, results/raw/sub_alarm (validity = summarize.validity) — VERIFIED 2026-11-09 |
| Non-taint FP deficits are reboot/connectivity stops (§7.4) | defOtherTT, defOtherReb, defOtherConnStop, defOtherTsix | outcomes.csv + device ONSTOP reason=7 — VERIFIED 2026-11-09 |
| Matrix of violation rates (§7.2) | tab_matrix.tex, viol*Pct | results/tab_matrix.csv ← outcomes.csv ← oracle.py |
| conv still leaks (§1, §7.2) | convViolPct, convTOneLifePct, convOtherLifeK/N, convRacePct | outcomes.csv |
| enqueue leaks except fstop (§7.2) | enqueueLifePct, enqueueFstopPct | outcomes.csv — VERIFIED 2026-11-09 (100% vs 40%) |
| egress leaks T5 after re-grant (§7.2) | egressTFivePct | outcomes.csv |
| net-loss leaks for job-start/conv/cancel (§7.2) | jobstartNetPct, convNetPct, cancelNetPct | outcomes.csv (net_mode=per-app-iptables only) — VERIFIED 2026-11-09 (99/100/100%) |
| rd zero prohibited items (§1, §7.2, §10) | rdItems, rdTenantTrials | outcomes.csv |
| volatile fails after kill/reboot/fstop (§7.2) | volatilePenPct, volatileLifePct | outcomes.csv |
| Eq.(2) prediction vs observed (§7.3) | predMaxAbsErr, nCmax, cmaxMedianMs | fig_inflight.csv + device_events.jsonl |
| Outstanding (unrecallable) submissions (§7.3) | outstandingSubs, outstandingRd | outcomes.csv |
| Serialization ablation (§7.3, Tab cost) | noserZeroPct, noserFivePct, rdStressViol | results/raw/micro/sink/stress.jsonl |
| FP deficit; taint blocks permitted flows (§7.4) | deficit*Pct, tab_fp.tex | outcomes.csv |
| Unmediated T9 leaks under rd (§7.4) | rdUnmedPct | outcomes.csv |
| Opaque T10 unattributable (§7.4) | opaqueUnknownSubs, opaqueTrials, rdOpaqueUnknown | outcomes.csv |
| Overhead (§7.6) | insNoUs, insLabUs, insDeltaUs, fenceNoneUs, fenceRdUs, eeNoneMs, eeRdMs, extrasDelta | results/raw/micro/sink/bench.jsonl |
| Durability orphans (§7.6) | crashKills, crashOrphA, crashOrphB, crashOrphBPct | results/raw/micro/crash.jsonl |
| Lifecycle facts (§2.2): reboot restores, kill keeps, force-stop removes jobs, revoke kills process | — | device_events.jsonl (smoke1 + campaign), RUNLOG 00:31–00:40 |
| Window CDF (§7.2) | winPendingMed, winRebootMed | device_events.jsonl (variant none) |
| Exclusions (§7.1, §8) | nInvalid, nTrialsTotal, nValidAll, nValidUnused | summary_campaign.json (first 50 valid trials per AVD×schedule analyzed) |
| Implementation size (§6) | impLoc | fixture/src/**/*.java |

## Claims deliberately NOT made (novelty audit §5)
- No "first withdrawal measurement" (MowChecker is prior art); contribution = persistent job lineage + serialized late fence.
- Residual storage alone is never called a violation (T7 OS-revocation tenant is an FP control).
- No recall of submitted bytes (Prop. 4; outstanding submissions reported).
- No transparent enforcement for arbitrary apps; claims limited to mediated paths; uncovered list in §8/App. C.
- No legal conclusions; ACRA behavior described as configuration-dependent, not as a vulnerability in any app.

## Known artifact caveat (not used in the paper)
- outcomes.csv `legit_*` for T5 under cancel/conv is not meaningful: cancel purges the outbox, so the four post-re-grant
  records are renumbered e1-00..03 while the oracle expects e1-12..15. T5 is not an FP-control tenant and no paper number
  uses its legit deficit; violation counting (epoch-based) is unaffected. Found 2026-11-09.
