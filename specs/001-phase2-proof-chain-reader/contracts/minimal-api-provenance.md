# Contract: Minimal API Provenance

## Surface

- `POST /simulate` on `backend/api_server.py`
- `GET /runs/{run_id}` on `backend/api_server.py`

## Required response shape

A completed simulation returns `run_id`, `status`, `metrics`, and `provenance`. Persisted run retrieval returns the same `config`, `metrics`, and `provenance` fields.

## Provenance fields

- `run_id`
- `config`
- `config_hash`
- `trust_tier`
- `verification_status`
- `proof_lifecycle`
- `onchain`
- `proof_bundle`

## Failure contract

Malformed config and unknown fields return structured validation errors. Runtime simulation errors return machine-readable `type` and `message`.
