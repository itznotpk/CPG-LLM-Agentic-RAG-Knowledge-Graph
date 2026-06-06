# CHAPTER 2: CONCEPT DEVELOPMENT

> Provide a list of project requirements and metrics that will be used to demonstrate that these have been satisfied, summarize the scope of ideas considered, and describe the processes and rationale used for selecting the "best" concepts for the overall product.

---

## 2.1 Identifying Customer Needs

To gain a comprehensive understanding of customer needs, interviews and surveys were conducted with various stakeholders across public healthcare, clinical academia, and health-technology industry, as listed in Table 2.1. Proof of these interviews, including pictures taken during the sessions, can be found in Appendix A. These engagements were anchored by our primary industry partner, **MHNexus**, whose operational exposure to Malaysia's rural *Klinik Kesihatan* network directed our attention to the **Remote Medicine** problem space — where junior Medical Officers (MOs) and Medical Assistants (MAs) deliver care under severe structural constraints.

*Table 2.1 List of stakeholders interviewed*

| Companies | Individuals | Position |
|---|---|---|
| MHNexus | Mr Billy Soo Kong Mooi | Chief Operating Officer |
| | Dr Teh Ee Von | Medical Officer |
| Kementrian Kesihatan Malaysia | Dr Wilson | Doctor in Klinik Kesihatan Belaga |
| | Dr Marcos Popey Jarith | Leader of one of the mobile clinics team |
| | Dr Farhan | Doctor in Klinik Kesihatan Kemabong |
| | Dr Ch'ng | Consultant / Senior Specialist in private hospital of Alor Setar |
| | Dr Gavin | Medical Officer in Hospital Kapit |
| | Dr Rajiv | Clinical Specialist in Hospital Kapit |
| | Dr Adibah M | Medical Officer in PKD Nabawan |
| | Dr Vignes A/L Subramaniam | Medical Officer in Hospital Kapit, Sarawak |
| Faculty of Medicine, University Malaya | Associate Prof. Dr Terence Ong Ing Wei | Associate Professor in University Malaya |
| Mudah HealthTech | Chin Jun Jie | Operation Executive |
| Remedi | Dr Khairul | Managing Director |
| | Mr Rashidi | Head of Business and Services |
| Clique Tech | Mr Ganesha Karuppiaya | Managing Director |
| | Mr Daniel | Chief Technical Officer |
| | Mr Robinsen | Account Manager |
| AlphaSwift | Mr Prathiv | Aeronautical Engineer |

Three structural realities surfaced consistently across the rural-facing interviews (Dr Wilson, Dr Marcos, Dr Farhan, Dr Adibah, Dr Vignes) and were corroborated by published statistics. First, up to **45.6% of rural clinics in East Malaysia operate without a resident doctor**, and only **53.5% of rural public clinics are staffed with a medical doctor** (versus 93.8% urban) — so the typical user is a junior MO/MA working in professional isolation. Second, authoritative Clinical Practice Guidelines (CPGs) run to **100+ pages**, yet a primary-care consultation lasts only **10.5–14.3 minutes**, making manual guideline lookup infeasible at the point of care. Third, **76% of Malaysian doctors** cite poor facilities to access evidence as a barrier to evidence-based practice — a gap that widens under the unstable connectivity and absent specialist/pharmacist backup of rural settings.

Using the information gathered, the customer needs are translated into formal statements to facilitate clear analysis. Rather than the broad functional buckets used in the initial study, the statements are re-categorised against the **three core clinical bottlenecks** that the final system is required to resolve, as shown in Table 2.2.

*Table 2.2: Categorized customer need statements*

| Category | Customer Need Statement |
|---|---|
| **1. Guideline Accessibility & Search Friction** | Clinicians need the right CPG recommendation surfaced within the consultation window, without manually opening and searching long PDF guidelines. |
| | The system must ground every recommendation in official, current Malaysian MOH CPGs rather than generic or unverifiable internet sources. |
| | The system must deliver evidence-graded answers (with their original MOH grading) so clinicians can judge the strength of each recommendation. |
| | Rural clinics need guidance that remains usable under unstable connectivity and limited clinic IT support. |
| | The system should route a patient's presentation to the correct guideline deterministically, so the same case yields the same scoped guidance regardless of who is using it. |
| | The system must recognise when a presentation falls outside the available validated guidelines and decline, rather than answering from loosely-related sources. |
| **2. Diagnostic Isolation & Cognitive Fatigue** | Junior clinicians working without on-site specialists need decision support that helps reason through complex, overlapping comorbidities. |
| | The system needs to generate a ranked differential diagnosis tailored to the patient's age, sex, comorbidities, and current medications. |
| | The system must respect the clinician's own clinical judgement — surfacing diagnoses they have already named and never overriding them silently. |
| | Clinicians need full override control, with the care plan re-synthesised instantly when they change a diagnosis. |
| | The system must reduce cognitive load with a transparent, step-by-step trace the clinician can follow and trust, not an opaque single answer. |
| **3. Medication Safety in Pharmacist-Vacant Clinics** | In clinics without an on-site pharmacist, the system must independently audit prescriptions for drug–drug interactions, allergy cross-reactivity, and organ-impairment dosing. |
| | The system must catch structural drug–condition contraindications even when no single guideline paragraph explicitly states them. |
| | The system must block sign-off when a critical or major safety concern is detected, rather than letting an unsafe plan pass silently. |
| | Safety review must remain reliable even when supporting infrastructure is flaky — concerns must never be hidden by a technical failure. |
| **Cross-cutting: Continuity & Workflow Fit** | The system must produce a structured, executable care plan that a clinician can act on directly within the visit. |
| | The system should preserve continuity across visits — carrying forward what changed, what to watch, and what to verify — for patients seen by rotating staff. |
| | The system must keep the clinician in the loop: it advises and documents, but the clinician retains final sign-off and accountability. |

These needs map directly onto the three bottlenecks the final ClearPath system was built to resolve — **guideline access friction** (deterministic scoped routing and evidence-graded retrieval), **diagnostic isolation** (contextual differential re-ranking with clinician override), and **medication safety** (the hybrid adversarial safety critic) — with continuity and human-in-the-loop sign-off carried across all three. This categorisation forms the foundation for the prioritised needs statements (Section 2.2) and the target specifications (Section 2.3) that follow.

---

## 2.2 Needs Statements

In discussions with the collaborator company, MHNexus, it was highlighted that optimizing the post-diagnostic clinical workflow is a critical priority. Once a diagnosis is established, clinicians must formulate care plans that strictly adhere to the latest Malaysian Clinical Practice Guidelines (CPGs) while simultaneously managing extensive documentation duties. This dual burden creates a significant bottleneck, potentially degrading consultation quality and increasing cognitive load as clinicians struggle to recall dynamic guideline updates. Furthermore, in rural districts (e.g. Belaga), medical officers frequently encounter unfamiliar cases without an on-site specialist or pharmacist to consult, raising the risk of diagnostic error and unsafe prescribing. Based on this input, the focus was placed on the evidence-based clinical practice guideline system, customer needs were identified from the information collected, and Table 2.3 was generated which serves as a foundation for assessing the alignment of the guidance system design with user needs and for systematically addressing the most significant requirements.

The raw customer statements gathered in Section 2.1 were consolidated to remove overlapping requirements — several statements expressed the same underlying need (for example, "aligned with the latest guidelines" and "grounded in the latest CPGs" are facets of a single grounding requirement). The result is a concise set of nine distinct, prioritized needs, each phrased in solution-neutral language and rated on a 1–5 priority scale, where **5 = Critical** (the product fails without it), **4 = High**, and **3 = Moderate**.

*Table 2.3: Customer needs*

| No | Need | Priority |
|---|---|---|
| 1 | The system provides real-time diagnostic suggestions based on patient data. | 5 |
| 2 | The system generates a complete, actionable care plan after diagnosis covering treatment, monitoring, follow-up, and referrals. | 5 |
| 3 | The system independently audits each plan for medication safety — drug interactions, allergy cross-reactivity, organ-impairment dosing, and structural drug–condition contraindications that no single guideline paragraph states explicitly — and blocks sign-off on critical concerns. | 5 |
| 4 | The system's recommendations are grounded in and aligned with the latest Malaysian MOH CPGs, with traceable citations. | 4 |
| 5 | When a presentation falls outside the available validated guidelines, the system recognises this and withholds a recommendation rather than producing a confident answer from loosely-related material. | 4 |
| 6 | The clinician can inspect the reasoning behind each output — the diagnoses considered and ranked, how the guideline was scoped, and the source of every safety flag — to verify it and remain accountable. | 4 |
| 7 | The system carries forward the patient's prior-visit history to maintain continuity when patients are seen by rotating or visiting clinicians. | 3 |
| 8 | The system's recommendations are clinically accurate and validated by clinical experts. | 5 |
| 9 | The system keeps the clinician in final control, allowing override of diagnoses and requiring clinician sign-off. | 4 |

The prioritisation reflects the hierarchy our stakeholders refused to compromise on. **Real-time diagnostic support** (Need 1) is Critical because a second opinion that arrives after the consultation has ended provides no value; **complete care-plan generation** (Need 2), **medication safety** (Need 3), and **clinical accuracy** (Need 8) are the non-negotiable clinical-quality requirements. The remaining needs encode the properties that make those outputs *trustworthy* in an isolated clinic: **scope-refusal** (Need 5) — declining when no guideline applies, because silence is safer than a confident wrong answer — **auditable reasoning** (Need 6), and **clinician control** (Need 9), each rated High as a precondition for adoption; a junior officer in an isolated clinic will only rely on a second opinion they can inspect, verify, and overrule. CPG grounding (Need 4) is a High-priority enabler, while continuity across visits (Need 7) is a Moderate-priority enhancement that directly serves the rural reality of rotating and visiting clinicians. This prioritisation directly shapes the target specifications in Section 2.3, where each need is converted into one or more measurable engineering metrics.

---

## 2.3 Target Specifications

After identifying the project need statements, a Needs-Metrics Matrix was established, as shown in Table 2.4. The matrix maps each prioritized customer need to one or more measurable engineering metrics, ensuring that every need can be objectively verified rather than assessed subjectively. Each need is served by at least one metric, and a single metric may satisfy more than one need — for example, the end-to-end *System response time* serves both real-time diagnosis (Need 1) and care-plan generation (Need 2), since it measures the full pipeline from patient input to a signed-off plan.

*Table 2.4: Needs-Metrics Matrix*

| No | Need | System response time | Diagnosis relevance | Care plan completeness | Care plan appropriateness | Clinical accuracy | Safety issue detection rate | Unsafe plan block rate | Citation coverage | Patient history carry-over | Usability satisfaction | Out-of-scope detection rate | Reasoning-trace transparency | Appropriate referral/deferral |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | The system provides real-time diagnostic suggestions based on patient data. | ■ | ■ | | | | | | | | | | | |
| 2 | The system generates a complete, actionable care plan after diagnosis covering treatment, monitoring, follow-up, and referrals. | ■ | | ■ | ■ | | | | | | ■ | | | ■ |
| 3 | The system independently audits each plan for medication safety and blocks sign-off on critical concerns. | | | | | | ■ | ■ | | | | | | |
| 4 | The system's recommendations are grounded in and aligned with the latest Malaysian MOH CPGs, with traceable citations. | | | | | | | | ■ | | | | | |
| 5 | When a presentation falls outside the available validated guidelines, the system recognises this and withholds a recommendation. | | | | | | | | | | | ■ | | |
| 6 | The clinician can inspect the reasoning behind each output to verify it and remain accountable. | | | | | | | | | | | | ■ | |
| 7 | The system carries forward the patient's prior-visit history to maintain continuity for rotating or visiting clinicians. | | | | | | | | | ■ | ■ | | | |
| 8 | The system's recommendations are clinically accurate and validated by clinical experts. | | ■ | | ■ | ■ | | | | | | | | |
| 9 | The system keeps the clinician in final control, allowing override of diagnoses and requiring clinician sign-off. | | | | | | | | | | ■ | | | |

The marginal and ideal values for each metric were then determined, as outlined in Table 2.5. The marginal value represents the minimum acceptable threshold for the system to be considered viable, while the ideal value represents the target the design aims to achieve.

*Table 2.5: Marginal Values and Ideal Values*

| No | Metric | Units | Marginal Value | Ideal Value |
|---|---|---|:--:|:--:|
| 1 | System response time | seconds | ≤ 180 | ≤ 60 |
| 2 | Diagnosis relevance | % | ≥ 85 | ≥ 95 |
| 3 | Care plan completeness | % | ≥ 85 | 100 |
| 4 | Care plan appropriateness | % | ≥ 85 | ≥ 95 |
| 5 | Clinical accuracy (faithfulness) | % | ≥ 85 | ≥ 95 |
| 6 | Safety issue detection rate | % | ≥ 90 | ≥ 99 |
| 7 | Unsafe plan block rate | % | 100 | 100 |
| 8 | Citation coverage | % | ≥ 85 | ≥ 95 |
| 9 | Patient history carry-over | % | ≥ 90 | 100 |
| 10 | Usability satisfaction score | /5 | ≥ 3.8 | ≥ 4.5 |
| 11 | Out-of-scope detection rate | % | ≥ 90 | 100 |
| 12 | Reasoning-trace transparency | % | ≥ 90 | 100 |
| 13 | Appropriate referral/deferral | % | ≥ 85 | ≥ 95 |

Three of these metrics double as scoring dimensions in the Chapter 4 comparative evaluation, so the targets here map directly onto how the system is later graded: *Reasoning-trace transparency* (Metric 12) operationalises the clinician-rubric dimensions of Explanation Clarity and Chain-of-Thought Depth, *Usability satisfaction* (Metric 10) subsumes Clinician Confidence and Explanation Clarity, and *Appropriate referral/deferral* (Metric 13) corresponds to the rubric's referral-correctness dimension. Explicit uncertainty quantification (a numeric confidence percentage) is deferred to future work — confidence is currently surfaced qualitatively through differential-diagnosis similarity scores and safety-severity tiers rather than a single exposed number.

Table 2.6 presents a comparative analysis of the three tools a clinician could realistically reach for today — a general-purpose LLM (ChatGPT/GPT-4), the document-summarisation assistant NotebookLM, and the CPG-native clinical tool Qmed AskCPG — evaluated against the needs metrics established in the Needs-Metrics Matrix (Table 2.4).

*Table 2.6: Benchmark of Customer Needs*

| No | Metric | Priority | Unit | ChatGPT (GPT-4) | NotebookLM | Qmed AskCPG |
|---|---|:--:|---|:--:|:--:|:--:|
| 1 | System response time | 5 | seconds | 15 | 30 | 18 |
| 2 | Diagnosis relevance | 5 | % | 78 | 58 | 83 |
| 3 | Care plan completeness | 5 | % | 55 | 15 | 65 |
| 4 | Care plan appropriateness | 5 | % | 55 | 20 | 80 |
| 5 | Clinical accuracy (faithfulness) | 5 | % | 50 | 58 | 85 |
| 6 | Safety issue detection rate | 5 | % | 25 | 0 | 50 |
| 7 | Unsafe plan block rate | 5 | % | 0 | 0 | 0 |
| 8 | Citation coverage | 4 | % | 15 | 94 | 88 |
| 9 | Patient history carry-over | 3 | % | 0 | 0 | 0 |
| 10 | Usability satisfaction | 4 | /5 | 3.2 | 1.8 | 3.9 |
| 11 | Out-of-scope detection rate | 4 | % | 0 | 0 | 0 |
| 12 | Reasoning-trace transparency | 4 | % | 15 | 20 | 25 |
| 13 | Appropriate referral/deferral | 4 | % | 45 | 10 | 60 |

The comparative analysis highlights specific gaps in existing tools. The general-purpose LLM is the fastest and most accessible option, yet it is the least safe — it blocks no unsafe plan (0%), grounds almost nothing in traceable citations (15%), and cannot recognise when a case falls outside its competence. NotebookLM and Qmed AskCPG respond quickly and cite sources, but neither provides a medication-safety guardrail (0% unsafe-plan block rate) nor continuity across visits (0% patient-history carry-over) — the two capabilities most critical in pharmacist-vacant, rotating-staff rural clinics. Two further axes separate ClearPath structurally: none of the three can decline an out-of-scope case (all score 0% on out-of-scope detection, always answering from whatever they retrieved), and none exposes an auditable per-stage reasoning trace — they surface a final answer, not the diagnoses considered, the guideline-scoping decisions, or the source of each safety flag. NotebookLM, designed for document summarisation, scores low on diagnosis relevance (58%) and cannot generate an actionable care plan, while Qmed AskCPG, though strong on guideline-aligned accuracy (83%), surfaces recommendations as prose without enforcing a safety sign-off. These gaps establish the design targets in Table 2.5: a real-time end-to-end response, a structured and clinically-appropriate care plan, traceable CPG citations, and — distinctively — an independent safety guardrail, a scope-refusal gate, an auditable reasoning trace, and a prior-visit continuity layer.

---

## 2.4 Proposed Solutions

### 2.4.1 Concept Generation

For each design parameter, four credible options were considered, each carrying its own advantages and trade-offs. The options are deliberately drawn at comparable levels of maturity rather than as an escalating ladder — for several parameters more than one option is defensible, and the "best" choice depends on how the parameter interacts with the project's specific constraints (real-time response, auditability, guideline currency, and medication safety). The full design space is presented in Table 2.7; the rationale for selecting a coherent combination is given in Section 2.4.2.

*Table 2.7: Concept Generation*

| Parameter | Option 1 | Option 2 | Option 3 | Option 4 |
|---|---|---|---|---|
| **Document Pre-Processing** | Docling layout-aware parsing | LlamaParse | Azure Document Intelligence (OCR + layout) | Raw text extraction (PyPDF / pdfplumber) |
| **Retrieval Strategy** | Dense vector search (pgvector + HNSW index) | Lexical BM25 + query expansion | Hybrid RRF (vector + BM25) | Vector + Knowledge-Graph fusion |
| **Reasoning Model(s)** | Single general-purpose LLM | Single reasoning LLM | Fine-tuned (LoRA) domain model | Stage-split: fast model + reasoning model |
| **Safety / Verification** | LLM self-critique | Deterministic rule engine | External DDI lookup API | Independent LLM critic + KG verifier |
| **Data Stores** | Single Postgres (JSONB + full-text index) | Postgres + pgvector | Dedicated vector DB (Pinecone / Weaviate) + metadata store | Postgres + pgvector + Neo4j |
| **Interface / Delivery** | Native mobile app | Embedded clinic terminal | Web dashboard (request-response) | Web dashboard (live SSE streaming) |

For **Document Pre-Processing**, Option 1 (Docling) uses a geometric layout model to detect headings, tables, and columns before extracting text, preserving the structure of native PDFs at the cost of higher computational overhead. Option 2 (LlamaParse) employs an LLM to interpret document layout, offering flexibility for complex or irregular formats but introducing per-page API costs and an external service dependency. Option 3 (Azure Document Intelligence) applies OCR and layout analysis at the image level, making it suitable for scanned or non-native PDFs, though it is slower and introduces character recognition errors on digital-native documents. Option 4 (Raw text extraction via PyPDF or pdfplumber) reads the PDF text stream directly, the fastest and most lightweight approach, but it loses all table structure and column ordering, which is critical for dosing tables in clinical guidelines.

For **Retrieval Strategy**, the four options are not a single accuracy ladder but distinct retrieval philosophies, each winning on a different dimension. Option 1 (Dense vector search via pgvector with an HNSW index) is the fastest and simplest to operate — a single index, no fusion step — and retrieves by semantic similarity, capturing meaning even when exact terms differ; it leads on latency and operational simplicity but can miss keyword-precise matches such as exact drug names and dosages. Option 2 (Lexical BM25 with query expansion) is the cheapest and most interpretable — no embedding model, fully transparent term matching — and is in fact the strongest option for exact clinical identifiers, drug names, and dose strings, though it fails on paraphrase and semantic equivalence. Option 3 (Hybrid RRF) is the strongest general-purpose retriever and the production default for clinical RAG: by fusing vector and BM25 rankings it captures both semantic and keyword matches, beating Option 4 on simplicity because it requires no graph to be constructed or maintained, and for the majority of single-passage lookups it is fully sufficient. Option 4 (Vector plus Knowledge-Graph fusion) wins on one dimension the others structurally cannot reach — multi-hop relationship reasoning — separating passage retrieval from structural reasoning so the graph resolves drug-condition and drug-drug relationships that no single CPG paragraph states explicitly; it is justified here, and only here, because medication-safety checking depends on exactly those cross-document relationships, and it carries a real cost the others avoid: the graph must be built, curated, and kept in sync with each guideline edition.

For **Reasoning Model(s)**, each option represents a different bet on how model capability should be allocated across the pipeline. Option 1 (Single general-purpose LLM) bets on operational simplicity: one general model serves every stage, minimising deployment and orchestration complexity, but accepting a reasoning ceiling that leaves it under-resourced for the deep clinical reasoning required by differential diagnosis and care-plan synthesis. Option 2 (Single reasoning LLM) bets on uniform output quality: a single high-capability reasoning model is applied to every stage so quality never varies, but this spends reasoning-grade latency and cost even on lightweight extraction tasks that do not require it. Option 3 (Fine-tuned LoRA model) bets on domain specialisation and on-device latency: a base LLM is adapted to clinical language for fast, locally-hostable inference, but this freezes knowledge at training time — because CPG editions update periodically, a fine-tuned model cannot incorporate new guidelines without retraining, nor does it produce a citation trail. Option 4 (Stage-split: fast model plus reasoning model) bets on task-matched allocation: model capability is assigned to task demand, routing lightweight structured extraction to a fast model while differential re-ranking and care-plan synthesis use a reasoning model, holding clinical output quality within the real-time response budget rather than optimising for any single stage in isolation.

For **Safety / Verification**, Option 1 (LLM self-critique) uses the same model that generated the care plan to review it, which risks the model's blind spots being shared between generation and review. Option 2 (Deterministic rule engine) applies hand-coded logic to flag known unsafe combinations, offering full auditability but unable to reason over novel drug-condition combinations that are not explicitly encoded. Option 3 (External DDI lookup API) queries a third-party drug-interaction database for structured checks, providing authoritative interaction data but introducing a network dependency that can fail in low-connectivity rural settings. Option 4 (Independent LLM critic plus KG verifier) runs a separate critic LLM and a Neo4j graph verifier in parallel, giving two failure-independent checks with no shared failure mode: the critic catches semantic safety concerns while the graph traverses structural contraindications.

For **Data Stores**, the options trade along an operational-philosophy axis — how much storage complexity to take on, and where — rather than simply "more stores is better." Option 1 (Single Postgres with JSONB and a full-text index) wins decisively on operational simplicity and cost: one database to deploy, back up, and secure, with flexible document fields and built-in lexical search, which for a small rural-clinic deployment is a genuine advantage — at the price of no native vector indexing for semantic search. Option 2 (Postgres plus pgvector) is the pragmatic default that most RAG systems settle on: it adds semantic retrieval inside the same database instance, so there is still a single backend to operate, and for any system that needs vector search but not graph traversal it is the right answer. Option 3 (Dedicated vector DB such as Pinecone or Weaviate) wins on scaling and managed operations — it outperforms Option 4 when the priority is high-volume vector workloads with zero self-hosted index maintenance, offloading that burden to a managed service, though at the cost of an external dependency and no relational or graph query capability. Option 4 (Postgres plus pgvector plus Neo4j) is not preferred for having the most stores — its three backends are a real operational and deployment burden the other options avoid — but because the chosen safety architecture requires native graph traversal for contraindication checking, a capability none of the single- or dual-store options can provide; the extra store is accepted as the cost of that one structural requirement, not adopted for its own sake.

For **Interface / Delivery**, Option 1 (Native mobile app) supports mobility and offline caching, which is valuable in rural clinic settings, but requires platform-specific development and app-store distribution. Option 2 (Embedded clinic terminal) integrates directly into existing clinical workstation workflows but is constrained by fixed hardware, limited screen space, and a high deployment cost per site. Option 3 (Web dashboard with request-response) provides broad device compatibility with no installation, but the full pipeline response arrives only after the complete backend computation finishes, with no intermediate feedback to the user. Option 4 (Web dashboard with live SSE streaming) delivers the same browser-based compatibility while streaming partial results as each pipeline stage completes, reducing perceived wait time and allowing the clinician to begin reviewing early outputs before synthesis finishes.

---

### 2.4.2 Concept Combination

From the six design parameters and their respective options in Table 2.7, four distinct concept combinations were assembled. Each concept reflects a coherent architectural stance — a consistent set of trade-off choices that serve a particular priority. One of the four concepts represents the realised ClearPath system.

*Table 2.8: Concept Combination*

| Parameter | Concept A | Concept B | Concept C (ClearPath) | Concept D |
|---|---|---|---|---|
| **Pre-Processing** | Raw text extraction (PyPDF) | LlamaParse | Docling | Azure Document Intelligence (OCR) |
| **Retrieval** | Lexical BM25 + query expansion | Hybrid RRF (vector + BM25) | Vector + Knowledge-Graph fusion | Dense vector (pgvector + HNSW index) |
| **Reasoning Model(s)** | Single general-purpose LLM | Fine-tuned (LoRA) model | Stage-split: fast + reasoning model | Single reasoning LLM |
| **Safety / Verification** | LLM self-critique | Deterministic rule engine | Independent LLM critic + KG verifier | External DDI lookup API |
| **Data Stores** | Single Postgres (JSONB + full-text index) | Dedicated vector DB (Pinecone) + metadata store | Postgres + pgvector + Neo4j | Postgres + pgvector |
| **Interface / Delivery** | Native mobile app | Embedded clinic terminal | Web dashboard (live SSE streaming) | Web dashboard (request-response) |

**Concept A** prioritises speed and simplicity for the lightest possible deployment. It uses raw PyPDF text extraction for fast ingestion and Lexical BM25 for keyword-precise retrieval, driven by a single general-purpose LLM. Safety relies on the model critiquing its own output, and all data sits in a single Postgres database, delivered through a native mobile app. This is the most lightweight stack, but it loses table structure during ingestion, cannot retrieve semantically equivalent guidance, and offers no failure-independent safety check, making it ill-suited to medication-safety-critical care.

**Concept B** focuses on managed-service scale and standards compliance. It applies LlamaParse for LLM-based document parsing and Hybrid RRF retrieval, with a fine-tuned LoRA model supplying low-latency domain-specific output. A deterministic rule engine enforces safety, a dedicated vector database handles scale, and the system is delivered through an embedded clinic terminal. This concept achieves strong retrieval and fast inference, but the fine-tuned model freezes guideline knowledge at training time with no citation trail, and the rule engine cannot reason over novel drug-condition combinations.

**Concept C (ClearPath)** is the realised system, balancing clinical quality, auditability, and medication safety. It uses Docling layout-aware parsing to preserve guideline tables and section structure, and combines dense vector retrieval with a knowledge graph so that semantic evidence recall and structural relationship reasoning are handled by purpose-fit mechanisms. A stage-split model architecture routes lightweight extraction to a fast model while differential re-ranking and care-plan synthesis use a reasoning model, holding output quality within the real-time response budget. Medication safety is enforced by an independent LLM critic running in parallel with a Neo4j graph verifier, giving two failure-independent checks. Data is stored across Postgres, pgvector, and Neo4j, each optimised for its role, and the system is delivered through a web dashboard with live SSE streaming so the clinician sees each pipeline stage complete in real time. This combination directly satisfies the critical needs of grounded accuracy, traceable citations, an independent safety guardrail, and continuity across visits.

**Concept D** emphasises broad compatibility and accessible deployment. It uses Azure Document Intelligence OCR to digitise both scanned and native records and a single reasoning LLM applied across all stages for consistently high-quality output. Dense vector search via pgvector handles retrieval, safety is delegated to an external DDI lookup API, and data is stored in Postgres plus pgvector, accessed through a standard request-response web dashboard. This concept is the most portable and infrastructure-flexible, but applying a heavy reasoning model to every stage inflates latency and cost, and the external safety API introduces a network dependency that fails in low-connectivity rural clinics.

**Conclusion.** Four distinct design concepts were assembled from Table 2.8, each combining a coherent set of architectural choices to serve a different priority: speed and simplicity (Concept A), managed scale with standards compliance (Concept B), clinical quality with auditable safety (Concept C), and broad compatibility and accessible deployment (Concept D). Concept C was carried forward as the realised ClearPath system, as justified by the selection process in Section 2.4.3.

---

### 2.4.3 Concept Selection

The selection of one concept among the four design concepts is based on the following selection criteria, evaluated first through a concept screening (Table 2.9) and then a weighted concept scoring (Table 2.10).

*Table 2.9: Concept Screening*

| Selection Criteria | A | B | C | D |
|---|:--:|:--:|:--:|:--:|
| Guideline Structure Completeness | + | + | 0 | 0 |
| Retrieval Accuracy | + | - | + | + |
| Clinical Reasoning Capability | - | 0 | + | + |
| Medication Safety Enforcement | - | 0 | + | 0 |
| Data Architecture Suitability | - | + | + | 0 |
| Deployment Feasibility | + | - | 0 | + |
| **Sum +'s** | **3** | **2** | **4** | **3** |
| **Sum 0's** | **0** | **1** | **2** | **3** |
| **Sum -'s** | **3** | **2** | **0** | **0** |
| **Net Score** | **0** | **+1** | **+4** | **+3** |
| **Rank** | **4** | **3** | **1** | **2** |
| **Continue?** | **No** | **No** | **Yes** | **Yes** |

Concept A is eliminated by its three minuses — raw text extraction loses table structure, BM25 cannot retrieve semantically equivalent guidance, and LLM self-critique shares the generator's blind spots. Concept B is eliminated primarily because the LoRA fine-tuned model freezes clinical knowledge at training time and cannot incorporate CPG edition updates without retraining, which is a fundamental incompatibility with a guideline-grounded system. Concepts C and D both advance: C leads on clinical reasoning, medication safety, and data architecture, while D scores neutrally on three criteria and outperforms C on deployment feasibility owing to its simpler two-service stack.

In the final stage of concept selection, shown in Table 2.10, each criterion is assigned a weight reflecting its importance to the project's binding constraints. Concepts C and D are rated on a scale of 1 to 5, the weighted score is calculated by multiplying the rating by its weight, and the concept with the highest total score is selected for development.

*Table 2.10: Concept Scoring*

| Selection Criteria | Weight | C Rating (/5) | C Weighted Score | D Rating (/5) | D Weighted Score |
|---|---|:--:|:--:|:--:|:--:|
| Guideline Structure Completeness | 15% | 4 | 0.60 | 4 | 0.60 |
| Retrieval Accuracy | 20% | 4 | 0.80 | 4 | 0.80 |
| Clinical Reasoning Capability | 25% | 5 | 1.25 | 4 | 1.00 |
| Medication Safety Enforcement | 20% | 4 | 0.80 | 3 | 0.60 |
| Data Architecture Suitability | 10% | 4 | 0.40 | 3 | 0.30 |
| Deployment Feasibility | 10% | 3 | 0.30 | 4 | 0.40 |
| **Total Score** | **100%** | | **4.15** | | **3.70** |
| **Rank** | | | **1** | | **2** |
| **Continue?** | | | **Develop** | | **No** |

Concept C and Concept D score closely across most criteria — both rate equally on guideline parsing quality and retrieval accuracy, and Concept D edges ahead on deployment feasibility due to its simpler two-service stack. The decisive separation comes from the two highest-weighted criteria: Clinical Reasoning Capability (25%) and Medication Safety Enforcement (20%). On clinical reasoning, the stage-split architecture in Concept C assigns a reasoning model only where it is needed — differential re-ranking and care-plan synthesis — whereas Concept D applies a single reasoning model uniformly across all stages, inflating latency and cost on lightweight extraction tasks without improving output quality. On medication safety, Concept C's independent LLM critic running in parallel with a Neo4j graph verifier provides two failure-independent checks, while Concept D's external DDI lookup API introduces a network dependency that is unreliable in low-connectivity rural settings and cannot traverse structural contraindications. These two gaps directly undermine the non-negotiable requirements identified in Section 2.2 (Needs 3 and 8), and neither can be resolved without replacing Concept D's core architectural choices. Concept C is therefore selected for development.

---

### 2.4.4 Concept Testing

With Concept C selected on paper, it was tested against stakeholder judgement before development began. The combination was presented to **Dr Teh** (Medical Officer, MHNexus) and **Mr Zikrie** (AI Lead Developer), whose feedback is summarised in Table 2.11. The objective was to confirm that the selected architecture matched real clinical-workflow expectations and to surface any refinement needed before build.

*Table 2.11: Concept Testing & Validation*

| Reviewer | Feedback | Resulting design refinement |
|---|---|---|
| **Mr Zikrie** (AI Lead) | Docling's automated layout parsing must be complemented by manual quality control to guarantee a standardised data structure and protect retrieval accuracy. | A human-in-the-loop **validation layer** was integrated into the CPG ingestion pipeline (verify-then-write), rather than trusting automated parsing alone. |
| **Dr Teh** (Medical Officer) | Clinical output must stay concise yet always contain the essential elements a clinician acts on. | The care plan was constrained to a fixed **executable schema** (medication, monitoring, referrals, lifestyle, follow-up, safety-netting), keeping output structured and scannable within the consultation window. |
| Both | Standards choices (FHIR-aligned data exchange, SQL-backed storage) were endorsed as industry best practice. | Retained as originally planned. |

The validation confirmed the core of Concept C and tightened two points — a quality-controlled ingestion layer and a schema-constrained clinical output — without altering the selected architecture.

**Design-for-X (DfX) considerations.** Because ClearPath is a software-and-AI system rather than a physical product, the conventional design constraints were assessed in their software-deployment form:

1. **Economical** — The system runs on a clinic's existing tablets and desktops with zero marginal hardware cost, and is built on an open-source Python/PostgreSQL/Neo4j stack. Software scales at near-zero marginal cost across clinics, and by catching unsafe prescriptions early it averts costly preventable adverse-drug-event admissions.
2. **Environmental** — Care plans are delivered digitally (PDF), removing printed guideline binders and paper records. Reusing existing clinic hardware avoids any new device footprint and the associated e-waste, and a lightweight cloud deployment removes the need to ship and maintain physical equipment at remote sites.
3. **Sustainability** — The knowledge base is versioned against CPG editions so it can be updated as guidelines are revised; the retrieval-grounded design (deliberately chosen over a fine-tuned model that would freeze knowledge at training time) lets new or updated guidelines be ingested without retraining, keeping the system useful over time.
4. **Manufacturability (Deployability)** — One Server-Sent-Events contract drives both the web Doctor UI and a terminal CLI, so the same backend deploys identically across surfaces. Offline-resilience measures (rotating logs, failed-job replay, correlation IDs) keep it usable under the unstable connectivity of rural clinics, and a containerised deployment with clear documentation eases roll-out and maintenance.
5. **Ethical** — The clinician retains final sign-off and accountability; the system advises but never overrides silently. Every recommendation is grounded in and cited to a verified CPG to prevent hallucinated advice, the safety critic refuses to sign off on an unsafe plan, patient data is protected (session state resets between consultations; no cross-patient leakage), and the auditable per-stage reasoning trace supports medico-legal accountability.
