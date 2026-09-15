# E14 — deterministic merge/repair over partitioned DAGs

Model: `z-ai/glm-5.3-flash`; provider: `Nous Portal`; temperature: `0.0`; seeds: `101–120`.

| arm | runs | admission rate | success rate | redundant frac | tok/accepted | cost USD |
|---|---:|---:|---:|---:|---:|---:|
| solo_planner | 20 | 0.632 | 0.450 | 0.000 | 732.0 | 0.0034 |
| swarm_partitioned | 20 | 0.267 | 0.000 | 0.000 | 4183.1 | 0.0102 |
| swarm_partitioned_merged | 20 | 0.333 | 0.000 | 0.000 | 2725.3 | 0.0077 |

## Determinism

Admission was run twice per seed from the same serialized proposals; `determinism_all_pass`: **True**.

## Anchors vs E12 (cross-model)

E12 anchors: solo_planner = 55 accepted / 160 proposed, 323.4 tok/node, 3/20 success; swarm_partitioned = 20 accepted / 120 proposed, 0/20 success. This E14 run uses `z-ai/glm-5.3-flash`, so exact proposal reproduction is a cross-model check.

## Rejection breakdown

| arm | acyclicity | reachability | contradiction cascade | resource consistency | verifier feasibility |
|---|---:|---:|---:|---:|---:|
| solo_planner | 0 | 18 | 0 | 28 | 4 |
| swarm_partitioned | 0 | 27 | 0 | 36 | 25 |
| swarm_partitioned_merged | 0 | 36 | 0 | 35 | 9 |

Total matrix cost: `$0.021220`; passed-gate pre-test cost: `$0.000650`; failed pre-test attempts: `$0.034866`; total known cache cost: `$0.056736` (cap `$0.25`, pass: **True**).

Pretest recovery history from `out/api_cache_pretest.jsonl`: v1 (`deepseek`, 9 empty responses, `$0.017325`); v2 (`deepseek`, 5 calls before timeout, `$0.016641`); v3 (`glm`, 9 calls, `$0.000450`); v4 (`glm` with immediate-JSON prompt, 9 calls, `$0.000450`); v5 passed with 13 calls including four bounded correction attempts, `$0.000650`).

A separate uncached GLM model-selection probe returned a valid 415-character proposal for `$0.000050`; it is not in the cache total above. Known E14 spend including that probe is `$0.056786`.

## Predeclared verdicts (frozen before the matrix)

- **SUPPORTED:** merged redundancy ≈0%, success ≥ 3/20, and tokens/accepted ≤ 1.5× solo.
- **REFUTED:** merged success remains 0/20 or below solo; partial views are fatal.
- **PARTIAL:** redundancy is fixed but success remains below solo; report the gap exactly.

Observed predeclared verdict: **REFUTED** (merged success 0 / 20 versus solo 9 / 20).

## Honest scope

The accepted subset is produced by canonical sorting, graph checks, contradiction propagation, fixture-resource checks, and verifier replay only; no model call occurs during admission. A zero unsafe-act count is a harness result, not a security proof. See `out/e14_summary.json` for tokens, paired exact sign tests, graph shape, and budget accounting.
