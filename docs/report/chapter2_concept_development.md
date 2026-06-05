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

The raw customer statements gathered in Section 2.1 were consolidated to remove overlapping requirements — several statements expressed the same underlying need (for example, "aligned with the latest guidelines" and "grounded in the latest CPGs" are facets of a single grounding requirement). The result is a concise set of seven distinct, prioritized needs, each phrased in solution-neutral language and rated on a 1–5 priority scale, where **5 = Critical** (the product fails without it), **4 = High**, and **3 = Moderate**.

*Table 2.3: Customer needs*

| No | Need | Priority |
|---|---|---|
| 1 | The system provides real-time diagnostic suggestions based on patient data. | 5 |
| 2 | The system generates a complete, actionable care plan after diagnosis covering treatment, monitoring, follow-up, and referrals. | 5 |
| 3 | The system independently audits each plan for medication safety (drug interactions, allergies, contraindications, dosing) and blocks sign-off on critical concerns. | 5 |
| 4 | The system's recommendations are grounded in and aligned with the latest Malaysian MOH CPGs, with traceable citations. | 4 |
| 5 | The system carries forward the patient's prior-visit history to maintain continuity when patients are seen by rotating or visiting clinicians. | 3 |
| 6 | The system's recommendations are clinically accurate and validated by clinical experts. | 5 |
| 7 | The system keeps the clinician in final control, allowing override of diagnoses and requiring clinician sign-off. | 4 |

The prioritisation reflects the hierarchy our stakeholders refused to compromise on. **Real-time diagnostic support** (Need 1) is Critical because a second opinion that arrives after the consultation has ended provides no value; **complete care-plan generation** (Need 2), **medication safety** (Need 3), and **clinical accuracy** (Need 6) are the non-negotiable clinical-quality requirements; and **clinician control** (Need 7) is the precondition for adoption — a junior officer in an isolated clinic will only rely on a second opinion they can both verify and overrule. CPG grounding (Need 4) is a High-priority enabler, while continuity across visits (Need 5) is a Moderate-priority enhancement that directly serves the rural reality of rotating and visiting clinicians. This prioritisation directly shapes the target specifications in Section 2.3, where each need is converted into one or more measurable engineering metrics.

---

## 2.3 Target Specifications

After identifying the project need statements, a Needs-Metrics Matrix was established, as shown in Table 2.4. The matrix maps each prioritized customer need to one or more measurable engineering metrics, ensuring that every need can be objectively verified rather than assessed subjectively. Each need is served by at least one metric, and a single metric may satisfy more than one need — for example, the end-to-end *System response time* serves both real-time diagnosis (Need 1) and care-plan generation (Need 2), since it measures the full pipeline from patient input to a signed-off plan.

*Table 2.4: Needs-Metrics Matrix*

| No | Need | System response time | Diagnosis relevance | Care plan completeness | Care plan appropriateness | Clinical accuracy | Safety issue detection rate | Unsafe plan block rate | Citation coverage | Patient history carry-over | Usability satisfaction |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | The system provides real-time diagnostic suggestions based on patient data. | ■ | ■ | | | | | | | | |
| 2 | The system generates a complete, actionable care plan after diagnosis covering treatment, monitoring, follow-up, and referrals. | ■ | | ■ | ■ | | | | | | ■ |
| 3 | The system independently audits each plan for medication safety and blocks sign-off on critical concerns. | | | | | | ■ | ■ | | | |
| 4 | The system's recommendations are grounded in and aligned with the latest Malaysian MOH CPGs, with traceable citations. | | | | | | | | ■ | | |
| 5 | The system carries forward the patient's prior-visit history to maintain continuity for rotating or visiting clinicians. | | | | | | | | | ■ | ■ |
| 6 | The system's recommendations are clinically accurate and validated by clinical experts. | | ■ | | ■ | ■ | | | | | |
| 7 | The system keeps the clinician in final control, allowing override of diagnoses and requiring clinician sign-off. | | | | | | | | | | ■ |

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

Table 2.6 presents a comparative analysis of current tools — the document-summarisation assistant NotebookLM and the CPG-native clinical tool Qmed AskCPG — evaluated against the needs metrics established in the Needs-Metrics Matrix (Table 2.4).

*Table 2.6: Benchmark of Customer Needs*

| No | Metric | Priority | Unit | NotebookLM | Qmed AskCPG |
|---|---|:--:|---|:--:|:--:|
| 1 | System response time | 5 | seconds | 30 | 18 |
| 2 | Diagnosis relevance | 5 | % | 58 | 83 |
| 3 | Care plan completeness | 5 | % | 15 | 65 |
| 4 | Care plan appropriateness | 5 | % | 20 | 80 |
| 5 | Clinical accuracy (faithfulness) | 5 | % | 58 | 85 |
| 6 | Safety issue detection rate | 5 | % | 0 | 50 |
| 7 | Unsafe plan block rate | 5 | % | 0 | 0 |
| 8 | Citation coverage | 4 | % | 94 | 88 |
| 9 | Patient history carry-over | 3 | % | 0 | 0 |
| 10 | Usability satisfaction | 4 | /5 | 1.8 | 3.9 |

The comparative analysis highlights specific gaps in existing tools. While both NotebookLM and Qmed AskCPG respond quickly and cite sources, neither provides a medication-safety guardrail (0% unsafe-plan block rate) or continuity across visits (0% patient-history carry-over) — the two capabilities most critical in pharmacist-vacant, rotating-staff rural clinics. NotebookLM, designed for document summarisation, scores low on diagnosis relevance (58%) and cannot generate an actionable care plan, while Qmed AskCPG, though strong on guideline-aligned accuracy (83%), surfaces recommendations as prose without enforcing a safety sign-off. These gaps establish the design targets in Table 2.5: a real-time end-to-end response, a structured and clinically-appropriate care plan, traceable CPG citations, and — distinctively — an independent safety guardrail and a prior-visit continuity layer.

---

## 2.4 Proposed Solutions

### 2.4.1 Concept Generation

For each design parameter, four credible options were considered, each carrying its own advantages and trade-offs. The options are deliberately drawn at comparable levels of maturity rather than as an escalating ladder — for several parameters more than one option is defensible, and the "best" choice depends on how the parameter interacts with the project's specific constraints (real-time response, auditability, guideline currency, and medication safety). The full design space is presented in Table 2.7; the rationale for selecting a coherent combination is given in Section 2.4.2.

*Table 2.7: Concept Generation*

| Parameter | Option 1 | Option 2 | Option 3 | Option 4 |
|---|---|---|---|---|
| **Document Pre-Processing** | Docling layout-aware parsing | LlamaParse | Azure Document Intelligence (OCR + layout) | Raw text extraction (PyPDF / pdfplumber) |
| **Retrieval Strategy** | Dense vector search (pgvector) | Lexical BM25 | Hybrid RRF (vector + BM25) | Vector + Knowledge-Graph fusion |
| **Reasoning Model(s)** | Single general-purpose LLM | Single reasoning LLM | Fine-tuned (LoRA) domain model | Stage-split: fast model + reasoning model |
| **Safety / Verification** | LLM self-critique | Deterministic rule engine | External DDI lookup API | Independent LLM critic + KG verifier |
| **Data Stores** | Single Postgres (JSONB) | Postgres + pgvector | Dedicated vector DB (Pinecone / Weaviate) | Postgres + pgvector + Neo4j |
| **Interface / Delivery** | Native mobile app | Embedded clinic terminal | Web dashboard (request-response) | Web dashboard (live SSE streaming) |

For **Document Pre-Processing**, Option 1 (Docling) uses a geometric layout model to detect headings, tables, and columns before extracting text, preserving the structure of native PDFs at the cost of higher computational overhead. Option 2 (LlamaParse) employs an LLM to interpret document layout, offering flexibility for complex or irregular formats but introducing per-page API costs and an external service dependency. Option 3 (Azure Document Intelligence) applies OCR and layout analysis at the image level, making it suitable for scanned or non-native PDFs, though it is slower and introduces character recognition errors on digital-native documents. Option 4 (Raw text extraction via PyPDF or pdfplumber) reads the PDF text stream directly, the fastest and most lightweight approach, but it loses all table structure and column ordering, which is critical for dosing tables in clinical guidelines.

For **Retrieval Strategy**, Option 1 (Dense vector search via pgvector) encodes passages as embeddings and retrieves by semantic similarity, capturing meaning even when exact terms differ, though it can miss keyword-precise matches. Option 2 (Lexical BM25) retrieves by exact term frequency and inverse document frequency, excelling at keyword precision but failing on paraphrased or semantically equivalent queries. Option 3 (Hybrid RRF) fuses vector and BM25 rankings via Reciprocal Rank Fusion, combining semantic and keyword strengths at the cost of added pipeline complexity. Option 4 (Vector plus Knowledge-Graph fusion) separates passage retrieval from structural relationship reasoning, using vector search for evidence recall while the graph resolves drug-condition and drug-drug relationships that no single CPG paragraph states explicitly.

For **Reasoning Model(s)**, Option 1 (Single general-purpose LLM) provides broad capability at low deployment complexity but is under-resourced for the deep clinical reasoning required by differential diagnosis and care-plan synthesis. Option 2 (Single reasoning LLM) applies a high-capability reasoning model across all pipeline stages, improving output quality but incurring high latency and cost on lightweight extraction tasks that do not require it. Option 3 (Fine-tuned LoRA model) adapts a base LLM to clinical domain language and achieves low inference latency, but freezes knowledge at training time; because CPG editions update periodically, a fine-tuned model cannot incorporate new guidelines without retraining, nor does it produce a citation trail. Option 4 (Stage-split: fast model plus reasoning model) assigns model capability to task demand, routing lightweight structured extraction to a fast model while differential re-ranking and care-plan synthesis use a reasoning model, balancing clinical output quality against the real-time response budget.

For **Safety / Verification**, Option 1 (LLM self-critique) uses the same model that generated the care plan to review it, which risks the model's blind spots being shared between generation and review. Option 2 (Deterministic rule engine) applies hand-coded logic to flag known unsafe combinations, offering full auditability but unable to reason over novel drug-condition combinations that are not explicitly encoded. Option 3 (External DDI lookup API) queries a third-party drug-interaction database for structured checks, providing authoritative interaction data but introducing a network dependency that can fail in low-connectivity rural settings. Option 4 (Independent LLM critic plus KG verifier) runs a separate critic LLM and a Neo4j graph verifier in parallel, giving two failure-independent checks with no shared failure mode: the critic catches semantic safety concerns while the graph traverses structural contraindications.

For **Data Stores**, Option 1 (Single Postgres with JSONB) stores all data in one relational database with flexible document fields, minimising operational complexity but lacking native vector indexing for semantic search. Option 2 (Postgres plus pgvector) extends relational storage with a vector index in the same database instance, enabling semantic retrieval without an additional service, though it is limited to flat similarity search with no graph traversal. Option 3 (Dedicated vector DB such as Pinecone or Weaviate) offers high-performance vector indexing and managed scaling, but introduces an external managed-service dependency and provides no relational or graph query capability. Option 4 (Postgres plus pgvector plus Neo4j) combines relational storage, vector retrieval, and graph-based structural reasoning across three purpose-fit stores, each optimised for its role, at the cost of higher operational and deployment complexity.

For **Interface / Delivery**, Option 1 (Native mobile app) supports mobility and offline caching, which is valuable in rural clinic settings, but requires platform-specific development and app-store distribution. Option 2 (Embedded clinic terminal) integrates directly into existing clinical workstation workflows but is constrained by fixed hardware, limited screen space, and a high deployment cost per site. Option 3 (Web dashboard with request-response) provides broad device compatibility with no installation, but the full pipeline response arrives only after the complete backend computation finishes, with no intermediate feedback to the user. Option 4 (Web dashboard with live SSE streaming) delivers the same browser-based compatibility while streaming partial results as each pipeline stage completes, reducing perceived wait time and allowing the clinician to begin reviewing early outputs before synthesis finishes.

---

### 2.4.2 Concept Combination

From the six design parameters and their respective options in Table 2.7, four distinct concept combinations were assembled. Each concept reflects a coherent architectural stance — a consistent set of trade-off choices that serve a particular priority. One of the four concepts represents the realised ClearPath system.

*Table 2.8: Concept Combination*

| Parameter | Concept A | Concept B | Concept C (ClearPath) | Concept D |
|---|---|---|---|---|
| **Pre-Processing** | Raw text extraction (PyPDF) | LlamaParse | Docling | Azure Document Intelligence (OCR) |
| **Retrieval** | Lexical BM25 | Hybrid RRF (vector + BM25) | Vector + Knowledge-Graph fusion | Dense vector (pgvector) |
| **Reasoning Model(s)** | Single general-purpose LLM | Fine-tuned (LoRA) model | Stage-split: fast + reasoning model | Single reasoning LLM |
| **Safety / Verification** | LLM self-critique | Deterministic rule engine | Independent LLM critic + KG verifier | External DDI lookup API |
| **Data Stores** | Single Postgres (JSONB) | Dedicated vector DB (Pinecone) | Postgres + pgvector + Neo4j | Postgres + pgvector |
| **Interface / Delivery** | Native mobile app | Embedded clinic terminal | Web dashboard (live SSE streaming) | Web dashboard (request-response) |

**Concept A** prioritises speed and simplicity for the lightest possible deployment. It uses raw PyPDF text extraction for fast ingestion and Lexical BM25 for keyword-precise retrieval, driven by a single general-purpose LLM. Safety relies on the model critiquing its own output, and all data sits in a single Postgres database, delivered through a native mobile app. This is the most lightweight stack, but it loses table structure during ingestion, cannot retrieve semantically equivalent guidance, and offers no failure-independent safety check, making it ill-suited to medication-safety-critical care.

**Concept B** focuses on managed-service scale and standards compliance. It applies LlamaParse for LLM-based document parsing and Hybrid RRF retrieval, with a fine-tuned LoRA model supplying low-latency domain-specific output. A deterministic rule engine enforces safety, a dedicated vector database handles scale, and the system is delivered through an embedded clinic terminal. This concept achieves strong retrieval and fast inference, but the fine-tuned model freezes guideline knowledge at training time with no citation trail, and the rule engine cannot reason over novel drug-condition combinations.

**Concept C (ClearPath)** is the realised system, balancing clinical quality, auditability, and medication safety. It uses Docling layout-aware parsing to preserve guideline tables and section structure, and combines dense vector retrieval with a knowledge graph so that semantic evidence recall and structural relationship reasoning are handled by purpose-fit mechanisms. A stage-split model architecture routes lightweight extraction to a fast model while differential re-ranking and care-plan synthesis use a reasoning model, holding output quality within the real-time response budget. Medication safety is enforced by an independent LLM critic running in parallel with a Neo4j graph verifier, giving two failure-independent checks. Data is stored across Postgres, pgvector, and Neo4j, each optimised for its role, and the system is delivered through a web dashboard with live SSE streaming so the clinician sees each pipeline stage complete in real time. This combination directly satisfies the critical needs of grounded accuracy, traceable citations, an independent safety guardrail, and continuity across visits.

**Concept D** emphasises broad compatibility and accessible deployment. It uses Azure Document Intelligence OCR to digitise both scanned and native records and a single reasoning LLM applied across all stages for consistently high-quality output. Dense vector search via pgvector handles retrieval, safety is delegated to an external DDI lookup API, and data is stored in Postgres plus pgvector, accessed through a standard request-response web dashboard. This concept is the most portable and infrastructure-flexible, but applying a heavy reasoning model to every stage inflates latency and cost, and the external safety API introduces a network dependency that fails in low-connectivity rural clinics.

**Conclusion.** Four distinct design concepts were assembled from Table 2.8, each combining a coherent set of architectural choices to serve a different priority: speed and simplicity (Concept A), managed scale with standards compliance (Concept B), clinical quality with auditable safety (Concept C), and broad compatibility and accessible deployment (Concept D). Concept C was carried forward as the realised ClearPath system, as justified by the selection process in Section 2.4.3.
