# Antelligence Stage 2 — ESP32 Glass Box Swarm Specification

Status: design spec
Target stage: physical proof-of-concept before medical hardware
Primary goal: prove Antelligence as a real-world architecture, not just a simulation

## 1. Purpose

Stage 2 is the first physical embodiment of Antelligence.

It is not a medical deployment.
It is a glass-box robotics experiment that proves:
- hierarchical Queen/worker coordination works on physical agents
- pheromone-style indirect communication works outside pure software
- worker agents can act under cloud latency constraints
- the same software architecture can later power medical nanobots

This stage should answer one question clearly:
Can a swarm of cheap physical agents, controlled by the Antelligence architecture, perform coordinated target-seeking and delivery behavior better than naive direct control?

## 2. Why ESP32

Use ESP32-S3-class bots for Stage 2 because they are:
- cheap
- Wi‑Fi native
- easy to prototype
- easy to replace
- close to the future medical architecture in communication style

We are not trying to miniaturize first.
We are trying to prove the architecture first.

Stage progression:
- Stage 1: software simulation
- Stage 2: ESP32 glass-box robots
- Stage 3: miniaturized medical hardware

## 3. Core architectural principle

The physical bots do not run the full intelligence stack locally.
They are reflexive edge devices.
The cloud/local server is the brain.

Physical bot responsibilities:
- read local sensors
- estimate pose/position
- upload state to server
- execute motion command
- execute safe dye/drug release command only when authorized
- enter safe mode on communication loss

Server responsibilities:
- maintain global pheromone field
- maintain world model
- run worker LLM decisions
- run Queen strategic coordination
- log immutable events
- compute safety envelopes
- reject unsafe delivery actions

## 4. Safety principle

Never let communication failure become harmful behavior.

Bad fallback:
- keep moving
- keep releasing
- continue stale command indefinitely

Required fallback:
- continue motion only for a bounded timeout window
- never release outside authorized delivery window
- stop release immediately on stale command timeout
- optionally brake/hold if localization confidence drops

For Stage 2 glass-box hardware, safety contract is:
- if no command refresh in 300 ms: continue prior steering for at most 500 ms total
- if no command refresh after 500 ms: stop motors
- if no explicit release authorization in current command frame: release actuator OFF
- if bot position leaves allowed arena polygon: force STOP

For future medical hardware, this becomes stricter:
- release only inside approved tumor boundary confidence region
- no stale release authorization survives command expiration

## 5. Latency assumptions

Design assumption from operator:
- 150–200 ms end-to-end latency due to API/network

So Stage 2 control loop is split:
- local reflex loop: 20–50 Hz on microcontroller
- server decision loop: 5–7 Hz effective
- Queen strategic loop: 0.2–1 Hz

This means a worker bot should not ask the LLM every motor tick.
Instead:
- bot streams state every 100–150 ms
- server returns short-horizon intent vector
- local bot follows that vector with closed-loop motor control until the next refresh

## 6. High-level system diagram

```text
+----------------------------+
| Queen model                |
| frontier / best available  |
| strategic guidance         |
+-------------+--------------+
              |
              v
+----------------------------+
| Antelligence local server  |
| - worker decision API      |
| - pheromone field          |
| - tracking / localization  |
| - blockchain/event logger  |
| - safety gate              |
+------+------+--------------+
       |      |
       | Wi-Fi|
       v      v
+-------------+   +-------------+   +-------------+
| ESP32 bot 1 |   | ESP32 bot 2 |   | ESP32 bot N |
| worker      |   | worker      |   | worker      |
+-------------+   +-------------+   +-------------+
```

## 7. Stage 2 physical environment

Glass-box setup:
- transparent arena with overhead camera
- fiducial markers on bots or colored tracking markers
- target objects representing tumor cells / food / anomalies
- optional dye release mechanism or pickup magnet/gripper
- local Wi‑Fi network with dedicated server

Recommended environment versions:

### Version A — pickup task
Simplest and fastest.
- target pellets represent tumor cells or food
- bots pick up pellets and transport to drop zones
- proves target acquisition, coordination, and route formation

### Version B — dye-release task
Closer to medical analogy.
- stationary targets represent tumor regions
- bot must arrive in range and release colored dye
- overhead camera measures precision and spillover
- directly maps to “drug delivery only inside target region”

### Version C — mixed task
- some targets require pickup
- some require dye release
- some are decoys / healthy tissue
- proves selective action and damage avoidance

Recommended order: A -> B -> C

## 8. Bot hardware bill of materials

Per bot recommended baseline:
- ESP32-S3 dev board
- dual DC micro gear motors with motor driver
- LiPo battery + regulator
- wheel chassis or omni-drive mini base
- IMU (MPU6050 or better)
- optional ToF sensor for obstacle proximity
- RGB LED for state debugging
- optional micro servo for release gate
- AprilTag / ArUco marker on top for overhead tracking

Optional sensing upgrades:
- line sensor for arena lanes
- color sensor for target confirmation
- UWB tags for indoor localization if camera-free mode desired

## 9. Localization strategy

Do not attempt onboard SLAM first.
Use overhead tracking first.

Recommended Stage 2 localization:
- overhead camera above glass box
- each bot has AprilTag or ArUco marker
- server computes x, y, heading
- bots receive authoritative pose from server

Benefits:
- faster development
- lower onboard compute burden
- better reproducibility
- easier debugging

Later optional upgrade:
- onboard odometry + IMU fused with server pose

## 10. Communication model

Communication is intentionally minimal.
Bots are not chatty.
They do not send free text.
They send structured state.

### Worker -> server packet

```json
{
  "bot_id": "bot-03",
  "ts_ms": 1712712000123,
  "pose": {"x": 182.4, "y": 96.7, "heading_deg": 44.1},
  "velocity": {"linear": 8.2, "angular": -12.0},
  "battery_pct": 82.3,
  "sensors": {
    "front_range_cm": 7.1,
    "imu_ok": true,
    "color": "red",
    "payload_present": false
  },
  "status": {
    "state": "searching",
    "last_command_age_ms": 121,
    "release_enabled": false,
    "fault": null
  },
  "local_pheromone": {
    "trail": 0.24,
    "alarm": 0.03,
    "recruitment": 0.61
  }
}
```

### Server -> worker command

```json
{
  "bot_id": "bot-03",
  "command_id": "cmd-882191",
  "expires_in_ms": 300,
  "intent": {
    "mode": "vector_follow",
    "target_heading_deg": 58.0,
    "target_speed": 0.42,
    "confidence": 0.91
  },
  "release": {
    "authorized": false,
    "window_ms": 0,
    "payload_type": null
  },
  "safety": {
    "must_stop": false,
    "reason": null,
    "allowed_zone": "tumor-core-1"
  },
  "pheromone_write": {
    "trail": 0.1,
    "alarm": 0.0,
    "recruitment": 0.0
  }
}
```

## 11. Firmware state machine

Worker firmware states:
- BOOT
- IDLE
- SEARCHING
- TARGETING
- DELIVERING
- RETURNING
- SAFE_STOP
- FAULT

State transitions:
- BOOT -> IDLE when Wi‑Fi + server heartbeat established
- IDLE -> SEARCHING when mission assigned
- SEARCHING -> TARGETING when target intent received
- TARGETING -> DELIVERING when target proximity confirmed and release authorized
- ANY -> SAFE_STOP when command timeout or localization fault
- SAFE_STOP -> IDLE when heartbeat and pose confidence restored

## 12. Local fallback logic

This is the exact fallback logic to implement on ESP32:

```text
Every 20 ms:
  read motor state, sensors, last server command, last command age

If hard fault:
  stop motors
  disable release
  set state = FAULT

Else if last_command_age_ms <= 300:
  execute command normally

Else if 300 < last_command_age_ms <= 500:
  continue prior heading with reduced speed (e.g. 40%)
  disable release
  set state = SAFE_STOP_PENDING

Else:
  stop motors
  disable release
  set state = SAFE_STOP
```

Release actuator rule:
- release only if `authorized == true`
- and current command not expired
- and pose is inside authorized target radius
- and local target confirmation sensor passes

## 13. Pheromone implementation in glass box

Physical pheromones are not chemical in Stage 2.
They are digital field values maintained on the server.

Field layers:
- trail: successful route / prior success corridor
- alarm: obstacle, congestion, unsafe zone
- recruitment: valuable target discovered, more bots needed

Server stores a 2D grid over the arena.
Each bot reads a local neighborhood of that grid based on its pose.
Each bot may also deposit into the field indirectly by server command or event outcome.

This is critical:
Stage 2 proves that the Antelligence communication primitive is the field, not direct messaging.
That is one of the invention’s core claims.

## 14. Queen/worker division of labor

### Queen
Runs slower, richer reasoning.
Inputs:
- full arena state
- full pheromone field
- all bot positions and recent outcomes
- mission objective

Outputs:
- regional priorities
- worker parameter updates
- load balancing
- escalation / safety alerts

### Worker
Runs faster, narrow reasoning.
Inputs:
- local state
- local pheromone neighborhood
- short list of nearby targets
- current mission bias from Queen

Outputs:
- immediate movement intent
- target choice
- whether to request recruitment or raise alarm

Recommended practical setup:
- Queen = strongest available hosted model
- workers = cheaper fast hosted model or heuristic-first policy with LLM arbitration

## 15. Server APIs

Recommended endpoints:

### POST /api/v1/bots/heartbeat
Worker state upload + command response.
Single round trip.

### POST /api/v1/queen/tick
Queen strategic update endpoint invoked periodically by scheduler.

### GET /api/v1/world/state
Full current arena state for dashboard.

### GET /api/v1/world/pheromones
Current pheromone layers.

### POST /api/v1/events/log
Immutable structured event logging.

### POST /api/v1/mission/start
Start a physical experiment.

### POST /api/v1/mission/stop
Stop all bots and enter safe mode.

## 16. Event log schema

Every meaningful event should be structured.

```json
{
  "event_id": "evt-001882",
  "ts_ms": 1712712000455,
  "bot_id": "bot-03",
  "event_type": "target_acquired",
  "pose": {"x": 182.4, "y": 96.7},
  "payload": {
    "target_id": "target-12",
    "confidence": 0.88,
    "local_pheromone": {"trail": 0.24, "alarm": 0.03, "recruitment": 0.61}
  }
}
```

This same schema can later map onto blockchain logging.

## 17. Recommended first experiment set

### Experiment 1 — naive random bots
No Queen, no pheromones.
Measure baseline target acquisition and completion rate.

### Experiment 2 — pheromone only
No Queen, field-based coordination only.
Measure emergence of route reuse.

### Experiment 3 — Queen + pheromone
Full Antelligence architecture.
Measure improvement in:
- time to first target
- total targets handled
- spillover / false action rate
- path efficiency
- collision/congestion rate

### Experiment 4 — latency injection
Inject 50 ms, 100 ms, 200 ms, 300 ms, 500 ms latency.
Measure system degradation.
This directly informs future medical feasibility.

### Experiment 5 — stale command safety test
Deliberately sever connection.
Verify no harmful actuation occurs.

## 18. Metrics

Primary metrics:
- task completion rate
- time-to-target
- precision of delivery action
- false positive action count
- healthy-zone intrusion count
- command timeout count
- swarm throughput
- collision count
- energy per completion

Medical analogy metrics:
- target hit rate -> tumor cell hit rate
- healthy-zone intrusion -> collateral tissue damage
- recruitment efficiency -> swarm convergence on pathology
- stale command safety -> failure containment

## 19. Firmware implementation outline

Suggested code split on ESP32:
- `main.cpp` — task scheduling
- `wifi_client.cpp` — connectivity + retries
- `protocol.cpp` — JSON encode/decode
- `motion.cpp` — motor control
- `safety.cpp` — watchdog + release lockout
- `sensors.cpp` — IMU, range, color, battery
- `state_machine.cpp` — operational states

Suggested tasks:
- task_sensor_loop: 50 Hz
- task_motion_loop: 50 Hz
- task_network_loop: 7–10 Hz
- task_watchdog_loop: 20 Hz
- task_led_debug_loop: 5 Hz

## 20. Design recommendations

Recommended decision stack for Stage 2:
- local closed-loop motion on ESP32
- worker decision on server every 150–200 ms
- Queen strategic update every 1–3 s

Recommended first bot count:
- 4 bots minimum
- 6–8 bots ideal
- more than 10 only after tracking is stable

Recommended first arena:
- 1m x 1m top view
- overhead camera
- AprilTags
- simple target markers

## 21. What this proves for Antelligence

If Stage 2 succeeds, Antelligence is no longer just a simulation.
It becomes a demonstrated architecture framework for:
- hierarchical LLM swarms
- stigmergic machine communication
- safety-bounded cloud robotics
- future medical micro-agent control

This is bigger than GBM.
The same architecture could later be adapted to:
- vascular diagnostics
- anomaly detection swarms
- industrial inspection swarms
- warehouse micro-robot routing
- environmental sensing swarms

## 22. Immediate next implementation tasks

1. Create `backend/glass_box_server.py`
   - heartbeat endpoint
   - pheromone field state
   - mission control

2. Create `docs/ESP32_FIRMWARE_API.md`
   - exact message schemas
   - timing guarantees
   - retry rules

3. Create `firmware/esp32/reference_worker/`
   - PlatformIO skeleton
   - watchdog + safe stop logic

4. Create simulation mode `physical_arena`
   - same protocol, but simulated bots first
   - validates the firmware contract before hardware exists
