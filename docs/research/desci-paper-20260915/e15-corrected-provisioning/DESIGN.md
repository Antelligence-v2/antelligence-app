# E15 — corrected provisioning + serialized merge claims + delegated slots (pre-registered before the live matrix)

Status: written 2026-09-15 **before** the live matrix. Harness: `run_e15.py`, version
`e15-fixed-provisioning-v4`. The arm runner refuses to start without a passing
`--pretest` gate in `out/pretest.json`.

## Purpose

E12/E14 partitioned arms were underprovisioned: 3 agents against a 4-sample fixture, so
sample-3 (the terminal goal) was never proposed and 0/20 coverage failure was structurally
guaranteed. Their coverage conclusions are confounded and are not quoted anywhere. E15
re-runs the three arms with correct provisioning:

- **Arms:** `solo_planner`, `swarm_partitioned` (raw union), `swarm_partitioned_merged`
  (deterministic merge). Seeds 101–120. One model for all arms: `z-ai/glm-5.3-flash` via
  Nous Portal, temperature 0. Admission gate unchanged (no model call in admission).

## Fix 1 — provisioning (2026-09-14/15)

- The swarm spawns `len(all_samples)` agents (4 for this fixture family).
- `assert_partition_coverage` asserts at startup that the union of agents' slices equals
  `set(all_samples)` (and raises if not — verified by a negative control in the self-test).
- The pretest gate asserts: the goal node's sample is owned by some agent, all proposals
  parseable, merged admission > 0 on every seed, and at least one pretest seed reaches
  non-zero execution success.

## Fix 2 — serialized merge claims (2026-09-15, operator-approved)

**Rationale.** The verifier's `reserve` claims a slot *and* one unit of the sample's
resource; `place` releases both. A resource whose claimants outnumber its capacity (e.g.
fork: `sealed-tray` capacity 1, both siblings require it) can be over-claimed by the bare
union, because the union adds no edge between siblings. Admission then submits two
overlapping reservations, the verifier rejects the second (`resource_unavailable`), and its
subtree cascades — a scheduling artifact, not a coverage result. Chain fixtures recover
fully because prerequisite edges already serialize claims.

**Mechanism.** For each over-subscribed resource, deterministic "take turns" edges:
claimants in fixture topological order; each next reserve depends on the previous claimant's
place node. Edges already implied by the prerequisite repair are skipped; cycle-closing
pairs are skipped. Deterministic, model-free, additive only — a rewrite of the same class as
the existing prerequisite repair.

**Scope.** Merged arm only. The admission gate is untouched; the unmerged arm is untouched
(its raw-union rejections are part of what `swarm_partitioned` measures). The task fixture
is shared input to the merge, so fixture-level constraints (requirements/resources) are not
"invented" data.

## Fix 3 — delegated slots (2026-09-15, operator-approved)

**Why.** The v2 pretest (live, 3 seeds) exposed the next coupling layer: every sample needs
a globally distinct, zone-compatible slot, but each slot is picked by an agent that sees
only its own slice — independent proposers cannot coordinate distinctness. Observed: all
three pretest seeds had two same-zone agents claiming the same slot (usually the example
value copied from the shape), collapsing admission (2/8, 2/8, 6/8 accepted).

**Fix.** The delegator — which already assigns each agent its sample (`my_sample`) — now
also assigns its slot (`my_slot`): samples in prerequisite order, free slots in sorted
order within each zone (deterministic; matches the reference assignment on the checked
seeds). The slice carries `my_slot`; the prompt tells agents to use it verbatim in both
action nodes and the shape example shows their actual slot. The startup coverage assert
extends to the assignment (distinct + zone-compatible). The prompt also states the
resource-field contract explicitly — each node's `resource` is that sample's requirement
value from the requirements map — applied symmetrically to the partitioned **and solo**
prompts, because the field's meaning was previously left to inference and observed
mis-transcriptions collapsed otherwise-clean seeds (v3 pretest).

**Scope.** Slice/prompt/stand-in only. The merge layer and the admission gate are
unchanged from v2. The scripted stand-in now mirrors exactly what real agents receive
(no reference-solution lookup for slots).

**Pretest history → v4.** v2 pretest (live): slot collisions on all three seeds
(2/8, 2/8, 6/8 accepted). v3 (delegated slots, live): all 12 proposals used their
assigned slot correctly, but resource-field mis-transcriptions (3 nodes across seeds
101/102, one writing a slot name as a resource) collapsed those seeds to 0 admitted;
seed 103 was clean (8/8 + execution success). v4 adds the resource contract sentence to
both prompts; its live pretest is re-run before any matrix spend. Offline scripted sweep
on v3/v4: 8/8 + success on every chain/fork fixture, 0 on impossible.

**Evidence recorded before the live run** (offline, scripted proposals, all 20 fixtures):

| composition | merged accepted | merged success | unmerged accepted | unmerged success |
|---|---|---|---|---|
| chain × 8 | 8/8 | true | 1/8 | false |
| fork × 8 | 8/8 | true | 4–5/8 | false |
| impossible × 4 | 0/8 | false | 0/8 | false |

Self-test: `pass: true` (rule cases, coverage case chain+fork, negative control, prompt
checks 4/4).

## Predeclared verdicts (frozen in `run_e15.py` before the matrix)

- **SUPPORTED (asymmetry theory):** partitioned redundancy stays ≈0% (≤ 0.01) AND
  partitioned successes ≥ 3/20.
- **SUPPORTED WITH REPAIR:** merged successes > partitioned successes AND merged successes
  ≥ half of solo's.
- **REFUTED (for real this time):** partitioned and merged successes both remain 0/20 while
  solo is high.

## Budget

Total cap $0.50; expected ≈ $0.10. Per-arm hard stop $0.12; pretest cap $0.03. Route:
`https://inference-api.nousresearch.com/v1`; token read fresh per call from
`~/.hermes/auth.json` (`providers.nous`).
