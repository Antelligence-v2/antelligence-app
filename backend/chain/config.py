"""Canonical chain configuration for Antelligence.

This module centralizes contract address and RPC resolution so submission,
leaderboard, runtime blockchain clients, and future proof tooling all read from
one source of truth.
"""

from __future__ import annotations

import os
from typing import Optional

BASE_SEPOLIA_CHAIN_ID = 84532
DEFAULT_TUMOR_INTEL_ADDRESS = "0x925b455175eF932a9a0239090a94E593224CD8AB"
DEFAULT_EXPERIENCE_REGISTRY_ADDRESS = "0x58A78E337ce3D948A39475f05Ca1A2c30274CADE"
DEFAULT_COLONY_MEMORY_ADDRESS = "0x914D72b9d49ED4Bb46FA553a01fEbbd5EEf481fA"
DEFAULT_FOOD_TOKEN_ADDRESS = "0x7310fb01b393459d2f8Ab15AD4a66F5380200869"


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def get_base_sepolia_rpc_url() -> str:
    return _first_env("BASE_SEPOLIA_RPC_URL", "BASE_SEPOLIA_RPC", "CHAIN_RPC") or ""


def get_private_key() -> str:
    return _first_env("PRIVATE_KEY", "ANTELLIGENCE_DEPLOYER_PRIVATE_KEY") or ""


def get_food_address() -> str:
    return _first_env("ANTELLIGENCE_FOOD_ADDR", "FOOD_ADDR") or DEFAULT_FOOD_TOKEN_ADDRESS


def get_memory_address() -> str:
    return _first_env("ANTELLIGENCE_MEMORY_ADDR", "MEMORY_ADDR") or DEFAULT_COLONY_MEMORY_ADDRESS


def get_experience_registry_address() -> str:
    return (
        _first_env("ANTELLIGENCE_REGISTRY_ADDR", "EXPERIENCE_REGISTRY_ADDR")
        or DEFAULT_EXPERIENCE_REGISTRY_ADDRESS
    )


def get_verifier_address() -> str:
    return _first_env("ANTELLIGENCE_VERIFIER_ADDR", "VERIFIER_ADDR") or ""


def get_tumor_intel_address() -> str:
    return (
        _first_env("ANTELLIGENCE_TUMOR_INTEL_ADDR", "TUMOR_INTEL_ADDR")
        or DEFAULT_TUMOR_INTEL_ADDRESS
    )


def resolve_rpc_url(prefer_local: bool = True) -> str:
    chain_rpc = _first_env("CHAIN_RPC")
    base_rpc = get_base_sepolia_rpc_url()
    if prefer_local and chain_rpc and chain_rpc != "http://127.0.0.1:8545":
        return chain_rpc
    return base_rpc


def validate_required_address(address: str, env_name: str) -> str:
    if not address:
        raise ValueError(f"{env_name} is not configured")
    if not address.startswith("0x") or len(address) != 42:
        raise ValueError(f"{env_name} must be a 20-byte hex address, got: {address}")
    return address


def get_canonical_chain_config() -> dict:
    return {
        "chain_id": BASE_SEPOLIA_CHAIN_ID,
        "rpc_url": get_base_sepolia_rpc_url(),
        "tumor_intel_address": get_tumor_intel_address(),
        "verifier_address": get_verifier_address(),
        "food_address": get_food_address(),
        "memory_address": get_memory_address(),
        "experience_registry_address": get_experience_registry_address(),
    }
