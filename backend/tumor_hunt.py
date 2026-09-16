"""
Tumor Hunt v2 — Dynamic wave-based tumor cell spawning with LLM-brained nanobot hunters.

This mirrors the ant/food foraging paradigm:
  food    -> tumor cell
  ant     -> nanobot
  nest    -> reload station (edge of domain)
  pheromone trail -> same concept, marks paths to targets
"""
import numpy as np
import time
from typing import List, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field


class HuntState(Enum):
    SEARCHING = "searching"
    TARGETING = "targeting"
    DELIVERING = "delivering"
    RETURNING = "returning"
    RELOADING = "reloading"


@dataclass
class HuntCell:
    cell_id: int
    position: np.ndarray  # [x, y] in µm
    accumulated_drug: float = 0.0
    is_alive: bool = True
    wave: int = 0
    drug_kill_threshold: float = 3.0

    def accumulate_drug(self, amount: float) -> bool:
        """Returns True if cell is killed."""
        self.accumulated_drug += amount
        if self.accumulated_drug >= self.drug_kill_threshold:
            self.is_alive = False
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "id": self.cell_id,
            "position": self.position.tolist(),
            "accumulated_drug": round(self.accumulated_drug, 3),
            "is_alive": self.is_alive,
            "wave": self.wave
        }


@dataclass
class HuntNanobot:
    nanobot_id: int
    position: np.ndarray  # [x, y] in µm
    max_drug: float = 30.0
    drug_payload: float = 30.0
    speed: float = 40.0
    state: HuntState = HuntState.SEARCHING
    target: Optional[HuntCell] = None
    kills: int = 0
    is_llm: bool = True
    delivery_rate: float = 5.0
    _reload_station: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0]))

    def to_dict(self) -> dict:
        return {
            "id": self.nanobot_id,
            "position": self.position.tolist(),
            "state": self.state.value,
            "drug_payload": round(self.drug_payload, 2),
            "kills": self.kills,
            "is_llm": self.is_llm,
            "target_id": self.target.cell_id if self.target else None
        }


class PheromoneGrid:
    """Lightweight 2D pheromone grid. No biofvm dependency."""
    def __init__(self, domain_size: float, resolution: int = 30, decay_rate: float = 0.08):
        self.domain_size = domain_size
        self.resolution = resolution
        self.decay_rate = decay_rate
        self.cell_size = domain_size / resolution
        self.trail = np.zeros((resolution, resolution), dtype=np.float32)
        self.recruitment = np.zeros((resolution, resolution), dtype=np.float32)

    def _pos_to_idx(self, pos: np.ndarray) -> Tuple[int, int]:
        x = int(np.clip(pos[0] / self.cell_size, 0, self.resolution - 1))
        y = int(np.clip(pos[1] / self.cell_size, 0, self.resolution - 1))
        return x, y

    def deposit_trail(self, pos: np.ndarray, amount: float):
        x, y = self._pos_to_idx(pos)
        self.trail[x, y] = min(10.0, self.trail[x, y] + amount)

    def deposit_recruitment(self, pos: np.ndarray, amount: float):
        x, y = self._pos_to_idx(pos)
        self.recruitment[x, y] = min(10.0, self.recruitment[x, y] + amount)

    def get_trail(self, pos: np.ndarray) -> float:
        x, y = self._pos_to_idx(pos)
        return float(self.trail[x, y])

    def get_recruitment(self, pos: np.ndarray) -> float:
        x, y = self._pos_to_idx(pos)
        return float(self.recruitment[x, y])

    def gradient_toward(self, pos: np.ndarray, grid: np.ndarray) -> np.ndarray:
        """Return direction vector toward highest concentration in 3x3 neighborhood."""
        x, y = self._pos_to_idx(pos)
        best_dir = np.array([0.0, 0.0])
        best_val = -1.0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx = int(np.clip(x + dx, 0, self.resolution - 1))
                ny = int(np.clip(y + dy, 0, self.resolution - 1))
                val = grid[nx, ny]
                if val > best_val:
                    best_val = val
                    best_dir = np.array([float(dx), float(dy)])
        if best_val > 0.01 and np.linalg.norm(best_dir) > 0:
            return best_dir / np.linalg.norm(best_dir)
        return np.array([0.0, 0.0])

    def decay(self):
        self.trail *= (1 - self.decay_rate)
        self.recruitment *= (1 - self.decay_rate)
        np.clip(self.trail, 0, 10.0, out=self.trail)
        np.clip(self.recruitment, 0, 10.0, out=self.recruitment)

    def to_list(self, grid: np.ndarray) -> List[List[float]]:
        return grid.tolist()


class TumorHuntModel:
    """
    Dynamic tumor hunt simulation.
    Tumor cells spawn in waves. Nanobots (optionally LLM-controlled) hunt and eradicate them.
    Architecture mirrors SimpleForagingModel: cells = food, nanobots = ants.
    """

    def __init__(self, config):
        self.config = config
        self.domain_size = config.domain_size
        self.step_count = 0
        self.waves_spawned = 0
        self.cells_spawned = 0
        self.next_cell_id = 0
        self.errors = []
        self.queen_report = ""

        # Pheromone grid
        self.pheromones = PheromoneGrid(
            domain_size=self.domain_size,
            resolution=30,
            decay_rate=config.pheromone_decay
        )

        # Reload stations: corners of the domain (nanobots return here to reload)
        margin = 20.0
        self.reload_stations = [
            np.array([margin, margin]),
            np.array([self.domain_size - margin, margin]),
            np.array([margin, self.domain_size - margin]),
            np.array([self.domain_size - margin, self.domain_size - margin]),
        ]

        # Cells and nanobots
        self.cells: List[HuntCell] = []
        self.nanobots: List[HuntNanobot] = []

        # Metrics
        self.metrics = {
            "cells_alive": 0,
            "cells_killed": 0,
            "cells_spawned": 0,
            "waves_spawned": 0,
            "total_drug_delivered": 0.0,
            "nanobots_searching": 0,
            "nanobots_targeting": 0,
            "nanobots_delivering": 0,
            "kills_by_llm": 0,
            "kills_by_rule": 0,
            "drug_efficiency": 0.0,
        }

        # Spawn initial cells
        self._spawn_wave(initial=True)

        # Spawn nanobots near reload stations
        self._init_nanobots()

        # LLM client (optional)
        self.llm_client = None
        self.selected_model = config.selected_model
        if config.agent_type in ("LLM-Powered", "Hybrid"):
            try:
                from backend.litellm_client import get_io_client
                self.llm_client = get_io_client()
            except ImportError:
                try:
                    from litellm_client import get_io_client
                    self.llm_client = get_io_client()
                except Exception as e:
                    self.errors.append(f"LLM client init failed: {e}")
            except Exception as e:
                self.errors.append(f"LLM client init failed: {e}")

    def _spawn_wave(self, initial: bool = False):
        """Spawn a wave of tumor cells at random positions in the domain center area."""
        count = self.config.initial_cells if initial else self.config.cells_per_wave
        wave_num = 0 if initial else self.waves_spawned

        # Cells spawn in the central 60% of the domain
        margin = self.domain_size * 0.2
        max_coord = self.domain_size * 0.8

        # Cluster spawning: 2-3 clusters per wave
        n_clusters = max(2, count // 4)
        cluster_radius = self.domain_size * 0.08
        cluster_centers = [
            np.random.uniform(margin, max_coord, size=2)
            for _ in range(n_clusters)
        ]

        spawned = 0
        for cc in cluster_centers:
            per_cluster = count // n_clusters
            for _ in range(per_cluster):
                offset = np.random.randn(2) * cluster_radius * 0.3
                pos = np.clip(cc + offset, margin, max_coord)
                cell = HuntCell(
                    cell_id=self.next_cell_id,
                    position=pos,
                    drug_kill_threshold=self.config.drug_kill_threshold,
                    wave=wave_num
                )
                self.cells.append(cell)
                self.next_cell_id += 1
                self.cells_spawned += 1
                spawned += 1

        # Fill remainder
        while spawned < count:
            pos = np.random.uniform(margin, max_coord, size=2)
            cell = HuntCell(
                cell_id=self.next_cell_id,
                position=pos,
                drug_kill_threshold=self.config.drug_kill_threshold,
                wave=wave_num
            )
            self.cells.append(cell)
            self.next_cell_id += 1
            self.cells_spawned += 1
            spawned += 1

        if not initial:
            self.waves_spawned += 1

        # Deposit strong recruitment pheromone at each new cell location
        for cell in self.cells[-count:]:
            self.pheromones.deposit_recruitment(cell.position, self.config.recruitment_strength * 2)

    def _init_nanobots(self):
        """Initialize nanobots near reload stations."""
        for i in range(self.config.n_nanobots):
            station = self.reload_stations[i % len(self.reload_stations)]
            offset = np.random.randn(2) * 15.0
            pos = np.clip(station + offset, 0, self.domain_size)

            is_llm = False
            if self.config.agent_type == "LLM-Powered":
                is_llm = True
            elif self.config.agent_type == "Hybrid":
                is_llm = (i < self.config.n_nanobots // 2)

            bot = HuntNanobot(
                nanobot_id=i,
                position=pos,
                max_drug=self.config.drug_payload,
                drug_payload=self.config.drug_payload,
                speed=self.config.nanobot_speed,
                is_llm=is_llm,
                delivery_rate=self.config.drug_delivery_rate,
            )
            # Assign nearest reload station
            dists = [np.linalg.norm(pos - s) for s in self.reload_stations]
            bot._reload_station = self.reload_stations[np.argmin(dists)]
            self.nanobots.append(bot)

    def step(self):
        """Advance simulation by one step."""
        self.step_count += 1

        # Check if we should spawn a new wave
        if (
            self.waves_spawned < self.config.max_waves
            and self.step_count % self.config.wave_interval == 0
        ):
            self._spawn_wave(initial=False)

        # Step each nanobot
        living_cells = [c for c in self.cells if c.is_alive]
        for bot in self.nanobots:
            self._step_nanobot(bot, living_cells)

        # Pheromone decay
        self.pheromones.decay()

        # Update metrics
        self._update_metrics()

    def _step_nanobot(self, bot: HuntNanobot, living_cells: List[HuntCell]):
        """State machine for a single nanobot."""

        if bot.state == HuntState.RELOADING:
            # Reload at station
            bot.drug_payload = min(bot.max_drug, bot.drug_payload + bot.delivery_rate * 2)
            if bot.drug_payload >= bot.max_drug * 0.9:
                bot.state = HuntState.SEARCHING
                bot.target = None
            return

        if bot.state == HuntState.RETURNING:
            # Navigate to nearest reload station
            dists = [np.linalg.norm(bot.position - s) for s in self.reload_stations]
            nearest_station = self.reload_stations[np.argmin(dists)]
            direction = nearest_station - bot.position
            dist = np.linalg.norm(direction)
            if dist < 20.0:
                bot.state = HuntState.RELOADING
                bot.position = nearest_station.copy()
            else:
                bot.position += (direction / dist) * bot.speed
                bot.position = np.clip(bot.position, 0, self.domain_size)
            return

        if bot.state == HuntState.DELIVERING:
            # Deliver drug to target
            if bot.target is None or not bot.target.is_alive:
                bot.state = HuntState.SEARCHING
                bot.target = None
                return
            direction = bot.target.position - bot.position
            dist = np.linalg.norm(direction)
            if dist < 20.0:  # Within delivery range
                # Deliver drug
                amount = min(bot.delivery_rate, bot.drug_payload)
                killed = bot.target.accumulate_drug(amount)
                bot.drug_payload -= amount
                self.metrics["total_drug_delivered"] += amount

                # Deposit trail so other bots can follow
                self.pheromones.deposit_trail(bot.position, self.config.trail_strength)

                if killed:
                    bot.kills += 1
                    if bot.is_llm:
                        self.metrics["kills_by_llm"] += 1
                    else:
                        self.metrics["kills_by_rule"] += 1
                    # Deposit strong recruitment at kill site for other bots nearby
                    self.pheromones.deposit_recruitment(bot.position, self.config.recruitment_strength)
                    bot.state = HuntState.SEARCHING
                    bot.target = None

                if bot.drug_payload < 2.0:
                    bot.state = HuntState.RETURNING
            else:
                # Move toward target
                bot.position += (direction / dist) * bot.speed
                bot.position = np.clip(bot.position, 0, self.domain_size)
                self.pheromones.deposit_trail(bot.position, self.config.trail_strength * 0.3)
            return

        if bot.state == HuntState.TARGETING:
            # Locked onto a target, move to delivery range
            if bot.target is None or not bot.target.is_alive:
                bot.state = HuntState.SEARCHING
                bot.target = None
                return
            direction = bot.target.position - bot.position
            dist = np.linalg.norm(direction)
            if dist < 30.0:
                bot.state = HuntState.DELIVERING
            else:
                bot.position += (direction / dist) * bot.speed
                bot.position = np.clip(bot.position, 0, self.domain_size)
                self.pheromones.deposit_trail(bot.position, self.config.trail_strength * 0.5)
            return

        # SEARCHING state
        if not living_cells:
            # Random walk
            direction = np.random.randn(2)
            if np.linalg.norm(direction) > 0:
                direction = direction / np.linalg.norm(direction)
            bot.position += direction * bot.speed
            bot.position = np.clip(bot.position, 0, self.domain_size)
            return

        if bot.drug_payload < 2.0:
            bot.state = HuntState.RETURNING
            return

        # LLM or rule-based decision
        if bot.is_llm and self.llm_client is not None:
            target = self._llm_decide_target(bot, living_cells)
        else:
            target = self._rule_decide_target(bot, living_cells)

        if target is not None:
            bot.target = target
            bot.state = HuntState.TARGETING
        else:
            # Follow recruitment pheromone or wander
            pheromone_dir = self.pheromones.gradient_toward(bot.position, self.pheromones.recruitment)
            if np.linalg.norm(pheromone_dir) > 0:
                bot.position += pheromone_dir * bot.speed
            else:
                direction = np.random.randn(2)
                direction = direction / np.linalg.norm(direction)
                bot.position += direction * bot.speed
            bot.position = np.clip(bot.position, 0, self.domain_size)

    def _rule_decide_target(self, bot: HuntNanobot, living_cells: List[HuntCell]) -> Optional[HuntCell]:
        """Rule-based: target nearest living cell not already being targeted by another bot."""
        targeted_ids = {b.target.cell_id for b in self.nanobots if b.target and b.target.is_alive and b is not bot}
        candidates = [c for c in living_cells if c.cell_id not in targeted_ids]
        if not candidates:
            candidates = living_cells  # fallback: allow overlap
        if not candidates:
            return None
        dists = [np.linalg.norm(bot.position - c.position) for c in candidates]
        return candidates[int(np.argmin(dists))]

    def _llm_decide_target(self, bot: HuntNanobot, living_cells: List[HuntCell]) -> Optional[HuntCell]:
        """LLM-based target selection. Falls back to rule if LLM fails."""
        try:
            nearby = sorted(living_cells, key=lambda c: np.linalg.norm(bot.position - c.position))[:5]
            trail = self.pheromones.get_trail(bot.position)
            recruitment = self.pheromones.get_recruitment(bot.position)
            cell_info = [{"id": c.cell_id, "distance": round(float(np.linalg.norm(bot.position - c.position)), 1),
                          "accumulated_drug": round(c.accumulated_drug, 2),
                          "threshold": c.drug_kill_threshold, "wave": c.wave} for c in nearby]
            prompt = (
                f"You control nanobot {bot.nanobot_id}. Position: {bot.position.tolist()}. "
                f"Drug payload: {bot.drug_payload:.1f}/{bot.max_drug}. "
                f"Trail pheromone: {trail:.2f}. Recruitment signal: {recruitment:.2f}. "
                f"Nearby tumor cells: {cell_info}. "
                f"Which cell ID should you target? Consider: cells with more accumulated drug are closer to death "
                f"(worth finishing), high recruitment means other bots found targets there. "
                f"Reply with ONLY a number: the cell_id to target, or -1 to explore."
            )
            response = self.llm_client.chat.completions.create(
                model=self.selected_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1
            )
            text = response.choices[0].message.content.strip()
            chosen_id = int(''.join(filter(lambda c: c.isdigit() or c == '-', text)) or '-1')
            if chosen_id == -1:
                return None
            matches = [c for c in living_cells if c.cell_id == chosen_id]
            if matches:
                return matches[0]
        except Exception as e:
            self.errors.append(f"LLM decision failed for bot {bot.nanobot_id}: {e}")
        return self._rule_decide_target(bot, living_cells)

    def _update_metrics(self):
        living = [c for c in self.cells if c.is_alive]
        dead = [c for c in self.cells if not c.is_alive]
        self.metrics["cells_alive"] = len(living)
        self.metrics["cells_killed"] = len(dead)
        self.metrics["cells_spawned"] = self.cells_spawned
        self.metrics["waves_spawned"] = self.waves_spawned
        self.metrics["nanobots_searching"] = sum(1 for b in self.nanobots if b.state == HuntState.SEARCHING)
        self.metrics["nanobots_targeting"] = sum(1 for b in self.nanobots if b.state in (HuntState.TARGETING, HuntState.DELIVERING))
        self.metrics["nanobots_delivering"] = sum(1 for b in self.nanobots if b.state == HuntState.DELIVERING)
        total_drug_used = self.metrics["total_drug_delivered"]
        cells_killed = self.metrics["cells_killed"]
        self.metrics["drug_efficiency"] = round(cells_killed / max(1.0, total_drug_used), 4)

    def get_step_state(self, include_pheromones: bool = False) -> dict:
        state = {
            "step": self.step_count,
            "nanobots": [b.to_dict() for b in self.nanobots],
            "cells": [c.to_dict() for c in self.cells],
            "metrics": self.metrics.copy(),
            "queen_report": self.queen_report,
        }
        if include_pheromones:
            state["pheromone_trail"] = self.pheromones.to_list(self.pheromones.trail)
            state["pheromone_recruitment"] = self.pheromones.to_list(self.pheromones.recruitment)
        return state
