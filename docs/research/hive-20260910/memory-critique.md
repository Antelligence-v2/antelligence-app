# Shared persistent memory for Antelligence

Research date: 2026-09-10. Scope is evidence beyond the prior G-Memory reading.
I deep-inspected exactly three complementary primary sources: **ReasoningBank**, **MIRIX**, and **Voyager**.[11]
A-MEM was used only as a reported MIRIX baseline; MemOS was screened as a lifecycle-design lead, not deep-reviewed.
This is a mechanism critique, not launch admission or a claim of global novelty.

## Executive judgment

The strongest decomposition is: **ReasoningBank supplies experience-to-strategy consolidation; MIRIX supplies typed stores plus a routing/retrieval hierarchy; Voyager supplies executable, compositional procedures that transfer to a fresh environment.**[1][3][6]
None demonstrates a bounded Queen coordinating independent evidence workers across unrelated future tasks.[1][3][6]
None gives convincing empirical evidence for contradiction resolution, version precedence, or expiry.[1][3][6]
Antelligence should therefore add those as explicit governance, not infer them from “memory.”

Do not build a transcript warehouse.
Keep worker evidence independent, retain source references, promote only compact lessons/procedures, and let the Queen see summaries, provenance, conflicts, and budget—not every raw trajectory.

## 1. ReasoningBank — compact experience, including failure lessons

**Mechanism.** A streaming agent retrieves top-k embedding-nearest memory items, completes the current task, has an LLM judge label the trajectory success/failure without ground-truth access, extracts title/description/content reasoning items, then appends them to the bank.[1]
Successful trajectories provide strategies; failures provide pitfalls/counterfactual guidance.[1]
Consolidation is deliberately simple addition, not a graph, merge, or decay policy.[1]
The authors explicitly say episodic/hierarchical memory and sophisticated retrieval/consolidation were outside scope.[1]

**Exact evidence.** In §4.2 Table 1 (WebArena, overall SR/steps), Gemini-2.5-Flash is 40.5/9.7 with No Memory, 42.1/9.2 Synapse, 44.1/9.0 AWM, and 48.8/8.3 ReasoningBank.[1]
Gemini-2.5-Pro is 46.7/8.8, 47.7/8.5, 47.6/8.7, and 53.9/7.4 respectively; Claude-3.7-Sonnet is 41.7/8.0, 42.6/7.9, 40.8/8.9, and 46.3/7.3.[1]
§4.2 Table 2 (SWE-Bench-Verified) reports Resolve Rate/Step: Flash No Memory 34.2/30.3 versus ReasoningBank 38.8/27.5; Pro 54.0/21.1 versus 57.4/19.8.[1]
Table 3 (Mind2Web) reports Gemini-2.5-Flash task SR across cross-task/cross-website/cross-domain as 3.3/1.7/1.0 for No Memory and 4.8/2.3/1.6 for ReasoningBank; Pro is 3.5/3.4/1.4 versus 5.1/3.8/1.7.[1]

**Controls and failure mode.** Controls include No Memory, trajectory memory (Synapse), workflow memory (AWM), and multiple backbones.[1] Appendix C.1 Figure 12 is especially useful for Antelligence: on WebArena-Shopping with Flash, one retrieved experience raises SR from 39.0 to 49.7, but 2/3/4 experiences fall to 46.0/45.5/44.4; more memory is not automatically better.[1] Appendix C.2 Figure 13 compares memory-aware scaling with no-memory and vanilla-TTS/no-aggregation: at k=2, 51.3 versus 47.6; at k=5, 62.1 versus 52.4.[1]

**Cost, contamination, reproducibility.** The paper reports interaction steps, not input/output tokens, memory-extraction calls, latency, or dollars; its MaTTS deliberately adds trajectories/refinement and therefore adds inference cost.[1]
Tasks are streamed sequentially and the bank starts empty, which is a useful chronology control, but this is still one agent in WebArena, Mind2Web, and SWE-Bench—not independent swarm workers.[1]
SWE-Bench-Verified has 500 instances; WebArena’s displayed subsets total 684 after excluding Map; Mind2Web cross-task/website/domain counts are 252/177/912.[1]
“No ground-truth during testing” applies to self-labeling, not to the final benchmark evaluation, which uses benchmark evaluators.[1]
The repository releases code for WebArena and SWE-Bench but requires external GPT/Gemini/Claude access; no learned model weights are released.[2]
The inspected repository HEAD was `ed80611788292ea739f1effd31f16c53823b8a0d`.[2]

**Author evidence vs project hypothesis.** Author evidence supports transferable *reasoning hints*, failure-derived guardrails, and a small relevant set.[1]
It does not support keeping raw episodes forever, correctness of self-judges, or automatic contradiction/version handling.[1]
Our hypothesis: this is the right promotion signal for a Queen’s “lesson ledger,” but only if every lesson keeps evidence links and failed lessons remain quarantined until independently revalidated.

## 2. MIRIX — typed memory and role-specific routing

**Mechanism.** MIRIX separates Core, Episodic, Semantic, Procedural, Resource, and Knowledge Vault memory, with six specialized memory managers, a Meta Memory Manager, and a Chat Agent.[3]
Episodic entries carry event type, summary/details, actor, and timestamp; semantic entries carry name/summary/details/source; procedural entries carry goal/type/steps.[3]
Active Retrieval first generates a current topic, then retrieves up to ten relevant entries from each component; coarse retrieval is followed by component-specific retrieval using embedding, BM25, or string matching.[3]
On updates, the meta manager routes to relevant managers, which update in parallel and avoid redundancy within a type.[3]

**Exact evidence.** §4.2 Table 1 (ScreenshotVQA) reports overall accuracy/storage: Gemini 0.1166/236.70 MB, SigLIP@50 0.4410/15.07 GB, MIRIX 0.5950/15.89 MB.[3]
The authors report this as 35% relative accuracy improvement over the RAG baseline with 99.9% less storage, and 410% relative improvement over the long-context baseline with 93.3% less storage.[3]
§4.3 Table 2 (LOCOMO, J score %) with GPT-4.1-mini reports MIRIX 85.11 single-hop, 83.70 multi-hop, 65.62 open-domain, 88.39 temporal, 85.38 overall; Full-Context is 88.53/77.70/71.88/92.70/87.52.[3]
Appendix A Table 3 shows three MIRIX runs at 83.98, 87.34, and 84.82 overall, while three Full-Context runs are 86.43, 88.13, and 88.00.[3]

**Controls and limits.** ScreenshotVQA compares long-context Gemini with resized images and SigLIP top-50 retrieval; text-memory systems are omitted because the authors say they cannot process multimodal input.[3]
LOCOMO compares A-Mem, LangMem, OpenAI memory, Mem0, Memobase, Zep, RAG-500, and Full-Context.[3]
Important asymmetry: baselines were run once, but MIRIX and Full-Context were run three times.[3]
The authors acknowledge open-domain weakness versus Full-Context and give a concrete temporal ambiguity where a confirmed later event can displace an earlier plan.[3]
Semantic entries are described as persisting unless conceptually overwritten and Core rewrites at 90% capacity, but no controlled contradiction, precedence, deletion, expiry, or stale-fact benchmark is reported.[3]

**Cost, contamination, reproducibility.** No token, latency, API-dollar, or manager-call total is reported.[3]
The paper says each screenshot step calls the meta manager plus zero to six other managers; LOCOMO uses GPT-4.1-mini, while GPT-4.1 judges answers.[3]
ScreenshotVQA contains 5,349–18,178 screenshots per student and 11/21/55 hand-created questions from three PhD students; LOCOMO has 10 conversations, about 600 dialogues and 26,000 tokens each, about 200 questions per conversation.[3]
LOCOMO’s adversarial/unanswerable category is explicitly excluded.[3]
Thus the result is not a clean test of refusal, contamination resistance, or unrelated cross-task transfer; ScreenshotVQA also couples question authors to the observed users.[3]
Code and predicted/evaluation results are released in the `public_evaluation` branch, but reproduction requires the LOCOMO download and OpenAI API key; no model weights are released.[4][5]
The inspected main-repository HEAD was `8cb06a62bbb7c478beb33dd4f2815696a72df482`.[4]

**Author evidence vs project hypothesis.** Evidence supports type-aware storage, routing, multi-hop consolidation, and compact multimodal summaries.[3]
It does not establish that eight agents outperform one manager under matched calls, or that “avoid redundancy” resolves contradictions.[3]
Our hypothesis: MIRIX’s topic→type routing is a good Queen interface, but the Queen should receive conflict metadata and evidence IDs rather than silently selecting one semantic fact.

## 3. Voyager — transferable executable skills

**Mechanism.** Voyager uses an automatic curriculum, a skill library of executable code indexed by description embeddings, and iterative code generation with environment feedback, execution errors, and self-verification.[6]
A skill is committed after verification; complex skills compose simpler ones.[6]
This is procedural memory with an executable acceptance test, not a transcript archive.[6]

**Exact evidence.** §3.3 Table 1 (three trials; fewer prompting iterations is better) reports Voyager versus Voyager without the skill library for wooden/stone/iron/diamond tools: 6±2/11±2/21±7/102 (Voyager, diamond 1/3) versus 7±2/9±4/29±11/N/A (without library).[6]
Table 2 tests a newly instantiated world with unseen tasks: Voyager succeeds 3/3 on golden sword, lava bucket, and compass at 18±7/21±5/18±2 iterations, and 1/3 on diamond pickaxe at 19±3; without the library it is 3/3/3/3 at 30±9/27±9/26±3 and 2/3 at 36.[6]
AutoGPT with the released skill library gets 1/3, 0/3, and 2/3 on diamond pickaxe, lava bucket, and compass respectively, evidence that the artifact transfers across controller designs.[6]

**Controls, retrieval, and cost.** The paper ablates curriculum, skill library, environment feedback, execution errors, self-verification, and GPT-4 versus GPT-3.5.[6]
Authors report a 93% discovered-item drop with random rather than automatic curriculum, a 73% drop without self-verification, and 5.7× more unique items with GPT-4 than GPT-3.5.[6]
Appendix B.4.4 Table A.4 evaluates 309 skill-retrieval samples: top-1/2/3/4/5 accuracy is 80.2±3.0/89.3±1.8/93.2±0.7/95.2±1.8/96.5±0.3.[6]
The paper reports GPT-4 as 15× the cost of GPT-3.5, but no absolute spend, token count, latency, or cost per accepted skill.[6]

**Contamination and reproducibility.** The new-world reset and empty inventory are meaningful transfer controls, but the domain is Minecraft, only three trials are used, and curriculum, generation, and verification all rely on the same GPT-4 family.[6]
“Unseen” therefore does not establish generalization to Antelligence’s changing research tasks.[6]
The MIT repository releases code and three learned skill-library trials; its README requires an OpenAI GPT-4 API key, and no model weights are released.[7][8]
The inspected repository HEAD was `55e45a880755d0c8c66ca7fb5fe7962ac8974f89`.[7]

**Author evidence vs project hypothesis.** Evidence supports storing a small, interpretable, executable procedure with a verifier and reusing it in a fresh state. It does not support ever-growing unversioned skills in a changing world: the library is success-oriented, lacks explicit expiry and contradiction handling, and can encode unsafe or environment-specific assumptions. Our hypothesis: Antelligence should admit “skill cards” only after independent evidence and a sandboxed replay, with a compatibility scope and expiry date.

## Cross-source gaps that matter for a bounded Queen

1. **Episodic → semantic → procedural is complementary, not interchangeable.** MIRIX names the stores; ReasoningBank distills reasoning lessons; Voyager demonstrates executable procedures.[1][3][6]
None measures a full consolidation pipeline where an episode is retained, abstracted, promoted, tested, and later demoted.[1][3][6]
2. **Contradiction/version/expiry is the missing safety layer.** MIRIX describes overwrite/rewrite language; ReasoningBank appends; Voyager grows a library.[1][3][6]
None reports stale-use rate, contradiction-resolution accuracy, version precedence, expiry recall, or rollback cost.[1][3][6]
MemOS was screened because its paper is a useful lifecycle/version-control design lead, but it was not selected as a fourth deep dive.[9][10]
3. **Role-specific retrieval needs cost and independence controls.** MIRIX routes by memory type; G-Memory already supplies the prior role-guidance precedent. Neither proves that routing helps a swarm when worker views must remain independent. The Queen must not receive a full-evidence adjudication prompt and call that distributed discovery.
4. **Benchmark contamination is not clinical validity.** These studies use benchmark tasks, LLM judges, hand-authored or domain-specific questions, and/or external model knowledge.[1][3][6] Do not expose future labels or answer keys to memory. Report every assigned case, validity, conditional accuracy, wrong→right, right→wrong, stale-use, and token/call overhead.

## Two project-specific syntheses (not claims of global novelty)

### A. Versioned evidence braid

Store `episode`, `semantic_claim`, and `procedure/skill` as separate records. Each promoted record carries `source_task`, exact evidence references, producer role, creation time, validity interval, confidence, status (`candidate|active|quarantined|expired`), supersedes/superseded-by links, and an explicit conflict set. Workers retrieve only role/task-scoped active records plus compact counterevidence; the Queen retrieves claim summaries, provenance, conflicts, and costs. Promotion requires two independent supporting episodes or one externally verifiable artifact; expiry forces re-check rather than deletion.

**Falsifiable test:** inject controlled stale and contradictory facts into a held-out task stream, with no future labels in memory. Compare no-memory, flat transcript, and versioned braid under matched retrieved tokens and calls. The synthesis fails if it does not reduce stale-use and wrong→right/right→wrong regressions versus flat memory, or if its conflict-check cost erases any assigned-case success gain.

### B. Role-gated executable skill cards

Turn a successful reasoning lesson into a typed card: preconditions, allowed tools, expected artifact/evidence, postcondition, replay command or structured steps, owning role, compatible domains, known failure modes, and expiry. Retrieval is role- and stage-gated; the Queen can recommend a card but cannot mark it valid. A worker or sandbox verifier must replay it on a fresh state, and independent workers retain separate observations before convergence.

**Falsifiable test:** create held-out cross-task tasks plus adversarial near-matches where a plausible skill is wrong. Compare shared untyped skills, role-gated cards, shuffled/role-blind retrieval, and token-matched transcript controls. The synthesis fails if role gating does not lower harmful skill adoption/right→wrong regressions, or if transfer does not improve assigned-case success after verifier and retrieval costs are counted.

## Admission recommendation

Start with a read-only local ledger and four-way evaluation: memory-off independent workers; typed/versioned memory; raw-transcript token-matched control; shuffled or role-blind retrieval. Keep a separate full-context adjudicator condition. Do not spend on external endpoints for a first Antelligence pilot: all three primary systems rely on external LLM calls in their released evaluation paths, and none supplies local weights.[2][4][7] The first acceptance gate is not a headline score; it is useful transfer without harmful convergence, stale recall, or hidden cost.

## Sources

[1] https://arxiv.org/html/2509.25140v1
[2] https://github.com/google-research/reasoning-bank/tree/ed80611788292ea739f1effd31f16c53823b8a0d
[3] https://arxiv.org/html/2507.07957v1
[4] https://github.com/Mirix-AI/MIRIX/tree/8cb06a62bbb7c478beb33dd4f2815696a72df482
[5] https://github.com/Mirix-AI/MIRIX/tree/public_evaluation/public_evaluations
[6] https://arxiv.org/html/2305.16291v2
[7] https://github.com/MineDojo/Voyager/tree/55e45a880755d0c8c66ca7fb5fe7962ac8974f89
[8] https://github.com/MineDojo/Voyager/tree/main/skill_library
[9] https://arxiv.org/html/2507.03724v1
[10] https://github.com/MemTensor/MemOS
[11] https://proceedings.iclr.cc/paper_files/paper/2026/hash/980ea04d23d1f6908964eba2a74afe45-Abstract-Conference.html
