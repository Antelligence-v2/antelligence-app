"""The legacy tumor agents, ported: LLM / hybrid nanobots and the Queen.

Behavior follows ``backend/nanobot_simulation.py``:

* :class:`LegacyNanobot` — a searching bot targets the nearest sensed living
  cell; otherwise follows Queen guidance; otherwise (LLM bots) asks the model
  for one word — ``target`` (nearest hypoxic cell within 120 µm), ``follow_trail``
  (trail pheromone gradient), ``explore`` / ``return`` (chemotaxis); otherwise
  chemotaxis. A failed or unusable model call falls back to chemotaxis, and the
  event log records why.
* :class:`LegacyQueen` — every 10 ticks steers searching bots with more than half
  a payload: toward the nearest hypoxic cell (heuristic), or by the model's JSON
  guidance with the legacy fallbacks (LLM).

Not ported: the knowledge-graph block legacy prepended to nanobot prompts and the
on-chain intel pins; engine runs carry their own provenance instead.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

from antelligence.kernel.policies.prompt import ask, json_object, one_word
from antelligence.kernel.types import Intent, LocalView
from antelligence.providers.base import Provider, ProviderError
from antelligence.worlds.tumor.policies import NanobotPolicy
from antelligence.worlds.tumor.world import SEARCHING

NANOBOT_WORDS = ("target", "follow_trail", "explore", "return")
NANOBOT_SYSTEM = "You are an intelligent nanobot. Respond with one word: target, follow_trail, explore, or return."
QUEEN_SYSTEM = ("You are a strategic Queen nanobot. Respond only with valid JSON in the format: "
                "{\"guidance\": {\"nanobot_id\": [dx, dy]}, \"report\": \"str\"}")


def nanobot_prompt(obs: Mapping[str, Any]) -> str:
    ctx = obs["legacy"]
    local = ctx["local"]
    types = ctx["cell_types_within_50"]
    bbb = ctx["nearest_vessel_bbb"]
    x, y = obs["pos"]
    return f"""You are an intelligent nanobot carrying anti-cancer drugs through a complex tumor microenvironment.

CURRENT STATUS:
- Position: ({x:.1f}, {y:.1f}) µm
- Drug payload: {obs['payload']:.1f}/{obs['max_payload']} units
- Deliveries made: {ctx['deliveries']}

LOCAL MICROENVIRONMENT:
- Oxygen: {local['oxygen']:.2f} mmHg (low = hypoxic tumor region, good target)
- Drug concentration: {local['drug']:.2f} (already treated area?)
- Trail pheromone: {local['trail_pheromone']:.2f} (successful delivery paths)
- Alarm pheromone: {local['alarm_pheromone']:.2f} (problems/toxicity reported)

IMMUNE SYSTEM SIGNALS:
- IFN-gamma: {local['ifn_gamma']:.2f} (T-cell activity, enhances immune response)
- TNF-alpha: {local['tnf_alpha']:.2f} (macrophage activity, pro-inflammatory)
- Perforin: {local['perforin']:.2f} (NK cell activity, cytotoxic)

MULTI-DRUG THERAPY:
- Drug A: {local['drug_a']:.2f} (primary therapeutic agent)
- Drug B: {local['drug_b']:.2f} (secondary/synergistic agent)

TUMOR CELL ANALYSIS (within 50µm):
- Total cells: {ctx['cells_within_50']}
- Stem cells: {types.get('stem_cell', 0)} (highly resistant, need more drug)
- Differentiated: {types.get('differentiated', 0)} (normal sensitivity)
- Resistant: {types.get('resistant', 0)} (developed resistance)
- Invasive: {types.get('invasive', 0)} (more sensitive)
- Average resistance level: {ctx['avg_resistance_within_50']:.2f} (0=no resistance, 1=fully resistant)

IMMUNE CELL ACTIVITY:
- Active immune cells nearby: {ctx['active_immune_within_50']}
- Average activation: {ctx['immune_activation_within_50']:.2f} (0=inactive, 1=fully active)

BLOOD-BRAIN BARRIER:
- Nearest vessel BBB permeability: {bbb:.2f} (0.05=very restrictive, 0.3=leaky tumor vessels)

STRATEGIC CONSIDERATIONS:
- Stem cells require 3x more drug than regular cells
- Immune cells make tumor cells more vulnerable to drugs
- High resistance areas need sustained drug delivery
- BBB restricts drug transport (only {bbb * 100:.0f}% passes through)
- Multi-drug combinations can overcome resistance

ACTIONS:
- 'target': Lock onto specific tumor cell (prioritize stem cells if payload sufficient)
- 'follow_trail': Follow pheromone trail to known effective areas
- 'explore': Use chemotaxis to find new targets (avoid high resistance areas)
- 'return': Return to vessel to reload (especially if near BBB vessels)

What should you do? Respond with ONE word only."""


class LegacyNanobot:
    """A legacy nanobot; LLM-driven when given a provider, rule-based otherwise."""

    def __init__(self, rule: NanobotPolicy, provider: Optional[Provider] = None, model: Optional[str] = None) -> None:
        if provider is not None and not model:
            raise ValueError("an LLM nanobot needs a model")
        self.rule = rule
        self.provider = provider
        self.model = model

    def describe(self) -> Dict[str, Any]:
        brain = {"brain": "rule"} if self.provider is None else {
            "brain": "llm", "model": self.model, "provider": self.provider.describe()}
        return {"policy": "legacy_nanobot", **brain, "rule": self.rule.describe()}

    async def decide(self, view: LocalView) -> Intent:
        obs = view.observation
        if obs["state"] != SEARCHING or obs["payload"] <= 2.0 or obs["cells"]:
            return self.rule.decide(view)  # missions, reloads and "nearest sensed cell" are rule behavior
        guidance = obs.get("queen_guidance")
        if guidance:
            return Intent("move", {"direction": guidance}, rationale="queen guidance")
        if self.provider is None:
            return self.rule.decide(view)
        try:
            text, meta = await ask(self.provider, self.model, NANOBOT_SYSTEM, nanobot_prompt(obs),
                                   temperature=0.3, max_tokens=10)
        except ProviderError as exc:
            return self._fallback(view, {"policy": "legacy_nanobot", "fallback": f"provider:{exc}"[:200]})
        word = one_word(text, NANOBOT_WORDS) or "explore"  # legacy: anything else means explore
        meta = {"policy": "legacy_nanobot", "word": word, **meta}
        ctx = obs["legacy"]
        if word == "target" and ctx["nearest_hypoxic_within_reach"]:
            cell = ctx["nearest_hypoxic_within_reach"]
            return Intent("target", {"cell_id": cell["id"]}, rationale="llm: target", meta=meta)
        if word == "follow_trail":
            dx, dy = ctx["trail_direction"]
            norm = math.hypot(dx, dy)
            if norm > 0:
                return Intent("move", {"direction": [dx / norm, dy / norm]}, rationale="llm: follow_trail", meta=meta)
        return self._fallback(view, meta)

    def _fallback(self, view: LocalView, meta: Dict[str, Any]) -> Intent:
        rule = self.rule.decide(view)
        return Intent(rule.action, rule.params, emit=rule.emit, rationale=rule.rationale, cites=rule.cites,
                      meta={**meta, **dict(rule.meta)})


class LegacyQueen:
    """The legacy QueenNanobot: heuristic, or LLM when given a provider."""

    def __init__(self, provider: Optional[Provider] = None, model: Optional[str] = None) -> None:
        if provider is not None and not model:
            raise ValueError("an LLM Queen needs a model")
        self.provider = provider
        self.model = model

    def describe(self) -> Dict[str, Any]:
        if self.provider is None:
            return {"policy": "legacy_queen", "brain": "heuristic"}
        return {"policy": "legacy_queen", "brain": "llm", "model": self.model, "provider": self.provider.describe()}

    async def decide(self, view: LocalView) -> Intent:
        obs = view.observation
        if not obs.get("turn"):
            return Intent("noop")
        if self.provider is None:
            return _guide(_heuristic(obs), "heuristic")
        try:
            text, meta = await ask(self.provider, self.model, QUEEN_SYSTEM, queen_prompt(obs),
                                   temperature=0.2, max_tokens=300)
        except ProviderError as exc:
            return _guide(_heuristic(obs), "heuristic", {"fallback": f"provider:{exc}"[:200]})
        meta = {"policy": "legacy_queen", **meta}
        parsed = json_object(text) or {}
        guidance = _parse_guidance(parsed.get("guidance"), obs)
        if guidance:
            report = parsed.get("report")
            return _guide(guidance, f"llm: {report}"[:300] if isinstance(report, str) else "llm", meta)
        return _guide(_enhanced_heuristic(obs), "enhanced heuristic", {**meta, "fallback": "reply:no usable guidance"})


def queen_prompt(obs: Mapping[str, Any]) -> str:
    types, immune = obs["cell_types"], obs["immune_types"]
    total = obs["total_cells"]
    survival = obs["living_cells"] / total if total else 0.0
    return f"""You are the Queen nanobot coordinating a swarm of {len(obs['bots'])} nanobots in a complex tumor microenvironment.

TUMOR STATUS:
- Total cells: {total}
- Living cells: {obs['living_cells']}
- Survival rate: {survival:.2%}

CELL TYPE DISTRIBUTION:
- Stem cells: {types.get('stem_cell', 0)} (highly resistant, priority targets)
- Differentiated: {types.get('differentiated', 0)} (normal sensitivity)
- Resistant: {types.get('resistant', 0)} (developed resistance)
- Invasive: {types.get('invasive', 0)} (more sensitive)

IMMUNE SYSTEM STATUS:
- T cells: {immune.get('t_cell', 0)} (adaptive immunity)
- Macrophages: {immune.get('macrophage', 0)} (phagocytosis)
- NK cells: {immune.get('nk_cell', 0)} (innate cytotoxicity)
- Dendritic: {immune.get('dendritic', 0)} (antigen presentation)

STRATEGIC PRIORITIES:
- Stem cell regions: {len(obs['stem'])} (require sustained drug delivery)
- High resistance areas: {len(obs['resistant'])} (need multi-drug approach)
- Immune active zones: {len(obs['immune_active'])} (synergistic opportunities)

NANOBOT STATUS:
- Total deliveries: {obs['deliveries']}
- Total drug delivered: {obs['drug_delivered']:.1f}
- Cells killed: {obs['cells_killed']}

COORDINATION STRATEGY:
1. Direct nanobots to stem cell regions (highest priority)
2. Avoid over-concentrating in already treated areas
3. Leverage immune-active regions for synergistic effects
4. Consider BBB permeability when planning reload routes

Provide guidance for nanobot positioning and targeting priorities."""


def _guide(guidance: Dict[str, List[float]], why: str, meta: Optional[Dict[str, Any]] = None) -> Intent:
    if not guidance:
        return Intent("noop", rationale=f"queen {why}: nobody to guide", meta=meta or {})
    return Intent("guide", {"guidance": guidance}, rationale=f"queen {why}", meta=meta or {})


def _ready(obs: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    """Legacy guided only searching bots with more than half a payload."""
    return {name: bot for name, bot in obs["bots"].items()
            if bot["state"] == SEARCHING and bot["payload"] > bot["max_payload"] * 0.5}


def _unit_toward(src, dst) -> Optional[List[float]]:
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    norm = math.hypot(dx, dy)
    return [round(dx / norm, 6), round(dy / norm, 6)] if norm > 0 else None


def _heuristic(obs: Mapping[str, Any]) -> Dict[str, List[float]]:
    hypoxic = obs["hypoxic"]
    guidance: Dict[str, List[float]] = {}
    if not hypoxic:
        return guidance
    for name, bot in _ready(obs).items():
        nearest = min(hypoxic, key=lambda p: math.hypot(p[0] - bot["pos"][0], p[1] - bot["pos"][1]))
        direction = _unit_toward(bot["pos"], nearest)
        if direction:
            guidance[name] = direction
    return guidance


def _enhanced_heuristic(obs: Mapping[str, Any]) -> Dict[str, List[float]]:
    guidance: Dict[str, List[float]] = {}
    for name, bot in _ready(obs).items():
        best, best_priority = None, 0.0
        for weight, regions in ((3.0, obs["stem"]), (2.0, obs["immune_active"]), (1.5, obs["resistant"])):
            for pos in regions:
                distance = math.hypot(pos[0] - bot["pos"][0], pos[1] - bot["pos"][1])
                if distance > 0 and weight / (distance + 1) > best_priority:
                    best, best_priority = _unit_toward(bot["pos"], pos), weight / (distance + 1)
        if best:
            guidance[name] = best
    return guidance


def _parse_guidance(raw: Any, obs: Mapping[str, Any]) -> Dict[str, List[float]]:
    """Legacy keys bots by integer index ("0", "1", ...); engine bots are bot-000, bot-001, ..."""
    guidance: Dict[str, List[float]] = {}
    if not isinstance(raw, dict):
        return guidance
    for key, direction in raw.items():
        try:
            name = f"bot-{int(key):03d}"
            dx, dy = float(direction[0]), float(direction[1])
        except (ValueError, TypeError, IndexError, KeyError):
            continue
        if name in obs["bots"] and len(direction) == 2 and math.isfinite(dx) and math.isfinite(dy):
            norm = math.hypot(dx, dy)
            if norm > 0:
                guidance[name] = [round(dx / norm, 6), round(dy / norm, 6)]
    return guidance
