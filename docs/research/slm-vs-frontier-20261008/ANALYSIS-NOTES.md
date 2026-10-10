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
