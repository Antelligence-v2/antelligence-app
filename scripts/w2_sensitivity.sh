#!/usr/bin/env bash
# W2 deviation D2: research_qa max_tokens sensitivity (2048 vs preregistered 512).
# Usage: scripts/w2_sensitivity.sh local|frontier
# Outputs go to the sensitivity dir; the shared ledger still counts all frontier spend (cap $12).
set -u
cd "$(dirname "$0")/.."
export PYTHON_DOTENV_DISABLED=1
SENS_OUT=docs/research/slm-vs-frontier-20261008/sensitivity-maxtok2048
ARMS="single evidence_exchange evidence_isolated"
run() {
  echo "$(date -u +%FT%TZ) START $*"
  uv run python scripts/w2_benchmark.py "$@"
  echo "$(date -u +%FT%TZ) END rc=$? $*"
}
case "${1:-}" in
  local)
    for seed in 0 1 2; do
      run --model qwen38-27b-q3k --world research_qa --arms $ARMS --seeds "$seed" --cell-concurrency 3 --max-tokens 2048 --out-dir "$SENS_OUT"
    done
    ;;
  frontier)
    for seed in 0 1 2; do
      run --model claude-haiku-5.5 --world research_qa --arms $ARMS --seeds "$seed" --cell-concurrency 6 --max-tokens 2048 --out-dir "$SENS_OUT"
    done
    run --model claude-sonnet-5.5 --world research_qa --arms $ARMS --seeds 0 --cell-concurrency 6 --max-tokens 2048 --out-dir "$SENS_OUT"
    ;;
  *) echo "usage: $0 local|frontier"; exit 2 ;;
esac
echo "$(date -u +%FT%TZ) SENS DONE ${1}"
