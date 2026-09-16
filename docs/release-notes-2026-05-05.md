# Antelligence Release Review Manifest — 2026-05-05

Status: dirty tree prepared for release review without staging, committing, pushing, deploying, editing secrets, or touching production/runtime code in this loop.
Intent: convert the validated twenty-path dirty tree into a current dated reviewer handoff instead of repeating a green-test audit.

## Current dirty inventory

`git status --short` before this docs-only pass showed fifteen dirty paths:

- `backend/api_server.py`
- `backend/chain/proof_spec.py`
- `backend/chain/submit.py`
- `backend/chain/verify.py`
- `backend/config.py`
- `docs/progress-notes.md`
- `docs/release-notes-2026-05-02.md`
- `docs/release-notes-2026-05-03.md` (untracked)
- `docs/release-notes-2026-05-04.md` (untracked)
- `tests/test_api_server.py`
- `tests/test_attestation_bot_dry_run.py`
- `tests/test_config.py`
- `tests/test_proof_transport_metadata_contract.py` (untracked)
- `tests/test_submit.py`
- `tests/test_verify.py`

This pass intentionally adds only this 2026-05-05 manifest plus the progress-note pointer. It preserves existing production code, tests, prior release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files untouched.

Second 2026-05-05 refresh: re-reading `git status --short` now shows sixteen dirty paths only because this 2026-05-05 manifest is itself an untracked review input. The underlying implementation/test slices are unchanged, the docs-only scope remains `docs/progress-notes.md` plus this manifest, and no separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret paths are visible.

Third 2026-05-05 refresh: re-read status still shows the same sixteen review paths and no selected-scope conflict in `docs/progress-notes.md` or this manifest. This pass keeps the release unit stable by updating only reviewer handoff evidence; production code, tests, prior release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files remain untouched.

Fourth 2026-05-05 refresh: current status remains the same sixteen review paths, with no new visible scratch/local files and no selected-scope conflict. This pass only refreshes the reviewer manifest/progress note pair; it preserves production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes untouched.

Fifth 2026-05-05 refresh: current status now shows twenty dirty paths because a legacy CLI artifact-compatibility slice has joined the release-review unit (`backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, and `tests/test_simulation_replay.py`) and this manifest remains an intentional untracked docs input. This docs-only pass updates the reviewer handoff only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.

Sixth 2026-05-05 refresh: re-read status still shows the same twenty-path release-review unit, with no new generated/build output, local runtime data, autonomous-loop state, deployment scratch, local proof artifacts, debug probes, or secrets visible in `git status --short`. This pass keeps the docs-only handoff current for release review without editing production code, tests, secrets, generated data, runtime data, debug scratch files, or prior dated release notes.

Seventh 2026-05-05 refresh: re-read status remains the same twenty-path release-review unit. The selected docs-only scope is still conflict-free (`docs/progress-notes.md` plus this manifest), no new scratch/local or secret paths are visible, and the recommended seven-part PR split remains unchanged. This pass only refreshes reviewer handoff evidence and preserves production code, tests, generated data, runtime data, deployment files, local proof artifacts, debug scratch files, and prior dated release notes untouched.

Eighth 2026-05-05 refresh: re-read status remains the same twenty-path release-review unit. The selected docs-only scope remains conflict-free, no new scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret paths are visible, and this pass only refreshes the reviewer handoff in this manifest plus `docs/progress-notes.md`.

Ninth 2026-05-05 refresh: re-read status remains the same twenty-path release-review unit. The selected docs-only scope is still conflict-free, no new scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret paths are visible, and this pass only sharpens the reviewer handoff in this manifest plus `docs/progress-notes.md` without editing production code, tests, prior release notes, secrets, runtime data, or generated artifacts.

Tenth 2026-05-05 refresh: re-read status remains the same twenty-path release-review unit. The selected docs-only scope is still conflict-free, no separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret paths are visible, and this pass refreshes only this manifest plus `docs/progress-notes.md` while preserving production code, tests, prior release notes, secrets, runtime data, and generated artifacts untouched.

Eleventh 2026-05-05 refresh: re-read status remains the same twenty-path release-review unit. The selected docs-only scope is still conflict-free, no separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret paths are visible, and this pass refreshes only this manifest plus `docs/progress-notes.md` while preserving production code, tests, prior release notes, secrets, runtime data, and generated artifacts untouched. The recommended split remains seven review units with docs last or bundled as reviewer context after the full pytest/build gate.

Twelfth 2026-05-05 refresh: re-read status remains twenty dirty paths: the seven intentional production/test review units plus dated release-review documentation. The selected scope for task `prepare-release-manifest-2026-05-05-12` is still limited to this manifest and `docs/progress-notes.md`; no selected-scope conflict was observed. No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret paths are visible, so reviewer staging should preserve the four intentional untracked inputs and continue excluding generated/local/scratch/secrets unless explicitly promoted and revalidated. The recommended split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled release-review docs after the full pytest/build gate.

Thirteenth 2026-05-05 refresh: re-read status remains the same twenty-path release-review unit, and task `prepare-release-manifest-2026-05-05-13` found no selected-scope conflict in this manifest or `docs/progress-notes.md`. This pass updates only release-review documentation handoff evidence; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes remain untouched. No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret paths are visible beyond the four intentional untracked review inputs, so keep generated/local/scratch/secrets excluded unless explicitly promoted and revalidated. The recommended split remains seven review units with release-review docs last or bundled as context after the full pytest/build gate.

Fourteenth 2026-05-05 refresh: re-read status remains the same twenty-path release-review unit, and task `prepare-release-manifest-2026-05-05-14` found no selected-scope conflict in this manifest or `docs/progress-notes.md`. This docs-only refresh tightens the release-review handoff by restating the seven intentional file groups, the four intentional untracked review inputs, the scratch/local exclusions, and the PR split while preserving production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes untouched.

Fifteenth 2026-05-05 refresh: re-read status remains the same twenty-path release-review unit for task `prepare-release-manifest-2026-05-05-15`, with no selected-scope conflict in this manifest or `docs/progress-notes.md`. This docs-only pass preserves production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes untouched while keeping the handoff anchored to the seven intentional file groups, the four intentional untracked review inputs, the scratch/local exclusions, and the recommended seven-part PR split.

Sixteenth 2026-05-05 refresh: re-read status remains the same twenty-path release-review unit for task `prepare-release-manifest-2026-05-05-16`, with no selected-scope conflict in this manifest or `docs/progress-notes.md`. This docs-only pass preserves production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes untouched while keeping the handoff anchored to the seven intentional file groups, the four intentional untracked review inputs, the scratch/local exclusions, and the recommended seven-part PR split.

Seventeenth 2026-05-05 refresh: re-read status remains the same twenty-path release-review unit for task `prepare-release-manifest-2026-05-05-17`, with no selected-scope conflict in this manifest or `docs/progress-notes.md`. This docs-only pass preserves production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes untouched while keeping the handoff anchored to the seven intentional file groups, the four intentional untracked review inputs, the scratch/local exclusions, and the recommended seven-part PR split.

Eighteenth 2026-05-05 refresh: re-read status now shows a twenty-two-path release-review unit for task `prepare-release-manifest-2026-05-05-18`, with no selected-scope conflict in this manifest or `docs/progress-notes.md`. The added intentional slice is leaderboard zero-kill summary accounting (`backend/chain/leaderboard.py` and `tests/test_leaderboard.py`), so the handoff now tracks eight review groups. This docs-only pass preserves production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes untouched while keeping the four intentional untracked review inputs explicit.

Nineteenth 2026-05-05 refresh: re-read status remains the same twenty-two-path release-review unit for task `prepare-release-manifest-2026-05-05-19`, with no selected-scope conflict in this manifest or `docs/progress-notes.md`. This docs-only pass keeps the handoff current without touching production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, or prior dated release notes. The release unit still tracks eight review groups, four intentional untracked review inputs, no visible extra scratch/local files, and the same PR split with release-review docs last or bundled as context after the full gate.

Twentieth 2026-05-05 refresh: re-read status remains the same twenty-two-path release-review unit for task `prepare-release-manifest-2026-05-05-20`, with no selected-scope conflict in this manifest or `docs/progress-notes.md`. This docs-only pass preserves all existing implementation/test changes while refreshing the release handoff around the same eight intentional review groups, the four intentional untracked review inputs, and the same scratch/local exclusions. No production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, or prior dated release notes were edited by this pass.

Twenty-first 2026-05-05 refresh: re-read status remains the same twenty-two-path release-review unit for task `prepare-release-manifest-2026-05-05-21`, with no selected-scope conflict in this manifest or `docs/progress-notes.md`. This docs-only pass keeps the release review handoff current while preserving production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes untouched. The manifest still tracks eight intentional review groups, four intentional untracked review inputs, no visible extra scratch/local files, and the same PR split with release-review docs last or bundled as context after the full gate.

Twenty-second 2026-05-05 refresh: re-read status remains the same twenty-two-path release-review unit for task `prepare-release-manifest-2026-05-05-22`, with no selected-scope conflict in this manifest or `docs/progress-notes.md`. This docs-only pass keeps the reviewer handoff current while preserving production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes untouched. The handoff still tracks eight intentional review groups, four intentional untracked review inputs, no visible extra scratch/local files, and the same PR split with release-review docs last or bundled as context after the full gate.

Twenty-third 2026-05-05 refresh: re-read status remains the same twenty-two-path release-review unit for task `prepare-release-manifest-2026-05-05-23`, with no selected-scope conflict in this manifest or `docs/progress-notes.md`. This docs-only pass keeps the reviewer handoff current while preserving production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes untouched. The handoff still tracks eight intentional review groups, four intentional untracked review inputs, no visible extra scratch/local files, and the same PR split with release-review docs last or bundled as context after the full gate.

## Intentional file groups to review

1. Strict simulation API/config validation
   - `backend/api_server.py`
   - `backend/config.py`
   - `tests/test_api_server.py`
   - `tests/test_config.py`
   - Review intent: reject unknown top-level simulation request/config fields and nested pheromone fields so misspelled knobs cannot silently pass into release runs.

2. Proof transport metadata contract
   - `backend/chain/proof_spec.py`
   - `tests/test_proof_transport_metadata_contract.py` (untracked)
   - Review intent: pin proof transport metadata key order/requirements and fail if the artifact metadata contract drifts.

3. Chain submission config-hash normalization
   - `backend/chain/submit.py`
   - `tests/test_submit.py`
   - Review intent: normalize `config_hash` once so already-prefixed `0x` values are not double-prefixed before `cast estimate` or `cast send`.

4. Chain verification tolerance hardening
   - `backend/chain/verify.py`
   - `tests/test_verify.py`
   - Review intent: fail claimed numeric metrics missing from recomputed metrics with `missing_recomputed_metric` instead of silently skipping them.

5. Leaderboard zero-kill summary accounting
   - `backend/chain/leaderboard.py`
   - `tests/test_leaderboard.py`
   - Review intent: include zero-kill runs in average kill-rate summaries so leaderboard rollups do not inflate release-review results by filtering failed/zero-effect runs out of the denominator.

6. Attestation dry-run test hygiene
   - `tests/test_attestation_bot_dry_run.py`
   - Review intent: keep dummy dry-run JSON under `tmp_path` so the test does not depend on or leave root/test-tree scratch output.

7. Legacy CLI artifact compatibility
   - `backend/cli.py`
   - `backend/simulation_replay.py`
   - `tests/test_cli.py`
   - `tests/test_simulation_replay.py`
   - Review intent: make newly written CLI artifacts use canonical `num_bots`/`seed` config fields while preserving replay support for older artifacts that still contain `bots`.

8. Release-review documentation
   - `docs/progress-notes.md`
   - `docs/release-notes-2026-05-02.md`
   - `docs/release-notes-2026-05-03.md` (untracked)
   - `docs/release-notes-2026-05-04.md` (untracked)
   - `docs/release-notes-2026-05-05.md` (untracked)
   - Review intent: preserve dated release-review context; docs should travel last or as bundled reviewer context after the full gate.

## Validation evidence

Most recent pre-existing release gate from the 2026-05-04 twenty-third pass:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 205 passed in 3.72s.
- Frontend build completed in 1.89s with existing non-failing Browserslist database staleness and chunk-size warnings.

Current 2026-05-05 release gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 205 passed in 4.43s.
- Frontend build completed in 2.18s with existing non-failing Browserslist database staleness and chunk-size warnings.

Second 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 205 passed in 5.58s.
- Frontend build completed in 2.08s with existing non-failing Browserslist database staleness and chunk-size warnings.

Third 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 205 passed in 4.06s.
- Frontend build completed in 1.93s with existing non-failing Browserslist database staleness and chunk-size warnings.

Fourth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 205 passed in 4.57s.
- Frontend build completed in 9.28s with existing non-failing Browserslist database staleness and chunk-size warnings.

Fifth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 206 passed in 4.01s.
- Frontend build completed in 1.90s with existing non-failing Browserslist database staleness and chunk-size warnings.

Sixth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 206 passed in 3.85s.
- Frontend build completed in 1.90s with existing non-failing Browserslist database staleness and chunk-size warnings.

Seventh 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 206 passed in 4.11s.
- Frontend build completed in 2.01s with existing non-failing Browserslist database staleness and chunk-size warnings.

Ninth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 206 passed in 3.55s.
- Frontend build completed in 1.91s with existing non-failing Browserslist database staleness and chunk-size warnings.

Tenth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 206 passed in 3.05s.
- Frontend build completed in 1.84s with existing non-failing Browserslist database staleness and chunk-size warnings.

Eleventh 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 206 passed in 4.45s.
- Frontend build completed in 2.54s with existing non-failing Browserslist database staleness and chunk-size warnings.

Twelfth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 206 passed in 3.57s.
- Frontend build completed in 2.07s with existing non-failing Browserslist database staleness and chunk-size warnings.

Thirteenth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 206 passed in 4.46s.
- Frontend build completed in 2.12s with existing non-failing Browserslist database staleness and chunk-size warnings.

Fourteenth 2026-05-05 refresh gate:

- `uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 206 passed in 3.77s.
- Frontend build completed in 2.00s with existing non-failing Browserslist database staleness and chunk-size warnings.

Fifteenth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 206 passed in 4.64s.
- Frontend build completed in 2.19s with existing non-failing Browserslist database staleness and chunk-size warnings.

Sixteenth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 206 passed in 3.39s.
- Frontend build completed in 1.90s with existing non-failing Browserslist database staleness and chunk-size warnings.

Seventeenth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 207 passed in 4.44s.
- Frontend build completed in 2.00s with existing non-failing Browserslist database staleness and chunk-size warnings.

Eighteenth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 207 passed in 3.93s.
- Frontend build completed in 1.89s with existing non-failing Browserslist database staleness and chunk-size warnings.

Nineteenth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 207 passed in 2.97s.
- Frontend build completed in 1.87s with existing non-failing Browserslist database staleness and chunk-size warnings.

Twentieth 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 207 passed in 3.43s.
- Frontend build completed in 1.87s with existing non-failing Browserslist database staleness and chunk-size warnings.

Twenty-first 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 207 passed in 3.06s.
- Frontend build completed in 1.87s with existing non-failing Browserslist database staleness and chunk-size warnings.

Twenty-second 2026-05-05 refresh gate:

- `uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 207 passed in 3.77s.
- Frontend build completed in 1.96s with existing non-failing Browserslist database staleness and chunk-size warnings.

Twenty-third 2026-05-05 refresh gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 207 passed in 3.92s.
- Frontend build completed in 1.92s with existing non-failing Browserslist database staleness and chunk-size warnings.

## Likely scratch/local files to exclude

No separate scratch/local paths were visible in the pre-edit `git status --short` inventory. Keep excluding these unless a human intentionally promotes and revalidates them:

- Generated/build artifacts: `frontend/dist/`, `out/`, coverage reports, cache directories.
- Local runtime or dataset files: `data/api_runs.sqlite3`, local BraTS archives/extractions, ad-hoc local proof artifacts.
- Agent/operator state: `.hermes/`, autonomous-loop state files, local logs.
- Temporary probes/scratch: root-level `debug_*.py`, `patch_*.py`, `test_*_direct*.py`, `tests/debug_*.py`, temporary dummy JSON outputs.
- Secrets and local environment files beyond reviewed non-secret preview defaults.
- Unrelated proof/simulation/frontend changes not represented in the intentional groups above.

## Recommended PR split

1. PR 1 — strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, and `tests/test_config.py`.
2. PR 2 — proof transport metadata contract: `backend/chain/proof_spec.py` plus `tests/test_proof_transport_metadata_contract.py`.
3. PR 3 — submission config-hash normalization: `backend/chain/submit.py` plus `tests/test_submit.py`.
4. PR 4 — verification tolerance hardening: `backend/chain/verify.py` plus `tests/test_verify.py`.
5. PR 5 — leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py` plus `tests/test_leaderboard.py`.
6. PR 6 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with test-maintenance if reviewers prefer fewer PRs.
7. PR 7 — legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, and `tests/test_simulation_replay.py`.
8. PR 8 or bundled reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `docs/release-notes-2026-05-05.md`.
9. Do not include generated artifacts, local runtime data, autonomous-agent state, secrets, unrelated proof/simulation/frontend changes, or unreviewed local proof artifacts unless they are intentionally promoted and separately validated.

## Handoff checklist

- Confirm all four untracked review inputs are intentional before staging: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`.
- Treat the current twenty-two-path dirty tree as eight review units, not one monolithic commit; stage `docs/release-notes-2026-05-05.md` intentionally if the 2026-05-05 documentation context is included.
- Run `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md` after docs edits.
- Run `uv run --extra test pytest -q`.
- Run `npm --prefix frontend run build`.
- Do not push until the implementation/test slices and docs context are reviewed together or explicitly split.
