"""Leaderboard service for ranking attested simulation policies.

Reads SimulationSubmitted / SimulationVerified events from TumorIntel on the
configured chain (``ANTELLIGENCE_CHAIN``, default ZKsync Era Sepolia) and ranks
runs by claimed kill rate. Supports on-chain reading and local artifact ranking.

Trust: an on-chain *submission* only records claimed public values. A submission is
``verified_onchain`` only when TumorIntel's record for its config hash is verified **and**
the record's ``publicValuesHash`` is the hash of exactly this submission's values (see
``chain.onchain_record``). ``isVerified(configHash)`` alone is not enough: it is keyed by
config hash, and ``submitSimulation`` can rewrite a verified record's values.

Usage:
    python3 -m chain.leaderboard                    # Show leaderboard
    python3 -m chain.leaderboard --from-dir ./runs  # Rank local artifacts
    python3 -m chain.leaderboard --json             # JSON output
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from chain.config import explorer_tx_url, get_network, get_rpc_url, get_tumor_intel_address, load_deployment
from chain.onchain_record import proves, public_values_hash, read_simulation_record

TUMOR_INTEL_ADDRESS = get_tumor_intel_address()
# keccak256 of the event signatures in blockchain/contracts/TumorIntel.sol
SIMULATION_SUBMITTED_TOPIC = "0xa21d9d52e2e6ed7649d4ed863a13b4745fffab40841d79e32b6d5a9c72334ca1"
SIMULATION_VERIFIED_TOPIC = "0xdeb2a6c54484ae22ad3e9e0132b27c57562483e240ae7f5f4760ef83143e9390"


def _hex(value) -> str:
    if isinstance(value, (bytes, bytearray)):
        return "0x" + bytes(value).hex()
    text = str(value)
    return text if text.startswith("0x") else "0x" + text


def _deployment_block() -> int:
    record = load_deployment()
    for contract in (record or {}).get("contracts", []):
        if contract.get("name") == "TumorIntel" and contract.get("block_number") is not None:
            return int(contract["block_number"])
    return 0


def fetch_onchain_simulations(rpc_url: str, contract: Optional[str] = None, from_block: Optional[int] = None,
                              w3=None) -> List[Dict]:
    """Decode TumorIntel SimulationSubmitted events and decide, per event, whether its values were proven.

    Returns one dict per submission: config_hash, submitter, kill_rate_bps, nanobot_count,
    tumor_radius, steps, tx_hash, block_number, plus
    ``verified`` (this event's exact values are the ones a verifier accepted) and
    ``contract_verified_flag`` (the raw per-config-hash ``verified`` bit, for diagnostics only).
    """
    contract = contract or get_tumor_intel_address()
    if not contract:
        return []
    if w3 is None:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
    from web3 import Web3 as _W3
    address = _W3.to_checksum_address(contract)
    logs = w3.eth.get_logs({"address": address, "fromBlock": from_block if from_block is not None else _deployment_block(),
                            "toBlock": "latest", "topics": [SIMULATION_SUBMITTED_TOPIC]})
    records: Dict[str, Dict] = {}
    out = []
    for log in logs:
        topics = [_hex(t) for t in log["topics"]]
        data = _hex(log["data"])[2:]
        words = [int(data[i:i + 64], 16) for i in range(0, len(data), 64)]
        if len(topics) < 3 or len(words) < 4:
            continue
        config_hash = topics[1]
        if config_hash not in records:
            records[config_hash] = read_simulation_record(w3, address, config_hash)
        record = records[config_hash]
        expected = public_values_hash(config_hash, words[0], words[1], words[2], words[3])
        out.append({
            "config_hash": config_hash[2:],
            "submitter": "0x" + topics[2][-40:],
            "kill_rate_bps": words[0], "nanobot_count": words[1], "tumor_radius": words[2], "steps": words[3],
            "tx_hash": _hex(log["transactionHash"]),
            "block_number": int(log["blockNumber"]),
            "verified": proves(record, expected),
            "contract_verified_flag": record["verified"],
        })
    return out


def onchain_artifacts(events: List[Dict]) -> List[Dict]:
    """Leaderboard rows for on-chain submissions, with honest trust fields.

    A submission carries only claimed public values: no artifact, no replay, no proof.
    It is ``verified_onchain`` only when ``verified`` is set, i.e. a verifier accepted a proof
    of exactly these values (see :func:`fetch_onchain_simulations`).
    """
    rows = []
    for evt in events:
        verified = bool(evt.get("verified"))
        rows.append({
            "type": "antelligence-simulation-v2",
            "run_id": evt["config_hash"][:16],
            "config_hash": evt["config_hash"],
            "config": {"nanobot_count": evt["nanobot_count"], "tumor_radius": evt["tumor_radius"],
                       "steps": evt["steps"]},
            "metrics": {"kill_rate": evt["kill_rate_bps"] / 100.0},
            "verification_status": {"schema_ok": True, "integrity_ok": False, "replay_ok": False,
                                    "proof_ok": verified, "onchain_ok": verified},
            "proof_lifecycle": {"stage": "verified_onchain" if verified else "submitted_onchain"},
            "tx_hash": evt.get("tx_hash", ""),
            "explorer_tx_url": explorer_tx_url(evt.get("tx_hash", "")),
            "network": get_network().name,
        })
    return rows


def fetch_onchain_events(rpc_url: str, from_block: Optional[int] = None) -> List[Dict]:
    """Backwards-compatible wrapper: decoded submissions, or [] if the chain is unreachable."""
    try:
        return fetch_onchain_simulations(rpc_url, from_block=from_block)
    except Exception:
        return []


def load_local_artifacts(directory: str) -> List[Dict]:
    """Load simulation artifacts from a local directory.

    Reads all JSON files that match the antelligence artifact format.

    Args:
        directory: Path to directory containing artifact JSON files

    Returns:
        List of artifact dicts
    """
    artifacts = []
    dir_path = Path(directory)
    if not dir_path.exists():
        return artifacts

    for f in sorted(dir_path.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            if data.get("type") == "antelligence-simulation-v2":
                artifacts.append(data)
        except (json.JSONDecodeError, OSError):
            continue

    return artifacts


def rank_by_kill_rate(entries: List[Dict]) -> List[Dict]:
    """Rank simulation entries by kill rate (descending).

    Args:
        entries: List of dicts with at least 'kill_rate' field

    Returns:
        Sorted list with rank added
    """
    sorted_entries = sorted(
        entries,
        key=lambda x: x.get("kill_rate", 0),
        reverse=True,
    )
    for i, entry in enumerate(sorted_entries):
        entry["rank"] = i + 1
    return sorted_entries


def derive_trust_tier(verification_status: Dict, proof_bundle: Dict, proof_lifecycle: Dict) -> str:
    if verification_status.get("onchain_ok"):
        return "verified_onchain"
    if proof_bundle:
        return "proof_staged"
    if verification_status.get("replay_ok"):
        return "replay_checked"
    if verification_status.get("integrity_ok"):
        return "integrity_checked"
    return "unverified"


def normalize_leaderboard_artifact(record: Dict) -> Dict:
    """Flatten attestation/proof bundle records into a canonical artifact view."""
    artifact = record.get("ipfs", {}).get("artifact", {}) if isinstance(record.get("ipfs"), dict) else {}
    if not artifact:
        return record

    normalized = dict(artifact)
    for field in (
        "verification_status",
        "proof_lifecycle",
        "proof_bundle",
        "trust_tier",
        "verified_onchain",
        "onchain",
        "status",
        "next_step",
        "replay_ok",
        "integrity_ok",
    ):
        if field in record:
            normalized[field] = record[field]
    
    # Ensure verification_status flags are flattened for the leaderboard
    if "verification_status" in record:
        vs = record["verification_status"]
        if "onchain_ok" in vs:
            normalized["verified_onchain"] = vs["onchain_ok"]
        if "replay_ok" in vs:
            normalized["replay_ok"] = vs["replay_ok"]
        if "integrity_ok" in vs:
            normalized["integrity_ok"] = vs["integrity_ok"]
            
    return normalized


def build_leaderboard(artifacts: List[Dict]) -> Dict:
    """Build leaderboard from simulation artifacts.

    Args:
        artifacts: List of simulation artifact dicts

    Returns:
        Leaderboard dict with ranked entries and summary stats
    """
    entries = []
    for raw_artifact in artifacts:
        artifact = normalize_leaderboard_artifact(raw_artifact)
        config = artifact.get("config", {})
        metrics = artifact.get("metrics", {})
        verification_status = artifact.get("verification_status", {})
        proof_lifecycle = artifact.get("proof_lifecycle", {})
        proof_bundle = artifact.get("proof_bundle", {})
        entries.append({
            "run_id": artifact.get("run_id", "unknown"),
            "config_hash": artifact.get("config_hash", ""),
            "kill_rate": metrics.get("kill_rate", 0),
            "deliveries": metrics.get("deliveries", 0),
            "total_drug": metrics.get("total_drug", 0),
            "tumor_radius": config.get("tumor_radius", 0),
            "nanobot_count": config.get("nanobot_count", config.get("n_nanobots", 0)),
            "steps": config.get("steps", config.get("n_steps", 0)),
            "pheromone_params": config.get("pheromone_params", {}),
            "timestamp": artifact.get("timestamp", ""),
            "verified_onchain": verification_status.get("onchain_ok", artifact.get("verified_onchain", False)),
            "proof_stage": proof_lifecycle.get("stage", "untracked"),
            "integrity_ok": verification_status.get("integrity_ok", False),
            "replay_ok": verification_status.get("replay_ok", False),
            "proof_ok": verification_status.get("proof_ok", False),
            "trust_tier": artifact.get("trust_tier") or derive_trust_tier(verification_status, proof_bundle, proof_lifecycle),
            "proof_origin": proof_bundle.get("proof_origin", "unknown"),
            "proof_artifact_version": proof_bundle.get("proof_artifact_version", "untracked"),
        })

    ranked = rank_by_kill_rate(entries)

    # Summary stats
    kill_rates = [e["kill_rate"] for e in entries]
    summary = {
        "total_entries": len(entries),
        "verified_entries": sum(1 for e in entries if e.get("verified_onchain")),
        "replay_checked_entries": sum(1 for e in entries if e.get("replay_ok")),
        "staged_proof_entries": sum(1 for e in entries if e.get("trust_tier") == "proof_staged"),
        "avg_kill_rate": round(sum(kill_rates) / len(kill_rates), 2) if kill_rates else 0,
        "best_kill_rate": max(kill_rates) if kill_rates else 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "ok": True,
        "leaderboard": ranked,
        "summary": summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Antelligence simulation leaderboard")
    parser.add_argument("--from-dir", help="Load artifacts from local directory")
    parser.add_argument("--onchain", action="store_true", help="Fetch submissions from the configured chain")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    artifacts = []

    if args.from_dir:
        artifacts = load_local_artifacts(args.from_dir)
    elif args.onchain:
        rpc_url = get_rpc_url()
        if not rpc_url:
            print(json.dumps({"ok": False, "error": "chain RPC not configured (set ANTELLIGENCE_CHAIN or ANTELLIGENCE_RPC_URL)"}))
            sys.exit(1)
        artifacts = onchain_artifacts(fetch_onchain_simulations(rpc_url))
    else:
        print(json.dumps({"ok": False, "error": "Specify --from-dir or --onchain"}))
        sys.exit(1)

    result = build_leaderboard(artifacts)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if not result["leaderboard"]:
            print("No simulation entries found.")
            return

        print(f"\nAntelligence Simulation Leaderboard")
        print(f"{'='*60}")
        print(f"{'Rank':<6}{'Kill Rate':<12}{'Deliveries':<12}{'Nanobots':<10}{'Steps':<8}{'Run ID'}")
        print(f"{'-'*60}")
        for entry in result["leaderboard"][:20]:
            print(
                f"{entry['rank']:<6}"
                f"{entry['kill_rate']:>8.1f}%   "
                f"{entry['deliveries']:>8}    "
                f"{entry['nanobot_count']:>6}    "
                f"{entry['steps']:>5}   "
                f"{entry['run_id'][:16]}"
            )
        print(f"\nTotal: {result['summary']['total_entries']} entries")
        print(f"Best: {result['summary']['best_kill_rate']}% | Avg: {result['summary']['avg_kill_rate']}%")


if __name__ == "__main__":
    main()
