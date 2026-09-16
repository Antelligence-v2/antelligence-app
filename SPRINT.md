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
- [x] Deploy ExperienceRegistry + TumorIntel to Base Sepolia testnet — TumorIntel at `0xd1cfa5b9994e06cc18a21dc18fb9d20a3c02238b`, SP1 Gateway wired
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

## Phase 6 — API & Developer Experience [CURRENT]
Goal: Make the simulation usable by external services and improve developer ergonomics.

- [ ] REST API server: create `backend/api_server.py` using FastAPI with POST /simulate (takes config JSON, returns run_id + metrics), GET /runs/{run_id} (returns stored results), GET /health. Add `tests/test_api_server.py` with 5+ tests using TestClient. Add `api-server` entry to pyproject.toml scripts.
- [ ] Unified CLI: create `backend/cli.py` using argparse with subcommands: `simulate --steps N --bots N --output results.json`, `benchmark --runs N --output benchmark.json`, `leaderboard --limit 10`. Add `tests/test_cli.py` with 3+ tests using subprocess. Add `cli` entry to pyproject.toml scripts.
- [ ] Colony heatmap: create `backend/visualize.py` with `render_pheromone_heatmap(biofvm, output_path)` that saves a matplotlib PNG of the trail pheromone field at current timestep, and `render_kill_rate_chart(results_list, output_path)` bar chart. Add `tests/test_visualize.py` with 3+ mock-based tests (no display required, just file output).
- [ ] Config schema: create `backend/config.py` with a pydantic `SimulationConfig` dataclass (fields: num_bots, grid_size, steps, pheromone_params, queen_enabled, seed). Add `load_config(path)` and `save_config(config, path)` functions. Add `tests/test_config.py` with 5+ tests including JSON roundtrip and validation errors.
- [ ] End-to-end integration test: create `tests/test_e2e.py` with a single test `test_full_simulation_pipeline` that runs a 10-step simulation (2 bots, 5x5 grid), checks metrics are non-null, verifies pheromone field has non-zero values after step 3, and asserts kill_rate is a float between 0 and 1.
