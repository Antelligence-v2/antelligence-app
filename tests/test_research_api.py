"""Real SQLite + worker lifecycle tests with explicitly fake unit inference only."""
import json
import threading
import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from backend.research_api import ResearchService, ResearchRequest, make_router
from backend.research_data import digest


class FakeModels:
    def catalog(self):
        return [{'key': 'qwen', 'availability': 'ready', 'model_id': 'unit-model', 'local': True}]
    def pin(self, keys):
        if keys != ['qwen']:
            raise RuntimeError('unavailable')
        return self.catalog()
    def infer(self, key, messages, **settings):
        return {'content': json.dumps({'answer':'yes','evidence_ids':[],'brief':'Unit fixture only'}), 'response_id':'unit', 'requested_model':'unit-model','served_model':'unit-model', 'prompt_tokens':10,'completion_tokens':5,'elapsed_s':.01,'finish_reason':'stop'}


class RecordingModels(FakeModels):
    def __init__(self):
        self.settings = []

    def infer(self, key, messages, **settings):
        self.settings.append(settings)
        return super().infer(key, messages, **settings)


def request(**kwargs):
    data = dict(name='unit run',model_keys=['qwen'],protocols=['single'],datasets=['pubmedqa'],split='development',tasks_per_dataset=2,temperature=.2,seed=17,max_tokens=64,target_accuracy=.8,max_calls=20,max_wall_seconds=30)
    data.update(kwargs)
    return data


def client_for(tmp_path, models=None):
    service = ResearchService(tmp_path / 'research.sqlite', models_factory=lambda: models or FakeModels())
    app = FastAPI()
    app.include_router(make_router(service))
    return TestClient(app),service


def wait_result(client, run_id):
    for _ in range(200):
        body = client.get('/research/runs/' + run_id).json()
        if body['status'] != 'running': return body
        time.sleep(.01)
    pytest.fail('unit worker did not finish')


def test_actual_persistence_and_restart_readback(tmp_path):
    client, service = client_for(tmp_path)
    response = client.post('/research/runs',json=request())
    assert response.status_code == 202, response.text
    body = wait_result(client,response.json()['run_id'])
    assert body['status'] == 'completed'
    assert body['actual_calls'] == 2 and len(body['events']) == 2 and len(body['cells']) == 2
    assert body['summary'][0]['gate'] == 'insufficient_evidence'
    assert body['proof_ok'] is False
    assert body['metered_api_cost_usd'] == 0
    again, _ = client_for(tmp_path)
    assert again.get('/research/runs/' + body['run_id']).json() == body
    assert again.get('/research/runs').json()['items'][0]['run_id'] == body['run_id']


def test_output_policy_defaults_to_prompt_only_and_catalog_exposes_both_policies(tmp_path):
    client, _ = client_for(tmp_path)
    assert ResearchRequest.model_validate(request()).output_policy == 'prompt_only'
    catalog = client.get('/research/catalog').json()
    assert [policy['id'] for policy in catalog['output_policies']] == ['prompt_only', 'constrained_short_v1']
    assert all(policy['label'] and policy['description'] for policy in catalog['output_policies'])


def test_constrained_policy_is_forwarded_and_persisted_per_event(tmp_path):
    models = RecordingModels()
    client, _ = client_for(tmp_path, models)
    response = client.post('/research/runs', json=request(output_policy='constrained_short_v1', tasks_per_dataset=1))
    assert response.status_code == 202, response.text
    body = wait_result(client, response.json()['run_id'])
    assert body['request']['output_policy'] == 'constrained_short_v1'
    assert body['cells'][0]['output_policy'] == 'constrained_short_v1'
    assert client.get('/research/runs').json()['items'][0]['output_policy'] == 'constrained_short_v1'
    event = body['events'][0]
    assert event['output_policy'] == 'constrained_short_v1'
    assert event['response_format']['type'] == 'json_schema'
    assert models.settings[0]['response_format'] == event['response_format']


def test_legacy_report_policy_display_does_not_rewrite_stored_bytes(tmp_path):
    client, service = client_for(tmp_path)
    response = client.post('/research/runs', json=request())
    body = wait_result(client, response.json()['run_id'])
    run_id = body['run_id']
    with service.store.connect() as con:
        row = con.execute('SELECT body FROM research_runs WHERE run_id=?', (run_id,)).fetchone()
        legacy = json.loads(row[0])
        legacy['request'].pop('output_policy', None)
        legacy['request_hash'] = digest(legacy['request'])
        for event in legacy['events']:
            event.pop('output_policy', None)
            event.pop('response_format', None)
        for cell in legacy['cells']:
            cell.pop('output_policy', None)
        con.execute('UPDATE research_runs SET body=? WHERE run_id=?', (json.dumps(legacy), run_id))
        before = con.execute('SELECT body FROM research_runs WHERE run_id=?', (run_id,)).fetchone()[0]
    displayed = client.get('/research/runs/' + run_id).json()
    assert displayed == legacy
    assert service.store.get(run_id) == legacy
    assert digest(displayed['request']) == displayed['request_hash']
    with service.store.connect() as con:
        after = con.execute('SELECT body FROM research_runs WHERE run_id=?', (run_id,)).fetchone()[0]
    assert before == after
    assert client.get('/research/runs').json()['items'][0]['output_policy'] == 'prompt_only'
    assert 'output_policy' not in displayed['request']
    assert 'output_policy' not in displayed['events'][0]
    assert 'response_format' not in displayed['events'][0]


@pytest.mark.parametrize('key,value',[('tasks_per_dataset',True),('seed','17'),('max_tokens',64.5),('temperature',float('inf')),('protocols',['made_up']),('model_keys',['http://elsewhere']),('model_keys',['qwen','qwen']),('output_policy','unsupported')])
def test_strict_request_rejection(key,value):
    payload = request();payload[key]=value
    with pytest.raises(ValueError): ResearchRequest.model_validate(payload)


def test_preflight_budget_and_unavailable_never_create_run(tmp_path):
    client, service = client_for(tmp_path)
    data = request();data.update(max_calls=1)
    assert client.post('/research/runs',json=data).status_code == 422
    data.update(max_calls=20, model_keys=['phi4'])
    assert client.post('/research/runs',json=data).status_code == 409
    assert client.get('/research/runs').json()['items'] == []


def test_cancel_and_conflicting_start_retains_unexecuted_denominator(tmp_path):
    entered, release = threading.Event(),threading.Event()
    class Blocking(FakeModels):
        def infer(self,*a,**kw):
            entered.set(); release.wait(5); return super().infer(*a,**kw)
    client,service = client_for(tmp_path,Blocking())
    response = client.post('/research/runs',json=request()); run_id=response.json()['run_id']
    assert entered.wait(2)
    assert client.post('/research/runs',json=request()).status_code == 409
    assert client.post('/research/runs/'+run_id+'/cancel').json()['cancel_requested'] is True
    release.set()
    body=wait_result(client,run_id)
    assert body['status'] == 'interrupted' and body['actual_calls'] == 1
    assert len(body['cells']) == 2 and body['summary'][0]['task_count'] == 2
    assert body['summary'][0]['gate'] == 'unknown'


def test_partial_round_checkpoints_preserve_real_usage_and_shared_lock(tmp_path):
    second,release=threading.Event(),threading.Event()
    class Partial(FakeModels):
        calls=0
        def infer(self,*a,**kw):
            self.calls+=1
            if self.calls==2: second.set();release.wait(5)
            return super().infer(*a,**kw)
    client,service=client_for(tmp_path,Partial())
    payload=request();payload.update(protocols=['independent_vote'],tasks_per_dataset=1)
    started=client.post('/research/runs',json=payload).json();run_id=started['run_id']
    assert second.wait(2)
    other,_=client_for(tmp_path)
    running=other.get('/research/runs/'+run_id).json()
    assert running['status']=='running' and running['actual_calls']==2
    assert len(running['events'])==1
    assert running['summary'][0]['prompt_tokens']==10
    assert running['summary'][0]['usage_complete'] is False
    assert other.post('/research/runs',json=payload).status_code==409
    release.set();assert wait_result(client,run_id)['status']=='completed'


def test_orphan_restart_is_interrupted_not_replayed(tmp_path):
    client,service=client_for(tmp_path)
    run_id=client.post('/research/runs',json=request()).json()['run_id']
    body=wait_result(client,run_id)
    service.thread.join(2)
    body.update(status='running')
    service.store.save(body)
    again,_=client_for(tmp_path)
    recovered=again.get('/research/runs/'+run_id).json()
    assert recovered['status']=='interrupted'
    assert recovered['events']==body['events'] and recovered['actual_calls']==body['actual_calls']
    assert recovered['errors']


def test_foreign_origin_and_unknown_uuid(tmp_path):
    client,_=client_for(tmp_path)
    assert client.post('/research/runs',json=request(),headers={'Origin':'https://evil.invalid'}).status_code == 403
    assert client.get('/research/runs/not-a-uuid').status_code == 422
    assert client.get('/research/runs/00000000-0000-0000-0000-000000000001').status_code == 404
