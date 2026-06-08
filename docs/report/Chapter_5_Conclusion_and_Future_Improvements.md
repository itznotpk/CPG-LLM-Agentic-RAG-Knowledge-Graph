# CHAPTER 5: CONCLUSION AND FUTURE IMPROVEMENTS

## 5.1 Project Outcome

ClearPath was built to close one specific gap: clinical decision isolation in Malaysia's rural and district primary care clinics, where a single clinician must manage a wide case spectrum without access to a colleague, a usable guideline, or a pharmacist. The system built and evaluated is a seven-stage hybrid deterministic–agentic pipeline, grounded in 30 validated Malaysian MOH CPGs and a curated drug knowledge graph, that accepts a structured patient case and returns a schema-validated, action-tagged care plan with dual-source safety checking.

The outcome is a working system that does what it set out to do: it routes a patient case to the right guideline, retrieves the evidence behind each recommendation, checks the resulting plan for medication risk against two independent sources, and returns an auditable plan a clinician can read, trace, and edit. Where it falls short, it does so narrowly — slightly below target on answer faithfulness and on consultation-window speed — and never in a way that hides its reasoning. The one dimension that could not be assessed without recruiting clinicians, a multi-clinician blinded study, remains the main outstanding validation step. This is stated plainly, not softened.

---

## 5.2 Achievement Against Objectives

The four objectives from Chapter 1, assessed against the measured evidence of Chapter 4:

| # | Objective | Verdict | Basis |
|---|---|---|---|
| 1 | Unified, machine-interpretable MOH-CPG knowledge base | **Met** | • Every tested ICD-11 code routes to the correct CPG (Top-1 and Hit@3 both 100%, 44/44)<br>• Out-of-scope cases refuse cleanly as a first-class event (11/11 separation)<br>• Retrieval Recall@10 (0.87) and Hit@10 (0.95) both clear target across all 30 embedded CPGs<br>• Ranking quality (nDCG) is the single metric still maturing — recall and routing are solid |
| 2 | Transparent, auditable second opinion within the consult window | **Largely met** | • Reasoning-transparency scores sit at ceiling — no Chapter 1 peer system matches the per-stage auditable trace<br>• Every recommendation carries its CPG citation and KG provenance, so the clinician can verify the "why"<br>• End-to-end runs in ~2.5 min — comfortably inside a consultation; the remaining work is optimising toward faster triage, not correctness |
| 3 | Medication safety via a dual-source critic | **Met** | • Dual-source critic (LLM reasoning ‖ deterministic drug KG) cross-checks every plan<br>• Demonstrated surfacing an unprompted KG interaction, vetoing a teratogen against pregnancy, and pre-empting a not-yet-prescribed drug<br>• Expert Safety score at ceiling across the tested cases |
| 4 | Structured, executable longitudinal care plan | **Largely met** | • Schema-validated, action-tagged care plan generated end-to-end<br>• Editable medication / care / monitoring sections plus the prior-visit summarisation loop are live<br>• The longitudinal carry-forward is built and working; broad exercise across repeated real-world visits is the natural next step |

All four objectives are met or substantially met. The two qualified verdicts reflect maturity headroom — consult-window speed and multi-visit field exercise — on capabilities that are already implemented and working, not design gaps.

---

## 5.3 Limitations and Future Improvements

*Table 5.3: Limitations paired with their future enhancement pathway.*

| # | Area | Current Limitation | Future Enhancement |
|---|---|---|---|
| 1 | **Latency** | ~2.5 min end-to-end; Stage 5 synthesis = ~43% of total time. Suits case review but not fast triage — the barrier flagged most strongly by the expert evaluator. | Stream Stage 5 output section-by-section; semantic cache for repeat patterns; fast-triage summary view (medications, referrals, red flags only); lighter/fine-tuned stage models at production scale. |
| 2 | **Faithfulness & Retrieval Ranking** | Mean faithfulness 0.864 vs ≥0.90 target; nDCG@10 below target because most queries surface only 1–3 relevant chunks, making high ranking scores structurally difficult. | Triage failing claim types (missing-chunk vs paraphrase); tune chunk size and BM25 weighting; train a learned re-ranker on the graded gold set. |
| 3 | **Determinism** | Top-1 diagnosis stable only with a single dominant diagnosis; seedless re-ranker flips top-1 when two diagnoses are co-equally explicit. Variance is isolated to one component. | Switch Stage-2 re-ranking to a seedable backend; re-validate A1 on the 35-vignette gold before deployment to confirm no regression. |
| 4 | **Clinician Validation** | Single expert evaluation (n=1, unblinded); insufficient breadth to tune recommendation ranking, confidence calibration, and safety guardrails to real clinical practice. | Multi-clinician blinded evaluation (≥3 across Cardiology, Endocrinology, O&G; rubric ready, IRB is the blocker); human-in-the-loop feedback loop from clinician edits and overrides. |
| 5 | **KG Coverage** | Models only the drug space of the 30-CPG corpus; no recall figure against a gold interaction set; no clinical relationships beyond medications. | Audit edge set against a pharmacological reference; broaden to more drug classes and new relationship types (disease–disease, symptom–disease, lab–condition); GraphRAG multi-hop traversal. |
| 6 | **Corpus Coverage & Maintenance** | 30-CPG subset of full MOH library; presentations outside refused by design. Each new CPG requires ~2–4 h manual engineering for ingestion, scope validation, and KG extraction. | Semi-autonomous ingestion pipeline: auto-chunk, embed, extract KG edges, and run harness regression; clinicians validate scope and edges only, not mechanical steps. |
| 7 | **Offline Resilience** | Online-only — every consultation depends on live cloud calls. Network drop means no tool at the moment of care; poor fit for rural intermittent connectivity. | Offline data-sync layer with local caching of recent patients and CPG index; edge/on-premise deployment of deterministic stages for connectivity-poor sites. |
| 8 | **Model Hosting & Data Residency** | Patient data transits third-party non-Malaysian endpoints (Gemini, MiMo, Bedrock) with no in-country residency guarantee and no health-sector certification — a barrier to public-health deployment. | Migrate to a health-compliant Malaysian-region cloud (Azure for Health or AWS in-region); upgrade KG extraction to a higher-reasoning model and Titan v2 embeddings; stage-specific LoRA fine-tuning where tasks are narrow. |
| 9 | **Contactless Vitals (rPPG)** | Clinically unvalidated against medical-grade devices; sensitive to lighting, motion, and skin tone; narrow parameter set (no BP or temperature). | Validation study vs reference oximeters; per-reading confidence indicator; hardened signal pipeline; expanded parameters (BP estimation, heart-rate variability). |
| 10 | **EMR / HIS Integration** | Plans stored in standalone Supabase mock-EMR; no live EMR/HIS link; patient data entered manually rather than drawn from existing records. | Substitute Supabase layer with a Malaysian EMR/HIS (e.g., Teleprimary Care, hospital HIS); auto-populate PatientCase from existing records; write finalised plan back to the chart. |

---

## 5.4 SWOT Analysis

| **Strengths** | **Weaknesses** |
|---|---|
| ICD-11 routing with first-class scope refusal | ~2.5 min latency — review speed, not yet fast triage |
| Dual grounding (vector + KG), unreachable by reprompting | Faithfulness 0.864, just below the 0.90 target |
| Schema-validated, action-tagged care plan | Online-only — limited offline resilience for rural sites |
| MOH-grounded corpus with full per-stage audit trace | Standalone store (mock EMR); no live EMR/HIS link yet |

| **Opportunities** | **Threats** |
|---|---|
| National Digital Health Blueprint + rural-clinic digitisation | Fast-moving general LLMs — edge must stay grounding-led |
| rPPG contactless vitals for resource-scarce clinics | Data residency & compliance to clear before deployment |
| Post-pandemic telehealth / async consultation | Reliance on third-party model & cloud providers |
| Dual-grounding RAG core reusable as an SDK / API | Corpus upkeep effort as MOH guidelines evolve |

**Strengths** are structural rather than incidental. Scope-aware routing and dual grounding give ClearPath two things a reprompted LLM cannot: it refuses cases outside its evidence base, and it flags drug risks the source text never mentions. Every recommendation arrives as a schema-validated, action-tagged plan whose every stage is auditable against the MOH corpus.

**Weaknesses** are matters of maturity, not design — and each is a measured gap with a defined path to closure in §5.3.

**Opportunities** are timely. National digital-health policy and rural-clinic digitisation give the system momentum, post-pandemic telehealth and rPPG contactless vitals extend its reach into resource-scarce clinics, and the dual-grounding core is reusable beyond this product as an SDK or API.

**Threats** are external and manageable. General LLMs keep improving, so the edge must stay grounding- and safety-led rather than model-led; data residency and compliance must be cleared before deployment; and third-party-provider reliance plus ongoing corpus upkeep are operational realities — each tracked by the agenda in §5.3 and the governance plan in §6.6.
