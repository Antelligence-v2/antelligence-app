"""Arms for the ant colony world: the legacy Queen vs No-Queen comparison.

* ``no_queen`` — ants (and predators) forage on their own.
* ``queen``    — a body-less Queen at the nest guides every ant every tick.

Brains are options, as in the legacy UI: ``agent_type`` / ``predator_type``
(Rule-Based, LLM-Powered, Hybrid = first half LLM), ``queen_brain``
(heuristic, llm) and ``prompt_style`` (Adaptive, Structured, Autonomous).
"""

from __future__ import annotations

from typing import Optional

from antelligence.kernel.field import GridField
from antelligence.kernel.scheduler import RunConfig, Scheduler
from antelligence.providers.base import Provider
from antelligence.worlds.ant_colony.policies import PROMPT_STYLES, ColonyAnt, ColonyPredator, ColonyQueen
from antelligence.worlds.ant_colony.world import QUEEN, AntColonyWorld, Deposits

ARMS = ("no_queen", "queen")
AGENT_TYPES = ("Rule-Based", "LLM-Powered", "Hybrid")
QUEEN_BRAINS = ("heuristic", "llm")
SEEDS = tuple(range(42, 52))  # legacy always ran seed 42


def _llm_indices(kind: str, n: int) -> set:
    if kind == "LLM-Powered":
        return set(range(n))
    if kind == "Hybrid":
        return set(range(n // 2))
    return set()


def needs_llm(agent_type: str, predator_type: str, n_predators: int, arm: Optional[str], queen_brain: str) -> bool:
    return (agent_type != "Rule-Based" or (n_predators > 0 and predator_type != "Rule-Based")
            or (arm in (None, "queen") and queen_brain == "llm"))


def build(
    arm: str,
    seed: int,
    *,
    width: int = 20,
    height: int = 20,
    n_ants: int = 10,
    n_food: int = 15,
    n_predators: int = 0,
    max_steps: int = 200,
    agent_type: str = "Rule-Based",
    predator_type: str = "Rule-Based",
    queen_brain: str = "heuristic",
    prompt_style: str = "Adaptive",
    deposits: Optional[Deposits] = None,
    provider: Optional[Provider] = None,
    model: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Scheduler:
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    for name, value, allowed in (("agent_type", agent_type, AGENT_TYPES), ("predator_type", predator_type, AGENT_TYPES),
                                 ("queen_brain", queen_brain, QUEEN_BRAINS), ("prompt_style", prompt_style, PROMPT_STYLES)):
        if value not in allowed:
            raise ValueError(f"{name} must be one of {allowed}")
    llm = needs_llm(agent_type, predator_type, n_predators, arm, queen_brain)
    if llm and (provider is None or not model):
        raise ValueError("LLM agents need a provider and a model")
    llm_ants, llm_predators = _llm_indices(agent_type, n_ants), _llm_indices(predator_type, n_predators)
    world = AntColonyWorld(seed, width=width, height=height, n_ants=n_ants, n_food=n_food, n_predators=n_predators,
                           max_steps=max_steps, llm_ants=llm_ants, llm_predators=llm_predators, queen=arm == "queen",
                           deposits=deposits)
    rule_ant, rule_predator = ColonyAnt(), ColonyPredator()
    llm_ant = ColonyAnt(provider, model, prompt_style) if llm_ants else None
    llm_predator = ColonyPredator(provider, model, prompt_style) if llm_predators else None
    policies: dict = {}
    for name, ant in world.ants.items():
        policies[name] = llm_ant if ant.is_llm else rule_ant
    for name, predator in world.predators.items():
        policies[name] = llm_predator if predator.is_llm else rule_predator
    if arm == "queen":
        policies[QUEEN] = ColonyQueen(provider, model) if queen_brain == "llm" else ColonyQueen()
    config = RunConfig(run_id or f"ant-colony-{seed}", seed=seed, max_ticks=max_steps, arm=arm)
    return Scheduler(world, policies, GridField(), config)
