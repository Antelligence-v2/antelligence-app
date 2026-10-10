# Colony v2 design: independence metric, reputation, calibrated aggregator

Status: **design for review** (2026-10-10), before any code. Goal: v3 Track 1, steps 1, 2 and 4. Steps 3 and 5 (diversity and verified admission) are sketched only where they connect.

## 0. What the pilot already tells us

This was measured offline from the stored Sprint 1 (W2) cells, with no new model calls. The pilot script lands in the first Track 1 PR together with its output file.

**Three copies of one model, voting (`independent_vote`, temperature 0.7).** An error means wrong or abstained, scored against the gold answer.

| Model | Items | Error correlation ρ between voters | Effective independent agents |
|---|---|---|---|
| Haiku 5.5 | 172 | 0.88, 0.88, 0.92 | **1.08** |
| Sonnet 5.5 | 41 | 0.81, 1.00, 0.81 | **1.09** |
| Qwen3.8-27B | 153 | 0.67, 0.56, 0.63 | **1.34** |

**Three different models, one call each, on the same 180 items (`single`).**

| Pair | ρ |
|---|---|
| Haiku × Sonnet | 0.14 |
| Haiku × Qwen | 0.29 |
| Sonnet × Qwen | 0.26 |

Together these three behave like **2.05** independent agents.

**Reading.** Sprint 1's teams were one agent counted three times, so voting could not help. That is the measured reason for the Q&A null. A mixed-model colony starts with about twice the independence. Two caveats:
- The cross-model numbers use strict scoring, so Sonnet's format failures count as errors.
- The within-model numbers use complete cells only.

## 1. Independence metric (`antelligence/kernel/independence.py`)

**Input.** An error matrix: agents × items, each entry 1 (error), 0 (correct) or missing. Errors are judged by the evaluator, never by the agent.

There are two builders:
- `errors_from_runs(runs, judge)` reads each run's `EventLog`. `judge(event) -> bool | None` decides from **world outcomes and verifier/evaluator verdicts only**. The default judge, for worlds without gold answers, counts these as errors: a rejected outcome, a blocked intent (`classify_episode` semantics) and a policy failure. An accepted outcome counts as correct.
- A Q&A judge scores each agent's final answer against the task's gold answer with the world's own scorer. The gold answer never enters an observation; the scorer runs after the cell closes.

**Agent identity across runs.** Each agent has a stable *seat* label from the arm config, e.g. `qwen38/scout#1`, so the matrix spans many runs.

**Output** (`IndependenceReport`, plain JSON):
- `error_rate[a]` and `n[a]`.
- `rho[a][b]`: phi correlation of the error indicators, over items where both agents answered, with `n[a][b]`.
  - It is undefined when either agent never or always errs; that is reported, never silently zeroed.
- `double_fault[a][b]` = P(both wrong). This is Kuncheva's measure, which is easier to read than ρ.
- **`n_eff = k² / Σ_ab ρ_ab`** (with ρ_aa = 1). This is the variance-based effective sample size: k equally correlated agents count as k / (1 + (k−1)ρ̄). It is the same arithmetic as "ten judges ≈ 3.5 independent".
  - Negative correlation makes `n_eff > k`, which is reported as is.
  - A pair with too little overlap (n_ab < 20) falls back to a preregistered prior ρ₀, and this is flagged.
- `n_eff_ci`: a seeded bootstrap over items (1,000 resamples), giving a 95% percentile interval.
- **`herding`** (multi-round protocols): `n_eff` on round-0 answers minus `n_eff` on final answers. This measures how much independence communication destroyed. It is the direct test of why `evidence_exchange` fell to 50.6%.

**Wiring.** `experiments/runner` adds `independence` to every experiment report. The kernel never imports a world, because the judge is passed in.

## 2. Reputation (`antelligence/kernel/reputation.py`)

**What carries reputation.** A *persona*: model + role + prompt, e.g. `qwen38-27b/scout`. Seats that share a persona pool their record. A persona does not gain influence by being copied; the correlation discount in §3 handles copies.

**Model.** One Beta-Bernoulli counter per (persona, area, channel).
- `area` is a competence domain such as `research_qa/finance`. It is deliberately not called "scope", because memory scope already means experimental arm.
- The prior is centred on **chance accuracy** (1/K) with strength 2. An unknown persona therefore starts with **zero voting weight** (§3), and a fresh identity cannot buy influence (Sybil resistance).
- Optional exponential forgetting λ, default 1 (off).

**Channels, all written only by an authority** (same rule as `EvidenceMemory` outcome records: anyone else gets `TrustError`):
| Channel | Written by | Event |
|---|---|---|
| `label` | evaluator, after an item closes | the persona's final answer was right or wrong |
| `verification` | verifier, immediately | a claim's quote/number check passed or failed (§5) |
| `contradiction` | memory resolution by an authority | the persona's claim lost a resolved contradiction |

Agent text, confidence statements and self-assessments never update reputation. There is no API that takes them.

**Leakage and replay rules:**
- Within one item, reputation is frozen. Label updates apply only after the item's cell closes, in a fixed, seeded item order. This is **prequential**: item t sees only labels from items before t.
- A run's `config_hash` includes the hash of the ledger snapshot it started from. Each update is appended as a `reputation_updated` event, so the ledger can be rebuilt by replaying logs (`ReputationLedger.from_events`).
- A warm-up on the **dev split** seeds the ledger before evaluation, so the eval run does not start from zero. The warm-up items are disjoint from eval items, and this is checked by task-id hashes.

**Signals and claims carry reputation:**
- **Signals:** a new optional `Signal.sender_reputation`, stamped by the scheduler at emission and never by the agent, so it cannot be forged. It is omitted from the hashed body when `None`, so every existing trace hash and replay stays byte-identical, and a test asserts that.
- **Claims:** reputation is attached at read time. `ScopedRecall` with a ledger returns the record plus `author_reputation` as of the reading tick. It is not written into the record body, because that would change `content_key` and break `min_confirmations`.

## 3. Calibrated aggregator (`antelligence/kernel/aggregate.py`)

This replaces strict-majority and AND-style rules. It is pure and model-free: votes in, decision out.

**Input.** A vote per agent: `(seat, persona, answer | None, verification ∈ {verified, unverified, failed})`. It also takes the reputation ledger and a correlation lookup ρ(seat_a, seat_b), estimated from data before this item.

**Steps:**
1. **Candidates.** Distinct non-null answers. Numeric answers are grouped by canonical value, preregistered as equal after rounding to 6 significant figures. K = the number of choices for closed questions, or the number of candidates + 1 for open numeric ones.
2. **Reliability weight.** w_i = clip(log((K−1)·p̂_i / (1−p̂_i)), 0, 4), where p̂_i is the persona's posterior accuracy. These are the Nitzan–Paroush optimal weights for independent voters. Clipping at 0 means an unreliable agent is ignored rather than inverted.
3. **Verification multiplier.** m_i is 1 for verified, γ = 0.5 for unverified and 0 for failed. A claim whose quote isn't in the source has no voice.
4. **Correlation discount.** d_i = 1 / Σ_{j ∈ voters} max(ρ_ij, 0), with ρ_ii = 1.
   - k exact copies count as one agent.
   - Independent agents count fully.
   - Σ d_i equals the `n_eff` formula of §1.
   - This needs no matrix inversion, gives no negative weights and copes with abstentions. Generalised least squares (inverse correlation) is the textbook alternative; it was rejected because it is unstable with 3–5 agents and small samples.
5. **Posterior.** score(a) = Σ_{i votes a} d_i·m_i·w_i, then P(a) = softmax(score / T) over the candidates. Temperature T is fitted on the warm-up split, preregistered, with default 1.
6. **Decision.**
   - *Forced-choice mode:* argmax. Ties break to the higher top individual weight, then deterministically.
   - *Abstain mode:* abstain if P(top) < τ, **or** if the effective independent support of the top answer, Σ_{i votes top} d_i·m_i, is below n_min (default 1.0, i.e. no fully independent verified backer).
7. **Output.** `AggregateDecision(answer, posterior, support_n_eff, abstained, reason, contributions[])`. It is logged as an `aggregated` event so Colony Lab (Track 5) can show exactly why an answer won.

**Properties that will be tested:**
- With equal reputations and zero correlation, it equals plurality vote.
- k copies of one agent produce the same decision and posterior as that agent alone.
- A failed-verification vote never changes the outcome.
- An unknown persona at the prior has zero weight.
- It is deterministic and order-independent.
- With one voter, it returns that voter's answer whenever w > 0.

## 4. How these connect (steps 3 and 5, for context)

- **Diversity.** Arm configs list seats as (model, role, evidence shard). The roles are:
  - *scout*: answers from its shard with quotes;
  - *critic*: may contradict a peer claim only by citing evidence, through memory `contradict`;
  - *summariser*: packages admitted claims into checkable form for the verifier.
- **Verified admission.** Claims carry `quotes: [{evidence_id, text}]`, and numbers carry a `source_calculation_v1` plan.
  - A model-free `ClaimCheck` tests that quotes appear verbatim (whitespace-normalised) and that the plan recomputes to the claimed number.
  - A pass is admitted by the verifier authority. Anything else stays an `unverified` candidate.
  - `min_confirmations = 2` gives two-witness admission.
  - The check's verdict feeds the `verification` channel and the multiplier m_i.
- **Fixes for Sprint 1's scoring artifacts, carried into the new protocols:**
  - state the citation limit in the prompt;
  - lenient parsing (last JSON object), with the format-failure rate reported separately;
  - a plurality control.

## 5. Experiment shape (full preregistration comes before the first run)

- **Arms:**
  - best solo member model, one call;
  - **best solo member at matched calls**: self-consistency, k samples, plurality vote;
  - Sprint 1's best protocol (`independent_vote`);
  - the new colony;
  - four ablations of the new colony: no correlation discount, no reputation (w_i equal), no diversity (one model), no verified admission.
- **Cost trick.** The correlation-discount and reputation ablations only change aggregation, so they **replay the same cached replies offline at zero extra calls**. Only the diversity and verified-admission ablations need new calls.
- **Domains:** PubMedQA and FinQA (eval split) and task_dag.
- **Paired by item:** sign tests with Holm correction, Wilson lower bounds, ECE and Brier, risk–coverage curves, `n_eff` with its CI, and cost.
- **Success rule (from the goal).** The new colony beats the best solo model with a confidence interval excluding zero on at least one Q&A domain, *or* a clear, explained null that names the mechanism that failed.

## 6. Code footprint

Three kernel modules plus small additive hooks:
- `Signal.sender_reputation`;
- `Scheduler(reputation=...)`;
- `ScopedRecall(ledger=...)`;
- event types `reputation_updated` and `aggregated`.

No world is imported. Each module gets its own test file. Planned PR 1 (kernel only) is about 900 lines including tests.

## 7. Operator decisions (2026-10-10)

1. **Abstention: agreed.** The headline always picks an answer (forced choice). Abstain mode is reported separately: coverage (how often it answers), and selective accuracy (how accurate it is when it does), plus risk–coverage curves.
2. **Solo baseline: agreed.** The headline comparison is the best member model at matched calls and tokens (self-consistency, k samples, plurality). The 1-call solo is also reported.
3. **Colony members.**
   - Local: Qwen3.8-27B, Phi4 and Gemma 4 E4B, plus **Haiku 5.5 as a cross-vendor member**.
   - **Report every colony result with and without Gemma 4 E4B.** A much weaker member can raise measured independence just by being wrong more often.
   - **Report two colonies:**
     - *local-only*, whose smartest member is probably Qwen;
     - *with Haiku*. Haiku is probably then the smartest member, so this colony must beat Haiku at matched calls. That is a much harder bar.
   - Models run one at a time, not co-resident. Replies are cached by request hash, so the colony is assembled from cached replies.
4. **Reputation warm-up: agreed, with two conditions.**
   - The dev split is kept disjoint from the eval set, checked mechanically by comparing task-id sets.
   - A **cold-start run with no warm-up** is also reported, so a gain cannot be credited to the warm-up.

### Addition prompted by decision 3: rate-adjusted independence

The phi correlation between two error indicators is capped below 1 when the agents' error rates differ:

phi_max = sqrt(p₁(1−p₂) / (p₂(1−p₁))) for p₁ ≤ p₂.

So a weak agent next to a strong one *looks* independent even when it fails on every item the strong one fails on. This already affects the pilot: Sonnet's 31.7% strict error is mostly format failures.

The metric therefore also reports:
- `rho_adjusted = rho / phi_max` (for rho > 0);
- `n_eff_rate_adjusted`, computed from `rho_adjusted`. This is the conservative figure.

Both raw and adjusted values go into every report, and the headline independence claim uses the adjusted one.
