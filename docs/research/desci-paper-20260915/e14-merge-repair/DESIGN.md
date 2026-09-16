# E14 — deterministic merge/repair over partitioned DAG proposals

Date: 2026-09-14. Status: pretest pending. Budget cap: `$0.25` incremental.

## Frozen design

Reuse E12's fixtures, seeds `101–120`, temperature `0.0`, and unchanged model-free
admission gate. the Nous route is used because OpenRouter is exhausted; comparisons with E12 are explicitly cross-model
(`z-ai/glm-5.3-flash` versus the E12 anchor).

Arms:

- `solo_planner`: full fixture view, one proposal per seed. Anchor target: 55 accepted /
  160 proposed, 3/20 execution success, 323.4 tokens/accepted node.
- `swarm_partitioned`: unchanged E12 partitioned view, three proposals per seed. Anchor
  target: 20 accepted / 120 proposed, 0/20 execution success, 2059.3 tokens/accepted node.
- `swarm_partitioned_merged`: take the same partitioned proposals, without another model
  call; union them into one canonical proposal, prefix local IDs, rewire each reserve node
  to depend on the place nodes of its declared prerequisite samples, choose the canonical
  final goal, and pass the result to the unchanged admission gate.

## Predeclared metrics

`accepted_nodes`, `proposed_nodes`, `redundant_node_fraction`,
`tokens_per_accepted_node`, `execution_successes`, `determinism_failures`, and
`unsafe_act_count`. Admission is run twice per seed from the exact serialized proposal;
byte differences are determinism failures.

## Predeclared verdicts

- **SUPPORTED:** merged redundancy is approximately 0%, execution success is at least
  3/20 (matching solo), and tokens/accepted is at most 1.5 × 323.4.
- **REFUTED:** merged execution remains 0/20, or is below solo; partial views are fatal
  and the missing structure is not recovered by deterministic merge.
- **PARTIAL:** redundancy is fixed but success remains below solo; report the gap exactly.

The gate must assert admission, not only parseability: the 3-seed × 3-agent pretest must
parse all nine proposals, run the merged repair, and show at least one admitted node per
seed. A parse-only gate is invalid.

## Cost and evidence

Each arm has its own versioned cache and budget stop. The review packet is read-only.
Every reported number is recomputed from `out/results_<arm>.json`; trajectory or process
notifications are not primary evidence. Failed attempts and costs are reported rather than
silently discarded.
