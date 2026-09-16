# Tasks: Phase 2 Chain Reader, Proof Lifecycle, and Trust Tiers

**Input**: Design documents from `/specs/001-phase2-proof-chain-reader/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

## Phase 1: Setup

- [ ] T001 Confirm branch is `checkpoint/2026-07-08-recovered-work` and `specify --version` reports 0.12.8
- [ ] T002 Run `.venv/bin/python -m pytest` before code changes to confirm current baseline

## Phase 2: Foundational

- [ ] T003 [P] Map selected daily work to `_CORE_TICKET_TEMPLATES` before dispatch in `/Users/operator/openclaw-infra/scripts/antelligence_ticket_compiler.py`
- [ ] T004 Record any unmapped work as `NEEDS_TEMPLATE` in `specs/001-phase2-proof-chain-reader/daily-plan-2026-07-09.md`

## Phase 3: User Story 1 - Verify a run without trusting the runner (P1)

**Independent Test**: focused proof/verifier pytest plus full suite.

- [ ] T005 [P] [US1] Execute template `proof-bundle-schema-guard` in `tests/test_proof_adapter.py` and `backend/chain/proof_adapter.py`
- [ ] T006 [P] [US1] Execute template `verifier-trust-tier-copy` in `tests/test_verifier_trust_tiers.py` and `backend/chain/verify.py`
- [ ] T007 [US1] Execute template `proof-adapter-interface` in `tests/test_proof_adapter.py` and `backend/chain/proof_lifecycle.py`

## Phase 4: User Story 2 - Replay and trace a simulation through the programmatic API (P1)

**Independent Test**: minimal API and run-store pytest.

- [ ] T008 [P] [US2] Execute template `verify-api-trust-tier-test` in `tests/test_verify.py` and `backend/api_server.py`
- [ ] T009 [P] [US2] Execute template `simulation-replay-fixture` in `tests/test_simulation_replay.py` and `backend/simulation_replay.py`
- [ ] T010 [US2] Execute template `shared-memory-proof-boundary` in `tests/test_proof_transport_metadata_contract.py` and `backend/chain/proof_spec.py`
- [ ] T011 [US2] NEEDS_TEMPLATE `minimal-api-provenance-contract` for persisted `/simulate` -> `/runs/{run_id}` provenance shape in `tests/test_api_server.py`, `tests/test_run_store.py`, `backend/api_server.py`, and `backend/run_store.py`

## Phase 5: User Story 3 - Use chain-reader evidence without claiming live determinism (P2)

**Independent Test**: deterministic chain-reader tests and leaderboard trust tests.

- [ ] T012 [P] [US3] Execute template `leaderboard-trust-propagation` in `tests/test_leaderboard_expansion.py` and `backend/chain/leaderboard.py`
- [ ] T013 [P] [US3] Execute template `leaderboard-core-metric-integrity` in `tests/test_leaderboard.py` and `backend/chain/leaderboard.py`
- [ ] T014 [US3] NEEDS_TEMPLATE `chain-reader-live-rpc-determinism-gate` for `tests/test_chain_reader_determinism.py` and `backend/chain/deterministic_buffer.py`

## Phase 6: User Story 4 - Show proof status honestly in frontend and leaderboard (P3)

**Independent Test**: frontend build and leaderboard pytest.

- [ ] T015 [P] [US4] Execute template `frontend-proof-status-copy` in `frontend/src/components/PreviewModeBanner.tsx`
- [ ] T016 [P] [US4] Execute template `submit-proof-lifecycle-test` in `tests/test_submit.py` and `backend/chain/submit.py`

## Final Phase: Polish & Cross-Cutting Concerns

- [ ] T017 Run `.venv/bin/python -m pytest` and record live output in closeout
- [ ] T018 Update the spec README/plan if implementation discovers a new template gap

## Dependencies

- Setup (T001-T002) before all implementation.
- Foundational compiler mapping (T003-T004) before daily autonomous dispatch.
- US1 and US2 can run in either order if templates do not touch the same files.
- US3 depends on canonical trust/provenance labels from US1/US2.
- US4 depends on backend trust labels being stable.

## Parallel Opportunities

- T005/T006 can run in parallel if workers use separate worktrees.
- T008/T009 can run in parallel if they do not edit shared API/proof files.
- T012/T013 should not run in parallel in the same worktree because both may touch leaderboard tests/code.

## Implementation Strategy

MVP first: T008 + T010 or T005 + T006, depending on whether the operator prioritizes A1 API provenance or proof-tier hardening. Do not dispatch T011 or T014 until their templates exist.
