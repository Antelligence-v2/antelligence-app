# Colony v2 preregistration: can a mixed colony beat its smartest member?

- **Status:** written 2026-10-10, before any colony-v2 model call. This file, `scripts/colony_v2_collect.py`, `scripts/colony_v2_analyze.py` and `scripts/colony_v2_pod.py` are committed before the first call. The collect script refuses evaluation calls unless all three are committed and unmodified, and the first call's ledger row comes after that commit.
- **Immutability:** this file does not change after the first evaluation-split call. Any departure goes in the "Deviations" section of `REPORT.md`.
- **Design:** `DESIGN.md` in this folder, including the operator decisions in §7.

## 1. Question

Does a colony of different models, combined by `antelligence.kernel.aggregate`, answer more questions correctly than its single best member given **the same number of calls**?

Sprint 1's answer was no for same-model colonies. The pilot (`pilot-independence.json`) shows why: three copies of one model are worth about 1.1–1.3 independent voters. This experiment tests whether mixing models fixes that.

## 2. Models (official releases only; no fine-tunes or modified weights)

| Seat | Model | Source | Served by |
|---|---|---|---|
| Q | Qwen3.8-27B (FP8) | `Qwen/Qwen3.8-27B-FP8` | vLLM on one rented RunPod GPU |
| P | Phi-4-mini-instruct | `microsoft/Phi-4-mini-instruct` | vLLM, same pod |
| G | Gemma 4 E4B-it | `google/gemma-4-E4B-it` | vLLM, same pod |
| H | Claude Haiku 5.5 | `anthropic/claude-haiku-5.5` | Nous inference API (existing credits) |

- **Serving:** `vllm/vllm-openai:v0.30.0`. The HF revisions are pinned in `colony_v2_pod.py`: Qwen `017b9c7a…`, Phi `cfbefacb…`, Gemma `ee0ef602…`. Thinking mode is turned off (`enable_thinking: false`) for every seat, so all models answer directly within the same budget.
- **Identity:** every reply records the served model name, the HF revision hash and the vLLM version. A reply whose served model name doesn't match is an error, not an answer.
- **Excluded:** the Sprint 1 local models (an abliterated Qwen and a finance fine-tune of Phi4) are not used, on the operator's instruction. So Sprint 1 and pilot Qwen numbers do not carry over to seat Q.
- **Decoding:** temperature 0.7, top-p 1.0, max 2,048 output tokens.
  - *Amended 2026-10-10, before any evaluation-split call.* The draft said 512. In the 2-task development plumbing check, Haiku hit 512 on 3 of 6 replies whose visible JSON was only about 300 characters, because Nous counts hidden reasoning tokens as output. A 512 cap would measure that budget, not the model. The new cap is the same for every seat, and tokens are reported per arm. The seed is fixed per (item, seat, sample index).
- **Output limit:** a reply cut off at the token limit is a format failure (§5), not a wrong answer.

## 3. Data

- **Source:** `backend/research_fixtures/tasks.json`, sha256 recorded by the run script at start.
- **Development split** (50 PubMedQA + 50 FinQA). Used for reputation warm-up, choosing the best member, and estimating the error-correlation matrix for the correlation discount.
- **Evaluation split** (50 + 50). Used for every reported result.
- **Disjointness:** the run script refuses to start if the two splits share a `task_id` or a question text.
- **Prior exposure.** W2 (2026-10-08) used 60 of the 100 evaluation tasks, and the design of the aggregator was made after reading its pilot data. The 40 untouched evaluation tasks are reported separately as a sensitivity check (S6). Nothing in this experiment is tuned on evaluation items.
- **task_dag** (named in the goal) is **not** in this experiment. Its colony needs the role seats of Track 1 step 3, which aren't built yet. It gets its own preregistration later. This experiment is Q&A only.

## 4. Calls

- **Per model:** 3 samples on every development and evaluation item, in the verified-claims reply format (`verified_claims_v1`: quotes for choice questions, a source calculation for numeric ones, at most 3 cited passages).
- **Totals:** 3 × 200 = 600 calls per model, so 2,400 calls in all, of which 600 are Haiku.
- **Caching and arms:** replies are cached by request hash. Every arm below is assembled offline from this one cache, so the arms are matched by construction:
  - a *k*-call arm uses exactly *k* replies per item;
  - tokens are reported per arm.

## 5. Arms (per item, each produces one forced-choice answer)

| Arm | Calls | Built from |
|---|---|---|
| `solo1[m]` | 1 | sample 1 of model *m* |
| `solo3[m]` | 3 | plurality of model *m*'s 3 samples (self-consistency) |
| `colony_local` | 3 | sample 1 of Q, P and G, combined by the full aggregator |
| `colony_haiku` | 3 | sample 1 of Q, P and H, full aggregator |
| `colony_local_noG` | 2 | sample 1 of Q and P (Gemma removed) |
| `colony_haiku_withG` | 4 | sample 1 of Q, P, G and H. `colony_haiku` already leaves Gemma out, so this arm is the "with Gemma" version of the Haiku colony. |

- **Best member:** the model with the highest `solo3` accuracy **on the development split**, chosen per colony from that colony's members, before any evaluation item is scored. The run script records the choice. It is expected to be Q for `colony_local` and H for `colony_haiku`, but the development data decides.
- **Matched baseline for a 4-call colony:** `solo4[m]`, a plurality over 4 samples, which needs one extra sample from the best member. So the best member of each colony gets a 4th sample on every evaluation item; if that member is Haiku, this adds 100 Haiku calls.
- **Full aggregator** (`antelligence.kernel.aggregate.Aggregator`, forced mode):
  - reliability is the reputation from the development-split warm-up (label channel, area = domain, chance = 1/3 for PubMedQA, 1/2 for FinQA);
  - the correlation is estimated on development-split errors (`independence`, min_overlap 20, prior 0);
  - verification multipliers are 1 / 0.5 / 0 (verified / unverified / failed); all other parameters use the `DESIGN.md` defaults.
- **Pooling:** the best member, the warm-up reputation and the correlation matrix are estimated from development items with both domains pooled (100 items). The warm-up uses sample 1 of each model.
- **Plurality ties:** in `solo_k`, a tie goes to the answer seen in the earliest sample. Where the aggregator decides, its deterministic canonical tie-break applies.
- **Chance level:** 1/3 for PubMedQA. FinQA has open numeric answers, so its chance level is set at 1/2, which is conservative (it gives weaker members less weight).
- **4th samples:** a 4th sample goes to every model that is the development-best member of any colony that needs `solo4`. S7's `solo2` uses the development-best of {Q, P}.
- **Reputation during evaluation:** reputation is frozen for the evaluation pass. There are no prequential updates, so the order of items can't matter.

## 6. Hypotheses and tests

**Primary (P1).** On the evaluation split, `colony_local` accuracy is greater than `solo3[best local member]`, in at least one domain.
- Test: exact two-sided McNemar (paired by item), per domain, with Holm correction across the 2 domains.
- "Colony wins": Holm-adjusted p < 0.05, and the 95% paired-difference interval (Newcombe) is above 0.

**Primary (P2).** The same test for `colony_haiku` against `solo3[best member of {Q, P, H}]`.

**Secondary (reported, not used to declare a win):**
- **S1 ablations** (offline, zero extra calls), each a version of `colony_local` and `colony_haiku`:
  - (a) no correlation discount;
  - (b) no reputation (equal weights);
  - (c) no verification weighting;
  - (d) plain plurality over the same seats;
  - (e) single-model colony, which equals the best member's `solo3` under the colony aggregator.
- **S2 independence:** rate-adjusted `n_eff` with a 95% bootstrap CI for the colony seats on evaluation errors, plus the raw value. Headline: rate-adjusted.
- **S3 abstain mode** (τ = 0.6, min_support = 1.0): coverage, selective accuracy with a Wilson interval, and risk–coverage curves.
- **S4 calibration:** ECE (10 equal-width bins) and Brier of the colony's top posterior, compared with the self-consistency vote share of `solo3`.
- **S5 cold start:** the same colonies with no warm-up. The development-split correlation matrix is kept. Reputation then sits at chance, so every weight is 0 by construction, and the colony falls back to correlation-discounted plurality. This guards against crediting a gain to the warm-up.
- **S6 untouched items:** P1 and P2 recomputed on the 40 evaluation tasks W2 never used.
- **S7 without Gemma:** `colony_local_noG` against `solo2[best]`, and `colony_haiku_withG` against `solo4[best]`.
- **S8 verification health:** the share of verified, unverified and failed claims per model and domain. Verification checks grounding, not correctness, so this is reported next to accuracy and is never presented as accuracy.
- **S9 cost:** calls, prompt and completion tokens, GPU wall-clock time and dollars per arm. GPU hours and dollars come from the pod script's own records. Haiku is reported in tokens, because the provider doesn't return a cost.

## 7. Scoring and failures

- **Scoring:** answers are scored by `backend.swarm_core._score_answer` (exact choice; decimal within the task tolerance).
- **Format failures:** a reply that isn't JSON, or is cut off, counts as a **format failure**.
  - That seat casts no vote, and the failure counts against that arm's accuracy (strict).
  - Format-failure rates are reported per model, and accuracy is also given with format failures excluded, as a labelled secondary figure.
  - Lenient parsing (`lenient=True`) applies to every arm alike.
- **Forced choice:** an arm whose seats all failed or all abstained has no answer, and that item counts as wrong.

## 8. Power, stated in advance

- **Sample size:** 50 evaluation items per domain.
- **Smallest detectable gain:** with McNemar at α = 0.05 (Holm), only a large paired gain is detectable, roughly **12–18 points** depending on how many items the two arms disagree on.
- **Smaller effects:** a smaller true effect will most likely produce a null.
- **Reporting a null:** it is reported as "not detected at this sample size", with the interval. The report will not say "no effect" unless the interval excludes gains above 5 points.
- **Further items:** if P1 and P2 are both null, extending to more items is a new preregistration, not a continuation of this one.

## 9. What would count as an explained null

If the colony does not win, the report names which link failed, using the secondary measures:
- the seats weren't independent (S2: rate-adjusted `n_eff` below 1.5);
- the weaker members were too weak to add information (weights from the warm-up near 0);
- verification didn't separate good claims from bad (S8: verified accuracy about equal to unverified accuracy);
- the correlation estimate from development didn't transfer to evaluation (development vs evaluation `rho` reported).

- **Thresholds for this checklist,** fixed now:
  - "near 0" means a mean weight below 0.25;
  - "about equal" means overlapping 95% Wilson intervals;
  - "didn't transfer" means a development-to-evaluation shift in `rho` above 0.3.

## 10. Stop rules and budget

- **GPU:** one RunPod pod, at most 2 hours of wall-clock time.
  - The pod is terminated as soon as the cache is complete, or on any failed identity check.
  - The balance before the run was $2.79.
- **Haiku:** at most 800 calls via Nous credits. Every call is logged with its usage.
- **No reruns:** an evaluation item is never rerun to change its result. Provider errors are retried up to 3 times with the same request, and are then marked as errors.
