"""Legacy ant colony brains (port of backend/simulation.py agents).

* :class:`ColonyAnt` — pick up food underfoot; escape a predator within 2
  cells; follow the Queen; then either ask the model for one word
  (``toward`` / ``random`` / ``stay``, three legacy prompt styles) or use the
  legacy rule (carry home, else walk to the nearest food, else wander).
  A failed model call means ``random`` plus an alarm pheromone, as in legacy.
* :class:`ColonyPredator` — rule: hunt the nearest ant when energy > 50 and not
  cooling down, else patrol toward the least fear; LLM: ``hunt`` / ``patrol`` /
  ``rest`` (a failed call means ``hunt``).
* :class:`ColonyQueen` — guides every ant every tick: carriers toward the nest,
  the rest toward the nearest food (heuristic), or the model's JSON guidance
  with a heuristic fallback (LLM). Guidance is a goal cell per ant; the world
  turns it into legacy's best step toward that goal.

Randomness comes from the view seed, so runs are reproducible.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Mapping, Optional, Sequence

from antelligence.kernel.policies.prompt import ask, json_object, one_word
from antelligence.kernel.types import Intent, LocalView
from antelligence.providers.base import Provider, ProviderError

PROMPT_STYLES = ("Adaptive", "Structured", "Autonomous")
ANT_WORDS = ("toward", "random", "stay")
PREDATOR_WORDS = ("hunt", "patrol", "rest")
ANT_SYSTEM = "You are an intelligent ant. Respond with one word: toward, random, or stay."
PREDATOR_SYSTEM = "You are an intelligent predator. Respond with only one word: hunt, patrol, or rest."
QUEEN_SYSTEM = "You are a Queen Ant. Respond only with valid JSON."


def _manhattan(a: Sequence[int], b: Sequence[int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _step_toward(neighbors: List[List[int]], pos: List[int], target: Sequence[int]) -> List[int]:
    """Legacy _step_toward: the neighbor (never "stay") closest to the target; first wins ties."""
    return min(neighbors, key=lambda n: _manhattan(n, target)) if neighbors else pos


def _llm_meta(meta: Mapping[str, Any], **extra: Any) -> Dict[str, Any]:
    return {**meta, **extra}


class _Brain:
    def __init__(self, provider: Optional[Provider], model: Optional[str], prompt_style: str) -> None:
        if provider is not None and not model:
            raise ValueError("an LLM brain needs a model")
        if prompt_style not in PROMPT_STYLES:
            raise ValueError(f"prompt_style must be one of {PROMPT_STYLES}")
        self.provider = provider
        self.model = model
        self.prompt_style = prompt_style

    def _describe(self, name: str) -> Dict[str, Any]:
        if self.provider is None:
            return {"policy": name, "brain": "rule"}
        return {"policy": name, "brain": "llm", "model": self.model, "provider": self.provider.describe(),
                "prompt_style": self.prompt_style}


class ColonyAnt(_Brain):
    def __init__(self, provider: Optional[Provider] = None, model: Optional[str] = None,
                 prompt_style: str = "Adaptive") -> None:
        super().__init__(provider, model, prompt_style)

    def describe(self) -> Dict[str, Any]:
        return self._describe("colony_ant")

    async def decide(self, view: LocalView) -> Intent:
        obs = view.observation
        pos, neighbors = obs["pos"], obs["neighbors"]
        rng = random.Random(view.seed)
        if obs["food_here"] and not obs["carrying"]:
            return Intent("move", {"to": pos}, rationale="pick up food")
        threats = obs["predators_within_2"]
        if threats and neighbors:
            nearest = min(threats, key=lambda p: _manhattan(p, pos))
            escape = max(neighbors + [pos], key=lambda c: _manhattan(c, nearest))
            return Intent("move", {"to": escape, "escape": True}, rationale="escape predator")
        if obs["queen_guidance"] is not None:
            return Intent("move", {"to": obs["queen_guidance"], "guided": True}, rationale="queen guidance")
        if self.provider is None:
            return Intent("move", {"to": self._rule(obs, rng)})
        try:
            text, meta = await ask(self.provider, self.model, ANT_SYSTEM, ant_prompt(obs, self.prompt_style),
                                   temperature=0.3, max_tokens=10)
        except ProviderError as exc:
            to = rng.choice(neighbors) if neighbors else pos
            return Intent("move", {"to": to, "api_error": True}, rationale="llm failed: random",
                          meta={"policy": "colony_ant", "word": "random", "fallback": f"provider:{exc}"[:200]})
        word = one_word(text, ANT_WORDS) or "random"
        meta = _llm_meta(meta, policy="colony_ant", word=word)
        if word == "toward" and neighbors:
            food = obs["nearest_food"]
            to = _step_toward(neighbors, pos, food) if food else rng.choice(neighbors)
        elif word == "stay":
            to = pos
        else:
            to = rng.choice(neighbors) if neighbors else pos
        return Intent("move", {"to": to}, rationale=f"llm: {word}", meta=meta)

    @staticmethod
    def _rule(obs: Mapping[str, Any], rng: random.Random) -> List[int]:
        pos, neighbors = obs["pos"], obs["neighbors"]
        if obs["carrying"]:
            return _step_toward(neighbors, pos, obs["nest"])
        if obs["nearest_food"]:
            return _step_toward(neighbors, pos, obs["nearest_food"])
        return rng.choice(neighbors) if neighbors else pos


def ant_prompt(obs: Mapping[str, Any], style: str) -> str:
    x, y = obs["pos"]
    w, h = obs["grid"]
    ph = obs["pheromones"]
    info = (f"Local Pheromones (radius 2): Trail: {ph['trail']:.2f}, Alarm: {ph['alarm']:.2f}, "
            f"Recruitment: {ph['recruitment']:.2f}, Fear: {ph['fear']:.2f}. "
            f"Predators nearby: {obs['predators_within_3']}. ")
    nearby, carrying = obs["food_nearby"], obs["carrying"]
    if style == "Structured":
        return (f"You are an ant at position ({x},{y}) on a {w}x{h} grid. "
                f"Food nearby: {nearby}. Carrying food: {carrying}. {info}"
                "Should you move 'toward' food, move 'random', or 'stay'? "
                "Consider: High trail=good path, high alarm=danger, high recruitment=help needed, high fear=predators! "
                "PRIORITY: Avoid areas with high fear pheromone (predators). "
                "Reply with only one word: 'toward', 'random', or 'stay'.")
    if style == "Autonomous":
        return ("As an autonomous ant foraging for food, my current state is: "
                f"Position: ({x},{y}), Food available nearby: {nearby}, Currently carrying food: {carrying}. {info}"
                "What is the best action? Choose: 'toward', 'random', or 'stay'. "
                "Pheromone signals: Trail=good path, alarm=danger, recruitment=help needed, fear=PREDATORS (avoid!). "
                "Survival is priority #1 - avoid fear pheromone areas.")
    return (f"Ant {obs['index']} has collected {obs['food_collected']} food items. "
            f"Current position: ({x},{y}). Food nearby: {nearby}. Carrying food: {carrying}. {info}"
            "Best action? Options: 'toward', 'random', 'stay'. "
            "Pheromone guide: Follow trails, avoid alarms/fear (predators!), respond to recruitment. "
            "Stay alive first, then collect food.")


class ColonyPredator(_Brain):
    def __init__(self, provider: Optional[Provider] = None, model: Optional[str] = None,
                 prompt_style: str = "Adaptive") -> None:
        super().__init__(provider, model, prompt_style)

    def describe(self) -> Dict[str, Any]:
        return self._describe("colony_predator")

    async def decide(self, view: LocalView) -> Intent:
        obs = view.observation
        pos, neighbors = obs["pos"], obs["neighbors"]
        rng = random.Random(view.seed)
        if self.provider is None:
            return Intent("move", {"to": self._rule(obs)})
        try:
            text, meta = await ask(self.provider, self.model, PREDATOR_SYSTEM, predator_prompt(obs, self.prompt_style),
                                   temperature=0.4, max_tokens=10)
            word = one_word(text, PREDATOR_WORDS) or "hunt"
            meta = _llm_meta(meta, policy="colony_predator", word=word)
        except ProviderError as exc:
            word, meta = "hunt", {"policy": "colony_predator", "word": "hunt", "fallback": f"provider:{exc}"[:200]}
        if word == "hunt" and neighbors:
            to = _step_toward(neighbors, pos, obs["nearest_ant"]) if obs["nearest_ant"] else rng.choice(neighbors)
        elif word == "patrol" and neighbors:
            to = self._patrol(obs)
        elif word == "rest":
            to = pos
        else:
            to = rng.choice(neighbors) if neighbors else pos
        return Intent("move", {"to": to}, rationale=f"llm: {word}", meta=meta)

    @classmethod
    def _rule(cls, obs: Mapping[str, Any]) -> List[int]:
        if obs["energy"] > 50 and obs["cooldown"] == 0 and obs["nearest_ant"]:
            return _step_toward(obs["neighbors"], obs["pos"], obs["nearest_ant"])
        return cls._patrol(obs) if obs["neighbors"] else obs["pos"]

    @staticmethod
    def _patrol(obs: Mapping[str, Any]) -> List[int]:
        cells = obs["neighbors"] + [obs["pos"]]
        best, low = obs["pos"], float("inf")
        for cell, fear in zip(cells, obs["fear_by_cell"]):
            if fear < low:
                best, low = cell, fear
        return best


def predator_prompt(obs: Mapping[str, Any], style: str) -> str:
    x, y = obs["pos"]
    w, h = obs["grid"]
    ph = obs["pheromones"]
    info = f"Local Pheromones: Fear: {ph['fear']:.2f}, Trail: {ph['trail']:.2f}. "
    near, energy, cooldown = obs["ants_within_3"], obs["energy"], obs["cooldown"]
    if style == "Structured":
        return (f"You are a predator at position ({x},{y}) on a {w}x{h} grid. "
                f"Nearby ants: {near}. Energy: {energy}/100. Hunt cooldown: {cooldown}. {info}"
                "Should you 'hunt' ants, 'patrol' territory, or 'rest'? "
                "High fear pheromone means you've been here recently. Trail pheromone indicates ant activity. "
                "Reply with only one word: 'hunt', 'patrol', or 'rest'.")
    if style == "Autonomous":
        return ("As an autonomous predator, my state is: "
                f"Position: ({x},{y}), Nearby prey: {near} ants, Energy: {energy}/100, Hunt cooldown: {cooldown}. "
                f"{info}What is the optimal strategy? Choose: 'hunt', 'patrol', or 'rest'. "
                "Consider energy management and territorial coverage.")
    rate = obs["ants_caught"] / max(1, obs["moves"])
    return (f"Predator {obs['index'] + 1000} has caught {obs['ants_caught']} ants with success rate {rate:.2f}. "
            f"Current position: ({x},{y}). Nearby ants: {near}. Energy: {energy}/100. {info}"
            "Best hunting strategy? Options: 'hunt', 'patrol', 'rest'. "
            "Adapt based on your success rate and current conditions.")


class ColonyQueen:
    def __init__(self, provider: Optional[Provider] = None, model: Optional[str] = None) -> None:
        if provider is not None and not model:
            raise ValueError("an LLM Queen needs a model")
        self.provider = provider
        self.model = model

    def describe(self) -> Dict[str, Any]:
        if self.provider is None:
            return {"policy": "colony_queen", "brain": "heuristic"}
        return {"policy": "colony_queen", "brain": "llm", "model": self.model, "provider": self.provider.describe()}

    async def decide(self, view: LocalView) -> Intent:
        obs = view.observation
        if not obs["foods"]:
            return Intent("noop", rationale="No food remaining for guidance")
        if self.provider is None:
            return self._heuristic(obs)
        try:
            text, meta = await ask(self.provider, self.model, QUEEN_SYSTEM, queen_prompt(obs),
                                   temperature=0.1, max_tokens=300)
        except ProviderError as exc:
            return self._heuristic(obs, f"Queen LLM: API error ({str(exc)[:50]}), using heuristic")
        meta = _llm_meta(meta, policy="colony_queen")
        parsed = json_object(text)
        if parsed is None:
            fallback = self._heuristic(obs, "Queen LLM: Invalid JSON response, using heuristic")
            return Intent(fallback.action, fallback.params, rationale=fallback.rationale,
                          meta={**meta, "fallback": "reply:invalid json"})
        guidance = _parse_guidance(parsed.get("guidance"), obs)
        report = parsed.get("report") if isinstance(parsed.get("report"), str) else "Queen provided guidance"
        return Intent("guide", {"guidance": guidance}, rationale=f"Queen LLM: {report} (guided {len(guidance)} ants)"[:300],
                      meta=meta)

    @staticmethod
    def _heuristic(obs: Mapping[str, Any], report: Optional[str] = None) -> Intent:
        guidance: Dict[str, List[int]] = {}
        for ant in obs["ants"]:
            pos = ant["pos"]
            goal = obs["nest"] if ant["carrying"] else min(obs["foods"], key=lambda f: _manhattan(f, pos))
            guidance[ant["id"]] = list(goal)
        carrying = sum(a["carrying"] for a in obs["ants"])
        text = report or (f"Queen heuristic guidance: Directed {len(guidance)} ants ({carrying} carrying food, "
                          f"{len(obs['ants']) - carrying} foraging)")
        return Intent("guide", {"guidance": guidance}, rationale=text)


def queen_prompt(obs: Mapping[str, Any]) -> str:
    w, h = obs["grid"]
    peaks = obs["peaks"]
    at = lambda p: f"({p['at'][0]}, {p['at'][1]})" if p["at"] else "N/A"  # noqa: E731
    prompt = f"""You are a Queen Ant. Guide your worker ants efficiently.

Current situation:
- Step: {obs['step']}
- Grid: {w}x{h}
- Ants: {len(obs['ants'])}
- Food: {len(obs['foods'])} remaining

Pheromone Summary:
- Max Trail: {peaks['trail']['max']:.2f} at {at(peaks['trail'])} (success paths)
- Max Alarm: {peaks['alarm']['max']:.2f} at {at(peaks['alarm'])} (problems)
- Max Recruitment: {peaks['recruitment']['max']:.2f} at {at(peaks['recruitment'])} (help needed)

Respond with JSON: {{"guidance": {{"0": [x,y], "1": [x,y]}}, "report": "brief status"}}

Ant positions:"""
    for ant in obs["ants"][:5]:  # legacy limited the prompt to five ants
        pos = ant["pos"]
        nearby = sum(abs(f[0] - pos[0]) <= 2 and abs(f[1] - pos[1]) <= 2 for f in obs["foods"])
        prompt += f"\nAnt {ant['index']}: at ({pos[0]}, {pos[1]}), carrying={ant['carrying']}, nearby_food={nearby}"
    return prompt


def _neighbors(pos: Sequence[int], w: int, h: int) -> List[List[int]]:
    x, y = pos
    return [[x + dx, y + dy] for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            if (dx, dy) != (0, 0) and 0 <= x + dx < w and 0 <= y + dy < h]


def _parse_guidance(raw: Any, obs: Mapping[str, Any]) -> Dict[str, List[int]]:
    """Legacy keyed ants by integer id and accepted only a neighbor cell (or staying put)."""
    guidance: Dict[str, List[int]] = {}
    if not isinstance(raw, dict):
        return guidance
    w, h = obs["grid"]
    by_index = {a["index"]: a for a in obs["ants"]}
    for key, pos in raw.items():
        try:
            ant = by_index.get(int(key))
            target = [int(pos[0]), int(pos[1])] if isinstance(pos, list) and len(pos) == 2 else None
        except (ValueError, TypeError):
            continue
        if ant is None or target is None:
            continue
        if target == ant["pos"] or target in _neighbors(ant["pos"], w, h):
            guidance[ant["id"]] = target
    return guidance
