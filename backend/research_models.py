"""Pinned local-only inference adapter. Nothing here loads credentials or falls back."""
from __future__ import annotations
import json
import hashlib
import time
import urllib.request
from pathlib import Path
from backend.research_data import digest

MODELS = {
    'qwen': {'key': 'qwen', 'label': 'Qwen3.8 27B abliterated Q3_K (local)', 'model_id': 'qwen38-abliterated',
             'endpoint': 'http://127.0.0.1:8301', 'path': '/Volumes/WD_BLACK/models/Qwen3.8-27B-abliterated-GGUF/Huihui-Qwen3.8-27B-abliterated-Q3_K.gguf',
             'provenance': 'Existing resident llama.cpp GGUF; fine-tuning/data exposure unverified.'},
    'phi4': {'key': 'phi4', 'label': 'Phi4 mini finance F16 (local experimental fine-tune)', 'model_id': 'antelligence-phi4-finance',
             'endpoint': 'http://127.0.0.1:18302', 'path': '/Volumes/WD_BLACK/models/phi4-mini-finance-f16.gguf',
             'provenance': 'Existing local finance fine-tune; training provenance and benchmark contamination unknown.'},
}
OPTIONS = {'stream': False, 'cache_prompt': False, 'top_k': 0, 'top_p': 1.0, 'min_p': 0.0,
           'repeat_penalty': 1.0, 'chat_template_kwargs': {'enable_thinking': False}}


class ResearchProviderError(RuntimeError):
    def __init__(self, message, result=None):
        super().__init__(message)
        self.result = result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ResearchProviderError('Local research endpoint redirect refused')


class LocalModels:
    def __init__(self):
        # No environment proxies; a localhost alias is not permission to reach a cloud proxy.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        self.pinned = {}
        self.timeout = 120.0

    def _json(self, url, payload=None, timeout: float=5):
        if not any(url.startswith(m['endpoint'] + '/') for m in MODELS.values()):
            raise ValueError('Endpoint not allowlisted')
        request = urllib.request.Request(url, data=None if payload is None else json.dumps(payload, allow_nan=False).encode(),
                                         headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        with self.opener.open(request, timeout=timeout) as response:
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ResearchProviderError('Provider response exceeds size limit')
            return json.loads(data)

    def catalog(self):
        rows = []
        for model in MODELS.values():
            row: dict = {k:v for k,v in model.items() if k != 'path'}
            row.update(local=True, availability='unknown', reason='Not checked', inference_options=OPTIONS)
            try:
                info = self._json(model['endpoint'] + '/v1/models')
                found = next(x for x in info['data'] if x['id'] == model['model_id'] and x['owned_by'] == 'llamacpp')
                props = self._json(model['endpoint'] + '/props')
                if props.get('model_path') != model['path'] or props.get('model_alias') != model['model_id']:
                    raise ValueError('Model file/alias differs from pinned local roster')
                if not Path(model['path']).is_file():
                    raise ValueError('Expected local weight file absent')
                snapshot = {'model_id': found['id'], 'meta': found.get('meta'), 'model_path': props['model_path'],
                            'build_info': props.get('build_info'), 'chat_template_hash': digest(props.get('chat_template')),
                            'file_bytes': Path(model['path']).stat().st_size}
                row.update(availability='ready', reason='Local model identity checked; availability is not a quality score.',
                           server_snapshot=snapshot, server_hash=digest(snapshot))
            except Exception as exc:
                row['reason'] = f'Local identity/readiness unknown: {type(exc).__name__}: {exc}'
            rows.append(row)
        return rows

    def pin(self, model_keys):
        rows = {r['key']: r for r in self.catalog()}
        selected = []
        for key in model_keys:
            if key not in rows or rows[key]['availability'] != 'ready':
                raise ResearchProviderError(f'Local model unavailable or identity unknown: {key}')
            # Full weight digest at run admission (not every catalog GET).
            h=hashlib.sha256()
            with Path(MODELS[key]['path']).open('rb') as source:
                while block:=source.read(8*1024*1024): h.update(block)
            rows[key]['observed_weight_sha256']=h.hexdigest()
            rows[key]['weight_binding']='Local file observation; not attestation of server memory or training data.'
            self.pinned[key] = rows[key]
            selected.append(rows[key])
        return selected

    def infer(self, model_key, messages, *, max_tokens, temperature, seed):
        if model_key not in MODELS:
            raise ValueError('Unknown research model')
        model = MODELS[model_key]
        payload = dict(OPTIONS, model=model['model_id'], messages=messages, max_tokens=max_tokens,
                       temperature=temperature, seed=seed)
        start = time.monotonic()
        response = self._json(model['endpoint'] + '/v1/chat/completions', payload, timeout=self.timeout)
        choice = response.get('choices', [{}])[0]
        usage = response.get('usage', {})
        result = dict(content=choice.get('message', {}).get('content'), response_id=response.get('id'),
                      requested_model=model['model_id'], served_model=response.get('model'),
                      prompt_tokens=usage.get('prompt_tokens'), completion_tokens=usage.get('completion_tokens'),
                      elapsed_s=time.monotonic() - start, finish_reason=choice.get('finish_reason'),
                      wire_request_hash=digest(payload), system_fingerprint=response.get('system_fingerprint'))
        if result['served_model'] != model['model_id']:
            raise ResearchProviderError('Served model identity mismatch', result)
        pinned = self.pinned.get(model_key)
        if pinned and response.get('system_fingerprint') != pinned['server_snapshot']['build_info']:
            raise ResearchProviderError('Server build fingerprint changed during run', result)
        if result['finish_reason'] != 'stop':
            raise ResearchProviderError('Model response truncated or did not finish normally', result)
        if not isinstance(result['content'], str) or not result['response_id']:
            raise ResearchProviderError('Missing public model content/response identity', result)
        if any(type(result[k]) is not int or result[k] < 0 for k in ('prompt_tokens','completion_tokens')):
            raise ResearchProviderError('Provider token usage missing or invalid', result)
        return result
