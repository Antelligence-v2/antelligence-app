"""IPFS pinning utility for simulation artifacts.

Hashes simulation results (config, metrics, run data) and pins to IPFS.
Returns CID for on-chain attestation via ExperienceRegistry.

Supports multiple backends:
  - Pinata (free tier: 500 pins, 1GB)
  - Web3.storage (free tier: 5GB)
  - Local IPFS node (if running)

Usage:
    from chain.ipfs import pin_simulation
    cid = pin_simulation(config, metrics, artifacts_dir)
"""

import hashlib
import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple


def compute_artifact_hash(data: dict) -> str:
    """Compute deterministic SHA-256 hash of simulation artifacts.

    Uses canonical JSON serialization (sorted keys, no indent) for
    reproducible hashing regardless of dict insertion order.

    Args:
        data: Simulation data dict (config, metrics, etc.)

    Returns:
        Hex-encoded SHA-256 hash
    """
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def compute_config_hash(
    tumor_radius: int,
    nanobot_count: int,
    steps: int,
    oxygen_level: float,
    drug_dosage: float,
    seed: int,
) -> str:
    """Compute config hash matching the ZK program's commitment.

    This hash should match configHash in the SimulationProof struct.

    Args:
        tumor_radius: Tumor radius in µm
        nanobot_count: Number of nanobots
        steps: Simulation steps
        oxygen_level: Oxygen level in mmHg
        drug_dosage: Drug dosage in µg
        seed: Random seed

    Returns:
        Hex-encoded hash
    """
    config = {
        "tumor_radius": tumor_radius,
        "nanobot_count": nanobot_count,
        "steps": steps,
        "oxygen_level": oxygen_level,
        "drug_dosage": drug_dosage,
        "seed": seed,
    }
    return compute_artifact_hash(config)


def create_simulation_artifact(
    config: dict,
    metrics: dict,
    run_id: Optional[str] = None,
) -> dict:
    """Create a standardized simulation artifact for IPFS pinning.

    Args:
        config: Simulation configuration (tumor params, nanobot params, etc.)
        metrics: Simulation results (kill_rate, deliveries, runtime, etc.)
        run_id: Optional unique run identifier

    Returns:
        Artifact dict ready for pinning
    """
    artifact = {
        "version": "1.0",
        "type": "antelligence-simulation-v2",
        "run_id": run_id or compute_artifact_hash(config)[:16],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "metrics": metrics,
        "config_hash": compute_artifact_hash(config),
        "metrics_hash": compute_artifact_hash(metrics),
    }
    artifact["artifact_hash"] = compute_artifact_hash(artifact)
    return artifact


def pin_to_pinata(artifact: dict, api_key: str, secret_key: str) -> Tuple[Optional[str], Optional[str]]:
    """Pin artifact to Pinata IPFS service.

    Args:
        artifact: Simulation artifact dict
        api_key: Pinata API key
        secret_key: Pinata secret API key

    Returns:
        (cid, error) tuple
    """
    url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
    payload = json.dumps({
        "pinataContent": artifact,
        "pinataMetadata": {
            "name": f"antelligence-sim-{artifact.get('run_id', 'unknown')}",
        },
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "pinata_api_key": api_key,
            "pinata_secret_api_key": secret_key,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        return result.get("IpfsHash"), None
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return None, f"Pinata HTTP {e.code}: {body[:200]}"
    except Exception as e:
        return None, str(e)


def pin_to_local_ipfs(artifact: dict, api_url: str = "http://localhost:5001") -> Tuple[Optional[str], Optional[str]]:
    """Pin artifact to local IPFS node.

    Args:
        artifact: Simulation artifact dict
        api_url: Local IPFS API URL

    Returns:
        (cid, error) tuple
    """
    import urllib.parse
    url = f"{api_url}/api/v0/add"
    data = json.dumps(artifact).encode()

    # Multipart form data for IPFS API
    boundary = "----AntelligenceBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="simulation.json"\r\n'
        f"Content-Type: application/json\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        return result.get("Hash"), None
    except Exception as e:
        return None, str(e)


def pin_simulation(
    config: dict,
    metrics: dict,
    run_id: Optional[str] = None,
    backend: str = "auto",
) -> Dict:
    """Pin simulation artifacts to IPFS.

    Tries backends in order: Pinata (if keys set), local IPFS, dry-run.

    Args:
        config: Simulation config
        metrics: Simulation results
        run_id: Optional run ID
        backend: "pinata", "local", "auto", or "dry-run"

    Returns:
        Dict with cid, artifact_hash, backend used, errors
    """
    artifact = create_simulation_artifact(config, metrics, run_id)

    if backend == "dry-run":
        return {
            "ok": True,
            "cid": None,
            "artifact_hash": artifact["artifact_hash"],
            "config_hash": artifact["config_hash"],
            "backend": "dry-run",
            "artifact": artifact,
        }

    # Try Pinata
    if backend in ("pinata", "auto"):
        api_key = os.environ.get("PINATA_API_KEY", "")
        secret_key = os.environ.get("PINATA_SECRET_KEY", "")
        if api_key and secret_key:
            cid, err = pin_to_pinata(artifact, api_key, secret_key)
            if cid:
                return {
                    "ok": True,
                    "cid": cid,
                    "artifact_hash": artifact["artifact_hash"],
                    "config_hash": artifact["config_hash"],
                    "backend": "pinata",
                    "gateway_url": f"https://gateway.pinata.cloud/ipfs/{cid}",
                }

    # Try local IPFS
    if backend in ("local", "auto"):
        cid, err = pin_to_local_ipfs(artifact)
        if cid:
            return {
                "ok": True,
                "cid": cid,
                "artifact_hash": artifact["artifact_hash"],
                "config_hash": artifact["config_hash"],
                "backend": "local",
                "gateway_url": f"https://ipfs.io/ipfs/{cid}",
            }

    # Fallback: return artifact hash without pinning
    return {
        "ok": False,
        "cid": None,
        "artifact_hash": artifact["artifact_hash"],
        "config_hash": artifact["config_hash"],
        "backend": "none",
        "error": "No IPFS backend available. Set PINATA_API_KEY/PINATA_SECRET_KEY or run local IPFS node.",
        "artifact": artifact,
    }
