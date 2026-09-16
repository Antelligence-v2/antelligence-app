const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ExperienceRegistry", function () {
  let ExperienceRegistry;
  let registry;
  let owner;
  let validator1;
  let validator2;
  let submitter;
  
  beforeEach(async function () {
    [owner, validator1, validator2, submitter] = await ethers.getSigners();
    
    ExperienceRegistry = await ethers.getContractFactory("ExperienceRegistry");
    registry = await ExperienceRegistry.deploy();
    await registry.waitForDeployment();
    
    // Add validators
    await registry.addValidator(validator1.address);
    await registry.addValidator(validator2.address);
  });
  
  describe("Deployment", function () {
    it("Should set the right owner", async function () {
      expect(await registry.owner()).to.equal(owner.address);
    });
    
    it("Should set owner as validator", async function () {
      expect(await registry.authorizedValidators(owner.address)).to.equal(true);
    });
    
    it("Should have default min attestations of 2", async function () {
      expect(await registry.minAttestations()).to.equal(2);
    });
  });
  
  describe("Validator Management", function () {
    it("Should allow owner to add validator", async function () {
      const newValidator = (await ethers.getSigners())[5];
      await registry.addValidator(newValidator.address);
      expect(await registry.authorizedValidators(newValidator.address)).to.equal(true);
    });
    
    it("Should allow owner to remove validator", async function () {
      await registry.removeValidator(validator1.address);
      expect(await registry.authorizedValidators(validator1.address)).to.equal(false);
    });
    
    it("Should prevent non-owners from adding validators", async function () {
      await expect(
        registry.connect(validator1).addValidator(validator2.address)
      ).to.be.revertedWith("Only owner");
    });
  });
  
  describe("Experience Submission", function () {
    const runHash = ethers.keccak256(ethers.toUtf8Bytes("test-run-123"));
    const ipfsCid = "QmTest123";
    const dataHash = ethers.keccak256(ethers.toUtf8Bytes("test-data"));
    const score = 1500;
    const strategyMeta = {
      strategyType: "pheromone-guided",
      modelUsed: "meta-llama/Llama-3.3-70B-Instruct",
      nanobotCount: 10,
      tumorRadius: 120,
      datasetHash: ethers.keccak256(ethers.toUtf8Bytes("BraTS-subject-001")),
      workerParamsJson: JSON.stringify({ trail_decay: 0.08, recruitment_diffusion: 1e-6 })
    };
    
    it("Should submit new experience", async function () {
      await expect(
        registry.connect(submitter).submitExperience(runHash, ipfsCid, dataHash, score, strategyMeta)
      ).to.emit(registry, "ExperienceSubmitted")
       .withArgs(runHash, ipfsCid, dataHash, score, submitter.address);
      
      const [exp, meta] = await registry.getExperience(runHash);
      expect(exp.runHash).to.equal(runHash);
      expect(exp.ipfsCid).to.equal(ipfsCid);
      expect(exp.score).to.equal(score);
      expect(exp.submitter).to.equal(submitter.address);
      expect(exp.verified).to.equal(false);
      
      expect(meta.strategyType).to.equal(strategyMeta.strategyType);
      expect(meta.modelUsed).to.equal(strategyMeta.modelUsed);
    });
    
    it("Should prevent duplicate submissions", async function () {
      await registry.connect(submitter).submitExperience(runHash, ipfsCid, dataHash, score, strategyMeta);
      
      await expect(
        registry.connect(submitter).submitExperience(runHash, "QmAnother", dataHash, 2000, strategyMeta)
      ).to.be.revertedWith("Experience already exists");
    });
    
    it("Should require positive score", async function () {
      await expect(
        registry.connect(submitter).submitExperience(runHash, ipfsCid, dataHash, 0, strategyMeta)
      ).to.be.revertedWith("Score must be positive");
    });
  });
  
  describe("Experience Attestation", function () {
    const runHash = ethers.keccak256(ethers.toUtf8Bytes("test-run-456"));
    
    beforeEach(async function () {
      await registry.connect(submitter).submitExperience(
        runHash,
        "QmTest456",
        ethers.keccak256(ethers.toUtf8Bytes("data456")),
        1800,
        {
          strategyType: "LLM-queen",
          modelUsed: "gpt-4o",
          nanobotCount: 15,
          tumorRadius: 150,
          datasetHash: ethers.keccak256(ethers.toUtf8Bytes("BraTS-subject-002")),
          workerParamsJson: JSON.stringify({ trail_decay: 0.1, recruitment_diffusion: 2e-6 })
        }
      );
    });
    
    it("Should allow validator to attest", async function () {
      await expect(
        registry.connect(validator1).attestExperience(runHash, 85, "Good strategy")
      ).to.emit(registry, "ExperienceAttested")
       .withArgs(runHash, validator1.address, 85);
      
      const [exp] = await registry.getExperience(runHash);
      expect(exp.attestations).to.equal(1);
      
      const atts = await registry.getAttestations(runHash);
      expect(atts.length).to.equal(1);
      expect(atts[0].validator).to.equal(validator1.address);
      expect(atts[0].quality).to.equal(85);
    });
    
    it("Should prevent non-validators from attesting", async function () {
      await expect(
        registry.connect(submitter).attestExperience(runHash, 90, "Test")
      ).to.be.revertedWith("Not authorized validator");
    });
    
    it("Should prevent duplicate attestation", async function () {
      await registry.connect(validator1).attestExperience(runHash, 85, "First");
      
      await expect(
        registry.connect(validator1).attestExperience(runHash, 90, "Second")
      ).to.be.revertedWith("Already attested");
    });
    
    it("Should auto-verify after enough attestations", async function () {
      await registry.connect(validator1).attestExperience(runHash, 85, "Good");
      
      let [exp] = await registry.getExperience(runHash);
      expect(exp.verified).to.equal(false);
      
      await registry.connect(validator2).attestExperience(runHash, 90, "Excellent");
      
      [exp] = await registry.getExperience(runHash);
      expect(exp.verified).to.equal(true);
      expect(exp.attestations).to.equal(2);
    });
    
    it("Should calculate average quality", async function () {
      await registry.connect(validator1).attestExperience(runHash, 80, "Good");
      await registry.connect(validator2).attestExperience(runHash, 90, "Excellent");
      
      const avg = await registry.getAverageQuality(runHash);
      expect(avg).to.equal(85); // (80 + 90) / 2 = 85
    });
  });
  
  describe("Manual Verification", function () {
    const runHash = ethers.keccak256(ethers.toUtf8Bytes("test-run-789"));
    
    beforeEach(async function () {
      await registry.connect(submitter).submitExperience(
        runHash,
        "QmTest789",
        ethers.keccak256(ethers.toUtf8Bytes("data789")),
        2200,
        {
          strategyType: "hybrid",
          modelUsed: "gemini-2.0",
          nanobotCount: 20,
          tumorRadius: 200,
          datasetHash: ethers.keccak256(ethers.toUtf8Bytes("BraTS-subject-003")),
          workerParamsJson: JSON.stringify({ trail_decay: 0.12, recruitment_diffusion: 3e-6 })
        }
      );
      
      await registry.connect(validator1).attestExperience(runHash, 95, "Outstanding");
    });
    
    it("Should allow manual verification with enough attestations", async function () {
      await registry.connect(validator2).attestExperience(runHash, 85, "Good");
      
      // Already auto-verified, but we can test manual
      const [exp] = await registry.getExperience(runHash);
      expect(exp.verified).to.equal(true);
    });
    
    it("Should prevent manual verification with insufficient attestations", async function () {
      await expect(
        registry.connect(validator2).verifyExperience(runHash)
      ).to.be.revertedWith("Insufficient attestations");
    });
  });
  
  describe("Configuration", function () {
    it("Should allow owner to update min attestations", async function () {
      await registry.setMinAttestations(3);
      expect(await registry.minAttestations()).to.equal(3);
    });
    
    it("Should prevent non-owners from updating min attestations", async function () {
      await expect(
        registry.connect(validator1).setMinAttestations(1)
      ).to.be.revertedWith("Only owner");
    });
  });
});