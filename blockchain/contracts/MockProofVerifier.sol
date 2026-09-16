// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockProofVerifier {
    bool public shouldVerify = true;

    event VerificationModeUpdated(bool shouldVerify);

    function setShouldVerify(bool newValue) external {
        shouldVerify = newValue;
        emit VerificationModeUpdated(newValue);
    }

    function verifyProof(bytes calldata, bytes calldata proofBytes) external view returns (bool) {
        return shouldVerify && proofBytes.length > 0;
    }
}
