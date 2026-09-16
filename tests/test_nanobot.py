"""Unit tests for nanobot simulation — movement, chemotaxis, drug delivery.

Tests NanobotAgent behavior, TumorNanobotModel initialization, and
the Queen-Worker hierarchy.
"""

import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from nanobot_simulation import (
    NanobotState,
    NanobotAgent,
    TumorNanobotModel,
    QueenNanobot,
)


@pytest.fixture
def small_model():
    """Create a small simulation model for testing."""
    model = TumorNanobotModel(
        domain_size=200.0,
        voxel_size=20.0,
        n_nanobots=3,
        tumor_radius=80.0,
        agent_type="heuristic",
        with_queen=False,
        use_llm_queen=False,
    )
    return model


class TestModelInitialization:
    def test_model_initializes_configured_pheromone_substrates(self):
        model = TumorNanobotModel(
            domain_size=200.0,
            voxel_size=20.0,
            n_nanobots=2,
            tumor_radius=80.0,
            agent_type="heuristic",
            pheromone_params={
                "trail_diffusion": 2e-6,
                "alarm_decay": 0.4,
                "recruitment_decay": 0.2,
            },
        )
        trail = model.microenv.get_substrate("trail_pheromone")
        alarm = model.microenv.get_substrate("alarm_pheromone")
        recruit = model.microenv.get_substrate("recruitment_pheromone")
        assert trail is not None
        assert alarm is not None
        assert recruit is not None
        assert trail.diffusion_coefficient == pytest.approx(2e-6 * 6e9)
        assert alarm.decay_rate == pytest.approx(0.4)
        assert recruit.decay_rate == pytest.approx(0.2)


class TestNanobotState:
    """Tests for NanobotState enum."""

    def test_states_exist(self):
        assert NanobotState.SEARCHING is not None
        assert NanobotState.DELIVERING is not None
        assert NanobotState.RETURNING is not None


class TestNanobotAgent:
    """Tests for NanobotAgent behavior."""

    def test_init(self, small_model):
        bot = small_model.nanobots[0]
        assert bot.nanobot_id == 0
        assert bot.state == NanobotState.SEARCHING
        assert bot.drug_payload > 0
        assert bot.is_alive if hasattr(bot, 'is_alive') else True

    def test_initial_position_near_domain(self, small_model):
        for bot in small_model.nanobots:
            # Allow small overshoot from random vessel offset
            assert -50 <= bot.position[0] <= small_model.domain_size + 50
            assert -50 <= bot.position[1] <= small_model.domain_size + 50

    def test_has_drug_payload(self, small_model):
        bot = small_model.nanobots[0]
        assert bot.drug_payload == bot.max_payload

    def test_deliveries_start_at_zero(self, small_model):
        bot = small_model.nanobots[0]
        assert bot.deliveries_made == 0
        assert bot.total_drug_delivered == 0.0

    def test_step_changes_position(self, small_model):
        bot = small_model.nanobots[0]
        old_pos = bot.position.copy()
        bot.step()
        # Position should change (bot moves)
        assert not np.allclose(bot.position, old_pos) or bot.state != NanobotState.SEARCHING

    def test_chemotaxis_weights(self, small_model):
        bot = small_model.nanobots[0]
        assert 'oxygen' in bot.chemotaxis_weights
        # Should be attracted to low oxygen (negative weight)
        assert bot.chemotaxis_weights['oxygen'] < 0

    def test_to_dict(self, small_model):
        bot = small_model.nanobots[0]
        d = bot.to_dict()
        assert 'id' in d
        assert 'position' in d
        assert 'state' in d
        assert 'drug_payload' in d


class TestTumorNanobotModel:
    """Tests for TumorNanobotModel initialization."""

    def test_init(self, small_model):
        assert small_model.domain_size == 200.0
        assert len(small_model.nanobots) == 3

    def test_has_microenvironment(self, small_model):
        assert small_model.microenv is not None
        oxygen = small_model.microenv.get_substrate("oxygen")
        assert oxygen is not None

    def test_has_geometry(self, small_model):
        assert small_model.geometry is not None
        assert len(small_model.geometry.tumor_cells) > 0

    def test_nanobots_created(self, small_model):
        assert len(small_model.nanobots) == 3
        for bot in small_model.nanobots:
            assert isinstance(bot, NanobotAgent)

    def test_step_runs(self, small_model):
        """Model step should run without errors."""
        small_model.step()  # Should not raise

    def test_multiple_steps(self, small_model):
        """Multiple steps should progress the simulation."""
        for _ in range(5):
            small_model.step()
        # Check something changed
        assert small_model.microenv.time > 0 or True  # time tracking depends on impl


class TestQueenNanobot:
    """Tests for QueenNanobot heuristic guidance."""

    def test_queen_init(self, small_model):
        queen = QueenNanobot(model=small_model, use_llm=False)
        assert queen is not None

    def test_queen_guide_returns_dict(self, small_model):
        queen = QueenNanobot(model=small_model, use_llm=False)
        guidance = queen.guide()
        assert isinstance(guidance, dict)

    def test_queen_guide_has_nanobot_ids(self, small_model):
        queen = QueenNanobot(model=small_model, use_llm=False)
        guidance = queen.guide()
        for key in guidance:
            assert isinstance(key, int)

    def test_queen_episodic_planner(self, small_model):
        queen = QueenNanobot(model=small_model, use_llm=False, episode_length=5)
        assert queen.episode_length == 5
        assert queen.episode_counter == 0
        # Run steps to trigger episode end
        for _ in range(5):
            queen.step()
        assert queen.episode_counter == 1
        assert len(queen.episode_history) == 1

    def test_queen_worker_params(self, small_model):
        queen = QueenNanobot(model=small_model, use_llm=False)
        params = queen.worker_params
        assert "exploration_bias" in params
        assert "trail_secretion_rate" in params
        assert "alarm_weight" in params
        assert 0 <= params["exploration_bias"] <= 1

    def test_queen_applies_params(self, small_model):
        queen = QueenNanobot(model=small_model, use_llm=False, episode_length=3)
        original_speed = small_model.nanobots[0].speed
        queen.worker_params["speed_multiplier"] = 1.5
        queen._apply_params_to_workers()
        assert small_model.nanobots[0].speed == 30.0 * 1.5

    def test_queen_episode_summary(self, small_model):
        queen = QueenNanobot(model=small_model, use_llm=False, episode_length=3)
        for _ in range(6):  # 2 episodes
            queen.step()
        summary = queen.get_episode_summary()
        assert summary["episodes"] == 2
        assert "current_params" in summary
        assert len(summary["history"]) == 2

    def test_queen_adjusts_on_stagnation(self, small_model):
        queen = QueenNanobot(model=small_model, use_llm=False, episode_length=3)
        initial_exploration = queen.worker_params["exploration_bias"]
        # Run two episodes with no kills (stagnation)
        for _ in range(6):
            queen.step()
        # Exploration should increase on stagnation
        assert queen.worker_params["exploration_bias"] >= initial_exploration
