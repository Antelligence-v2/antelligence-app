import asyncio
import json

import httpx
import pytest

from antelligence.providers import (ChatRequest, FakeProvider, LedgeredChat, LedgerWriter, OpenAICompatProvider,
                                    ProviderError, ledger_context)
from antelligence.providers.base import ChatResponse
from antelligence.providers.ledger import PRICES, ROW_FIELDS, cost_usd, price_for

NOUS = "deepseek/deepseek-v4.1-flash"


def req(text="hi", model=NOUS):
    return ChatRequest(model, ({"role": "user", "content": text},), max_tokens=300)


def test_cost_math_matches_brief_prices():
    # 1M input tokens at $0.106 plus 1M output at $0.513
    assert cost_usd(1_000_000, 1_000_000, price_for(NOUS)) == pytest.approx(0.619)
    assert cost_usd(405, 73, price_for("jev-1.13.0")) == pytest.approx(405 * 0.042 / 1e6)
    assert cost_usd(10_000, 50, price_for("convaiinnovations/laya-typed-decisions")) == 0.0
    assert PRICES["jev-1.13.0"][1] == 0.0
    with pytest.raises(KeyError):
        price_for("mystery-model")


def test_context_nests_and_rejects_unknown_tags(tmp_path):
    writer = LedgerWriter(tmp_path / "l.jsonl")
    with ledger_context(run="r1", arm="S", world="foraging", seed=100, condition="base"):
        with ledger_context(arm="Q-all"):
            writer.write(role="queen", backend="nous", model="m", served_model="m", request_hash="h")
        writer.write(role="worker", backend="jev", model="m", served_model="m", request_hash="h2")
    writer.write(role="worker", backend="jev", model="m", served_model="m", request_hash="h3")
    a, b, c = writer.rows()
    assert (a["arm"], b["arm"], c["arm"]) == ("Q-all", "S", None)
    assert a["run"] == "r1" and a["seed"] == 100 and c["run"] is None
    assert set(a) == set(ROW_FIELDS)
    with pytest.raises(ValueError):
        with ledger_context(bogus=1):
            pass
    with pytest.raises(ValueError):
        writer.write(role="boss", backend="x", model="m", served_model="m", request_hash="h")


def test_error_rows_are_redacted(tmp_path):
    writer = LedgerWriter(tmp_path / "l.jsonl", redact=["sk-SECRET"])
    writer.write(role="worker", backend="jev", model="m", served_model=None, request_hash="h",
                 error="HTTP 400 echo sk-SECRET")
    assert "sk-SECRET" not in (tmp_path / "l.jsonl").read_text()
    assert writer.rows()[0]["error"] == "HTTP 400 echo ***"


def chat(writer, content="ok", model=NOUS, extra=None, **kw):
    def responder(r):
        return ChatResponse(content, model, r.request_hash, 1000, 100, "stop", elapsed_s=0.5, extra=extra or {})
    return LedgeredChat(FakeProvider(responder, model=model), writer, role="queen", expected_model=NOUS, **kw)


def test_ledgered_chat_one_row_per_call_with_cost(tmp_path):
    writer = LedgerWriter(tmp_path / "l.jsonl")
    provider = chat(writer)
    with ledger_context(run="r", arm="queen"):
        asyncio.run(provider.complete(req("a")))
        asyncio.run(provider.complete(req("b")))
    rows = writer.rows()
    assert len(rows) == 2 and rows[0]["role"] == "queen" and rows[0]["arm"] == "queen"
    assert rows[0]["input_tokens"] == 1000 and rows[0]["output_tokens"] == 100
    assert rows[0]["cost_usd"] == pytest.approx(1000 * 0.106 / 1e6 + 100 * 0.513 / 1e6)
    assert rows[0]["served_model"] == NOUS and "error" not in rows[0]


def test_provider_reported_cost_wins(tmp_path):
    writer = LedgerWriter(tmp_path / "l.jsonl")
    asyncio.run(chat(writer, extra={"cost": 0.5}).complete(req()))
    assert writer.rows()[0]["cost_usd"] == 0.5


def test_served_model_mismatch_logged_and_rejected(tmp_path):
    writer = LedgerWriter(tmp_path / "l.jsonl")
    with pytest.raises(ProviderError):
        asyncio.run(chat(writer, model="deepseek/other").complete(req()))
    assert writer.rows()[0]["error"] == "served model identity mismatch"
    # prefix mode accepts a version suffix
    asyncio.run(chat(writer, model=NOUS + "-0101", prefix=True).complete(req()))
    assert "error" not in writer.rows()[1]


def test_provider_failure_writes_error_row(tmp_path):
    def boom(r):
        raise ProviderError("HTTP 500")
    writer = LedgerWriter(tmp_path / "l.jsonl")
    wrapped = LedgeredChat(FakeProvider(boom), writer, role="every_agent", expected_model=NOUS)
    with pytest.raises(ProviderError):
        asyncio.run(wrapped.complete(req()))
    row = writer.rows()[0]
    assert row["role"] == "every_agent" and "ProviderError" in row["error"] and row["served_model"] is None


def test_openai_compat_passes_usage_cost_through():
    def handler(request):
        body = {"model": NOUS, "choices": [{"message": {"content": "x"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "cost": 0.0123}}
        return httpx.Response(200, json=body)
    provider = OpenAICompatProvider("http://x/v1", transport=httpx.MockTransport(handler))
    assert asyncio.run(provider.complete(req())).extra["cost"] == 0.0123

    def no_cost(request):
        return httpx.Response(200, json={"model": NOUS, "choices": [{"message": {"content": "x"},
                                                                       "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 5, "completion_tokens": 2}})
    provider = OpenAICompatProvider("http://x/v1", transport=httpx.MockTransport(no_cost))
    assert "cost" not in asyncio.run(provider.complete(req())).extra


def test_ledger_file_is_valid_jsonl(tmp_path):
    writer = LedgerWriter(tmp_path / "sub" / "l.jsonl")
    writer.write(role="worker", backend="laya", model="m", served_model="s", request_hash="h", cost_usd=0.25)
    assert json.loads((tmp_path / "sub" / "l.jsonl").read_text().strip())["cost_usd"] == 0.25
    assert writer.total_cost() == 0.25
