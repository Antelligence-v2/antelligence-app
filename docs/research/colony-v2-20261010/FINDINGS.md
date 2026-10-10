# Colony v2: what we found

- **Generated tables:** `REPORT.md`, built from `results.json` by `scripts/colony_v2_analyze.py`.
- **Specification:** `PREREGISTRATION.md`, committed in `611dd09` before any colony-v2 model call.
- **Numbers:** every number here appears in REPORT.md, except two that are marked *exploratory*.

## Answer: no, and the mechanism that failed is identified

Neither colony beat its best member at the same number of calls, in either domain.

| Comparison (evaluation split, 50 items per domain) | Medical | Finance |
|---|---|---|
| Local colony (Qwen + Phi + Gemma) vs Qwen with 3 samples | +4.0 pts (−3.7 to +12.5), not significant | **−30.0 pts** (−42.1 to −16.1) |
| Haiku colony (Qwen + Phi + Haiku) vs Haiku with 3 samples | −2.0 pts (−11.0 to +6.7), not significant | **−16.0 pts** (−27.9 to −5.1) |

On finance the colonies are significantly *worse* (Holm p < 0.001 and p = 0.016). On medical, any effect is too small to detect with 50 items. The 40 evaluation items W2 never used (S6) tell the same story.

## Why the colony lost on finance

1. **The main cause is that verification weighting threw away good answers.**
   - The aggregator gives a vote zero weight when its claim *fails* verification. A finance claim fails when the model's calculation doesn't bind exactly to the source numbers.
   - But a failed claim still turned out right **59% of the time for Qwen and 77% for Haiku** (S8).
   - So the strong members' correct answers were often discarded, and the weak members decided the vote.
   - Switching verification weighting off (ablation c) brings the local colony's finance accuracy back **from 48% to 76%**, and the Haiku colony's from 74% to 78%.
2. **The weak members were very weak at finance.**
   - Phi-4-mini got 4% and Gemma 4 E4B got 8% (one sample each). Many of Gemma's finance replies were rejected for format (it wrote numbers as JSON numbers, not strings).
   - *Exploratory, added after seeing the data:* accepting those numbers would have rescued only 16 correct answers out of 107, so Gemma stays far below the other members.
   - Majority voting only helps when members are both better than chance and roughly comparable. Members at single-digit accuracy can only out-vote a strong one.
3. **Even without that mistake, mixing didn't beat the best member.**
   - With verification off, the local colony gets 77% overall against Qwen's 80%.
   - The Haiku colony gets 80% against Haiku's 87%.
4. **Independence was real but modest.**
   - Rate-adjusted independent members: 1.34 for the local colony (95% interval 1.07–1.73) and 1.60 for the Haiku colony (1.14–2.32).
   - Mixing models does decorrelate errors, as the pilot suggested. But adding uncorrelated *wrong* answers doesn't help.
5. **Reputation and the correlation discount barely mattered** (ablations a, b and the cold start are all within 4 points of the full colony). A warm-up can't explain any gain, because there was none.

## Where it nearly worked

- **Medical, local colony:** 86% against Qwen's 82%. The colony was right on 2 items Qwen missed, with no losses, but that is far too few to call.
- **Abstain mode is precise when it answers.** When the colony is allowed to abstain:
  - the Haiku colony answers 74% of items and is right on 89.2% of those;
  - the local colony answers 44% and is right on 90.9%.
  
  That is the colony's useful property here: *knowing when it doesn't know*. It does not answer more questions correctly.

## What this changes (inputs to the v4 plan)

1. **A failed verification should lower a vote's weight, not zero it.**
   - Grounding failures here are mostly format (exact-token binding), not evidence of a wrong answer.
   - Next step: calibrate the multiplier per channel from the development split, the same way reputation is, instead of fixing it at 0.
   - This needs a new preregistration. It can be tested on the cached replies at zero cost and confirmed on fresh items.
2. **Only admit members above a competence floor.** Run development-split accuracy per domain and seat a model only where it clears that floor. Phi and Gemma should not vote on finance.
3. **A real colony win probably needs comparable members.** Next time, use several strong models from different vendors (for example Qwen, Haiku and another strong open model), not one strong model plus small ones.

## Departures from the preregistration (all recorded in it before evaluation, except the last four)

- Max output tokens raised from 512 to 2,048 before any evaluation call (Haiku's hidden reasoning was truncating replies).
- The verifier restores a dropped `$` before any evaluation call (65 of 145 Haiku development calculations had failed on it).
- **Serving only:** Qwen needed `--max-num-seqs 64`. Its hybrid Mamba layers can't fit vLLM's default of 256 concurrent sequences on an L40S, so the first Qwen pod crash-looped for 28 minutes ($0.52 wasted). This limits concurrency and doesn't change prompts or decoding.
- 4th evaluation samples were collected for every local model, to avoid renting the GPU again. Only the 4th samples the preregistration names are used (Haiku's, for `solo4`).
- The Gemma number-format figure above is exploratory and is not part of any test.
- The pod launcher moved to RunPod's REST API, with a redacted log behind a per-pod secret path. This is infrastructure only.

## Cost

- **Calls:** 2,800 cells across 4 models, all on development and evaluation items from public benchmarks.
- **GPU:** about 59 minutes, $1.00 (RunPod balance $2.79 → $1.79).
- **Haiku:** 707 calls through Nous credits, recorded in the ledger (which is gitignored and stays on this machine).
