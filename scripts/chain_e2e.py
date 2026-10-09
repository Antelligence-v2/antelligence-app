#!/usr/bin/env python3
"""End-to-end chain check: one real tumor simulation -> on-chain public values -> read back -> replay.

    ANTELLIGENCE_CHAIN=zksync-era-sepolia PRIVATE_KEY=... python scripts/chain_e2e.py --out e2e.json
    ANTELLIGENCE_CHAIN=zksync-local-inmemory PRIVATE_KEY=<anvil dev key> python scripts/chain_e2e.py --out e2e.json

Steps (each recorded in the output JSON):
1. run the tumor simulation (``backend.runtime_factory.run_simulation``) with a fixed seed;
2. build the attestation + staged proof bundle with the same helpers the API uses;
3. submit the five public values through ``chain.submit.submit_bundle_onchain``;
4. read them back through the leaderboard path (``fetch_onchain_simulations``) and require an exact
   match with the bundle, plus ``isVerified == false``;
5. replay the simulation from the artifact config via ``chain.verify.verify_artifact``.

Trust: the result is ``proof_staged`` (mock SP1 adapter) with ``onchain_ok == false``. The chain
records claimed values; it does not prove the simulation ran correctly.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from backend.config import SimulationConfig  # noqa: E402
from backend.runtime_factory import run_simulation  # noqa: E402
from chain.config import get_canonical_chain_config, get_rpc_url  # noqa: E402
from chain.leaderboard import build_leaderboard, fetch_onchain_simulations, normalize_leaderboard_artifact, \
    onchain_artifacts  # noqa: E402
from chain.proof_adapter import create_proof_bundle  # noqa: E402
from chain.submit import submit_bundle_onchain  # noqa: E402
from chain.verify import verify_artifact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--bots", type=int, default=5)
    parser.add_argument("--grid", type=int, default=20)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20261008)
    args = parser.parse_args()

    chain = get_canonical_chain_config()
    if not chain["deployed"]:
        raise SystemExit(f"{chain['network']} has no deployments file; deploy first")

    cfg = SimulationConfig(num_bots=args.bots, grid_size=args.grid, steps=args.steps, seed=args.seed)
    with redirect_stdout(sys.stderr):
        model, metrics = run_simulation(cfg)
    # Same normalization as backend/api_server.py::_build_run_provenance.
    model_kwargs = cfg.to_model_kwargs()
    proof_config = dict(cfg.model_dump(), nanobot_count=cfg.num_bots, tumor_radius=int(model_kwargs["tumor_radius"]))
    proof_metrics = dict(metrics, kill_rate=float(metrics.get("kill_rate", 0.0)) * 100.0)
    run_id = f"e2e-{chain['network']}-{args.seed}"
    bundle = create_proof_bundle(proof_config, proof_metrics, run_id=run_id)

    submitted = submit_bundle_onchain(bundle)
    tx = submitted["onchain"]["submission"]

    events = fetch_onchain_simulations(get_rpc_url(), from_block=max(0, int(tx["block_number"]) - 1))
    payload = bundle["onchain"]["public_values_payload"]
    match = [e for e in events if e["config_hash"] == payload["config_hash"] and e["tx_hash"] == tx["tx_hash"]]
    if len(match) != 1:
        raise SystemExit(f"read-back failed: {len(match)} matching events for tx {tx['tx_hash']}")
    onchain = match[0]
    readback_ok = all(onchain[k] == payload[k] for k in ("kill_rate_bps", "nanobot_count", "tumor_radius", "steps"))
    leaderboard = build_leaderboard(onchain_artifacts(match))["leaderboard"][0]

    with redirect_stdout(sys.stderr):
        verification = verify_artifact(normalize_leaderboard_artifact(submitted), replay=True)

    result = {
        "schema": "antelligence.chain-e2e/v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "chain": {k: chain[k] for k in ("network", "chain_id", "explorer_url", "deployments_file",
                                        "tumor_intel_address")},
        "simulation": {"config": proof_config, "metrics_kill_rate_fraction": metrics.get("kill_rate"),
                       "run_id": run_id},
        "public_values_submitted": payload,
        "submission": tx,
        "readback": {"event": onchain, "values_match_bundle": readback_ok,
                     "contract_isVerified": onchain["verified"]},
        "leaderboard_entry": {k: leaderboard[k] for k in ("kill_rate", "nanobot_count", "steps", "trust_tier",
                                                          "verified_onchain", "proof_stage")},
        "replay": {"integrity_ok": verification["integrity"]["ok"],
                   "public_values_ok": (verification["public_values"] or {}).get("ok"),
                   "proof_bundle_schema_ok": (verification["proof_bundle"] or {}).get("ok"),
                   "replay_ok": (verification["replay"] or {}).get("ok"),
                   "tolerance": (verification["replay"] or {}).get("tolerance"),
                   "verify_trust_tier": verification["trust_tier"]},
        "trust": {"bundle_trust_tier": submitted["trust_tier"], "proof_is_mock": submitted["proof_bundle"]["is_mock"],
                  "onchain_ok": submitted["verification_status"]["onchain_ok"],
                  "note": "ZKsync's validity proofs cover the chain's state transition, not this simulation. "
                          "The simulation proof is a mock SP1 adapter bundle: proof_staged, never verified_onchain."},
        "bundle": submitted,
    }
    Path(args.out).write_text(json.dumps(result, indent=2, default=str) + "\n")
    summary = {k: result[k] for k in ("submission", "readback", "replay", "trust")}
    summary["readback"] = {k: v for k, v in summary["readback"].items() if k != "event"}
    print(json.dumps(summary, indent=2, default=str))
    ok = readback_ok and not onchain["verified"] and result["replay"]["replay_ok"] and result["replay"]["integrity_ok"]
    return 0 if ok else 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHON_DOTENV_DISABLED", "1")
    sys.exit(main())
