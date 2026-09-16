"""Tests for backend/visualize.py — mock-based, no display required."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.visualize import render_kill_rate_chart, render_pheromone_heatmap


def _make_microenv(shape=(10, 10), substrate_name="trail"):
    """Return a mock Microenvironment with a fake 2-D concentration field."""
    substrate = MagicMock()
    substrate.concentration = np.random.rand(*shape)
    microenv = MagicMock()
    microenv.get_substrate.side_effect = lambda name: substrate if name == substrate_name else None
    return microenv, substrate


class TestRenderPheromoneHeatmap:
    def test_creates_png_file(self, tmp_path):
        microenv, _ = _make_microenv()
        out = tmp_path / "heatmap.png"
        result = render_pheromone_heatmap(microenv, out)
        assert result.exists()
        assert result.suffix == ".png"

    def test_file_is_non_empty(self, tmp_path):
        microenv, _ = _make_microenv()
        out = tmp_path / "heatmap.png"
        render_pheromone_heatmap(microenv, out)
        assert out.stat().st_size > 0

    def test_unknown_substrate_raises(self, tmp_path):
        microenv, _ = _make_microenv()
        with pytest.raises(ValueError, match="not found"):
            render_pheromone_heatmap(microenv, tmp_path / "x.png", substrate_name="no_such")

    def test_3d_field_uses_first_slice(self, tmp_path):
        substrate = MagicMock()
        substrate.concentration = np.random.rand(10, 10, 3)
        microenv = MagicMock()
        microenv.get_substrate.return_value = substrate
        out = tmp_path / "heatmap3d.png"
        render_pheromone_heatmap(microenv, out)
        assert out.exists()

    def test_custom_title_accepted(self, tmp_path):
        microenv, _ = _make_microenv()
        out = tmp_path / "titled.png"
        render_pheromone_heatmap(microenv, out, title="My Custom Title")
        assert out.exists()


class TestRenderKillRateChart:
    def test_creates_png_file(self, tmp_path):
        results = [{"run_id": "A", "kill_rate": 0.3}, {"run_id": "B", "kill_rate": 0.5}]
        out = tmp_path / "chart.png"
        result = render_kill_rate_chart(results, out)
        assert result.exists()
        assert result.suffix == ".png"

    def test_file_is_non_empty(self, tmp_path):
        results = [{"run_id": "X", "kill_rate": 0.1}]
        out = tmp_path / "chart.png"
        render_kill_rate_chart(results, out)
        assert out.stat().st_size > 0

    def test_empty_list_raises(self, tmp_path):
        with pytest.raises(ValueError, match="empty"):
            render_kill_rate_chart([], tmp_path / "chart.png")
