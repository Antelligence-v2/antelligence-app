# From evidence exchange to selective cooperation and shared experience

Research date: 2026-09-10. **Research findings and experiment design, not a newly trained or evaluated swarm.**

## Bottom line

Sakana Fugu is a relevant precedent, but it is not evidence that adding more agents always helps. Its useful contribution is learning **which model should act, which work should stay independent, and which intermediate results should be shared**. Antelligence should test selective, evidence-grounded checking before attempting a large learned coordinator. Cross-task shared experience is a subsequent, separately controlled intervention.

This investigation also produced a runnable, read-only analysis of Antelligence's existing cloud traces. It finds both useful information transfer and a case of harmful convergence. No old scores, model settings, app execution paths, database rows or credit limits were changed.

## 1. What Fugu actually does

Primary source: [Sakana Fugu Technical Report, v2](https://arxiv.org/html/2606.21228v2).

| System | Mechanism reported by Sakana | What that means for us |
|---|---|---|
| Fugu | A language-model backbone with a worker-selection head; adapts a small parameter subset via singular-value fine-tuning. Supervised worker-performance targets initialize the router; evolutionary optimization then targets end-to-end task completion. It dispatches **one worker per input/step**, without TRINITY's role assignment. | Useful coordination can mean selecting or switching workers, not making every worker debate. §§3.1.1–3.1.3. |
| Fugu-Ultra | A trained Conductor writes workflow steps: subtask instruction, worker ID and an access list of prior outputs. GRPO optimizes workflow validity and final correctness. The reported training setup allows workflows up to five steps and a heterogeneous frontier-model pool. | Learnable communication structure, task decomposition and choice of synthesizer—not a fixed all-to-all chat. §§3.2.1, 3.2.3. |
| Ultra memory | Isolates workers' tool trajectories within the current workflow except for explicit access lists; makes prior workflow interactions available across the ongoing multi-turn conversation. | Preserve independent discovery while avoiding repeated discovery of already-observed artifacts. This is not, by itself, demonstrated transferable learning across unrelated future tasks. §3.2.2. |

Sakana calls premature conditioning on earlier agents' work **orchestration collapse** (§3.2.2). It supplies a plausible reason to preserve independent attempts, but a product description is not a causal ablation of that mechanism on our tasks.

Fugu is behavioral composition of separate models, not weight merging (§2). It still uses a trained central orchestrator. Antelligence's local-signal principle therefore argues for borrowing explicit information-access control, not giving an all-knowing Queen the full problem and calling the rest a swarm.

### Reported gains—and their limits

The report's benchmark table includes these author-reported scores:

| Benchmark | Fugu-Ultra | Fugu | Relevant single-model comparator |
|---|---:|---:|---|
| SWE Bench Pro | 73.7 | 59.0 | Opus 4.8: 69.2 |
| Terminal Bench 2.1 | 82.1 | 80.2 | GPT-5.5: 78.2 |
| GPQA Diamond | 95.5 | 95.5 | Gemini 3.1: 94.3 |
| SciCode | 58.7 | 60.1 | Gemini 3.1: 58.9 |
| MRCRv2 | 93.6 | 86.6 | GPT-5.5: 94.8 |

Source: §4.1 benchmark table. These numbers do **not** establish universal superiority, and Ultra does not win every row.

Appendix A is essential: many baselines are provider-reported or copied from external leaderboards rather than recomputed under one matched harness. SWE Bench Pro uses a 1,000-turn maximum, Terminal Bench a 500-turn maximum, and LiveCodeBench Pro describes five retries for baseline timeouts/token exhaustion. Same maximum reasoning effort is not the same aggregate tokens, latency, API spend or training budget. The main benchmark table is not a matched-compute proof of coordination benefit.

The AutoResearch case (§4.3.1, Table 2) does use a shared scaffold, per-experiment H100 budget, 123 experiments and three seeds per system. Mean best validation BPB is 0.9774 ± 0.0019 for Ultra versus 0.9781 ± 0.0011 for the nearest baseline. These are small differences in **best validation** performance over an optimization trajectory; the table alone does not establish significance, independent final-test generalization or an equal inference-dollar comparison.

The [official Fugu page](https://sakana.ai/fugu/) explicitly says selected model identities and routing are proprietary. The [official repository](https://github.com/SakanaAI/fugu/tree/cb5a66d84fcd4ba377eaed440affcea101e69b19) was inspected at that exact commit: it supplies integrations, demonstrations, reports and example artifacts; it is not a released reproduction of the proprietary coordinator. No installer was run, no account was opened, and no Fugu API experiment was performed.

### What the earlier TRINITY and Conductor papers establish

The independent paper reading is complete and [parent-reconciled](research/fugu-20260910/paper-reconciliation.md). The parent checked the following directly against [TRINITY v3](https://arxiv.org/html/2512.04695v3) and [Conductor v5](https://arxiv.org/html/2512.04388v5):

| Study | Learned behavior | Most useful reported comparison |
|---|---|---|
| TRINITY | A small coordinator selects a worker and a Thinker/Worker/Verifier role from the current transcript; evolutionary training adjusts fewer than 20K parameters. | Table 2: 61.46 LiveCodeBench, 70.44 four-task average under the default 4K/minimal setting. The 86.2% headline removes the output constraint (§4.4), so it is a different operating point. |
| Conductor | A 7B model writes subtasks, worker assignments and prior-output visibility; reinforcement learning rewards workflow validity and final correctness. | Table 7: 72.35 average versus 67.60 Gemini 5× context and 64.52 GPT-5 5× self-reflection. These are stronger controls than a one-call baseline, but not proof of equal realized inference cost. |

There are important counterweights. TRINITY's MMLU score of 91.56 (Table 2) does not clearly beat Gemini majority@5 at 91.57 ± 0.70 (Table 7). Conductor's fine-grained access-list ablation does not clearly beat its simpler `[]`/`all` interface (§B.8, Table 9). Thus **learned organization is promising; finer communication control is not automatically better**.

These methods learn coordinator parameters across training tasks. That is different from a persistent store of evidence-backed lessons retrieved by later tasks. Also, their central orchestrators are not proof that Antelligence must adopt a centrally knowledgeable Queen.

The delegated experiment suggestion was **not admitted as a launch specification**: empty message slots do not equalize token costs; fully informed adjudication is a different question from distributed evidence discovery; valid-only accuracy hides differing failure denominators; its sample size and thresholds were not justified. The reconciliation also records a Conductor budget misclassification and inconsistencies in TRINITY's own text/tables. None affects the narrower mechanism-based research direction below.

## 2. Two complementary research directions

### Preserve independence: Debate or Vote

[Choi et al., *Debate or Vote*, v1](https://arxiv.org/html/2508.17536v1) compare initial majority voting with subsequent debate across seven NLP benchmarks. Voting often accounts for most of the gain. Their martingale result concerns a particular homogeneous, Bayesian belief-update model; it is **not** a theorem that all heterogeneous or evidence-acquiring cooperation is useless (see §4 and Appendix H).

Appendix F also warns that answer extraction can create apparent debate gains. That is directly relevant to our own overlong-brief failure. Lesson: retain a strong independent-voting control, distinguish output validity from task correctness, and measure wrong-to-right **and** right-to-wrong changes.

### Retain experience: G-Memory

[Zhang et al., *G-Memory*, v2](https://arxiv.org/html/2506.07398v2) explicitly studies cross-trial memory. It links three levels: reusable insights, prior queries, and detailed collaboration trajectories (§§3–4). Retrieval supplies role-specific guidance rather than dumping a common transcript into every agent.

The paper evaluates AutoGen, DyLAN and MacNet with different memory baselines across five tasks and three LLM backbones (§5). Its component ablation (§5.4, Table 2) reports, for AutoGen on FEVER, 63.27 with interactions alone, 68.77 with insights alone and 71.43 with both. This supports testing both grounded experience and compact lessons, not assuming a transcript archive suffices. The reported figures are not measurements on Antelligence.

Important limits: retrieval and memory-maintenance tokens must be counted; more retrieved material sometimes hurts (§5.4); medical QA is explicitly left for future validation (§6). The impact statement warns that memory can amplify manipulated or incorrect reasoning. The learning benefit therefore needs chronology, memory-off controls and evidence-backed admission—not reinforcement by popularity.

## 3. What the current Antelligence code supports

Inspection base: application commit `98faa513fdfbb024d99e25ff9255541855140820`. Read-only analysis tooling was subsequently committed as `b4c5ce9cc28d6a693a5782b5b7585862ee61156f`.

- `backend/swarm_core.py::_run_collective` (§lines 648–730 at the base) uses three contexts of **one model**, round-robin evidence shards and one fixed exchange round. Workers select citations; the host transports exact passages. There is no learned model selector or learned edge allocation in this path.
- `evidence_sources` omits peer conclusions; `evidence_exchange` includes them. Neither is a targeted request/response protocol.
- Every recipient sees only its own shard plus delivered evidence; this is a useful foundation for explicit access lists. Invalid messages do not propagate.
- `_finish_cell` (lines 981–1031) invalidates a cell when any required message is invalid. `_MAX_SHORT_BRIEF_CHARS = 160` is part of the frozen historical policy. These semantics must not be silently changed to improve old results.
- The research report store is not read back as experience by this kernel. Separate Queen/chain experience code exists in the tumor simulation; its existence does not establish learning in the LLM research path. No chain calls were made in this investigation.

## 4. New diagnostic from the saved cloud experiment

**Post-hoc on already-consumed data, not a fresh efficacy experiment.** Input: run `28b93b4f-5dc1-4ff7-a58c-19d54d507582`, report SHA-256 `53dd046ee42f27c99e996dc4258f94494e24991348415fce4dd2005b64d4447d`.

Only saved, validated payloads are inspected. A group with any invalid member is blocked, not repaired by reparsing raw text. Shared initial replies count once, not once per condition. The benchmark label is used only by this offline diagnostic, never supplied to agents or a router.

| Initial partial-view group, across all 20 questions | Count |
|---|---:|
| Exactly one researcher matches the reference | 7 |
| A majority matches the reference | 2 |
| No validated proposal matches the reference, with all members valid | 2 |
| Classification blocked by invalid messages | 9 |

On the seven valid initial-minority cases, full-finding sharing reaches the reference in seven official valid runs. Source-only does so in six, with one invalid run. Isolation leaves the minority unresolved in six, with one invalid run. This is a descriptive slice selected after observing outcomes, **not** a seven-question held-out success claim. Full-finding sharing already solves these observed cases; a new selector cannot claim additional accuracy headroom on those same solved cases.

A counterexample remains: `pubmedqa:25007420` starts `maybe / maybe / yes` with reference `maybe`. Either sharing mode ends `yes / yes / yes`; isolation preserves `maybe / maybe / yes`. All these cells are valid. This records harmful convergence relative to the benchmark, not proof that a particular model was persuaded by peer authority: source-only also changes the answer, and the full-evidence controls answer `yes` too. A reference/evidence ambiguity remains possible.

For the fully informed independent-voting arm: 16 groups have a correct majority, three have **no** reference-matching proposal, and one is invalid. There is no observed valid minority answer for a better selector to rescue in that arm. This does not rule out a synthesizer combining partial reasoning, obtaining additional evidence, or using genuinely different model families.

### Reproduce

```sh
python3 scripts/analyze_collective_headroom.py \
  /Volumes/WD_BLACK/antelligence-collective-20260908/next-experiment/cloud/study-report.json \
  --expected-sha256 53dd046ee42f27c99e996dc4258f94494e24991348415fce4dd2005b64d4447d \
  --output /absolute/path/to/a/NEW/headroom.json
```

The output must not exist. The script refuses wrong input hashes and overwrites. Tests cover reference-minority versus absent-proposal classification, invalid/null preservation, paired origin identity, exact cell counts and unchanged official outcomes. A separate complete trace audit remains necessary for transport/source validity; this tool does not replace it.

Rscript was unavailable in PATH and the standard Homebrew/framework locations. This bounded counting analysis uses Python's existing standard library instead of introducing a new dependency. No inferential p-values or power claims are manufactured from this exploratory slice.

## 5. Research direction: earn each layer

These are distinct research questions, not one compound intervention:

1. **Reliable exchange.** Introduce a separately versioned machine message for answer and evidence; human-friendly prose must not be the condition that rejects an otherwise correct machine decision. Preserve strict source/answer validation and hard resource limits. Measure actual message and cell validity in a real development run before admitting new held-out cases. Do not alter or rescore the old policy.
2. **Selective checking.** Test whether evidence-grounded, targeted consultation retains correction benefits while reducing harmful convergence or communication cost. Preserve independent initial work; require explicit access lists and evidence-backed changes. Compare directed versus random routing with the same message/selection budget, plus fixed broadcast, isolation, full-evidence solo and independent voting. Controller/retrieval tokens count too. More agent calls are not free compute.
3. **Different expertise.** Cross model identities only in a subsequent or explicitly factorial experiment. Establish measured complementary errors rather than assigning permanent brand-based specialties. A task-adaptive router must use public task/state features, not evaluation labels.
4. **Shared experience—the hive-mind increment.** Store small, attributable lessons about successful and failed collaboration, with supporting runs, scope, expiry and contradictory evidence. Retrieve only relevant experiences. Compare identical workers with memory off, transcript-only memory, structured lessons, and shuffled memory under a token budget. Freeze memory before evaluation; use chronological/source-family separation and prevent evaluation labels or future outcomes from entering it. Online memory updating is a different experiment and needs its own isolation protocol.

The next behavioral experiment should center on **evidence-grounded selective checking**, with output reliability as its admission gate. Report valid-and-reference-matching outcomes over all assigned cases, with separate validity and conditional accuracy; a valid-only denominator must not hide failures. It should ask whether the group can preserve justified uncertainty rather than merely become more unanimous. A prototype can use an inspectable rule-based access policy before expensive coordinator training; that prototype must be labelled hand-designed, not learned Fugu.

No new paid cohort or training run was launched in this research pass. The existing research allowance is not permission to add subscriptions or reset the cumulative credit ledger. Existing evaluation cases remain consumed; sample size, exact protocols, budgets and decision thresholds must be frozen before a new pilot. A small pilot is for feasibility, not a universal swarm ranking.

## Evidence locations and review status

Working evidence: `/Volumes/WD_BLACK/antelligence-collective-20260908/fugu-research-20260910/`.

- `source-manifest.json` and `sources/`: retrieved primary-source text snapshots with hashes.
- `headroom.json`: executed diagnostic, with original report and analyzer hashes.
- `paper-critique.md`: completed independent TRINITY/Conductor reading, retained unmodified in the evidence root. [Parent reconciliation](research/fugu-20260910/paper-reconciliation.md) accepts the core source reading with explicit corrections and rejects the draft pilot as a launch-ready specification.
- `sources/trinity-v3.md`, `sources/conductor-v5.md`: additional version-pinned primary-source snapshots; hashes and parent checks are recorded in [the reconciliation receipt](research/fugu-20260910/paper-reconciliation-receipt.json).
- [Headroom review](research/fugu-20260910/headroom-review.md): independent recomputation PASS, no blocker/high; parent confirmed the exact reviewed analyzer and output hashes. Both research checks are reconciled; neither is approval of a new behavioral experiment.

This report deliberately separates what Sakana reports, what our code actually does, and what remains a hypothesis. A useful swarm is not defined by its agent count; a useful hive is not defined by the size of its transcript archive.
