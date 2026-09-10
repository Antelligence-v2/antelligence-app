# Parent reconciliation of the Sakana paper critique

Date: 2026-09-10. **Research reading accepted with corrections; proposed experiment NOT admitted for execution.** This supersedes conflicting interpretations in the raw delegated note, not the immutable source papers or historical experiment.

Raw artifact preserved at `/Volumes/WD_BLACK/antelligence-collective-20260908/fugu-research-20260910/paper-critique.md`, SHA-256 `c2439800d6ae7f3cdbb9778762422aee066d2a71bcc096697fe6feda0025b72a`.

## Accepted, checked against the primary text

- [TRINITY v3](https://arxiv.org/html/2512.04695v3), §§2–3, §4.1: a Qwen3-0.6B coordinator plus a worker/role head, with fewer than 20K trainable parameters including selected singular-value scales, uses sep-CMA-ES and terminal task reward. Seven workers, three roles, at most five turns in the reported setup. This is trained coordination, not a retrieved cross-task memory.
- TRINITY Table 2 reports 61.46 LiveCodeBench and 70.44 four-task average under the default 4K/minimal worker setting. The 86.2 ± 0.5% headline in §4.4 removes the output constraint. Keep these operating points separate. MMLU majority@5 Gemini is 91.57 ± 0.70 (Table 7), versus TRINITY 91.56 (Table 2): not a clean win over that strong independent control.
- [Conductor v5](https://arxiv.org/html/2512.04388v5), §3.1: GRPO trains a Qwen2.5-7B workflow writer; each step supplies a subtask, worker ID and access list. Default visibility is `[]`/`all`; selected-position access is a separate topology ablation. Reward is 0 for malformed workflow, 0.5 for well-formed but incorrect, 1 for correct.
- Conductor Table 7 reports 72.35 four-task average versus 67.60 Gemini 5× context and 64.52 GPT-5 5× self-reflection. These are author-reported benchmark means, not Antelligence results or universal improvement guarantees. Neither identical caps nor reported average tokens establish complete cost/latency equality.
- Conductor Table 9 and §B.8: targeted subtasks matter in the reported ablation; finer-grained access does not clearly improve on the simpler interface. Selective evidence challenge remains a hypothesis to test, not a direct consequence of this ablation.
- Fugu's ongoing-conversation history and workflow isolation are distinct from transferable cross-task memory. The earlier parent Fugu reading remains consistent with the new paper reading.

## Corrections and source inconsistencies

1. **Budget misclassification in the raw critique, §2 fixed-worker paragraph.** It calls Conductor Table 10's 93.30 / 37.86 / 87.50 comparison “constrained.” Those Conductor values match the high-budget main Table 1, not bounded-context Table 8's 66.67 / 37.8 / 81.31. Do not use Table 10 as a controlled 4K comparison; cite its own table context and disclose that resource parity is not established by the row.
2. **TRINITY text/table disagreement.** Appendix A.7.3 prose says 64.14 versus 70.44 for the prompted coordinator, but Table 8 gives 53.76 versus 70.44. Table 8 also uses 61.49 LCB versus Table 2's 61.46. Preserve those inconsistencies; do not silently harmonize them. The core summary uses Table 2 and does not depend on Table 8's disputed comparison.
3. **TRINITY hold-out “average” denominator.** Table 1 includes MT-Bench on a different scale. Its 54.21 matches the mean of AIME 50.00, BigCodeBench 35.80 and GPQA-D 76.82, excluding MT-Bench 9.60. It is not the raw mean of all four displayed metrics. Use per-task numbers or explicitly identify the three-percentage mean.
4. **Unlimited retries are part of a baseline.** Conductor §B.7 expressly gives prompted frontier coordinators unlimited format-failure resampling and double conductor output allowance. This reinforces the need to count failures, retries and actual consumption; it is not a production pattern to copy.

## Why the delegated four-arm pilot is not launch-ready

The raw note's §5 is advisory design, not an approved preregistration. The parent declines to adopt it as written:

- A final adjudicator with all source evidence in every arm tests review/aggregation atop a fully informed solver. It does not by itself test how distributed partial-knowledge workers obtain missing evidence. That may be a separate worthwhile experiment, but name the estimand correctly and retain full-evidence solo/voting as distinct controls.
- Three reserved record slots with blanks in two arms do not equalize tokens or transmitted information. Directed versus random routing can share the same selector/message envelope; broadcast comparisons must report actual information and token differences. Do not call all arms equal-cost merely because maximum lengths match.
- A 512-character record cap is not a proven reliability fix. Cosmetic presentation must not reject a valid machine answer/evidence record; strict structure, source membership and resource validation still apply. Real development outputs, not only hand-checked forms, are required for admission.
- Accuracy among valid outputs alone selects a different denominator per arm. Report valid-and-reference-matching results over all assigned cases as the operational endpoint, plus separate validity, conditional accuracy and paired transition diagnostics. Keep invalid outcomes visibly distinct rather than hiding or reparsing them.
- The proposed 16-item strata and net-two-item rule lack a demonstrated available sampling frame or power rationale. Do not freeze them merely because a delegate supplied exact numbers. A small feasibility pilot can assess readiness and justify continuation, not settle general superiority.
- Missing independent voting, ambiguous own-analysis exposure and incompletely specified tie-breaks/selection accounting need resolution before a causal comparison. A router must never see evaluation labels.

## Accepted direction

Preserve independent initial work; test a bounded evidence-backed consultation policy against a same-envelope random-target policy, then compare with fixed sharing, isolation, fully informed solo and voting under transparent resource accounting. Record right-to-wrong as well as wrong-to-right changes. Only after that should heterogeneous workers or frozen cross-task lessons become separate interventions.

No experiment, inference call, training run or service change follows from this reconciliation. Exact sample size, response contract, access policy, budget and decision rule remain to be frozen before a new pilot.

## Verification scope

The parent read the cited primary mechanisms and load-bearing tables, recorded source hashes and checked relevant arithmetic in `paper-reconciliation-receipt.json`. This is not a replication or a complete audit of every number in the raw 267-line note. All historical scores remain unchanged.
