# Chain options for Antelligence provenance (2026-10-08)

This note is for the operator's decision. Nothing has been ported.

## What Antelligence needs from a chain

- An append-only, timestamped commitment that run X was claimed with public values Y, signed by key Z.
- Later, verification of a proof about the run.
- Privacy for anything patient- or finance-derived.

Today the contracts write only hashes and small integers (see the privacy audit in `docs/status/2026-10-08-chain-redeploy.md`). The privacy property comes from what we choose to write, not from the chain.

## Options

| | ZKsync Era (public L2) | Aztec (private-state L2) | ZKsync Prividium (permissioned private chain) |
|---|---|---|---|
| **State visibility** | Public, like Ethereum. Validity proofs make the chain's state transitions correct; they hide nothing. | Hybrid. Contracts have private state (encrypted notes, UTXO-style) and public state. Private functions run and are proven client-side. | Private to the operator and permissioned participants. State roots and validity proofs settle to Ethereum. |
| **Language / tooling** | Solidity. EraVM today via `zksolc` (this sprint). ZKsync OS replaces EraVM with a fully EVM-equivalent VM, so stock `solc` and Hardhat/Foundry. Our 5 contracts compile unchanged. | **Noir** (Rust-like) via Aztec.nr. A full rewrite of TumorIntel / ExperienceRegistry; no Solidity path. | Solidity on the ZK Stack (ZKsync OS), plus an access-control and permissioning layer. |
| **Maturity** | Production mainnet since 2023. The EraVM → ZKsync OS transition is underway. | Ignition mainnet live since Nov 2025, but the network is labelled Alpha. A critical V5 Alpha proving-system vulnerability was disclosed on 2026-07-27, with the fix planned for V6 "later in 2026". | Enterprise product, SOC 2 Type I as of 2026-05-29. Core open-sourced in Sep 2026 (Apache-2.0). Bank pilots targeted Q3 2026. |
| **Testnet for us** | Era Sepolia (chain 300), public RPC and explorer. Used this sprint (deploy blocked only on gas). | Public testnet exists; needs Aztec sandbox/PXE tooling and Noir contracts. | No shared public testnet. We would run our own chain from the open-source core (an ops burden, not a deploy). |
| **What the proof covers** | The chain executed our transactions correctly. **Not** that the simulation behind the submitted numbers was run honestly. | Same for chain execution. A private function can additionally prove a statement about private inputs, but only if we write that circuit in Noir. | Same as ZKsync Era, with privacy enforced by access control rather than cryptography against the operator. |

## What each means for Antelligence

1. **ZKsync Era now (what this sprint built).** Lowest cost to adopt. Keeps today's hash-only design, which already passes the privacy audit. Privacy is a discipline, and the backend has to keep honouring it.
   - **Watch item:** ZKsync OS replaces EraVM. Once Era Sepolia moves, the `zksolc` / `hardhat-zksync` path becomes legacy. Our contracts are plain Solidity, so moving to standard `solc` is a config change, not a port.
2. **Aztec later, when data must be private on-chain.** It is the only option here where private inputs stay private against everyone, operator included. Example: a hospital submitting patient-derived parameters with a proof that the simulation satisfied a threshold.
   - **Costs:** a Noir rewrite, a different wallet/PXE model, and Alpha-stage security, given the recent critical bug.
   - **Recommendation:** prototype one Noir contract that verifies a commitment to private parameters before committing to it.
3. **Prividium if a consortium appears.** It fits a deployment where named institutions run the chain and regulators get views. It doesn't fit an open DeSci leaderboard, because outsiders can't verify what they can't see.

## The real gap, whichever chain wins

The simulation proof is a **mock** (`MockProofVerifier` / SP1 adapter boundary, `proof_staged`). No chain choice changes that. The trust-tier upgrade needs one of:

- a real SP1/Groth16 verifier contract and prover (the separate `antelligence-zk` repo is the start); or
- on Aztec, a Noir circuit.

Until then, every on-chain record is a signed claim plus a replayable off-chain bundle, and it must never be labelled `verified_onchain`.

Sources: aztec.network blog (V5 Alpha vulnerability notice, 2026-08-07; testnet posts); zksync.io/prividium and matterlabs.com/prividium (SOC 2 Type I, 2026-05-29); docs.zksync.io ZKsync OS FAQ (EVM-equivalent, EraVM to be deprecated); ZKsync blog (Prividium core open-sourced, Sep 2026).
