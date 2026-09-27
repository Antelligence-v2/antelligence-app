# 3D Tumor Visualization — Plan

**Status:** proposed · **Owner:** Kashyap · **Branch:** `kashyap/main-sep22`

## Goal

Replace the flat 2D tumor grid with a high-quality, interactive 3D render driven
by real simulation data. The render should work for exploration and for talks,
the paper and demos.

## Today

- `biofvm.py` already supports 3D diffusion (`dimensionality`, 3D Laplacian).
- `brats_loader.py` loads 3D NIfTI volumes but uses a single slice.
- Nanobots are 2D only (`position[:2]`, fixed 30 µm/step).
- Frontend draws 2D grids (`TumorSimulationGrid.tsx`) from one large JSON `history`.

## Architecture

```
 BACKEND                                        FRONTEND (React Three Fiber)
 ───────                                        ────────────────────────────
 tumor world (3D)                               <TumorScene3D>
   │                                              ├─ TumorMesh      glassy shells
   ├─ BraTS volume ─► marching cubes ─► GLB ────► ├─ CellInstances  colour by state
   │                  (once per run, cached)      ├─ VesselTubes
   │                                              ├─ BotInstances   glow + trails
   ├─ every step ──► binary frame ─────────────►  ├─ FieldVolume    drug cloud
   │   positions, states (Float32/Uint8)          ├─ SlicePlanes
   │                                              └─ PostFX         bloom, AO, tone map
   └─ every Nth step ─► field volume ─────────►
       (≤128³, compressed)                      Playback: interpolate frames → 60 fps
```

## Frame contract (agree first)

Both tracks build against this format, so the frontend can start on mock data.

```
run.glb                 tumor surface meshes (core / rim / edema)
frames.bin  per step:   bots  [N×3 f32 pos, N u8 state, N u8 payload]
                        cells [M×3 f32 pos, M u8 state]
fields/<name>_<step>    [X×Y×Z u8 normalized] + min/max
meta.json               units (µm), dims, dt, step count, field list
```

## Scene

| Element | Render | Signal |
|---|---|---|
| Tumor | Marching-cubes mesh from BraTS labels, transmission material | Real anatomy |
| Cells | Instanced spheres | Alive → hypoxic → dying → dead |
| Vessels | Tubes along 3D segments | Where bots enter |
| Nanobots | Instanced glowing capsules, fading trails | Swarm motion, payload |
| Drug / O₂ / pheromone | Raymarched volume + draggable slice planes | Where treatment reaches |

**Interaction:** orbit and zoom, timeline scrubber, cutaway slider, layer
toggles, click to inspect, camera presets, and video export.

**Quality modes:** *Presentation* (full post-processing) and *Interactive*
(effects off). Target: 60 fps with about 5k bots and 20k cells on a MacBook.

## Tickets

```
T1 Backend 3D (after engine P5) ┐
                                ├──► connect ──► T3 Polish
T2 Viewer v1 (mock data) ───────┘
```

**T1: Make the simulation 3D (backend).** About 1 week, ~1,500 LOC with tests.
- 3D positions for bots, cells and vessels; full BraTS volume; 3D diffusion on.
- Binary frame export plus a cached GLB tumor mesh.
- `dimensionality=2|3` flag, so 2D mode and existing tests are unchanged.
- *Done when:* a 3D run exports frames per the contract, and the 2D tests still pass.

**T2: 3D viewer v1 (frontend).** About 1.5 weeks, ~1,800 LOC with tests.
- R3F scene with a 2D/3D toggle on `/tumor`.
- Tumor mesh, cells, vessels, and bots with trails.
- Timeline playback with frame interpolation.
- *Done when:* a real 3D run plays back smoothly in the browser.

**T3: Presentation quality (frontend).** About 1.5 weeks, ~1,700 LOC with tests.
- Volume-rendered fields and slice planes.
- Post-processing and quality modes.
- Inspect panel, camera presets, video export.
- *Done when:* a polished video of a run can be recorded.

**Total:** about 3.5 weeks, ~5,000 LOC including tests. T2 runs alongside T1 on mock data.

## Sequencing with the engine refactor

Companion to [`2026-09-27-antelligence-engine-kernel.md`](2026-09-27-antelligence-engine-kernel.md).

```
Engine:  P1 kernel ─► P2 trust ─► P3 policies ─► P5 tumor world (2D parity) ─► T1 3D ─┐
                                                                                      ├─► T3
3D UI:   frame contract ─► T2 viewer v1 on mock data ─────────────────────────────────┘
```

- **T1 is built in `antelligence/worlds/tumor/`, after the engine's P5 gate.**
  It isn't built in the legacy `nanobot_simulation.py`, so nothing is written twice.
  3D starts only once the 2D tumor world matches the legacy metrics.
- **The frame export comes from the engine event log** (`events.py`): positions and
  states per tick, plus field snapshots. It isn't a separate output path.
- **Positions are N-dimensional from P1**, and `GridField` wraps `biofvm`, which
  already supports 3D. That keeps T1 small.
- **The engine plan leaves the frontend out of scope**, so T2 and T3 are the
  frontend track and can start immediately against the frame contract.

## Out of scope

Realistic nanoparticle physics is a separate track: Brownian motion, active vs
passive bots, BBB extravasation, clearance. This plan makes the render real;
that track makes the movement real.

## Risks

- **Volume rendering (T3)** is the hardest part. The fallback is slice planes only.
- **Frame size** with large N. Mitigate by sending every Nth frame and interpolating.
- **BraTS data** may be missing locally. Fall back to a procedural 3D tumor.
