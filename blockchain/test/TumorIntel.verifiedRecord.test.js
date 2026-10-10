const { expect } = require("chai");
const { ethers } = require("hardhat");

// A verified simulation record holds values a proof verifier accepted. These tests pin down
// that nothing short of another proof can change them, and that publicValuesHash binds the
// record to exactly the proven values (the backend relies on that hash, not on isVerified).
describe("TumorIntel - verified records are immutable", function () {
  const coder = ethers.AbiCoder.defaultAbiCoder();
  const TYPES = ["bytes32", "uint32", "uint32", "uint32", "uint32"];
  let intel;
  let owner;
  let honest;
  let attacker;
  let cfg;
  let publicValues;

  beforeEach(async function () {
    [owner, honest, attacker] = await ethers.getSigners();
    intel = await (await ethers.getContractFactory("TumorIntel")).deploy();
    const verifier = await (await ethers.getContractFactory("MockProofVerifier")).deploy();
    await intel.connect(owner).setVerifier(await verifier.getAddress());
    cfg = ethers.id("config-A");
    publicValues = coder.encode(TYPES, [cfg, 3000, 5, 66, 30]);
    await intel.connect(honest).submitSimulation(cfg, 3000, 5, 66, 30);
    await intel.connect(honest).verifySimulation(publicValues, "0x01");
  });

  it("rejects a resubmission that would rewrite a verified record", async function () {
    await expect(intel.connect(attacker).submitSimulation(cfg, 9999, 5, 66, 30))
      .to.be.revertedWith("Simulation already verified");
  });

  it("rejects an identical resubmission too (no attribution takeover)", async function () {
    await expect(intel.connect(attacker).submitSimulation(cfg, 3000, 5, 66, 30))
      .to.be.revertedWith("Simulation already verified");
    expect((await intel.getSimulation(cfg)).submitter).to.equal(honest.address);
  });

  it("keeps the proven values, submitter and verified flag", async function () {
    const rec = await intel.getSimulation(cfg);
    expect(rec.killRateBps).to.equal(3000);
    expect(rec.submitter).to.equal(honest.address);
    expect(rec.verified).to.equal(true);
    expect(await intel.isVerified(cfg)).to.equal(true);
  });

  it("stores publicValuesHash = keccak256(abi.encode(proven values))", async function () {
    const rec = await intel.getSimulation(cfg);
    expect(rec.publicValuesHash).to.equal(ethers.keccak256(publicValues));
    expect(rec.publicValuesHash).to.not.equal(ethers.keccak256(coder.encode(TYPES, [cfg, 9999, 5, 66, 30])));
  });

  it("still lets unverified records be resubmitted before any proof", async function () {
    const other = ethers.id("config-B");
    await intel.connect(honest).submitSimulation(other, 1000, 5, 66, 30);
    await intel.connect(honest).submitSimulation(other, 1100, 5, 66, 30);
    expect((await intel.getSimulation(other)).killRateBps).to.equal(1100);
  });
});
