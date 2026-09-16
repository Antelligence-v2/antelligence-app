# Antelligence Progress Notes

Purpose
- Keep a concise development record for future publication, patent drafting, and technical retrospectives.
- Focus on architectural milestones, verifier/proof evolution, deployment checkpoints, and validation evidence.

## 2026-05-06 — Release review manifest prepared

The dirty tree has a fresh dated release-review manifest at `docs/release-notes-2026-05-06.md`. This docs-only pass changed only the new manifest plus this progress pointer and preserved existing production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files untouched.

Summary:
- Pre-edit dirty inventory was twenty-two paths: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and dated release-review documentation.
- Intentional untracked review inputs are now five paths to preserve during staging: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `docs/release-notes-2026-05-06.md`, and `tests/test_proof_transport_metadata_contract.py`.
- Likely scratch/local exclusions remain absent beyond intentional untracked review inputs; keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains eight small review units: strict simulation validation, proof metadata contract, submission normalization, verification hardening, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context last after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 5.26s and frontend build completed in 1.95s with existing non-failing Browserslist/chunk-size warnings.

Second 2026-05-06 release review refresh:
- Re-read dirty inventory is now twenty-three paths only because `docs/release-notes-2026-05-06.md` itself is part of the intentional untracked documentation inputs; no selected-scope conflict was observed in `docs/progress-notes.md` or `docs/release-notes-2026-05-06.md`.
- This docs-only pass refreshed the reviewer handoff for task `prepare-release-manifest-2026-05-06-2`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional file groups remain eight review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, leaderboard zero-kill summary accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Preserve all five untracked review inputs during staging (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `docs/release-notes-2026-05-06.md`, and `tests/test_proof_transport_metadata_contract.py`) while excluding generated/local/scratch/secrets unless intentionally promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard summary accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review docs after the full pytest/build gate.
- Current validation passed for this refresh: `uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 4.05s and frontend build completed in 2.23s with existing non-failing Browserslist/chunk-size warnings.

Third 2026-05-06 release review refresh:
- Re-read dirty inventory remains twenty-three paths for task `prepare-release-manifest-2026-05-06-3`, and the selected docs-only scope is still conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-06.md`.
- This pass refreshed only the release-review handoff; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional review groups remain eight units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, leaderboard zero-kill summary accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the five intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `docs/release-notes-2026-05-06.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard zero-kill accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review docs after the full pytest/build gate.
- Current validation passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 7.26s and frontend build completed in 7.05s with existing non-failing Browserslist/chunk-size warnings.

Fourth 2026-05-06 release review refresh:
- Re-read dirty inventory remains twenty-three paths for task `prepare-release-manifest-2026-05-06-4`, with no selected-scope conflict in `docs/progress-notes.md` or `docs/release-notes-2026-05-06.md`.
- This docs-only pass refreshed only the 2026-05-06 release-review manifest and this progress note; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional file groups remain eight review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, leaderboard zero-kill summary accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the five intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `docs/release-notes-2026-05-06.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard zero-kill accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review docs after the full pytest/build gate.
- Current validation passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 3.73s and frontend build completed in 1.93s with existing non-failing Browserslist/chunk-size warnings.

Fifth 2026-05-06 release review refresh:
- Re-read dirty inventory remains twenty-three paths for task `prepare-release-manifest-2026-05-06-5`, and the selected docs-only scope remains conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-06.md`.
- This pass refreshed only the release-review handoff; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional file groups remain eight review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, leaderboard zero-kill summary accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the five intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `docs/release-notes-2026-05-06.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard zero-kill accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review docs after the full pytest/build gate.
- Current validation passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 4.13s and frontend build completed in 2.49s with existing non-failing Browserslist/chunk-size warnings.

Seventh 2026-05-06 release review refresh:
- Re-read dirty inventory now remains twenty-five paths for task `prepare-release-manifest-2026-05-06-7`, with the selected docs-only scope still limited to `docs/progress-notes.md` plus `docs/release-notes-2026-05-06.md`.
- This pass refreshed release-review handoff context only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, prior dated release notes, commits, pushes, and deploy state were preserved untouched.
- Intentional file groups remain nine review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the five intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `docs/release-notes-2026-05-06.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, cache/coverage, local runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review docs after the full pytest/build gate.
- Current validation passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 4.47s and frontend build completed in 2.55s with existing non-failing Browserslist/chunk-size warnings.

Thirteenth 2026-05-06 release review refresh:
- Re-read dirty inventory remains twenty-five paths for task `prepare-release-manifest-2026-05-06-13`, with the selected docs-only scope still limited to `docs/progress-notes.md` plus `docs/release-notes-2026-05-06.md`.
- This pass refreshed release-review handoff context only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, prior dated release notes, commits, pushes, deploy state, and staging state were preserved untouched.
- Intentional file groups remain nine review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the five intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `docs/release-notes-2026-05-06.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, cache/coverage, local runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review docs after the full pytest/build gate.
- Current validation passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 3.52s and frontend build completed in 1.98s with existing non-failing Browserslist/chunk-size warnings.

Fourteenth 2026-05-06 release review refresh:
- Re-read dirty inventory remains twenty-five paths for task `prepare-release-manifest-2026-05-06-14`, and the selected docs-only scope remains conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-06.md`.
- This pass refreshed release-review staging guidance only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, prior dated release notes, commits, pushes, deploy state, and staging state were preserved untouched.
- Intentional file groups remain nine review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the five intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `docs/release-notes-2026-05-06.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, cache/coverage, local runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 verifier-admin address validation, PR 6 leaderboard zero-kill accounting, PR 7 attestation dry-run hygiene, PR 8 legacy CLI artifact compatibility, and PR 9 or bundled release-review docs after the full pytest/build gate.
- Current validation passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 208 passed in 4.21s and frontend build completed in 1.98s with existing non-failing Browserslist/chunk-size warnings.

Sixteenth 2026-05-06 release review refresh:
- Re-read dirty inventory is now twenty-seven paths for task `prepare-release-manifest-2026-05-06-16`, and the selected docs-only scope remains conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-06.md`.
- This pass refreshed release-review handoff evidence only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, prior dated release notes, commits, pushes, deploy state, and staging state were preserved untouched.
- Intentional file groups now split into ten review units: README public-readiness documentation, strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the six intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `docs/release-notes-2026-05-06.md`, `tests/test_proof_transport_metadata_contract.py`, and `tests/test_readme_public_readiness.py`); keep generated/build output, cache/coverage, local runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split is PR 1 README public-readiness docs, PR 2 strict simulation validation, PR 3 proof metadata contract, PR 4 submission normalization, PR 5 verification hardening, PR 6 verifier-admin address validation, PR 7 leaderboard zero-kill accounting, PR 8 attestation dry-run hygiene, PR 9 legacy CLI artifact compatibility, and PR 10 or bundled release-review docs after the full pytest/build gate.
- Current validation passed for this refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 209 passed in 3.94s and frontend build completed in 1.93s with existing non-failing Browserslist/chunk-size warnings.

## 2026-05-05 — Release review manifest prepared

The dirty tree has a fresh dated release-review manifest at `docs/release-notes-2026-05-05.md`. This docs-only pass changed only the new manifest plus this progress pointer and preserved existing production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files untouched.

Summary:
- Current pre-edit dirty inventory remained fifteen paths: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and dated release-review documentation.
- Intentional untracked review inputs are now four paths to preserve during staging: `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`.
- Likely scratch/local exclusions remain absent from `git status --short`; keep generated/build output, local runtime data, autonomous-loop state, temporary probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains six small review units: strict simulation validation, proof metadata contract, submission normalization, verification hardening, attestation dry-run test hygiene, and release-review documentation/context last after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 4.43s and frontend build completed in 2.18s with existing non-failing Browserslist database staleness and chunk-size warnings.

Second 2026-05-05 release review refresh:
- Re-read dirty inventory is now sixteen paths only because `docs/release-notes-2026-05-05.md` is part of the intentional untracked documentation inputs; no selected-scope conflict was observed.
- This docs-only pass refined the release handoff without editing production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, or debug scratch files.
- Intentional review groups remain six small units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Preserve all four untracked review inputs during staging (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `tests/test_proof_transport_metadata_contract.py`) and keep generated/local/scratch/secrets excluded unless explicitly promoted and revalidated.
- Final gate for this refresh passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 5.58s and frontend build completed in 2.08s with existing non-failing Browserslist/chunk-size warnings.

Third 2026-05-05 release review refresh:
- Re-read dirty inventory remains sixteen paths and the selected docs-only scope is conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-05.md`.
- This pass refreshed reviewer handoff evidence only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional review groups remain six small units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Preserve all four untracked review inputs during staging (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `tests/test_proof_transport_metadata_contract.py`) and keep generated/local/scratch/secrets excluded unless explicitly promoted and revalidated.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 4.06s and frontend build completed in 1.93s with existing non-failing Browserslist/chunk-size warnings.

Fourth 2026-05-05 release review refresh:
- Re-read dirty inventory remains sixteen paths and still maps cleanly to the same six reviewer units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- This docs-only pass refreshed the manifest/progress handoff only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Scratch/local exclusions remain absent beyond intentional untracked review inputs; keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Preserve all four untracked review inputs during staging (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `tests/test_proof_transport_metadata_contract.py`) and keep docs last or bundled as reviewer context after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 4.57s and frontend build completed in 9.28s with existing non-failing Browserslist/chunk-size warnings.

Fifth 2026-05-05 release review refresh:
- Re-read dirty inventory is now twenty paths: the prior six review units plus a legacy CLI artifact-compatibility slice (`backend/cli.py`, `backend/simulation_replay.py`, `tests/test_cli.py`, and `tests/test_simulation_replay.py`).
- This docs-only pass updated the reviewer handoff only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional review groups now split into seven units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Scratch/local exclusions remain absent beyond intentional untracked review inputs; keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split is PR 1 strict simulation validation, PR 2 proof metadata, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled reviewer context for release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 206 passed in 4.01s and frontend build completed in 1.90s with existing non-failing Browserslist/chunk-size warnings.

Sixth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths and still maps cleanly to seven release-review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- This docs-only pass refreshed the dated release-review handoff only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret paths are visible beyond the intentional untracked review inputs; keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled reviewer context for release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 206 passed in 3.85s and frontend build completed in 1.90s with existing non-failing Browserslist/chunk-size warnings.

Seventh 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths and still has no selected-scope conflict in `docs/progress-notes.md` or `docs/release-notes-2026-05-05.md`.
- This docs-only pass refreshed the release-review handoff only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional review groups remain seven small units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Staging guidance remains explicit: preserve the four untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`) while excluding generated/local/scratch/secrets unless intentionally promoted and revalidated.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 206 passed in 4.11s and frontend build completed in 2.01s with existing non-failing Browserslist/chunk-size warnings.

Eighth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths, and the selected docs-only scope is still conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-05.md`.
- This pass preserved existing production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes while refreshing only the release-review handoff.
- The release unit remains seven small review groups: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Scratch/local exclusions remain unchanged: no extra generated/build output, runtime data, autonomous-loop state, debug probes, local proof artifacts, or secrets are visible beyond the four intentional untracked review inputs.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled release-review docs after the full gate.

Ninth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths, and the selected docs-only scope remains conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-05.md`.
- This refresh only sharpened the release-review handoff; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional review groups remain seven small units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 206 passed in 3.55s and frontend build completed in 1.91s with existing non-failing Browserslist/chunk-size warnings.

Tenth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths and the selected docs-only scope remains conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-05.md`.
- This pass refreshed only the release-review handoff; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional release groups remain seven reviewable units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 206 passed in 3.05s and frontend build completed in 1.84s with existing non-failing Browserslist/chunk-size warnings.

Eleventh 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths: seven production/test review slices plus dated release-review documentation, with the selected scope still limited to `docs/progress-notes.md` and `docs/release-notes-2026-05-05.md`.
- This pass refreshed only the release-review manifest/progress pointer; existing production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional review groups remain seven units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 206 passed in 4.45s and frontend build completed in 2.54s with existing non-failing Browserslist/chunk-size warnings.

Twelfth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths and the selected release-review scope remains docs-only: `docs/progress-notes.md` plus `docs/release-notes-2026-05-05.md`.
- This pass refreshed only the dated reviewer manifest for task `prepare-release-manifest-2026-05-05-12`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional file groups remain seven review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Scratch/local exclusions remain absent beyond the four intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains seven small units with release-review docs last or bundled as context after the full pytest/build gate: strict simulation validation, proof metadata, submission normalization, verification hardening, attestation dry-run hygiene, legacy CLI artifact compatibility, and documentation.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 206 passed in 3.57s and frontend build completed in 2.07s with existing non-failing Browserslist/chunk-size warnings.

Thirteenth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths and the selected task `prepare-release-manifest-2026-05-05-13` is still safe as a docs-only refresh: `docs/progress-notes.md` plus `docs/release-notes-2026-05-05.md`.
- This pass updated only release-review handoff evidence; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional file groups remain seven review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 206 passed in 4.46s and frontend build completed in 2.12s with existing non-failing Browserslist/chunk-size warnings.

Fourteenth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths and selected task `prepare-release-manifest-2026-05-05-14` remains safe as a docs-only refresh in `docs/progress-notes.md` plus `docs/release-notes-2026-05-05.md`.
- This pass refreshed release-review staging guidance only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional file groups remain seven review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 206 passed in 3.77s and frontend build completed in 2.00s with existing non-failing Browserslist/chunk-size warnings.

Fifteenth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths and selected task `prepare-release-manifest-2026-05-05-15` remains safe as a docs-only refresh in `docs/progress-notes.md` plus `docs/release-notes-2026-05-05.md`.
- This pass refreshed release-review handoff evidence only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional file groups remain seven review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 206 passed in 4.64s and frontend build completed in 2.19s with existing non-failing Browserslist/chunk-size warnings.

Sixteenth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths and selected task `prepare-release-manifest-2026-05-05-16` remains safe as a docs-only refresh in `docs/progress-notes.md` plus `docs/release-notes-2026-05-05.md`.
- This pass refreshed release-review handoff evidence only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional file groups remain seven review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 206 passed in 3.39s and frontend build completed in 1.90s with existing non-failing Browserslist/chunk-size warnings.

Seventeenth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty paths and selected task `prepare-release-manifest-2026-05-05-17` remains safe as a docs-only refresh in `docs/progress-notes.md` plus `docs/release-notes-2026-05-05.md`.
- This pass refreshed release-review handoff evidence only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional file groups remain seven review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run hygiene, PR 6 legacy CLI artifact compatibility, and PR 7 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 4.44s and frontend build completed in 2.00s with existing non-failing Browserslist/chunk-size warnings.

Eighteenth 2026-05-05 release review refresh:
- Re-read dirty inventory is now twenty-two paths for task `prepare-release-manifest-2026-05-05-18`; the added review slice is leaderboard zero-kill summary accounting (`backend/chain/leaderboard.py` and `tests/test_leaderboard.py`).
- This docs-only pass refreshed only `docs/progress-notes.md` and `docs/release-notes-2026-05-05.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional file groups now split into eight review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, leaderboard zero-kill summary accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split is PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard summary accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 3.93s and frontend build completed in 1.89s with existing non-failing Browserslist/chunk-size warnings.

Nineteenth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty-two paths for task `prepare-release-manifest-2026-05-05-19`, with no selected-scope conflict in `docs/progress-notes.md` or `docs/release-notes-2026-05-05.md`.
- This docs-only pass preserved production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes untouched while refreshing only the release-review handoff.
- Intentional file groups remain eight review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, leaderboard zero-kill summary accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs; keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard summary accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 2.97s and frontend build completed in 1.87s with existing non-failing Browserslist/chunk-size warnings.

Twenty-first 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty-two paths for task `prepare-release-manifest-2026-05-05-21`, with no selected-scope conflict in `docs/progress-notes.md` or `docs/release-notes-2026-05-05.md`.
- This docs-only pass preserved production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes while refreshing only the release-review handoff.
- Intentional file groups remain eight review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, leaderboard zero-kill summary accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs; keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard summary accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 3.06s and frontend build completed in 1.87s with existing non-failing Browserslist/chunk-size warnings.

Twenty-second 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty-two paths for task `prepare-release-manifest-2026-05-05-22`, with no selected-scope conflict in `docs/progress-notes.md` or `docs/release-notes-2026-05-05.md`.
- This docs-only pass preserved production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes while refreshing only the release-review handoff.
- Intentional file groups remain eight review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, leaderboard zero-kill summary accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs; keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard summary accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 3.77s and frontend build completed in 1.96s with existing non-failing Browserslist/chunk-size warnings.

Twenty-third 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty-two paths for task `prepare-release-manifest-2026-05-05-23`, with no selected-scope conflict in `docs/progress-notes.md` or `docs/release-notes-2026-05-05.md`.
- This docs-only pass preserved production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes while refreshing only the release-review handoff.
- Intentional file groups remain eight review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, leaderboard zero-kill summary accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs; keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard summary accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 3.92s and frontend build completed in 1.92s with existing non-failing Browserslist/chunk-size warnings.

## 2026-05-04 — Release review manifest prepared

The dirty tree is now documented as a ten-path release-review unit with a fresh dated manifest at `docs/release-notes-2026-05-04.md`. This pass intentionally changed only documentation: the new manifest plus this progress pointer.

Summary:
- Intentional implementation/test groups: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, and attestation dry-run test hygiene.
- Documentation group: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, `docs/release-notes-2026-05-03.md`, and `docs/release-notes-2026-05-04.md`.
- Scratch/local exclusions observed in `git status --short`: none; continue excluding generated artifacts, local runtime data, autonomous-loop state, debug probes, deployment scratch, temporary dummy outputs, local proof artifacts, and secrets unless explicitly promoted and revalidated.
- Recommended PR split is five small units: proof metadata contract, submission normalization, verification tolerance hardening, attestation test hygiene, and release-review docs/context after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 4.13s and the frontend build completed in 3.16s with existing non-failing warnings.

Second 2026-05-04 release review refresh:
- Re-read dirty inventory is now eleven paths only because the 2026-05-04 manifest itself is untracked; the underlying implementation/test groups remain unchanged from the ten-path handoff.
- This docs-only pass sharpened reviewer scope without touching production code, tests, secrets, generated data, deployment files, local proof artifacts, or debug scratch files.
- Recommended PR split remains five small units: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 4.37s and the frontend build completed in 2.17s with existing non-failing Browserslist/chunk-size warnings.

Third 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths: four implementation/test slices, three dated release notes, the progress log, and the untracked proof metadata regression test.
- This docs-only pass tightened the release-review handoff by explicitly preserving all untracked review inputs while keeping generated artifacts, local runtime data, deployment scratch, local proof artifacts, debug probes, and secrets excluded.
- Recommended PR split remains five small units with docs last or bundled as reviewer context: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- Current validation passed before this note refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 6.13s and the frontend build completed in 2.74s with existing non-failing Browserslist/chunk-size warnings.

Fourth 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths and the release-review unit is unchanged: proof transport metadata contract, submission normalization, verification tolerance hardening, attestation dry-run test hygiene, and dated documentation.
- This docs-only pass refreshed the handoff note without editing production code, tests, secrets, generated data, deployment files, local proof artifacts, or debug scratch files.
- Recommended PR split remains five small units, with generated artifacts, local runtime data, autonomous-loop state, temporary probes, deployment scratch, dummy outputs, local proof artifacts, and secrets excluded unless intentionally promoted and revalidated.
- Current validation passed twice in this loop: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; the first run reported 201 passed in 5.07s and frontend build in 2.49s, and the post-note rerun also passed with existing non-failing Browserslist/chunk-size warnings.

Fifth 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths: four implementation/test review slices, the dated documentation trail, and three untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`).
- This docs-only pass refreshed release-review evidence only; no production code, tests, secrets, generated data, deployment files, local proof artifacts, runtime data, or debug scratch files were edited.
- Recommended PR split remains five small units after the full gate: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.

Sixth 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths and still maps cleanly to the same five reviewer units: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- This docs-only pass refreshed the manifest/checklist with current validation evidence only; production code, tests, secrets, generated data, deployment files, local proof artifacts, runtime data, and debug scratch files were not edited.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 4.33s and frontend build completed in 2.07s with existing non-failing Browserslist/chunk-size warnings.
- Preserve all three untracked review inputs during handoff (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`) and keep docs last or bundled as reviewer context after the full gate.

Seventh 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths and still maps to the same five reviewer units: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- This docs-only pass refreshed reviewer handoff evidence without touching production code, tests, secrets, generated data, deployment files, local proof artifacts, runtime data, or debug scratch files.
- Preserve the three untracked review inputs during staging/review (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`), keep scratch/local artifacts excluded, and keep docs last or bundled as reviewer context after validation.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 8.08s and frontend build completed in 3.28s with existing non-failing Browserslist/chunk-size warnings.

Eighth 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths with no separate scratch/local artifacts, generated outputs, deployment files, runtime data, local proof artifacts, debug probes, or secrets visible in `git status --short`.
- This docs-only pass refreshed the release-review manifest and progress pointer only; production code, tests, untracked review inputs, secrets, generated data, and debug scratch files were preserved untouched.
- Reviewer handoff remains the same five-part split: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context last after the full gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 3.81s and frontend build completed in 1.94s with existing non-failing Browserslist database staleness and large chunk-size warnings.

Ninth 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths and still cleanly separates into four implementation/test review slices plus dated release-review documentation.
- This docs-only pass refreshed reviewer handoff evidence only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were preserved untouched.
- Preserve all three untracked review inputs during staging (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`) and keep docs last or bundled as context after validation.
- Recommended PR split remains five small units: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.

Tenth 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths; untracked review inputs are still limited to the two dated manifests and the proof metadata regression test.
- This docs-only pass refreshed the manifest handoff without touching production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, or debug scratch files.
- Recommended PR split remains five small units with docs last or bundled as reviewer context after validation: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- Scratch/local exclusions remain generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, and secrets unless explicitly promoted and revalidated.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 4.54s and frontend build completed in 2.45s with existing non-failing Browserslist/chunk-size warnings.

Eleventh 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths with no new scratch/local, generated, runtime, deployment, local proof artifact, debug probe, or secret entries visible in `git status --short`.
- This docs-only pass refreshed release-review handoff evidence only; production code, tests, untracked review inputs, generated data, and secrets were preserved untouched.
- Recommended PR split remains five small units after the full gate: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Reviewer staging note remains explicit: preserve `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py` as intentional untracked review inputs.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed and frontend build completed with existing non-failing Browserslist/chunk-size warnings.

Twelfth 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths; this pass found no extra scratch/local, generated, runtime, deployment, local proof artifact, debug probe, or secret entries beyond the documented review inputs.
- This docs-only refresh keeps the release unit reviewable without touching production code, tests, secrets, generated data, deployment files, runtime data, or debug scratch files.
- Reviewer staging remains explicit: preserve all three untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`) and keep documentation last or bundled as context after validation.
- Recommended PR split remains five small units: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 4.38s and frontend build completed in 2.17s with existing non-failing Browserslist/chunk-size warnings.

Thirteenth 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths, with the same four implementation/test review slices plus dated release-review documentation and no new visible scratch/local artifacts.
- This docs-only pass refreshed the release-review manifest and progress pointer only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were preserved untouched.
- Reviewer staging remains explicit: keep `docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, and `tests/test_proof_transport_metadata_contract.py` as intentional untracked review inputs if this unit is staged.
- Recommended PR split remains five small units after validation: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 3.90s and frontend build completed in 1.93s with existing non-failing Browserslist/chunk-size warnings.

Fourteenth 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths and still maps cleanly to five review units: proof transport metadata, submission normalization, verification hardening, attestation dry-run hygiene, and release-review documentation.
- This docs-only pass refreshed the release manifest without touching production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, or debug scratch files.
- Preserve the three intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`) and keep generated/local/scratch/secrets excluded unless explicitly promoted and revalidated.
- Recommended PR split remains five small units, with documentation last or bundled as reviewer context only after `uv run --extra test pytest -q` and `npm --prefix frontend run build` pass.

Fifteenth 2026-05-04 release review refresh:
- Re-read dirty inventory remains eleven paths and the selected scope is still documentation-only: the progress log plus the 2026-05-04 release manifest.
- This pass refreshed reviewer evidence without touching production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, or debug scratch files.
- The release unit remains five reviewable groups: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Preserve the intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`) and keep generated/local/scratch/secrets excluded unless explicitly promoted and revalidated.

Sixteenth 2026-05-04 release review refresh:
- Re-read dirty inventory is now fifteen paths: five implementation/test review slices, three dated release-review notes, the progress log, and the untracked proof metadata regression test.
- Newly visible review slice is strict simulation request/config schema validation (`backend/api_server.py`, `backend/config.py`, `tests/test_api_server.py`, `tests/test_config.py`); this docs-only pass did not edit production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, or debug scratch files.
- Recommended PR split is now six small units: strict simulation config/API validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Preserve the intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`) and keep generated/local/scratch/secrets excluded unless explicitly promoted and revalidated.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.71s and frontend build completed in 1.92s with existing non-failing Browserslist/chunk-size warnings.

Seventeenth 2026-05-04 release review refresh:
- Re-read dirty inventory remains fifteen paths and still separates cleanly into six reviewer units: strict simulation config/API validation, proof transport metadata, submission normalization, verification hardening, attestation dry-run hygiene, and release-review documentation.
- This docs-only pass refreshed the manifest evidence after a clean pre-edit gate; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were preserved untouched.
- Current validation evidence before this note refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.86s and frontend build completed in 1.93s with existing non-failing Browserslist/chunk-size warnings.
- Preserve the three intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`) and keep docs last or bundled as reviewer context only after the full gate.

Eighteenth 2026-05-04 release review refresh:
- Re-read dirty inventory remains fifteen paths and still maps to six small reviewer units: strict simulation config/API validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- This docs-only pass refreshed reviewer handoff evidence only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were preserved untouched.
- No separate scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret paths are visible in `git status --short`; continue excluding them unless explicitly promoted and revalidated.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 4.46s and frontend build completed in 2.23s with existing non-failing Browserslist/chunk-size warnings.
- Preserve the three intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`) and keep docs last or bundled as reviewer context after the full pytest/build gate.

Nineteenth 2026-05-04 release review refresh:
- Re-read dirty inventory remains fifteen paths and the scope is still documentation-only: `docs/progress-notes.md` plus the untracked `docs/release-notes-2026-05-04.md` manifest.
- Intentional review groups remain six small units: strict simulation config/API validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- This pass preserved existing production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and all three untracked review inputs.
- Scratch/local exclusions observed in `git status --short` remain none beyond the intentional untracked review inputs; keep generated/build outputs, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation test hygiene, and PR 6 or bundled reviewer context for release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.73s and frontend build completed in 1.84s with existing non-failing Browserslist/chunk-size warnings.


Twentieth 2026-05-04 release review refresh:
- Re-read dirty inventory remains fifteen paths and no selected-scope conflict was observed in `docs/progress-notes.md` or `docs/release-notes-2026-05-04.md`.
- This docs-only pass refreshed reviewer handoff evidence only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were preserved untouched.
- Intentional review groups remain six small units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Preserve the intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `tests/test_proof_transport_metadata_contract.py`) and keep generated/local/scratch/secrets excluded unless explicitly promoted and revalidated.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.96s and frontend build completed in 1.96s with existing non-failing Browserslist database staleness and chunk-size warnings.

Twenty-first 2026-05-04 release review refresh:
- Re-read dirty inventory remains fifteen paths and the selected docs-only scope is conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-04.md`.
- This pass refreshed the reviewer manifest only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were preserved untouched.
- Intentional release groups remain six small units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- No extra scratch/local, generated, deployment, runtime, local proof artifact, debug probe, or secret paths are visible in `git status --short`; preserve the three intentional untracked review inputs and keep docs last or bundled only after validation.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.79s and frontend build completed in 1.88s with existing non-failing Browserslist database staleness and chunk-size warnings.

Twenty-second 2026-05-04 release review refresh:
- Re-read dirty inventory remains fifteen paths and the selected docs-only scope is still conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-04.md`.
- This pass refreshed the reviewer handoff only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were preserved untouched.
- Intentional release groups remain six small units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Likely scratch/local exclusions remain none beyond the three intentional untracked review inputs visible in `git status --short`; keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run test hygiene, and PR 6 or bundled reviewer context for release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 5.40s and frontend build completed in 2.67s with existing non-failing Browserslist database staleness and chunk-size warnings.

Twenty-third 2026-05-04 release review refresh:
- Re-read dirty inventory remains fifteen paths and the selected docs-only scope has no observed conflict with existing user changes.
- This pass refreshed only `docs/progress-notes.md` and `docs/release-notes-2026-05-04.md`; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, and debug scratch files were preserved untouched.
- Intentional release groups remain six reviewable units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context.
- Likely scratch/local exclusions remain none beyond the three intentional untracked review inputs visible in `git status --short`; keep generated/build output, local runtime data, autonomous-loop state, ad-hoc probes, dummy outputs, unreviewed proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata, PR 3 submission normalization, PR 4 verification hardening, PR 5 attestation dry-run test hygiene, and PR 6 or bundled reviewer context for release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-04.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 205 passed in 3.72s and frontend build completed in 1.89s with existing non-failing Browserslist database staleness and chunk-size warnings.

## 2026-05-03 — Release review manifest refreshed

The current dirty tree has been narrowed into a release-review handoff: one backend verification regression slice plus documentation-only release-prep notes. The detailed dated manifest is `docs/release-notes-2026-05-03.md`.

Summary:
- Intentional implementation group: `backend/chain/verify.py` with focused regression coverage in `tests/test_verify.py`.
- Documentation group: `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and `docs/release-notes-2026-05-03.md`.
- Likely scratch exclusions are currently absent from `git status --short`; continue excluding generated artifacts, local runtime data, agent state, temporary debug/probe scripts, and secrets if they reappear.
- Recommended PR split is the tiny chain-verification fix first, with release-review docs either included as context or split into a docs-only PR.

Second-pass release review refresh:
- Current dirty inventory is five paths: the backend/test regression pair, two pre-existing release-review docs, and the untracked `docs/release-notes-2026-05-03.md` manifest.
- Keep the review unit unchanged: `backend/chain/verify.py` plus `tests/test_verify.py` as PR 1; release-review docs as PR 2 or bundled reviewer context.
- No new production code, generated artifacts, secrets, deployment files, or scratch/debug files were introduced by this pass.

Third-pass release review refresh:
- Dirty inventory is still the same five-path release unit: `backend/chain/verify.py`, `tests/test_verify.py`, `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.
- Reviewer-facing intent remains a small backend correctness fix plus explicit release-prep documentation; no extra production, generated, secret, deployment, or scratch files were pulled into scope.
- Recommended handoff is unchanged: PR 1 for the verification regression pair, PR 2 or bundled context for the release notes after final validation.

Fourth-pass release review refresh:
- Dirty inventory is now seven paths: two backend implementation files (`backend/chain/submit.py`, `backend/chain/verify.py`), their focused regression tests (`tests/test_submit.py`, `tests/test_verify.py`), two existing release-review docs, and the untracked `docs/release-notes-2026-05-03.md` manifest.
- Intentional implementation groups should be split into two tiny backend PR candidates: config-hash normalization for cast submission, and missing-recomputed-metric tolerance failure behavior.
- Scratch/local exclusions observed in `git status --short` remain none; continue excluding generated artifacts, local runtime data, autonomous-agent state, temporary debug/probe scripts, deployment artifacts, and secrets if they reappear.

Fifth-pass release review refresh:
- Re-read dirty inventory remains seven paths: `backend/chain/submit.py`, `backend/chain/verify.py`, `tests/test_submit.py`, `tests/test_verify.py`, `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.
- The review shape is stable: two tiny backend regression PR candidates plus release-review documentation; no production scope was widened by this docs-only pass.
- Scratch/local exclusions observed in `git status --short` remain none; keep generated artifacts, local runtime data, autonomous-agent state, debug probes, deployment scratch, and secrets out of the release unit.

Sixth-pass release review refresh:
- Re-read dirty inventory remains the same seven-path release unit, with no generated artifacts, local data, deployment scratch, debug probes, or secrets visible in `git status --short`.
- Intentional groups remain: submission config-hash normalization, verification missing-metric tolerance hardening, and release-review documentation.
- Recommended review split is unchanged: two tiny backend regression PR candidates first, then docs as either a separate release-prep PR or bundled reviewer context after validation.

Seventh-pass release review refresh:
- Re-read dirty inventory still matches the seven-path release unit: `backend/chain/submit.py`, `backend/chain/verify.py`, `tests/test_submit.py`, `tests/test_verify.py`, `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.
- No scratch/local artifacts, generated outputs, deployment files, local data, debug probes, or secrets are visible in `git status --short`.
- Recommended PR split remains three reviewable pieces: submission normalization, verification tolerance hardening, and release-review documentation/context.

Eighth-pass release review refresh:
- Re-read dirty inventory remains unchanged at seven paths, with only the two backend regression pairs and release-review documentation visible.
- Validation evidence is current again after this pass's required full test/build run; keep the existing non-failing frontend Browserslist/chunk-size warnings classified as build warnings, not release blockers.
- Recommended PR split remains PR 1 for submission config-hash normalization, PR 2 for verification tolerance hardening, and PR 3 or bundled context for release-review notes; continue excluding generated artifacts, local runtime data, agent state, debug probes, deployment scratch, and secrets.

Ninth-pass release review refresh:
- Re-read dirty inventory is still seven paths: `backend/chain/submit.py`, `backend/chain/verify.py`, `tests/test_submit.py`, `tests/test_verify.py`, `docs/progress-notes.md`, `docs/release-notes-2026-05-02.md`, and untracked `docs/release-notes-2026-05-03.md`.
- Intentional file groups remain stable: submission config-hash normalization, verification missing-metric tolerance hardening, and release-review documentation.
- No scratch/local artifacts, generated outputs, local runtime data, deployment files, debug probes, or secrets are visible in `git status --short`; maintain the same three-part PR split after validation.

Tenth-pass release review refresh:
- Re-read dirty inventory remains the same seven-path release-review unit; this docs-only pass did not introduce production code, generated data, deployment files, secrets, or scratch/debug artifacts.
- Validation evidence is refreshed again for the exact review unit, preserving the current classification as two tiny backend regression slices plus release-review documentation.
- Recommended PR split remains unchanged: PR 1 submission config-hash normalization, PR 2 verification missing-metric tolerance hardening, and PR 3 or bundled reviewer context for the release notes.

Eleventh-pass release review refresh:
- Re-read dirty inventory remains unchanged at seven paths: the two backend regression pairs plus release-review documentation; no production scope was widened by this docs-only pass.
- Scratch/local exclusions observed in `git status --short` remain none, so generated artifacts, local runtime data, autonomous-loop state, debug probes, deployment scratch, and secrets stay out of the release unit.
- Recommended review split remains PR 1 for submission config-hash normalization, PR 2 for verification missing-metric tolerance hardening, and PR 3 or bundled reviewer context for release-review notes after full validation.

Twelfth-pass release review refresh:
- Re-read dirty inventory remains the same seven paths: submission normalization pair, verification tolerance pair, and release-review documentation; this pass intentionally edited docs only.
- Validation handoff now explicitly ties the two backend PR candidates to their focused tests plus the required full pytest/build run.
- Scratch/local exclusions observed in `git status --short` remain none; keep generated artifacts, local runtime data, autonomous-loop state, debug probes, deployment scratch, and secrets outside the release unit.

Thirteenth-pass release review refresh:
- Re-read dirty inventory remains unchanged at seven paths: two backend regression slices, their tests, and release-review documentation; no production code, generated data, deployment files, secrets, or scratch/debug artifacts were edited by this pass.
- Release handoff is now framed as a reviewer checklist: confirm the untracked 2026-05-03 manifest is intentionally added, validate both focused regression tests, then run the full pytest/build gate before any push.
- Recommended PR split remains PR 1 submission config-hash normalization, PR 2 verification missing-metric tolerance hardening, and PR 3 or bundled context for the release-review notes.

Fourteenth-pass release review refresh:
- Re-read dirty inventory is now eight paths: the two backend regression slices, their focused tests, one attestation-bot dry-run test hygiene change, and release-review documentation.
- Intentional groups are ready for review as submission normalization, verification missing-metric tolerance hardening, test-output hygiene for the attestation bot, and docs-only release context; no production scope was widened by this pass.
- Recommended PR split is PR 1 submission normalization, PR 2 verification tolerance hardening, PR 3 test hygiene if reviewers want it separate, and PR 4 or bundled reviewer context for release-review documentation after the required full validation gate.

Fifteenth-pass release review refresh:
- Re-read dirty inventory remains the same eight-path review unit: submission normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- The release manifest now carries the current validation handoff and exact scratch exclusions for the eight-path tree; this pass changed documentation only.
- Recommended PR split remains four small units, with the docs either last as PR 4 or bundled as reviewer context once the full pytest/build gate passes.

Sixteenth-pass release review refresh:
- Re-read dirty inventory is now a ten-path review unit: proof transport metadata contract, submission normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- The release manifest now calls out the untracked proof transport metadata regression test, the intentional file groups, scratch exclusions, prior/current validation evidence, and the required full pytest/build gate for this docs-only pass.
- Recommended PR split is five small units, with the proof transport metadata contract first and docs either last as PR 5 or bundled as reviewer context after validation.

Seventeenth-pass release review refresh:
- Re-read dirty inventory remains the same ten-path release unit: proof transport metadata contract, submission normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- This docs-only pass preserved all existing implementation/test changes while refreshing the manifest's intentional groups, scratch exclusions, validation handoff, and recommended PR split for release review.
- Recommended PR split remains five small units, with generated artifacts, local runtime data, autonomous-loop state, debug probes, deployment scratch, local proof artifacts, temporary dummy outputs, and secrets excluded unless explicitly promoted and revalidated.

Eighteenth-pass release review refresh:
- Re-read dirty inventory remains the same ten-path release unit: proof transport metadata contract, submission normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- The manifest now carries fresh reviewer evidence for the unchanged dirty tree, including scratch exclusions and the five-part PR split without touching production code, secrets, generated data, or debug scratch files.
- Full release validation passed again for this docs-only pass: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 3.73s and frontend build completed in 1.90s with existing non-failing warnings.

Nineteenth-pass release review refresh:
- Re-read dirty inventory remains the same ten-path release unit: proof transport metadata contract, submission normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- This docs-only pass preserves the existing implementation/test changes while refreshing the reviewer manifest with intentional file groups, scratch exclusions, validation evidence, and the five-part PR split.
- Full release validation passed for this docs-only pass: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed and frontend build completed with existing non-failing warnings.
- No production code, secrets, generated data, deployment files, local proof artifacts, or debug scratch files were edited by this pass.

Twentieth-pass release review refresh:
- Re-read dirty inventory remains the same ten-path release unit: proof transport metadata contract, submission normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- This docs-only pass refreshed the release handoff without touching production code, tests, secrets, generated data, deployment files, local proof artifacts, or debug scratch files.
- Full release validation passed for this docs-only pass: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 4.48s and frontend build completed in 3.34s with existing non-failing warnings.
- Recommended PR split remains five small units: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation/context after the full pytest/build gate.

Twenty-first-pass release review refresh:
- Re-read dirty inventory remains the same ten-path release unit: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- This docs-only pass refreshed reviewer handoff details only; no production code, tests, secrets, generated data, deployment files, local proof artifacts, or debug scratch files were edited.
- Recommended PR split remains five small units with docs last or bundled as reviewer context after validation: proof transport metadata contract, submission normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.

Twenty-second-pass release review refresh:
- Re-read dirty inventory remains the same ten-path release unit: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- This docs-only pass refreshed the review manifest only; no production code, tests, secrets, generated data, deployment files, local proof artifacts, or debug scratch files were edited.
- Full release validation passed for this pass: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-03.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 201 passed in 5.15s and frontend build completed in 2.15s with existing non-failing warnings.
- Recommended PR split remains five small units with docs last or bundled as reviewer context after validation; preserve the untracked manifest/test additions explicitly during review handoff.

Twenty-third-pass release review refresh:
- Re-read dirty inventory remains the same ten-path release unit: proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, attestation dry-run test hygiene, and release-review documentation.
- This docs-only pass refreshed the dated handoff note only; no production code, tests, secrets, generated data, deployment files, local proof artifacts, or debug scratch files were edited.
- Reviewer handoff remains a five-part PR split with the untracked proof metadata regression test and untracked 2026-05-03 manifest explicitly preserved for review.
- Scratch/local exclusions observed in `git status --short` remain none; keep generated artifacts, local runtime data, autonomous-loop state, debug probes, deployment scratch, temporary dummy outputs, local proof artifacts, and secrets excluded unless explicitly promoted and revalidated.

Twentieth 2026-05-05 release review refresh:
- Re-read dirty inventory remains twenty-two paths and selected task `prepare-release-manifest-2026-05-05-20` remains safe as a docs-only refresh in `docs/progress-notes.md` plus `docs/release-notes-2026-05-05.md`.
- This pass refreshed release-review handoff evidence only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, and prior dated release notes were preserved untouched.
- Intentional file groups remain eight review units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the four intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, and `tests/test_proof_transport_metadata_contract.py`); keep generated/build output, runtime data, autonomous-loop state, ad-hoc probes, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains PR 1 strict simulation validation, PR 2 proof metadata contract, PR 3 submission normalization, PR 4 verification hardening, PR 5 leaderboard zero-kill accounting, PR 6 attestation dry-run hygiene, PR 7 legacy CLI artifact compatibility, and PR 8 or bundled release-review docs after the full pytest/build gate.
- Current validation passed: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-05.md && uv run --extra test pytest -q && npm --prefix frontend run build`; pytest reported 207 passed in 3.43s and frontend build completed in 1.87s with existing non-failing Browserslist/chunk-size warnings.


## 2026-05-06 — Release review manifest corrected

The dirty tree was re-read for task `prepare-release-manifest-2026-05-06-5`, and the dated release manifest was corrected from the stale twenty-three-path inventory to the live twenty-five-path review unit. The detailed dated manifest is `docs/release-notes-2026-05-06.md`.

Summary:
- Intentional review groups are now nine units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Validation evidence for this docs-only correction: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 208 passed in 4.95s and frontend build completed in 2.82s with existing non-failing Browserslist/chunk-size warnings.
- Likely scratch/local exclusions remain absent from `git status --short` beyond the five intentional untracked review inputs; keep generated/build output, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split is nine parts, with release-review docs last or bundled only after the full backend/frontend gate.

## 2026-05-02 — Release review manifest prepared

The dirty tree has been organized for release review instead of receiving another audit-only green-test note. The detailed dated manifest is `docs/release-notes-2026-05-02.md`.

Summary:
- Intentional review groups are split into proof lifecycle/trust tiers, chain/runtime integration, simulation persistence/replay, frontend preview UI, and dependency/lockfile changes.
- Validation evidence recorded from the latest autonomous scorecard: `uv run --extra test pytest -q` passed with 198 tests, and `npm --prefix frontend run build` passed.
- Likely exclusions are called out explicitly: agent state, local cache/data, generated artifacts, root debug/patch probes, and test-side debug probes.
- Recommended PR split is five parts: proof core, chain/runtime integration, simulation/replay, frontend preview UI, and cleanup-only artifact removal.

Release-review caution:
- Review `frontend/.env.preview` before inclusion to confirm it contains only non-secret preview defaults.
- Exclude `frontend/dist/`, `out/`, `cache/`, local SQLite data, and the local BraTS archive unless a reviewer intentionally asks for generated/local artifacts.
- Promote only durable tests; discard temporary debug/probe scripts before PR handoff.

Pass 7 addendum:
- Current dirty inventory was refreshed at 85 paths: 25 modified tracked paths and 60 untracked paths.
- `docs/plans/` should be treated as planning context, not automatically bundled into implementation PRs.
- `uv.lock` should be reviewed with Python dependency changes rather than slipped into an unrelated cleanup.

Pass 8 addendum:
- Current dirty inventory has narrowed to two modified tracked paths: `backend/chain/verify.py` and `tests/test_verify.py`.
- Treat this as a single chain-verification regression slice: implementation plus focused test for missing recomputed numeric metrics.
- Recommended immediate review unit is one tiny backend PR after full pytest and frontend build validation; no frontend, generated, secret, or local data files are currently part of the dirty tree.

## 2026-04-11 — Backend / blockchain / proof-path foundation

... (rest of existing content)

## 2026-05-06 — Release review manifest sixth refresh

The dirty tree was re-read for task `prepare-release-manifest-2026-05-06-6`, and the live twenty-five-path release unit remains stable after the corrected fifth pass. The detailed dated manifest is `docs/release-notes-2026-05-06.md`.

Summary:
- Intentional review groups remain nine units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent from `git status --short` beyond the five intentional untracked review inputs; keep generated/build output, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains nine parts, with release-review docs last or bundled only after the full backend/frontend gate.
- Validation evidence for this sixth docs-only refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 208 passed in 6.88s and frontend build completed in 3.43s with existing non-failing Browserslist/chunk-size warnings.

## 2026-05-06 — Release review manifest eighth refresh

The dirty tree was re-read for task `prepare-release-manifest-2026-05-06-8`, and the live twenty-five-path release unit remains stable after the seventh pass. The detailed dated manifest is `docs/release-notes-2026-05-06.md`.

Summary:
- Intentional review groups remain nine units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent from `git status --short` beyond the five intentional untracked review inputs; keep generated/build output, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains nine parts, with release-review docs last or bundled only after the full backend/frontend gate.
- Validation evidence for this eighth docs-only refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 208 passed in 3.86s and frontend build completed in 2.32s with existing non-failing Browserslist/chunk-size warnings.

## 2026-05-06 — Release review manifest ninth refresh

The dirty tree was re-read for task `prepare-release-manifest-2026-05-06-9`, and the live twenty-five-path release unit remains stable after the eighth pass. The detailed dated manifest is `docs/release-notes-2026-05-06.md`.

Summary:
- Intentional review groups remain nine units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent from `git status --short` beyond the five intentional untracked review inputs; keep generated/build output, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains nine parts, with release-review docs last or bundled only after the full backend/frontend gate.
- Validation evidence for this ninth docs-only refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 208 passed in 3.56s and frontend build completed in 1.87s with existing non-failing Browserslist/chunk-size warnings.

## 2026-05-06 — Release review manifest tenth refresh

The dirty tree was re-read for task `prepare-release-manifest-2026-05-06-10`, and the live twenty-five-path release unit remains stable after the ninth pass. The detailed dated manifest is `docs/release-notes-2026-05-06.md`.

Summary:
- Intentional review groups remain nine units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent from `git status --short` beyond the five intentional untracked review inputs; keep generated/build output, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains nine parts, with release-review docs last or bundled only after the full backend/frontend gate.
- Validation evidence for this tenth docs-only refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 208 passed in 4.05s and frontend build completed in 1.96s with existing non-failing Browserslist/chunk-size warnings.

## 2026-05-06 — Release review manifest eleventh refresh

The dirty tree was re-read for task `prepare-release-manifest-2026-05-06-11`, and the live twenty-five-path release unit remains stable after the tenth pass. The detailed dated manifest is `docs/release-notes-2026-05-06.md`.

Summary:
- Intentional review groups remain nine units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent from `git status --short` beyond the five intentional untracked review inputs; keep generated/build output, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains nine parts, with release-review docs last or bundled only after the full backend/frontend gate.
- Validation evidence for this eleventh docs-only refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 208 passed in 4.08s and frontend build completed in 2.10s with existing non-failing Browserslist/chunk-size warnings.


## 2026-05-06 — Release review manifest twelfth refresh

The dirty tree was re-read for task `prepare-release-manifest-2026-05-06-12`, and the live twenty-five-path release unit remains stable after the eleventh pass. The detailed dated manifest is `docs/release-notes-2026-05-06.md`.

Summary:
- Intentional review groups remain nine units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent from `git status --short` beyond the five intentional untracked review inputs; keep generated/build output, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains nine parts, with release-review docs last or bundled only after the full backend/frontend gate.
- Validation evidence for this twelfth docs-only refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 208 passed in 3.83s and frontend build completed in 2.01s with existing non-failing Browserslist/chunk-size warnings.

## 2026-05-06 — Release review manifest fifteenth refresh

The dirty tree was re-read for task `prepare-release-manifest-2026-05-06-15`, and the live twenty-five-path release unit remains stable after the fourteenth pass. The detailed dated manifest is `docs/release-notes-2026-05-06.md`.

Summary:
- Intentional review groups remain nine units: strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent from `git status --short` beyond the five intentional untracked review inputs; keep generated/build output, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains nine parts, with release-review docs last or bundled only after the full backend/frontend gate.
- Validation evidence for this fifteenth docs-only refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 208 passed in 4.08s and frontend build completed in 2.10s with existing non-failing Browserslist/chunk-size warnings.

## 2026-05-06 — Release review manifest seventeenth refresh

The dirty tree was re-read for task `prepare-release-manifest-2026-05-06-17`, and the selected docs-only scope remains conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-06.md`. The live release unit is still twenty-seven paths, with no production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, commits, pushes, deploy state, or staging state touched in this pass.

Summary:
- Intentional review groups remain ten units: README public-readiness documentation, strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent from `git status --short` beyond the six intentional untracked review inputs; keep generated/build output, coverage/cache directories, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains ten parts, with release-review docs last or bundled only after the full backend/frontend gate.
- Validation evidence for this seventeenth docs-only refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 209 passed in 4.04s and frontend build completed in 2.19s with existing non-failing Browserslist/chunk-size warnings.

Eighteenth 2026-05-06 release review refresh:
- Re-read dirty inventory remains twenty-seven paths for task `prepare-release-manifest-2026-05-06-18`, with the selected docs-only scope still conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-06.md`.
- This pass refreshed release-review handoff context only; production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, prior dated release notes, commits, pushes, deploy state, and staging state were preserved untouched.
- Intentional file groups remain ten review units: README public-readiness documentation, strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the six intentional untracked review inputs; keep generated/build output, cache/coverage, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains ten small parts, with release-review docs last or bundled only after the full backend/frontend gate.
- Validation evidence for this eighteenth docs-only refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 209 passed in 11.96s and frontend build completed in 2.02s with existing non-failing Browserslist/chunk-size warnings.

## 2026-05-06 — Release review manifest nineteenth refresh

The dirty tree was re-read for task `prepare-release-manifest-2026-05-06-19`, and the selected docs-only scope remains conflict-free: `docs/progress-notes.md` plus `docs/release-notes-2026-05-06.md`. The live release unit remains twenty-seven paths, with no production code, tests, secrets, generated data, deployment files, runtime data, local proof artifacts, debug scratch files, prior dated release notes, commits, pushes, deploy state, or staging state touched in this pass.

Summary:
- Intentional review groups remain ten units: README public-readiness documentation, strict simulation API/config validation, proof transport metadata contract, submission config-hash normalization, verification tolerance hardening, verifier-admin address validation, leaderboard zero-kill accounting, attestation dry-run hygiene, legacy CLI artifact compatibility, and release-review documentation/context.
- Likely scratch/local exclusions remain absent beyond the six intentional untracked review inputs (`docs/release-notes-2026-05-03.md`, `docs/release-notes-2026-05-04.md`, `docs/release-notes-2026-05-05.md`, `docs/release-notes-2026-05-06.md`, `tests/test_proof_transport_metadata_contract.py`, and `tests/test_readme_public_readiness.py`); keep generated/build output, cache/coverage, local runtime data, autonomous-loop state, ad-hoc probes, temporary dummy outputs, local proof artifacts, unrelated proof/simulation/frontend changes, and secrets out unless explicitly promoted and revalidated.
- Recommended PR split remains ten small parts, with release-review docs last or bundled only after the full backend/frontend gate.
- Validation evidence for this nineteenth docs-only refresh: `git diff --check -- docs/progress-notes.md docs/release-notes-2026-05-06.md && uv run --extra test pytest -q && npm --prefix frontend run build` passed; pytest reported 209 passed in 4.17s and frontend build completed in 2.01s with existing non-failing Browserslist/chunk-size warnings.
