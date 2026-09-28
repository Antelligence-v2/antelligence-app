# Frontend Refactor v1 — Plan

**Status:** in progress (11/14 steps + landing page) · **Branch:** `kashyap/frontend-refactor-v1` (from `engine/v1`) · one commit per step
**Supersedes:** [frontend-port](2026-09-27-frontend-port.md). That plan assumed the engine didn't exist yet.
**Builds on:** [engine kernel](2026-09-27-antelligence-engine-kernel.md) · slots in: [3D visualization](2026-09-27-3d-tumor-visualization.md)

## Goal

A frontend that feels like a **precision research instrument**: calm, fast and
legible, with every number traceable to its evidence. One shell and one run
experience for every engine world, where the engine's trust machinery (signals,
verifier verdicts, hash-chained provenance) is something you can *see*.

## Design direction

| Principle | In practice |
|---|---|
| **Dark-first, quiet** | Neutral graphite surfaces, one accent (signal cyan), semantic colors only for verdicts. No gradients or decorative imagery; the data is the visual. A light theme ships too. |
| **Typographic hierarchy** | Inter Variable for UI, JetBrains Mono for hashes, ids and numbers. Tabular numerals everywhere. |
| **Motion with purpose** | 150–250 ms springs (framer-motion) for layout and panel changes. Playback at 60 fps. `prefers-reduced-motion` is honored. |
| **Keyboard-native** | ⌘K command palette; `space` play/pause, `←/→` step a tick, `[ ]` jump between events, `g w / g r / g e` to navigate. |
| **Honest by design** | Trust tier and verdict are always visible. Caveats sit next to results, never hidden. "Staged" never looks like "verified". |
| **No jank** | Skeletons that match the final layout, no layout shift, virtualized lists, lazy-loaded routes, canvas rendering for spatial views. |

```
┌──────┬───────────────────────────────────────────────────────────────────────────┐
│ ◈    │  tumor · rule · case 3            ● safe_incomplete   ◇ local_replay  ⌘K  │
│      ├───────────────────────────────────────────────────────────────────────────┤
│ Wld  │ ┌─ kill rate ─┐┌─ living ────┐┌─ deliveries ┐┌─ unsafe ────┐              │
│ Run  │ │ 17.1%  ▁▃▅▇ ││ 97 / 117    ││ 20          ││ 0           │              │
│ Exp  │ └─────────────┘└─────────────┘└─────────────┘└─────────────┘              │
│ Rsch │ ┌──────────── viewport (canvas) ─────────────┐┌─ inspector ─────────────┐ │
│      │ │                                             ││ bot-003 · tick 42       │ │
│      │ │      ·  ◉   ·      bots, cells, trails      ││ observed  3 signals     │ │
│      │ │   ◉      ·    ◉                             ││ decided   target #72    │ │
│      │ │                                             ││ outcome   ✓ accepted    │ │
│      │ └─────────────────────────────────────────────┘│ hash 9f3a…e1 ← 77c0…    │ │
│      │  ▶  ━━━━━━━━━━━●──────────────  tick 42 / 150  └─────────────────────────┘ │
└──────┴───────────────────────────────────────────────────────────────────────────┘
```

## Engine API this builds on (verified live)

```
GET  /engine/worlds                 name, arms (+descriptions), params {default,min,max}, metrics
POST /engine/runs                   {world, arm, case, params} → record + bundle   (synchronous)
GET  /engine/runs/{id}              record, verdict, bundle, outbox status
GET  /engine/runs/{id}/events       paginated hash-chained events (observed, decided, outcome,
                                    signal_*, intent_blocked, memory_changed, tick_ended, …)
POST /engine/runs/{id}/verify       replay the bundle → match / mismatch
POST /engine/experiments            arms × cases → paired report (sign test, Wilson CI, caveats)
GET  /engine/experiments[/{id}]
```

**Gap:** the events hold no spatial state, so a replay viewport needs per-tick
frames (step 9). The engine API also only accepts loopback requests with local
origins, which is fine for dev. Deployment is a separate decision.

## Commits

Each commit leaves `npm run check` green: lint, typecheck, unit tests and build.

```
 Foundation            Core experience                    Depth                  Finish
 ──────────            ───────────────                    ─────                  ──────
 1 ─ 2 ─ 3 ─ 4 ──────► 5 worlds ─ 6 run ─ 7 inspector ─┬─► 9 frames ─ 10 viewport ─► 13 polish ─ 14 legacy
                                          8 provenance ┘   11 experiments
                                                           12 research
```

| # | Commit | What lands | Done when |
|---|---|---|---|
| 1 | `chore(frontend): check pipeline` | `typecheck`, `test` and `check` scripts. Stricter TS where it's cheap. Stale `dist/` removed from git. | `npm run check` passes in CI |
| 2 | `feat(ui): design system` | Tokens (color, type, space, radius, motion, elevation) for dark and light. Self-hosted Inter and JetBrains Mono (offline-safe). shadcn primitives restyled. The sand/amber theme retired. Dev-only `/design` page. | Every primitive renders correctly in both themes |
| 3 | `feat(ui): app shell` | Left rail nav, top bar, ⌘K palette, theme toggle, route transitions, lazy routes, error boundary. Legacy pages move under **Legacy**, unchanged. | Every existing page is reachable in the new shell |
| 4 | `feat(api): typed engine client` | `api/` layer: react-query client, query keys, error normalization. Types generated from OpenAPI (`npm run gen:api`). Inline `axios` calls moved out of pages. | No `axios` import in pages or components |
| 5 | `feat(worlds): catalog + launcher` | `/` shows world cards (description, arms, primary metric). `/w/:world` has arm segmented control, param sliders from schema bounds, case picker, and a launch that goes to the new run. | A run can be launched for any world |
| 6 | `feat(runs): run page` | `/runs/:id`: header (world, arm, case, verdict, trust tier), KPI tiles with sparklines from `tick_ended`, a metric timeline, and a tick scrubber with keyboard control. | Tick-by-tick metrics can be scrubbed smoothly |
| 7 | `feat(runs): event inspector` | Virtualized event stream, filterable by type and agent. Agent swimlanes (decided / outcome / blocked per tick). Event drawer: data, cites, rationale, `prev_hash → hash`. Synced to the scrubber. | Clicking any agent at any tick shows what it saw, decided and got |
| 8 | `feat(runs): provenance + verify` | Hash panel (config, trace, bundle), trust tier, outbox state. **Verify replay** runs the replay and shows the result (match ✓ / mismatch ✕). Copy buttons and bundle download. | A run can be independently replayed from the UI |
| 9 | `feat(engine): per-tick frames` ⚠ backend | `World.snapshot()` for tumor and foraging, stored as `frames.jsonl` next to the events. Kept out of the hash chain, so trace hashes don't change. Adds `GET /engine/runs/{id}/frames`, with tests. Coordinate with the engine session, which is editing `worlds/tumor/world.py`. | Frames are served and existing trace hashes are unchanged |
| 10 | `feat(viewport): 2D replay` | Canvas renderer registry per world: tumor (cells by state, vessels, bots with trails) and foraging (grid, food, nest, agents). Interpolated 60 fps playback, linked to the inspector (click a bot to select it). 3D slots in here later as `Viewport3D`. | Tumor and foraging runs play back smoothly |
| 11 | `feat(experiments): engine lab` | Builder (world, arms, cases, baseline). Report: arm table, forest plot of effect versus baseline with sign-test p and Wilson CIs, verdict breakdown, and the caveats block. Every row links to its run. | One experiment runs end-to-end in the UI |
| 12 | `refactor(research): move into shell` | The Research Workbench adopts the design system and api layer. Its logic and tests are unchanged. | Existing research tests pass |
| 13 | `polish: states, a11y, perf` | Empty, loading and error states everywhere. Focus rings, contrast, reduced motion. Responsive to 1280 px and tablet. Bundle split with a size budget. | Lighthouse a11y ≥ 95; no layout shift |
| 14 | `refactor!: retire legacy UI` | Remove the legacy ant, tumor-hunt and old tumor pages (~4,300 LOC) and redirect the old routes. **This needs your go-ahead** (open product decision). | No legacy endpoints are called |

**Estimate:** ~5,500 new LOC plus ~1,500 of tests, and ~4,300 LOC deleted in step 14.
Steps 1–8 are frontend-only and don't depend on the engine session's in-progress work.

## Stack additions

`framer-motion` (motion) · `@tanstack/react-virtual` (event stream) ·
`@fontsource-variable/inter`, `@fontsource/jetbrains-mono` (self-hosted fonts) ·
`openapi-typescript` (dev, type generation). Already present and kept: React 18,
Vite, Tailwind, shadcn/Radix, react-query, recharts (restyled), cmdk, lucide.

## Testing

- **Unit** (`node:test`, the existing pattern): API mappers, event reducers (events → per-tick agent state), playback clock, frame interpolation, schema-to-form.
- **Browser** (Playwright against a real backend, the existing pattern): launch → run → scrub → inspect → verify, plus experiment end-to-end.
- **Visual:** screenshots of key screens in both themes, attached to each UI commit.

## Decisions (defaults in bold)

1. Theme: **dark-first plus light**, or light-first?
2. Legacy ant sim and Tumor Hunt: keep under **Legacy until step 14**, then delete (needs your OK).
3. Charts: **restyle recharts**, or switch to visx for finer control (+1 dependency)?
4. Long runs: **synchronous with a progress shimmer** now, streaming (SSE) once the engine exposes it.

## Progress (2026-09-27)

| # | Commit | Notes |
|---|---|---|
| 1 | `35bd75d` | The 30 existing unit tests never ran before; legacy files with real type errors marked `@ts-nocheck` until step 14 |
| 2 | `6cf509c` | |
| 3 | `14aec55` | Legacy pages kept their URLs; only the ant sim moved from `/` to `/ants` |
| 4 | `0cf9a07` | **Deviation:** zod runtime contracts instead of OpenAPI codegen (engine returns plain dicts, so codegen yields `unknown`). Legacy pages keep inline axios until step 14 |
| 5 | `507a2e9` | |
| 6 | `96419f4` | |
| 7 | `37603bc` | |
| 8 | `302381d` | |
| — | `3843a60` | **Added:** photographic landing page at `/`; world catalog moved to `/worlds`; legacy IntroPage deleted |
| 11 | `cf98309` | Engine lab lives at `/lab` (legacy lab keeps `/experiments`); shows the engine's optional recommendation |
| 12 | `ca9ea8e` | |
| 13 | `ef3d8af` | Entry chunk 203 → 153 kB gzip with a 170 kB budget in `npm run check`; axe WCAG A/AA clean in both themes |
| 9 | — | **Blocked:** needs `runner.py`, `app.py`, `worlds/tumor/world.py`, which hold another session's uncommitted recommendation feature |
| 10 | — | Waits on 9. Note: foraging and tumor outcomes already carry `effects.pos`, which covers bot positions but not cells or vessels |
| 14 | — | Waits on a product decision (keep the ant sim as a world or delete it) |
