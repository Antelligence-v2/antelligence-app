# Parent reconciliation: memory and cooperative task research

Date: 2026-09-10. **Reading accepted with corrections; worker proposals are not an admitted model experiment or an approved production architecture.** This note supersedes conflicting interpretations in the preserved, unedited [memory critique](memory-critique.md) and [sandbox critique](sandbox-critique.md). Source coverage/citation-checker scores are not correctness certificates.

Parent fetched all six version-pinned papers and checked their load-bearing text/tables. Fresh raw code snapshots are independently pinned in [code-source-manifest.json](code-source-manifest.json); the paper extracts are listed in [delegation-primary-manifest.json](delegation-primary-manifest.json). Current source snapshots must not be treated as the historical code that produced a paper's scores.

## Corrections and interpretation boundaries

### Voyager: a wrong count and a different kind of verifier

- Worker memory critique line 80 incorrectly says Voyager's fresh-world Diamond Pickaxe result is **1/3**. [Voyager v2 Table 2](https://arxiv.org/html/2305.16291v2#S3.T2) reports **3/3 at 19±3 prompting iterations**, versus **2/3 at 36** without the skill library. The **1/3 at 102** result belongs to the lifelong-learning Diamond Tools column in **Table 1**, not the fresh-world transfer table.
- Table 2 reports 3/3 with and without the library on Golden Sword, Lava Bucket and Compass; the library has fewer reported prompting iterations. Do not present this as an across-the-board success-rate improvement. There are only three trials and a 50-iteration cutoff in this evaluation; iteration numbers and censored failures are not an audited latency or dollar comparison.
- Worker lines 77 and 93 overstate the verification basis by describing an 'executable acceptance test' without qualification. [§2.3](https://arxiv.org/html/2305.16291v2#S2.SS3) explicitly uses **another GPT-4 agent as the task-success critic**, then admits the code to the library. Executable skills and real environment feedback are useful; deterministic, independent success checking is **our proposed stricter adaptation**, not demonstrated by Voyager's skill-admission mechanism.

### ReasoningBank: quantity can hurt relative to the best setting

[ReasoningBank v1 Appendix C.1](https://arxiv.org/html/2509.25140v1#A3.SS1) confirms WebArena-Shopping/Flash success rates of **39.0, 49.7, 46.0, 45.5, 44.4** for zero through four retrieved experiences. More than one hurts **relative to one**; every reported nonzero-memory setting still exceeds the no-memory result. This is one domain/model ablation, not a universal memory-size law or cost-matched result.

Its memory construction uses an LLM success/failure proxy without ground-truth labels (§3.2); final benchmark scores use benchmark evaluation. A failure-derived lesson is a hypothesis about what to avoid, not an independently established universal prohibition. Table 1 supports 40.5→48.8 overall SR and 9.7→8.3 interaction steps for Flash, but the steps omit complete memory-manager/model token and dollar accounting.

### MIRIX: typed memory is not proof that a manager swarm beats a solo manager

[MIRIX v1 Table 2](https://arxiv.org/html/2507.07957v1#S4.T2) confirms **85.38** LOCOMO overall J-score versus **87.52** for Full-Context. Both were repeated three times; most other baselines were run once. LOCOMO adversarial/unanswerable questions were excluded (§4.1.1), and GPT-4.1 judged answers (§4.1.2). This supports type-specific storage/retrieval as an architectural lead, not independent-worker cooperation, contradiction safety, abstention reliability, or superiority over all full-context controls. Its personal screenshot-memory application is not permission to capture the operator's screen or ingest unrestricted personal data.

### CooperBench: real coordination difficulty, but do not merge its metrics or evaluator versions

- [CooperBench v1 §2](https://arxiv.org/html/2601.13295v1#S2) reports 652 feature-pair tasks, 12 repositories and **77.3% conflicting gold patches**, while joint features remain implementable. A fully informed solo agent is an explicit control.
- Its abstract's '30% lower' average success statement and Appendix C's **Solo AUC 0.338 / Coop AUC 0.200, retention 0.59** are different reported summaries. Do not call the AUC numbers success percentages or silently equate these summaries. The small 2/3/4-agent study does not establish a fixed-total-work, fixed-total-compute causal effect of adding agents.
- Appendix B describes standard/union merging plus a **learned conflict resolver** after earlier candidates fail tests. The paper's scoring path therefore is not merely a deterministic merge with no extra model assistance. Final feature tests are externally checkable, but merge assistance and test-selection budget matter.
- At parent-pinned code commit `cdd16702860bbfad28e26d17e7a679caff1a31e3`, `eval/sandbox.py::test_merged` explicitly disables union fallback and describes a lead-patch fallback after conflicts. This is concrete code/paper drift. Reuse the **two complementary patches + hidden combined requirements** experiment shape, not an unpinned runner or an assumed historic scoring contract.

### MARBLE: verified current-source adoption blockers, not a retroactive invalidation of the paper

At current pinned commit `8d60fa17b5596b44458a52d4296061b9fc13d6f2`:

- `marble/evaluator/evaluator.py::evaluate_task_db` lines 284–300 stores root cause and predicted text for separate evaluation; that method does not itself establish task success.
- The same file **fails Python 3.11 `ast.parse` at line 324** due to the misindented `except json.JSONDecodeError:`. See [the actual parse receipt](marble-source-parse.json). This was a syntax-only check; no foreign code was imported or executed.
- `engine/engine.py` lines 211–214 assigns the same task to all graph agents. `BaseAgent` accepts an optional shared-memory argument but constructs a fresh `SharedMemory()` at lines 72–73; engine construction does not pass the shared object.

These are enough to reject transplanting this current source snapshot as our evaluator or persistent-memory foundation. They do **not** prove the published historical results are false, that every MARBLE environment fails, or that no separate offline evaluator exists. The worker's broad phrasing that coding/DB outcomes are 'contaminated' overstates the verified conclusion. Keep it at source-specific, end-to-end verification not established.

### τ²-bench: borrow compositional tasks, require our own admission semantics

[τ²-bench v1 §3.2](https://arxiv.org/html/2506.07982v1#S3.SS2) confirms **15 atomic groups → 2,285 tasks → 114 sampled telecom tasks**, using initialization, solution and assertion functions. The task is asymmetric agent–user dual control, not a peer swarm, and the no-user control gives one agent all tools. Published simulator error rates and agent/user costs are separate from model task success.

At current parent-pinned code `caca045853d1e1cb1f9550846155a8299fd000a4`, `EnvironmentEvaluator.calculate_reward` replays predicted and gold states and uses the selected reward components. It also returns reward 1.0 when evaluation criteria are absent, and an empty selected reward basis can leave reward at 1.0. These may be framework conventions for other task types, but **Antelligence critical-task admission must require explicit load-bearing goal AND safety criteria**; do not copy those defaults as proof of work. End-state hashes alone do not prove that an unsafe intermediate action never occurred; check trajectory prefixes too.

## Proposed designs: accept the questions, not arbitrary authorities

1. Keep episode, claim and procedure records distinct, with source references, applicability scope, contradictions and a revocable promotion status. The worker's 'two supporting episodes or one artifact' is **not adopted as an authority threshold**: two agents can copy one wrong source, and an artifact's existence is not correctness. Require evidence appropriate to the claim and a verifier outside worker authority.
2. Role identifiers/signature fields are **not proofs of independent review or authorization**. Two role signatures are not sufficient without distinct authenticated principals and an explicit applicable authority policy. The testbed has no such signature system and makes no such claim.
3. A Queen should coordinate retrieval, consultation and commitments while evidence remains inspectable. Compare targeted versus random/fixed scheduling, with actual equal-budget envelopes and consumption accounting. Preserve full-information solo/vote controls. For action-plan voting, specify a whole-plan, verifier-safe selection/abstention protocol before execution; never splice per-action majorities or silently use a lexicographic tie-break.
4. Separate familiar-rule transfer on renamed IDs, unseen compositions, and actual rule shifts. The existing coldroom exposes development seeds/revisions and uses a public, fixed rule generator. It is **not a blinded task family or proof that its role facts cannot be inferred by other means**.
5. Structural novelty, correctly justified abstention and Queen replacement are worthwhile next tests. Failures, invalid messages and unnecessary abstentions remain in the assigned-case denominator. Benchmark task admission, actual model-output readiness and independent evaluator review are still required; no arbitrary sample size/win threshold or new model run is admitted here.

## Accepted practical priority

**First expand the small typed testbed into genuinely varied, independently reviewed task compositions and scoped memory records; then test whether a fresh Queen can select useful evidence/skills and avoid obsolete ones.** Retain a strong fully informed solver. Only after that compare learned consultation with fixed/random coordination. This is a falsifiable bridge from an evidence-sharing swarm toward transferable colony memory—not a claim that the colony already learns broadly.

Independent static review of the separate frozen coldroom code packet is in flight (`deleg_4929999d`), scoped to model-free development use. It does not review these external papers or admit model experiments. No testbed code was modified while that packet was under review.
