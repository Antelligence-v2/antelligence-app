# Graph-engineering source review: parent reconciliation

Date: 2026-09-10. **Reading accepted with corrections; no model-experiment, architecture or topology admission.** The independently written [critique](graph-paper-critique.md) is preserved byte-for-byte; this note governs interpretation where wording differs. [Acceptance/source identity](graph-review-acceptance.json).

## What was checked

Parent read the completed `deleg_b08bf590` manifest, transcript and artifact; reread the version-pinned [paper](https://arxiv.org/html/2606.21666v1), its §§3–6 and Tables1–4, and raw HTML Algorithm1 through its final loop line. The worker's transcript records source reading/search and its single artifact target, not a reproduction or implementation run. The saved primary HTML matches its original retrieval manifest SHA-256 `345b929e9c3f42b8e39bf858c6466234b65d7727cd9012104328245b5d4100f3` (148605 bytes). Worker critique SHA-256: `815f7121fc54150cdc5e123693eb32005748577a12a88472ec8ae8054c1cb827`.

## Admitted findings

| Question | Primary-source answer | Boundary for Antelligence |
|---|---|---|
| What does HR measure? | Fraction of assertions inconsistent with initialization ground truth, not agreement; up to eight outputs sampled/trial; 78% structured assertions and 22% free-text judging (§4.4) | Exact assertion denominators, extraction/de-duplication, checker implementation and judge access/blinding are not supplied. Do not call this an independently reproduced truth audit or task-success rate. |
| Did SSVP beat the cheaper baseline? | Travel HR: No-Sync0.492, SSVP0.463, Full-Broadcast0.658; SSVP vs No-Sync p=0.257 (Tables1/3). Calls/trial18/53/126 (Table2). | Small point estimate, not a demonstrated SSVP improvement over No-Sync; calls are not matched tokens, dollars or latency. No-Sync still exchanges task-directed messages (§4.3). |
| How broad is the evidence? | One exact agent model `claude-haiku-4-5-20251001`, three agents; travel30/30/15 trials and software-project-planning10/10/5 (Tables1/4) | Abstract's blanket30/condition is inconsistent with the table. Eight scenarios are travel destinations. Software planning is not executed code repair. No stated pairing or shared seeds supports paired inference. |
| Did the broadcast harm generalize? | Software HR0.188/0.150/0.150; travel's contamination effect did not replicate (§5.8/Table4) | Cascading versus orthogonal task structure is a useful hypothesis, not an identified causal law or proof for critical domains. |
| What does the protocol do? | [Algorithm1](https://arxiv.org/html/2606.21666v1#alg1) broadcasts summaries to all peers, computes all-pair CDS, gates on fleet-average CDS, then lets high-drift pairs exchange full context representations and reconcile/re-embed. §3.3 prepends full timestamped structured context for ContextMerge. | Not a pair-only trigger, not summary-only transport, and not independent verification: a receiving LLM adjudicates. Exact executable serialization remains unavailable from the paper. |
| Was topology isolated? | No controlled topology/routing factor. Content, synchronization timing, calls and merge prompting change together. All30 SSVP trials trigger at steps2/4 (§4.5). | Compare an adaptive trigger against the same merge policy at fixed steps2/4 before crediting adaptivity. Separate content/verification policy from edge selection. |
| Does similarity reveal truth? | No-sync maximum CDS vs HR r=-0.03; full broadcast has lower divergence yet higher travel HR (§5.3) | Do not optimize low divergence as correctness. Preserve valid disagreement and score external outcomes. |
| Can we reproduce the implementation now? | §4.2 promises code/prompts/scenarios/rubrics upon publication; worker found no first-party implementation link in the retrieved record/search scope | No implementation was inspected or run. Availability elsewhere is unknown, not disproven. A paper algorithm is not a verified executable implementation. |

## Corrections and qualifications to the worker review

1. **Interval labeling:** Table1 explicitly labels HR/TCS intervals as **95%CI**. The review's suggestion that they might simply be SE overstates ambiguity. The unreported part is their construction procedure and underlying data; retain the published interval label without reverse-engineering a method.
2. **Threshold calibration:** §4.5 calls two exceedances in the No-Sync series a low false-positive rate. But §4.1 already injects mismatches and no independent negative/positive drift labels are supplied. Do not admit a validated false-positive rate, calibrated truth detector, or held-out calibration from these exceedances alone.
3. **Independent judging:** HR is defined against truth, separately from agreement. The paper's adjective “independent” and two judge calls with κ=0.79 do not establish independent model families, blinded evaluation, deduplicated claims or verified factual accuracy. Judge consistency is not correctness.
4. **Adaptive control and implementation precision:** A fleet-average gate appears in the pseudocode; all observed SSVP runs use the same trigger steps. Neither this nor the merge prose establishes a causal benefit from adaptivity. The pseudocode uses context-vector notation while the prose supplies structured context; without released code, do not claim exact message serialization or a faithful reproduced router.

## What changes in our work—not another survey

The [living ledger](LEARNINGS.md) now marks the source review complete with these corrections. The tested [memory-action gate](memory-gate-follow-up.md) is unaffected; it remains a model-free substrate, not learned coordination.

The next communication comparison must preserve three distinctions:
- **Content and authority:** raw sharing versus evidence-scoped claims/reconciliation, with topology fixed. Include equally credible conflicts and a well-supported minority view. Missing/conflicting evidence should lead to bounded consultation or explicit abstention, not manufactured consensus.
- **Scheduling and routing:** fixed schedule versus adaptive trigger, then fixed/random/targeted edges with the same message and merge policy. Keep no-extra-sync with task-directed messages as a genuine control.
- **Measurement:** external task outcome and prefix safety first; unique-fact errors, repeated-assertion errors, agreement, justified/unnecessary abstention and actual resource use separately. Freeze per-arm memory histories, retain full-information solo/voting controls, and test structurally different compositions rather than renamed fixtures.

These are requirements for the pending shared contract/comparison, not newly implemented tests, chosen sample sizes, a victory threshold or authorization for inference. No new broad literature sweep, graph database, provider restart, deployment, scheduler change or spend authority is created by accepting this reading.
