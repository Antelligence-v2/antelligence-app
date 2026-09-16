"""Feature-flagged writer for ExperienceRegistry strategy submissions."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from typing import Any, Dict, Optional

from chain.config import get_base_sepolia_rpc_url, get_experience_registry_address, get_private_key
from chain.ipfs import pin_simulation

EXPERIENCE_REGISTRY_WRITER_ABI = [
    {
        "inputs": [
            {"internalType": "bytes32", "name": "runHash", "type": "bytes32"},
            {"internalType": "string", "name": "ipfsCid", "type": "string"},
            {"internalType": "bytes32", "name": "dataHash", "type": "bytes32"},
            {"internalType": "uint256", "name": "score", "type": "uint256"},
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
                "name": "strategyMeta",
                "type": "tuple",
            },
        ],
        "name": "submitExperience",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {"inputs": [{"internalType": "bytes32", "name": "runHash", "type": "bytes32"}], "name": "promoteStrategy", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
]


def env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _bytes32_hex(value: str) -> str:
    if value.startswith("0x") and len(value) == 66:
        return value
    stripped = value[2:] if value.startswith("0x") else value
    if len(stripped) == 64 and all(c in "0123456789abcdefABCDEF" for c in stripped):
        return "0x" + stripped.lower()
    return "0x" + hashlib.sha256(value.encode()).hexdigest()


def _tx_hex(tx_hash: Any) -> str:
    if isinstance(tx_hash, bytes):
        return "0x" + tx_hash.hex()
    if hasattr(tx_hash, "hex"):
        value = tx_hash.hex()
        return value if str(value).startswith("0x") else "0x" + str(value)
    value = str(tx_hash)
    return value if value.startswith("0x") else "0x" + value


class ChainStrategyWriter:
    """Transaction facade over ExperienceRegistry, off unless CHAIN_WRITE_ENABLED=true."""

    def __init__(
        self,
        contract: Any = None,
        w3: Any = None,
        rpc_url: Optional[str] = None,
        address: Optional[str] = None,
        enabled: Optional[bool] = None,
        transaction_options: Optional[dict] = None,
        use_cast: bool = False,
        cast_runner=None,
    ):
        self.enabled = env_truthy("CHAIN_WRITE_ENABLED") if enabled is None else enabled
        self.transaction_options = transaction_options or {}
        self.use_cast = use_cast
        self.cast_runner = cast_runner or self._run_cast_send
        self.contract = None if use_cast else (contract or self._build_contract(w3=w3, rpc_url=rpc_url, address=address))
        self.address = address or get_experience_registry_address()

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
            return w3.eth.contract(address=contract_address, abi=EXPERIENCE_REGISTRY_WRITER_ABI)
        except Exception:
            return None

    @staticmethod
    def _run_cast_send(args: list[str]) -> dict:
        result = subprocess.run(args, capture_output=True, text=True, timeout=90, check=True)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def _send_submit_with_cast(self, run_hash: str, ipfs_cid: str, data_hash: str, score: int, meta_tuple: tuple) -> str:
        rpc_url = get_base_sepolia_rpc_url()
        private_key = get_private_key()
        if not rpc_url:
            raise ValueError("BASE_SEPOLIA_RPC_URL is not configured")
        if not private_key:
            raise ValueError("PRIVATE_KEY is not configured")
        args = [
            "cast",
            "send",
            self.address,
            "submitExperience(bytes32,string,bytes32,uint256,(string,string,uint16,uint16,bytes32,string))",
            run_hash,
            ipfs_cid,
            data_hash,
            str(score),
            (
                f"({meta_tuple[0]},{meta_tuple[1]},{meta_tuple[2]},{meta_tuple[3]},{meta_tuple[4]},"
                f"\"{meta_tuple[5].replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34))}\")"
            ),
            "--rpc-url",
            rpc_url,
            "--private-key",
            private_key,
            "--json",
        ]
        return str(self.cast_runner(args).get("transactionHash", ""))

    def _send_promotion_with_cast(self, run_hash: str) -> str:
        rpc_url = get_base_sepolia_rpc_url()
        private_key = get_private_key()
        if not rpc_url:
            raise ValueError("BASE_SEPOLIA_RPC_URL is not configured")
        if not private_key:
            raise ValueError("PRIVATE_KEY is not configured")
        args = [
            "cast",
            "send",
            self.address,
            "promoteStrategy(bytes32)",
            _bytes32_hex(run_hash),
            "--rpc-url",
            rpc_url,
            "--private-key",
            private_key,
            "--json",
        ]
        return str(self.cast_runner(args).get("transactionHash", ""))

    def submit_experience(self, config: dict, metrics: dict, run_id: str, strategy_meta: dict) -> Optional[Dict]:
        if not self.enabled:
            return None
        try:
            pin_result = pin_simulation(config, metrics, run_id=run_id, backend="dry-run")
            artifact_hash = pin_result["artifact_hash"]
            run_hash = _bytes32_hex(run_id or artifact_hash)
            data_hash = _bytes32_hex(artifact_hash)
            ipfs_cid = pin_result.get("cid") or f"dryrun://{artifact_hash}"
            score = int(metrics.get("score", metrics.get("kill_rate", 0) * 100))
            if score <= 0:
                score = int(metrics.get("cells_killed", 0)) or 1

            worker_params = strategy_meta.get("worker_params", config.get("pheromone_params", {}))
            if not isinstance(worker_params, dict):
                raise ValueError("worker parameters must be a JSON object")
            worker_params_json = json.dumps(worker_params, sort_keys=True, separators=(",", ":"))
            meta_tuple = (
                str(strategy_meta.get("strategyType", strategy_meta.get("strategy_type", "pheromone-guided"))),
                str(strategy_meta.get("modelUsed", strategy_meta.get("model_used", config.get("selected_model", "heuristic")))),
                int(strategy_meta.get("nanobotCount", strategy_meta.get("nanobot_count", config.get("nanobot_count", config.get("n_nanobots", 0))))),
                int(strategy_meta.get("tumorRadius", strategy_meta.get("tumor_radius", config.get("tumor_radius", 0)))),
                _bytes32_hex(str(strategy_meta.get("datasetHash", strategy_meta.get("dataset_hash", artifact_hash)))),
                worker_params_json,
            )

            if self.use_cast or self.contract is None:
                tx_hash = self._send_submit_with_cast(run_hash, ipfs_cid, data_hash, score, meta_tuple)
            else:
                tx_hash = _tx_hex(self.contract.functions.submitExperience(
                    run_hash,
                    ipfs_cid,
                    data_hash,
                    score,
                    meta_tuple,
                ).transact(self.transaction_options))
            return {
                "ok": True,
                "run_hash": run_hash,
                "data_hash": data_hash,
                "ipfs_cid": ipfs_cid,
                "score": score,
                "tx_hash": tx_hash,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def request_promotion(self, run_hash: str) -> bool:
        if not self.enabled:
            return False
        try:
            if self.use_cast or self.contract is None:
                self._send_promotion_with_cast(run_hash)
            else:
                self.contract.functions.promoteStrategy(_bytes32_hex(run_hash)).transact(self.transaction_options)
            return True
        except Exception:
            return False
