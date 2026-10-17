# W1: chain layer moved to ZKsync Era Sepolia (2026-10-08/09)

**Status: done.** Deployed to ZKsync Era Sepolia (chain 300) and run end to end on 2026-10-09. Funded deployer: `0xF822f19C0FEc804f002e9087523677195a3C96cE` (the earlier deployer `0xEE8a…B086` and its key are retired). The simulation proof is still a mock, so the run is `proof_staged`.

**Where to find the evidence:**

- Branch: `hermes/zksync-20261008`, cut from the upstream sync (fork PR #15).
- Commands: the exact commands are in the sections below.
- Raw outputs: in the PR description.

## 1. Feasibility

| Item | Result |
|---|---|
| Plugins | `@matterlabs/hardhat-zksync-solc` 1.5.1, `-deploy` 1.8.0, `-node` 1.5.3, `-ethers` 1.4.0, `zksync-ethers` 6.21.2, on Hardhat 2.26.0. I installed the individual plugins, not the umbrella `@matterlabs/hardhat-zksync`. Its telemetry dependency stays disabled in non-interactive or CI runs (`zksync-telemetry-js` `isInteractive()`). |
| Config | `blockchain/hardhat.config.js` adds `zkSyncSepoliaTestnet` (chain 300, public RPC, verify URL) and `inMemoryNode` (:8011). `hardhat` and `baseSepolia` are unchanged. `zksolc` is pinned to **1.5.15**, so a deployment can be reproduced from its commit. |
| Compile | `CI=1 npx hardhat compile --network zkSyncSepoliaTestnet` with **zksolc v1.5.15 and zkvm-solc v0.8.24-1.0.2** compiles 19 files with no errors or warnings. All five contracts compile unchanged: FoodToken, ColonyMemory, TumorIntel, ExperienceRegistry, MockProofVerifier. |
| Contracts that differ on ZKsync | None found. The contracts use no `CREATE`/`CREATE2` address prediction, assembly, `selfdestruct`, `extcodesize` or `tx.origin`. Deployment goes through the ContractDeployer system contract (0x…8006), and the test transactions confirm it (below). |
| Toolchain quirk | On Node **26.7** the zksolc downloader fails with `ZkSyncSolcPluginError: opts.dispatcher is not supported by instance methods` (an undici incompatibility). On Node **22.22** (`/opt/homebrew/opt/node@22`) it works. CI pins Node 20, so CI is unaffected. |
| Gas | `eth_getBalance(0xEE8a…B086)` returns **0** on chain 300, confirmed via `sepolia.era.zksync.dev`, `zksync-sepolia.drpc.org` and the explorer API. The deploy script's preflight estimates **438,256,700,000,000 wei (0.000438 ETH)** for all four contracts, and it requires ×1.5 of that, **0.000657 ETH**. It refused to deploy: `Insufficient testnet gas: balance 0 wei < required 657385050000000 wei`. |

## 2. Tests

```
$ npx hardhat test                                   # default EVM network, unchanged
  46 passing
$ CI=1 npx hardhat test --network inMemoryNode       # anvil-zksync, chain 260
  46 passing (54s)
```

To check that the suite really ran on EraVM, I scanned the node's last 400 blocks after the run:

- 199 transactions, all of type **0x71** (EIP-712, ZKsync native).
- 62 of them were sent to **ContractDeployer 0x…8006**, and all 62 produced a `contractAddress`.
- Deployed code is 32-byte word-aligned (27,104 B), which is the EraVM bytecode format.

Python suite after the backend rewiring: `PYTHON_DOTENV_DISABLED=1 uv run --extra test pytest tests/ -q -rs` = **918 passed, 3 skipped** (BraTS, TCGA data absent; the Era Sepolia deployments-file check skips until deployed).

## 3. Deploy script

`blockchain/scripts/deploy-zksync.js` deploys the same set as `scripts/deploy.js`: FoodToken(deployer), ColonyMemory, TumorIntel, ExperienceRegistry. Safety behaviour:

- It refuses any chain other than 260 (local) and 300 (Era Sepolia).
- It runs `estimateDeployFee` for every contract before sending anything, and refuses to start unless the balance is at least 1.5× the estimate.
- It writes `blockchain/deployments/<network>.json` containing: name, address, deploy tx hash, block number, gas used, explorer URLs, deployer, the zksolc and solc versions with settings, the git commit, and a dirty-tree flag.

**MockProofVerifier is deliberately not deployed or wired.** `TumorIntel.verifySimulation` marks a run verified whenever its verifier returns true, and the mock returns true for any non-empty proof. Wiring it would let a mock proof read `isVerified == true` on-chain. With no verifier configured, `verifySimulation` reverts (`Verifier not configured`), so no run can be labelled `verified_onchain`. The deployments file records `"proof_verifier": {"address": null, ...}`, and a test enforces this (`tests/test_chain_config_zksync.py`).

**Local rehearsal** (anvil-zksync, chain 260, publicly known dev account, file not committed):

| Contract | Address | Deploy tx | Block | Gas used |
|---|---|---|---|---|
| FoodToken | `0x9c1a3d7C98dBF89c7f5d167F2219C29c2fe775A7` | `0xf0b2c633…6393` | 536 | 2,343,081 |
| ColonyMemory | `0xCeAB1fc2693930bbad33024D270598c620D7A52B` | `0x3eaaa959…cf42` | 538 | 1,679,873 |
| TumorIntel | `0x99E12239CBf8112fBB3f7Fd473d0558031abcbb5` | `0x579a6bf7…010c` | 540 | 167,862 |
| ExperienceRegistry | `0xaAF5f437fB0524492886fbA64D703df15BF619AE` | `0x06ceb288…5d26` | 542 | 177,895 |

On the local node the actual spend was 0.0001977 ETH, against an estimate of 0.000353 ETH.

## 3a. Testnet deployment (ZKsync Era Sepolia, chain 300, 2026-10-09)

Deployer `0xF822f19C0FEc804f002e9087523677195a3C96cE`; balance before 95,000,000,000,000,000 wei (0.095 ETH). Built from commit `7eef6781370d291426dc70f70aedf59c9a6c105b` (zksolc 1.5.15, solc zkVM-0.8.24-1.0.2). Record: `blockchain/deployments/zksync-era-sepolia.json`. MockProofVerifier was not deployed.

| Contract | Address | Deploy tx | Block | Gas used | Explorer |
|---|---|---|---|---|---|
| FoodToken | `0xA2B81529f67BEA1f536Ce97D31fe389Bdba54330` | `0x008401902d6d928297757f663702760f6d1c1a31fe78198ca4c50e53cb8f1549` | 8668193 | 1627725 | [address](https://sepolia.explorer.zksync.io/address/0xA2B81529f67BEA1f536Ce97D31fe389Bdba54330) / [tx](https://sepolia.explorer.zksync.io/tx/0x008401902d6d928297757f663702760f6d1c1a31fe78198ca4c50e53cb8f1549) |
| ColonyMemory | `0x5e204425CDECebA8134B51522ff839a99De79363` | `0x13152cf23b806dd97820b6be471af380a7be002cfa17c53c8d1ec0ef99ff157d` | 8668194 | 1132677 | [address](https://sepolia.explorer.zksync.io/address/0x5e204425CDECebA8134B51522ff839a99De79363) / [tx](https://sepolia.explorer.zksync.io/tx/0x13152cf23b806dd97820b6be471af380a7be002cfa17c53c8d1ec0ef99ff157d) |
| TumorIntel | `0x90445eDC246d83FA42D700584796216E6510e317` | `0xb3edbad44f09861e93afbaa9960d9c90436c6bdaf3dab533247f303c176d2ffb` | 8668195 | 2563211 | [address](https://sepolia.explorer.zksync.io/address/0x90445eDC246d83FA42D700584796216E6510e317) / [tx](https://sepolia.explorer.zksync.io/tx/0xb3edbad44f09861e93afbaa9960d9c90436c6bdaf3dab533247f303c176d2ffb) |
| ExperienceRegistry | `0x2d77EE763987ab6131Ad5e9627C22EFE1FB29c3b` | `0xf557209bf7baccff12ca156ca214441c3b450f7d227e85a49f5727563035744e` | 8668196 | 3250693 | [address](https://sepolia.explorer.zksync.io/address/0x2d77EE763987ab6131Ad5e9627C22EFE1FB29c3b) / [tx](https://sepolia.explorer.zksync.io/tx/0xf557209bf7baccff12ca156ca214441c3b450f7d227e85a49f5727563035744e) |

`eth_getCode` on every address returned non-empty EraVM bytecode (FoodToken 16,928 B; ColonyMemory 11,296 B; TumorIntel 27,104 B; ExperienceRegistry 39,264 B), and every deploy receipt has status `0x1`.

**Testnet gas spent:** 95,000,000,000,000,000 - 94,782,826,050,000,000 = **217,173,950,000,000 wei (0.000217 ETH)** for the four deploys plus the end-to-end submission (the deploy alone cost 214,357,650,000,000 wei against an estimate of 438,165,250,000,000).

**Testnet end-to-end run** (`docs/status/e2e-zksync-era-sepolia.json`): `submitSimulation` tx `0xf0cf992598bd4324808270ebb426f44a0beac7fa874ade35563ee71d3b94150f`, block 8668197, status `0x1`, [explorer](https://sepolia.explorer.zksync.io/tx/0xf0cf992598bd4324808270ebb426f44a0beac7fa874ade35563ee71d3b94150f). Read back through the leaderboard decoder: exact match to the bundle, `isVerified == false`, leaderboard `trust_tier: unverified`, `proof_stage: submitted_onchain`. Replay: integrity, public values and replay all pass (kill_rate 100.0 vs 100.0, deliveries 12 vs 12). Bundle tier **`proof_staged`** (`is_mock: true`). Two separate statements: ZKsync's validity proofs cover the chain's state transition; they say nothing about whether the simulation was honest, and the simulation proof is a mock.

**Privacy re-check (§6):** the submission tx input is 164 bytes: the 4-byte selector plus exactly five 32-byte words (`configHash`, `killRateBps`, `nanobotCount`, `tumorRadius`, `steps`). The `SimulationSubmitted` log carries the indexed hash and submitter plus integer words. No raw simulation data, patient data or free text was written; this matches the `TumorIntel.submitSimulation` row of the §6 table. The caveats there (tumorRadius from patient geometry, unsalted configHash) still apply and do not bite for this synthetic run.

**Deploy command (used)** :

```bash
cd blockchain && CI=1 PATH=/opt/homebrew/opt/node@22/bin:$PATH \
  ANTELLIGENCE_ENV_FILE=$HOME/Desktop/research/antelligence-app/.env \
  npx hardhat run scripts/deploy-zksync.js --network zkSyncSepoliaTestnet
cd .. && ANTELLIGENCE_CHAIN=zksync-era-sepolia ANTELLIGENCE_ENV_FILE=... \
  PRIVATE_KEY=<from .env, never echoed> uv run python scripts/chain_e2e.py --out docs/status/e2e-zksync-era-sepolia.json
```

## 4. Backend wiring

`backend/chain/config.py` was rewritten as the single source of truth:

- **Network selection:** `ANTELLIGENCE_CHAIN` picks the network. The default is `zksync-era-sepolia` (300); `zksync-local-inmemory` (260) and `base-sepolia` (84532, fallback) are also known.
- **Addresses:** read only from `blockchain/deployments/<network>.json`, which is validated for chain ID and address format. Explicit per-contract env overrides still win.
- **Hard-coded addresses removed:** Base Sepolia `0x925b…D8AB`, `0x58A7…CADE`, `0x914D…81fA` and `0x7310…0869` are gone from `config.py`. `0xd1cf…238b` is gone from `scripts/dashboard.py` and `scripts/generate_report.py`. A test now fails if either TumorIntel address reappears in backend code. The history of those addresses is in `docs/status/2026-10-08-truth-pass.md` §4.
- **RPC resolution:** `ANTELLIGENCE_RPC_URL` / `CHAIN_RPC`, then the network's own env var, then the public RPC. The public RPC is used only when a chain is explicitly selected, so the default stays offline.
- **Explorer URLs** are generated from the selected network.
- **Callers moved off `get_base_sepolia_rpc_url`:** `submit.py`, `verify.py`, `leaderboard.py`, `intel_reader.py`, `experience_consumer.py`, `experience_writer.py`, `verifier_admin.py`, `cli.py`, `blockchain/client.py`.
- **`chain.submit.submit_bundle_onchain`** (new) sends `submitSimulation` and records the tx hash, block and explorer URL. It sets the lifecycle to `submitted_onchain` and **never** touches `trust_tier`, `proof_ok` or `onchain_ok`. The CLI form is `python -m chain.submit --bundle <provenance.json> --submit --out <file>`.
- **Leaderboard fix (trust-tier honesty):** the old `--onchain` path labelled every on-chain log `onchain_ok: True, stage: verified_onchain`. It now decodes `SimulationSubmitted` events and reads `isVerified(configHash)` from the contract. A submission is `verified_onchain` only if the contract says so, which is impossible in this deployment. Regression tests are in `tests/test_onchain_trust_tiers.py`.

## 5. End-to-end proof (local ZKsync node; testnet pending gas)

`scripts/chain_e2e.py` runs one real tumor simulation (5 bots, 20×20, 30 steps, seed 20261008). It then builds the attestation and staged-proof bundle using the API's helpers, submits it, reads it back through the leaderboard decoder, and replays it.

| Check | Result |
|---|---|
| Submission | `submitSimulation` tx `0xff4b1c3f389291cc392efe72afa2f1012a0c6c7029d30efe08215ae0e8829bb3`, block 546, chain 260 |
| Read-back (`fetch_onchain_simulations`) | Exact match: config_hash `6b1c83d4…e74b`, kill_rate_bps 10000, nanobot_count 5, tumor_radius 66, steps 30 |
| `isVerified(configHash)` | **false** |
| Leaderboard entry | `trust_tier: unverified`, `verified_onchain: false`, `proof_stage: submitted_onchain` |
| Replay (`verify_artifact`, replay on) | integrity ✓, public values ✓, proof-bundle schema ✓, **replay ✓** (kill_rate 100.0 claimed vs 100.0 recomputed; deliveries 12 vs 12; 0.0% deviation) |
| Bundle trust tier | **`proof_staged`**, `proof_bundle.is_mock: true`, `onchain_ok: false` |
| Explorer URL | None for the local run (no explorer). The testnet run is in §3a with an explorer URL. |

**Trust tiers, kept separate:**

- ZKsync's validity proofs show that the chain executed our transaction correctly. They say nothing about whether the simulation behind `kill_rate_bps = 10000` ran honestly.
- The simulation proof is the SP1 adapter mock, so the run is `proof_staged`, never `verified_onchain`.

**Caveat on this example run:** its kill rate is 100%, because a 12-cell synthetic tumor is cleared within 30 steps. It is a plumbing check, not a result.

## 6. Privacy audit: every field each contract writes on-chain

**Verdict:** the attestation path this sprint uses (`TumorIntel.submitSimulation`) is clean apart from two caveats. However, the full contract set is **not** clean. Three contracts still expose writes of raw simulation coordinates and free text. Today those writes are reachable only behind default-off flags, and `ANTELLIGENCE_OFFLINE` forces them off. The goal asked me to confirm that nothing sensitive is written; I can confirm that only for the attestation path.

| Contract → function / event | Fields written | Class | Backend caller (default) |
|---|---|---|---|
| **TumorIntel.submitSimulation** / `SimulationSubmitted` | `configHash` (bytes32), `killRateBps`, `nanobotCount`, `tumorRadius`, `steps` (uint32), `submitter`, `submittedAt` | Hash + 4 small integers + public address | `chain.submit`, explicit `--submit` only |
| TumorIntel.verifySimulation / `SimulationVerified` | Decoded public values (as above), `publicValuesHash`, `verifiedAt` | Hash + integers | None (reverts: no verifier) |
| TumorIntel.reportIntel / `IntelReported` | `x`, `y` (uint256 grid coordinates), `pinType` (enum), `priority`, `reporter`, `timestamp` | **Raw simulation/agent state** (tumor feature locations) | `nanobot_simulation.py` when `ANTELLIGENCE_ENABLE_BLOCKCHAIN_TX=1` (default off) |
| TumorIntel.confirm / deactivate / updateIntelPriority / pruneStalePins | pin id, priority, sender | Integers | None |
| TumorIntel.setVerifier / transferOwnership | Addresses | Public addresses | Admin only |
| **ColonyMemory**.recordDrugDelivery / recordTumorKill / markVisited / recordFood; initialize/completeSimulation | `x, y, z`, sim `timestamp`, `payloadAmount`, `cellId`, `runHash`, counts | **Raw simulation trajectories** | `simulation.py` `recordFood` (legacy foraging) when chain TX is enabled; the rest unused |
| **ExperienceRegistry**.submitExperience | `runHash`, `ipfsCid` (**string**), `dataHash`, `score`, `strategyType` (**string**), `modelUsed` (**string**), `nanobotCount`, `tumorRadius`, `datasetHash` (bytes32), `workerParamsJson` (**free-text JSON**) | **Free text** + hashes | `experience_writer.py` when `CHAIN_WRITE_ENABLED=true` (default off) |
| ExperienceRegistry.attestExperience | `quality`, `notes` (**free text**) | **Free text** | None |
| FoodToken.mint / ERC-721 transfers | Addresses, token ids | Public | Legacy foraging only |

**Caveats on the clean path:**

1. **`tumorRadius` can be patient-derived.** If a run uses BraTS geometry (`create_brats_tumor_geometry`), the radius reflects a real (public-dataset) patient's tumor. For private patient data this would leak one physical measurement. Synthetic runs, which are all runs today, are fine.
2. **`configHash` is an unsalted SHA-256 of the config JSON.** Low-entropy configs (a few integers) can be brute-forced, so it is a binding commitment, not a hiding one. If configs ever include private parameters, commit to `H(config ‖ salt)` and keep the salt off-chain.
3. **`ExperienceRegistry.datasetHash`** is a hash of a BraTS subject ID, a guessable pseudonym. That is fine for public BraTS data, but not for private cohorts.

**Recommendations (operator decision; not implemented in this PR):**

- Make `submitSimulation` the only on-chain write for medical or financial runs.
- Remove `reportIntel` and the ColonyMemory coordinate writes from the backend, or hard-gate them to synthetic geometry.
- Drop the string fields from ExperienceRegistry in favour of a single content hash.
- Salt `configHash`.

This matches VISION.md principle 4. Moving to ZKsync changes none of it, because ZKsync state is as public as Ethereum's.

## 7. Options note

`docs/research/chain-options-20261008.md` compares ZKsync Era, Aztec (Noir, private state, Alpha with a critical V5 bug disclosed 2026-07-27) and ZKsync Prividium (permissioned, SOC 2 Type I, core open-sourced in Sep 2026).

The headline: no chain choice fixes the mock simulation proof. It also flags that ZKsync OS is replacing EraVM, after which plain `solc` replaces `zksolc`.

## 8. release-manifest.json

- **Added** a `deployments` block with three entries:
  - zksync-era-sepolia: not deployed, gas blocker with the measured preflight.
  - Local rehearsal: not committed.
  - Base Sepolia: historical, listing the five addresses that have code.
- **Clarified** that `operator_boundary.contracts_deployed: false` refers to the target network.

## Done-when checklist (goal W1)

- [x] Deployments file exists: `blockchain/deployments/zksync-era-sepolia.json` (§3a).
- [x] One run visible on ZKsync Era Sepolia with an explorer URL (§3a); trust tier `proof_staged`.
- [x] Replay check passes (§5).
- [x] Privacy audit written (§6). Result: the attestation path is clean; three contracts expose raw or free-text writes, gated off.
- [x] Options note written (§7).
- [x] Summarised here.
