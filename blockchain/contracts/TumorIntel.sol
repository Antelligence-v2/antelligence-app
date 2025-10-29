// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title TumorIntel
 * @dev Smart contract for nanobots to share intelligence on the tumor battlefield.
 * Enables decentralized, verifiable communication between autonomous agents.
 */
contract TumorIntel {
    enum PinType { 
        HYPOXIC_CLUSTER,      // Area with low oxygen - high priority target
        STEM_CELL_DETECTED,   // Cancer stem cell found - requires special attention
        HIGH_RESISTANCE_AREA, // Area where drug resistance is high
        VESSEL_LOCATION,      // Blood vessel for reloading detected
        SUCCESSFUL_KILL,      // Cell successfully eliminated
        DRUG_OVERDOSE_ZONE,   // Area with too much drug concentration
        TARGET_ACQUIRED,      // Nanobot has acquired a tumor cell target
        DRUG_DELIVERY         // Drug delivered to target location
    }

    struct IntelPin {
        uint x;               // X coordinate in micrometers
        uint y;               // Y coordinate in micrometers
        PinType pinType;      // Type of intelligence
        address reporter;     // Nanobot that reported this
        uint timestamp;       // When this was reported
        uint priority;        // Priority level (1-10)
        bool isActive;        // Whether this intel is still relevant
    }

    IntelPin[] public intelPins;
    
    // Mapping from pin ID to confirmation count (how many nanobots confirmed this)
    mapping(uint => uint) public confirmations;
    
    // Mapping to track which nanobot confirmed which pin
    mapping(uint => mapping(address => bool)) public hasConfirmed;

    event IntelReported(
        uint indexed pinId,
        uint x,
        uint y,
        PinType pinType,
        address reporter,
        uint priority
    );

    event IntelConfirmed(
        uint indexed pinId,
        address confirmer,
        uint totalConfirmations
    );

    event IntelDeactivated(
        uint indexed pinId,
        address deactivator
    );

    /**
     * @dev Report new intelligence to the battlefield
     * @param x X coordinate in micrometers
     * @param y Y coordinate in micrometers
     * @param pinType Type of intelligence being reported
     * @param priority Priority level (1-10, 10 being highest)
     */
    function reportIntel(uint x, uint y, PinType pinType, uint priority) public returns (uint) {
        require(priority >= 1 && priority <= 10, "Priority must be between 1 and 10");
        
        uint pinId = intelPins.length;
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

    /**
     * @dev Confirm an existing intel report (increases its reliability)
     * @param pinId ID of the intel pin to confirm
     */
    function confirmIntel(uint pinId) public {
        require(pinId < intelPins.length, "Pin does not exist");
        require(intelPins[pinId].isActive, "Pin is no longer active");
        require(!hasConfirmed[pinId][msg.sender], "Already confirmed this intel");
        
        hasConfirmed[pinId][msg.sender] = true;
        confirmations[pinId]++;
        
        emit IntelConfirmed(pinId, msg.sender, confirmations[pinId]);
    }

    /**
     * @dev Deactivate an intel pin (e.g., target has been eliminated)
     * @param pinId ID of the intel pin to deactivate
     */
    function deactivateIntel(uint pinId) public {
        require(pinId < intelPins.length, "Pin does not exist");
        require(intelPins[pinId].isActive, "Pin is already inactive");
        
        intelPins[pinId].isActive = false;
        emit IntelDeactivated(pinId, msg.sender);
    }

    /**
     * @dev Get the total number of intel pins
     */
    function getIntelCount() public view returns (uint) {
        return intelPins.length;
    }

    /**
     * @dev Get active intel pins of a specific type
     * @param pinType Type of intel to filter by
     * @return Array of pin IDs matching the criteria
     */
    function getActiveIntelByType(PinType pinType) public view returns (uint[] memory) {
        uint count = 0;
        
        // First pass: count matching pins
        for (uint i = 0; i < intelPins.length; i++) {
            if (intelPins[i].isActive && intelPins[i].pinType == pinType) {
                count++;
            }
        }
        
        // Second pass: collect matching pin IDs
        uint[] memory result = new uint[](count);
        uint index = 0;
        for (uint i = 0; i < intelPins.length; i++) {
            if (intelPins[i].isActive && intelPins[i].pinType == pinType) {
                result[index] = i;
                index++;
            }
        }
        
        return result;
    }

    /**
     * @dev Get all active intel pins
     * @return Array of pin IDs that are currently active
     */
    function getActiveIntel() public view returns (uint[] memory) {
        uint count = 0;
        
        // First pass: count active pins
        for (uint i = 0; i < intelPins.length; i++) {
            if (intelPins[i].isActive) {
                count++;
            }
        }
        
        // Second pass: collect active pin IDs
        uint[] memory result = new uint[](count);
        uint index = 0;
        for (uint i = 0; i < intelPins.length; i++) {
            if (intelPins[i].isActive) {
                result[index] = i;
                index++;
            }
        }
        
        return result;
    }

    /**
     * @dev Get detailed information about a specific pin
     * @param pinId ID of the pin to query
     */
    function getIntelDetails(uint pinId) public view returns (
        uint x,
        uint y,
        PinType pinType,
        address reporter,
        uint timestamp,
        uint priority,
        bool isActive,
        uint confirmationCount
    ) {
        require(pinId < intelPins.length, "Pin does not exist");
        
        IntelPin memory pin = intelPins[pinId];
        return (
            pin.x,
            pin.y,
            pin.pinType,
            pin.reporter,
            pin.timestamp,
            pin.priority,
            pin.isActive,
            confirmations[pinId]
        );
    }
}

