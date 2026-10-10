// Deploy the Antelligence contracts to a ZKsync network (EraVM) and record them.
//
//   npx hardhat compile --network zkSyncSepoliaTestnet
//   npx hardhat run scripts/deploy-zksync.js --network inMemoryNode          # local rehearsal (chain 260)
//   npx hardhat run scripts/deploy-zksync.js --network zkSyncSepoliaTestnet  # testnet (chain 300)
//
// Deploys the same set as scripts/deploy.js: FoodToken, ColonyMemory, TumorIntel,
// ExperienceRegistry.
//
// MockProofVerifier is deliberately NOT deployed or wired in. TumorIntel.verifySimulation
// marks a run verified whenever its verifier says yes, and the mock always says yes, so
// wiring it would let a mock proof read as `isVerified == true` on-chain. With no verifier
// configured, verifySimulation reverts ("Verifier not configured"): the attestation path
// stops at submitSimulation, which is honestly `proof_staged`/`mock`, never `verified_onchain`.
//
// Safety: refuses any chain other than 260 (local in-memory node) and 300 (Era Sepolia).
// Refuses to start if the deployer balance cannot cover the estimated deploy cost x1.5.

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");
const hre = require("hardhat");
const { Wallet, Provider } = require("zksync-ethers");
const { Deployer } = require("@matterlabs/hardhat-zksync-deploy");

const ALLOWED = {
  260: { name: "zksync-local-inmemory", explorer: null, committed: false },
  300: { name: "zksync-era-sepolia", explorer: "https://sepolia.explorer.zksync.io", committed: true },
};
const CONTRACTS = [
  { name: "FoodToken", args: (deployer) => [deployer] },
  { name: "ColonyMemory", args: () => [] },
  { name: "TumorIntel", args: () => [] },
  { name: "ExperienceRegistry", args: () => [] },
];
const SAFETY_FACTOR_NUM = 3n; // balance must be >= estimate * 1.5
const SAFETY_FACTOR_DEN = 2n;

function git(cmd) {
  return execSync(`git ${cmd}`, { cwd: path.join(__dirname, ".."), encoding: "utf8" }).trim();
}

function compilerVersions() {
  const buildInfoDir = path.join(__dirname, "..", "artifacts-zk", "build-info");
  const file = fs.readdirSync(buildInfoDir).filter((f) => f.endsWith(".json"))[0];
  const info = JSON.parse(fs.readFileSync(path.join(buildInfoDir, file), "utf8"));
  const settings = hre.config.solidity.compilers[0].settings;
  return {
    zksolc: hre.config.zksolc.version,
    solc: info.solcLongVersion,
    zksolc_settings: hre.config.zksolc.settings,
    solc_optimizer: settings.optimizer,
    via_ir: settings.viaIR,
  };
}

function deployerWallet(provider, chainId) {
  if (chainId === 260) {
    // Public, well-known anvil-zksync dev account #0 (local node only; holds no real value).
    const { richWallets } = require("@matterlabs/hardhat-zksync-ethers/dist/rich-wallets");
    return new Wallet(richWallets["0x104"][0].privateKey, provider);
  }
  const accounts = hre.network.config.accounts;
  if (!Array.isArray(accounts) || accounts.length === 0) {
    throw new Error("No deployer key configured for this network (PRIVATE_KEY in ../.env).");
  }
  return new Wallet(accounts[0], provider);
}

async function main() {
  if (!hre.network.config.zksync) throw new Error(`Network ${hre.network.name} is not a ZKsync network.`);
  const provider = new Provider(hre.network.config.url);
  const chainId = Number((await provider.getNetwork()).chainId);
  const target = ALLOWED[chainId];
  if (!target) throw new Error(`Refusing to deploy: chain ${chainId} is not an allowed testnet/local chain.`);

  const wallet = deployerWallet(provider, chainId);
  const deployer = new Deployer(hre, wallet);
  const balance = await provider.getBalance(wallet.address);

  // Pre-flight: estimate every deploy before sending any transaction.
  const artifacts = {};
  let estimate = 0n;
  for (const c of CONTRACTS) {
    artifacts[c.name] = await deployer.loadArtifact(c.name);
    estimate += await deployer.estimateDeployFee(artifacts[c.name], c.args(wallet.address));
  }
  const needed = (estimate * SAFETY_FACTOR_NUM) / SAFETY_FACTOR_DEN;
  const preflight = {
    chain_id: chainId,
    network: hre.network.name,
    deployer: wallet.address,
    balance_wei: balance.toString(),
    estimated_deploy_fee_wei: estimate.toString(),
    required_with_margin_wei: needed.toString(),
  };
  console.log(JSON.stringify({ preflight }, null, 2));
  if (balance < needed) {
    throw new Error(
      `Insufficient testnet gas: balance ${balance} wei < required ${needed} wei (estimate x1.5). Not deploying.`,
    );
  }

  const commit = git("rev-parse HEAD");
  const dirty = git("status --porcelain -- contracts hardhat.config.js scripts") !== "";
  const records = [];
  for (const c of CONTRACTS) {
    const contract = await deployer.deploy(artifacts[c.name], c.args(wallet.address));
    const tx = contract.deploymentTransaction();
    const receipt = await tx.wait();
    const address = await contract.getAddress();
    records.push({
      name: c.name,
      address,
      deploy_tx_hash: receipt.hash,
      block_number: receipt.blockNumber,
      deployer: wallet.address,
      is_mock: false,
      constructor_args: c.args(wallet.address),
      gas_used: receipt.gasUsed.toString(),
      explorer_address_url: target.explorer ? `${target.explorer}/address/${address}` : null,
      explorer_tx_url: target.explorer ? `${target.explorer}/tx/${receipt.hash}` : null,
    });
    console.log(`${c.name} -> ${address} (tx ${receipt.hash}, block ${receipt.blockNumber})`);
  }
  const balanceAfter = await provider.getBalance(wallet.address);

  const out = {
    schema: "antelligence.deployment/v1",
    network: target.name,
    chain_id: chainId,
    vm: "EraVM",
    deployer: wallet.address,
    deployed_at_utc: new Date().toISOString(),
    git_commit: commit,
    git_tree_dirty_for_blockchain_dir: dirty,
    compiler: compilerVersions(),
    gas: {
      balance_before_wei: balance.toString(),
      balance_after_wei: balanceAfter.toString(),
      spent_wei: (balance - balanceAfter).toString(),
      estimated_deploy_fee_wei: estimate.toString(),
    },
    proof_verifier: {
      address: null,
      note:
        "No proof verifier is configured on TumorIntel. verifySimulation() reverts, so no run can become " +
        "verified on-chain from this deployment. MockProofVerifier was intentionally not deployed.",
    },
    contracts: records,
  };
  const dir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${target.name}.json`);
  fs.writeFileSync(file, JSON.stringify(out, null, 2) + "\n");
  console.log(`Wrote ${path.relative(path.join(__dirname, ".."), file)}`);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exitCode = 1;
});
