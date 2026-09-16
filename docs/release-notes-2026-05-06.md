# Antelligence Release Review Manifest — 2026-05-06

Status: dirty tree prepared for release review without staging, committing, pushing, deploying, editing secrets, or touching production/runtime code in this loop.
Intent: keep the validated but dirty working tree reviewable as a release unit, with dated reviewer context instead of another broad audit.

## Current dirty inventory

`git status --short` before this docs-only pass showed twenty-two dirty paths:

- `backend/api_server.py`
- `backend/chain/leaderboard.py`
- `backend/chain/proof_spec.py`
- `backend/chain/submit.py`
- `backend/chain/verify.py`
- `backend/cli.py`
- `backend/config.py`
- `backend/simulation_replay.py`
- `docs/progress-notes.md`
- `docs/release-notes-2026-05-02.md`
- `docs/release-notes-2026-05-03.md` (untracked)
- `docs/release-notes-2026-05-04.md` (untracked)
- `docs/release-notes-2026-05-05.md` (untracked)
- `tests/test_api_server.py`
- `tests/test_attestation_bot_dry_run.py`
- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_leaderboard.py`
- `tests/test_proof_transport_metadata_contract.py` (untracked)
- `tests/test_simulation_replay.py`
- `tests/test_submit.py`
- `tests/test_verify.py`

This pass intentionally adds only this 2026-05-06 manifest plus a progress-note pointer. It preserves existing production code, tests, prior release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files untouched.

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
   - Review intent: pin proof transport metadata key order/requirements and fail if artifact metadata drifts.

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
   - `docs/release-notes-2026-05-06.md` (untracked)
   - Review intent: preserve dated release-review context; docs should travel last or as bundled reviewer context after the full gate.

## Validation evidence

Most recent pre-existing release gate from the 2026-05-05 twenty-third pass:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 207 passed in 3.92s.
- Frontend build completed in 1.92s with existing non-failing Browserslist/chunk-size warnings.

Current 2026-05-06 release gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 207 passed in 5.26s.
- Frontend build completed in 1.95s with existing non-failing Browserslist/chunk-size warnings.

## Likely scratch/local files to exclude

No separate scratch/local paths were visible in the pre-edit `git status --short` inventory beyond the intentional untracked review inputs. Keep excluding these unless a human intentionally promotes and revalidates them:

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
8. PR 8 or bundled reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `docs/release-notes-2026-05-06.md`.
9. Do not include generated artifacts, local runtime data, autonomous-agent state, secrets, unrelated proof/simulation/frontend changes, or unreviewed local proof artifacts unless they are intentionally promoted and separately validated.

## Handoff checklist

- Confirm all five untracked review inputs are intentional before staging: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `docs/release-notes-2026-05-06.md`, and `tests/test_proof_transport_metadata_contract.py`.
- Treat the current release unit as eight review groups, not one monolithic commit; stage `docs/release-notes-2026-05-06.md` intentionally if the 2026-05-06 documentation context is included.
- Run `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md` after docs edits.
- Run `uv run --extra test pytest -q`.
- Run `npm --prefix frontend run build`.
- Do not push until the implementation/test slices and docs context are reviewed together or explicitly split.

## Second 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-2`. This refresh re-read the dirty tree after the first 2026-05-06 manifest and kept scope docs-only: this file plus `docs/progress-notes.md`. No production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, or prior dated release notes were edited in this pass.

### Re-read dirty inventory

`git status --short` showed twenty-three dirty paths because `docs/release-notes-2026-05-06.md` is now also an intentional untracked review input. The implementation/test groups are unchanged from the manifest above:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Exclude from staging unless explicitly promoted

No new scratch/local paths appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build output, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc debug probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer intentionally promotes them and reruns the gate.

### Recommended PR split

Keep the same eight review units: strict simulation validation, proof metadata contract, submission normalization, verification hardening, leaderboard summary accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context last or bundled only after the full backend/frontend gate.

### Validation for this refresh

Passed for this refresh: `uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 4.05s and frontend build completed in 2.23s with existing non-failing Browserslist/chunk-size warnings.

## Third 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-3`. This refresh re-read the working tree and kept the selected scope limited to this manifest plus `docs/progress-notes.md`; production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were preserved untouched.

### Re-read dirty inventory

`git status --short` still showed twenty-three dirty paths. The reviewable implementation/test slices remain unchanged, and the extra untracked path versus the first 2026-05-06 inventory is this manifest itself:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Keep excluding generated/build outputs, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, unrelated proof/simulation/frontend changes, and secrets unless explicitly promoted and revalidated.

### Recommended PR split

Keep eight small review units: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard zero-kill accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review documentation/context after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 7.26s and frontend build completed in 7.05s with existing non-failing Browserslist/chunk-size warnings.

## Fourth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-4`. This refresh re-read the repo state before editing and kept the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, or debug scratch files were edited in this pass.

### Re-read dirty inventory

`git status --short` still showed twenty-three dirty paths. The reviewable groups remain unchanged from the third refresh:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, unrelated proof/simulation/frontend changes, and secrets unless explicitly promoted and revalidated.

### Recommended PR split

Keep the release unit split into eight small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard zero-kill accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review documentation/context after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 3.73s and frontend build completed in 1.93s with existing non-failing Browserslist/chunk-size warnings.

## Fifth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-5`. This refresh re-read the repo state before editing and kept the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, or debug scratch files were edited in this pass.

### Re-read dirty inventory

`git status --short` still showed twenty-three dirty paths. The reviewable groups remain unchanged from the fourth refresh:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, unrelated proof/simulation/frontend changes, and secrets unless explicitly promoted and revalidated.

### Recommended PR split

Keep the release unit split into eight small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard zero-kill accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review documentation/context after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 4.13s and frontend build completed in 2.49s with existing non-failing Browserslist/chunk-size warnings.

## Corrected fifth 2026-05-06 release review manifest

Task: `prepare-release-manifest-2026-05-06-5`. This correction re-read the live dirty tree after the prior analysis-only attempt and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, or deploy state were edited in this pass.

### Re-read dirty inventory

`git status --short` now shows twenty-five dirty paths. The two additional paths relative to the stale fifth refresh are an intentional verifier-admin address-validation slice: `backend/chain/verifier_admin.py` and `tests/test_verifier_admin.py`. The reviewable groups are:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, unrelated proof/simulation/frontend changes, local proof artifacts, and secrets unless explicitly promoted and revalidated.

### Recommended PR split

Split the dirty tree into nine small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review documentation/context after the full pytest/build gate.

### Validation for this correction

Passed for this correction: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 4.95s and frontend build completed in 2.82s with existing non-failing Browserslist/chunk-size warnings.

## Sixth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-6`. This refresh re-read the live working tree after the corrected fifth pass and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, or deploy state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-five dirty paths. The release-review groups remain unchanged from the corrected fifth pass:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into nine small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 6.88s and frontend build completed in 3.43s with existing non-failing Browserslist/chunk-size warnings.

## Seventh 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-7`. This refresh re-read the live working tree and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, or deploy state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-five dirty paths. The release-review groups remain unchanged from the corrected fifth and sixth passes:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into nine small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 4.47s and frontend build completed in 2.55s with existing non-failing Browserslist/chunk-size warnings.

## Eighth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-8`. This refresh re-read the live working tree and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-five dirty paths. The release-review groups remain unchanged from the corrected fifth through seventh passes:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into nine small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 3.86s and frontend build completed in 2.32s with existing non-failing Browserslist/chunk-size warnings.

## Ninth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-9`. This refresh re-read the live working tree and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-five dirty paths. The release-review groups remain unchanged from the corrected fifth through eighth passes:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into nine small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 3.56s and frontend build completed in 1.87s with existing non-failing Browserslist/chunk-size warnings.

## Tenth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-10`. This refresh re-read the live working tree and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-five dirty paths. The release-review groups remain unchanged from the corrected fifth through ninth passes:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into nine small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 4.05s and frontend build completed in 1.96s with existing non-failing Browserslist/chunk-size warnings.

## Eleventh 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-11`. This refresh re-read the live working tree and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-five dirty paths. The release-review groups remain unchanged from the corrected fifth through tenth passes:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into nine small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 4.08s and frontend build completed in 2.10s with existing non-failing Browserslist/chunk-size warnings.


## Twelfth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-12`. This refresh re-read the live working tree and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-five dirty paths. The release-review groups remain unchanged from the corrected fifth through eleventh passes:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into nine small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 3.83s and frontend build completed in 2.01s with existing non-failing Browserslist/chunk-size warnings.

## Thirteenth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-13`. This refresh re-read the live working tree and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-five dirty paths. The release-review groups remain unchanged from the corrected fifth through twelfth passes:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into nine small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 3.52s and frontend build completed in 1.98s with existing non-failing Browserslist/chunk-size warnings.

## Fourteenth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-14`. This refresh re-read the live working tree and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-five dirty paths. The release-review groups remain unchanged from the corrected fifth through thirteenth passes:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into nine small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 4.21s and frontend build completed in 1.98s with existing non-failing Browserslist/chunk-size warnings.

## Fifteenth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-15`. This refresh re-read the live working tree and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-five dirty paths. The release-review groups remain unchanged from the corrected fifth through fourteenth passes:

- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the five intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into nine small review chunks: PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 4.08s and frontend build completed in 2.10s with existing non-failing Browserslist/chunk-size warnings.

## Sixteenth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-16`. This refresh re-read the live working tree and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` now shows twenty-seven dirty paths. The added release-review surface versus the prior recorded scorecard is README public-readiness documentation plus its public-readiness test; the rest of the implementation/test slices remain the established review units:

- README public-readiness documentation: `README.md`, `tests/test_readme_public_readiness.py` (untracked).
- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the six intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into ten small review chunks: PR 1 README public-readiness docs, PR 2 strict simulation validation, PR 3 proof metadata contract, PR 4 submission normalization, PR 5 verification hardening, PR 6 verifier-admin address validation, PR 7 leaderboard zero-kill accounting, PR 8 attestation dry-run hygiene, PR 9 legacy CLI artifact compatibility, and PR 10 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 209 passed in 3.94s and frontend build completed in 1.93s with existing non-failing Browserslist/chunk-size warnings.

## Seventeenth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-17`. This refresh re-read the live working tree and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-seven dirty paths. The release-review groups remain unchanged from the sixteenth pass:

- README public-readiness documentation: `README.md`, `tests/test_readme_public_readiness.py` (untracked).
- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the six intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into ten small review chunks: PR 1 README public-readiness docs, PR 2 strict simulation validation, PR 3 proof metadata contract, PR 4 submission normalization, PR 5 verification hardening, PR 6 verifier-admin address validation, PR 7 leaderboard zero-kill accounting, PR 8 attestation dry-run hygiene, PR 9 legacy CLI artifact compatibility, and PR 10 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 209 passed in 4.04s and frontend build completed in 2.19s with existing non-failing Browserslist/chunk-size warnings.
## Eighteenth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-18`. This refresh re-read the live working tree before editing and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-seven dirty paths. The release-review groups remain unchanged from the seventeenth pass:

- README public-readiness documentation: `README.md`, `tests/test_readme_public_readiness.py` (untracked).
- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the six intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into ten small review chunks: PR 1 README public-readiness docs, PR 2 strict simulation validation, PR 3 proof metadata contract, PR 4 submission normalization, PR 5 verification hardening, PR 6 verifier-admin address validation, PR 7 leaderboard zero-kill accounting, PR 8 attestation dry-run hygiene, PR 9 legacy CLI artifact compatibility, and PR 10 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 209 passed in 11.96s and frontend build completed in 2.02s with existing non-failing Browserslist/chunk-size warnings

## Nineteenth 2026-05-06 release review refresh

Task: `prepare-release-manifest-2026-05-06-19`. This refresh re-read the live working tree before editing and keeps the selected scope docs-only: this manifest plus `docs/progress-notes.md`. No production code, tests, prior dated release notes, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state were edited in this pass.

### Re-read dirty inventory

`git status --short` still shows twenty-seven dirty paths. The release-review groups remain unchanged from the eighteenth pass:

- README public-readiness documentation: `README.md`, `tests/test_readme_public_readiness.py` (untracked).
- Strict simulation API/config validation: `backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`.
- Proof transport metadata contract: `backend/chain/proof_spec.py`, `tests/test_proof_transport_metadata_contract.py` (untracked).
- Submission config-hash normalization: `backend/chain/submit.py`, `tests/test_submit.py`.
- Verification tolerance hardening: `backend/chain/verify.py`, `tests/test_verify.py`.
- Verifier-admin address validation: `backend/chain/verifier_admin.py`, `tests/test_verifier_admin.py`.
- Leaderboard zero-kill summary accounting: `backend/chain/leaderboard.py`, `tests/test_leaderboard.py`.
- Attestation dry-run hygiene: `tests/test_attestation_bot_dry_run.py`.
- Legacy CLI artifact compatibility: `backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, `tests/test_simulation_replay.py`.
- Release-review documentation/context: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md` (untracked), `docs/release-notes-2026-05-04.md` (untracked), `docs/release-notes-2026-05-05.md` (untracked), and `docs/release-notes-2026-05-06.md` (untracked).

### Scratch/local exclusions

No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, cache/coverage, or secret path appeared in the re-read status beyond the six intentional untracked review inputs. Continue excluding generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy JSON outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless a reviewer explicitly promotes them and reruns the full gate.

### Recommended PR split

Keep the dirty tree split into ten small review chunks: PR 1 README public-readiness docs, PR 2 strict simulation validation, PR 3 proof metadata contract, PR 4 submission normalization, PR 5 verification hardening, PR 6 verifier-admin address validation, PR 7 leaderboard zero-kill accounting, PR 8 attestation dry-run hygiene, PR 9 legacy CLI artifact compatibility, and PR 10 or bundled release-review documentation/context only after the full pytest/build gate.

### Validation for this refresh

Passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 209 passed in 4.17s and frontend build completed in 2.01s with existing non-failing Browserslist/chunk-size warnings.
