---
linked: 2026-09-14
---

# E13 — second task family (cold-start brief)

Date: 2026-09-13. Status: NOT STARTED. Budget cap: **$1.00**. Operator approval required.

## Why this experiment exists

The paper's headline claim — shared evidence memory cuts redundant search ~16%
(2319 → 1941 sweep moves, sign test p=0.012) — rests on **one task family and one
harness**. Twenty seeds, temperature 0, a binary FOLLOW/SWEEP decision on a 10x10 grid
with three agents and three foods.

It replicated across two model families (hermes-4-405b and grok-4-fast), which rules out a
model quirk. It does **not** rule out a task-shape quirk. A hostile reviewer's first
question is generality, and right now the paper has no answer.

Purpose: build one genuinely different task family under the same conventions and see
whether the direction reproduces. Both outcomes are publishable — a null result means the
headline must be narrowed to the tested family, and the paper must say so.

## Design

Keep the harness conventions identical so this is a generalization test and not a new
instrument (same seeds 101–120, temperature 0, model `nousresearch/hermes-4-405b`, same
arm names and semantics, oracle solvability check, same primary metric `sweep_moves`).
Start from `e7-swarmbench-v6/run_pilot.py`.

Change the **task structure**, not the instrument. Requirements:
- It must still be solvable by a sweep-only oracle on 20/20 seeds (prove it, as E7v6 did).
- It must still isolate coordination from state-conditional action execution. Do not
  reintroduce the PICK/DROP confound — that floor is real and already characterized
  (E9, E10-model-floor: only 2/32 backends pass a state-conditional action probe).
- It must differ in a way that plausibly changes coordination demand. Suggested axes, pick
  one and justify it: more agents (5–6) with more foods; a grid with two nests so agents
  can specialize by destination; or prerequisite structure borrowed from the E1/E4 fixture
  families (`chain`, `fork`) so discovering food A changes what is worth doing next.

Arms: `baseline`, `hive_memory`, `hive_memory_comm` — identical semantics to E7v6.

Predeclared metrics: `sweep_moves` (primary), `steps_to_success`, success rate,
deliveries, tokens/run.

## Predeclared verdicts

- **Generality supported:** hive memory reduces aggregate sweep moves with the same sign
  test direction and p < 0.05 on the new family.
- **Generality refuted:** no reduction, or a reversal. Then the paper's headline narrows to
  the coordination-isolated foraging family, and the abstract must be edited accordingly.
- **Partial:** reduction in the same direction but not significant at 20 seeds. Report the
  effect size and the limitation; do not upgrade a marginal result to a claim.

## Hard rules

- Review packet `/Volumes/WD_BLACK/antelligence-review-20260911/` is READ-ONLY.
- Do **not** reuse the full-spatial harness for arm comparison — it measures model
  capability, not architecture (E9 proved this).
- Cache responses per arm; pre-test gate before the matrix; one background process per arm
  with its own budget stop; verify by results files, not notifications.
- Report honest negatives and any anchor deltas, exactly as E7v6/E9 did.

## Deliverables

`e13-<family-name>/` with `run_pilot.py`, `DESIGN.md` (predeclared metrics + verdicts),
`REPORT.md`, `out/results_*.json`, `out/oracle.json`, `out/trajectories.jsonl`.
Update the vault session note and the paper the same session.

<!-- wiki:semantic:start -->
## Related (auto-linked)

- [[decisions-moc]]
- [[mistakes-moc]]
- [[2026-07-25-honesty-steering-step18-direction]]

<!-- wiki:semantic:end -->
