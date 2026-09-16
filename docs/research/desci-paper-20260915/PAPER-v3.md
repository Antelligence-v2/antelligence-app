# Antelligence: Shared Evidence Memory and Model-Free Verification for Safer, More Efficient LLM Swarms

**Draft status:** v3 revision — E13 second headline; E15 resolves the E12/E14 partitioned-coverage confound (merged 16/20 vs raw-partitioned 0/20 vs solo 8/20, zero redundancy, $0.0175 total); based only on existing local experiment reports and the review snapshot.  
**Authors:** [TODO: verify]  
**Affiliation:** [TODO: verify]  
**Date:** 2026-09-16

## Abstract

Large language model (LLM) swarms can divide search and exchange partial observations, but shared state also creates stale-memory, contradictory-evidence, and confident-wrong-action failures. Antelligence is a decentralized-science (DeSci) framework for attributed evidence, evidence invalidation, bounded communication, and independent task verification. Its motivating application is patient-aware brain-tumor simulation: robots or agents coordinate through trails in a simulated environment, while evidence provenance and verification make the resulting claims inspectable. This paper reports what the current experiments establish, without treating a simulator result as clinical evidence.

The approved headline is: **Shared evidence memory with a model-free verifier makes capability-matched LLM swarms more search-efficient, with the effect replicated across two task families and three model families, and converts confident-wrong acting on stale memory into verified-safe behavior (0 unsafe acts); the benefit is architectural within the tested protocols, while raw spatial competence is model-bound.** In the capability-matched E7v6 binary harness, hive memory reduced sweep moves from 2319 to 1941 across 20 seeds with hermes-4-405b at temperature 0; a genuine E9-binary run with grok-4-fast reproduced the same aggregate and sign-test result (p=0.012), despite different token totals. E13 is the second headline: on a chain-prioritized foraging family, where sightings carry a temporal delivery order, a cross-model Nous Portal run with z-ai/glm-5.3-flash reduced sweep moves from 3057 to 2655 (13.15%, paired sign test p=0.000656). Two caveats bound it: the run is cross-model, so it evidences generality across model families rather than an exact replication of the anchors, and success was at ceiling (19/20 in every arm), so the family measures efficiency, not capability. In deterministic mechanism tests, memory plus verification was 2.6–6.9x cheaper than always re-querying under silent drift, with 0 unsafe acts and McNemar p<=0.006; the verifier classified 58/58 cases, and the evidence transport blocked 6/6 attacks admitted by a naive swarm. The negative and conditional results matter: E13 does not isolate an independent communication throughput effect, E10's dose-response shows search efficiency rising with memory scope (none, private, shared), and independent swarm proposals add cost without a material success lift. The full-spatial task exposed a model capability floor rather than an architectural gain. The evidence supports a bounded cross-family coordination result, safety, and cost-under-drift—not a general increase in raw model capability or clinical efficacy.

## 1. Introduction

Antelligence studies a narrow systems question with a broad DeSci motivation: can a swarm of language-model agents reuse evidence without turning shared state into an unexamined source of error? The intended long-term setting is a patient-aware tumor simulation in which many simple agents coordinate search, movement, or intervention under constrained information. In that setting, a useful coordination layer must do more than move messages. It must preserve where a claim came from, distinguish a candidate claim from a trusted outcome, invalidate dependent procedures when their evidence changes, and refuse to act when current state cannot be established.

The current work is deliberately smaller than that vision. It evaluates a self-contained evidence-memory packet and two model-in-the-loop foraging harnesses. The packet includes a common evidence contract (C0), evidence memory (F1), task planning and checking (F2), and local evidence communication (F3). The review snapshot describes these components as a development harness, not an integration into the live workbench, tumor engine, API, or UI. The experiments therefore ask whether the mechanisms earn their complexity in controlled task families, not whether Antelligence treats tumors or improves a deployed swarm.

The main architectural result comes from E7v6. Earlier spatial versions were not discriminating because the model had to execute state-conditional PICK and DROP actions. E7v6 removes that confound: picking up food and dropping it at the nest happen automatically, while the LLM chooses only between following a known target and continuing a systematic sweep. The discriminating measure is sweep moves, a proxy for redundant blind search. Under this isolation, shared hive memory reduces sweep moves by approximately 16%.

E9 tests whether that result is merely a property of one model. Its binary harness uses the same seeds and task structure with grok-4-fast. The aggregate is identical to the hermes-4-405b result: baseline 2319 sweep moves, hive memory 1941, with 16/20 seeds favoring hive memory and a sign test of p=0.012. Token totals differ, so the replication is a genuine run rather than cache reuse. This supports a bounded claim: within this harness, the improvement is driven by the memory-mediated coordination architecture rather than by a model-specific quirk.

E13 supplies the second headline. It repeats the coordination-isolated comparison on a second, structurally different task family — chain-prioritized foraging, where sightings carry temporal delivery prerequisites and the step budget is 120 — and reduces sweep moves by 13.15% (p=0.000656) on a third model family (z-ai/glm-5.3-flash via Nous Portal). Two caveats bind it: the run is cross-model, so it evidences generality across model families rather than an exact replication of the anchors, and success was at ceiling (19/20 in all arms), so the family measures efficiency, not capability. The paper makes three narrower contributions:

1. It separates architectural value from model capability by using a binary, coordination-isolated harness.
2. It measures safety mechanisms directly: verification, provenance-aware memory, and transport admission.
3. It records conditional and negative results as first-class results, including E10's dose-response along memory scope (its earlier communication/privacy reading withdrawn), E11's costly redundant swarm proposals, and the persistence of a full-spatial model floor.

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

A focused capability probe (E10-model-floor, 2026-09-13) sent one fixed state-conditional prompt once to each reachable relay backend at temperature 0. It attempted 32 uniquely-configured backends; exactly 2 passed (both deepseek-v4-flash variants), with PASS requiring an exact four-action match. UNKNOWN results, including 401, 404, 410, and timeouts, are infrastructure observations, not model verdicts, and are not counted as failures. Combined with the prior full-spatial evidence (hermes-4-405b and grok-4-fast fail; deepseek-v4-pro passes), the floor appears near-universal among fast non-reasoning models: reliably tracking one's own carrying state across steps is a capability bottleneck, not a prompt-engineering artifact. Cost of the probe: $0.034.

### 4.5 E10 private-knowledge foraging

E10 made information sharing the independent variable in the E7v6 binary harness. The four arms used hermes-4-405b (`nousresearch/hermes-4-405b`) via OpenRouter at temperature 0 on seeds 101–120. Food pickup and nest drop remained automatic; the primary measure was aggregate `sweep_moves`.

| arm | successes | aggregate sweep moves | deliveries | tokens |
|---|---:|---:|---:|---:|
| `independent` | 16/20 | 2319 | 54 | 210472 |
| `positions_only` | 16/20 | 2319 | 54 | 291756 |
| `strict` | 17/20 | 2192 | 55 | 204846 |
| `shared_memory` | 15/20 | 1940 | 53 | 195005 |

Relative to `independent`, `positions_only` had 0 wins, 0 losses, and 20 ties (p=1.000); `strict` had 6 wins, 0 losses, and 14 ties, a delta of −127 (−5.5%), with sign-test p=0.031; `shared_memory` had 16 wins, 4 losses, and 0 ties, a delta of −379 (−16.3%), with p=0.012. `shared_memory`'s 1940 against the E7v6 anchor of 1941 is a −1 delta that the offline self-test predicted in advance.

The ladder's axis must be stated carefully, because it is **memory scope, not privacy**. Inspecting the harness after the run: `positions_only` and `independent` implement no memory mechanism at all, and `positions_only` was indeed exactly +0 against `independent` on all 20 seeds. The `strict` arm gives each agent a **private record of its own sightings**, which it consults when no food is currently visible; the peer-to-peer transport was also exercised, but its admitted-usable-reply counter is **0 on every seed** (transport events, about 18–19 per seed, are send attempts, of which roughly 100 per seed were rejected). The `strict` gain is therefore attributable to single-agent private memory, not to peer coordination, and it does not establish a coordination value for the communication layer. What the dose-response does establish is that value increases with memory scope: no memory (2319), private memory of own sightings (2192, −5.5%), shared memory across agents (1940, −16.3%).

### 4.6 E11 swarm-proposed task DAGs

E11 tested model-proposed task nodes on the existing fixtures, with model-free admission at temperature 0 on seeds 101–120. The accepted DAG bytes are a deterministic function of serialized proposals plus fixture input; no model call occurs during admission.

| arm | proposed nodes | accepted nodes | admission rate | exec successes | tokens per accepted node | unsafe acts | determinism failures |
|---|---:|---:|---:|---:|---:|---:|---:|
| `solo_planner` | 160 | 49 | 0.306 | 2/20 | 361.1 | 0 | 0 |
| `swarm_proposal` | 479 | 54 | 0.113 | 3/20 | 993.2 | 0 | 0 |
| `swarm_proposal_verified` | 478 | 55 | 0.115 | 3/20 | 961.3 | 0 | 0 |

The swarm arms contained 63.3% and approximately 63.4% redundant nodes, respectively. Each paired comparison had 19 ties and 1 swarm win, with p=1.000. The pre-test cost $0.006066, the matrix cost $0.257950, and the total cost $0.264016. The narrow positive result is deterministic admission, not a planning or security theorem. The honest negative is that independent swarm proposals add approximately 2.7x the tokens per accepted node with no material success lift.

### 4.7 Second headline: E13 chain-prioritized foraging (third model family)

E13 is the paper's second headline: it tests whether the binary coordination result survives a task family in which information has temporal structure. It uses the same 10x10 grid, three agents, three foods, 20 seeds, and binary `FOLLOW`/`SWEEP` protocol as E7v6, but deliveries must occur in order 0→1→2; sightings of later foods are temporarily irrelevant, and the step budget is 120. The sweep-only oracle solved all 20 seeds (mean 33.0 steps; maximum 60), so failures are not task impossibility. The run used `z-ai/glm-5.3-flash` through the Nous Portal at temperature 0 with cache version `v14`, making comparisons to the hermes-4-405b and grok-4-fast anchors cross-model.

| arm | successes | aggregate sweep moves | mean steps to success | deliveries | parse errors |
|---|---:|---:|---:|---:|---:|
| `baseline` | 19/20 | 3057 | 58.3 | 59 | 2 |
| `hive_memory` | 19/20 | 2655 | 54.5 | 59 | 2 |
| `hive_memory_comm` | 19/20 | 2590 | 53.7 | 59 | 1 |

Relative to baseline, hive memory reduced sweep moves by 13.15% (3057→2655), with 16 wins,
2 losses, and 2 ties across paired seeds; the one-sided sign-test p-value was 0.000656. The
memory-plus-communication arm reduced sweep moves by 15.28% (3057→2590), with 17 wins,
2 losses, and 1 tie; p=0.000364. Both hive mechanisms operated in their arms (memory hits/deposits
were 2243/458 in `hive_memory` and 2189/442 in `hive_memory_comm`; the comm arm's transport
logged `transport_events=380`), but the comm arm's additional reduction does not identify an
independent communication effect relative to shared memory. All arms failed only on seed 115,
delivering 2/3 foods. The pre-registered bar—at least 5% reduction and p<0.05 for hive
memory—was cleared.

Two caveats bound E13. First, the run is cross-model: it is a third model family measured
against anchors from hermes-4-405b and grok-4-fast, so it evidences generality across model
families rather than an exact replication of the anchor aggregates. Second, success was at
ceiling in all three arms (19/20), so this family measures search efficiency, not capability.
One further admission: the one-step paid pretest did not exercise delivery (all arms delivered
0/3 by construction), so the delivery behavior rests on the full matrix. E13 therefore sustains
the headline's cross-family generality claim — two task families, three model families — with
those caveats stated.

Artifacts: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/e13_summary.json`,
the three per-arm result files, and the pre-registered bar and verdicts in
`/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/DESIGN.md`.

### 4.8 Partitioned DAG proposals: confound (E12/E14) and resolution (E15)

**Confounded in E12/E14; resolved by E15 (below).** E12's partitioned arm and E14's partitioned and merged arms were underprovisioned: three agents proposed against a four-sample fixture, and `my_sample = all_samples[agent_idx % len(all_samples)]` is only safety-correct when the agent count equals the sample count. Sample-3 — the terminal goal in every fixture composition — was never proposed by any agent, so **their 0/20 execution success was structurally guaranteed rather than measured**. The redundancy halves of both experiments stand (partitioning collapsed redundant nodes to 0%); their coverage conclusions do not, and are superseded by the corrected re-run below. Full confound write-up: `/Users/operator/Documents/Jarvis's Vault/mistakes/mistake-2026-09-14-e12-e14-partitioned-underprovisioned.md`.

E14 tested whether a model-free merge layer could recover coverage from partitioned proposals. The merge unioned the partitioned proposals (three per seed at the time of the run), namespaced local node IDs, rewired each reserve to the place nodes of its declared prerequisites, and passed the result through the unchanged deterministic admission gate. This run used `z-ai/glm-5.3-flash` through the Nous Portal, so the E12 anchor comparison is cross-model; the predeclared anchor values were not reproduced exactly.

| arm | proposed nodes | accepted nodes | redundant fraction | exec successes | tokens per accepted node | parse errors | unsafe acts | determinism failures |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `solo_planner` | 136 | 86 | 0.000 | 9/20 | 732.0 | 12 | 0 | 0 |
| `swarm_partitioned` | 120 | 32 | 0.000 | 0/20 | 4183.1 | 25 | 0 | 0 |
| `swarm_partitioned_merged` | 120 | 40 | 0.000 | 0/20 | 2725.3 | 13 | 0 | 0 |

The predeclared verdict fired as **REFUTED**, but the experiment as run does not earn it: with sample-3 absent from every proposal and a merge layer that invents no nodes, the 0/20 outcome was guaranteed by construction. The table's arithmetic is correct (deterministic merge did preserve zero redundancy, and admission was byte-identical across both runs for every seed) — it is simply not evidence about merge layers or partial views. The corrected re-run below supplies that evidence. Artifacts: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e14-merge-repair/out/e14_summary.json`, the three per-arm result files, and the E15 brief `/Users/operator/Documents/Jarvis's Vault/Briefs/2026-09-14-e15-corrected-provisioning-partitioned-dags.md`.

**E15 — corrected-provisioning re-run (the resolution).** E15 re-ran the same three arms on the same fixtures and seeds with one agent per sample and three corrections recorded in `/Volumes/WD_BLACK/antelligence-experiments-20260911/e15-corrected-provisioning/DESIGN.md` before the matrix (`run_e15.py`, harness version `e15-fixed-provisioning-v4`): (i) provisioning — one agent per sample, with startup assertions that the agents' slices cover every sample and a pretest gate requiring goal ownership and a non-zero execution success; (ii) claim serialization — the merge adds deterministic "take turns" edges for resources whose claimants outnumber their capacity (without it, fan-out fixtures lost a subtree to overlapping reservations while linear fixtures passed); (iii) delegated assignment and field contracts — the delegator supplies each agent its globally unique slot in its slice, and both prompts state the `resource`-field contract explicitly. The model-free admission gate is unchanged.

| arm | proposed | accepted | redundant fraction | execution successes | tokens/accepted | cost |
|---|---:|---:|---:|---:|---:|---:|
| `solo_planner` | 160 | 94 | 0.000 | 8/20 | 428.6 | $0.0030 |
| `swarm_partitioned` | 158 | 40 | 0.000 | 0/20 | 3902.2 | $0.0058 |
| `swarm_partitioned_merged` | 158 | 128 | 0.000 | 16/20 | 1380.5 | $0.0064 |

The merged arm assembled all eight nodes and executed to verified success on each of the 16 solvable fixtures; the four impossible fixtures were correctly refused (0 admitted, resource-consistency rejections). The raw union of partial plans remains non-executable (0/20): a union of partial plans is still not a plan. Deterministic reconciliation lifted coverage to 16/20 against solo's 8/20 — a paired exact sign test gives 8 wins, 0 losses, and 12 ties (p=0.0078) — with zero redundant nodes in every arm, byte-identical admission on reruns, and 0 unsafe acts in all arms.

**What E15 claims.** The recovery belongs to the full stack of named reconciliation layers (delegator: samples, slots, field contracts; merge: prerequisite edges, claim scheduling), not to any single mechanism; the merge invents no nodes and no model call occurs during reconciliation. It costs tokens — 3.2x solo per accepted node — so the claim is recovered coverage and executability, not token efficiency. It is a single cross-model run (`z-ai/glm-5.3-flash`) over 20 fixtures, and proposal generation remains stochastic even at temperature 0 (measured at 19/20 seeds in a prior rerun), so per-seed outcomes are samples. Within those bounds this is the program's first positive coordination result in the DAG layer, and it resolves the E12/E14 question: with correct provisioning, coverage is recoverable by deterministic reconciliation at exactly zero redundancy.

Artifacts: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e15-corrected-provisioning/REPORT.md`, exact aggregate `out/e15_summary.json`, per-arm result files in the same directory, harness `run_e15.py`, and design `DESIGN.md`.


## 5. Honest Negatives

### 5.1 Communication has no demonstrated throughput value

Communication has a proven **safety** role (E3 blocked 6/6 attack scenarios a naive swarm admitted), but no **isolated** demonstrated throughput role. It is zero when memory is already shared in E7/E9-binary (1941 versus 1940 sweep moves), and it is also zero when only positions are visible (E10 `positions_only` was exactly +0 against `independent`, on all 20 seeds). E13's communication arm was numerically below shared memory (2590 versus 2655), but that comparison was not preregistered as an isolated communication contrast and does not establish that transport caused the additional reduction.

E10's `strict` arm was previously read as the exception, and that reading was wrong. The arm does move the metric (−127, −5.5%, 6 discordant seeds, p=0.031), but harness inspection shows the peer-to-peer transport admitted **zero usable replies on every seed**, so no information travelled between agents. What `strict` actually adds is a **private record of each agent's own sightings**; the gain is a single-agent memory effect. Two further cautions stand: p=0.031 is the minimum achievable two-sided sign-test p at 6 discordant pairs, so the effect rests on 6 of 20 seeds, and the arm logged roughly 100 transport rejections per seed against about 18–19 send attempts.

The E5 byte-overhead caveat also remains: targeted consultation halved message count relative to naive gossip, but the envelope made the byte total larger than gossip. A privileged central solver with full information still solved the partial-knowledge task with zero messages. Communication therefore earns its place as an admission and safety boundary, not as a performance multiplier, and the claim that it has conditional throughput value under privacy is withdrawn.

### 5.2 Raw spatial competence remains model-bound

The full-spatial task exposed a capability floor in 2 of the 3 tested model conditions: hermes-4-405b in the earlier versions and grok-4-fast in E9 could not reliably execute state-conditional spatial actions; deepseek-v4-pro could, but at approximately 2 hours per run. The binary harness removes this confound for architectural comparison. It does not remove the practical requirement that a deployed swarm model track state and execute its chosen actions. Hive machinery neither rescued nor worsened a policy that could not execute its own decisions.

### 5.3 The mechanism is not raw intelligence

The deterministic suite contains no LLM in the loop, and its drift rates and re-query costs are synthetic. E7/E9 measure a narrow foraging-search proxy under a harness that executes movement. The current evidence supports safety and cost-under-drift, not a broad claim of improved reasoning, accuracy, clinical efficacy, or autonomous tumor eradication. Nothing in these experiments shows that Antelligence solves a task that a fully informed central solver cannot solve.

## 6. Discussion: A MAST-Framed Interpretation

MAST is useful here as a failure-oriented lens rather than as a claim that the machinery eliminates multi-agent failure. The mapping below should be checked against the canonical MAST terminology before publication. [TODO: verify exact MAST failure-class names and citation.]

| MAST-framed failure concern | Hive mechanism | Existing evidence | Boundary |
|---|---|---|---|
| Communication and evidence-integrity failure | LocalEvidenceTransport admission, identity, scope, revision, causality, expiry, replay, and byte checks | E3 blocked 6/6 attack scenarios; E5 targeted consultation halved gossip messages | No demonstrated throughput value: E10-strict's apparent gain came from private self-memory with zero admitted peer replies |
| Stale or inconsistent shared state | HiveMemoryStore lineage, source replacement, invalidation, contradiction, and arm isolation | E1: 0 unsafe acts with verification; E4: failed closed under tamper, cascade, contradiction, and arm-crossing | Unannounced source change can still yield stale recall; automatic truth detection is not demonstrated |
| Coordination and redundant-work failure | Shared food sightings and target retrieval in the binary harness | E7v6, E9-binary, and E13: memory reduced sweep moves across two task families and three model families; E13 3057→2655, p=0.000656 | E13 is cross-model (generality across families, not exact replication) and success was at ceiling (19/20, efficiency-only); bounded to the tested protocols |
| Planning and action-verification failure | Model-free `verify_task` replays actions and owns the outcome | E2: 58/58 classifications; E6: 288/288 replay agreement | Verification diagnoses and blocks; it does not supply missing model capability |
| Execution or capability failure | Explicit harness control separates architecture from action execution | E9 full-spatial: grok-4-fast 1/20 in all arms; deepseek-v4-pro solves but is too slow to matrix | The model floor remains a deployment constraint |

The strongest MAST-framed conclusion is therefore selective. The hive machinery addresses failures caused by stale, untrusted, contradictory, or unbounded shared evidence, and it reduces redundant exploration when the model can participate in a capability-matched binary protocol. It does not address every failure that appears at the agent-policy layer. In particular, no amount of provenance metadata makes a model reliably execute a state transition it cannot represent or track.

This separation also clarifies what “model-independent” means in the headline. The E7/E9-binary aggregates are identical across hermes-4-405b and grok-4-fast under the same task and temperature, supporting architectural rather than model-specific causation within the harness. It does not mean all models will benefit equally on all tasks. Full-spatial E9 demonstrates the opposite: architecture and capability interact, and capability can dominate the measurement.

## 7. Threats to Validity

**Construct validity.** Sweep moves are a proxy for redundant search, not a universal measure of swarm intelligence. Automatic pickup and drop isolate the coordination question but remove part of the end-to-end control problem. The deterministic verifier and transport tests measure mechanism behavior, not open-ended agent behavior.

**Internal validity.** The binary E7v6 harness was designed to remove the earlier PICK/DROP confound, and its solvability was checked by oracle on 20/20 seeds. Nevertheless, the LLM receives harness-constructed prompts and the harness executes the chosen movement. The identical E9 aggregates strengthen replication but do not establish generality beyond the tested seed set and decision protocol. [TODO: verify exact randomization, run-order, and pre-registration details.]

**Statistical validity.** The E7/E9 result uses 20 paired seeds and a sign test of p=0.012; E13 uses 20 paired seeds with p=0.000656 for hive memory versus baseline — a cross-model run (generality across model families, not exact replication) whose success was at ceiling in every arm (19/20), so it measures efficiency, not capability. E10-strict uses 20 paired seeds but only 6 discordant pairs; p=0.031 is the minimum achievable two-sided sign-test p at that discordance count, and harness inspection further shows the arm's peer channel admitted no usable reply, so it measures private self-memory rather than coordination. E1 reports McNemar p<=0.006 in the relevant cells, with a documented caveat for one low-drift cell where p=0.175 because discordant pairs were few. These values are not evidence for a broad population effect outside the simulated task families or tested model/protocol conditions.

**External validity.** The environments are synthetic grids and coldroom-style task variants. No clinical, biological, laboratory, or live-finance suitability has been demonstrated. The tumor-simulation motivation is a target application, not an evaluated medical result. The review snapshot states that the packet is not integrated into the live application.

**Information and implementation validity.** Caches, replies, and several task inputs are seeded by trusted harness code. New arms in the review packet receive a trusted source-change notice that the legacy memory path does not; this tests an added mechanism, not equal-information reasoning ability. The experiments do not show learned memory, actual multi-model negotiation, or automatic detection of every source change.

**Scaling validity.** Memory retrieval is linear in store size in the current implementation, measured at 0.47 ms for 20 records and 17.7 ms for 1000 records. Behavior at 10^5 or more records is unknown. Communication envelope overhead also matters: in E5, the C0 canonical bytes were approximately three times the raw view.

## 8. Future Work

### 8.1 Engineering and application follow-ups

Future work should address linear retrieval scaling, measure byte and latency costs rather than message counts alone, and compare against ordinary retrieval plus a single solver. A fair model comparison should report model, latency, token usage, failures, and evaluator behavior together. Any move toward patient-aware tumor simulation must add domain-specific validation and expert review rather than treating these swarm benchmarks as clinical evidence. [TODO: verify the intended clinical-safety and domain-validation pathway.]

## 9. Conclusion

The current evidence supports a bounded architectural claim. Shared evidence memory paired with a model-free verifier makes a capability-matched LLM swarm about 16% more search-efficient in the E7v6 binary harness, and E13 — the second headline — reduces sweep moves by 13.15% (15.28% with communication) in a chain-prioritized second task family at p=0.000656. The E7/E9 anchors replicate across hermes-4-405b and grok-4-fast, while E13 is on a third model family via a separate cross-model Nous run; together they support bounded cross-family generality across two task families and three model families — with E13's cross-model and ceiling caveats stated — not model-independent universal performance. The broader mechanism suite shows why the architecture can matter: memory plus verification is cheaper than always re-querying under silent drift, unsafe stale-memory actions are blocked, the verifier classifies all tested cases, and bounded transport rejects attacks that naive message passing admits.

The negative results define the boundary. Communication has no **isolated demonstrated throughput value**: its contribution is defensive admission, and E10's dose-response shows search efficiency rising with memory scope rather than with privacy. E13's communication arm was numerically lower than shared memory, but that arm was not an isolated preregistered communication contrast. E11 adds a deterministic admission result but also shows that independent swarm proposals cost approximately 2.7x more tokens per accepted node without a material success lift, and a same-harness rerun measured proposal reproducibility at 19 of 20 seeds even at temperature 0. Full-spatial control remains model-bound, with a capability floor in 2 of 3 tested model conditions. The partitioned-DAG line completes with E15: the earlier confounds (E12/E14 under-provisioned partitioning, three agents against a four-sample fixture) are resolved by a corrected re-run in which the raw union of partial plans still fails (0/20) while the deterministic merge recovers full coverage on every solvable fixture (16/20 overall; paired exact sign test versus solo 8 wins, 0 losses, p=0.0078; zero redundancy) — the program's first positive coordination result in the DAG layer, at a stated token premium (3.2x solo per accepted node). Antelligence therefore should be presented as evidence and safety infrastructure for swarm experiments—not as a general intelligence multiplier, a clinical system, or a substitute for capable action policies.

## References

[TODO: verify and add primary citations for MAST, DeSci, stigmergic coordination, multi-agent LLM systems, verifiable computation, and any tumor-simulation background used in the final submission.]

## Reproducibility pointers

* Deterministic experiment report: `/Volumes/WD_BLACK/antelligence-experiments-20260911/EXPERIMENTS-REPORT.md`
* E7v6 harness design: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e7-swarmbench-v6/run_pilot.py`
* E9 report: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e9-strongmodel/REPORT.md`
* E10 private-knowledge foraging: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e10-private-forage/out/e10_dose_response_summary.json` (aggregate) and the per-arm `results_*.json` in the same `out/` directory
* E11 task DAGs: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e11-task-dags/REPORT.md`, exact aggregate `e11-task-dags/out/e11_summary.json`, harness `e11-task-dags/run_e11.py`
* E10 model-floor probe: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e10-model-floor-v2/REPORT.md`
* E13 chain-prioritized foraging: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/REPORT.md`, exact aggregate `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/e13_summary.json`, and per-arm result files in the same `out/` directory
* E13 pre-registered bar and design: `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/DESIGN.md`
* E12 partitioned DAGs (coverage confounded — superseded by E15; redundancy stands): `/Volumes/WD_BLACK/antelligence-experiments-20260911/e12-partitioned-dags/REPORT.md` and `out/e12_summary.json`
* E14 merge/repair (coverage confounded — superseded by E15; redundancy stands): `/Volumes/WD_BLACK/antelligence-experiments-20260911/e14-merge-repair/REPORT.md` and `out/e14_summary.json`
* E15 corrected-provisioning re-run (resolves E12/E14): `/Volumes/WD_BLACK/antelligence-experiments-20260911/e15-corrected-provisioning/REPORT.md`, exact aggregate `out/e15_summary.json`, harness `run_e15.py`, design `DESIGN.md`
* Provisioning mistake note: `/Users/operator/Documents/Jarvis's Vault/mistakes/mistake-2026-09-14-e12-e14-partitioned-underprovisioned.md`
* Review snapshot and component description: `/Volumes/WD_BLACK/antelligence-review-20260911/review/hive-fit-20260911/README.md`
* The review snapshot reports 167 tests passed, 480 assigned matrix rows replayed, and 24 unreported-drift diagnostic cases. Raw traces and databases remain local to the experiment/review directories.
