# Antelligence Release Review Manifest — 2026-05-04

Status: dirty tree prepared for release review without staging, committing, pushing, deploying, editing secrets, or touching production/runtime code in this loop.
Intent: convert the validated fifteen-path dirty tree into an explicit reviewer handoff with intentional file groups, validation evidence, scratch exclusions, and a recommended PR split.

## Current dirty inventory

`git status --short` at this pass shows fifteen dirty paths:

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

This pass intentionally refreshes only `docs/release-notes-2026-05-04.md` plus the progress-note pointer. It does not edit production code, secrets, generated data, debug scratch files, deployment configuration, local proof artifacts, or runtime data.

## Intentional file groups to review

1. Strict simulation API/config validation
   - `backend/api_server.py`
   - `backend/config.py`
   - `tests/test_api_server.py`
   - `tests/test_config.py`
   - Review intent: reject unknown simulation request/config and nested pheromone fields so misspelled knobs cannot silently pass into release runs.

2. Proof transport metadata contract
   - `backend/chain/proof_spec.py`
   - `tests/test_proof_transport_metadata_contract.py`
   - Review intent: pin proof transport metadata keys/order so artifact metadata drift is caught by regression coverage.

3. Chain submission config-hash normalization
   - `backend/chain/submit.py`
   - `tests/test_submit.py`
   - Review intent: preserve already-prefixed `0x` config hashes before `cast` submission or gas estimation.

4. Chain verification tolerance hardening
   - `backend/chain/verify.py`
   - `tests/test_verify.py`
   - Review intent: fail claimed numeric metrics missing from recomputed metrics with `missing_recomputed_metric` instead of silently skipping them.

5. Attestation dry-run test hygiene
   - `tests/test_attestation_bot_dry_run.py`
   - Review intent: keep dummy dry-run JSON under `tmp_path` so tests do not depend on or leave root/test-tree scratch output.

6. Release-review documentation
   - `docs/progress-notes.md`
   - `docs/release-notes-2026-05-02.md`
   - `docs/release-notes-2026-05-03.md`
   - `docs/release-notes-2026-05-04.md`
   - Review intent: preserve the dated manifest trail and reviewer handoff; docs should travel last or as bundled context.

## Validation evidence

Previous full gate from the 2026-05-03 twenty-third-pass handoff:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 201 passed in 4.95s.
- Frontend build passed in 2.21s with existing non-failing Browserslist database staleness and chunk-size warnings.

Current pass release gate:

- `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed.
- Pytest reported 201 passed in 4.13s.
- Frontend build completed in 3.16s with the existing non-failing Browserslist database staleness and large chunk-size warnings.

Second 2026-05-04 pass gate:

- Dirty inventory was re-read before editing; it now shows eleven paths because this `docs/release-notes-2026-05-04.md` manifest is also untracked.
- The intentional review groups are unchanged: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- This docs-only pass changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; no production code, tests, generated data, debug scratch files, deployment files, local proof artifacts, or secrets were edited.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 4.37s and the frontend build completed in 2.17s with existing non-failing Browserslist database staleness and large chunk-size warnings.

Third 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains eleven paths: the four implementation/test review slices, three dated release notes, `docs/progress-notes.md`, and the untracked proof metadata regression test.
- This docs-only pass changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; no production code, tests, generated data, debug scratch files, deployment files, local proof artifacts, or secrets were edited.
- Current validation passed before this note refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 6.13s and the frontend build completed in 2.74s with existing non-failing Browserslist database staleness and large chunk-size warnings.
- Reviewer action stays the same: preserve all three untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`) if this release-review unit is staged.

Fourth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains eleven paths; the release-review unit is still four implementation/test slices plus the dated documentation trail.
- This pass intentionally changed documentation only: `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, local proof artifacts, and debug scratch files were left untouched.
- Reviewer action remains: stage the proof metadata contract, submission normalization, verification tolerance hardening, attestation dry-run test hygiene, and documentation groups as separate small PRs or one clearly separated review stack.
- Scratch/local exclusions remain unchanged: generated artifacts, local runtime data, autonomous-loop state, temporary probes, deployment scratch, local proof artifacts, dummy outputs, and secrets stay out unless intentionally promoted and revalidated.
- Current validation passed twice in this loop: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; the first run reported 201 passed in 5.07s and frontend build in 2.49s, and the post-note rerun also passed with existing non-failing Browserslist database staleness and large chunk-size warnings.

Fifth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains eleven paths: `backend/chain/proof_spec.py`, `backend/chain/submit.py`, `backend/chain/verify.py`, `tests/test_proof_transport_metadata_contract.py`, `tests/test_submit.py`, `tests/test_verify.py`, `tests/test_attestation_bot_dry_run.py`, `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md`, and `docs/release-notes-2026-05-04.md`.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, local proof artifacts, runtime data, and debug scratch files were left untouched.
- Reviewer action remains unchanged: preserve the three untracked review inputs, exclude scratch/local artifacts, and split into proof metadata, submission normalization, verification hardening, attestation test hygiene, and documentation/context after the required full gate.

Sixth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains the same eleven paths; no new scratch/local paths, generated artifacts, local data, deployment files, debug probes, or secrets are visible in `git status --short`.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, generated data, deployment files, local proof artifacts, runtime data, and debug scratch files were left untouched.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 4.33s and frontend build completed in 2.07s with existing non-failing Browserslist database staleness and large chunk-size warnings.
- Reviewer action remains unchanged: preserve the three untracked review inputs, keep generated/local/scratch/secrets excluded, and split into proof metadata, submission normalization, verification hardening, attestation test hygiene, and documentation/context after the required full gate.

Seventh 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains the same eleven paths; no scratch/local files, generated outputs, runtime data, deployment files, debug probes, local proof artifacts, or secrets are visible as separate `git status --short` entries.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; existing production code, tests, untracked review inputs, generated data, and secrets were preserved untouched.
- Reviewer action remains unchanged: preserve all three untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`), keep scratch/local artifacts excluded, and split into proof metadata, submission normalization, verification hardening, attestation test hygiene, and documentation/context after validation.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 8.08s and frontend build completed in 3.28s with existing non-failing Browserslist database staleness and large chunk-size warnings.

Eighth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains the same eleven paths: three backend implementation paths, four test paths, the progress log, and three dated release-review notes.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were left untouched.
- The intentional groups and recommended PR split are unchanged: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context last after validation.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 3.81s and frontend build completed in 1.94s with existing non-failing Browserslist database staleness and large chunk-size warnings.

Ninth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains the same eleven paths; no extra scratch/local, generated, runtime, deployment, local proof artifact, debug probe, or secret paths are visible in `git status --short`.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; existing production code, tests, untracked review inputs, generated data, and secrets were preserved untouched.
- Reviewer action remains unchanged: preserve all three untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`) and split into proof metadata, submission normalization, verification hardening, attestation test hygiene, and documentation/context after validation.
- Recommended PR split stays five small units, with release-review docs last or bundled as reviewer context after the required full pytest/build gate.

Tenth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains the same eleven review paths; the only untracked entries are the two dated manifests plus the proof metadata regression test.
- This docs-only pass refreshed release-review evidence only and intentionally left production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files untouched.
- Reviewer action remains unchanged: stage/review proof metadata, submission normalization, verification hardening, attestation test hygiene, and documentation as five small units, with docs last or bundled only after the full gate.
- Scratch exclusion guidance remains unchanged: generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, and secrets stay out unless explicitly promoted and revalidated.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 4.54s and frontend build completed in 2.45s with existing non-failing Browserslist database staleness and large chunk-size warnings.

Eleventh 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains the same eleven review paths: three backend implementation files, four test files, the progress log, and three dated release-review notes.
- This docs-only pass refreshed the release-review manifest and progress pointer only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were left untouched.
- No separate scratch/local paths are visible in `git status --short`; continue excluding generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, and secrets unless intentionally promoted and revalidated.
- Recommended PR split remains five small review units after validation: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Preserve all three untracked review inputs during staging: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed and frontend build completed with existing non-failing Browserslist database staleness and large chunk-size warnings.

Twelfth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains the same eleven review paths; no extra scratch/local, generated, runtime, deployment, local proof artifact, debug probe, or secret entries are visible in `git status --short`.
- This docs-only pass changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, untracked review inputs, generated data, deployment files, runtime data, local proof artifacts, and secrets were preserved untouched.
- Reviewer action remains unchanged: preserve all three untracked review inputs, keep generated/local/scratch/secrets excluded, and split review into proof metadata, submission normalization, verification hardening, attestation dry-run test hygiene, and release-review documentation/context after the full gate.
- The release unit is still small enough for one stacked review, but the recommended PR split below remains safer for bisectability and focused reviewer ownership.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 4.38s and frontend build completed in 2.17s with existing non-failing Browserslist database staleness and large chunk-size warnings.

Thirteenth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains the same eleven review paths: three backend implementation files, four test files, the progress log, and three dated release-review notes.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were left untouched.
- Intentional file groups remain stable for review: proof transport metadata contract, chain submission config-hash normalization, chain verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- Scratch/local exclusions remain unchanged: generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets stay out unless intentionally promoted and revalidated.
- Recommended PR split remains five small units, with docs last or bundled as reviewer context only after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 3.90s and frontend build completed in 1.93s with existing non-failing Browserslist database staleness and large chunk-size warnings.

Fourteenth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains the same eleven review paths: proof transport metadata, submission normalization, verification hardening, attestation dry-run hygiene, and release-review documentation.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; no production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, or debug scratch files were edited.
- Intentional untracked review inputs remain explicit: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py` should be preserved if this release unit is staged.
- Scratch/local exclusions remain generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless intentionally promoted and revalidated.
- Recommended PR split remains five small units, with release-review documentation last or bundled as reviewer context only after the full pytest/build gate.

Fifteenth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains the same eleven review paths; no additional scratch/local, generated, runtime, deployment, local proof artifact, debug probe, or secret entries are visible in `git status --short`.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were left untouched.
- Intentional groups and recommended PR split are unchanged: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Preserve all three untracked review inputs if staging this unit: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`.
- Keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets excluded unless intentionally promoted and revalidated.

Sixteenth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and is now fifteen review paths: strict simulation API/config validation, proof transport metadata, submission normalization, verification hardening, attestation dry-run hygiene, and release-review documentation.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were left untouched.
- Intentional groups and recommended PR split are updated to six small units, with docs last or bundled as reviewer context after the full pytest/build gate.
- Preserve all three untracked review inputs if staging this unit: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`.
- Keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets excluded unless intentionally promoted and revalidated.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.71s and frontend build completed in 1.92s with existing non-failing Browserslist database staleness and large chunk-size warnings.

Seventeenth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains fifteen review paths; no extra scratch/local, generated, runtime, deployment, local proof artifact, debug probe, or secret entries are visible in `git status --short`.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; existing production code, tests, untracked review inputs, generated data, and secrets were preserved untouched.
- Intentional groups and recommended PR split remain six small review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Current validation evidence before this note refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.86s and frontend build completed in 1.93s with existing non-failing Browserslist database staleness and large chunk-size warnings.
- Preserve all three untracked review inputs if staging this unit: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`; keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets excluded unless intentionally promoted and revalidated.

Eighteenth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains fifteen review paths: strict simulation API/config validation, proof transport metadata, submission normalization, verification hardening, attestation dry-run hygiene, and release-review documentation.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were left untouched.
- Intentional groups and recommended PR split remain six small review units, with docs last or bundled as reviewer context after the full pytest/build gate.
- No separate scratch/local, generated, runtime, deployment, local proof artifact, debug probe, or secret entries are visible in `git status --short`; keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets excluded unless explicitly promoted and revalidated.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 4.46s and frontend build completed in 2.23s with existing non-failing Browserslist database staleness and chunk-size warnings.
- Preserve all three untracked review inputs if staging this unit: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`.

Nineteenth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains fifteen review paths; no conflict with existing user changes was observed inside the selected docs-only scope.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were left untouched.
- Intentional groups and recommended PR split remain six small review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Preserve all three untracked review inputs if staging this unit: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`.
- Scratch/local exclusions remain generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless explicitly promoted and revalidated.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.73s and frontend build completed in 1.84s with existing non-failing Browserslist database staleness and chunk-size warnings.


Twentieth 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains fifteen review paths; no conflict with existing user changes was observed inside the selected docs-only scope.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were left untouched.
- Intentional groups and recommended PR split remain six small review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Preserve all three untracked review inputs if staging this unit: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`.
- Scratch/local exclusions remain generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets unless explicitly promoted and revalidated.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.96s and frontend build completed in 1.96s with existing non-failing Browserslist database staleness and chunk-size warnings.

Twenty-first 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains fifteen review paths; the selected docs-only scope has no observed conflict with existing user changes.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were left untouched.
- Intentional groups and recommended PR split remain six small review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Likely scratch/local exclusions remain unchanged: no extra scratch/local, generated, runtime, deployment, local proof artifact, debug probe, or secret paths are visible in `git status --short`; keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless promoted and revalidated.
- Preserve all three untracked review inputs if staging this unit: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`; docs should remain PR 6 or bundled reviewer context after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.79s and frontend build completed in 1.88s with existing non-failing Browserslist database staleness and chunk-size warnings.

Twenty-second 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains fifteen review paths; the selected docs-only scope has no observed conflict with existing user changes.
- This pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were left untouched.
- Intentional groups and recommended PR split remain six small review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Likely scratch/local exclusions remain unchanged: no extra scratch/local, generated, runtime, deployment, local proof artifact, debug probe, or secret paths are visible in `git status --short`; keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless promoted and revalidated.
- Preserve all three untracked review inputs if staging this unit: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`; docs should remain PR 6 or bundled reviewer context after the full pytest/build gate.
- Recommended PR split remains: PR 1 strict simulation validation, PR 2 proof metadata, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run test hygiene, and PR 6/bundled reviewer context for release-review docs.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 5.40s and frontend build completed in 2.67s with existing non-failing Browserslist database staleness and chunk-size warnings.

Twenty-third 2026-05-04 pass gate:

- Dirty inventory was re-read before editing and remains fifteen review paths; no conflict with existing user changes was observed inside the selected documentation scope.
- This docs-only pass intentionally changed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were left untouched.
- Intentional file groups remain six small release-review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Likely scratch/local exclusions remain unchanged: no extra scratch/local, generated, runtime, deployment, local proof artifact, debug probe, or secret paths are visible in `git status --short`; keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless promoted and revalidated.
- Preserve all three untracked review inputs if staging this unit: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`.
- Recommended PR split remains: PR 1 strict simulation validation, PR 2 proof metadata, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run test hygiene, and PR 6/bundled reviewer context for release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.72s and frontend build completed in 1.89s with existing non-failing Browserslist database staleness and chunk-size warnings.

## Likely scratch/local files to exclude

None are currently visible as separate scratch/local paths in `git status --short`. Keep excluding these unless a human intentionally promotes and revalidates them:

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
5. PR 5 — attestation dry-run test hygiene: `tests/test_attestation_bot_dry_run.py`, or bundle with test-maintenance if reviewers prefer fewer PRs.
6. PR 6 or bundled reviewer context — release-review documentation: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md`, and `docs/release-notes-2026-05-04.md`.
7. Do not include generated artifacts, local runtime data, autonomous-agent state, secrets, unrelated proof/simulation/frontend changes, or unreviewed local proof artifacts unless they are intentionally promoted and separately validated.

## Handoff checklist

- Confirm all three untracked review inputs are intentional before staging: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py`.
- Run `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md` after docs edits.
- Run `uv run --extra test pytest -q`.
- Run `npm --prefix frontend run build`.
- Do not push until the implementation/test slices and docs context are reviewed together or explicitly split.
