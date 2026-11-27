import asyncio
import json

import httpx
import pytest

from antelligence.providers import (
    Budgeted, ChatRequest, ChatResponse, OpenAICompatProvider, ProviderError, ProviderTruncated,
    ProviderUnavailable, RetryPolicy, Retrying, SqliteCache,
)
from antelligence.providers.cache import UnsafeCachePath, base_request_hash, import_legacy_jsonl
from antelligence.providers.local_mlx import LocalModelError, LocalModelManager, free_memory_fraction


def req(content="hi", model="m1", **kw):
    return ChatRequest(model=model, messages=({"role": "user", "content": content},), **kw)


def reply(finish="stop", status=200, completion=3):
    body = {"id": "r", "model": "m1", "choices": [{"message": {"content": "x"}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 5, "completion_tokens": completion}}
    return httpx.Response(status, json=body)


def run(coro):
    return asyncio.run(coro)


class Scripted:
    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    def describe(self):
        return {"provider": "scripted"}

    async def complete(self, request):
        self.calls += 1
        out = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(out, Exception):
            raise out
        return ChatResponse(content="c", model=request.model, request_hash=request.request_hash, prompt_tokens=2,
                            completion_tokens=1, finish_reason="stop", extra=dict(out))


def test_request_hash_unchanged_without_extra_body_and_changes_with_it():
    assert "extra_body" not in req().payload()
    assert req().request_hash == req(extra_body=None).request_hash == req(extra_body={}).request_hash
    assert req(extra_body={"logprobs": True}).request_hash != req().request_hash


def test_pooled_client_is_reused_across_calls():
    p = OpenAICompatProvider("http://local.test/v1", transport=httpx.MockTransport(lambda r: reply()))

    async def go():
        await p.complete(req("a"))
        first = p._client
        await p.complete(req("b"))
        assert p._client is first
        await p.aclose()

    run(go())


def test_http_status_classification():
    for status in (401, 429, 503):
        p = OpenAICompatProvider("http://local.test/v1", transport=httpx.MockTransport(lambda r, s=status: reply(status=s)))
        with pytest.raises(ProviderUnavailable):
            run(p.complete(req()))
    p = OpenAICompatProvider("http://local.test/v1", transport=httpx.MockTransport(lambda r: reply(status=400)))
    with pytest.raises(ProviderError) as e:
        run(p.complete(req()))
    assert not isinstance(e.value, ProviderUnavailable)


def test_truncation_is_billed_stored_and_flagged(tmp_path):
    p = OpenAICompatProvider("http://local.test/v1", transport=httpx.MockTransport(lambda r: reply("length", completion=256)))
    cache = SqliteCache(p, tmp_path / "c.db")
    budget = Budgeted(cache)
    with pytest.raises(ProviderTruncated):
        run(budget.complete(req()))
    assert budget.usage.completion_tokens == 256 and budget.usage.calls == 1 and budget.usage.failed_calls == 0
    with pytest.raises(ProviderTruncated) as e:           # second time comes from the cache, still billed, no new call
        run(budget.complete(req()))
    assert e.value.response.extra["format_ok"] is False and e.value.response.cached
    assert len(cache) == 0                                 # never usable


def test_provider_error_is_never_cached(tmp_path):
    inner = Scripted(ProviderError("bad"), {})
    cache = SqliteCache(inner, tmp_path / "c.db")
    with pytest.raises(ProviderError):
        run(cache.complete(req()))
    assert len(cache) == 0
    assert run(cache.complete(req())).content == "c" and inner.calls == 2


def test_superset_matching_does_not_corrupt_older_rows(tmp_path):
    inner = Scripted({}, {"logprobs": {"conf": 0.9}})
    plain = SqliteCache(inner, tmp_path / "c.db")
    first = run(plain.complete(req()))
    assert run(plain.complete(req())).cached and inner.calls == 1
    wants = SqliteCache(inner, tmp_path / "c.db", required_telemetry={"logprobs"})
    second = run(wants.complete(req()))                    # superset needed: miss, new immutable row
    assert inner.calls == 2 and second.extra["logprobs"]
    assert run(wants.complete(req())).cached and inner.calls == 2
    assert run(plain.complete(req())).extra == first.extra  # plain lookup still sees the old row first
    rows = plain._db.execute("SELECT COUNT(*) FROM responses").fetchone()[0]
    assert rows == 2


def test_superset_lookup_strips_telemetry_extra_body_keys(tmp_path):
    inner = Scripted({"logprobs": {"conf": 0.9}, "usage": {"total_tokens": 3}})
    cache = SqliteCache(inner, tmp_path / "c.db")

    req_plain = req(extra_body={})
    req_lp = req(extra_body={"logprobs": True})
    req_full = req(extra_body={"logprobs": True, "top_logprobs": 5, "stream_options": {"include_usage": True}})
    req_other = req(extra_body={"thinking": {"type": "disabled"}})

    # ChatRequest.request_hash stays sensitive to extra_body; SqliteCache base key strips telemetry-only keys.
    assert req_lp.request_hash != req_plain.request_hash
    assert base_request_hash(req_plain) == base_request_hash(req_lp) == base_request_hash(req_full)
    assert base_request_hash(req_other) != base_request_hash(req_plain)

    # Seed a cached row with telemetry_flags={"logprobs", "usage"} via a telemetry-bearing ChatRequest.
    seeded = run(cache.complete(req_full))
    assert not seeded.cached and inner.calls == 1
    stored_flags = json.loads(cache._db.execute("SELECT telemetry FROM responses").fetchone()[0])
    assert set(stored_flags) == {"logprobs", "usage"}

    # Hit by ChatRequest(extra_body={}) AND by ChatRequest(extra_body={"logprobs": True}).
    hit_plain = run(cache.complete(req_plain))
    assert hit_plain.cached and hit_plain.content == seeded.content and inner.calls == 1
    hit_lp = run(cache.complete(req_lp))
    assert hit_lp.cached and hit_lp.extra["logprobs"] == {"conf": 0.9} and inner.calls == 1
    assert cache.lookup(req_plain) is not None and cache.lookup(req_lp) is not None


def test_empty_telemetry_row_misses_request_extra_body_logprobs_without_corrupting(tmp_path):
    class DistinctContentProvider:
        def __init__(self):
            self.calls = 0

        def describe(self):
            return {"provider": "distinct"}

        async def complete(self, request):
            self.calls += 1
            if (request.extra_body or {}).get("logprobs"):
                return ChatResponse(content="lp-content", model=request.model, request_hash=request.request_hash,
                                    prompt_tokens=2, completion_tokens=1, finish_reason="stop",
                                    extra={"logprobs": {"conf": 0.95}})
            return ChatResponse(content="plain-content", model=request.model, request_hash=request.request_hash,
                                prompt_tokens=2, completion_tokens=1, finish_reason="stop", extra={})

    inner = DistinctContentProvider()
    cache = SqliteCache(inner, tmp_path / "c.db")

    # Seed a cached row with telemetry_flags=set().
    first = run(cache.complete(req(extra_body={})))
    assert not first.cached and first.content == "plain-content" and inner.calls == 1
    assert cache.lookup(req(extra_body={"logprobs": True})) is None

    # Lookup with extra_body={"logprobs": True} misses cleanly, inserts a new row, and keeps old content intact.
    second = run(cache.complete(req(extra_body={"logprobs": True})))
    assert not second.cached and second.content == "lp-content" and second.extra["logprobs"] == {"conf": 0.95}
    assert inner.calls == 2

    # Subsequent calls hit their respective rows without extra provider calls.
    hit_lp = run(cache.complete(req(extra_body={"logprobs": True})))
    assert hit_lp.cached and hit_lp.content == "lp-content" and inner.calls == 2
    hit_plain = run(cache.complete(req(extra_body={})))
    assert hit_plain.cached and hit_plain.content == "plain-content" and hit_plain.extra == {} and inner.calls == 2
    assert len(cache) == 1
    assert cache._db.execute("SELECT COUNT(*) FROM responses").fetchone()[0] == 2


def test_provider_level_extra_body_requires_telemetry(tmp_path):
    lp_payload = {"content": [{"token": "A", "logprob": -0.1, "top_logprobs": [{"token": "A", "logprob": -0.1}]}]}
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        body = {"id": "r", "model": "m1",
                "choices": [{"message": {"content": "x"}, "finish_reason": "stop", "logprobs": lp_payload}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3}}
        return httpx.Response(200, json=body)

    db = tmp_path / "c.db"
    # Seed plain row (telemetry_flags=set()).
    plain_cache = SqliteCache(Scripted({}), db)
    run(plain_cache.complete(req()))

    # Provider-level extra_body={"logprobs": True} (even behind Retrying) must require "logprobs" and miss plain row.
    prov = OpenAICompatProvider("http://local.test/v1", extra_body={"logprobs": True},
                                transport=httpx.MockTransport(handler))
    lp_cache = SqliteCache(Retrying(prov), db)
    assert lp_cache.required_for(req()) == frozenset({"logprobs"})
    assert lp_cache.lookup(req()) is None

    res = run(lp_cache.complete(req()))
    assert not res.cached and res.extra["logprobs"] and len(calls) == 1
    # Now cached: hits for both provider-level and request-level logprobs requests, and plain lookup stays intact.
    assert run(lp_cache.complete(req())).cached and len(calls) == 1
    assert run(lp_cache.complete(req(extra_body={"logprobs": True}))).cached and len(calls) == 1
    assert lp_cache.required_for(req(extra_body={"logprobs": False})) == frozenset()


def test_concurrent_identical_requests_hit_model_once(tmp_path):
    inner = Scripted({})
    cache = SqliteCache(inner, tmp_path / "c.db")

    async def go():
        await asyncio.gather(*(cache.complete(req()) for _ in range(5)))

    run(go())
    assert inner.calls == 1


def test_external_volume_is_refused(tmp_path):
    with pytest.raises(UnsafeCachePath):
        SqliteCache(None, "/Volumes/WD_BLACK/cache.db")
    assert SqliteCache(None, tmp_path / "ok.db", offline=True).path.exists()


def test_import_legacy_jsonl_is_free_and_idempotent(tmp_path):
    good = {"request_hash": "h1", "model": "m1", "content": "a", "prompt_tokens": 1, "completion_tokens": 1,
            "finish_reason": "stop", "extra": {}}
    bad = {**good, "request_hash": "h2", "finish_reason": "length"}
    src = tmp_path / "legacy.jsonl"
    src.write_text("\n".join(json.dumps(r) for r in (good, bad, good)) + "\n")
    cache = SqliteCache(None, tmp_path / "c.db", offline=True)
    assert import_legacy_jsonl(cache, src) == {"imported": 1, "skipped_duplicate": 1, "skipped_unusable": 1}
    assert cache.lookup("h1")["content"] == "a"


def test_retry_waits_out_outage_then_gives_up():
    slept = []

    async def sleep(s):
        slept.append(s)

    t = [0.0]

    async def tick(s):
        slept.append(s)
        t[0] += s

    inner = Scripted(ProviderUnavailable("down"), ProviderUnavailable("down"), {})
    r = Retrying(inner, RetryPolicy(sleep=tick, clock=lambda: t[0]))
    assert run(r.complete(req())).content == "c" and slept == [15.0, 30.0]
    dead = Retrying(Scripted(ProviderUnavailable("down")), RetryPolicy(max_wait_s=40, sleep=tick, clock=lambda: t[0]))
    with pytest.raises(ProviderUnavailable):
        run(dead.complete(req()))
    other = Retrying(Scripted(ProviderError("bad")))
    with pytest.raises(ProviderError):
        run(other.complete(req()))
    assert other.policy.retries == 0


class FakeProc:
    def __init__(self):
        self.alive, self.terminated = True, False

    def poll(self):
        return None if self.alive else 0

    def terminate(self):
        self.alive, self.terminated = False, True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.alive = False


def test_local_model_manager_switches_and_guards_memory():
    procs, cmds = [], []

    def popen(cmd):
        cmds.append(cmd)
        procs.append(FakeProc())
        return procs[-1]

    m = LocalModelManager(popen=popen, probe=lambda url: True, memory=lambda: 0.5, sleep=lambda s: None)
    assert m.ensure("a") == m.base_url and m.ensure("a") and len(procs) == 1
    m.ensure("b")
    assert procs[0].terminated and len(procs) == 2 and "b" in cmds[1]
    m.stop()
    assert procs[1].terminated
    low = LocalModelManager(popen=popen, probe=lambda url: True, memory=lambda: 0.05)
    with pytest.raises(LocalModelError, match="memory pressure"):
        low.ensure("c")
    assert len(procs) == 2


def test_memory_probe_parses_memory_pressure_and_vm_stat():
    assert free_memory_fraction(lambda *c: "System-wide memory free percentage: 42%") == 0.42
    vm = "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free:  100.\nPages inactive:  100.\nPages active:  800.\n"

    def fake(*c):
        if c[0] == "memory_pressure":
            raise OSError
        return vm

    assert free_memory_fraction(fake) == 0.2
