# Common contract for Sol feature leads

Read your one feature brief, this file, your controller-supplied ASSIGNMENT and the project VISION/RULES/ARCHITECTURE. Do not recover the old conversation or load every feature brief. This is operator-directed local development, not permission to restart autonomous schedulers.

## Roles and ownership

- **New-chat controller:** owns goals, frozen shared interfaces, admissions, worktree/slot assignments and integration. It verifies feature return packages first-hand and keeps the living learning ledger current.
- **Sol feature lead:** independent root Hermes session, requested `openai-codex:gpt-5.6-sol`. Own one user-visible feature and its requirement ledger. Split it into bounded Luna increments, rerun the load-bearing checks yourself, arrange fresh non-author review, then return the feature package. Do not make the user coordinate every worker.
- **Luna maker:** leaf worker requested `openai-codex:gpt-5.6-luna`, one bounded implementation artifact/patch at a time. Read the named actual code, record RED→GREEN, produce the scoped patch and evidence, commit verified work on the assigned non-main feature branch. Do not combine an entire feature, broad suite, review and integration into one child.
- **Luna reviewer:** fresh non-author context. Review the frozen exact source after maker work is complete. Read plain newline-preserving files and a separate hash manifest, not source escaped into one long JSON line. Sol checks reader visibility and actual output; reviewer self-report is not proof.

The active delegate_task schema has no nested-role/model override and leaf children cannot delegate. Live default-profile values were provider=openai-codex, model=gpt-5.6-luna, max_concurrent_children=2, max_spawn_depth=1. Official docs also describe optional orchestrator children; that does not enable them in this session. Use independent Sol roots, not a Sol leaf asked to subdelegate, and do not raise limits or change other profiles. Recheck at dispatch; exact served identities must be recorded, not inferred solely from a model catalog.

## Concurrency and durability

Start with one C0 lead. After acceptance, allow at most two feature leads with one active Luna each, subject to host admission and actual runtime caps. Reserve worker slots centrally across independent roots; do not let each root expand into its own full pool. Reviewers use the same slots after makers finish. If admission allows less, run sequentially rather than bypassing it.

Before any job expected to exceed1GiB or a proposed pool exceeding two processes, run the shared host gate and honor its worker_cap/defer result. Count proposed Sol roots and Luna workers together. Requesting two roots plus two leaves is a four-process payload, not “two workers.” Do not change the host gate or treat its defer as a fault.

Assign isolated worktrees from an immutable accepted base, preferably reusing clean inactive lanes only after checking ownership, running processes and old evidence needs. Keep at most two feature worktrees active, plus an owned integration candidate if needed. Existing worktrees in git worktree list are not automatically free. Preserve old branches/artifacts; no deletion or worktree cleanup without authorization.

One source writer per lane at a time. Sol does not edit source while its Luna writes. Separate peer feature leads never write the canonical checkout or each other's paths. Shared interface changes go back to the controller as a versioned contract checkpoint. Store large reports/databases/plain-source snapshots on the assigned SSD evidence root, not in chat.

Use bounded root runs and persist committed checkpoints before time limits. A timed-out worker may have usable committed work: inspect its actual state before retrying. After two failed repair rounds, Sol rederives the diagnosis instead of sending a third variation. All terminal outcomes—ready, checkpointed, blocked or rejected—must produce a durable return package; never label a time-limit exit as complete.

## ASSIGNMENT prerequisites

Controller supplies: feature/outcome ID; absolute worktree and branch; exact base and C0 contract commits; accepted dependency commit IDs; exclusive paths; absolute interpreter; scratch/evidence/output paths; owner session; hard run budget; assigned worker slot and host-admission receipt. Missing assignments are a concrete blocker, not permission to invent paths, overwrite a live lane or reset budgets. New worktrees lack .venv/untracked fixtures: use a verified interpreter with PYTHONPATH pointing at the lane, after checking imports and test side effects.

## Definition of feature-ready

All of the following, not a subset:
1. Every requirement in the feature brief maps to executable checks and inspectable artifacts; no required item is silently deferred.
2. Meaningful tests passed in the named interpreter/worktree, including affected existing consumers. Save full commands/output, not only a count. Inspect collection/import side effects before a broad suite.
3. A real producer→consumer behavioural probe exercised the feature against accepted dependencies. Unit mocks alone may earn CODE_TESTED, not FEATURE_READY_FOR_INTEGRATION. Conditional future coverage is named, never counted as proven.
4. A plain-language before/after explanation identifies the actual evidence/message/memory/controller change and external outcome. List negative cases, expected failures, unexplained results and limits. Failing to outperform a control is an honest research result, not permission to alter the test.
5. All feature source changes are committed on the owned non-main branch and the exact candidate is frozen. Record source/input hashes, actual model/session IDs, test/trace paths and ancestor/contract identities.
6. A fresh non-author exact-object review has no unresolved blocker/high issue; Sol independently reads it and reruns critical checks. Repairs change the object and require fresh review. Static review is labelled static—not independent execution.
7. The final result package passes the shared result shape and Sol verifies the referenced artifacts exist and match. “Process exited0” or a plausible summary never supplies the evidence.

Use FEATURE_READY_FOR_INTEGRATION only for the feature’s declared scope. C0 readiness means an accepted executable interface, not a complete hive. F6’s harness may be CODE_TESTED while its separately gated model study is still unrun. No feature lead grants model-run, merge, deployment or scientific-superiority approval.

## Integration gate (main controller only)

Read the exact returned package and commit diff, reconcile each requirement, rerun inexpensive decisive probes, inspect review provenance and verify raw byte identities. Assemble accepted dependency-compatible changes in an isolated non-main integration candidate; no git merge, push or canonical promotion by feature leads. The controller chooses an allowed reversible integration method after checking scope/ownership. A joined producer→memory→transport→Queen→verifier test must pass on the assembled object, followed by fresh independent exact-object review. If UI is mounted, verify actual local browser/API/store output. Only then consider canonical promotion under applicable authority; never silently mutate scheduler-consumed paths.

## Non-negotiable safety and research limits

Preserve historical reports/scoring, canonical databases and unfinished unrelated work. No deletion, main commit/merge, push, public deployment, scheduler/chain/firewall change, secrets/env edit, live money/clinical data/action or new paid dependency. Do not restart the separately owned Qwen service or old closed model experiments. No new experimental model call before F6 admission; the prior cumulative$5 approval is not a fresh allowance and current remaining spend is not audited. Pin requested/served identities; no silent metered fallback or model substitution. Check auth without exposing credentials; if it needs user action, return the exact blocker.

These model-free fixtures are neither OS isolation nor learned intelligence. Agreement, hashes, version matches, green tests and process restarts each prove only their specific property. Retain independent/full-information solo and voting controls, every assigned outcome, per-arm memory isolation and actual resource accounting. Mathematical/statistical analysis uses R. Record findings and mistakes in the assigned feature note/return package; the controller consolidates LEARNINGS.md and Vault to avoid shared-file races.

## Return

Write `DELIVERY.json` and `DELIVERY.md` in the controller-assigned fresh per-run evidence directory. Use DELIVERY-SHAPE.json as the field specification (not a successful-run example). Reference full source/trace/test/review artifacts rather than pasting huge payloads. Final chat output should be short: feature ID, status, candidate commit, absolute return path, user-visible result and the exact unresolved blocker if any. Completion is delivered to the new controller that launched you, not back to the old bloated conversation.
