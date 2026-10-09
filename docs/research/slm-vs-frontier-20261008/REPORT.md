# SLM vs frontier benchmark report

## Status

**No held-out evaluation-split model call was completed.** The preregistration was committed at `755c4f5727ffad3d5b08d822c381c663d9faf150` before any attempted eval run. Therefore there is no results table to interpret and no headline claim about swarm benefit.

## Verified smoke evidence

- Development fixture smoke plumbing was exercised with the benchmark runner; the unavailable local endpoint produced explicit transport-failure cells and an append-only raw bundle during the probe. Those probe files were not retained as benchmark results.
- Claude subscription access was exercised with a non-evaluation one-call smoke prompt. The exact returned model was `claude-sonnet-5-5`; usage was recorded in `ledger/goal-2026-10-08-usage.jsonl` as subscription cost. This is not a benchmark result.
- Pinned local catalog was checked: Qwen endpoint `127.0.0.1:8301` and Phi4 endpoint `127.0.0.1:18302` were both connection-refused. Their weight files exist, but no local server was started because the available memory admission was only 8.341 GiB and the required Qwen/Phi4 loads are multi-gigabyte. Gemma 4 E4B was not available in the pinned roster.
- The evaluation task inventory is 100 tasks: 50 medical PubMedQA and 50 finance FinQA. The evaluation task-ID-list SHA-256 is `17f2acbcbb3de9f53561aadca1b7bc0a9d185f6e201689fb04412476b91accb7`.

## Deviations

1. The registered full grid was not run because both pinned local endpoints were unavailable and local model startup was not admitted under the memory gate. No eval result was fabricated.
2. Foraging and task-DAG were explicitly excluded from this first executable reduced slice in the preregistration because equivalent LLM benchmark-cell wiring was not completed.
3. No raw held-out run bundle, `results.csv` data row, or accuracy headline is claimed.

## Blockers

- Start/admit the pinned local model servers sequentially, or provide a genuinely local Gemma endpoint, then run the evaluation grid.
- Run Claude/Codex/Nous through adapters that preserve exact request/response accounting and append every call to the ledger.

## Planned verification commands

```text
uv run --extra test pytest tests/ -q -p no:cacheprovider
gitleaks git --log-opts="hermes/sync-20261008..HEAD" --redact
```
