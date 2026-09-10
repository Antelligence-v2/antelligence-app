"""Experimental inert coldroom: can shared facts support safe state changes?

Typed JSON actions only. No shell, network, real samples or model calls. This is
an application-level simulator, NOT isolation for executing untrusted Python.
The evaluator owns ground truth; future workers must receive only worker_views.
Scripted plans below test evaluator mechanics, never intelligence performance.
"""
from __future__ import annotations

import copy
import random
import hashlib
import json
import sqlite3
from pathlib import Path

KINDS = ('amber', 'teal', 'violet')
PROTOCOL = 'inert-coldroom-v1'


def make_task(seed: int, revision: int = 0) -> dict:
    if type(seed) is not int or not 0 <= seed <= 2_147_483_647:
        raise ValueError("seed must be a nonnegative 32-bit integer")
    if type(revision) is not int or revision not in (0, 1):
        raise ValueError("revision must be 0 or 1")
    rng = random.Random(seed)
    sample_ids = [f'vial-{seed}-{i}' for i in rng.sample(range(10, 99), 3)]
    zones = rng.sample(range(3), 3)
    return {
        'task_id': f'coldroom-development-{seed}-r{revision}',
        'protocol': PROTOCOL, 'revision': revision, 'max_actions': 8,
        'sample_kinds': dict(zip(sample_ids, KINDS)),
        'slot_zones': {f'locker-{seed}-{i}': zone for i, zone in enumerate(zones)},
        'rules': {kind: (i + revision) % 3 for i, kind in enumerate(KINDS)},
    }


def worker_views(task: dict) -> dict:
    common = {k: copy.deepcopy(task[k]) for k in ('task_id', 'protocol', 'revision', 'max_actions')}
    return {
        'queen': {**common, 'samples': list(task['sample_kinds']),
                  'slots': list(task['slot_zones']), 'goal': 'place every inert vial in its permitted zone'},
        'assay': {'sample_kinds': copy.deepcopy(task['sample_kinds'])},
        'protocol': {'rules': copy.deepcopy(task['rules'])},
        'logistics': {'slot_zones': copy.deepcopy(task['slot_zones']), 'capacity_per_slot': 1},
    }


def plan_from_rules(views: dict, rules: dict) -> list[dict]:
    """Hand-written join baseline, not a Queen model or learned policy."""
    zones = views['logistics']['slot_zones']
    result = []
    for sample, kind in views['assay']['sample_kinds'].items():
        slot = next(slot for slot, zone in zones.items() if zone == rules[kind])
        for op in ('reserve', 'place'):
            result.append({'op': op, 'sample': sample, 'slot': slot,
                           'revision': views['queen']['revision']})
    return result


def replay(task: dict, actions: list[dict]) -> dict:
    """Replay bounded submitted actions; stop at the first rejected transition.

    Task is trusted evaluator state, never a worker-controlled payload. An
    incomplete safe plan is not successful. Rejected actions change no state.
    """
    if type(actions) is not list:
        raise ValueError('actions must be a list')
    placed, reserved, events = {}, {}, []
    reason = None
    for ordinal, action in enumerate(actions):
        shape_ok = (
            type(action) is dict and set(action) == {'op', 'sample', 'slot', 'revision'}
            and all(type(action.get(k)) is str for k in ('op', 'sample', 'slot'))
            and action.get('op') in ('reserve', 'place')
            and type(action.get('revision')) is int
            and action.get('sample') in task['sample_kinds']
            and action.get('slot') in task['slot_zones']
        )
        if ordinal >= task['max_actions']:
            reason = 'action_budget_exceeded'
        elif not shape_ok:
            reason = 'invalid_action'
        elif action['revision'] != task['revision']:
            reason = 'revision_mismatch'
        else:
            sample, slot = action['sample'], action['slot']
            if sample in placed:
                reason = 'sample_already_placed'
            elif action['op'] == 'reserve':
                if slot in reserved or slot in placed.values() or sample in reserved.values():
                    reason = 'slot_unavailable'
                else:
                    reserved[slot] = sample
            elif reserved.get(slot) != sample:
                reason = 'reservation_required'
            elif task['slot_zones'][slot] != task['rules'][task['sample_kinds'][sample]]:
                reason = 'incompatible_zone'
            else:
                placed[sample] = slot
                del reserved[slot]
        events.append({'action': copy.deepcopy(action), 'accepted': reason is None,
                       'reason': reason, 'placed': dict(placed), 'reserved': dict(reserved)})
        if reason is not None:
            break
    complete = set(placed) == set(task['sample_kinds'])
    return {'complete': complete, 'safe_success': complete and reason is None,
            'submitted_actions': len(actions), 'attempted_actions': len(events),
            'stop_reason': reason, 'placed': placed, 'events': events}


def remember(path: Path, task: dict, actions: list[dict]) -> str:
    """Evaluator-owned insertion into a scratch DB, never an agent-write API.

    Hashes detect accidental tampering, not authentic authorship or truth. The
    caller/evaluator is trusted; arbitrary worker-supplied task state is not.
    """
    if not replay(task, actions)['safe_success']:
        raise ValueError('only successful safe episodes may become reusable rules')
    payload = json.dumps({'task': task, 'actions': actions}, sort_keys=True, separators=(',', ':'))
    episode_id = hashlib.sha256(payload.encode()).hexdigest()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS episodes (id TEXT PRIMARY KEY, protocol TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL)')
        db.execute('INSERT OR IGNORE INTO episodes VALUES (?, ?, ?, ?)',
                   (episode_id, task['protocol'], task['revision'], payload))
    return episode_id


def recall(path: Path, protocol: str, revision: int) -> dict | None:
    """Read-only, scoped recall; re-derive a rule from a replayed episode."""
    if not Path(path).exists():
        return None
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('SELECT id, payload FROM episodes WHERE protocol=? AND revision=? ORDER BY id',
                          (protocol, revision)).fetchall()
    if not rows:
        return None
    memories = []
    for episode_id, payload in rows:
        if hashlib.sha256(payload.encode()).hexdigest() != episode_id:
            raise ValueError('memory payload hash mismatch')
        source = json.loads(payload)
        task = source['task']
        if task['protocol'] != protocol or task['revision'] != revision:
            raise ValueError('memory scope index mismatch')
        result = replay(task, source['actions'])
        if not result['safe_success']:
            raise ValueError('memory episode no longer passes replay')
        rules = {task['sample_kinds'][sample]: task['slot_zones'][slot]
                 for sample, slot in result['placed'].items()}
        if memories and rules != memories[0]['rules']:
            raise ValueError('memory contains conflicting rules in the same scope')
        memories.append({'episode_id': episode_id, 'source_task_id': task['task_id'],
                         'protocol': protocol, 'revision': revision, 'rules': rules})
    return memories[0]


def replay_with_memory(task: dict, path: Path) -> dict:
    """Apply scoped recall before any simulated action; evaluator owns task.

    This model-free gate is not an agent permission or OS security boundary.
    """
    try:
        memory = recall(path, task['protocol'], task['revision'])
    except (ValueError, sqlite3.Error) as exc:
        return {**replay(task, []), 'status': 'blocked_memory_invalid',
                'memory': None, 'memory_error': str(exc)}
    if memory is None:
        return {**replay(task, []), 'status': 'abstained_scope_miss', 'memory': None}
    views = {role: view for role, view in worker_views(task).items() if role != 'protocol'}
    actions = plan_from_rules(views, memory['rules'])
    return {**replay(task, actions), 'status': 'memory_replayed', 'memory': memory}
