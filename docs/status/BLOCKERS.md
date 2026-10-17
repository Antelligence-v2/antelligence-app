# Blockers

Newest first. Each entry records what was tried, the exact error, and what the operator must do.

## 2026-10-09: ZKsync Era Sepolia gas blocker RESOLVED

- **Status:** RESOLVED 2026-10-09. The operator funded a new deployer, `0xF822f19C0FEc804f002e9087523677195a3C96cE` (0.095 ETH on chain 300). The four contracts were deployed and one end-to-end run completed (`docs/status/2026-10-08-chain-redeploy.md` §3a, `docs/status/e2e-zksync-era-sepolia.json`). Gas spent: 217,173,950,000,000 wei.
- The old deployer `0xEE8a688CE7beb1bd46bd5C84bd774Efc750fB086` and its key are retired. Nothing uses them any more.
- The entries below are kept as history.

## 2026-10-09 (history): ZKsync Era Sepolia deployer still unfunded (W1 steps 4-6)

- **Status:** open since 2026-10-08 (more than 60 min, now about a day). Steps 4 (testnet deploy) and 6 (testnet end-to-end run with explorer URL) cannot run.
- **Re-check, 2026-10-09T16:02Z** (`https://sepolia.era.zksync.dev`, block tag `latest`), address `0xEE8a688CE7beb1bd46bd5C84bd774Efc750fB086`:
  - `eth_chainId` = `0x12c` (300)
  - `eth_getBalance` = `0x0`
  - `eth_getTransactionCount` = `0x0`
- **Discrepancy:** the goal file said this deployer was funded. The chain says it holds 0 and has never sent a transaction.
- **Measured need:** the preflight in `blockchain/scripts/deploy-zksync.js` (line 36, `SAFETY_FACTOR_NUM = 3n`, i.e. balance must be at least estimate x1.5; applied at line 88) estimated 0.000438 ETH for the four contracts, so it requires about **0.00066 ETH** (657,385,050,000,000 wei). This replaces the earlier 0.02 ETH guess.
- **Needed from the operator (pick one):**
  1. Send **at least 0.001 Sepolia ETH on ZKsync Era Sepolia** (chain 300) to `0xEE8a688CE7beb1bd46bd5C84bd774Efc750fB086`, or
  2. Authorise the **Base Sepolia fallback**. The same key held about 0.008 ETH there at the 2026-10-08 check.
- **Not tried, by rule:** faucets and captchas. No new accounts were created.

## 2026-10-08 (history, resolved 2026-10-09): ZKsync Era Sepolia deployer has no gas (W1 step 4)

- **Status:** open. W1 continues locally: plugin, zksolc compile, tests on the in-memory node, deploy script, privacy audit and options note.
- **Deployer (public address):** `0xEE8a688CE7beb1bd46bd5C84bd774Efc750fB086`. This address is derived from the only deployer key configured for the repo (`.env` `PRIVATE_KEY`, never printed).
- **Tried:**
  1. `eth_getBalance` on `https://sepolia.era.zksync.dev`: chain 300, balance `0x0`, nonce 0.
  2. Same call on `https://zksync-sepolia.drpc.org`: chain `0x12c`, balance `0x0`.
  3. Explorer API `https://block-explorer-api.sepolia.zksync.dev/api?module=account&action=txlist&address=…`: `"No transactions found"`.
  4. For comparison, Base Sepolia (`https://base-sepolia-rpc.publicnode.com`): 0.00796 ETH, so the key itself works.
- **Not tried, by rule:** faucets and captchas. No new accounts were created.
- **Needed from the operator:** send **≥ 0.02 Sepolia ETH on ZKsync Era Sepolia** to the address above. Alternatively, point me at the funded key's existing config.
  - The 0.02 figure is an estimate: about four contract deploys plus one submission, with headroom. It gets replaced with a measured number once `deploy-zksync.js` runs `estimateDeployFee` against the testnet.
- **Fallback already authorised by the goal:** Base Sepolia, if ZKsync stays blocked.
