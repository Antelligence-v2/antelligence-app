# Research: Phase 2 Chain Reader, Proof Lifecycle, and Trust Tiers

## Decision: Preserve `08cc279` as the recovered proof/provenance baseline

**Rationale**: The checkpoint added deterministic chain buffer, proof lifecycle/verification, verifier admin/config, API/runtime/replay, attestation dry-run behavior, release manifest, and 22 touched test/source files. Its commit message records `.venv/bin/python .venv/bin/pytest => 237 passed, 1 warning`.

**Alternatives considered**: Re-plan from old docs or rewrite proof architecture. Rejected because current source already carries the single-owner seams to harden.

## Decision: Minimal API provenance is the first weekly shipping slice

**Rationale**: The active A1 roadmap requires `/simulate` and related API paths to return structured validation/error details and trace a simulation from request config to stored run record to proof/provenance metadata. The 2026-07-08 A1 delta says the next micro-step is a stable API provenance/error schema.

**Alternatives considered**: Frontend status polish first. Rejected because UI copy is downstream of backend truth.

## Decision: Chain-reader work remains fixture deterministic until live RPC determinism is proven

**Rationale**: `backend/chain/deterministic_buffer.py` explicitly avoids RPC, clocks, and process-local state. Its risk note says Sepolia RPC same-height determinism must be checked before live use; otherwise use local archive/snapshot fixtures.

**Alternatives considered**: Query live Base Sepolia during proof/replay tests. Rejected because network variability would poison deterministic replay and unattended tests.

## Decision: Trust tiers are evidence labels, not status copy

**Rationale**: `backend/chain/verify.py` derives `verified_onchain` only from on-chain verifier acceptance. Staged bundles can pass schema and transport checks while `proof_ok` remains gated by on-chain acceptance.

**Alternatives considered**: Treat locally validated proof bundles as `proof_ok=true`. Rejected because it would violate proof honesty and the README contract.

## Decision: Daily tickets use the compiler whitelist as the contract

**Rationale**: `_CORE_TICKET_TEMPLATES` is the deterministic loop compiler. Broad work without a template produces `BLOCKED_COMPILE`; plans must map to existing keys or propose `NEEDS_TEMPLATE` entries.

**Alternatives considered**: Invent human-readable task ids in the spec. Rejected because that bypasses the loop compiler and creates dead tasks.

## Installed Spec Kit Version

- Latest release checked: `v0.12.8` (`Spec Kit - 0.12.8`, published 2026-07-08).
- Install command used: `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v0.12.8`.
- Installed CLI reported: `specify 0.12.8`.
- Resolved source commit: `464d57fe30c72e9a88d279cc49834539ec989c03`.
- Initialized repo with: `specify init --here --integration codex --force --ignore-agent-tools`.
