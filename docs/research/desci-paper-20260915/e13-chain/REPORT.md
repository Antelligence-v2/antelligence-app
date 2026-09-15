# E13 — chain-prioritized foraging

## Status

**Complete and evaluable.** The full 20-seed × 3-arm matrix ran fresh on the Nous Portal with cache
version `v14`, model `z-ai/glm-5.3-flash`, temperature `0.0`, and `max_tokens=1500`.
The previous mixed `v13` caches were not used by the new run. The old cache replay is reported
separately below as a historical cross-model comparison.

## Gates

- Oracle: **20/20 seeds solvable**, mean 33.0 steps, maximum 60 steps; `out/oracle.json`.
- Paid pre-test: **passed**, 3 seeds × 3 arms × 3 agents, 0 parse errors, 12 communication
  events; `out/pretest.json`.
- The pre-test exercised the real arm loop with an isolated `v14-pretest` cache. Total provider
  cost across the failed longer gate attempt and the passed replacement gate was `$0.002870371`.
  The earlier hung attempt is included in that cost; it is not hidden.

## Full matrix — authoritative harness metric

| arm | sweep moves | mean steps to success | success | deliveries | parse errors |
|---|---:|---:|---:|---:|---:|
| baseline | 3,057 | 58.3 | 19/20 | 59 | 2 |
| hive_memory | 2,655 | 54.5 | 19/20 | 59 | 2 |
| hive_memory_comm | 2,590 | 53.7 | 19/20 | 59 | 1 |

`steps` is the mean `steps_to_success` over successful runs. The single failure in every arm was
seed 115, which delivered 2/3 foods within the 120-step limit. The authoritative primary metric
is `sweep_moves`; trajectory action tallies are not substituted for it.

## Paired sign tests

| comparison | hive better | hive worse | ties | non-tied | one-sided p |
|---|---:|---:|---:|---:|---:|
| hive_memory vs baseline | 16 | 2 | 2 | 18 | 0.0006561 |
| hive_memory_comm vs baseline | 17 | 2 | 1 | 19 | 0.0003643 |

Aggregate reductions versus baseline:

- `hive_memory`: 3,057 → 2,655, **−13.15%**.
- `hive_memory_comm`: 3,057 → 2,590, **−15.27%**.

The communication mechanism operated in the comm arm: `transport_events = 380` in the raw
results. This is an arm-level transport counter, not a claim that communication independently
caused the entire difference.

## Pre-registered verdict

**Generality supported within this second task family.** Hive memory clears both frozen criteria:
reduction is at least 5% and the one-sided sign-test p-value is below 0.05. The headline may retain
its cross-family wording, but the result is a cross-model replication: the E13 run used
`z-ai/glm-5.3-flash` through Nous, whereas the E7v6/E9 anchors used other model/route conditions.
It should not be presented as an exact same-model reproduction of the anchor aggregates.

## Historical cross-check — kept separate

The old `v13` cache entries for seeds 101–112 were replayed offline using the historical
`hermes-4-405b`/OpenRouter harness semantics. They are not merged into the new v14 table:

| arm | sweep moves | success | deliveries | parse errors |
|---|---:|---:|---:|---:|
| baseline | 1,825 | 12/12 | 36 | 0 |
| hive_memory | 1,667 | 12/12 | 36 | 0 |
| hive_memory_comm | 1,609 | 12/12 | 36 | 0 |

These numbers are a labelled 12-seed historical cross-model comparison only. The historical
replay's estimated provider cost is `$0.683069`; replay cost is not new spend.

## Spend

| component | provider cost |
|---|---:|
| prior mixed v13 E13 cache | $1.143507140 |
| prior pre-test probe | $0.000116400 |
| v14 pre-test attempts (all cache rows) | $0.002870371 |
| v14 full matrix (all cache rows) | $0.541859579 |
| **total known E13 spend** | **$1.688353490** |
| approved cap | $2.500000000 |
| headroom | $0.811646510 |

Each matrix arm remained below the approved `$0.80` per-arm hard stop; v14 provider costs were
`$0.191702720` baseline, `$0.176313261` hive-memory, and `$0.173843598` comm. Result-file
`totals.estimated_cost_usd` is a replay-accounted figure and is lower than the baseline cache
sum because interrupted attempts left valid v14 rows that were not replayed by the final pass;
all cache-row charges are included in the spend table above.

## Artifacts

- `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/results_baseline.json`
- `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/results_hive_memory.json`
- `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/results_hive_memory_comm.json`
- `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/e13_summary.json`
- `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/oracle.json`
- `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/pretest.json`
- `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/historical_e13_hermes_101_112.json`
- `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/historical_results_baseline_hermes_101_112.json`
- `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/historical_results_hive_memory_hermes_101_112.json`
- `/Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain/out/historical_results_hive_memory_comm_hermes_101_112.json`

The review packet at `/Volumes/WD_BLACK/antelligence-review-20260911/` was read-only throughout.
