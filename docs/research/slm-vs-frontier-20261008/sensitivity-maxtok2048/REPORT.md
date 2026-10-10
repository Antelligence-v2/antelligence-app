# REPORT: small local models vs frontier models on the Antelligence engine

Generated 2026-10-10T03:36:10+00:00 by `scripts/w2_report.py` from `results.csv` and `comparisons.json` (produced by `scripts/w2_analyze.py`). Design: `PREREGISTRATION.md` (committed before the first evaluation call; first evaluation call in the ledger: `2026-10-09T03:15:18.501741+00:00`).

## Headline

- **(a) The swarm made the small model worse** for `evidence_exchange` (-0.239).
- **(b) Small-model swarm vs frontier solo: no reliable difference** for at least one protocol (see table); this is not evidence of equivalence.
- **(c) Cost:** see the accuracy-per-dollar table. Local Qwen has $0 API cost (hardware and electricity not measured); every swarm arm multiplies tokens and wall time.
- Agreement between agents is not correctness: all accuracy below is scored by the world against reference answers, with abstentions, invalid replies, transport errors and missing cells counted as failures.

## Primary comparisons (research_qa, 60 evaluation tasks, both domains pooled)

| Comparison | Pairs | Treatment acc | Baseline acc | Δ (treat−base) | 95% CI (task bootstrap) | Wins/Losses/Ties | Sign-test p | Holm p | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| a1 small swarm(signal_board) vs small single | 0 | — | — | — | — | 0/0/0 | — | — | no reliable difference |
| a2 small swarm(evidence_exchange) vs small single | 180 | 45.0% | 68.9% | -0.239 | -0.322 … -0.161 | 4/47/129 | 2.42e-10 | 0 | treatment worse |
| b1 small swarm(signal_board) vs frontier-strong single | 0 | — | — | — | — | 0/0/0 | — | — | no reliable difference |
| b2 small swarm(evidence_exchange) vs frontier-strong single | 60 | 50.0% | 65.0% | -0.150 | -0.250 … -0.067 | 0/9/51 | 0.00391 | 0.00391 | treatment worse |

## Every research_qa cell (seeds pooled)

Accuracy = correct / requested. Wilson = one-sided 95% lower bound on accuracy. Tokens and cost count every logical call of the arm (cache hits included, as if run alone); latency = summed model time.

| Model | Tier | Domain | Arm | Seeds | Req | Missing | Acc | Wilson LB | Coverage | Answered acc | Abst | Invalid | Error | Prompt tok | Output tok | Model s | Cost | $/correct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5.5 | frontier | finance | evidence_exchange | 3 | 90 | 0 | 80.0% | 72.2% | 82.2% | 97.3% | 4 | 12 | 0 | 651,040 | 186,478 | 1,575 | $0.1583 | $0.0022 |
| claude-haiku-5.5 | frontier | finance | evidence_isolated | 3 | 90 | 0 | 0.0% | 0.0% | 0.0% | — | 68 | 22 | 0 | 541,568 | 160,605 | 1,464 | $0.1345 | — |
| claude-haiku-5.5 | frontier | finance | single | 3 | 90 | 0 | 93.3% | 87.6% | 100.0% | 93.3% | 0 | 0 | 0 | 175,953 | 20,419 | 217 | $0.0278 | $0.0003 |
| claude-haiku-5.5 | frontier | medical | evidence_exchange | 3 | 90 | 0 | 72.2% | 63.9% | 84.4% | 85.5% | 1 | 13 | 0 | 472,912 | 171,953 | 1,567 | $0.1333 | $0.0021 |
| claude-haiku-5.5 | frontier | medical | evidence_isolated | 3 | 90 | 0 | 2.2% | 0.7% | 2.2% | 100.0% | 67 | 21 | 0 | 320,154 | 148,339 | 1,467 | $0.1062 | $0.0531 |
| claude-haiku-5.5 | frontier | medical | single | 3 | 90 | 0 | 87.8% | 81.0% | 97.8% | 89.8% | 0 | 2 | 0 | 72,645 | 20,878 | 230 | $0.0177 | $0.0002 |
| claude-sonnet-5.5 | frontier | finance | evidence_exchange | 1 | 30 | 0 | 30.0% | 18.4% | 33.3% | 90.0% | 1 | 19 | 0 | 216,573 | 35,632 | 534 | $0.7895 | $0.0877 |
| claude-sonnet-5.5 | frontier | finance | evidence_isolated | 1 | 30 | 0 | 3.3% | 0.8% | 3.3% | 100.0% | 4 | 25 | 0 | 179,046 | 32,184 | 510 | $0.6799 | $0.6799 |
| claude-sonnet-5.5 | frontier | finance | single | 1 | 30 | 0 | 33.3% | 21.1% | 36.7% | 90.9% | 0 | 19 | 0 | 58,651 | 4,072 | 70 | $0.1580 | $0.0158 |
| claude-sonnet-5.5 | frontier | medical | evidence_exchange | 1 | 30 | 0 | 76.7% | 62.1% | 80.0% | 95.8% | 0 | 6 | 0 | 156,405 | 21,252 | 457 | $0.5253 | $0.0228 |
| claude-sonnet-5.5 | frontier | medical | evidence_isolated | 1 | 30 | 0 | 0.0% | 0.0% | 3.3% | 0.0% | 12 | 17 | 0 | 105,507 | 20,125 | 445 | $0.4123 | — |
| claude-sonnet-5.5 | frontier | medical | single | 1 | 30 | 0 | 96.7% | 86.4% | 100.0% | 96.7% | 0 | 0 | 0 | 24,215 | 3,146 | 68 | $0.0799 | $0.0028 |
| qwen38-27b-q3k | small | finance | evidence_exchange | 2 | 90 | 30 | 12.2% | 7.6% | 15.6% | 78.6% | 0 | 45 | 1 | 271,187 | 79,088 | 17,197 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | finance | evidence_isolated | 2 | 90 | 30 | 0.0% | 0.0% | 1.1% | 0.0% | 14 | 40 | 5 | 233,128 | 89,014 | 18,328 | $0.0000 | — |
| qwen38-27b-q3k | small | finance | single | 3 | 90 | 28 | 51.1% | 42.5% | 56.7% | 90.2% | 0 | 11 | 0 | 86,102 | 9,500 | 2,260 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | medical | evidence_exchange | 3 | 90 | 0 | 77.8% | 69.8% | 82.2% | 94.6% | 3 | 13 | 0 | 308,304 | 48,051 | 13,149 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | medical | evidence_isolated | 3 | 90 | 0 | 24.4% | 17.8% | 70.0% | 34.9% | 3 | 23 | 1 | 209,863 | 51,284 | 12,763 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | medical | single | 3 | 90 | 0 | 86.7% | 79.7% | 96.7% | 89.7% | 0 | 3 | 0 | 49,332 | 8,374 | 2,274 | $0.0000 | $0.0000 |

## Accuracy per dollar (research_qa, both domains pooled)

| Model | Arm | Accuracy | API cost | Correct per $ | Hypothetical hosted cost (Qwen only, Nous list price) |
|---|---|---|---|---|---|
| claude-haiku-5.5 | evidence_exchange | 76.1% | $0.2916 | 470 | — |
| claude-haiku-5.5 | evidence_isolated | 1.1% | $0.2406 | 8 | — |
| claude-haiku-5.5 | single | 90.6% | $0.0455 | 3,582 | — |
| claude-sonnet-5.5 | evidence_exchange | 53.3% | $1.3148 | 24 | — |
| claude-sonnet-5.5 | evidence_isolated | 1.7% | $1.0922 | 1 | — |
| claude-sonnet-5.5 | single | 65.0% | $0.2379 | 164 | — |
| qwen38-27b-q3k | evidence_exchange | 45.0% | $0.0000 | ∞ ($0 API) | $0.5667 |
| qwen38-27b-q3k | evidence_isolated | 12.2% | $0.0000 | ∞ ($0 API) | $0.6207 |
| qwen38-27b-q3k | single | 68.9% | $0.0000 | ∞ ($0 API) | $0.0809 |

## Secondary comparisons (exploratory, uncorrected)

| Comparison | Domain | Pairs | Treatment | Baseline | Δ | 95% CI | Sign-test p |
|---|---|---|---|---|---|---|---|
| claude-haiku-5.5: communication beyond more calls: signal_board vs independent_vote | both | 0 | — | — | — | — | — |
| claude-haiku-5.5: communication beyond more calls: signal_board vs solo_refine | both | 0 | — | — | — | — | — |
| claude-haiku-5.5: sharing beyond sharding: evidence_exchange vs evidence_isolated | both | 180 | 76.1% | 1.1% | +0.750 | +0.656 … +0.839 | 4.59e-41 |
| claude-haiku-5.5: voting vs single | both | 0 | — | — | — | — | — |
| claude-sonnet-5.5: communication beyond more calls: signal_board vs independent_vote | both | 0 | — | — | — | — | — |
| claude-sonnet-5.5: communication beyond more calls: signal_board vs solo_refine | both | 0 | — | — | — | — | — |
| claude-sonnet-5.5: sharing beyond sharding: evidence_exchange vs evidence_isolated | both | 60 | 53.3% | 1.7% | +0.517 | +0.383 … +0.650 | 9.31e-10 |
| claude-sonnet-5.5: voting vs single | both | 0 | — | — | — | — | — |
| qwen38-27b-q3k: communication beyond more calls: signal_board vs independent_vote | both | 0 | — | — | — | — | — |
| qwen38-27b-q3k: communication beyond more calls: signal_board vs solo_refine | both | 0 | — | — | — | — | — |
| qwen38-27b-q3k: sharing beyond sharding: evidence_exchange vs evidence_isolated | both | 180 | 45.0% | 12.2% | +0.328 | +0.228 … +0.428 | 2.48e-15 |
| qwen38-27b-q3k: voting vs single | both | 0 | — | — | — | — | — |
| a1 small swarm(signal_board) vs small single [medical] | medical | 0 | — | — | — | — | — |
| a1 small swarm(signal_board) vs small single [finance] | finance | 0 | — | — | — | — | — |
| a2 small swarm(evidence_exchange) vs small single [medical] | medical | 90 | 77.8% | 86.7% | -0.089 | -0.189 … +0.000 | 0.0768 |
| a2 small swarm(evidence_exchange) vs small single [finance] | finance | 90 | 12.2% | 51.1% | -0.389 | -0.489 … -0.289 | 5.82e-11 |
| b1 small swarm(signal_board) vs frontier-strong single [medical] | medical | 0 | — | — | — | — | — |
| b1 small swarm(signal_board) vs frontier-strong single [finance] | finance | 0 | — | — | — | — | — |
| b2 small swarm(evidence_exchange) vs frontier-strong single [medical] | medical | 30 | 83.3% | 96.7% | -0.133 | -0.267 … -0.033 | 0.125 |
| b2 small swarm(evidence_exchange) vs frontier-strong single [finance] | finance | 30 | 16.7% | 33.3% | -0.167 | -0.300 … -0.033 | 0.0625 |

## E15 task_dag and E13 foraging (secondary, small samples)

| World | Model | Arm | Fixtures req | Missing | Successes | Success rate | Wilson LB | Failed calls | Prompt tok | Output tok | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|

## Usage (physical calls, from `ledger/goal-2026-10-08-usage.jsonl`, W2 non-smoke rows)

| Billing | Model | Calls | Failed calls | Prompt tok | Output tok | Cost |
|---|---|---|---|---|---|---|
| local | qwen38-27b-q3k | 7,075 | 476 | 5,132,098 | 752,654 | $0.0000 |
| nous-credits | claude-haiku-5.5 | 7,199 | 956 | 7,506,502 | 1,638,486 | $1.5699 |
| nous-credits | claude-sonnet-5.5 | 2,199 | 16 | 2,662,960 | 324,177 | $8.5677 |

## Deviations from the preregistration

1. 88 requested cell(s) were never written (see `Missing` columns); counted as failures per the preregistered denominator rule.
2. Phi4 mini finance (conditional secondary small model) was not run: the local queue did not reach it before the run deadline. Only one small model (Qwen3.8-27B Q3_K) is in the study.
3. Run order of the frontier queue differs from the preregistration's listing order (Sonnet `single` seeds first, then Haiku, then Sonnet swarm arms) so that the spend cap could only cut the least load-bearing cells; the set of planned cells is unchanged.
4. 89 ledger rows from the 2026-10-09 00:41–02:59 UTC smoke runs predate the `split`/`smoke` ledger fields; they are development-split / fixture-120 calls (see PREREGISTRATION ordering note) and are excluded from usage totals here.

## Limitations

- One small model, quantized to Q3_K; one frontier vendor family (Anthropic) via one gateway (Nous).
- PubMedQA/FinQA are public; contamination is unknown for every model. 60 tasks per study; seeds are correlated within a task (CIs resample tasks).
- Output truncation (`finish_reason=length` at 512 tokens for QA, 256 for E13) is counted as an error, as the engine's providers define it; Haiku hit this often. No output limit was changed mid-study.
- E13 truncated to 40 steps and 5 fixtures; E15 has 19 fixtures. Treat both as smoke-scale evidence.
- Local cost is API cost only; electricity, hardware amortization and the operator's time are unmeasured. Wall time for Qwen is on a shared 36 GB Mac with 3 llama.cpp slots.
- A Wilson bound describes this sample; it is not a guarantee of future accuracy. Nothing here is clinical or financial evidence.

## Raw evidence

Hashes of every raw file are in `MANIFEST.sha256` (cells, bundles, raw responses, run log, ledger). Raw responses are request-hash keyed, so every cell can be replayed offline through the engine with `antelligence.providers.Cached(..., offline=True)`.
