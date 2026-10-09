"""Read TumorIntel simulation records and decide whether a set of public values was proven.

``TumorIntel`` keys simulation records by ``configHash`` and ``isVerified(configHash)`` only
says that *some* proof was accepted for that hash. It does not say the proof covered the
values a caller is looking at: ``submitSimulation`` is permissionless and (in the deployed
contract) overwrites an existing record's values without clearing ``verified``.

What a verifier cannot have accepted for anything else is ``publicValuesHash``, which
``verifySimulation`` sets to ``keccak256(publicValues)`` and ``submitSimulation`` never
touches. So a set of public values is proven on-chain only when the record is verified
**and** its ``publicValuesHash`` equals ``keccak256(abi.encode(configHash, killRateBps,
nanobotCount, tumorRadius, steps))`` for exactly those values. Every trust decision in the
backend goes through :func:`proves`.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from eth_abi import encode
from eth_utils import keccak

PUBLIC_VALUES_TYPES = ["bytes32", "uint32", "uint32", "uint32", "uint32"]

# Auto-generated getter for ``mapping(bytes32 => SimulationRecord) public simulations``.
# Present in every TumorIntel deployment, including the ones that predate getSimulation().
SIMULATIONS_GETTER_ABI = [{
    "type": "function", "name": "simulations", "stateMutability": "view",
    "inputs": [{"name": "", "type": "bytes32"}],
    "outputs": [
        {"name": "configHash", "type": "bytes32"}, {"name": "killRateBps", "type": "uint32"},
        {"name": "nanobotCount", "type": "uint32"}, {"name": "tumorRadius", "type": "uint32"},
        {"name": "steps", "type": "uint32"}, {"name": "submitter", "type": "address"},
        {"name": "submittedAt", "type": "uint64"}, {"name": "verifiedAt", "type": "uint64"},
        {"name": "submitted", "type": "bool"}, {"name": "verified", "type": "bool"},
        {"name": "publicValuesHash", "type": "bytes32"},
    ],
}]

_ZERO32 = "0x" + "00" * 32


def bytes32(value: Any) -> bytes:
    """Accept 0x-prefixed or bare hex (or raw bytes) and return exactly 32 bytes."""
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    else:
        text = str(value)
        raw = bytes.fromhex(text[2:] if text.startswith("0x") else text)
    if len(raw) != 32:
        raise ValueError(f"expected 32 bytes, got {len(raw)}")
    return raw


def hex32(value: Any) -> str:
    return "0x" + bytes32(value).hex()


def public_values_hash(config_hash: Any, kill_rate_bps: int, nanobot_count: int, tumor_radius: int,
                       steps: int) -> str:
    """keccak256(abi.encode(...)) of the five public values, as TumorIntel stores it after a proof."""
    encoded = encode(PUBLIC_VALUES_TYPES, [bytes32(config_hash), int(kill_rate_bps), int(nanobot_count),
                                           int(tumor_radius), int(steps)])
    return "0x" + keccak(encoded).hex()


def public_values_hash_from_encoded(public_values: str) -> str:
    """keccak256 of already ABI-encoded public values (``onchain.public_values`` in a bundle)."""
    text = public_values[2:] if public_values.startswith("0x") else public_values
    return "0x" + keccak(bytes.fromhex(text)).hex()


def read_simulation_record(w3, contract: str, config_hash: Any) -> Dict[str, Any]:
    """Return TumorIntel's stored record for ``config_hash`` (all-zero fields if none exists)."""
    from web3 import Web3

    reader = w3.eth.contract(address=Web3.to_checksum_address(contract), abi=SIMULATIONS_GETTER_ABI)
    (cfg, kill_rate_bps, nanobot_count, tumor_radius, steps, submitter, submitted_at, verified_at,
     submitted, verified, pv_hash) = reader.functions.simulations(bytes32(config_hash)).call()
    return {
        "config_hash": hex32(cfg), "kill_rate_bps": int(kill_rate_bps), "nanobot_count": int(nanobot_count),
        "tumor_radius": int(tumor_radius), "steps": int(steps), "submitter": str(submitter),
        "submitted_at": int(submitted_at), "verified_at": int(verified_at), "submitted": bool(submitted),
        "verified": bool(verified), "public_values_hash": hex32(pv_hash),
    }


def proves(record: Optional[Dict[str, Any]], expected_public_values_hash: Optional[str]) -> bool:
    """True only if the record is verified and its proven public values are exactly the expected ones."""
    if not record or not record.get("verified") or not expected_public_values_hash:
        return False
    stored = str(record.get("public_values_hash") or "").lower()
    return stored not in ("", _ZERO32) and stored == expected_public_values_hash.lower()
