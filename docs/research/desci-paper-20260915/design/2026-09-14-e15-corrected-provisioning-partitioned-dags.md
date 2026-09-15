---
linked: 2026-09-15
---

# E15 — corrected-provisioning partitioned DAGs (cold-start brief)

Date: 2026-09-14. Status: NOT STARTED. Budget: ~$0.10. Route: **Nous Portal**.

## Why

E12 and E14 both ran `swarm_partitioned` with **3 agents against a 4-sample fixture**. The mapping
`my_sample = all_samples[agent_idx % len(all_samples)]` assigns agent-0/1/2 to sample-0/1/2, so
**sample-3 was never proposed by anyone** — and in a chain fixture sample-3 *is* the terminal
goal. Both arms' 0/20 execution success was therefore guaranteed by construction, and both
"coverage collapse" conclusions are confounded. Full write-up:
`mistakes/mistake-2026-09-14-e12-e14-partitioned-underprovisioned.md`.

E15 does exactly one thing: give the partitioned swarm enough agents to cover the fixture, then
re-run the arms that E12/E14 could not fairly test.

## Fix (do this first, before any model call)

In `run_e12.py` / `run_e14.py`'s partitioned path:
1. Spawn `len(all_samples)` agents (4 for these fixtures), not a hardcoded 3. Keep the existing
   `% len(all_samples)` as a safety modulo — it is correct once the count matches.
2. **Assert coverage at startup:** the union of agents' assigned slices must equal
   `set(all_samples)`. Fail loudly, do not warn.
3. Assert in the pretest that the goal node's sample is owned by at least one agent, and that at
   least one pretest seed reaches a non-zero execution success. A gate that cannot fail on the
   metric you care about is not a gate — E12 shipped a bug through two gates already.

## Run

Same fixtures, seeds 101–120, temperature 0, unchanged model-free admission gate.
Arms: `solo_planner`, `swarm_partitioned`, `swarm_partitioned_merged`.
Route: `https://inference-api.nousresearch.com/v1`, token from `~/.hermes/auth.json`
`providers.nous` **read fresh per call** (~1h TTL), `max_tokens >= 1500`.
Use one model for all arms — E14 used `z-ai/glm-5.3-flash` because DeepSeek exhausted its budget
on DAG prompts; either is fine as long as it is the same one across arms. State the model and
label any comparison with E12 as cross-model.

## Predeclared verdicts (freeze in DESIGN.md before the matrix)

- **Asymmetry theory SUPPORTED:** partitioned redundancy stays ≈0% AND success is materially
  above 0/20 — i.e. coverage is recoverable once provisioning is correct.
- **SUPPORTED with repair:** `swarm_partitioned_merged` success > `swarm_partitioned` success and
  within reach of solo's — that is the program's first genuine coordination win.
- **REFUTED (for real this time):** with correct provisioning, partitioned/merged success still
  ≈0/20 while solo is high. Only then is the "partial plans cannot merge" claim earned.
- Report `solo_planner` as the within-session reference; do not compare success to E12's anchors.

## Rules

- Review packet READ-ONLY. Cache keyed `(version, seed, arm, agent, step)`; one background
  process per arm; verify by results files, never notifications.
- Report spent cost honestly, including failed attempts.
- Write the vault session note the same session; if the verdict changes what the paper can claim,
  update the paper draft too.

<!-- wiki:semantic:start -->
## Related (auto-linked)

- [[2026-04-24-autonomy-master-plan]]
- [[BOARD-005-review-this-8-phase-autonomy-master-plan-for-the-o]]
- [[2026-04-24-autonomy-plan-board-review]]

<!-- wiki:semantic:end -->
