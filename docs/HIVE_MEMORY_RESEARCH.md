# Antelligence: broad memory, bounded Queen, verifiable collective work

Date: 2026-09-10. **Research synthesis and an executed model-free testbed—not a demonstrated LLM hive mind.** The memory/benchmark source critiques are complete and parent-reconciled; the [corrections and adoption boundaries](research/hive-20260910/review-reconciliation.md) supersede conflicting worker interpretations. This expands [the Fugu investigation](FUGU_RESEARCH.md), not the old calculator roadmap.

## The direction in plain language

Give the colony a durable library, not one enormous shared prompt. Let workers remember different things and consult one another. Let the Queen allocate attention, track unresolved questions and coordinate commitments. Let an evaluator outside the Queen decide whether the resulting work actually succeeded safely.

The core research question is: **Can a fresh team use the colony's accumulated experience to solve unfamiliar tasks more reliably, with less duplicated work, without inheriting old mistakes?**

## 1. What exists—and what does not

Code inspected at `b3a25cc4841204766cf17ada00a043c3d3ac13d4`:

- `backend/swarm_core.py` deliberately owns no persistence. Its collective path uses partial evidence and a fixed exchange round; the research store is an archive, not a memory the agents consult across tasks.
- `backend/simulation.py::QueenAnt` provides per-step movement guidance from current simulation information. Its heuristic can see all food locations; that is not the same information model as the partial-view research workers.
- `backend/nanobot_simulation.py::QueenNanobot` adjusts worker parameters from an in-memory episode history and can adopt a promoted chain strategy only behind its explicit chain-read gate. That does not implement broad semantic/procedural memory for the LLM workbench.
- `scripts/evaluate_queen.py` already provides paired offline **heuristic** Queen/control evaluations on synthetic tumors. Reuse its paired-seed/evidence discipline, not its results as evidence of LLM collaboration.

The user's Queen direction need not erase the local-signal principle in VISION.md: the Queen can see goals, budgets, dependencies and cited summaries while workers retain private evidence. If a fully informed Queen is tested, label it a distinct centralized control rather than calling it decentralized emergence. No existing Queen, API, scheduler or chain behavior was changed in this pass.

## 2. Broad storage, selective attention

| Memory layer | What it retains | How it should be used |
|---|---|---|
| Episode archive | Actual observations, actions, outputs, failures, evaluator receipts | Immutable evidence for replay and audit; not dumped into every prompt |
| Evidence/claim memory | A claim, its source, scope, date/version, contradictions and uncertainty | Retrieve relevant claims; preserve disputed alternatives |
| Procedural memory | A reusable method plus preconditions, invariants and observed failure cases | Suggest a procedure only when its preconditions still hold |
| Capability directory | Which worker/artifact has useful knowledge for which kinds of state | Help the Queen find expertise; do not rank workers by branding or confidence alone |
| Task workspace | Current hypotheses, reservations, dependencies and unresolved questions | Expiring shared working state; never automatically promoted into durable truth |

Broad means many domains and artifact types can be indexed with common provenance. It does not mean universal read access, identical worker knowledge, limitless retrieval or universal truth. Raw documents, tables and code can live in content-addressed files on the SSD with a small local index. A new graph database, paid memory service or on-chain write is not a prerequisite.

### Queen contract worth testing

The Queen may assign subtasks, request supporting evidence, choose communication edges, allocate a fixed budget, and stop or escalate. It cannot create evaluator success, silently overwrite contradictory findings, expand its own permissions, or promote its own untested assertion into authoritative memory. Its output is a proposed coordination decision, not proof.

The most interesting capability is **knowing what the colony does not know**: choosing whether to consult a specialist, test a hypothesis, retrieve a previous failure, or abstain. Test that against a fixed scheduler and a same-budget random scheduler—not only against an isolated weak worker.

## 3. Primary-source findings added in this pass

### Population-level experience reuse: MATM

[Multi-Agent Transactive Memory, v1](https://arxiv.org/html/2606.19911v1) indexes other agents' action-observation trajectories with current-state-conditioned retrieval. Its learned reranker predicts a retrieved chunk's utility, not merely semantic similarity (§§3–4). Producer and consumer roles can differ; coordinated execution or joint agent training is not required.

Table 1 reports consumer-population averages:

| Setting | ALFWorld success | WebArena success |
|---|---:|---:|
| No retrieval | 0.4708 | 0.1818 |
| Dense retrieval | 0.5511 | 0.2045 |
| SVMRank reranking | 0.6431 | 0.2045 |
| LambdaMART reranking | 0.5715 | 0.1818 |

This is genuine evidence worth building on, but not a universal gain. Construction/reranker learning uses training partitions (§4); the WebArena split is custom, and environment/task-type overlap remains possible. The cross-task WebArena analysis uses **47 tasks**, not the full **88-task** test cohort (Appendix L). Its counts and gains must not be combined as if they had the same denominator. The paper measures interaction steps, not complete dollar/latency parity including the retrieval-planning LLM. Appendix O reports an L40S for retrieval and approximately $2,000 total inference expenditure; this is not a proposed Antelligence budget.

A useful hypothesis for Antelligence: learn a small **memory-usefulness selector** before a large end-to-end Queen. A weaker worker's well-matched experience may help a stronger worker. Similarity, model prestige and repeated retrieval are not sufficient evidence of utility.

### Memory can also preserve the wrong lesson

[MemoryGraft, v1](https://arxiv.org/html/2512.16962v1) illustrates the risk of letting retrieved 'successful experiences' become trusted procedures. Its quantitative evaluation uses 110 handcrafted memory seeds, 10 poisoned, and 12 probe queries; **23 of 48 retrieved records** are poisoned (§5). That is a retrieval-exposure metric—not a measured 47.9% rate of task compromise or a demonstrated multi-agent propagation rate. The proposed signature/reranking defenses are proposals, not experimentally established fixes (§6).

For our design, authentic authorship alone cannot make a false lesson correct. Keep the validator and memory-admission service outside the workers' write authority; scope memories by environment version and preserve contradictions. Evaluate harmless stale/conflicting-memory cases in an isolated testbed before any adversarial model test or live integration.

### Completed memory and benchmark readings

| Lead | Finding that changes our design | Limit we retain |
|---|---|---|
| [ReasoningBank v1](https://arxiv.org/html/2509.25140v1#A3.SS1) | On one Shopping ablation: 39.0% with no experience, 49.7% with one, 44.4% with four. Retrieve a small useful set, not the largest available set. | Single-agent memory; self-judged lessons; no complete token/cost parity; four still beats zero here |
| [MIRIX v1](https://arxiv.org/html/2507.07957v1#S4.T2) | Typed stores and type-specific managers are a useful interface. | LOCOMO J-score 85.38 versus Full-Context 87.52; unanswerable questions excluded; no matched single-manager ablation |
| [Voyager v2](https://arxiv.org/html/2305.16291v2#S3.T2) | Store reusable procedures, not just narratives: fresh-world Diamond Pickaxe 3/3 versus 2/3 without the library, in three trials. | GPT-4 skill-admission critic, not an independent deterministic checker; one-domain transfer and censored iteration budgets |
| [CooperBench v1](https://arxiv.org/html/2601.13295v1) | Test whether separately produced artifacts actually fit together, against a fully informed solo control. | Cooperation underperformed; paper merge assistance and current evaluator differ; not a memory benchmark |
| [τ²-bench v1](https://arxiv.org/html/2506.07982v1#S3.SS2) | Generate tasks from composable initialization/solution/assertion units, rather than hand-writing a list of questions. | Agent–user dual control, not a peer swarm; final-state checks need additional trajectory safety checks |
| [MultiAgentBench v1](https://arxiv.org/html/2503.01935v1) / MARBLE code | Broad task/role vocabulary is useful for scenario design. | Current pinned evaluator has deferred DB scoring and a syntax defect; do not transplant it as an evaluation foundation |

**Most useful synthesis:** a colony retains what happened, what the evidence suggests, and which procedure worked as distinct records. A fresh Queen consults that library selectively, but changed rules and contrary evidence can invalidate a previously useful procedure. The Queen is an attention/commitment coordinator, not the authority that declares its own success.

The unedited [memory critique](research/hive-20260910/memory-critique.md) and [sandbox critique](research/hive-20260910/sandbox-critique.md) remain available for provenance. In particular, the worker's Voyager Table 2 count and description of its verifier were corrected. A citation-check pass did not catch either issue. Proposed two-episode/two-signature admission rules and unspecified plan-voting tie breaks were **not adopted**.

## 4. Promising syntheses—novel to this project, not claims of global novelty

| Idea | What is different | A falsifiable test |
|---|---|---|
| **Capability directory for the Queen** | Retrieve who/what has useful evidence, not only documents matching the question | Compare evidence-targeted versus random consultation with identical slot/call budgets; retain fully informed solo/vote controls |
| **Conditional memories** | Lessons have explicit applicability conditions and counterexamples; contradictions can invalidate dependent guidance | Change a relevant rule while keeping the task superficially similar; measure stale reuse, safe completion and unnecessary abstention |
| **Counterfactual consolidation** | A frequently repeated lesson is not promoted merely because it was repeated | From a frozen development state, compare no memory, relevant memory and matched unrelated memory; count verifier outcomes and all consumption |
| **Queen succession** | The colony's competence should outlive one coordinator's chat | Replace the Queen mid-task while retaining typed artifacts; compare structured memory, raw transcript and no-memory restoration; test duplicate/lost actions |
| **Paired-world curriculum** | Surface novelty and structural novelty are separated | Rename objects, then change dependencies, then reverse a rule; report each shift separately rather than one blended 'novel-task' score |

Failure memories matter too. Retain 'why this failed under these conditions' separately from reusable success procedures. Do not make failed attempts executable instructions, and do not let the absence of evidence become a categorical prohibition.

## 5. Candidate critical-task testbeds

All are fictional/offline. None authorizes clinical decisions, live finance, infrastructure control, production repository changes or public deployments.

| Task family | Distributed roles | External correctness and safety checks | Novelty axis |
|---|---|---|---|
| Inert lab transfer | Assay: vial kinds; protocol: compatible zones; logistics: capacities/reservations | Every vial placed in its allowed zone; no collisions, unauthorized action or version mismatch | New identifiers vs changed compatibility rules; later missing/conflicting evidence |
| Scientific reproducibility detective | Data steward: schema/calibration; analyst: hypothesis; reproducer: sealed execution results | Recover a seeded known result and artifact lineage; no train/test contamination, overwritten source data or fabricated measurements | New compositions of unit mismatch, stale calibration and confounding |
| Coupled software repair | Separate workers own interacting modules and public interface contracts | Immutable combined hidden tests plus API compatibility and write-scope checks in a real disposable OS sandbox | New dependency combinations, simultaneous changes and misleading old repair recipes |
| Synthetic incident/resource coordination | Observers see separate subsystem logs; planners hold resource/ordering constraints | Reach a specified terminal state without breaking invariant/resource/permission constraints | One rule change, stale runbooks, delayed observations and Queen replacement |

An independent fully informed solver may solve any of these; that is a necessary control, not an embarrassment. The evidence for a swarm must be a measured reliability/efficiency/availability advantage under a declared information and resource model—not an artificially handicapped solo baseline.

## 6. Executed first testbed: inert coldroom

New experimental module `backend/research_coldroom.py` and runner `scripts/probe_hive_coldroom.py`. These are not imported by the production API and do not replace the old workbench scorer. The evaluator accepts only bounded `reserve`/`place` JSON actions and stops at the first rejected transition. It checks reservation ownership, unit slot capacity, placement compatibility, duplicate placement, revision and action budget. Success is recomputed from state.

A scratch SQLite episode store admits only replayed safe successes. Recall checks payload hash, scope-index consistency, replay success and contradictory rules within a scope, then derives a reusable kind-to-zone rule from placements. **The evaluator/caller owns ground truth and insertion.** This is not cryptographic protection against a malicious DB owner; hashes are not signatures. General semantic memory, expiry, dependency invalidation and access-control isolation are not implemented.

A real new Python process recalled the saved episode. The executed development cases were:

- Current evidence → safe completion.
- Restarted memory on different vial/locker IDs, with the protocol view omitted from the planner → safe completion.
- Old rule used after a rule change, even with the current revision tag → incompatible placement rejected.
- Scoped recall after that change → no memory returned, no actions, **abstention, not task success**.
- Fresh protocol evidence after the change → safe completion.
- Self-claimed success without a valid action → rejected.

These are **handwritten-policy fixtures**, not LLM or emergent-swarm results. Familiar-rule transfer across renamed objects is not generalization to new task structure. A full-information solo join solves this toy too. The demonstration proves that the proposed conditions and failure states can be measured, not that memory or cooperation improves model performance.

Run without additional dependencies or model credentials:

```sh
python3 scripts/probe_hive_coldroom.py --output-dir /absolute/path/to/a/NEW/folder
```

The runner refuses an existing output directory. Evidence from the actual run is in `/Volumes/WD_BLACK/antelligence-collective-20260908/hive-research-20260910/coldroom-probe-1/`. The [recorded browser replay](research/hive-20260910/coldroom-replay.html) steps through those saved state changes; it is not live inference. Focused tests returned **25 passed** (20 testbed checks plus five existing headroom checks). The source critiques are accepted only with parent corrections. [Independent static review](research/hive-20260910/coldroom-review.md) returned **FIT for continued model-free research**, with zero blocker/high findings. Parent rechecked source identity and reran the 25 tests; [acceptance evidence](research/hive-20260910/coldroom-review-acceptance.json) distinguishes those executions from the static review. This does not admit a model experiment.

Original-review limitations: in the first probe the scope-miss lookup was real, but the zero-action abstention object was a **handwritten report fixture**. The [memory-action-gate follow-up](research/hive-20260910/memory-gate-follow-up.md) replaces that fixture with an executed gate in a fresh process. Its replacement [plain-source static review](research/hive-20260910/memory-gate-review-v3.md) is accepted for continued model-free research only; the original review does not certify the successor. Existing-directory refusal still proves no-clobber behavior, not interrupted-run recovery.

A typed-action simulator is not an OS security sandbox. Do not execute arbitrary agent Python/shell in this process. Code-repair/scientific execution needs a separate hardened environment with disposable storage, no credentials, restricted network and an evaluator workers cannot modify.

## 7. What would count as progress toward a hive?

Measure safe completion over **every assigned case**, invalid/unsafe attempted actions, actual state violations, justified vs unnecessary abstention, total model input/output/tool/retrieval costs, duplicated work and end-to-end latency. Keep memory retrieval exposure distinct from downstream behavior.

Separate interventions: coordination first with memory fixed; memory on/off with workers and scheduling fixed; then a small interaction study. Include no memory, raw transcript, relevant structured memory, matched irrelevant/shuffled memory and stale/conflicting-memory stress tests. Freeze admissible training memories before evaluating disjoint source/structural families; an online-updating experiment needs isolated per-arm histories. Do not choose a sample size or victory threshold until the candidate task set, costs, reliability and variance are inspected.

The next research-to-build seam is a **typed, replayable evidence-and-memory envelope** plus a bounded consultation policy. Only after real development-message reliability and independent evaluator review should new model trials start. Existing $5 cumulative credit authority is not reset; no new paid inference was used by this testbed.

## Living learning ledger

[LEARNINGS.md](research/hive-20260910/LEARNINGS.md) links findings, uncertainty, implemented checks and the next discriminating tests. Update this index as work changes; retain original evidence bytes.

## Review checkpoint

Parent source snapshots and hashes: `hive-research-20260910/sources/`, `parent-source-manifest.json`, `delegation-primary-manifest.json` and `code-source-manifest.json` in the evidence root. Both outputs from `deleg_8ea6fa2a` are complete, preserved and reconciled. The original coldroom candidate was frozen at `c0ed98600ed2528e029bfde42b3426d5f0167474`; independent static source/packet review `deleg_4929999d` is complete and accepted only for model-free research. The reviewer used reads/writes, not execution; parent verified current blobs against the frozen commit and accounted for terminal-display trailing-newline normalization. No foreign benchmark was installed or executed and no new model experiment was started.
