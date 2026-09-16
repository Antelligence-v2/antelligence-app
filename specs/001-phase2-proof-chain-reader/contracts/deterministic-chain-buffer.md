# Contract: Deterministic Chain Buffer

## Surface

- `backend/chain/deterministic_buffer.py`

## Event ordering

Events are sorted by `chain_id`, `source`, `block_height`, `tx_index`, `log_index`, and canonical payload JSON. Arrival order is ignored.

## Trust labels

- Missing/stale observation: `T1 local`
- Observer at or above event height: `T2 observer@<height>`
- Finality at or above event height: `T3 finality`

## Live RPC rule

No live RPC read is replayable until same-height query determinism is verified and recorded. Use fixture snapshots until then.
