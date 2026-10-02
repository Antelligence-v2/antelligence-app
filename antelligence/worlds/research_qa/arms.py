"""Wire research-QA protocols onto the engine and emit Workbench-compatible cells.

``build`` returns a Scheduler for one (task, protocol). ``cell`` converts the
finished run into the same cell shape ``backend.swarm_core.summarize``
consumes, so Wilson bounds and gates are computed by the existing code.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Optional

from antelligence.kernel.admission import AdmissionPolicy
from antelligence.kernel.field import BoardField
from antelligence.kernel.scheduler import RunConfig, RunResult, Scheduler
from antelligence.kernel.types import Policy
from antelligence.worlds.research_qa.world import PROTOCOLS, ResearchQAWorld

PolicyFactory = Callable[[str], Policy]


def _claim_payload(payload: Mapping[str, Any]) -> Optional[str]:
    if set(payload) != {"answer", "evidence_ids", "brief"}:
        return "claim_fields"
    if len(payload["brief"]) > 160 or len(payload["evidence_ids"]) > 3:
        return "claim_bounds"
    return None


def _safe_id(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in text)


def build(task: Mapping[str, Any], protocol: str, policy_factory: PolicyFactory, *, seed: int = 0,
          run_id: Optional[str] = None) -> Scheduler:
    world = ResearchQAWorld(task, protocol)
    p = PROTOCOLS[protocol]
    config = RunConfig(run_id or f"qa-{_safe_id(world.task_id)}", seed=seed, max_ticks=p.rounds, arm=protocol,
                       max_emits_per_tick=1)
    admission = AdmissionPolicy(kinds={"claim": _claim_payload}, max_ttl=1, max_per_topic_per_tick=p.agents,
                                require_known_parents=True)
    policies = {agent: policy_factory(agent) for agent in world.agents()}
    return Scheduler(world, policies, BoardField(), config, admission=admission)


def cell(result: RunResult, *, model_keys, usage: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Workbench cell (see backend.swarm_core.summarize)."""
    m = result.metrics
    usage = usage or {}
    return {
        "task_id": m["task_id"],
        "domain": m["domain"],
        "protocol": m["protocol"],
        "variant": m["protocol"],
        "model_keys": list(model_keys),
        "status": m["status"],
        "answer": m["answer"],
        "correct": m["correct"],
        "call_count": usage.get("calls", 0),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "elapsed_s": usage.get("elapsed_s", 0.0),
        "usage_complete": bool(usage) and usage.get("failed_calls", 0) == 0,
        "trace_hash": result.trace_hash,
        "config_hash": result.config_hash,
    }
