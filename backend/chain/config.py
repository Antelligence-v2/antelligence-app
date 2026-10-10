"""Canonical chain configuration for Antelligence.

One source of truth for which chain the backend talks to and where the contracts
live, so submission, verification, the leaderboard and runtime clients agree.

* The network is selected by ``ANTELLIGENCE_CHAIN`` (default: ``zksync-era-sepolia``).
* Contract addresses come from that network's deployments file,
  ``blockchain/deployments/<network>.json``, written by the deploy script with tx
  hashes, block numbers, deployer and git commit. No addresses are hard-coded here.
  If the file does not exist the network has no deployment and addresses are ``""``.
* Explicit per-contract env overrides (``ANTELLIGENCE_TUMOR_INTEL_ADDR`` etc.) still
  win, for local experiments.
* RPC: ``ANTELLIGENCE_RPC_URL``, then the network's own env var (e.g.
  ``ZKSYNC_SEPOLIA_RPC_URL``), then legacy ``CHAIN_RPC`` (ignored when it is the old
  local-Hardhat default ``http://127.0.0.1:8545``), then the network's public RPC, but only
  when the network was selected explicitly via ``ANTELLIGENCE_CHAIN``. With no explicit
  selection and no RPC configured, chain access stays off (offline by default).
  Signing paths call ``assert_rpc_matches_network`` so a mismatched RPC fails loudly.

History: earlier Base Sepolia deployments (TumorIntel ``0xd1cf…238b``, later
``0x925b…D8AB``) are recorded in ``docs/status/2026-10-08-truth-pass.md``; they have
no deployments file, so nothing resolves to them any more.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_NETWORK = "zksync-era-sepolia"
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Network:
    name: str
    chain_id: int
    public_rpc_url: str
    rpc_env: str
    explorer_url: str
    is_testnet: bool = True


NETWORKS: Dict[str, Network] = {
    "zksync-era-sepolia": Network(
        name="zksync-era-sepolia", chain_id=300, public_rpc_url="https://sepolia.era.zksync.dev",
        rpc_env="ZKSYNC_SEPOLIA_RPC_URL", explorer_url="https://sepolia.explorer.zksync.io",
    ),
    "zksync-local-inmemory": Network(
        name="zksync-local-inmemory", chain_id=260, public_rpc_url="http://127.0.0.1:8011",
        rpc_env="ZKSYNC_LOCAL_RPC_URL", explorer_url="",
    ),
    "base-sepolia": Network(
        name="base-sepolia", chain_id=84532, public_rpc_url="https://sepolia.base.org",
        rpc_env="BASE_SEPOLIA_RPC_URL", explorer_url="https://sepolia.basescan.org",
    ),
}

CONTRACT_ENV = {
    "TumorIntel": ("ANTELLIGENCE_TUMOR_INTEL_ADDR", "TUMOR_INTEL_ADDR"),
    "ExperienceRegistry": ("ANTELLIGENCE_REGISTRY_ADDR", "EXPERIENCE_REGISTRY_ADDR"),
    "ColonyMemory": ("ANTELLIGENCE_MEMORY_ADDR", "MEMORY_ADDR"),
    "FoodToken": ("ANTELLIGENCE_FOOD_ADDR", "FOOD_ADDR"),
}


class ChainConfigError(ValueError):
    """The selected network or its deployments file is invalid."""


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def get_network() -> Network:
    name = _first_env("ANTELLIGENCE_CHAIN") or DEFAULT_NETWORK
    try:
        return NETWORKS[name]
    except KeyError:
        raise ChainConfigError(f"unknown ANTELLIGENCE_CHAIN {name!r}; known: {sorted(NETWORKS)}") from None


def get_chain_id() -> int:
    return get_network().chain_id


def deployments_dir() -> Path:
    override = _first_env("ANTELLIGENCE_DEPLOYMENTS_DIR")
    return Path(override) if override else REPO_ROOT / "blockchain" / "deployments"


def deployments_path(network: Optional[Network] = None) -> Path:
    return deployments_dir() / f"{(network or get_network()).name}.json"


def load_deployment(network: Optional[Network] = None) -> Optional[Dict[str, Any]]:
    """Return the network's deployments record, or None if it has never been deployed."""
    network = network or get_network()
    path = deployments_path(network)
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("chain_id") != network.chain_id:
        raise ChainConfigError(
            f"{path.name} records chain_id {record.get('chain_id')}, expected {network.chain_id} for {network.name}"
        )
    for contract in record.get("contracts", []):
        validate_required_address(contract.get("address", ""), f"{path.name}:{contract.get('name')}")
    return record


# The unprefixed names (TUMOR_INTEL_ADDR, FOOD_ADDR, ...) are what every pre-ZKsync .env holds,
# and they hold Base Sepolia addresses. They only mean something on that network.
LEGACY_ADDRESS_NETWORK = "base-sepolia"


def get_contract_address(name: str) -> str:
    """Address of ``name`` on the selected network.

    ``ANTELLIGENCE_*_ADDR`` overrides always win (local experiments). Legacy unprefixed
    overrides are honoured only on Base Sepolia, where they came from; elsewhere a stale
    ``.env`` would otherwise silently point a ZKsync backend at Base Sepolia addresses.
    Otherwise the deployments file decides.
    """
    prefixed, legacy = CONTRACT_ENV.get(name, (None, None))
    override = _first_env(prefixed) if prefixed else None
    if not override and legacy and get_network().name == LEGACY_ADDRESS_NETWORK:
        override = _first_env(legacy)
    if override:
        return override
    record = load_deployment()
    if record is None:
        return ""
    for contract in record.get("contracts", []):
        if contract.get("name") == name:
            return contract["address"]
    return ""


# The value env.example.txt, docker-compose-ecr.yml, setup-ec2.sh and deploy-new-ip.sh have
# always put in CHAIN_RPC: the old local Hardhat node. It never pointed at a ZKsync network, and
# the pre-ZKsync resolver ignored it for the same reason, so it must not outrank a real RPC.
LEGACY_LOCAL_CHAIN_RPC = {"http://127.0.0.1:8545", "http://localhost:8545"}


def get_rpc_url() -> str:
    """RPC for the selected network.

    Order: ``ANTELLIGENCE_RPC_URL``; the network's own variable (e.g. ``ZKSYNC_SEPOLIA_RPC_URL``);
    legacy ``CHAIN_RPC`` unless it is the old local-Hardhat default; then the network's public
    RPC, but only when ``ANTELLIGENCE_CHAIN`` was set explicitly (offline by default). Whatever
    is returned, :func:`assert_rpc_matches_network` refuses to sign if it serves another chain.
    """
    network = get_network()
    explicit = _first_env("ANTELLIGENCE_RPC_URL", network.rpc_env)
    if explicit:
        return explicit
    legacy = _first_env("CHAIN_RPC")
    if legacy and legacy.rstrip("/") not in LEGACY_LOCAL_CHAIN_RPC:
        return legacy
    if _first_env("ANTELLIGENCE_CHAIN"):
        return network.public_rpc_url
    return ""


def assert_rpc_matches_network(w3) -> int:
    """Refuse to act unless the connected RPC serves the selected network, and that network is a testnet.

    The deployments file, explorer URLs and recorded ``chain_id`` all come from
    ``ANTELLIGENCE_CHAIN``; the RPC comes from environment variables. If the two disagree, a
    signed transaction would land on a chain the records do not describe (or, with a mainnet
    RPC, spend real funds). Returns the verified chain id.
    """
    network = get_network()
    actual = int(w3.eth.chain_id)
    if actual != network.chain_id:
        raise ChainConfigError(
            f"RPC serves chain {actual}, but ANTELLIGENCE_CHAIN selects {network.name} (chain {network.chain_id}); "
            "refusing to continue. Fix ANTELLIGENCE_RPC_URL / CHAIN_RPC / "
            f"{network.rpc_env}."
        )
    if not network.is_testnet:
        raise ChainConfigError(f"{network.name} is not a testnet; this backend only signs on testnets")
    return actual


def get_private_key() -> str:
    return _first_env("PRIVATE_KEY", "ANTELLIGENCE_DEPLOYER_PRIVATE_KEY") or ""


def get_food_address() -> str:
    return get_contract_address("FoodToken")


def get_memory_address() -> str:
    return get_contract_address("ColonyMemory")


def get_experience_registry_address() -> str:
    return get_contract_address("ExperienceRegistry")


def get_verifier_address() -> str:
    return _first_env("ANTELLIGENCE_VERIFIER_ADDR", "VERIFIER_ADDR") or ""


def get_tumor_intel_address() -> str:
    return get_contract_address("TumorIntel")


def explorer_tx_url(tx_hash: str) -> str:
    base = get_network().explorer_url
    return f"{base}/tx/{tx_hash}" if base and tx_hash else ""


def explorer_address_url(address: str) -> str:
    base = get_network().explorer_url
    return f"{base}/address/{address}" if base and address else ""


def validate_required_address(address: str, env_name: str) -> str:
    if not address:
        raise ValueError(f"{env_name} is not configured")
    if not address.startswith("0x") or len(address) != 42:
        raise ValueError(f"{env_name} must be a 20-byte hex address, got: {address}")
    return address


def get_canonical_chain_config() -> dict:
    network = get_network()
    return {
        "network": network.name,
        "chain_id": network.chain_id,
        "rpc_url": get_rpc_url(),
        "explorer_url": network.explorer_url,
        "deployments_file": str(deployments_path(network).relative_to(REPO_ROOT))
        if deployments_path(network).is_relative_to(REPO_ROOT) else str(deployments_path(network)),
        "deployed": load_deployment(network) is not None,
        "tumor_intel_address": get_tumor_intel_address(),
        "verifier_address": get_verifier_address(),
        "food_address": get_food_address(),
        "memory_address": get_memory_address(),
        "experience_registry_address": get_experience_registry_address(),
    }
