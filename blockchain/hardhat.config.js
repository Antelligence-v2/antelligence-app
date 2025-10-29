require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config({ path: "../.env" }); // Load from parent directory

const { BASE_SEPOLIA_RPC_URL, PRIVATE_KEY } = process.env;

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
  networks: {
    hardhat: {},

    ...(BASE_SEPOLIA_RPC_URL && PRIVATE_KEY && PRIVATE_KEY.length === 66
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
