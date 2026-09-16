# Antelligence Glass Box Implementation Roadmap

Goal: move from simulation-only Antelligence to a physical ESP32 swarm demo.

## Current state

Already built in repo:
- ant colony simulation
- tumor nanobot simulation
- Tumor Hunt v2
- knowledge graph layer
- message bus / typed cargo routing concepts
- BraTS real MRI integration
- CED comparison baseline
- patent draft

Missing for Stage 2:
- physical robot server
- firmware contract
- overhead localization pipeline
- physical arena mission mode

## Phase GB-0 — protocol freeze

Deliverables:
- finalize `docs/ESP32_GLASS_BOX_SPEC.md`
- freeze worker <-> server packet schema
- define stale-command safety behavior

Exit criteria:
- operator approves packet schema and safety timeout budget

## Phase GB-1 — physical arena server

Deliverables:
- `backend/glass_box_server.py`
- REST heartbeat endpoint
- pheromone 2D field state
- world state dashboard endpoint
- bot registration endpoint
- mission start/stop endpoint

Exit criteria:
- simulated bots can talk to server using exact ESP32 packet schema

## Phase GB-2 — simulated hardware mode

Deliverables:
- `backend/physical_arena_sim.py`
- 2D arena with collision + localization noise
- uses same heartbeat/command loop as physical bots
- latency injection settings (50/100/200/300/500 ms)

Exit criteria:
- physical protocol works in simulation under latency
- safe-stop behavior validated

## Phase GB-3 — overhead localization

Deliverables:
- camera tracking service
- AprilTag/ArUco pose extraction
- bot pose broadcast to server
- calibration procedure for arena coordinates

Exit criteria:
- x/y/heading estimated in real time for 4+ bots

## Phase GB-4 — ESP32 reference firmware

Deliverables:
- PlatformIO project
- Wi‑Fi client
- heartbeat loop
- command expiry watchdog
- motor control abstraction
- LED state debugging

Exit criteria:
- one real bot can connect, move, and safe-stop reliably

## Phase GB-5 — multi-bot experiment pack

Deliverables:
- experiment scripts
- target layouts
- metrics export
- benchmark report templates

Experiments:
- random baseline
- pheromone only
- Queen + pheromone
- latency stress test
- disconnect safety test

Exit criteria:
- reproducible benchmark report from real arena

## Phase GB-6 — publication / patent support

Deliverables:
- figures
- metrics tables
- hardware photos
- protocol diagrams
- provisional patent appendix references

## Recommended immediate next action

Build GB-1 and GB-2 before touching hardware.

Reason:
- locks the protocol
- lets firmware be thin
- reduces wasted electronics work
- makes ESP32 assembly almost mechanical
