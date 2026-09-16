"""SimulationConfig — pydantic schema for nanobot simulation parameters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PheromoneParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trail_diffusion: float = Field(default=1e-6, gt=0, description="Trail pheromone diffusion coefficient")
    alarm_diffusion: float = Field(default=5e-6, gt=0, description="Alarm pheromone diffusion coefficient")
    recruitment_diffusion: float = Field(default=2e-6, gt=0, description="Recruitment pheromone diffusion coefficient")
    trail_decay: float = Field(default=0.0693, gt=0, description="Trail pheromone decay rate (ln2/10min)")
    alarm_decay: float = Field(default=0.231, gt=0, description="Alarm pheromone decay rate (ln2/3min)")
    recruitment_decay: float = Field(default=0.099, gt=0, description="Recruitment pheromone decay rate (ln2/7min)")


class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    num_bots: int = Field(default=10, ge=1, le=1000, description="Number of nanobots")
    grid_size: int = Field(default=60, ge=2, le=500, description="Grid size (N×N voxels)")
    steps: int = Field(default=100, ge=1, le=10000, description="Number of simulation steps")
    pheromone_params: PheromoneParams = Field(default_factory=PheromoneParams)
    queen_enabled: bool = Field(default=False, description="Enable Queen agent for strategic coordination")
    seed: Optional[int] = Field(default=None, description="Random seed for reproducibility")

    @field_validator("num_bots")
    @classmethod
    def num_bots_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("num_bots must be at least 1")
        return v

    @field_validator("grid_size")
    @classmethod
    def grid_size_must_be_at_least_two(cls, v: int) -> int:
        if v < 2:
            raise ValueError("grid_size must be at least 2")
        return v

    def to_model_kwargs(self) -> Dict[str, Any]:
        """Return kwargs suitable for TumorNanobotModel constructor."""
        voxel_size = 10.0
        domain_size = float(self.grid_size) * voxel_size
        tumor_radius = min(domain_size * 0.33, 200.0)
        return {
            "n_nanobots": self.num_bots,
            "domain_size": domain_size,
            "voxel_size": voxel_size,
            "tumor_radius": tumor_radius,
            "with_queen": self.queen_enabled,
            # This small reproducible config has no paid/model policy fields.
            "agent_type": "Rule-Based",
            "use_llm_queen": False,
            "pheromone_params": self.pheromone_params.model_dump(),
            "seed": self.seed,
        }


def load_config(path: str | Path) -> SimulationConfig:
    """Load a SimulationConfig from a JSON file."""
    data = json.loads(Path(path).read_text())
    return SimulationConfig(**data)


def save_config(config: SimulationConfig, path: str | Path) -> None:
    """Save a SimulationConfig to a JSON file."""
    Path(path).write_text(config.model_dump_json(indent=2))
