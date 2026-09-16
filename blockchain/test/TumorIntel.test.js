const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("TumorIntel", function () {
  let TumorIntel;
  let tumorIntel;
  let owner;
  let addr1;
  let addr2;

  beforeEach(async function () {
    [owner, addr1, addr2] = await ethers.getSigners();
    TumorIntel = await ethers.getContractFactory("TumorIntel");
    tumorIntel = await TumorIntel.deploy();
    await tumorIntel.waitForDeployment();
  });

  describe("Deployment", function () {
    it("Should deploy successfully", async function () {
      expect(await tumorIntel.getAddress()).to.be.properAddress;
    });
  });

  describe("Intel Reporting", function () {
    it("Should allow reporting new intel", async function () {
      const tx = await tumorIntel.connect(addr1).reportIntel(
        100, // x
        200, // y
        0,   // PinType.HYPOXIC_CLUSTER
        5    // priority
      );
      
      await expect(tx)
        .to.emit(tumorIntel, "IntelReported")
        .withArgs(0, 100, 200, 0, addr1.address, 5);
      
      const pin = await tumorIntel.intelPins(0);
      expect(pin.x).to.equal(100);
      expect(pin.y).to.equal(200);
      expect(pin.pinType).to.equal(0); // HYPOXIC_CLUSTER
      expect(pin.reporter).to.equal(addr1.address);
      expect(pin.priority).to.equal(5);
      expect(pin.isActive).to.equal(true);
    });

    it("Should increment pin ID for each new report", async function () {
      await tumorIntel.connect(addr1).reportIntel(100, 200, 0, 5);
      await tumorIntel.connect(addr2).reportIntel(150, 250, 1, 7);
      
      const pin0 = await tumorIntel.intelPins(0);
      const pin1 = await tumorIntel.intelPins(1);
      
      expect(pin0.x).to.equal(100);
      expect(pin1.x).to.equal(150);
    });
  });

  describe("Intel Confirmation", function () {
    beforeEach(async function () {
      await tumorIntel.connect(addr1).reportIntel(100, 200, 0, 5);
    });

    it("Should allow confirming intel", async function () {
      const tx = await tumorIntel.connect(addr2).confirmIntel(0);
      
      // The event has 3 parameters: pinId, confirmer, totalConfirmations
      await expect(tx)
        .to.emit(tumorIntel, "IntelConfirmed")
        .withArgs(0, addr2.address, 1);
      
      expect(await tumorIntel.confirmations(0)).to.equal(1);
      expect(await tumorIntel.hasConfirmed(0, addr2.address)).to.equal(true);
    });

    it("Should prevent duplicate confirmation by same address", async function () {
      await tumorIntel.connect(addr2).confirmIntel(0);
      
      await expect(
        tumorIntel.connect(addr2).confirmIntel(0)
      ).to.be.revertedWith("Already confirmed this intel");
    });

    it("Should allow multiple confirmations from different addresses", async function () {
      await tumorIntel.connect(addr2).confirmIntel(0);
      await tumorIntel.connect(owner).confirmIntel(0);
      
      expect(await tumorIntel.confirmations(0)).to.equal(2);
    });
  });

  describe("Intel Deactivation", function () {
    beforeEach(async function () {
      await tumorIntel.connect(addr1).reportIntel(100, 200, 0, 5);
    });

    it("Should allow reporter to deactivate intel", async function () {
      const tx = await tumorIntel.connect(addr1).deactivateIntel(0);
      
      await expect(tx)
        .to.emit(tumorIntel, "IntelDeactivated")
        .withArgs(0, addr1.address);
      
      const pin = await tumorIntel.intelPins(0);
      expect(pin.isActive).to.equal(false);
    });

    it("Should allow confirmer to deactivate intel", async function () {
      // First confirm, then deactivate
      await tumorIntel.connect(addr2).confirmIntel(0);
      const tx = await tumorIntel.connect(addr2).deactivateIntel(0);

      await expect(tx)
        .to.emit(tumorIntel, "IntelDeactivated")
        .withArgs(0, addr2.address);

      const pin = await tumorIntel.intelPins(0);
      expect(pin.isActive).to.equal(false);
    });
  });

  describe("Intel Querying", function () {
    beforeEach(async function () {
      await tumorIntel.connect(addr1).reportIntel(100, 200, 0, 5);
      await tumorIntel.connect(addr2).reportIntel(150, 250, 1, 7);
      await tumorIntel.connect(addr1).reportIntel(200, 300, 2, 3);
    });

    it("Should return correct intel count", async function () {
      expect(await tumorIntel.getPinCount()).to.equal(3);
    });

    it("Should return active intel only", async function () {
      await tumorIntel.connect(addr2).deactivateIntel(1);
      
      const activeIntel = await tumorIntel.getActivePins();
      expect(activeIntel.length).to.equal(2);
    });

    it("Should return intel by type", async function () {
      const hypoxicIntel = await tumorIntel.getPinsByType(0); // HYPOXIC_CLUSTER
      expect(hypoxicIntel.length).to.equal(1);
      // Check that the returned ID corresponds to the right pin
      const pinId = hypoxicIntel[0];
      const pin = await tumorIntel.intelPins(pinId);
      expect(pin.x).to.equal(100);
    });

    it("Should return intel details from mapping", async function () {
      const pin = await tumorIntel.intelPins(0);
      expect(pin.x).to.equal(100);
      expect(pin.y).to.equal(200);
      expect(pin.pinType).to.equal(0);
      expect(pin.reporter).to.equal(addr1.address);
      expect(pin.priority).to.equal(5);
      expect(pin.isActive).to.equal(true);
      expect(await tumorIntel.confirmations(0)).to.equal(0);
    });
  });
});