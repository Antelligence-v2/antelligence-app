<!--
Sync Impact Report
Version change: template -> 1.0.0
Modified principles: placeholder principles -> Antelligence repo-state principles
Added sections: Runtime Surface & Safety Boundaries; Spec/Plan Governance
Removed sections: template placeholder sections only
Templates requiring updates: ✅ reviewed .specify/templates/spec-template.md; ✅ reviewed .specify/templates/plan-template.md; ✅ reviewed .specify/templates/tasks-template.md; ✅ reviewed .specify/templates/checklist-template.md; no template edits required for this first repo-specific constitution.
Follow-up TODOs: none
-->
# Antelligence Constitution

## Core Principles

### I. Honest Proof Provenance
Antelligence MUST distinguish staged evidence from cryptographically accepted verification. `proof_ok=false`, `proof_origin=mock`, `trust_tier=proof_staged`, and `verified_onchain` are load-bearing labels, not copy. A feature may improve proof bundle shape, replay checks, chain-reader determinism, verifier admin, or leaderboard propagation only if it preserves the invariant that no mock, simulated, replay-only, or locally staged artifact is presented as final cryptographic proof.

### II. Replayable Simulation Baseline
Every run that matters MUST be traceable from request config to stored run record to proof/provenance metadata. `/simulate`, `/runs/{run_id}`, CLI artifacts, replay fixtures, and proof bundles MUST carry structured machine-readable fields rather than relying on prose. Deterministic replay, config hashes, metric hashes, public values, and chain-buffer digests are first-class product data.

### III. Frontend Uses `backend/main.py`; Programmatic API Uses `backend/api_server.py`
The repository has two API servers. `backend/main.py` is the frontend-facing server with `/simulation/*` routes. `backend/api_server.py` is the minimal programmatic `/simulate` and `/runs/{run_id}` API. Specs, plans, tests, and runbooks MUST name which server they touch; starting the wrong server is a product bug, not operator error.

### IV. Test-First, Compiler-Compatible Micro-Deltas
Implementation work MUST be executable as small RED -> GREEN tickets. Daily autonomous tickets MUST map to an existing `_CORE_TICKET_TEMPLATES` key in `/Users/operator/openclaw-infra/scripts/antelligence_ticket_compiler.py`; if the work has no compiler template, the plan MUST say `NEEDS_TEMPLATE: <proposed-template-name>` instead of inventing a task id. Code changes require focused pytest or frontend build evidence, followed by the full suite before closeout.

### V. Local-First Safety and Cost Discipline
Antelligence work defaults to local simulation, local/free models, and Base Sepolia-only provenance. Specs MUST NOT require public deployment, contract deployment, authority changes, paid API cap increases, real patient data, live funds, or secret edits without explicit operator approval. On-chain public values stay minimal; richer provenance stays off-chain in proof metadata.

## Runtime Surface & Safety Boundaries

- Canonical product target: DeSci swarm intelligence for glioblastoma tumor simulation, with nanobot pheromone coordination and verifiable provenance.
- Python target: 3.10+ in `pyproject.toml`; current Hermes/macOS runtime is Python 3.11.
- Primary verification: `.venv/bin/python -m pytest` or `uv run --extra test pytest -q` depending on environment readiness.
- Contract public values remain: `config_hash`, `kill_rate_bps`, `nanobot_count`, `tumor_radius`, `steps`.
- Current canonical Base Sepolia TumorIntel address: `0x925b455175eF932a9a0239090a94E593224CD8AB`.
- No spec may treat a live RPC read as replayable until same-height determinism is verified; snapshot fixtures are acceptable.

## Spec/Plan Governance

Specs are expected to produce:

1. a stakeholder-facing `spec.md` that says what value and trust boundary changes are needed;
2. an implementation `plan.md` grounded in actual repo state;
3. a `weekly-plan.md` with shippable value in 24-48h slices;
4. a `daily-plan-YYYY-MM-DD.md` whose tickets map to compiler templates or explicit `NEEDS_TEMPLATE` entries;
5. validation artifacts that name exact commands and expected outputs.

## Governance

This constitution supersedes generic spec-kit defaults for Antelligence planning. Amendments require a written Sync Impact Report, semantic version bump, and a review of affected spec-kit templates and repo guidance files. Compliance is checked at every spec/plan/task generation pass and again before commit. If a plan conflicts with `VISION.md`, `RULES.md`, `ARCHITECTURE.md`, or Jarvis's Vault decisions, the stricter safety and proof-honesty rule wins unless the operator explicitly updates the authority boundary.

**Version**: 1.0.0 | **Ratified**: 2026-07-08 | **Last Amended**: 2026-07-08
