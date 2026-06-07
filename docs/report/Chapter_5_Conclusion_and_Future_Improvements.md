# CHAPTER 5: CONCLUSION AND FUTURE IMPROVEMENTS

## 5.1 Project Outcome

ClearPath set out to address a precisely bounded problem: clinical decision isolation in Malaysia's rural and district primary care clinics. The rural clinician — often a medical assistant or sole medical officer managing a wide case spectrum without specialist backup — lacks the three forms of support that urban practice takes for granted: a colleague to consult, a guideline at hand, and a pharmacist to review the prescription. This project built a hybrid deterministic–agentic system, grounded exclusively in validated Malaysian Ministry of Health Clinical Practice Guidelines and a curated drug knowledge graph, to close those three gaps within a standard consultation window.

The system that was built and tested is a functioning seven-stage pipeline — DDx, routing, evidence retrieval, re-ranking, synthesis, safety critic, and delivery — that accepts a structured patient case and returns a schema-validated care plan with action-tagged medication recommendations, section-and-chunk citations, time-anchored monitoring, and a dual-source safety surface. The backend pipeline is deployed, instrumented, and evaluated against a live grounded evidence store: 30 Malaysian MOH CPGs indexed in a pgvector store and a Neo4j drug knowledge graph with typed contraindication, interaction, and monitoring edges.

Whether ClearPath meets its objectives depends on which layer of the system one examines. The reasoning backend — the part that can be evaluated without recruiting clinicians — passed the majority of its quantitative targets. The application tier and the human-centred validation remain partially complete. Both facts are reported honestly in what follows.

---

## 5.2 Achievement Against Objectives

The four objectives stated in Chapter 1 are assessed below against the measured evidence from Chapter 4.

**Objective 1: Unified, machine-interpretable knowledge base grounded in Malaysian MOH CPGs with ICD-11 terminology, enabling real-time scope-controlled retrieval.**

This objective is met. The scope layer (Stage 3, D1–D6 routing ladder) resolves 100% of the 44 gold-set ICD-11 codes to their correct CPG at Top-1 and Hit@3 after harness and gold correction (A2, n=44). The semantic refusal layer passes all 11 scope probes — 5 in-scope codes route and 6 out-of-corpus orphans produce `out_of_scope` as a first-class event. The vector retrieval store reaches Recall@10 = 0.874 and Hit@10 = 0.953 on a 148-row LLM-judged graded gold, both passing their targets. The category re-ranker produces a net nDCG lift of +6.0% and MRR lift of +10.0% over the unranked pool across five multi-condition cases. The knowledge base is machine-interpretable in the precise sense required: every retrieval decision is tied to a specific ICD-11 code, a named CPG, and a chunk-level citation — not a probabilistic paraphrase of global medical text.

**Objective 2: Transparent, auditable second opinion within the consultation window, with per-stage reasoning traces.**

This objective is substantially met at the reasoning layer and partially met at the UI layer. The SSE stream emits typed events per stage — DDx shortlist with ICD-11 codes and confidence scores, routing D-level and any sex-filter rejection, retrieved chunks with similarity scores, and safety flags with `source` and `severity` — making the decision logic auditable in a way that no peer system reviewed in Chapter 1 can match. The expert clinician evaluation (Universiti Malaya, n=1 evaluator, 3 scenarios) confirmed ceiling scores (15/15) on Reasoning Transparency and Guideline Fidelity across all three cases, and 5/5 on Reasoning Visibility and Override & Feedback in the workflow rubric. The gap is in-consult speed and output density: the evaluator scored Workflow Fit 2/5 and Time-to-Answer 2/5, noting that the 2–3 minute end-to-end latency and dense structured output are better suited to case review than a fast triage encounter. The auditable second opinion exists; its integration into the sub-10-minute rural consultation is the work that remains.

**Objective 3: Medication safety enforcement through a dual-source critic combining LLM pharmacological reasoning with a structured drug knowledge graph.**

This objective is met for the cases tested. The dual-source safety critic — a Stage 6 async gather of the LLM critic and the KG verifier — fires on every evaluated scenario. Case 9 surfaces three KG-sourced DDIs (warfarin × fluconazole CRITICAL, warfarin × amiodarone CRITICAL, amiodarone × clopidogrel MAJOR) that the clinician did not prompt. Case 10 vetoes an existing medication (losartan) against the patient's current pregnancy state via a typed `CONTRAINDICATED_WITH` edge. Case 11 pre-empts a not-yet-prescribed drug (PDE5 inhibitor) against a long-acting nitrate, flags the interaction as CRITICAL before any prescription attempt, and simultaneously surfaces bisoprolol as an occult ED contributor the clinician had not linked. The expert clinician scored Safety at 15/15 across all three cases. What is not yet measured at scale is the false-positive rate and the false-negative rate on the full 30-CPG medication space; the KG-verified interaction set is a curated subset, not a complete pharmacological ontology.

**Objective 4: Structured, executable care plan carried longitudinally across patient visits.**

The care-plan schema is fully implemented and validated structurally. Every Stage 5 output is a Pydantic-validated TreatmentPlan with 9 sections (P1 Clinical Summary through P9 Follow-up), action-tagged recommendations (START/CHANGE/CONTINUE/STOP), chunk-level citations, and time-anchored monitoring. The prior-visit summary loop — a 5-field `PriorVisitSummary` persisted to Supabase and auto-loaded into the next consultation — is implemented in the data layer. The gap is that the Supabase round-trip and the authentication layer have not been integration-tested (application-tier test suites are a defined plan, not yet executed), so longitudinal persistence under concurrent write load has not been verified.

---

## 5.3 Validated Results Summary

The measured results are reproduced here for reference. These numbers come from live eval-harness runs against the deployed backend and are traceable to raw result files under `backend/eval/results/` and `backend/tasks/eval_runs/`.

| Layer | Metric | Target | Achieved | Pass |
|---|---|---|---|---|
| A1 DDx | Hit@5 (lineage) | ≥ 0.90 | **0.971** (34/35) | ✅ |
| A1 DDx | MRR (lineage) | ≥ 0.70 | **0.810** | ✅ |
| A1 DDx | Hit@5 (exact) | — | 0.771 (27/35) | (below lineage) |
| A2 Routing | Top-1 accuracy | ≥ 0.85 | **1.000** (44/44) | ✅ |
| A2 Routing | Hit@3 | ≥ 0.95 | **1.000** (44/44) | ✅ |
| Scope refusal | 11-probe pass | 100% | **11/11** | ✅ |
| B Retrieval | Recall@10 | ≥ 0.85 | **0.874** | ✅ |
| B Retrieval | Hit@10 | ≥ 0.95 | **0.953** | ✅ |
| B Retrieval | nDCG@10 | ≥ 0.75 | 0.669 | ❌ |
| C Re-ranker | nDCG lift | > 0 | **+6.0%** (n=5) | ✅ |
| D Faithfulness | Mean faith (n=30) | ≥ 0.90 | **0.864** | ❌ (close) |
| SIL/INF Robustness | Fail-loud probes | 6/6 | **6/6** | ✅ |
| Determinism | Top-1 stability (dominant dx) | stable | **10/10** (cases 8, 9) | ✅ |
| Latency | p50 end-to-end | — | **~2.5 min** (n=3 pilot) | (target needs revision) |
| Test coverage | Line coverage | ≥ 60% | **64.93%** | ✅ |
| Clinician eval | Safety (15/15) | ≥ 4.0/5 | **5/5** per dimension | ✅ |
| Clinician eval | Reasoning transparency | ≥ 4.0/5 | **5/5** | ✅ |
| Clinician eval | Workflow fit | — | **2/5** | gap |

---

## 5.4 Limitations

The following limitations are stated precisely rather than softened.

**Faithfulness gap (0.864 vs ≥0.90 target).** The full-population faithfulness run (n=30, independent Gemini judge) measured mean faithfulness at 0.864, missing the ≥0.90 target by approximately 3.6 percentage points. The residual unsupported claims trace primarily to three hard cases (qa_027 0.59, qa_016 0.61, qa_012 0.62) where the care-plan synthesis paraphrases clinical knowledge not explicitly present in the retrieved chunks — a known property of instruction-tuned language models. The judge-fairness methodology was rigorously controlled (independent judge, full population, 0 rate-limit gaps, dose/drug/threshold strictness preserved), so the 0.864 is the honest number for a single pass. Hardening it to a publishable mean±sd requires repeated runs.

**nDCG@10 retrieval ranking (0.669 vs ≥0.75 target).** The vector retrieval store meets the recall target but misses on ranking quality. Most rows in the 148-row gold carry 1–3 graded-relevant chunks; nDCG demands several relevant chunks ranked high, not just one anywhere in top-10. The gap is partly structural (≤3 relevant chunks against a denominator of 10) and partly tunable (chunk size, BM25 weighting). Precision@5 (0.251 vs ≥0.50) is structurally bounded in the same way.

**DDx exact-leaf vs lineage gap.** Exact Hit@5 = 0.771 while lineage Hit@5 = 0.971. The 8 exact misses are all leaf↔parent ICD-11 family granularity disagreements, not wrong-family errors — the pipeline returns the correct disease family but a different specificity level than the gold's single accepted code. The gap is a scoring artefact more than a clinical error, but it means the pipeline cannot claim verbatim ICD-11 code precision at ≥0.90 on the gold set.

**Non-determinism in co-equal-diagnosis cases.** The primary diagnosis is stable across 10 runs only when a single dominant diagnosis exists (cases 8 and 9, top-1 = 10/10). When two clinical diagnoses are co-equally explicit in the chief complaint (case 10: GDM vs pregnancy HTN; case 11: ED vs T2DM), the seedless Gemini reranker flips the top-1 across runs. The Stage-2 candidate query is byte-identical across runs, so the non-determinism is isolated to the reranker's lack of a settable seed. Moving the rerank to a seedable backend would close this gap but requires an A1 re-validation.

**Latency at ~2.5 minutes.** The end-to-end latency pilot (n=3) measured a mean of 141.9 seconds, with Stage 5 care-plan synthesis as the dominant cost at ~43% of total. The published target of `p95 < 8 s` in the validation plan was calibrated for a retrieval-only RAG system, not a two-LLM-call pipeline. The realistic target for this architecture is `p95 < 60 s` end-to-end with Stage 5 < 35 s; neither has been achieved. The expert clinician evaluation explicitly flagged this as the most significant barrier to in-consult adoption.

**Application-tier test suites not executed.** The Supabase data layer, authentication, and the Doctor UI frontend all have defined test plans but no executed results. The care-plan delivery flow and the knowledge-graph helper tests carry real tests; the data layer, auth, and UI suites are planned and have not run. This is the single largest testing gap in the project.

**Stakeholder validation blocked.** The blinded multi-clinician evaluation (target: ≥3 clinicians across Cardiology, Endocrinology, and O&G) requires IRB approval and clinician recruitment, estimated at 6–8 weeks. The single expert evaluation performed was conducted without blinding or competitor outputs, and without a locked gold answer key. Its findings are treated as directional, not as the full validation event.

**KG coverage boundary.** The drug knowledge graph covers interactions for the conditions and medications present in the 30-CPG corpus. It is not a complete pharmacological database. Drug pairs outside the curated edge set will not generate KG-sourced flags, and there is no coverage metric published for the KG's recall against a gold interaction set.

---

## 5.5 Future Improvements

The improvements below are listed in order of clinical impact, not implementation complexity.

**Reduce end-to-end latency (highest clinical impact).** Stage 5 synthesis is the single largest cost driver (~43% of total). The most direct levers are: (1) switching Stage 5 to a streaming output so the clinician sees the plan section by section rather than waiting for the full response; (2) caching DDx and routing results for repeat presentations of the same chief-complaint pattern; (3) profiling and reducing prompt length for common cases. The target is `p50 < 60 s end-to-end`, which would bring the tool within the consultation window for case-review use.

**Close the faithfulness gap.** Three cases (qa_027, qa_016, qa_012) account for a disproportionate share of the 0.136 faithfulness gap. Targeted triage — inspecting which claim types fail and whether they trace to missing chunks, paraphrase of background knowledge, or synthesis extrapolation — would allow a focused prompt or retrieval fix rather than a full pipeline retrain. The judge-context lever (passing the patient's existing regimen to the faithfulness judge) is implemented and awaiting a re-run that could lift the headline modestly at no system cost.

**Improve retrieval ranking quality (nDCG@10).** Two options are available without changing the retrieval architecture: smaller chunk size (splitting current ~500-token chunks to ~200–300 tokens would increase the count of individually rankable relevant units) and BM25 weight retuning to reduce the keyword arm's noise on ranking. A third option — replacing the RRF hybrid with a learned re-ranker trained on the graded gold — would require more engineering but could close the nDCG gap structurally.

**Seed the DDx re-ranker for determinism.** Moving Stage-2 LLM re-ranking from Gemini (which 400s on `seed`) to a seedable backend (MiMo or equivalent with `enable_thinking:False`) would close the co-equal-dx top-1 instability observed in Cases 10 and 11. This requires a full A1 re-validation on the 35-vignette DDx gold set to confirm that the swap does not regress exact or lineage Hit@5.

**Execute application-tier test suites.** The Supabase data layer, authentication, and the Doctor UI frontend have defined test plans. Running the data-layer tests against a Supabase test project, the Vitest unit suite, and the Playwright e2e suite against a staging Doctor UI are the most straightforward near-term quality steps. Until these are executed, the longitudinal persistence and role-based access-control claims rest on design intent rather than measured behaviour.

**Multi-clinician blinded evaluation.** The single expert evaluation provides directional signal but not statistically reportable validation. Recruiting ≥3 clinicians across Cardiology, Endocrinology/Internal Medicine, and O&G — scoring blinded outputs against a locked gold answer key with competitor baselines — would convert the validation from anecdote to data. The rubrics and scoring formula are already defined in the Evaluation Framework; the blocking step is IRB approval and clinician scheduling.

**Expand the KG coverage.** Extending the drug knowledge graph to cover drug classes not currently in the 30-CPG corpus (e.g., ophthalmological agents, antiretrovirals, immunosuppressants) would reduce the risk of missed interactions for patients with comorbidities outside the current CPG scope. A coverage audit — comparing the KG's interaction edge set against a standard pharmacological reference — would quantify the current gap before expansion begins.

**UI output simplification for fast triage.** The expert clinician evaluation scored Information Density at 3/5 and Workflow Fit at 2/5, with an explicit note that the structured output is suited to long review, not fast triage. A "summary mode" that renders only P2 (medications with action tags), P6 (referrals), and P7 (red flags) — with the full 9-section plan accessible on demand — would target the sub-3-minute triage workflow without discarding the depth available for complex cases.

---

## 5.6 Concluding Remarks

ClearPath demonstrates that a compound system — deterministic routing, grounded retrieval, and an independent safety critic — can reliably surface CPG-aligned care plans for multi-comorbid rural primary care presentations within a single consultation. The backbone results (perfect routing, 97.1% lineage DDx accuracy, 100% scope-refusal, 86.4% faithfulness, 6/6 fail-loud robustness, dual-source safety confirmed by an expert evaluator) establish that the architecture is sound and the safety contract holds for the cases tested.

The honest picture also includes what is not yet finished: the faithfulness and nDCG ranking gaps, the ~2.5-minute latency, the application-tier test suites that have not run, and the multi-clinician blinded validation that requires IRB. These are not concealed limitations — they are the precise agenda for the work that follows.

The system addresses a real and documented infrastructure gap. Where a second clinical opinion changes or refines the original diagnosis in up to 88% of reviewed complex cases, and where rural Malaysian clinics routinely operate without a resident doctor or pharmacist, a CPG-grounded, safety-enforcing, auditable decision-support tool is not a convenience — it is a structural intervention. ClearPath is a working prototype of that intervention. Making it fast enough and simple enough for the 10-minute rural consultation is the next engineering task; demonstrating its clinical impact on patient outcomes is the research task that follows deployment.
