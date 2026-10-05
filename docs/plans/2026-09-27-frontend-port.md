# Frontend Port — Plan

**Status:** superseded by [frontend-refactor-v1](2026-09-27-frontend-refactor-v1.md) · **Owner:** Kashyap
**Companions:** [engine kernel](2026-09-27-antelligence-engine-kernel.md) ·
[3D visualization](2026-09-27-3d-tumor-visualization.md)

## Goal

Move the frontend from **one page per backend** to **one run UI for every world**,
matching the engine's "one kernel, many worlds" design. The UI should also make
the engine's new value visible: signals, memory trust, verifier outcomes and
provenance.

## Today (~8,700 LOC in `frontend/src`, excluding `ui/`)

```
 Route            Page (LOC)                  Backend                     Fate under engine
 ───────────────  ──────────────────────────  ──────────────────────────  ─────────────────────
 /                Index + IntroPage (777)     /simulation/run             legacy ant sim → ?
 /comparison      SimulationComparison (439)  /simulation/run, /compare   legacy ant sim → ?
 /tumor           TumorSimulation (484)       /simulation/tumor/run,runs  → tumor world
 /tumor-hunt      TumorHunt (416)             /simulation/tumor/hunt      tumor_hunt.py deleted
 /experiments     ExperimentLab (721)         /experiments/*              → cross-world lab
 /research        ResearchWorkbench (437)     /research/*                 → research_qa world
```

**Problems to fix in the port**
- API calls are inline `axios` in pages and components (only research has an `api` module).
- Types are hand-written copies of the Pydantic schemas (`interface TumorSimulationConfig` in pages), so they drift.
- Every page has its own grid, playback and charts, and none of it is shared.
- Runs block on one big request (tumor hunt waits up to 300 s). Only research polls for progress.
- `@tanstack/react-query` is installed but unused.
- There's no UI for fact-level provenance (signals, memory, verifier), which is the engine's main feature.

## Target shape

```
 ┌──────────────────────────────── RunShell (every world) ────────────────────────────────┐
 │ ┌─ Controls ──────┐ ┌─ Viewport ─────────────────────────┐ ┌─ Inspector ─────────────┐ │
 │ │ world config    │ │ world renderer (2D / 3D)           │ │ Metrics                 │ │
 │ │ (from schema)   │ │                                    │ │ Signals   (live field)  │ │
 │ │ arms: memory,   │ │                                    │ │ Memory    (lineage)     │ │
 │ │ signals, queen  │ │                                    │ │ Verifier  (outcomes)    │ │
 │ │ seed, budget    │ │                                    │ │ Provenance (trust tier) │ │
 │ └─────────────────┘ └────────────────────────────────────┘ └─────────────────────────┘ │
 │ ─── Timeline: ▶ ▮▮ ───●────────────── tick 42/200 · events for this tick ───────────── │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

```
frontend/src/
├── api/          client.ts (axios + react-query) · generated.ts (from OpenAPI)
│                 runs.ts · worlds.ts · experiments.ts · research.ts
├── run/          RunShell · useRun (SSE → poll fallback) · usePlayback (interpolation)
│                 frames.ts (binary decoder, shared with the 3D plan's frame contract)
├── worlds/       registry.ts → { tumor, foraging, task_dag, research_qa }
│   └── <world>/  Controls? · Viewport2D · Viewport3D? · metrics.ts
├── inspect/      SignalPanel · MemoryLineage · VerifierLog · EventTimeline · RunProvenance
├── pages/        Home · WorldRun · ExperimentLab · ResearchWorkbench · NotFound
└── components/ui (shadcn, unchanged)
```

**World registry:** each world ships only what's specific to it; everything else is shared.

```
worlds.tumor = {
  label: "Tumor", viewports: { "2d": TumorGrid, "3d": TumorScene3D },
  controls: TumorControls,          // optional; default = form generated from config schema
  metrics: ["kill_rate", "drug_efficiency"],
}
```

**Routes (old ones redirect):**

```
/                      Home (IntroPage + world cards)
/w/:world              new run for a world            ← /tumor, /tumor-hunt redirect here
/runs/:runId           replay any run, any world      ← /tumor?run=… redirects here
/experiments[/:id]     cross-world experiment lab
/research[/:id]        research workbench (research_qa world)
```

## Backend contract needed (engine P7)

```
GET  /worlds                     catalog + JSON Schema of each world's config
POST /runs                       {world, config, arms, seed} → {run_id}
GET  /runs/{id}                  status, metrics, provenance, trust_tier
GET  /runs/{id}/stream           SSE: progress, tick metrics      (fallback: poll)
GET  /runs/{id}/frames           binary frames (3D plan's frame contract)
GET  /runs/{id}/events?tick=…    signals, memory records, intents, verifier outcomes
POST /experiments                arms × seeds × worlds
```

Types are generated from FastAPI's OpenAPI (`openapi-typescript`) and never
hand-written. CI fails if `generated.ts` is out of date.

## Phases

```
 Engine:  P1 ─ P2 ─ P3 ─┬─ P4 ─┬─ P7 API ─────────────── P8 cutover
                        ├─ P5 ─┤
                        └─ P6 ─┘
                                  │                       │
 Frontend: F0 ──── F1 ────────────┴── F2 ──── F3 ─────────┴── F4
           (now)   (now, on           (worlds    (lab +       (delete
                    adapters)          live)      research)     legacy)
```

**F0: Foundations** — starts now, no engine needed. ~800 LOC.
- Create `api/` with react-query and move every inline `axios` call into it. No behaviour change.
- Generate types from today's OpenAPI and replace the hand-written page interfaces.
- One shared trust-tier badge (mock / staged / verified), used everywhere.
- *Done when:* no `axios` calls remain in pages or components, and the existing browser tests pass.

**F1: RunShell and playback** — starts now, using adapters. ~1,200 LOC.
- `RunShell`, `usePlayback`, and the timeline with interpolation.
- `frames.ts` decoder (the same contract as the 3D plan).
- An adapter turns today's `/simulation/tumor/run` response into frames, so `/tumor` moves onto RunShell before the engine exists.
- 3D plan T2 lands here as `worlds/tumor/Viewport3D`.
- *Done when:* `/tumor` runs inside RunShell with the same results, plus a 2D/3D toggle.

**F2: Worlds and inspector** — after engine P7. ~1,800 LOC.
- `GET /worlds` catalog, the config form generated from the schema, and the `/w/:world` and `/runs/:id` routes.
- Tumor switches from the adapter to the engine API. Foraging and task-DAG get 2D viewports.
- Inspector panels: signals, memory lineage (the cascade of invalidations), verifier log, event timeline.
- Live progress over SSE, replacing the 300 s blocking requests.
- *Done when:* any world can be run and replayed, and clicking an agent shows what it sensed and trusted that tick.

**F3: Experiment Lab and Research** — after engine P6 and P7. ~600 LOC.
- The Experiment Lab gets a world picker and cross-world arms (memory/signals on vs off in every world).
- Research Workbench is pointed at the research_qa world endpoints; its UI mostly stays.
- *Done when:* one experiment compares the same switch across 2 or more worlds.

**F4: Cutover** — with engine P8. About −4,000 LOC.
- Delete the legacy ant UI (~3,700 LOC: Index sim, Comparison, Simulation*, PerformanceCharts, BlockchainMetrics, HistoricalPerformance, `simulationHistory`), unless it's kept as a world.
- Delete TumorHunt (~630 LOC). Wave spawning becomes a tumor-world option if still wanted.
- Remove the adapters and add redirects for old routes.
- *Done when:* every route is served by the engine API and no legacy endpoint is called.

**Total:** ~4,400 new LOC plus tests, and ~4,000 LOC deleted. The net code size stays about the same while supporting 4 worlds instead of 3 bespoke pages.

## Testing

Follows the existing pattern in `frontend/tests/`:
- **Unit** (`node:test`): API mappers, frame decoder, playback interpolation, world registry, schema-to-form generation.
- **Browser** (Playwright, real backend): one smoke test per world route, plus replay and inspector.
- **Parity:** during F1 and F2, the same seed must show the same tumor metrics through the adapter and through the engine.

## Decisions needed

1. **Legacy ant sim:** keep it as a world, or delete it? This drives ~3,700 LOC in F4. The engine plan leaves it open too.
2. **Tumor Hunt:** drop it, or keep wave spawning as a tumor-world option?
3. **Research Workbench:** keep its own UI (recommended; it's mature and tested), or fully merge it into RunShell?
4. **Progress:** SSE (recommended) or polling only?

## Risks

- **The engine API (P7) is late in the sequence.** F0 and F1 are deliberately independent so the frontend isn't blocked.
- **Generated types will churn** while the engine API settles. Pin the OpenAPI snapshot per engine phase.
- **Inspector volume:** event logs for long runs are large. Fetch per tick and paginate; never load everything.
