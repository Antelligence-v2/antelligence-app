import asyncio
import json

import httpx
import pytest

from antelligence.providers import (
    BudgetExceeded,
    Budgeted,
    Cached,
    ChatRequest,
    FakeProvider,
    OpenAICompatProvider,
    ProviderError,
)


def req(content="hi", model="m1", **kw):
    return ChatRequest(model=model, messages=({"role": "user", "content": content},), **kw)


def reply(model="m1", content='{"ok":1}', finish="stop", usage=None, status=200):
    body = {"id": "r1", "model": model, "choices": [{"message": {"content": content}, "finish_reason": finish}],
            "usage": usage if usage is not None else {"prompt_tokens": 5, "completion_tokens": 3}}
    return httpx.Response(status, json=body)


def provider(handler, **kw):
    seen = []

    def record(request):
        seen.append(request)
        return handler(request)

    return OpenAICompatProvider("http://local.test/v1", transport=httpx.MockTransport(record), **kw), seen


def run(coro):
    return asyncio.run(coro)


def test_request_hash_is_stable_and_sensitive():
    assert req().request_hash == req().request_hash
    assert req().request_hash != req(temperature=0.5).request_hash
    assert req().request_hash != req(seed=1).request_hash
    with pytest.raises(ValueError):
        ChatRequest(model="m", messages=({"role": "tool", "content": "x"},))


def test_openai_compat_happy_path_and_payload():
    p, seen = provider(lambda r: reply(), api_key="k", extra_body={"cache_prompt": False})
    response = run(p.complete(req(seed=7, response_format={"type": "json_object"})))
    assert response.content == '{"ok":1}' and response.prompt_tokens == 5 and not response.cached
    assert response.request_hash == req(seed=7, response_format={"type": "json_object"}).request_hash
    sent = json.loads(seen[0].content)
    assert sent["seed"] == 7 and sent["cache_prompt"] is False and sent["response_format"] == {"type": "json_object"}
    assert seen[0].headers["authorization"] == "Bearer k"
    assert str(seen[0].url) == "http://local.test/v1/chat/completions"


@pytest.mark.parametrize(
    "response, message",
    [
        (reply(model="other"), "differs"),
        (reply(finish="length"), "did not finish"),
        (reply(usage={"prompt_tokens": 1}), "malformed"),
        (reply(usage={"prompt_tokens": -1, "completion_tokens": 2}), "usage"),
        (reply(status=500), "HTTP 500"),
        (httpx.Response(200, text="not json"), "malformed"),
    ],
)
def test_untrustworthy_responses_are_refused(response, message):
    p, _ = provider(lambda r: response)
    with pytest.raises(ProviderError, match=message):
        run(p.complete(req()))


def test_allowlist_and_transport_errors():
    p, seen = provider(lambda r: reply(), allowed_models={"m1"})
    with pytest.raises(ProviderError, match="allowlisted"):
        run(p.complete(req(model="m2")))
    assert seen == []

    def boom(request):
        raise httpx.ConnectError("refused")

    p, _ = provider(boom)
    with pytest.raises(ProviderError, match="transport"):
        run(p.complete(req()))
    with pytest.raises(ValueError):
        OpenAICompatProvider("ftp://x")


def test_fake_provider_counts_tokens_and_records_requests():
    fake = FakeProvider(lambda r: "abcdefgh")
    response = run(fake.complete(req()))
    assert response.completion_tokens == 2 and response.finish_reason == "stop"
    assert fake.requests == [req()]


def test_cache_hits_persist_and_offline_misses_fail(tmp_path):
    path = tmp_path / "cache.jsonl"
    calls = []
    inner = FakeProvider(lambda r: calls.append(r) or f"answer-{len(calls)}")
    cache = Cached(inner, path)
    first = run(cache.complete(req()))
    second = run(cache.complete(req()))
    assert first.content == second.content == "answer-1" and second.cached and len(calls) == 1
    replay = Cached(FakeProvider(lambda r: "never"), path, offline=True)
    assert run(replay.complete(req())).content == "answer-1"
    with pytest.raises(ProviderError, match="offline"):
        run(replay.complete(req("different")))


def test_cache_deduplicates_concurrent_identical_requests():
    calls = []
    cache = Cached(FakeProvider(lambda r: calls.append(1) or "x", latency_s=0.01))

    async def many():
        return await asyncio.gather(*(cache.complete(req()) for _ in range(5)))

    results = run(many())
    assert len(calls) == 1 and sum(r.cached for r in results) == 4


def test_budget_caps_calls_and_tokens_and_counts_failures():
    budget = Budgeted(FakeProvider(lambda r: "x" * 40), max_calls=2)
    run(budget.complete(req("a")))
    run(budget.complete(req("b")))
    with pytest.raises(BudgetExceeded):
        run(budget.complete(req("c")))
    assert budget.usage.calls == 2

    tokens = Budgeted(FakeProvider(lambda r: "x" * 40), max_tokens=10)
    run(tokens.complete(req("a")))
    with pytest.raises(BudgetExceeded):
        run(tokens.complete(req("b")))

    def fail(r):
        raise ProviderError("down")

    failing = Budgeted(FakeProvider(fail), max_calls=1)
    with pytest.raises(ProviderError):
        run(failing.complete(req()))
    assert failing.usage.failed_calls == 1
    with pytest.raises(BudgetExceeded):
        run(failing.complete(req()))


def test_budget_counts_in_flight_calls():
    budget = Budgeted(FakeProvider(lambda r: "x", latency_s=0.01), max_calls=2)

    async def burst():
        return await asyncio.gather(*(budget.complete(req(str(i))) for i in range(4)), return_exceptions=True)

    results = run(burst())
    assert sum(isinstance(r, BudgetExceeded) for r in results) == 2
    usage = budget.usage.to_dict()
    assert usage["calls"] == 2 and usage["by_model"]["m1"]["calls"] == 2
