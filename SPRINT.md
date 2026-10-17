# Antelligence v2 — Sprint Roadmap

This file guides the dev-sprint-pipeline. The pipeline reads this to determine what to build next.
Work on the FIRST unchecked `[ ]` task in the CURRENT phase. Do NOT skip ahead to later phases.
Do NOT create new Solidity contracts unless the current phase requires it.
Do NOT write more tests for completed contracts — move forward.

## Phase 0 — Blockchain Foundation [COMPLETE]
- [x] ExperienceRegistry.sol — on-chain run registry with validator management
- [x] TumorIntel.sol — tumor intelligence contract with priority updates
- [x] AdvancedTumorIntel.sol — enhanced queries and analytics
- [x] ColonyMemory.sol — shared colony memory contract
- [x] FoodToken.sol — ERC20 resource token
- [x] Hardhat test suites for all contracts
- [x] GitHub Actions CI pipeline

## Phase 1 — Python Simulation Core [COMPLETE]
Goal: Get the existing Python simulation running with tests that pass in CI.
The simulation code already exists in `backend/` — fix and extend it, don't rewrite from scratch.

- [x] Fix imports: replace `openai`/`google.generativeai`/`mistralai` with LiteLLM client (use `requests` to call `http://host.orb.internal:4000/v1/chat/completions`)
- [x] Make `backend/biofvm.py` independently testable: add unit tests in `tests/test_biofvm.py` for substrate diffusion, decay, mass conservation (21 tests, all passing)
- [x] Make `backend/tumor_environment.py` independently testable: add unit tests in `tests/test_tumor_env.py` for voxel grid initialization and oxygen gradients (22 tests, all passing)
- [x] Make `backend/nanobot_simulation.py` independently testable: add unit tests in `tests/test_nanobot.py` for nanobot movement, chemotaxis, drug delivery (17 tests, all passing)
- [x] Add `pytest.ini` or `pyproject.toml` with test configuration and CI integration
- [x] Update GitHub Actions to run both `npx hardhat test` AND `pytest` in CI

## Phase 2 — Pheromone System Enhancement [COMPLETE]
Goal: Implement and validate the pheromone signaling system for decentralized coordination.

- [x] Implement trail pheromone field in `backend/biofvm.py` with secretion, diffusion, and exponential decay (D=1e-6, t½≈10min)
- [x] Implement alarm pheromone field with higher diffusion rate and faster decay (D=5e-6, t½≈3min)
- [x] Implement recruitment pheromone for zone exploration signaling (D=2e-6, t½≈7min)
- [x] Add chemotaxis logic to nanobots: follow trail gradient, avoid alarm zones (wired to trail_pheromone, alarm_pheromone, recruitment_pheromone substrates)
- [x] Unit tests: pheromone decay half-life, chemotaxis directionality, mass conservation (7 pheromone tests in test_biofvm.py)
- [x] Baseline comparison: bots without pheromones vs with pheromones (benchmark_pheromones.py — 0% improvement, expected: secretion logic not yet wired)

## Phase 3 — Blockchain Integration [COMPLETE]
Goal: Connect the Python simulation to the Solidity contracts for provenance.

- [x] IPFS pinning utility: hash simulation artifacts, pin to IPFS, return CID (backend/chain/ipfs.py, 11 tests, supports Pinata/local/dry-run)
- [x] Verification CLI: `python3 -m chain.verify <run_hash>` fetches CID, recomputes metrics, checks tolerance (8 tests)
- [x] Deploy ExperienceRegistry + TumorIntel to Base Sepolia testnet — originally TumorIntel at `0xd1cfa5b9994e06cc18a21dc18fb9d20a3c02238b`; later redeployed, backend default `0x925b455175eF932a9a0239090a94E593224CD8AB` (both have code on Base Sepolia; see truth-pass §4)
- [x] Submission CLI: `python3 -m chain.submit` creates attestation bundle (IPFS + on-chain data), ready for ZK proof submission (3 tests)
- [x] Leaderboard service: reads on-chain events, ranks policies by attested performance (6 tests, CLI with table + JSON output)

## Phase 4 — LLM Hierarchy (Queen/Worker) [COMPLETE]
Goal: Add the Queen agent for strategic coordination with measurable improvement over baseline.

- [x] Queen policy wrapper: episodic planner that adjusts bot parameters every K simulation steps (heuristic adaptation)
- [x] Worker agent parameters: exploration bias, trail secretion rate, alarm sensitivity (configurable, applied to workers each episode)
- [x] Queen uses LiteLLM (qwen3.5-35b or deepseek-chat) for strategic decisions (with heuristic fallback)
- [x] Evaluation harness: compare queen-guided vs fixed-policy across seeds and patients (evaluate_queen.py, 3 patient configs)
- [x] Pheromone secretion wired into nanobot behavior (commit 7b9a40d); success gate benchmark deferred to Phase 6 optimization

## Phase 5 — Experiment Ops & Evaluation [COMPLETE]
Goal: Automated experiment sweeps with reproducible, on-chain-attested results.

- [x] Batch runner: YAML config for seed × parameter grid sweeps (batch_runner.py, includes IPFS attestation)
- [x] Metrics collection: tumor-kill %, toxicity proxy, time-to-control, runtime/cost per run (integrated into batch runner)
- [x] Report generator: Markdown with tables, parameters, seed stats, links to Sepolia tx + IPFS CID (generate_report.py)
- [x] Attestation bot: re-runs k% of submissions for reproducibility spot-checks (attestation_bot.py, tested 2/2 pass)
- [x] Streamlit dashboard: live leaderboard from on-chain data (dashboard.py with 3 tabs)

## Phase 6 — API & Developer Experience [COMPLETE — verified 2026-10-08]
Goal: Make the simulation usable by external services and improve developer ergonomics.
Evidence: `uv run --extra test pytest tests/test_api_server.py tests/test_cli.py tests/test_visualize.py tests/test_config.py tests/test_e2e.py -q` → 64 passed (see `docs/status/2026-10-08-truth-pass.md`).

- [x] REST API server: `backend/api_server.py` (FastAPI: POST /simulate, GET /runs/{run_id}, GET /runs/{run_id}/config-trace, GET /health); `tests/test_api_server.py` (31 tests); script entry `antelligence-api` in pyproject.toml.
- [x] Unified CLI: `backend/cli.py` with `simulate`, `benchmark`, `leaderboard` subcommands; `tests/test_cli.py`; script entry `antelligence` in pyproject.toml (named `antelligence`, not `cli`).
- [x] Colony heatmap: `backend/visualize.py` with `render_pheromone_heatmap` and `render_kill_rate_chart`; `tests/test_visualize.py` (8 tests).
- [x] Config schema: `backend/config.py` with pydantic `SimulationConfig` (num_bots, grid_size, steps, pheromone_params, queen_enabled, seed), `load_config`, `save_config`; `tests/test_config.py`.
- [x] End-to-end integration test: `tests/test_e2e.py::test_full_simulation_pipeline`.

Also landed since this file was last updated (upstream PR #3, merged 2026-10-05): the `antelligence/` engine (kernel, providers, worlds foraging/task_dag/tumor/research_qa, experiments, provenance, /engine API). Full suite at W0: 905 passed, 2 skipped (BraTS/TCGA data absent).

## Phase 7 — Sprint 1, 2026-10-08 → 10-10 [COMPLETE — in review]
Each item is its own upstream PR (Antelligence-v2/antelligence-app).

- [x] W0 truth pass: `docs/status/2026-10-08-truth-pass.md`, this file reconciled
- [x] Provenance: config fingerprint + `metrics_hash` on simulate/run responses (fork PR #14)
- [x] W1 chain layer on ZKsync Era Sepolia (chain 300): zksolc compile + tests, `blockchain/scripts/deploy-zksync.js`, `blockchain/deployments/zksync-era-sepolia.json`, backend chain config driven by the deployments file, one end-to-end run at trust tier `proof_staged`, privacy audit, `docs/research/chain-options-20261008.md`, `docs/status/2026-10-08-chain-redeploy.md`
- [x] W1 security review fixes: "verified" bound to proven values, wrong-chain signing refused, verified records immutable (contract-side fix needs a redeploy)
- [x] W2 preregistered SLM-vs-frontier benchmark: `docs/research/slm-vs-frontier-20261008/` (PREREGISTRATION.md, bundles, results.csv, REPORT.md)
