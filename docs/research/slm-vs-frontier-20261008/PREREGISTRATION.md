# Preregistration: small local models vs frontier models on the Antelligence engine

- **Registered:** 2026-10-09 ~03:20 UTC (2026-10-08 23:20 EDT).
- **Ordering:** this file, `scripts/w2_benchmark.py` and `scripts/w2_analyze.py` are committed before any evaluation-split model call. Every model call logged earlier in `ledger/goal-2026-10-08-usage.jsonl` (89 rows, 00:41–02:59 UTC) was one of three things:
  - a one-call Claude smoke;
  - a Qwen development-split research_qa smoke;
  - a Qwen E15/E13 smoke on fixture 120.

  Fixture 120 is excluded from evaluation below. The first evaluation-split call will appear in the ledger with `"split": "evaluation"`.
- **Supersedes:** the draft in commit `755c4f5`. Its REPORT records that no evaluation call was ever made under it, so replacing it before the first held-out call is legitimate. Git keeps the draft.
- **Immutability:** this file does not change after the first evaluation call. Departures go in the "Deviations" section of `REPORT.md`.

## Question

Does Antelligence's swarm coordination (shared expiring signals, evidence exchange, model-free verifier) let a small local model close the accuracy gap to a frontier model? At what token, latency and dollar cost?

**Agreement between agents is not correctness.** Only world or verifier scoring against reference answers counts.

## Hypotheses (two-sided)

- **H-a:** small-model swarm (`signal_board`, `evidence_exchange`) vs the same small model `single`.
- **H-b:** small-model swarm vs the strong frontier model `single`.
- **H-c:** accuracy per dollar. Descriptive only, no test.

A null result is a valid result and will be stated plainly.

## Models

| Key | Tier | Access | Identity |
|---|---|---|---|
| `qwen38-27b-q3k` | small, local, $0 API | llama.cpp `b9590-d2462f8f7` on 127.0.0.1:8301, alias `qwen38-abliterated` | `Huihui-Qwen3.8-27B-abliterated-Q3_K.gguf`, 13,500,736,800 B, sha256 `a82fe31ff8716377d1dd2f47e1dc1847b96566ddcfa9a3c394a1b6ecf7adc75c`; chat-template sha256 `c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041`; 3 slots × 12,288 ctx, q8_0 KV cache |
| `phi4-mini-finance-f16` | small, local, $0 API. Secondary, run only if time remains after Qwen | llama.cpp on 127.0.0.1:18302, alias `antelligence-phi4-finance` | `phi4-mini-finance-f16.gguf`, sha256 `164c080720aee985193d1f9160b22763d71ade61cefea0dc46c69533569d352e`. Experimental finance fine-tune with unknown training provenance. |
| `claude-sonnet-5.5` | frontier, strong | Nous portal, existing credits | `anthropic/claude-sonnet-5.5`; the served ID must equal the requested ID or the call fails |
| `claude-haiku-5.5` | frontier, cheap | Nous portal, existing credits | `anthropic/claude-haiku-5.5` |

- **Gemma 4 E4B:** not run. No local E4B weights or endpoint exist on this host. The only Gemma found is an MLX `gemma-4-26b-a4b-it-4bit` HF cache, which is neither E4B nor a pinned endpoint.
- **Claude subscription (`claude -p`) and Codex CLI:** not used. The operator approval prompt for subscription `claude -p` calls timed out unanswered. The Nous route returns per-call token usage and dollar cost, which the CLIs do not expose comparably.
- **Weight hashes:** a local file digest does not attest server memory or training data.

## Tasks

1. **research_qa (primary).**
   - Source: `backend/research_fixtures/tasks.json` (file sha256 `01868e7976bf35a190fb92266fb43579aa26c50e989c66a6656aeb8788070004`), `split == "evaluation"`.
   - Selection: the first 30 medical (PubMedQA) and first 30 finance (FinQA) tasks in fixture order. That order is SHA256(source_id), which no outcome could have influenced.
   - Frozen in `eval-task-ids.json`. sha256 of the newline-joined IDs: `ea0c1866247cbf576f74dbd418048f44589f800a3274ada8159c21926a7ae197`.
   - The other 20 evaluation tasks are untouched. Development tasks served only as plumbing smoke; nothing was tuned on them.
2. **task_dag (E15, secondary).**
   - Fixtures 101–119, all three existing arms (`solo_planner`, `swarm_partitioned`, `swarm_partitioned_merged`).
   - Planner: the existing `LLMPlanner` (temperature 0, 2,200 max tokens, one retry after a parse error).
   - Models: Qwen, Haiku, Sonnet.
3. **foraging (E13, secondary, reduced).**
   - Fixtures 101–105 with `max_steps=40`. Arms: `baseline` vs `hive_memory_signals`.
   - Policy: the existing kernel `LLMPolicy` with the world's `LLM_ACTIONS`/`LLM_SIGNAL_KINDS`, temperature 0, 256 max tokens, JSON mode.
   - Models: Qwen and Haiku.

What the model sees is exactly what the engine policies send. For research_qa that is `backend.swarm_core.public_task`. It includes the public `source_url` but never `expected_answer` or `tolerance`. I audited all 420 round-0 evaluation prompts for `single` and `evidence_exchange` on 2026-10-09: none contain either key, and no system prompt contains the gold answer.

## Arms (existing protocols only, `antelligence/worlds/research_qa/world.py`)

| Arm | Role | Agents × rounds | Logical calls per task |
|---|---|---|---|
| `single` | solo | 1 × 1 | 1 |
| `independent_vote` | independent vote, strict majority | 3 × 1 | 3 |
| `signal_board` | Antelligence protocol: claims posted as expiring board signals | 3 × 3 | 9 |
| `evidence_exchange` | Antelligence protocol: sharded evidence, cited passages delivered to peers | 3 × 2 | 6 |
| `evidence_isolated` | matched control for `evidence_exchange` (same shards, no sharing) | 3 × 2 | 6 |
| `solo_refine` | matched control: one agent, same number of calls as `evidence_exchange` | 1 × 6 | 6 |

## Decoding, seeds, caching

- **research_qa decoding:** temperature **0.7**, max_tokens 512, the engine's default `prompt_only` output policy. Local servers use `backend/research_models.OPTIONS`: `top_k=0, top_p=1, min_p=0, repeat_penalty=1`, thinking disabled.
  - Temperature is above 0 on purpose. At 0, three independent voters on the same prompt are copies.
  - The engine derives each agent's request seed from (run seed, agent, tick). Anthropic models ignore `seed`.
- **E15/E13 decoding:** the existing policies' defaults.
- **Seeds:**
  - Qwen and Haiku: research_qa seeds **0, 1, 2**, all six arms.
  - Sonnet: seed **0** for all arms, plus seeds **1, 2** for `single` only, so H-b is paired over three seeds.
  - Phi4, if run: seed 0, all arms.
- **One harness invocation per (model, world, seed).** An invocation that never started is not part of the design. A started invocation that does not finish leaves its unwritten cells as **missing**, which count as failures.
- **Response cache:** within one model, identical request hashes are served from the append-only raw cache (`raw/*.jsonl`).
  - Example: round 0 of `independent_vote` and `signal_board` sends identical requests, a common-initial-state fork.
  - Each cell's tokens, latency and cost count all of its logical calls, as if run alone. The ledger counts physical calls.

## Metrics (per model × world × domain × arm, seeds pooled; also per seed)

- **Accuracy:** correct ÷ requested. Abstained, invalid, error/transport and missing cells all count as failures.
- **Coverage** (answered ÷ requested) and **answered accuracy** (correct ÷ answered).
- **Failure counts:** abstained, invalid (malformed or out-of-contract), error (transport, truncation, provider refusal), failed calls.
- **One-sided 95% Wilson lower bound:** `antelligence.experiments.stats.wilson_interval`, z = 1.6449.
- **Usage:** prompt and output tokens, logical and physical calls, summed model latency, mean cell wall time.
- **Cost:** provider-reported `usage.cost` from Nous.
  - Local API cost is $0. Electricity and hardware are not measured.
  - As a labelled counterfactual only, Qwen tokens are also priced at Nous's hosted `qwen/qwen3.8-27b` list price: $0.0235 per M input, $4.35 per M output.

## Analysis plan (`scripts/w2_analyze.py`, frozen with this file)

1. **Primary comparisons:** research_qa, both domains pooled, Qwen as the small model.
   - a1: `signal_board` vs Qwen `single`
   - a2: `evidence_exchange` vs Qwen `single`
   - b1: `signal_board` vs Sonnet `single`
   - b2: `evidence_exchange` vs Sonnet `single`
2. **Pairing and statistics:**
   - Pairs are matched on (domain, seed, task); a pair needs both arms requested.
   - Effect size: mean paired difference in correctness.
   - CI: 95% percentile bootstrap that resamples tasks as clusters across seeds (10,000 reps, RNG seed 20261008).
   - Test: exact two-sided sign test on discordant pairs (`stats.paired_comparison`).
3. **Multiplicity:** Holm correction over the four primary comparisons.
   - "Swarm better" requires Holm p < 0.05 **and** a CI low above 0.
   - "Swarm worse" is the mirror case.
   - Anything else is reported as **no reliable difference**, which does not imply equivalence.
4. **Secondary, exploratory and uncorrected:**
   - Per-domain versions of a1–b2.
   - For every model: `signal_board` vs `independent_vote` and vs `solo_refine` (communication vs merely more calls); `evidence_exchange` vs `evidence_isolated` (sharing vs sharding alone); `independent_vote` vs `single`.
   - E15/E13: each arm vs the world's baseline arm, per model, with sign tests over fixtures. These are small samples and labelled as such.
5. **H-c:** accuracy, cost per correct answer, and tokens per correct answer, per cell.

## Stop rules

- **Frontier spend:** hard cap of **$12.00** across all W2 Nous calls, enforced in the harness. No new cell starts once it is reached. A provider error reporting exhausted credits stops that provider; I record it and continue with what remains.
- **Local memory:** local server starts go through the shared memory-admission gate. A defer means wait.
- **Time:** model runs stop at **2026-10-10 05:00 EDT**. Missing cells are handled as described under seeds.
- **Integrity:** stop on served-identity mismatch, any secret exposure, or label leakage into prompts.
- **Restarts:** a restarted harness skips already-written cells and logs the restart (`run-log.jsonl`, `resumed: true`). It never silently re-scores.

## Outputs

- `cells/<model>.jsonl`, `bundles/<model>.jsonl` (engine run bundles with trace hash and bundle hash), `raw/<model>-<world>.jsonl` (every response; offline replay possible), `run-log.jsonl`.
- `results.csv`, `results-by-seed.csv`, `comparisons.json`.
- `REPORT.md` (tables, limitations, deviations) and `MANIFEST.sha256`.

## Limitations stated in advance

- PubMedQA and FinQA are public, so contamination is unknown for every model.
- 60 tasks × 3 seeds gives moderate power. Seeds are correlated within a task, so the bootstrap resamples tasks.
- Q3_K quantization lowers Qwen's quality.
- E13 is truncated to 40 steps and E15 has 19 fixtures, so both are small-sample secondary evidence.
- The frontier models run through one gateway (Nous) and one vendor family (Anthropic).
