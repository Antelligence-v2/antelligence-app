# Data Model: Phase 2 Proof/Provenance Completion

## SimulationRun

- `run_id`: stable run identity
- `config`: structured simulation request config
- `metrics`: measured simulation outcome fields
- `status`: completed/error state
- `provenance`: structured `RunProvenance`

Validation rules:
- Unknown config fields fail validation.
- Stored run retrieval returns the same provenance shape as initial response.

## RunProvenance

- `run_id`
- `config`
- `config_hash`
- `trust_tier`
- `verification_status`
- `proof_lifecycle`
- `onchain`
- `proof_bundle`

Validation rules:
- `config_hash` must match the proof bundle/on-chain public values payload.
- `trust_tier` cannot outrank verification evidence.

## ProofBundle

Required fields from current verifier contract:
`run_id`, `artifact_hash`, `config_hash`, `public_values`, `proof_bytes`, `proof_system`, `proof_format`, `proof_origin`, `proof_artifact_version`, `public_values_schema_version`, `prover_status`, `is_mock`, `program_version`, `proof_boundary_version`, `trace_commitment`, `witness_commitment`, `adapter`, `transport_metadata`.

State rules:
- Mock bundles remain non-cryptographic.
- Proof bytes can be schema-valid while still not accepted on-chain.
- Transport commitment binds public values, proof bytes, origin/status, and program version.

## VerificationStatus

- `schema_ok`
- `integrity_ok`
- `replay_ok`
- `proof_ok`
- `onchain_ok`
- `is_trusted_tier`

State rules:
- `proof_ok` requires on-chain acceptance.
- `is_trusted_tier` is true only for non-mock accepted evidence tiers.

## ProofLifecycle

Allowed stages:
1. `bundle_created`
2. `proof_pending`
3. `proof_generated`
4. `submitted_onchain`
5. `verified_onchain`

State rules:
- Only `verified_onchain` is final.
- `proof_generated` is staged and awaiting verifier acceptance.

## DeterministicChainBuffer

- `events`: sorted `ChainBufferEvent` list
- `digest`: SHA-256 of canonical JSON bytes

`ChainBufferEvent` fields:
- `chain_id`
- `source`
- `block_height`
- `tx_index`
- `log_index`
- `payload`

State rules:
- Arrival order, wall clock, and process state are excluded.
- Live RPC reads are not replayable unless same-height determinism is separately proven.

## CompilerTicketTemplate

Fields used by the daily plan:
- `task_id`
- `title`
- `objective`
- `files_allowed`
- `files_forbidden`
- `test_file`
- `test_name`
- `verification_command`
- `red_step`
- `green_step`
- `max_changed_files`
- `success_contract`

State rules:
- Daily tickets must match existing keys or be listed as `NEEDS_TEMPLATE`.
