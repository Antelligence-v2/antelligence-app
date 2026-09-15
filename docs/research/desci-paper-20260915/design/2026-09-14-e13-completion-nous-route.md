---
linked: 2026-09-15
---

# E13 completion — finish the generality test on the Nous route

Date: 2026-09-14. Status: INCOMPLETE, resuming. Budget: ~$0.25 remaining of $0.99.

## Where it stands

Task family: chain-prioritized foraging (delivery order 0→1→2, so not every sighting is timely).
Oracle: **20/20 seeds solvable**, mean 33 steps, max 60 (seed 104).

On disk in `e13-chain/` (verified 2026-09-14, the "nothing salvaged" report was wrong):
- `out/pilot_error.json` — **12 complete baseline runs, seeds 101–112**
- `out/trajectories.jsonl` — 13 hive seeds (101–113), binary outcome 3/3 delivered on all 38 pairs
- `out/api_cache_*.jsonl` — three per-arm caches (~320 KB each)
- `out/oracle.json`, `REPORT.md` (marked INCOMPLETE)
- Spend so far: **$0.746** of a $0.99 cap

Missing: **seeds 114–120 (8 seeds × 3 arms)** plus a **seed-113 baseline**.

## Why it stopped

OpenRouter credit exhaustion — verified `total_credits 838, total_usage 838.21`, negative balance,
permanent HTTP 402. Not a harness bug. Do not retry that route.

## Route to finish on

**OPERATOR-APPROVED CAP INCREASE (2026-09-14):** E13's cap is raised from $0.99 to **$2.50 total**,
with a per-arm hard stop of **$0.80**. The previous cap was exceeded ($1.1435 spent), and the
operator has approved this increase explicitly. Record the amendment in `DESIGN.md` as an
operator-approved change with its date.

**All API calls must go to the Nous Portal.** Do not use OpenRouter.

- base_url: `https://inference-api.nousresearch.com/v1`
- auth: `~/.hermes/auth.json` → `providers.nous.access_token` (or `.agent_key`) — **read the file
  fresh per call**, the token lives ~1 hour
- model: one model for the whole run. `deepseek/deepseek-v4.1-flash`,
  `z-ai/glm-5.3-flash` and `qwen/qwen3.8-flash` are all verified as emitting correct `SWEEP`/
  `FOLLOW` at `max_tokens >= 1500` (they return `content=None` at small caps).
  `google/gemini-3.8-flash` also works. Prefer one and state it.

## CRITICAL — re-run all 20 seeds; do not resume from the old caches

The surviving caches in `out/` were produced by **two different models** and their keys do not
encode the model: per-entry cost is ~$0.00010 for seeds 101–113 and ~$0.00018–0.00022 for seeds
114–115, i.e. a pricing change. Seeds 101–112 came from `nousresearch/hermes-4-405b` via OpenRouter
(now dead); 113–115 from the Nous resume.

Therefore **resuming would produce a silently mixed-model 20-seed result that must not be
published.** Run the full matrix fresh: 20 seeds × 3 arms, one model, one route.

The old caches are still useful as a **cross-check only** — replay them separately, offline, and
report the hermes-4-405b (seeds 101–112) numbers as a labelled historical comparison. Never merge
them into the new result.

`nousresearch/hermes-4-405b` is not offered by Nous, so the new run is a different model from the
E7v6/E9/E10 anchors. **Label any cross-experiment comparison as cross-model.**

## Rules

1. **Do not present the trajectory-derived sweep counts as the pre-registered result.** They are
   action tallies including retry calls, systematically inflated vs the harness metric. Only the
   harness numbers count, and the pre-registered bar in `DESIGN.md` stands.
2. Complete the remaining seeds, then report the full 20-seed result for the three arms, the sign
   test on the authoritative metric, and the model change.
3. If the effect is < 5% or p > 0.05, the headline narrows to "single task family" and the paper's
   abstract gets edited. That bar was set before the run; do not renegotiate it after.
4. Seeds already cached are free — do not re-run them.

## Deliverables

Complete `out/results_baseline.json`, `out/results_hive_memory.json`,
`out/results_hive_memory_comm.json`, a final `out/e13_summary.json`, and a `REPORT.md` that
states the verdict against the pre-registered bar plus the model-change caveat.

<!-- wiki:semantic:start -->
## Related (auto-linked)

- [[decisions-moc]]
- [[mistakes-moc]]
- [[README]]

<!-- wiki:semantic:end -->
