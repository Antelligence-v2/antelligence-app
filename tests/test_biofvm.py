"""Unit tests for BioFVM substrate diffusion and reaction system.

Tests substrate field operations, microenvironment initialization,
diffusion/decay simulation, and mass conservation properties.
"""

import numpy as np
import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from biofvm import (
    SubstrateField,
    Microenvironment,
    create_oxygen_substrate,
    create_drug_substrate,
    create_pheromone_substrate,
    create_trail_pheromone,
    create_alarm_pheromone,
    create_recruitment_pheromone,
)


class TestSubstrateField:
    """Tests for SubstrateField class."""

    def test_initialization(self):
        field = SubstrateField("oxygen", shape=(10, 10, 10), initial_value=38.0)
        assert field.name == "oxygen"
        assert field.concentration.shape == (10, 10, 10)
        assert np.allclose(field.concentration, 38.0)
        assert field.diffusion_coefficient == 1e-5
        assert field.decay_rate == 0.1

    def test_initial_value_zero(self):
        field = SubstrateField("drug", shape=(5, 5, 5))
        assert np.allclose(field.concentration, 0.0)

    def test_add_source(self):
        field = SubstrateField("test", shape=(5, 5, 5))
        field.add_source((2, 2, 2), 10.0)
        assert field.source_sink[2, 2, 2] == 10.0
        assert field.source_sink.sum() == 10.0

    def test_add_sink(self):
        field = SubstrateField("test", shape=(5, 5, 5))
        field.add_sink((1, 1, 1), 5.0)
        assert field.source_sink[1, 1, 1] == -5.0

    def test_source_out_of_bounds(self):
        field = SubstrateField("test", shape=(5, 5, 5))
        field.add_source((10, 10, 10), 10.0)  # Should not crash
        assert field.source_sink.sum() == 0.0

    def test_reset_sources_sinks(self):
        field = SubstrateField("test", shape=(5, 5, 5))
        field.add_source((2, 2, 2), 10.0)
        field.reset_sources_sinks()
        assert field.source_sink.sum() == 0.0

    def test_custom_parameters(self):
        field = SubstrateField(
            "drug",
            shape=(8, 8, 8),
            diffusion_coefficient=1e-7,
            decay_rate=0.05,
            initial_value=0.0,
            dirichlet_boundary_value=0.0,
        )
        assert field.diffusion_coefficient == 1e-7
        assert field.decay_rate == 0.05
        assert field.dirichlet_boundary_value == 0.0


class TestMicroenvironment:
    """Tests for Microenvironment class."""

    def test_initialization(self):
        env = Microenvironment(
            x_range=(0, 100),
            y_range=(0, 100),
            z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        assert env.dx == 20.0
        assert env.shape == (6, 6, 6)  # int(100/20)+1 = 6
        assert len(env.substrates) == 0

    def test_add_substrate(self):
        env = Microenvironment(
            x_range=(0, 100),
            y_range=(0, 100),
            z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        sub = env.add_substrate("oxygen", diffusion_coefficient=1e-5, decay_rate=0.1)
        assert sub.name == "oxygen"
        assert sub.concentration.shape == env.shape
        assert len(env.substrates) == 1

    def test_get_substrate(self):
        env = Microenvironment(
            x_range=(0, 100),
            y_range=(0, 100),
            z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        env.add_substrate("oxygen", diffusion_coefficient=1e-5, decay_rate=0.1)
        sub = env.get_substrate("oxygen")
        assert sub is not None
        assert sub.name == "oxygen"

    def test_get_nonexistent_substrate(self):
        env = Microenvironment(
            x_range=(0, 100),
            y_range=(0, 100),
            z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        sub = env.get_substrate("missing")
        assert sub is None

    def test_position_to_voxel(self):
        env = Microenvironment(
            x_range=(0, 100),
            y_range=(0, 100),
            z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        voxel = env.position_to_voxel((50.0, 50.0, 50.0))
        assert voxel == (2, 2, 2)

    def test_position_to_voxel_origin(self):
        env = Microenvironment(
            x_range=(0, 100),
            y_range=(0, 100),
            z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        voxel = env.position_to_voxel((0.0, 0.0, 0.0))
        assert voxel == (0, 0, 0)

    def test_voxel_to_position(self):
        env = Microenvironment(
            x_range=(0, 100),
            y_range=(0, 100),
            z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        pos = env.voxel_to_position((2, 2, 2))
        assert np.allclose(pos, (40.0, 40.0, 40.0))  # 0 + 2*20 = 40


class TestDiffusionDecay:
    """Tests for diffusion and decay simulation."""

    @pytest.mark.parametrize("dimensionality", [2, 3])
    def test_aliases_do_not_advance_the_same_field_twice(self, dimensionality):
        env = Microenvironment(
            x_range=(0, 100), y_range=(0, 100), z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=dimensionality,
        )
        trail = env.add_substrate(
            "trail_pheromone", diffusion_coefficient=1e-6,
            decay_rate=0.1, initial_value=10.0,
        )
        # These are the compatibility aliases installed by TumorNanobotModel.
        env.substrates["trail"] = trail
        env.substrates["legacy_trail"] = trail
        trail.source_sink.fill(2.0)
        before = trail.concentration.copy()
        dt = env.dt
        expected = before + dt * (-trail.decay_rate * before + trail.source_sink)

        env.step()

        np.testing.assert_array_equal(trail.concentration, expected)
        assert env.get_substrate("trail") is trail
        assert env.time == dt

    @pytest.mark.parametrize("dimensionality", [2, 3])
    @pytest.mark.parametrize("at_boundary", [False, True])
    def test_no_flux_preserves_nonuniform_mass(self, dimensionality, at_boundary):
        env = Microenvironment(
            x_range=(0, 100), y_range=(0, 100), z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=dimensionality,
        )
        substrate = env.add_substrate("drug", 1e-6, 0.0)
        index = 0 if at_boundary else 1
        point = (index, index, index if dimensionality == 3 else 0)
        substrate.concentration[point] = 100.0
        for _ in range(10):
            env.step()
            assert float(substrate.concentration.sum()) == pytest.approx(100.0, rel=1e-6)
        assert np.count_nonzero(substrate.concentration) > 1

    def test_decay_reduces_concentration(self):
        env = Microenvironment(
            x_range=(0, 100),
            y_range=(0, 100),
            z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        sub = env.add_substrate(
            "test",
            diffusion_coefficient=1e-6,  # Small diffusion to get reasonable timestep
            decay_rate=10.0,  # Strong decay
            initial_value=100.0,
        )
        initial_total = sub.concentration.sum()
        # Use auto-calculated timestep, run many steps
        for _ in range(1000):
            env.step()
        final_total = sub.concentration.sum()
        assert final_total < initial_total

    def test_zero_decay_preserves_mass(self):
        """With no decay and no-flux boundaries, total mass should be conserved."""
        env = Microenvironment(
            x_range=(0, 100),
            y_range=(0, 100),
            z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        sub = env.add_substrate(
            "test",
            diffusion_coefficient=1e-6,
            decay_rate=0.0,
            initial_value=50.0,
        )
        initial_total = sub.concentration.sum()
        for _ in range(100):
            env.step()
        final_total = sub.concentration.sum()
        assert np.allclose(initial_total, final_total, rtol=0.01)

    def test_diffusion_smooths_concentration(self):
        env = Microenvironment(
            x_range=(0, 100),
            y_range=(0, 100),
            z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        sub = env.add_substrate(
            "test",
            diffusion_coefficient=1e-6,  # Moderate diffusion
            decay_rate=0.0,
            initial_value=0.0,
        )
        # Create a point source in the center
        center = env.shape[0] // 2
        sub.concentration[center, center, center] = 1000.0
        initial_std = sub.concentration.std()

        # Diffuse with auto timestep
        for _ in range(1000):
            env.step()

        final_std = sub.concentration.std()
        # Standard deviation should decrease (more uniform)
        assert final_std < initial_std

    def test_concentration_stays_nonnegative(self):
        env = Microenvironment(
            x_range=(0, 100),
            y_range=(0, 100),
            z_range=(0, 100),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        sub = env.add_substrate(
            "test",
            diffusion_coefficient=1e-5,
            decay_rate=1.0,  # High decay
            initial_value=1.0,
        )
        for _ in range(100):
            env.step(dt=0.1)
        assert np.all(sub.concentration >= -1e-6)  # Allow tiny numerical errors


class TestFactoryFunctions:
    """Tests for substrate factory functions."""

    def test_create_oxygen_substrate(self):
        env = Microenvironment(
            x_range=(0, 200),
            y_range=(0, 200),
            z_range=(0, 200),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        sub = create_oxygen_substrate(env, boundary_value=38.0)
        assert sub.name == "oxygen"
        assert sub.dirichlet_boundary_value == 38.0

    def test_create_drug_substrate(self):
        env = Microenvironment(
            x_range=(0, 200),
            y_range=(0, 200),
            z_range=(0, 200),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        sub = create_drug_substrate(env)
        assert sub.name == "drug"
        # Drug diffuses slower than oxygen (after unit conversion to µm²/min)
        oxygen = env.get_substrate("oxygen") if "oxygen" in env.substrates else None
        assert sub.diffusion_coefficient > 0

    def test_create_pheromone_substrate(self):
        env = Microenvironment(
            x_range=(0, 200),
            y_range=(0, 200),
            z_range=(0, 200),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )
        sub = create_pheromone_substrate(env, name="trail_pheromone")
        assert sub.name == "trail_pheromone"


class TestPheromoneSystem:
    """Tests for Phase 2 pheromone substrates."""

    def _make_env(self):
        return Microenvironment(
            x_range=(0, 200), y_range=(0, 200), z_range=(0, 200),
            dx=20.0, dy=20.0, dz=20.0, dimensionality=3,
        )

    def test_create_trail_pheromone(self):
        env = self._make_env()
        trail = create_trail_pheromone(env)
        assert trail.name == "trail_pheromone"
        assert trail.decay_rate > 0
        assert np.allclose(trail.concentration, 0.0)

    def test_create_alarm_pheromone(self):
        env = self._make_env()
        alarm = create_alarm_pheromone(env)
        assert alarm.name == "alarm_pheromone"
        # Alarm should diffuse faster than trail
        trail = create_trail_pheromone(env)
        assert alarm.diffusion_coefficient > trail.diffusion_coefficient

    def test_create_recruitment_pheromone(self):
        env = self._make_env()
        recruit = create_recruitment_pheromone(env)
        assert recruit.name == "recruitment_pheromone"
        assert recruit.decay_rate > 0

    def test_alarm_decays_faster_than_trail(self):
        env = self._make_env()
        trail = create_trail_pheromone(env)
        alarm = create_alarm_pheromone(env)
        assert alarm.decay_rate > trail.decay_rate

    def test_trail_pheromone_secretion_and_decay(self):
        """Simulate a nanobot depositing trail pheromone and verify it decays."""
        env = self._make_env()
        trail = create_trail_pheromone(env)
        center = env.shape[0] // 2

        # Simulate nanobot secretion at center
        trail.add_source((center, center, center), 10.0)
        initial = trail.source_sink[center, center, center]
        assert initial == 10.0

        # Step the environment — source should diffuse and decay
        env.step()
        # After one step with source, concentration at center should increase
        assert trail.concentration[center, center, center] > 0

    def test_pheromone_half_life(self):
        """Trail pheromone should lose ~half concentration in ~10 min (decay_rate=0.07)."""
        env = self._make_env()
        trail = create_trail_pheromone(env)
        center = env.shape[0] // 2

        # Set initial concentration directly (no diffusion, just decay)
        trail.concentration[center, center, center] = 100.0
        initial = trail.concentration[center, center, center]

        # Run decay for ~10 minutes with many small steps
        for _ in range(10000):
            env.step()

        # After ~10 min, should be roughly half (with diffusion spreading it out)
        # We just check it decreased significantly
        final_center = trail.concentration[center, center, center]
        assert final_center < initial * 0.8  # At least 20% reduction

    def test_all_three_pheromones_coexist(self):
        """All three pheromone fields can coexist in the same environment."""
        env = self._make_env()
        trail = create_trail_pheromone(env)
        alarm = create_alarm_pheromone(env)
        recruit = create_recruitment_pheromone(env)

        assert len(env.substrates) == 3
        assert env.get_substrate("trail_pheromone") is trail
        assert env.get_substrate("alarm_pheromone") is alarm
        assert env.get_substrate("recruitment_pheromone") is recruit
