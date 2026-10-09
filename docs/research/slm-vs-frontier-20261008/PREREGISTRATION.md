# SLM vs Frontier Benchmark — preregistration

- **Registered:** 2026-10-08 UTC, before any evaluation-split model call.
- **Question:** Does Antelligence coordination close the accuracy gap between small local models and frontier models, and at what cost?
- **Scope:** Research-QA engine protocols only for the first executable benchmark slice. The pinned `evaluation` split is used as held-out data; no gold labels enter prompts. Foraging/task-DAG are not included in this reduced run because the existing LLM hooks are not registered as equivalent benchmark cells here.
- **Tasks:** `backend/research_fixtures/tasks.json`, `split=evaluation`, PubMedQA medical and FinQA finance, all 100 task IDs. Development split is smoke-only.
- **Arms:** `single`, `independent_vote`, `signal_board`, `evidence_exchange`, `evidence_isolated`, `solo_refine`. Protocol definitions are those in `antelligence/worlds/research_qa/world.py`: calls/task = 1, 3, 9, 6, 6, 6 respectively.
- **Tiers:** small local models pinned in `backend/research_models.py` when admitted; frontier models accessed only through existing operator subscriptions/credits. The run records requested and served IDs.
- **Models:** record exact endpoint/model identity, local quantization and full weight SHA-256 in the run manifest. Gemma 4 E4B is included only if a genuinely local pinned endpoint/weight exists.
- **Seeds:** seeds 0, 1, 2 where budget permits. Temperature is fixed at 0.0, so seeds may not alter deterministic outputs; seeds are retained for protocol reproducibility and are not treated as independent stochastic replications.
- **Primary metrics per cell:** accuracy over all requested tasks (failures, invalid, missing, and abstentions remain in denominator); answered accuracy and coverage; abstention/invalid/transport-failure counts; one-sided 95% Wilson lower bound using z=1.6448536269514722; prompt/output tokens; measured latency; dollar cost (local $0, frontier provider-reported cost or subscription).
- **Analysis:** paired comparisons on identical task IDs using `antelligence/experiments/stats.py` `paired_comparison` and exact sign test. Report headline (a) small swarm vs small single, (b) small swarm vs frontier single, (c) accuracy per dollar. Agreement is not correctness.
- **Stop rules:** stop a provider on exhausted subscription/credits; stop local launch on memory gate defer; stop the benchmark on malformed infrastructure or secret exposure; do not tune on evaluation labels; do not silently resume an interrupted run. Reduced designs and deviations are reported, not rewritten here.
- **Raw evidence:** append-only JSONL call ledger and per-cell raw run bundles/pointers with SHA-256 hashes. No patient-derived/private data; only public benchmark fixture content.

This file is immutable after the first held-out model call. Deviations belong in `REPORT.md`.
