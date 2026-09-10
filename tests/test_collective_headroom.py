"""Unit-only trace fixtures, not model-quality evidence."""
import importlib.util
import copy
import pytest
from pathlib import Path
from typing import Any


def analyzer():
    path = Path(__file__).resolve().parents[1] / 'scripts/analyze_collective_headroom.py'
    assert path.exists(), 'saved-trace headroom analyzer is not implemented'
    spec = importlib.util.spec_from_file_location('headroom', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def message(answer, *, invalid=False):
    return {'payload': None if invalid else {'answer': answer},
            'parse_error': 'brief exceeds 160 characters' if invalid else None,
            'error': None, 'content': '{"answer":"yes"}'}


def test_oracle_headroom_distinguishes_wrong_majority_from_no_right_member():
    classify = analyzer().classify_group
    assert classify([message('yes'), message('no'), message('no')], 'yes') == 'minority_reference'
    assert classify([message('yes'), message('yes'), message('no')], 'yes') == 'majority_reference'
    assert classify([message('no'), message('no'), message(None)], 'yes') == 'no_reference_proposal'
    # Validated null never resurrects the raw yes string.
    assert classify([message(None), message(None), message(None)], 'yes') == 'no_reference_proposal'


def test_invalid_or_missing_member_stays_blocked_even_with_correct_raw_text():
    classify = analyzer().classify_group
    assert classify([message('yes', invalid=True), message('no'), message('no')], 'yes') == 'blocked_invalid'
    assert classify([message('yes'), message('yes')], 'yes') == 'blocked_invalid'
    assert classify([message('yes'), message('yes'), message('invented')], 'yes') == 'blocked_invalid'


def report_fixture() -> dict[str, Any]:
    cells = []
    for arm in ['evidence_exchange', 'evidence_sources', 'evidence_isolated', 'independent_vote', 'solo_refine']:
        events = []
        answers = ['yes', 'no', 'no'] + ['yes'] * 3
        if arm == 'independent_vote':
            answers = ['no'] * 3
        for index, answer in enumerate(answers):
            event = message(answer)
            event.update(round=0 if index < 3 else 1,
                         kind='claim' if index < 3 else 'revision',
                         inference_provenance={'origin_response_id': f'origin-{index}'})
            events.append(event)
        correct = arm != 'independent_vote'
        cells.append(dict(task_id='unit-only', protocol=arm, expected_answer='yes',
                          status='completed', correct=correct, answer='yes' if correct else 'no',
                          messages=events))
    return dict(run_id='unit-only', status='completed', selected_task_ids=['unit-only'],
                total_cells=5, completed_cells=5, cells=cells)


def test_report_counts_shared_initial_once_and_preserves_official_outcomes():
    report = report_fixture()
    before = copy.deepcopy(report)
    result = analyzer().analyze_report(report)
    assert report == before
    assert result['questions'] == 1
    assert result['initial_groups']['minority_reference'] == 1
    assert result['independent_vote_groups']['no_reference_proposal'] == 1
    assert result['arms']['evidence_sources']['transitions']['minority_rescued'] == 1
    assert result['arms']['independent_vote']['official_successes'] == 0


def test_report_rejects_duplicate_or_missing_cells_and_unpaired_initials():
    module = analyzer()
    for mutation in ['duplicate', 'missing', 'unpaired']:
        report = report_fixture()
        if mutation == 'duplicate':
            report['cells'][-1] = copy.deepcopy(report['cells'][0])
        elif mutation == 'missing':
            report['cells'].pop()
        else:
            report['cells'][1]['messages'][0]['inference_provenance']['origin_response_id'] = 'other'
        with pytest.raises(ValueError):
            module.analyze_report(report)


def test_invalid_cell_cannot_become_success_via_valid_final_messages():
    report = report_fixture()
    report['cells'][1].update(status='invalid', correct=None, answer=None)
    result = analyzer().analyze_report(report)
    assert result['arms']['evidence_sources']['official_successes'] == 0
    assert result['arms']['evidence_sources']['transitions']['blocked_invalid'] == 1
