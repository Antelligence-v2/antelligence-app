"""v4 pilot wiring: live and fake hooks, and the one ``build_policies`` that assembles every arm (goal 4.4-4.5, 6).

The arm recipes are those of ``kernel/policies/framework_arms.py``. The same ``build_policies`` serves live runs
and dry runs: only the *leaves* (the objects that would touch the network) differ, so a dry run exercises the real
HiveWorld, LLMQueen, DecisionWorker, StateChatPolicy, caches, ledger and reconciliation.

Stacking, outermost first (a cache hit makes no physical call, so it writes no ledger row)::

    chat      Cached(LedgeredChat(Counting(leaf)))                       per run and role
    decision  EscalatingBackend(CachedDecision(LedgeredDecision(Counting(primary), role="worker")),
                                CachedDecision(LedgeredDecision(Counting(slm), role="escalation")))

Caches are scoped to one run (``<cache_dir>/<backend>/<run_id>...``): every arm pays for its own calls, so cost and
seconds-per-decision are never flattered by another arm's replies, and rerunning a cell offline replays it exactly.
Keys arrive as callables or values from the CLI, are read only when an arm needs them, are held only inside the
HTTP backends, and are registered with the ledger so they are scrubbed from error rows. Nothing here logs them.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union

from antelligence.experiments.pilot_contract import PilotWorld
from antelligence.experiments.v4_pilot import ARMS, NOUS_MODEL, ArmSpec, CellSpec, Hooks, PolicySet, SetupError
from antelligence.kernel.decision import REPORT, Answer, DecisionBackend, DecisionRequest
from antelligence.kernel.hive import HiveWorld
from antelligence.kernel.policies.framework_arms import framework_policies
from antelligence.kernel.policies.llm_queen import LLMQueen
from antelligence.kernel.policies.state_policy import StateChatPolicy
from antelligence.kernel.types import World
from antelligence.providers.base import ChatRequest, ChatResponse, Provider
from antelligence.providers.decision_backends import (LAYA_MODEL, LAYA_URL, CachedDecision, EscalatingBackend,
                                                      FakeBackend, JevBackend, LayaBackend, LedgeredDecision,
                                                      SLMBackend)
from antelligence.providers.ledger import LedgeredChat, LedgerWriter, ledger_context, price_for
from antelligence.providers.openai_compat import OpenAICompatProvider
from antelligence.providers.wrappers import Cached, FakeProvider

NOUS_URL = "https://inference-api.nousresearch.com/v1"
JEV_MODEL = "jev-1.13.0"
SLM_MODEL = "Qwen/Qwen3.5-9B"  # the escalation model; the framework arms run while this pod is up
NOUS_EXTRA = {"reasoning": {"enabled": False}}
POD_EXTRA = {"chat_template_kwargs": {"enable_thinking": False}}
EVERY_AGENT_TOKENS = 64
QUEEN_TOKENS = 300
# Queen cadence per world (goal 4.4): foraging every 10 ticks; coloring once per round (one round = one tick).
QUEEN_EVERY = {"foraging_sb": 10, "graph_coloring": 1}
DEFAULT_QUEEN_EVERY = 10
MIN_REPORT_TTL = 10  # worker reports stay on the board at least this long, and always >= the queen cadence
POD_STATE_NAME = "v4-pod-state.json"
REPORT_SHARE = 0.08  # fake decision model: share of move answers that are "report"


class WiringError(SetupError):
    """A configuration problem found before any model call (wrong pod loaded, no pod, no key)."""


def queen_every(spec: CellSpec) -> int:
    """The queen's cadence for a cell: the budget-cut override, else the world's constant."""
    return spec.queen_every or QUEEN_EVERY.get(spec.world, DEFAULT_QUEEN_EVERY)


# --- leaves: the only objects that differ between live and fake -----------------------------------------------


@dataclass
class Leaves:
    """Factories for the raw, unwrapped model endpoints. ``pod(model)`` returns (provider, wire model name)."""

    nous: Callable[[], Provider]
    pod: Callable[[str], Tuple[Provider, str]]
    jev: Callable[[], DecisionBackend]
    laya: Callable[[], DecisionBackend]
    slm: Callable[[], DecisionBackend]
    deepseek: Callable[[], DecisionBackend]  # DeepSeek asked the typed questions (Phase 0 calibration only)


def _pod_matches(state: Optional[Mapping[str, Any]], model: str) -> Tuple[Mapping[str, Any], str]:
    """The loaded pod must serve ``model`` (one model per pod). FP8 builds serve ``<model>-FP8``."""
    if not state:
        raise WiringError(f"no pod is up (ledger/{POD_STATE_NAME} missing); start one with scripts/v4_pod.py")
    served = str(state.get("served") or state.get("hf") or "")
    if served not in (model, f"{model}-FP8"):
        raise WiringError(f"the pod serves {served or '?'} but this arm needs {model} (one model per pod)")
    return state, served


def live_leaves(*, nous_key: Union[str, Callable[[], str]], env_value: Callable[[str], str], ledger: LedgerWriter,
                pod_state: Optional[Mapping[str, Any]], pod_state_path: Path, laya_url: str,
                max_concurrency: int = 16) -> Leaves:
    """Real endpoints. Secrets are read lazily, once, and handed straight to the HTTP backends."""
    secrets: Dict[str, str] = {}

    def secret(name: str, read: Callable[[], str]) -> str:
        if name not in secrets:
            secrets[name] = read()
            ledger.add_redaction(secrets[name])
        return secrets[name]

    def state() -> Optional[Mapping[str, Any]]:
        if pod_state is not None:
            return pod_state
        return json.loads(pod_state_path.read_text()) if pod_state_path.exists() else None

    def nous() -> Provider:
        key = secret("nous", nous_key if callable(nous_key) else (lambda: nous_key))
        return OpenAICompatProvider(NOUS_URL, api_key=key, allowed_models=[NOUS_MODEL], extra_body=NOUS_EXTRA,
                                    max_concurrency=max_concurrency)

    def pod(model: str) -> Tuple[Provider, str]:
        st, served = _pod_matches(state(), model)
        key = secret("pod", lambda: str(st["api_secret"]))
        return OpenAICompatProvider(str(st["base_url"]), api_key=key, allowed_models=[served], extra_body=POD_EXTRA,
                                    max_concurrency=max_concurrency), served

    def slm() -> DecisionBackend:
        provider, served = pod(SLM_MODEL)
        return SLMBackend(provider, served)

    return Leaves(
        nous=nous, pod=pod, slm=slm, laya=lambda: LayaBackend(laya_url),
        deepseek=lambda: SLMBackend(nous(), NOUS_MODEL, name="deepseek"),
        jev=lambda: JevBackend(api_key=secret("jev", lambda: env_value("TYPESAFE_API_KEY"))))


_MENU = re.compile(r"^- (\S+?):", re.MULTILINE)


def _fake_chat_reply(request: ChatRequest) -> str:
    """Fake Nous / pod brain. Queen: allow every action to every group. Worker: the first legal action."""
    system, user = request.messages[0]["content"], request.messages[-1]["content"]
    if system.startswith("You are the queen"):
        body = json.loads(user)
        orders = {"goal": "keep working; report anything odd", "allowed": sorted(body["actions"])}
        return json.dumps({"groups": {g: orders for g in body["groups"]}})
    menu = _MENU.findall(user)
    return json.dumps({"action": menu[0] if menu else "noop"})


def _fake_answers(request: DecisionRequest, *, sure: bool) -> Dict[str, Answer]:
    """Fake decision model: first offered non-report option (REPORT in ``REPORT_SHARE`` of cases), with a
    seeded spread of confidences so that escalation fires sometimes (``sure=True`` is the
    escalation model: always confident, never unsure)."""
    rng = random.Random(int(request.request_hash[:12], 16))
    out: Dict[str, Answer] = {}
    for qid, q in sorted(request.questions.items()):
        if q.type == "noul":
            p = 0.92 if sure else round(rng.choice((0.05, 0.1, 0.35, 0.5, 0.65, 0.9, 0.95)), 2)
            out[qid] = Answer("noul", p, {"yes": p, "no": 1 - p})
            continue
        keys = q.options if q.type == "choice" else tuple(str(i) for i in range(len(q.options)))
        top = next((k for k in keys if k != REPORT), keys[0]) if q.type == "choice" else keys[0]
        if q.type == "choice" and REPORT in keys and not sure and rng.random() < REPORT_SHARE:
            top = REPORT  # now and then, so a dry run exercises report posting and report precision
        conf = 0.9 if sure else round(rng.uniform(0.3, 1.0), 3)
        rest = [k for k in keys if k != top]
        probs = {top: conf, **{k: (1 - conf) / len(rest) for k in rest}}
        out[qid] = Answer(q.type, top if q.type == "choice" else 0.0, probs, conf)
    return out


def fake_leaves(*, latency_s: float = 0.0) -> Leaves:
    """Scripted endpoints for dry runs and tests: no network, no keys."""
    def chat(model: str) -> FakeProvider:
        return FakeProvider(_fake_chat_reply, model=model, latency_s=latency_s)

    def backend(model: str, name: str, sure: bool = False) -> FakeBackend:
        return FakeBackend(lambda r: _fake_answers(r, sure=sure), model=model, name=name, latency_s=latency_s)

    return Leaves(nous=lambda: chat(NOUS_MODEL), pod=lambda model: (chat(model), model),
                  jev=lambda: backend(JEV_MODEL, "jev"), laya=lambda: backend(LAYA_MODEL, "laya"),
                  slm=lambda: backend(SLM_MODEL, "slm", sure=True), deepseek=lambda: backend(NOUS_MODEL, "deepseek"))


# --- counting + stacking --------------------------------------------------------------------------------------


class _CountingProvider:
    """Counts physical chat calls reaching the leaf. Sits directly under the ledger wrapper."""

    def __init__(self, inner: Provider, counter: List[int]) -> None:
        self.inner, self.counter = inner, counter

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    async def complete(self, request: ChatRequest) -> ChatResponse:
        self.counter[0] += 1
        return await self.inner.complete(request)


class _CountingBackend:
    def __init__(self, inner: DecisionBackend, counter: List[int]) -> None:
        self.inner, self.counter = inner, counter

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    async def decide(self, request: DecisionRequest) -> Any:
        self.counter[0] += 1
        return await self.inner.decide(request)


@dataclass
class ChatLane:
    provider: Provider
    model: str  # the model name to put on the wire


class Wiring:
    """What ``build_policies`` is handed as ``factories``: leaves + ledger + caches + per-run call counters."""

    def __init__(self, leaves: Leaves, writer: LedgerWriter, cache_dir: Path, *, offline: bool = False,
                 thresholds: Optional[Mapping[str, float]] = None) -> None:
        self.leaves, self.writer, self.cache_dir, self.offline = leaves, writer, Path(cache_dir), offline
        self.thresholds = dict(thresholds or {})  # EscalatingBackend lo / hi / c_min, fixed by the preregistration
        self.calls: Dict[str, List[List[int]]] = {}  # run id -> one counter per physical call site

    def _counter(self, run: str) -> List[int]:
        counter = [0]
        self.calls.setdefault(run, []).append(counter)
        return counter

    def physical_calls(self, run: str) -> int:
        return sum(c[0] for c in self.calls.get(run, []))

    def chat(self, spec: CellSpec, arm: ArmSpec, role: str) -> ChatLane:
        """A role-tagged, ledgered, cached chat lane for ``role`` ("every_agent" | "queen")."""
        if role == "queen" or arm.backend == "nous":
            leaf, model, backend, price = self.leaves.nous(), NOUS_MODEL, "nous", price_for(NOUS_MODEL)
        else:
            (leaf, model), backend, price = self.leaves.pod(arm.model), "vllm", (0.0, 0.0)
        counted = _CountingProvider(leaf, self._counter(spec.run_id))
        ledgered = LedgeredChat(counted, self.writer, role=role, expected_model=model, backend=backend, price=price)
        path = self.cache_dir / backend / f"{spec.run_id}-{role}.jsonl"
        return ChatLane(Cached(ledgered, path, offline=self.offline), model)

    def decision(self, spec: CellSpec, leaf: DecisionBackend, role: str) -> CachedDecision:
        backend = str(leaf.describe().get("backend", "unknown"))
        counted = _CountingBackend(leaf, self._counter(spec.run_id))
        ledgered = LedgeredDecision(counted, self.writer, role=role)
        return CachedDecision(ledgered, self.cache_dir / backend / spec.run_id, offline=self.offline)

    def reconcile(self, run: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Physical calls made by this cell vs the ledger rows written for it (cache hits are neither)."""
        physical = self.physical_calls(run)
        return {"calls_physical": physical, "calls_ledger_rows": len(rows), "calls_gap": physical - len(rows),
                "calls_reconciled": physical == len(rows)}


# --- the one assembly -----------------------------------------------------------------------------------------


def build_policies(spec: CellSpec, pilot_world: PilotWorld, world: World, *, factories: Wiring) -> PolicySet:
    """Assemble one cell's arm (the B4 recipe table in framework_arms.py). Raises SetupError before any call."""
    arm = ARMS[spec.arm]
    if arm.decider in ("script", "script_adapted"):
        return PolicySet(default_policy=pilot_world.script(spec.condition, adapted=arm.decider == "script_adapted"))
    sensor = pilot_world.sensor()
    if arm.decider == "every_agent":
        lane = factories.chat(spec, arm, "every_agent")
        return PolicySet(default_policy=StateChatPolicy(lane.provider, lane.model, sensor,
                                                        max_tokens=EVERY_AGENT_TOKENS))
    if arm.decider != "decision_model":
        raise ValueError(f"unknown decider {arm.decider!r}")
    leaves = factories.leaves
    primary = factories.decision(spec, leaves.jev() if arm.backend == "jev" else leaves.laya(), "worker")
    escalation = factories.decision(spec, leaves.slm(), "escalation") if arm.escalation else None
    backend = EscalatingBackend(primary, escalation, **factories.thresholds)
    groups, every = pilot_world.groups(world), queen_every(spec)
    queen = None
    if arm.queen:
        lane = factories.chat(spec, arm, "queen")
        queen = LLMQueen(lane.provider, lane.model, groups=groups, actions=pilot_world.actions, every=every,
                         max_tokens=QUEEN_TOKENS)
    policies = framework_policies(world.agents(), groups, backend, sensor, arm.model, use_queen=arm.queen,
                                  queen=queen, report_ttl=max(MIN_REPORT_TTL, every))
    use_queen = arm.queen
    return PolicySet(policies=policies,
                     wrap_world=lambda inner: HiveWorld(inner, pilot_world.board_summary, queen=use_queen))


# --- hooks ----------------------------------------------------------------------------------------------------


class _Tagged:
    """Calibration backend: every call is tagged ``run=phase0`` in the ledger (role ``calibration``)."""

    def __init__(self, inner: DecisionBackend, name: str) -> None:
        self.inner, self.name = inner, name

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    async def decide(self, request: DecisionRequest) -> Any:
        with ledger_context(run="phase0", arm=self.name):
            return await self.inner.decide(request)


def _make_backend(leaves: Leaves, writer: LedgerWriter) -> Callable[[str], DecisionBackend]:
    def make(name: str) -> DecisionBackend:
        if name == "jev":
            leaf = leaves.jev()
        elif name == "laya":
            leaf = leaves.laya()
        elif name == "qwen3.5-9b":
            leaf = leaves.slm()
        elif name == "deepseek":
            leaf = leaves.deepseek()
        else:
            raise ValueError(f"unknown backend {name!r}")
        return _Tagged(LedgeredDecision(leaf, writer, role="calibration"), name)  # uncached: latency is the point
    return make


def _hooks(leaves: Leaves, writer: LedgerWriter, cache_dir: Path, *, offline: bool,
           thresholds: Optional[Mapping[str, float]]) -> Hooks:
    wiring = Wiring(leaves, writer, cache_dir, offline=offline, thresholds=thresholds)

    def rows_for(run: str) -> List[Dict[str, Any]]:
        return [r for r in writer.rows() if r.get("run") == run]

    return Hooks(build_policies=lambda spec, pw, world: build_policies(spec, pw, world, factories=wiring),
                 ledger_tags=ledger_context, ledger_rows=rows_for, make_backend=_make_backend(leaves, writer),
                 reconcile=wiring.reconcile)


def make_hooks(*, nous_key: Union[str, Callable[[], str]], env_value: Callable[[str], str], ledger: Path,
               cache_dir: Path, pod_state: Optional[Mapping[str, Any]] = None, laya_url: str = LAYA_URL,
               offline: bool = False, thresholds: Optional[Mapping[str, float]] = None,
               max_concurrency: int = 16) -> Hooks:
    """Live hooks. ``nous_key`` / ``env_value`` are called lazily, only when an arm needs that secret.
    ``pod_state`` defaults to ``<ledger dir>/v4-pod-state.json`` (written by scripts/v4_pod.py)."""
    writer = LedgerWriter(ledger)
    leaves = live_leaves(nous_key=nous_key, env_value=env_value, ledger=writer, pod_state=pod_state,
                         pod_state_path=Path(ledger).parent / POD_STATE_NAME, laya_url=laya_url,
                         max_concurrency=max_concurrency)
    return _hooks(leaves, writer, Path(cache_dir), offline=offline, thresholds=thresholds)


def make_dry_hooks(*, ledger: Path, cache_dir: Path, offline: bool = False,
                   thresholds: Optional[Mapping[str, float]] = None) -> Hooks:
    """Same wiring, fake leaves: for ``--dry-run`` and tests."""
    return _hooks(fake_leaves(), LedgerWriter(ledger), Path(cache_dir), offline=offline, thresholds=thresholds)
