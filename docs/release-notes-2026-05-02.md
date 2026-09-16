# Antelligence Release Review Manifest — 2026-05-02

Status: validated dirty tree, prepared for human release review.
Intent: convert the current uncommitted work into a reviewable release unit without committing, pushing, deploying, editing secrets, or touching production code in this loop.

## Intentional file groups to review

### 1. Proof lifecycle, trust tiers, and verifier administration
Review first because this is the release spine for replacing opaque/mock proof handling with explicit proof states and trust boundaries.

- `backend/chain/proof_adapter.py` — proof bundle adapter surface.
- `backend/chain/proof_lifecycle.py` — proof lifecycle/state handling.
- `backend/chain/proof_spec.py` — shared proof metadata/schema definitions.
- `backend/chain/verifier_admin.py` — verifier administration helpers.
- `backend/chain/config.py` — chain/proof configuration support.
- `blockchain/contracts/MockProofVerifier.sol` — local/dev verifier contract.
- `blockchain/contracts/TumorIntel.sol` — contract-side verifier integration.
- `tests/test_proof_adapter.py`, `tests/test_verifier_admin.py`, `tests/test_verify_is_mock.py`, `tests/test_verify_trust_tiers.py`, `tests/test_trust_tiers.py`, `tests/test_trust_tier_explicit.py`, `tests/test_trust_tiers_explicit.py`, `tests/test_trust_tiers_new.py` — proof/trust-tier regression coverage.

### 2. Chain submission, verification, leaderboard, and runtime wiring
Review after the proof lifecycle because these files connect proof state to API/runtime behavior.

- `backend/chain/verify.py`, `backend/chain/submit.py`, `backend/chain/leaderboard.py` — backend chain operations.
- `blockchain/client.py` — client integration with contract/verifier flow.
- `backend/config.py`, `backend/main.py`, `backend/runtime_factory.py`, `backend/__init__.py` — runtime/config packaging updates.
- `tests/test_config.py`, `tests/test_submit.py`, `tests/test_verify.py`, `tests/test_leaderboard.py`, `tests/test_leaderboard_expansion.py` — integration/regression coverage.

### 3. Simulation persistence, replay, and API behavior
Review as its own unit because it changes how simulation output is stored, replayed, and exposed.

- `backend/nanobot_simulation.py` — simulation behavior/output changes.
- `backend/api_server.py` — API integration.
- `backend/run_store.py` — persisted run store.
- `backend/simulation_replay.py` — replay support.
- `scripts/attestation_bot.py` — attestation automation changes.
- `scripts/eval/` — evaluation scripts intended for reproducible analysis.
- `tests/test_nanobot.py`, `tests/test_run_store.py`, `tests/test_simulation_replay.py`, `tests/test_simulation_replay_buggy.py`, `tests/test_attestation_bot_dry_run.py` — simulation/store/bot coverage.

### 4. Frontend preview and UX updates
Review separately from backend proof/runtime changes so visual/API assumptions stay easy to inspect.

- `frontend/src/App.tsx`, `frontend/src/pages/Index.tsx`, `frontend/src/pages/SimulationComparison.tsx`, `frontend/src/pages/TumorHunt.tsx`, `frontend/src/pages/TumorSimulation.tsx` — UI/page changes.
- `frontend/src/components/PreviewModeBanner.tsx` — preview-mode disclosure.
- `frontend/package.json`, `frontend/vite.config.ts` — frontend build/config updates.
- `frontend/.env.preview` — review carefully before inclusion; include only if it contains non-secret preview defaults.

### 5. Dependency and lockfile changes
Review with the unit that requires them, but keep them visible in the release checklist.

- `pyproject.toml`, `uv.lock` — Python dependency/test environment updates.
- `backend/requirements.txt` — backend dependency updates.
- `frontend/package.json` — frontend dependency/script updates.

## Validation evidence

Latest known validation from the autonomous implementation scorecard:

- `uv run --extra test pytest -q` — passed, 198 tests.
- `npm --prefix frontend run build` — passed, frontend build successful.

This loop should re-run the same verification after this documentation-only manifest update. If either command fails, treat this manifest as prepared but not release-validated.

## Likely scratch/local files to exclude from release PRs

Exclude unless a human explicitly promotes one of these into an intentional fixture or tool:

- Agent/internal state: `.hermes/`.
- Local data/cache/artifacts: `cache/`, `out/`, `data/api_runs.sqlite3`, `data/brats/brats2020-training-data.zip`, `frontend/dist/`.
- Root debug/patch/probe scripts: `apply_fix_v5.py`, `check_init.py`, `fix_package.py`, `debug_bot_final.py`, `debug_bot_path.py`, `debug_import.py`, `debug_imports.py`, `debug_replay.py`, `debug_tier.py`, `patch_bot.py`, `patch_bot_final.py`, `patch_bot_v2.py`, `test_bot_direct.py`, `test_bot_direct_final.py`, `test_bot_direct_final_v2.py`, `test_bot_direct_final_v3.py`, `test_bot_direct_fixed.py`, `test_fix.py`, `test_fix_final.py`, `test_trust_tiers_check.py`, `test_trust_tiers_diff.py`.
- Test-side debug probes: `tests/debug_fix.py`, `tests/debug_integrity_recalc.py`, `tests/debug_structure.py`, `tests/debug_verify.py`.

## Recommended PR split

1. PR 1 — Proof lifecycle and trust-tier core: proof adapter/lifecycle/spec/admin, verifier contract changes, and focused proof/trust-tier tests.
2. PR 2 — Chain/runtime integration: submit/verify/leaderboard/client/config/runtime wiring and matching backend tests.
3. PR 3 — Simulation persistence and replay: nanobot simulation, API server integration, run store, replay, attestation/eval support, and simulation/store tests.
4. PR 4 — Frontend preview UI: page/component/config changes plus preview environment review; exclude `frontend/dist/` unless the project intentionally tracks built assets.
5. PR 5 — Cleanup-only PR or pre-PR chore: remove scratch/debug/local artifacts from the working tree before opening review PRs.

## 2026-05-02 unattended pass 7 addendum

Current release-prep inventory from `git status --short` at this pass: 85 dirty paths total, split as 25 modified tracked paths and 60 untracked paths. The review shape remains releaseable, but the handoff should preserve the distinction between durable implementation/test files and local loop artifacts.

Additional review notes:

- `docs/plans/` is untracked and should be reviewed as planning context, not bundled automatically with implementation PRs.
- The durable test candidates are the named `tests/test_*.py` regression files in the groups above; `tests/debug_*.py` files remain scratch/probe exclusions.
- `uv.lock` is now visible as an untracked dependency-lock change and should travel only with the Python dependency update that requires it.
- The recommended PR split is unchanged: proof core first, chain/runtime second, simulation/replay third, frontend preview fourth, cleanup/artifact removal last.

## 2026-05-02 unattended pass 8 addendum

Current release-prep inventory from `git status --short` at this pass: two dirty paths total, both modified tracked files: `backend/chain/verify.py` and `tests/test_verify.py`. No untracked, generated, local-data, frontend, secret, or scratch files are present in the current dirty tree.

Intentional review group:

- Chain verification hardening: `backend/chain/verify.py` now treats a claimed numeric metric missing from recomputed metrics as a failed tolerance check instead of silently skipping it.
- Focused regression coverage: `tests/test_verify.py` adds `test_missing_recomputed_numeric_metric_fails` to lock the behavior.

Validation evidence to preserve for review:

- Latest focused loop evidence before this manifest pass: `uv run --extra test pytest -q tests/test_verify.py::TestMetricsTolerance::test_missing_recomputed_numeric_metric_fails` — passed, 1 test.
- Latest focused suite evidence before this manifest pass: `uv run --extra test pytest -q tests/test_nanobot.py tests/test_tumor_env.py tests/test_verify.py` — passed, 64 tests.
- This manifest pass ran the required full commands: `uv run --extra test pytest -q` — passed, 199 tests in 4.28s; `npm --prefix frontend run build` — passed, built in 1.91s.

Likely exclusions for this narrowed tree:

- None from `git status --short`; the only dirty files are the implementation/test pair above.
- Continue excluding any regenerated `frontend/dist/`, `out/`, cache, local SQLite, BraTS archives, `.hermes/`, and debug/probe scripts if they reappear before PR handoff.

Recommended PR split for the current narrowed dirty tree:

1. Single tiny PR — chain verification tolerance hardening with the focused regression test.
2. Defer the broader proof/runtime/simulation/frontend release groups listed above until their files are intentionally reintroduced into the review set.

## Release-review checklist

- Confirm `.env.preview` contains no secrets before including it.
- Confirm `frontend/dist/`, `out/`, cache, local database, and BraTS zip are excluded or intentionally regenerated.
- Confirm every included new test is durable regression coverage, not a temporary probe.
- Run `uv run --extra test pytest -q` and `npm --prefix frontend run build` immediately before review handoff.
