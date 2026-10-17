import asyncio
import copy
import json
from pathlib import Path

import httpx
import pytest

from antelligence.kernel.decision import Answer, DecisionError, DecisionRequest, Question
from antelligence.providers import (CachedDecision, ChatResponse, EscalatingBackend, FakeBackend, FakeProvider,
                                    JevBackend, LayaBackend, LedgeredDecision, LedgerWriter, ProviderError,
                                    SLMBackend, ledger_context)
from antelligence.providers.decision_backends import hashed_answers, parse_slm_json, slm_max_tokens

FIX = Path(__file__).parent / "fixtures" / "decision"
JEV = json.loads((FIX / "jev_1_13_0_reply.json").read_text())
LAYA = json.loads((FIX / "laya_typed_decisions_reply.json").read_text())
KEY = "dummy-key-for-tests"
SLM = "Qwen/Qwen3.5-9B"


def questions():
    return {
        "food_known": Question("noul", "Does the agent know where food is?",
                               criteria={"true": "A food location is stated", "false": "No food location is stated"}),
        "move": Question("choice", "Which action moves toward the food?", ("move north", "move south", "stay")),
        "urgency": Question("score", "How urgent is moving now?", ("Not urgent", "Somewhat urgent", "Very urgent")),
    }


def jev_request(seed=0):
    return DecisionRequest("jev-1.13.0", JEV["request"]["state"], questions(), seed)


def laya_request():
    return DecisionRequest("convaiinnovations/laya-typed-decisions", LAYA["request"]["state"], questions())


def transport(handler):
    seen = []

    def wrapped(request):
        seen.append(request)
        return handler(request)
    return httpx.MockTransport(wrapped), seen


def jev(handler, **kw):
    t, seen = transport(handler)
    return JevBackend("https://jev.test", KEY, transport=t, backoff_s=0, **kw), seen


def ok(fixture):
    return lambda request: httpx.Response(200, json=fixture["response"])


def run(coro):
    return asyncio.run(coro)


# --- Jev -------------------------------------------------------------------


def test_jev_sends_exact_payload_with_bearer_and_parses_reply():
    backend, seen = jev(ok(JEV))
    request = jev_request()
    response = run(backend.decide(request))
    assert len(seen) == 1 and seen[0].url.path == "/v1/systemone"
    assert json.loads(seen[0].content) == request.payload() == JEV["request"]
    assert seen[0].headers["Authorization"] == f"Bearer {KEY}"
    a = response.answers
    assert a["food_known"].p_yes == 0.94 and a["food_known"].confidence is None
    assert a["move"].value == "move north" and a["move"].confidence == 1.0
    assert a["urgency"].value == 0.43 and a["urgency"].confidence == 0.37
    assert (response.served_model, response.input_tokens, response.output_tokens) == ("jev-1.13.0", 405, 73)
    assert response.cost_usd == pytest.approx(405 * 0.042 / 1e6)  # output is free
    assert response.request_hash == request.request_hash and not response.cached


def test_jev_is_pinned_and_needs_a_key():
    with pytest.raises(ValueError):
        JevBackend("https://jev.test", KEY, model="jev-latest")
    with pytest.raises(ValueError):
        JevBackend("https://jev.test", "")
    backend, seen = jev(ok(JEV))
    with pytest.raises(DecisionError):
        run(backend.decide(DecisionRequest("jev-latest", "s", questions())))
    assert seen == []


def test_seeded_shuffle_order_is_sent_and_recorded():
    orders = set()
    for seed in range(8):
        backend, seen = jev(lambda r: httpx.Response(200, json=JEV["response"]))
        request = DecisionRequest.build("jev-1.13.0", JEV["request"]["state"], questions(), seed)
        run(backend.decide(request))
        sent = json.loads(seen[0].content)
        assert sent == request.payload()  # shuffled order is part of the payload and hash
        assert tuple(sent["questions"]["move"]["criteria"]) == request.questions["move"].options
        orders.add(request.questions["move"].options)
    assert len(orders) > 1
    again = DecisionRequest.build("jev-1.13.0", "s", questions(), 5)
    assert again.request_hash == DecisionRequest.build("jev-1.13.0", "s", questions(), 5).request_hash


def test_key_never_appears_in_ledger_cache_or_exceptions(tmp_path):
    def echo(request):  # a hostile server that echoes the Authorization header back
        return httpx.Response(400, text="bad auth " + request.headers["Authorization"])
    writer = LedgerWriter(tmp_path / "l.jsonl", redact=[KEY])
    backend, _ = jev(echo)
    stack = CachedDecision(LedgeredDecision(backend, writer), tmp_path / "cache")
    with pytest.raises(DecisionError) as err:
        run(stack.decide(jev_request()))
    assert KEY not in str(err.value) and "***" in str(err.value)
    good, _ = jev(ok(JEV))
    run(CachedDecision(LedgeredDecision(good, writer), tmp_path / "cache").decide(jev_request()))
    blob = "".join(p.read_text() for p in tmp_path.rglob("*") if p.is_file())
    assert KEY not in blob
    assert KEY not in repr(good.describe())


def test_cache_hit_writes_no_row_and_returns_identical_response(tmp_path):
    writer = LedgerWriter(tmp_path / "l.jsonl")
    backend, seen = jev(ok(JEV))
    stack = CachedDecision(LedgeredDecision(backend, writer, role="worker"), tmp_path / "cache")
    with ledger_context(run="r", arm="DS-all"):
        first = run(stack.decide(jev_request()))
        second = run(stack.decide(jev_request()))
    assert len(seen) == 1 and len(writer.rows()) == 1
    row = writer.rows()[0]
    assert row["backend"] == "jev" and row["served_model"] == "jev-1.13.0" and row["run"] == "r"
    assert row["input_tokens"] == 405 and row["cost_usd"] == pytest.approx(405 * 0.042 / 1e6)
    assert second.cached and not first.cached
    assert second.answers == first.answers and second.accounting() == first.accounting()
    assert second.cost_usd == first.cost_usd


def test_offline_cache_miss_raises_and_hit_replays(tmp_path):
    backend, seen = jev(ok(JEV))
    run(CachedDecision(backend, tmp_path).decide(jev_request()))
    offline = CachedDecision(FakeBackend(), tmp_path, offline=True)
    assert run(offline.decide(jev_request())).cached
    with pytest.raises(DecisionError, match="offline"):
        run(offline.decide(DecisionRequest("jev-1.13.0", "other", questions())))


def test_concurrent_identical_requests_call_once(tmp_path):
    backend, seen = jev(ok(JEV))
    stack = CachedDecision(backend, tmp_path)

    async def go():
        return await asyncio.gather(*(stack.decide(jev_request()) for _ in range(5)))
    assert len({r.request_hash for r in run(go())}) == 1 and len(seen) == 1


def test_retries_then_decision_error_and_error_row(tmp_path):
    writer = LedgerWriter(tmp_path / "l.jsonl")
    backend, seen = jev(lambda r: httpx.Response(503, text="down"))
    with pytest.raises(DecisionError, match="4 attempts"):
        run(LedgeredDecision(backend, writer).decide(jev_request()))
    assert len(seen) == 4  # first try + 3 retries
    rows = writer.rows()
    assert len(rows) == 1 and "DecisionError" in rows[0]["error"] and rows[0]["served_model"] is None


def test_transient_errors_recover():
    state = {"n": 0}

    def flaky(request):
        state["n"] += 1
        if state["n"] == 1:
            return httpx.Response(429)
        if state["n"] == 2:
            raise httpx.ConnectError("boom")
        if state["n"] == 3:
            return httpx.Response(200, text="not json")
        return httpx.Response(200, json=JEV["response"])
    backend, seen = jev(flaky)
    assert run(backend.decide(jev_request())).answers["move"].value == "move north"
    assert len(seen) == 4


def test_permanent_http_error_is_not_retried():
    backend, seen = jev(lambda r: httpx.Response(401, text="no"))
    with pytest.raises(DecisionError, match="401"):
        run(backend.decide(jev_request()))
    assert len(seen) == 1


def test_served_model_mismatch_rejected_without_retry():
    wrong = copy.deepcopy(JEV)
    wrong["response"]["model"] = "jev-1.14.0"
    backend, seen = jev(ok(wrong))
    with pytest.raises(DecisionError, match="jev-1.14.0"):
        run(backend.decide(jev_request()))
    assert len(seen) == 1


def test_answers_that_fail_the_contract_are_retried_then_rejected():
    bad = copy.deepcopy(JEV)
    bad["response"]["answers"]["move"]["choice"] = "teleport"
    bad["response"]["answers"]["move"]["probabilities"] = {"teleport": 1.0}
    backend, seen = jev(ok(bad))
    with pytest.raises(DecisionError):
        run(backend.decide(jev_request()))
    assert len(seen) == 4


# --- Laya ------------------------------------------------------------------


def laya(handler, **kw):
    t, seen = transport(handler)
    return LayaBackend("http://127.0.0.1:8520", transport=t, backoff_s=0, **kw), seen


def test_laya_tolerates_extra_fields_and_records_served_model():
    backend, seen = laya(ok(LAYA))
    request = laya_request()
    response = run(backend.decide(request))
    assert json.loads(seen[0].content) == request.payload() == LAYA["request"]
    assert "Authorization" not in seen[0].headers
    assert response.served_model == "laya-rl-agent"
    a = response.answers
    assert a["food_known"].p_yes == 0.496 and a["food_known"].confidence is None  # noul's confidence is ignored
    assert a["move"].value == "stay" and a["move"].confidence == 0.0152  # `confidence`, not answer_confidence
    assert a["urgency"].confidence == 0.0467
    assert (response.input_tokens, response.output_tokens, response.cost_usd) == (149, 0, 0.0)


def test_laya_refuses_wrong_request_model_and_bad_probabilities():
    backend, _ = laya(ok(LAYA))
    with pytest.raises(DecisionError):
        run(backend.decide(jev_request()))
    bad = copy.deepcopy(LAYA)
    bad["response"]["answers"]["food_known"]["noul"] = 1.7
    backend, seen = laya(ok(bad))
    with pytest.raises(DecisionError):
        run(backend.decide(laya_request()))
    assert len(seen) == 4


# --- SLM -------------------------------------------------------------------

GOOD = ('{"food_known": 0.9, "move": {"move north": 0.7, "move south": 0.1, "stay": 0.2}, '
        '"urgency": {"0": 0.2, "1": 0.3, "2": 0.5}}')


def slm_request(**kw):
    return DecisionRequest(SLM, "Carrying food: no.", questions(), **kw)


def parse(text):
    return parse_slm_json(slm_request(), text)


def test_slm_parses_good_and_fenced_json():
    for text in (GOOD, f"```json\n{GOOD}\n```", f"  ```\n{GOOD}\n```  "):
        a = parse(text)
        assert a["food_known"].p_yes == 0.9
        assert a["move"].value == "move north" and a["move"].confidence == pytest.approx(0.7)
        assert a["urgency"].value == pytest.approx(0.3 + 1.0) and a["urgency"].confidence == 0.5


@pytest.mark.parametrize("text", [
    "I think north.", '{"food_known": 0.9}', GOOD.replace('"stay": 0.2', '"fly": 0.2'),
    GOOD.replace("0.9,", "1.4,"), GOOD.replace('"stay": 0.2', '"stay": -0.1'),
    GOOD.replace('"stay": 0.2', '"stay": 0.9'),  # sums to 1.7: outside the normalisation range
    GOOD.replace('"stay": 0.2', '"stay": 0.0').replace('"move south": 0.1', '"move south": 0.0').replace(
        '"move north": 0.7', '"move north": 0.2'),  # sums to 0.2
    GOOD.replace('"0": 0.2, ', ""), GOOD.replace("0.9,", '"high",'), "[1, 2]", GOOD[:-10],
])
def test_slm_malformed_or_unnormalisable_is_rejected(text):
    with pytest.raises(DecisionError):
        parse(text)


def test_slm_probabilities_not_summing_to_one_are_normalised():
    a = parse(GOOD.replace('"move north": 0.7', '"move north": 0.6'))  # sums to 0.9
    assert sum(a["move"].probabilities.values()) == pytest.approx(1.0)
    assert a["move"].probabilities["move north"] == pytest.approx(0.6 / 0.9)
    assert a["move"].confidence == pytest.approx(0.6 / 0.9)


def slm_provider(content=GOOD, model=SLM, fail=0):
    state = {"n": 0}

    def responder(chat):
        state["n"] += 1
        if state["n"] <= fail:
            raise ProviderError("HTTP 502")
        return ChatResponse(content, model, chat.request_hash, 120, 40, "stop", elapsed_s=0.2)
    provider = FakeProvider(responder, model=model)
    return provider, state


def test_slm_backend_end_to_end_and_accounting():
    provider, _ = slm_provider()
    response = run(SLMBackend(provider, SLM, backoff_s=0).decide(slm_request(seed=9)))
    chat = provider.requests[0]
    assert chat.max_tokens == 148 and chat.temperature == 0.0 and chat.seed == 9
    prompt = chat.messages[1]["content"]
    assert "Carrying food: no." in prompt
    assert '"food_known": 0.83, "move": {"move north": p, "move south": p, "stay": p}' in prompt
    assert '"urgency": {"0": p, "1": p, "2": p}' in prompt
    assert response.answers["move"].value == "move north"
    assert (response.served_model, response.input_tokens, response.output_tokens) == (SLM, 120, 40)
    assert response.cost_usd == 0.0


def test_slm_retries_provider_errors_then_gives_up():
    provider, state = slm_provider(fail=2)
    assert run(SLMBackend(provider, SLM, backoff_s=0).decide(slm_request())).answers
    assert state["n"] == 3
    provider, state = slm_provider(fail=99)
    with pytest.raises(DecisionError, match="4 attempts"):
        run(SLMBackend(provider, SLM, backoff_s=0).decide(slm_request()))
    assert state["n"] == 4


def test_slm_rejects_served_model_mismatch_and_malformed_without_retry():
    provider, state = slm_provider(model="Qwen/Other")
    with pytest.raises(DecisionError, match="served model"):
        run(SLMBackend(provider, SLM, backoff_s=0).decide(slm_request()))
    provider, state = slm_provider(content="nope")
    with pytest.raises(DecisionError):
        run(SLMBackend(provider, SLM, backoff_s=0).decide(slm_request()))
    assert state["n"] == 1


SHAPES = [  # (replacement for the three-question GOOD reply, expected food_known, expected move confidence)
    ('{"food_known": {"noul": 0.5}, ', 0.5), ('{"food_known": {"p_yes": 0.5}, ', 0.5),
    ('{"food_known": {"yes": 0.5}, ', 0.5), ('{"food_known": {"yes": 1.0, "no": 3.0}, ', 0.25),
    ('{"food_known": {"choice": {"yes": 0.0, "no": 1.0}}, ', 0.0)]


@pytest.mark.parametrize("head,expected", SHAPES)
def test_slm_noul_tolerates_wrapped_and_yes_no_forms(head, expected):
    assert parse(head + GOOD.split(", ", 1)[1])["food_known"].p_yes == pytest.approx(expected)


def test_slm_choice_nested_and_omitted_zero_options():
    a = parse(GOOD.replace('"move": {', '"move": {"choice": {').replace('"stay": 0.2}', '"stay": 0.2}}'))
    assert a["move"].value == "move north"
    full = GOOD.replace('"move south": 0.1, ', "").replace('"stay": 0.2', '"stay": 0.3')  # listed sum 1.0
    assert parse(full)["move"].probabilities["move south"] == 0.0
    with pytest.raises(DecisionError):  # listed options sum 0.9 < 0.98: not safe to assume the rest is 0
        parse(GOOD.replace('"move south": 0.1, ', ""))
    with pytest.raises(DecisionError):
        parse(GOOD.replace('"food_known": 0.9', '"food_known": {"maybe": 0.9}'))


def test_slm_length_and_parse_failures_are_not_retried():
    for content, finish in ((GOOD[:30], "length"), ("nope", "stop")):
        provider = FakeProvider(lambda chat: ChatResponse(content, SLM, chat.request_hash, 9, 9, finish), model=SLM)
        with pytest.raises(DecisionError):
            run(SLMBackend(provider, SLM, backoff_s=0).decide(slm_request()))
        assert len(provider.requests) == 1
    calls = []

    class LengthRaising:  # OpenAICompatProvider raises on a length cut-off before SLMBackend sees the reply
        def describe(self):
            return {"provider": "length-raising"}

        async def complete(self, chat):
            calls.append(chat)
            raise ProviderError("generation did not finish normally (length)")

    with pytest.raises(DecisionError, match="cut off"):
        run(SLMBackend(LengthRaising(), SLM, backoff_s=0).decide(slm_request()))
    assert len(calls) == 1


def test_slm_max_tokens_scales_with_options_and_respects_cap():
    request = slm_request()
    assert slm_max_tokens(request) == 148
    assert slm_max_tokens(request, cap=50) == 50
    big = DecisionRequest(SLM, "s", {"m": Question("choice", "?", tuple(f"o{i}" for i in range(7)))})
    assert slm_max_tokens(big) == 146 and slm_max_tokens(slm_request(), 256) == 148


# --- Fake ------------------------------------------------------------------


def test_fake_backend_default_is_deterministic_and_valid():
    request = DecisionRequest("fake-1", "state", questions())
    a, b = run(FakeBackend().decide(request)), run(FakeBackend().decide(request))
    assert a.answers == b.answers and a.served_model == "fake-1"
    other = DecisionRequest("fake-1", "different state", questions())
    assert hashed_answers(other) != hashed_answers(request)


def test_fake_backend_rejects_contract_breaking_responder():
    backend = FakeBackend(lambda r: {})
    with pytest.raises(DecisionError):
        run(backend.decide(DecisionRequest("fake-1", "s", questions())))


# --- escalation ------------------------------------------------------------


def scripted(p_yes, confidence, name="primary"):
    def responder(request):
        out = {}
        for qid, q in request.questions.items():
            if q.type == "noul":
                out[qid] = Answer("noul", p_yes, {"yes": p_yes, "no": 1 - p_yes})
            elif q.type == "choice":
                rest = 0.2 / (len(q.options) - 1)
                probs = {o: (0.8 if i == 0 else rest) for i, o in enumerate(q.options)}
                out[qid] = Answer("choice", q.options[0], probs, confidence)
            else:
                out[qid] = Answer("score", 0.0, {"0": 1.0, "1": 0.0, "2": 0.0}, 0.0)
        return out
    return FakeBackend(responder, model=name, name=name)


def two_questions():
    return {"a": Question("noul", "A?"), "b": Question("noul", "B?"),
            "move": Question("choice", "Which?", ("x", "y", "z"))}


@pytest.mark.parametrize("p_yes,escalates", [(0.2, False), (0.21, True), (0.5, True), (0.79, True), (0.8, False),
                                              (0.0, False), (1.0, False)])
def test_noul_escalation_boundaries(p_yes, escalates):
    esc = scripted(0.99, 0.9, "esc")
    hub = EscalatingBackend(scripted(p_yes, 0.9), esc)
    response = run(hub.decide(DecisionRequest("primary", "s", {"a": Question("noul", "A?")})))
    assert bool(esc.requests) is escalates
    assert response.escalated == (("a",) if escalates else ())
    assert response.answers["a"].p_yes == (0.99 if escalates else p_yes)


@pytest.mark.parametrize("confidence,escalates", [(0.5, False), (0.4999, True), (0.0, True), (1.0, False)])
def test_choice_escalation_boundary(confidence, escalates):
    esc = scripted(0.5, 0.9, "esc")
    hub = EscalatingBackend(scripted(0.99, confidence), esc)
    run(hub.decide(DecisionRequest("primary", "s", {"move": Question("choice", "Which?", ("x", "y", "z"))})))
    assert bool(esc.requests) is escalates


def test_only_uncertain_questions_are_reasked_and_merged():
    def primary_responder(request):
        base = scripted(0.5, 0.9).responder(request)
        base["a"] = Answer("noul", 0.95, {"yes": 0.95, "no": 0.05})  # confident
        return base                                                    # b stays at 0.5 (uncertain), move conf .9
    esc = scripted(0.1, 0.9, "esc")
    hub = EscalatingBackend(FakeBackend(primary_responder, model="primary"), esc)
    request = DecisionRequest("primary", "state text", two_questions(), seed=3)
    response = run(hub.decide(request))
    (sub,) = esc.requests
    assert list(sub.questions) == ["b"] and sub.model == "esc" and sub.state == "state text" and sub.seed == 3
    assert response.escalated == ("b",)
    assert response.answers["a"].p_yes == 0.95 and response.answers["b"].p_yes == 0.1
    assert response.request_hash == request.request_hash and response.served_model == "primary"
    assert response.input_tokens == sum(len(r.state) // 4 for r in (request, sub))


def test_escalated_choice_keeps_shuffled_option_order():
    esc = scripted(0.5, 0.9, "esc")
    hub = EscalatingBackend(scripted(0.99, 0.1), esc)
    request = DecisionRequest.build("primary", "s", {"move": Question("choice", "Which?", ("x", "y", "z", "w"))}, 11)
    run(hub.decide(request))
    assert esc.requests[0].questions["move"].options == request.questions["move"].options


def test_custom_thresholds_and_no_escalation_backend():
    esc = scripted(0.5, 0.9, "esc")
    request = DecisionRequest("primary", "s", {"a": Question("noul", "A?")})
    run(EscalatingBackend(scripted(0.25, 0.9), esc, lo=0.3, hi=0.7).decide(request))
    assert esc.requests == []
    assert run(EscalatingBackend(scripted(0.5, 0.9)).decide(request)).escalated == ()
    for bad in ({"lo": 0.8, "hi": 0.2}, {"c_min": 1.5}):
        with pytest.raises(ValueError):
            EscalatingBackend(scripted(0.5, 0.9), **bad)


def test_escalation_failure_keeps_the_primary_answer_and_rows_have_roles(tmp_path):
    writer = LedgerWriter(tmp_path / "l.jsonl")
    primary = LedgeredDecision(scripted(0.5, 0.9), writer, role="worker")
    esc = LedgeredDecision(scripted(0.5, 0.9, "esc"), writer, role="escalation")
    request = DecisionRequest("primary", "s", {"a": Question("noul", "A?")})
    run(EscalatingBackend(primary, esc).decide(request))
    assert [r["role"] for r in writer.rows()] == ["worker", "escalation"]

    def boom(request):
        raise DecisionError("down")
    out = run(EscalatingBackend(scripted(0.5, 0.9), FakeBackend(boom, model="esc")).decide(request))
    assert out.answers["a"].p_yes == 0.5 and out.escalated == () and out.escalation_failed == ("a",)
    assert out.accounting()["escalation_failed"] == ["a"]
    assert "escalation_failed" not in run(EscalatingBackend(scripted(0.99, 0.9), esc).decide(request)).accounting()
