# Implementation Plan: Phase 2 Chain Reader, Proof Lifecycle, and Trust Tiers

**Branch**: `checkpoint/2026-07-08-recovered-work` | **Date**: 2026-07-08 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-phase2-proof-chain-reader/spec.md`

## Summary

Complete the recovered Phase 2 proof/provenance work by turning checkpoint `08cc279` into an explicit implementation contract: stabilize structured API provenance, harden staged proof and verifier trust tiers, preserve deterministic chain-reader fixtures, and route tomorrow's work through compiler-compatible micro-tickets. No push, no main, no deployment, no contract authority changes.

## Technical Context

**Language/Version**: Python >=3.10 from `pyproject.toml`; current local test runtime Python 3.11 via `.venv/bin/python`

**Primary Dependencies**: FastAPI, Pydantic, numpy, web3, pytest, uv, React/Vite frontend for proof-status copy

**Storage**: SQLite run store at `data/api_runs.sqlite3` for minimal API runs; fixture files/proof bundles for replay/provenance; no new production database

**Testing**: pytest (`.venv/bin/python -m pytest` full gate); focused pytest commands from `_CORE_TICKET_TEMPLATES`; frontend build only for frontend proof copy

**Target Platform**: Local macOS development and local API simulation; Base Sepolia provenance reads/writes only when explicitly configured and safe

**Project Type**: Python backend + CLI + FastAPI APIs + React/Vite frontend + Solidity contracts

**Performance Goals**: Keep proof/provenance checks lightweight enough for the existing 237-test suite to remain a routine full gate; deterministic chain buffer must be pure and fixture-only

**Constraints**: No push/main/deploy; no `.env`/secret edits; no contract deployment or authority change; no live RPC determinism claims without proof; all daily tickets must map to compiler templates or be flagged `NEEDS_TEMPLATE`

**Scale/Scope**: 16 compiler-compatible micro-ticket templates; one A1 daily execution card tomorrow; weekly work capped to 24-48h shippable slices

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Honest Proof Provenance: PASS — plan preserves `proof_staged` vs `verified_onchain` and requires fail-closed tests.
- Replayable Simulation Baseline: PASS — first weekly slice targets `/simulate` -> `/runs/{run_id}` -> provenance schema.
- API Server Separation: PASS — plan explicitly names `backend/main.py` as frontend-facing and `backend/api_server.py` as minimal API.
- Compiler-Compatible Micro-Deltas: PASS — daily plan maps tickets to `_CORE_TICKET_TEMPLATES` keys and flags gaps.
- Local-First Safety/Cost: PASS — no deployment, paid spend, authority change, or secret edits.

Post-design re-check: PASS. All design artifacts maintain the same safety and proof-honesty constraints.

## Project Structure

### Documentation (this feature)

```text
specs/001-phase2-proof-chain-reader/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── weekly-plan.md
├── daily-plan-2026-07-09.md
├── tasks.md
├── contracts/
│   ├── minimal-api-provenance.md
│   ├── proof-bundle-verification.md
│   └── deterministic-chain-buffer.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
backend/
├── api_server.py                 # minimal /simulate and /runs provenance surface
├── main.py                       # frontend-facing /simulation/* surface
├── simulation_replay.py          # deterministic replay seam
└── chain/
    ├── deterministic_buffer.py   # fixture-only chain reader buffer
    ├── proof_adapter.py          # proof bundle creation / adapter seam
    ├── proof_lifecycle.py        # lifecycle vocabulary
    ├── proof_spec.py             # public values + transport commitment contract
    ├── submit.py                 # submit lifecycle seam
    ├── verifier_admin.py         # verifier config/admin guard
    ├── verify.py                 # schema/replay/onchain verification and trust tiers
    └── leaderboard.py            # trust propagation

tests/
├── test_api_server.py
├── test_chain_reader_determinism.py
├── test_proof_adapter.py
├── test_proof_transport_metadata_contract.py
├── test_simulation_replay.py
├── test_submit.py
├── test_verifier_admin.py
├── test_verify.py
├── test_verify_trust_tiers.py
├── test_leaderboard.py
└── test_leaderboard_expansion.py

frontend/src/
└── components/pages touched only by `frontend-proof-status-copy`
```

**Structure Decision**: Keep the existing backend/chain ownership model. Do not introduce parallel proof, trust-tier, replay, or chain-reader abstractions; plans should strengthen existing modules and tests.

## Complexity Tracking

No constitution violations are required. The only complexity risk is dual API servers; this plan reduces that risk by naming the server surface in every slice.

## Phase 0 Research Summary

See [research.md](./research.md). Key decisions: keep staged proof local until on-chain acceptance, treat deterministic chain buffer as fixture-only, and use the compiler whitelist as the daily planning contract.

## Phase 1 Design Summary

See [data-model.md](./data-model.md), [quickstart.md](./quickstart.md), and [contracts/](./contracts/). The feature is complete when backend trust/provenance semantics, chain-reader determinism, and demo-facing copy all consume one canonical evidence model.
