# CHAPTER 6: PROJECT SELF-EVALUATION

## 6.1 Reflection

The core design principle — deterministic wherever possible, generative only where genuine clinical reasoning is required — proved highly successful, though its engineering overhead was originally underestimated.

### 6.1.1 Reflection on Design

#### 6.1.1.1 Deterministic Scope Table

Routing was built as an explicit ICD-11 scope table rather than vector similarity, enabling first-class `out_of_scope` refusals. This absolute safety guardrail requires an upfront architectural mandate and cannot be retrofitted via prompt tuning.

#### 6.1.1.2 Dual-Grounding Architecture

Separating CPG text chunks (pgvector) from typed drug-interaction edges (Neo4j) ensures true dual-source safety. The knowledge graph flags contraindications deterministically, independent of whether the retrieved text mentions those specific drug risks.

#### 6.1.1.3 Pydantic Schema Validation

Enforcing strongly typed data contracts for all care-plan generation eliminated the structural brittleness inherent to free-form text outputs. This explicit standardization proved critical for enabling automated downstream validation, predictable interface rendering, and granular evaluation of factual faithfulness.

#### 6.1.1.4 Architectural Debt

The sequential seven-stage pipeline favours clinical correctness over speed. The resulting ~2.5-minute latency leaves a narrow margin in fast-paced consultations — an architectural debt requiring a structural engineering remedy, not a prompt adjustment (§5.3.1).

#### 6.1.1.5 Knowledge Graph Auditing

Omitting a baseline coverage metric for the knowledge graph at inception left its recall against a gold interaction set unquantified. Incorporating an independent coverage audit from the outset would have defined this boundary before evaluation, not after.

---

### 6.1.2 Reflections on Implementation

#### 6.1.2.1 Proactive Safety Probing

Robustness testing must be a first-class development milestone, not a late addition. Introducing silent-degradation probes late in the cycle exposed four critical fail-silent bugs — including zero-chunk retrievals generating confident care plans — that standard happy-path unit tests never would have caught.

#### 6.1.2.2 Gold-Set Integrity

Evaluation metrics are only as reliable as the validation dataset behind them. Early anomalies (e.g., routing accuracy of 18.2%) were traced directly to gold-set defects — incorrect ICD codes, non-existent sub-codes. Prioritising gold-set correctness before running metrics avoids expensive false-diagnosis cycles.

#### 6.1.2.3 Stratified Determinism

Determinism in clinical AI is a layered property. Mapping the pipeline's deterministic surface (byte-identical candidate queries) against its stochastic nodes (seedless re-ranker, synthesis model) provided the exact diagnostic foundation needed to isolate and close runtime variance.

---

## 6.2 Project Schedule and Work Plan

The project ran from August 2025 to June 2026 across four phases. The Gantt chart below records the planned versus actual timeline; the phase summary that follows it states the principal deliverable of each phase.

> **Figure 6.1 — Project Gantt Chart.** *(insert Gantt chart here)*

| Phase | Period | Principal work |
|---|---|---|
| 1 — Requirements & corpus | Aug–Oct 2025 | Stakeholder interviews, 30-CPG ingestion, ICD-11 scope table, knowledge-graph construction |
| 2 — Pipeline & UI | Oct 2025–Jan 2026 | Seven-stage backend, Doctor UI, Supabase data layer, rPPG integration |
| 3 — Evaluation | Jan–May 2026 | Eval harness, validation runs (A1/A2/B/C/D), expert clinician review |
| 4 — Report & deployment prep | May–Jun 2026 | Chapter write-up, robustness probes, determinism runs, final fixes |

The single largest schedule lesson — recorded in §6.1.2 — is that the evaluation phase (Phase 3) carried more diagnostic cost than planned because gold-set correction and the full faithfulness run landed late; an earlier evaluation start would have shortened the critical path.

### 6.2.1 Phase 1 & 2 — System Design and Build (August 2025 – January 2026)

During the first half of the project, all team members participated in stakeholder discovery — conducting interviews with rural clinicians, Ministry of Health doctors, and health-technology partners (Table 2.1) to anchor the system's requirements in real clinical need. Following the requirements phase, the team split across the core workstreams required to build the seven-stage pipeline and its surrounding infrastructure.

**Chua Zhu Heng (Leader)** drove the overall system architecture and held the primary technical integration role. He designed the LLM orchestration layer, integrated the Gemini 2.5 Flash API across the extraction, re-ranking, and query-generation stages, and established the Stage 6 hybrid safety-critic design — combining LLM pharmacological reasoning with the typed Neo4j drug knowledge graph. He also structured the evaluation framework, defining the multi-layer validation strategy (Layers A–D) that would govern Phase 3.

**Lim Zhi Pin** was responsible for the backend cloud infrastructure. He provisioned and configured the AWS deployment environment, set up the PostgreSQL/pgvector instance for the 30-CPG corpus, and integrated the Cohere Rerank v3.5 retrieval pipeline. He also led the testing strategy, designing the adversarial and safety stress-test cases that formed the backbone of the Layer C/D evaluation suite.

**Satish Rao** led the rPPG (remote photoplethysmography) integration workstream, building the contactless vitals-capture pipeline that feeds heart rate into the patient case input. He also took primary ownership of CPG corpus preprocessing, writing the ingestion scripts that chunked, tagged, and embedded all 30 Malaysian MOH guidelines into the vector database.

**Chin Pei Kang** developed the Doctor UI frontend (React), implementing the case-input forms, DDx selection interface, care-plan display, and the safety-flag acknowledgement workflow. He also hardened the DDx selection pipeline on the backend — implementing the ICD-11 CC-Boost resolver and the multi-granularity scoring logic to prevent empty or misrouted care plan generation.

**Low Jia Qi** built the care-plan delivery and notification features, including the email care-plan PDF workflow and the DDx UI components. She also developed the SULAM interactive prototype and contributed to early frontend architecture decisions.

### 6.2.2 Phase 3 & 4 — Evaluation and Reporting (January 2026 – June 2026)

In the second half of the project, the team shifted focus to system validation, expert review, and final documentation.

**Chua Zhu Heng** owned Evaluation Layers B, C, and D — running clinical QA retrieval benchmarks, correcting the gold sets when ICD-code defects were discovered, and executing the full Stage 4 and Stage 5 faithfulness evaluation runs. He resolved the most significant evaluation bugs (mismatched UUIDs, Layer B/C framework failures) and produced the consolidated validation results that underpin Chapter 4.

**Lim Zhi Pin** executed the full adversarial and safety testing battery — running the injection (INJ), adversarial-prompt (ADV), language-robustness (LNG), and safety-critic (SAF-05) probes. He identified input- and output-side failures and proposed the targeted fixes that brought those test cases to pass.

**Satish Rao** led the rPPG accuracy validation, running the 34-subject pilot and producing the Bland-Altman agreement analysis (bias −0.5 BPM) reported in §4.4.5.1. He took primary responsibility for assembling the final report, authoring Chapters 5 and 6 and making the cross-chapter consistency passes that unified the manuscript.

**Chin Pei Kang** completed the frontend unit-test suite (Vitest, React Testing Library), ran the DDx and determinism evaluation layers, and wrote the technical sections of Chapters 1, 3, and 4. He also produced the expert-evaluation poster design and integrated the final validation visual assets — the DDx three-granularity scorecard and the knowledge-graph composition diagram — into the report.

**Low Jia Qi** produced the project video plan and edited the final video submission. She contributed to the poster layout and supported documentation tasks during the final report sprint.

### 6.2.3 Summary of Individual Task Contributions (Semester 1 & 2)

Table 6.1a consolidates the per-member work breakdown shown in the Gantt chart (Figure 6.1) with the actual contributions delivered during Semester 2. Tasks marked "ALL" in the Gantt chart were carried out jointly by the whole team and are listed once at the top of the table rather than repeated under each member.

*Table 6.1a: Individual Contribution Summary (Semester 1 & 2)*

| Team Member | Semester 1 — Planned & Completed Tasks | Semester 2 — Planned & Actual Tasks |
|---|---|---|
| **All Members (Shared)** | • Identify target market<br>• Identify the problem<br>• Generate concept generation table<br>• Screen and select the product concept<br>• Idea pitching (Mini TGL)<br>• Prepare system design documentation<br>• Validate extracted clinical knowledge<br>• Backend functional testing | • Integration testing<br>• Clinical validation with healthcare professionals<br>• Final system integration<br>• Final documentation and presentation |
| **Chua Zhu Heng** (Knowledge Base & Grounding Infrastructure) | • Developed the need-metrics matrix<br>• Defined data flow between components<br>• Identified and obtained Clinical Practice Guidelines<br>• CPG pre-processing (Docling)<br>• Optimised markdown structure<br>• Built the ingestion pipeline<br>• Structured content with metadata and versioning<br>• Set up the pgvector vector database | • Entity-based chunking for the ICD-11 DDx engine<br>• Refinement based on clinical validation results<br>• Integrated the structured clinical knowledge base into the live consultation pipeline; finalised metadata routing and vector-retrieval protocols<br>• Revamped the ingestion pipeline (parent-child chunking, restructured KG node relationships)<br>• STT integration as part of the grounding infrastructure layer |
| **Chin Pei Kang** (AI Systems & Evaluation Engineering) | • Conducted benchmarking of existing solutions<br>• Designed the RAG + LLM interaction pipeline<br>• Set up Neo4j and the graph schema<br>• Built the knowledge-graph search<br>• Drafted the system prompt for the tool-routing strategy<br>• Built the two-stage formatting pipeline<br>• Implemented the search tools | • Integrated the ICD-11 DDx engine with the main RAG<br>• DDx engine testing and validation<br>• Created the test dataset of patient cases<br>• Faithfulness, adversarial & safety stress testing<br>• Transitioned to API-level integration and evaluation; developed automated backend test harnesses and executed RAG performance assessments |
| **Satish Rao** (Multimodal Intake & Hardware Integration) | • Identified the needs statement<br>• Defined the security and access-control model<br>• Implemented the audit trail and version control<br>• Calibrated LLM response quality<br>• Implemented citation and hallucination safeguards<br>• Implemented the care-plan API endpoint<br>• Displayed source CPG citations clearly | • Researched rPPG / contactless vital-sign methods<br>• Set up the rPPG signal-processing pipeline<br>• Camera signal capture & rPPG extraction<br>• Integrated rPPG vitals into the clinical consultation<br>• Started building the clinical test dataset<br>• Finalised the rPPG vital-sign acquisition hardware<br>• Engineered the CPG citation and hallucination-auditing displays |
| **Low Jia Qi** (System Architecture & Application Integration) | • Established the target specification<br>• Defined the overall system architecture<br>• Structured CPG markdown content with metadata<br>• Defined the database schema<br>• Frontend UI integration<br>• Designed the patient dashboard<br>• Began the user-interaction controls for the Doctor UI | • Finalised the full-stack integration<br>• Developed the front-end clinician dashboard<br>• Built the application data layer on Supabase to provide an isolated, stable testing environment |
| **Lim Zhi Pin** (Clinical Logic & Diagnostic Engineering) | • Conducted the stakeholder survey and interviews<br>• Defined the API input/output contracts<br>• Implemented API authentication and authorisation<br>• Handled the API-unavailability fallback logic | • Built the ICD-11 knowledge base<br>• Built the symptom-to-code vector search<br>• Built the DDx ranking logic<br>• Implemented the system's fallback mechanisms<br>• Validated the differential diagnosis engine against clinical gold sets formally verified by collaborating healthcare professionals |

> **Note on unassigned Gantt rows:** WBS items 6.3, 10.2, and 11.2–11.5 appear as numbering gaps in the Gantt chart with no task title or owner visible. If these correspond to real, undocumented tasks, they should be assigned to **Lim Zhi Pin** or **Low Jia Qi**, who carry the lightest Semester 2 load relative to the other members — please confirm the task titles for those rows so they can be added to the table above.

---

## 6.3 Project Cost

The project incurred costs across two categories: a one-time hardware purchase for the rPPG contactless vitals prototype and direct software expenditure for cloud and API services consumed during development. All costs are stated in Malaysian Ringgit (RM). Foreign-currency charges are converted at USD 1 ≈ RM 4.70 and CNY 1 ≈ RM 0.66. Projected operating figures in §6.3.3 are estimates based on expected usage patterns; the actual development figures in §6.3.1 and §6.3.2 reflect invoiced amounts.

### 6.3.1 Hardware Costs

The rPPG module was prototyped using an ESP32 microcontroller paired with a MAX30100 pulse-oximeter breakout board, sourced locally from Robotronik. All four components were purchased as a single one-time outlay at the start of the project.

*Table 6.1: Hardware Bill of Materials*

| No. | Component | Purpose | Cost (RM) |
|:---:|:----------|:--------|----------:|
| 1 | ESP32 NodeMCU 38-Pin (Wi-Fi + Bluetooth) | Microcontroller — runs rPPG signal processing and streams vitals over Wi-Fi | 26.99 |
| 2 | MAX30100 Heart-Rate & SpO₂ Sensor (soldered) | Captures pulse and blood-oxygen readings for rPPG baseline validation | 9.99 |
| 3 | Solderless Breadboard (830 tie-points) | Prototyping platform for the sensor circuit | 3.69 |
| 4 | Jumper Wires — Male-to-Female, 40-wire, 20 cm | Sensor-to-microcontroller connections | 3.20 |
| | | **Hardware Subtotal** | **43.87** |

### 6.3.2 Software and Cloud Development Costs

Direct software costs were incurred by two team members for services billed to the project during the development period. Internal tooling and personal subscriptions used for general work are excluded from this account.

*Table 6.2: Actual Software Development Expenditure*

| No. | Team Member | Service | Cost (RM) |
|:---:|:-----------|:--------|----------:|
| 1 | Lim Zhi Pin | AWS — backend infrastructure and hosting | 173.16 |
| 2 | Chua Zhu Heng | Gemini Flash API — LLM stage calls | 100.00 |
| | | **Software Subtotal** | **273.16** |

### 6.3.3 Estimated Monthly Operating Costs (Projected)

For reference, Table 6.3 projects the system's recurring cost at a representative pilot volume of 500 consultations per month. Fixed subscriptions cover the six managed services required to run the backend pipeline, knowledge graph, and hosting infrastructure. Variable costs arise from per-consultation LLM and retrieval calls billed on usage.

*Table 6.3: Projected Monthly Operating Cost at Pilot Scale (500 Consultations / Month)*

| No. | Cost Line | Provider / Tier | Monthly Cost (RM) |
|:---:|:----------|:----------------|------------------:|
| | **A — Fixed Monthly Subscriptions** | | |
| 1 | Vector + relational store | Neon Postgres — Launch | ~89 |
| 2 | Auth, application database & PDF storage | Supabase — Pro | ~118 |
| 3 | Drug knowledge graph | Neo4j AuraDB — Professional (1 GB) | ~306 |
| 4 | Backend API hosting | Render — Standard | ~118 |
| 5 | Frontend hosting | Vercel — Pro | ~94 |
| 6 | Stage 5 synthesis LLM | MiMo v2.5 Pro — Standard (¥99/mo, 200 M tokens) | ~65 |
| | | **Fixed Subtotal** | **~790** |
| | **B — Variable API Cost (per consultation)** | | |
| 7 | Extraction, DDx re-rank, query-gen & safety critic (Stages 2, 4, 6) | Gemini 2.5 Flash | ~0.05 |
| 8 | Query embedding + chunk rerank | Titan Embed v1 + Cohere Rerank v3.5 (AWS Bedrock) | ~0.05 |
| | | **Variable Cost per Consultation** | **~0.10** |
| | | **Estimated Monthly Total (500 consultations)** | **~840** |

The MiMo Standard plan supplies 200 million tokens per month. At approximately 17,000 tokens per synthesis call, this covers around 11,000 consultations — well above pilot volume — making Stage 5 synthesis effectively a fixed cost at this scale rather than a per-consultation charge. The one-time corpus build cost (30 CPGs chunked, embedded, and parsed into the knowledge graph) is a few tens of Ringgit in API calls, repeated only when a guideline is revised.

### 6.3.4 Total Project Expenditure

Total actual expenditure for the project was **RM 317.03**: RM 43.87 in hardware (§6.3.1) and RM 273.16 in software and cloud services (§6.3.2). The dominant resource throughout was engineering time rather than monetary spend. The projected recurring operating cost at pilot scale is addressed separately in §6.3.3.

---

## 6.4 Risk Considerations and Assessment

A clinical decision-support system carries risks a consumer application does not: a wrong output can contribute to patient harm, and the absence of a specialist to catch it is the very condition the tool is deployed into. The risks span five categories — **clinical & patient-safety**, **technical & operational**, **data privacy & regulatory compliance**, **adoption & human-factors**, and **sustainability & maintenance**. Each is assessed below for likelihood and impact and mapped to the mitigation already built into the system.

### 6.4.1 Risk Assessment and Mitigation Strategies

| ID | Category | Risk | Likelihood | Impact | Mitigation (built-in) |
|---|---|---|---|---|---|
| R1 | Clinical | Unsupported/hallucinated recommendation (faithfulness 0.864 < 0.90 target) | Medium | High | Independent Stage 6 faithfulness critic; cite-or-abstain commandment; Pydantic schema validation fails closed |
| R2 | Clinical | Drug interaction outside KG coverage missed | Medium | High | Dual-source critic — LLM arm reasons beyond the graph; coverage boundary disclosed; mandatory clinician sign-off |
| R3 | Clinical | Automation bias — clinician over-trusts output | Medium | High | Per-stage reasoning traces; forced pertinent-negative; positioned as decision support, not autonomous diagnosis; audited human sign-off |
| R4 | Clinical | Confident answer on out-of-scope case | Low | High | Scope-refusal gate emits first-class `out_of_scope`; silence preferred over reach |
| R5 | Technical | LLM API outage / latency spike | Medium | Medium | Fail-loud degradation events; configurable model fallback (`STAGE5_LLM_*` override) |
| R6 | Technical | Silent degradation (e.g. zero-chunk → confident plan) | Low (post-fix) | High | SIL/INF probes; fail-loud contract added to the pipeline |
| R7 | Technical | Non-deterministic top-1 in co-equal-diagnosis cases | Medium | Low | Variance localised to the seedless re-ranker and surfaced, not hidden; seedable-backend roadmap |
| R8 | Data / Compliance | Patient PII exposure under PDPA 2010 | Medium | High | Data minimisation; client state resets on refresh (no patient data persists); audit trail; managed-DB encryption — production needs a formal PDPA review |
| R9 | Regulatory | Software-medical-device classification / MOH governance | Medium | High | Non-autonomous positioning + clinician sign-off + scope refusal — formal SaMD/MDA classification is a deployment precondition |
| R10 | Adoption | Latency leaves little margin in the ~10-minute consultation, slowing fast-triage uptake | High | Medium | Streaming Stage 5 and summary-mode UI on the roadmap (§5.3.1) |
| R11 | Sustainability | CPG corpus goes stale on MOH revision | Medium | Medium | Low-friction re-ingestion + regression harness (~2–4 h engineering per revised document) |

### 6.4.2 System Design Response to Risks

The architecture was risk-driven, not retrofitted. The three highest-impact clinical risks each answer to a specific structural control rather than a prompt instruction: hallucination (R1) to an *independent* faithfulness critic that fails closed; a missed interaction (R2) to a *dual-source* safety critic whose LLM arm reasons past the graph's coverage boundary; and over-trust (R3) to mandatory, fully-traced human sign-off that keeps the clinician — not the model — as the decision-maker. The fail-loud testing posture (R6) converts the most dangerous failure mode, silent degradation, into a visible event. The residual high-impact risks the project cannot close from within — PDPA review, medical-device classification, multi-clinician validation — are not concealed but stated as explicit deployment preconditions (§6.5.3).

---

## 6.5 Safety and Health

For a clinical system, safety is not one consideration among many — it is the design centre. This section states affirmatively how the system protects patient safety, clinician wellbeing, and safe clinical use; the corresponding failure modes, their likelihood, and their mitigations are tabulated as a risk register in §6.3.

### 6.5.1 Patient Safety by Design

Patient safety is enforced structurally, not by prompt instruction. The Stage 6 **dual-source safety critic** combines LLM pharmacological reasoning with a typed drug knowledge graph and blocks plan sign-off on any CRITICAL or MAJOR flag until the clinician resolves it. The synthesis stage operates under a cite-or-abstain rule — a recommendation must be traceable to a retrieved guideline chunk or the model must say "unknown" — and the entire output is schema-validated, so a malformed plan is rejected rather than shown half-finished. Two further behaviours protect against the most dangerous failure mode, confident wrongness: **scope refusal** emits a first-class `out_of_scope` event instead of fabricating a plan for a case outside the validated corpus, and the **fail-loud** contract (verified by the SIL/INF probes) ensures a degraded dependency surfaces as a visible error rather than a confident plan built on no evidence.

### 6.5.2 Clinician Health and Ergonomics

A decision-support tool can harm patients not only by being wrong but by being badly designed for the human using it — a well-documented hazard in clinical informatics. Two ergonomic risks were treated as safety concerns, not cosmetics:

- **Alert fatigue.** When a system over-warns, clinicians learn to dismiss alerts wholesale — including the valid ones. The safety banner therefore filters low-value MODERATE LLM noise (while always retaining graph-verified flags), classifies every flag into *plan-relevant*, *current-medication*, or *class/noise*, and gates acknowledgement only on the flags that bear on the planned medications. The clinician is asked to act on what matters, not to clear a wall of warnings.
- **Cognitive load under time pressure.** The dense, structured care plan suits considered review but burdens a fast triage encounter — a gap the expert evaluation made explicit (Information Density 3/5, Workflow Fit 2/5). The roadmap responses to this (summary-first view, streaming output; §5.3.1) are framed here as a clinician-ergonomics measure, not only a speed one. Conversely, the action-tagged plan (START / CHANGE / CONTINUE / STOP) already reduces the mental effort of extracting an order list from prose.

Reducing the clinician's cognitive burden in a time-constrained consultation is itself a patient-safety measure: a clear, scannable, appropriately-alerting interface is less error-prone than a dense one.

### 6.5.3 Clinical Governance and Safe Use

ClearPath is positioned as **decision support, not autonomous diagnosis**. The clinician reviews, edits, and signs off every plan and remains the accountable decision-maker; the system's role is to surface grounded options and catch what an isolated clinician might miss. This is backed by a complete **audit trail** — per-stage reasoning traces and a safety-acknowledgement record (who acknowledged which flag, and when) — so every recommendation and every override is reconstructable after the fact. Scope refusal functions here as a governance boundary: the system declines rather than reaches beyond its validated competence.

Safe deployment carries explicit preconditions, stated rather than assumed: a formal PDPA review of patient-data handling, software-medical-device classification under MDA governance, and clinician orientation so the tool is used within its validated scope and not over-trusted (the automation-bias risk, R3). Within that governed workflow, the system augments clinical judgement; it does not substitute for clinical responsibility.

---

## 6.6 Sustainability: Economic, Environmental, Social, and Stakeholder

ClearPath is not only a technical artefact but a sustainable intervention in a resource-constrained health system. Its impact is evaluated below from four perspectives: economic, environmental, social, and stakeholder.

### 6.6.1 Economic Sustainability

ClearPath is software-only: it runs in a browser against managed cloud infrastructure, so a clinic needs no special hardware, workstation, or per-seat licence — only its existing computer and internet connection. At **~RM 0.10 per consultation** and a fixed run-rate of **~RM 840/month** for an entire clinic's caseload (§6.3), the economics scale favourably — the marginal cost of the next consultation is a few sen, and the fixed infrastructure is shared across every clinician on the platform.

The larger economic argument is downstream. Each consultation in which the tool surfaces a guideline the clinician lacked time to find, catches an interaction a pharmacist-vacant clinic would have missed, or averts an unnecessary referral displaces a cost far larger than the inference that produced it — avoided patient travel, avoided medication-related admission, avoided repeat visit. Against the documented CPG non-adherence gap (§6.7), even a modest improvement in adherence compounds across a national network of clinics. Ongoing maintenance is bounded — about 2–4 hours of engineering per revised guideline (§6.3).

### 6.6.2 Environmental Sustainability

The system's environmental footprint is light and largely digital. Per-consultation compute is dominated by the LLM inference calls — chiefly the Stage 5 synthesis on MiMo v2.5 Pro — while the deterministic early stages (routing, vector retrieval, rerank scoring) carry negligible energy cost. Two design choices actively reduce waste: **scope refusal** halts the pipeline before the expensive synthesis call on out-of-scope cases, spending no inference where the system has nothing valid to say; and the backend runs on **managed serverless infrastructure** (Neon, Aura) that scales with load rather than holding idle compute.

The more meaningful environmental contribution is indirect. In the geographically dispersed districts of Sabah and Sarawak, an unnecessary secondary referral often means a patient travelling hundreds of kilometres — by road, river, or air — to a tertiary centre. Every referral that grounded decision support safely avoids is avoided travel, and the carbon of that displaced journey dwarfs the few grams attributable to the inference call. A correctly grounded care plan delivered at the point of first contact is, in this sense, an environmentally efficient substitute for the physical movement of patients across a large, low-density geography.

### 6.6.3 Social Sustainability

Social sustainability is the dimension where ClearPath's purpose is clearest: it is an equity intervention. The structured second opinion, guideline-at-hand, and pharmacist-style medication check that urban practice takes for granted (§6.7) are brought to the rural clinic that structurally lacks them, narrowing the urban–rural care gap for the populations most exposed to it.

It does so without deskilling the clinician — the system is decision support, not a replacement (§6.5.3) — and its grounding in Malaysian MOH guidelines rather than imported defaults keeps the advice culturally and clinically appropriate. By reasoning transparently and declining cases beyond its competence, it earns the professional trust on which adoption depends.

### 6.6.4 Stakeholder Considerations

The system was designed with several stakeholder groups in mind, each with distinct needs:

- **Rural clinicians and medical assistants** gain a safety net and a structured second opinion that reduces cognitive load under time pressure, with a full audit trail behind every recommendation — support without surrendering authority.
- **Patients** receive safer prescriptions, fewer unnecessary referrals and the travel they entail, and care that is aligned to the current national guideline rather than to whatever could be recalled under time pressure.
- **The Ministry of Health and the wider health system** stand to gain measurable improvement against the CPG non-adherence gap, reduced preventable medication harm, and cost savings on avoidable referrals and admissions — alongside structured data on real rural care patterns.
- **Regulators (the Medical Device Authority)** are served by the system's non-autonomous positioning, mandatory clinician sign-off, scope refusal, and complete audit trail, which together ease the software-medical-device governance pathway that production deployment will require.
- **Pharmacists and specialists** are complemented, not replaced: the tool offloads routine interaction and guideline checks at the point of first contact, reserving scarce specialist attention for the cases that genuinely need it.
- **The public**, as indirect stakeholders, benefit from a more equitable health system and from the trust that transparent, appropriately bounded clinical AI can build.

As the system matures, stakeholder engagement remains essential — collecting clinician feedback through the built-in approval loop, re-validating against revised guidelines, and maintaining the transparency that keeps every recommendation accountable to the people it affects.

---

## 6.7 Addressing the Local Community: Rural Malaysian Primary Care

ClearPath was built for a specific community: rural and district primary-care clinicians in Sabah and Sarawak, and the patients they serve under systematic resource constraint. Every architectural choice reflects that context — the corpus is exclusively Malaysian MOH guidelines (not AHA or ESC defaults adopted without local adaptation), the evaluation gold sets and safety-critic logic follow Malaysian clinical and prescribing practice, and the interface is built for a solo medical officer or medical assistant under time pressure, not a specialist in a resource-rich tertiary centre.

Its design answers the three faces of clinical decision isolation identified in §1.2. The absence of a *colleague* is met by a structured, evidence-grounded second opinion (DDx and care-plan synthesis); the absence of a usable *guideline* by surfacing the relevant locally-validated CPG section within the consultation; the absence of a *pharmacist* by a dual-source medication audit that checks current and proposed drugs against both LLM reasoning and a typed interaction graph. These are not generic features but a direct response to documented rural practice: a 39.3% CPG non-adherence rate driven by time and search friction [6], an 88% second-assessment revision rate among complex cases [3], and medication-related harm that is roughly half of all preventable harm when no pharmacist is present [18]. ClearPath is the second pair of eyes these clinics structurally lack — not a replacement for the clinician.

What has been demonstrated is bounded honestly. The recommendations are guideline-grounded, safety-checked, and endorsed in a single structured expert evaluation (Universiti Malaya, n=1), which also identified speed and output density as the primary adoption gaps — directly shaping the §5.3 priorities. What has *not* been collected is clinical evidence of improved decisions under real rural conditions; that requires deployment, IRB approval, and a prospective study beyond this project's scope.

ClearPath's contribution is therefore best described as a credible infrastructure artefact: a functional, evaluated, and honestly documented decision-support system built specifically for Malaysian rural primary care, ready for the deployment and prospective validation that will determine whether it improves care in practice.
