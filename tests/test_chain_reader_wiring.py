"""Tests for chain reader wiring into KG and Queen."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


def test_knowledge_graph_syncs_from_chain_reader():
    from knowledge_graph import TumorKnowledgeGraph
    from chain.intel_reader import IntelPinData

    kg = TumorKnowledgeGraph(domain_size=600.0)

    class Reader:
        def fetch_active_intel_pins(self):
            return [
                IntelPinData(
                    pin_id=1,
                    x=310,
                    y=320,
                    pin_type="HYPOXIC_CLUSTER",
                    pin_type_code=0,
                    reporter="0x0000000000000000000000000000000000000001",
                    priority=8,
                    confirmations=2,
                    timestamp=100,
                )
            ]

    imported = kg.sync_from_chain(Reader())
    nearby = kg.get_nearby_intel((10, 20), radius=1.0)

    assert imported == 1
    assert nearby[0]["pin_id"] == 1
    assert nearby[0]["priority"] == 8


def test_knowledge_graph_export_to_ipfs_returns_hash_without_backend():
    from knowledge_graph import TumorKnowledgeGraph

    kg = TumorKnowledgeGraph(domain_size=100.0)
    kg.add_intel_pin(1, (10, 20), "test", 5, -1, -1)

    result = kg.export_to_ipfs()

    assert result["ok"] in {True, False}
    assert isinstance(result["artifact_hash"], str)
    assert len(result["artifact_hash"]) == 64


def test_queen_applies_top_chain_strategy_when_read_flag_enabled(monkeypatch, small_model=None):
    monkeypatch.setenv("CHAIN_READ_ENABLED", "true")
    from nanobot_simulation import QueenNanobot, TumorNanobotModel

    class Consumer:
        def get_top_strategies(self, n=1):
            class Strategy:
                worker_params = {"exploration_bias": 0.1, "speed_multiplier": 1.4}
                run_hash = "0x" + "11" * 32
            return [Strategy()]

    model = TumorNanobotModel(
        domain_size=200.0,
        voxel_size=20.0,
        n_nanobots=1,
        tumor_radius=80.0,
        agent_type="heuristic",
        with_queen=False,
        use_llm_queen=False,
    )

    queen = QueenNanobot(model=model, use_llm=False, experience_consumer=Consumer())

    assert queen.worker_params["exploration_bias"] == 0.1
    assert queen.worker_params["speed_multiplier"] == 1.4
    assert queen.selected_chain_strategy == "0x" + "11" * 32


def test_model_syncs_knowledge_graph_from_chain_when_read_flag_enabled(monkeypatch):
    monkeypatch.setenv("CHAIN_READ_ENABLED", "true")
    from nanobot_simulation import TumorNanobotModel
    from chain.intel_reader import IntelPinData

    class Reader:
        def fetch_active_intel_pins(self):
            return [
                IntelPinData(
                    pin_id=42,
                    x=200,
                    y=200,
                    pin_type="TARGET_ACQUIRED",
                    pin_type_code=5,
                    reporter="0x0000000000000000000000000000000000000001",
                    priority=10,
                    confirmations=1,
                    timestamp=100,
                )
            ]

    model = TumorNanobotModel(
        domain_size=200.0,
        voxel_size=20.0,
        n_nanobots=1,
        tumor_radius=80.0,
        agent_type="heuristic",
        with_queen=False,
        chain_intel_reader=Reader(),
    )

    assert model.chain_sync_summary == {"imported_intel_pins": 1}
    assert model.knowledge_graph.get_nearby_intel((100, 100), radius=1.0)[0]["pin_id"] == 42
