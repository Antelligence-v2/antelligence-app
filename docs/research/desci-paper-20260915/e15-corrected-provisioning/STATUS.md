# E15 — corrected provisioning: COMPLETE (2026-09-16)

**State: complete; verified from `out/results_*.json` independently of the summary (all match).**
Harness `run_e15.py` v4; full matrix over seeds 101–120 on `z-ai/glm-5.3-flash` via Nous Portal,
temperature 0, unchanged admission gate.

## Result

| arm | proposed | accepted | redundant fraction | execution successes | tokens/accepted | cost |
|---|---:|---:|---:|---:|---:|---:|
| `solo_planner` | 160 | 94 | 0.000 | 8/20 | 428.6 | $0.0030 |
| `swarm_partitioned` | 158 | 40 | 0.000 | 0/20 | 3902.2 | $0.0058 |
| `swarm_partitioned_merged` | 158 | 128 | 0.000 | 16/20 | 1380.5 | $0.0064 |

Verdict fired: **`SUPPORTED_WITH_REPAIR`** — merged successes (16) > partitioned (0) and ≥ half
of solo's (4). The merged arm assembled all 8 nodes and executed to verified success on every one
of the 16 solvable fixtures; impossible fixtures were correctly refused; admission was
byte-identical on reruns; 0 unsafe acts; paired exact sign test merged-vs-solo 8 W / 0 L / 12 T
(p=0.0078). This resolves the E12/E14 coverage question and supersedes their confounded
coverage conclusions.

## Harness history (each iteration recorded in `DESIGN.md` before the relevant run)

- v1: provisioning fix only (one agent per sample + coverage asserts) — never ran live.
- v2: + claim serialization ("take turns" edges for over-subscribed resources). Live pretest
  failed: same-zone agents collided on slots on all three seeds.
- v3: + delegator-assigned slots (`my_slot` in each slice). Live pretest failed: `resource`-field
  mis-transcriptions (the prompt never stated that field's contract).
- v4: + explicit `resource`-field contract in all prompts (symmetric with solo). Pretest passed
  3/3 (8/8 nodes, success); the matrix ran.

Total spend across all versions: **$0.0175** — matrix $0.0152, passed pretest $0.0007, failed
attempts $0.0016 (the v2/v3 pretest caches are retained as failed-attempt evidence, not deleted).
Budget cap was $0.50.

## Interpretation bounds

The recovery belongs to the full layer stack — delegator: samples, slots, field contracts; merge:
prerequisite edges, claim scheduling; no model call occurs during reconciliation — and it costs
3.2× solo tokens per accepted node, so the claim is recovered coverage and executability, not
token efficiency. Single cross-model run; proposal stochasticity at temperature 0 (19/20
reproducibility measured earlier) means per-seed outcomes are samples.

## Files

`run_e15.py` (final harness), `DESIGN.md` (pre-registration + fix record), `REPORT.md` (generated),
`e15_summary.json` (exact aggregate), `results_*.json` (per-seed), `pretest.json`, `selftest.json`.
Large derived artifacts (API caches, trajectories) remain on the external volume.
