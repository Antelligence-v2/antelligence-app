# Antelligence Release Review Manifest — 2026-05-03

Status: narrowed dirty tree, prepared for release review without committing, pushing, deploying, editing secrets, or touching production code in this loop.
Intent: preserve the current validated backend regression slice as a reviewable unit and keep documentation-only release-prep notes distinct from implementation changes.

## Current dirty inventory

`git status --short` at the original manifest pass showed four modified tracked paths and no untracked paths:

- `backend/chain/verify.py`
- `tests/test_verify.py`
- `docs/progress-notes.md`
- `docs/release-notes-2026-05-02.md`

This pass intentionally added only this dated manifest plus the progress-note pointer. No production code, secrets, generated data, debug scratch files, deployment configuration, or local data paths were edited.

## Intentional file groups to review

### 1. Chain verification regression slice

Review as the only implementation PR candidate currently visible in the dirty tree:

- `backend/chain/verify.py` — changes `verify_metrics_tolerance` so a claimed numeric metric missing from recomputed metrics is emitted as a failed check instead of being silently skipped.
- `tests/test_verify.py` — adds focused regression coverage for the missing-recomputed-numeric-metric behavior.

Recommended review framing: small backend correctness fix with a single matching unit test.

### 2. Release-preparation documentation

Keep these as release-review notes, not runtime behavior changes:

- `docs/progress-notes.md` — concise progress index and handoff pointer.
- `docs/release-notes-2026-05-02.md` — previous release manifest and narrowed-tree addenda.
- `docs/release-notes-2026-05-03.md` — this current manifest for the final pre-review dirty tree shape.

Recommended review framing: either include with the backend PR as reviewer context or keep as a separate docs-only release-prep PR if maintainers prefer implementation diffs to stay minimal.

## Validation evidence

Evidence already present before this pass:

- Focused regression: `uv run --extra test pytest -q tests/test_verify.py::TestMetricsTolerance::test_missing_recomputed_numeric_metric_fails` — passed, 1 test.
- Focused backend suite: `uv run --extra test pytest -q tests/test_nanobot.py tests/test_tumor_env.py tests/test_verify.py` — passed, 64 tests.
- Full validation from the previous manifest pass: `uv run --extra test pytest -q` — passed, 199 tests in 4.28s; `npm --prefix frontend run build` — passed, built in 1.91s.

This pass refreshed the required full validation after writing the manifest:

- `uv run --extra test pytest -q` — passed, 199 tests in 4.16s.
- `npm --prefix frontend run build` — passed, built in 1.91s.

The frontend build emitted the existing non-failing Browserslist staleness and chunk-size warnings; no generated `frontend/dist/` changes appeared in `git status --short` after the build.

## Likely scratch/local files to exclude

None are present in the current `git status --short` inventory. Continue excluding the following if they reappear before review handoff:

- Generated or build artifacts: `frontend/dist/`, `out/`, coverage reports, cache directories.
- Local runtime data: `data/api_runs.sqlite3`, local BraTS archives or extracted medical-imaging datasets.
- Agent/operator state: `.hermes/`, autonomous-loop state files, local logs.
- Temporary probes: root-level `debug_*.py`, `patch_*.py`, `test_*_direct*.py`, and `tests/debug_*.py` scripts unless a human explicitly promotes one into durable regression coverage.
- Secrets or local environment files beyond reviewed non-secret preview defaults.

## Recommended PR split

1. PR 1 — Chain verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`. This is the smallest releaseable implementation unit.
2. PR 2 — Release review documentation, if desired separately: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
3. Defer all broader proof lifecycle, simulation/replay, frontend preview, dependency, and artifact-cleanup release groups until their corresponding files are intentionally reintroduced into the dirty tree.

## 2026-05-03 second-pass refresh

This pass re-read the dirty tree before editing and preserved the existing implementation/test changes. The review shape is unchanged, with one nuance: `docs/release-notes-2026-05-03.md` is still untracked because this unattended loop must not commit or stage files.

Current dirty inventory for release review:

- Implementation/test pair: `backend/chain/verify.py`, `tests/test_verify.py`.
- Release-review docs: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md`.
- Scratch/local exclusions observed in `git status --short`: none.

Recommended handoff remains:

1. Review and land the backend verification regression pair as the smallest functional PR.
2. Keep the three release-review docs together as reviewer context, or split them into a docs-only PR if the backend PR should contain only code and tests.
3. Before any push, confirm the untracked 2026-05-03 manifest is intentionally added and do one final `git status --short` check for regenerated artifacts.

## 2026-05-03 third-pass refresh

This pass re-read the dirty tree before editing and preserved all existing user changes. The release unit remains intentionally narrow and reviewable:

- Implementation/test group: `backend/chain/verify.py` plus `tests/test_verify.py` for the missing-recomputed-numeric-metric failure behavior.
- Release-review documentation group: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and this untracked `docs/release-notes-2026-05-03.md` manifest.
- Scratch/local exclusions observed in `git status --short`: none. Keep excluding generated artifacts, local runtime data, autonomous-agent state, temporary debug/probe scripts, and secrets if they reappear.

Recommended PR split remains:

1. PR 1 — chain verification tolerance hardening with focused regression coverage.
2. PR 2 — release-review notes, or bundle the docs as reviewer context if maintainers want one release-prep handoff.
3. Do not widen the PR with proof lifecycle, simulation/replay, frontend preview, dependency, or cleanup groups until their files are intentionally reintroduced and validated.

## 2026-05-03 fourth-pass refresh

This pass re-read the dirty tree before editing and preserved the existing user changes. The current review unit has widened from the earlier five-path manifest to seven dirty paths, all still reviewable as small intentional groups:

- Chain submission normalization: `backend/chain/submit.py` plus `tests/test_submit.py`. This preserves an existing `0x` config-hash prefix before calling `cast` instead of constructing a double-prefixed bytes32 argument.
- Chain verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`. This fails claimed numeric metrics that are absent from recomputed metrics with `reason: missing_recomputed_metric`.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and this untracked `docs/release-notes-2026-05-03.md` manifest.

Validation evidence to preserve for review:

- Previous full manifest validation: `uv run --extra test pytest -q` — passed, 199 tests; `npm --prefix frontend run build` — passed with existing non-failing Browserslist/chunk-size warnings.
- Fourth-pass full validation: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` — passed; pytest 200 passed in 4.81s; frontend build passed in 2.49s with the existing non-failing Browserslist staleness and chunk-size warnings.

Likely scratch/local exclusions observed in the current `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite or BraTS data, `.hermes/` or loop state, temporary debug/probe scripts, deployment scratch, and secrets.

Recommended PR split for the current dirty tree:

1. PR 1 — chain submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
2. PR 2 — chain verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
3. PR 3 or reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
4. Do not include generated artifacts, local runtime data, autonomous-agent state, secrets, or unrelated proof/simulation/frontend changes unless they are intentionally reintroduced and separately validated.

## 2026-05-03 fifth-pass refresh

This pass re-read the repository state before editing and made only documentation updates to preserve the existing user changes. Current `git status --short` still shows seven dirty paths and no scratch/local artifacts:

- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, preserving already-prefixed config hashes when constructing `cast` arguments.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric`.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Validation evidence from this pass: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 200 passed in 5.10s, and the frontend build completed in 2.57s with only the existing non-failing Browserslist staleness and chunk-size warnings.

Recommended PR split is unchanged: PR 1 for submission config-hash normalization, PR 2 for verification tolerance hardening, and PR 3 or bundled reviewer context for release-review docs. Keep generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or loop state, debug/probe scripts, deployment scratch, and secrets excluded unless a human intentionally promotes and revalidates them.

## 2026-05-03 sixth-pass refresh

This pass re-read the repository state before editing and made only documentation updates to preserve the existing user changes. Current `git status --short` remains a seven-path review unit with no scratch/local artifacts:

- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, preserving already-prefixed config hashes when constructing `cast` arguments.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric`.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Validation evidence from this pass: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 200 passed in 4.79s, and the frontend build completed in 2.39s with only the existing non-failing Browserslist staleness and chunk-size warnings.

Preserve the recommended PR split: PR 1 for submission config-hash normalization, PR 2 for verification tolerance hardening, and PR 3 or bundled reviewer context for release-review docs. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or loop state, debug/probe scripts, deployment scratch, and secrets unless a human intentionally promotes and revalidates them.

## 2026-05-03 seventh-pass refresh

This pass re-read the repository state before editing and preserved all existing user changes. Current `git status --short` remains the same seven-path release-review unit:

- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, preserving already-prefixed config hashes before invoking `cast`.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric`.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Scratch/local exclusions observed in `git status --short`: none. Keep generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or loop state, debug/probe scripts, deployment scratch, and secrets excluded unless a human intentionally promotes and revalidates them.

Recommended PR split remains stable: PR 1 for submission config-hash normalization, PR 2 for verification tolerance hardening, and PR 3 or bundled reviewer context for release-review documentation. This pass intentionally made only docs changes and did not stage, commit, push, deploy, edit secrets, or touch production code.

## 2026-05-03 eighth-pass refresh

This pass re-read the repository state before editing and preserved all existing user changes. Current `git status --short` remains the same seven-path release-review unit:

- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, preserving already-prefixed config hashes before invoking `cast`.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric`.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Scratch/local exclusions observed in `git status --short`: none. Keep excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or loop state, debug/probe scripts, deployment scratch, and secrets unless a human intentionally promotes and revalidates them.

Recommended PR split remains stable and reviewable: PR 1 for submission config-hash normalization, PR 2 for verification tolerance hardening, and PR 3 or bundled reviewer context for release-review documentation. This pass intentionally made only docs changes and did not stage, commit, push, deploy, edit secrets, or touch production code.

## 2026-05-03 ninth-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same seven-path release-review unit:

- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, normalizing config hashes so already-prefixed `0x` values are not double-prefixed before `cast` submission/estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric` instead of silently skipping them.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Scratch/local exclusions observed in `git status --short`: none. Keep excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or loop state, debug/probe scripts, deployment scratch, and secrets unless a human intentionally promotes and revalidates them.

Recommended PR split remains stable and minimal: PR 1 for submission config-hash normalization, PR 2 for verification tolerance hardening, and PR 3 or bundled reviewer context for release-review documentation. This pass intentionally made only docs changes and did not stage, commit, push, deploy, edit secrets, or touch production code.

## 2026-05-03 tenth-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same seven-path release-review unit:

- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, normalizing config hashes so already-prefixed `0x` values are not double-prefixed before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric` rather than silently treating them as non-comparable.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, and secrets unless a human intentionally promotes and revalidates them.

Recommended PR split remains stable and minimal: PR 1 for submission config-hash normalization, PR 2 for verification tolerance hardening, and PR 3 or bundled reviewer context for release-review documentation. This pass intentionally made only docs changes and did not stage, commit, push, deploy, edit secrets, or touch production code.

## 2026-05-03 eleventh-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same seven-path release-review unit:

- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, normalizing config hashes so already-prefixed `0x` values are not double-prefixed before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric` rather than silently treating them as non-comparable.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Validation evidence from this pass: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 200 passed, and the frontend build completed with only the existing non-failing Browserslist staleness and chunk-size warnings.

Scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, and secrets unless a human intentionally promotes and revalidates them.

Recommended PR split remains stable and minimal: PR 1 for submission config-hash normalization, PR 2 for verification tolerance hardening, and PR 3 or bundled reviewer context for release-review documentation. This pass intentionally made only docs changes and did not stage, commit, push, deploy, edit secrets, or touch production code.

## 2026-05-03 twelfth-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same seven-path release-review unit:

- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, normalizing config hashes so already-prefixed `0x` values are not double-prefixed before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric` rather than silently treating them as non-comparable.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Review evidence to preserve with the handoff:

- Focused test for PR 1 is `tests/test_submit.py::TestAttestationBundle::test_submit_via_cast_preserves_existing_0x_prefix`.
- Focused test for PR 2 is `tests/test_verify.py::TestMetricsTolerance::test_missing_recomputed_numeric_metric_fails`.
- Required full validation should remain the release gate: `uv run --extra test pytest -q && npm --prefix frontend run build`.

Scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, and secrets unless a human intentionally promotes and revalidates them.

Recommended PR split remains stable and minimal: PR 1 for submission config-hash normalization, PR 2 for verification tolerance hardening, and PR 3 or bundled reviewer context for release-review documentation. This pass intentionally made only docs changes and did not stage, commit, push, deploy, edit secrets, or touch production code.

## 2026-05-03 thirteenth-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same seven-path release-review unit:

- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, normalizing config hashes so already-prefixed `0x` values are not double-prefixed before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric` rather than silently treating them as non-comparable.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Reviewer checklist before PR creation:

1. Confirm the untracked `docs/release-notes-2026-05-03.md` manifest is intentionally added if the docs context should travel with the implementation review.
2. Preserve the focused regression anchors: `tests/test_submit.py::TestAttestationBundle::test_submit_via_cast_preserves_existing_0x_prefix` for PR 1 and `tests/test_verify.py::TestMetricsTolerance::test_missing_recomputed_numeric_metric_fails` for PR 2.
3. Keep generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, and secrets excluded unless explicitly promoted and revalidated.
4. Use the full release gate immediately before handoff: `uv run --extra test pytest -q && npm --prefix frontend run build`.

Recommended PR split remains stable and minimal: PR 1 for submission config-hash normalization, PR 2 for verification tolerance hardening, and PR 3 or bundled reviewer context for release-review documentation. This pass intentionally made only docs changes and did not stage, commit, push, deploy, edit secrets, or touch production code.

## 2026-05-03 fourteenth-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` shows an eight-path release-review unit:

- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, normalizing config hashes so already-prefixed `0x` values are not double-prefixed before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric` rather than silently treating them as non-comparable.
- Test hygiene slice: `tests/test_attestation_bot_dry_run.py`, moving the dummy dry-run JSON fixture into `tmp_path` so release review does not rely on or leave root/test-tree scratch output.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Validation evidence to preserve with the handoff:

- Previous pass full gate: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 200 passed and the frontend build completed with only existing non-failing Browserslist staleness and chunk-size warnings.
- Required release gate for this pass is still `uv run --extra test pytest -q && npm --prefix frontend run build`, with `git diff --check` on the edited docs before that gate.

Likely scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, temporary dummy JSON outputs, and secrets unless a human intentionally promotes and revalidates them.

Recommended PR split:

1. PR 1 — submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
2. PR 2 — verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
3. PR 3 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with the nearest backend test-maintenance PR if maintainers prefer fewer PRs.
4. PR 4 or reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
5. Do not include generated artifacts, local runtime data, autonomous-agent state, secrets, or unrelated proof/simulation/frontend changes unless they are intentionally reintroduced and separately validated.

## 2026-05-03 fifteenth-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same eight-path release-review unit:

- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, normalizing config hashes so already-prefixed `0x` values are not double-prefixed before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric` rather than silently treating them as non-comparable.
- Test hygiene slice: `tests/test_attestation_bot_dry_run.py`, keeping dummy dry-run JSON under `tmp_path` so review does not depend on root/test-tree scratch output.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Validation handoff for this pass:

- Required command: `uv run --extra test pytest -q && npm --prefix frontend run build`.
- Preflight doc whitespace check: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md`.
- Existing expected frontend build warnings remain non-blocking unless they become errors: Browserslist database staleness and large chunk-size warnings.

Likely scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, temporary dummy JSON outputs, and secrets unless a human intentionally promotes and revalidates them.

Recommended PR split remains:

1. PR 1 — submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
2. PR 2 — verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
3. PR 3 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with test-maintenance if reviewers prefer fewer PRs.
4. PR 4 or reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
5. Do not include generated artifacts, local runtime data, autonomous-agent state, secrets, or unrelated proof/simulation/frontend changes unless they are intentionally reintroduced and separately validated.

## 2026-05-03 sixteenth-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` shows a ten-path release-review unit:

- Proof transport metadata contract slice: `backend/chain/proof_spec.py` plus untracked `tests/test_proof_transport_metadata_contract.py`, pinning the proof transport metadata key set/order so reviewer-facing artifact metadata cannot drift silently.
- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, normalizing config hashes so already-prefixed `0x` values are not double-prefixed before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric` rather than silently treating them as non-comparable.
- Test hygiene slice: `tests/test_attestation_bot_dry_run.py`, keeping dummy dry-run JSON under `tmp_path` so review does not depend on root/test-tree scratch output.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Validation evidence to preserve with the handoff:

- Previous full gate from the fifteenth pass: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 200 passed in 4.06s, and frontend build passed in 2.06s with existing non-failing Browserslist staleness and chunk-size warnings.
- Current pass full gate: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 201 passed in 3.73s, and frontend build passed in 1.89s with the existing non-failing Browserslist staleness and chunk-size warnings.

Likely scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, temporary dummy JSON outputs, local proof artifacts, and secrets unless a human intentionally promotes and revalidates them.

Recommended PR split:

1. PR 1 — proof transport metadata contract: `backend/chain/proof_spec.py` plus `tests/test_proof_transport_metadata_contract.py`.
2. PR 2 — submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
3. PR 3 — verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
4. PR 4 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with test-maintenance if reviewers prefer fewer PRs.
5. PR 5 or reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
6. Do not include generated artifacts, local runtime data, autonomous-agent state, secrets, or unrelated proof/simulation/frontend changes unless they are intentionally reintroduced and separately validated.

## 2026-05-03 seventeenth-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same ten-path release-review unit:

- Proof transport metadata contract slice: `backend/chain/proof_spec.py` plus untracked `tests/test_proof_transport_metadata_contract.py`, pinning the proof transport metadata key set/order so artifact metadata cannot drift silently.
- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, normalizing config hashes so already-prefixed `0x` values are not double-prefixed before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric` rather than silently treating them as non-comparable.
- Test hygiene slice: `tests/test_attestation_bot_dry_run.py`, keeping dummy dry-run JSON under `tmp_path` so release review does not depend on root/test-tree scratch output.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Validation handoff for this pass:

- Required command: `uv run --extra test pytest -q && npm --prefix frontend run build`.
- Preflight doc whitespace check: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md`.
- Existing expected frontend build warnings remain non-blocking unless they become errors: Browserslist database staleness and large chunk-size warnings.

Likely scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, temporary dummy JSON outputs, local proof artifacts, and secrets unless a human intentionally promotes and revalidates them.

Recommended PR split:

1. PR 1 — proof transport metadata contract: `backend/chain/proof_spec.py` plus `tests/test_proof_transport_metadata_contract.py`.
2. PR 2 — submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
3. PR 3 — verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
4. PR 4 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with test-maintenance if reviewers prefer fewer PRs.
5. PR 5 or reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
6. Do not include generated artifacts, local runtime data, autonomous-agent state, secrets, unrelated proof/simulation/frontend changes, or unreviewed local proof artifacts unless they are intentionally reintroduced and separately validated.

## 2026-05-03 eighteenth-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same ten-path release-review unit:

- Proof transport metadata contract slice: `backend/chain/proof_spec.py` plus untracked `tests/test_proof_transport_metadata_contract.py`, pinning the proof transport metadata key set/order so artifact metadata cannot drift silently.
- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, normalizing config hashes so already-prefixed `0x` values are not double-prefixed before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics that are absent from recomputed metrics with `missing_recomputed_metric` rather than silently treating them as non-comparable.
- Test hygiene slice: `tests/test_attestation_bot_dry_run.py`, keeping dummy dry-run JSON under `tmp_path` so release review does not depend on root/test-tree scratch output.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Current pass validation evidence:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 201 passed in 3.73s.
- Frontend build completed in 1.90s with only the existing non-failing Browserslist database staleness and large chunk-size warnings.

Likely scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, temporary dummy JSON outputs, local proof artifacts, secrets, and unrelated proof/simulation/frontend changes unless they are intentionally promoted and separately validated.

Recommended PR split remains:

1. PR 1 — proof transport metadata contract: `backend/chain/proof_spec.py` plus `tests/test_proof_transport_metadata_contract.py`.
2. PR 2 — submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
3. PR 3 — verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
4. PR 4 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with test-maintenance if reviewers prefer fewer PRs.
5. PR 5 or reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
6. Keep generated artifacts, local runtime data, autonomous-agent state, secrets, unrelated proof/simulation/frontend changes, and unreviewed local proof artifacts out of the release unit unless explicitly promoted and revalidated.

## 2026-05-03 nineteenth-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same ten-path release-review unit:

- Proof transport metadata contract slice: `backend/chain/proof_spec.py` plus untracked `tests/test_proof_transport_metadata_contract.py`, pinning proof transport metadata keys/order so artifact metadata drift is caught by reviewable regression coverage.
- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, preserving already-prefixed `0x` config hashes before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics missing from recomputed metrics with `missing_recomputed_metric` instead of silently skipping them.
- Test hygiene slice: `tests/test_attestation_bot_dry_run.py`, keeping dummy dry-run JSON under `tmp_path` so release review does not depend on root/test-tree scratch output.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Current pass validation evidence:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 201 passed.
- Frontend build completed with only existing non-failing Browserslist database staleness and large chunk-size warnings.

Likely scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, temporary dummy JSON outputs, local proof artifacts, secrets, and unrelated proof/simulation/frontend changes unless they are intentionally promoted and separately validated.

Recommended PR split remains:

1. PR 1 — proof transport metadata contract: `backend/chain/proof_spec.py` plus `tests/test_proof_transport_metadata_contract.py`.
2. PR 2 — submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
3. PR 3 — verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
4. PR 4 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with test-maintenance if reviewers prefer fewer PRs.
5. PR 5 or reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
6. Keep generated artifacts, local runtime data, autonomous-agent state, secrets, unrelated proof/simulation/frontend changes, and unreviewed local proof artifacts out of the release unit unless explicitly promoted and revalidated.

## 2026-05-03 twentieth-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same ten-path release-review unit:

- Proof transport metadata contract slice: `backend/chain/proof_spec.py` plus untracked `tests/test_proof_transport_metadata_contract.py`, pinning proof transport metadata keys/order so artifact metadata drift is caught by regression coverage.
- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, preserving already-prefixed `0x` config hashes before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics missing from recomputed metrics with `missing_recomputed_metric` instead of silently skipping them.
- Test hygiene slice: `tests/test_attestation_bot_dry_run.py`, keeping dummy dry-run JSON under `tmp_path` so release review does not depend on root/test-tree scratch output.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Current pass validation evidence:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 201 passed in 4.48s.
- Frontend build completed in 3.34s with only the existing non-failing Browserslist database staleness and large chunk-size warnings.
- Preserve focused anchors for reviewers: `tests/test_proof_transport_metadata_contract.py`, `tests/test_submit.py::TestAttestationBundle::test_submit_via_cast_preserves_existing_0x_prefix`, and `tests/test_verify.py::TestMetricsTolerance::test_missing_recomputed_numeric_metric_fails`.

Likely scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, temporary dummy JSON outputs, local proof artifacts, secrets, and unrelated proof/simulation/frontend changes unless they are intentionally promoted and separately validated.

Recommended PR split remains:

1. PR 1 — proof transport metadata contract: `backend/chain/proof_spec.py` plus `tests/test_proof_transport_metadata_contract.py`.
2. PR 2 — submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
3. PR 3 — verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
4. PR 4 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with test-maintenance if reviewers prefer fewer PRs.
5. PR 5 or reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
6. Keep generated artifacts, local runtime data, autonomous-agent state, secrets, unrelated proof/simulation/frontend changes, and unreviewed local proof artifacts out of the release unit unless explicitly promoted and revalidated.

## 2026-05-03 twenty-first-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same ten-path release-review unit:

- Proof transport metadata contract slice: `backend/chain/proof_spec.py` plus untracked `tests/test_proof_transport_metadata_contract.py`, pinning proof transport metadata keys/order so artifact metadata drift is caught by regression coverage.
- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, preserving already-prefixed `0x` config hashes before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics missing from recomputed metrics with `missing_recomputed_metric` instead of silently skipping them.
- Test hygiene slice: `tests/test_attestation_bot_dry_run.py`, keeping dummy dry-run JSON under `tmp_path` so release review does not depend on root/test-tree scratch output.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Current pass validation evidence:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 201 passed in 4.51s.
- Frontend build completed in 2.05s with only the existing non-failing Browserslist database staleness and large chunk-size warnings.

Likely scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, temporary dummy JSON outputs, local proof artifacts, secrets, unrelated proof/simulation/frontend changes, and unreviewed local proof artifacts unless they are intentionally promoted and separately validated.

Recommended PR split remains:

1. PR 1 — proof transport metadata contract: `backend/chain/proof_spec.py` plus `tests/test_proof_transport_metadata_contract.py`.
2. PR 2 — submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
3. PR 3 — verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
4. PR 4 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with test-maintenance if reviewers prefer fewer PRs.
5. PR 5 or reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
6. Keep generated artifacts, local runtime data, autonomous-agent state, secrets, unrelated proof/simulation/frontend changes, and unreviewed local proof artifacts out of the release unit unless explicitly promoted and revalidated.

## 2026-05-03 twenty-second-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same ten-path release-review unit:

- Proof transport metadata contract slice: `backend/chain/proof_spec.py` plus untracked `tests/test_proof_transport_metadata_contract.py`, pinning proof transport metadata keys/order so artifact metadata drift is caught by regression coverage.
- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, preserving already-prefixed `0x` config hashes before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics missing from recomputed metrics with `missing_recomputed_metric` instead of silently skipping them.
- Test hygiene slice: `tests/test_attestation_bot_dry_run.py`, keeping dummy dry-run JSON under `tmp_path` so release review does not depend on root/test-tree scratch output.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Current pass validation evidence:

- Previous full gate from the twenty-first pass: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 201 passed in 4.51s and frontend build completed in 2.05s with existing non-failing warnings.
- Current pass full gate: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 201 passed in 5.15s and frontend build completed in 2.15s with existing non-failing Browserslist database staleness and large chunk-size warnings.

Likely scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, temporary dummy JSON outputs, local proof artifacts, secrets, unrelated proof/simulation/frontend changes, and unreviewed local proof artifacts unless they are explicitly promoted and separately validated.

Recommended PR split remains:

1. PR 1 — proof transport metadata contract: `backend/chain/proof_spec.py` plus `tests/test_proof_transport_metadata_contract.py`.
2. PR 2 — submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
3. PR 3 — verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
4. PR 4 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with test-maintenance if reviewers prefer fewer PRs.
5. PR 5 or reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
6. Keep generated artifacts, local runtime data, autonomous-agent state, secrets, unrelated proof/simulation/frontend changes, and unreviewed local proof artifacts out of the release unit unless explicitly promoted and revalidated.

## 2026-05-03 twenty-third-pass refresh

This pass re-read repository state before editing and preserved all existing user changes. Current `git status --short` remains the same ten-path release-review unit:

- Proof transport metadata contract slice: `backend/chain/proof_spec.py` plus untracked `tests/test_proof_transport_metadata_contract.py`, pinning proof transport metadata keys/order so artifact metadata drift is caught by regression coverage.
- Submission regression slice: `backend/chain/submit.py` plus `tests/test_submit.py`, preserving already-prefixed `0x` config hashes before `cast` submission or gas estimation.
- Verification regression slice: `backend/chain/verify.py` plus `tests/test_verify.py`, failing claimed numeric metrics missing from recomputed metrics with `missing_recomputed_metric` instead of silently skipping them.
- Test hygiene slice: `tests/test_attestation_bot_dry_run.py`, keeping dummy dry-run JSON under `tmp_path` so release review does not depend on root/test-tree scratch output.
- Release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.

Current pass validation handoff:

- Previous full gate from the twenty-second pass: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 201 passed in 5.15s and frontend build completed in 2.15s with existing non-failing warnings.
- Required current gate remains `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build`.

Likely scratch/local exclusions observed in `git status --short`: none. Continue excluding generated `frontend/dist/`, `out/`, coverage/cache directories, local SQLite/BraTS data, `.hermes/` or autonomous-loop state, debug/probe scripts, deployment scratch, temporary dummy JSON outputs, local proof artifacts, secrets, unrelated proof/simulation/frontend changes, and unreviewed local proof artifacts unless they are explicitly promoted and separately validated.

Recommended PR split remains:

1. PR 1 — proof transport metadata contract: `backend/chain/proof_spec.py` plus `tests/test_proof_transport_metadata_contract.py`.
2. PR 2 — submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
3. PR 3 — verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
4. PR 4 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with test-maintenance if reviewers prefer fewer PRs.
5. PR 5 or reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
6. Keep generated artifacts, local runtime data, autonomous-agent state, secrets, unrelated proof/simulation/frontend changes, and unreviewed local proof artifacts out of the release unit unless explicitly promoted and revalidated.

## Handoff checklist

- Run `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md` after edits.
- Run `uv run --extra test pytest -q`.
- Run `npm --prefix frontend run build`.
- Do not push until the implementation/test slice and docs context are reviewed together or explicitly split.
