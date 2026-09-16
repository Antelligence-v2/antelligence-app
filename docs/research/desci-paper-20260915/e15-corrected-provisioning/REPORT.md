# E15 — corrected-provisioning partitioned DAGs

Model: `z-ai/glm-5.3-flash`; provider: `Nous Portal`; temperature: `0.0`; seeds: `101–120`.

| arm | runs | admission rate | success rate | redundant frac | tok/accepted | cost USD |
|---|---:|---:|---:|---:|---:|---:|
| solo_planner | 20 | 0.588 | 0.400 | 0.000 | 428.6 | 0.0030 |
| swarm_partitioned | 20 | 0.253 | 0.000 | 0.000 | 3902.2 | 0.0058 |
| swarm_partitioned_merged | 20 | 0.810 | 0.800 | 0.000 | 1380.5 | 0.0064 |

## Determinism

Admission was run twice per seed from the same serialized proposals; `determinism_all_pass`: **True**.

## Reference and cross-model note

`solo_planner` is the within-session reference. E12's anchor values are quoted for context only; the E15 verdicts do not compare against them (cross-model: `z-ai/glm-5.3-flash` here versus the E12 anchor model).

## Rejection breakdown

| arm | acyclicity | reachability | contradiction cascade | resource consistency | verifier feasibility |
|---|---:|---:|---:|---:|---:|
| solo_planner | 0 | 26 | 0 | 32 | 8 |
| swarm_partitioned | 0 | 37 | 0 | 51 | 30 |
| swarm_partitioned_merged | 0 | 0 | 0 | 30 | 0 |

Total matrix cost: `$0.015157`; passed-gate pre-test cost: `$0.000700`; failed pre-test attempts: `$0.001600`; total known cache cost: `$0.017457` (cap `$0.50`, pass: **True**).

## Predeclared verdicts (frozen before the matrix)

- **SUPPORTED (asymmetry theory):** partitioned redundancy stays ≈0% (≤ 0.01) AND partitioned successes ≥ 3/20 — coverage is recoverable once provisioning is correct.
- **SUPPORTED WITH REPAIR:** merged successes > partitioned successes AND merged successes ≥ half of solo's — the program's first genuine coordination win.
- **REFUTED (for real this time):** partitioned and merged successes both remain 0/20 while solo is high; only then is the coverage-collapse claim earned.

Observed predeclared verdict: **SUPPORTED_WITH_REPAIR** (partitioned 0 / 20, merged 16 / 20, versus solo 8 / 20; flags {'refuted': False, 'repair': True, 'asymmetry': False, 'half_solo_bar': 4}).

## Honest scope

The accepted subset is produced by canonical sorting, graph checks, contradiction propagation, fixture-resource checks, and verifier replay only; no model call occurs during admission. A zero unsafe-act count is a harness result, not a security proof. See `out/e15_summary.json` for tokens, paired exact sign tests, graph shape, and budget accounting.
