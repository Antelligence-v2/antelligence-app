"""Task-DAG planners.

* :class:`ScriptedPlanner` — E15's offline stand-ins: the solo planner proposes
  the full-information reference plan; a partitioned agent proposes the
  reserve/place sub-DAG for its own sample and delegated slot. Both work only
  from their observation.
* :class:`LLMPlanner` — sends the exact E15 prompt from the observation, parses
  with E15's ``parse_proposal`` and retries once with the paper's retry
  suffix. Unparseable twice -> ``noop`` (a parse error, as in E15).
"""

from __future__ import annotations

from typing import Any, Dict

from antelligence.kernel.types import Intent, LocalView
from antelligence.providers.base import ChatRequest, Provider
from antelligence.worlds.task_dag.planning import parse_proposal, record_for_plan, reference_solve
from antelligence.worlds.task_dag.world import PROPOSE

RETRY_SUFFIX = ("\nYour previous output was invalid. Return one JSON object now; ensure goal exactly names "
                "one node id in nodes.")


class ScriptedPlanner:
    def describe(self) -> Dict[str, Any]:
        return {"policy": "task_dag_scripted"}

    def decide(self, view: LocalView) -> Intent:
        fixture = view.observation["fixture"]
        if "my_sample" not in fixture:
            plan = reference_solve(fixture)
            if plan is None:  # E15's stand-in for infeasible fixtures
                plan = [{"op": "reserve", "sample": name, "slot": "slot-0", "revision": fixture["revision"]}
                        for name in fixture["sample_kinds"]]
            proposal = record_for_plan(fixture, plan, view.agent_id)
        else:
            sample, slot = fixture["my_sample"], fixture["my_slot"]
            evidence = [{"source_id": "fixture", "revision": fixture["revision"]}]
            resource = fixture["requirements"][sample]
            proposal = {"goal": "n1", "nodes": [
                {"id": "n0", "parents": [], "resource": resource, "evidence": evidence,
                 "action": {"op": "reserve", "sample": sample, "slot": slot, "revision": fixture["revision"]}},
                {"id": "n1", "parents": ["n0"], "resource": resource, "evidence": evidence,
                 "action": {"op": "place", "sample": sample, "slot": slot, "revision": fixture["revision"]}},
            ]}
        proposal.pop("agent", None)
        return Intent(PROPOSE, {"proposal": proposal})


class LLMPlanner:
    def __init__(self, provider: Provider, model: str, *, max_tokens: int = 2200, temperature: float = 0.0) -> None:
        self.provider = provider
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def describe(self) -> Dict[str, Any]:
        return {"policy": "task_dag_llm", "model": self.model, "provider": self.provider.describe(),
                "max_tokens": self.max_tokens, "temperature": self.temperature}

    async def decide(self, view: LocalView) -> Intent:
        prompt = view.observation["prompt"]
        meta: Dict[str, Any] = {"policy": "task_dag_llm", "calls": 0, "parse_errors": 0}
        for attempt in (prompt, prompt + RETRY_SUFFIX):
            response = await self.provider.complete(ChatRequest(
                model=self.model, messages=({"role": "user", "content": attempt},),
                max_tokens=self.max_tokens, temperature=self.temperature))
            meta["calls"] += 1
            meta.setdefault("request_hashes", []).append(response.request_hash)
            try:
                proposal = parse_proposal(response.content)
            except ValueError:
                meta["parse_errors"] += 1
                continue
            return Intent(PROPOSE, {"proposal": proposal}, meta=meta)
        return Intent("noop", meta=meta)
