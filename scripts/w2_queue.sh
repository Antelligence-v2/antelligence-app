#!/usr/bin/env bash
# Run one W2 queue (a lane) sequentially. Each line = one harness invocation.
# Usage: scripts/w2_queue.sh local|frontier
# Stops starting new invocations after the preregistered deadline (2026-10-10 05:00 EDT).
set -u
cd "$(dirname "$0")/.."
export PYTHON_DOTENV_DISABLED=1
DEADLINE_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S %z" "2026-10-10 05:00:00 -0400" +%s)
run() {
  if [ "$(date +%s)" -ge "$DEADLINE_EPOCH" ]; then
    echo "$(date -u +%FT%TZ) deadline reached; not starting: $*"; return 0
  fi
  echo "$(date -u +%FT%TZ) START $*"
  uv run python scripts/w2_benchmark.py "$@"
  echo "$(date -u +%FT%TZ) END rc=$? $*"
}
case "${1:-}" in
  local)
    # Qwen: research_qa seeds 0,1,2 (all arms), then E15, then E13.
    for seed in 0 1 2; do
      run --model qwen38-27b-q3k --world research_qa --seeds "$seed" --cell-concurrency 3
    done
    run --model qwen38-27b-q3k --world task_dag --fixtures $(seq 101 119) --cell-concurrency 3
    run --model qwen38-27b-q3k --world foraging --arms baseline hive_memory_signals --fixtures 101 102 103 104 105 --max-steps 40 --cell-concurrency 2
    ;;
  frontier)
    # Ordered so the $12 cap (enforced in the harness) can only cut the most expensive, least
    # load-bearing cells last: Sonnet single (H-b) -> Haiku all -> E15/E13 (Haiku) -> Sonnet swarm arms -> Sonnet E15.
    for seed in 0 1 2; do
      run --model claude-sonnet-5.5 --world research_qa --arms single --seeds "$seed" --cell-concurrency 6
    done
    for seed in 0 1 2; do
      run --model claude-haiku-5.5 --world research_qa --seeds "$seed" --cell-concurrency 6
    done
    run --model claude-haiku-5.5 --world task_dag --fixtures $(seq 101 119) --cell-concurrency 6
    run --model claude-haiku-5.5 --world foraging --arms baseline hive_memory_signals --fixtures 101 102 103 104 105 --max-steps 40 --cell-concurrency 4
    run --model claude-sonnet-5.5 --world research_qa --arms independent_vote signal_board evidence_exchange evidence_isolated solo_refine --seeds 0 --cell-concurrency 6
    run --model claude-sonnet-5.5 --world task_dag --fixtures $(seq 101 119) --cell-concurrency 6
    ;;
  *) echo "usage: $0 local|frontier"; exit 2 ;;
esac
echo "$(date -u +%FT%TZ) QUEUE DONE ${1}"
