# Antelligence Swarm Intelligence Refactor — Handoff

## Context

Antelligence is a DeSci swarm-intelligence platform for tumor simulation. The project lives at `~/Desktop/research/antelligence-app`. It has nanobot swarm agents that coordinate through pheromones to find and eradicate tumor cells (or collect food in the ant colony sim). The blockchain (Base Sepolia) has 4 Solidity contracts: TumorIntel, ColonyMemory, FoodToken, ExperienceRegistry.

## Vision

"Antelligence should be a well-orchestrated swarm intelligence framework which shares knowledge via blockchain as a ledger and generates better decisions based on its shared understanding on that particular high risk or high accuracy task."

The core concept: shared swarm intelligence with hierarchical guidance (Queen coordinates workers) helps nanobots perform precise tasks — collecting food (v1) or eradicating tumor cells (v2). The blockchain is the canonical knowledge layer, not just a logging layer.

## What's Done

### PR #10 (merged): 6 UX/logistical bug fixes
- CLI leaderboard broken import fixed
- Per-nanobot per-step blockchain warning spam eliminated
- Frontend page title fixed from "colony-ai-grid-vision" to "Antelligence"
- Comparison page 422 error (max_pheromone_value exceeding schema limit) fixed
- Comparison chart rendering fixed (Recharts Cell components with explicit fill)
- README updated to document both API servers

### Contract upgrades (deployed to Base Sepolia, tests pass)
New TumorIntel functions:
- `getActivePinDetails()` — batch read of all active intel pins with full details (x, y, type, reporter, priority, confirmations, timestamp)
- `getVerificationStatus(bytes32)` — returns 0=not submitted, 1=submitted, 2=verified
- `pruneStalePins(uint256 maxAgeSeconds)` — auto-deactivate old unconfirmed pins

New ExperienceRegistry functions:
- `promoteStrategy(bytes32 runHash)` — promote a verified experience as an adoptable strategy
- `getTopStrategies(uint8 n)` — returns top-N promoted strategies sorted by score descending
- `getPromotedCount()` — count of promoted strategies
- `getExperiencesByStrategy(string)` — filter promoted strategies by type
- `isPromoted(bytes32)` — check if a strategy is promoted
- `PromotedStrategy` struct, `StrategyPromoted` event

Deployed contract addresses (latest):
- TumorIntel: 0x925b455175eF932a9a0239090a94E593224CD8AB
- ExperienceRegistry: 0x58A78E337ce3D948A39475f05Ca1A2c30274CADE
- ColonyMemory: 0x914D72b9d49ED4Bb46FA553a01fEbbd5EEf481fA
- FoodToken: 0x7310fb01b393459d2f8Ab15AD4a66F5380200869

Tests: 45 Hardhat tests pass (30 existing + 15 new). 10/10 on-chain verifications pass on Base Sepolia. 214+ Python pytest tests pass.

## The Plan

The complete refactor plan is at:
`~/Desktop/research/antelligence-app/docs/plans/2026-06-23-blockchain-native-swarm-refactor.md`

It has 43 user stories across 3 layers:

### Blockchain Layer (15 stories, BC-01 through BC-15)
- Batch intel reads, strategy promotion, ranked leaderboard, cross-contract linkage, reputation weighting, stale pin pruning, UUPS proxies
- Key: contracts already upgraded and deployed (see above)

### Backend Layer (15 stories, BE-01 through BE-15)
- ChainIntelReader (reads active pins from chain, TTL cached)
- ChainExperienceConsumer (reads verified experiences and promoted strategies)
- ChainStrategyWriter (submits experiences, requests promotion)
- Knowledge graph bidirectional sync (import_from_contract_events on init)
- Queen reads chain on init (getTopStrategies → adjusts worker_params)
- Nanobots query KG for nearby intel (KG reads from chain)
- Experience submission at run end
- Leaderboard integration
- API endpoints for intel/experiences/strategies

### Feedback Loop (8 stories, LOOP-01 through LOOP-08)
The self-improving core:
1. Queen reads promoted strategies from chain at init
2. Nanobots read on-chain intel via KG during the run
3. Nanobots write new intel/kills/deliveries to chain during the run
4. Run submits experience (score, strategy, IPFS CID) to ExperienceRegistry at end
5. Validators attest quality → auto-verify at N attestations
6. High-score verified experiences get promoted via promoteStrategy()
7. Next run's Queen reads promoted strategy → adjusts worker_params
8. Strategy rotation (epsilon-greedy: 80% top, 20% explore top-5)

### Dependency Graph / Critical Path
```
BC-01 → BE-01 → BE-03 → BE-05 → LOOP-02
BC-02 → BC-03 → BE-02 → BE-04 → LOOP-01 → LOOP-05 → LOOP-06
BC-02 → BE-07 → BE-06 → LOOP-03 → LOOP-04 → LOOP-05
```

### Migration Strategy
- Feature flags: CHAIN_READ_ENABLED, CHAIN_WRITE_ENABLED (default False)
- Phase 1: Contract upgrades (DONE)
- Phase 2: Backend chain readers (non-breaking, feature-flagged)
- Phase 3: Wire readers into simulation (feature-flagged)
- Phase 4: Wire experience submission (feature-flagged)
- Phase 5: Enable feedback loop (both flags on)
- Phase 6: API & frontend (additive)
- Phase 7: Hardening

## Next Steps

Start Phase 2: Build the Python ChainReaderLayer.

1. Create `backend/chain/intel_reader.py` — ChainIntelReader class with:
   - `fetch_active_intel_pins()` — calls TumorIntel.getActivePinDetails()
   - TTL-based cache (default 60s refresh)
   - Graceful degradation (returns empty list on RPC failure)

2. Create `backend/chain/experience_consumer.py` — ChainExperienceConsumer class with:
   - `get_top_strategies(n)` — calls ExperienceRegistry.getTopStrategies(n)
   - `get_experience(run_hash)` — calls ExperienceRegistry.getExperience(runHash)
   - `is_promoted(run_hash)` — calls ExperienceRegistry.isPromoted(runHash)

3. Create `backend/chain/experience_writer.py` — ChainStrategyWriter class with:
   - `submit_experience(config, metrics, run_id, strategy_meta)` — calls ExperienceRegistry.submitExperience()
   - `request_promotion(run_hash)` — calls ExperienceRegistry.promoteStrategy()
   - Feature-flagged via CHAIN_WRITE_ENABLED

4. Wire into knowledge_graph.py:
   - `sync_from_chain()` — calls ChainIntelReader, imports pins into local KG
   - Called on TumorNanobotModel init when CHAIN_READ_ENABLED=True

5. Wire into QueenNanobot:
   - On init, call ChainExperienceConsumer.get_top_strategies(1)
   - If a promoted strategy exists, apply its worker_params
   - Feature-flagged via CHAIN_READ_ENABLED

## Key Files

- Plan: `~/Desktop/research/antelligence-app/docs/plans/2026-06-23-blockchain-native-swarm-refactor.md`
- Feature tracking spreadsheet: `~/Desktop/research/antelligence-app/feature-tracking-spreadsheet.csv`
- Contracts: `~/Desktop/research/antelligence-app/blockchain/contracts/`
- Backend: `~/Desktop/research/antelligence-app/backend/`
- Tests: `~/Desktop/research/antelligence-app/tests/` and `~/Desktop/research/antelligence-app/blockchain/test/`
- .env: `~/Desktop/research/antelligence-app/.env` (has BASE_SEPOLIA_RPC_URL, PRIVATE_KEY, contract addresses)
- Python venv: `~/Desktop/research/antelligence-app/.venv/`
- LiteLLM proxy: `http://host.orb.internal:4000/v1` (fugu model may be available here — check with operator)
- Foundry (cast/forge): `/Users/operator/.foundry/bin/`
- Hardhat: `~/Desktop/research/antelligence-app/blockchain/node_modules/.bin/hardhat`

## Rules

- Read VISION.md, RULES.md, ARCHITECTURE.md at repo root before starting
- Never push to main without approval; open PRs
- Never edit .env or secrets
- Never deploy contracts without approval (contracts already deployed for Phase 1)
- Test-first: write tests before implementation
- Everything verifiable: acceptance criteria must be checkable via cast call/cast send on Base Sepolia or pytest
- Local-first: use free models for autonomous work, paid APIs for interactive/planning
