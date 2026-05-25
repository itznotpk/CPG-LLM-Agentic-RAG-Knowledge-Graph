<p align="center">
  <strong>UNIVERSITI MALAYA</strong> &nbsp;•&nbsp; <strong>MHNEXUS</strong>
</p>
<p align="center">
  <img src="assets/ClearPath Logo.png" alt="ClearPath Logo" width="320" />
</p>
<p align="center"><strong>Clinician's second opinion, at the speed of a glance.</strong></p>
<p align="center">
  <i>An Evidence-Based Clinical Practice Guidance System grounded in Malaysia's Clinical Practice Guidelines (CPGs)</i>
</p>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React" />
  <img src="https://img.shields.io/badge/PostgreSQL_pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Neo4j_Graph-008CC1?style=flat-square&logo=neo4j&logoColor=white" alt="Neo4j" />
  <img src="https://img.shields.io/badge/Google_Gemini-4285F4?style=flat-square&logo=google&logoColor=white" alt="Gemini" />
</p>

<p align="center">
  <img width="800" alt="ClearPath Clinician Dashboard" src="assets/clearpath_landing.png" />
</p>

---

**One Line Summary:** A deterministic, auditable clinical practice guidance pipeline that streams evidence-graded specialist second opinions to isolated rural clinics in under a minute.

**Key Insight:** Authoritative medical guidelines are only useful if they can be referenced within a standard 10-minute consultation window. By transforming massive static CPG PDFs into a contextual, real-time routing engine audited by an adversarial safety critic, we shift clinical guideline utilization from active, high-friction search to passive, intelligent decision-support at the speed of a glance.

---

## Project Background & Remote Medicine Context

In remote medicine, junior Medical Officers (MOs) and Medical Assistants (MAs) in rural Malaysian *Klinik Kesihatan* operate under severe structural constraints:
* **Resident Doctor Shortage:** Up to **45.6% of rural clinics in East Malaysia operate without a resident doctor**, run entirely by medical assistants and nurses with basic paracetamol-level supplies.
* **Specialist & Pharmacist Absence:** Junior clinicians face absolute clinical isolation, devoid of immediate senior specialist consult teams or clinical pharmacists to audit prescribing safety.

---

## Problem Statements & Transformed Needs

ClearPath directly addresses the three core bottlenecks of rural clinical delivery, transforming each clinical friction into a structured capability:

### 1. Guideline Accessibility & Search Friction
* **The Clinical Bottleneck:** Authoritative Clinical Practice Guidelines (CPGs) reside in massive, multi-hundred-page static PDFs. Under intense patient volume, junior clinicians cannot manually open, search, and parse these documents within a standard **10-minute consultation window**, leading to guideline underutilization.
* **Need (Top Feature):** **Deterministic Scoped Routing & Multi-Query Retrieval** (Stages 3 & 4). Automatically scopes queries to verified CPGs and brings exact, deduplicated evidence-graded chunks to the doctor instantly, eliminating manual PDF searches.

### 2. Clinical Diagnostic Isolation & Cognitive Fatigue
* **The Clinical Bottleneck:** Rural clinicians operate in professional isolation without senior specialists. When presented with patients exhibiting complex, overlapping comorbidities (e.g., uncontrolled diabetes and stage-2 hypertension), junior officers face extreme diagnostic cognitive fatigue and increased risk of misdiagnosis.
* **Need (Top Feature):** **Contextual DDx Re-Ranking & Interactive Clinician Override** (Stages 2 & 5). Generates named disease hypotheses, re-ranks differentials using Gemini thinking tokens tailored to patient profiles, and gives clinicians full override controls to trigger instant care-plan re-synthesis.

### 3. Medication Safety Vulnerability in Pharmacist-Vacant Clinics
* **The Clinical Bottleneck:** Resource-constrained rural clinics operate without on-site clinical pharmacists. Junior practitioners prescribing multi-drug therapies face significant risks of severe adverse drug events (ADEs) due to overlooked drug-drug interactions, cross-reactive allergies, and organ-clearance dosing limits (e.g., renal failure).
* **Need (Top Feature):** **Independent Adversarial Safety Critic** (Stage 6). An automated clinical pharmacist operating on a Generator-Evaluator pattern that audits the complete care plan for allergies, interactions, and contraindications before the doctor signs off.

---

## Solution

We propose **ClearPath<span style="color:#0d9488">.</span>**, an AI-powered Clinical Practice Guidance System designed specifically for the **Remote Medicine Track**. 

ClearPath acts as a clinician's second opinion, at the speed of a glance. By converting static, complex guidelines into an automated, moment-driven pipeline, it minimizes documentation time, safeguards patient care, and allows doctors to spend their precious hours **with patients, not paperwork**.

<p align="center">
  <img width="800" alt="From triage to care plan, in three steps" src="assets/triage_concept.png" />
</p>

---

## System Architecture

ClearPath features a **hybrid deterministic + agentic clinical architecture** that enforces strict guideline safety boundaries while leveraging advanced clinical reasoning models (with thinking tokens) to synthesize plans. 

```
                               ┌────────────────────────────────────────────────────────┐
                               │           Patient Intake & Vitals Ingestion            │
                               │  - Vitals (Manual/rPPG), History, Chief Complaint      │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ PatientCase JSON
                                                           ▼
     [STAGE 2: DDX]            ┌────────────────────────────────────────────────────────┐
                               │        Symptom-to-ICD-11 DDx Extraction Pipeline        │
                               │  - Symptom Extractor Subagent (lightweight distiller)  │
                               │  - Hypothesis Generator Subagent (named diseases list) │
                               │  - Multi-Query Parallel Vector Search (3,914 codes)    │
                               │  - Contextual LLM Re-Ranker Agent (thinking tokens)    │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ Top Differentials (Ranked & Scored)
                                                           ▼
     [STAGE 3: ROUTE]          ┌────────────────────────────────────────────────────────┐
                               │       Deterministic Guideline Scoped Routing Layer     │
                               │  - Deterministic Scope Resolver (exact/ancestor/sib)   │
                               │  - Sex-Incompatibility Filter (obstetric exclusions)   │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ Scoped CPG Document References
                                                           ▼
     [STAGE 4: RETRIEVE]       ┌────────────────────────────────────────────────────────┐
                               │           Evidence-Graded Scoped Retrieval             │
                               │  - Targeted Query Generator Subagent (3-7 CPG queries) │
                               │  - Scoped Vector Search (strictly scoped via pgvector) │
                               │  - Hierarchical Content Prefetcher (H3 -> H2 -> H1)   │
                               │  - Cross-Reference Resolver (resolves inline anchors)  │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ High-Fidelity Context Pack
                                                           ▼
     [STAGE 5: SYNTHESIZE]     ┌────────────────────────────────────────────────────────┐
                               │             Evidence-Guided Care Plan Synthesis        │
                               │  - Knowledge Graph Traversal Subagent (Neo4j pathways) │
                               │  - Treatment Plan Synthesizer Agent (Pydantic schema)  │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ Drafted Care Plan (JSON)
                                                           ▼
     [STAGE 6: CRITIC]         ┌────────────────────────────────────────────────────────┐
                               │           Medication Safety Critic (Adversarial)       │
                               │  - Independent Clinical Safety Critic (allergy/DDI)    │
                               │  - Audit Logger (timestamped review trails)            │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ Audited TreatmentPlan & Safety Flags
                                                           ▼
                                ┌────────────────────────────────────────────────────────┐
                                │          Live Transparent Clinician UI (SSE)           │
                                │  - Watch agent reasoning steps & override diagnostics  │
                                └────────────────────────────────────────────────────────┘
```

### Stage 2: Symptom-to-ICD-11 DDx Extraction (`stage_2_ddx`)
* **Symptom Extractor Subagent:** Distills raw intake notes into a single symptom-focused query phrase (max 15 words) using a lightweight model to bridge the vocabulary gap.
* **Condition Hypothesis Generator Subagent:** Generates likely named medical conditions (which embed far better in vector space than symptom narratives).
* **LLM Contextual Re-Ranker Agent:** Employs Gemini with extended thinking tokens to re-rank vector matches based on patient age, sex, comorbidities, and current medication context, logging rank changes and override reasons.

### Stage 3: Deterministic Scoped Routing (`stage_3_route`)
* **Deterministic Scope Resolver:** Maps top ICD-11 codes strictly against database-enforced metadata (`documents.icd11_scope` in PostgreSQL). Supports exact, parent/ancestor, sibling, and semantic fallbacks.
* **Sex-Incompatibility Filter:** Prevents cross-biological routing errors (e.g., automatically excluding pregnancy CPGs for male patients or erectile dysfunction for female patients) and logs exclusions in the trace.

### Stage 4: Scoped Evidence Retrieval (`stage_4_retrieve`)
* **Targeted Query Generator Subagent:** Drafts 3-7 domain-specific queries based on the routed guideline scopes.
* **Scoped pgvector Search:** Runs parallel similarity searches scoped strictly by Neon PostgreSQL `document_id_filter` to the active CPG documents to prevent cross-guideline contamination.
* **Hierarchical Content Prefetcher:** Prefetches grandparent headers and section scopes (H3 -> H2 -> H1) to ensure critical local guidelines, Levels of Evidence, and localized abbreviations are retained in context.
* **Cross-Reference Resolver:** Scans hit chunks for inline cross-references to other CPGs and programmatically resolves, fetches, and appends them to the evidence pack.

### Stage 5: Care Plan Synthesis (`stage_5_synthesize`)
* **Knowledge Graph Traversal Subagent:** Queries Neo4j Aura via Graphiti to extract explicit drug-to-drug safety boundaries and step-by-step guideline algorithm pathways.
* **Treatment Plan Synthesizer Agent:** Assembles patient data, retrieved CPG evidence, and Graph rules into a Pydantic-validated `TreatmentPlan` JSON structure, stamping recommendations with MOH evidence levels (e.g., Level I, Grade A).

### Stage 6: Medication Safety Critic (`run_safety_critic`)
* **Hybrid LLM + Knowledge-Graph Critic:** Two independent graders run in parallel (`asyncio.gather`) and their flags are **merged without dedup** — the LLM critic catches narrative/reasoning issues, while a Neo4j `_kg_verify_plan` pass catches structural drug/condition violations even when no CPG paragraph mentions them. `safe_to_proceed` is recomputed across the union; any CRITICAL/MAJOR flag blocks sign-off.
* **Independent Clinical Safety Critic Subagent:** Operating on a strict **Generator → Evaluator pattern**, this adversarial subagent plays the role of an independent clinical pharmacist. Without having seen Stage 5's reasoning chain, it audits the TreatmentPlan for:
  1. *Drug Allergies* (including complex sulfonamide class cross-reactivity risks).
  2. *Drug-Drug Interactions* (e.g., Warfarin + new NSAID bleeding risk).
  3. *Dosing Suite* (e.g., standard Metformin contraindications in Stage 4 CKD).
  4. *Absolute Contraindications* (e.g., non-selective beta-blockers in severe asthma).
* **Audit Logger:** Persists all safety flags, active clinician diagnostic overrides, and final plans with exact session timestamps to generate a transparent audit trail.

---

## Implementation

ClearPath represents a complete clinical end-product, designed for visual tablet/desktop dashboards at rural clinics or standalone terminal deployments:

<table width="100%">
  <tr>
    <td align="center" width="50%">
      <strong>Doctor UI Dashboard (Clinician Workspace)</strong>
    </td>
    <td align="center" width="50%">
      <strong>clinical_cli.py (Backend Orchestrator)</strong>
    </td>
  </tr>
  <tr>
    <td align="center" valign="top">
      <img width="100%" alt="Doctor UI Dashboard View" src="assets/doctor_ui_dashboard.png" />
    </td>
    <td align="center" valign="top">
      <img width="100%" alt="clinical_cli.py Terminal View" src="assets/clinical_cli_terminal.png" />
    </td>
  </tr>
  <tr>
    <td align="left" valign="top" style="padding: 10px;">
      <ul>
        <li><strong>Patient Queue Pulse:</strong> Prioritizes clinical triage by highlighting critical cases and overdue follow-ups dynamically.</li>
        <li><strong>Workflow Analytics:</strong> Tracks administrative impact, demonstrating overall CPG alignment and cumulative clinician time reclaimed.</li>
        <li><strong>Real-Time Streaming:</strong> Streams interactive differentials lists, safety reviews, and synthesized care plans to the workspace.</li>
      </ul>
      <p align="center">
        <a href="Doctor%20UI/">Explore Frontend Workspace →</a>
      </p>
    </td>
    <td align="left" valign="top" style="padding: 10px;">
      <ul>
        <li><strong>Intake Console:</strong> Guides clinicians through structured intake parsing (vitals, current medications, allergies, and history).</li>
        <li><strong>Scope Verification:</strong> Enforces deterministic mapping of primary ICD-11 codes to verified MOH guidelines on the backend.</li>
        <li><strong>Override Harness:</strong> Prompts clinicians to accept AI suggestions or input custom codes, executing real-time re-synthesis.</li>
      </ul>
      <p align="center">
        <a href="clinical_cli.py">View clinical_cli.py Code →</a>
      </p>
    </td>
  </tr>
</table>

---

## Decision & Reasoning Matrix

The table below illustrates how a single remote consultation is processed step-by-step through the ClearPath clinical decision engine:

| Stage | Input Signals / State | AI & Engine Action | Output Artifact / Decision | Reasoning & Grounding |
|---|---|---|---|---|
| **Stage 1: Intake** | *Patient Case (rural Sarawak clinic):* 67 F, exertional chest tightness • T2DM history • BP 142/88 • HbA1c 8.5% | Standardizes intake details and vitals into a structured query. | `PatientCase` (JSON schema) | Organizes raw clinical signals for downstream agent processing. |
| **Stage 2: DDx** | PatientCase symptoms and comorbidities. | Distills symptom phrase • Generates hypotheses • Vector search over 3,914 codes • Reranks with Gemini. | 1. T2DM uncontrolled (`5A11`, 87%) <br>2. Stage 2 Hypertension (`BA00`, 71%) | Correlates patient age, elevated HbA1c, and BP readings with WHO diagnostic criteria. |
| **Stage 3: Routing** | Primary DDx selected: `5A11` and `BA00` | Resolves metadata in PostgreSQL • Enforces biological sex compatibility filter. | Routes to *T2DM (6th Ed)* and *Hypertension (5th Ed)* | Confirms that CPG documents exist and that sex-restricted guidelines are not violated. |
| **Stage 4: Retrieval** | Scoped CPG documents + PatientCase | Generates 3 CPG queries • Scopes pgvector chunks • Prefetches grandparent headers. | Fetches evidence-grade chunks and local abbreviations. | Prevents out-of-scope guideline references; ensures rich context is fed to synthesis. |
| **Stage 5: Synthesis** | Retrieved chunks + Neo4j Graph rules | Traverses Neo4j drug nodes • Synthesizes TreatmentPlan JSON with Gemini. | Drafts care plan (e.g., START SGLT2i [Level I, Grade A] • START ACEi). | Grounded recommendations cited to CPG sections and evidence tables. |
| **Stage 6: Critic** | PatientCase + Drafted TreatmentPlan | Evaluates plan for allergies, interactions, dosing, and contraindications. | `SafetyReport` (safe_to_proceed = true, 0 flags) | screens all drugs against current medications and comorbidity records before rendering. |
