# Experiment Lab

## Feature and vision

The Experiment Lab at `/experiments` turns individual tumor animations into a reproducible, controlled experiment workflow.

| Shipped capability | Vision connection |
| --- | --- |
| Same-seed no-bot, fixed-rule and pheromone-coordinated trials | `VISION.md`: measurable local-signal coordination; authored v2 D1.5 baselines |
| Multi-seed reports, variability, saved library and exports | Authored v2 G4/D4.1–D4.3 experiment operations and reporting |
| Open each run in tumor playback; recompute a saved case | `VISION.md`: replayable, attributable runs; local portion of reproducibility before the trust-layer boundary |

This is a new research workflow, not a claim that the long-term patient/3D, Queen-improvement or real-prover milestones are complete.

## Use

1. Open **Experiment Lab** from the home page, or its link on the tumor simulation page.
2. Give the experiment a name, choose unique seeds and a bounded number of steps/bots. All arms share the same initial tumor geometry for each seed.
3. Run the experiment locally. It runs real simulations sequentially; the interface does not fabricate progress or substitute sample metrics.
4. Compare the three arms, inspect per-seed variability and open an individual case in tumor playback.
5. Reopen the saved experiment from the library or its URL. Export its report as JSON or case rows as CSV.
6. Use **Replay check** on a case to recompute its recorded configuration and compare the actual saved trajectory. A match is local deterministic replay, not cryptographic verification.

## Controls and measurements

- **No bots:** the model evolves without nanobots or their pheromones. It is a control for background model change, not a promise that all biological drug/immune terms are absent.
- **Fixed-rule bots:** the requested bots with pheromone secretion/following disabled.
- **Pheromone-coordinated bots:** the same requested bots with pheromones enabled. The Queen is disabled in this experiment; otherwise it would change a second variable.

All cases carry the executed configuration, seed, run ID, initial-geometry hash and trace hash. Initial geometry is captured before stepping rather than inferred from cell counts. Full run snapshots remain in the existing local run store.

Net living-cell reduction is `100 * (initial_living - final_living) / initial_living`; a negative value indicates growth. It is **not treatment-attributable efficacy**. Baseline differences are percentage points paired by seed. Sample standard deviation is unavailable with one seed, not silently zero. Empty geometry or incomplete batches must not count as successful experiments.

The interface reports actual simulated duration separately from wall-clock runtime. The current model's short exposure time and simplified biology restrict interpretation. Toxicity is not modeled by this report. Small synthetic samples do not establish statistical or clinical superiority; ties are not a winning policy.

## Local-only contract

- Rule-based, Queen disabled, explicit offline mode, synthetic 2D geometry.
- At most five unique seeds, three fixed arms per seed, 200 steps per run and 25 bots in the bot arms.
- Additional allocation/work limits apply to geometry and aggregate cell-steps; invalid batches are rejected before construction.
- No model API calls, RPC/wallet operations, patient ingestion, IPFS publication or on-chain submission.
- Preview mode must not execute experiments or replay requests.
- A partial failure is a failed experiment with retained evidence, not a completed report with dropped cases.
- Replay checks rederive the saved trace binding before comparing a recomputation. They do not promote `proof_ok`, on-chain status or strategy trust.

HTTP entry points: `POST /experiments`, `GET /experiments`, `GET /experiments/{id}`, and `POST /experiments/{id}/replay/{case_id}`. Per-case playback uses the existing `/tumor?run=...` route. The library is stored in local SQLite alongside the run snapshots.

## Verification

Backend integration tests exercise real tiny models, controls, seeded geometry, persistence, replay, altered saved evidence, failure behavior and workload/policy rejection. Frontend helper tests exercise input parsing and export semantics. `frontend/tests/experiment_browser.py` drives the real home-entry → experiment → report → exports → replay → reload path; it does not mock API responses. Its `ANTELLIGENCE_E2E_OUTPUT` path is required so test artifacts do not overwrite another run.

Actual acceptance receipts and exact reviewed source identity are recorded in the corresponding Vault delivery note. A passing test is engineering evidence, not a biomedical claim.
