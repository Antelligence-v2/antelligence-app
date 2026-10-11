"""Decision backends: Jev, Laya, an SLM on vLLM, a fake, plus cache, ledger and escalation wrappers.

All of them speak :class:`DecisionRequest` / :class:`DecisionResponse` from the
kernel contract. Stack for a run (innermost first)::

    EscalatingBackend(
        CachedDecision(LedgeredDecision(JevBackend(...), writer, role="worker"), cache_dir),
        CachedDecision(LedgeredDecision(SLMBackend(...), writer, role="escalation"), cache_dir),
    )

Keys are passed in by the caller and only ever used in the Authorization header;
they are scrubbed from every error message. Retry policy: transport errors,
HTTP 429/5xx and malformed bodies are retried ``retries`` times (default 3, so up
to 4 attempts), then :class:`DecisionError`. Other 4xx and a served-model mismatch
fail at once. No backend reads the environment or any file for credentials.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import math
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, Union

import httpx

from antelligence.kernel.canonical import canonical_json, content_hash
from antelligence.kernel.decision import (Answer, DecisionBackend, DecisionError, DecisionRequest, DecisionResponse,
                                          Question, QUESTION_TYPES, check_answers)
from antelligence.providers.base import BudgetExceeded, ChatRequest, Provider, ProviderError
from antelligence.providers.ledger import LedgerWriter, cost_usd

JEV_MODEL = "jev-1.13.0"
JEV_URL = "https://api.typesafe.ai"
LAYA_MODEL = "convaiinnovations/laya-typed-decisions"
LAYA_URL = "http://127.0.0.1:8520"
MAX_RESPONSE_BYTES = 2_000_000


class _Transient(Exception):
    """Worth retrying."""


class _Permanent(Exception):
    """Retrying cannot help."""


# --- wire <-> Answer -------------------------------------------------------


def _num(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"not a finite number: {value!r}")
    return float(value)


def parse_wire_answers(request: DecisionRequest, wire: Mapping[str, Any]) -> Dict[str, Answer]:
    """Jev/laya-serve ``answers`` -> Answers. Extra fields (answer_confidence, action, ...) are ignored."""
    if not isinstance(wire, Mapping):
        raise ValueError("answers is not an object")
    out: Dict[str, Answer] = {}
    for qid, question in request.questions.items():
        a = wire[qid]
        if a.get("type") != question.type:
            raise ValueError(f"{qid}: answer type {a.get('type')!r} != {question.type!r}")
        if question.type == "noul":
            p = _num(a["noul"])
            out[qid] = Answer("noul", p, {"yes": p, "no": 1.0 - p})
        else:
            confidence = None if a.get("confidence") is None else _num(a["confidence"])
            value = a["choice"] if question.type == "choice" else _num(a["score"])
            out[qid] = Answer(question.type, value, {str(k): _num(v) for k, v in a["probabilities"].items()},
                              confidence)
    return out


# --- HTTP backends ---------------------------------------------------------


class _TypedHTTPBackend:
    """POST /v1/systemone with retries, identity check, accounting."""

    name = "http"

    def __init__(self, base_url: str, *, model: str, api_key: Optional[str] = None, timeout_s: float = 60.0,
                 retries: int = 3, backoff_s: float = 0.5, price: Tuple[float, float] = (0.0, 0.0),
                 transport: Optional[httpx.AsyncBaseTransport] = None) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must be http(s)")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._api_key = api_key
        self.timeout_s, self.retries, self.backoff_s, self.price = timeout_s, retries, backoff_s, price
        self._transport = transport
        self.calls = 0  # physical HTTP attempts

    def describe(self) -> Dict[str, Any]:
        return {"backend": self.name, "model": self.model, "base_url": self.base_url}

    def _scrub(self, text: str) -> str:
        return text.replace(self._api_key, "***") if self._api_key else text

    def _check_served(self, served: str) -> None:
        raise NotImplementedError

    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        if request.model != self.model:
            raise DecisionError(f"request model {request.model!r} != backend model {self.model!r}")
        last = ""
        for attempt in range(self.retries + 1):
            try:
                return await self._once(request)
            except _Permanent as exc:
                raise DecisionError(self._scrub(f"{self.name}: {exc}")) from None
            except _Transient as exc:
                last = self._scrub(str(exc))
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff_s * (attempt + 1))
        raise DecisionError(f"{self.name}: failed after {self.retries + 1} attempts: {last}")

    async def _once(self, request: DecisionRequest) -> DecisionResponse:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        self.calls += 1
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, follow_redirects=False, trust_env=False,
                                         transport=self._transport) as client:
                reply = await client.post(f"{self.base_url}/v1/systemone", json=request.payload(), headers=headers)
        except httpx.HTTPError as exc:
            raise _Transient(f"transport error: {type(exc).__name__}") from None
        elapsed = time.monotonic() - start
        if reply.status_code == 429 or reply.status_code >= 500:
            raise _Transient(f"HTTP {reply.status_code}")
        if reply.status_code != 200:
            raise _Permanent(f"HTTP {reply.status_code}: {reply.text[:200]}")
        if len(reply.content) > MAX_RESPONSE_BYTES:
            raise _Permanent("response exceeds size limit")
        try:
            data = reply.json()
            served = data["model"]
            answers = parse_wire_answers(request, data["answers"])
            usage = data.get("usage") or {}
            tokens_in, tokens_out = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
        except (ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
            raise _Transient(f"malformed response: {type(exc).__name__}: {exc}") from None
        if not isinstance(served, str) or not served:
            raise _Transient("malformed response: no served model")
        self._check_served(served)
        try:
            check_answers(request, answers)
        except DecisionError as exc:
            raise _Transient(str(exc)) from None
        return DecisionResponse(answers=answers, served_model=served, request_hash=request.request_hash,
                                input_tokens=tokens_in, output_tokens=tokens_out,
                                cost_usd=cost_usd(tokens_in, tokens_out, self.price), elapsed_s=elapsed)


class JevBackend(_TypedHTTPBackend):
    """TypeSafe Jev, pinned to ``jev-1.13.0`` (``jev-latest`` is refused). ``base_url`` is the origin."""

    name = "jev"

    def __init__(self, base_url: str = JEV_URL, api_key: str = "", *, model: str = JEV_MODEL, **kw: Any) -> None:
        if model != JEV_MODEL:
            raise ValueError(f"Jev is pinned to {JEV_MODEL!r}; got {model!r}")
        if not api_key:
            raise ValueError("api_key is required (pass it in; this module never reads the environment)")
        super().__init__(base_url, model=model, api_key=api_key, price=(0.042, 0.0), **kw)

    def _check_served(self, served: str) -> None:
        if served != JEV_MODEL:
            raise _Permanent(f"served model {served!r} is not {JEV_MODEL!r}")


class LayaBackend(_TypedHTTPBackend):
    """Local ``laya-serve``. Whatever model name it reports (e.g. ``laya-rl-agent``) is recorded."""

    name = "laya"

    def __init__(self, base_url: str = LAYA_URL, *, model: str = LAYA_MODEL, api_key: Optional[str] = None,
                 **kw: Any) -> None:
        super().__init__(base_url, model=model, api_key=api_key, **kw)

    def _check_served(self, served: str) -> None:  # any non-empty name; it is recorded in served_model
        return None


# --- SLM -------------------------------------------------------------------

_SLM_SYSTEM = (
    "You answer typed questions about a state. Reply with ONE JSON object and nothing else: no prose, no code "
    "fence. Probabilities in one question sum to 1; every listed option must appear (0 is allowed).")
SLM_TOKEN_CAP = 256  # per-request budget ceiling; the every-agent arms' 64-token cap does not apply here
_FENCE = re.compile(r"^```[a-zA-Z]*\s*(.*?)\s*```$", re.DOTALL)
NORMALISE_RANGE = (0.5, 1.5)  # probability vectors summing inside this are rescaled to 1; outside is rejected


def slm_max_tokens(request: DecisionRequest, cap: int = SLM_TOKEN_CAP) -> int:
    """24 + 12 per noul + 10 per option of every choice/score question, at most ``cap``."""
    need = 24 + sum(12 if q.type == "noul" else 10 * len(q.options) for q in request.questions.values())
    return min(need, cap)


def _slm_prompt(request: DecisionRequest) -> str:
    questions, shape = {}, []
    for qid, q in request.questions.items():
        body: Dict[str, Any] = {"type": q.type, "instructions": q.instructions}
        keys = q.options if q.type == "choice" else tuple(str(i) for i in range(len(q.options)))
        if q.type == "choice":
            body["options"] = {o: q.criteria.get(o) for o in q.options}
        elif q.type == "score":
            body["levels"] = {str(i): text for i, text in enumerate(q.options)}
        questions[qid] = body
        probs = ", ".join(f"{json.dumps(k)}: p" for k in keys)
        shape.append(f"{json.dumps(qid)}: " + ("0.83" if q.type == "noul" else "{" + probs + "}"))
    return (json.dumps({"state": request.state, "questions": questions}, ensure_ascii=False, sort_keys=True)
            + "\nReply exactly in this shape (noul: P(yes) as one number, e.g. 0.83; choice/score: p is each "
            "option's probability, all options listed, sum 1):\n{" + ", ".join(shape) + "}")


def _unwrap(raw: Any) -> Any:
    """Models nest the value under the type name ({"noul": x}); strip one such wrapper."""
    if isinstance(raw, dict) and len(raw) == 1 and next(iter(raw)) in QUESTION_TYPES:
        return next(iter(raw.values()))
    return raw


def _p_yes(raw: Any) -> float:
    """Number, {"p_yes": x}, {"yes": x} or {"yes": a, "no": b} (a / (a + b)); anything else is rejected."""
    raw = _unwrap(raw)
    if not isinstance(raw, dict):
        return _num(raw)
    if set(raw) == {"p_yes"}:
        return _num(raw["p_yes"])
    if "yes" in raw and set(raw) <= {"yes", "no"}:
        yes, no = _num(raw["yes"]), _num(raw.get("no", 0.0))
        if yes < 0 or no < 0 or ("no" in raw and yes + no == 0):
            raise ValueError(f"yes/no weights {yes}, {no} are unusable")
        return yes / (yes + no) if "no" in raw else yes
    raise ValueError(f"cannot read P(yes) from {raw!r}")


def _distribution(raw: Any, keys: Tuple[str, ...]) -> Dict[str, float]:
    """Option map (maybe nested under the type name). Unknown names reject; omitted options count as 0 only
    when the listed ones already sum to >= 0.98 (otherwise the reply was truncated or confused)."""
    raw = _unwrap(raw)
    if not isinstance(raw, dict) or not raw or not {str(k) for k in raw} <= set(keys):
        raise ValueError(f"probabilities must be named from {list(keys)}")
    probs = {str(k): _num(v) for k, v in raw.items()}
    total = sum(probs.values())
    if len(probs) < len(keys) and total < 0.98:
        raise ValueError(f"options {sorted(set(keys) - set(probs))} missing and listed ones sum to {total:.3f}")
    if any(p < 0 for p in probs.values()) or not NORMALISE_RANGE[0] <= total <= NORMALISE_RANGE[1]:
        raise ValueError(f"probabilities sum to {total:.3f}")
    return {k: probs.get(k, 0.0) / total for k in keys}


def parse_slm_json(request: DecisionRequest, text: str) -> Dict[str, Answer]:
    """Strict parse of the SLM's JSON object (code fences allowed). Sums within 0.5..1.5 are normalised to 1."""
    body = text.strip()
    fenced = _FENCE.match(body)
    if fenced:
        body = fenced.group(1)
    try:
        raw = json.loads(body)
    except ValueError as exc:
        raise DecisionError(f"slm: reply is not JSON ({exc})") from None
    if not isinstance(raw, dict) or set(raw) != set(request.questions):
        raise DecisionError("slm: reply keys do not match the question ids")
    answers: Dict[str, Answer] = {}
    try:
        for qid, q in request.questions.items():
            if q.type == "noul":
                p = _p_yes(raw[qid])
                if not 0.0 <= p <= 1.0:
                    raise ValueError(f"{qid}: P(yes) {p} outside [0, 1]")
                answers[qid] = Answer("noul", p, {"yes": p, "no": 1.0 - p})
                continue
            keys = q.options if q.type == "choice" else tuple(str(i) for i in range(len(q.options)))
            probs = _distribution(raw[qid], keys)
            top = max(probs.values())
            if q.type == "choice":
                value: Any = next(k for k in keys if probs[k] == top)
            else:
                value = sum(int(k) * p for k, p in probs.items())
            answers[qid] = Answer(q.type, value, probs, top)
    except ValueError as exc:
        raise DecisionError(f"slm: {exc}") from None
    return answers


class SLMBackend:
    """Asks a chat model the same typed questions; non-thinking is the provider's extra_body.

    ``max_tokens`` caps the per-request budget from :func:`slm_max_tokens`. Only transport/provider errors are
    retried; a length cut-off or an unparseable reply raises at once.
    """

    def __init__(self, provider: Provider, model: str, *, max_tokens: int = SLM_TOKEN_CAP, retries: int = 3,
                 backoff_s: float = 0.5, name: str = "slm") -> None:
        self.provider, self.model, self.max_tokens = provider, model, max_tokens
        self.retries, self.backoff_s, self.name = retries, backoff_s, name

    def describe(self) -> Dict[str, Any]:
        return {"backend": self.name, "model": self.model, "provider": self.provider.describe()}

    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        if request.model != self.model:
            raise DecisionError(f"request model {request.model!r} != backend model {self.model!r}")
        chat = ChatRequest(self.model, ({"role": "system", "content": _SLM_SYSTEM},
                                        {"role": "user", "content": _slm_prompt(request)}),
                           max_tokens=slm_max_tokens(request, self.max_tokens), temperature=0.0, seed=request.seed)
        last = ""
        for attempt in range(self.retries + 1):
            try:
                reply = await self.provider.complete(chat)
                break
            except BudgetExceeded as exc:
                raise DecisionError(f"{self.name}: {exc}") from None
            except ProviderError as exc:
                last = str(exc)
                if attempt < self.retries:
                    await asyncio.sleep(self.backoff_s * (attempt + 1))
        else:
            raise DecisionError(f"{self.name}: failed after {self.retries + 1} attempts: {last}")
        if reply.model != self.model:
            raise DecisionError(f"{self.name}: served model {reply.model!r} is not {self.model!r}")
        if reply.finish_reason == "length":  # deterministic at temperature 0: a retry would only repeat it
            raise DecisionError(f"{self.name}: reply cut off at max_tokens={chat.max_tokens}")
        answers = parse_slm_json(request, reply.content)  # malformed output is not retried: temperature 0
        check_answers(request, answers)
        reported = (reply.extra or {}).get("cost")
        return DecisionResponse(answers=answers, served_model=reply.model, request_hash=request.request_hash,
                                input_tokens=reply.prompt_tokens, output_tokens=reply.completion_tokens,
                                cost_usd=float(reported) if isinstance(reported, (int, float)) else 0.0,
                                elapsed_s=reply.elapsed_s)


# --- fake ------------------------------------------------------------------


def hashed_answers(request: DecisionRequest) -> Dict[str, Answer]:
    """Default FakeBackend responder: deterministic, varied, valid answers derived from the request hash."""
    out: Dict[str, Answer] = {}
    for qid, q in request.questions.items():
        h = int(content_hash([request.request_hash, qid])[:8], 16)
        if q.type == "noul":
            p = (h % 101) / 100
            out[qid] = Answer("noul", p, {"yes": p, "no": 1.0 - p})
            continue
        n = len(q.options)
        keys = q.options if q.type == "choice" else tuple(str(i) for i in range(n))
        top = h % n
        rest = 0.3 / (n - 1)
        probs = {k: (0.7 if i == top else rest) for i, k in enumerate(keys)}
        value: Any = keys[top] if q.type == "choice" else float(sum(i * probs[k] for i, k in enumerate(keys)))
        out[qid] = Answer(q.type, value, probs, 0.7)
    return out


class FakeBackend:
    """Offline backend: ``responder(request) -> {qid: Answer}`` (default :func:`hashed_answers`)."""

    def __init__(self, responder: Optional[Callable[[DecisionRequest], Mapping[str, Answer]]] = None, *,
                 model: str = "fake-1", served_model: Optional[str] = None, latency_s: float = 0.0,
                 name: str = "fake") -> None:
        self.responder = responder or hashed_answers
        self.model, self.served_model, self.latency_s, self.name = model, served_model or model, latency_s, name
        self.requests: list = []

    def describe(self) -> Dict[str, Any]:
        return {"backend": self.name, "model": self.model}

    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        self.requests.append(request)
        if self.latency_s:
            await asyncio.sleep(self.latency_s)
        answers = dict(self.responder(request))
        check_answers(request, answers)
        return DecisionResponse(answers=answers, served_model=self.served_model, request_hash=request.request_hash,
                                input_tokens=max(1, len(request.state) // 4), output_tokens=len(answers) * 4,
                                elapsed_s=self.latency_s)


# --- cache / ledger / escalation -------------------------------------------


def response_to_dict(response: DecisionResponse) -> Dict[str, Any]:
    return {"answers": {q: a.to_dict() for q, a in response.answers.items()}, "served_model": response.served_model,
            "request_hash": response.request_hash, "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens, "cost_usd": response.cost_usd, "elapsed_s": response.elapsed_s,
            "escalated": list(response.escalated)}


def response_from_dict(data: Mapping[str, Any], *, cached: bool = False) -> DecisionResponse:
    answers = {q: Answer(a["type"], a["value"], a["probabilities"], a["confidence"])
               for q, a in data["answers"].items()}
    return DecisionResponse(answers=answers, served_model=data["served_model"], request_hash=data["request_hash"],
                            input_tokens=data["input_tokens"], output_tokens=data["output_tokens"],
                            cost_usd=data["cost_usd"], elapsed_s=data["elapsed_s"], cached=cached,
                            escalated=tuple(data["escalated"]))


class CachedDecision:
    """Reply cache keyed by request hash, one JSON file per reply under ``cache_dir``.

    A hit returns the stored reply (``cached=True``) and calls nothing, so a
    wrapped :class:`LedgeredDecision` writes no row. ``offline=True`` raises on a miss.
    """

    def __init__(self, inner: DecisionBackend, cache_dir: Union[str, Path], *, offline: bool = False) -> None:
        self.inner, self.cache_dir, self.offline = inner, Path(cache_dir), offline
        self._locks: Dict[str, asyncio.Lock] = {}

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()  # transparent: a replay shares the live run's config

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        key = request.request_hash
        async with self._locks.setdefault(key, asyncio.Lock()):  # identical concurrent requests call once
            path = self._path(key)
            if path.exists():
                return response_from_dict(json.loads(path.read_text(encoding="utf-8")), cached=True)
            if self.offline:
                raise DecisionError(f"cache miss in offline mode ({key[:12]})")
            response = await self.inner.decide(request)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(canonical_json(response_to_dict(response)), encoding="utf-8")
            tmp.replace(path)
            return response


class LedgeredDecision:
    """One ledger row per physical ``decide`` (failures write an error row). Put it under the cache."""

    def __init__(self, inner: DecisionBackend, writer: LedgerWriter, *, role: str = "worker") -> None:
        self.inner, self.writer, self.role = inner, writer, role
        self.backend = str(inner.describe().get("backend", "unknown"))

    def describe(self) -> Dict[str, Any]:
        return self.inner.describe()

    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        try:
            response = await self.inner.decide(request)
        except Exception as exc:
            self.writer.write(role=self.role, backend=self.backend, model=request.model, served_model=None,
                              request_hash=request.request_hash, error=f"{type(exc).__name__}: {exc}")
            raise
        self.writer.write(role=self.role, backend=self.backend, model=request.model,
                          served_model=response.served_model, request_hash=request.request_hash,
                          input_tokens=response.input_tokens, output_tokens=response.output_tokens,
                          latency_s=response.elapsed_s, cost_usd=response.cost_usd)
        return response


class EscalatingBackend:
    """Primary backend plus an optional escalation backend for the questions it is unsure about.

    A noul is uncertain when ``lo < P(yes) < hi`` (boundaries are confident); a
    choice when ``confidence < c_min`` or missing; scores never escalate. Only the
    uncertain questions are re-asked, in their original option order, and the
    escalation answers replace the primary's. A failing escalation raises.
    ``escalation`` must report its model in ``describe()["model"]``.
    """

    def __init__(self, primary: DecisionBackend, escalation: Optional[DecisionBackend] = None, *,
                 lo: float = 0.2, hi: float = 0.8, c_min: float = 0.5) -> None:
        if not 0.0 <= lo < hi <= 1.0 or not 0.0 <= c_min <= 1.0:
            raise ValueError("need 0 <= lo < hi <= 1 and 0 <= c_min <= 1")
        self.primary, self.escalation, self.lo, self.hi, self.c_min = primary, escalation, lo, hi, c_min

    def describe(self) -> Dict[str, Any]:
        return {"backend": "escalating", "model": self.primary.describe().get("model"),
                "primary": self.primary.describe(),
                "escalation": None if self.escalation is None else self.escalation.describe(),
                "lo": self.lo, "hi": self.hi, "c_min": self.c_min}

    def uncertain(self, question: Question, answer: Answer) -> bool:
        if question.type == "noul":
            return self.lo < answer.p_yes < self.hi
        if question.type == "choice":
            return answer.confidence is None or answer.confidence < self.c_min
        return False

    async def decide(self, request: DecisionRequest) -> DecisionResponse:
        first = await self.primary.decide(request)
        if self.escalation is None:
            return first
        unsure = {qid: q for qid, q in request.questions.items() if self.uncertain(q, first.answers[qid])}
        if not unsure:
            return first
        sub = DecisionRequest(str(self.escalation.describe()["model"]), request.state, unsure, request.seed)
        second = await self.escalation.decide(sub)
        merged = {**first.answers, **second.answers}
        check_answers(request, merged)
        return dataclasses.replace(
            first, answers=merged, input_tokens=first.input_tokens + second.input_tokens,
            output_tokens=first.output_tokens + second.output_tokens, cost_usd=first.cost_usd + second.cost_usd,
            elapsed_s=first.elapsed_s + second.elapsed_s, cached=first.cached and second.cached,
            escalated=tuple(sorted(set(first.escalated) | set(unsure))))
