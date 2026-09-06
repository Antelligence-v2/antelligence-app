# Antelligence

Antelligence is a DeSci swarm-intelligence product for tumor simulation, nanobot coordination, and verifiable research provenance. It models how small agents coordinate through local signals, records run provenance for later verification, and stages a proof pipeline that can evolve from mock artifacts to real cryptographic checks.

## What it does

- Runs a tumor simulation with configurable nanobot count, grid size, steps, seed, and pheromone parameters.
- Exposes a small simulation API for local apps and demos.
- Ships a CLI for single runs, benchmarks, and leaderboard reads.
- Records provenance for Base Sepolia workflows and proof artifacts.
- Distinguishes staged proof bundles from cryptographically accepted verification.

## Current product surface

### CLI

The Python package exposes these entry points:

- `antelligence`
- `antelligence-api`

Common commands:

```bash
uv run antelligence simulate --steps 100 --bots 10 --output out/run.json
uv run antelligence benchmark --runs 5 --steps 50 --bots 5 --output out/benchmark.json
uv run antelligence leaderboard --limit 10
uv run antelligence-api
```

### API

The project has two API servers:

**`backend/main.py`** — the full-featured API used by the frontend. Start it with:

```bash
PYTHON_DOTENV_DISABLED=1 ANTELLIGENCE_OFFLINE=1 \
ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX=0 CHAIN_READ_ENABLED=0 CHAIN_WRITE_ENABLED=0 \
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

Endpoints:

- `GET /health`
- `POST /simulation/run` — ant colony simulation
- `POST /simulation/compare` — queen vs no-queen comparison
- `POST /simulation/tumor/run` — tumor nanobot simulation
- `GET /simulation/tumor/runs/{run_id}` — retrieve the persisted tumor run and its staged provenance
- `POST /simulation/tumor/hunt` — tumor hunt v2
- `POST /simulation/tumor/compare` — tumor simulation comparison
- `GET /simulation/history` — simulation history
- `GET /simulation/compare/{id1}/{id2}` — compare two runs

**`backend/api_server.py`** — a minimal simulation API for programmatic use:

- `POST /simulate` — run a simulation with num_bots, grid_size, steps, seed
- `GET /runs/{run_id}` — retrieve stored results
- `GET /health` — liveness check

Example local flow (minimal API):

```bash
curl -X POST http://127.0.0.1:8001/simulate \
  -H 'content-type: application/json' \
  -d '{"num_bots": 8, "grid_size": 40, "steps": 60, "seed": 7}'

curl http://127.0.0.1:8001/runs/{run_id}
curl http://127.0.0.1:8001/health
```

### Proof and provenance

Antelligence already carries proof-shaped artifacts, but the product is explicit about what is and is not cryptographically real yet.

- `proof_origin=mock` means the proof bytes are staging placeholders.
- `proof_ok=false` must remain false for mock or staged artifacts.
- `trust_tier=proof_staged` means a proof bundle exists, not that it has been cryptographically accepted.
- `verified_onchain` is the only state that should be treated as cryptographically accepted.

The current on-chain transport is intentionally small and Base Sepolia oriented:

- `config_hash`
- `kill_rate_bps`
- `nanobot_count`
- `tumor_radius`
- `steps`

Richer provenance lives in the backend proof artifact alongside that tuple so replay, proof generation, and contract verification can stay pinned to the same run identity.

## Quick start

### 1. Install Python dependencies

Using `uv`:

```bash
uv sync --extra test
```

Or with `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
```

### 2. Run a local simulation from the CLI

```bash
uv run antelligence simulate --steps 25 --bots 6 --output out/example-run.json
```

This writes a JSON artifact containing:

- `config`
- `metrics`

### 3. Run the frontend-facing API locally

```bash
PYTHON_DOTENV_DISABLED=1 ANTELLIGENCE_OFFLINE=1 \
ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX=0 CHAIN_READ_ENABLED=0 CHAIN_WRITE_ENABLED=0 \
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8001
```

Use this server for the frontend. `antelligence-api` starts the separate minimal `/simulate` API; it does **not** implement the frontend routes. Do not run both on the same port. Offline mode rejects model/chain-dependent requests; select **Rule-Based** workers and keep LLM Queen disabled. No `.env` editing, credentials, paid model, wallet, or deployment is needed for this workflow.

### 4. Optional frontend

If you want the frontend dev server:

```bash
npm --prefix frontend ci
npm --prefix frontend run dev -- --host 127.0.0.1
```

Open `http://localhost:8081/tumor`. The frontend defaults to API port `8001`; override it at launch with `VITE_API_BASE_URL` if needed. Preview mode is deliberately read-only, not a simulation demo.

## Research limits

The current tumor runtime is a **synthetic 2D research model**, not validated treatment software, physical nanobot control, or a clinical efficacy predictor. Selecting unsupported patient geometry must fail rather than silently relabel a synthetic tumor. The field solver supports 2D/3D numerical tests; this is not a complete 3D tumor runtime.

Pheromone and Queen comparisons are paired synthetic experiments. A measured change is not evidence of clinical benefit, and `kill_rate` includes model cell death rather than isolated treatment-attributable effect. Real SP1/Groth16 proof generation, independently accepted chain outcomes, patient-derived end-to-end geometry, and the richer typed pheromone protocol remain separate milestones. See [the delivery and development map](docs/LOCAL_DELIVERY.md).

## Base Sepolia scope

Blockchain-facing provenance is currently scoped to Base Sepolia test workflows. The repo includes chain utilities for submission, verification, leaderboard reads, and verifier administration, but the public contract is conservative: staged artifacts are not marketed as finished cryptographic proof.

## Testing

Run the narrow test suite you need while keeping the `uv` cache in a writable directory:

```bash
mkdir -p /private/tmp/uv-cache
PYTHON_DOTENV_DISABLED=1 ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX=0 \
CHAIN_READ_ENABLED=0 CHAIN_WRITE_ENABLED=0 \
UV_CACHE_DIR=/private/tmp/uv-cache uv run --extra test pytest tests/ -q
npm --prefix frontend run lint
npm --prefix frontend run build
node --test frontend/tests/runtimeConfig.test.ts
# With both local servers running and Playwright available in python3:
python3 frontend/tests/tumor_browser.py
```

## Repository layout

- `backend/` - simulation engine, CLI, API, proof helpers, and chain integration
- `tests/` - Python test suite
- `frontend/` - local UI
- `blockchain/` - smart contracts and Hardhat project
- `docs/` - release notes, plans, and proof specification

## Status

This repo is being tightened toward a public-ready DeSci release. The current emphasis is simulation correctness, provenance clarity, proof lifecycle staging, and consistent local interfaces.
