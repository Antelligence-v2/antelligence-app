# Local research delivery and development map

## Product authority

Antelligence is a reusable **pheromone-coordinated swarm research platform**, with tumor simulation as the first application. It is not an autonomous coding-loop product. `VISION.md` defines the operating scope; historical plans describe a longer destination, not an achieved implementation.

Authoritative operator context on this machine:

- `~/Desktop/plans/vision/antelligence/antelligence-v2-vision.md`: patient-aware geometry, simulation and provenance, followed by episodic Queen evaluation.
- `~/Documents/Jarvis's Vault/Briefs/2026-07-02-antelligence-pheromone-spec-patent-handoff.md`: typed signal identity, evidence-weighted decay, deterministic conflict resolution and reusable strategy memory.
- `specs/001-phase2-proof-chain-reader/`: the narrower staged-proof/trust/minimal-API contract already implemented in the recovered release candidate.

## This delivery's acceptance surface

1. A fresh Python environment installs the documented console commands.
2. A local researcher can run synthetic simulations without a model credential, wallet, RPC or spend.
3. The frontend-facing tumor route returns an attributable, persisted run and explicitly mock/staged proof metadata; retrieval preserves the actual executed configuration.
4. Pheromone aliases represent one physical field clock; closed fields conserve mass; fixed reservoirs stay fixed under diffusion, sources and decay.
5. Comparisons genuinely toggle pheromone behavior and use one Queen per enabled model, with paired seeds and honest output units.
6. The browser can run a simulation, show its run identity/status and retrieve/export its result. Reload uses the durable run ID in the URL rather than overflowing browser storage; playback metrics correspond to the selected step.
7. Cell/vessel density controls change generated geometry. Unknown fields, unsupported biological overrides and oversized grid/cell/vessel allocations fail before simulation instead of producing misleading provenance.

Acceptance evidence is recorded separately; this list is not a claim that all gates passed merely because the file exists.

## Repository consolidation

The root checkout had older code plus unfinished API trace work. The more advanced `release/config-trace-provenance` candidate at `dc29f1b` was recovered rather than recreating its existing fixes.

- Prior root WIP is committed on `preserved/antelligence-root-wip-20260905` (`ab7e9c9`). Its stricter legacy behavior was preserved, not silently overlaid on the newer API.
- A raw preservation manifest and original bytes live under `/Volumes/WD_BLACK/antelligence-delivery-20260905/preserved/`.
- New implementation is integrated on local development branches, not `main`.
- Old worktrees, source, local agent context, datasets and backups remain available. `.gitignore` separates local tool/recovery files from application changes; it does not delete them.
- SSD evidence workspace: `/Volumes/WD_BLACK/antelligence-delivery-20260905/`.

No push, public deployment, contract deployment, wallet/secret change or deletion was authorized by this consolidation.

## What the current scientific model does not establish

- The tumor agent runtime is synthetic and two-dimensional. Supporting 3D diffusion arrays does not make the complete tumor model three-dimensional.
- Cell death/kill-rate includes natural/initial model death and cannot be read as treatment-attributable efficacy. Empty geometry must not score as successful treatment.
- Small paired experiments establish executable comparison behavior, not statistical superiority or clinical benefit.
- Seeds reproduce the supported sequential local execution path. Global RNG use is not a claim of safely parallel/interleaved model-local randomness.
- Proof staging checks structure and binds identifiers. Mock bytes do not prove physics, clinical accuracy or cryptographic correctness; `proof_ok` remains false.

## Remaining vision milestones

These are real product work, not authority to deploy or a claim of completion:

1. **Typed pheromone protocol:** canonical signal IDs and schema; confidence/trust-weighted decay; duplicate damping; safety-gated deterministic resolution; wire trail/alarm emission into replayable local records before chain transport.
2. **Geometry fidelity:** explicit public-dataset geometry with source/spacing/label commitments and failure-on-missing-data; then tested 3D agents and tumor dynamics. Never silently substitute synthetic input or ingest PHI.
3. **Scientific evaluation:** meaningful exposure time, initial-state and no-treatment controls, trajectories/coverage/delivery endpoints, held-out public scenarios and multi-seed uncertainty. No efficacy claim from one positive delta.
4. **Cryptographic verification:** implement and exercise the actual prover/guest and independent verification. Pin five public fields to the same run artifact and keep privacy-sensitive state off-chain.
5. **Strategy memory:** accepted-run-to-memory-to-Queen feedback with bounded promotion and evidence gates. Staged/mock runs must not promote themselves as verified strategies.

Local implementation and tests can continue. Spending, new paid dependencies, publishing, chain writes/deployment and authority changes need separate operator approval. Clinical deployment is out of scope.
