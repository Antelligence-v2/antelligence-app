"""Feature-flagged reader for ExperienceRegistry strategies and experiences."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from chain.config import get_base_sepolia_rpc_url, get_experience_registry_address

EXPERIENCE_REGISTRY_READER_ABI = [
    {
        "inputs": [{"internalType": "uint8", "name": "n", "type": "uint8"}],
        "name": "getTopStrategies",
        "outputs": [
            {
                "components": [
                    {"internalType": "bytes32", "name": "runHash", "type": "bytes32"},
                    {"internalType": "uint256", "name": "score", "type": "uint256"},
                    {"internalType": "uint256", "name": "promotedAt", "type": "uint256"},
                    {"internalType": "string", "name": "strategyType", "type": "string"},
                    {"internalType": "uint16", "name": "nanobotCount", "type": "uint16"},
                    {"internalType": "uint16", "name": "tumorRadius", "type": "uint16"},
                    {"internalType": "string", "name": "workerParamsJson", "type": "string"},
                ],
                "internalType": "struct ExperienceRegistry.PromotedStrategy[]",
                "name": "",
                "type": "tuple[]",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "bytes32", "name": "runHash", "type": "bytes32"}],
        "name": "getExperience",
        "outputs": [
            {
                "components": [
                    {"internalType": "bytes32", "name": "runHash", "type": "bytes32"},
                    {"internalType": "string", "name": "ipfsCid", "type": "string"},
                    {"internalType": "bytes32", "name": "dataHash", "type": "bytes32"},
                    {"internalType": "uint256", "name": "score", "type": "uint256"},
                    {"internalType": "address", "name": "submitter", "type": "address"},
                    {"internalType": "uint32", "name": "timestamp", "type": "uint32"},
                    {"internalType": "uint16", "name": "attestations", "type": "uint16"},
                    {"internalType": "bool", "name": "verified", "type": "bool"},
                ],
                "internalType": "struct ExperienceRegistry.Experience",
                "name": "",
                "type": "tuple",
            },
            {
                "components": [
                    {"internalType": "string", "name": "strategyType", "type": "string"},
                    {"internalType": "string", "name": "modelUsed", "type": "string"},
                    {"internalType": "uint16", "name": "nanobotCount", "type": "uint16"},
                    {"internalType": "uint16", "name": "tumorRadius", "type": "uint16"},
                    {"internalType": "bytes32", "name": "datasetHash", "type": "bytes32"},
                    {"internalType": "string", "name": "workerParamsJson", "type": "string"},
                ],
                "internalType": "struct ExperienceRegistry.StrategyMeta",
                "name": "",
                "type": "tuple",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {"inputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}], "name": "isPromoted", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"internalType": "string", "name": "strategyType", "type": "string"}], "name": "getExperiencesByStrategy", "outputs": [{"internalType": "bytes32[]", "name": "", "type": "bytes32[]"}], "stateMutability": "view", "type": "function"},
]


def env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _hex_bytes32(value: Any) -> str:
    if isinstance(value, bytes):
        return "0x" + value.hex()
    return str(value)


def _get(obj: Any, key: str, index: int, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return getattr(obj, key)
    except Exception:
        pass
    try:
        return obj[index]
    except Exception:
        return default


def _parse_worker_params(value: Any) -> Dict[str, float]:
    parsed = json.loads(value or "{}") if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError("worker parameters must be a JSON object")
    if not all(
        isinstance(key, str)
        and isinstance(item, (int, float))
        and not isinstance(item, bool)
        for key, item in parsed.items()
    ):
        raise ValueError("worker parameters must contain only numeric values")
    return {key: float(item) for key, item in parsed.items()}


@dataclass(frozen=True)
class StrategyData:
    run_hash: str
    score: int
    promoted_at: int
    strategy_type: str
    nanobot_count: int
    tumor_radius: int
    worker_params: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperienceData:
    run_hash: str
    ipfs_cid: str
    data_hash: str
    score: int
    submitter: str
    timestamp: int
    attestations: int
    verified: bool
    strategy_type: str
    model_used: str
    nanobot_count: int
    tumor_radius: int
    dataset_hash: str
    worker_params: Dict[str, float] = field(default_factory=dict)


class ChainExperienceConsumer:
    """Cached-free, graceful read facade over ExperienceRegistry."""

    def __init__(self, contract: Any = None, w3: Any = None, rpc_url: Optional[str] = None, address: Optional[str] = None, enabled: Optional[bool] = None):
        self.enabled = env_truthy("CHAIN_READ_ENABLED") if enabled is None else enabled
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
            contract_address = address or get_experience_registry_address()
            if not contract_address:
                return None
            return w3.eth.contract(address=contract_address, abi=EXPERIENCE_REGISTRY_READER_ABI)
        except Exception:
            return None

    def get_top_strategies(self, n: int = 5) -> List[StrategyData]:
        if not self.enabled or self.contract is None:
            return []
        try:
            raw = self.contract.functions.getTopStrategies(n).call()
            return [
                StrategyData(
                    run_hash=_hex_bytes32(_get(item, "runHash", 0, "")),
                    score=int(_get(item, "score", 1, 0)),
                    promoted_at=int(_get(item, "promotedAt", 2, 0)),
                    strategy_type=str(_get(item, "strategyType", 3, "")),
                    nanobot_count=int(_get(item, "nanobotCount", 4, 0)),
                    tumor_radius=int(_get(item, "tumorRadius", 5, 0)),
                    worker_params=_parse_worker_params(_get(item, "workerParamsJson", 6, "{}")),
                )
                for item in raw
            ]
        except Exception:
            return []

    def get_experience(self, run_hash: str) -> Optional[ExperienceData]:
        if not self.enabled or self.contract is None:
            return None
        try:
            experience, strategy = self.contract.functions.getExperience(run_hash).call()
            return ExperienceData(
                run_hash=_hex_bytes32(_get(experience, "runHash", 0, "")),
                ipfs_cid=str(_get(experience, "ipfsCid", 1, "")),
                data_hash=_hex_bytes32(_get(experience, "dataHash", 2, "")),
                score=int(_get(experience, "score", 3, 0)),
                submitter=str(_get(experience, "submitter", 4, "")),
                timestamp=int(_get(experience, "timestamp", 5, 0)),
                attestations=int(_get(experience, "attestations", 6, 0)),
                verified=bool(_get(experience, "verified", 7, False)),
                strategy_type=str(_get(strategy, "strategyType", 0, "")),
                model_used=str(_get(strategy, "modelUsed", 1, "")),
                nanobot_count=int(_get(strategy, "nanobotCount", 2, 0)),
                tumor_radius=int(_get(strategy, "tumorRadius", 3, 0)),
                dataset_hash=_hex_bytes32(_get(strategy, "datasetHash", 4, "")),
                worker_params=_parse_worker_params(_get(strategy, "workerParamsJson", 5, "{}")),
            )
        except Exception:
            return None

    def is_promoted(self, run_hash: str) -> bool:
        if not self.enabled or self.contract is None:
            return False
        try:
            return bool(self.contract.functions.isPromoted(run_hash).call())
        except Exception:
            return False

    def get_verified_experiences(self, strategy_type: Optional[str] = None) -> List[ExperienceData]:
        if not self.enabled or self.contract is None or not strategy_type:
            return []
        try:
            run_hashes = self.contract.functions.getExperiencesByStrategy(strategy_type).call()
            experiences = [self.get_experience(_hex_bytes32(run_hash)) for run_hash in run_hashes]
            return [experience for experience in experiences if experience and experience.verified]
        except Exception:
            return []
