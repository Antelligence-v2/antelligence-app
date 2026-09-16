# Antelligence: Shared Evidence Memory and Model-Free Verification for Safer, More Efficient LLM Swarms

**Draft status:** v0 skeleton, based only on existing local experiment reports and the review snapshot.  
**Authors:** [TODO: verify]  
**Affiliation:** [TODO: verify]  
**Date:** [TODO: verify]

## Abstract

Large language model (LLM) swarms can divide search and exchange partial observations, but shared state also creates stale-memory, contradictory-evidence, and confident-wrong-action failures. Antelligence is a decentralized-science (DeSci) framework for attributed evidence, evidence invalidation, bounded communication, and independent task verification. Its motivating application is patient-aware brain-tumor simulation: robots or agents coordinate through trails in a simulated environment, while evidence provenance and verification make the resulting claims inspectable. This paper reports what the current experiments establish, without treating a simulator result as clinical evidence.

The approved headline is: **Shared evidence memory with a model-free verifier makes LLM swarms ~16% more search-efficient (p=0.012, replicated across weak and strong models), and converts confident-wrong acting on stale memory into verified-safe behavior (0 unsafe acts); the benefit is architectural (model-independent), while raw spatial competence is model-bound (capability floor in 2 of 3 tested models).** In the capability-matched E7v6 binary harness, hive memory reduced sweep moves from 2319 to 1941 across 20 seeds with hermes-4-405b at temperature 0; a genuine E9-binary run with grok-4-fast reproduced the same aggregate and sign-test result (p=0.012), despite different token totals. In deterministic mechanism tests, memory plus verification was 2.6–6.9x cheaper than always re-querying under silent drift, with 0 unsafe acts and McNemar p<=0.006; the verifier classified 58/58 cases, and the evidence transport blocked 6/6 attacks admitted by a naive swarm. The negative results matter: communication added no demonstrated throughput value when memory was already shared, and the full-spatial task exposed a model capability floor rather than an architectural gain. The evidence supports safety and cost-under-drift, not a general increase in raw model capability or clinical efficacy.

## 1. Introduction

Antelligence studies a narrow systems question with a broad DeSci motivation: can a swarm of language-model agents reuse evidence without turning shared state into an unexamined source of error? The intended long-term setting is a patient-aware tumor simulation in which many simple agents coordinate search, movement, or intervention under constrained information. In that setting, a useful coordination layer must do more than move messages. It must preserve where a claim came from, distinguish a candidate claim from a trusted outcome, invalidate dependent procedures when their evidence changes, and refuse to act when current state cannot be established.

The current work is deliberately smaller than that vision. It evaluates a self-contained evidence-memory packet and two model-in-the-loop foraging harnesses. The packet includes a common evidence contract (C0), evidence memory (F1), task planning and checking (F2), and local evidence communication (F3). The review snapshot describes these components as a development harness, not an integration into the live workbench, tumor engine, API, or UI. The experiments therefore ask whether the mechanisms earn their complexity in controlled task families, not whether Antelligence treats tumors or improves a deployed swarm.

The main architectural result comes from E7v6. Earlier spatial versions were not discriminating because the model had to execute state-conditional PICK and DROP actions. E7v6 removes that confound: picking up food and dropping it at the nest happen automatically, while the LLM chooses only between following a known target and continuing a systematic sweep. The discriminating measure is sweep moves, a proxy for redundant blind search. Under this isolation, shared hive memory reduces sweep moves by approximately 16%.

E9 tests whether that result is merely a property of one model. Its binary harness uses the same seeds and task structure with grok-4-fast. The aggregate is identical to the hermes-4-405b result: baseline 2319 sweep moves, hive memory 1941, with 16/20 seeds favoring hive memory and a sign test of p=0.012. Token totals differ, so the replication is a genuine run rather than cache reuse. This supports a bounded claim: within this harness, the improvement is driven by the memory-mediated coordination architecture rather than by a model-specific quirk.

The paper makes three narrower contributions:

1. It separates architectural value from model capability by using a binary, coordination-isolated harness.
2. It measures safety mechanisms directly: verification, provenance-aware memory, and transport admission.
3. It records negative results as first-class results, including the absence of communication throughput gains under shared memory and the persistence of a full-spatial model floor.

## 2. Related Work

This paper sits at the intersection of four literatures. First, multi-agent LLM systems study delegation, communication, shared memory, and collective task completion. [TODO: verify citations and delimit Antelligence from the closest LLM-swarm baselines.] Second, stigmergic and ant-colony systems motivate indirect coordination through shared environmental traces rather than unrestricted peer dialogue. [TODO: verify citations for the biological and computational antecedents.] Third, DeSci systems emphasize provenance, reproducibility, and verifiable research artifacts; Antelligence applies those concerns to agent evidence and action outcomes. [TODO: verify citations and define the intended DeSci contribution precisely.] Fourth, the Multi-Agent System failure taxonomy (MAST) provides a vocabulary for discussing how multi-agent systems fail. [TODO: verify the canonical MAST reference and exact category names before submission.]

The present work is not a survey and does not claim priority over any of these lines. Its operational distinction is that shared evidence is not treated as truth merely because it is shared. The evidence store records lineage and status; the verifier independently replays submitted actions against current task state; and the transport validates scope, source revision, causality, expiry, identity, and resource bounds before invoking a recipient. These mechanisms are evaluated as separable pieces rather than bundled into a single end-to-end accuracy claim.

## 3. System: Antelligence Hive Machinery

### 3.1 Design principle

The system treats a swarm's shared state as evidence with obligations, not as a transparent blackboard. Unknown is not success. A claim may be retained for retrieval, but an action outcome is evaluator-owned. A procedure that depends on invalidated or contradicted evidence must not remain actionable.

### 3.2 Common rules and evidence memory

The C0 contract separates public evidence from trusted outcomes and gives events canonical, attributed forms. F1, implemented by `HiveMemoryStore`, is a small versioned scratch store with atomic candidate/admission operations. Records carry source identity, protocol and revision information, kind, status, and dependency references. The store validates its schema and stored rows when opened; record identity is content-derived; and cross-experimental-arm references are rejected.

Source replacement is propagated through dependent records. A superseded source can invalidate a dependent procedure, and contradiction records block admission of dependent procedures. These behaviors are central to the paper's safety claim: memory does not need to discover every change automatically to fail closed once a change or contradiction is represented. The review snapshot explicitly warns that unannounced source changes can still leave stale information recallable; source identifiers, revisions, and timestamps are not automatic truth detection.

### 3.3 Model-free task verification

F2 exposes `verify_task`, which replays every submitted action and derives an evaluator-owned result. Rejected actions do not mutate state, but every later attempt remains recorded. Worker-provided `accepted` fields and terminal claims are ignored. The verifier checks action shape, operation support, revision, identifiers, resource availability, reservation requirements, prerequisites, zone compatibility, and the action budget. It classifies episodes as success, attempted unsafe, verified impossible, safe incomplete, unknown, or actual state violation when applicable.

This separation is important for LLM systems. The model may propose an action and describe it confidently; the verifier decides whether the action was accepted, whether state changed, and whether the task completed. The reported experiments use this boundary to distinguish an unsafe attempt from a safe abstention and a genuine success.

### 3.4 Bounded evidence communication

F3, implemented by `LocalEvidenceTransport`, is an in-process recipient-addressed transport with admission before callbacks. It checks frame shape and content-derived message identity, sender and recipient identity, scope, source revision, causal references, expiry, duplicate/replay status, message size, consultation count, fanout, and step bounds. Conflicting equally credible replies are quarantined. `plan_after_consultation` gates planner execution on admitted consultation state. When evidence is missing, the transport can return an explicit abstention rather than manufacturing a reply.

The transport is therefore not primarily a throughput optimizer. Its intended value is to prevent stale, tampered, duplicated, contradictory, over-budget, or wrongly addressed evidence from becoming an accepted planning input. E5 also tests whether targeted consultation can reduce message count relative to naive broadcast when agents have genuinely partial views.

## 4. Evaluation

### 4.1 Evaluation questions and controls

The experiments use the actual review-packet components, imported read-only. The deterministic suite uses no model calls and standard-library runtime code. A fresh Python 3.11 environment ran 167 tests successfully. The review packet reports 480 assigned matrix rows replayed plus 24 unreported-drift diagnostic cases. These are controlled task families, not independent real-world trials.

The evaluation separates four questions:

* Does verification prevent unsafe action and provide useful diagnosis?
* Does evidence memory reduce the cost of repeatedly obtaining information when sources drift silently?
* Does bounded communication defend against malformed or adversarial evidence and reduce naive gossip?
* Does shared evidence reduce redundant exploration when model action execution is not the confound?

### 4.2 Deterministic mechanism suite: E1–E6

**E1 — Costly re-query economics.** Across 24-task streams and 12 master seeds, memory plus verification was 2.6–6.9x cheaper than always-requery under silent drift, with 0 unsafe acts and McNemar p<=0.006. The memory-plus-verifier arm completed 288/288 in every grid cell. The no-verifier cache acted on stale memory and produced 120–156 unsafe rejected attempts per cell in the reported drift conditions. The result is regime-specific: the machinery earns its cost when re-queries are expensive and sources drift silently; it is not a universal token or latency saving.

**E2 — Verifier classification.** The verifier classified 58/58 cases correctly, including feasible chain and fork plans, impossible tasks, corrupted wrong-zone plans, over-budget plans, private-metadata smuggling, and partial plans. It caught every unsafe plan before the evaluator did. The evidence supports diagnostic classification and prevention of unsafe execution, not an increase in the model's planning ability.

**E3 — Communication defense.** The real transport blocked 6/6 attack scenarios that a naive dict-passing swarm admitted. The cases covered stale-source replies, equal-credibility conflicts, no-reply behavior, duplicate/replay, content tampering, and byte-budget enforcement. In the no-reply case the planner was never called. This is the clearest evidence for retaining the communication layer as a safety boundary.

**E4 — Memory integrity.** Memory failed closed under direct database tamper, source-replacement cascades, contradiction, and cross-experimental-arm references. A source replacement changed a dependent procedure from recallable to not recallable (recall 1 to 0). The engineering caveat is that retrieval latency is linear in store size because each hit validates the reachable dependency graph: the reported measurements were 0.47 ms at 20 records and 17.7 ms at 1000 records. Scaling to 10^5 or more records remains work, not a demonstrated property.

**E5 — Partial knowledge and coordination.** With 48 fresh disjoint tasks and genuinely partial views, no coordination solved 0/48. A privileged central solver solved 48/48 with 0 messages, but it assumes free information flow. Naive gossip solved 48/48 with 576 messages and 74 KB. Hive consultation solved 48/48 with 288 messages, half the gossip message count, but used 226 KB because the C0 envelope was approximately three times the raw view. This establishes a message-count benefit for targeted consultation, not a byte or end-to-end throughput benefit.

**E6 — Replay agreement.** On the packet's 480 rows, verifier replay agreed with legacy replay 288/288, or 100%, with zero actual-state violations and zero errors. The transport cost per successful recovery was constant at two events and 1920 bytes in the reported run. This supports compatibility of the evaluator boundary; it does not show that the new machinery beats a fully informed solver.

### 4.3 Main result: E7v6 binary coordination-isolated foraging

E7v6 is designed to measure coordination rather than state-conditional action execution. It uses a 10x10 grid, three agents, three foods, 20 seeds, and an 80-step limit. The seeds are 101–120, temperature is 0, and food pickup and nest drop happen automatically. The LLM chooses only `FOLLOW` or `SWEEP`; the harness executes movement toward the selected target. An oracle verified 20/20 seeds as solvable under a sweep-only policy.

The baseline agents sweep independently, causing redundant coverage. Hive agents deposit food sightings into the real `HiveMemoryStore` and retrieve known targets, so a discovery can redirect other agents. The primary metric is `sweep_moves`, interpreted as wasted blind-search movement. With hermes-4-405b, hive memory reduced aggregate sweep moves from 2319 to 1941 across the 20 seeds: approximately 16%, with a sign test of p=0.012. This is the main architecture result.

The comparison is intentionally narrower than general swarm intelligence. The harness gives the model a binary decision and supplies the movement execution. It demonstrates reduced redundant search under shared evidence; it does not show that the swarm can independently solve arbitrary spatial control, infer hidden tumor biology, or outperform a privileged fully informed central solver.

### 4.4 E9 replication and capability separation

E9 repeats the binary harness with grok-4-fast on the same 20 seeds and three arms. The aggregate is identical: baseline 2319 sweep moves and hive memory 1941, with 16/20 seeds favoring hive memory and p=0.012. The communication arm recorded 1940 sweep moves, showing no additional throughput value over shared memory. Token totals differ—176,633 for grok-4-fast versus 210,472 for hermes-4-405b in the baseline—so the matching aggregates are genuine runs, not cache reuse. At temperature 0, both models appear to make the same easy FOLLOW/SWEEP decisions in this harness.

The full-spatial E9 matrix gives the necessary negative control. With grok-4-fast, all three arms succeeded on only 1/20 seeds. The model repeatedly attempted PICK while carrying and did not reliably track carrying state; the hive arms consequently showed more sweep moves than baseline (1249 and 1214 versus 867). Deepseek-v4-pro solved the full-spatial task with 3/3 deliveries and 0 errors at a 600-token thinking cap, but required approximately 2 hours per run, making a 60-run matrix impractical. The full-spatial task therefore discriminates model capability more than architecture.

A focused capability probe (E10-model-floor, 2026-09-13) broadened this from 3 to 35 model conditions. One fixed state-conditional action-sequence prompt was sent once to each reachable relay backend at temperature 0, with PASS requiring an exact four-action match. Only 2 of 32 uniquely-configured reachable backends passed (both deepseek-v4-flash variants); gpt-4.1, claude-sonnet-5, gemini-3.1-pro, llama-3.3-70b, and qwen3-coder all failed on action-sequence grounds, and several more were unreachable (UNKNOWN, not scored as failure). Combined with the prior full-spatial evidence (hermes-4-405b and grok-4-fast fail; deepseek-v4-pro passes), the floor appears near-universal among fast non-reasoning models: reliably tracking one's own carrying state across steps is a capability bottleneck, not a prompt-engineering artifact. Cost of the probe: $0.034.

## 5. Honest Negatives

### 5.1 Communication is not a free speedup

When memory is already shared, adding communication did not produce a demonstrated throughput improvement. In E7/E9-binary, hive memory achieved 1941 sweep moves and the communication arm achieved 1940 in the grok replication; the difference is not evidence of a meaningful architecture gain. In E5, targeted consultation halved message count relative to naive gossip, but envelope overhead made the byte total larger than gossip. A central solver with privileged full information still solved the partial-knowledge task with zero messages. Communication earns its place as an admission and safety layer, especially under attack, not as a general-purpose performance multiplier.

### 5.2 Raw spatial competence remains model-bound

The full-spatial task exposed a capability floor in 2 of the 3 tested model conditions: hermes-4-405b in the earlier versions and grok-4-fast in E9 could not reliably execute state-conditional spatial actions; deepseek-v4-pro could, but at approximately 2 hours per run. The binary harness removes this confound for architectural comparison. It does not remove the practical requirement that a deployed swarm model track state and execute its chosen actions. Hive machinery neither rescued nor worsened a policy that could not execute its own decisions.

### 5.3 The mechanism is not raw intelligence

The deterministic suite contains no LLM in the loop, and its drift rates and re-query costs are synthetic. E7/E9 measure a narrow foraging-search proxy under a harness that executes movement. The current evidence supports safety and cost-under-drift, not a broad claim of improved reasoning, accuracy, clinical efficacy, or autonomous tumor eradication. Nothing in these experiments shows that Antelligence solves a task that a fully informed central solver cannot solve.

## 6. Discussion: A MAST-Framed Interpretation

MAST is useful here as a failure-oriented lens rather than as a claim that the machinery eliminates multi-agent failure. The mapping below should be checked against the canonical MAST terminology before publication. [TODO: verify exact MAST failure-class names and citation.]

| MAST-framed failure concern | Hive mechanism | Existing evidence | Boundary |
|---|---|---|---|
| Communication and evidence-integrity failure | LocalEvidenceTransport admission, identity, scope, revision, causality, expiry, replay, and byte checks | E3 blocked 6/6 attack scenarios; E5 targeted consultation halved gossip messages | Does not make communication cheaper in bytes or replace a trusted source |
| Stale or inconsistent shared state | HiveMemoryStore lineage, source replacement, invalidation, contradiction, and arm isolation | E1: 0 unsafe acts with verification; E4: failed closed under tamper, cascade, contradiction, and arm-crossing | Unannounced source change can still yield stale recall; automatic truth detection is not demonstrated |
| Coordination and redundant-work failure | Shared food sightings and target retrieval in the binary harness | E7v6 and E9-binary: 2319 to 1941 sweep moves, p=0.012 | Gain is shown only in the coordination-isolated task family |
| Planning and action-verification failure | Model-free `verify_task` replays actions and owns the outcome | E2: 58/58 classifications; E6: 288/288 replay agreement | Verification diagnoses and blocks; it does not supply missing model capability |
| Execution or capability failure | Explicit harness control separates architecture from action execution | E9 full-spatial: grok-4-fast 1/20 in all arms; deepseek-v4-pro solves but is too slow to matrix | The model floor remains a deployment constraint |

The strongest MAST-framed conclusion is therefore selective. The hive machinery addresses failures caused by stale, untrusted, contradictory, or unbounded shared evidence, and it reduces redundant exploration when the model can participate in a capability-matched binary protocol. It does not address every failure that appears at the agent-policy layer. In particular, no amount of provenance metadata makes a model reliably execute a state transition it cannot represent or track.

This separation also clarifies what “model-independent” means in the headline. The E7/E9-binary aggregates are identical across hermes-4-405b and grok-4-fast under the same task and temperature, supporting architectural rather than model-specific causation within the harness. It does not mean all models will benefit equally on all tasks. Full-spatial E9 demonstrates the opposite: architecture and capability interact, and capability can dominate the measurement.

## 7. Threats to Validity

**Construct validity.** Sweep moves are a proxy for redundant search, not a universal measure of swarm intelligence. Automatic pickup and drop isolate the coordination question but remove part of the end-to-end control problem. The deterministic verifier and transport tests measure mechanism behavior, not open-ended agent behavior.

**Internal validity.** The binary E7v6 harness was designed to remove the earlier PICK/DROP confound, and its solvability was checked by oracle on 20/20 seeds. Nevertheless, the LLM receives harness-constructed prompts and the harness executes the chosen movement. The identical E9 aggregates strengthen replication but do not establish generality beyond the tested seed set and decision protocol. [TODO: verify exact randomization, run-order, and pre-registration details.]

**Statistical validity.** The E7/E9 result uses 20 paired seeds and a sign test of p=0.012. E1 reports McNemar p<=0.006 in the relevant cells, with a documented caveat for one low-drift cell where p=0.175 because discordant pairs were few. These values are not evidence for a broad population effect outside the simulated task families.

**External validity.** The environments are synthetic grids and coldroom-style task variants. No clinical, biological, laboratory, or live-finance suitability has been demonstrated. The tumor-simulation motivation is a target application, not an evaluated medical result. The review snapshot states that the packet is not integrated into the live application.

**Information and implementation validity.** Caches, replies, and several task inputs are seeded by trusted harness code. New arms in the review packet receive a trusted source-change notice that the legacy memory path does not; this tests an added mechanism, not equal-information reasoning ability. The experiments do not show learned memory, actual multi-model negotiation, or automatic detection of every source change.

**Scaling validity.** Memory retrieval is linear in store size in the current implementation, measured at 0.47 ms for 20 records and 17.7 ms for 1000 records. Behavior at 10^5 or more records is unknown. Communication envelope overhead also matters: in E5, the C0 canonical bytes were approximately three times the raw view.

## 8. Future Work

### 8.1 E10: private-knowledge foraging — COMPLETE (2026-09-13)

E10 made information sharing the independent variable: a four-level privacy ladder on the E7v6 binary harness (same grid, seeds 101–120, temperature 0, hermes-4-405b). Arms: `independent` (no shared state), `positions_only` (peer positions visible, discoveries hidden), `strict` (sightings move only through the real LocalEvidenceTransport, positions hidden), `shared_memory` (E7v6 design). Aggregate sweep moves: independent 2319 (exactly reproducing E7v6 baseline), positions_only 2319 (+0, sign test 0/0), strict 2192 (−127, 6/6 discordant seeds favoring strict, p=0.031), shared_memory 1940 (−379, 16/20, p=0.012; −1 from the E7v6 hive anchor of 1941, matching the offline self-test's predicted delta). Coordination value is strictly increasing in shared information, and each increment is carried by the evidence machinery: positional context alone bought nothing (and cost the most tokens, 291,756 vs 210,472), admitted peer-to-peer sightings bought 5.5% through 369 admitted transport events with zero parse errors, and shared memory delivered the full 16.3%. This is the communication layer's first positive coordination result — its value is conditional on privacy, complementing its unconditional safety value from E3. Total spend: $0.97.

### 8.2 E11: swarm-proposed task DAGs — COMPLETE (2026-09-13)

E11 tested whether an accepted plan can be a deterministic function of untrusted proposals. Hermes-4-405B proposed task nodes for the existing E1/E4 `chain`, `fork`, and `impossible` fixtures at temperature 0 on seeds 101–120. Admission was model-free: canonical proposal sorting, acyclicity, source-to-goal reachability, contradiction-cascade handling, resource consistency, and incremental `verify_task` feasibility. Admission ran twice per seed and produced byte-identical accepted DAGs in all three arms; no model call occurred during admission.

The pre-test passed 3/3 parseable DAGs at $0.006066. The matrix cost $0.257950, for $0.264016 including the pre-test. `solo_planner` admitted 49/160 proposed nodes (0.306) and succeeded on 2/20 goals (0.100). `swarm_proposal` admitted 54/479 (0.113) and succeeded on 3/20 (0.150). `swarm_proposal_verified` admitted 55/478 (0.115) and succeeded on 3/20 (0.150). All three arms had zero determinism failures and zero unsafe acts. The swarm arms had approximately 63% redundant proposed nodes and used roughly 2.7× the solo tokens per accepted node; the exact paired sign tests had 19 ties and 1 swarm win in each comparison (p=1.000).

This supports the narrow determinism claim for this harness, not a general planning or safety theorem. The honest model result is negative on proposal efficiency: independent swarm proposals added duplication and did not improve execution success materially over solo planning. The full verifier boundary added no observed success lift in these 20 paired seeds. Four impossible fixture rows are intentionally included, and the small matrix is not evidence of real-world task-planning quality. See `e11-task-dags/REPORT.md` and `e11-task-dags/out/e11_summary.json`.

### 8.3 Engineering and application follow-ups

Future work should address linear retrieval scaling, measure byte and latency costs rather than message counts alone, and compare against ordinary retrieval plus a single solver. A fair model comparison should report model, latency, token usage, failures, and evaluator behavior together. Any move toward patient-aware tumor simulation must add domain-specific validation and expert review rather than treating these swarm benchmarks as clinical evidence. [TODO: verify the intended clinical-safety and domain-validation pathway.]

## 9. Conclusion

The current evidence supports a bounded architectural claim. Shared evidence memory paired with a model-free verifier makes a capability-matched LLM swarm about 16% more search-efficient in the E7v6 binary harness, and the result replicates across hermes-4-405b and grok-4-fast with p=0.012. The broader mechanism suite shows why the architecture can matter: memory plus verification is cheaper than always re-querying under silent drift, unsafe stale-memory actions are blocked, the verifier classifies all tested cases, and bounded transport rejects attacks that naive message passing admits.

The negative results define the boundary. Communication has defensive value but no demonstrated throughput value once memory is shared. Full-spatial control remains model-bound, with a capability floor in 2 of 3 tested model conditions. Antelligence therefore should be presented as evidence and safety infrastructure for swarm experiments—not as a general intelligence multiplier, a clinical system, or a substitute for capable action policies.

## References

[TODO: verify and add primary citations for MAST, DeSci, stigmergic coordination, multi-agent LLM systems, verifiable computation, and any tumor-simulation background used in the final submission.]

## Reproducibility pointers

* Deterministic experiment report: `/Volumes/WD_BLACK/antelligence-experiments-20260911/EXPERIMENTS-REPORT.md`
* E7v6 harness design: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e7-swarmbench-v6/run_pilot.py`
* E9 report: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e9-strongmodel/REPORT.md`
* E10 model-floor probe: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e10-model-floor-v2/REPORT.md`
* Review snapshot and component description: `/Volumes/WD_BLACK/antelligence-review-20260911/review/hive-fit-20260911/README.md`
* The review snapshot reports 167 tests passed, 480 assigned matrix rows replayed, and 24 unreported-drift diagnostic cases. Raw traces and databases remain local to the experiment/review directories.
