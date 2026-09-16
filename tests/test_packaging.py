"""The documented uv console command must exist after uv sync."""

from pathlib import Path
import subprocess
import sys


def test_installed_simulation_console_command():
    command = Path(sys.executable).parent / "antelligence"
    assert command.is_file(), "uv sync must install the documented antelligence command"
    result = subprocess.run([str(command), "simulate", "--help"], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "--steps" in result.stdout
    assert "--bots" in result.stdout


def test_installed_api_console_command():
    command = Path(sys.executable).parent / "antelligence-api"
    assert command.is_file(), "uv sync must install the documented antelligence-api command"
