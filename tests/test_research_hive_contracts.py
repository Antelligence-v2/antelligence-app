"""Executable C0 shared-contract tests; model-free and fail-closed."""
import json
import pytest

from backend.research_hive_contracts import (
    CONTRACT_VERSION,
    ContractError,
    adapt_coldroom,
    consume_coldroom_bytes,
    deserialize_envelope,
    serialize_envelope,
    validate_envelope,
    validate_trusted_envelope,
    deserialize_trusted_envelope,
    serialize_trusted_envelope,
    validate_event_stream,
    _event_id,
)


def test_coldroom_adapter_crosses_bytes_and_hides_private_state():
    task = {
        'task_id': 'coldroom-development-11-r0', 'protocol': 'inert-coldroom-v1',
        'revision': 0, 'max_actions': 8,
        'sample_kinds': {'vial-opaque-a': 'amber'},
        'slot_zones': {'locker-opaque-0': 0}, 'rules': {'amber': 0, 'teal': 1, 'violet': 2},
    }
    produced = adapt_coldroom(task, adapter_key=b'evaluator-key-strong')
    raw = serialize_envelope('task-public', produced['task_public'])
    assert isinstance(raw, bytes)
    assert b'"rules"' not in raw and b'coldroom-development-11-r0' not in raw and b'vial-11-' not in raw and b'locker-11-' not in raw
    consumed = consume_coldroom_bytes(raw)
    assert consumed['task_id'].startswith('worker-task-')
    assert consumed['scope'] == {'protocol': 'inert-coldroom-v1', 'revision': 0}
    assert consumed['private_metadata_leaked'] is False


def test_envelopes_are_versioned_exact_and_null_is_explicit():
    envelope = {
        'version': CONTRACT_VERSION, 'kind': 'evidence-reference',
        'event_id': 'evt-0001', 'ordinal': 0,
        'scope': {'protocol': 'inert-coldroom-v1', 'revision': 0},
        'source': {'source_id': 'coldroom', 'revision': 'r0', 'applicability': 'task', 'dependencies': []},
        'claim': 'vial-opaque-a is amber', 'accepted': None,
    }
    assert validate_envelope('evidence-reference', envelope) == envelope
    assert deserialize_envelope(serialize_envelope('evidence-reference', envelope)) == envelope
    with pytest.raises(ContractError):
        validate_envelope('evidence-reference', {**envelope, 'extra': True})
    with pytest.raises(ContractError):
        validate_envelope('evidence-reference', {**envelope, 'accepted': 'yes'})


@pytest.mark.parametrize('kind', ['task-public', 'role-observation', 'evidence-reference',
                                  'memory-query', 'memory-result', 'consultation',
                                  'typed-action', 'checkpoint', 'outcome'])
def test_all_public_envelope_kinds_have_strict_schemas(kind):
    with pytest.raises(ContractError):
        validate_envelope(kind, {'version': CONTRACT_VERSION, 'kind': kind})


def test_fail_closed_negatives_cover_scope_version_success_and_private_metadata():
    task = {'task_id': 'coldroom-development-11-r0', 'protocol': 'inert-coldroom-v1', 'revision': 0,
            'max_actions': 8, 'sample_kinds': {'vial-opaque-a': 'amber'},
            'slot_zones': {'locker-opaque-0': 0}, 'rules': {'amber': 0, 'teal': 1, 'violet': 2}}
    public = adapt_coldroom(task, adapter_key=b'evaluator-key-strong')['task_public']
    cases = [
        ({k: v for k, v in public.items() if k != 'scope'}, 'missing'),
        ({**public, 'scope': None}, 'null'),
        ({**public, 'scope': {'protocol': 'other', 'revision': 0}}, 'scope'),
        ({**public, 'version': 'hive-contract-v99'}, 'version'),
        ({**public, 'reference_plan': []}, 'private'),
    ]
    for bad, _ in cases:
        with pytest.raises(ContractError):
            validate_envelope('task-public', bad)
    with pytest.raises(ContractError):
        consume_coldroom_bytes(json.dumps({**public, 'reference_plan': []}).encode())


def test_candidate_evidence_cannot_admit_itself_and_success_is_evaluator_owned():
    task = {'task_id': 'coldroom-development-11-r0', 'protocol': 'inert-coldroom-v1', 'revision': 0,
            'max_actions': 8, 'sample_kinds': {'vial-opaque-a': 'amber'},
            'slot_zones': {'locker-opaque-0': 0}, 'rules': {'amber': 0, 'teal': 1, 'violet': 2}}
    evidence = adapt_coldroom(task, adapter_key=b'evaluator-key-strong')['evidence']
    assert evidence['accepted'] is None
    with pytest.raises(ContractError):
        validate_envelope('evidence-reference', {**evidence, 'accepted': True})
    outcome = adapt_coldroom(task, adapter_key=b'evaluator-key-strong')['outcome']
    assert outcome['task_success'] is None
    with pytest.raises(ContractError):
        validate_envelope('outcome', {**outcome, 'task_success': True})


def test_event_order_and_attempt_acceptance_are_immutable_and_distinct():
    action = adapt_coldroom({'task_id': 'coldroom-development-11-r0', 'protocol': 'inert-coldroom-v1',
        'revision': 0, 'max_actions': 8, 'sample_kinds': {'vial-opaque-a': 'amber'},
        'slot_zones': {'locker-opaque-0': 0}, 'rules': {'amber': 0, 'teal': 1, 'violet': 2}}, adapter_key=b'evaluator-key-strong')['action']
    assert action['attempted'] is True and action['accepted'] is None
    assert action['ordinal'] == 2 and action['event_id'].startswith('evt-')
    with pytest.raises(ContractError):
        validate_envelope('typed-action', {**action, 'ordinal': -1})


def test_trace_ids_bind_content_and_stream_order():
    task = {'task_id': 'coldroom-development-11-r0', 'protocol': 'inert-coldroom-v1', 'revision': 0,
            'max_actions': 8, 'sample_kinds': {'vial-opaque-a': 'amber'},
            'slot_zones': {'locker-opaque-0': 0}, 'rules': {'amber': 0, 'teal': 1, 'violet': 2}}
    produced = adapt_coldroom(task, adapter_key=b'evaluator-key-strong')
    trace = [produced[name] for name in ('task_public', 'evidence', 'action', 'outcome')]
    assert len({event['event_id'] for event in trace}) == 4
    from backend.research_hive_contracts import validate_event_stream
    assert validate_event_stream(trace) == trace
    with pytest.raises(ContractError):
        validate_event_stream([trace[0], {**trace[1], 'claim': 'tampered'}, trace[2], trace[3]])
    with pytest.raises(ContractError):
        validate_event_stream([trace[0], trace[2], trace[1], trace[3]])


def test_worker_claims_fail_closed_but_trusted_evaluator_can_authorize():
    from backend.research_hive_contracts import evaluator_admit_evidence, evaluator_record_outcome, validate_worker_envelope
    produced = adapt_coldroom({'task_id': 't', 'protocol': 'inert-coldroom-v1', 'revision': 0,
        'max_actions': 1, 'sample_kinds': {'s': 'amber'}, 'slot_zones': {'z': 0}, 'rules': {}}, adapter_key=b'evaluator-key-strong')
    with pytest.raises(ContractError):
        validate_worker_envelope('typed-action', {**produced['action'], 'accepted': True})
    with pytest.raises(ContractError):
        validate_worker_envelope('outcome', {**produced['outcome'], 'scope_admitted': True, 'accepted_transition': True, 'disposition': 'accepted'})
    admitted = evaluator_admit_evidence(produced['evidence'], accepted=True, ordinal=4)
    assert admitted['accepted'] is True
    authoritative = evaluator_record_outcome(produced['outcome'], ordinal=5, disposition='accepted', scope_admitted=True, accepted_transition=True, task_success=True)
    assert authoritative['task_success'] is True


def test_default_validator_rejects_coherent_self_claimed_authority():
    from backend.research_coldroom import make_task
    from backend.research_hive_contracts import validate_worker_envelope
    produced = adapt_coldroom(make_task(11), adapter_key=b'evaluator-key-strong')
    claimed_action = {**produced['action'], 'accepted': True}
    claimed_outcome = {
        **produced['outcome'], 'disposition': 'completed',
        'scope_admitted': True, 'accepted_transition': True, 'task_success': True,
    }
    for validator in (validate_envelope, validate_worker_envelope):
        with pytest.raises(ContractError):
            validator('typed-action', claimed_action)
        with pytest.raises(ContractError):
            validator('outcome', claimed_outcome)
    with pytest.raises(ContractError):
        serialize_envelope('outcome', claimed_outcome)


def test_trusted_authority_is_typed_ordered_and_stream_valid():
    from backend.research_coldroom import make_task
    from backend.research_hive_contracts import (
        evaluator_admit_evidence, evaluator_record_action,
        evaluator_record_outcome,
    )
    produced = adapt_coldroom(make_task(11), adapter_key=b'evaluator-key-strong')
    with pytest.raises(ContractError):
        evaluator_admit_evidence(produced['evidence'], accepted='yes', ordinal=4)
    with pytest.raises(ContractError):
        evaluator_record_action({**produced['action'], 'attempted': False}, accepted=True, ordinal=4)
    with pytest.raises(ContractError):
        evaluator_admit_evidence(produced['evidence'], accepted=True, ordinal=1)
    admitted = evaluator_admit_evidence(produced['evidence'], accepted=True, ordinal=4)
    outcome = evaluator_record_outcome(
        produced['outcome'], ordinal=5, disposition='completed',
        scope_admitted=True, accepted_transition=True, task_success=True,
    )
    assert validate_event_stream(produced['trace'] + [admitted, outcome], trusted=True)
    with pytest.raises(ContractError):
        validate_event_stream(produced['trace'] + [admitted, outcome])


def test_task_opaque_adapter_is_keyed_and_binds_sources_and_resources():
    from backend.research_hive_contracts import validate_envelope
    from backend.research_coldroom import make_task, worker_views
    first = adapt_coldroom(make_task(11), adapter_key=b'evaluator-key-strong')
    second = adapt_coldroom(make_task(29), adapter_key=b'evaluator-key-strong')
    assert first['task_public']['task_id'] != second['task_public']['task_id']
    assert first['task_public']['samples'] != second['task_public']['samples']
    assert set(worker_views(make_task(11))) == {'queen', 'assay', 'protocol', 'logistics'}
    with pytest.raises(ContractError):
        validate_envelope('memory-result', {**first['evidence'], 'kind': 'memory-result', 'result': {}, 'found': False})
    bad = {**first['outcome'], 'resource_budget': {'actions': -1, 'bytes': None, 'seconds': None}}
    with pytest.raises(ContractError):
        validate_envelope('outcome', bad)


def test_repair2_trusted_events_rebind_ids_and_roundtrip_only_at_trust_boundary():
    from backend.research_coldroom import make_task
    base = adapt_coldroom(make_task(11), adapter_key=b'evaluator-key-strong')
    admitted = __import__('backend.research_hive_contracts', fromlist=['evaluator_admit_evidence']).evaluator_admit_evidence(base['evidence'], accepted=True, ordinal=4)
    assert admitted['ordinal'] == 4 and admitted['accepted'] is True
    assert admitted['event_id'] != base['evidence']['event_id']
    with pytest.raises(ContractError):
        serialize_envelope('evidence-reference', admitted)
    assert deserialize_trusted_envelope(serialize_trusted_envelope('evidence-reference', admitted)) == admitted
    with pytest.raises(ContractError):
        deserialize_envelope(serialize_trusted_envelope('evidence-reference', admitted))


def test_repair2_adapter_consumes_views_and_emits_roundtripped_role_observations():
    from backend.research_coldroom import make_task, worker_views
    task = make_task(29)
    produced = adapt_coldroom(task, worker_views_output=worker_views(task), adapter_key=b'evaluator-key-strong')
    roles = [e['role'] for e in produced['trace'] if e['kind'] == 'role-observation']
    assert roles == ['queen', 'assay', 'protocol', 'logistics']
    assert all('rules' not in e['observation'] for e in produced['trace'] if e['kind'] == 'role-observation')
    for kind, envelope in [(e['kind'], e) for e in produced['trace']]:
        assert deserialize_envelope(serialize_envelope(kind, envelope)) == envelope
    validate_event_stream(produced['trace'])
    payload = b''.join(serialize_envelope(e['kind'], e) for e in produced['trace'])
    assert b'coldroom-development-29-r0' not in payload and b'vial-29-' not in payload and b'locker-29-' not in payload


def test_repair2_scope_coherence_and_lifecycle_invariants():
    from backend.research_coldroom import make_task
    produced = adapt_coldroom(make_task(11), adapter_key=b'evaluator-key-strong')
    action = produced['action']
    with pytest.raises(ContractError):
        validate_envelope('typed-action', {**action, 'attempted': False, 'accepted': True})
    checkpoint = {**produced['outcome'], 'kind': 'checkpoint', 'resume_position': None, 'terminal': True}
    checkpoint.pop('disposition'); checkpoint.pop('scope_admitted'); checkpoint.pop('accepted_transition'); checkpoint.pop('task_success'); checkpoint.pop('resource_budget'); checkpoint.pop('resource_usage')
    validate_envelope('checkpoint', checkpoint)
    with pytest.raises(ContractError):
        validate_event_stream([produced['task_public'], {**produced['evidence'], 'scope': {'protocol': 'inert-coldroom-v1', 'revision': 1}}, produced['action'], produced['outcome']])


def test_repair2_provenance_and_canonical_bytes_are_strict():
    from backend.research_coldroom import make_task
    evidence = adapt_coldroom(make_task(11), adapter_key=b'evaluator-key-strong')['evidence']
    with pytest.raises(ContractError):
        validate_envelope('evidence-reference', {**evidence, 'source': {**evidence['source'], 'source_id': ''}})
    raw = serialize_envelope('evidence-reference', evidence)
    with pytest.raises(ContractError):
        deserialize_envelope(raw[:-1])
    with pytest.raises(ContractError):
        adapt_coldroom(make_task(11), adapter_key=b'short')


def test_every_required_kind_has_a_valid_roundtripped_golden():
    scope = {'protocol': 'inert-coldroom-v1', 'revision': 0}
    source = {'source_id': 'golden-source', 'revision': 'r0', 'applicability': 'golden', 'dependencies': ['inert-coldroom-v1']}
    payloads = {
        'task-public': {'task_id': 'golden-task', 'samples': ['sample-a'], 'slots': ['slot-a'], 'max_actions': 1},
        'role-observation': {'role': 'assay', 'observation': {'sample_kinds': {'sample-a': 'amber'}}},
        'evidence-reference': {'source': source, 'claim': 'golden claim', 'accepted': None},
        'memory-query': {'query': 'golden query'},
        'memory-result': {'source': source, 'result': {}, 'found': False},
        'consultation': {'from_role': 'assay', 'to_role': 'queen', 'question': 'ready?', 'answer': None},
        'typed-action': {'action': {'op': 'reserve', 'sample': 'sample-a', 'slot': 'slot-a'}, 'attempted': True, 'accepted': None},
        'checkpoint': {'resume_position': None, 'terminal': True},
        'outcome': {'disposition': 'running', 'scope_admitted': False, 'accepted_transition': False, 'task_success': None, 'resource_budget': {'actions': 1, 'bytes': None, 'seconds': None}, 'resource_usage': {'actions': None, 'bytes': None, 'seconds': None}},
    }
    for ordinal, (kind, payload) in enumerate(payloads.items()):
        envelope = {'version': CONTRACT_VERSION, 'kind': kind, 'event_id': 'pending', 'ordinal': ordinal, 'scope': scope, **payload}
        envelope['event_id'] = _event_id(envelope)
        assert deserialize_envelope(serialize_envelope(kind, envelope)) == envelope


def test_review_repair_malformed_containers_fail_as_contract_errors():
    malformed_kind = b'{"kind":[],"version":"hive-contract-v1"}\n'
    with pytest.raises(ContractError):
        validate_envelope([], {})
    with pytest.raises(ContractError):
        deserialize_envelope(malformed_kind)
    with pytest.raises(ContractError):
        validate_event_stream([None])


def test_review_repair_success_requires_admitted_scope():
    from backend.research_coldroom import make_task
    from backend.research_hive_contracts import evaluator_record_outcome
    base = adapt_coldroom(make_task(11), adapter_key=b'evaluator-key-strong')['outcome']
    with pytest.raises(ContractError):
        evaluator_record_outcome(
            base, ordinal=4, disposition='completed', scope_admitted=False,
            accepted_transition=True, task_success=True,
        )


@pytest.mark.parametrize(('field', 'value'), [
    ('max_actions', -1),
    ('resource_usage', {'actions': 9, 'bytes': None, 'seconds': None}),
])
def test_review_repair_resource_limits_are_enforced(field, value):
    from backend.research_coldroom import make_task
    produced = adapt_coldroom(make_task(11), adapter_key=b'evaluator-key-strong')
    target = produced['task_public'] if field == 'max_actions' else produced['outcome']
    with pytest.raises(ContractError):
        validate_envelope(target['kind'], {**target, field: value})


def test_review_repair_named_adapter_outputs_match_shifted_trace():
    from backend.research_coldroom import make_task, worker_views
    task = make_task(29)
    produced = adapt_coldroom(
        task, worker_views_output=worker_views(task),
        adapter_key=b'evaluator-key-strong',
    )
    by_kind = {event['kind']: event for event in produced['trace'] if event['kind'] != 'role-observation'}
    for name, kind in [('task_public', 'task-public'), ('evidence', 'evidence-reference'),
                       ('action', 'typed-action'), ('outcome', 'outcome')]:
        assert produced[name] == by_kind[kind]


def test_review2_protocol_answer_mapping_is_not_worker_visible():
    from backend.research_coldroom import make_task, worker_views
    task = make_task(29)
    produced = adapt_coldroom(
        task, worker_views_output=worker_views(task),
        adapter_key=b'evaluator-key-strong',
    )
    protocol = next(
        event for event in produced['trace']
        if event['kind'] == 'role-observation' and event['role'] == 'protocol'
    )
    assert protocol['observation'] == {'guidance_redacted': True}
    assert task['rules'] not in protocol['observation'].values()


@pytest.mark.parametrize('mutation', ['missing_task_field', 'wrong_task_type', 'bad_identifier', 'extra_view_field'])
def test_review2_adapter_inputs_fail_closed_as_contract_errors(mutation):
    from backend.research_coldroom import make_task, worker_views
    task = make_task(29)
    views = worker_views(task)
    if mutation == 'missing_task_field':
        task.pop('sample_kinds')
    elif mutation == 'wrong_task_type':
        task['max_actions'] = 'eight'
    elif mutation == 'bad_identifier':
        task['sample_kinds'] = {1: 'amber'}
    else:
        views['protocol']['ground_truth'] = task['rules']
    with pytest.raises(ContractError):
        adapt_coldroom(
            task, worker_views_output=views,
            adapter_key=b'evaluator-key-strong',
        )


def test_review3_non_json_view_and_envelope_values_fail_as_contract_errors():
    from backend.research_coldroom import make_task, worker_views
    task = make_task(29)
    views = worker_views(task)
    views['queen']['goal'] = object()
    with pytest.raises(ContractError):
        adapt_coldroom(
            task, worker_views_output=views,
            adapter_key=b'evaluator-key-strong',
        )
    envelope = {
        'version': CONTRACT_VERSION, 'kind': 'role-observation',
        'event_id': 'not-yet-stream-checked', 'ordinal': 0,
        'scope': {'protocol': 'inert-coldroom-v1', 'revision': 0},
        'role': 'assay', 'observation': {'bad': object()},
    }
    with pytest.raises(ContractError):
        serialize_envelope('role-observation', envelope)


def test_review3_separate_consumer_consumes_complete_real_shaped_trace():
    from backend.research_coldroom import make_task, worker_views
    from backend.research_hive_contracts import consume_coldroom_trace_bytes
    task = make_task(29)
    produced = adapt_coldroom(
        task, worker_views_output=worker_views(task),
        adapter_key=b'evaluator-key-strong',
    )
    wire = [serialize_envelope(event['kind'], event) for event in produced['trace']]
    consumed = consume_coldroom_trace_bytes(wire)
    assert consumed['task_public'] == produced['task_public']
    assert set(consumed['role_observations']) == {'queen', 'assay', 'protocol', 'logistics'}
    assert consumed['role_observations']['protocol'] == {'guidance_redacted': True}
    assert consumed['event_ids'] == [event['event_id'] for event in produced['trace']]


@pytest.mark.parametrize('mutation', ['missing_outcome', 'arbitrary_role'])
def test_review4_trace_consumer_requires_exact_complete_coldroom_vocabulary(mutation):
    from backend.research_coldroom import make_task, worker_views
    from backend.research_hive_contracts import consume_coldroom_trace_bytes
    task = make_task(29)
    trace = adapt_coldroom(
        task, worker_views_output=worker_views(task),
        adapter_key=b'evaluator-key-strong',
    )['trace']
    if mutation == 'missing_outcome':
        trace = trace[:-1]
    else:
        trace[1] = {**trace[1], 'role': 'intruder'}
        trace[1]['event_id'] = _event_id(trace[1])
    with pytest.raises(ContractError):
        wire = [serialize_envelope(event['kind'], event) for event in trace]
        consume_coldroom_trace_bytes(wire)


@pytest.mark.parametrize('case', ['completed_empty', 'first_action_rejected', 'scope_miss_abstained'])
def test_known_terminal_failure_is_false_without_accepted_transition(case):
    from backend.research_coldroom import make_task, replay, worker_views
    from backend.research_hive_contracts import evaluator_record_outcome
    task = make_task(29)
    result = replay(task, [{'op': 'not-an-action'}] if case == 'first_action_rejected' else [])
    assert result['safe_success'] is False
    assert not any(event['accepted'] for event in result['events'])
    initial = adapt_coldroom(task, worker_views_output=worker_views(task), adapter_key=b'controller-c0-probe-key')['outcome']
    disposition = {'completed_empty': 'completed', 'first_action_rejected': 'rejected', 'scope_miss_abstained': 'abstained'}[case]
    final = evaluator_record_outcome(initial, disposition=disposition,
        scope_admitted=case != 'scope_miss_abstained', accepted_transition=False,
        task_success=result['safe_success'], ordinal=8)
    assert deserialize_trusted_envelope(serialize_trusted_envelope('outcome', final))['task_success'] is False
    with pytest.raises(ContractError):
        serialize_envelope('outcome', final)


def test_terminal_success_still_requires_admitted_scope_and_accepted_transition():
    from backend.research_coldroom import make_task, plan_from_rules, replay, worker_views
    from backend.research_hive_contracts import evaluator_record_outcome
    task = make_task(29)
    result = replay(task, plan_from_rules(worker_views(task), task['rules']))
    assert result['safe_success'] is True
    initial = adapt_coldroom(task, worker_views_output=worker_views(task), adapter_key=b'controller-c0-probe-key')['outcome']
    with pytest.raises(ContractError):
        evaluator_record_outcome(initial, disposition='completed', scope_admitted=True,
            accepted_transition=False, task_success=True, ordinal=8)
    with pytest.raises(ContractError):
        evaluator_record_outcome(initial, disposition='completed', scope_admitted=False,
            accepted_transition=True, task_success=True, ordinal=8)
