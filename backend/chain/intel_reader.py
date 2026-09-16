"""Feature-flagged reader for TumorIntel on-chain intel pins."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from chain.config import get_base_sepolia_rpc_url, get_tumor_intel_address

PIN_TYPE_NAMES = {
    0: "HYPOXIC_CLUSTER",
    1: "STEM_CELL_DETECTED",
    2: "HIGH_RESISTANCE_AREA",
    3: "VESSEL_LOCATION",
    4: "SUCCESSFUL_KILL",
    5: "DRUG_OVERDOSE_ZONE",
    6: "TARGET_ACQUIRED",
    7: "DRUG_DELIVERY",
}

TUMOR_INTEL_READER_ABI = [
    {
        "inputs": [],
        "name": "getActivePinDetails",
        "outputs": [
            {"internalType": "uint256[]", "name": "ids", "type": "uint256[]"},
            {"internalType": "uint256[]", "name": "xs", "type": "uint256[]"},
            {"internalType": "uint256[]", "name": "ys", "type": "uint256[]"},
            {"internalType": "enum TumorIntel.PinType[]", "name": "types", "type": "uint8[]"},
            {"internalType": "address[]", "name": "reporters", "type": "address[]"},
            {"internalType": "uint256[]", "name": "priorities", "type": "uint256[]"},
            {"internalType": "uint256[]", "name": "pinConfirmations", "type": "uint256[]"},
            {"internalType": "uint256[]", "name": "timestamps", "type": "uint256[]"},
        ],
        "stateMutability": "view",
        "type": "function",
    }
]


def env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class IntelPinData:
    pin_id: int
    x: int
    y: int
    pin_type: str
    pin_type_code: int
    reporter: str
    priority: int
    confirmations: int
    timestamp: int
    is_active: bool = True

    def to_contract_pin_dict(self) -> dict:
        return {
            "pinId": self.pin_id,
            "x": self.x,
            "y": self.y,
            "pinType": self.pin_type,
            "pinTypeCode": self.pin_type_code,
            "reporter": self.reporter,
            "priority": self.priority,
            "confirmations": self.confirmations,
            "timestamp": self.timestamp,
            "isActive": self.is_active,
        }


class ChainIntelReader:
    """Cached, feature-flagged reader for TumorIntel.getActivePinDetails()."""

    def __init__(
        self,
        contract: Any = None,
        w3: Any = None,
        rpc_url: Optional[str] = None,
        address: Optional[str] = None,
        enabled: Optional[bool] = None,
        ttl_seconds: int = 60,
        now: Callable[[], float] = time.time,
    ):
        self.enabled = env_truthy("CHAIN_READ_ENABLED") if enabled is None else enabled
        self.ttl_seconds = ttl_seconds
        self.now = now
        self._cache: Optional[List[IntelPinData]] = None
        self._cache_at = 0.0
        self.contract = contract or self._build_contract(w3=w3, rpc_url=rpc_url, address=address)

    def _build_contract(self, w3: Any = None, rpc_url: Optional[str] = None, address: Optional[str] = None) -> Any:
        if not self.enabled:
            return None
        try:
            if w3 is None:
                from web3 import Web3

                rpc = rpc_url or get_base_sepolia_rpc_url()
                if not rpc:
                    return None
                w3 = Web3(Web3.HTTPProvider(rpc))
            contract_address = address or get_tumor_intel_address()
            if not contract_address:
                return None
            return w3.eth.contract(address=contract_address, abi=TUMOR_INTEL_READER_ABI)
        except Exception:
            return None

    def fetch_active_intel_pins(self, limit: Optional[int] = None) -> List[IntelPinData]:
        if not self.enabled or self.contract is None:
            return []

        now = self.now()
        if self._cache is not None and now - self._cache_at < self.ttl_seconds:
            return self._cache[:limit] if limit else self._cache

        try:
            raw = self.contract.functions.getActivePinDetails().call()
            ids, xs, ys, type_codes, reporters, priorities, confirmations, timestamps = raw
            pins = [
                IntelPinData(
                    pin_id=int(pin_id),
                    x=int(x),
                    y=int(y),
                    pin_type=PIN_TYPE_NAMES.get(int(pin_type_code), f"UNKNOWN_{int(pin_type_code)}"),
                    pin_type_code=int(pin_type_code),
                    reporter=str(reporter),
                    priority=int(priority),
                    confirmations=int(confirmation),
                    timestamp=int(timestamp_value),
                )
                for pin_id, x, y, pin_type_code, reporter, priority, confirmation, timestamp_value in zip(
                    ids, xs, ys, type_codes, reporters, priorities, confirmations, timestamps
                )
            ]
            self._cache = pins
            self._cache_at = now
            return pins[:limit] if limit else pins
        except Exception:
            return []

    def get_active_pins(self, limit: Optional[int] = 50) -> List[IntelPinData]:
        return self.fetch_active_intel_pins(limit=limit)
