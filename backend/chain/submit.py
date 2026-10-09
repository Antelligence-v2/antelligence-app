"""Submission CLI for posting simulation attestations on-chain.

Posts the five public values of a simulation run (config hash, kill rate in basis
points, nanobot count, tumor radius, steps) to TumorIntel.submitSimulation on the
chain selected by ``ANTELLIGENCE_CHAIN`` (default ZKsync Era Sepolia; addresses come
from ``blockchain/deployments/<network>.json``).

Usage:
    python3 -m chain.submit --config config.json --metrics metrics.json          # build bundle only
    python3 -m chain.submit --bundle run-provenance.json --submit --out out.json  # live testnet submit

Trust tier: submitting public values on-chain does NOT verify the simulation. The
bundle keeps its proof tier (``proof_staged`` for the mock SP1 adapter) and only
``verifySimulation`` through a real verifier can make it ``verified_onchain``.

Requires: Foundry ``cast`` for transaction submission.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from chain.config import (
    explorer_tx_url,
    get_chain_id,
    get_network,
    get_private_key,
    get_rpc_url,
    get_tumor_intel_address,
)
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


# Resolved at import for backwards compatibility; functions re-resolve at call time.
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
    contract = get_tumor_intel_address()
    if not contract:
        return {"ok": False, "error": f"TumorIntel is not deployed on {get_network().name} (no deployments file)"}
    if dry_run:
        try:
            result = subprocess.run(
                [
                    "cast", "estimate",
                    contract,
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
                "contract": contract,
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
                contract,
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
            "contract": contract,
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
            "contract": contract,
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
            "contract": get_tumor_intel_address(),
            "network": get_network().name,
            "chain_id": get_chain_id(),
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


SUBMIT_SIMULATION_ABI = [{
    "type": "function", "name": "submitSimulation", "stateMutability": "nonpayable", "outputs": [],
    "inputs": [{"name": "configHash", "type": "bytes32"}, {"name": "killRateBps", "type": "uint32"},
               {"name": "nanobotCount", "type": "uint32"}, {"name": "tumorRadius", "type": "uint32"},
               {"name": "steps", "type": "uint32"}],
}]


def _web3_send_submit(*, rpc_url: str, private_key: str, contract: str, args: list) -> Dict:
    """Sign and send submitSimulation in-process (the key never reaches a subprocess argv)."""
    from web3 import Web3

    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 60}))
    account = w3.eth.account.from_key(private_key)
    fn = w3.eth.contract(address=Web3.to_checksum_address(contract), abi=SUBMIT_SIMULATION_ABI) \
        .functions.submitSimulation(bytes.fromhex(args[0][2:]), *[int(a) for a in args[1:]])
    tx = fn.build_transaction({"from": account.address, "nonce": w3.eth.get_transaction_count(account.address),
                               "chainId": w3.eth.chain_id})
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    return {"status": hex(receipt["status"]), "transactionHash": "0x" + bytes(receipt["transactionHash"]).hex().removeprefix("0x"),
            "blockNumber": receipt["blockNumber"], "from": receipt["from"]}


def submit_bundle_onchain(bundle: Dict, *, rpc_url: Optional[str] = None, private_key: Optional[str] = None,
                          sender=_web3_send_submit) -> Dict:
    """Send a bundle's public values to TumorIntel.submitSimulation and record the receipt.

    Returns a copy of the bundle with ``onchain.submission`` (tx hash, block, explorer
    URL) and lifecycle ``submitted_onchain``. Never changes ``trust_tier``,
    ``verification_status.onchain_ok`` or ``proof_ok``: a submission is not a proof.
    """
    onchain = bundle.get("onchain") or {}
    payload = onchain.get("public_values_payload") or {}
    missing = [k for k in ("config_hash", "kill_rate_bps", "nanobot_count", "tumor_radius", "steps") if k not in payload]
    if missing:
        raise ValueError(f"bundle onchain.public_values_payload missing {missing}")
    contract = get_tumor_intel_address()
    if not contract:
        raise ValueError(f"TumorIntel is not deployed on {get_network().name} (no deployments file)")
    rpc_url = rpc_url or get_rpc_url()
    private_key = private_key or get_private_key()
    if not rpc_url or not private_key:
        raise ValueError("chain RPC and PRIVATE_KEY must be configured for a live submission")
    args = [
        "0x" + normalize_config_hash(str(payload["config_hash"])),
        str(int(payload["kill_rate_bps"])), str(int(payload["nanobot_count"])),
        str(int(payload["tumor_radius"])), str(int(payload["steps"])),
    ]
    receipt = sender(rpc_url=rpc_url, private_key=private_key, contract=contract, args=args)
    status = str(receipt.get("status", ""))
    if status not in ("1", "0x1", "true", "True"):
        raise RuntimeError(f"submitSimulation reverted (status={status!r}, tx={receipt.get('transactionHash')})")
    tx_hash = receipt.get("transactionHash", "")
    block = receipt.get("blockNumber")
    block = int(block, 16) if isinstance(block, str) and block.startswith("0x") else block
    out = json.loads(json.dumps(bundle))
    out["onchain"]["contract"] = contract
    out["onchain"]["network"] = get_network().name
    out["onchain"]["chain_id"] = get_chain_id()
    out["onchain"]["submission"] = {
        "method": "submitSimulation(bytes32,uint32,uint32,uint32,uint32)",
        "tx_hash": tx_hash,
        "block_number": block,
        "from": receipt.get("from"),
        "explorer_tx_url": explorer_tx_url(tx_hash),
        "note": "Public values recorded on-chain. This is not proof verification; trust tier unchanged.",
    }
    out["proof_lifecycle"] = build_lifecycle(
        "submitted_onchain",
        note="Public values submitted on-chain. No verifier is configured, so verifySimulation() cannot run; "
             "the simulation proof remains a mock adapter bundle.",
    )
    return out


def _load_json_arg(value: str) -> dict:
    path = Path(value)
    return json.loads(path.read_text()) if path.exists() else json.loads(value)


def main():
    parser = argparse.ArgumentParser(description="Build and (optionally) submit a simulation attestation")
    parser.add_argument("--config", help="Config JSON file or inline JSON")
    parser.add_argument("--metrics", help="Metrics JSON file or inline JSON (kill_rate in percentage points)")
    parser.add_argument("--bundle", help="Existing attestation/proof bundle JSON (e.g. an API run's provenance)")
    parser.add_argument("--submit", action="store_true", help="Send submitSimulation on the configured testnet")
    parser.add_argument("--out", help="Write the resulting bundle JSON here")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.bundle:
        bundle = _load_json_arg(args.bundle)
    elif args.config and args.metrics:
        bundle = create_attestation_bundle(_load_json_arg(args.config), _load_json_arg(args.metrics))
    else:
        parser.error("provide --bundle, or --config and --metrics")

    if args.submit:
        bundle = submit_bundle_onchain(bundle)
    text = json.dumps(bundle, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
