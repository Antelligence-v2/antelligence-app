# Feature Specification: Phase 2 Chain Reader, Proof Lifecycle, and Trust Tiers

**Feature Branch**: `checkpoint/2026-07-08-recovered-work`

**Created**: 2026-07-08

**Status**: Draft

**Input**: User description: "Install spec-kit and produce the first spec + daily plan for Antelligence from the actual repo state, Phase 2 chain-reader checkpoint 08cc279, and Antelligence loop notes."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Verify a run without trusting the runner (Priority: P1)

A researcher or reviewer receives an Antelligence run artifact and needs to verify what level of evidence it actually has: integrity only, replay checked, proof staged, or verified on-chain. They should be able to see structured proof/provenance status without reading code or trusting marketing copy.

**Why this priority**: This is the product's trust boundary. The checkpointed work already added proof lifecycle, verification, public-values schema checks, replay wiring, and fail-closed tests; completing it turns recovered work into an explicit product contract.

**Independent Test**: Generate or load a representative run/proof artifact, run verifier tests, and confirm the result differentiates `proof_staged` from `verified_onchain` with `proof_ok=false` unless the verifier-capable contract accepts it.

**Acceptance Scenarios**:

1. **Given** a mock/staged proof bundle with valid schema and transport commitments, **When** it is verified locally, **Then** it reports staged proof evidence and not final cryptographic acceptance.
2. **Given** malformed proof metadata, stale schema versions, fabricated origins, or unsupported trust tiers, **When** verification runs, **Then** the artifact fails closed and cannot promote leaderboard or API trust state.
3. **Given** an artifact whose public values encode the five on-chain fields, **When** decoding and round-trip checks run, **Then** the decoded payload matches the declared payload and config hash.

---

### User Story 2 - Replay and trace a simulation through the programmatic API (Priority: P1)

An autonomous loop or external tool calls the minimal `/simulate` API and later retrieves `/runs/{run_id}`. It needs a stable machine-readable path from request config to stored record, proof bundle, on-chain public values, and replay metadata.

**Why this priority**: The active A1 roadmap objective is structured simulation/provenance baseline. The latest loop note says the next A1 micro-step is enforcing a stable API provenance/error schema.

**Independent Test**: Use `backend/api_server.py` tests to submit a run, retrieve it from SQLite-backed storage, and compare config/provenance fields without using prose or frontend-only routes.

**Acceptance Scenarios**:

1. **Given** a valid `/simulate` request, **When** the run completes, **Then** the response includes `run_id`, `metrics`, and `provenance` with config hash, trust tier, verification status, proof lifecycle, on-chain fields, and proof bundle.
2. **Given** an invalid request with unknown nested fields or malformed config, **When** the API rejects it, **Then** the error is structured and machine-readable.
3. **Given** a stored run, **When** `/runs/{run_id}` is called after process memory is empty, **Then** the persisted record returns the same config, metrics, and provenance shape.

---

### User Story 3 - Use chain-reader evidence without claiming live determinism (Priority: P2)

An agent wants to include chain observation evidence in simulation provenance. It needs deterministic fixture-buffer behavior now, and a clear gate before any live RPC read is treated as replayable.

**Why this priority**: Checkpoint 08cc279 introduced `backend/chain/deterministic_buffer.py` and chain-reader determinism tests. The next safe step is to finish the contract around fixture determinism and live-read risk, not to expand live chain execution.

**Independent Test**: Run deterministic chain-reader tests with reordered fixture events and verify identical canonical digests, trust-tier labels, and provenance checksums.

**Acceptance Scenarios**:

1. **Given** identical chain events in different arrival orders, **When** they are canonicalized, **Then** the buffer digest is identical.
2. **Given** missing or stale observer/finality heights, **When** a chain trust label is derived, **Then** it degrades to local or observer trust rather than finality.
3. **Given** live Base Sepolia RPC has not passed same-height determinism checks, **When** a plan references chain reads, **Then** it uses snapshot fixtures or labels live reads as untrusted observations.

---

### User Story 4 - Show proof status honestly in the frontend and leaderboard (Priority: P3)

A demo viewer sees Antelligence proof status in frontend or leaderboard surfaces. The UI should make staged proof visible without implying production cryptographic verification.

**Why this priority**: Useful for demos, but lower priority than backend proof semantics and API traceability. It should consume the same trust labels rather than creating a parallel copy system.

**Independent Test**: Build frontend proof-status copy and leaderboard tests; verify staged proof wording survives score creation/retrieval.

**Acceptance Scenarios**:

1. **Given** a staged proof run, **When** it appears in leaderboard records, **Then** the trust tier and verification status survive creation and retrieval.
2. **Given** a frontend preview surface, **When** it shows proof status, **Then** it says staged/non-production unless the backend reports `verified_onchain`.

### Edge Cases

- Malformed proof bundle metadata MUST fail closed and report schema errors.
- Mock proof flags MUST not be laundered into non-mock trust tiers.
- Replay mismatch MUST not promote to proof or on-chain trust.
- Zero-effect runs MUST remain in aggregate metrics without inflating trust or verification state.
- Missing chain config, missing verifier address, or failed `cast call` MUST produce staged/unverified status, not final proof.
- `backend/main.py` and `backend/api_server.py` route contracts MUST not be confused in docs or tests.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST preserve a single proof lifecycle vocabulary: `bundle_created`, `proof_pending`, `proof_generated`, `submitted_onchain`, `verified_onchain`.
- **FR-002**: System MUST expose trust tiers that distinguish integrity checks, replay checks, staged proof bundles, mock evidence, unsupported claims, and verified on-chain acceptance.
- **FR-003**: System MUST keep `proof_ok=false` unless on-chain verifier acceptance is observed through the configured verifier-capable TumorIntel contract.
- **FR-004**: System MUST validate proof bundle schema fields, proof artifact version, proof system/format, public-values schema version, program version, proof boundary version, public-values decoding, and transport commitment consistency.
- **FR-005**: System MUST keep the on-chain public-values payload limited to `config_hash`, `kill_rate_bps`, `nanobot_count`, `tumor_radius`, and `steps` unless a separate contract-authority decision changes it.
- **FR-006**: System MUST store richer provenance off-chain in proof bundle metadata, including run identity, artifact hash, config hash, trace commitment, witness commitment, adapter, mock/prover status, and transport metadata.
- **FR-007**: System MUST let `/simulate` and `/runs/{run_id}` expose a stable structured provenance shape with config, config hash, trust tier, verification status, proof lifecycle, on-chain fields, and proof bundle.
- **FR-008**: System MUST reject malformed or unknown config fields with machine-readable validation errors.
- **FR-009**: System MUST canonicalize fixture chain events by deterministic chain identifiers rather than arrival order, wall clock, or process state.
- **FR-010**: System MUST label deterministic chain observations by available evidence (`T1 local`, `T2 observer@height`, `T3 finality`) and degrade on missing/stale observation evidence.
- **FR-011**: System MUST not treat live RPC reads as replayable until same-height determinism has been verified and recorded.
- **FR-012**: Leaderboard and frontend surfaces MUST consume canonical trust/proof status and avoid separate weaker promotion rules.
- **FR-013**: Daily execution tasks generated from this spec MUST map to existing `_CORE_TICKET_TEMPLATES` keys or be flagged as `NEEDS_TEMPLATE`.

### Key Entities *(include if feature involves data)*

- **Simulation Run**: Request config, seed/run identity, metrics, status, persisted record, and provenance pointer.
- **Proof Bundle**: Off-chain evidence envelope with public values, proof bytes/status, mock flag, schema versions, commitments, adapter, and transport metadata.
- **Verification Status**: Structured booleans for schema, integrity, replay, proof, on-chain acceptance, and trusted-tier eligibility.
- **Trust Tier**: Human- and machine-readable label describing the strongest accepted evidence for a run.
- **Deterministic Chain Buffer**: Fixture-only canonical view of collected chain events keyed by chain id, source, block height, tx index, log index, and payload.
- **Compiler Ticket Template**: Whitelisted micro-ticket contract in `_CORE_TICKET_TEMPLATES` that defines files, test name, verification command, red step, green step, and success contract.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Full suite passes with `.venv/bin/python -m pytest` after spec-kit artifacts are committed.
- **SC-002**: Every tomorrow daily ticket either maps to one of the 16 existing compiler template keys or appears in the `NEEDS_TEMPLATE` list with a proposed template name.
- **SC-003**: A reviewer can identify the difference between `proof_staged` and `verified_onchain` from the spec without reading source code.
- **SC-004**: At least one 24-48h implementation slice advances the A1 structured simulation/provenance baseline rather than producing analysis-only work.
- **SC-005**: No plan item requires pushing, merging to main, public deployment, contract deployment, secret edits, or paid spend.

## Assumptions

- Current checkpoint commit `08cc279386c29144b3b094b80f836a933cf79d83` is the recovered baseline to preserve and plan from.
- `backend/main.py` remains the frontend-facing API; `backend/api_server.py` remains the minimal programmatic API.
- Base Sepolia remains the chain scope; no new chain deployment or authority change is in scope.
- Spec-kit was installed from release tag `v0.12.8` (`Specify CLI 0.12.8`, source commit `464d57fe30c72e9a88d279cc49834539ec989c03`).
- The compiler whitelist is `/Users/operator/openclaw-infra/scripts/antelligence_ticket_compiler.py` and currently contains 16 core templates.
