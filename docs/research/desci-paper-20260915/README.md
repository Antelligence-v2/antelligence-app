# Antelligence DeSci paper + E12/E13/E14/E15 experiment package

Snapshot date: **2026-09-15**. This directory is the in-repo copy of the decomposable-science
(DeSci) manuscript and the experiment artifacts it cites, so the paper's claims travel with the
repository instead of living only on an external volume.

**Canonical memory** (design rationale, decisions, mistake write-ups) lives in the Obsidian vault
`~/Documents/Jarvis's Vault/`; the copies under `design/` here are convenience mirrors. The vault
is the source of truth for *why*; this directory is the source of truth for *what was run*.

## Files

| path | what |
|---|---|
| `PAPER-v0.md` | first draft (superseded) |
| `PAPER-v1.md` | verified v1 draft (E10 corrected, 10 `[TODO: verify]` markers) |
| `PAPER-v2.md` | **current** — E13 promoted to second headline; E12/E14 coverage marked confounded pending E15 |
| `e12-partitioned-dags/` | partitioned-DAG experiment (redundancy result stands, coverage confounded) |
| `e13-chain/` | chain-prioritized foraging, the second headline (complete, positive) |
| `e14-merge-repair/` | merge/repair layer (redundancy result stands, coverage confounded) |
| `e15-corrected-provisioning/` | corrected-provisioning re-run — **see `STATUS.md`; not yet complete** |
| `design/` | the four experiment briefs, the E12/E14 mistake note, and the program handoff |
| `MANIFEST.sha256` | sha256 of every file in this directory (excluding the manifest itself) |

## E13 — second headline (verified 2026-09-15)

Task family: chain-prioritized foraging (delivery order 0→1→2). Model `z-ai/glm-5.3-flash` via the
Nous Portal, 20 seeds, temperature 0, cache version `v14`. Numbers below were **recomputed from the
raw per-seed `results_*.json`** on 2026-09-15 and match the manuscript exactly.

| arm | sweep moves | reduction | successes | mean steps to success | W/L/T vs baseline | paired sign p |
|---|---:|---:|---:|---:|---:|---:|
| `baseline` | 3057 | — | 19/20 | 58.3 | — | — |
| `hive_memory` | 2655 | −13.15% | 19/20 | 54.5 | 16 / 2 / 2 | 0.000656 |
| `hive_memory_comm` | 2590 | −15.28% | 19/20 | 53.7 | 17 / 2 / 1 | 0.000364 |

Pre-registered bar: "reduction ≥ 5% AND one-sided p < 0.05" — cleared. Verdict:
`generality_supported_within_second_task_family`, with `cross_model_caveat: true`.

**Caveats carried into the paper:** (1) cross-model run — evidence of generality across model
*families*, not an exact replication of the E7v6/E9 anchors; (2) success at ceiling (19/20 in every
arm) — the family measures efficiency, not capability; (3) the 1-step paid pretest did not exercise
delivery by construction.

Known E13 spend: **$1.6884** against the operator-approved $2.50 cap (headroom $0.81).

## E12 / E14 — coverage conclusions CONFOUNDED

Both partitioned arms spawned **3 agents against a 4-sample fixture**
(`my_sample = all_samples[agent_idx % len(all_samples)]` maps to sample-0/1/2), so sample-3 — the
terminal goal in a chain fixture — was never proposed. The 0/20 execution-success outcomes were
**structurally guaranteed, not measured**. Their *redundancy* results stand; their *coverage*
conclusions are not quoted anywhere in the manuscript. See
`design/mistake-2026-09-14-e12-e14-partitioned-underprovisioned.md`.

E14 verified numbers: solo 86 accepted/136 proposed, 9/20, 732 tok/node; partitioned 32/120, 0/20;
merged 40/120, 0/20; 0 determinism failures; spend $0.0568.

## Provenance

Artifacts were copied from their working locations on 2026-09-15 and sha256-verified against source
(spot checks pass; full list in `MANIFEST.sha256`):

* experiments: `/Volumes/WD_BLACK/antelligence-experiments-20260911/{e12-partitioned-dags,e13-chain,e14-merge-repair,e15-corrected-provisioning}/`
* papers: `/Users/operator/antelligence-desci-paper-v{0,1,2}.md`
* design record: `~/Documents/Jarvis's Vault/{Briefs,mistakes,Sessions}/`

Large derived artifacts are deliberately **not** copied here: per-seed API caches
(`api_cache_*.jsonl`), `trajectories.jsonl`, and memory SQLite files stay on the external volume.

## Reproducibility

* Admission gate and fixtures: the review packet snapshot at
  `/Volumes/WD_BLACK/antelligence-review-20260911/review/hive-fit-20260911/` (READ-ONLY original).
* Routing: Nous Portal `https://inference-api.nousresearch.com/v1`, token from
  `~/.hermes/auth.json` (`providers.nous`), read fresh per call (~1 h TTL), `max_tokens >= 1500`.
  OpenRouter is exhausted (permanent HTTP 402) — do not retry it.
