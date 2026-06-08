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

Each limitation below is paired with the enhancement that addresses it.

### 5.3.1 Latency and Consultation-Window Fit

**Limitation.** End-to-end latency averages ~2.5 minutes (mean ~142 s), with Stage 5 synthesis alone accounting for ~43% of that time. That fits a considered case review comfortably, but leaves a thin margin once the rest of the consultation is added, so the tool currently suits review better than fast triage — the adoption barrier the expert evaluator flagged most strongly.

**Future Enhancement.** The biggest real-world gains come from *perceived* latency rather than raw compute: streaming Stage 5 output so the clinician sees the first recommendations within seconds, a semantic cache/memory layer so repeat patterns are not recomputed, and a fast-triage summary view that surfaces the essentials first with full depth on demand. At production scale, faster or regional inference endpoints, horizontal concurrency, and lighter or fine-tuned stage models bring time-to-first-recommendation into the few-seconds range clinicians expect.

### 5.3.2 Faithfulness and Retrieval Ranking

**Limitation.** Mean faithfulness is 0.864 against a ≥0.90 target — a ~3.6 pp gap traced to a few hard cases where synthesis paraphrases knowledge not present in the retrieved chunks. Retrieval recall and hit-rate pass, but nDCG@10 falls short because most queries surface only 1–3 relevant chunks, making a high ranking score structurally difficult. Neither is a wrong-family retrieval error; both are precision and ranking gaps.

**Future Enhancement.** Triage the failing claim types to separate missing-chunk failures from background-knowledge paraphrase, enabling a targeted prompt or retrieval fix rather than a full retrain. Tune chunk size and BM25 weighting; a learned re-ranker trained on the graded gold could close the nDCG gap structurally.

### 5.3.3 Determinism

**Limitation.** The primary diagnosis is stable across runs only when a single dominant diagnosis exists; when two diagnoses are co-equally explicit, the seedless re-ranker flips the top-1. The candidate query is byte-identical across runs, so the variance is isolated to a single component — the re-ranker's lack of a settable seed.

**Future Enhancement.** Move Stage-2 re-ranking to a seedable backend to stabilise top-1 for co-equal-diagnosis cases, followed by an A1 re-validation to confirm no regression in exact or lineage Hit@5 before deployment.

### 5.3.4 Clinician Feedback and Human-in-the-Loop Tuning

**Limitation.** Clinical evaluation so far is a single expert (n=1, unblinded) on CPG-scope routing — a directional data point, not the large-scale, diverse input that practising clinicians across specialties would provide. Without that breadth of real-world feedback, the system's recommendation ranking, confidence calibration, and safety guardrails cannot yet be tuned to how clinicians actually practise.

**Future Enhancement.** Run a multi-clinician blinded evaluation (≥3 across Cardiology, Endocrinology, and O&G; the rubric and scoring are already designed, with IRB approval the blocker), then operationalise a human-in-the-loop feedback loop in which clinicians' edits, overrides, and approval signals continuously refine prompts, ranking, and guardrails. The feedback ecosystem that already captures these clinician signals is the foundation for that loop.

### 5.3.5 Knowledge Graph Coverage and Scope

**Limitation.** The knowledge graph today models only the *drug* space of the 30-CPG corpus — interactions, contraindications, and monitoring — and has no published recall figure against a gold interaction set, so its safety arm can only be characterised as "flags what the graph knows." Drug pairs outside the curated edge set produce no flag, and the graph does not yet represent clinical relationships beyond medications.

**Future Enhancement.** Audit the edge set against a standard pharmacological reference to quantify coverage, then broaden the graph in two directions: more drug classes for completeness, and entirely new clinical relationships beyond medications — disease–disease comorbidity, symptom–disease, lab–condition, and guideline–recommendation links — evolving it from a drug-safety graph into a general clinical knowledge graph that also serves DDx and routing. As a deterministic, continuously-growing asset, richer edges plus GraphRAG-style multi-hop traversal would let it act as a reasoning substrate, surfacing indirect paths that single-pass vector retrieval misses.

### 5.3.6 Corpus Coverage, Expansion, and Maintenance

**Limitation.** The validated corpus is a curated 30-CPG subset of the full Malaysian MOH guideline library, so any presentation outside it is refused rather than answered — a deliberate safety choice that nonetheless bounds clinical reach. Expanding the corpus is not a pure ingestion task: each new CPG needs clinician input to validate its scope-routing and KG extraction, and ingestion, embedding, and review cost and time scale with corpus size. Today that work is largely manual (~2–4 h engineering per CPG, §6.4), so breadth is gated on human effort.

**Future Enhancement.** Build a semi-autonomous ingestion pipeline that detects new or revised MOH CPGs, then chunks, embeds, extracts KG edges, and runs the evaluation-harness regression automatically — leaving clinicians to validate scope and edges rather than perform the mechanical steps. Lowering the marginal cost of each added guideline is the prerequisite for moving from a 30-CPG pilot toward full-corpus coverage.

### 5.3.7 Connectivity and Offline Resilience

**Limitation.** The system is online-only: every consultation depends on live calls to cloud databases and cloud LLM endpoints. The rural and district clinics it targets often have intermittent or low-bandwidth connectivity, so a network drop means no tool at exactly the moment of care — a poor fit for the deployment environment.

**Future Enhancement.** Add an offline-tolerant data-sync layer that queues writes and retries on reconnect, with local caching of recent patients and the CPG index so retrieval degrades gracefully rather than failing. For the most connectivity-poor sites, an edge or on-premise deployment of the deterministic stages would keep the system useful when the cloud is unreachable.

### 5.3.8 Model Selection, Hosting, and Data Residency

**Limitation.** Patient data currently transits general-purpose third-party endpoints — Gemini (Google), MiMo (Xiaomi), and AWS Bedrock — some hosted outside Malaysia, across a data layer spread over several managed services (Neon, Supabase, Neo4j Aura) with no single in-country residency guarantee. None are health-sector-certified, which is a barrier to public-health deployment (the compliance dimension is treated as a risk in §6.5 and §6.6). The build pipeline also favours lighter, cheaper models — Claude Haiku for KG edge extraction and Titan v1 embeddings — trading some extraction accuracy and embedding fidelity for cost.

**Future Enhancement.** Migrate to a health-sector-compliant cloud with a Malaysian region — Azure for Health or AWS in the local region, with managed object storage and in-country data residency — or self-host the models and databases for full data control. The same model-selection layer (each stage's model is already abstracted behind environment configuration) lets capability be raised where it most affects quality: a higher-reasoning model such as Claude Opus 4.8 for build-time KG edge extraction, and a newer-generation embedding model such as Titan v2 to curb the semantic dilution that currently blurs near-duplicate codes and chunks. Conversely, where a stage's task is narrow and repetitive, parameter-efficient fine-tuning (LoRA) or stage-specific supervised fine-tuning could match a larger model's quality on a smaller, faster, cheaper one — improving accuracy and latency together. These are configuration or training choices, so compliant hosting, model upgrades, and fine-tuning can all proceed without re-architecting the pipeline.

### 5.3.9 Contactless Vitals (rPPG)

**Limitation.** The rPPG module captures heart rate, SpO₂, and respiratory rate from a webcam — valuable where a clinic's pulse oximeter is broken or unavailable — but the readings have not been clinically validated against medical-grade devices, and the technique is sensitive to lighting, motion, and skin tone. Its parameter set is also narrow (no blood pressure or temperature), so it supplements rather than replaces standard vitals capture.

**Future Enhancement.** Run a validation study comparing rPPG readings against reference oximeters and monitors to establish accuracy bounds and surface a per-reading confidence indicator to the clinician, and harden the signal pipeline against lighting, motion, and skin-tone variation. Expanding the captured parameters — blood-pressure estimation, heart-rate variability — would widen its clinical usefulness.

### 5.3.10 EMR / HIS Integration

**Limitation.** Patients and finalised plans are persisted to the system's own Supabase store — a deliberate stand-in for a clinical record system — rather than to a live EMR/HIS. The patient case is therefore entered into ClearPath rather than drawn from existing records, and the plan is not written back into the clinic's official chart; EMR/HIS interoperability was an explicit scope exclusion of the current evaluation.

**Future Enhancement.** Because the record layer is deliberately abstracted behind this stand-in, integrating a Malaysian EMR/HIS (e.g., Teleprimary Care, hospital HIS) once access is granted is a substitution rather than a re-architecture — auto-populating the typed `PatientCase` from existing records and writing the finalised plan back to the chart. This removes manual entry and strengthens the longitudinal prior-visit loop, fitting the tool more naturally into the encounter.

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
