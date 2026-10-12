"""Serve the original ant page (``/simulation/run``, ``/simulation/compare``) from the engine.

The page keeps its config and response shapes; the simulation underneath is the
engine ``ant_colony`` world (a port of ``simulation.SimpleForagingModel``), so
every run is also a stored, replayable engine run. Per-tick state is read from
the world as the run goes, at full precision.

Differences from the old endpoint, by design:

* ``food_collected`` counts pickups once (legacy added pickups and nest drops);
* blockchain transactions are not sent; ``blockchain_logs`` names the engine run
  and its trace hash instead;
* integer engine params round the pheromone sliders to 0.01 (decay) and 0.1
  (deposits), and clamp sizes to the engine's bounds.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from antelligence.kernel import events as ev
from antelligence.worlds.ant_colony.world import QUEEN

SEED = 42  # the old endpoint always seeded 42


def _clamp(value: float, low: int, high: int) -> int:
    return int(min(high, max(low, round(value))))


def engine_spec(config: Any) -> Tuple[str, Dict[str, Any]]:
    """Old page config (SimulationConfig) -> (arm, ant_colony params)."""
    width, height = _clamp(config.grid_width, 5, 60), _clamp(config.grid_height, 5, 60)
    predators = _clamp(config.n_predators, 0, 10) if config.enable_predators else 0
    params: Dict[str, Any] = {
        "grid_width": width,
        "grid_height": height,
        "n_ants": _clamp(config.n_ants, 1, 60),
        "n_food": _clamp(min(config.n_food, width * height), 1, 200),
        "n_predators": predators,
        "max_steps": _clamp(config.max_steps, 1, 1000),
        "pheromone_decay_pct": _clamp(config.pheromone_decay_rate * 100, 1, 20),
        "trail_deposit_x10": _clamp(config.trail_deposit * 10, 1, 50),
        "alarm_deposit_x10": _clamp(config.alarm_deposit * 10, 1, 50),
        "recruitment_deposit_x10": _clamp(config.recruitment_deposit * 10, 1, 50),
        "fear_deposit_x10": _clamp(config.fear_deposit * 10, 10, 100),
        "max_pheromone": _clamp(config.max_pheromone_value, 5, 20),
        "agent_type": config.agent_type,
        "predator_type": config.predator_type if predators else "Rule-Based",
        "queen_brain": "llm" if config.use_queen and config.use_llm_queen else "heuristic",
        "prompt_style": config.prompt_style,
    }
    from antelligence.experiments.registry import world
    if world("ant_colony").uses_llm(params):
        params["model"] = config.selected_model
    return ("queen" if config.use_queen else "no_queen"), params


def _grid(values: np.ndarray) -> List[List[float]]:
    return values.T.tolist()  # the old page expects [y][x]


def _pheromones(w) -> Dict[str, Any]:
    return {name: _grid(w.pheromones[name]) for name in ("trail", "alarm", "recruitment", "fear")} | {
        "max_values": {name: float(w.pheromones[name].max()) for name in ("trail", "alarm", "recruitment", "fear")}}


def _efficiency(w) -> Dict[str, Any]:
    top = float(w.efficiency.max())
    hotspots = [(int(x), int(y)) for x, y in np.argwhere(w.efficiency >= top * 0.1)[:20]] if top > 0 else []
    return {"efficiency_grid": _grid(w.efficiency), "max_efficiency": top, "hotspot_locations": hotspots}


class _Recorder:
    """Builds the old page's per-step history from the live engine run."""

    def __init__(self, max_steps: int, llm_queen: bool) -> None:
        self.detail_every = max(1, max_steps // 50)
        self.max_steps = max_steps
        self.llm_queen = llm_queen
        self.history: List[Dict[str, Any]] = []
        self.depletion: List[Dict[str, int]] = []
        self.api_calls = 0
        self.predator_api_calls = 0
        self._seen = 0

    def attach(self, scheduler) -> None:
        self.scheduler = scheduler
        scheduler.on_tick = self.on_tick

    def _new_events(self) -> Tuple[int, int, List[str]]:
        events = list(self.scheduler.log)[self._seen:]
        self._seen += len(events)
        calls = predator_calls = 0
        errors: List[str] = []
        for e in events:
            if e.type != ev.DECIDED:
                continue
            meta = e.data.get("meta") or {}
            failed = str(meta.get("fallback", "")).startswith("provider:")
            if "request_hash" in meta or failed:
                calls += 1
                predator_calls += bool(e.agent_id and e.agent_id.startswith("predator-"))
            if failed:
                errors.append(f"LLM call failed for {e.agent_id}: {meta['fallback'][len('provider:'):]}")
        return calls, predator_calls, errors

    def on_tick(self, scheduler) -> None:
        w, tick = scheduler.world, scheduler.tick
        calls, predator_calls, errors = self._new_events()
        self.api_calls += calls
        self.predator_api_calls += predator_calls
        ants = [{"id": a.index, "pos": a.pos, "carrying_food": a.carrying, "is_llm": a.is_llm,
                 "steps_since_food": a.steps_since_food} for _, a in sorted(w.ants.items())]
        if w.queen:
            ants.append({"id": "queen", "pos": w.nest, "carrying_food": False, "is_llm": self.llm_queen,
                         "is_queen": True})
        # Same cadence as the old endpoint: every detail_every-th step from the first, plus the last.
        detail = (tick - 1) % self.detail_every == 0 or tick == self.max_steps or w.done(tick)
        self.history.append({
            "step": tick,
            "ants": ants,
            "predators": [{"id": p.index + 1000, "pos": p.pos, "energy": p.energy, "is_llm": p.is_llm,
                           "ants_caught": p.ants_caught, "hunt_cooldown": p.cooldown}
                          for _, p in sorted(w.predators.items())],
            "food_positions": list(w.foods),
            "metrics": self.metrics(w),
            "queen_report": w.queen_report,
            "errors": errors,
            "pheromone_data": _pheromones(w) if detail else None,
            "efficiency_data": _efficiency(w) if detail else None,
            "nest_position": w.nest,
        })
        self.depletion.append({"step": tick, "food_piles_remaining": len(w.foods)})

    def metrics(self, w) -> Dict[str, Any]:
        c = w.counters
        return {"food_collected": c["food_collected"], "total_api_calls": self.api_calls, "avg_response_time": 0,
                "food_collected_by_llm": c["food_collected_by_llm"], "food_collected_by_rule": c["food_collected_by_rule"],
                "ants_carrying_food": sum(a.carrying for a in w.ants.values()), "ants_caught": c["ants_caught"],
                "llm_ants_caught": c["llm_ants_caught"], "rule_ants_caught": c["rule_ants_caught"],
                "predator_api_calls": self.predator_api_calls, "food_delivered": c["food_delivered"]}


def run(config: Any, service) -> Dict[str, Any]:
    """Run the old page's config on the engine; returns a SimulationResult-shaped dict."""
    arm, params = engine_spec(config)
    recorder = _Recorder(params["max_steps"], arm == "queen" and params["queen_brain"] == "llm")
    record = service.run_spec("ant_colony", arm, SEED, params, on_start=recorder.attach)
    w = recorder.scheduler.world
    queen_note = "" if QUEEN not in w.agents() else " with the Queen"
    return {
        "config": config,
        "total_steps_run": record["ticks"],
        "final_metrics": recorder.metrics(w),
        "history": recorder.history,
        "food_depletion_history": recorder.depletion,
        "initial_food_count": w.initial_food,
        "final_pheromone_data": _pheromones(w),
        "final_efficiency_data": _efficiency(w),
        "blockchain_logs": [f"Engine run {record['run_id']}{queen_note}: trace {record['trace_hash'][:16]}…, "
                            f"bundle {record['bundle_hash'][:16]}… (replayable; no chain transactions sent)"],
        "blockchain_transactions": [],
    }


def compare(config: Any, service, steps: int) -> Tuple[int, int]:
    """Queen vs no Queen, rule-based ants (as the old comparison forced). Returns (with, without)."""
    _, params = engine_spec(config)
    params = {**params, "agent_type": "Rule-Based", "predator_type": "Rule-Based", "queen_brain": "heuristic",
              "max_steps": _clamp(steps, 1, 1000)}
    params.pop("model", None)
    with_queen = service.run_spec("ant_colony", "queen", SEED, params)
    without = service.run_spec("ant_colony", "no_queen", SEED, params)
    return with_queen["metrics"]["food_collected"], without["metrics"]["food_collected"]

