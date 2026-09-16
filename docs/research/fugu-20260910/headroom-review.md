# Hostile review: collective headroom diagnostic

## Verdict

**PASS. No blocker or high-severity finding.** `headroom.json` is provenance-correct, reproducible from the approved immutable report, and its essential counts independently recompute exactly. The results support the narrow post-hoc/oracle diagnostic claims below, not claims of a deployed router, causal belief collapse, fresh accuracy, or impossible future improvement.

## Provenance and execution evidence

- Approved input: `/Volumes/WD_BLACK/antelligence-collective-20260908/next-experiment/cloud/study-report.json`
- Input SHA-256: `53dd046ee42f27c99e996dc4258f94494e24991348415fce4dd2005b64d4447d` — exact expected digest.
- Commit `b4c5ce9cc28d6a693a5782b5b7585862ee61156f` exists. The audited script and test paths have no diff from that commit.
- Analyzer SHA-256: `2cd8dad807649a32acb220dc9cc60ef5153f94176b2cf8b2bbd544393b8cc3fa`; this matches `headroom.json.analyzer_sha256`.
- Re-running the canonical CLI against the immutable input into a temporary output produced a byte-for-byte match to the archived `headroom.json` (both output files SHA-256 `d8ebedbaf5d863386afbe57951addde7c6b398d24f0f2e385c5d2dd8bb19a550`).
- Existing `.venv`: Python 3.11.15, pytest 9.0.3. `tests/test_collective_headroom.py`: **5 passed**.
- No source, report, or test files were modified. No model endpoint or paid call was used.

## Independent recomputation (without importing the analyzer)

A separate stdlib-only pass parsed the raw report and recomputed the classifications, common-initial identity, final groups, official status/correctness projection, and transitions.

- Exact cohort shape: 20 selected tasks, 100 cells = 20 x 5 arms; all expected keys present and unique.
- The three collective arms share the same initial identities for all 20 tasks.
- Common initial groups: **7 `minority_reference`, 2 `majority_reference`, 2 `no_reference_proposal`, 9 `blocked_invalid`**.
- Collective transitions:
  - `evidence_exchange`: **7 minority rescued**; 2 no-initial-match unresolved; 9 blocked; 1 majority retained; 1 majority lost.
  - `evidence_sources`: **6 minority rescued plus 1 minority blocked-invalid**; 1 no-initial-match unresolved plus 1 blocked; 9 blocked common initials; 1 majority retained; 1 majority lost.
  - `evidence_isolated`: **6 minority unresolved plus 1 minority blocked-invalid**; 13 blocked; 1 majority retained.
- Full-evidence `independent_vote`: **16 `majority_reference`, 3 `no_reference_proposal`, 1 `blocked_invalid`**.
- All 100 per-cell official `status`/`correct` projections in the artifact match the raw report; no official score was turned into a diagnostic success.
- Raw invalid denominator: **40/100** cells (`exchange` 9, `sources` 11, `isolated` 13, `independent_vote` 1, `solo_refine` 6). All 40 invalid cells still contain raw content with the string `answer`; the diagnostic correctly does not reparse that text as a valid answer.

## Qualitative-claim assessment

Supported, with the stated scope:

- There is oracle-selection headroom in the shared partial-view diagnostic: 7 initial minority-reference groups become reference-majority under exchange, and 6 under source sharing among otherwise valid minority cases.
- Isolation leaves 6 valid initial minority cases unresolved; one additional minority case is blocked by invalid transport.
- Full-evidence voting shows no observable pure-selection headroom in this sample: 16 reference-majority groups, 3 valid groups with no reference proposal, and 1 invalid group. Complementary-information synthesis and heterogeneous-model effects remain untested.
- For `pubmedqa:25007420`, reference=`maybe`: the common initial is `maybe/maybe/yes`; exchange and sources end `yes/yes/yes` (officially incorrect), while isolation remains `maybe/maybe/yes` (officially correct). This is a diagnostic change, not evidence that sharing improved accuracy.

Do **not** upgrade these results into claims that improvement is impossible, that a best routing policy was found, that routing caused belief collapse, or that the 7 rescued cases are fresh 7/7 accuracy. The artifact's own limitations correctly mark the analysis as post-hoc, reference-aware, single-model/one-draw, and consumed-data only.

## Findings

- **Blocker/high:** none.
- **Residual caution:** keep `minority_rescued` and final-message groups labeled as oracle diagnostics. They are not deployable routing outcomes and do not override invalid official cells.

Reviewed artifact: `/Volumes/WD_BLACK/antelligence-collective-20260908/fugu-research-20260910/headroom.json`
