"""Unit tests for tumor environment — cells, geometry, and initialization.

Tests TumorCell lifecycle, TumorGeometry generation, voxel grid setup,
and oxygen gradient properties.
"""

import numpy as np
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from tumor_environment import (
    CellPhase,
    CellType,
    TumorCell,
    TumorGeometry,
    VesselPoint,
    create_simple_tumor_environment,
)


class TestTumorCell:
    """Tests for TumorCell class."""

    def test_init_defaults(self):
        cell = TumorCell(cell_id=1, position=(50.0, 50.0, 0.0))
        assert cell.cell_id == 1
        assert cell.position == (50.0, 50.0, 0.0)
        assert cell.phase == CellPhase.VIABLE
        assert cell.cell_type == CellType.DIFFERENTIATED
        assert cell.is_alive is True
        assert cell.accumulated_drug == 0.0

    def test_init_stem_cell(self):
        cell = TumorCell(
            cell_id=2,
            position=(0.0, 0.0, 0.0),
            cell_type=CellType.STEM_CELL,
        )
        assert cell.cell_type == CellType.STEM_CELL
        # Stem cells should have different resistance than differentiated
        diff_cell = TumorCell(cell_id=3, position=(0.0, 0.0, 0.0), cell_type=CellType.DIFFERENTIATED)
        assert cell.resistance_level != diff_cell.resistance_level

    def test_oxygen_status_viable(self):
        cell = TumorCell(cell_id=1, position=(0.0, 0.0, 0.0))
        cell.update_oxygen_status(oxygen_concentration=38.0, dt=1.0)
        assert cell.phase == CellPhase.VIABLE
        assert cell.is_alive is True

    def test_oxygen_status_hypoxic(self):
        cell = TumorCell(cell_id=1, position=(0.0, 0.0, 0.0))
        # Low oxygen should trigger hypoxia
        cell.update_oxygen_status(oxygen_concentration=1.0, dt=1.0)
        assert cell.phase == CellPhase.HYPOXIC

    def test_oxygen_status_necrotic(self):
        cell = TumorCell(cell_id=1, position=(0.0, 0.0, 0.0))
        # Prolonged severe hypoxia → necrosis
        for _ in range(1000):
            cell.update_oxygen_status(oxygen_concentration=0.5, dt=1.0)
        assert cell.phase == CellPhase.NECROTIC
        assert cell.is_alive is False

    def test_drug_accumulation(self):
        cell = TumorCell(cell_id=1, position=(0.0, 0.0, 0.0))
        initial_drug = cell.accumulated_drug
        cell.absorb_drug(drug_concentration=10.0, dt=1.0)
        assert cell.accumulated_drug > initial_drug

    def test_drug_kills_cell(self):
        cell = TumorCell(cell_id=1, position=(0.0, 0.0, 0.0))
        # Give massive drug dose
        killed = cell.accumulate_drug(cell.lethal_drug_dose * 2)
        assert killed is True
        assert cell.is_alive is False

    def test_cell_division(self):
        cell = TumorCell(cell_id=1, position=(0.0, 0.0, 0.0))
        # Accumulate enough growth for division
        cell.growth_progress = cell.division_threshold + 1
        daughter = cell.divide(new_cell_id=100)
        assert daughter is not None
        assert daughter.cell_id == 100
        assert daughter.generation == cell.generation + 1

    def test_dead_cell_cannot_divide(self):
        cell = TumorCell(cell_id=1, position=(0.0, 0.0, 0.0))
        cell.is_alive = False
        cell.growth_progress = cell.division_threshold + 1
        daughter = cell.divide(new_cell_id=100)
        assert daughter is None

    def test_oxygen_consumption(self):
        cell = TumorCell(cell_id=1, position=(0.0, 0.0, 0.0))
        consumption = cell.get_oxygen_consumption()
        assert consumption > 0

    def test_dead_cell_no_consumption(self):
        cell = TumorCell(cell_id=1, position=(0.0, 0.0, 0.0))
        cell.is_alive = False
        consumption = cell.get_oxygen_consumption()
        assert consumption == 0

    def test_to_dict(self):
        cell = TumorCell(cell_id=1, position=(10.0, 20.0, 30.0))
        d = cell.to_dict()
        assert d["id"] == 1
        assert d["position"] == (10.0, 20.0, 30.0)
        assert "phase" in d
        assert "is_alive" in d


class TestTumorGeometry:
    """Tests for TumorGeometry class."""

    def test_init(self):
        geo = TumorGeometry(
            center=(100.0, 100.0, 0.0),
            tumor_radius=200.0,
            necrotic_core_radius=50.0,
        )
        assert geo.center == (100.0, 100.0, 0.0)
        assert geo.tumor_radius == 200.0
        assert len(geo.tumor_cells) == 0

    def test_generate_circular_tumor(self):
        geo = TumorGeometry(
            center=(100.0, 100.0, 0.0),
            tumor_radius=100.0,
        )
        geo.generate_circular_tumor(cell_density=0.001, dimensionality=2)
        assert len(geo.tumor_cells) > 0
        # All cells should be within tumor radius
        for cell in geo.tumor_cells:
            dist = np.sqrt(
                (cell.position[0] - 100.0) ** 2
                + (cell.position[1] - 100.0) ** 2
            )
            assert dist <= 100.0 + 10.0  # Allow cell radius margin

    def test_tumor_has_mixed_types(self):
        geo = TumorGeometry(
            center=(100.0, 100.0, 0.0),
            tumor_radius=150.0,
            necrotic_core_radius=30.0,
        )
        geo.generate_circular_tumor(cell_density=0.001, dimensionality=2)
        types = {cell.cell_type for cell in geo.tumor_cells}
        assert len(types) > 1  # Should have multiple cell types

    def test_get_living_cells(self):
        geo = TumorGeometry(center=(0.0, 0.0, 0.0), tumor_radius=100.0)
        geo.generate_circular_tumor(cell_density=0.001, dimensionality=2)
        living = geo.get_living_cells()
        assert len(living) == len(geo.tumor_cells)  # Initially all alive

    def test_get_tumor_statistics(self):
        geo = TumorGeometry(center=(0.0, 0.0, 0.0), tumor_radius=100.0)
        geo.generate_circular_tumor(cell_density=0.001, dimensionality=2)
        stats = geo.get_tumor_statistics()
        assert "total_cells" in stats
        assert "living_cells" in stats
        assert stats["total_cells"] > 0
        assert stats["living_cells"] == stats["total_cells"]

    def test_is_inside_tumor(self):
        geo = TumorGeometry(center=(100.0, 100.0, 0.0), tumor_radius=50.0)
        assert geo.is_inside_tumor((100.0, 100.0, 0.0)) == True
        assert geo.is_inside_tumor((300.0, 300.0, 0.0)) == False

    def test_is_inside_necrotic_core(self):
        geo = TumorGeometry(
            center=(100.0, 100.0, 0.0),
            tumor_radius=200.0,
            necrotic_core_radius=50.0,
        )
        assert geo.is_inside_necrotic_core((100.0, 100.0, 0.0)) == True
        assert geo.is_inside_necrotic_core((180.0, 100.0, 0.0)) == False


class TestVesselPoint:
    """Tests for VesselPoint."""

    def test_init(self):
        v = VesselPoint(
            position=(50.0, 50.0, 0.0),
            oxygen_supply=38.0,
            supply_radius=50.0,
        )
        assert v.position == (50.0, 50.0, 0.0)
        assert v.supply_radius == 50.0

    def test_to_dict(self):
        v = VesselPoint(position=(10.0, 20.0, 0.0))
        d = v.to_dict()
        assert d["position"] == (10.0, 20.0, 0.0)
        assert "oxygen_supply" in d


class TestFactoryFunctions:
    """Tests for environment factory functions."""

    def test_create_simple_tumor_environment(self):
        geo = create_simple_tumor_environment(
            tumor_radius=100.0,
            domain_size=400.0,
        )
        assert geo is not None
        assert len(geo.tumor_cells) > 0
