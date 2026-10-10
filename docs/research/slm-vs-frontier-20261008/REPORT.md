# REPORT: small local models vs frontier models on the Antelligence engine

## Read this first: plain-language summary, deviations, limits

*Hand-written by the analyst after the run. `scripts/w2_report.py` copies this file verbatim to the top of `REPORT.md`, so regenerating the report does not lose it. Every number below comes from `results.csv`, `comparisons.json`, `sensitivity-maxtok2048/SENSITIVITY.md`, `exploratory-lenient.csv` or `exploratory-lenient-comparisons.json`.*

### The question

Can a small model that runs on a laptop (Qwen3.8-27B, heavily compressed) do as well as a much larger paid model (Claude Sonnet 5.5, plus the cheaper Claude Haiku 5.5) if we let several copies of it work as a team ("swarm") and share notes? We tested this on 60 held-out questions (30 medical yes/no/maybe questions from PubMedQA, 30 finance number questions from FinQA), with 3 repeats per question, plus two small side-tests (planning task dependencies; a foraging game).

### What was run

Six ways of answering each question: one agent alone (`single`), three agents voting (`independent_vote`), three agents posting to a shared board (`signal_board`), three agents each holding a third of the evidence and trading citations (`evidence_exchange`), the same split without any trading (`evidence_isolated`, a control), and one agent revising its own answer (`solo_refine`). Qwen and Haiku ran all arms for 3 repeats. Sonnet ran `single` for 3 repeats and every other arm for 1 repeat only (60 questions each) to stay under the $12 spend cap. A wrong, malformed, abstained, truncated or missing answer all count as a miss.

### Headline under the preregistered (strict) scoring

- Teamwork did **not** help the small model. Three agents sharing evidence (`evidence_exchange`) was clearly worse than one agent alone: 50.6% vs 78.9% (-28 points, significant after multiple-comparison correction). The shared-board swarm (`signal_board`) was statistically indistinguishable from one agent (74.4% vs 78.9%).
- Small-model swarm vs the strong paid model working alone: no reliable difference for `signal_board` (74.4% vs 68.3%, a gap inside the noise), and the small swarm was worse for `evidence_exchange` (50.6% vs 68.3%). "No reliable difference" is not "equal".
- Per model, `single` vs the best multi-agent arm (both domains pooled, strict): Qwen 78.9% vs 76.7% (`independent_vote`); Haiku 88.9% vs 88.3% (`independent_vote`); Sonnet 68.3% vs 65.0% (`independent_vote`, 1 repeat). No swarm beat a single agent for any model.
- Task planning (E15): the raw union of three planners' partial plans scored 0/19 for every model, because the pieces cannot reference each other. This is built into the design (see limitations). After a model-free merge step the same plans succeeded on 16/19 for all three models; the other 3 fixtures are impossible. Alone, one planner got Sonnet 10/19, Haiku 4/19, Qwen 2/19. So the planning result reflects the merge step, not model quality.
- Foraging (E13) is uninformative: Qwen 1/5 and 0/5, Haiku 0/5 and 0/5, mostly because replies were cut off.
- Money: frontier models cost $10.14 in total (limit $12); Qwen ran locally for $0 API cost (electricity and hardware not counted).

### How the exploratory lenient view changes it (post hoc, deviation D3)

The strict parser throws away a whole multi-call answer if any single reply has anything other than a bare JSON object. Re-scoring the same stored replies more forgivingly (last JSON object in the reply; extra fields ignored; the text "null" counts as abstain; see D3) changes the picture mainly for **Sonnet**, which writes its working before the JSON on finance questions:

| Model | single strict | single lenient | best multi-agent arm strict | best multi-agent arm lenient |
|---|---|---|---|---|
| Qwen3.8-27B | 78.9% | 78.9% | independent_vote 76.7% | independent_vote 76.7% |
| Haiku 5.5 | 88.9% | 91.1% | independent_vote 88.3% | independent_vote 90.0% |
| Sonnet 5.5 (1 repeat, n=60 per arm) | 68.3% | 93.3% | independent_vote 65.0% | independent_vote and signal_board 91.7% |

- Sonnet `single` on finance: 40.0% strict -> 86.7% lenient. Its "weak" strict score was a formatting habit, not a lack of ability. Qwen's scores are unchanged by lenient parsing (its failures are other things: truncation, wrong shape, citing too many passages).
- Because of that, the strict comparison "small swarm vs Sonnet alone: no reliable difference" (b1) does **not** survive: under lenient scoring Sonnet alone is 91.7% vs 75.0% for the Qwen `signal_board` swarm (sign test, 3 wins vs 33 losses, p=2e-7, exploratory, uncorrected). `evidence_exchange` is worse still (50.6% vs 91.7%). The a-comparisons (small swarm vs small single) are essentially unchanged: `signal_board` 75.0% vs 78.9% (p=0.12), `evidence_exchange` 50.6% vs 78.9%.
- The `evidence_isolated` control: strict majority scores ~0 for the frontier models (an agent that lacks the evidence rightly abstains, and a majority is impossible). Scored by plurality of the non-null answers, Haiku reaches 50.0%, Sonnet 58.3% and Qwen 17.8%, versus 63.9% / 43.3% / 50.6% for the real `evidence_exchange` arm under strict scoring (lenient exchange: Haiku 63.9%, Sonnet 71.7%, Qwen 50.6%). The control is a floor, not a matched baseline (see limitations).
- Dropping the two scale-ambiguous FinQA items (JPM/2008/page_117.pdf-2, AWK/2012/page_117.pdf-1; gold in different units than models answer) raises every accuracy by about 1-3 points and does not change any ordering. Both versions are in `exploratory-lenient.csv` (`scale_items` column).
- Lenient scoring is a post hoc view and is **not** confirmatory. The preregistered strict analysis stays the primary result.

### Sensitivity to the output cap (deviation D2)

Raising the per-reply cap from 512 to 2048 tokens (arms single, evidence_exchange, evidence_isolated; table in `sensitivity-maxtok2048/SENSITIVITY.md`) removes essentially all truncation but changes accuracy little, with one exception:

- Haiku finance `evidence_exchange`: 54.4% -> 80.0% (26 truncated cells -> 0). That arm was mostly a victim of the 512 cap.
- Haiku medical exchange 73.3% -> 72.2%; Haiku single +1 to +2 points; Qwen (seeds 0-1) every arm within 2 points either way; Sonnet moves are within noise at n=30 (exchange +7 and +13 points, single finance -7).
- Truncated cells drop to ~0 for Haiku and Sonnet and from 34 to 7 for Qwen (repeats 0-1), but "invalid" cells do not drop (Qwen finance exchange invalid 31 -> 45): replies that used to be cut off now finish with a malformed shape. Truncation was not the main thing holding the swarm arms back, except for Haiku finance exchange.
- The Qwen swarm still loses to Qwen alone at 2048: finance `evidence_exchange` 18.3% vs `single` 75.0%.

### Deviations from the preregistration

- **D1. Qwen task_dag cells killed by a process reap.** At 2026-10-09 18:06Z a Hermes process reap killed the local llama-server mid-run, so 42 Qwen `task_dag` cells ended with transport errors (connection refused / server disconnected). They were moved unaltered to `excluded/qwen38-27b-q3k-crash-20261009.jsonl` and never scored; all 42 were re-run and finished cleanly (42/42). Operator-approved. The re-run uses the same fixtures, arms and seeds.
- **D2. max_tokens 2048 sensitivity.** Operator-approved extra run for research_qa arms single / evidence_exchange / evidence_isolated, written to `sensitivity-maxtok2048/` with the preregistered run untouched. Haiku (3 repeats) and Sonnet (repeat 0) completed. Qwen was **stopped by the operator at 452 of 540 cells** (repeats 0 and 1 complete, repeat 2 partial). The automatic `sensitivity-maxtok2048/results.csv` and `REPORT.md` count Qwen's 88 unwritten repeat-2 cells as failures; they are wrong for Qwen. `SENSITIVITY.md` (script `scripts/w2_sensitivity_table.py`) compares only completed (model, repeat) pairs, with the 512 side restricted to the same repeats.
- **D3. Exploratory lenient re-score.** Post hoc, offline, no model calls, `scripts/w2_rescore_lenient.py`. It replays every stored response through the real engine with the lenient parser. Where a lenient parse changes a later round's prompt (so that prompt was never cached), the model's stored reply for the same agent and round is reused (counted in `fallback_cells`); this isolates the parsing effect but is an approximation. Cells with a truncated or never-stored call stay failures. The replay with the strict parser reproduces the stored cell status for 480/480 Sonnet, 1067/1080 Haiku and 1072/1080 Qwen cells; the rest are cells whose failed physical call was never cached.

### Limitations, plainly

- **Strict JSON scoring voids whole cells on one format slip.** A multi-call cell is "invalid" if any one of its 3-9 calls is malformed (`world.py:192-193`), so a small per-reply slip rate is magnified by the number of calls in the arm.
- **Sonnet writes prose before the JSON on finance** (strict 0.40 vs lenient ~0.87 for single). The strict Sonnet-vs-others comparison therefore measures instruction-following on output format as much as skill.
- **The 512-token cap truncated mostly the evidence arms** (Haiku error cells: exchange 41, isolated 28, solo_refine 22, signal_board 11, single 5), and truncated replies are not saved in `raw/`.
- **The `evidence_isolated` control is near zero by design**: it needs a strict majority of 3 agents, but each agent sees about a third of the evidence and is told to abstain if unsure, so a correct team still scores zero. A hidden rule (at most 3 cited passages, `MAX_CITED`) is enforced by the scorer but is not stated in the prompt. Treat it as a floor, not a matched control.
- **task_dag `swarm_partitioned` is 0 by construction**: the raw union of per-agent sub-plans fails admission because cross-agent prerequisites cannot be expressed. It is a control, not evidence that a swarm cannot plan. The merged arm differs only by a model-free merge step.
- **Impossible fixtures 105, 110, 115 are scored as failures** although refusing is the verifier-correct outcome, capping every task_dag arm at 16/19.
- **Foraging is uninformative**: 256-token cap truncations (Haiku idle for most steps), Qwen emitting float coordinates that the validator rejects. No re-run was done.
- **Sonnet's non-single arms have repeat 0 only (n=60)**, versus n=180 for Haiku and Qwen, so intervals and paired tests are not comparable across models for those arms.
- **Cost-per-correct is understated** for Haiku and Qwen: truncated responses (and their tokens) are not stored in `raw/`.
- **Frontier models were billed through Nous credits.** Total frontier spend from the operator-local usage ledger (non-smoke, Nous-billed rows; aggregated in `usage-summary.json`): **$10.1376** (Sonnet $8.5677 + Haiku $1.5699; cap $12), of which the D2 sensitivity run is roughly $3.2 by cell accounting.
- One small model, quantized to Q3_K; PubMedQA/FinQA are public, so contamination is unknown; 60 tasks. Nothing here is clinical or financial evidence.

---

# Preregistered results (auto-generated)

Generated 2026-10-10T17:20:59+00:00 by `scripts/w2_report.py` from `results.csv` and `comparisons.json` (produced by `scripts/w2_analyze.py`). Design: `PREREGISTRATION.md` (committed before the first evaluation call; first evaluation call in the usage ledger: `2026-10-09T03:15:18.501741+00:00`).

## Headline

- **(a) The swarm made the small model worse** for `evidence_exchange` (-0.283).
- **(b) Small-model swarm vs frontier solo: no reliable difference** for at least one protocol (see table); this is not evidence of equivalence.
- **(c) Cost:** see the accuracy-per-dollar table. Local Qwen has $0 API cost (hardware and electricity not measured); every swarm arm multiplies tokens and wall time.
- Agreement between agents is not correctness: all accuracy below is scored by the world against reference answers, with abstentions, invalid replies, transport errors and missing cells counted as failures.

## Primary comparisons (research_qa, 60 evaluation tasks, both domains pooled)

| Comparison | Pairs | Treatment acc | Baseline acc | Δ (treat−base) | 95% CI (task bootstrap) | Wins/Losses/Ties | Sign-test p | Holm p | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| a1 small swarm(signal_board) vs small single | 180 | 74.4% | 78.9% | -0.044 | -0.089 … -0.006 | 4/12/164 | 0.0768 | 0.154 | no reliable difference |
| a2 small swarm(evidence_exchange) vs small single | 180 | 50.6% | 78.9% | -0.283 | -0.400 … -0.167 | 8/59/113 | 1.02e-10 | 0 | treatment worse |
| b1 small swarm(signal_board) vs frontier-strong single | 180 | 74.4% | 68.3% | +0.061 | -0.067 … +0.194 | 34/23/123 | 0.185 | 0.185 | no reliable difference |
| b2 small swarm(evidence_exchange) vs frontier-strong single | 180 | 50.6% | 68.3% | -0.178 | -0.272 … -0.089 | 4/36/140 | 1.86e-07 | 1e-06 | treatment worse |

## Every research_qa cell (seeds pooled)

Accuracy = correct / requested. Wilson = one-sided 95% lower bound on accuracy. Tokens and cost count every logical call of the arm (cache hits included, as if run alone); latency = summed model time.

| Model | Tier | Domain | Arm | Seeds | Req | Missing | Acc | Wilson LB | Coverage | Answered acc | Abst | Invalid | Error | Prompt tok | Output tok | Model s | Cost | $/correct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5.5 | frontier | finance | evidence_exchange | 3 | 90 | 0 | 54.4% | 45.8% | 55.6% | 98.0% | 0 | 14 | 26 | 577,557 | 147,242 | 1,342 | $0.1314 | $0.0027 |
| claude-haiku-5.5 | frontier | finance | evidence_isolated | 3 | 90 | 0 | 0.0% | 0.0% | 0.0% | — | 54 | 16 | 20 | 512,395 | 137,437 | 1,349 | $0.1200 | — |
| claude-haiku-5.5 | frontier | finance | independent_vote | 3 | 90 | 0 | 92.2% | 86.2% | 98.9% | 93.3% | 0 | 1 | 0 | 527,859 | 60,816 | 618 | $0.0832 | $0.0010 |
| claude-haiku-5.5 | frontier | finance | signal_board | 3 | 90 | 0 | 86.7% | 79.7% | 93.3% | 92.9% | 0 | 2 | 4 | 1,791,205 | 160,603 | 1,768 | $0.2594 | $0.0033 |
| claude-haiku-5.5 | frontier | finance | single | 3 | 90 | 0 | 91.1% | 84.9% | 97.8% | 93.2% | 0 | 0 | 2 | 171,583 | 19,179 | 197 | $0.0267 | $0.0003 |
| claude-haiku-5.5 | frontier | finance | solo_refine | 3 | 90 | 0 | 83.3% | 75.9% | 88.9% | 93.8% | 0 | 4 | 6 | 1,100,723 | 122,973 | 1,235 | $0.1716 | $0.0023 |
| claude-haiku-5.5 | frontier | medical | evidence_exchange | 3 | 90 | 0 | 73.3% | 65.1% | 77.8% | 94.3% | 0 | 5 | 15 | 435,700 | 151,248 | 1,401 | $0.1192 | $0.0018 |
| claude-haiku-5.5 | frontier | medical | evidence_isolated | 3 | 90 | 0 | 1.1% | 0.2% | 1.1% | 100.0% | 62 | 19 | 8 | 313,149 | 142,060 | 1,380 | $0.1023 | $0.1023 |
| claude-haiku-5.5 | frontier | medical | independent_vote | 3 | 90 | 0 | 84.4% | 77.2% | 92.2% | 91.6% | 0 | 4 | 3 | 215,541 | 60,156 | 644 | $0.0516 | $0.0007 |
| claude-haiku-5.5 | frontier | medical | signal_board | 3 | 90 | 0 | 77.8% | 69.8% | 85.6% | 90.9% | 0 | 6 | 7 | 862,033 | 157,257 | 1,829 | $0.1648 | $0.0024 |
| claude-haiku-5.5 | frontier | medical | single | 3 | 90 | 0 | 86.7% | 79.7% | 93.3% | 92.9% | 0 | 3 | 3 | 70,324 | 18,851 | 204 | $0.0165 | $0.0002 |
| claude-haiku-5.5 | frontier | medical | solo_refine | 3 | 90 | 0 | 71.1% | 62.7% | 77.8% | 91.4% | 0 | 4 | 16 | 474,066 | 136,178 | 1,269 | $0.1155 | $0.0018 |
| claude-sonnet-5.5 | frontier | finance | evidence_exchange | 1 | 30 | 0 | 23.3% | 13.2% | 26.7% | 87.5% | 0 | 20 | 2 | 207,778 | 29,419 | 468 | $0.7097 | $0.1014 |
| claude-sonnet-5.5 | frontier | finance | evidence_isolated | 1 | 30 | 0 | 0.0% | 0.0% | 0.0% | — | 5 | 24 | 1 | 170,120 | 26,179 | 442 | $0.6020 | — |
| claude-sonnet-5.5 | frontier | finance | independent_vote | 1 | 30 | 0 | 33.3% | 21.1% | 36.7% | 90.9% | 0 | 19 | 0 | 175,953 | 12,395 | 216 | $0.4759 | $0.0476 |
| claude-sonnet-5.5 | frontier | finance | signal_board | 1 | 30 | 0 | 33.3% | 21.1% | 36.7% | 90.9% | 0 | 19 | 0 | 561,882 | 35,318 | 628 | $1.4769 | $0.1477 |
| claude-sonnet-5.5 | frontier | finance | single | 3 | 90 | 0 | 40.0% | 31.9% | 43.3% | 92.3% | 0 | 51 | 0 | 175,953 | 12,021 | 228 | $0.4721 | $0.0131 |
| claude-sonnet-5.5 | frontier | finance | solo_refine | 1 | 30 | 0 | 36.7% | 23.9% | 40.0% | 91.7% | 0 | 18 | 0 | 363,036 | 25,760 | 437 | $0.9837 | $0.0894 |
| claude-sonnet-5.5 | frontier | medical | evidence_exchange | 1 | 30 | 0 | 63.3% | 48.3% | 66.7% | 95.0% | 0 | 10 | 0 | 156,307 | 21,377 | 449 | $0.5264 | $0.0277 |
| claude-sonnet-5.5 | frontier | medical | evidence_isolated | 1 | 30 | 0 | 0.0% | 0.0% | 0.0% | — | 16 | 14 | 0 | 105,485 | 20,282 | 433 | $0.4138 | — |
| claude-sonnet-5.5 | frontier | medical | independent_vote | 1 | 30 | 0 | 96.7% | 86.4% | 100.0% | 96.7% | 0 | 0 | 0 | 72,645 | 9,484 | 210 | $0.2401 | $0.0083 |
| claude-sonnet-5.5 | frontier | medical | signal_board | 1 | 30 | 0 | 86.7% | 73.4% | 90.0% | 96.3% | 0 | 3 | 0 | 287,899 | 30,090 | 620 | $0.8767 | $0.0337 |
| claude-sonnet-5.5 | frontier | medical | single | 3 | 90 | 0 | 96.7% | 92.0% | 100.0% | 96.7% | 0 | 0 | 0 | 72,645 | 9,503 | 219 | $0.2403 | $0.0028 |
| claude-sonnet-5.5 | frontier | medical | solo_refine | 1 | 30 | 0 | 70.0% | 55.1% | 73.3% | 95.5% | 0 | 8 | 0 | 165,857 | 21,651 | 422 | $0.5482 | $0.0261 |
| qwen38-27b-q3k | small | finance | evidence_exchange | 3 | 90 | 0 | 21.1% | 14.9% | 25.6% | 82.6% | 0 | 46 | 21 | 361,567 | 56,013 | 16,492 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | finance | evidence_isolated | 3 | 90 | 0 | 0.0% | 0.0% | 1.1% | 0.0% | 21 | 49 | 19 | 309,501 | 53,618 | 16,040 | $0.0000 | — |
| qwen38-27b-q3k | small | finance | independent_vote | 3 | 90 | 0 | 67.8% | 59.3% | 73.3% | 92.4% | 0 | 19 | 5 | 361,994 | 32,487 | 10,535 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | finance | signal_board | 3 | 90 | 0 | 63.3% | 54.7% | 67.8% | 93.4% | 0 | 27 | 2 | 1,264,056 | 91,734 | 32,934 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | finance | single | 3 | 90 | 0 | 71.1% | 62.7% | 83.3% | 85.3% | 0 | 11 | 4 | 119,624 | 10,985 | 3,735 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | finance | solo_refine | 3 | 90 | 0 | 72.2% | 63.9% | 80.0% | 90.3% | 0 | 15 | 3 | 767,390 | 59,079 | 19,881 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | medical | evidence_exchange | 3 | 90 | 0 | 80.0% | 72.2% | 84.4% | 94.7% | 2 | 8 | 4 | 307,182 | 43,034 | 13,529 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | medical | evidence_isolated | 3 | 90 | 0 | 24.4% | 17.8% | 68.9% | 35.5% | 4 | 17 | 7 | 207,783 | 43,821 | 12,815 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | medical | independent_vote | 3 | 90 | 0 | 85.6% | 78.4% | 95.6% | 89.5% | 1 | 2 | 1 | 147,448 | 20,862 | 6,038 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | medical | signal_board | 3 | 90 | 0 | 85.6% | 78.4% | 96.7% | 88.5% | 0 | 2 | 1 | 574,739 | 62,533 | 20,498 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | medical | single | 3 | 90 | 0 | 86.7% | 79.7% | 97.8% | 88.6% | 0 | 1 | 1 | 48,784 | 7,238 | 2,194 | $0.0000 | $0.0000 |
| qwen38-27b-q3k | small | medical | solo_refine | 3 | 90 | 0 | 85.6% | 78.4% | 96.7% | 88.5% | 0 | 2 | 1 | 330,637 | 41,589 | 12,917 | $0.0000 | $0.0000 |

## Accuracy per dollar (research_qa, both domains pooled)

| Model | Arm | Accuracy | API cost | Correct per $ | Hypothetical hosted cost (Qwen only, Nous list price) |
|---|---|---|---|---|---|
| claude-haiku-5.5 | evidence_exchange | 63.9% | $0.2506 | 459 | — |
| claude-haiku-5.5 | evidence_isolated | 0.6% | $0.2223 | 4 | — |
| claude-haiku-5.5 | independent_vote | 88.3% | $0.1348 | 1,179 | — |
| claude-haiku-5.5 | signal_board | 82.2% | $0.4243 | 349 | — |
| claude-haiku-5.5 | single | 88.9% | $0.0432 | 3,703 | — |
| claude-haiku-5.5 | solo_refine | 77.2% | $0.2871 | 484 | — |
| claude-sonnet-5.5 | evidence_exchange | 43.3% | $1.2361 | 21 | — |
| claude-sonnet-5.5 | evidence_isolated | 0.0% | $1.0158 | 0 | — |
| claude-sonnet-5.5 | independent_vote | 65.0% | $0.7160 | 54 | — |
| claude-sonnet-5.5 | signal_board | 60.0% | $2.3536 | 15 | — |
| claude-sonnet-5.5 | single | 68.3% | $0.7124 | 173 | — |
| claude-sonnet-5.5 | solo_refine | 53.3% | $1.5319 | 21 | — |
| qwen38-27b-q3k | evidence_exchange | 50.6% | $0.0000 | ∞ ($0 API) | $0.4466 |
| qwen38-27b-q3k | evidence_isolated | 12.2% | $0.0000 | ∞ ($0 API) | $0.4360 |
| qwen38-27b-q3k | independent_vote | 76.7% | $0.0000 | ∞ ($0 API) | $0.2440 |
| qwen38-27b-q3k | signal_board | 74.4% | $0.0000 | ∞ ($0 API) | $0.7143 |
| qwen38-27b-q3k | single | 78.9% | $0.0000 | ∞ ($0 API) | $0.0832 |
| qwen38-27b-q3k | solo_refine | 78.9% | $0.0000 | ∞ ($0 API) | $0.4637 |

## Secondary comparisons (exploratory, uncorrected)

| Comparison | Domain | Pairs | Treatment | Baseline | Δ | 95% CI | Sign-test p |
|---|---|---|---|---|---|---|---|
| claude-haiku-5.5: communication beyond more calls: signal_board vs independent_vote | both | 180 | 82.2% | 88.3% | -0.061 | -0.117 … -0.017 | 0.000977 |
| claude-haiku-5.5: communication beyond more calls: signal_board vs solo_refine | both | 180 | 82.2% | 77.2% | +0.050 | -0.006 … +0.111 | 0.0636 |
| claude-haiku-5.5: sharing beyond sharding: evidence_exchange vs evidence_isolated | both | 180 | 63.9% | 0.6% | +0.633 | +0.522 … +0.739 | 9.63e-35 |
| claude-haiku-5.5: voting vs single | both | 180 | 88.3% | 88.9% | -0.006 | -0.044 … +0.028 | 1 |
| claude-sonnet-5.5: communication beyond more calls: signal_board vs independent_vote | both | 60 | 60.0% | 65.0% | -0.050 | -0.117 … +0.000 | 0.25 |
| claude-sonnet-5.5: communication beyond more calls: signal_board vs solo_refine | both | 60 | 60.0% | 53.3% | +0.067 | -0.017 … +0.167 | 0.289 |
| claude-sonnet-5.5: sharing beyond sharding: evidence_exchange vs evidence_isolated | both | 60 | 43.3% | 0.0% | +0.433 | +0.317 … +0.550 | 2.98e-08 |
| claude-sonnet-5.5: voting vs single | both | 60 | 65.0% | 68.3% | -0.033 | -0.083 … +0.000 | 0.5 |
| qwen38-27b-q3k: communication beyond more calls: signal_board vs independent_vote | both | 180 | 74.4% | 76.7% | -0.022 | -0.072 … +0.017 | 0.344 |
| qwen38-27b-q3k: communication beyond more calls: signal_board vs solo_refine | both | 180 | 74.4% | 78.9% | -0.044 | -0.083 … -0.006 | 0.0386 |
| qwen38-27b-q3k: sharing beyond sharding: evidence_exchange vs evidence_isolated | both | 180 | 50.6% | 12.2% | +0.383 | +0.272 … +0.494 | 3.73e-18 |
| qwen38-27b-q3k: voting vs single | both | 180 | 76.7% | 78.9% | -0.022 | -0.056 … +0.006 | 0.388 |
| a1 small swarm(signal_board) vs small single [medical] | medical | 90 | 85.6% | 86.7% | -0.011 | -0.056 … +0.022 | 1 |
| a1 small swarm(signal_board) vs small single [finance] | finance | 90 | 63.3% | 71.1% | -0.078 | -0.156 … -0.011 | 0.0923 |
| a2 small swarm(evidence_exchange) vs small single [medical] | medical | 90 | 80.0% | 86.7% | -0.067 | -0.156 … +0.022 | 0.18 |
| a2 small swarm(evidence_exchange) vs small single [finance] | finance | 90 | 21.1% | 71.1% | -0.500 | -0.678 … -0.322 | 7.05e-11 |
| b1 small swarm(signal_board) vs frontier-strong single [medical] | medical | 90 | 85.6% | 96.7% | -0.111 | -0.222 … -0.022 | 0.00195 |
| b1 small swarm(signal_board) vs frontier-strong single [finance] | finance | 90 | 63.3% | 40.0% | +0.233 | +0.011 … +0.444 | 0.00309 |
| b2 small swarm(evidence_exchange) vs frontier-strong single [medical] | medical | 90 | 80.0% | 96.7% | -0.167 | -0.256 … -0.089 | 6.1e-05 |
| b2 small swarm(evidence_exchange) vs frontier-strong single [finance] | finance | 90 | 21.1% | 40.0% | -0.189 | -0.356 … -0.033 | 0.000911 |

## E15 task_dag and E13 foraging (secondary, small samples)

| World | Model | Arm | Fixtures req | Missing | Successes | Success rate | Wilson LB | Failed calls | Prompt tok | Output tok | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| foraging | claude-haiku-5.5 | baseline | 5 | 0 | 0 | 0.0% | 0.0% | 234 | 162,213 | 46,565 | $0.0395 |
| foraging | claude-haiku-5.5 | hive_memory_signals | 5 | 0 | 0 | 0.0% | 0.0% | 538 | 28,219 | 7,799 | $0.0067 |
| foraging | qwen38-27b-q3k | baseline | 5 | 0 | 1 | 20.0% | 4.6% | 18 | 156,063 | 37,974 | $0.0000 |
| foraging | qwen38-27b-q3k | hive_memory_signals | 5 | 0 | 0 | 0.0% | 0.0% | 10 | 245,287 | 81,855 | $0.0000 |
| task_dag | claude-haiku-5.5 | solo_planner | 19 | 0 | 4 | 21.1% | 9.8% | 0 | 11,427 | 24,759 | $0.0135 |
| task_dag | claude-haiku-5.5 | swarm_partitioned | 19 | 0 | 0 | 0.0% | 0.0% | 0 | 75,151 | 23,253 | $0.0191 |
| task_dag | claude-haiku-5.5 | swarm_partitioned_merged | 19 | 0 | 16 | 84.2% | 66.4% | 0 | 75,151 | 23,253 | $0.0191 |
| task_dag | claude-sonnet-5.5 | solo_planner | 19 | 0 | 10 | 52.6% | 34.7% | 0 | 11,427 | 20,010 | $0.2230 |
| task_dag | claude-sonnet-5.5 | swarm_partitioned | 19 | 0 | 0 | 0.0% | 0.0% | 0 | 75,151 | 17,396 | $0.3243 |
| task_dag | claude-sonnet-5.5 | swarm_partitioned_merged | 19 | 0 | 16 | 84.2% | 66.4% | 0 | 75,151 | 17,396 | $0.3243 |
| task_dag | qwen38-27b-q3k | solo_planner | 19 | 0 | 2 | 10.5% | 3.5% | 0 | 7,943 | 18,147 | $0.0000 |
| task_dag | qwen38-27b-q3k | swarm_partitioned | 19 | 0 | 0 | 0.0% | 0.0% | 0 | 51,148 | 8,852 | $0.0000 |
| task_dag | qwen38-27b-q3k | swarm_partitioned_merged | 19 | 0 | 16 | 84.2% | 66.4% | 0 | 51,148 | 8,852 | $0.0000 |

| World | Model | Treatment vs baseline | Pairs | Successes (treat/base) | Sign-test p |
|---|---|---|---|---|---|
| task_dag | claude-haiku-5.5 | swarm_partitioned vs solo_planner | 19 | 0/4 | 0.125 |
| task_dag | claude-haiku-5.5 | swarm_partitioned_merged vs solo_planner | 19 | 16/4 | 0.000488 |
| task_dag | claude-sonnet-5.5 | swarm_partitioned vs solo_planner | 19 | 0/10 | 0.00195 |
| task_dag | claude-sonnet-5.5 | swarm_partitioned_merged vs solo_planner | 19 | 16/10 | 0.0312 |
| task_dag | qwen38-27b-q3k | swarm_partitioned vs solo_planner | 19 | 0/2 | 0.5 |
| task_dag | qwen38-27b-q3k | swarm_partitioned_merged vs solo_planner | 19 | 16/2 | 0.000122 |
| foraging | claude-haiku-5.5 | hive_memory_signals vs baseline | 5 | 0/0 | — |
| foraging | qwen38-27b-q3k | hive_memory_signals vs baseline | 5 | 0/1 | 1 |

## Usage (physical calls, W2 non-smoke rows; aggregated in `usage-summary.json` from the operator-local ledger)

| Billing | Model | Calls | Failed calls | Prompt tok | Output tok | Cost |
|---|---|---|---|---|---|---|
| local | qwen38-27b-q3k | 7,075 | 476 | 5,132,098 | 752,654 | $0.0000 |
| nous-credits | claude-haiku-5.5 | 7,199 | 956 | 7,506,502 | 1,638,486 | $1.5699 |
| nous-credits | claude-sonnet-5.5 | 2,199 | 16 | 2,662,960 | 324,177 | $8.5677 |

## Deviations from the preregistration

1. 5 harness invocation(s) were restarted; already-written cells were kept and skipped (logged `resumed: true`).
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

Hashes of every raw file are in `MANIFEST.sha256` (cells, bundles, raw responses, run log, usage summary). Raw responses are request-hash keyed, so every cell can be replayed offline through the engine with `antelligence.providers.Cached(..., offline=True)`.
