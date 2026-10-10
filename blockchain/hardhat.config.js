require("@nomicfoundation/hardhat-toolbox");
// ZKsync tooling. These plugins only switch the compiler to zksolc on networks
// marked `zksync: true`, so `npx hardhat test` on the default network still
// compiles with solc and runs on the EVM exactly as before.
require("@matterlabs/hardhat-zksync-solc");
require("@matterlabs/hardhat-zksync-deploy");
require("@matterlabs/hardhat-zksync-node");
require("@matterlabs/hardhat-zksync-ethers");
// Load from the repo root .env. ANTELLIGENCE_ENV_FILE lets a git worktree point at
// the main checkout's .env without copying secrets into the worktree.
require("dotenv").config({ path: process.env.ANTELLIGENCE_ENV_FILE || "../.env" });

const { BASE_SEPOLIA_RPC_URL, PRIVATE_KEY, ZKSYNC_SEPOLIA_RPC_URL } = process.env;
const hasKey = Boolean(PRIVATE_KEY && PRIVATE_KEY.length === 66);

module.exports = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
      viaIR: true,
    },
  },
  zksolc: {
    // Pinned (not "latest") so a deployment is reproducible from its commit.
    version: "1.5.15",
    settings: {
      optimizer: { enabled: true, mode: "3" },
      codegen: "yul",
    },
  },
  networks: {
    hardhat: {},

    // Local ZKsync in-memory node (anvil-zksync on :8011).
    inMemoryNode: {
      url: "http://127.0.0.1:8011",
      ethNetwork: "",
      zksync: true,
    },

    // ZKsync Era Sepolia testnet (chain 300). Public RPC by default; never put
    // an API-keyed RPC URL in this file (the repo is public).
    zkSyncSepoliaTestnet: {
      url: ZKSYNC_SEPOLIA_RPC_URL || "https://sepolia.era.zksync.dev",
      ethNetwork: "sepolia",
      zksync: true,
      chainId: 300,
      verifyURL: "https://explorer.sepolia.era.zksync.dev/contract_verification",
      ...(hasKey ? { accounts: [PRIVATE_KEY] } : {}),
    },

    ...(BASE_SEPOLIA_RPC_URL && hasKey
      ? {
          baseSepolia: {
            url: BASE_SEPOLIA_RPC_URL,
            accounts: [PRIVATE_KEY],
            chainId: 84532, // Base Sepolia testnet chain ID
          },
        }
      : {}),
  },
};
