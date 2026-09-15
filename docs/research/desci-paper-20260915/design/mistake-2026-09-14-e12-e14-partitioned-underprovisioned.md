---
linked: 2026-09-15
---

# E12 and E14 partitioned arms were one agent short — coverage failure was structural

Date found: 2026-09-14. Severity: high — invalidates the coverage conclusions of BOTH E12
("partitioning kills coverage") and E14 ("a merge layer does not restore coverage").

## The defect

`run_e12.py` / `run_e14.py`, `swarm_partitioned` proposal path:

```
agent_idx = int(agent.split("-")[-1])
all_samples = list(task["sample_kinds"].keys())
my_sample = all_samples[agent_idx % len(all_samples)]
```

The swarm is always `["agent-0", "agent-1", "agent-2"]` — **3 agents**.
The fixture always has **4 samples** (`sample-0..3`), verified by importing `fixture_task`:
e.g. seed 101 `prerequisites = {sample-0: [], sample-1: [sample-0], sample-2: [sample-1],
sample-3: [sample-2]}`.

So the mapping assigns agent-0→sample-0, agent-1→sample-1, agent-2→sample-2, and
**sample-3 is never assigned to any agent.** In a chain fixture sample-3 is the terminal node —
in E12's own seed-116 output the partitioned goal was literally `node-sample-3-place`.

Consequence: the partitioned and merged arms could never produce the goal node. Their **0/20
execution success was guaranteed by construction, not measured.** The E14 merge layer cannot
repair it either, and by design "invents no nodes beyond deterministic rewrites", so it could
only ever partially close the gap (it did raise accepted nodes 32→40 — consistent with repairing
edges among samples 0–2 while sample-3 stayed absent).

## What this invalidates

- **E12's verdict "refutes the asymmetry theory in the DAG layer" is confounded.** The
  *redundancy* half survives and is real: partitioning did collapse redundant nodes to 0%,
  because each agent proposes only its own distinct sample. But the *coverage* half is an
  artifact. E12 does **not** show that a union of partial plans cannot cover a task; it shows
  that three agents cannot cover a four-sample fixture.
- **E14's verdict is confounded the same way** and for the same reason. Its merge layer was
  never given the chance to demonstrate repair, because the missing part (sample-3) was absent
  from every agent's slice and the merge explicitly does not invent nodes.
- The paired statistic E14 reported (merged 0/20 vs solo 9/20, p=0.0039) is arithmetically
  correct and describes a real difference between those arms, but it is not evidence about
  merge layers.

## Why it survived two rounds

The arm was named `swarm_partitioned`, the design note said "each agent sees a disjoint slice",
and the prompt used `% len(all_samples)` — which reads like a deliberate round-robin *for
safety*. Nobody checked that the agent count equalled the sample count. E12's pretest checked
only parseability (and its v1 bug was a separate literal-string defect), so a structurally
unsatisfiable arm passed the gate, twice: once in E12, once when E14 inherited the harness.

This is the "two failures means the diagnosis is wrong" case: E12 said partitioning loses
coverage, E14 added the obvious repair and coverage still did not appear. The shared cause was
never the hypothesis — it was the agent/sample arithmetic.

## Rule

Before claiming an arm *failed to do* something, assert the arm *could* have done it. For any
coverage-style claim, check the provisioning arithmetic (agents vs required units) and assert
coverage in the pretest — e.g. the union of agents' assigned slices must equal the full sample
set, and the goal node must be reachable in at least one pretest seed. A pretest that cannot
fail on the metric you care about is not a gate.

## Required correction

1. Fix the mapping: spawn `len(all_samples)` agents, or map round-robin over samples so the
   union of slices covers every sample. Assert `set(slices) == set(all_samples)` at startup.
2. Re-run the partitioned and merged arms as **E15** (correct provisioning) before either arm's
   result is quoted anywhere.
3. Until E15 lands, E12's and E14's coverage conclusions must be marked **confounded** in the
   paper, the session notes and the handoff. The redundancy results may still be cited.
4. E14's proposed goal must be checked too — confirm the merged arm targets a sample that a
   proposer actually owns.

<!-- wiki:semantic:start -->
## Related (auto-linked)

- [[decisions-moc]]
- [[mistakes-moc]]
- [[mistake-2026-07-27-usage-weekly-is-a-monday-counter-runway-off-by-1570x]]

<!-- wiki:semantic:end -->
