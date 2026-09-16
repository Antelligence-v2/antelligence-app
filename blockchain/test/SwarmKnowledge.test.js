const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("Swarm Knowledge Sharing", function () {
  let tumorIntel;
  let experienceRegistry;
  let mockVerifier;
  let owner, validator1, validator2, other;

  beforeEach(async function () {
    [owner, validator1, validator2, other] = await ethers.getSigners();

    const TumorIntel = await ethers.getContractFactory("TumorIntel");
    tumorIntel = await TumorIntel.deploy();
    await tumorIntel.waitForDeployment();

    const MockProofVerifier = await ethers.getContractFactory("MockProofVerifier");
    mockVerifier = await MockProofVerifier.deploy();
    await mockVerifier.waitForDeployment();

    await tumorIntel.setVerifier(await mockVerifier.getAddress());

    const ExperienceRegistry = await ethers.getContractFactory("ExperienceRegistry");
    experienceRegistry = await ExperienceRegistry.deploy();
    await experienceRegistry.waitForDeployment();

    await experienceRegistry.addValidator(validator1.address);
    await experienceRegistry.addValidator(validator2.address);
  });

  describe("TumorIntel - getActivePinDetails", function () {
    it("returns full details of all active pins in a single call", async function () {
      await tumorIntel.reportIntel(100, 200, 0, 5); // HYPOXIC_CLUSTER
      await tumorIntel.reportIntel(300, 400, 1, 8); // STEM_CELL_DETECTED
      await tumorIntel.reportIntel(500, 600, 4, 3); // SUCCESSFUL_KILL

      const result = await tumorIntel.getActivePinDetails();
      expect(result.ids.length).to.equal(3);
      expect(result.xs[0]).to.equal(100);
      expect(result.ys[0]).to.equal(200);
      expect(result.priorities[1]).to.equal(8);
      expect(result.reporters[0]).to.equal(owner.address);
    });

    it("excludes deactivated pins", async function () {
      await tumorIntel.reportIntel(100, 200, 0, 5);
      await tumorIntel.reportIntel(300, 400, 1, 8);
      await tumorIntel.deactivateIntel(0);

      const result = await tumorIntel.getActivePinDetails();
      expect(result.ids.length).to.equal(1);
      expect(result.xs[0]).to.equal(300);
    });

    it("includes confirmation counts", async function () {
      await tumorIntel.reportIntel(100, 200, 0, 5);
      await tumorIntel.connect(other).confirmIntel(0);

      const result = await tumorIntel.getActivePinDetails();
      expect(result.pinConfirmations[0]).to.equal(1);
    });
  });

  describe("TumorIntel - getVerificationStatus", function () {
    it("returns 0 for unknown config hash", async function () {
      const status = await tumorIntel.getVerificationStatus(ethers.ZeroHash);
      expect(status).to.equal(0);
    });

    it("returns 1 after submission", async function () {
      const configHash = ethers.id("test-config");
      await tumorIntel.submitSimulation(configHash, 5000, 10, 200, 100);
      const status = await tumorIntel.getVerificationStatus(configHash);
      expect(status).to.equal(1);
    });

    it("returns 2 after verification", async function () {
      const configHash = ethers.id("test-config-verify");
      await tumorIntel.submitSimulation(configHash, 5000, 10, 200, 100);

      const abiCoder = new ethers.AbiCoder();
      const publicValues = abiCoder.encode(
        ["bytes32", "uint32", "uint32", "uint32", "uint32"],
        [configHash, 5000, 10, 200, 100]
      );
      const proofBytes = "0x" + "ab".repeat(64);
      await tumorIntel.verifySimulation(publicValues, proofBytes);

      const status = await tumorIntel.getVerificationStatus(configHash);
      expect(status).to.equal(2);
    });
  });

  describe("TumorIntel - pruneStalePins", function () {
    it("rejects pruning by non-owners", async function () {
      await tumorIntel.reportIntel(100, 200, 0, 5);
      await ethers.provider.send("evm_increaseTime", [3600]);
      await ethers.provider.send("evm_mine");

      await expect(tumorIntel.connect(other).pruneStalePins(0))
        .to.be.revertedWith("Only owner");

      const result = await tumorIntel.getActivePinDetails();
      expect(result.ids.length).to.equal(1);
    });

    it("deactivates old unconfirmed pins", async function () {
      await tumorIntel.reportIntel(100, 200, 0, 5);
      // Advance time by 1 hour
      await ethers.provider.send("evm_increaseTime", [3600]);
      await ethers.provider.send("evm_mine");

      await tumorIntel.pruneStalePins(1800); // 30 min threshold

      const result = await tumorIntel.getActivePinDetails();
      expect(result.ids.length).to.equal(0);
    });

    it("preserves pins with 2+ confirmations", async function () {
      await tumorIntel.reportIntel(100, 200, 0, 5);
      await tumorIntel.connect(other).confirmIntel(0);
      await tumorIntel.connect(validator1).confirmIntel(0);

      await ethers.provider.send("evm_increaseTime", [3600]);
      await ethers.provider.send("evm_mine");

      await tumorIntel.pruneStalePins(1800);

      const result = await tumorIntel.getActivePinDetails();
      expect(result.ids.length).to.equal(1);
    });
  });

  describe("ExperienceRegistry - Strategy Promotion", function () {
    async function submitAndVerifyExperience(runHash, score) {
      const strategyMeta = {
        strategyType: "pheromone-guided",
        modelUsed: "gpt-4o-mini",
        nanobotCount: 10,
        tumorRadius: 200,
        datasetHash: ethers.ZeroHash,
        workerParamsJson: JSON.stringify({ trail_decay: score / 10000, recruitment_diffusion: 1e-6 })
      };

      await experienceRegistry.submitExperience(
        runHash,
        "QmTestCid",
        ethers.id("test-data"),
        score,
        strategyMeta
      );

      // Attest with 2 validators to auto-verify
      await experienceRegistry.connect(validator1).attestExperience(runHash, 80, "good");
      await experienceRegistry.connect(validator2).attestExperience(runHash, 90, "great");
    }

    it("promotes a verified experience", async function () {
      const runHash = ethers.id("run-1");
      await submitAndVerifyExperience(runHash, 750);

      await experienceRegistry.promoteStrategy(runHash);

      expect(await experienceRegistry.isPromoted(runHash)).to.be.true;
      expect(await experienceRegistry.getPromotedCount()).to.equal(1);
    });

    it("reverts on unverified experience", async function () {
      const runHash = ethers.id("run-unverified");
      const strategyMeta = {
        strategyType: "pheromone-guided",
        modelUsed: "gpt-4o-mini",
        nanobotCount: 10,
        tumorRadius: 200,
        datasetHash: ethers.ZeroHash,
        workerParamsJson: JSON.stringify({ trail_decay: 0.05, recruitment_diffusion: 1e-6 })
      };
      await experienceRegistry.submitExperience(
        runHash, "QmTest", ethers.id("data"), 500, strategyMeta
      );

      await expect(experienceRegistry.promoteStrategy(runHash))
        .to.be.revertedWith("Not verified");
    });

    it("reverts on double promotion", async function () {
      const runHash = ethers.id("run-double");
      await submitAndVerifyExperience(runHash, 750);
      await experienceRegistry.promoteStrategy(runHash);

      await expect(experienceRegistry.promoteStrategy(runHash))
        .to.be.revertedWith("Already promoted");
    });

    it("getTopStrategies returns sorted by score descending", async function () {
      await submitAndVerifyExperience(ethers.id("run-a"), 500);
      await submitAndVerifyExperience(ethers.id("run-b"), 900);
      await submitAndVerifyExperience(ethers.id("run-c"), 700);

      await experienceRegistry.promoteStrategy(ethers.id("run-a"));
      await experienceRegistry.promoteStrategy(ethers.id("run-b"));
      await experienceRegistry.promoteStrategy(ethers.id("run-c"));

      const top3 = await experienceRegistry.getTopStrategies(3);
      expect(top3.length).to.equal(3);
      expect(top3[0].score).to.equal(900);
      expect(top3[1].score).to.equal(700);
      expect(top3[2].score).to.equal(500);
      expect(JSON.parse(top3[0].workerParamsJson)).to.deep.equal({
        trail_decay: 0.09,
        recruitment_diffusion: 1e-6
      });
    });

    it("getTopStrategies returns fewer if not enough promoted", async function () {
      await submitAndVerifyExperience(ethers.id("run-x"), 600);
      await experienceRegistry.promoteStrategy(ethers.id("run-x"));

      const top5 = await experienceRegistry.getTopStrategies(5);
      expect(top5.length).to.equal(1);
      expect(top5[0].score).to.equal(600);
    });

    it("getExperiencesByStrategy filters by type", async function () {
      // Submit with different strategy types
      const meta1 = { strategyType: "pheromone-guided", modelUsed: "m", nanobotCount: 10, tumorRadius: 200, datasetHash: ethers.ZeroHash, workerParamsJson: "{}" };
      const meta2 = { strategyType: "llm-queen", modelUsed: "m", nanobotCount: 10, tumorRadius: 200, datasetHash: ethers.ZeroHash, workerParamsJson: "{}" };

      await experienceRegistry.submitExperience(ethers.id("r1"), "c1", ethers.id("d1"), 500, meta1);
      await experienceRegistry.submitExperience(ethers.id("r2"), "c2", ethers.id("d2"), 600, meta2);

      await experienceRegistry.connect(validator1).attestExperience(ethers.id("r1"), 80, "ok");
      await experienceRegistry.connect(validator2).attestExperience(ethers.id("r1"), 80, "ok");
      await experienceRegistry.connect(validator1).attestExperience(ethers.id("r2"), 80, "ok");
      await experienceRegistry.connect(validator2).attestExperience(ethers.id("r2"), 80, "ok");

      await experienceRegistry.promoteStrategy(ethers.id("r1"));
      await experienceRegistry.promoteStrategy(ethers.id("r2"));

      const pheromoneRuns = await experienceRegistry.getExperiencesByStrategy("pheromone-guided");
      expect(pheromoneRuns.length).to.equal(1);
      expect(pheromoneRuns[0]).to.equal(ethers.id("r1"));
    });

    it("emits StrategyPromoted event", async function () {
      const runHash = ethers.id("run-event");
      await submitAndVerifyExperience(runHash, 800);

      await expect(experienceRegistry.promoteStrategy(runHash))
        .to.emit(experienceRegistry, "StrategyPromoted")
        .withArgs(runHash, 800, owner.address);
    });
  });
});
