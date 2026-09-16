# Antelligence — Blockchain-Native Swarm Intelligence Refactor Plan

> **Goal**: Transform Antelligence from a DeSci tumor simulation that *logs to* blockchain into a
> self-improving swarm intelligence framework that *reads from and writes to* blockchain as a
> canonical knowledge layer. Nanobots and the Queen consume on-chain intel, verified experiences,
> and promoted strategies to make better decisions on every subsequent run.

---

## 1. REFACTORED ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BLOCKCHAIN (Base Sepolia)                            │
│                                                                             │
│  TumorIntel              ColonyMemory           ExperienceRegistry         │
│  ──────────              ────────────           ───────────────────        │
│  • Intel pins (R/W)      • Visited cells        • Experiences (run→score)   │
│  • Confirmations         • Drug deliveries      • Strategy metadata         │
│  • Simulation attest.    • Tumor kills          • Validator attestations    │
│  • Proof verification    • Run completion       • Auto-verify @ N attests   │
│  • getActivePins() ◄── READ by swarm                                         │
│                          ▲                     • promoteStrategy() ◄ NEW    │
│                          │                     • getPromotedStrategy()       │
│                          │                     • StrategyRanking ◄ NEW      │
└──────────┬───────────────┴──────────────────────┴───────────────────────────┘
           │  (a) write intel / kills / deliveries / experiences              │
           │  (b) READ back intel pins, verified experiences, promoted        │
           │       strategies, kill-rate leaderboard                          │
           ▼                                                                     ▼
┌────────────────────────────────────┐    ┌────────────────────────────────────┐
│     Simulation Backend (Python)    │    │   Chain Reader Layer (Python) ◄ NEW│
│  ─────────────────────────────────│    │  ──────────────────────────────────│
│                                    │    │                                    │
│  TumorNanobotModel                 │◄───┤  ChainIntelReader                   │
│   ├─ reads KG before each action   │    │   • fetch_active_intel_pins()       │
│   ├─ writes intel pins to chain    │    │   • fetch_verified_experiences()    │
│   ├─ writes kills to ColonyMemory  │    │   • fetch_promoted_strategies()    │
│   └─ submits experience at run end │    │   • fetch_leaderboard()             │
│                                    │    │                                    │
│  QueenNanobot                      │◄───┤  ChainExperienceConsumer            │
│   ├─ reads verified experiences    │    │   • get_top_strategies(n)           │
│   ├─ reads promoted strategies     │    │   • get_experience(run_hash)        │
│   ├─ adjusts worker_params from    │    │                                    │
│   │   accumulated swarm knowledge  │    │  ChainStrategyWriter               │
│   └─ proposes strategy promotions  ├───►│   • submit_experience()             │
│                                    │    │   • request_promotion()             │
│  TumorKnowledgeGraph               │◄───┤                                    │
│   ├─ import_from_contract_events() │    │  (cached reads; TTL-based refresh)  │
│   ├─ export_to_ipfs() for CID      │    │                                    │
│   └─ synced bidirectionally        │    │                                    │
│                                    │    │                                    │
│  ProofPipeline                     │    │                                    │
│   ├─ mock → staged → verified      │    │                                    │
│   └─ verifySimulation() on chain   │    │                                    │
└────────────────────────────────────┘    └────────────────────────────────────┘
           │                                              │
           ▼                                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FEEDBACK LOOP (per run)                              │
│                                                                             │
│  1. INIT: Queen reads promoted strategies + verified experiences from chain  │
│  2. RUN:  Nanobots read on-chain intel pins → inform movement & targeting   │
│  3. RUN:  Nanobots write new intel pins, kills, deliveries to chain         │
│  4. END:  Run submits experience (score, strategy meta, IPFS CID) to chain  │
│  5. ATTEST: Validators attest quality; auto-verify at N attestations        │
│  6. PROMOTE: High-score verified experiences → promoteStrategy() on chain    │
│  7. NEXT RUN: Queen reads promoted strategy → adjusts worker_params          │
│                                                                             │
│  ⟲ The loop makes the system self-improving: every run's outcome feeds      │
│    the knowledge that shapes the next run's strategy.                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key change**: The blockchain is no longer a write-only logging layer. A new `ChainReaderLayer`
(Python) sits between the contracts and the simulation, providing cached, typed reads of intel,
experiences, and promoted strategies. The Queen and KnowledgeGraph both *consume* from it before
making decisions.

---

## 2. USER STORIES — BLOCKCHAIN LAYER

### BC-01: Batch intel pin reading via `getActivePins`
- **Title**: Read all active intel pins in a single call
- **User story**: As a nanobot simulation instance, I want to fetch all active intel pins from
  `TumorIntel` in a single call so I can seed my local knowledge graph without N round-trips.
- **Expected behavior**: A view function returns all active pins with their confirmations,
  reporter, priority, and type — paginated or full.
- **Contract function affected**: `TumorIntel.getActivePins(uint256 offset, uint256 limit) view
  returns (IntelPin[] memory)` — **NEW** (currently only individual `intelPins(uint256)` accessor
  exists).
- **Acceptance criteria**:
  - `cast call <TumorIntel> "getActivePins(uint256,uint256)(uint256,uint256,uint256,uint256,address,uint256,uint256,bool)[]" 0 50` returns only pins where `isActive == true`.
  - Returns ≤ `limit` pins starting at `offset`; total count available via `getActivePinCount()`.
  - Hardhat test: report 3 pins, deactivate 1, assert `getActivePins(0,10)` returns 2.

### BC-02: Strategy promotion on `ExperienceRegistry`
- **Title**: Promote best-performing verified strategies
- **User story**: As a swarm coordinator, I want to promote a verified experience's strategy to a
  global "promoted" registry so future runs can discover and adopt it.
- **Expected behavior**: Owner or auto-promotion logic calls `promoteStrategy(bytes32 runHash)`
  which adds the strategy to a ranked list. Only verified experiences can be promoted.
- **Contract function affected**: `ExperienceRegistry.promoteStrategy(bytes32 runHash)` — **NEW**;
  `promotedStrategies(bytes32) → bool` mapping; `StrategyRank` struct with cumulative score.
- **Acceptance criteria**:
  - `cast send <ExperienceRegistry> "promoteStrategy(bytes32)" <runHash>` reverts with
    `"Not verified"` if experience is unverified.
  - After promotion, `cast call <ExperienceRegistry> "isPromoted(bytes32)(bool)" <runHash>`
    returns `true`.
  - Hardhat test: submit → attest ×2 (auto-verify) → promote → `isPromoted` returns true.

### BC-03: Ranked strategy leaderboard on-chain
- **Title**: On-chain ranked list of promoted strategies by score
- **User story**: As a Queen nanobot, I want to query the top-N promoted strategies by score so I
  can select the best strategy for the next run.
- **Expected behavior**: A view function returns promoted strategy runHashes sorted by score
  descending.
- **Contract function affected**: `ExperienceRegistry.getTopStrategies(uint8 n) view returns
  (bytes32[] memory)` — **NEW**; backed by an array + insertion-sort or linked-list pattern.
- **Acceptance criteria**:
  - After promoting 3 strategies with scores 50, 90, 70, `cast call ... "getTopStrategies(uint8)"
    3` returns runHashes in order [score90, score70, score50].
  - Hardhat test: promote 5, call `getTopStrategies(3)`, assert order matches score descending.

### BC-04: Cross-contract experience linkage
- **Title**: Link `TumorIntel.SimulationRecord` to `ExperienceRegistry.Experience`
- **User story**: As a third-party verifier, I want to confirm that a simulation attestation on
  `TumorIntel` corresponds to an experience on `ExperienceRegistry` so I can verify end-to-end
  provenance.
- **Expected behavior**: `ExperienceRegistry` stores a reference to the `TumorIntel` configHash;
  a view function cross-checks that the simulation is verified on `TumorIntel`.
- **Contract function affected**: `ExperienceRegistry` — add `bytes32 configHash` field to
  `Experience` struct; add `isSimulationVerifiedOnTumorIntel(address tumorIntel, bytes32
  configHash) view returns (bool)` — **NEW** (uses `staticcall` to `TumorIntel.isVerified`).
- **Acceptance criteria**:
  - `cast call <ExperienceRegistry> "getConfigHash(bytes32)(bytes32)" <runHash>` returns the
    linked configHash.
  - `cast call <ExperienceRegistry> "isSimulationVerifiedOnTumorIntel(address,bytes32)(bool)"
    <TumorIntel> <configHash>` returns `true` only if `TumorIntel.isVerified(configHash)` is true.

### BC-05: Reputation-weighted attestations
- **Title**: Validators with higher on-chain reputation have more weight
- **User story**: As a swarm participant, I want attestations from validators with proven track
  records to carry more weight so strategy promotion is based on credible quality signals.
- **Expected behavior**: Each validator has an on-chain `reputation` score that increases with
  each attestation that aligns with consensus. Attestation quality is multiplied by reputation
  weight.
- **Contract function affected**: `ExperienceRegistry` — add `mapping(address => uint256)
  validatorReputation`; modify `_verifyExperience` to compute weighted average. Add
  `getValidatorReputation(address) view returns (uint256)` — **NEW**.
- **Acceptance criteria**:
  - `cast call <ExperienceRegistry> "getValidatorReputation(address)(uint256)" <addr>` returns ≥ 0.
  - After validator attests 5 times, reputation increases.
  - Hardhat test: two validators with different reputation → weighted average differs from
    simple average.

### BC-06: Intel pin deprecation on stale data
- **Title**: Auto-deprecate intel pins that haven't been confirmed in N blocks
- **User story**: As a nanobot, I want stale intel pins to be automatically deprecated so I don't
  waste time targeting cells that no longer exist.
- **Expected behavior**: A public function `pruneStalePins(uint256 maxAgeBlocks)` deactivates pins
  whose `block.timestamp - timestamp > threshold` and have < 2 confirmations.
- **Contract function affected**: `TumorIntel.pruneStalePins(uint256 maxAgeSeconds)` — **NEW**.
- **Acceptance criteria**:
  - After time travel in Hardhat, `cast call <TumorIntel> "getActivePins(...)"` excludes pruned
    pins.
  - Pins with ≥2 confirmations survive pruning.
  - Hardhat test: report pin, advance time, prune, assert `isActive == false`.

### BC-07: IPFS CID integrity check on experience submission
- **Title**: Verify IPFS CID format and data hash consistency on submission
- **User story**: As a verifier, I want the experience submission to validate that the `dataHash`
  matches a known schema so I can detect malformed or tampered submissions.
- **Expected behavior**: `submitExperience` requires `dataHash != bytes32(0)` and stores it;
  `verifyDataHash(bytes32 runHash, bytes32 expectedHash) view returns (bool)` allows off-chain
  comparison.
- **Contract function affected**: `ExperienceRegistry.submitExperience` (existing, add
  `require(dataHash != bytes32(0))`); add `verifyDataHash(bytes32, bytes32) view returns (bool)`.
- **Acceptance criteria**:
  - `cast send <ExperienceRegistry> "submitExperience(...)"` with `dataHash=0x0` reverts with
    `"Data hash required"`.
  - `cast call ... "verifyDataHash(bytes32,bytes32)(bool)" <runHash> <expectedHash>` returns
    `true` when they match.

### BC-08: Run-to-experience atomic submission
- **Title**: Submit simulation result + experience in a single transaction
- **User story**: As a simulation runner, I want to atomically post the simulation attestation
  and the experience record so there's no partial state where a simulation is attested but no
  experience exists.
- **Expected behavior**: A facade function on `TumorIntel` or a new `SwarmCoordinator` contract
  calls both `submitSimulation` and `submitExperience` in one transaction.
- **Contract function affected**: New `SwarmCoordinator.sol` with `submitRunAndExperience(...)`
  that calls both contracts via known interfaces — **NEW**.
- **Acceptance criteria**:
  - Single `cast send` to `SwarmCoordinator` results in both `SimulationSubmitted` event on
    `TumorIntel` and `ExperienceSubmitted` event on `ExperienceRegistry`.
  - Hardhat test: revert rolls back both writes atomically.

### BC-09: Experience query by strategy type
- **Title**: Filter experiences by strategy type
- **User story**: As a Queen, I want to query all verified experiences for a given strategy type
  (e.g., "pheromone-guided") so I can compare strategy effectiveness.
- **Expected behavior**: `getExperiencesByStrategy(string strategyType) view returns (bytes32[]
  memory)` returns runHashes matching the strategy type.
- **Contract function affected**: `ExperienceRegistry.getExperiencesByStrategy(string)` — **NEW**;
  backed by `mapping(bytes32 => bytes32[]) strategyTypeIndex`.
- **Acceptance criteria**:
  - `cast call ... "getExperiencesByStrategy(string)(bytes32[])" "pheromone-guided"` returns only
    matching runHashes.
  - Hardhat test: submit 2 experiences with different strategy types, assert filter returns 1.

### BC-10: On-chain proof status query
- **Title**: Query whether a simulation has a verified proof
- **User story**: As a third-party verifier, I want a single call to check if a simulation's proof
  is verified on-chain so I can trust its results.
- **Expected behavior**: `TumorIntel.isVerified(bytes32 configHash) view returns (bool)` (exists)
  and `getVerificationStatus(bytes32) view returns (uint8)` returning 0=not submitted, 1=submitted,
  2=verified.
- **Contract function affected**: `TumorIntel.getVerificationStatus(bytes32)` — **NEW** (extends
  existing `isVerified`).
- **Acceptance criteria**:
  - `cast call <TumorIntel> "getVerificationStatus(bytes32)(uint8)" <hash>` returns `0` before
    submission, `1` after `submitSimulation`, `2` after `verifySimulation`.

### BC-11: ColonyMemory visited-cell batch read
- **Title**: Batch query visited cells for knowledge graph seeding
- **User story**: As a nanobot, I want to query whether a set of cells has been visited so I can
  avoid redundant exploration.
- **Expected behavior**: `batchHasVisited(uint32[] xs, uint32[] ys) view returns (bool[])`.
- **Contract function affected**: `ColonyMemory.batchHasVisited(uint32[], uint32[])` — **NEW**.
- **Acceptance criteria**:
  - `cast call <ColonyMemory> "batchHasVisited(uint32[],uint32[])(bool[])" "[1,2]" "[3,4]"`
    returns `[true, false]` after cell (1,3) was visited.
  - Hardhat test: mark 3 cells, batch query 5, assert 3 true + 2 false.

### BC-12: ColonyMemory kill-rate aggregate per run
- **Title**: Query aggregate kill rate for a run
- **User story**: As a leaderboard consumer, I want to read the kill count and delivery count for
  a completed run in a single call.
- **Expected behavior**: `getRunStats(bytes32 runHash) view returns (uint16 cellsKilled, uint16
  drugDeliveries, uint32 totalSteps, bool completed)`.
- **Contract function affected**: `ColonyMemory.getRunStats(bytes32)` — **NEW** (wraps existing
  `getSimulationRun` into a stable tuple interface).
- **Acceptance criteria**:
  - `cast call <ColonyMemory> "getRunStats(bytes32)(uint16,uint16,uint32,bool)" <runHash>`
    returns correct values after `completeSimulation`.

### BC-13: ExperienceRegistry event emission for promotion
- **Title**: Emit event when a strategy is promoted
- **User story**: As an off-chain indexer, I want an event when a strategy is promoted so I can
  update the leaderboard in real-time.
- **Expected behavior**: `StrategyPromoted(bytes32 indexed runHash, uint256 score, address
  promoter)` event.
- **Contract function affected**: `ExperienceRegistry` — add `StrategyPromoted` event and emit in
  `promoteStrategy`.
- **Acceptance criteria**:
  - `cast logs --address <ExperienceRegistry>` shows `StrategyPromoted` after promotion.
  - Hardhat test: expectEvent `StrategyPromoted` on `promoteStrategy` call.

### BC-14: Access control for strategy promotion
- **Title**: Only owner or auto-promote can promote strategies
- **User story**: As a system operator, I want strategy promotion to be restricted so malicious
  actors can't promote bad strategies.
- **Expected behavior**: `promoteStrategy` callable only by owner or by a designated
  `autoPromoter` address; or permissionless if experience is verified AND score > threshold.
- **Contract function affected**: `ExperienceRegistry.promoteStrategy` — add `require(msg.sender ==
  owner || experiences[runHash].verified && experiences[runHash].score >= promotionThreshold)`.
- **Acceptance criteria**:
  - Promotion of unverified experience reverts with `"Not verified"`.
  - Promotion of low-score experience reverts with `"Score below threshold"`.
  - Hardhat test: verify + high score → succeeds; low score → reverts.

### BC-15: Contract upgrade proxy pattern
- **Title**: Make contracts upgradeable for future iterations
- **User story**: As a developer, I want contracts to be upgradeable so I can add features without
  migrating all data.
- **Expected behavior**: Deploy behind UUPS proxy (OpenZeppelin).
- **Contract function affected**: All 4 contracts — add UUPS proxy pattern; `_authorizeUpgrade`
  restricted to owner.
- **Acceptance criteria**:
  - `cast call <Proxy> "implementation()(address)"` returns current implementation.
  - `cast send <Proxy> "upgradeTo(address)" <newImpl>` succeeds from owner, reverts from non-owner.

---

## 3. USER STORIES — BACKEND / CORE LAYER

### BE-01: `ChainIntelReader` module
- **Title**: Python module to read active intel pins from chain
- **User story**: As a nanobot, I want a Python module that reads active intel pins from
  `TumorIntel` and returns typed objects so I can inject them into the knowledge graph.
- **Expected behavior**: `ChainIntelReader.get_active_pins(limit=50) → List[IntelPinData]` with
  TTL caching (default 60s) to avoid RPC spam.
- **Module affected**: `backend/chain/intel_reader.py` — **NEW**.
- **Acceptance criteria**:
  - `pytest test_intel_reader.py::test_get_active_pins` mocks RPC and returns ≥1 pin after
    `reportIntel` is called.
  - Cached calls within TTL don't hit RPC (assert call count).

### BE-02: `ChainExperienceConsumer` module
- **Title**: Python module to read verified experiences and promoted strategies
- **User story**: As a Queen, I want to fetch the top-N promoted strategies and verified
  experiences so I can select the best strategy for the next run.
- **Expected behavior**: `ChainExperienceConsumer.get_top_strategies(n=5) → List[StrategyData]`
  and `get_verified_experiences(strategy_type=None) → List[ExperienceData]`.
- **Module affected**: `backend/chain/experience_consumer.py` — **NEW**.
- **Acceptance criteria**:
  - `pytest test_experience_consumer.py::test_get_top_strategies` returns strategies sorted by
    score descending.
  - Filter by `strategy_type` returns only matching experiences.

### BE-03: Knowledge graph bidirectional sync
- **Title**: KG syncs from chain on init and exports to IPFS on run end
- **User story**: As a simulation instance, I want the knowledge graph to be seeded from on-chain
  intel at startup and exported to IPFS at run end so other instances can consume my discoveries.
- **Expected behavior**: `TumorKnowledgeGraph.sync_from_chain(reader: ChainIntelReader)` populates
  nodes from active pins; `export_to_ipfs() → CID` serializes and pins via `chain/ipfs.py`.
- **Module affected**: `backend/knowledge_graph.py` — extend `import_from_contract_events` (exists)
  with `sync_from_chain`; add `export_to_ipfs` method.
- **Acceptance criteria**:
  - `pytest test_knowledge_graph.py::test_sync_from_chain` — mock reader returns 3 pins, assert 3
    `INTEL_PIN` nodes in graph.
  - `test_export_to_ipfs` — assert returned CID is non-empty string.

### BE-04: Queen reads on-chain knowledge before strategy adjustment
- **Title**: Queen consumes verified experiences and promoted strategies
- **User story**: As a Queen, I want to read promoted strategies from chain before adjusting
  `worker_params` so the swarm benefits from accumulated knowledge.
- **Expected behavior**: `QueenNanobot._adjust_params()` calls
  `ChainExperienceConsumer.get_top_strategies()` and applies the top strategy's parameters.
- **Module affected**: `backend/nanobot_simulation.py` — `QueenNanobot._adjust_params` and
  `_end_episode`.
- **Acceptance criteria**:
  - `pytest test_queen.py::test_reads_promoted_strategy` — mock consumer returns strategy with
    `exploration_bias=0.1`; assert Queen's `worker_params["exploration_bias"]` becomes 0.1.
  - When no promoted strategies exist, Queen falls back to heuristic (existing behavior).

### BE-05: Nanobot reads on-chain intel before movement
- **Title**: Nanobots query chain-seeded KG before movement decisions
- **User story**: As a nanobot, I want to query the knowledge graph (seeded from chain intel) before
  moving so I can navigate toward high-value targets.
- **Expected behavior**: `TumorNanobotModel.step()` calls
  `kg.get_nearby_intel(position, radius)` and biases movement toward high-priority pins.
- **Module affected**: `backend/nanobot_simulation.py` — `Nanobot._decide_movement` or equivalent;
  `backend/knowledge_graph.py` — add `get_nearby_intel(position, radius)`.
- **Acceptance criteria**:
  - `pytest test_nanobot.py::test_uses_onchain_intel` — seed KG with a high-priority pin, assert
    nanobot moves toward it within N steps.
  - Without chain intel, nanobot uses existing pheromone-only behavior.

### BE-06: Experience submission on run completion
- **Title**: Every completed simulation submits an experience to `ExperienceRegistry`
- **User story**: As a simulation runner, I want to automatically submit an experience record
  (score, strategy meta, IPFS CID) to `ExperienceRegistry` when a run completes so the knowledge
  is available to future runs.
- **Expected behavior**: `TumorNanobotModel.end_run()` calls
  `ChainStrategyWriter.submit_experience(run_hash, ipfs_cid, data_hash, score, strategy_meta)`.
- **Module affected**: `backend/nanobot_simulation.py` — add `end_run()` / hook into existing
  cleanup; `backend/chain/experience_writer.py` — **NEW** or extend `submit.py`.
- **Acceptance criteria**:
  - `pytest test_run_lifecycle.py::test_experience_submitted` — mock writer, assert
    `submit_experience` called with correct args (non-zero score, non-empty CID).
  - Score = kill_rate_bps (consistent with TumorIntel attestation).

### BE-07: `ChainStrategyWriter` module
- **Title**: Python module to submit experiences and request strategy promotion
- **User story**: As a Queen, I want to request promotion of a high-scoring verified experience so
  the strategy becomes globally available.
- **Expected behavior**: `ChainStrategyWriter.request_promotion(run_hash)` calls
  `ExperienceRegistry.promoteStrategy(runHash)`.
- **Module affected**: `backend/chain/experience_writer.py` — **NEW**.
- **Acceptance criteria**:
  - `pytest test_experience_writer.py::test_request_promotion` — mock contract, assert
    `promoteStrategy` called.
  - Returns `True` if promoted, `False` if reverted (not verified / below threshold).

### BE-08: Leaderboard integration with promoted strategies
- **Title**: Leaderboard reads promoted strategies, not just `SimulationVerified` events
- **User story**: As a frontend user, I want the leaderboard to show promoted strategies ranked by
  score so I can see the best swarm strategies.
- **Expected behavior**: `leaderboard.py` calls `ExperienceRegistry.getTopStrategies(n)` and
  merges with existing `SimulationVerified` event data.
- **Module affected**: `backend/chain/leaderboard.py` — extend `fetch_onchain_events` or add
  `fetch_promoted_strategies`.
- **Acceptance criteria**:
  - `pytest test_leaderboard.py::test_promoted_strategies_in_leaderboard` — mock RPC returns 2
    promoted strategies, assert they appear in output sorted by score.

### BE-09: Chain reader caching with block-number watermark
- **Title**: Cache chain reads efficiently using block-number watermark
- **User story**: As a simulation, I want chain reads to be cached with a block-number watermark
  so I only fetch new events since the last query.
- **Expected behavior**: `ChainIntelReader` stores `last_block_read` and queries
  `logs --from-block <last_block_read>` on each refresh.
- **Module affected**: `backend/chain/intel_reader.py` — **NEW**.
- **Acceptance criteria**:
  - `pytest test_intel_reader.py::test_block_watermark` — two calls: first fetches from block 0,
    second fetches from block of first call's result.
  - Assert second call's RPC `fromBlock` > first call's.

### BE-10: Proof pipeline wired to experience submission
- **Title**: Verified proof triggers experience submission
- **User story**: As a simulation runner, I want the proof pipeline to trigger experience
  submission only after the proof is verified (or staged, with honest labeling) so the experience
  quality reflects proof status.
- **Expected behavior**: `proof_lifecycle.py` calls `submit_experience` with
  `verified=(proof_status == "verified_onchain")`.
- **Module affected**: `backend/chain/proof_lifecycle.py`, `backend/chain/submit.py`.
- **Acceptance criteria**:
  - `pytest test_proof_lifecycle.py::test_experience_after_verification` — mock pipeline,
    advance to `verified_onchain`, assert `submit_experience` called with `verified=True`.
  - At `staged` tier, experience is submitted with `verified=False`.

### BE-11: Run config hash consistency across contracts
- **Title**: Ensure `configHash` on `TumorIntel` matches `runHash` on `ExperienceRegistry`
- **User story**: As a verifier, I want the config hash used in `TumorIntel.submitSimulation` to be
  the same as the `runHash` in `ExperienceRegistry.submitExperience` so I can cross-reference.
- **Expected behavior**: `backend/chain/submit.py` and `experience_writer.py` use the same
  `compute_config_hash()` function.
- **Module affected**: `backend/chain/proof_spec.py` (hash computation), `submit.py`,
  `experience_writer.py`.
- **Acceptance criteria**:
  - `pytest test_submit.py::test_config_hash_consistency` — same inputs produce same hash in both
    submission paths.
  - `cast call <ExperienceRegistry> "getConfigHash(bytes32)(bytes32)" <runHash>` equals the
    `TumorIntel` configHash.

### BE-12: API server exposes chain-read endpoints
- **Title**: FastAPI endpoints for intel, experiences, and promoted strategies
- **User story**: As a frontend developer, I want REST endpoints to query on-chain intel and
  promoted strategies so the UI can display swarm knowledge.
- **Expected behavior**: `GET /api/intel-pins`, `GET /api/experiences?strategy_type=...`,
  `GET /api/promoted-strategies?limit=5`.
- **Module affected**: `backend/api_server.py` — **NEW** endpoints.
- **Acceptance criteria**:
  - `pytest test_api_server.py::test_get_intel_pins` — returns 200 with list of pins.
  - `pytest test_api_server.py::test_get_promoted_strategies` — returns sorted list.

### BE-13: Simulation replay reads from chain
- **Title**: Replay module can reconstruct a run from on-chain data
- **User story**: As a verifier, I want to replay a simulation using on-chain intel + IPFS data so
  I can independently verify results.
- **Expected behavior**: `simulation_replay.py` fetches kills/deliveries from `ColonyMemory` and
  intel from `TumorIntel` for a given `runHash`.
- **Module affected**: `backend/simulation_replay.py`, `backend/chain/intel_reader.py`.
- **Acceptance criteria**:
  - `pytest test_replay.py::test_replay_from_chain` — mock chain data, assert replay produces
    same kill count as `ColonyMemory.getKillCount(runHash)`.

### BE-14: Graceful degradation when blockchain is disabled
- **Title**: Simulation runs without blockchain, logging a warning
- **User story**: As a developer, I want the simulation to work without blockchain so I can test
  locally without RPC.
- **Expected behavior**: If `BLOCKCHAIN_ENABLED=False`, chain readers return empty lists, Queen
  uses heuristics only, experience submission is skipped with a log.
- **Module affected**: All chain modules — add `if not BLOCKCHAIN_ENABLED: return []` guards.
- **Acceptance criteria**:
  - `pytest test_simulation.py::test_runs_without_blockchain` — set `BLOCKCHAIN_ENABLED=False`,
    assert simulation completes without errors and no RPC calls are made.

### BE-15: Frontend displays chain-synced knowledge graph
- **Title**: UI shows intel pins and promoted strategies from chain
- **User story**: As a user, I want to see on-chain intel pins overlaid on the simulation and a
  sidebar of promoted strategies.
- **Expected behavior**: Frontend calls `/api/intel-pins` and renders pins on the simulation grid;
  calls `/api/promoted-strategies` and shows a ranked list.
- **Module affected**: `frontend/src/` — new components.
- **Acceptance criteria**:
  - Manual: start API, load simulation page, assert pins render at correct (x, y).
  - `npm run build` succeeds with new components.

---

## 4. USER STORIES — SWARM INTELLIGENCE FEEDBACK LOOP

### LOOP-01: Strategy selection from on-chain knowledge
- **Title**: Queen selects strategy from promoted list before run
- **User story**: As a Queen, I want to select the top promoted strategy from the blockchain before
  starting a run so the swarm starts with the best known approach.
- **Expected behavior**: On `TumorNanobotModel.__init__` or `QueenNanobot.__init__`, call
  `ChainExperienceConsumer.get_top_strategies(1)` and apply its parameters to `worker_params`.
- **Module affected**: `backend/nanobot_simulation.py`, `backend/chain/experience_consumer.py`.
- **Acceptance criteria**:
  - `pytest test_feedback_loop.py::test_strategy_selected_from_chain` — mock chain returns
    strategy with `exploration_bias=0.15`; assert Queen initializes with that value.
  - `cast call <ExperienceRegistry> "getTopStrategies(uint8)(bytes32[])" 1` returns non-empty
    before run.

### LOOP-02: Intel feedback during run
- **Title**: Nanobots write intel that other nanobots read within the same run
- **User story**: As a nanobot, I want my intel pins to be visible to other nanobots in the same
  simulation via the knowledge graph so the swarm converges faster.
- **Expected behavior**: When a nanobot reports an intel pin to chain, it also writes to the local
  KG; other nanobots query the KG (not chain) for real-time reads.
- **Module affected**: `backend/nanobot_simulation.py` — `_report_intel_to_blockchain` already
  writes to chain; add KG write in the same call.
- **Acceptance criteria**:
  - `pytest test_feedback_loop.py::test_intel_shared_in_run` — nanobot A reports pin, nanobot B
    within 5 steps moves toward that pin.
  - KG node count increases after `reportIntel`.

### LOOP-03: Run outcome → experience submission
- **Title**: Run completion triggers experience submission with full provenance
- **User story**: As a Queen, I want every run's outcome (kill rate, strategy, proof status) to be
  submitted as an experience so the swarm learns from every run.
- **Expected behavior**: At run end, `QueenNanobot` computes score, builds strategy meta, pins
  KG to IPFS, and calls `ChainStrategyWriter.submit_experience()`.
- **Module affected**: `backend/nanobot_simulation.py` — `QueenNanobot._end_run()` or
  `TumorNanobotModel.cleanup()`.
- **Acceptance criteria**:
  - `pytest test_feedback_loop.py::test_experience_submitted_after_run` — mock writer, assert
    `submit_experience` called once with `score > 0` and non-empty `ipfs_cid`.
  - `cast call <ExperienceRegistry> "experiences(bytes32)" <runHash>` returns non-zero `runHash`.

### LOOP-04: Attestation → verification → promotion pipeline
- **Title**: Verified experiences become promotable strategies
- **User story**: As a validator, I want to attest to an experience's quality so it becomes
  verified and eligible for promotion.
- **Expected behavior**: Off-chain validator (cron or manual) calls
  `ExperienceRegistry.attestExperience(runHash, quality, notes)`. After `minAttestations`, the
  experience auto-verifies. Then `promoteStrategy` can be called.
- **Module affected**: `backend/chain/experience_consumer.py` (read verified status),
  `backend/chain/experience_writer.py` (trigger promotion).
- **Acceptance criteria**:
  - `pytest test_feedback_loop.py::test_attest_verify_promote` — submit → attest ×2 → assert
    `verified == true` → promote → assert `isPromoted == true`.
  - `cast call <ExperienceRegistry> "experiences(bytes32)" <runHash>` shows `verified: true`,
    `attestments: 2`.

### LOOP-05: Next run adopts promoted strategy
- **Title**: Subsequent runs automatically adopt the best promoted strategy
- **User story**: As a swarm instance, I want my next run to use the highest-scoring promoted
  strategy so the system continuously improves.
- **Expected behavior**: On init, `QueenNanobot` calls `get_top_strategies(1)` and if a strategy
  exists, applies its `worker_params`. If no promoted strategy exists, uses defaults.
- **Module affected**: `backend/nanobot_simulation.py` — `QueenNanobot.__init__`.
- **Acceptance criteria**:
  - `pytest test_feedback_loop.py::test_next_run_adopts_strategy` — run 1 submits + gets promoted;
    run 2's Queen initializes with promoted strategy's params.
  - Param diff: `worker_params` in run 2 matches promoted strategy, not defaults.

### LOOP-06: Kill-rate improvement across runs (integration)
- **Title**: Swarm kill rate improves over multiple runs using on-chain feedback
- **User story**: As an operator, I want to see kill rate improve across N runs because the swarm
  is learning from promoted strategies.
- **Expected behavior**: Run 3+ should have measurably different (ideally better) kill rate than
  run 1, driven by strategy adoption.
- **Module affected**: Integration test across full loop.
- **Acceptance criteria**:
  - `pytest test_feedback_loop.py::test_kill_rate_improvement` — 3 runs with mocked chain; run 3
    Queen uses promoted strategy from run 1; assert `worker_params` changed from defaults.
  - (Kill rate improvement is strategy-dependent; test asserts *param change*, not necessarily
    higher kill rate, to avoid flaky tests.)

### LOOP-07: Third-party verification of run integrity
- **Title**: External verifier can validate a run end-to-end from chain
- **User story**: As a third party, I want to verify a simulation's integrity by checking
  `TumorIntel.isVerified`, `ExperienceRegistry.verified`, and `ColonyMemory.getRunStats` so I can
  trust the results without trusting the runner.
- **Expected behavior**: A CLI tool `verify_run.py --run-hash <hash>` checks all three contracts.
- **Module affected**: `backend/chain/verify.py` — add `verify_run_from_chain(run_hash)`.
- **Acceptance criteria**:
  - `pytest test_verify.py::test_verify_run_from_chain` — mock all 3 contracts returning verified
    data, assert function returns `{"tumor_intel": true, "experience": true, "colony": true}`.
  - `cast call <TumorIntel> "isVerified(bytes32)(bool)" <hash>` returns `true`.

### LOOP-08: Strategy decay and rotation
- **Title**: Old promoted strategies decay if newer ones perform better
- **User story**: As a Queen, I want to rotate through top strategies (not just the #1) so the
  swarm explores alternatives and doesn't overfit to one approach.
- **Expected behavior**: Queen uses epsilon-greedy: 80% top strategy, 20% random from top-5.
- **Module affected**: `backend/nanobot_simulation.py` — `QueenNanobot._select_strategy()`.
- **Acceptance criteria**:
  - `pytest test_feedback_loop.py::test_strategy_rotation` — mock 5 promoted strategies; over 100
    strategy selections, assert ≥2 distinct strategies selected.
  - Assert top strategy selected ~80% of time.

---

## 5. DEPENDENCY GRAPH

```
Layer 0 (No dependencies — contract foundation):
  BC-01 (getActivePins)          BC-07 (IPFS data hash)
  BC-06 (prune stale pins)       BC-10 (verification status)
  BC-11 (batch visited)          BC-12 (getRunStats)
  BC-13 (StrategyPromoted event) BC-15 (UUPS proxy)

Layer 1 (Depends on Layer 0):
  BC-02 (promoteStrategy)        → depends on BC-13 (event), BC-10 (verified check)
  BC-03 (getTopStrategies)       → depends on BC-02
  BC-04 (cross-contract linkage) → depends on BC-10
  BC-09 (filter by strategy type)→ depends on BC-07

Layer 2 (Depends on Layer 1):
  BC-05 (reputation weighting)   → depends on BC-02
  BC-08 (atomic submit facade)    → depends on BC-07, BC-02
  BC-14 (access control)         → depends on BC-02

Backend Layer A (Depends on contract Layer 0):
  BE-01 (ChainIntelReader)       → depends on BC-01
  BE-09 (block watermark cache)  → depends on BE-01
  BE-14 (graceful degradation)    → depends on BE-01

Backend Layer B (Depends on contract Layer 1+):
  BE-02 (ChainExperienceConsumer) → depends on BC-03, BC-09
  BE-07 (ChainStrategyWriter)    → depends on BC-02, BC-08
  BE-11 (config hash consistency) → depends on BC-04
  BE-13 (replay from chain)      → depends on BC-01, BC-12, BE-01

Backend Layer C (Depends on A+B):
  BE-03 (KG bidirectional sync)  → depends on BE-01, BE-09
  BE-04 (Queen reads chain)      → depends on BE-02, BE-03
  BE-05 (nanobot reads KG)        → depends on BE-03
  BE-06 (experience submission)   → depends on BE-07, BE-11
  BE-08 (leaderboard integration)→ depends on BC-03, BE-02
  BE-10 (proof→experience)       → depends on BE-06
  BE-12 (API endpoints)          → depends on BE-01, BE-02, BE-08

Backend Layer D:
  BE-15 (frontend display)       → depends on BE-12

Feedback Loop (Depends on Backend C):
  LOOP-01 (strategy selection)    → depends on BE-04
  LOOP-02 (intel sharing in-run)  → depends on BE-03, BE-05
  LOOP-03 (run→experience)        → depends on BE-06
  LOOP-04 (attest→verify→promote)→ depends on BC-02, BE-07
  LOOP-05 (next run adopts)       → depends on LOOP-01, LOOP-04
  LOOP-06 (kill rate improvement) → depends on LOOP-05, LOOP-02
  LOOP-07 (third-party verify)    → depends on BC-10, BC-04, BE-13
  LOOP-08 (strategy rotation)     → depends on LOOP-05
```

### Critical Path
```
BC-01 → BE-01 → BE-03 → BE-05 → LOOP-02
BC-02 → BC-03 → BE-02 → BE-04 → LOOP-01 → LOOP-05 → LOOP-06
BC-02 → BE-07 → BE-06 → LOOP-03 → LOOP-04 → LOOP-05
```

### Suggested Implementation Order
1. **Phase 1 — Contract foundation** (BC-01, BC-02, BC-03, BC-07, BC-10, BC-13)
2. **Phase 2 — Backend readers** (BE-01, BE-02, BE-09, BE-14)
3. **Phase 3 — Knowledge graph & Queen wiring** (BE-03, BE-04, BE-05)
4. **Phase 4 — Experience submission** (BE-06, BE-07, BE-10, BE-11)
5. **Phase 5 — Feedback loop** (LOOP-01 → LOOP-02 → LOOP-03 → LOOP-04 → LOOP-05 → LOOP-06)
6. **Phase 6 — API & frontend** (BE-12, BE-15, BE-08)
7. **Phase 7 — Hardening** (BC-05, BC-06, BC-08, BC-14, BC-15, LOOP-07, LOOP-08)

---

## 6. MIGRATION STRATEGY

### Principles
1. **Never break existing functionality**: every change is additive; existing tests must pass at
   each step.
2. **Feature-flag all chain reads**: `CHAIN_READ_ENABLED` env var (default `False` in dev, `True`
   in production). When `False`, simulation runs exactly as today.
3. **Deploy new contracts behind UUPS proxies** so future migrations are upgrade-only.
4. **Dual-write period**: during migration, both write to chain AND keep local KG as source of
   truth. Once verified, switch reads to chain-first.

### Phase-by-Phase Migration

#### Phase 1: Contract upgrades (non-breaking)
- Deploy upgraded `TumorIntel` (with `getActivePins`, `getVerificationStatus`) behind UUPS proxy.
- Deploy upgraded `ExperienceRegistry` (with `promoteStrategy`, `getTopStrategies`) behind proxy.
- Deploy upgraded `ColonyMemory` (with `batchHasVisited`, `getRunStats`) behind proxy.
- **Migration**: call `upgradeTo(newImpl)` on existing proxy (if already proxied) or deploy new
  and migrate storage via script if not.
- **Existing behavior**: unchanged — new functions are additive.
- **Rollback**: revert proxy to old implementation.

#### Phase 2: Backend chain readers (non-breaking)
- Add `backend/chain/intel_reader.py`, `experience_consumer.py`, `experience_writer.py`.
- All guarded by `CHAIN_READ_ENABLED` flag.
- **Existing behavior**: unchanged — readers are not called yet.
- **Tests**: new test files only; existing tests untouched.

#### Phase 3: Wire readers into simulation (feature-flagged)
- Modify `QueenNanobot.__init__` to call `ChainExperienceConsumer` if `CHAIN_READ_ENABLED`.
- Modify `TumorKnowledgeGraph` to call `sync_from_chain` if `CHAIN_READ_ENABLED`.
- Modify `TumorNanobotModel.step` to query KG for nearby intel (KG already exists; just add query
  method — non-breaking).
- **Existing behavior**: with `CHAIN_READ_ENABLED=False` (default), identical to current.
- **Rollback**: set `CHAIN_READ_ENABLED=False`.

#### Phase 4: Wire experience submission (feature-flagged)
- Add `TumorNanobotModel.end_run()` that calls `submit_experience` if `CHAIN_WRITE_ENABLED`.
- Add `QueenNanobot` promotion request if score > threshold.
- **Existing behavior**: with `CHAIN_WRITE_ENABLED=False`, no experience submission (same as
  today).
- **Rollback**: set `CHAIN_WRITE_ENABLED=False`.

#### Phase 5: Enable feedback loop (feature-flagged)
- `LOOP-01` through `LOOP-05` activate when both `CHAIN_READ_ENABLED` and `CHAIN_WRITE_ENABLED`
  are `True`.
- Run integration tests with both flags on (mocked RPC).
- **Production cutover**: enable both flags on a staging instance, verify loop completes,
  then enable on production.

#### Phase 6: API & frontend (additive)
- New API endpoints under `/api/intel-pins`, `/api/experiences`, `/api/promoted-strategies`.
- New frontend components — additive, don't modify existing simulation view.
- **Existing behavior**: simulation UI unchanged; new panels are optional.

#### Phase 7: Hardening & cleanup
- Add reputation weighting (BC-05), stale pin pruning (BC-06), access control (BC-14).
- Add strategy rotation (LOOP-08) and third-party verification tool (LOOP-07).
- Remove feature flags (or keep as kill-switches) once stable.

### Risk Mitigation
| Risk | Mitigation |
|------|-----------|
| RPC failures break simulation | Chain readers have try/except + cache fallback; simulation continues with stale/empty data |
| Gas costs from experience submission | Batch submissions; only submit on run completion (not per-step) |
| Contract upgrade introduces storage layout bug | Use OpenZeppelin storage gap pattern; run `forge inspect` storage layout diff before upgrade |
| Knowledge graph divergence between chain and local | `sync_from_chain` runs on every run init; KG is treated as cache, chain is canonical |
| Flaky integration tests from RPC timing | All chain-read tests use mocked RPC; only e2e tests hit real network |

---

## Appendix: Contract Change Summary

| Contract | New Functions | Modified Functions |
|----------|--------------|-------------------|
| `TumorIntel` | `getActivePins`, `getActivePinCount`, `getVerificationStatus`, `pruneStalePins` | — |
| `ColonyMemory` | `batchHasVisited`, `getRunStats` | — |
| `ExperienceRegistry` | `promoteStrategy`, `getTopStrategies`, `getExperiencesByStrategy`, `isPromoted`, `getValidatorReputation`, `verifyDataHash`, `getConfigHash`, `isSimulationVerifiedOnTumorIntel` | `submitExperience` (add `configHash` field, `dataHash` validation), `_verifyExperience` (reputation weighting) |
| `SwarmCoordinator` (NEW) | `submitRunAndExperience` | — |

## Appendix: Python Module Change Summary

| Module | Status | Changes |
|--------|--------|---------|
| `backend/chain/intel_reader.py` | **NEW** | `ChainIntelReader` with TTL cache, block watermark |
| `backend/chain/experience_consumer.py` | **NEW** | `ChainExperienceConsumer` for verified experiences, promoted strategies |
| `backend/chain/experience_writer.py` | **NEW** | `ChainStrategyWriter` for experience submission, promotion requests |
| `backend/knowledge_graph.py` | Modified | Add `sync_from_chain`, `export_to_ipfs`, `get_nearby_intel` |
| `backend/nanobot_simulation.py` | Modified | Queen: read chain on init + adjustment; Nanobot: query KG; Model: `end_run()` submits experience |
| `backend/chain/leaderboard.py` | Modified | Add `fetch_promoted_strategies` |
| `backend/chain/verify.py` | Modified | Add `verify_run_from_chain` |
| `backend/api_server.py` | Modified | New endpoints for intel, experiences, promoted strategies |
| `backend/chain/proof_lifecycle.py` | Modified | Trigger experience submission on verified proof |
