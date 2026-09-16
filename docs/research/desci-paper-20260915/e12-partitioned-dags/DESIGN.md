# E12 — partitioned-view swarm DAGs

Date: 2026-09-13. Status: PRETEST PENDING. Budget cap: **$1.00**.

## Hypothesis

Coordination machinery's value is a function of *information asymmetry*, not of the
machinery. E11 showed three agents with identical views produce 63.3% redundant nodes
at 2.7x solo tokens per accepted node with no success lift. E10 showed the communication
layer only has value when information is genuinely partitioned. E12 tests whether
partitioning the proposers' views collapses the redundancy.

## Design

Reuse E11's harness verbatim from
`/Volumes/WD_BLACK/antelligence-experiments-20260911/e11-task-dags/run_e11.py`.
Same fixtures (`chain`, `fork`, `impossible`), same seeds 101–120, temperature 0,
same model `nousresearch/hermes-4-405b` via OpenRouter, same model-free admission gate
(**do not touch admission**).

Route/model defaults derived from E11's verified result files
(`out/e11_summary.json`, `out/pretest.json`), not from copied source defaults.

### Arms

- `solo_planner` — anchor. One agent, full fixture view. Must reproduce E11: 49 accepted
  / 160 proposed, 361.1 tok/node, 2/20 success.
- `swarm_proposal` — anchor. Three agents, identical full fixture views. Must reproduce
  E11: 63.3% redundant, 993.2 tok/node, 3/20 success.
- `swarm_partitioned` — **new**. Three agents; each receives only a disjoint subset of the
  fixture. Agent *i* sees the public protocol/goal/revision plus `slot_zones` and `rules`,
  plus the `requirements` and `prerequisites` entries for its own assigned sample only.
  Agents do not see each other's sample data. The admission gate is unchanged and still
  receives all proposals; merge is deterministic exactly as in E11.

### Predeclared metrics

Recorded before the matrix runs; no post-hoc additions:

- `redundant_node_fraction`
- `tokens_per_accepted_node`
- `admission_rate`
- `execution_successes`
- `determinism_failures`
- `proposed_nodes`

### Predeclared verdicts

- **Supports the theory:** redundancy falls well below the 63.3% anchor (target under ~30%)
  AND tokens per accepted node lands within ~1.5x solo WITHOUT losing execution success.
- **Refutes the theory in the DAG layer:** redundancy stays near 63% despite partitioned
  views. Reported as the honest negative; it bounds the asymmetry claim to the evidence layer.
- **Inconclusive:** anything in between, or success collapses. Said so, not rounded up.

## Hard rules

- `/Volumes/WD_BLACK/antelligence-review-20260911/` is READ-ONLY.
- Route/model defaults from latest verified predecessor result file.
- Cache API responses keyed `(version, seed, arm, agent, step)`.
- Pre-test gate first (few seeds, parseable proposals); report before full matrix.
- One background process per arm, own cache, own budget stop.
- Verify completion by process list + results files, never by notification alone.
- Report every number from artifact files; state anchor deltas honestly.
