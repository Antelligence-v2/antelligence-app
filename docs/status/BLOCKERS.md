# Blockers

Newest first. Each entry records what was tried, the exact error, and what the operator must do.

## 2026-10-08: ZKsync Era Sepolia deployer has no gas (W1 step 4)

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
