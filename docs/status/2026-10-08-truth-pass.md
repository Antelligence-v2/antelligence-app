# Truth pass, 2026-10-08 (W0)

- Sprint 1 (2026-10-08 → 10-10), workstream W0.
- Tree checked: `hermes/sync-20261008` @ `12428af`. This is the fork's `main` merged with upstream `main` @ `3c7418e` (Antelligence-v2 PR #3), as opened for review in fork PR #15.
- Every number below comes from a command run on 2026-10-08 against that tree.

## 1. Test suites

| Suite | Exact command | Result |
|---|---|---|
| Python (all) | `uv run --extra test pytest tests/ -q -p no:cacheprovider` | **905 passed, 2 skipped**, 1 warning, 216 s (907 collected) |
| Python: the 5 Phase 6 files | `uv run --extra test pytest tests/test_api_server.py tests/test_cli.py tests/test_visualize.py tests/test_config.py tests/test_e2e.py -q` | **64 passed** |
| Solidity | `cd blockchain && npx hardhat test` | **46 passing** |
| Frontend lint | `cd frontend && npm run lint` | **0 errors, 10 warnings** (all `react-refresh/only-export-components`) |
| Frontend build | `cd frontend && npm run build` | **built** in 2.46 s |

The 2 skips are data-gated rather than broken:

```
SKIPPED [1] tests/test_brats_loader.py:81: BraTS2024-GLI data not present
SKIPPED [1] tests/test_brats_loader.py:119: TCGA TIFF data not present
```

The only warning is a `websockets.legacy` deprecation raised in `tests/engine/test_tumor_world.py`.

Before the merge, the fork's `main` had 4 commits upstream lacked, and upstream had 140 commits the fork lacked. The 2 conflicting files were resolved per the operator's ruling (details in PR #15). After resolution, `tests/test_api_server.py` passes 31/31.

## 2. Broken

Nothing in the test suites is red. Items that work but are not healthy:

- **Gitleaks is not clean on history.** `gitleaks git` reports 5 findings in commits already in upstream `main`. All 5 are false positives: 4 SHA-256 file digests in `release-manifest.json` and 1 public contract address in `docs/plans/handoff.md`. No `.gitleaksignore` exists, so every future scan reports them again.
- **The Hardhat config only knows Base Sepolia.** `blockchain/hardhat.config.js` defines `hardhat` and, when env vars are set, `baseSepolia`. There is no ZKsync network or plugin yet; that is W1's job.

## 3. Stale

| Item | What it says | Reality |
|---|---|---|
| `SPRINT.md` Phase 6 | All 5 items unchecked, labelled "[CURRENT]" | All 5 files exist and their tests pass (64 tests above). Ticked in this PR. |
| `SPRINT.md` Phase 3 | TumorIntel at `0xd1cfa5b9…2238b` | Code and docs disagree on the canonical address; see §4. |
| `release-manifest.json` | `generated_at` 2026-08-27, `current_branch: release/config-trace-provenance`, PR #12, `contracts_deployed: false`, `deployed: false` | Describes an August release candidate, not the current tree. Contracts *were* deployed to Base Sepolia (§4), so `contracts_deployed: false` is wrong for history. W1 rewrites the deployment fields. |
| `ARCHITECTURE.md` "Chain Configuration" | Canonical chain is Base Sepolia | Correct today; changes in W1 (ZKsync Era Sepolia). |
| `VISION.md` principle 5 | "Blockchain integration (Base Sepolia)" | Same as above. |
| `VISION.md` "Reference Architecture" | "pytest suite (currently 228+ tests)" | 907 collected. |
| `scripts/dashboard.py:30`, `scripts/generate_report.py:106` | Hard-code `0xd1cfa5b9…2238b` | They disagree with `backend/chain/config.py`. W1 removes the hard-coding. |

## 4. What was deployed before (Base Sepolia, chain 84532)

I read bytecode presence with `eth_getCode` against `https://base-sepolia-rpc.publicnode.com` on 2026-10-08 (block 0x2da6ab3):

| Contract | Address | Code bytes | Referenced by |
|---|---|---|---|
| TumorIntel (old) | `0xd1cfa5b9994e06cc18a21dc18fb9d20a3c02238b` | 2,551 | `SPRINT.md` Phase 3, `scripts/dashboard.py`, `scripts/generate_report.py` |
| TumorIntel (current) | `0x925b455175eF932a9a0239090a94E593224CD8AB` | 7,804 | `backend/chain/config.py` default, `ARCHITECTURE.md`, `docs/plans/handoff.md`, `.specify/memory/constitution.md`, `tests/test_chain_reader_layer.py` |
| ExperienceRegistry | `0x58A78E337ce3D948A39475f05Ca1A2c30274CADE` | 8,374 | `backend/chain/config.py`, `ARCHITECTURE.md` |
| ColonyMemory | `0x914D72b9d49ED4Bb46FA553a01fEbbd5EEf481fA` | 3,557 | `backend/chain/config.py`, `ARCHITECTURE.md` |
| FoodToken | `0x7310fb01b393459d2f8Ab15AD4a66F5380200869` | 3,661 | `backend/chain/config.py`, `ARCHITECTURE.md` |

**Conflicts found:**

1. There are two TumorIntel addresses, and both have code on-chain. The `0xd1cf…` contract is much smaller (2.5 KB vs 7.8 KB), which fits an earlier contract version. The backend uses `0x925b…`, while two scripts and SPRINT.md still point at `0xd1cf…`.
2. `release-manifest.json` says `contracts_deployed: false`, but five contracts have code on Base Sepolia. The manifest field describes that release candidate's authority boundary (it did not deploy), not chain history. Read literally, it is wrong.
3. No deployments file records tx hashes, deployer or commit for any of these addresses. Their provenance rests on docs only.

## 5. Environment facts (for W1/W2)

- The only deployer key configured for this repo is in `antelligence-app/.env` (`PRIVATE_KEY`; never printed). Its public address is `0xEE8a688CE7beb1bd46bd5C84bd774Efc750fB086`.
  - **ZKsync Era Sepolia (chain 300):** balance **0 ETH**, nonce 0. Checked via `https://sepolia.era.zksync.dev`, `https://zksync-sepolia.drpc.org` and the explorer API (`No transactions found`).
  - **Base Sepolia:** 0.00796 ETH.

## 6. Changes in this PR

- `SPRINT.md`: Phase 6 ticked with evidence; Phase 7 (Sprint 1) added.
- `docs/status/2026-10-08-truth-pass.md`: this file.
