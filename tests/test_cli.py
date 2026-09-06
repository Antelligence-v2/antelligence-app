"""Tests for backend/cli.py."""

import json
import subprocess
import sys
from argparse import Namespace
from unittest.mock import MagicMock, patch


# We run the CLI as: python -m backend.cli <subcommand>
CLI = [sys.executable, "-m", "backend.cli"]


def _fake_model(**kwargs):
    """Return a lightweight mock TumorNanobotModel."""
    model = MagicMock()
    model.step_count = 3
    model.metrics = {
        "total_deliveries": 1,
        "total_drug_delivered": 5.0,
        "cells_killed": 0,
        "hypoxic_cells": 2,
        "viable_cells": 40,
        "necrotic_cells": 0,
        "apoptotic_cells": 0,
        "total_api_calls": 0,
        "food_collected_by_llm": 0,
        "food_collected_by_rule": 1,
        "deliveries_by_llm": 0,
        "deliveries_by_rule": 1,
    }
    model.geometry.get_tumor_statistics.return_value = {"total_cells": 50, "living_cells": 50}
    return model


class TestCLIHelp:
    def test_help_exits_zero(self):
        result = subprocess.run(CLI + ["--help"], capture_output=True, text=True)
        assert result.returncode == 0

    def test_simulate_help(self):
        result = subprocess.run(CLI + ["simulate", "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "steps" in result.stdout

    def test_benchmark_help(self):
        result = subprocess.run(CLI + ["benchmark", "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "runs" in result.stdout


class TestCLISimulate:
    def test_simulate_writes_json_output(self, tmp_path):
        out = tmp_path / "results.json"
        from backend.cli import cmd_simulate

        args = Namespace(steps=2, bots=1, grid_size=5, seed=7, output=str(out))
        with patch("backend.cli.TumorNanobotModel", side_effect=_fake_model):
            cmd_simulate(args)

        data = json.loads(out.read_text())
        assert data["config"] == {"num_bots": 1, "steps": 2, "grid_size": 5, "seed": 7}
        assert "bots" not in data["config"]
        assert data["metrics"]["step_count"] == 3

    def test_simulate_no_output_prints_json(self):
        """CLI without --output should print JSON to stdout."""
        with patch("backend.cli.TumorNanobotModel", side_effect=_fake_model):
            import io
            import sys
            from backend.cli import cmd_simulate

            args = Namespace(steps=2, bots=1, grid_size=5, seed=None, output=None)
            captured = io.StringIO()
            sys_stdout = sys.stdout
            sys.stdout = captured
            try:
                with patch("backend.cli.TumorNanobotModel", side_effect=_fake_model):
                    cmd_simulate(args)
            finally:
                sys.stdout = sys_stdout

            out_text = captured.getvalue()
            data = json.loads(out_text)
            assert "metrics" in data
            assert "config" in data
            assert data["config"]["num_bots"] == 1
            assert "bots" not in data["config"]


class TestLocalCommandSafety:
    def test_simulate_explicit_local_policy_and_seed(self, capsys):
        from backend.cli import cmd_simulate

        args = Namespace(steps=1, bots=1, grid_size=5, seed=7, output=None)
        with patch("backend.cli.TumorNanobotModel", side_effect=_fake_model) as factory:
            cmd_simulate(args)
        assert factory.call_args.kwargs["agent_type"] == "Rule-Based"
        assert factory.call_args.kwargs["use_llm_queen"] is False
        assert factory.call_args.kwargs["seed"] == 7
        json.loads(capsys.readouterr().out)

    def test_benchmark_explicit_local_policy_and_json(self, capsys):
        from backend.cli import cmd_benchmark

        args = Namespace(runs=2, steps=1, bots=1, grid_size=5, output=None)
        with patch("backend.cli.TumorNanobotModel", side_effect=_fake_model) as factory:
            cmd_benchmark(args)
        assert factory.call_count == 2
        assert [c.kwargs["seed"] for c in factory.call_args_list] == [0, 1]
        assert all(c.kwargs["agent_type"] == "Rule-Based" for c in factory.call_args_list)
        data = json.loads(capsys.readouterr().out)
        assert len(data["results"]) == 2

    def test_real_command_stdout_is_json(self):
        result = subprocess.run(
            CLI + ["simulate", "--steps", "1", "--bots", "1", "--grid-size", "5", "--seed", "7"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["metrics"]["step_count"] == 1
        assert data["metrics"]["total_api_calls"] == 0


class TestCLILeaderboard:
    def test_leaderboard_offline_graceful(self):
        """leaderboard command should not crash when blockchain is unavailable."""
        result = subprocess.run(
            CLI + ["leaderboard", "--limit", "5"],
            capture_output=True,
            text=True,
        )
        # Should exit 0 (graceful fallback), not crash with exception exit code 1.
        assert result.returncode == 0
