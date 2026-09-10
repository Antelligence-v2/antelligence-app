"""Read-only diagnostic of validated proposals, never a replacement scorer."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path

COLLECTIVE = ('evidence_exchange', 'evidence_sources', 'evidence_isolated')
ARMS = COLLECTIVE + ('independent_vote', 'solo_refine')


def classify_group(messages, reference):
    if reference not in ('yes', 'no', 'maybe'):
        raise ValueError('only PubMedQA choice references are supported')
    if len(messages) != 3 or any(
        message.get('error') or message.get('parse_error')
        or not isinstance(message.get('payload'), dict)
        or 'answer' not in message['payload']
        or message['payload']['answer'] not in ('yes', 'no', 'maybe', None)
        for message in messages
    ):
        return 'blocked_invalid'
    answers = [message['payload']['answer'] for message in messages]
    matches = answers.count(reference)
    if matches >= 2:
        return 'majority_reference'
    return 'minority_reference' if matches else 'no_reference_proposal'


def analyze_report(report):
    ids = report['selected_task_ids']
    expected = {(task_id, arm) for task_id in ids for arm in ARMS}
    keys = [(cell['task_id'], cell['protocol']) for cell in report['cells']]
    if (report['status'] != 'completed' or not ids or len(set(ids)) != len(ids)
            or len(keys) != len(expected) or set(keys) != expected
            or report['total_cells'] != len(expected)
            or report['completed_cells'] != len(expected)):
        raise ValueError('requires exact terminal five-arm cohort with unique cells')
    cells = dict(zip(keys, report['cells']))
    rows = []
    arm_summary = {arm: {'official_successes': 0, 'official_statuses': Counter(),
                        'final_groups': Counter(), 'transitions': Counter()} for arm in ARMS}
    for task_id in ids:
        group = {arm: cells[task_id, arm] for arm in ARMS}
        refs = {cell['expected_answer'] for cell in group.values()}
        if len(refs) != 1:
            raise ValueError('reference drift across arms')
        reference = refs.pop()
        for arm, cell in group.items():
            expected_length = 3 if arm == 'independent_vote' else 6
            if len(cell['messages']) != expected_length:
                raise ValueError('missing or surplus logical messages')
            stored_correct = (cell['answer'] == reference) if cell['status'] == 'completed' else None
            if cell['correct'] is not stored_correct:
                raise ValueError('stored official outcome inconsistent; use independent full audit')
        initials = {arm: group[arm]['messages'][:3] for arm in COLLECTIVE}
        signatures = []
        for arm, events in initials.items():
            signature = []
            for event in events:
                origin = event.get('inference_provenance', {}).get('origin_response_id')
                if not origin or event['kind'] != 'claim' or event['round'] != 0:
                    raise ValueError('missing explicit common-initial identity')
                signature.append((origin, event['payload'], event.get('parse_error'), event.get('error')))
            signatures.append(signature)
        if any(value != signatures[0] for value in signatures[1:]):
            raise ValueError('unpaired initials; do not merge distinct samples')
        initial = classify_group(initials[COLLECTIVE[0]], reference)
        row = {'task_id': task_id, 'reference': reference, 'initial_group': initial, 'arms': {}}
        for arm, cell in group.items():
            summary = arm_summary[arm]
            summary['official_successes'] += cell['correct'] is True
            summary['official_statuses'][cell['status']] += 1
            arm_row = {'official_status': cell['status'], 'official_correct': cell['correct']}
            if arm != 'solo_refine':
                final = classify_group(cell['messages'][-3:], reference)
                summary['final_groups'][final] += 1
                arm_row['final_group'] = final
                if arm in COLLECTIVE:
                    if initial == 'blocked_invalid' or final == 'blocked_invalid' or cell['status'] not in ('completed', 'abstained'):
                        transition = 'blocked_invalid'
                    elif initial == 'minority_reference':
                        transition = 'minority_rescued' if final == 'majority_reference' else 'minority_unresolved'
                    elif initial == 'majority_reference':
                        transition = 'majority_retained' if final == 'majority_reference' else 'majority_lost'
                    else:
                        transition = 'no_initial_match_to_majority' if final == 'majority_reference' else 'no_initial_match_unresolved'
                    summary['transitions'][transition] += 1
                    arm_row['transition'] = transition
            row['arms'][arm] = arm_row
        rows.append(row)
    return {'run_id': report['run_id'], 'analysis_kind': 'post_hoc_oracle_diagnostic_not_new_evaluation',
            'questions': len(ids), 'initial_groups': dict(Counter(row['initial_group'] for row in rows)),
            'independent_vote_groups': dict(arm_summary['independent_vote']['final_groups']),
            'arms': arm_summary, 'rows': rows,
            'limitations': [
                'Uses benchmark references after execution; not a deployable router or learned policy.',
                'Only validated payloads are inspected; raw rejected answers are never recovered.',
                'Any invalid group member blocks group classification; every selected question stays counted.',
                'Minority reference means oracle selection opportunity, not achievable improvement.',
                'No reference proposal does not rule out synthesis of complementary partial evidence.',
                'Final-message groups are diagnostic; official invalid cells remain invalid.',
                'Single hosted model, selected public tasks, one draw; not heterogeneous model diversity.',
                'Consumed evaluation data; cannot be reused to claim a fresh replication.',
            ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.report.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    if digest != args.expected_sha256:
        raise ValueError('report hash differs from approved archived input')
    result = analyze_report(json.loads(source))
    result.update(source_report_sha256=digest, analyzer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write('\n')
    print(json.dumps({'output': str(args.output), 'questions': result['questions'],
                      'initial_groups': result['initial_groups'],
                      'independent_vote_groups': result['independent_vote_groups']}, indent=2))


if __name__ == '__main__':
    main()
