# Launch and return: independent Sol roots, Luna leaves

**Instructions for the new controller; no feature process was started by preparing this pack.**

## What was actually verified

- Installed `hermes chat --help` supports `--provider`, `--model`, `--query-file`, `--oneshot`, `--in`, `--max-turns`, `--run-budget` and `--source`.
- Terminal command resolution: `/Users/operator/.local/bin/hermes`. The Python tool environment resolved `/Users/operator/.hermes/hermes-agent/venv/bin/hermes`; check the executable used by the actual launch.
- Installed Codex model catalog source lists `gpt-5.6-sol` and `gpt-5.6-luna`. This is catalog recognition, not a fresh Sol inference/auth smoke test. Earlier completed Luna reviewer manifests recorded openai-codex/gpt-5.6-luna.
- Current default-profile delegation settings read-only: provider=openai-codex, model=gpt-5.6-luna, max_concurrent_children=2, max_spawn_depth=1, max_iterations=250. No settings or credentials were edited.
- The active delegate_task schema has no role/model override, and its leaves cannot delegate. General docs describe optional nested orchestrators, but those are not enabled here. One tools-directory source search was permission-denied; it was not bypassed. Planning uses the actual exposed schema, read-only settings, installed CLI help and official docs.
- Official reference: https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation . Background child execution is process-local; durable completion delivery is not durable execution. Root CLI processes and checkpoints are separate from ephemeral leaf sessions.

## Before spawning

1. Confirm the canonical branch/base and ownership. Never reuse the old named worktrees merely because they appear in git worktree list. Resolve an active writer or target-path conflict rather than stashing/resetting it.
2. Check the actual default-profile provider route (including endpoint overrides and fallbacks without printing secrets). No silent metered fallback or model substitution; unresolved auth/route/cost is a launch blocker. Do not change another profile or globally repin models.
3. Run `/Users/operator/openclaw-infra/scripts/lib/memory_admission.py` through its verified Python command with a descriptive job and the requested total new Sol+Luna process count. Honor defer/worker_cap; do not increase the gate. This inspection/dispatch is not permission to modify openclaw-infra.
4. Create/reuse an explicitly owned isolated lane at the accepted immutable source/contract reference. Supply absolute interpreter and scratch paths. Emit ASSIGNMENT.json plus a short dispatch prompt that names its absolute path, COMMON.md and exactly one feature brief. Do not copy the old chat into the prompt.
5. Register the feature’s worker slot with the new controller. Default two root leads maximum, each one active Luna; start C0 alone. Limits apply across roots, not independently per root.

## Supported invocation shape

The following is a template, not an executed launch and not a runnable placeholder assignment. Substitute controller-verified absolute paths; never omit --in or the assignment.

```text
/Users/operator/.local/bin/hermes chat
  --provider openai-codex
  --model gpt-5.6-sol
  --query-file ABSOLUTE_DISPATCH_PROMPT
  --in OWNED_FEATURE_WORKTREE
  --oneshot
  --max-turns 120
  --run-budget 3600
  --source antelligence-feature
```

The bounds are proposed safety ceilings, not a completion ETA. Do not add --yolo, --ignore-rules, --ignore-user-config, --safe-mode or unverified nested-role flags. Keep protections and existing routing authority intact. Sol verifies actual served identity from runtime/session evidence before source work and verifies each Luna manifest; an alias/picker label alone is insufficient.

Launch from the **new chat** with `terminal(background=True, notify=True)` and a durable per-feature log path; preserve the returned process/session handle. This makes completion notify the correct new controller, not this old chat. Capture the full child output in that owned log; do not pipe through head/tail. Sol should write its return package before exiting. Checkpoints survive a timeout; absence of a completion package is partial/unknown, not success. Do not assume callbacks survive every app/process/session exit: retain the handles and artifact locations for explicit recovery, and never call a missing callback a completed feature.

Within the Sol root use one bounded native `delegate_task` Luna leaf at a time in the assigned slot. Native one-shot execution may join workers synchronously; do not invent polling or a nested orchestrator parameter. Let results return through the supported transport, then verify first-hand. Sol must emit a package for ready, blocked and checkpointed states alike.

## Return routing and integration

Per-run `DELIVERY.json`/`DELIVERY.md` go under the assigned SSD evidence directory. The terminal completion is only a signal to read them. The new main controller verifies status, literal model/session/commit IDs, requirement coverage, actual outputs and independent review. Missing/full-source-truncated evidence keeps integration closed. Sol leads never merge or promote their branches; the controller owns the combined-candidate gate in COMMON.md.

Starting a new chat is not permission to restart old model jobs or reset the research budget. No daemon, cron or scheduler is installed for this handoff.
