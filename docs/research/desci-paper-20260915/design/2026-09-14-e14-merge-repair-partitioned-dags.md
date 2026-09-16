---
linked: 2026-09-15
---

# E14 — merge/repair layer over partitioned swarm proposals (cold-start brief)

Date: 2026-09-14. Status: NOT STARTED. Budget: **~$0.25**. Route: **Nous Portal** (see below).

## Why

E12 tested whether E11's 63% redundancy was caused by information identity. It was:
`swarm_partitioned` collapsed redundant nodes to **0%**. But it collapsed coverage too —
**0/20 execution success** vs solo's 3/20 — at **6.4x solo tokens per accepted node** (2059.3 vs
323.4). Each agent proposed only its own sample's reserve/place sub-DAG, so the union was missing
the cross-sample prerequisite edges and admission rejected the place nodes
(`prerequisite_unmet` / `resource_unavailable` / `slot_unavailable`).

E12's own result implies the next hypothesis: **coordination value requires partitioning AND a
merge layer that restores the missing structure.** Partitioning removes duplication; a merge layer
restores coverage. Neither alone is enough.

This is the first design in the program where a *positive* coordination result is plausible.
A clean refutation is equally publishable: it would show the missing piece is not mergeable
structure but the agents' missing information, and that partial views are fatal for plan proposal.

## Route — Nous Portal (OpenRouter is dead)

Verified 2026-09-14: OpenRouter is out of credit (`total_credits 838, total_usage 838.21`).
All direct-OpenRouter calls return HTTP 402 permanently. Do NOT use it.

- base_url: `https://inference-api.nousresearch.com/v1` (OpenAI-compatible)
- auth: `~/.hermes/auth.json` → `providers.nous.access_token` (or `.agent_key`). Both verified 200.
- **The token expires in ~1 hour. Read auth.json FRESH PER CALL.** Caching it at startup is how
  E13 died mid-matrix.
- model: `deepseek/deepseek-v4.1-flash` (verified: correct `SWEEP`/`FOLLOW` in 85/92 completion
  tokens at `max_tokens=1500`; returns `content=None` at `max_tokens=24`). `z-ai/glm-5.3-flash`
  and `qwen/qwen3.8-flash` also verified working. **Budget `max_tokens >= 1500`.**
- `nousresearch/hermes-4-405b` is not in the Nous catalog — this run is a different model from
  E11/E12. Label the cross-experiment anchor comparison as cross-model.

## Design

Reuse the E12 harness (`e12-partitioned-dags/run_e12.py`, VERSION `e12-partitioned-dags-v2`).
Same fixtures, seeds 101–120, temperature 0. **Do not modify the admission gate** — model-free
deterministic admission is the proven piece and the reason this is testable.

Arms:
- `solo_planner` — anchor. Must reproduce E12: 55 accepted / 160 proposed, 3/20, 323.4 tok/node.
- `swarm_partitioned` — anchor. Must reproduce E12: 20 accepted / 120 proposed, 0/20, 2059.3.
- `swarm_partitioned_merged` — **NEW.** Identical partitioned proposals, then a **model-free
  deterministic merge layer** before the unchanged admission gate:
  1. union all nodes from all agents (no model call);
  2. for each sample, rewire its `reserve` node to depend on the `place` nodes of its
     prerequisites — the agents already receive `prerequisites` and `rules` in their public
     slice, so the *information* for the edge exists; only the *assignment* was missing;
  3. canonicalise ordering (the gate already sorts by canonical bytes) and let admission decide.

Predeclared metrics: `accepted_nodes`, `redundant_node_fraction`, `tokens_per_accepted_node`,
`execution_successes`, `determinism_failures`, `unsafe_act_count`.

## Predeclared verdicts

- **SUPPORTED:** merged arm has redundancy ≈0% AND execution success ≥ 3/20 (matching solo) AND
  tokens per accepted node ≤ 1.5x solo's 323.4. Then: partitioning + deterministic merge preserves
  coverage, and this is the program's first genuine coordination win.
- **REFUTED:** merged arm still 0/20, or success stays below solo. Then the missing piece is not
  mergeable structure; partial views are fatal to plan proposal and the paper says so.
- **PARTIAL:** redundancy fixed but success still below solo — report the gap, do not round up.

## Hard rules (carry-overs from E12's failure)

1. **The pre-test gate must assert ADMISSION, not just parseability.** E12's v1 bug emitted the
   literal string `"my_sample"` as the sample field; all 60 nodes were rejected
   (`resource_consistency`) and the parse-only pretest passed it anyway. New gate: a pretest that
   cannot fail on the metric you care about is not a gate.
2. Verify the merge layer is deterministic — admission must be run twice per seed and produce
   byte-identical accepted DAGs, as in E11/E12. Zero determinism failures is part of the claim.
3. Review packet `/Volumes/WD_BLACK/antelligence-review-20260911/` is READ-ONLY.
4. Cache responses keyed `(version, seed, arm, agent, step)`. Launch one arm per background
   process with its own cache and budget stop. Verify by results files, never by notifications.
5. Report every number from artifact files. Report failed attempts and their cost honestly
   (E12 reported its v1 bug spend rather than hiding it — that is the standard).

## Deliverables

`e14-merge-repair/` with `run_e14.py`, `DESIGN.md` (metrics + verdicts frozen before the matrix),
`REPORT.md`, `out/results_<arm>.json`, `out/e14_summary.json`, `out/pretest.json`.
Write the vault session note the same session the result lands.

<!-- wiki:semantic:start -->
## Related (auto-linked)

- [[HANDOFF-CODEX-2026-07-03-verify-and-dashboard]]
- [[2026-05-19-hackathon-progress]]
- [[2026-08-20-work-completion-and-telegram-notification-contract]]

<!-- wiki:semantic:end -->
