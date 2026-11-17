# P04 — Four MobiSys reviews and meta-review

**Paper:** *ResidueDroid: Durable Lineage for Withdrawal-Aware Deferred Egress*  
**Review date:** 16 November 2026  
**Target:** MobiSys 2027, regular research paper  
**Meta-decision:** **Reject — weak reject; substantial practical validation remains.**

These are AI-generated author-feedback reviews, written as four distinct reviewer perspectives by one assistant. They are not independent human reviews or an actual program-committee decision. Apply author judgment to the recommendations. The assessment concerns the current manuscript, not the older review packets.

## Reviewed version, scope and scoring

The review covers `manuscript/main.tex`, the included sections and generated tables, the current PDF, selected implementation code including `artifact/transport/src/org/residuelab/transport/TlsTransport.java`, and the local validation reports. Experiments were not rerun for this review. A report of a successful local rebuild is not independent retrieval or reproduction.

PDF SHA-256: `b81d76b4d560adf2850ac1979cce60c135e5502f16784e155729094eb78dc06d`.

Overall scores use a simulated five-point scale: **5 strong accept; 4 weak accept; 3 borderline; 2 weak reject; 1 strong reject**. Dimension scores run from 1, poor, to 5, excellent. Confidence runs from 1, low, to 5, expert-level certainty. These are not claimed to be HotCRP's official fields.

The [MobiSys 2027 CFP](https://www.sigmobile.org/mobisys/2027/call_for_papers/) emphasizes implemented systems and practical evaluation. It specifies single-blind review, a 12-page body, at least 10-point type, at most 55 lines per column, and disclosure of LLM-generated text. Registration is 27 November and submission 4 December 2026, both AoE. Current source and PDF checks show the author's name, 10pt in `main.log`, US Letter pages, and references beginning on page 12. The package reports 53 review lines per column. These previously raised formatting issues are not current rejection reasons. This pass did not independently measure every rendered column or inspect every caption visually.

## Paper and evidence map

The paper addresses a cooperative application's explicit promise to invalidate previously queued data after withdrawal. Its mechanism persists source labels and policy epochs with deferred work, including copied job inputs, and optionally serializes each bounded socket handoff against withdrawal. The guarantee ends at accepted bytes, not delivery, server processing or recall.

| Claim or result | Current evidence | Interpretation and remaining limit |
|---|---|---|
| Collection checks alone miss retained copies, derived data and re-grants | §§2–4; ten-tenant fixture; separate lineage, epoch and retry cases | Useful mechanism decomposition. Fixture frequencies are not population violation rates. |
| Final placement adds protection beyond matched early checks | §7.3; 280 paired schedule trials, five variants | Layered early, fence and layered-plus-fence each have zero confirmed violating tenants in this campaign. The natural-schedule marginal benefit of the fence is unobserved. |
| The fence closes an adversarially placed residual race | HTTP and TLS barriers in §7.3 | The TLS barrier yields 20/20 complete early-arm requests versus 20/20 fenced blocks. This establishes a reachable schedule, not its field frequency. |
| Withdrawal need not wait behind a stalled upload | 800 backpressure attempts comparing whole-write and chunk locking | Strong operational result: stalled/slow whole-write acknowledgement approaches five seconds while observed chunk-lock acknowledgement remains milliseconds. Not a hard deadline or a population tail guarantee. |
| HTTPS is mediated | TLS 1.2 `SSLEngine` over nonblocking `SocketChannel` | Actual ciphertext writes are guarded. Pooling, redirects, proxies, renegotiation and other transports remain outside the implementation. |
| Labels fail closed | Conformance tests and malformed-label tests | Missing or malformed labels can be rejected. Valid but incomplete labels pass in 20/20 injected TLS cases; completeness remains trusted. |
| Real SDK integration is possible | ACRA and Matomo embeddings, settings trace, source counts | SDK integration is real; a production app's complete settings-to-egress path is not established. |
| Artifact can rebuild | `review/package-validation.json`: 1,098 manifest files, 16 generated files unchanged, matching PDF text | Credible reported local reproducibility. No independent external retrieval was performed in this review. |

## Context, novelty and gap audit

The following nine targeted primary sources were checked for this assessment. They are comparison context, not nine demands for new citations. The related-work section already includes most of them.

| Verified source | Relationship and review consequence |
|---|---|
| [MowChecker, IEEE S&P 2024, author paper](https://yinzhicao.org/mowchecker/mowchecker.pdf) | Closest withdrawal-choice work. The paper already distinguishes wiring a choice to collection from governing previously persisted work. Preserve that distinction without implying prior work never considers scope mismatches. |
| [TaintDroid, OSDI 2010](https://www.usenix.org/conference/osdi10/taintdroid-information-flow-tracking-system-realtime-privacy-monitoring) | Establishes mobile runtime information-flow tracking. Source labels and sink checks alone are not the novelty; durable withdrawal semantics must carry the contribution. |
| [CleanOS, OSDI 2012](https://www.usenix.org/conference/osdi12/technical-sessions) | Tracks sensitive data and limits idle exposure. Different objective, but relevant precedent for persistent sensitive-data management. |
| [Pebbles, OSDI 2014](https://www.usenix.org/conference/osdi14/technical-sessions/presentation/spahn) | Logical objects and their copies are an established management problem. Its automated object recovery highlights the burden of manually complete labels here. |
| [Weir: Practical DIFC Enforcement on Android, USENIX Security 2016](https://www.usenix.org/conference/usenixsecurity16/technical-sessions/presentation/nadkarni) | Stronger enforcement infrastructure under a different trust model. Do not present a synthetic broad-taint rule as a measured reproduction of Weir or modern IFC systems. |
| [Riverbed, NSDI 2019](https://www.usenix.org/conference/nsdi19/presentation/wang-frank) | Enforces user policies in managed server execution. Useful for explaining why device acceptance and downstream policy enforcement are complementary. |
| [WorkManager work management](https://developer.android.com/develop/background-work/background-tasks/persistent/how-to/manage-work) | Cancellation and stopping are relevant operational baselines. The remaining comparison is cancellation plus identical durable labels and epochs, not an unlabeled cancellation strawman. |
| [Android SDK Runtime architecture](https://privacysandbox.google.com/private-advertising/sdk-runtime/architecture) | Process isolation does not itself implement queued-data withdrawal. It also illustrates that deployment includes process lifecycle and inter-process boundaries. |
| [Matomo tracking and cookie consent](https://developer.matomo.org/guides/tracking-consent) | Illustrates distinct consent contracts. These JavaScript APIs do not establish the semantics of the Android dispatcher evaluated in the paper. |

**Novelty judgment.** The potentially publishable contribution is the combination of explicit pending-data contracts, durable provenance across Android deferred-work copies, and a precisely scoped handoff boundary. Labels, epoch revocation and serialization are established techniques. The theory is useful specification and explanation; it is not independently a new concurrency algorithm.

**Remaining baseline gap.** Matched metadata and layered early checks are already implemented. Asking for them again would be incorrect. The remaining question is whether their difference from the fence matters in a realistic integrated workload, and whether the integration can maintain complete metadata under ordinary application evolution.

**Framework that would strengthen the argument.** A lifecycle state machine should separate retained data, queued work, TLS-buffered application records, socket-accepted prefixes, receiver completion and response receipt. Each transition should name its policy check, crash outcome and retry contract. This would make the existing proofs easier to connect to the evaluated implementations.

## Reviewer 1 — Mobile systems and transport integration

**Overall: 3/5, borderline. Confidence: 4/5.**

### Summary

ResidueDroid makes withdrawal apply to deferred work by carrying durable lineage and grant epochs into transmission. The transport implementation guards bounded writes under the same synchronization used to acknowledge withdrawal. The paper measures lifecycle persistence, matched check placement, backpressure, HTTPS and two SDK embeddings. I find the specification and transport engineering useful, but the deployment evidence is still narrower than the title's general application setting.

### Strengths

1. The accepted-byte boundary is much better specified than a pre-write authorization marker. The paper distinguishes successful handoff, partial requests and receiver completion, and admits uncertainty around a process death between native return and logging (§§5, 7.3).
2. The backpressure campaign answers a genuine systems concern. Moving readiness waits outside the lock and checking bounded writes prevents a stalled upload from holding up unrelated withdrawal for the entire send deadline in the measured cases.
3. HTTPS is implemented rather than merely proposed. The inspected `TlsTransport.java` checks application ciphertext writes, including record remainders, and does not treat `wrap()` as network delivery. This addresses a major practical gap in a plain-HTTP prototype.
4. The matched campaign gives early checks the same metadata. Its negative result is valuable: the mechanism's benefit cannot simply be attributed to being placed later.

### Weaknesses and implications

The transport is intentionally restricted to single-request TLS 1.2. In §6 and §7.3, there is no demonstrated integration with the pooling, redirects, retry logic or alternate senders of a production HTTP stack. Those exclusions are honest, but mediation is the premise of the guarantee. A production embedding needs either an explicit, enforceable restriction to this transport or evidence that all relevant paths actually use it.

The current performance experiment is an instrumented 1 MiB transfer on an emulator. TLS median CPU rises from 168.5 to 214.0 ms between the early and fenced arms, while elapsed times are 626.9 and 642.8 ms. Fixed block order and included handshake/logging costs prevent a clean attribution of overhead. Concurrent-throughput numbers also need an explicit aggregate-versus-per-upload denominator. This is useful feasibility evidence, not a mobile energy or sustained-throughput characterization.

The enlarged matched campaign observes no confirmed violating tenants for layered early checks, the fence or their combination. The forced barrier justifies closing a residual race, but does not establish that a general application should pay the integration cost for it. The narrowed title and contribution help; a natural integrated execution would make the systems case much stronger.

Finally, the app-wide lock is a clear correctness choice, but contention across many active scopes and senders is not characterized beyond the fixture. The five-second operation deadline is best effort, and the text should retain that qualification.

### Questions for the authors

- Which production request path can be constrained to this transport without bypassing the application's ordinary retry or authentication behavior?
- What are per-upload throughput, aggregate throughput and acknowledgement distributions under randomized concurrent load?
- Is there an organically occurring integration schedule that distinguishes matched layered early checks from the fence, without an injected pre-send barrier?

### Recommendation

I am borderline. A convincing end-to-end app integration and randomized physical-device transport measurements would move me toward acceptance. More repetitions of the same deterministic barrier would not materially change my assessment.

## Reviewer 2 — Privacy contracts and information-flow correctness

**Overall: 2/5, weak reject. Confidence: 4/5.**

### Summary

The paper presents a developer-cooperative enforcement library for explicit withdrawal contracts. It correctly separates permission revocation, collection opt-out, pending-data invalidation and deletion. Its principal challenge is preserving complete source provenance through persisted copies and derivations. The proposed bookkeeping handles that challenge when developers supply correct labels, but the current evaluation does not establish how reliably they can do so in a realistic application.

### Strengths

The four-contract taxonomy (§2) prevents several common but serious interpretation errors. In particular, a stock toggle that stops collection does not automatically promise deletion of queued reports. The ACRA stock result is therefore not mislabeled as a demonstrated privacy violation.

Epochs make the re-grant case explicit: restoring a grant does not silently authorize data from an invalidated epoch. Persisting labels alongside job extras also addresses a concrete way in which deleting a database row can fail to remove a deferred copy.

The label-error experiment is candid. Missing or malformed metadata can fail closed, whereas syntactically valid but incomplete labels escape that defense. Similarly, mixed-source request rejection is reported as an availability cost rather than a free security improvement.

### Weaknesses and implications

**A2 is the largest practical assumption.** The incomplete-label experiment allows all 20/20 affected TLS requests. This does not refute the conditional theorem, but it demonstrates that the library cannot independently establish the provenance premise on which that theorem rests. The DEX checker finds candidate unwrapped network calls; it does not verify derived-data labels, serialization boundaries, job-extra copying or developer omissions. The paper needs evidence about the effort and failure modes of maintaining these obligations in an app with an actual data pipeline.

**Revocation granularity remains a product decision.** Unioning labels conservatively causes a request containing one forbidden item to lose permitted items as well. The experiment establishes this behavior, but not a policy for splitting batches, retrying the permitted subset or preventing repeated suppression. Availability is consequential for telemetry and crash reports even under an explicit stronger contract.

**The user-visible acknowledgement is narrower than a user might infer.** No later accepted prefix is the relevant guarantee. Already accepted bytes may still reach the receiver after acknowledgement. The reported socket-buffer experiment does not measure exactly how many bytes were still unsent at acknowledgement, and the manuscript says so. The settings wording and examples should explain this boundary directly rather than relying on a later proposition.

**Incremental novelty needs sharper evidence.** Taint tracking, policy epochs and a serialized sink are established. The distinctive contribution is durable, contract-specific treatment of deferred Android work. The current controlled app is built around precisely the cases these mechanisms solve; the real SDK embeddings do not yet show coverage of a broad application's derived-data lifecycle.

### Questions for the authors

- How can a maintainer check that a newly introduced summary field or copied job input has a complete source set?
- What happens to allowed records in a mixed batch after rejection: are they split, retained, retried or permanently lost?
- What exact acknowledgement wording is exposed to the user, including the treatment of bytes accepted before acknowledgement?

### Recommendation

Weak reject. I do not require enforcement against a malicious host, which is explicitly out of scope. I do require stronger evidence that cooperative developers can satisfy the library's provenance and mediation obligations without silently losing its guarantee.

## Reviewer 3 — Experimental design and statistical validity

**Overall: 2/5, weak reject. Confidence: 4/5.**

### Summary

The paper contains a substantial controlled evaluation, with useful separation between authorization-order evidence and observed socket acceptance. However, the studies remain concentrated on one designed fixture and a small number of emulator configurations. Their careful interpretation improves validity within that setting but does not yet establish the practical importance of the complete system.

### Strengths

The 280-trial matched campaign is a substantial improvement over unmatched comparisons. Its five arms share lineage, epochs, copied work inputs and transport. Pairing by schedule is appropriate, and the paper does not equate multiple instances on one host with independent phones.

The static screen is presented as a candidate-path study rather than a population count of contract violations. Its tracking-related stratum is separated from the random stratum, and manual-validation uncertainty is disclosed (§3).

Unknown outcomes and invalid paired attempts are retained instead of being silently counted as successes. The crash/logging ambiguity is particularly important when assessing a claim about the last accepted write.

### Weaknesses and implications

**The headline mechanism decomposition is still fixture-conditioned.** T1, T5 and T8 expose lineage, epoch and retry needs, but their rates depend on how tenants and schedules were chosen. The paper now acknowledges this. The unresolved issue is external evidence that these combinations occur, with relevant pending-data contracts, in actual applications.

**Zero-versus-zero is not an equivalence result.** Layered early, fenced and combined variants each have zero confirmed violating tenants in the enlarged matched campaign, with unknown counts 6, 2 and 1 respectively. A paired bootstrap interval of [0,0] describes these samples; it does not bound the difference under rare races. Unknowns and shared tenants prevent treating the tenant total as independent Bernoulli replications. Report trial-level sensitivity to unknown outcomes and the smallest effect the campaign could reasonably distinguish.

**Availability needs a current-cohort explanation.** Permitted-item deficits are 168/14,000, 96/14,000 and 60/14,000 for layered early, fence and their combination. The explanation of the smaller cohort's 56/3,500 and 52/3,500 deficits is useful but cannot automatically explain the enlarged cohort. An exhaustive current-cohort accounting would connect missing deliveries to retirement, window closure, timeout, policy rejection and unresolved outcomes.

**Performance and backpressure are not hardware replication.** The large number of attempts improves coverage of the selected schedules. It does not capture radio variability, device CPU scheduling, OEM lifecycle behavior or physical energy. Fixed order in the TLS transfer campaign is another confound. These are limitations of the experimental units, not a complaint that every microbenchmark needs a field deployment.

### Questions for the authors

- How many independent paired trials contain any confirmed violation or any unknown outcome, by schedule and platform?
- Can every permitted-item deficit in the enlarged campaign be assigned a mutually exclusive terminal cause?
- What fraction of actual app settings promise invalidation of previously queued data, rather than stopping future collection only?

### Recommendation

Weak reject for a regular MobiSys paper. A smaller number of well-instrumented, diverse real integrations and physical-device trials would be more persuasive than another increase in fixture repetitions.

## Reviewer 4 — Reproducibility and developer adoption

**Overall: 3/5, borderline. Confidence: 3/5.**

### Summary

The artifact appears unusually transparent about exclusions, prototype boundaries and failed attempts. The manuscript gives enough technical detail to understand the library and many of its checks. My uncertainty is whether a new developer could adopt it correctly and reproduce the principal results without inheriting the authors' prepared environment and fixture assumptions.

### Strengths

The reported clean package rebuild checks 1,098 manifest files, regenerates 16 outputs without changes and reproduces PDF text. The manuscript separates that local result from independent artifact retrieval. This is the right level of honesty.

The ACRA and Matomo examples are concrete SDK embeddings, not pseudocode. The paper provides source counts—six ACRA Java files with 202 nonblank lines, two Matomo files with 56, and three shared files with 196—and identifies important unsupported paths. The figures should remain described as maintained source, not a measured upstream patch size or person-time estimate.

The conformance suite, incomplete-label experiment and mediation checker give developers useful negative tests. The actual TLS code is consistent with the stated restriction to a single request and a conservative union of request labels.

### Weaknesses and implications

The integration evidence spans several differently scoped builds and studies: stream authorization logging, channel acceptance, the TLS fixture, ACRA-P, the smaller ACRA-R smoke tests and Matomo's controlled pre-send barrier. Those distinctions are disclosed, but the reader must reconstruct which claim is supported by which exact build. A compact implementation/contract matrix would reduce the risk of accidentally combining them into a single fully evaluated deployment.

No identified third-party F-Droid app has yet been exercised end-to-end through its own settings UI and normal lifecycle. The ACRA fixture UI and stronger invalidation setting establish an integration example, not a stock product contract. That gap matters especially because most integration errors are likely to occur in app code around the SDK.

The checker flags five of seven candidate ACRA sites and four of six Matomo sites. These are useful leads but not proof of reachable bypasses or complete mediation. A developer needs triage results explaining which paths are reachable under supported configurations, wrapped elsewhere or intentionally excluded.

The artifact is locally packaged, but the report relies on an existing toolchain. Fresh download, dependency installation and result regeneration by another person remain unverified. This is not evidence of a broken artifact; it is an uncompleted reproducibility claim.

### Questions for the authors

- Is there one documented “supported deployment” configuration whose label coverage, send coverage, retry behavior and settings contract are all tested together?
- What must change when an application introduces a new source, summary or background service?
- Which candidate bypasses survive a reachability and configuration audit?

### Recommendation

Borderline. The implementation and artifact are useful enough to merit serious consideration, but the paper needs one coherent realistic integration more than additional isolated feature demonstrations.

## Scores across perspectives

| Dimension | R1 systems | R2 privacy | R3 evaluation | R4 adoption |
|---|---:|---:|---:|---:|
| Originality | 3 | 2 | 3 | 3 |
| Importance | 4 | 4 | 4 | 4 |
| Claim support | 4 | 3 | 3 | 4 |
| Experimental soundness | 3 | 3 | 2 | 3 |
| Writing clarity | 3 | 3 | 3 | 3 |
| Community value | 4 | 3 | 3 | 4 |
| Contextualization | 4 | 3 | 4 | 4 |
| **Overall recommendation** | **3** | **2** | **2** | **3** |
| **Confidence** | **4** | **4** | **4** | **3** |

## Writing and logic audit

- **Keep the new thesis.** Durable lineage and epochs are primary; the fence closes a residual schedule. Do not restore an aggregate fixture percentage as a population headline.
- **Unify boundary vocabulary.** “Bytes leave the device” is less precise than positive socket acceptance. Use the latter for the theorem and explicitly connect it to user-facing withdrawal wording.
- **Make implementation coverage scannable.** One table should identify build, HTTP/TLS transport, contract, retry support, evidence boundary and exclusions. This is more useful than chronology.
- **Finish the prose cleanup.** Generated ACRA text still contains lowercase sentence starts such as “acra delivered” and “stock sent.” Fix the generator, not only its output.
- **Preserve distinctions that are already correct.** Process-crash tests do not establish power-loss durability; missing labels differ from valid incomplete labels; accepted bytes differ from exact unsent residue; SDK embedding differs from a deployed app.

## Meta-review

### Decision: Reject — weak reject

All four perspectives find the problem relevant and the implementation substantially more credible than a wrapper that checks only before a blocking write. The HTTPS path, matched-metadata baselines, backpressure tests, explicit incomplete-label failure and contract-sensitive ACRA interpretation resolve several serious earlier concerns. They should receive credit rather than be requested again.

The disagreement concerns whether this combination is already a sufficient MobiSys contribution. Reviewers 1 and 4 see a useful systems design and reproducible developer toolkit. Reviewers 2 and 3 give greater weight to the premises left outside the demonstrated system: complete provenance, complete mediation and realistic settings-to-egress behavior. The matched campaign also finds no confirmed difference between layered early checking and the fence under its lifecycle schedules. This is not evidence that the fence is useless; it limits the practical benefit presently demonstrated.

The rejection is therefore based on the gap between a well-specified cooperative fixture and a validated application integration, combined with an incremental core mechanism. It is not based on a known counterexample to the theorem under its assumptions, a missing TLS implementation, a missing metadata-matched baseline or the old formatting problems.

I would not recommend conditional acceptance that depends on finding a new real-app discriminating case, completing extensive phone measurements and establishing provenance coverage after notification. Those are substantial evidence tasks. A successful real integration, a coverage-oriented adoption study and randomized device measurements could materially change the decision.

**Subjective acceptance band:** approximately **15–30%** for the current regular-paper version, with low confidence in the numerical band. This is a planning judgment, not a calibrated conference forecast. The strongest upward move would be a coherent production-style integration that validates the bookkeeping obligations; more controlled race repetitions would have much less impact.

## Prioritized checklist

### P0 — Submission readiness

- [x] Current source requests 10pt; log confirms it; PDF author is Xuan-Bach Le; references start on page 12.
- [x] Current manuscript includes LLM-assistance disclosure and single-blind front matter.
- [ ] Recheck final rendered columns, captions, links and body pagination after all edits; retain the essential matched, TLS and uncertainty results in the body.
- [ ] Complete abstract registration by 27 November 2026 AoE and submission by 4 December 2026 AoE. Registration/submission was not performed by this review.

### P1 — Decision-critical evidence and framing

- [ ] Demonstrate one real application's complete settings → queued copies/derivations → restart/retry → HTTP(S) path. State its actual contract and include allowed-flow controls.
- [ ] Validate provenance maintenance: enumerate supported sources and transformations, trace job-extra copies and migrations, and show how an incomplete but well-formed label is detected or explicitly remains trusted.
- [ ] Audit all reachable send paths in that integration; triage the DEX checker's candidates and clearly bound unsupported/native/IPC paths.
- [ ] Keep the fence contribution residual unless a natural integrated schedule distinguishes it from matched layered early checks. Report paired zero-versus-zero evidence without claiming equivalence.
- [ ] Explain every permitted-item deficit in the enlarged matched campaign and report trial-level results with unknown-outcome sensitivity.
- [ ] Add randomized physical-device transport and lifecycle measurements, ideally spanning two Android/OEM configurations. Report CPU, throughput denominators, contention, acknowledgement tails and actual physical energy if claiming it. Handset validation remains open under the current emulator-only work constraint.

### P2 — Strongly recommended

- [ ] Define a mixed-batch recovery policy and measure allowed-record retention and retry success after one forbidden component blocks a request.
- [ ] Measure kernel-unsent residue with a justified observation method, or continue to label accepted ciphertext as a different quantity and avoid exact-residue claims.
- [ ] Publish a single deployment/implementation matrix connecting each table to its tested build and contract.
- [ ] Have an independent reader retrieve and rebuild the distributable artifact; keep local rebuild claims separate until then.
- [ ] Expose the accepted-byte limitation in the user-facing acknowledgement contract.

### P3 — Presentation and extensions

- [ ] Fix generated lowercase sentences and harmonize acceptance/commit/delivery terminology.
- [ ] Explore per-scope synchronization only if measurements identify app-wide contention; preserve the withdrawal ordering argument.
- [ ] Add a developer change checklist for new sources, summaries, queues and SDK transports.
