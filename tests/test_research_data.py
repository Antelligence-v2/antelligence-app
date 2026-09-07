"""Projection tests: public sources must never serialize gold metadata."""
from decimal import Decimal
import pytest
from backend.research_data import project_pubmed, project_finqa, load_bundle, select_tasks


def test_pubmed_projection_does_not_copy_labels():
    task = project_pubmed('1', {'QUESTION': 'Question?', 'CONTEXTS': ['Evidence'], 'final_decision': 'yes', 'LONG_ANSWER': 'SECRET'}, 'development')
    assert task['expected_answer'] == 'yes'
    assert task['evidence'] == [{'id': 'context_0', 'text': 'Evidence'}]
    assert 'SECRET' not in str(task)


def record(answer='25%', execution=.25):
    return {'id': 'firm/1', 'pre_text': ['Report text'], 'post_text': [], 'table': [['Year','Sales'], ['2020','25']], 'qa': {'question': 'What percentage?', 'answer': answer, 'exe_ans': execution, 'program': 'SECRET', 'gold_inds': {'secret': 'SECRET'}}}


def test_numeric_percentage_is_explicit_and_not_execution_program():
    task = project_finqa(record(), 'development')
    assert task['expected_answer'] == '25'
    assert 'percentage points' in task['question']
    assert 'SECRET' not in str(task)
    assert Decimal(task['tolerance']) == Decimal('.01')
    assert project_finqa(record(execution=25), 'development')['expected_answer'] == '25'


@pytest.mark.parametrize('answer,execution', [('18.6',19.2), ('NaN',1), ('yes',True), ('1', float('inf'))])
def test_ambiguous_or_inconsistent_labels_are_excluded(answer, execution):
    with pytest.raises(ValueError):
        project_finqa(record(answer, execution), 'evaluation')


def test_pinned_bundle_and_selection_are_complete_disjoint_deterministic():
    bundle = load_bundle()
    tasks = bundle['tasks']
    assert len(tasks) == 200
    assert len({t['task_id'] for t in tasks}) == len(tasks)
    for dataset in ('pubmedqa','finqa'):
        dev = select_tasks([dataset], 'development', 50, 17)
        evaluation = select_tasks([dataset], 'evaluation', 50, 17)
        assert len(dev) == len(evaluation) == 50
        assert not ({t['source_id'] for t in dev} & {t['source_id'] for t in evaluation})
        assert select_tasks([dataset], 'development', 2, 17) == dev[:2]
    assert all(d['source_sha256'] and d['revision'] for d in bundle['datasets'])
