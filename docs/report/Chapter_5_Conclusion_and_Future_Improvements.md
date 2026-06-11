# CHAPTER 5: CONCLUSION AND FUTURE IMPROVEMENTS

## 5.1 Project Outcome

ClearPath was built to close one specific gap: clinical decision isolation in Malaysia's rural and district primary care clinics, where a single clinician must manage a wide case spectrum without access to a colleague, a usable guideline, or a pharmacist. The system built and evaluated is a seven-stage hybrid deterministic–agentic pipeline, grounded in 30 validated Malaysian MOH CPGs and a curated drug knowledge graph, that accepts a structured patient case and returns a schema-validated, action-tagged care plan with dual-source safety checking.

The outcome is a working system that does what it set out to do: it routes a patient case to the right guideline, retrieves the evidence behind each recommendation, checks the resulting plan for medication risk against two independent sources, and returns an auditable plan a clinician can read, trace, and edit. Where it falls short, it does so narrowly — slightly below target on answer faithfulness and on consultation-window speed — and never in a way that hides its reasoning. The one dimension that could not be assessed without recruiting clinicians, a multi-clinician blinded study, remains the main outstanding validation step. This is stated plainly, not softened.

---

## 5.2 Achievement Against Objectives

The four objectives from Chapter 1, assessed against the measured evidence of Chapter 4:

*Table 5.1: Achievement against objectives.*

| # | Objective | Verdict | Basis |
|---|---|---|---|
| 1 | Real-time, evidence-backed clinical second opinion | **Largely met** | • Maps presentation → ICD-11 differential, then deterministically scopes to the governing CPG — refusing cleanly when none applies (routing exact, 44/44; out-of-scope 11/11)<br>• Each recommendation citation-traceable to its CPG section and evidence-graded, replacing manual guideline search (Recall@10 0.87, Hit@10 0.95)<br>• Delivered within the consult window (~2.4 min) but not yet real-time for live triage — the in-consult speed qualifier shared with Objective 2; exact-leaf and ranking precision still maturing (DDx lineage Hit@5 0.97) |
| 2 | Transparent, auditable second opinion with per-stage reasoning traces | **Largely met** | • Inspectable per-stage reasoning trace end-to-end — beyond any Chapter 1 peer (reasoning-visibility 5/5)<br>• Every recommendation traceable to its CPG citation and KG provenance for trust and accountability<br>• Runs within the consult window; in-consult speed is the remaining optimisation, not a correctness gap (~2.4 min) |
| 3 | Dual-source medication safety critic | **Met** | • Dual-source critic (LLM reasoning ‖ deterministic drug KG) blocks sign-off until every critical flag is acknowledged<br>• Catches what one source misses — unprompted KG interaction, teratogen veto, pre-empted not-yet-prescribed drug<br>• Critic recall at target; expert Safety at ceiling (SAF 5/5; clinician 15/15) |
| 4 | Structured, executable longitudinal care plan in routine workflow | **Largely met** | • Schema-validated, action-tagged eight-section plan, editable end-to-end<br>• Carried across visits via the prior-visit summarisation loop, slotting into the routine workflow<br>• Built and working; broad multi-visit real-world exercise is the natural next step |

All four objectives are met or substantially met. The three qualified verdicts reflect maturity headroom — consult-window speed (Objectives 1 and 2) and multi-visit field exercise (Objective 4) — on capabilities that are already implemented and working, not design gaps.

### 5.2.1 Closure Against the Chapter 2 Measurable Contract

Chapter 2 committed the design to a measurable contract: nine prioritised customer needs (Table 2.3), mapped through the Needs–Metrics Matrix (Table 2.4) onto thirteen target specifications (Table 2.5). This subsection retires that contract at both levels against the measured evidence of Chapter 4.

*Table 5.2: Target-specification closure (the thirteen metrics of Table 2.5).*

| # | Metric | Marginal target | Measured result | Status |
|---|---|---|---|---|
| 1 | System response time | ≤ 180 s | ~141.9 s mean (pilot, n=3) | Met |
| 2 | Diagnosis relevance | ≥ 85% | Hit@5 lineage 0.97; exact 0.77 | Met (lineage) |
| 3 | Care plan completeness | ≥ 85% | 8/8 sections, 3/3 end-to-end cases (§4.5.1) | Met (structural) |
| 4 | Care plan appropriateness | ≥ 85% | Clinical Correctness 4.56/5 (clinician, blinded) | Met (clinician rubric) |
| 5 | Clinical accuracy (faithfulness) | ≥ 85% | 0.864 mean per-claim | Close (below 0.90 ideal) |
| 6 | Safety issue detection rate | ≥ 90% | SAF sensitivity 92% (8 runs); clinician Safety 5.00/5 | Met |
| 7 | Unsafe plan block rate | 100% | Sign-off blocked on every critical flag (§4.5.1) | Met |
| 8 | Citation coverage | ≥ 85% | Citation Quality 4.56/5; faithfulness 0.864 as proxy | Met (clinician rubric) |
| 9 | Patient history carry-over | ≥ 90% | Prep-brief / MPIS sync functionally verified (§4.4.1.3) | Functionally met — not %-quantified |
| 10 | Usability satisfaction | ≥ 3.8/5 | UI-UX 21/30; reasoning-visibility & override 5/5, workflow & latency 2/5 | Partially met |
| 11 | Out-of-scope detection rate | ≥ 90% | Orphan refusal 11/11 (100%) | Met |
| 12 | Reasoning-trace transparency | ≥ 90% | Reasoning-visibility 5/5; full per-stage trace | Met |
| 13 | Appropriate referral/deferral | ≥ 85% | Appropriate Deferral 4.44/5 (clinician) | Met (clinician rubric) |

Five of the thirteen (3, 4, 8, 9, 13) were assessed through the blinded clinician rubric (/5) and end-to-end functional runs rather than standalone percentage harnesses; they are reported against that evidence, not the original numeric threshold. Patient-history carry-over (9) is functionally verified but not yet percentage-quantified — a measured multi-visit study is carried forward as future work (§5.3, Limitation 4).

*Table 5.2b: Customer-needs fulfilment (the nine needs of Table 2.3, rolled up through Table 2.4).*

| # | Need (priority) | Serving metrics | Verdict and evidence |
|---|---|---|---|
| 1 | Real-time diagnostic suggestions (5) | response time, dx relevance | **Largely met** — DDx lineage Hit@5 0.97; within consult window (~2.4 min) but not real-time (see Objective 1) |
| 2 | Complete actionable care plan (5) | response time, completeness, appropriateness, usability, referral/deferral | **Met** — 8/8 sections across all 3 cases; Clinical Correctness 4.56/5; Appropriate Deferral 4.44/5 |
| 3 | Medication safety audit and block (5) | safety detection, unsafe-plan block | **Met** — SAF specificity 100% / sensitivity 92%; clinician Safety 5.00/5; sign-off blocked on critical flags |
| 4 | CPG grounding and citations (4) | citation coverage | **Met** — Citation Quality 4.56/5; faithfulness 0.864; Recall@10 0.87 |
| 5 | Out-of-scope refusal (4) | out-of-scope detection | **Met** — orphan refusal 11/11 (100%) |
| 6 | Auditable reasoning (4) | reasoning-trace transparency | **Met** — reasoning-visibility 5/5; full per-stage trace |
| 7 | Prior-visit continuity (3) | carry-over, usability | **Functionally met** — prep-brief / MPIS sync (§4.4.1.3); not %-quantified — multi-visit field exercise is future work |
| 8 | Clinically accurate and expert-validated (5) | dx relevance, appropriateness, clinical accuracy | **Largely met** — DDx lineage 0.97, faithfulness 0.864, Clinical Correctness 4.56/5; expert validation conducted but on a single-session three-evaluator cohort (see §5.3, Limitation 4) |
| 9 | Clinician final control (4) | usability | **Met** — override and sign-off enforced; override & feedback 5/5 |

The projected competitor benchmark of Table 2.6 was realised through the blinded three-system clinician comparison of §4.5.3 (Table 4.21), which replaces the original mixed-unit projections with a single rigorous clinical-quality rubric scored by independent evaluators. ClearPath led every dimension (overall 4.59 vs Qmed AskCPG 4.18, NotebookLM 4.24), confirming the directional advantage Table 2.6 projected.

---

## 5.3 Limitations and Future Improvements

*Table 5.3: Limitations and Future Enhancements*

| # | Area | Current Limitation | Future Enhancement |
|---|---|---|---|
| 1 | **Latency** | • End-to-end runtime averages ~2.5 minutes<br>• Stage 5 synthesis alone accounts for ~43% of total time<br>• Suits case review, but too slow for fast triage<br>• Flagged as the top adoption barrier by the expert evaluator | • Stream Stage 5 output so clinicians see results as they generate<br>• Cache repeat presentations to avoid recomputation<br>• Add a fast-triage summary view (medications, referrals, red flags only)<br>• Deploy lighter or fine-tuned models at production scale |
| 2 | **Faithfulness & Retrieval Ranking** | • Mean faithfulness is 0.864, below the ≥0.90 target<br>• Synthesis occasionally paraphrases knowledge not in retrieved chunks<br>• nDCG@10 falls short as most queries return only 1–3 relevant chunks<br>• A ranking gap, not a wrong-family retrieval error | • Triage failing claims to separate missing-chunk from paraphrase failures<br>• Tune chunk size and BM25 weighting for better ranking<br>• Train a learned re-ranker on the graded gold set |
| 3 | **Determinism** | • Top-1 diagnosis is stable only when one diagnosis clearly dominates<br>• Seedless re-ranker flips the top result when two diagnoses are co-equal<br>• Variance is isolated to a single component — no settable seed | • Switch Stage-2 re-ranking to a seedable backend<br>• Re-validate on the 35-vignette gold set before deployment<br>• Confirm no regression in exact or lineage Hit@5 |
| 4 | **Clinician Validation** | • Evaluated by a five-clinician blinded panel against two competitor systems (QMed AskCPG, NotebookLM) across three multimorbid cases<br>• A small, single-session cohort, not stratified by specialty and not capturing longitudinal prescribing behaviour<br>• Captured clinician edits, overrides, and approvals are logged in the feedback ecosystem but not yet fed back into the pipeline | • Scale the blinded panel into a specialty-stratified cohort (Cardiology, Endocrinology, O&G) for statistical power<br>• Reuse the rubric already designed — IRB approval is the blocker<br>• Operationalise a human-in-the-loop loop that maps captured edits, overrides, and approvals back into prompts, ranking, and guardrail calibration |
| 5 | **KG Coverage** | • Knowledge graph covers only the drug space of the 30-CPG corpus<br>• No recall figure measured against a gold interaction set<br>• No clinical relationships beyond medications are modelled | • Audit the edge set against a standard pharmacological reference<br>• Broaden to more drug classes and new relationship types (disease–disease, symptom–disease, lab–condition)<br>• Enable GraphRAG multi-hop traversal for indirect clinical reasoning |
| 6 | **Corpus Coverage & Maintenance** | • Covers only 30 CPGs from the full MOH library<br>• Presentations outside the corpus are refused by design<br>• Each new CPG requires ~2–4 hours of manual engineering and clinical review | • Build a semi-autonomous ingestion pipeline<br>• Automatically chunk, embed, extract KG edges, and run regression tests<br>• Clinicians validate scope and edges only — not the mechanical steps |
| 7 | **Offline Resilience** | • System is entirely online — depends on live cloud calls<br>• A network drop leaves the clinician without the tool at the moment of care<br>• Rural clinics often have intermittent or low-bandwidth connectivity | • Add an offline data-sync layer with local caching of recent patients and the CPG index<br>• Deploy deterministic pipeline stages on-premise for connectivity-poor sites<br>• Graceful degradation so retrieval continues when the cloud is unreachable |
| 8 | **Model Hosting & Data Residency** | • Patient data transits third-party non-Malaysian endpoints (Gemini, MiMo, Bedrock)<br>• No in-country data residency guarantee<br>• No health-sector certification — a barrier to public-health deployment | • Migrate to a health-compliant Malaysian-region cloud (Azure for Health or AWS in-region)<br>• Upgrade KG extraction to a higher-reasoning model and Titan v2 embeddings<br>• Apply stage-specific LoRA fine-tuning where tasks are narrow and repetitive |
| 9 | **Contactless Vitals (rPPG)** | • Clinically unvalidated against medical-grade reference devices<br>• Sensitive to lighting conditions, motion, and skin tone<br>• Narrow parameter set — does not capture blood pressure or temperature | • Run a validation study comparing rPPG readings against reference oximeters<br>• Surface a per-reading confidence indicator to the clinician<br>• Harden the signal pipeline against lighting and motion artefacts<br>• Expand captured parameters to include BP estimation and heart-rate variability |
| 10 | **EMR / HIS Integration** | • Plans are stored in a standalone Supabase mock-EMR, not a live clinical system<br>• Patient data must be entered manually into ClearPath<br>• Finalised plans are not written back to the clinic's official chart | • Substitute the Supabase layer with a Malaysian EMR/HIS (e.g., Teleprimary Care)<br>• Auto-populate the patient case from existing records<br>• Write the finalised care plan back to the official chart after sign-off |

---

## 5.4 SWOT Analysis

| **Strengths** | **Weaknesses** |
|---|---|
| ICD-11 routing with first-class scope refusal | ~2.5 min latency — review speed, not yet fast triage |
| Dual grounding (vector + KG), unreachable by reprompting | Single expert evaluation (n=1); clinical validation breadth limited |
| Schema-validated, action-tagged care plan | Online-only — limited offline resilience for rural sites |
| MOH-grounded corpus with full per-stage audit trace | Standalone store (mock EMR); no live EMR/HIS link yet |

| **Opportunities** | **Threats** |
|---|---|
| National Digital Health Blueprint + rural-clinic digitisation | Fast-moving general LLMs — edge must stay grounding-led |
| rPPG contactless vitals for resource-scarce clinics | Data residency & compliance to clear before deployment |
| Post-pandemic telehealth / async consultation | Reliance on third-party model & cloud providers |
| Dual-grounding RAG core reusable as an SDK / API | Corpus upkeep effort as MOH guidelines evolve |

**Strengths** are structural rather than incidental. Scope-aware routing and dual grounding give ClearPath two things a reprompted LLM cannot: it refuses cases outside its evidence base, and it flags drug risks the source text never mentions. Every recommendation arrives as a schema-validated, action-tagged plan whose every stage is auditable against the MOH corpus.

**Weaknesses** are matters of maturity, not design — each is an operational or validation gap with a defined path to closure in §5.3. Notably, the single-expert evaluation (n=1) limits how confidently the system's clinical ranking and guardrails can be tuned to real practice; this is the most significant outstanding gap before broader deployment.

**Opportunities** are timely. National digital-health policy and rural-clinic digitisation give the system momentum, post-pandemic telehealth and rPPG contactless vitals extend its reach into resource-scarce clinics, and the dual-grounding core is reusable beyond this product as an SDK or API.

**Threats** are external and manageable. General LLMs keep improving, so the edge must stay grounding- and safety-led rather than model-led; data residency and compliance must be cleared before deployment; and third-party-provider reliance plus ongoing corpus upkeep are operational realities — each tracked by the agenda in §5.3 and the governance plan in §6.6.
