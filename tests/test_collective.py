"""Behaviour probes; fake inference tests information flow, not model quality."""
import json
from backend.swarm_core import run_task, estimate_calls


def task():
    return dict(task_id='local-pieces', source_id='unit', dataset='pubmedqa', domain='medical',
                split='development', question='Do all three checks pass?',
                evidence=[{'id':f'e{i}', 'text':f'Check {i} passes.'} for i in range(3)],
                answer_type='choice', choices=['yes','no','maybe'], expected_answer='yes',
                tolerance='0', source_url='https://example.test')


def execute(protocol, bad=False):
    prompts=[]
    def infer(model, messages, **settings):
        view=json.loads(messages[-1]['content']); prompts.append(view)
        ids=[e['id'] for e in view['task']['evidence']]
        payload=dict(answer='yes' if len(ids)==3 else 'maybe', evidence_ids=ids,
                     brief='All available checks pass.')
        if bad and len(prompts)==1: payload['evidence_ids']=['e2']
        return dict(content=json.dumps(payload),response_id=str(len(prompts)),requested_model=model,
                    served_model=model,prompt_tokens=10,completion_tokens=10,elapsed_s=.1,finish_reason='stop')
    cells=run_task(task(),['m'],'%s'%protocol,dict(seed=19,temperature=0.,max_tokens=256),infer,lambda e:None,lambda:False,output_policy='constrained_short_v1')
    return cells[0],prompts


def test_collective_caps_shared_sources_even_without_constrained_decoding():
    value = dict(task(), evidence=[{'id':f'e{i}', 'text':'Public source'} for i in range(12)])
    def infer(model, messages, **settings):
        ids = [e['id'] for e in json.loads(messages[-1]['content'])['task']['evidence']]
        return dict(content=json.dumps(dict(answer='yes',evidence_ids=ids,brief='test')),
                    response_id='unit',requested_model=model,served_model=model,prompt_tokens=1,
                    completion_tokens=1,elapsed_s=.1,finish_reason='stop')
    cell = run_task(value,['m'],'evidence_exchange',dict(seed=0,temperature=0.,max_tokens=128),
                    infer,lambda e:None,lambda:False)[0]
    assert cell['status'] == 'invalid'
    assert all(not agent['received'] for agent in cell['cooperation']['agents'])


def test_empty_shard_schema_allows_only_empty_citations():
    from backend.swarm_core import build_response_format
    empty = dict(task(), evidence=[])
    schema = build_response_format(empty, kind='claim', output_policy='constrained_short_v1')
    assert schema['json_schema']['schema']['properties']['evidence_ids']['maxItems'] == 0
    assert schema['json_schema']['schema']['properties']['evidence_ids']['items'] == {'type':'string'}


def test_foreign_citation_is_not_transferred_or_counted_as_success():
    cell, prompts = execute('evidence_exchange', bad=True)
    assert cell['status'] == 'invalid' and cell['answer'] is None
    assert cell['messages'][0]['payload'] is None
    assert all(s['sender'] != 'm:worker-1' for p in prompts[3:] for s in p['signals'])


def test_sharing_transfers_selected_evidence_and_changes_group_answer():
    on,prompts=execute('evidence_exchange')
    off,off_prompts=execute('evidence_isolated')
    solo,solo_prompts=execute('solo_refine')
    assert on['answer']=='yes' and off['answer']=='maybe' and solo['answer']=='yes'
    assert [len(p['task']['evidence']) for p in prompts]==[1,1,1,3,3,3]
    assert all(len(p['task']['evidence'])==1 for p in off_prompts)
    assert all(len(p['task']['evidence'])==3 for p in solo_prompts)
    assert all('expected_answer' not in p['task'] for p in prompts+off_prompts+solo_prompts)
    assert len(prompts)==len(off_prompts)==len(solo_prompts)==6
    assert estimate_calls(1,1,['evidence_exchange','evidence_isolated','solo_refine'])==18
    assert on['cooperation']['agents'][0]['initial_answer']=='maybe'
    assert on['cooperation']['agents'][0]['final_answer']=='yes'
    assert len(on['cooperation']['agents'][0]['received'])==2
    for event in on['messages'][3:]:
        assert len(event['parent_ids'])==3
        assert event['response_format']['json_schema']['schema']['properties']['evidence_ids']['items']['enum']==['e0','e1','e2']
    assert all(not a['received'] for a in off['cooperation']['agents'])
