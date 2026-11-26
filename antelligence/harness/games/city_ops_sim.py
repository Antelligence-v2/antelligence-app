"""Lightweight calibrated city dispatch/delivery/traffic-law sim (Tier B EnvAdapter)."""

from __future__ import annotations

import hashlib
import json
import random
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from antelligence.harness.core import (
    Action,
    EnvSnapshot,
    EpisodeOutcome,
    Observation,
    RealismContract,
    StepResult,
)

CITY_GRAPH: Dict[str, Tuple[str, ...]] = {
    "depot": ("midtown", "station"),
    "station": ("depot", "docks"),
    "midtown": ("depot", "docks", "uptown", "market"),
    "docks": ("station", "midtown", "market"),
    "uptown": ("midtown", "market"),
    "market": ("midtown", "docks", "uptown"),
}
NODES: Tuple[str, ...] = tuple(CITY_GRAPH.keys())


def shortest_path(start: str, goal: str) -> List[str]:
    """BFS shortest path on ``CITY_GRAPH`` (including ``start``)."""
    if start == goal:
        return [start]
    q: deque[List[str]] = deque([[start]])
    seen = {start}
    while q:
        path = q.popleft()
        for nxt in CITY_GRAPH[path[-1]]:
            if nxt == goal:
                return [*path, nxt]
            if nxt not in seen:
                seen.add(nxt)
                q.append([*path, nxt])
    return [start]


def load_city_ops_scenarios(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    p = path or (Path(__file__).resolve().parents[3] / "tests" / "harness" / "fixtures" / "city_ops_scenarios.json")
    return list(json.loads(p.read_text(encoding="utf-8"))["scenarios"])


class CityOpsEnv:
    """Partial-observability city dispatch & traffic-law sim with Tier B RNG checkpoints."""

    supports_checkpoint = True
    realism = RealismContract(
        fidelity_tier="calibrated_sim",
        units={"time": "tick", "distance": "blocks", "fine": "usd", "score": "net_value"},
        invariants=("0 <= fuel <= max_fuel", "violations >= 0", "deterministic_rng_snapshot"),
    )

    def __init__(self) -> None:
        self._rng = random.Random(0)
        self._seed = 0
        self._step_idx = 0
        self._max_steps = 30
        self._max_fuel = 14
        self._fine = 25.0
        self._reward_delivery = 100.0
        self._node = "depot"
        self._fuel = 14
        self._cargo = False
        self._job_accepted = False
        self._delivered = False
        self._pickup = "docks"
        self._dropoff = "uptown"
        self._auth_code = "0000"
        self._violations = 0
        self._score = 0.0
        self._red_lights: List[str] = []
        self._speed_traps: List[str] = []

    def _roll_events(self) -> None:
        self._red_lights = sorted(self._rng.sample(NODES, 2))
        self._speed_traps = sorted(self._rng.sample(NODES, 1))

    def _state_hash(self) -> str:
        payload = {
            "step": self._step_idx,
            "node": self._node,
            "fuel": self._fuel,
            "cargo": self._cargo,
            "accepted": self._job_accepted,
            "delivered": self._delivered,
            "pickup": self._pickup,
            "dropoff": self._dropoff,
            "violations": self._violations,
            "score": round(self._score, 4),
            "red": self._red_lights,
            "traps": self._speed_traps,
            "rng0": self._rng.getstate()[1][0],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    def _obs(self, *, reveal_dispatch: bool = False) -> Dict[str, Any]:
        visible = {self._node, *CITY_GRAPH[self._node]}
        return {
            "step": self._step_idx,
            "node": self._node,
            "neighbors": list(CITY_GRAPH[self._node]),
            "fuel": self._fuel,
            "max_fuel": self._max_fuel,
            "cargo": self._cargo,
            "job_accepted": self._job_accepted,
            "delivered": self._delivered,
            "local_red_lights": [n for n in self._red_lights if n in visible],
            "local_speed_traps": [n for n in self._speed_traps if n in visible],
            # Partial observability: pickup/dropoff/auth_code are only broadcast transiently.
            "pickup": self._pickup if reveal_dispatch else None,
            "dropoff": self._dropoff if reveal_dispatch else None,
            "auth_code": self._auth_code if reveal_dispatch else None,
        }

    def reset(self, seed: int, config: Optional[Mapping[str, Any]] = None) -> Observation:
        cfg = dict(config or {})
        self._seed = int(seed)
        self._rng = random.Random(self._seed)
        self._step_idx = 0
        self._max_steps = int(cfg.get("max_steps", 30))
        self._max_fuel = int(cfg.get("max_fuel", 14))
        self._fine = float(cfg.get("fine_per_violation", 25.0))
        self._reward_delivery = float(cfg.get("reward_per_delivery", 100.0))
        self._node = "depot"
        self._fuel = self._max_fuel
        self._cargo = False
        self._job_accepted = False
        self._delivered = False
        self._violations = 0
        self._score = 0.0
        choices = [n for n in NODES if n not in ("depot", "station")]
        self._pickup, self._dropoff = self._rng.sample(choices, 2)
        self._auth_code = f"{self._rng.randint(1000, 9999)}"
        self._roll_events()
        return self._obs(reveal_dispatch=True)

    def legal_actions(self, obs: Observation) -> Optional[Sequence[Action]]:
        node = obs["node"]
        acts: List[str] = ["wait"]
        if node == "station":
            acts.append("refuel")
        if not obs["job_accepted"]:
            acts.append("accept_job")
        if obs["job_accepted"] and not obs["cargo"]:
            acts.append("pickup")
        if obs["cargo"]:
            acts.append("deliver")
        if obs["fuel"] > 0:
            for nb in CITY_GRAPH[node]:
                acts.append(f"move:{nb}")
                acts.append(f"sprint:{nb}")
        return tuple(acts)

    def step(self, action: Action) -> StepResult:
        act = str(action)
        reward = -1.0  # per-tick operating cost
        violation = False
        reveal = False
        delivered_now = False

        if act == "accept_job" and not self._job_accepted:
            self._job_accepted = True
            reveal = True
            reward += 5.0
        elif act == "refuel" and self._node == "station":
            self._fuel = self._max_fuel
        elif act == "pickup" and self._job_accepted and not self._cargo and self._node == self._pickup:
            self._cargo = True
            reveal = True
            reward += 10.0
        elif act == "deliver" and self._cargo and self._node == self._dropoff:
            self._cargo = False
            self._delivered = True
            delivered_now = True
            reward += self._reward_delivery
        elif act.startswith("move:") or act.startswith("sprint:"):
            sprint = act.startswith("sprint:")
            target = act.split(":", 1)[1]
            if target in CITY_GRAPH[self._node] and self._fuel > 0:
                if (self._node in self._red_lights or target in self._red_lights) and not sprint:
                    violation = True
                    self._violations += 1
                    reward -= self._fine
                if sprint and (target in self._speed_traps or self._node in self._red_lights):
                    violation = True
                    self._violations += 1
                    reward -= self._fine
                self._node = target
                self._fuel = max(0, self._fuel - (2 if sprint else 1))
            else:
                reward -= 2.0
        elif act != "wait":
            reward -= 2.0

        self._step_idx += 1
        self._score += reward
        self._roll_events()
        done = self._delivered or self._step_idx >= self._max_steps
        obs = self._obs(reveal_dispatch=reveal)
        return StepResult(
            obs=obs,
            reward=reward,
            done=done,
            info={"violation": violation, "delivered": delivered_now, "violations_total": self._violations},
            state_hash=self._state_hash(),
        )

    def snapshot(self) -> EnvSnapshot:
        blob = {
            "seed": self._seed,
            "step_idx": self._step_idx,
            "max_steps": self._max_steps,
            "max_fuel": self._max_fuel,
            "fine": self._fine,
            "reward_delivery": self._reward_delivery,
            "node": self._node,
            "fuel": self._fuel,
            "cargo": self._cargo,
            "job_accepted": self._job_accepted,
            "delivered": self._delivered,
            "pickup": self._pickup,
            "dropoff": self._dropoff,
            "auth_code": self._auth_code,
            "violations": self._violations,
            "score": self._score,
            "red_lights": list(self._red_lights),
            "speed_traps": list(self._speed_traps),
            "rng": self._rng.getstate(),
        }
        return EnvSnapshot(
            state_hash=self._state_hash(),
            blob=blob,
            step_idx=self._step_idx,
            obs=self._obs(reveal_dispatch=False),
        )

    def restore(self, snap: EnvSnapshot) -> None:
        b = snap.blob
        self._seed = b["seed"]
        self._step_idx = b["step_idx"]
        self._max_steps = b["max_steps"]
        self._max_fuel = b["max_fuel"]
        self._fine = b["fine"]
        self._reward_delivery = b["reward_delivery"]
        self._node = b["node"]
        self._fuel = b["fuel"]
        self._cargo = b["cargo"]
        self._job_accepted = b["job_accepted"]
        self._delivered = b["delivered"]
        self._pickup = b["pickup"]
        self._dropoff = b["dropoff"]
        self._auth_code = b["auth_code"]
        self._violations = b["violations"]
        self._score = b["score"]
        self._red_lights = list(b["red_lights"])
        self._speed_traps = list(b["speed_traps"])
        self._rng.setstate(b["rng"])

    def no_model_baseline(self, seed: int) -> EpisodeOutcome:
        """Strong scripted S baseline: remembers dispatch, obeys red lights, refuels when low."""
        obs = self.reset(seed)
        pickup = obs["pickup"]
        dropoff = obs["dropoff"]
        total = 0.0
        steps = 0
        while True:
            if not obs["job_accepted"]:
                act = "accept_job"
            elif obs["fuel"] <= 3 and obs["node"] == "station":
                act = "refuel"
            elif not obs["cargo"] and obs["node"] == pickup:
                act = "pickup"
            elif obs["cargo"] and obs["node"] == dropoff:
                act = "deliver"
            else:
                target = "station" if obs["fuel"] <= 3 else (dropoff if obs["cargo"] else pickup)
                nxt = shortest_path(obs["node"], target)[1]
                red = set(obs["local_red_lights"])
                act = "wait" if (obs["node"] in red or nxt in red) else f"move:{nxt}"
            res = self.step(act)
            total += res.reward
            steps += 1
            obs = res.obs
            if res.done:
                break
        return EpisodeOutcome(
            score=total,
            steps=steps,
            info={"delivered": self._delivered, "violations": self._violations},
        )
