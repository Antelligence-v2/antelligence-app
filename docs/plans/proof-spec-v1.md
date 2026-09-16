# Antelligence Proof Spec v1

Goal:
Lock the first canonical proof/public-values boundary so backend artifacts, replay verification, proof generation, and TumorIntel on-chain verification all commit to the same run identity.

Status:
- Current contract transport tuple remains:
  - config_hash
  - kill_rate_bps
  - nanobot_count
  - tumor_radius
  - steps
- This is the minimal on-chain payload for v1 transport.
- Additional provenance/versioning now lives alongside the tuple in backend proof artifacts.

Canonical identifiers:
- artifact_hash: canonical commitment to the full attestation artifact
- config_hash: canonical commitment to simulation config
- run_id: human/workflow identifier for the run
- public_values_schema_version: public-values-v1
- proof_artifact_version: proof-bundle-v1
- program_version: tumor-intel-proof-v1

Proof artifact semantics:
- proof_origin=mock means the proof bytes are staging placeholders only
- proof_ok must remain false for mock/staged proofs
- trust_tier=proof_staged means a proof-shaped artifact exists but has not earned cryptographic trust
- verified_onchain is the only state that should be treated as cryptographically accepted

Planned SP1/Groth16 evolution:
- keep the current tuple as the contract-decoded transport payload for now
- make SP1 prove over a richer witness that is bound to:
  - config_hash
  - artifact_hash / trace_commitment
  - witness_commitment
  - program_version
- emit Groth16 proof bytes for the verifier contract

Warnings:
- Do not treat presence of proof bytes as proof validity
- Do not let public-values schema drift independently from contract decoding
- Do not let replay verifier and proof artifact commit to different run identities
