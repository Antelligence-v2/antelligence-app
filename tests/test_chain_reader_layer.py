"""Tests for the blockchain-native chain reader layer."""

import json
import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def _fn(return_value=None, side_effect=None):
    function = Mock()
    call = Mock(side_effect=side_effect, return_value=return_value)
    function.return_value.call = call
    function.call = call
    return function


def test_chain_config_defaults_to_latest_deployed_phase1_contracts(monkeypatch):
    monkeypatch.delenv("ANTELLIGENCE_TUMOR_INTEL_ADDR", raising=False)
    monkeypatch.delenv("TUMOR_INTEL_ADDR", raising=False)
    monkeypatch.delenv("ANTELLIGENCE_REGISTRY_ADDR", raising=False)
    monkeypatch.delenv("EXPERIENCE_REGISTRY_ADDR", raising=False)
    from chain.config import get_experience_registry_address, get_tumor_intel_address

    assert get_tumor_intel_address() == "0x925b455175eF932a9a0239090a94E593224CD8AB"
    assert get_experience_registry_address() == "0x58A78E337ce3D948A39475f05Ca1A2c30274CADE"


def test_intel_reader_pin_type_names_match_solidity_enum():
    from chain.intel_reader import PIN_TYPE_NAMES

    assert PIN_TYPE_NAMES == {
        0: "HYPOXIC_CLUSTER",
        1: "STEM_CELL_DETECTED",
        2: "HIGH_RESISTANCE_AREA",
        3: "VESSEL_LOCATION",
        4: "SUCCESSFUL_KILL",
        5: "DRUG_OVERDOSE_ZONE",
        6: "TARGET_ACQUIRED",
        7: "DRUG_DELIVERY",
    }


def test_intel_reader_disabled_returns_empty_without_rpc(monkeypatch):
    monkeypatch.delenv("CHAIN_READ_ENABLED", raising=False)
    from chain.intel_reader import ChainIntelReader

    contract = Mock()
    reader = ChainIntelReader(contract=contract)

    assert reader.fetch_active_intel_pins() == []
    contract.functions.getActivePinDetails.assert_not_called()


def test_intel_reader_fetches_active_pin_details_and_caches(monkeypatch):
    monkeypatch.setenv("CHAIN_READ_ENABLED", "true")
    from chain.intel_reader import ChainIntelReader

    contract = Mock()
    contract.functions.getActivePinDetails = _fn(
        return_value=(
            [7],
            [301],
            [299],
            [2],
            ["0x0000000000000000000000000000000000000001"],
            [9],
            [3],
            [123456],
        )
    )

    reader = ChainIntelReader(contract=contract, ttl_seconds=60, now=lambda: 1000.0)

    first = reader.fetch_active_intel_pins()
    second = reader.fetch_active_intel_pins()

    assert [pin.to_contract_pin_dict() for pin in first] == [
        {
            "pinId": 7,
            "x": 301,
            "y": 299,
            "pinType": "HIGH_RESISTANCE_AREA",
            "pinTypeCode": 2,
            "reporter": "0x0000000000000000000000000000000000000001",
            "priority": 9,
            "confirmations": 3,
            "timestamp": 123456,
            "isActive": True,
        }
    ]
    assert second == first
    assert contract.functions.getActivePinDetails.call_count == 1


def test_intel_reader_gracefully_degrades_on_rpc_failure(monkeypatch):
    monkeypatch.setenv("CHAIN_READ_ENABLED", "true")
    from chain.intel_reader import ChainIntelReader

    contract = Mock()
    contract.functions.getActivePinDetails = _fn(side_effect=RuntimeError("rpc down"))

    reader = ChainIntelReader(contract=contract)

    assert reader.fetch_active_intel_pins() == []


def test_experience_consumer_reads_top_strategies_and_experience(monkeypatch):
    monkeypatch.setenv("CHAIN_READ_ENABLED", "1")
    from chain.experience_consumer import ChainExperienceConsumer

    contract = Mock()
    contract.functions.getTopStrategies = _fn(
        return_value=[
            {
                "runHash": "0x" + "aa" * 32,
                "score": 9000,
                "promotedAt": 123,
                "strategyType": "pheromone-guided",
                "nanobotCount": 12,
                "tumorRadius": 180,
                "workerParamsJson": '{"exploration_bias":0.1}',
            }
        ]
    )
    contract.functions.getExperience = _fn(
        return_value=(
            ("0x" + "aa" * 32, "ipfs://cid", "0x" + "bb" * 32, 9000, "0xabc", 123, 2, True),
            (
                "pheromone-guided",
                "gemma4",
                12,
                180,
                "0x" + "cc" * 32,
                '{"exploration_bias":0.1}',
            ),
        )
    )
    contract.functions.isPromoted = _fn(return_value=True)

    consumer = ChainExperienceConsumer(contract=contract)

    strategies = consumer.get_top_strategies(1)
    experience = consumer.get_experience("0x" + "aa" * 32)

    assert strategies[0].run_hash == "0x" + "aa" * 32
    assert strategies[0].score == 9000
    assert strategies[0].worker_params == {"exploration_bias": 0.1}
    assert experience.verified is True
    assert experience.worker_params == {"exploration_bias": 0.1}
    assert consumer.is_promoted("0x" + "aa" * 32) is True


def test_experience_writer_disabled_skips_contract(monkeypatch):
    monkeypatch.delenv("CHAIN_WRITE_ENABLED", raising=False)
    from chain.experience_writer import ChainStrategyWriter

    contract = Mock()
    writer = ChainStrategyWriter(contract=contract)

    assert writer.request_promotion("0x" + "aa" * 32) is False
    assert writer.submit_experience({"tumor_radius": 100}, {"kill_rate": 50}, "run-1", {}) is None
    contract.functions.promoteStrategy.assert_not_called()


def test_experience_writer_submits_and_promotes_when_enabled(monkeypatch):
    monkeypatch.setenv("CHAIN_WRITE_ENABLED", "true")
    from chain.experience_writer import ChainStrategyWriter

    contract = Mock()
    contract.functions.submitExperience.return_value.transact.return_value = b"submit-tx"
    contract.functions.promoteStrategy.return_value.transact.return_value = b"promote-tx"

    writer = ChainStrategyWriter(contract=contract, transaction_options={"from": "0xabc"})

    result = writer.submit_experience(
        config={
            "tumor_radius": 100,
            "nanobot_count": 4,
            "pheromone_params": {"trail_decay": 0.08, "recruitment_diffusion": 1e-6},
        },
        metrics={"kill_rate": 42.5},
        run_id="run-1",
        strategy_meta={"strategyType": "pheromone-guided", "modelUsed": "heuristic"},
    )

    assert result is not None
    assert result["ok"] is True
    assert result["tx_hash"] == "0x7375626d69742d7478"
    assert writer.request_promotion(result["run_hash"]) is True
    contract.functions.submitExperience.assert_called_once()
    submitted_meta = contract.functions.submitExperience.call_args.args[4]
    assert json.loads(submitted_meta[5]) == {
        "recruitment_diffusion": 1e-6,
        "trail_decay": 0.08,
    }
    contract.functions.promoteStrategy.assert_called_once_with(result["run_hash"])


def test_experience_writer_can_submit_with_cast_when_private_key_configured(monkeypatch):
    monkeypatch.setenv("CHAIN_WRITE_ENABLED", "true")
    monkeypatch.setenv("BASE_SEPOLIA_RPC_URL", "http://rpc.test")
    monkeypatch.setenv("PRIVATE_KEY", "0x" + "11" * 32)
    monkeypatch.setenv("EXPERIENCE_REGISTRY_ADDR", "0x58A78E337ce3D948A39475f05Ca1A2c30274CADE")
    from chain.experience_writer import ChainStrategyWriter

    calls = []
    def runner(args):
        calls.append(args)
        return {"transactionHash": "0xabc123"}

    writer = ChainStrategyWriter(contract=None, use_cast=True, cast_runner=runner)
    result = writer.submit_experience(
        config={
            "tumor_radius": 100,
            "nanobot_count": 4,
            "pheromone_params": {"trail_decay": 0.08},
        },
        metrics={"kill_rate": 42.5},
        run_id="run-1",
        strategy_meta={"strategyType": "pheromone-guided", "modelUsed": "heuristic"},
    )

    assert result is not None
    assert result["ok"] is True
    assert result["tx_hash"] == "0xabc123"
    assert calls[0][:3] == ["cast", "send", "0x58A78E337ce3D948A39475f05Ca1A2c30274CADE"]
    assert any("(string,string,uint16,uint16,bytes32,string)" in arg for arg in calls[0])
    assert any('\\"trail_decay\\":0.08' in arg for arg in calls[0])
    assert "--private-key" in calls[0]
    assert "0x" + "11" * 32 in calls[0]
