"""Chain selection: ZKsync Era Sepolia by default, addresses from the deployments file."""

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from chain import config  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
STALE = ("0xd1cfa5b9994e06cc18a21dc18fb9d20a3c02238b", "0x925b455175eF932a9a0239090a94E593224CD8AB")


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for name in ("ANTELLIGENCE_CHAIN", "ANTELLIGENCE_RPC_URL", "CHAIN_RPC", "ZKSYNC_SEPOLIA_RPC_URL",
                 "BASE_SEPOLIA_RPC_URL", "ANTELLIGENCE_TUMOR_INTEL_ADDR", "TUMOR_INTEL_ADDR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("ANTELLIGENCE_DEPLOYMENTS_DIR", str(tmp_path))
    return tmp_path


def _write(dirpath, network, chain_id, address="0x" + "ab" * 20):
    (dirpath / f"{network}.json").write_text(json.dumps({
        "network": network, "chain_id": chain_id,
        "contracts": [{"name": "TumorIntel", "address": address, "deploy_tx_hash": "0x" + "11" * 32,
                       "block_number": 7}],
    }))


def test_default_network_is_zksync_era_sepolia(clean_env):
    network = config.get_network()
    assert network.name == "zksync-era-sepolia"
    assert network.chain_id == 300
    assert config.get_chain_id() == 300


def test_addresses_come_from_the_deployments_file(clean_env):
    assert config.get_tumor_intel_address() == ""
    _write(clean_env, "zksync-era-sepolia", 300)
    assert config.get_tumor_intel_address() == "0x" + "ab" * 20
    assert config.get_canonical_chain_config()["deployed"] is True


def test_deployments_file_with_wrong_chain_id_is_rejected(clean_env):
    _write(clean_env, "zksync-era-sepolia", 84532)
    with pytest.raises(config.ChainConfigError):
        config.get_tumor_intel_address()


def test_unknown_network_is_rejected(clean_env, monkeypatch):
    monkeypatch.setenv("ANTELLIGENCE_CHAIN", "ethereum-mainnet")
    with pytest.raises(config.ChainConfigError):
        config.get_network()


def test_rpc_is_offline_unless_a_chain_is_selected(clean_env, monkeypatch):
    assert config.get_rpc_url() == ""
    monkeypatch.setenv("ANTELLIGENCE_CHAIN", "zksync-era-sepolia")
    assert config.get_rpc_url() == "https://sepolia.era.zksync.dev"
    monkeypatch.setenv("ANTELLIGENCE_RPC_URL", "http://127.0.0.1:8011")
    assert config.get_rpc_url() == "http://127.0.0.1:8011"


def test_explorer_urls_follow_the_selected_network(clean_env):
    assert config.explorer_tx_url("0xabc") == "https://sepolia.explorer.zksync.io/tx/0xabc"


def test_all_configured_networks_are_testnets_or_local():
    assert all(n.is_testnet for n in config.NETWORKS.values())
    assert {n.chain_id for n in config.NETWORKS.values()} == {300, 260, 84532}


def test_no_stale_base_sepolia_address_in_backend_code():
    for path in list((REPO / "backend").rglob("*.py")) + [REPO / "blockchain" / "client.py",
                                                         REPO / "scripts" / "dashboard.py",
                                                         REPO / "scripts" / "generate_report.py"]:
        text = path.read_text(encoding="utf-8")
        for stale in STALE:
            assert stale.lower() not in text.lower(), f"{path} still hard-codes {stale}"


def test_committed_zksync_deployment_file_is_consistent_if_present():
    path = REPO / "blockchain" / "deployments" / "zksync-era-sepolia.json"
    if not path.exists():
        pytest.skip("not deployed yet (testnet gas blocker, docs/status/BLOCKERS.md)")
    record = json.loads(path.read_text())
    assert record["chain_id"] == 300
    names = {c["name"] for c in record["contracts"]}
    assert {"FoodToken", "ColonyMemory", "TumorIntel", "ExperienceRegistry"} <= names
    assert "MockProofVerifier" not in names
    assert record["proof_verifier"]["address"] is None
    for c in record["contracts"]:
        assert c["address"].startswith("0x") and len(c["address"]) == 42
        assert c["deploy_tx_hash"].startswith("0x") and len(c["deploy_tx_hash"]) == 66
        assert isinstance(c["block_number"], int)
    assert len(record["git_commit"]) == 40
    assert record["compiler"]["zksolc"] and record["compiler"]["solc"]
