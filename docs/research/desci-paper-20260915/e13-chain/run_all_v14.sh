#!/bin/bash
# Run all three E13 arms sequentially, resuming from v14 cache.
set -e
cd /Volumes/WD_BLACK/antelligence-experiments-20260911/e13-chain
export E13_MODEL=z-ai/glm-5.3-flash

echo "=== $(date) Starting E13 v14 sequential run ==="

# Baseline: seeds 101-120 (cache has 101,102,116 already)
echo "--- $(date) Baseline arm ---"
python3 -u run_pilot.py --arm baseline --max-cost 0.447835363 2>&1 || echo "baseline exited with $?"

# hive_memory: seeds 101-120 (cache has 101,102 already)
echo "--- $(date) Hive memory arm ---"
python3 -u run_pilot.py --arm hive_memory --max-cost 0.447835363 2>&1 || echo "hive_memory exited with $?"

# hive_memory_comm: seeds 101-120 (cache has 101,102 already)
echo "--- $(date) Hive memory+comm arm ---"
python3 -u run_pilot.py --arm hive_memory_comm --max-cost 0.447835363 2>&1 || echo "hive_memory_comm exited with $?"

echo "=== $(date) All arms complete ==="
