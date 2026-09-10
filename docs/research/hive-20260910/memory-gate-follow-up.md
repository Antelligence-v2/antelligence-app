# Memory action gate: tested implementation, review pending

Date: 2026-09-10. Code commit `8e212292e56cb85ef0f12a639d862de4a4d484d3`; source base `4a5acfe10d33a94754a0f9c43fbde23f0bfd1edf`.

## Changed

`backend/research_coldroom.py::replay_with_memory` now routes the handwritten planner through scoped, replayed memory. A scope miss emits no submitted or attempted actions; corrupt/misindexed/conflicting episodes and unusable SQLite storage yield a distinct blocked result. The rule planner receives assay/logistics/Queen views, not the current protocol rules. State-based replay still determines success, including rejecting same-version stale rules.

`probe_hive_coldroom.py --output-dir NEW_FOLDER` now starts a fresh Python process that executes both same-scope reuse and changed-scope abstention. The old `--recall-db` mode remains. `--gate-db` executes these public development fixtures without rewriting the memory store. The probe's abstention is no longer a handcrafted report object.

## Verified

- Five RED→GREEN passes covered missing scope gate, positive reuse, invalid memory, unusable storage and cross-process probe integration. Receipt files preserve actual pytest failures and passes.
- `PYTHON_DOTENV_DISABLED=1 .venv/bin/python -m pytest tests/test_research_coldroom.py tests/test_collective_headroom.py -q`: **31 passed in 0.11s** (26 coldroom checks plus 5 existing headroom checks).
- Standalone producer PID **52544**, gate-process PID **52545**. Same-scope memory completed with six accepted actions; changed-scope memory submitted/attempted **zero**, placed nothing and did not claim success.
- Separate fresh-evidence comparison completed after the rule change; this is not autonomous evidence fetching.
- Original probe report hash remained `e34aaed5413004bddb37f9d67462982bfc853b541cbf08a9c2a8c0db0068dcdf`. Earlier replay/report bytes and historical study scoring remain unchanged.
- `git diff --check` passed before the code commit; clean branch readback followed it.

[Actual new report](memory-gate-report.json). Full RED/GREEN/probe receipts: `/Volumes/WD_BLACK/antelligence-collective-20260908/hive-next-wave-20260910/memory-gate-evidence/`.

## What this proves—and does not

A real model-free memory→planner→state-checker path now replaces a scripted abstention label. It does not prove that a learned agent chooses wisely, that graph routing improves performance, or that memory is generally truthful. The task generator/evaluator and insertion caller are trusted; this is not malicious-writer protection, cross-user access control or an OS sandbox. Unexpected faults may propagate rather than yield a structured result; they must remain failures, never success. Scope validation does not replace the external state checker. No autonomous fresh-evidence fallback, interrupted-run recovery, broad shared memory, Queen succession or live application integration is implemented by this change.

Independent static review of the frozen successor is **pending**. No new experimental model requests were made and no prior credit authority was reset.
