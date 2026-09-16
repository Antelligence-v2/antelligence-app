---
linked: 2026-09-15
---

# HANDOFF — Antelligence program, start here (2026-09-14)

Purpose: let a fresh chat resume with no context from the bloated session that produced this.
Read this, then the brief for whichever task you are running.

## What the program is

Evaluating whether the Antelligence hive machinery (evidence memory, model-free verifier, bounded
communication) measurably helps LLM swarms, toward a publishable DeSci paper. Product vision:
patient-aware brain-tumor simulation with verifiable provenance (TumorIntel, Base Sepolia).

Experiments root: `/Volumes/WD_BLACK/antelligence-experiments-20260911/` (e1..e14 dirs).
Review packet (the real application, **READ-ONLY**): `/Volumes/WD_BLACK/antelligence-review-20260911/`.
Paper: `/Users/operator/antelligence-desci-paper-v1.md`.

## Routing — READ THIS FIRST

**OpenRouter is exhausted.** Verified 2026-09-14: `total_credits 838, total_usage 838.21`, negative
balance, permanent HTTP 402. Every direct-OpenRouter call fails. Do not retry it.

**Use the Nous Portal inference API instead:**
- base_url `https://inference-api.nousresearch.com/v1` (OpenAI-compatible)
- auth `~/.hermes/auth.json` → `providers.nous.access_token` (or `.agent_key`); both verified live.
- **Token TTL ~1 hour → read auth.json FRESH PER CALL.** Caching it at startup is exactly how E13
  died mid-matrix.
- `max_tokens >= 1500` for the flash models. At small caps `deepseek/deepseek-v4.1-flash`,
  `z-ai/glm-5.3-flash`, `qwen/qwen3.8-flash` return `content=None` (cap consumed as reasoning).
  Verified working: those three plus `google/gemini-3.8-flash`.
- Model catalog: `curl -L https://hermes-agent.nousresearch.com/docs/api/model-catalog.json`
- `nousresearch/hermes-4-405b` is NOT in the Nous catalog. Every existing anchor ran on it, so any
  new run is a different model — label cross-anchor comparisons as cross-model.
- LiteLLM relay at `127.0.0.1:4000` is alive and cheap, but **its aliases lie**: relay id
  `grok-4-fast` → backend `openai/x-ai/grok-4.5`, and `gemma4` → `openai/google/gemma-3-27b-it`.
  Check `e10-model-floor-v2/discovery.json` before trusting a relay alias name.

## Established results (do not re-run)

- **E7v6 + E9-binary (the headline, replicated):** hive memory cuts redundant search ~16.3%
  (2319→1941 sweep moves), 20 seeds, temperature 0, sign test **p=0.012**. Identical on two model
  families (hermes-4-405b, grok-4-fast) → architectural, not a model quirk. **One task family,
  one harness** — that is the known hole.
- **E1 (deterministic):** memory+verifier 2.6–6.9x cheaper than always-requery under silent drift,
  0 unsafe acts, McNemar p≤0.006. Without the verifier: 81–156 unsafe stale-memory acts per cell.
- **E2/E3/E4/E6:** verifier 58/58 classification; transport blocks 6/6 attacks a naive swarm admits;
  memory fails closed under tamper/cascade/contradiction/arm-crossing; 288/288 replay agreement.
- **Model floor:** only 2 of 32 reachable backends pass a state-conditional action probe (both
  deepseek-v4-flash). Tracking one's own carrying state is a capability bottleneck.
- **E11:** accepted DAG bytes are a deterministic function of serialized proposals + fixture
  (0 determinism failures, 0 unsafe acts, no model in admission). Honest negative: 3 agents given
  identical information propose **63% redundant** nodes at ~2.7x solo tokens/accepted node, no
  lift (3/20 vs 2/20, p=1.000).
- **E12 (COMPLETE):** partitioning the proposers collapsed redundancy **63%→0%** exactly as
  predicted — and collapsed coverage with it: **0/20 success**, 6.4x solo tokens/accepted
  (2059.3 vs 323.4). A union of partial plans is not a complete plan. Strongest negative in the
  program. Anchors: solo 55 accepted/160 proposed, 3/20, 323.4 tok/node.
- **Proposal reproducibility:** a same-harness rerun showed temperature 0 does NOT guarantee
  reproducible *proposals* — 19/20 seeds bit-identical, seed 116 diverged (2 vs 8 accepted nodes).
  Admission given fixed proposals IS deterministic.

## CORRECTIONS that must not be lost (a claim died on 2026-09-13)

**E10's `strict` arm was mislabelled and is NOT evidence for the communication layer.**
It was reported as "peer-to-peer sightings → −5.5%, p=0.031, the first positive coordination
result" and written into the paper. Harness inspection disproved it: in `strict`, each agent
stores **its own** sightings in `private_sightings` and consults that set (run_e10.py L452-464),
while the peer transport admitted **zero usable replies on every seed**
(`transport_admitted_replies == 0`). So the −127 is a **single-agent private-memory effect**.
The dose-response axis is **memory scope**, not privacy:

| memory scope | arm | sweep moves |
|---|---|---:|
| none | independent | 2319 |
| none | positions_only | 2319 (+0, all 20 seeds) |
| private (own sightings) | strict | 2192 (−5.5%) |
| shared across agents | shared_memory | 1940 (−16.3%) |

`positions_only` has no memory mechanism at all and scored *exactly* +0 — the internal proof.
Communication therefore still has **no demonstrated throughput value**; its value is defensive
(E3). Full write-up: `mistakes/mistake-2026-09-13-e10-strict-arm-mislabelled.md`.
The paper (v1) has already been corrected in §4.5, §5.1 (retitled "Communication has no
demonstrated throughput value"), abstract, §6, §7 and §9.

**E12's `swarm_partitioned` v1 bug:** the prompt told agents to emit the literal string
`"my_sample"` as the sample field, but admission matches `sample-0`/`sample-1` keys → 0 accepted
across all 20 seeds. Fixed in v2 with a fresh cache; the v1 spend was reported, not hidden.
Lesson: the pretest only checked parseability, not admission. **A gate that cannot fail on the
metric you care about is not a gate.**

## Where the paper stands

`/Users/operator/antelligence-desci-paper-v1.md` — v1, verified number-by-number against artifact
files. E10 and E11 promoted from "Future Work" into §4.5/§4.6, E10-strict corrected, model floor
corrected to 2/32, missing artifact pointers restored. 10 `[TODO: verify]` markers remain
(citations, authors, MAST names, prereg details) — **deliberate. Never resolve a citation from
memory; leave the marker.**

Still structurally missing: **the headline has no second task family** (that is E13) and the
paper has no unifying theory (E12 tested one candidate and refuted it in the DAG layer).

## Council record (2026-09-13, $0.119)

Four models over OpenRouter (dead route, but the artifacts stand):
`/Users/operator/antelligence-reports/council-20260913/` — `brief.md`, `r1_*.json`, `r2_*.json`,
`transcript.md`. Their best catches: the integration plan presupposed write access to the
READ-ONLY packet; a 10-seed cap would have manufactured a null; a blanket tumor-work ban did not
follow from n=1. Two "surviving" recommendations (instrument E10 rejections; provenance-audit the
paper) were executed — the first is what exposed the E10 mislabel.

## Current state of the workstreams

| | status |
|---|---|
| E12 partitioned DAGs | **COMPLETE** — theory refuted in the DAG layer |
| E13 chain-prioritized foraging | **INCOMPLETE** — 12/20 baseline seeds, 13/20 hive seeds on disk |
| E14 merge/repair layer | not started — see the brief |
| Paper v1 | done and corrected; awaiting a generality result |
| Z1 tumor zero-shot | Phase 0+1 done; scored 0/1, model chose highest-viable zone instead of the simulator's entry-nearest zone |

## UPDATE 2026-09-14 evening — E13 incomplete, E14 confounded, read this before trusting either

## UPDATE 2026-09-15 — E13 is COMPLETE and POSITIVE (the report circulating on 09-14 13:13 is stale)

**E13 finished on 2026-09-14 at 21:44** on the Nous route with `cache_version v14`.
Model: **`z-ai/glm-5.3-flash`** via `https://inference-api.nousresearch.com/v1`. Provider
nousresearch. 20 seeds × 3 arms, no contamination from the old mixed-model cache (version prefix
was bumped as instructed). Authoritative `results_*.json` exist for all three arms.

| arm | sweep moves | reduction | successes | mean steps | cost |
|---|---:|---:|---:|---:|---:|
| baseline | 3057 | — | 19/20 | 58.3 | $0.1871 |
| hive_memory | 2655 | **−13.15%** | 19/20 | 54.5 | $0.1763 |
| hive_memory_comm | 2590 | **−15.28%** | 19/20 | 53.7 | $0.1738 |

Paired sign tests vs baseline (independently recomputed from `results_*.json`, exact match):
hive_memory 16 wins / 2 losses / 2 ties, **p=0.000656**; hive_memory_comm 17/2/1,
**p=0.000364**. Pre-registered bar was "reduction ≥ 5% AND one-sided p < 0.05".
Verdict recorded: **`generality_supported_within_second_task_family`**, with
`cross_model_caveat: true`.

**This closes the paper's biggest hole.** The E7v6 headline (16.3% on coordination-isolated
foraging, hermes-4-405b/grok-4-fast) now replicates on a *different task family* — chain-prioritized
foraging, where sightings have temporal ordering — at 13.2%/15.3%, on a *third model family*.
Same verdict bar was set before the run.

Budget: total known E13 spend **$1.6884** against the operator-approved $2.50 cap → $0.81 headroom.
The historical hermes-4-405b (seeds 101–112) replay was produced separately and labelled
(`historical_results_*_hermes_101_112.json`) — not merged into the new result, as required.

**Caveats to carry into the paper:** (1) the run is cross-model — it is not the same instrument as
E7v6, so it is evidence of generality across *families*, not an exact replication; (2) success was
at ceiling in all three arms (19/20), so this family measures efficiency, not capability; (3) a
1-step pretest showed all arms delivering 0/3, which is expected for a 1-step smoke but means the
pretest did not exercise delivery.

### Earlier E13 detail (still true, superseded by the above)

The pre-existing v13 caches (15 seeds) **must not be used**: their keys do not encode the model and
per-entry cost shows ~$0.00010 for seeds 101–113 vs ~$0.00018–0.00022 for 114–115 — two models.
`pilot_error.json` was overwritten by a failed resume (now holds 2 baseline runs, not 12).

**E12 and E14 partitioned arms were one agent short — both coverage conclusions are CONFOUNDED.**
The fixture has **4 samples**; the swarm spawns **3 agents**
(`agents = ["agent-0","agent-1","agent-2"]`), and
`my_sample = all_samples[agent_idx % len(all_samples)]` maps them to sample-0/1/2. **sample-3 is
never proposed by anyone** — and in a chain fixture sample-3 is the terminal goal (E12's own
seed-116 partitioned goal was `node-sample-3-place`). So 0/20 success was structurally guaranteed
in E12's partitioned arm and in E14's partitioned *and* merged arms; E14's merge layer "invents no
nodes", so it could never repair the gap (it lifted accepted nodes 32→40, nothing more).
Their *redundancy* results stand (partitioning genuinely eliminates duplication). Their *coverage*
results do not. Do not quote "partitioning kills coverage" or "merge layers don't help" as
findings. Full write-up: `mistakes/mistake-2026-09-14-e12-e14-partitioned-underprovisioned.md`.

**E14 numbers (verified against raw results):** solo 86 accepted/136 proposed, 9/20, 732 tok/node;
partitioned 32/120, 0/20; merged 40/120, 0/20; 0 determinism failures; spend $0.0568. Correct
arithmetic, wrong experiment.

## The four briefs to run

1. `Briefs/2026-09-14-e15-corrected-provisioning-partitioned-dags.md` — **the priority.** Fix the
   agent/sample provisioning, assert coverage in the gate, re-run partitioned + merged. Until this
   lands, the coverage conclusions of E12 and E14 must be marked confounded wherever quoted.
2. `Briefs/2026-09-14-e13-completion-nous-route.md` — finish E13. **Free first step:** replay the
   surviving caches for seeds 101–112 to regenerate authoritative `results_*.json` at zero cost;
   only seeds 116–120 need new calls, and the cap is already exceeded so that needs approval.
3. `Briefs/2026-09-14-e14-merge-repair-partitioned-dags.md` — the design is sound, the provisioning
   was not. Fold into E15 rather than re-running as-is.
4. `Briefs/2026-09-13-z1-tumor-zero-shot-knowledge-task.md` — tumor-domain angle (Phase 0 done;
   the grounded-vs-ungrounded arm is still undecided).

## Standing constraints

- Local-first; paid calls need a reason defensible aloud. Approved experiment envelope $10,
  ~$4.0 spent before E12/E13. **New spend needs explicit operator approval.**
- Review packet READ-ONLY. Never edit it; copy what you need.
- Report honest negatives; verify by artifact files, never by process exit or notification.
- Write the vault session note the same session a result lands.

<!-- wiki:semantic:start -->
## Related (auto-linked)

- [[weekly-digest-2026-W26]]
- [[hermes-20260424_050009_74db99]]
- [[hermes-20260423_050008_49822c]]

<!-- wiki:semantic:end -->
