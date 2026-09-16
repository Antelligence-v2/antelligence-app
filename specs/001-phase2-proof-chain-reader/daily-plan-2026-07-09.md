# Daily Plan: 2026-07-09

## Objective

Ship the first post-spec implementation delta for A1: a stable, machine-readable simulation/provenance contract from minimal API run to stored record to proof/trust metadata. Keep every executable ticket mapped to the existing compiler whitelist.

## Ticket order and template mappings

1. **T1 — API trust status regression**
   - Template mapping: `verify-api-trust-tier-test`
   - Why first: protects `/simulate` and verifier/API status from representing staged proof as production crypto.
   - Focus command: `uv run --extra test pytest tests/test_verify.py -q`
   - Done when: named trust-tier response test is collected and passing.

2. **T2 — Proof bundle schema guard**
   - Template mapping: `proof-bundle-schema-guard`
   - Why second: locks required proof bundle fields and schema/transport versions before API copy depends on them.
   - Focus command: `uv run --extra test pytest tests/test_proof_adapter.py tests/test_verify.py -q`
   - Done when: proof bundle schema tests collect and pass.

3. **T3 — Shared memory proof boundary**
   - Template mapping: `shared-memory-proof-boundary`
   - Why third: binds config hash, transport metadata, and simulation-result commitments across proof submit paths.
   - Focus command: `uv run --extra test pytest tests/test_proof_transport_metadata_contract.py tests/test_submit.py -q`
   - Done when: shared-memory/proof commitment boundary test passes.

4. **T4 — Simulation replay fixture**
   - Template mapping: `simulation-replay-fixture`
   - Why fourth: ensures replay determinism exists before stronger trust labels consume replay evidence.
   - Focus command: `uv run --extra test pytest tests/test_simulation_replay.py tests/test_run_store.py tests/test_nanobot.py -q`
   - Done when: deterministic replay fixture test passes.

5. **T5 — Verifier trust tier copy**
   - Template mapping: `verifier-trust-tier-copy`
   - Why fifth: consolidates explicit mock/simulated/replay/staged/on-chain status language after the schema/replay base is stable.
   - Focus command: `uv run --extra test pytest tests/test_verifier_trust_tiers.py tests/test_verify.py tests/test_leaderboard.py -q`
   - Done when: explicit trust-tier tests collect and pass.

6. **T6 — Leaderboard trust propagation**
   - Template mapping: `leaderboard-trust-propagation`
   - Why sixth: ensures downstream records preserve trust state without stronger promotion logic.
   - Focus command: `uv run --extra test pytest tests/test_leaderboard.py tests/test_leaderboard_expansion.py -q`
   - Done when: leaderboard trust propagation tests pass.

7. **T7 — Chain-reader deterministic live-RPC gate**
   - Template mapping: `NEEDS_TEMPLATE: chain-reader-live-rpc-determinism-gate`
   - Why not executable tomorrow by compiler: existing templates cover proof, replay, leaderboard, config, frontend, runtime, and attestation seams; none allow `backend/chain/deterministic_buffer.py` plus `tests/test_chain_reader_determinism.py` as a chain-reader-specific live/snapshot determinism gate.
   - Proposed contract: fixture-first test proving live RPC reads are labeled untrusted unless a recorded same-height snapshot determinism probe exists.

8. **T8 — Minimal API provenance contract documentation/test seam**
   - Template mapping: `NEEDS_TEMPLATE: minimal-api-provenance-contract`
   - Why not executable tomorrow by compiler: `verify-api-trust-tier-test` touches `tests/test_verify.py`, `backend/chain/verify.py`, and `backend/api_server.py`, but no template directly owns `/simulate` -> `/runs/{run_id}` provenance persistence across `tests/test_api_server.py`, `tests/test_run_store.py`, `backend/api_server.py`, and `backend/run_store.py`.
   - Proposed contract: RED test for persisted run provenance shape, GREEN minimal schema/persistence guard, verification `uv run --extra test pytest tests/test_api_server.py tests/test_run_store.py -q`.

## Recommended tomorrow execution

Start with T1 or T2 if the loop must use only existing templates. If the operator wants the highest-leverage A1 schema delta, add `minimal-api-provenance-contract` first, then run it before T1.

## Full closeout gate

After any code/test delta:

```bash
.venv/bin/python -m pytest
```

No push. No main. Commit only on `checkpoint/2026-07-08-recovered-work` after the full gate passes.

## NEEDS_TEMPLATE list

- `chain-reader-live-rpc-determinism-gate`
- `minimal-api-provenance-contract`
