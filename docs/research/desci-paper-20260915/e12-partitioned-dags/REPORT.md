# E12 — partitioned-view swarm task DAGs

Model: `" + MODEL + "`; temperature: `0.0`; seeds: `101–120`; total cap: `$1.00`.

| arm | runs | admission rate | success rate | redundant frac | tok/accepted | cost USD |
|---|---:|---:|---:|---:|---:|---:|
| solo_planner | 20 | 0.344 | 0.150 | 0.000 | 323.4 | 0.0370 |
| swarm_proposal | 20 | 0.100 | 0.100 | 0.628 | 1099.4 | 0.1092 |
| swarm_partitioned | 20 | 0.167 | 0.000 | 0.000 | 2059.3 | 0.0546 |

## Determinism

Admission was run twice per seed from the same serialized proposals; `determinism_all_pass`: **True**.

## Anchors vs E11

E11 anchors (must reproduce within tolerance): solo_planner = 49 accepted / 160 proposed, 361.1 tok/node, 2/20 success; swarm_proposal = 63.3% redundant, 993.2 tok/node, 3/20 success.

## Rejection breakdown

| arm | acyclicity | reachability | contradiction cascade | resource consistency | verifier feasibility |
|---|---:|---:|---:|---:|---:|
| solo_planner | 0 | 59 | 0 | 32 | 14 |
| swarm_proposal | 0 | 74 | 0 | 38 | 18 |
| swarm_partitioned | 0 | 32 | 0 | 46 | 22 |

Total matrix cost: `$0.200845`; pre-test cost: `$0.008203`; total: `$0.209048` (cap pass: **True**).

## Predeclared verdicts (frozen before the matrix)

- **Supports the theory:** redundancy < ~30% AND tokens/accepted node within ~1.5x solo AND execution success not lost.
- **Refutes the theory in the DAG layer:** redundancy stays near 63% despite partitioned views.
- **Inconclusive:** anything in between.

## Honest scope

The accepted subset is produced by canonical sorting, graph checks, contradiction propagation, fixture-resource checks, and verifier replay only; no model call occurs during admission. A zero unsafe-act count is a harness result, not a security proof. See `out/e12_summary.json` for tokens, paired exact sign tests, graph shape, and budget accounting.
