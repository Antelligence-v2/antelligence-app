"""Research QA world: evidence-grounded questions answered by a swarm.

One run is one task under one protocol. Each tick is a protocol round.
Agents observe the public task (evidence limited to what they may see this
round), their own previous answer, and — on a :class:`BoardField` topic equal
to the task id — other agents' previous-round claims. They act by
``answer``-ing ({answer, evidence_ids, brief}) or ``abstain``-ing.

Answer parsing, scoring and the strict-majority rule are ``backend.swarm_core``'s
own (imported, not re-implemented), so correctness semantics are identical to
the Research Workbench. Evaluator labels (``expected_answer``) never enter an
observation.

Evidence sharding for ``evidence_exchange`` is world-mediated, as in
swarm_core: after round 0 each agent additionally sees the passages its peers
*cited* (the host transports citations; it never chooses evidence).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from backend.swarm_core import (
    _PayloadError,
    _parse_answer,
    _answer_key,
    _score_answer,
    _strict_majority,
    _validate_task,
    public_task,
)

from antelligence.kernel.aggregate import FAILED, UNVERIFIED, VERIFIED, canonical_answer
from antelligence.kernel.field import SenseQuery
from antelligence.kernel.memory import CLAIM, EvidenceMemory
from antelligence.kernel.types import Intent, Observation, Outcome
from antelligence.worlds.research_qa.verify import ClaimVerdict, verify_claim

ANSWER = "answer"
ABSTAIN = "abstain"
MALFORMED = "malformed"
MAX_CITED = 3


@dataclass(frozen=True)
class Protocol:
    name: str
    agents: int
    rounds: int
    sharded: bool = False
    board: bool = False
    share_citations: bool = False
    aggregate: str = "majority"  # "majority" over final answers, or "last" (single agent)

    def describe(self) -> Dict[str, Any]:
        return dict(self.__dict__)


PROTOCOLS = {
    "single": Protocol("single", agents=1, rounds=1, aggregate="last"),
    "independent_vote": Protocol("independent_vote", agents=3, rounds=1),
    "signal_board": Protocol("signal_board", agents=3, rounds=3, board=True),
    "evidence_exchange": Protocol("evidence_exchange", agents=3, rounds=2, sharded=True, board=True,
                                  share_citations=True),
    "evidence_isolated": Protocol("evidence_isolated", agents=3, rounds=2, sharded=True),
    "solo_refine": Protocol("solo_refine", agents=1, rounds=6, aggregate="last"),
}

INSTRUCTIONS = {
    "solve": "Solve independently.",
    "board": "Use this bounded snapshot of other-agent signals; then answer independently.",
    "shard": ("You have only a local evidence shard. Cite up to three evidence IDs; your cited passages "
              "will be delivered to peers. Answer only what the evidence supports; abstain when insufficient."),
    "exchange": ("Reconsider your initial answer using your local evidence and any received findings. "
                 "Challenge unsupported peer conclusions; source passages matter more than agreement."),
    "refine": "Review the full evidence independently. Check your previous answer for mistakes; revise or abstain.",
}


class ResearchQAWorld:
    def __init__(self, task: Mapping[str, Any], protocol: str, *, agent_prefix: str = "worker",
                 lenient: bool = False, verify: bool = False, min_confirmations: int = 1,
                 plurality: bool = False) -> None:
        _validate_task(task)
        if protocol not in PROTOCOLS:
            raise ValueError(f"unknown protocol {protocol!r}")
        self.task = copy.deepcopy(dict(task))
        self.protocol = PROTOCOLS[protocol]
        self.task_id = self.task["task_id"]
        n = self.protocol.agents
        self.agent_ids = [f"{agent_prefix}-{i + 1}" for i in range(n)]
        all_ids = [e["id"] for e in self.task["evidence"]]
        self.shards: Dict[str, List[str]] = {
            a: (all_ids[i::n] if self.protocol.sharded else list(all_ids)) for i, a in enumerate(self.agent_ids)
        }
        self.received: Dict[str, List[str]] = {a: [] for a in self.agent_ids}
        self.answers: Dict[str, Dict[int, Optional[dict]]] = {a: {} for a in self.agent_ids}
        self.invalid: Dict[str, int] = {a: 0 for a in self.agent_ids}
        self.missing: Dict[str, int] = {a: 0 for a in self.agent_ids}
        self._round = 0
        self.lenient, self.verify, self.plurality = lenient, verify, plurality
        self.min_confirmations = min_confirmations
        # lenient: rounds whose reply was unusable; counted apart from accuracy, a missing vote not a dead cell.
        self.format_failed: Dict[str, set] = {a: set() for a in self.agent_ids}
        self.verdicts: Dict[str, Dict[int, ClaimVerdict]] = {a: {} for a in self.agent_ids}
        self.claim_memory: Optional[EvidenceMemory] = None
        self._claim_ids: Dict[str, Optional[str]] = {}
        if verify:
            self.claim_memory = EvidenceMemory(min_confirmations=min_confirmations)

    # ------------------------------------------------------------- contract
    @property
    def revision(self) -> int:
        return self._round

    def agents(self) -> List[str]:
        return list(self.agent_ids)

    def describe(self) -> Dict[str, Any]:
        out = {"world": "research_qa", "version": 1, "task_id": self.task_id, "protocol": self.protocol.describe()}
        if self.lenient:
            out["lenient"] = True
        if self.verify:
            out.update(verify=True, min_confirmations=self.min_confirmations)
        if self.plurality:
            out["plurality"] = True
        return out

    def visible_ids(self, agent_id: str) -> List[str]:
        own = self.shards[agent_id]
        return own + [e for e in self.received[agent_id] if e not in own]

    def observe(self, agent_id: str, tick: int) -> Observation:
        round_number = tick - 1
        visible = set(self.visible_ids(agent_id))
        view_task = dict(self.task, evidence=[e for e in self.task["evidence"] if e["id"] in visible])
        previous = self.answers[agent_id].get(round_number - 1)
        p = self.protocol
        if p.name == "solo_refine" and round_number > 0:
            instruction = INSTRUCTIONS["refine"]
        elif p.sharded:
            instruction = INSTRUCTIONS["shard"] if round_number == 0 else INSTRUCTIONS["exchange"]
        elif p.board and round_number > 0:
            instruction = INSTRUCTIONS["board"]
        else:
            instruction = INSTRUCTIONS["solve"]
        data = {"task": public_task(view_task), "round": round_number, "own_previous": previous,
                "instruction": instruction, "post_to_board": p.board}
        sense = SenseQuery(topic=self.task_id, max_results=p.agents) if p.board and round_number > 0 \
            else SenseQuery(topic=self.task_id, kinds=frozenset())
        return Observation(data, sense)

    def apply(self, agent_id: str, intent: Intent, tick: int) -> Outcome:
        round_number = tick - 1
        if intent.action == "noop":
            # A policy that failed (e.g. provider error) is failed closed to noop by
            # the scheduler: that is a missing answer (error cell), not an invalid one.
            return Outcome(False, "no_answer")
        if intent.action not in (ANSWER, ABSTAIN):
            # Includes "malformed": the policy got a reply it could not parse.
            if self.lenient:
                self.format_failed[agent_id].add(round_number)
                return Outcome(False, "malformed_reply" if intent.action == MALFORMED else "unknown_action")
            self.invalid[agent_id] += 1
            return Outcome(False, "malformed_reply" if intent.action == MALFORMED else "unknown_action")
        visible = set(self.visible_ids(agent_id))
        view_task = dict(self.task, evidence=[e for e in self.task["evidence"] if e["id"] in visible])
        payload = {k: intent.params.get(k) for k in ("answer", "evidence_ids", "brief")}
        if intent.action == ABSTAIN:
            # An abstention still carries its public brief and citations (as in swarm_core).
            payload = {"answer": None, "evidence_ids": payload["evidence_ids"] or [], "brief": payload["brief"] or ""}
        try:
            parsed = _parse_answer(json.dumps(payload), view_task)
        except (_PayloadError, ValueError) as exc:
            return self._reject(agent_id, round_number, f"invalid_payload: {exc}"[:120])
        if len(parsed["evidence_ids"]) > MAX_CITED:
            if not self.lenient:
                return self._reject(agent_id, round_number, "invalid_payload: too many evidence ids")
            parsed["evidence_ids"] = parsed["evidence_ids"][:MAX_CITED]
        self.answers[agent_id][round_number] = parsed
        effects: Dict[str, Any] = {"answer": parsed["answer"], "evidence_ids": parsed["evidence_ids"]}
        if self.verify:
            verdict = verify_claim({**parsed, **{k: intent.params[k] for k in ("quotes", "calculation")
                                                 if k in intent.params}}, view_task)
            if verdict is not None:
                self.verdicts[agent_id][round_number] = verdict
                effects["verification"] = verdict.to_dict()
            self._record_claim(agent_id, parsed["answer"], verdict, view_task, tick)
        return Outcome(True, effects=effects)

    def _reject(self, agent_id: str, round_number: int, reason: str) -> Outcome:
        if self.lenient:
            self.format_failed[agent_id].add(round_number)
        else:
            self.invalid[agent_id] += 1
        return Outcome(False, reason)

    def _record_claim(self, agent_id: str, answer: Optional[str], verdict: Optional[ClaimVerdict],
                      view_task: Mapping[str, Any], tick: int) -> None:
        """Propose a verified answer to the claim memory; a changed mind retracts the agent's earlier claim."""
        assert self.claim_memory is not None
        record_id = None
        if verdict is not None and verdict.status == VERIFIED:
            body = canonical_answer(answer) if view_task["answer_type"] == "decimal" else answer
            record_id = self.claim_memory.propose(scope=self.task_id, kind=CLAIM, author=agent_id,
                                                  subject=self.task_id, body={"answer": body}, tick=tick).id
        previous = self._claim_ids.get(agent_id)
        if previous is not None and previous != record_id:
            self.claim_memory.invalidate(previous, tick, "superseded")
        self._claim_ids[agent_id] = record_id

    def step_environment(self, tick: int) -> None:
        round_number = tick - 1
        for agent in self.agent_ids:
            if round_number not in self.answers[agent] and round_number not in self.format_failed[agent]:
                self.missing[agent] += 1
        if self.protocol.share_citations and round_number == 0:
            for agent in self.agent_ids:
                for peer in self.agent_ids:
                    if peer == agent:
                        continue
                    cited = (self.answers[peer].get(0) or {}).get("evidence_ids", [])
                    for evidence_id in cited:
                        if evidence_id in self.shards[peer] and evidence_id not in self.received[agent]:
                            self.received[agent].append(evidence_id)
        self._round = tick

    def done(self, tick: int) -> bool:
        return tick >= self.protocol.rounds

    # ------------------------------------------------------------- scoring
    def final_answers(self) -> List[Optional[str]]:
        last = self.protocol.rounds - 1
        return [(self.answers[a].get(last) or {}).get("answer") for a in self.agent_ids]

    def metrics(self) -> Dict[str, Any]:
        finals = self.final_answers()
        last = self.protocol.rounds - 1
        complete = all(last in self.answers[a] or last in self.format_failed[a] for a in self.agent_ids)
        if self.protocol.aggregate == "last":
            answer = finals[0]
        else:
            answer = _strict_majority(self.task, finals, self.protocol.agents)
        if any(self.invalid.values()) or (self.lenient and all(last in self.format_failed[a] for a in self.agent_ids)):
            status, answer = "invalid", None
        elif not complete or any(self.missing.values()):
            # Any required call that never produced an answer (e.g. a provider failure
            # in an earlier round) makes the cell an error, as in swarm_core.
            status, answer = "error", None
        elif answer is None:
            status = "abstained"
        else:
            status = "completed"
        out = {
            "task_id": self.task_id,
            "domain": self.task["domain"],
            "protocol": self.protocol.name,
            "status": status,
            "answer": answer,
            "correct": _score_answer(self.task, answer) if status == "completed" else None,
            "final_answers": finals,
            "invalid": sum(self.invalid.values()),
            "rounds_completed": self._round,
        }
        if self.lenient:
            out["format_failures"] = sum(len(r) for r in self.format_failed.values())
        if self.verify:
            out.update(self._verification_metrics(last, finals))
        if self.plurality:
            counts: Dict[Any, List[str]] = {}
            for a in finals:
                if a is not None:
                    counts.setdefault(_answer_key(self.task, a), []).append(a)
            ranked = sorted(counts.values(), key=len, reverse=True)
            top = None if not ranked or (len(ranked) > 1 and len(ranked[1]) == len(ranked[0])) else ranked[0][0]
            out["plurality_answer"] = top
            out["plurality_correct"] = _score_answer(self.task, top) if top is not None else None
        return out

    def _verification_metrics(self, last: int, finals: List[Optional[str]]) -> Dict[str, Any]:
        """Final-round ballots with their verdicts, for a downstream aggregator (counts cover cast answers)."""
        assert self.claim_memory is not None
        votes = [{"seat": a, "answer": ans,
                  "verification": self.verdicts[a][last].status if last in self.verdicts[a] else UNVERIFIED}
                 for a, ans in zip(self.agent_ids, finals)]
        counts = {s: sum(1 for v in votes if v["answer"] is not None and v["verification"] == s)
                  for s in (VERIFIED, UNVERIFIED, FAILED)}
        admitted = sorted(r.body["answer"] for r in self.claim_memory.recall(self.task_id, kinds=[CLAIM]))
        return {"votes": votes, "verification_counts": counts, "admitted_answers": admitted}
