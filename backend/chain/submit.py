"""Submission CLI for posting simulation attestations on-chain.

Posts simulation results (config hash, kill rate, metrics) to the
ExperienceRegistry contract on Base Sepolia via the deployed TumorIntel.

Usage:
    python3 -m chain.submit --config config.json --metrics metrics.json
    python3 -m chain.submit --dry-run --config config.json

Requires: web3.py or cast CLI for transaction submission.
Falls back to cast CLI if web3 not installed.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from chain.config import BASE_SEPOLIA_CHAIN_ID, get_tumor_intel_address
from chain.ipfs import pin_simulation, compute_artifact_hash
from chain.proof_lifecycle import build_lifecycle, build_verification_status
from chain.proof_spec import (
    PUBLIC_VALUES_SCHEMA_VERSION,
    PROGRAM_VERSION,
    build_public_values_metadata,
    build_public_values_payload,
    encode_public_values_payload,
    normalize_config_hash,
)


TUMOR_INTEL_ADDRESS = get_tumor_intel_address()


def encode_public_values(
    config_hash: str,
    kill_rate_bps: int,
    nanobot_count: int,
    tumor_radius: int,
    steps: int,
) -> str:
    """ABI-encode verifier public values for TumorIntel.verifySimulation.

    Use the canonical Python encoder so local bundle creation, tests, and future
    prover integration do not depend on Foundry being installed.
    """
    payload = build_public_values_payload(
        config_hash=config_hash,
        kill_rate_bps=kill_rate_bps,
        nanobot_count=nanobot_count,
        tumor_radius=tumor_radius,
        steps=steps,
    )
    return encode_public_values_payload(payload)


def submit_via_cast(
    config_hash: str,
    kill_rate: int,
    nanobot_count: int,
    tumor_radius: int,
    steps: int,
    rpc_url: str,
    private_key: str,
    dry_run: bool = True,
) -> Dict:
    """Submit simulation attestation using Foundry's cast CLI.

    Args:
        config_hash: Hex config hash (32 bytes)
        kill_rate: Kill rate scaled by 10000
        nanobot_count: Number of nanobots
        tumor_radius: Tumor radius in µm
        steps: Simulation steps
        rpc_url: Base Sepolia RPC URL
        private_key: Deployer private key
        dry_run: If True, only estimate gas

    Returns:
        Result dict with tx_hash or estimate
    """
    normalized_config_hash = "0x" + normalize_config_hash(config_hash)
    if dry_run:
        try:
            result = subprocess.run(
                [
                    "cast", "estimate",
                    TUMOR_INTEL_ADDRESS,
                    "submitSimulation(bytes32,uint32,uint32,uint32,uint32)",
                    normalized_config_hash,
                    str(kill_rate),
                    str(nanobot_count),
                    str(tumor_radius),
                    str(steps),
                    "--rpc-url", rpc_url,
                    "--private-key", private_key,
                ],
                capture_output=True, text=True, timeout=20, check=True,
            )
            return {
                "ok": True,
                "dry_run": True,
                "contract": TUMOR_INTEL_ADDRESS,
                "config_hash": config_hash,
                "gas_estimate": result.stdout.strip(),
                "message": "Dry run complete for submitSimulation(). Proof verification remains a later stage.",
                "proof_lifecycle": build_lifecycle(
                    "bundle_created",
                    note="Bundle can be submitted on-chain now; proof verification remains pending.",
                ),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    try:
        result = subprocess.run(
            [
                "cast", "send",
                TUMOR_INTEL_ADDRESS,
                "submitSimulation(bytes32,uint32,uint32,uint32,uint32)",
                normalized_config_hash,
                str(kill_rate),
                str(nanobot_count),
                str(tumor_radius),
                str(steps),
                "--rpc-url", rpc_url,
                "--private-key", private_key,
                "--json",
            ],
            capture_output=True, text=True, timeout=60, check=True,
        )
        tx_result = json.loads(result.stdout)
        return {
            "ok": True,
            "dry_run": False,
            "contract": TUMOR_INTEL_ADDRESS,
            "config_hash": config_hash,
            "tx": tx_result,
            "proof_lifecycle": build_lifecycle(
                "submitted_onchain",
                note="Simulation metadata submitted on-chain. Await proof generation and verifySimulation().",
            ),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Live submission failed: {e}",
            "contract": TUMOR_INTEL_ADDRESS,
            "config_hash": config_hash,
            "proof_lifecycle": build_lifecycle(
                "bundle_created",
                note="Bundle created locally but on-chain submission failed.",
            ),
        }


def create_attestation_bundle(
    config: dict,
    metrics: dict,
    run_id: Optional[str] = None,
) -> Dict:
    """Create a complete attestation bundle: IPFS artifact + on-chain data.

    Args:
        config: Simulation config
        metrics: Simulation results
        run_id: Optional run ID

    Returns:
        Bundle with IPFS pin result + on-chain submission data
    """
    # Pin to IPFS
    ipfs_result = pin_simulation(config, metrics, run_id=run_id, backend="dry-run")

    # Prepare on-chain data
    config_hash = ipfs_result["config_hash"]
    kill_rate = int(metrics.get("kill_rate", 0) * 100)  # Scale to basis points
    nanobot_count = config.get("nanobot_count", config.get("n_nanobots", 0))
    tumor_radius = config.get("tumor_radius", 0)
    steps = config.get("steps", config.get("n_steps", config.get("max_steps", 0)))

    public_values_payload = build_public_values_payload(
        config_hash=config_hash,
        kill_rate_bps=kill_rate,
        nanobot_count=nanobot_count,
        tumor_radius=tumor_radius,
        steps=steps,
    )
    public_values = encode_public_values_payload(public_values_payload)
    artifact = ipfs_result.get("artifact", {})
    simulation_commitments = {
        "config_hash": config_hash,
        "metrics_hash": artifact.get("metrics_hash", compute_artifact_hash(metrics)),
        "artifact_hash": ipfs_result["artifact_hash"],
    }

    return {
        "ok": True,
        "ipfs": ipfs_result,
        "onchain": {
            "contract": TUMOR_INTEL_ADDRESS,
            "chain_id": BASE_SEPOLIA_CHAIN_ID,
            "config_hash": config_hash,
            "kill_rate_bps": kill_rate,
            "nanobot_count": nanobot_count,
            "tumor_radius": tumor_radius,
            "steps": steps,
            "public_values": public_values,
            "public_values_payload": public_values_payload,
            "public_values_schema_version": PUBLIC_VALUES_SCHEMA_VERSION,
            "program_version": PROGRAM_VERSION,
            "public_values_metadata": build_public_values_metadata(),
            "simulation_commitments": simulation_commitments,
        },
        "verification_status": build_verification_status(
            schema_ok=True,
            integrity_ok=True,
            replay_ok=False,
            proof_ok=False,
            onchain_ok=False,
        ),
        "proof_lifecycle": build_lifecycle(
            "bundle_created",
            note="Artifact created with encoded public values. Next steps: submitSimulation(), generate SP1+Groth16 proof, then verifySimulation().",
        ),
        "status": "ready_for_submission",
        "next_step": "Submit simulation metadata on-chain, then generate SP1+Groth16 proof and call verifySimulation(publicValues, proofBytes).",
    }


def main():
    parser = argparse.ArgumentParser(description="Submit simulation attestation")
    parser.add_argument("--config", required=True, help="Config JSON file or inline JSON")
    parser.add_argument("--metrics", required=True, help="Metrics JSON file or inline JSON")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # Load config
    config_path = Path(args.config)
    if config_path.exists():
        config = json.loads(config_path.read_text())
    else:
        config = json.loads(args.config)

    # Load metrics
    metrics_path = Path(args.metrics)
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text())
    else:
        metrics = json.loads(args.metrics)

    bundle = create_attestation_bundle(config, metrics)
    print(json.dumps(bundle, indent=2))


if __name__ == "__main__":
    main()
