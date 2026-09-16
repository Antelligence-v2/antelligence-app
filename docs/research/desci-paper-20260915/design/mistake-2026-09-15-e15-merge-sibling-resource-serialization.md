---
linked: 2026-09-15
---

# E15 merge layer does not serialize sibling resource claims — fork compositions lose a subtree

Date found: 2026-09-15. Severity: medium — near-miss. No published claim was wrong, but running E15
as-is and interpreting `swarm_partitioned_merged` coverage without this would blame the coverage
hypothesis for a scheduling gap.

## The defect

`merge_partitioned` (run_e15.py, inherited from run_e14.py) rewires each reserve node to depend on
the **place nodes of its declared prerequisite samples** and adds nothing else. It introduces no edge
between *sibling* samples that share a limited resource.

The admission verifier's `reserve` **claims a slot and one unit of the sample's resource**; `place`
releases both. If two siblings require the same resource and admission submits both reservations
before either releases, the second is rejected `resource_unavailable` and its subtree cascades.

Reproduced on seed 102 (fork), `merge_partitioned` → `admit`:

```
resources      = {bench: 2, sealed-tray: 1}
requirements   = {sample-0: bench, sample-1: sealed-tray, sample-2: sealed-tray, sample-3: bench}
accepted       = 4
rejected       = 1x verifier_feasibility "resource_unavailable" + 3x reachability "child of rejected node"
execute success= False
```

Chain (seed 101, all samples on `bench`, capacity 1) recovers 8/8 — the prerequisite chain already
serializes every reservation. So this is not a provisioning bug (the one-agent-per-sample fix is
correct); it is a merge/ordering gap that only bites fan-out (fork) compositions.

## Why it is easy to miss

A **single** scripted whole-task proposal chains each node to the previous one, so it is inherently
serialized and passes. The E15 self-test's `matrix_runs` block uses exactly that single-proposal
path — it does **not** exercise merge — so it shows fork 8/accepted/success while the merged coverage
case shows 4/failure. Read `selftest.json`'s `matrix_runs` as the solo path, not the merged path.

## Rule

When merging partial plans, check for **ordering constraints the union drops**, not just missing
nodes. Any resource with `capacity < number of concurrently-reservable siblings` needs an explicit
serialization edge, or the merged plan will fail admission for a reason that has nothing to do with
coverage. Assert this in the coverage self-test.

## Required correction

1. Decide (operator) between: pin the observed fork behaviour as a documented characterization test
   and attribute fork losses in the write-up, or add an explicit sibling-serialization edge to
   `merge_partitioned` (a design change — needs sign-off and re-registration).
2. Until then, do **not** report E15 `swarm_partitioned_merged` fork coverage as evidence about the
   merge's repair ability.

## Resolution (2026-09-16)

Fixed in E15 `run_e15.py` v2 (deterministic "take turns" edges for over-subscribed resources; see
the experiment's `DESIGN.md` Fix 2). Because the same fixture family also has a second global
coupling (slots), the merged arm became fully operable only after the delegator also supplied each
agent its slot and both prompts stated the field contracts (Fixes 3/4). Final corrected re-run:
merged **16/20** (8/8 nodes + executed success on every solvable fixture) vs raw-partitioned
**0/20** vs solo **8/20**; verdict `SUPPORTED_WITH_REPAIR`; total spend $0.0175. Session record:
`[[2026-09-15-antelligence-paper-v2-archive]]`.
