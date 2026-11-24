# Claim → evidence ledger (P04 ResidueDroid)

All numbers in the PDF are macros from `manuscript/generated/macros.tex` (written by `artifact/scripts/render.py`).
This ledger maps each claim to its source. "VERIFY-FINAL" = re-check wording against the final run.

| Claim (where) | Macro(s) | Source |
|---|---|---|
| Corpus size, strata (§3) | corpusN, trackN, randN, eligibleN | static/corpus.csv, index-v2.json |
| Persisted deferred work per stratum (Tab corpus; the pooled pctPersistAll/pctAlarmAll are no longer cited, 22/11) | tab_corpus.tex | results/static_corpus.csv |
| Candidate counts, three-hop and any-depth screens (§3; pooled pctCand* no longer cited, 22/11) | candConsentLoN, candConsentHiN | static_corpus.csv (candidate3/candidate) |
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
| Early check with cancellation matches the fence on the natural race; costs (§7b, abstract, §1) | gcloseN, gcloseEarlyViol, gcloseCloseViol, gcloseFenceViol, gcloseCut, gcloseCutComplete, gcloseAckLo/Hi, gcloseFenceAck | results/round3/g2close/analysis/g2close-summary.json ← final/trials.jsonl.gz (g2close-card.md, pre-registered) via make_summary.derived() |
| Cancellation aborts delivered requests (§7b, abstract; exploratory) | gcloseAbortDelivered, gcloseFenceAbortDelivered, gcloseFenceDelivered | results/round3/g2close/posthoc/posthoc.json (followup/posthoc_g2close.py, defined after the data) |
| Race outcomes counted from the withdrawal commit W: cancellation accepts post-W writes, fence none (§7b, abstract, §1; exploratory) | gcloseCommit{Early,Close,Fence,N}, gcloseCommitCloseKib, raceCommit*, racePhoneCommit* | results/round3/c-analysis/post-commit.json (scripts/post_commit_race.py, from the frozen race trial logs) via make_summary.derived() |
| Wilson 95% for pooled race cells (Tab race caption) | raceObsLo/Hi, racePhoneObsLo/Hi, raceZeroHi | b10 and test1-phone race-summary.json via make_summary.derived() (scripts/summarize.wilson) |
| AirGuard layered early build (§7b, §1) | glayN, glayStockViol, glayFenceViol, glayLayerViol, glayUnknown | results/round3/g2layer/analysis/airguard-summary.json (oracle v2, g2layer-card.md) via make_summary.derived() |
| Commit-point race: cross-process cancellation accepts post-W writes, same-process cancellation and fence none (abstract, §1, §7.3 Tab commit; pre-registered primary of G3a and P3) | gtrN, gtr{Early,Close,CloseTwo,Fence,Abort}W, gtrCloseLte, gtrEarlyAck, gtrCancelAck; gpN, gp{Early,Close,CloseTwo,Fence,Abort}W, gpCloseExposed, gp{Fence,Abort,CloseTwo}AckP | results/round3/g3race/analysis/g3race-summary.json (final + final-r2) and analysis-lte5/{g3race-summary,g3race-audit}.json (g3race-card.md, g3lte-card.md) via make_summary.group3(). C re-counted G3a independently (23/11, match) |
| Accepted bytes leave after the ack: capture counts and send-buffer sweep; about one buffer with a normal close, at most gsAbortMax with abortive close (abstract, §1, §7.3, §8, §10) | gtrCapLo/Hi; gsN, gsAfterW, gsFence{Small,Mid,Def}{Lo,Hi}, gsAbortMax, gsPairs, gsAbortLess, gsDefaultKib | g3race-summary.json capture (G3b); results/round3/g3race/analysis-p4/g3p4-summary.json (TLS v2 records, W during writes; g3p4-card.md) via make_summary.group3() |
| AirGuard in-upload withdrawal: builds not separated at the capture; at equal send buffer OkHttp Call.cancel() ~ fence at the receiver (abstract, §1, §7.4, App. airrace) | gaN, gaSentMin/Max, ga{Stock,Cancel,Layer,Fence}Rx; gb{Sixteen,Cancel,Fence}{N,Rx,Lo,Hi}, gbPair*, gbKern{Small,Def}Kib | results/round3/g3app/analysis-v4-r2 (receiver window corrected 23/11; analysis-v4 kept) and analysis-v5c/g3app5-summary.json (g3app-card.md, g3app5-card.md) via make_summary.group3(). C re-counted both independently (23/11, match) |
| Framing (24/11, after mock review round 5): lineage and epochs decide the lifecycle schedules whatever the placement; placement matters only during an upload, at the commit W (abstract, §1 Approach/Contributions/Evidence, §4 "Why this placement", §5 remark, §10) | tab:matched (generated/revision_results.tex), lifeFourteen*/lifeFifteen*, glayLayerViol; gtr*/gp* | matched campaign, B11, G2b; G3a and P3 as in the commit-point row. No new number |
| Cancellation found no registered call in one AirGuard trial (§7.4; exploratory) | gbNoCallRx | analysis-v5c/diag-v5c.json (followup/diag_g3app5.py, post hoc) |
| Phone cost: fence/early CPU per MiB and time; no energy reading (abstract, §7.5, §8) | gdCells, gdUploads, gdUploadFail, gdCpuLo/Hi, gdTimeLo/Hi, gdEnergyNonzero, gdEnergyCells; phone label racePhoneModel (same Galaxy A06) | results/round3/g3cost/analysis-v4/{g3cost-summary,batterystats-check}.json (g3cost-card.md protocol v4) via make_summary.group3(). C reran analyze_g3cost.py (24/11, identical) |

## Claims deliberately NOT made (novelty audit §5)
- No "first withdrawal measurement" (MowChecker is prior art); contribution = persistent job lineage + serialized late fence.
- Residual storage alone is never called a violation (T7 OS-revocation tenant is an FP control).
- No recall of submitted bytes (Prop. 4; outstanding submissions reported).
- No transparent enforcement for arbitrary apps; claims limited to mediated paths; uncovered list in §8/App. C.
- No legal conclusions; ACRA behavior described as configuration-dependent, not as a vulnerability in any app.
- No claim that the fence leaks fewer bytes at the NIC than cancellation: at equal send buffers they did not differ at the receiver (G3c v5c), and a graceful close drains about one buffer for any design (P4).
- No claim that same-process cancellation closes the race: its 0 post-W trials bound a rate; it is not serialized with the writer.
- No claim that the fence is the only way to meet the commit boundary: a cancellation serialized with the writer that reaches every in-flight request would too (§5 remark; untested). The fence's stated edge is that it needs no registry of in-flight requests.
- AirGuard lifecycle counts are violations only under our reading of the sharing switch (data collected while off stays forbidden after re-consent); §7.4 and App. round3impl say so (24/11, after the paperreview.ai and round-5 reviews).
- Appendix "Design Variants We Did Not Evaluate" (per-scope locks, serialized cancellation, abortive close and small buffers, durable acknowledgement with synchronous=FULL), the HTTP/2, TLS 1.3, Cronet and kernel/VPN composition notes, and the safety specification (App. lifecycle) are reasoning only: no run, no number.
- No fence/platform cost ratio (G3d): the platform arm logs 4 events per upload, the fixture transport about 7 per TLS record.
- No energy claim: batterystats estimated 0 mAh in every G3d cell.

## Known artifact caveat (not used in the paper)
- outcomes.csv `legit_*` for T5 under cancel/conv is not meaningful: cancel purges the outbox, so the four post-re-grant
  records are renumbered e1-00..03 while the oracle expects e1-12..15. T5 is not an FP-control tenant and no paper number
  uses its legit deficit; violation counting (epoch-based) is unaffected. Found 2026-11-09.
