# Contract: Proof Bundle Verification

## Surface

- `backend/chain/verify.py`
- `backend/chain/proof_adapter.py`
- `backend/chain/proof_spec.py`

## Evidence tiers

- `unverified`
- `integrity_checked`
- `replay_checked`
- `proof_staged`
- `verified_onchain`

Mock evidence may be labeled with mock context but must never become cryptographic acceptance.

## Required invariant

`proof_ok` requires on-chain verifier acceptance. Local schema, replay, and transport checks can stage proof evidence but cannot finalize it.
