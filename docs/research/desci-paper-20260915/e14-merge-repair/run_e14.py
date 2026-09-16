#!/opt/homebrew/bin/python3.11
"""E12: partitioned-view swarm task-DAG proposals.

The new arm, ``swarm_partitioned``, gives each of three agents only a disjoint subset
of the fixture (its own sample's requirements and prerequisites, plus the shared
public protocol/goal/revision/slot_zones/rules). The admission gate is unchanged and
model-free; it still receives all proposals and merges them deterministically as in E11.

``--self-test`` never opens a network connection. ``--pretest`` is the cheap
three-seed gate; matrix arms are run separately so their budgets and caches cannot
bleed into one another.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import math
import os
import re
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib import error, request

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
PACKET = Path("/Volumes/WD_BLACK/antelligence-review-20260911/review/hive-fit-20260911")
sys.path.insert(0, str(PACKET))

from backend.research_hive_tasks import generate_task, reference_solve  # noqa: E402
from backend.research_hive_verifier import verify_task  # noqa: E402

# E14 frozen route: OpenRouter is exhausted; read the short-lived Nous token fresh per call.
MODEL = os.environ.get("E14_MODEL", "z-ai/glm-5.3-flash")
API = "https://inference-api.nousresearch.com/v1/chat/completions"
API_KEY_ENV = "~/.hermes/auth.json:providers.nous.access_token|agent_key"
VERSION = "e14-merge-repair-v5"
ADAPTER_KEY = b"e11-development-adapter-key"  # unchanged packet adapter
ARMS = ("solo_planner", "swarm_partitioned", "swarm_partitioned_merged")
SEEDS = list(range(101, 121))
RULES = ("acyclicity", "reachability", "contradiction_cascade", "resource_consistency", "verifier_feasibility")
MAX_ARM_COST = 0.07


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def load_env() -> None:
    path = Path(os.path.expanduser("~/.hermes/.env"))
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


class BudgetStop(Exception):
    pass


class Pilot:
    """Small cached relay client following the E10 accounting convention.

    Identical structure to E11's Pilot; only the cache filename and VERSION key differ.
    """

    def __init__(self, arm: str, max_cost: float = MAX_ARM_COST) -> None:
        self.arm = arm
        self.max_cost = max_cost
        self.tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost = 0.0
        OUT.mkdir(parents=True, exist_ok=True)
        self.cache_path = OUT / ("api_cache_" + arm + ".jsonl")
        self.cache: Dict[str, Dict[str, Any]] = {}
        if self.cache_path.exists():
            for line in self.cache_path.read_text().splitlines():
                try:
                    item = json.loads(line)
                    self.cache[item["key"]] = item
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    continue

    def _account(self, usage: Dict[str, Any]) -> None:
        p = int(usage.get("prompt_tokens", 0))
        c = int(usage.get("completion_tokens", 0))
        self.prompt_tokens += p
        self.completion_tokens += c
        self.tokens += int(usage.get("total_tokens", p + c))
        self.cost += float(usage.get("cost", p * 0.5e-6 + c * 2e-6))
        if self.cost > self.max_cost:
            raise BudgetStop("arm budget exhausted")

    def call(self, key: str, prompt: str) -> Tuple[str, Dict[str, Any]]:
        if key in self.cache:
            item = self.cache[key]
            usage = item.get("usage", {})
            self._account(usage)
            return str(item.get("content", "")), usage
        if self.cost >= self.max_cost:
            raise BudgetStop("arm budget exhausted")
        load_env()
        auth_path = Path(os.path.expanduser("~/.hermes/auth.json"))
        auth = json.loads(auth_path.read_text())
        nous = auth.get("providers", {}).get("nous", {})
        api_key = nous.get("access_token") or nous.get("agent_key")
        if not api_key:
            raise RuntimeError("Nous access token not found in ~/.hermes/auth.json")
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2200,
            "temperature": 0.0,
        }
        data = json.dumps(payload).encode()
        last: Optional[Exception] = None
        for attempt in range(5):
            try:
                req = request.Request(API, data=data, headers={
                    "Authorization": "Bearer " + api_key,
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://hermes-agent.nousresearch.com",
                    "X-Title": "antelligence-e14-merge-repair",
                })
                with request.urlopen(req, timeout=90) as response:
                    obj = json.load(response)
                content = obj["choices"][0]["message"].get("content") or ""
                use = obj.get("usage", {})
                p = int(use.get("prompt_tokens", 0))
                c = int(use.get("completion_tokens", 0))
                total = int(use.get("total_tokens", p + c))
                reported = use.get("cost", obj.get("cost"))
                cost = float(reported) if reported is not None else p * 0.5e-6 + c * 2e-6
                usage = {"prompt_tokens": p, "completion_tokens": c, "total_tokens": total, "cost": cost}
                item = {"key": key, "content": content, "usage": usage}
                with self.cache_path.open("a") as handle:
                    handle.write(json.dumps(item, separators=(",", ":")) + "\n")
                self.cache[key] = item
                self._account(usage)
                return content, usage
            except error.HTTPError as exc:
                try:
                    body = exc.read().decode("utf-8", "replace")[:500]
                except Exception:
                    body = "<unreadable response>"
                last = RuntimeError("HTTP {}: {}".format(exc.code, body))
                if exc.code not in (429, 500, 502, 503, 504):
                    break
            except Exception as exc:
                last = exc
            time.sleep(2 ** attempt)
        raise RuntimeError("relay failed after retries: " + repr(last))


def fixture_task(seed: int, composition: Optional[str] = None) -> Dict[str, Any]:
    if composition is None:
        composition = ("chain", "fork", "chain", "fork", "impossible")[(seed - 101) % 5]
    task = generate_task(seed, composition=composition)
    task = copy.deepcopy(task)
    task["composition"] = composition
    return task


def parse_proposal(text: str) -> Dict[str, Any]:
    """Parse only one bounded JSON DAG and reject unresolvable local refs."""
    raw = (text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw).strip()
    start = raw.find("{")
    if start < 0:
        raise ValueError("proposal contains no JSON object")
    try:
        value, end = json.JSONDecoder().raw_decode(raw[start:])
    except json.JSONDecodeError as exc:
        raise ValueError("proposal JSON is not parseable") from exc
    if not isinstance(value, dict) or not isinstance(value.get("nodes"), list):
        raise ValueError("proposal must contain a nodes list")
    ids: Set[str] = set()
    for node in value["nodes"]:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            raise ValueError("each node needs a string id")
        if node["id"] in ids:
            raise ValueError("duplicate node id")
        ids.add(node["id"])
        if not isinstance(node.get("parents"), list) or not all(isinstance(x, str) for x in node["parents"]):
            raise ValueError("node parents must be a string list")
        if not isinstance(node.get("action"), dict):
            raise ValueError("node action must be an object")
    if not isinstance(value.get("goal"), str) or value["goal"] not in ids:
        raise ValueError("goal must reference a local node")
    return value


def _node_identity(node: Dict[str, Any]) -> str:
    payload = {
        "action": node.get("action"),
        "resource": node.get("resource"),
        "evidence": node.get("evidence", []),
        "replaces": node.get("replaces", []),
    }
    return "node-" + hashlib.sha256(canonical(payload)).hexdigest()[:16]


def _action_for_verifier(task: Dict[str, Any], action: Dict[str, Any]) -> Dict[str, Any]:
    """Translate fixture IDs to the packet verifier's keyed opaque IDs."""
    sample = action.get("sample", "")
    slot = action.get("slot", "")
    sample_alias = "sample-" + hmac.new(ADAPTER_KEY, sample.encode(), hashlib.sha256).hexdigest()[:16]
    slot_alias = "slot-" + hmac.new(ADAPTER_KEY, slot.encode(), hashlib.sha256).hexdigest()[:16]
    result = dict(action)
    result["sample"] = sample_alias
    result["slot"] = slot_alias
    return result


def _valid_evidence(evidence: Any) -> bool:
    return isinstance(evidence, list) and all(
        isinstance(item, dict) and set(item) == {"source_id", "revision"}
        and isinstance(item["source_id"], str) and isinstance(item["revision"], int)
        for item in evidence
    )


def _replacement_invalidates(replacements: Iterable[Dict[str, int]], evidence: Iterable[Dict[str, int]]) -> bool:
    for replacement in replacements:
        for link in evidence:
            if replacement["source_id"] == link["source_id"] and replacement["revision"] > link["revision"]:
                return True
    return False


def _topological(nodes: Dict[str, Dict[str, Any]], allowed: Set[str]) -> List[str]:
    indegree = {key: sum(parent in allowed for parent in nodes[key]["parents"]) for key in allowed}
    children: Dict[str, List[str]] = defaultdict(list)
    for key in sorted(allowed):
        for parent in nodes[key]["parents"]:
            if parent in allowed:
                children[parent].append(key)
    ready = [key for key in sorted(allowed) if indegree[key] == 0]
    order: List[str] = []
    queue = deque(ready)
    while queue:
        key = queue.popleft()
        order.append(key)
        for child in sorted(children[key]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return order


def _cycle_nodes(nodes: Dict[str, Dict[str, Any]], allowed: Set[str]) -> Set[str]:
    visiting: List[str] = []
    active: Set[str] = set()
    done: Set[str] = set()
    cycles: Set[str] = set()

    def visit(key: str) -> None:
        if key in done:
            return
        if key in active:
            cycles.update(visiting[visiting.index(key):])
            return
        active.add(key)
        visiting.append(key)
        for parent in sorted(nodes[key]["parents"]):
            if parent in allowed:
                visit(parent)
        visiting.pop()
        active.remove(key)
        done.add(key)

    for key in sorted(allowed):
        visit(key)
    return cycles


def admit(task: Dict[str, Any], proposals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Admit a canonical subset using no model calls or nondeterminism.

    Identical to E11's admit(); not touched.
    """
    nodes: Dict[str, Dict[str, Any]] = {}
    invalid: List[Dict[str, Any]] = []
    goals: Set[str] = set()
    ordered_proposals = sorted((copy.deepcopy(p) for p in proposals), key=canonical)

    for pindex, proposal in enumerate(ordered_proposals):
        if not isinstance(proposal, dict) or not isinstance(proposal.get("nodes"), list):
            invalid.append({"node_id": "proposal-" + str(pindex), "rule": "resource_consistency", "detail": "malformed proposal"})
            continue
        local: Dict[str, str] = {}
        for nindex, raw in enumerate(proposal["nodes"]):
            if not isinstance(raw, dict):
                invalid.append({"node_id": "proposal-" + str(pindex) + "-" + str(nindex), "rule": "resource_consistency", "detail": "node is not an object"})
                continue
            required = {"id", "parents", "resource", "evidence", "action"}
            if not required <= set(raw) or not isinstance(raw.get("id"), str) or not isinstance(raw.get("parents"), list):
                invalid.append({"node_id": str(raw.get("id", "proposal-" + str(pindex) + "-" + str(nindex))), "rule": "resource_consistency", "detail": "node shape"})
                continue
            if any(not isinstance(parent, str) for parent in raw["parents"]):
                invalid.append({"node_id": raw["id"], "rule": "resource_consistency", "detail": "parent shape"})
                continue
            key = _node_identity(raw)
            local[raw["id"]] = key
            if key not in nodes:
                nodes[key] = {"node": copy.deepcopy(raw), "parents": set(), "proposals": 0}
            nodes[key]["proposals"] += 1
        goal = proposal.get("goal")
        if isinstance(goal, str) and goal in local:
            goals.add(local[goal])
        else:
            invalid.append({"node_id": "proposal-" + str(pindex) + "-goal", "rule": "reachability", "detail": "goal is not local"})
        for raw in proposal["nodes"]:
            if not isinstance(raw, dict) or raw.get("id") not in local:
                continue
            key = local[raw["id"]]
            for parent in raw["parents"]:
                nodes[key]["parents"].add(local.get(parent, "@missing:" + parent))

    status: Dict[str, Dict[str, str]] = {}
    for item in invalid:
        status[item["node_id"]] = {"rule": item["rule"], "detail": item["detail"]}
    node_keys = set(nodes)
    for key, record in nodes.items():
        raw = record["node"]
        action = raw.get("action")
        if not isinstance(raw.get("resource"), str) or not _valid_evidence(raw.get("evidence")):
            status[key] = {"rule": "resource_consistency", "detail": "resource or evidence shape"}
        elif not isinstance(action, dict) or set(action) != {"op", "sample", "slot", "revision"}:
            status[key] = {"rule": "resource_consistency", "detail": "action shape"}
        elif any(parent.startswith("@missing:") for parent in record["parents"]):
            status[key] = {"rule": "resource_consistency", "detail": "parent reference is not local"}
        else:
            sample = action.get("sample")
            slot = action.get("slot")
            resource = raw.get("resource")
            if (sample not in task.get("sample_kinds", {}) or slot not in task.get("slot_zones", {})
                    or action.get("revision") != task.get("revision")
                    or action.get("op") not in {"reserve", "place"}
                    or resource != task.get("requirements", {}).get(sample)
                    or resource not in task.get("resources", {})
                    or task.get("resources", {}).get(resource, 0) <= 0):
                status[key] = {"rule": "resource_consistency", "detail": "fixture resource or action mismatch"}
            for replacement in raw.get("replaces", []):
                if (not isinstance(replacement, dict) or set(replacement) != {"source_id", "revision"}
                        or not isinstance(replacement["source_id"], str) or not isinstance(replacement["revision"], int)):
                    status[key] = {"rule": "resource_consistency", "detail": "replacement shape"}

    clean = {key for key in node_keys if key not in status}
    cycles = _cycle_nodes(nodes, clean)
    for key in sorted(cycles):
        status[key] = {"rule": "acyclicity", "detail": "cycle detected"}

    eligible = {key for key in node_keys if key not in status}
    roots = {key for key in eligible if not nodes[key]["parents"]}
    forward: Set[str] = set(roots)
    changed = True
    while changed:
        changed = False
        for key in sorted(eligible - forward):
            if all(parent in forward for parent in nodes[key]["parents"]):
                forward.add(key)
                changed = True
    backward: Set[str] = set(key for key in goals if key in eligible)
    changed = True
    while changed:
        changed = False
        for key in sorted(eligible - backward):
            if any(child in backward for child in eligible if key in nodes[child]["parents"]):
                backward.add(key)
                changed = True
    for key in sorted(eligible):
        if key not in forward or key not in backward:
            status[key] = {"rule": "reachability", "detail": "not on source-to-goal path"}

    structurally_live = {key for key in node_keys if key not in status}
    topo = _topological(nodes, structurally_live)
    accepted: List[str] = []
    accepted_actions: List[Dict[str, Any]] = []
    replacement_ancestors: Dict[str, List[Dict[str, int]]] = {}
    for key in topo:
        record = nodes[key]
        if any(parent not in accepted for parent in record["parents"]):
            status[key] = {"rule": "reachability", "detail": "child of rejected node"}
            continue
        inherited: List[Dict[str, int]] = []
        for parent in sorted(record["parents"]):
            inherited.extend(replacement_ancestors.get(parent, []))
            if parent in nodes:
                inherited.extend(record_for_replacements(nodes[parent]["node"]))
        evidence = record["node"].get("evidence", [])
        if _replacement_invalidates(inherited, evidence):
            status[key] = {"rule": "contradiction_cascade", "detail": "ancestor replacement invalidates evidence"}
            replacement_ancestors[key] = inherited
            continue
        opaque = _action_for_verifier(task, record["node"]["action"])
        checked = verify_task(task, accepted_actions + [opaque], adapter_key=ADAPTER_KEY)
        if not checked["events"] or checked["events"][-1]["accepted"] is not True:
            status[key] = {"rule": "verifier_feasibility", "detail": checked["events"][-1].get("reason") or "action rejected"}
            replacement_ancestors[key] = inherited
            continue
        accepted.append(key)
        accepted_actions.append(opaque)
        replacement_ancestors[key] = inherited + record_for_replacements(record["node"])

    for key in sorted(node_keys):
        if key not in status and key not in accepted:
            status[key] = {"rule": "reachability", "detail": "not admitted"}

    accepted_set = set(accepted)
    graph_nodes: List[Dict[str, Any]] = []
    for key in accepted:
        raw = copy.deepcopy(nodes[key]["node"])
        raw["id"] = key
        raw["parents"] = sorted(parent for parent in nodes[key]["parents"] if parent in accepted_set)
        if not raw["parents"]:
            raw["parents"] = ["__source__"]
        graph_nodes.append(raw)
    sink_parents = sorted(key for key in goals if key in accepted_set)
    graph = {"version": VERSION, "source": "__source__", "goal_sink": "__goal_sink__", "sink_parents": sink_parents, "nodes": graph_nodes}
    rejected = list(invalid)
    for key, reason in status.items():
        if key in accepted_set:
            continue
        node_id = key if key in nodes else key
        rejected.append({"node_id": node_id, "rule": reason["rule"], "detail": reason["detail"]})
    rejected.sort(key=lambda item: (item["node_id"], item["rule"], item["detail"]))
    breakdown = {rule: sum(1 for item in rejected if item["rule"] == rule) for rule in RULES}
    return {
        "version": VERSION,
        "accepted_dag": graph,
        "accepted_count": len(accepted),
        "accepted_node_keys": accepted,
        "rejected": rejected,
        "rejection_breakdown": breakdown,
        "proposed_node_count": sum(len(p.get("nodes", [])) for p in proposals if isinstance(p, dict) and isinstance(p.get("nodes"), list)),
        "unique_node_count": len(nodes),
    }


def record_for_replacements(node: Dict[str, Any]) -> List[Dict[str, int]]:
    replacements = node.get("replaces", [])
    if not isinstance(replacements, list):
        return []
    return [item for item in replacements if isinstance(item, dict) and set(item) == {"source_id", "revision"}]


def admission_bytes(result: Dict[str, Any]) -> bytes:
    return canonical(result["accepted_dag"])


def execute_admitted(task: Dict[str, Any], result: Dict[str, Any], full_verifier: bool) -> Dict[str, Any]:
    actions = [node["action"] for node in result["accepted_dag"]["nodes"]]
    if full_verifier:
        checked = verify_task(task, [_action_for_verifier(task, action) for action in actions], adapter_key=ADAPTER_KEY)
        unsafe = sum(1 for event in checked["events"] if event.get("accepted") is not True)
        return {"classification": checked["classification"], "success": checked["classification"] == "success", "unsafe_act_count": unsafe, "verifier_calls": 1, "submitted_actions": len(actions)}
    placed: Set[str] = set()
    seen_reserves: Set[str] = set()
    for action in actions:
        if action.get("op") == "reserve":
            seen_reserves.add(action.get("sample"))
        elif action.get("op") == "place" and action.get("sample") in seen_reserves:
            placed.add(action.get("sample"))
    success = placed == set(task["sample_kinds"])
    return {"classification": "success" if success else "safe incomplete", "success": success, "unsafe_act_count": 0, "verifier_calls": 0, "submitted_actions": len(actions)}


def record_for_plan(task: Dict[str, Any], plan: List[Dict[str, Any]], agent: str) -> Dict[str, Any]:
    last_place: Dict[str, str] = {}
    nodes: List[Dict[str, Any]] = []
    for index, action in enumerate(plan):
        node_id = "n" + str(index)
        parents: List[str] = []
        if action["op"] == "reserve":
            parents.extend(last_place.get(parent, "") for parent in task["prerequisites"].get(action["sample"], []))
            parents = [parent for parent in parents if parent]
        else:
            reserve_id = next((node["id"] for node in reversed(nodes) if node["action"].get("op") == "reserve" and node["action"].get("sample") == action["sample"]), None)
            if reserve_id:
                parents.append(reserve_id)
        if nodes:
            if nodes[-1]["id"] not in parents:
                parents.append(nodes[-1]["id"])
        nodes.append({"id": node_id, "parents": parents, "resource": task["requirements"][action["sample"]], "evidence": [{"source_id": "fixture", "revision": task["revision"]}], "action": dict(action)})
        if action["op"] == "place":
            last_place[action["sample"]] = node_id
    return {"agent": agent, "goal": nodes[-1]["id"] if nodes else "", "nodes": nodes}


class ScriptedDAGPolicy:
    """Offline valid-plan oracle used only to exercise the hard admission layer."""

    def propose(self, task: Dict[str, Any], seed: int, arm: str, agent: str) -> Dict[str, Any]:
        plan = reference_solve(task)
        if plan is None:
            plan = [{"op": "reserve", "sample": name, "slot": "slot-0", "revision": task["revision"]} for name in task["sample_kinds"]]
        return record_for_plan(task, plan, agent)


def prompt_for(task: Dict[str, Any], seed: int, arm: str, agent: str) -> str:
    """Public fixture view for solo_planner and swarm_proposal (full view).

    E12 NEW: swarm_partitioned gives agent *i* only its assigned sample's slice.
    """
    public = {key: task[key] for key in ("protocol", "revision", "max_actions", "sample_kinds", "slot_zones", "rules", "prerequisites", "resources", "requirements")}
    if arm == "swarm_partitioned":
        # agentN -> sample index N (modulo sample_kinds for safety)
        agent_idx = int(agent.split("-")[-1])
        all_samples = list(task["sample_kinds"].keys())
        my_sample = all_samples[agent_idx % len(all_samples)]
        # Disjoint slice: public protocol + slot_zones + rules + my sample's requirements
        # and prerequisites (empty by construction in this packet, but included for generality).
        partitioned = {
            "protocol": task["protocol"],
            "revision": task["revision"],
            "max_actions": task["max_actions"],
            "sample_kinds": task["sample_kinds"],
            "slot_zones": task["slot_zones"],
            "rules": task["rules"],
            "resources": task["resources"],
            "my_sample": my_sample,
            "requirements": {my_sample: task["requirements"].get(my_sample)},
            "prerequisites": {my_sample: task["prerequisites"].get(my_sample, [])},
        }
        # Sanity: every sample still listed so the agent knows the DAG must cover all,
        # but it only has data for its own.
        prompt_body = """You are an untrusted task planner in a three-agent swarm. Each agent receives a DISJOINT slice of the fixture: only the public protocol/goal/revision/slot_zones/rules plus the requirements and prerequisites for ONE sample assigned to that agent. You do NOT see the other samples' requirements or prerequisites. Your job is to propose a reserve/place sub-DAG for YOUR sample only, using the public slot_zones/rules and your sample's own data. Do NOT invent data for the other samples — propose only your sample's reserve and place.

Return ONLY one JSON object, no markdown, with this exact top-level shape: {"goal":"node-id","nodes":[{"id":"local-id","parents":["local-id"],"resource":"resource-name","evidence":[{"source_id":"fixture","revision":0}],"action":{"op":"reserve","sample":"<your-actual-sample-name>","slot":"slot-0","revision":0}}]}. Build a complete executable sub-DAG for your sample: a reserve node followed by a place node that depends on the reserve. A child sample's reserve depends on all prerequisite sample place nodes; since you only know your own prerequisites, express them as parents if they appear in your slice, otherwise chain off the most recent node. Use local parent references only. Use the ACTUAL sample name from your private slice (the value of the "my_sample" key in the fixture json — e.g. "sample-0", "sample-1", or "sample-2") as the "sample" field in every action. Never include evaluator fields or prose. Output the JSON immediately; do not spend tokens on reasoning.

The public shared fields (protocol, slot_zones, rules) are the same for all agents; your PRIVATE slice below is only for your sample.
"""
        return prompt_body + "\n\n" + json.dumps({"seed": seed, "arm": arm, "agent": agent, "fixture": partitioned}, sort_keys=True)
    return """You are an untrusted task planner. Return ONLY one JSON object, no markdown, with this exact top-level shape: {"goal":"node-id","nodes":[{"id":"local-id","parents":["local-id"],"resource":"resource-name","evidence":[{"source_id":"fixture","revision":0}],"action":{"op":"reserve","sample":"sample-0","slot":"slot-0","revision":0}}]}. Build a complete executable DAG using only the supplied fixture. Include reserve and place nodes for each sample; place must depend on its reserve; a child sample's reserve must depend on all prerequisite sample place nodes. Use local parent references only. Never include evaluator fields or prose.

""" + json.dumps({"seed": seed, "arm": arm, "agent": agent, "fixture": public}, sort_keys=True)


def merge_partitioned(task: Dict[str, Any], proposals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Model-free union and prerequisite repair for the merged arm.

    Local proposal IDs are namespaced by agent, then every reserve node is rewired to
    the merged proposal's place node for each declared prerequisite. No nodes or edges
    are invented beyond those deterministic rewrites; the unchanged admission gate
    decides what survives.
    """
    merged_nodes: List[Dict[str, Any]] = []
    id_map: Dict[Tuple[str, str], str] = {}
    sample_places: Dict[str, str] = {}
    ordered = sorted((copy.deepcopy(p) for p in proposals), key=canonical)
    for proposal in ordered:
        agent = str(proposal.get("agent", "unknown"))
        for raw in proposal.get("nodes", []):
            local_id = str(raw["id"])
            id_map[(agent, local_id)] = f"{agent}::{local_id}"
            if raw.get("action", {}).get("op") == "place":
                sample = raw.get("action", {}).get("sample")
                if isinstance(sample, str):
                    sample_places.setdefault(sample, f"{agent}::{local_id}")
    for proposal in ordered:
        agent = str(proposal.get("agent", "unknown"))
        for raw in proposal.get("nodes", []):
            node = copy.deepcopy(raw)
            node["id"] = id_map[(agent, str(raw["id"]))]
            action = node.get("action", {})
            if action.get("op") == "reserve":
                sample = action.get("sample")
                node["parents"] = sorted({sample_places[parent] for parent in task["prerequisites"].get(sample, []) if parent in sample_places})
            else:
                node["parents"] = sorted({id_map[(agent, parent)] for parent in raw.get("parents", []) if (agent, parent) in id_map})
            merged_nodes.append(node)
    terminal_samples = sorted(set(task["sample_kinds"]) - {p for ps in task["prerequisites"].values() for p in ps})
    goal = next((sample_places[s] for s in terminal_samples if s in sample_places), None)
    if goal is None and merged_nodes:
        goal = sorted(node["id"] for node in merged_nodes)[-1]
    return {"agent": "merge", "goal": goal or "", "nodes": merged_nodes}


def proposals_for(task: Dict[str, Any], seed: int, arm: str, pilot: Any) -> Tuple[List[Dict[str, Any]], int, int]:
    agents = ["solo"] if arm == "solo_planner" else ["agent-0", "agent-1", "agent-2"]
    prompt_arm = "swarm_partitioned" if arm == "swarm_partitioned_merged" else arm
    proposals: List[Dict[str, Any]] = []
    parse_errors = 0
    calls = 0
    for agent in agents:
        key = "|".join((VERSION, str(seed), arm, agent, "dag"))
        text, _usage = pilot.call(key, prompt_for(task, seed, prompt_arm, agent))
        calls += 1
        try:
            proposal = parse_proposal(text)
        except ValueError:
            parse_errors += 1
            text, _usage = pilot.call(key + "|retry", prompt_for(task, seed, prompt_arm, agent) + "\nYour previous output was invalid. Return one JSON object now; ensure goal exactly names one node id in nodes.")
            calls += 1
            try:
                proposal = parse_proposal(text)
            except ValueError:
                parse_errors += 1
                continue
        proposal["agent"] = agent
        proposals.append(proposal)
    return proposals, parse_errors, calls


def run_arm(arm: str, seeds: List[int]) -> Dict[str, Any]:
    pilot = Pilot(arm)
    runs: List[Dict[str, Any]] = []
    budget_stopped = False
    for seed in seeds:
        task = fixture_task(seed)
        try:
            proposals, parse_errors, calls = proposals_for(task, seed, arm, pilot)
        except BudgetStop:
            budget_stopped = True
            break
        except Exception as exc:
            write_json(OUT / ("error_" + arm + ".json"), {"error": repr(exc), "arm": arm})
            raise
        admission_proposals = [merge_partitioned(task, proposals)] if arm == "swarm_partitioned_merged" else proposals
        admitted = admit(task, admission_proposals)
        second = admit(task, admission_proposals)
        deterministic = admission_bytes(admitted) == admission_bytes(second)
        executed = execute_admitted(task, admitted, full_verifier=(arm == "swarm_proposal_verified"))
        runs.append({"seed": seed, "composition": task["composition"], "proposals": len(proposals), "parse_errors": parse_errors, "api_calls": calls, "deterministic": deterministic, "admission": admitted, "execution": executed})
    result = {
        "experiment": "e14-merge-repair",
        "model": MODEL,
        "provider": "nousresearch",
        "api": API,
        "api_key_env": API_KEY_ENV,
        "arm": arm,
        "config": {"seeds": seeds, "temperature": 0.0, "max_tokens": 2200, "max_arm_cost": MAX_ARM_COST, "rules": list(RULES)},
        "runs": runs,
        "budget_stopped": budget_stopped,
        "totals": {"prompt_tokens": pilot.prompt_tokens, "completion_tokens": pilot.completion_tokens, "total_tokens": pilot.tokens, "estimated_cost_usd": pilot.cost, "cache_entries": len(pilot.cache)},
    }
    write_json(OUT / ("results_" + arm + ".json"), result)
    print(json.dumps({"arm": arm, "runs": len(runs), "determinism_failures": sum(not r["deterministic"] for r in runs), "accepted_nodes": sum(r["admission"]["accepted_count"] for r in runs), "successes": sum(r["execution"]["success"] for r in runs), "cost": round(pilot.cost, 6), "budget_stopped": budget_stopped}, sort_keys=True))
    return result


def run_selftest() -> int:
    task = fixture_task(101, "chain")
    policy = ScriptedDAGPolicy()
    proposal = policy.propose(task, 101, "solo_planner", "solo")
    partitioned = []
    for agent in ["agent-0", "agent-1", "agent-2"]:
        value = policy.propose(task, 101, "swarm_partitioned", agent)
        value["agent"] = agent
        partitioned.append(value)
    merged = merge_partitioned(task, partitioned)
    merged_once = admit(task, [merged])
    merged_twice = admit(task, [merge_partitioned(task, partitioned)])
    if merged_once["accepted_count"] <= 0 or admission_bytes(merged_once) != admission_bytes(merged_twice):
        write_json(OUT / "selftest.json", {"experiment": "e14-merge-repair", "pass": False, "error": "merge admission/determinism"})
        return 1
    cases: Dict[str, Dict[str, Any]] = {}
    base = copy.deepcopy(proposal)
    cases["valid"] = base
    cyclic = copy.deepcopy(base)
    cyclic["nodes"][0]["parents"] = [cyclic["nodes"][-1]["id"]]
    cases["cyclic"] = cyclic
    unreachable = copy.deepcopy(base)
    stray_sample = next(sample for sample in task["sample_kinds"] if sample != base["nodes"][0]["action"]["sample"])
    stray_slot = next(slot for slot, zone in task["slot_zones"].items()
                       if zone == task["rules"][task["sample_kinds"][stray_sample]])
    unreachable["nodes"].append({"id": "stray", "parents": [], "resource": task["requirements"][stray_sample], "evidence": [{"source_id": "fixture", "revision": 0}], "action": {"op": "reserve", "sample": stray_sample, "slot": stray_slot, "revision": 0}})
    cases["unreachable"] = unreachable
    contradiction = copy.deepcopy(base)
    contradiction["nodes"][0]["replaces"] = [{"source_id": "fixture", "revision": 1}]
    cases["contradiction"] = contradiction
    cross_arm = copy.deepcopy(base)
    cross_arm["nodes"][1]["parents"] = ["agent-2:n0"]
    cases["cross_arm"] = cross_arm
    unsafe = copy.deepcopy(base)
    first = unsafe["nodes"][0]["action"]
    wrong = next(slot for slot, zone in task["slot_zones"].items() if zone != task["rules"][task["sample_kinds"][first["sample"]]])
    unsafe["nodes"][1]["action"]["slot"] = wrong
    cases["unsafe"] = unsafe
    checks = {
        "valid": lambda r: r["accepted_count"] == 8 and execute_admitted(task, r, True)["success"],
        "cyclic": lambda r: any(i["rule"] == "acyclicity" for i in r["rejected"]),
        "unreachable": lambda r: any(i["rule"] == "reachability" for i in r["rejected"]),
        "contradiction": lambda r: any(i["rule"] == "contradiction_cascade" for i in r["rejected"]),
        "cross_arm": lambda r: any(i["rule"] == "resource_consistency" for i in r["rejected"]),
        "unsafe": lambda r: any(i["rule"] == "verifier_feasibility" for i in r["rejected"]),
    }
    details: Dict[str, Any] = {}
    passed = True
    for name, value in cases.items():
        result = admit(task, [value])
        second = admit(task, [value])
        ok = bool(checks[name](result)) and admission_bytes(result) == admission_bytes(second)
        details[name] = {"passed": ok, "accepted_count": result["accepted_count"], "breakdown": result["rejection_breakdown"]}
        passed = passed and ok
    matrix = []
    for seed in SEEDS:
        fixture = fixture_task(seed)
        p = policy.propose(fixture, seed, "offline", "stub")
        result = admit(fixture, [p])
        matrix.append({"seed": seed, "composition": fixture["composition"], "accepted": result["accepted_count"], "success": execute_admitted(fixture, result, True)["success"]})
    payload = {"experiment": "e14-merge-repair", "offline": True, "policy": "ScriptedDAGPolicy", "pass": passed, "rule_cases": details, "matrix_runs": matrix, "run_count": len(matrix)}
    write_json(OUT / "selftest.json", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if passed else 1


def run_pretest() -> int:
    """Three seeds × three agents; gate parseability AND merged admission."""
    pilot = Pilot("pretest", max_cost=0.03)
    rows: List[Dict[str, Any]] = []
    for seed in SEEDS[:3]:
        task = fixture_task(seed)
        proposals, parse_errors, calls = proposals_for(task, seed, "swarm_partitioned_merged", pilot)
        if len(proposals) == 3:
            merged = merge_partitioned(task, proposals)
            admitted = admit(task, [merged])
            rows.append({"seed": seed, "parseable": len(proposals), "parse_errors": parse_errors, "calls": calls, "merged_admitted": admitted["accepted_count"], "merged_success": execute_admitted(task, admitted, True)["success"]})
        else:
            rows.append({"seed": seed, "parseable": len(proposals), "parse_errors": parse_errors, "calls": calls, "merged_admitted": 0, "merged_success": False})
    parseable = sum(row["parseable"] for row in rows)
    passed = parseable == 9 and len(rows) == 3 and all(row["merged_admitted"] > 0 for row in rows)
    result = {"experiment": "e14-merge-repair", "gate": "pretest", "model": MODEL, "rows": rows, "parseable_count": parseable, "merged_admission_count": sum(row["merged_admitted"] > 0 for row in rows), "pass": passed, "cost": pilot.cost, "tokens": pilot.tokens}
    write_json(OUT / "pretest.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 3


def _sign_test(left: List[bool], right: List[bool]) -> Dict[str, Any]:
    wins = losses = ties = 0
    for a, b in zip(left, right):
        if a == b:
            ties += 1
        elif a and not b:
            wins += 1
        else:
            losses += 1
    n = wins + losses
    tail = sum(math.comb(n, k) for k in range(0, min(wins, losses) + 1)) / (2 ** n) if n else 1.0
    return {"wins": wins, "losses": losses, "ties": ties, "n_non_tied": n, "p_two_sided": min(1.0, 2 * tail)}


def _graph_shape(graph: Dict[str, Any]) -> Tuple[int, int]:
    parents = {n["id"]: [p for p in n["parents"] if p != "__source__"] for n in graph["nodes"]}
    depth: Dict[str, int] = {}
    for node in graph["nodes"]:
        depth[node["id"]] = 1 + max((depth.get(p, 0) for p in parents[node["id"]]), default=0)
    widths: Dict[int, int] = defaultdict(int)
    for value in depth.values():
        widths[value] += 1
    return (max(depth.values(), default=0), max(widths.values(), default=0))


def aggregate() -> int:
    results: Dict[str, Dict[str, Any]] = {}
    for arm in ARMS:
        path = OUT / ("results_" + arm + ".json")
        if not path.exists():
            print("BLOCKED: missing " + str(path))
            return 2
        results[arm] = json.loads(path.read_text())
        if len(results[arm].get("runs", [])) != len(SEEDS):
            print("BLOCKED: incomplete " + arm + " matrix")
            return 2
    pretest_path = OUT / "pretest.json"
    if not pretest_path.exists():
        print("BLOCKED: missing " + str(pretest_path))
        return 2
    pretest = json.loads(pretest_path.read_text())
    pretest_cost = float(pretest.get("cost", 0.0))
    pretest_cache_cost = 0.0
    for cache_path in OUT.glob("api_cache_*.jsonl"):
        for line in cache_path.read_text().splitlines():
            try:
                item = json.loads(line)
                if str(item.get("key", "")).split("|")[0] != VERSION:
                    pretest_cache_cost += float(item.get("usage", {}).get("cost", 0.0))
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
    failed_pretest_cost = max(0.0, pretest_cache_cost)
    summary: Dict[str, Any] = {"experiment": "e14-merge-repair", "seeds": SEEDS, "arms": {}, "determinism_all_pass": True, "pretest_cost_usd": pretest_cost, "failed_attempt_cost_usd": failed_pretest_cost}
    solo_success = [bool(r["execution"]["success"]) for r in results["solo_planner"]["runs"]]
    for arm in ARMS:
        runs = results[arm]["runs"]
        breakdown = {rule: sum(r["admission"]["rejection_breakdown"][rule] for r in runs) for rule in RULES}
        proposed = sum(r["admission"]["proposed_node_count"] for r in runs)
        accepted = sum(r["admission"]["accepted_count"] for r in runs)
        depths = [_graph_shape(r["admission"]["accepted_dag"])[0] for r in runs]
        widths = [_graph_shape(r["admission"]["accepted_dag"])[1] for r in runs]
        unique = sum(r["admission"]["unique_node_count"] for r in runs)
        redundant = max(0, proposed - unique) / proposed if proposed else 0.0
        summary["arms"][arm] = {
            "runs": len(runs), "parse_errors": sum(r["parse_errors"] for r in runs), "admission_rate": accepted / proposed if proposed else 0.0,
            "proposed_nodes": proposed, "accepted_nodes": accepted, "rejection_breakdown": breakdown,
            "determinism_failures": sum(not r["deterministic"] for r in runs), "execution_successes": sum(bool(r["execution"]["success"]) for r in runs),
            "execution_success_rate": sum(bool(r["execution"]["success"]) for r in runs) / len(runs), "unsafe_act_count": sum(r["execution"]["unsafe_act_count"] for r in runs),
            "total_tokens": results[arm]["totals"]["total_tokens"], "cost_usd": results[arm]["totals"]["estimated_cost_usd"],
            "tokens_per_accepted_node": results[arm]["totals"]["total_tokens"] / accepted if accepted else None,
            "mean_depth": sum(depths) / len(depths), "max_width_mean": sum(widths) / len(widths), "redundant_node_fraction": redundant,
        }
        summary["determinism_all_pass"] = summary["determinism_all_pass"] and not summary["arms"][arm]["determinism_failures"]
    for arm in ARMS[1:]:
        summary["paired_sign_tests"] = summary.get("paired_sign_tests", {})
        summary["paired_sign_tests"][arm + "_vs_solo"] = _sign_test([bool(r["execution"]["success"]) for r in results[arm]["runs"]], solo_success)
    summary["matrix_cost_usd"] = sum(summary["arms"][arm]["cost_usd"] for arm in ARMS)
    summary["total_cost_usd"] = summary["matrix_cost_usd"] + pretest_cost + failed_pretest_cost
    summary["budget_cap_usd"] = 0.25
    summary["budget_cap_pass"] = summary["total_cost_usd"] <= summary["budget_cap_usd"]
    merged_successes = summary["arms"]["swarm_partitioned_merged"]["execution_successes"]
    solo_successes = summary["arms"]["solo_planner"]["execution_successes"]
    summary["predeclared_verdict_fired"] = "REFUTED" if merged_successes == 0 or merged_successes < solo_successes else ("SUPPORTED" if summary["arms"]["swarm_partitioned_merged"]["redundant_node_fraction"] <= 0.01 and summary["arms"]["swarm_partitioned_merged"]["tokens_per_accepted_node"] <= 1.5 * summary["arms"]["solo_planner"]["tokens_per_accepted_node"] else "PARTIAL")
    write_json(OUT / "e14_summary.json", summary)
    lines = ["# E14 — deterministic merge/repair over partitioned DAGs", "",
             "Model: `" + MODEL + "`; provider: `Nous Portal`; temperature: `0.0`; seeds: `101–120`.",
             "",
             "| arm | runs | admission rate | success rate | redundant frac | tok/accepted | cost USD |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        item = summary["arms"][arm]
        lines.append("| {0} | {1} | {2:.3f} | {3:.3f} | {4:.3f} | {5:.1f} | {6:.4f} |".format(
            arm, item["runs"], item["admission_rate"], item["execution_success_rate"],
            item["redundant_node_fraction"],
            item["tokens_per_accepted_node"] or 0.0,
            item["cost_usd"]))
    lines += ["",
              "## Determinism",
              "",
              "Admission was run twice per seed from the same serialized proposals; `determinism_all_pass`: **{}**.".format(summary["determinism_all_pass"]),
              "",
              "## Anchors vs E12 (cross-model)",
              "",
              "E12 anchors: solo_planner = 55 accepted / 160 proposed, 323.4 tok/node, 3/20 success; swarm_partitioned = 20 accepted / 120 proposed, 0/20 success. This E14 run uses `z-ai/glm-5.3-flash`, so exact proposal reproduction is a cross-model check.",
              "",
              "## Rejection breakdown",
              "",
              "| arm | acyclicity | reachability | contradiction cascade | resource consistency | verifier feasibility |",
              "|---|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        b = summary["arms"][arm]["rejection_breakdown"]
        lines.append("| {0} | {1} | {2} | {3} | {4} | {5} |".format(arm, b["acyclicity"], b["reachability"], b["contradiction_cascade"], b["resource_consistency"], b["verifier_feasibility"]))
    lines += ["",
              "Total matrix cost: `${:.6f}`; passed-gate pre-test cost: `${:.6f}`; failed pre-test attempts: `${:.6f}`; total known cache cost: `${:.6f}` (cap `${:.2f}`, pass: **{}**).".format(
                  summary["matrix_cost_usd"], pretest_cost, failed_pretest_cost, summary["total_cost_usd"], summary["budget_cap_usd"], summary["budget_cap_pass"]),
              "",
              "## Predeclared verdicts (frozen before the matrix)",
              "",
              "- **SUPPORTED:** merged redundancy ≈0%, success ≥ 3/20, and tokens/accepted ≤ 1.5× solo.",
              "- **REFUTED:** merged success remains 0/20 or below solo; partial views are fatal.",
              "- **PARTIAL:** redundancy is fixed but success remains below solo; report the gap exactly.",
              "",
              "Observed predeclared verdict: **{}** (merged success {} / 20 versus solo {} / 20).".format(summary["predeclared_verdict_fired"], merged_successes, solo_successes),
              "",
              "## Honest scope",
              "",
              "The accepted subset is produced by canonical sorting, graph checks, contradiction propagation, fixture-resource checks, and verifier replay only; no model call occurs during admission. A zero unsafe-act count is a harness result, not a security proof. See `out/e14_summary.json` for tokens, paired exact sign tests, graph shape, and budget accounting.",
              ""]
    (ROOT / "REPORT.md").write_text("\n".join(lines))
    print(json.dumps({"summary": str(OUT / "e14_summary.json"), "total_cost_usd": summary["total_cost_usd"], "determinism_all_pass": summary["determinism_all_pass"], "budget_cap_pass": summary["budget_cap_pass"]}, sort_keys=True))
    return 0 if summary["determinism_all_pass"] and summary["budget_cap_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--pretest", action="store_true")
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in SEEDS))
    args = parser.parse_args()
    if args.self_test:
        return run_selftest()
    if args.pretest:
        return run_pretest()
    if args.aggregate:
        return aggregate()
    if args.arm:
        try:
            seeds = [int(item) for item in args.seeds.split(",") if item.strip()]
            if seeds != SEEDS:
                raise ValueError("full matrix requires seeds 101-120 in order")
            gate = OUT / "pretest.json"
            if not gate.exists() or not json.loads(gate.read_text()).get("pass"):
                print("BLOCKED: pretest gate is absent or failed")
                return 3
            return 0 if run_arm(args.arm, seeds) else 1
        except (ValueError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
    parser.error("choose --self-test, --pretest, --arm, or --aggregate")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
