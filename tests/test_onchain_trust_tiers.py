"""A testnet submission records claimed public values; it must never read as verified."""

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from chain.leaderboard import build_leaderboard, onchain_artifacts  # noqa: E402
from chain.proof_adapter import create_proof_bundle  # noqa: E402
from chain.submit import submit_bundle_onchain  # noqa: E402

EVENT = {"config_hash": "ab" * 32, "submitter": "0x" + "cd" * 20, "kill_rate_bps": 4550, "nanobot_count": 10,
         "tumor_radius": 66, "steps": 30, "tx_hash": "0x" + "11" * 32, "block_number": 5}


def test_unverified_onchain_submission_is_not_verified_onchain():
    entry = build_leaderboard(onchain_artifacts([dict(EVENT, verified=False)]))["leaderboard"][0]
    assert entry["verified_onchain"] is False
    assert entry["trust_tier"] != "verified_onchain"
    assert entry["proof_stage"] == "submitted_onchain"
    assert entry["kill_rate"] == 45.5


def test_contract_verified_submission_is_verified_onchain():
    entry = build_leaderboard(onchain_artifacts([dict(EVENT, verified=True)]))["leaderboard"][0]
    assert entry["verified_onchain"] is True
    assert entry["trust_tier"] == "verified_onchain"


@pytest.fixture
def deployed(monkeypatch, tmp_path):
    (tmp_path / "zksync-era-sepolia.json").write_text(json.dumps({
        "network": "zksync-era-sepolia", "chain_id": 300,
        "contracts": [{"name": "TumorIntel", "address": "0x" + "ab" * 20}]}))
    monkeypatch.setenv("ANTELLIGENCE_DEPLOYMENTS_DIR", str(tmp_path))
    monkeypatch.delenv("ANTELLIGENCE_CHAIN", raising=False)
    monkeypatch.delenv("ANTELLIGENCE_TUMOR_INTEL_ADDR", raising=False)
    monkeypatch.delenv("TUMOR_INTEL_ADDR", raising=False)


def _runner(receipt):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(receipt), stderr="")

    return run, calls


def test_submission_keeps_the_mock_proof_tier(deployed):
    bundle = create_proof_bundle({"nanobot_count": 5, "tumor_radius": 66, "steps": 30}, {"kill_rate": 12.5},
                                 run_id="r1")
    run, calls = _runner({"status": "0x1", "transactionHash": "0x" + "22" * 32, "blockNumber": "0x10",
                          "from": "0x" + "cd" * 20})
    out = submit_bundle_onchain(bundle, rpc_url="http://rpc.test", private_key="0x" + "11" * 32, runner=run)
    assert calls[0][:4] == ["cast", "send", "0x" + "ab" * 20, "submitSimulation(bytes32,uint32,uint32,uint32,uint32)"]
    assert calls[0][4] == "0x" + bundle["onchain"]["public_values_payload"]["config_hash"]
    assert out["onchain"]["chain_id"] == 300
    assert out["onchain"]["submission"]["block_number"] == 16
    assert out["onchain"]["submission"]["explorer_tx_url"] == "https://sepolia.explorer.zksync.io/tx/0x" + "22" * 32
    assert out["proof_lifecycle"]["stage"] == "submitted_onchain"
    assert out["trust_tier"] == "proof_staged"
    assert out["proof_bundle"]["is_mock"] is True
    assert out["verification_status"]["onchain_ok"] is False
    assert out["verification_status"]["proof_ok"] is False


def test_reverted_submission_raises(deployed):
    bundle = create_proof_bundle({"nanobot_count": 5, "tumor_radius": 66, "steps": 30}, {"kill_rate": 12.5},
                                 run_id="r1")
    run, _ = _runner({"status": "0x0", "transactionHash": "0x" + "33" * 32})
    with pytest.raises(RuntimeError, match="reverted"):
        submit_bundle_onchain(bundle, rpc_url="http://rpc.test", private_key="0x" + "11" * 32, runner=run)


def test_submission_refuses_when_not_deployed(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTELLIGENCE_DEPLOYMENTS_DIR", str(tmp_path))
    monkeypatch.delenv("ANTELLIGENCE_TUMOR_INTEL_ADDR", raising=False)
    monkeypatch.delenv("TUMOR_INTEL_ADDR", raising=False)
    bundle = create_proof_bundle({"nanobot_count": 5, "tumor_radius": 66, "steps": 30}, {"kill_rate": 1.0})
    with pytest.raises(ValueError, match="not deployed"):
        submit_bundle_onchain(bundle, rpc_url="http://rpc.test", private_key="0x" + "11" * 32)
