#!/usr/bin/env python3
"""One-command MODEL-FREE probe: partial views, persistence and changed rules.

Run: python3 scripts/probe_hive_coldroom.py --output-dir /path/to/NEW/folder
All cases are public development fixtures. No OS sandbox or model benchmark.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'backend/research_coldroom.py'
spec = importlib.util.spec_from_file_location('research_coldroom', MODULE)
assert spec is not None and spec.loader is not None
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--output-dir', type=Path)
    group.add_argument('--recall-db', type=Path)
    group.add_argument('--gate-db', type=Path)
    args = parser.parse_args()
    if args.recall_db:
        print(json.dumps(lab.recall(args.recall_db, lab.PROTOCOL, 0)))
        return
    if args.gate_db:
        print(json.dumps({
            'process_id': os.getpid(),
            'same_scope': lab.replay_with_memory(lab.make_task(29), args.gate_db),
            'changed_scope': lab.replay_with_memory(lab.make_task(29, revision=1), args.gate_db),
        }))
        return
    root = args.output_dir
    root.mkdir(parents=True, exist_ok=False)
    db = root / 'prototype-memory.sqlite3'
    teacher = lab.make_task(11)
    teacher_plan = lab.plan_from_rules(lab.worker_views(teacher), teacher['rules'])
    episode = lab.remember(db, teacher, teacher_plan)
    child = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--gate-db', str(db.resolve())],
                           capture_output=True, text=True, check=True, timeout=20)
    gated = json.loads(child.stdout)
    memory = gated['same_scope']['memory']
    assert memory['episode_id'] == episode
    cross_process = gated['process_id'] != os.getpid()
    assert cross_process
    task = lab.make_task(29)
    views = lab.worker_views(task)
    after_change = lab.make_task(29, revision=1)
    changed_views = lab.worker_views(after_change)
    scenarios = {
        'current_evidence': lab.replay(task, lab.plan_from_rules(views, views['protocol']['rules'])),
        'restarted_memory': gated['same_scope'],
        'stale_memory_unchecked': lab.replay(after_change, lab.plan_from_rules(changed_views, memory['rules'])),
        'stale_memory_scoped': gated['changed_scope'],
        'current_evidence_after_change': lab.replay(after_change, lab.plan_from_rules(changed_views, changed_views['protocol']['rules'])),
        'self_claimed_success': lab.replay(task, [{'op': 'claim_success', 'safe_success': True}]),
    }
    assert scenarios['restarted_memory']['safe_success']
    assert scenarios['stale_memory_unchecked']['stop_reason'] == 'incompatible_zone'
    assert scenarios['stale_memory_scoped']['status'] == 'abstained_scope_miss'
    assert scenarios['stale_memory_scoped']['attempted_actions'] == 0
    assert not scenarios['stale_memory_scoped']['safe_success']
    assert scenarios['current_evidence_after_change']['safe_success']
    assert not scenarios['self_claimed_success']['safe_success']
    report = {
        'kind': 'scripted_testbed_demonstration_not_model_evaluation',
        'model_requests': 0, 'cross_process_recall': cross_process,
        'processes': {'producer_pid': os.getpid(), 'gate_pid': gated['process_id']},
        'scope': 'inert symbolic vials; public development fixtures; no physical/clinical validity',
        'memory': memory, 'scenarios': scenarios,
        'artifacts': {'memory_db': str(db.resolve()), 'report': str((root / 'report.json').resolve())},
        'code_hashes': {str(p.relative_to(MODULE.parents[1])): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [MODULE, Path(__file__).resolve()]},
        'limitations': [
            'Handwritten join policy; no LLM, learned Queen or emergent cooperation.',
            'Same-rule transfer across randomized identifiers is not structural generalization.',
            'Independent full-information solo can also solve this small task.',
            'Role views are data projection, not a security boundary for same-process agents.',
            'Scratch DB insertion/evaluator task state are trusted; hashes are not signatures.',
            'The gate abstains; fresh-evidence recovery is a separate scripted comparison, not an autonomous fetch.',
            'Scope matches do not establish truth; the state verifier can still reject an admitted plan.',
            'No live API/workbench integration or model-pilot admission.',
        ],
    }
    for name, value in [('report.json', report), ('development-tasks.json', [teacher, task, after_change])]:
        with (root / name).open('x') as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write('\n')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
