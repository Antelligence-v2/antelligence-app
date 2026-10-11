import asyncio
import json

from antelligence.kernel.policies import StateChatPolicy
from antelligence.kernel.types import NOOP, LocalView
from antelligence.providers.base import ProviderError
from antelligence.providers.wrappers import FakeProvider
from tests.engine.hive_helpers import ACTIONS, ChoiceSensor, ChoiceWorld, run


def view(seed=100):
    return LocalView("w0", 3, 0, seed, {"tick": 3})


def policy(responder):
    provider = FakeProvider(responder)
    return StateChatPolicy(provider, "m", ChoiceSensor()), provider


def go(p, v):
    return asyncio.run(p.decide(v))


def test_valid_answer_acts():
    p, _ = policy(lambda r: json.dumps({"action": "b"}))
    intent = go(p, view())
    assert intent.action == "b" and intent.meta["answer"] == "b" and "request_hash" in intent.meta


def test_prompt_has_state_and_all_actions_but_no_report_or_checks():
    p, provider = policy(lambda r: '{"action": "a"}')
    go(p, view())
    req = provider.requests[0]
    text = req.messages[1]["content"]
    assert "It is step 3" in text and all(f"- {a}:" in text for a in ACTIONS)
    assert "report" not in text.lower().replace("reply with json", "") and "plan" not in text
    assert req.max_tokens == 64 and req.temperature == 0


def test_options_shuffled_by_seed_and_reproducible():
    p, provider = policy(lambda r: '{"action": "a"}')
    orders = set()
    for seed in range(100, 130):
        go(p, view(seed))
        lines = provider.requests[-1].messages[1]["content"].splitlines()
        orders.add(tuple(line for line in lines if line.startswith("- ")))
    assert len(orders) > 1
    assert p.request(view(105)).request_hash == p.request(view(105)).request_hash


def test_off_list_unparsable_and_provider_error_are_noop_with_reason():
    for content, reason in [('{"action": "report"}', "action_not_offered"), ('{"action": "zzz"}', "action_not_offered"),
                            ("not json", "reply_not_json"), ('["a"]', "action_not_offered"), ('{"x": 1}',
                                "action_not_offered")]:
        p, _ = policy(lambda r, c=content: c)
        intent = go(p, view())
        assert intent.action == NOOP and intent.meta["reason"] == reason

    def boom(r):
        raise ProviderError("no")

    intent = go(policy(boom)[0], view())
    assert intent.action == NOOP and intent.meta["reason"].startswith("provider:ProviderError")


def test_fenced_reply_and_never_off_list_over_many_seeds():
    p, _ = policy(lambda r: '```json\n{"action": "c"}\n```')
    assert go(p, view()).action == "c"
    p2, _ = policy(lambda r: json.dumps({"action": "a"}))
    assert {go(p2, view(s)).action for s in range(100, 120)} <= set(ACTIONS)


def test_runs_in_scheduler_deterministically():
    def once():
        p, _ = policy(lambda r: '{"action": "a"}')
        return run(ChoiceWorld(n=3), {a: p for a in ChoiceWorld(n=3).agents()}, ticks=3, queen=False).log.trace_hash

    assert once() == once()
