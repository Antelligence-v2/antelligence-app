# HARNESS-SPEC v0.4: L0/L0.5 Record & L1 Subtree Gate

Status: Canonical vNext specification for `antelligence/record/`. Preserves full wire compatibility with `HARNESS-SPEC v0.2` and `v0.3` validators.

## 1. L0 Canonical Hash-Chained JSONL

- **Format & Framing:** UTF-8, no BOM, LF (`0x0a`) delimited, max `16,777,216` bytes/file, max `1,048,576` bytes/line, max nesting depth `128`.
- **Canonicalization:** Sorted keys (`[a-z0-9_]+`), no whitespace outside strings, unsigned integers `0..2^53-1` only (no floats/NaN/Infinity), SHA-256 over the 8-member object excluding `hash`.
- **Blobs (`blobs/<sha256>`):** Payloads (`result`, `text`, `detail`) exceeding `4096` bytes (`4 KiB`) are stored atomically in `blobs/<sha256>` and referenced in-event via `blob:<sha256>` plus `blob_sha256` and `blob_bytes`.
- **12 MiB Segment Rollover:** Writers stop before `12 * 1024 * 1024` bytes (`ROLLOVER_BYTES`), close the current segment with `run_end(..., continuation_run_id=<next_run_id>)`, and open `<stem>.segNNNN.jsonl` with `run_start(..., continuation_run_id=<next_run_id>, prev_segment_sha256=<sha256>)`. Every segment remains independently valid under v0.2 validators.
- **Writer Locking:** `O_CREAT | O_EXCL` on `<path>.lock` with PID liveness check (`LockHeld` vs `NeedsRecovery`).

## 2. L0.5 Diagnose & Recover

- `diagnose(data)` classifies logs into `clean`, `empty`, `torn_first_line`, `torn_tail`, `corrupt_tail_after_end`, or `corrupt` (with `fork_suspected` and `over_limit`).
- `recover(path)` never mutates `path`; it preserves dropped bytes in `<path>.torn-<sha12>` and writes `<path>.recovered` atomically with a `note` event recording `dropped_bytes`, `dropped_sha256`, and `source_sha256`.

## 3. L1 Subtree Gate & Escrow

- **Static Sub-Budget Slice Escrow:** Spawning a child deducts `caps.spend_microusd` and `caps.max_steps` upfront from `parent.remaining()`.
- **Verified Settlement & Forfeit:** On verified `child_end` (in-process or via validated child log), only `escrow - subtree_spent(child)` is refunded. Any crashed, missing, unverified, or orphaned child forfeits its entire escrowed slice.
- **Grandchild Rollup:** `subtree_spent()` and `subtree_calls()` sum direct usage plus all descendants' settled/escrowed usage, closing the v4.8 grandchild 2x spend leak.
- **Operational Controls:** `max_concurrent_workers` cap, `<path>.kill` abort check, atomic `run_status.json` on init/exit/`SIGTERM`, and post-run usability gate (`usable_rate < 0.85` emits `status="INVALID_RUN"` and blocks `export_bundle`).

## 4. Worker Sandbox & Live State

- `verify_worker_sandbox(config_dir, allowed_tools)` checks on disk before step 1 that `config_dir` is isolated, `allowed_tools` has no wildcard `*`, and zero inherited global instructions (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.cursorrules`) exist.
- `load_live_state(run_dir)` reads runtime truth strictly from structured JSON artifacts (`run_status.json`, `env_state.json`, `manifest.lock.json`), never prose docs.
