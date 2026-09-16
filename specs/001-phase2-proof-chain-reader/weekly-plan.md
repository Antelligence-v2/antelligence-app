# Weekly Plan: 2026-07-09 to 2026-07-15

## Operating thesis

This week is a consolidation week: convert recovered proof/chain-reader work into a shippable, compiler-driven Phase 2 baseline. The fleet must ship verified code/test deltas every 24-48h, not another analysis-only loop.

## Weekly outcomes

1. **A1 provenance schema locked** — `/simulate` and `/runs/{run_id}` have a stable structured provenance/error contract.
2. **Proof lifecycle hardened** — staged bundles, mock flags, unsupported trust tiers, and transport commitments fail closed.
3. **Chain-reader determinism bounded** — fixture buffers are deterministic; live RPC remains explicitly gated.
4. **Trust display unified** — leaderboard/frontend consume canonical trust tiers without overstating staged proof.
5. **Compiler backlog expanded only where needed** — gaps become `NEEDS_TEMPLATE`, not invented task IDs.

## 24-48h slices

### Slice 1 — Tomorrow: A1 provenance schema lock

- Primary templates: `verify-api-trust-tier-test`, `proof-bundle-schema-guard`, `simulation-replay-fixture`, `shared-memory-proof-boundary`.
- Output: one backend/test delta that makes API/run/proof provenance schema explicit.
- Gate: focused pytest from the selected template, then `.venv/bin/python -m pytest`.

### Slice 2 — Day 2-3: Proof lifecycle fail-closed sweep

- Primary templates: `verifier-trust-tier-copy`, `proof-adapter-interface`, `submit-proof-lifecycle-test`, `verifier-admin-config-test`.
- Output: tests proving malformed/stale/mock/onchain-missing paths cannot become final proof.
- Gate: focused verifier/proof tests, then full suite.

### Slice 3 — Day 3-4: Chain-reader deterministic evidence boundary

- Primary templates: `leaderboard-trust-propagation`, `leaderboard-core-metric-integrity`.
- Output: deterministic fixture evidence wired only as bounded trust metadata, not finality.
- Gap: live RPC same-height determinism probe has no current template; keep as `NEEDS_TEMPLATE` until added.

### Slice 4 — Day 4-5: Demo-facing trust copy

- Primary template: `frontend-proof-status-copy`.
- Output: frontend/leaderboard says "Proof: Staged" or equivalent non-production copy where applicable.
- Gate: `npm --prefix frontend run build`, relevant leaderboard pytest, then full backend suite if backend touched.

### Slice 5 — Day 5-7: Compiler and strategy closeout

- Primary templates: `attestation-bot-dry-run-test`, `runtime-factory-config-guard` if those seams remain active.
- Output: any missing compiler templates proposed from real gaps; weekly review note records what shipped vs stalled.
- Gate: compiler contract remains deterministic; no broad uncompiled backlog task is dispatched.

## Non-goals

- No push/merge/main.
- No public deployment.
- No contract deployment or authority change.
- No `.env`, secret, or paid API cap changes.
- No live RPC determinism claim without a new template and recorded evidence.
