"""v4 pilot Phase 0 calibration: harvest labelled questions from development seeds, ask each backend.

A noul item is scored on P(yes) against the simulator's bool. A choice item may have several equally good
options (``accept``): it is correct iff the answer is in ``accept``, and the probability scored for Brier/ECE
is the model's total probability over ``accept``. Rows keep the full ``probabilities`` vector and the
``accept`` set, so they can be rescored later without new calls.
"""

from __future__ import annotations

import asyncio
import dataclasses
import random
import time
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from antelligence.experiments.pilot_contract import CONDITIONS, PilotWorld
from antelligence.experiments.v4_pilot import DEV_SEEDS, WorldProxy, uses_eval_seeds
from antelligence.kernel.decision import DecisionRequest, Question
from antelligence.kernel.field import BoardField
from antelligence.kernel.scheduler import RunConfig, Scheduler
from antelligence.kernel.types import LocalView, Observation, World


MOVE_ASK = "Which action?"  # what DecisionWorker appends to the task text (before any queen goal)


def move_question(pilot_world: PilotWorld, question: Question) -> Question:
    """The labelled move question as the framework arms ask it: task text + "Which action?" (Phase 0 must
    measure the same question the arms face)."""
    return dataclasses.replace(question, instructions=f"{pilot_world.instructions} {MOVE_ASK}")


class _Harvester(WorldProxy):
    """Collects labelled questions (with the sensed state text) while a script plays; privileged, labels only."""

    def __init__(self, inner: World, pilot_world: PilotWorld, stride: int) -> None:
        super().__init__(inner)
        self.pilot_world, self.stride, self.items = pilot_world, stride, []
        self.sensor = pilot_world.sensor()

    def observe(self, agent_id: str, tick: int) -> Observation:
        obs = self.inner.observe(agent_id, tick)
        if tick % self.stride == 0:
            view = LocalView(agent_id, tick, self.inner.revision, 0, obs.data)
            state = self.sensor.sense(view).text
            for lq in self.pilot_world.labelled_questions(self.inner, view, tick):
                question = move_question(self.pilot_world, lq.question) if lq.kind == "move" else lq.question
                self.items.append({"id": f"{agent_id}-t{tick}-{lq.qid}", "kind": lq.kind, "qtype": lq.question.type,
                                   "state": state, "question": question, "label": lq.label,
                                   "accept": list(lq.accept), "tick": tick})
        return obs


def harvest_questions(worlds: Mapping[str, PilotWorld], *, total: int = 300, seeds: Sequence[int] = DEV_SEEDS,
                      rng_seed: int = 0) -> List[Dict[str, Any]]:
    """``total`` labelled questions from development seeds, split evenly across worlds and, inside each
    world, as evenly as the pool allows between judgement and move questions."""
    if uses_eval_seeds(seeds):
        raise ValueError("calibration uses development seeds only")
    rng, out = random.Random(rng_seed), []
    for name in sorted(worlds):
        pw, pool = worlds[name], []
        stride = max(1, int(pw.describe().get("max_ticks", 100)) // 14)  # ~14 sampled ticks per episode
        for seed in seeds:
            for condition in CONDITIONS:
                h = _Harvester(pw.make_world(seed, condition), pw, stride)
                Scheduler(h, {}, BoardField(), RunConfig(f"harvest-{name}-{seed}-{condition}", seed=seed, arm="S",
                                                         max_ticks=int(pw.describe().get("max_ticks", 100))),
                          default_policy=pw.script(condition, adapted=False), record_frames=False).run()
                pool += [{**i, "world": name, "seed": seed, "condition": condition,
                          "id": f"{name}-{seed}-{condition}-{i['id']}"} for i in h.items]
        quota = total // len(worlds) + (total % len(worlds) > sorted(worlds).index(name))
        rank: Dict[Tuple[str, str], int] = {}
        by_kind: Dict[str, List[Tuple[int, Dict[str, Any]]]] = {}
        for i in rng.sample(pool, len(pool)):  # judgements alternate yes/no so both labels stay represented
            key = (i["kind"], str(i["label"]) if i["kind"] == "judgement" else "")
            rank[key] = rank.get(key, -1) + 1
            by_kind.setdefault(i["kind"], []).append((-rank[key], i))
        by_kind = {k: [i for _, i in sorted(v, key=lambda r: r[0])] for k, v in sorted(by_kind.items())}
        picked: List[Dict[str, Any]] = []
        while len(picked) < min(quota, len(pool)):
            for kind in list(by_kind):
                if by_kind[kind] and len(picked) < quota:
                    picked.append(by_kind[kind].pop())
            by_kind = {k: v for k, v in by_kind.items() if v}
        out += picked
    return out


async def calibrate(backend: Any, name: str, items: Sequence[Mapping[str, Any]], *, concurrency: int = 4,
                    done: Sequence[str] = ()) -> List[Dict[str, Any]]:
    """Ask one named backend every item (one question per request); wall-clock latency includes the network."""
    sem = asyncio.Semaphore(concurrency)
    model = str(backend.describe().get("model", name))
    skip = set(done)

    async def ask(item: Mapping[str, Any]) -> Dict[str, Any]:
        row: Dict[str, Any] = {"id": item["id"], "backend": name, "world": item["world"], "kind": item["kind"],
                               "type": item["qtype"]}
        request = DecisionRequest.build(model, item["state"], {"q": item["question"]}, seed=item["seed"])
        async with sem:
            start = time.monotonic()
            try:
                response = await backend.decide(request)
            except Exception as exc:
                return {**row, "error": f"{type(exc).__name__}: {exc}"[:200], "latency_s": time.monotonic() - start}
            row["latency_s"] = time.monotonic() - start
        answer = response.answers["q"]
        if answer.type == "noul":
            row.update(prob=answer.p_yes, label=item["label"], correct=(answer.p_yes >= 0.5) == item["label"])
        else:
            accept = list(item.get("accept") or [item["label"]])
            right = answer.value in accept
            row.update(prob=sum(answer.probabilities.get(o, 0.0) for o in accept), label=right, correct=right,
                       accept=accept)
        return {**row, "answer": answer.value, "probabilities": dict(answer.probabilities),
                "served_model": response.served_model, "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens, "cost_usd": response.cost_usd}

    return list(await asyncio.gather(*(ask(i) for i in items if f"{name}:{i['id']}" not in skip)))
