"""No credential lookup, cloud proxies, redirects or completion cache in research."""
import pytest
from backend.research_models import LocalModels, ResearchProviderError


def test_unknown_model_is_rejected_before_any_http():
    client = LocalModels()
    with pytest.raises(ValueError):
        client.infer('cloud', [], max_tokens=64, temperature=.2, seed=17)


def test_redirects_and_identity_fail_closed(monkeypatch):
    client = LocalModels()
    monkeypatch.setattr(client, '_json', lambda *a, **k: {'model': 'wrong', 'id': 'x', 'usage': {'prompt_tokens': 10,'completion_tokens': 20}, 'choices': [{'finish_reason': 'stop', 'message': {'content': 'real returned content'}}]})
    with pytest.raises(ResearchProviderError) as error:
        client.infer('qwen', [], max_tokens=64, temperature=.2, seed=17)
    assert error.value.result['served_model'] == 'wrong'
    assert error.value.result['content'] == 'real returned content'
    assert error.value.result['completion_tokens'] == 20


def test_request_is_explicit_no_fallback_and_no_reasoning_export(monkeypatch):
    seen = []
    client = LocalModels()
    def http(url, payload=None, **kwargs):
        seen.append((url,payload))
        return {'model': 'qwen38-abliterated','id':'real','usage':{'prompt_tokens':10,'completion_tokens':2},'choices':[{'finish_reason':'stop','message':{'content':'{}','reasoning_content':'PRIVATE'}}]}
    monkeypatch.setattr(client, '_json', http)
    result = client.infer('qwen', [], max_tokens=64, temperature=.2, seed=17)
    assert len(seen) == 1
    assert seen[0][0] == 'http://127.0.0.1:8301/v1/chat/completions'
    payload = seen[0][1]
    assert payload['stream'] is False and payload['cache_prompt'] is False
    assert payload['max_tokens'] == 64 and payload['seed'] == 17 and payload['temperature'] == .2
    assert 'PRIVATE' not in str(result)


def test_constrained_response_format_is_forwarded_without_changing_generation_settings(monkeypatch):
    seen = []
    client = LocalModels()
    response_format = {
        'type': 'json_schema',
        'json_schema': {
            'name': 'swarm_reply',
            'strict': True,
            'schema': {'type': 'object', 'additionalProperties': False},
        },
    }

    def http(url, payload=None, **kwargs):
        seen.append((url, payload))
        return {
            'model': 'qwen38-abliterated',
            'id': 'real',
            'usage': {'prompt_tokens': 10, 'completion_tokens': 2},
            'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}],
        }

    monkeypatch.setattr(client, '_json', http)
    client.infer('qwen', [], max_tokens=64, temperature=.2, seed=17, response_format=response_format)

    payload = seen[0][1]
    assert payload['response_format'] == response_format
    assert payload['max_tokens'] == 64 and payload['temperature'] == .2 and payload['seed'] == 17


def test_provider_refusing_constrained_response_format_is_not_retried_or_downgraded(monkeypatch):
    seen = []
    client = LocalModels()
    response_format = {'type': 'json_schema', 'json_schema': {'name': 'swarm_reply', 'strict': True, 'schema': {}}}

    def refusing(url, payload=None, **kwargs):
        seen.append(payload)
        raise RuntimeError('unsupported response_format')

    monkeypatch.setattr(client, '_json', refusing)
    with pytest.raises(RuntimeError, match='unsupported response_format'):
        client.infer('qwen', [], max_tokens=64, temperature=.2, seed=17, response_format=response_format)
    assert len(seen) == 1
    assert seen[0]['response_format'] == response_format


def test_truncation_retains_actual_usage(monkeypatch):
    client = LocalModels()
    monkeypatch.setattr(client, '_json', lambda *a, **k: {'model': 'qwen38-abliterated', 'id': 'x', 'usage': {'prompt_tokens': 10,'completion_tokens': 64}, 'choices': [{'finish_reason': 'length', 'message': {'content': '{'}}]})
    with pytest.raises(ResearchProviderError) as error:
        client.infer('qwen', [], max_tokens=64, temperature=.2, seed=17)
    assert error.value.result['finish_reason'] == 'length'
    assert error.value.result['completion_tokens'] == 64


def test_constrained_truncation_still_fails_closed_with_public_usage(monkeypatch):
    client = LocalModels()
    response_format = {'type': 'json_schema', 'json_schema': {'name': 'swarm_reply', 'strict': True, 'schema': {}}}
    monkeypatch.setattr(client, '_json', lambda *a, **k: {'model': 'qwen38-abliterated', 'id': 'x', 'usage': {'prompt_tokens': 10,'completion_tokens': 64}, 'choices': [{'finish_reason': 'length', 'message': {'content': '{'}}]})
    with pytest.raises(ResearchProviderError) as error:
        client.infer('qwen', [], max_tokens=64, temperature=.2, seed=17, response_format=response_format)
    assert error.value.result['finish_reason'] == 'length'
    assert error.value.result['content'] == '{'
    assert error.value.result['completion_tokens'] == 64
