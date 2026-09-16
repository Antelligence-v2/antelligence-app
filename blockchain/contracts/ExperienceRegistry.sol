// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Experience Registry for continual learning and knowledge sharing.
///         Stores simulation run metadata, IPFS pointers, and quality attestations.
///         Enables agents to learn from previous successful strategies.
contract ExperienceRegistry {
    /// @notice Simulation experience record
    struct Experience {
        bytes32 runHash;        // Unique hash of simulation parameters
        string ipfsCid;         // IPFS content ID with full simulation data
        bytes32 dataHash;       // Hash of simulation results for integrity
        uint256 score;          // Performance score (cells killed, efficiency, etc.)
        address submitter;      // Address that submitted the experience
        uint32 timestamp;       // Block timestamp
        uint16 attestations;    // Number of quality attestations received
        bool verified;          // Whether experience has been verified
    }
    
    /// @notice Strategy metadata for categorizing experiences
    struct StrategyMeta {
        string strategyType;    // e.g., "pheromone-guided", "LLM-queen", "hybrid"
        string modelUsed;       // LLM model identifier
        uint16 nanobotCount;    // Number of nanobots
        uint16 tumorRadius;     // Tumor size parameter
        bytes32 datasetHash;    // Hash of tumor geometry (BraTS subject)
        string workerParamsJson; // Canonical JSON parameters the Queen may adopt
    }
    
    /// @notice Attestation from a validator
    struct Attestation {
        address validator;
        uint32 timestamp;
        uint8 quality;          // Quality score 0-100
        string notes;           // Optional notes
    }
    
    // Events
    event ExperienceSubmitted(
        bytes32 indexed runHash,
        string ipfsCid,
        bytes32 dataHash,
        uint256 score,
        address indexed submitter
    );
    
    event ExperienceAttested(
        bytes32 indexed runHash,
        address indexed validator,
        uint8 quality
    );
    
    event ExperienceVerified(
        bytes32 indexed runHash,
        address indexed verifier
    );
    
    // Storage
    mapping(bytes32 => Experience) public experiences;
    mapping(bytes32 => StrategyMeta) public strategies;
    mapping(bytes32 => Attestation[]) public attestations;
    mapping(address => bool) public authorizedValidators;
    
    // Owner for managing validators
    address public owner;
    
    // Minimum attestations required for verification
    uint8 public minAttestations = 2;
    
    constructor() {
        owner = msg.sender;
        authorizedValidators[msg.sender] = true;
    }
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }
    
    modifier onlyValidator() {
        require(authorizedValidators[msg.sender], "Not authorized validator");
        _;
    }
    
    /// @notice Submit a new simulation experience
    function submitExperience(
        bytes32 runHash,
        string calldata ipfsCid,
        bytes32 dataHash,
        uint256 score,
        StrategyMeta calldata strategyMeta
    ) external {
        require(experiences[runHash].runHash == bytes32(0), "Experience already exists");
        require(score > 0, "Score must be positive");
        require(bytes(ipfsCid).length > 0, "IPFS CID required");
        
        experiences[runHash] = Experience({
            runHash: runHash,
            ipfsCid: ipfsCid,
            dataHash: dataHash,
            score: score,
            submitter: msg.sender,
            timestamp: uint32(block.timestamp),
            attestations: 0,
            verified: false
        });
        
        strategies[runHash] = strategyMeta;
        
        emit ExperienceSubmitted(runHash, ipfsCid, dataHash, score, msg.sender);
    }
    
    /// @notice Attest to the quality of an experience
    function attestExperience(
        bytes32 runHash,
        uint8 quality,
        string calldata notes
    ) external onlyValidator {
        require(experiences[runHash].runHash != bytes32(0), "Experience not found");
        require(quality <= 100, "Quality must be <= 100");
        require(!hasConfirmed(runHash, msg.sender), "Already attested");
        
        Attestation memory attestation = Attestation({
            validator: msg.sender,
            timestamp: uint32(block.timestamp),
            quality: quality,
            notes: notes
        });
        
        attestations[runHash].push(attestation);
        experiences[runHash].attestations++;
        
        emit ExperienceAttested(runHash, msg.sender, quality);
        
        // Auto-verify if enough attestations
        if (experiences[runHash].attestations >= minAttestations) {
            _verifyExperience(runHash);
        }
    }
    
    /// @notice Verify an experience (can be called manually if conditions met)
    function verifyExperience(bytes32 runHash) external onlyValidator {
        require(experiences[runHash].runHash != bytes32(0), "Experience not found");
        require(!experiences[runHash].verified, "Already verified");
        require(experiences[runHash].attestations >= minAttestations, "Insufficient attestations");
        
        _verifyExperience(runHash);
    }
    
    /// @notice Internal verification logic
    function _verifyExperience(bytes32 runHash) internal {
        experiences[runHash].verified = true;
        emit ExperienceVerified(runHash, msg.sender);
    }
    
    /// @notice Check if validator has already attested
    function hasConfirmed(bytes32 runHash, address validator) public view returns (bool) {
        Attestation[] storage atts = attestations[runHash];
        for (uint i = 0; i < atts.length; i++) {
            if (atts[i].validator == validator) {
                return true;
            }
        }
        return false;
    }
    
    /// @notice Get average quality score for an experience
    function getAverageQuality(bytes32 runHash) public view returns (uint8) {
        Attestation[] storage atts = attestations[runHash];
        if (atts.length == 0) return 0;
        
        uint256 total = 0;
        for (uint i = 0; i < atts.length; i++) {
            total += atts[i].quality;
        }
        return uint8(total / atts.length);
    }
    
    /// @notice Get all attestations for an experience
    function getAttestations(bytes32 runHash) external view returns (Attestation[] memory) {
        return attestations[runHash];
    }
    
    /// @notice Add a new validator
    function addValidator(address validator) external onlyOwner {
        authorizedValidators[validator] = true;
    }
    
    /// @notice Remove a validator
    function removeValidator(address validator) external onlyOwner {
        authorizedValidators[validator] = false;
    }
    
    /// @notice Update minimum attestations required
    function setMinAttestations(uint8 newMin) external onlyOwner {
        require(newMin > 0, "Minimum must be positive");
        minAttestations = newMin;
    }
    
    /// @notice Get experience details
    function getExperience(bytes32 runHash) external view returns (Experience memory, StrategyMeta memory) {
        return (experiences[runHash], strategies[runHash]);
    }

    // ======================================================================
    // STRATEGY PROMOTION — makes the blockchain a knowledge-sharing layer
    // ======================================================================

    /// @notice A promoted strategy that the swarm can adopt in future runs
    struct PromotedStrategy {
        bytes32 runHash;
        uint256 score;
        uint256 promotedAt;
        string strategyType;
        uint16 nanobotCount;
        uint16 tumorRadius;
        string workerParamsJson;
    }

    PromotedStrategy[] public promotedStrategies;
    mapping(bytes32 => bool) public isPromoted;
    mapping(bytes32 => uint256) public promotedIndex;

    event StrategyPromoted(bytes32 indexed runHash, uint256 score, address indexed promoter);

    /// @notice Promote a verified experience as a strategy for future runs to adopt.
    ///         This is the core of the self-improving loop: high-score verified
    ///         experiences become promoted strategies that the Queen reads on
    ///         the next run's init.
    function promoteStrategy(bytes32 runHash) external onlyValidator {
        require(experiences[runHash].runHash != bytes32(0), "Experience not found");
        require(experiences[runHash].verified, "Not verified");
        require(!isPromoted[runHash], "Already promoted");

        isPromoted[runHash] = true;
        promotedIndex[runHash] = promotedStrategies.length;
        promotedStrategies.push(PromotedStrategy({
            runHash: runHash,
            score: experiences[runHash].score,
            promotedAt: uint256(block.timestamp),
            strategyType: strategies[runHash].strategyType,
            nanobotCount: strategies[runHash].nanobotCount,
            tumorRadius: strategies[runHash].tumorRadius,
            workerParamsJson: strategies[runHash].workerParamsJson
        }));

        emit StrategyPromoted(runHash, experiences[runHash].score, msg.sender);
    }

    /// @notice Get the top-N promoted strategies sorted by score descending.
    ///         The Queen calls this at run init to select the best strategy.
    function getTopStrategies(uint8 n) external view returns (PromotedStrategy[] memory) {
        uint256 count = promotedStrategies.length;
        if (count == 0) return new PromotedStrategy[](0);
        uint256 resultCount = count < n ? count : n;

        // Copy to memory for sorting
        PromotedStrategy[] memory sorted = new PromotedStrategy[](count);
        for (uint256 i = 0; i < count; i++) {
            sorted[i] = promotedStrategies[i];
        }

        // Insertion sort by score descending
        for (uint256 i = 1; i < count; i++) {
            PromotedStrategy memory key = sorted[i];
            int256 j = int256(i) - 1;
            while (j >= 0 && sorted[uint256(j)].score < key.score) {
                sorted[uint256(j + 1)] = sorted[uint256(j)];
                j--;
            }
            sorted[uint256(j + 1)] = key;
        }

        // Return top n
        PromotedStrategy[] memory result = new PromotedStrategy[](resultCount);
        for (uint256 i = 0; i < resultCount; i++) {
            result[i] = sorted[i];
        }
        return result;
    }

    /// @notice Get promoted strategy count
    function getPromotedCount() external view returns (uint256) {
        return promotedStrategies.length;
    }

    /// @notice Get experiences filtered by strategy type
    function getExperiencesByStrategy(string calldata strategyType) external view returns (bytes32[] memory) {
        uint256 count = 0;
        for (uint256 i = 0; i < promotedStrategies.length; i++) {
            if (keccak256(bytes(promotedStrategies[i].strategyType)) == keccak256(bytes(strategyType))) {
                count++;
            }
        }

        bytes32[] memory result = new bytes32[](count);
        uint256 index = 0;
        for (uint256 i = 0; i < promotedStrategies.length; i++) {
            if (keccak256(bytes(promotedStrategies[i].strategyType)) == keccak256(bytes(strategyType))) {
                result[index] = promotedStrategies[i].runHash;
                index++;
            }
        }
        return result;
    }
}