# Quickstart Validation: Phase 2 Proof/Provenance Completion

## Prerequisites

```bash
cd /Users/operator/Desktop/research/antelligence-app
git branch --show-current   # checkpoint/2026-07-08-recovered-work
specify --version           # specify 0.12.8
```

## Full regression gate

```bash
.venv/bin/python -m pytest
```

Expected: full suite passes. Current baseline from checkpoint was `237 passed, 1 warning`; the post-spec run must be reported from live output.

## Focused proof/trust gates

```bash
.venv/bin/python -m pytest   tests/test_proof_adapter.py   tests/test_verify.py   tests/test_verify_trust_tiers.py   tests/test_proof_transport_metadata_contract.py -q
```

Expected: staged proof bundles validate schema/transport while `proof_ok` remains gated by on-chain acceptance.

## Minimal API provenance gate

```bash
.venv/bin/python -m pytest tests/test_api_server.py tests/test_run_store.py -q
```

Expected: `/simulate` and `/runs/{run_id}` keep structured config, metrics, and provenance fields.

## Chain-reader determinism gate

```bash
.venv/bin/python -m pytest tests/test_chain_reader_determinism.py -q
```

Expected: reordered fixture events produce identical buffer digests, trust labels degrade safely, and provenance checksums bind sim identity + chain buffer digest + provenance id.

## Frontend proof copy gate (only for `frontend-proof-status-copy`)

```bash
npm --prefix frontend run build
```

Expected: build exits 0 and staged proof status copy is visible in the touched component/page.
