"""Task-DAG world (E15): partial-view planners, deterministic merge, model-free admission.

One run is one fixture (seed) under one arm and lasts one tick:

* **observe** — each planner receives its view. ``solo_planner`` sees the whole
  public fixture; each ``swarm_partitioned*`` agent sees only its own sample's
  slice plus a delegated slot. The observation carries the exact E15 prompt
  (``prompt``) and the structured view (``fixture``); private evaluator fields
  never appear.
* **apply** — ``propose`` submits a DAG, validated by E15's ``parse_proposal``.
* **reconcile** (``step_environment``) — raw union, or E15's deterministic
  ``merge_partitioned`` for the merged arm, then the unchanged five-rule
  ``admit`` gate (run twice to check determinism) and execution against the
  real F2 verifier.

The admission gate and merge are properties of the world (the environment's
rules), not agents: no model call happens after proposals are in.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from antelligence.kernel.field import SenseQuery
from antelligence.kernel.types import Intent, Observation, Outcome
from antelligence.worlds.task_dag.planning import (
    admission_bytes,
    admit,
    assert_partition_coverage,
    delegated_slots,
    execute_admitted,
    fixture_task,
    merge_partitioned,
    parse_proposal,
    prompt_for,
)

ARMS = ("solo_planner", "swarm_partitioned", "swarm_partitioned_merged")
PUBLIC_FIELDS = ("protocol", "revision", "max_actions", "sample_kinds", "slot_zones", "rules", "prerequisites",
                 "resources", "requirements")
PROPOSE = "propose"


def public_fixture(task: Dict[str, Any]) -> Dict[str, Any]:
    return {key: task[key] for key in PUBLIC_FIELDS}


def partitioned_slice(task: Dict[str, Any], sample: str) -> Dict[str, Any]:
    """The E15 per-agent slice (same fields as the paper's partitioned prompt)."""
    return {
        "protocol": task["protocol"],
        "revision": task["revision"],
        "max_actions": task["max_actions"],
        "sample_kinds": task["sample_kinds"],
        "slot_zones": task["slot_zones"],
        "rules": task["rules"],
        "resources": task["resources"],
        "my_sample": sample,
        "my_slot": delegated_slots(task)[sample],
        "requirements": {sample: task["requirements"].get(sample)},
        "prerequisites": {sample: task["prerequisites"].get(sample, [])},
    }


def _malformed_action(proposal: Dict[str, Any]) -> Optional[str]:
    for node in proposal["nodes"]:
        action = node["action"]
        for key in ("op", "sample", "slot"):
            if key in action and not isinstance(action[key], str):
                return f"node {node['id']!r}: {key} must be a string"
        if "revision" in action and (isinstance(action["revision"], bool) or not isinstance(action["revision"], int)):
            return f"node {node['id']!r}: revision must be an integer"
        if "resource" in node and not isinstance(node["resource"], (str, type(None))):
            return f"node {node['id']!r}: resource must be a string"
    return None


class TaskDAGWorld:
    def __init__(self, seed: int, arm: str, *, composition: Optional[str] = None) -> None:
        if arm not in ARMS:
            raise ValueError(f"unknown arm {arm!r}")
        self.seed = seed
        self.arm = arm
        self.task = fixture_task(seed, composition)
        self.composition = self.task["composition"]
        if arm == "solo_planner":
            self.slices = {"solo": None}
        else:
            self.slices = assert_partition_coverage(self.task)  # fails loudly if under-provisioned
        self.proposals: Dict[str, Dict[str, Any]] = {}
        self.parse_errors = 0
        self.result: Optional[Dict[str, Any]] = None
        self._revision = 0

    # ------------------------------------------------------------- contract
    @property
    def revision(self) -> int:
        return self._revision

    def agents(self) -> List[str]:
        return sorted(self.slices)

    def describe(self) -> Dict[str, Any]:
        return {"world": "task_dag", "version": "e15-fixed-provisioning-v4", "seed": self.seed, "arm": self.arm,
                "composition": self.composition}

    def observe(self, agent_id: str, tick: int) -> Observation:
        prompt_arm = "swarm_partitioned" if self.arm == "swarm_partitioned_merged" else self.arm
        sample = self.slices[agent_id]
        fixture = public_fixture(self.task) if sample is None else partitioned_slice(self.task, sample)
        data = {"agent": agent_id, "arm": prompt_arm, "fixture": fixture,
                "prompt": prompt_for(self.task, self.seed, prompt_arm, agent_id)}
        return Observation(data, SenseQuery(topic=f"dag:{self.seed}", kinds=frozenset()))

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        if intent.action != PROPOSE:
            self.parse_errors += 1
            return Outcome(False, "no_proposal" if intent.action == "noop" else "unknown_action")
        try:
            proposal = parse_proposal(json.dumps(intent.params.get("proposal")))
        except ValueError as exc:
            self.parse_errors += 1
            return Outcome(False, f"unparseable_proposal: {exc}")
        problem = _malformed_action(proposal)
        if problem:
            # E15's admission gate assumes scalar action fields and crashes on e.g. a
            # list-valued "op"; reject such proposals here instead.
            self.parse_errors += 1
            return Outcome(False, f"malformed_action: {problem}")
        proposal["agent"] = agent_id
        self.proposals[agent_id] = proposal
        return Outcome(True, effects={"nodes": len(proposal["nodes"])})

    def step_environment(self, tick: int) -> None:
        proposals = [self.proposals[a] for a in self.agents() if a in self.proposals]
        admitted_input = [merge_partitioned(self.task, proposals)] if self.arm == "swarm_partitioned_merged" \
            else proposals
        first = admit(self.task, admitted_input)
        second = admit(self.task, admitted_input)
        light = execute_admitted(self.task, first, False)  # the paper's execution check for these arms
        full = execute_admitted(self.task, first, True)  # stricter: replay every action in the F2 verifier
        self.result = {"admission": first, "deterministic": admission_bytes(first) == admission_bytes(second),
                       "execution": light, "full_verifier": full}
        self._revision = tick

    def done(self, tick: int) -> bool:
        return tick >= 1

    def metrics(self) -> Dict[str, Any]:
        if self.result is None:
            return {"composition": self.composition, "reconciled": False}
        admission, execution, full = self.result["admission"], self.result["execution"], self.result["full_verifier"]
        return {
            "composition": self.composition,
            "reconciled": True,
            "proposals": len(self.proposals),
            "parse_errors": self.parse_errors,
            "proposed_nodes": admission["proposed_node_count"],
            "unique_nodes": admission["unique_node_count"],
            "accepted_nodes": admission["accepted_count"],
            "rejection_breakdown": admission["rejection_breakdown"],
            "deterministic": self.result["deterministic"],
            "success": execution["success"],
            "classification": execution["classification"],
            "verifier_classification": full["classification"],
            "unsafe_act_count": full["unsafe_act_count"],
        }
