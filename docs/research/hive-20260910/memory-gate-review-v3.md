# Independent static review — memory gate v3

## Verdict

**FIT for continued model-free research only.**

- Blocker findings: **0**
- High findings: **0**
- Candidate SHA: `f4f20323137a94ecab80a34df9161dbc881fb141`
- Base SHA: `4a5acfe10d33a94754a0f9c43fbde23f0bfd1edf`

This is a replacement review of the declared candidate, not a reuse of the superseded review. The verdict is limited to the contract's trusted generated task/evaluator and insertion context; it is not approval for autonomous model decisions, production deployment, OS isolation, or security against a malicious database writer.

## Source visibility

I read the contract and manifest first, then read every line of all three plain Python snapshots. Each `read_file` result was complete and reported `truncated: false`:

| Plain snapshot | Lines read | Manifest SHA-256 |
|---|---:|---|
| `backend/research_coldroom.py` | 172/172 | `2c28481a2931105078484f3271098c1ef56e81342418a3fee71aa346abf7a9a1` |
| `scripts/probe_hive_coldroom.py` | 100/100 | `27df00f8bc96e65be369ae82a54bad4cd3eb775e65d821f15346e860320fa08f` |
| `tests/test_research_coldroom.py` | 252/252 | `83d39b16b6df45753f98b8bbf6b13ef1bf73d2735db7fe89827d366f99b5ebc1` |

The required end-of-file visibility is demonstrated by these exact source quotes:

- Final `replay_with_memory` return, backend line 172: `return {**replay(task, actions), 'status': 'memory_replayed', 'memory': memory}`
- Final output-preservation assertion, test line 252: `assert (output / 'report.json').read_bytes() == saved`

## Static contract review

### Scope miss and invalid memory are pre-action abstentions

`replay_with_memory` performs `recall` before constructing or replaying any action (backend lines 163–172). A missing scoped row returns `abstained_scope_miss` with `replay(task, [])` (lines 168–169). Hash mismatch, scope-index mismatch, replay failure, conflicting same-scope rules, malformed JSON (`ValueError` family), and SQLite errors are converted to `blocked_memory_invalid` with no memory and `replay(task, [])` (lines 163–167; recall validation at lines 139–155). The supplied tests pin zero submitted/attempted actions and empty events for scope miss, invalid records, and unusable storage (tests lines 108–137, 140–156, and 185–197). Missing storage is read-only/absent and does not create a database (backend lines 129–137; tests lines 215–223).

### Positive reuse does not leak fresh protocol rules

For an admitted episode, the planner receives a projection that excludes the `protocol` view (backend lines 170–171), while the rules argument comes from recalled memory. The test's observing planner explicitly asserts `'protocol' not in views` (tests lines 159–182). Thus same-scope reuse uses stored rules rather than the current protocol rules. The scope is deliberately `protocol + revision`, not task identity; transfer across randomized identifiers is documented as a model-free fixture behavior, not structural generalization.

### State verification remains authoritative

The admitted plan is still passed through `replay(task, actions)` (backend line 172). `replay` checks action shape, budget, revision, reservations, slot availability, current task zone compatibility, and completion (backend lines 61–109). The same-version changed-rules case is therefore rejected by the current verifier with `incompatible_zone` even though admission status is `memory_replayed` (tests lines 200–213). This is the required independent state-check behavior: admission is not success.

### Real fresh-process gate execution

The producer creates a successful episode, then invokes a separate Python process with `--gate-db` through `subprocess.run` (script lines 43–51). The child reports its PID and performs both same-scope and changed-revision gated calls (script lines 33–38); the producer asserts the PID differs and the same-scope result succeeds (script lines 49–52 and 65–69). The supplied parent evidence reports producer/gate PIDs `52544/52545`, same-scope reuse with safe success, and changed-scope zero submitted/attempted actions with false success. Tests also require a distinct producer/gate process (tests lines 225–247).

### No-clobber and output preservation

The output directory is created with `exist_ok=False` (script line 41), and output files use exclusive creation mode `'x'` (script lines 92–95). Re-running the same `--output-dir` command therefore fails at directory creation before overwriting the prior report. The final regression stores the original bytes, requires a nonzero rerun, and compares the bytes afterward (tests lines 249–252).

### `--recall-db` compatibility

The CLI keeps `--recall-db` as a mutually exclusive mode and prints the scoped read-only recall result without running the producer path (script lines 23–32). `recall` opens an existing database through a read-only SQLite URI (backend lines 129–137).

## Findings

No blocker or high finding is supported by the fully visible plain sources under the declared contract.

## Residual limitations

- The planner is a handwritten join baseline, not an LLM, learned Queen, or autonomous policy (backend line 50; script lines 72–89).
- Scope matching does not establish truth. Same-scope memory can be admitted and then rejected by the current verifier; same-version rule drift is covered, but truth/freshness is not supplied by this fixture.
- The gate abstains on scope miss/invalid memory; there is no autonomous fresh-evidence fetch or interrupted-run recovery (contract and script lines 81–89).
- Task state, evaluator behavior, and database insertion are trusted. Episode hashes detect accidental tampering but are not signatures or authorship proofs (backend lines 112–119; script limitations lines 85–87).
- Role views are projections, not a same-process security boundary (backend lines 38–47; script line 85).
- The demo and parent test evidence exercise inert symbolic development fixtures only; no live API, physical/clinical validity, production deployment, or model-pilot admission is established.
- This review is static. The stated `31 passed` result and standalone probe are supplied parent evidence, not independently executed here, as required.

## Exact source identity

`candidate = f4f20323137a94ecab80a34df9161dbc881fb141`

`base = 4a5acfe10d33a94754a0f9c43fbde23f0bfd1edf`
