// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IProofVerifier {
    function verifyProof(bytes calldata publicValues, bytes calldata proofBytes) external view returns (bool);
}

/**
 * @title TumorIntel
 * @dev Shared swarm-intelligence memory plus proof-backed simulation attestations.
 *
 * The contract keeps the existing battlefield intel pin workflow while adding an
 * explicit lifecycle for simulation attestations:
 * 1. submitSimulation(...) stores public metadata on-chain
 * 2. verifySimulation(publicValues, proofBytes) verifies a proof via the configured verifier
 * 3. isVerified(configHash) exposes verified state for backend/leaderboard consumers
 */
contract TumorIntel {
    enum PinType {
        HYPOXIC_CLUSTER,
        STEM_CELL_DETECTED,
        HIGH_RESISTANCE_AREA,
        VESSEL_LOCATION,
        SUCCESSFUL_KILL,
        DRUG_OVERDOSE_ZONE,
        TARGET_ACQUIRED,
        DRUG_DELIVERY
    }

    struct IntelPin {
        uint256 x;
        uint256 y;
        PinType pinType;
        address reporter;
        uint256 timestamp;
        uint256 priority;
        bool isActive;
    }

    struct SimulationRecord {
        bytes32 configHash;
        uint32 killRateBps;
        uint32 nanobotCount;
        uint32 tumorRadius;
        uint32 steps;
        address submitter;
        uint64 submittedAt;
        uint64 verifiedAt;
        bool submitted;
        bool verified;
        bytes32 publicValuesHash;
    }

    address public owner;
    address public verifier;

    IntelPin[] public intelPins;
    mapping(uint256 => uint256) public confirmations;
    mapping(uint256 => mapping(address => bool)) public hasConfirmed;

    mapping(bytes32 => SimulationRecord) public simulations;

    event IntelReported(
        uint256 indexed pinId,
        uint256 x,
        uint256 y,
        PinType pinType,
        address reporter,
        uint256 priority
    );

    event IntelConfirmed(uint256 indexed pinId, address confirmer, uint256 totalConfirmations);
    event IntelDeactivated(uint256 indexed pinId, address deactivator);
    event IntelPriorityUpdated(uint256 indexed pinId, uint256 oldPriority, uint256 newPriority, address updater);

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    event VerifierUpdated(address indexed previousVerifier, address indexed newVerifier);
    event SimulationSubmitted(
        bytes32 indexed configHash,
        address indexed submitter,
        uint32 killRateBps,
        uint32 nanobotCount,
        uint32 tumorRadius,
        uint32 steps
    );
    event SimulationVerified(bytes32 indexed configHash, address indexed verifierCaller, bytes32 publicValuesHash);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    constructor() {
        owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        require(newOwner != address(0), "Owner cannot be zero");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }

    function setVerifier(address newVerifier) external onlyOwner {
        emit VerifierUpdated(verifier, newVerifier);
        verifier = newVerifier;
    }

    function reportIntel(uint256 x, uint256 y, PinType pinType, uint256 priority) public returns (uint256) {
        require(priority >= 1 && priority <= 10, "Priority must be between 1 and 10");

        uint256 pinId = intelPins.length;
        intelPins.push(IntelPin({
            x: x,
            y: y,
            pinType: pinType,
            reporter: msg.sender,
            timestamp: block.timestamp,
            priority: priority,
            isActive: true
        }));

        emit IntelReported(pinId, x, y, pinType, msg.sender, priority);
        return pinId;
    }

    function confirmIntel(uint256 pinId) public {
        require(pinId < intelPins.length, "Invalid pin ID");
        require(intelPins[pinId].isActive, "Intel is no longer active");
        require(!hasConfirmed[pinId][msg.sender], "Already confirmed this intel");

        hasConfirmed[pinId][msg.sender] = true;
        confirmations[pinId] += 1;

        emit IntelConfirmed(pinId, msg.sender, confirmations[pinId]);
    }

    function deactivateIntel(uint256 pinId) public {
        require(pinId < intelPins.length, "Invalid pin ID");
        require(intelPins[pinId].isActive, "Intel already deactivated");
        require(
            msg.sender == intelPins[pinId].reporter || hasConfirmed[pinId][msg.sender],
            "Not authorized to deactivate"
        );

        intelPins[pinId].isActive = false;
        emit IntelDeactivated(pinId, msg.sender);
    }

    function updateIntelPriority(uint256 pinId, uint256 newPriority) public {
        require(pinId < intelPins.length, "Invalid pin ID");
        require(intelPins[pinId].isActive, "Intel is no longer active");
        require(newPriority >= 1 && newPriority <= 10, "Priority must be between 1 and 10");
        require(
            msg.sender == intelPins[pinId].reporter || hasConfirmed[pinId][msg.sender],
            "Not authorized to update priority"
        );

        uint256 oldPriority = intelPins[pinId].priority;
        intelPins[pinId].priority = newPriority;
        emit IntelPriorityUpdated(pinId, oldPriority, newPriority, msg.sender);
    }

    function submitSimulation(
        bytes32 configHash,
        uint32 killRateBps,
        uint32 nanobotCount,
        uint32 tumorRadius,
        uint32 steps
    ) public returns (bytes32) {
        require(configHash != bytes32(0), "Config hash required");

        SimulationRecord storage record = simulations[configHash];
        record.configHash = configHash;
        record.killRateBps = killRateBps;
        record.nanobotCount = nanobotCount;
        record.tumorRadius = tumorRadius;
        record.steps = steps;
        record.submitter = msg.sender;
        record.submittedAt = uint64(block.timestamp);
        record.submitted = true;

        emit SimulationSubmitted(configHash, msg.sender, killRateBps, nanobotCount, tumorRadius, steps);
        return configHash;
    }

    function verifySimulation(bytes calldata publicValues, bytes calldata proofBytes) external returns (bool) {
        require(verifier != address(0), "Verifier not configured");
        (bytes32 configHash, uint32 killRateBps, uint32 nanobotCount, uint32 tumorRadius, uint32 steps) =
            abi.decode(publicValues, (bytes32, uint32, uint32, uint32, uint32));

        require(configHash != bytes32(0), "Config hash required");
        require(IProofVerifier(verifier).verifyProof(publicValues, proofBytes), "Proof verification failed");

        SimulationRecord storage record = simulations[configHash];
        if (!record.submitted) {
            record.configHash = configHash;
            record.killRateBps = killRateBps;
            record.nanobotCount = nanobotCount;
            record.tumorRadius = tumorRadius;
            record.steps = steps;
            record.submitter = msg.sender;
            record.submittedAt = uint64(block.timestamp);
            record.submitted = true;
            emit SimulationSubmitted(configHash, msg.sender, killRateBps, nanobotCount, tumorRadius, steps);
        } else {
            require(record.killRateBps == killRateBps, "Kill rate mismatch");
            require(record.nanobotCount == nanobotCount, "Nanobot count mismatch");
            require(record.tumorRadius == tumorRadius, "Tumor radius mismatch");
            require(record.steps == steps, "Step count mismatch");
        }

        record.verified = true;
        record.verifiedAt = uint64(block.timestamp);
        record.publicValuesHash = keccak256(publicValues);

        emit SimulationVerified(configHash, msg.sender, record.publicValuesHash);
        return true;
    }

    function isVerified(bytes32 configHash) external view returns (bool) {
        return simulations[configHash].verified;
    }

    function getSimulation(bytes32 configHash) external view returns (SimulationRecord memory) {
        return simulations[configHash];
    }

    function getPinCount() public view returns (uint256) {
        return intelPins.length;
    }

    function getActivePins() public view returns (uint256[] memory) {
        uint256 activeCount = 0;
        for (uint256 i = 0; i < intelPins.length; i++) {
            if (intelPins[i].isActive) activeCount++;
        }

        uint256[] memory activePins = new uint256[](activeCount);
        uint256 index = 0;
        for (uint256 i = 0; i < intelPins.length; i++) {
            if (intelPins[i].isActive) {
                activePins[index] = i;
                index++;
            }
        }
        return activePins;
    }

    function getPinsByType(PinType pinType) public view returns (uint256[] memory) {
        uint256 count = 0;
        for (uint256 i = 0; i < intelPins.length; i++) {
            if (intelPins[i].pinType == pinType && intelPins[i].isActive) count++;
        }

        uint256[] memory pinIds = new uint256[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < intelPins.length; i++) {
            if (intelPins[i].pinType == pinType && intelPins[i].isActive) {
                pinIds[index] = i;
                index++;
            }
        }
        return pinIds;
    }

    function getHighPriorityPins() public view returns (uint256[] memory) {
        uint256 count = 0;
        for (uint256 i = 0; i < intelPins.length; i++) {
            if (intelPins[i].priority >= 8 && intelPins[i].isActive) count++;
        }

        uint256[] memory highPriorityPins = new uint256[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < intelPins.length; i++) {
            if (intelPins[i].priority >= 8 && intelPins[i].isActive) {
                highPriorityPins[index] = i;
                index++;
            }
        }
        return highPriorityPins;
    }

    function getPinsInArea(uint256 centerX, uint256 centerY, uint256 radius) public view returns (uint256[] memory) {
        uint256 count = 0;
        uint256 radiusSquared = radius * radius;
        for (uint256 i = 0; i < intelPins.length; i++) {
            if (!intelPins[i].isActive) continue;
            int256 deltaX = int256(intelPins[i].x) - int256(centerX);
            int256 deltaY = int256(intelPins[i].y) - int256(centerY);
            uint256 distanceSquared = uint256(deltaX * deltaX + deltaY * deltaY);
            if (distanceSquared <= radiusSquared) count++;
        }

        uint256[] memory pinIds = new uint256[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < intelPins.length; i++) {
            if (!intelPins[i].isActive) continue;
            int256 deltaX = int256(intelPins[i].x) - int256(centerX);
            int256 deltaY = int256(intelPins[i].y) - int256(centerY);
            uint256 distanceSquared = uint256(deltaX * deltaX + deltaY * deltaY);
            if (distanceSquared <= radiusSquared) {
                pinIds[index] = i;
                index++;
            }
        }
        return pinIds;
    }

    /// @notice Get full details of active intel pins (batch read for swarm knowledge sharing)
    /// @dev Returns arrays for x, y, pinType, reporter, priority, confirmations, timestamp
    ///      so nanobots and Queen can consume on-chain intel without N individual calls.
    function getActivePinDetails() external view returns (
        uint256[] memory ids,
        uint256[] memory xs,
        uint256[] memory ys,
        PinType[] memory types,
        address[] memory reporters,
        uint256[] memory priorities,
        uint256[] memory pinConfirmations,
        uint256[] memory timestamps
    ) {
        uint256 activeCount = 0;
        for (uint256 i = 0; i < intelPins.length; i++) {
            if (intelPins[i].isActive) activeCount++;
        }

        ids = new uint256[](activeCount);
        xs = new uint256[](activeCount);
        ys = new uint256[](activeCount);
        types = new PinType[](activeCount);
        reporters = new address[](activeCount);
        priorities = new uint256[](activeCount);
        pinConfirmations = new uint256[](activeCount);
        timestamps = new uint256[](activeCount);

        uint256 index = 0;
        for (uint256 i = 0; i < intelPins.length; i++) {
            if (intelPins[i].isActive) {
                ids[index] = i;
                xs[index] = intelPins[i].x;
                ys[index] = intelPins[i].y;
                types[index] = intelPins[i].pinType;
                reporters[index] = intelPins[i].reporter;
                priorities[index] = intelPins[i].priority;
                pinConfirmations[index] = confirmations[i];
                timestamps[index] = intelPins[i].timestamp;
                index++;
            }
        }
    }

    /// @notice Get verification status enum: 0=not submitted, 1=submitted, 2=verified
    function getVerificationStatus(bytes32 configHash) external view returns (uint8) {
        SimulationRecord storage record = simulations[configHash];
        if (record.verified) return 2;
        if (record.submitted) return 1;
        return 0;
    }

    /// @notice Prune stale intel pins that haven't been confirmed and are older than maxAgeSeconds
    function pruneStalePins(uint256 maxAgeSeconds) external onlyOwner {
        for (uint256 i = 0; i < intelPins.length; i++) {
            if (!intelPins[i].isActive) continue;
            if (confirmations[i] >= 2) continue;
            if (block.timestamp - intelPins[i].timestamp > maxAgeSeconds) {
                intelPins[i].isActive = false;
                emit IntelDeactivated(i, msg.sender);
            }
        }
    }
}
