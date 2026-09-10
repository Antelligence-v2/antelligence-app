# Coldroom static contract review

## Disposition

**FIT** for continued **model-free research only** under the packet's stated scope.

- Candidate code SHA: `c0ed98600ed2528e029bfde42b3426d5f0167474`
- Blocker findings: **0**
- High findings: **0**
- Review basis: the immutable packet's exact three files, supplied parent output (`25 passed`), and supplied model-free probe report. The parent test suite and probe were **not independently executed for this review**.

No production, OS-isolation, malicious-DB-owner, learned-Queen, model-performance, physical-sample, or clinical claim is justified—and the contract and report explicitly disclaim those claims.

## Safety and success checks

No blocker/high defect found in the typed action evaluator.

- `backend/research_coldroom.py:67-109` requires an exact four-field action shape, exact string fields, `reserve`/`place` operations, integer (not boolean) revision, and evaluator-owned sample/slot membership.
- It checks the action budget before transition, rejects stale revisions, enforces one reservation before placement, checks zone compatibility, prevents collisions/duplicate placement, records the rejected transition, and stops at the first rejection.
- Rejected transitions do not mutate evaluator task state or the prior placed/reserved snapshots (`replay`, lines 87-105).
- `complete` is derived from the final placed state, and `safe_success` additionally requires no rejection (`lines 106-109`). A caller cannot manufacture success with `claim_success`; the supplied probe records that case as unsafe.

## Persistence, scope, and conflict checks

No blocker/high defect found under the trusted evaluator and trusted scratch-DB assumptions.

- `remember` (`lines 112-126`) replays before insertion and refuses any episode that is not a complete safe transition.
- `recall` (`lines 129-155`) opens read-only, filters by protocol/revision, verifies the payload hash, checks payload scope against the requested scope, replays every recalled episode, and rejects conflicting derived rule maps.
- The supplied tests cover corrupted payload, forged scope index, and same-scope conflicting rules. The supplied probe also demonstrates revision-1 scope miss and stale-rule replay failure.
- The persistence proof is a real subprocess: `scripts/probe_hive_coldroom.py:37-40` starts a fresh interpreter, reads the DB, parses the child JSON, and checks the returned episode ID; the child-derived rules are then used in a replay scenario (`lines 49-57`). This is stronger than a same-process/new-connection check.

## Residual evidence limitations and concrete repro suggestions

These are not blocker/high defects for the stated toy contract, but should not be overclaimed:

1. **Scoped abstention is partly report-fixture data.** At `scripts/probe_hive_coldroom.py:46-54`, `recall(..., revision=1)` is genuinely checked for `None`, but `stale_memory_scoped` is then manually constructed rather than returned by an action-execution gate. Static repro: change or bypass the `scoped` lookup; the emitted `safe_success: false`, `status: abstained_scope_miss`, and zero-action fields at lines 52-53 remain unchanged. If this is meant to prove an integrated scope-to-abstention path, add that path and assert its returned result. Current evidence proves scoped recall withholding, not a reusable production gate.

2. **Output preservation is fail-closed, not resumable.** `scripts/probe_hive_coldroom.py:31-32` requires a new output directory (`exist_ok=False`), and the supplied test (`tests/test_research_coldroom.py:135-151`) verifies that a second invocation fails before changing `report.json`. This supports no-clobber preservation. It does not prove recovery from a partially populated directory, preservation of every artifact under an interrupted first run, or append/resume behavior. Static repro: pre-create the requested output directory with a sentinel and invoke the probe; it refuses to run and leaves the sentinel untouched.

3. **Integrity is not authenticity.** The hash checks in `remember`/`recall` detect accidental payload changes, but a party able to rewrite both payload and hash can forge memory. This is explicitly within the packet's trusted-DB-owner limitation; do not promote it to an adversarial persistence guarantee.

4. **The experiment is deliberately narrow.** It has three fixed vial kinds, revisions `0/1`, a handwritten `plan_from_rules`, public fixtures, same-process role projections, and no learned/model worker. Same-rule transfer across randomized IDs demonstrates the toy replay contract only, not generalization, cooperation, or model capability.

## Final assessment

Continue model-free contract research with the stated caveats. Before treating the result as an integrated memory/action subsystem, replace the hand-built scoped-abstention report object with an exercised gate and add interruption/partial-output cases. No high-severity safety or state-derived-success defect is supported by the supplied packet.