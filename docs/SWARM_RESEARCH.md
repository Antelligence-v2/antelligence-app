# Swarm Research Workbench

A reusable LLM coordination experiment surface at **`/research`**, alongside the tumor Experiment Lab. This is the first multi-domain research increment—not a claim of clinical, financial, or publication readiness.

## What it makes measurable

| Protocol | Actual behavior | Call ceiling per selected model/task |
|---|---|---:|
| Single | One blind proposal per model; separate baseline rows | 1 |
| Independent vote | Three blind samples per model; deterministic strict majority | 3 |
| Peer review | Blind proposals → named peer critiques → revised proposals | 3 |
| Signal board | Task-scoped typed claims; two snapshot-isolated revision rounds; one-round TTL | 3 |

Model disagreement can abstain. Missing/invalid required messages cannot become consensus. All proposals, critiques, revisions and failures retain source attribution. A short **public** rationale is requested, not private chain-of-thought. No model-as-judge chooses the correct answer; deterministic reference scoring is separate from inference.

Protocol ensembles have equal call/output-token ceilings, **not equal input-token costs**. The single baseline is cheaper. Compare observed prompt tokens, output tokens and latency. One-model peer review is self-review, not model diversity. A proper scientific comparison still requires same-model and heterogeneous teams, repeated sampling seeds, token-matched controls, pre-registration and held-out replication.

## Public task tracks

`backend/research_fixtures/tasks.json` pins 200 projected tasks: 50 development + 50 evaluation examples per domain, selected in SHA256(source ID) order after recorded admission checks. Per-run subsets use SHA256(seed:task ID) ordering and record all selected IDs. Fixture byte hash is checked on every load.

- **PubMedQA**: abstract comprehension, choices yes/no/maybe. Official labeled corpus and public test-ID split, revision `1cbae8e92f72f20c8d3747cbb3bf5bc53554d997`. Only question/context reach agents, not `LONG_ANSWER`, labels or judgments. Attribution: Jin et al. (2019), https://pubmedqa.github.io/. Repository MIT notice does not establish blanket rights over underlying article abstracts.
- **FinQA-derived numeric answer QA**: question and full supplied text/table, not gold retrieval fields/program/explanation. Revision `0f16e2867befa6840783e58be38c9efb9229d742`; original dev/test remain disjoint. Explicit output units, finite Decimal arithmetic and absolute tolerance 0.01. Percentage answers use points; both percentage execution conventions are checked before admission. Ambiguous, nonnumeric, label-inconsistent and overlong cases are excluded **before inference**, with every ID/reason retained in the bundle audit. This is a deliberately selected subset and **not official FinQA program/execution accuracy**. Attribution: Chen et al. (2021), https://finqasite.github.io/; dataset CC BY 4.0, repository code MIT.

Public benchmark exposure to model training is unknown. Locally held-out does not mean model-unseen. No PHI, patient upload, clinical recommendations, finance execution, tools or arbitrary model URLs are accepted.

Rebuild with `PYTHONPATH=. python scripts/build_research_fixtures.py RAW_DIRECTORY`. Download only the four pinned URLs declared in the script, retain their hashes, and review any proposed fixture/hash update; the app never downloads data automatically. The full raw datasets live outside the source checkout.

## Accuracy requirements are evidence gates

Each domain/variant reports task successes over **all requested tasks**, answered accuracy, coverage, abstentions, invalid responses, transport failures, one-sided 95% Wilson lower bound and minimum 30 cases. Failed/missing evidence stays unknown; small samples remain insufficient. An all-abstain/all-error run cannot show answered accuracy as zero or 100%. The Wilson bound is approximate selected-sample evidence, not a future reliability guarantee; it is not simultaneous multiple-comparison correction.

A `meets_sample_target` label means only that this selected sample meets the chosen lower-bound threshold. It is not clinical/financial approval. Repeated browsing/tuning on the evaluation split invalidates independent evaluation claims; the app does not enforce an experiment preregistration/one-shot lock yet.

## Local model and execution boundary

`backend/research_models.py` pins two machine-local llama.cpp endpoints:

- `qwen`: Qwen3.8 27B abliterated Q3_K, `qwen38-abliterated`, loopback `:8301`.
- `phi4`: existing experimental Phi4 mini finance F16 fine-tune, `antelligence-phi4-finance`, loopback `:18302`.

Model aliases, paths, server build, template hash and local weight SHA256 observations are recorded. Local file hashes are **not attestation of server memory or training provenance**. Phi4's training source/benchmark exposure is unverified; do not infer a clean finance advantage. Catalog checks are read-only, not inference or model-quality endorsements. The old `:8090` service is a cloud proxy and is intentionally not in this local roster.

Explicit temperature, seed and output bounds; no credential lookup, environment proxies, redirects, cloud fallback, response replay or completion cache. Prompt caching is disabled for these comparisons. API cost is zero; electricity/hardware cost is not measured. One job at a time per shared SQLite target via an OS file lock, sequential calls, maximum 600 calls/3600 seconds, bounded HTTP timeout. Wall-time is checked between calls and limits the pending call timeout, not a hard real-time process kill.

Jobs start only on an explicit POST. SQLite persists admissions, reserved call counts, returned events and completed cells. A cancelled job stops after the current call; it never silently resumes. Restart marks orphaned running jobs interrupted under the same lock; historical completed reports remain unchanged. Unfinished tasks remain in denominators, and missing returned usage is unknown rather than measured zero.

`ANTELLIGENCE_RESEARCH_DB` optionally selects a separate research SQLite database; otherwise the existing run DB is used with a separate table. This permits retaining all historical tumor/experiment records unchanged.

Endpoints: `GET /research/catalog`, `POST /research/runs`, `GET /research/runs`, `GET /research/runs/<uuid>`, `POST /research/runs/<uuid>/cancel`. Existing simulation/Experiment Lab routes are retained. Preview makes no private research requests.

## Development verification

Use the project test interpreter and offline/chain-denied flags. Focused suite:

```sh
PYTHON_DOTENV_DISABLED=1 ANTELLIGENCE_OFFLINE=1 ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX=0 CHAIN_READ_ENABLED=0 CHAIN_WRITE_ENABLED=0 \
  python -m pytest tests/test_swarm_core.py tests/test_research_data.py tests/test_research_models.py tests/test_research_api.py -q
node --experimental-strip-types --test frontend/tests/*.test.ts
npm --prefix frontend run build
npm --prefix frontend run lint
```

`frontend/tests/research_browser.py` is **live local-model** acceptance, not a mocked UI test. It starts 40 real model calls unless `RESEARCH_RUN_ID` selects existing evidence. Requires an interpreter with Playwright/Chromium, `ANTELLIGENCE_E2E_OUTPUT`, and optional frontend/API URLs. Do not confuse the test venv with the separate browser interpreter. No metered calls are needed.

## Vision contribution and unfinished research

The signal board operationalizes typed, expiring agent communication; peer critique makes agent-to-agent review inspectable; model/protocol controls and evidence gates begin the reproducibility layer beyond tumor physics. Blockchain remains a future commitment/provenance adapter, not the hot communication bus. `proof_ok` remains false.

Next research stages are selective escalation, fair token-budget/adaptive policies, multiple framework adapters against this same task contract, domain expert adjudication of references, independent unseen evaluations, failure-slice analysis, calibration and adversarial robustness. Patient-aware 3D simulations, learned episodic Queen, signal reinforcement/conflict policies and actual cryptographic verification are separate uncompleted vision items. Do not replace them with a benchmark dashboard and call the whole platform finished.
