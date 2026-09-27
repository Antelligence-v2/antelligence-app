# Antelligence Engine — Shared Kernel Design & Implementation Plan

> **Status:** proposal (2026-09-27). Nothing in this document is built yet.
> **Branch:** `engine/v1` (from `main`), one commit per phase.

---

## 1. What we are building (one paragraph)

One **engine** (the `antelligence/` package) that every swarm experiment runs on.
The engine owns *how agents coordinate and how we trust what they share*: local
views, typed expiring signals, provenance-bearing memory, admission checks, a
model-free verifier, and an append-only event log that becomes the run's proof.
**Worlds** plug into the engine and own only *what exists, what an agent can see,
what an action does, and how a run is scored* — tumor, foraging, task-DAG, and
research QA are four worlds on the same engine.

> Pitch: **a verifiable stigmergic substrate** — agents coordinate only through a
> typed, expiring, provenance-bearing signal field; a model-free verifier owns
> outcomes; the chain notarizes runs.

---

## 2. Why

| Today | Problem | Engine answer |
|---|---|---|
| 3 swarm systems (ants, tumor nanobots, LLM research) in one repo | No shared code for signals, LLM calls, logging | One kernel, many worlds |
| 3 pheromone implementations (biofvm, dict grid, `tumor_hunt.PheromoneGrid`) | Drift, inconsistent semantics | One `Signal` + `SignalField` |
| Queen / knowledge graph see the whole tumor | Violates "no agent sees the whole picture" | `LocalView` enforced by types; Queen emits signals |
| `QueenNanobot.step()` never called by the model loop | Episodic adaptation is dead code in the app | Scheduler owns the loop for every policy |
| Per-bot blocking LLM calls + sync chain tx inside the tick | Slow, fragile, untestable | Async batched provider; async provenance outbox |
| Paper machinery (memory, transport, verifier) lives outside the repo | App and paper are different projects | Trust layer is part of the kernel |

---

## 3. The big picture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                               antelligence/                                 │
│                                                                             │
│  ┌──────────────────────────── kernel/ (the engine) ──────────────────────┐ │
│  │                                                                        │ │
│  │   COORDINATION              TRUST                    EXECUTION         │ │
│  │   ────────────              ─────                    ─────────         │ │
│  │   signal.py                 memory.py                types.py          │ │
│  │   field.py                  admission.py             scheduler.py      │ │
│  │    ├ GridField              verifier.py              policies/         │ │
│  │    └ BoardField                                      events.py         │ │
│  │                                                                        │ │
│  └───────────────▲──────────────────────▲─────────────────────▲───────────┘ │
│                  │ implements World      │ uses                │ calls       │
│  ┌───────────────┴──────┐  ┌─────────────┴────────┐  ┌─────────┴──────────┐  │
│  │ worlds/              │  │ providers/           │  │ provenance/        │  │
│  │  ├ tumor/            │  │  one OpenAI-compat.  │  │  event log →       │  │
│  │  ├ foraging/         │  │  client, usage,      │  │  proof bundle →    │  │
│  │  ├ task_dag/         │  │  cache, budget,      │  │  async outbox →    │  │
│  │  └ research_qa/      │  │  offline fake        │  │  IPFS / chain      │  │
│  └──────────────────────┘  └──────────────────────┘  └────────────────────┘  │
│                                                                             │
│  experiments/  arms × seeds × worlds, paired stats, store                   │
│  api/          FastAPI routers          settings.py  typed config, no env   │
│                                                      reads at import        │
└─────────────────────────────────────────────────────────────────────────────┘
          │ wraps (unchanged)                          │ wraps (unchanged)
          ▼                                            ▼
   backend/biofvm.py, tumor_environment.py,     backend/chain/* (proof_spec,
   brats_loader.py                              ipfs, submit, verify, ...)
```

**Rule of the architecture:** the kernel never imports a world. Worlds import the
kernel. That is what lets one flag (e.g. "shared memory on/off") mean the exact
same code in every world.

---

## 4. One tick — how agents act

```
          ┌──────────────────────────── Scheduler.tick() ─────────────────────────────┐
          │                                                                           │
          │  for each agent (batched; LLM calls run concurrently under a budget):     │
          │                                                                           │
          │   ① world.local_view(agent)      what THIS agent can see (radius/topic)   │
          │            │                                                              │
          │            ▼                                                              │
          │   ② field.sense(agent)  ──────►  only live, in-scope signals              │
          │   ③ memory.recall(agent) ─────►  only ADMITTED, non-invalidated records   │
          │            │                                                              │
          │            ▼                                                              │
          │   ④ policy.decide(LocalView) ──► Intent  (+ optional Signals to emit)     │
          │            │                     RulePolicy | LLMPolicy | QueenEmitter    │
          │            ▼                                                              │
          │   ⑤ admission.check(signals) ──► reject: expired / out of scope /         │
          │            │                     replay / over budget / bad sender        │
          │            ▼                                                              │
          │   ⑥ verifier.check(intent)  ──► accepted? (agent's own claim ignored)     │
          │            │                                                              │
          │            ▼                                                              │
          │   ⑦ world.apply(intent)     ──► state changes (physics / rules)           │
          │   ⑧ field.deposit(signals)  ──► visible to others NEXT tick               │
          │   ⑨ events.append(...)      ──► every view, intent, signal, outcome       │
          │                                                                           │
          │  end of tick: field.decay()  ·  world.step_environment()  ·  metrics      │
          └───────────────────────────────────────────────────────────────────────────┘
```

Key properties:

- **Locality by type.** A policy receives a `LocalView`; it has no handle to the world.
- **Deferred visibility.** Signals deposited at tick *t* are sensed at *t+1* — no agent
  sees another's same-tick output, so order of agents does not change results.
- **Outcomes are owned by the verifier.** "I delivered the drug" from an agent is a
  claim; only the verifier writes the outcome.
- **Deterministic.** Seeded RNG per agent per tick; LLM responses cached by request
  hash → a run can be replayed exactly.

---

## 5. The `Signal` — one envelope for pheromones AND LLM messages

```
Signal {
  id            content hash (stable, dedupable)
  sender        agent id
  kind          found | claimed | depleted | alarm | recruit | claim | critique | ...
  scope         run id + arm (signals never cross experimental arms)
  where         pos (spatial worlds)  or  topic (task / QA worlds)
  payload       small typed dict (world-defined schema)
  cites[]       evidence / record ids this signal relies on
  parent_ids[]  signals this one responds to (causality)
  revision      world revision the sender observed
  ttl           ticks until it expires
}
```

Same object, two worlds:

```
Tumor:        Signal(kind="found",   where=pos(412,318), payload={"cells":7}, ttl=5)
Research QA:  Signal(kind="found",   where=topic("q17"), cites=["e3"],        ttl=1)
```

Lifecycle:

```
 emitted ──► admission ──┬── rejected (logged with reason)
                         │
                         └── deposited in field ──► sensed by agents in range/topic
                                    │
                                    ├── ttl reaches 0 ──────────────► expired
                                    └── world revision moves past ──► stale (not sensed)
```

Field backends:

| Backend | Used by | "Nearby" means |
|---|---|---|
| `GridField` | tumor, foraging | spatial radius; intensity diffuses/decays (via biofvm for tumor) |
| `BoardField` | research QA, task DAG | same topic; round-based TTL (lifted from `swarm_core._run_signal_board`) |

---

## 6. Evidence memory — what the swarm "knows" and whether to trust it

Signals are short-lived. **Memory records** are durable facts with provenance.

```
Record {
  id          content hash
  source      who produced it (agent / world / verifier)
  source_rev  world revision it was based on
  kind        claim | procedure | outcome
  status      candidate | admitted | invalidated | contradicted
  depends_on  [record ids]
  scope       run + arm
}
```

Lifecycle:

```
                ┌──────────── contradiction recorded ────────────┐
                │                                                ▼
 candidate ──► admitted ──► (used by agents) ──► source replaced ──► invalidated
     │                                               │
     └── rejected                                    └── cascade: every record that
                                                         depends_on it → invalidated
```

Rules the kernel enforces:

1. Agents act only on **admitted** records.
2. **Outcome** records are written only by the verifier.
3. Replacing a source **cascades** invalidation to all dependents.
4. Contradicting records block dependent procedures until resolved.
5. Records never leak across experimental arms.

Source: this is the `HiveMemoryStore` design from the DeSci paper (§3.2), which
produced the paper's "0 unsafe acts under drift" result.

---

## 7. Provenance — two levels, one event log

```
 DURING THE RUN (fact-level)                     AFTER THE RUN (run-level)
 ───────────────────────────                     ─────────────────────────
 signals, memory records, intents,
 admissions, verifier outcomes
            │
            ▼
   events.jsonl  (append-only, ordered) ──► trace_hash ──► proof bundle
                                                             │  run_id, config_hash,
                                                             │  seed, metrics,
                                                             │  trust_tier
                                                             ▼
                                                     provenance outbox (async)
                                                        ├── IPFS pin (CID)
                                                        └── chain (5 public values)
                                                            mock → proof_staged →
                                                            verified_onchain
```

- **Fact-level** answers: *why did agent 3 target that cell, and what was it trusting?*
- **Run-level** answers: *is this run real and reproducible?*
- **Replay** = feed the same config + seed + cached LLM responses → same event log →
  same `trace_hash`.
- Chain writes **never** run inside the tick loop.

---

## 8. Worlds — what each one supplies

A world implements three things; everything else comes from the kernel.

```
class World(Protocol):
    def local_view(self, agent) -> LocalView    # what can this agent see?
    def apply(self, intent) -> Outcome          # what happens when it acts?
    def metrics(self) -> dict                   # how is the run scored?
    (+ a Verifier and a signal payload schema)
```

| | Tumor | Foraging | Task DAG | Research QA |
|---|---|---|---|---|
| State | cells, O₂, drug, vessels | grid, food, nest | samples, resources, deps | question, evidence |
| Actions | move, target, deliver | follow target / sweep | propose plan nodes | answer, cite, abstain |
| Score | kill rate, drug efficiency | sweep moves | plan executes | correct answer |
| Rule brain | chemotaxis (ported) | systematic sweep | scripted proposer | — |
| LLM brain | shared `LLMPolicy` | shared `LLMPolicy` | shared `LLMPolicy` | shared `LLMPolicy` |
| Coordination | **kernel (identical)** | **kernel** | **kernel** | **kernel** |

The headline experiment this enables: *flip the same kernel switch (memory,
signals, Queen-emitter) across all worlds and test whether the effect holds
everywhere* — not just in the one world it was tuned in.

---

## 9. What exists vs what is new

| Category | Contents | Size |
|---|---|---|
| **Reused as-is** | `biofvm.py`, `tumor_environment.py`, `brats_loader.py`, `backend/chain/*`, `research_data.py`, `source_calculation.py` | ~5,100 LOC |
| **Ported** (logic exists, relocated) | nanobot behavior, Queen, tumor step loop, `swarm_core` protocols, TTL board, E13 / E15 harnesses, replay/trace hash, local model client, experiment stats | ~3,700 of new LOC |
| **Genuinely new** | `Signal`, `SignalField`, evidence memory, admission, verifier protocol, `World`/`Policy`/`LocalView` types, scheduler, typed tumor signals, provenance outbox, cross-world runner, typed settings, routers | ~3,500 of new LOC |
| **Deleted at cutover** | `simulation.py`, `app.py`, `tumor_hunt.py`, `litellm_client.py`, `api_server.py`, most of `main.py`, eventually `nanobot_simulation.py` | ~−5,000 LOC |

Estimated new code **~7,200 LOC** + tests **~6,500 LOC**.

```
antelligence/
├── kernel/        signal 150 · field 300 · memory 450 · admission 300 · verifier 200
│                  types 150 · scheduler 300 · events 250 · policies 350      ~2,450
├── providers/                                                               ~350
├── worlds/        tumor 900 · foraging 600 · task_dag 700 · research_qa 600 ~2,800
├── provenance/                                                              ~350
├── experiments/                                                             ~450
├── api/                                                                     ~500
└── settings.py + cli                                                        ~300
```

---

## 10. Phases and dependency graph

```
            P1 kernel core
                 │
            P2 trust layer
                 │
            P3 providers + policies
       ┌─────────┼──────────┐
       ▼         ▼          ▼
   P4 foraging  P5 tumor  P6 research QA      ← independent; cherry-pickable
     + dag       world     world
       └─────────┼──────────┘
                 ▼
            P7 experiments + provenance + API
                 │
            P8 cutover (delete legacy, repoint routes)
```

| # | Phase | New | Tests | Exit gate |
|---|---|---|---|---|
| P1 | Kernel core: signal, field, types, events, scheduler | ~1,150 | ~1,200 | Toy world deterministic; same seed → same trace hash |
| P2 | Trust layer: memory, admission, verifier | ~950 | ~1,200 | Stale fact invalidated → agent refuses; tampered/expired signal rejected; self-claims ignored |
| P3 | Providers + policies | ~700 | ~600 | LLM policy runs offline on fake provider; budget cap stops cleanly |
| P4 | Foraging + task-DAG worlds | ~1,300 | ~1,100 | Reproduces published E13 / E15 summaries from cached responses |
| P5 | Tumor world | ~900 | ~900 | Rule policy matches legacy metrics within tolerance over N seeds; typed-signal arms added |
| P6 | Research QA world | ~600 | ~600 | Existing `swarm_core` tests pass through the engine |
| P7 | Experiments + provenance + API | ~1,300 | ~900 | Cross-world experiment runs via API; proof bundle from event log; chain off the tick loop |
| P8 | Cutover | ~200 shims | — | Frontend routes served by engine; legacy removed |

---

## 11. Branch and commit strategy

```
main
 └── engine/v1
      ├── P1  feat(engine): kernel core            tag engine-p1
      ├── P2  feat(engine): trust layer            tag engine-p2
      ├── P3  feat(engine): providers + policies   tag engine-p3
      ├── P4  feat(engine): foraging + task-dag    tag engine-p4
      ├── P5  feat(engine): tumor world            tag engine-p5
      ├── P6  feat(engine): research-qa world      tag engine-p6
      ├── P7  feat(engine): experiments + API      tag engine-p7
      └── P8  refactor!: cutover, remove legacy    tag engine-p8
```

1. Every commit passes the **full** test suite (legacy + engine).
2. P1–P7 **only add files** under `antelligence/` and `tests/engine/`.
3. Shared files (`pyproject.toml`) are touched once, in P1.
4. World commits never touch each other's folders → P4/P5/P6 cherry-pick independently.
5. P8 is the only destructive commit and stays last.
6. Stacked PRs (P1–P3, then P4 / P5 / P6) are optional for parallel review.

---

## 12. Risks and open decisions

**Risks**

- **Hive code is not in this repo.** Paper imports `backend.research_hive_memory`,
  `research_hive_communication`, `research_hive_contracts` — present on no branch.
  Recovering it (review branch `review/hive-fit-20260911` or external volume) lets P2
  port instead of re-derive, and guarantees parity with published results.
- **Legacy tumor sim is not bit-reproducible** (global `np.random` / `random`). P5 gate
  is metric parity within tolerance, after which the engine becomes the reference.
- **Frontend** changes are out of scope; P8 preserves response shapes.

**Decisions**

1. Recover the hive code, or rebuild memory/admission from the paper spec?
2. Keep the legacy ant sim (`/simulation/run`) as a world, or drop it?
3. Build all 8 phases, or stop after P5 (~5,000 LOC) and reassess?

---

## 13. Honest scope of claims

Consistent with `VISION.md` and `RULES.md`: the engine is research and provenance
infrastructure. The tumor world is a synthetic 2D model, not clinical software.
A cross-world result, positive or negative, is reported with the same pre-registered,
paired-seed methodology as the DeSci paper; agreement is not truth, and `staged` is
not `verified_onchain`.
