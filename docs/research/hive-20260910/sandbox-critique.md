# Sandboxed multi-agent task critique

**Scope.** Source-only review completed 2026-09-10: papers, READMEs, and evaluator/environment/memory code were read remotely; no benchmark was installed, executed, or called through a provider. A benchmark sandbox is not automatically an OS/security sandbox.

## Bottom line

1. **Best direct lead: CooperBench.** It has the cleanest partial-view, independent-workspace, cooperation-versus-solo comparison and an externally checkable artifact check: two patches are merged and both hidden feature test suites must pass.[1][3][5]
2. **Best procedural-generator lead: τ²-bench.** Its telecom generator composes 2,285 tasks from 15 atomic groups, with 114 sampled tasks; task JSON carries initialization/actions/assertion criteria.[19][20][23]
3. **Memory lead with a red evaluator flag: MultiAgentBench/MARBLE.** It exposes shared/private memory and several environments, but the inspected DB evaluator only stores the predicted root-cause text for later evaluation; its generic completion check compares the last action result to a string ground truth.[11][13][14]

## 1. CooperBench — strongest cooperation seam

**Task and dependency.** The paper reports 652 feature-pair tasks across 12 repositories and four languages, with 199 features; each agent sees only its own feature, while the pair must implement both on one base revision.[1] (paper §2.1; coop.py L50-L70) Features are jointly compatible but deliberately overlap; 77.3% of tasks have conflicting gold solutions.[1] (paper §2.1) This is genuine distributed information and action integration, not merely two agents answering the same prompt.

**Evaluator.** The evaluator filters test files out of submitted patches, creates a fresh backend sandbox, applies each patch on its own branch, merges, resets to the base SHA, and runs both feature test patches.[5] (sandbox.py L85-L138, L495-L562) A pass is `exit_code == 0` and at least one parsed test passed for each feature; the pair result is `both_passed`.[5] (sandbox.py L515-L520, L321-L333) The merge path also records whether patch application failed rather than silently treating a missing patch as success.[5] (sandbox.py L375-L425)

**Isolation versus cooperation.** The paper describes separate Docker-based containers and SQL/Redis message passing with immediate delivery on the next agent step.[1] (paper §3) The implementation names per-task Docker Hub images and creates a detached container, but exposes no claim of hardened security isolation.[6] (docker.py L61-L88)[3] (coop.py L250-L294) Coop mode launches one thread per feature and can namespace Redis by run; solo mode concatenates both feature descriptions, disables messaging/git, and gives one agent both features.[3] (coop.py L96-L157)[4] (solo.py L152-L195)

**Does cooperation matter?** The benchmark tests it rather than assuming it: the published paper reports an abstract average 30% lower success under cooperation, and pooled AUC Solo 0.338 versus Coop 0.200 (retention 0.59); GPT-5 is 0.506 versus 0.325 and Claude is 0.469 versus 0.283.[1] (paper abstract; Appendix C table) The paper reports 68.6% with two agents, 46.5% with three, and 30.0% with four on 46 tasks.[1] (paper §4) A fully informed solo model can solve the same workload, so cooperation is not logically necessary for the code result; the gap measures coordination cost under restricted views and separate workspaces. Cross-task persistent memory is not part of the task contract.

**Local seam and cost.** Reuse the shape, not the repo: canonical typed patch/action artifacts, an isolated deterministic replay, and hidden tests or state predicates. Dataset preparation snapshots `CodeConflict/cooperbench-dataset`; evaluation also needs per-task images, Docker/Modal/GCP, and Redis for coop.[7] (dataset.py L1-L30)[2] The code package says MIT; the paper lists mixed underlying repository licenses (MIT, BSD-3, Apache-2.0, MIT-CMU), so a local derivative needs per-fixture attribution.[2][1] (paper Appendix A table 3) Cloud backends and closed-model results are not free/reproducible under this task's constraints. The paper says repositories were not in SWE-Bench/Multi-SWE-Bench, reducing but not eliminating contamination; now-public feature prompts, patches, and tests remain leakable.[1] (paper §2.3)

## 2. MultiAgentBench/MARBLE — broad coordination, weak verifier

**Task and dependency.** The paper has six scenarios: research, Minecraft, database diagnosis, coding, Werewolf, and bargaining; the task-oriented database scenario uses exactly five agents with distinct root-cause specialties, and the paper describes 100 test cases per task.[10] (paper §3.2) The paper reports gpt-4o-mini TS 84.13 research, 45.00 database, 33.60 Minecraft, and 65.10 coding; Llama-3.1-70B has Minecraft TS 0.21 but CS 75.00.[10] (paper Table 1) These are useful leads, not clean evidence that cooperation caused the result.

**Evaluator reality.** MARBLE's generic `BaseEnvironment.is_task_completed()` compares `state["last_action_result"]` to a configured string ground truth after lowercasing/stripping.[14] (base_env.py L28-L41) The evaluator also uses an LLM for communication/planning scores and for research/bargaining task scores; the paper says Minecraft, Werewolf, DB, and coding are rule-based, but the inspected DB method only stores `root_cause` and `predicted` with a comment that evaluation happens separately.[10] (paper §3.3)[13] (evaluator.py L246-L261) Therefore do not import MARBLE's headline score as an externally checkable critical-task result without replacing its evaluator.

**Memory and information isolation.** `Engine` initializes a memory object, but graph coordination initially assigns the *same full task text* to every agent.[11] (engine.py L160-L190) Each `BaseAgent` independently constructs private `BaseMemory` and `SharedMemory`; the engine's memory object is not passed into that constructor.[12] (base_agent.py L40-L70)[11] (engine.py L136-L175) Shared memory itself is only a thread-safe dictionary with overwrite-by-key semantics.[16] (shared_memory.py L6-L42) Long-term memory stores embeddings and retrieves by cosine similarity, then may call a model to summarize; it is per process and provider-dependent, not a demonstrated cross-task memory protocol.[17] (long_term_memory.py L10-L32, L40-L103)

**Does cooperation matter?** Werewolf's villager side has real private-role dependencies and environment-mediated messages; the paper explicitly says werewolf success needs less explicit teamwork.[10] (paper Appendix A.5) Research and database roles are complementary, but the default graph path gives all agents the overall task and permits solving by tool calls without communicating.[11] (engine.py L187-L213)[12] (base_agent.py L150-L180) Thus cooperation may help, but the published setup does not establish necessity against a strong solo/full-information control. The coding/DB outcomes are also contaminated by LLM-defined scoring or incomplete code paths.

**Local seam and cost.** The useful local seam is a finite-state database/incident simulator with typed queries, explicit hidden views, and a deterministic root-cause predicate; do not copy its LLM judge. The software is MIT.[9] The paper's research corpus is 100 ML/AI papers from ResearchTown and its scenario data mixes adapted and LLM-generated material; the inspected paper does not establish one license for that corpus.[10] (paper §3.2; Appendix A.4) The DB environment starts/stops a local Docker Compose PostgreSQL/monitoring stack with `sudo`, hard-coded local connection material, and provider/Prometheus assumptions; that is an operational dependency, not a per-agent security sandbox.[15] (db_env.py L53-L107, L475-L504)

## 3. τ²-bench — compositional dual control

**Task and dependency.** τ² models an agent and an active user as a Dec-POMDP: distinct tool sets act on agent/user databases and exchange messages, with only one player acting per turn.[19] (paper §3.1) Telecom has 15 atomic subtask groups, 2,285 compositional tasks, and a balanced 114-task sample in the paper.[19] (paper §3.2) The current generator seeds the CLI at 42 by default, uses `random.sample`, and writes full/small/sampled JSON.[20] (create_tasks.py L11-L26, L50-L77) The task schema and orchestrator carry initialization actions, reference actions, and environment assertions.[23] (evaluation.md L7-L23)[25] (orchestrator.py L249-L265)

**Evaluator.** The environment evaluator replays reference actions on a fresh gold environment, hashes agent and user DBs, then checks assertions; the action list is a reference path, not a required path unless `ACTION` is in the reward basis.[22] (evaluator_env.py L47-L147)[23] (evaluation.md L7-L23) The final reward multiplies only the components named by `reward_basis`; `ACTION` is an exact action-match check, while NL assertions are explicitly WIP/LLM-judged.[24] (evaluator.py L25-L62, L200-L245) This is a strong seam for deterministic end-state and safety assertions, provided the hidden evaluator uses only machine predicates.

**Isolation versus cooperation.** Half-duplex/full-duplex orchestration constrains turn/tick flow and termination; solo mode replaces the user with `DummyUser` and requires an autonomous tool-calling agent.[25] (orchestrator.py L319-L362, L434-L451) This is simulated state/tool isolation, not an OS sandbox. The paper's telecom simulator is reported at 16% error with 6% critical errors, and published pass^1 is 34% for gpt-4.1 telecom versus 74% retail and 56% airline; no-user to default drops are 18% for gpt-4.1 and 25% for o4-mini.[19] (paper abstract; §4.2) The paper reports $0.086 agent and $0.059 user-simulator cost per gpt-4.1 task and about $40 for all domains for one trial.[19] (paper §4.1)

**Does cooperation matter?** Dual control requires coordinating with an active user who owns some state-changing actions, but it is intentionally asymmetric: the paper says the target is guiding the user, not a pure symmetric multi-agent task.[19] (paper §2) The built-in no-user control isolates reasoning/tool use; a full-information solo agent can still execute all tools, so the default does not prove a collective advantage. Cross-task persistent memory is absent from the core task contract.

**Local seam and cost.** Telecom's compositional generator is the closest blueprint: public atomic definitions, frozen seed manifests, a private held-out seed set, and a replay verifier. The repository and code are MIT, but model/provider calls, current Python/runtime dependencies, and version drift matter; the README warns that v1.0.1 banking fixes make scores before/after the release incomparable, so pin a release/commit rather than `main`.[18] (README and release note) Public JSON tasks, policies, tools, and reference trajectories create prompt/answer contamination risk. Keep held-out seeds and evaluator predicates private; publish only generator code, hashes, and provenance.

## What Intelligence should borrow

**Artifact/verifier seam.** Emit canonical JSONL events `{episode, actor, action, arguments, pre_state_hash, post_state_hash, evidence_ids, memory_ids}` plus a final-state manifest. A deterministic verifier replays typed transitions from a seed, checks preconditions, target predicates, evidence provenance, and safety invariants, and returns per-invariant pass/fail plus the first violating event. An LLM may propose actions; it must never judge correctness. Any safety violation is a hard safety failure even if the task goal is reached.

**Three small procedural families (novel-to-Intelligence, not claims of global novelty).**

1. **Virtual instrument/SOP interlock (non-clinical scientific safety).** Roles: instrument observer sees readings and calibration status; materials steward sees compatibility, quantities, and waste limits; safety officer sees interlocks and abort rules. The commit action requires a typed plan plus two role signatures. Correctness: required calibration and processing transitions occur exactly once and final batch state equals the seed's target predicate. Safety: no energize while guard open; no incompatible mix; every temperature/pressure sample stays within bounds; no action after abort; no commit without current-version signatures.
2. **Synthetic service-change incident runbook.** Roles: telemetry analyst sees metrics/log slice; security analyst sees exposure and change policy; release operator sees dependency graph and rollback snapshot. Correctness: selected root cause matches the hidden fault label and the replayed action log reaches the target recovered state. Safety: no destructive migration before a verified rollback; no secret-bearing artifact in messages; no change outside the declared service scope; emergency stop is monotonic; production-like commit requires two independent approvals.
3. **Hazardous-inventory chain-of-custody routing.** Roles: inventory clerk sees item identity/quantity; compatibility officer sees handling constraints; dispatcher sees route/capacity/time windows. Correctness: every item is accounted for exactly once, route edges are valid, and delivery/receipt hashes match the target manifest. Safety: incompatible items never share a container/edge; capacity and temperature limits are never exceeded; custody transfer needs the current holder's signature; stale authorization cannot unlock a transfer.

For each family, the generator must prove a distributed dependency before admission: at least two role-private facts affect the valid action set, and at least one transition requires evidence from another role. The same seed is then exposed to a strong solo/full-information control (one agent receives the union of views and gets the sum of team action/token budgets) and to a full-information vote control (the same number of independent planners, deterministic majority/lexicographic tie-break, no shared memory). These controls separate coordination from extra inference samples.

**Memory and analysis controls.** Keep per-episode environment state separate from learned coordination policy and from cross-episode memory. Run `memory-off`, `relevant` (only matching versioned records), `shuffled` (same-size distractor records), and `stale` (superseded-version records) with identical retrieval budgets and logged provenance. A stale record must fail a version precondition rather than merely lower a score. Use all instances in the frozen public seed suite and all held-out evaluator instances; report paired per-task deltas, invariant failures, and confidence intervals. Do not set an arbitrary sample size, win threshold, or green-exit/progress success rule.

## Sources

[1] https://arxiv.org/html/2601.13295v1
[2] https://github.com/cooperbench/CooperBench
[3] https://raw.githubusercontent.com/cooperbench/CooperBench/main/src/cooperbench/runner/coop.py
[4] https://raw.githubusercontent.com/cooperbench/CooperBench/main/src/cooperbench/runner/solo.py
[5] https://raw.githubusercontent.com/cooperbench/CooperBench/main/src/cooperbench/eval/sandbox.py
[6] https://raw.githubusercontent.com/cooperbench/CooperBench/main/src/cooperbench/eval/backends/docker.py
[7] https://raw.githubusercontent.com/cooperbench/CooperBench/main/src/cooperbench/dataset.py
[9] https://github.com/ulab-uiuc/MARBLE
[10] https://arxiv.org/html/2503.01935v1
[11] https://raw.githubusercontent.com/ulab-uiuc/MARBLE/main/marble/engine/engine.py
[12] https://raw.githubusercontent.com/ulab-uiuc/MARBLE/main/marble/agent/base_agent.py
[13] https://raw.githubusercontent.com/ulab-uiuc/MARBLE/main/marble/evaluator/evaluator.py
[14] https://raw.githubusercontent.com/ulab-uiuc/MARBLE/main/marble/environments/base_env.py
[15] https://raw.githubusercontent.com/ulab-uiuc/MARBLE/main/marble/environments/db_env.py
[16] https://raw.githubusercontent.com/ulab-uiuc/MARBLE/main/marble/memory/shared_memory.py
[17] https://raw.githubusercontent.com/ulab-uiuc/MARBLE/main/marble/memory/long_term_memory.py
[18] https://github.com/sierra-research/tau2-bench
[19] https://arxiv.org/html/2506.07982
[20] https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/domains/telecom/tasks/create_tasks.py
[22] https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/evaluator/evaluator_env.py
[23] https://raw.githubusercontent.com/sierra-research/tau2-bench/main/docs/evaluation.md
[24] https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/evaluator/evaluator.py
[25] https://raw.githubusercontent.com/sierra-research/tau2-bench/main/src/tau2/orchestrator/orchestrator.py
