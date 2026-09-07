"""Pinned, label-separated public research task projections (not clinical data)."""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

BUNDLE_PATH = Path(__file__).with_name('research_fixtures') / 'tasks.json'
BUNDLE_SHA256 = '01868e7976bf35a190fb92266fb43579aa26c50e989c66a6656aeb8788070004'
LIMITATIONS = [
    'Offline public benchmark research only; not clinical advice, patient validation or trading.',
    'Public benchmark exposure in model training is unknown; locally held out does not mean model-unseen.',
    'FinQA-derived metric is numeric answer accuracy, NOT official program/execution accuracy.',
    'Fixed compact subset: numeric label-consistent FinQA records and bounded context. Selection bias is disclosed.',
    'Equal ensemble call/output ceilings do not equal actual input-token or hardware cost.',
    'Accuracy gates are approximate selected-sample evidence, not future accuracy guarantees.',
    'Citation IDs and short rationales are recorded, not independently checked for entailment.',
]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _task(dataset, source_id, split, question, evidence, answer_type, choices, answer, url):
    if split not in {'development', 'evaluation'} or not question or not evidence:
        raise ValueError('invalid task source')
    if len(json.dumps(evidence, ensure_ascii=False)) > 16000:
        raise ValueError('context exceeds compact research subset limit')
    return dict(task_id=f'{dataset}:{source_id}', source_id=source_id, dataset=dataset,
                domain='medical' if dataset == 'pubmedqa' else 'finance', split=split,
                question=question, evidence=evidence, answer_type=answer_type, choices=choices,
                expected_answer=answer, tolerance='0.01' if answer_type == 'decimal' else '0', source_url=url)


def project_pubmed(source_id, row, split):
    answer = row['final_decision']
    if answer not in {'yes', 'no', 'maybe'}:
        raise ValueError('invalid medical label')
    return _task('pubmedqa', str(source_id), split, row['QUESTION'],
                 [{'id': f'context_{i}', 'text': text} for i, text in enumerate(row['CONTEXTS'])],
                 'choice', ['yes', 'no', 'maybe'], answer, f'https://pubmed.ncbi.nlm.nih.gov/{source_id}/')


def project_finqa(row, split):
    qa = row['qa']
    raw = str(qa['answer']).strip()
    if not re.fullmatch(r'-?\d+(?:\.\d+)?%?', raw) or isinstance(qa.get('exe_ans'), bool):
        raise ValueError('non-numeric or ambiguous FinQA answer')
    try:
        answer, execution = Decimal(raw.rstrip('%')), Decimal(str(qa['exe_ans']))
    except (InvalidOperation, KeyError) as exc:
        raise ValueError('invalid FinQA execution label') from exc
    if not answer.is_finite() or not execution.is_finite():
        raise ValueError('nonfinite FinQA label')
    # Validate consistency ONLY for evaluator admission, never feed either label/program to inference.
    possibilities = [execution, execution * 100] if raw.endswith('%') else [execution]
    if not any(abs(answer - x) <= Decimal('.01') for x in possibilities):
        raise ValueError('FinQA answer/execution labels disagree')
    unit = ('For percentages, return percentage points (e.g. five percent is 5, not 0.05).'
            if raw.endswith('%') else 'Return the numeric value in the units requested by the question/table.')
    question = qa['question'] + '\n' + unit + ' Use a decimal string without commas, units or a percent sign; round to two decimal places.'
    evidence = [{'id': f'table_{i}', 'text': json.dumps(cells, ensure_ascii=False)} for i, cells in enumerate(row['table'])]
    evidence += [{'id': f'{name}_{i}', 'text': text} for name in ('pre_text', 'post_text') for i, text in enumerate(row[name])]
    return _task('finqa', row['id'], split, question, evidence, 'decimal', [], str(answer),
                 'https://github.com/czyssrs/FinQA')


def load_bundle():
    raw = BUNDLE_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BUNDLE_SHA256:
        raise ValueError('Research fixture checksum mismatch; refuse unpinned data')
    return json.loads(raw)


def select_tasks(datasets, split, count, seed):
    if not datasets or len(set(datasets)) != len(datasets) or set(datasets) - {'pubmedqa', 'finqa'}:
        raise ValueError('invalid dataset selection')
    if split not in {'development', 'evaluation'} or type(count) is not int or not 1 <= count <= 50:
        raise ValueError('invalid task selection')
    bundle = load_bundle()
    selected = []
    for dataset in datasets:
        tasks = [t for t in bundle['tasks'] if t['dataset'] == dataset and t['split'] == split]
        tasks.sort(key=lambda t: hashlib.sha256(f'{seed}:{t["task_id"]}'.encode()).hexdigest())
        if len(tasks) < count:
            raise ValueError('insufficient pinned tasks')
        selected.extend(tasks[:count])
    return selected
