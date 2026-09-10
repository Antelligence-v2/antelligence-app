"""Contracts for an inert, typed-action research testbed; not model evidence."""
import importlib.util
import copy
import pytest
from pathlib import Path


def lab():
    path = Path(__file__).resolve().parents[1] / 'backend/research_coldroom.py'
    assert path.exists(), 'typed-action coldroom evaluator is not implemented'
    spec = importlib.util.spec_from_file_location('research_coldroom', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_views_are_partial_and_a_joined_plan_completes_the_inert_task():
    m = lab()
    task = m.make_task(11, revision=0)
    views = m.worker_views(task)
    assert set(views) == {'queen', 'assay', 'protocol', 'logistics'}
    assert 'sample_kinds' not in views['queen']
    assert 'rules' not in views['assay']
    assert 'sample_kinds' not in views['protocol']
    assert 'rules' not in views['logistics']
    plan = m.plan_from_rules(views, views['protocol']['rules'])
    result = m.replay(task, plan)
    assert result['complete'] is True
    assert result['safe_success'] is True
    assert result['attempted_actions'] == 6
    assert len(result['placed']) == 3
    assert len(result['events']) == 6


@pytest.mark.parametrize('fault,reason', [
    ('stale', 'revision_mismatch'), ('wrong_zone', 'incompatible_zone'),
    ('unreserved', 'reservation_required'), ('collision', 'slot_unavailable'),
    ('duplicate', 'sample_already_placed'), ('unknown', 'invalid_action'),
    ('extra_field', 'invalid_action'), ('boolean_revision', 'invalid_action'),
    ('missing', 'invalid_action'), ('budget', 'action_budget_exceeded'),
])
def test_rejected_action_is_visible_terminal_and_cannot_be_a_safe_success(fault, reason):
    m = lab()
    task = m.make_task(11)
    actions = m.plan_from_rules(m.worker_views(task), task['rules'])
    if fault == 'stale':
        actions[0]['revision'] = 1
    elif fault == 'wrong_zone':
        for action in actions[:2]:
            action['slot'] = actions[2]['slot']
    elif fault == 'unreserved':
        actions = actions[1:]
    elif fault == 'collision':
        actions = [actions[0], dict(actions[2], slot=actions[0]['slot'])]
    elif fault == 'duplicate':
        actions = actions[:2] + actions
    elif fault == 'unknown':
        actions[0]['op'] = 'run_shell'
    elif fault == 'extra_field':
        actions[0]['trusted'] = True
    elif fault == 'boolean_revision':
        actions[0]['revision'] = False
    elif fault == 'missing':
        actions[0].pop('sample')
    elif fault == 'budget':
        task['max_actions'] = 1
    before = copy.deepcopy(task)
    result = m.replay(task, actions)
    assert result['safe_success'] is False
    assert result['stop_reason'] == reason
    assert result['events'][-1]['accepted'] is False
    assert task == before
    rejected = result['events'][-1]
    prior = result['events'][-2] if len(result['events']) > 1 else {'placed': {}, 'reserved': {}}
    assert rejected['placed'] == prior['placed']
    assert rejected['reserved'] == prior['reserved']


@pytest.mark.parametrize('seed,revision', [(True, 0), (1, True), (-1, 0), (1, 3)])
def test_generator_rejects_ambiguous_or_unsupported_identifiers(seed, revision):
    with pytest.raises(ValueError):
        lab().make_task(seed, revision)


def test_only_successful_episodes_are_persisted_and_recalled_in_their_scope(tmp_path):
    m = lab()
    path = tmp_path / 'prototype-memory.sqlite3'
    task = m.make_task(11)
    plan = m.plan_from_rules(m.worker_views(task), task['rules'])
    with pytest.raises(ValueError, match='successful'):
        m.remember(path, task, plan[:2])
    episode_id = m.remember(path, task, plan)
    recalled = lab().recall(path, task['protocol'], 0)  # new module/connection
    assert recalled['episode_id'] == episode_id
    assert recalled['rules'] == task['rules']
    assert m.recall(path, task['protocol'], 1) is None
    assert m.recall(path, 'other-environment', 0) is None
    new_task = m.make_task(29)
    assert new_task['task_id'] != recalled['source_task_id']
    transfer = m.plan_from_rules(m.worker_views(new_task), recalled['rules'])
    assert m.replay(new_task, transfer)['safe_success'] is True
    drifted = m.make_task(29, revision=1)
    stale = m.plan_from_rules(m.worker_views(drifted), recalled['rules'])
    assert m.replay(drifted, stale)['stop_reason'] == 'incompatible_zone'


@pytest.mark.parametrize('fault', ['corrupted_payload', 'forged_scope', 'conflicting_rules'])
def test_recall_refuses_corrupted_misindexed_or_contradictory_memory(tmp_path, fault):
    import sqlite3
    m = lab()
    path = tmp_path / 'prototype-memory.sqlite3'
    task = m.make_task(11)
    m.remember(path, task, m.plan_from_rules(m.worker_views(task), task['rules']))
    if fault == 'conflicting_rules':
        changed = m.make_task(29)
        changed['rules'] = m.make_task(29, 1)['rules']
        m.remember(path, changed, m.plan_from_rules(m.worker_views(changed), changed['rules']))
    else:
        with sqlite3.connect(path) as db:
            if fault == 'corrupted_payload':
                db.execute("UPDATE episodes SET payload=payload || ' '")
            else:
                db.execute('UPDATE episodes SET revision=1')
    with pytest.raises(ValueError, match='memory'):
        m.recall(path, task['protocol'], 1 if fault == 'forged_scope' else 0)


def test_demo_runs_real_cross_process_recall_and_preserves_prior_output(tmp_path):
    import json
    import subprocess
    import sys
    script = Path(__file__).resolve().parents[1] / 'scripts/probe_hive_coldroom.py'
    assert script.exists(), 'cross-process coldroom probe is not implemented'
    output = tmp_path / 'new-only-artifacts'
    command = [sys.executable, str(script), '--output-dir', str(output)]
    run = subprocess.run(command, capture_output=True, text=True, check=True)
    report = json.loads(run.stdout)
    assert report['model_requests'] == 0
    assert report['cross_process_recall'] is True
    assert report['scenarios']['restarted_memory']['safe_success'] is True
    assert report['scenarios']['stale_memory_unchecked']['stop_reason'] == 'incompatible_zone'
    assert report['scenarios']['stale_memory_scoped']['safe_success'] is False
    assert report['scenarios']['stale_memory_scoped']['status'] == 'abstained_scope_miss'
    assert report['scenarios']['current_evidence_after_change']['safe_success'] is True
    assert report['scenarios']['self_claimed_success']['safe_success'] is False
    saved = (output / 'report.json').read_bytes()
    again = subprocess.run(command, capture_output=True, text=True)
    assert again.returncode != 0
    assert (output / 'report.json').read_bytes() == saved
