# E15 — corrected provisioning: STATUS (2026-09-15)

**State: harness built; self-test FAILING on one sub-case; full live three-arm run NOT executed.**
Do not cite anything here as an E15 finding.

## What exists

* `run_e15.py` — E15 harness, derived from `run_e14.py` with the provisioning fix (one agent per
  sample) and added coverage assertions. Intended to run `solo_planner` / `swarm_partitioned` /
  `swarm_partitioned_merged` over seeds 101–120 on one model, unchanged admission gate.
* `selftest.json` — output of `run_e15.py --self-test` (offline, `ScriptedDAGPolicy`).

## What the self-test says

`pass: false`, from one failing sub-case in `partition_coverage_case`:

| sub-case | accepted | success | passed |
|---|---:|---:|---|
| `chain` | 8 | true | yes |
| `fork` | 4 | false | **no** |
| negative control (3 agents raises) | — | — | yes |

Prompt checks (one agent per sample, 4/4) and all six rule cases (valid / unsafe / unreachable /
cyclic / contradiction / cross-arm) pass.

Note on the `matrix_runs` block in `selftest.json`: it calls `policy.propose(...)` for a **single
whole-task scripted proposal** (the solo path), *not* the partitioned→merge path. Its
chain/fork = 8/accepted/success rows therefore do **not** exercise the merged arms; the fork
failure below lives only in `partition_coverage_case`.

## Cause of the fork failure (proven, not hypothesised)

Reproduced directly on seed 102 (fork), `merge_partitioned` → `admit`:

```
resources      = {bench: 2, sealed-tray: 1}
requirements   = {sample-0: bench, sample-1: sealed-tray, sample-2: sealed-tray, sample-3: bench}
accepted       = 4
rejected       = 1x verifier_feasibility "resource_unavailable" + 3x reachability "child of rejected node"
execute success= False
```

The verifier's `reserve` **claims a slot and one unit of the sample's resource**; `place` releases
both. The fork fixture gives `sealed-tray` capacity **1** while siblings `sample-1` and `sample-2`
both require it. `merge_partitioned` rewires each reserve to depend on its declared prerequisite
*places* only, so it introduces no edge between the two siblings. Admission (Kahn order) therefore
submits both reservations before either place releases; the second is rejected
`resource_unavailable` and its subtree cascades — 4 of 8 nodes accepted.

This is a **merge-layer scheduling gap, not a provisioning defect**: the provisioning fix is
correct, and chain (seed 101, all samples on `bench` capacity 1) recovers 8/8 with success because
its prerequisite chain already serializes every reservation.

## Consequence for the E15 verdict if run as-is

Fork compositions will lose a subtree in the `swarm_partitioned_merged` arm for a reason unrelated
to the coverage hypothesis. That must be stated in the E15 write-up, or the merge must be given a
serialization edge first — which **changes the frozen E14 merge design and needs operator
sign-off**.

## Options before a live run

1. **Pin the behaviour.** Add an explicit characterization expectation for the fork sub-case
   (accepted == 4, `resource_unavailable` present) with this cause documented, pass the self-test,
   and run the live matrix as designed. The merged arm then measures the frozen merge *as built*,
   and fork losses are attributed in the report rather than silently blamed on coverage.
2. **Serialize siblings.** Add an explicit sibling-ordering edge in `merge_partitioned` (e.g. chain
   a reserve to the previous sibling's place when their resources collide). This changes the E14
   merge layer, so it is a design change, not a fix — needs operator approval and a new
   pre-registration before the live run.

Then, either way: pass the self-test, run the three live arms over seeds 101–120 (~$0.10 expected;
budget cap $0.50; Nous Portal only, token read fresh per call, `max_tokens >= 1500`). If E15 flips
the E12/E14 verdict, update the manuscript §4.8.

## Provenance

Harness source and self-test copied 2026-09-15 from
`/Volumes/WD_BLACK/antelligence-experiments-20260911/e15-corrected-provisioning/`; the seed-102
reproduction above was re-run from the archived `run_e15.py` on 2026-09-15.