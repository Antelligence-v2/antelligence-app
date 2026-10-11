"""Arm assembly for the framework arms (the per-agent policy map).

Recipes (``model`` is the decision model id; the backend decides escalation)::

    F-Laya        framework_policies(.., backend=EscalatingBackend(laya, slm), use_queen=True,  queen=LLMQueen(..))
    F-Jev         framework_policies(.., backend=EscalatingBackend(jev, slm),  use_queen=True,  queen=LLMQueen(..))
    F-Jev-noQueen framework_policies(.., backend=EscalatingBackend(jev, slm),  use_queen=False)
                  and world = HiveWorld(inner, fn, queen=False)  -- every action allowed, no board traffic read
    F-Jev-noEsc   framework_policies(.., backend=jev,                          use_queen=True,  queen=LLMQueen(..))
    DS-all/Q-all  {agent: StateChatPolicy(provider, model, sensor) for agent in agents}  (no queen, no HiveWorld)

Escalation is purely a backend property, so "no escalation" is just handing in the bare primary backend.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence

from antelligence.kernel.decision import DecisionBackend, Sensor
from antelligence.kernel.policies.decision_worker import DecisionWorker
from antelligence.kernel.types import Policy

QUEEN_ID = "queen"


def framework_policies(world_agents: Sequence[str], groups: Mapping[str, Sequence[str]], backend: DecisionBackend,
                       sensor: Sensor, model: str, *, use_queen: bool, queen: Optional[Policy] = None,
                       max_checks: int = 2, report_ttl: int = 10) -> Dict[str, Policy]:
    """Per-agent policy map: a DecisionWorker for every worker, plus the queen when ``use_queen``.

    ``report_ttl`` is how long a worker report stays on the board; it must be >= the queen's cadence.
    """
    group_of: Dict[str, str] = {}
    for group, members in groups.items():
        for agent in members:
            if agent in group_of:
                raise ValueError(f"agent {agent!r} is in two groups")
            group_of[agent] = group
    workers = [a for a in world_agents if a != QUEEN_ID]
    missing = [a for a in workers if a not in group_of]
    if missing:
        raise ValueError(f"agents without a group: {missing}")
    policies: Dict[str, Policy] = {
        a: DecisionWorker(backend, sensor, group_of[a], model=model, use_queen=use_queen, max_checks=max_checks,
                          report_ttl=report_ttl)
        for a in workers}
    if use_queen:
        if queen is None:
            raise ValueError("use_queen=True needs a queen policy")
        policies[QUEEN_ID] = queen
    return policies
