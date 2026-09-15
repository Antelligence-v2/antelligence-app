# E13 Design: Chain-Prioritized Foraging

## Task Family

**Chain-prioritized foraging** on a 10×10 grid with 3 agents and 3 foods.

Foods carry a delivery order: food 0, then food 1, then food 2. An agent carrying food 1
is *not* closer to success until food 0 is delivered. Discovering food 1 before food 0 is
delivered is useless noise.

## Why This Family

In E7v6, every food sighting was immediately actionable by any agent. Here, shared
information has temporal structure — some sightings are valuable only in a later phase.
This plausibly changes coordination demand. If hive memory helps when information has
prerequisites, the effect is more robust (and the headline is stronger). If it doesn't,
the headline needs narrowing.

This differs from E7v6 in multiple axes simultaneously:
- **Temporal prerequisites** (chain constraint) — new.
- **Multi-carry** (auto-pick always picks; auto-drop delivers in chain order) — new in
  interaction with the chain.
- **Holding penalty** — carrying wrong food adds wasted travel.
- **Memory relevance filtering** — memory stores all sightings but only next-needed ones
  are useful; the agent must distinguish relevant from irrelevant recalls.

## What Stays Identical (Harness Conventions)

- Grid: 10×10, 3 agents, 3 foods, view_k=5, seeds 101–120, temperature 0.
- Model route for this completion: `z-ai/glm-5.3-flash` via the Nous Portal. This is a
  cross-model replication of the original `nousresearch/hermes-4-405b`/OpenRouter run.
- Arms: `baseline`, `hive_memory`, `hive_memory_comm` — identical semantics.
- Binary FOLLOW/SWEEP decision; harness executes movement. LLM does not compute directions.
- Primary metric: `sweep_moves` (wasted blind search).
- Secondary: `steps_to_success`, success rate, deliveries, tokens/run.
- Oracle solvability check on all 20 seeds before arms.
- Budget cap: $1.00.

## What Changed (Task Structure Only)

- Foods have delivery order. Prompt tells agent which food is next-needed and which it
  carries.
- Auto-pick: always pick food when stepping on it (multi-carry).
- Auto-drop: deliver foods at nest in chain order (0→1→2).
- Carrying wrong food: agent must keep searching for the next-needed food.
- Memory records: "food {i} at (x,y)" — index included.
- Memory retrieval: all sightings recalled, but only next-needed sightings are useful.
- `sweep_path` unchanged — sweep is still a deterministic snake pattern.
- STEPS bumped to 120 (from 80) to account for holding penalty.

## Predeclared Metrics

| Metric | Definition |
|--------|------------|
| `sweep_moves` (primary) | Count of moves executed as part of a SWEEP (blind coverage) |
| `steps_to_success` | Steps until all 3 foods delivered (None if failed) |
| `success` | Boolean: all 3 foods delivered within STEPS |
| `deliveries` | Number of foods delivered (0–3) |
| `llm_calls` | Number of LLM API calls |
| `prompt_tokens` / `completion_tokens` | Token counts |
| `memory_deposits` | Number of food sightings recorded to hive memory |
| `memory_hits` / `memory_relevant_hits` | Memory retrieval count / count of hits that matched next-needed food |
| `transport_events` | Number of transport frames sent/received (hive_memory_comm only) |
| `parse_errors` | Number of unparseable LLM responses |

## Predeclared Verdicts

- **Generality supported:** hive memory reduces aggregate sweep moves with the same sign
  test direction AND p < 0.05 on the new family, AND the aggregate reduction is ≥ 5%. A
  hostile reviewer's proposed bar: below 5% reduction or p > 0.05 means the effect is too
  small or too noisy to generalize, so the paper's headline narrows to "single task family"
  and the abstract is edited.
- **Generality refuted:** no reduction, or a reversal, or p ≥ 0.05. Then the paper's
  headline narrows to the coordination-isolated foraging family (no prerequisite structure),
  and the abstract is edited.
- **Partial:** reduction in the same direction but below the 5% threshold or with 0.05 ≤
  p < 0.10. Report the effect size and the limitation; do not upgrade a marginal result to
  a claim.

**Pre-registered bar (added 2026-09-13 before matrix):** if hive-memory reduction < 5% OR
sign test p > 0.05 → headline narrowed to "single task family", abstract edited. The
operator rejected a 10-seed cap (insufficient sign-test power); the full 20-seed matrix
runs.

## Oracle Solvability

The sweep-only oracle knows all food positions and indices. It moves optimally toward the
next-needed food (or nest if carrying it). With 3 parallel agents and 120 steps, the oracle
must solve 20/20 seeds. This proves the task is solvable and that any baseline failure is
model limitation, not task impossibility.

## Run Protocol

```
# Pre-test gate: oracle solvability
python3 run_pilot.py --oracle-only --steps 120

# If oracle passes 20/20, run arms in background
python3 run_pilot.py --arm baseline   &
python3 run_pilot.py --arm hive_memory &
python3 run_pilot.py --arm hive_memory_comm &

# Verify by results files, not notifications
```

## Budget

$1.00 cap in the preregistration.

**Operator-approved amendment (2026-09-14):** the E13 total spend cap is raised to **$2.50**
(including the previously incurred E13 spend), with a hard stop of **$0.80 per matrix arm**.
This is a cap increase only; the task, arms, seeds, temperature, and authoritative metrics are
unchanged. Do not exceed $2.50 without renewed operator approval.

