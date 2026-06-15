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
  <img src="https://img.shields.io/badge/Neo4j_Aura-008CC1?style=flat-square&logo=neo4j&logoColor=white" alt="Neo4j" />
  <img src="https://img.shields.io/badge/MiMo_v2.5_Pro-FF6F00?style=flat-square" alt="MiMo" />
  <img src="https://img.shields.io/badge/Gemini_2.5_Flash-4285F4?style=flat-square&logo=google&logoColor=white" alt="Gemini" />
</p>

<p align="center">
  <img width="800" alt="ClearPath Clinician Dashboard" src="assets/clearpath_landing.png" />
</p>

---

**One Line Summary:** A deterministic, auditable clinical practice guidance pipeline that streams evidence-graded specialist second opinions to isolated rural clinics in minutes, well inside the standard consultation window.

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
* **Need (Top Feature):** **Deterministic Scoped Routing & Multi-Query Retrieval** (Stages 3 & 4). Six-level routing ladder (D1 exact → D2 sibling → ancestor → semantic pgvector against `documents.scope_embedding` → out-of-scope) deterministically scopes queries to verified CPGs and brings deduplicated, evidence-graded chunks to the doctor instantly, eliminating manual PDF searches.

### 2. Clinical Diagnostic Isolation & Cognitive Fatigue
* **The Clinical Bottleneck:** Rural clinicians operate in professional isolation without senior specialists. When presented with patients exhibiting complex, overlapping comorbidities (e.g., uncontrolled diabetes and stage-2 hypertension), junior officers face extreme diagnostic cognitive fatigue and increased risk of misdiagnosis.
* **Need (Top Feature):** **Contextual DDx Re-Ranking + Clinician-Named CC Boost + Interactive Override** (Stages 2 & 5). Generates named-disease hypotheses, lifts diagnoses the clinician already named in CC/HPI via a name→ICD resolver (never trusting LLM-emitted codes), re-ranks differentials with reasoning-token LLMs tailored to age/sex/comorbidities/meds, and gives clinicians full override controls that trigger instant care-plan re-synthesis.

### 3. Medication Safety Vulnerability in Pharmacist-Vacant Clinics
* **The Clinical Bottleneck:** Resource-constrained rural clinics operate without on-site clinical pharmacists. Junior practitioners prescribing multi-drug therapies face significant risks of severe adverse drug events (ADEs) due to overlooked drug-drug interactions, cross-reactive allergies, and organ-clearance dosing limits (e.g., renal failure).
* **Need (Top Feature):** **Hybrid Adversarial Safety Critic** (Stage 6). Runs an independent LLM clinical-pharmacist critic and a Neo4j knowledge-graph plan-verifier in parallel (`asyncio.gather`), merges both flag streams **without dedup** so structural drug/condition violations surface even when no CPG paragraph explicitly mentions them, and blocks sign-off on any CRITICAL/MAJOR flag.

---

## Solution

We propose **ClearPath<span style="color:#0d9488">.</span>**, an AI-powered Clinical Practice Guidance System designed specifically for the **Remote Medicine Track**.

ClearPath acts as a clinician's second opinion, at the speed of a glance. By converting static, complex guidelines into an automated, moment-driven pipeline, it minimizes documentation time, safeguards patient care, and allows doctors to spend their precious hours **with patients, not paperwork**.

<p align="center">
  <img width="800" alt="From triage to care plan, in three steps" src="assets/triage_concept.png" />
</p>

---

## System Architecture

ClearPath is a **hybrid deterministic + agentic clinical pipeline**: every routing, retrieval, and safety decision that *can* be deterministic is deterministic; LLMs are reserved for clinical reasoning steps and are always grounded against retrieved CPG chunks and Neo4j knowledge-graph edges. All seven stages stream to clients via a single Server-Sent Events (SSE) channel with a shared `emit` contract, so the same backend serves both the React Doctor UI and the terminal `clinical_cli.py` driver identically.

```
                               ┌────────────────────────────────────────────────────────┐
                               │           Patient Intake & Vitals Ingestion            │
                               │  Vitals (Manual / rPPG), History, Chief Complaint,     │
                               │  Allergies, Current Meds, Staged Comorbidities,        │
                               │  Prior-Visit Summary (auto-loaded from last visit)     │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ PatientCase JSON  (+ derived BMI)
                                                           ▼
     [STAGE 2: DDX]            ┌────────────────────────────────────────────────────────┐
                               │     Symptom → ICD-11 DDx Extraction Pipeline           │
                               │  • Mode A vs Mode B detector (symptom- vs task-framed) │
                               │  • Symptom-phrase Extractor (seed-pinned, cached)      │
                               │  • Condition Hypothesis Generator                      │
                               │  • CC-boost (clinician-named dx → name→ICD resolver)   │
                               │  • Regex disease→ICD fallback (~60 aliases)            │
                               │  • Parallel pgvector search over 3,914 ICD-11 codes    │
                               │    (Bedrock Titan 1536-dim, ivfflat probes=100)        │
                               │  • LLM contextual reranker (thinking tokens)           │
                               │  • Sibling-cluster collapse (4-char stem dedup)        │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ Top-K Differentials (ranked, scored)
                                                           ▼
     [STAGE 3: ROUTE]          ┌────────────────────────────────────────────────────────┐
                               │   Deterministic CPG Scope Routing (D1 → D6 ladder)     │
                               │  D1 exact ICD → D2 sibling → ancestor_d1 → ancestor_d2 │
                               │  → semantic_scope (pgvector vs scope_embedding,        │
                               │    threshold 0.32, calibrated)  → out_of_scope         │
                               │  Sex-incompatibility filter (obstetric / women-only)   │
                               │  Staged-comorbidity short-circuit (0 ms vs ~4 s)       │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ Scoped CPG document set
                                                           ▼
     [STAGE 4: RETRIEVE]       ┌────────────────────────────────────────────────────────┐
                               │           Evidence-Graded Scoped Retrieval             │
                               │  • Targeted Query Generator (3–7 CPG queries)          │
                               │  • Scoped pgvector search (document_id_filter pinned)  │
                               │  • Hierarchical prefetch (H3 → H2 → H1 ancestors)     │
                               │  • Cross-reference resolver (inline §-anchors)         │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ High-fidelity Context Pack
                                                           ▼
     [STAGE 4.5: KG INJECT]    ┌────────────────────────────────────────────────────────┐
                               │     Pre-Synthesis Knowledge-Graph Lookup (Neo4j)       │
                               │  • clinical_graph_lookup — comorbidity-aware           │
                               │    Cypher: drug-class expansion + comorbidity aliasing │
                               │  • Graph Navigator PREFER arm (FIRST_LINE_FOR /        │
                               │    SECOND_LINE_FOR / RECOMMENDED_FOR)                  │
                               │  • Routed-chunk scope filter (no cross-CPG drift)      │
                               │  • Paediatric-source filter for adult plans            │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ ClinicalFlags + PREFER edges
                                                           ▼
     [STAGE 5: SYNTHESIZE]     ┌────────────────────────────────────────────────────────┐
                               │        Evidence-Guided 8-Section Care Plan             │
                               │  • TreatmentPlan synthesizer (Pydantic-validated)      │
                               │  • Recommendations tagged                              │
                               │    action ∈ {start, stop, change, continue,            │
                               │              contraindicated}                          │
                               │  • Stamped with MoH grading (ESC / USPSTF / SIGN50)    │
                               │  • Post-process: medication dedup (×2), referral       │
                               │    dedup, urgency↔severity harmonisation,              │
                               │    coverage-gap detector, specialist↔med cross-check,  │
                               │    STOP-with-switch splitter, assumption flagger,      │
                               │    gate-audit per-CPG cap                              │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ Drafted TreatmentPlan (JSON)
                                                           ▼
     [STAGE 6: CRITIC]         ┌────────────────────────────────────────────────────────┐
                               │       Hybrid Adversarial Safety Critic                 │
                               │  asyncio.gather(                                       │
                               │    _llm_critic(),        ← reasoning, allergy, DDI,   │
                               │                            renal/hepatic dosing        │
                               │    _kg_verify_plan(),    ← Neo4j Cypher: structural   │
                               │                            drug/condition violations   │
                               │  )                                                     │
                               │  Flags merged WITHOUT dedup (source ∈ {llm, graph})    │
                               │  safe_to_proceed = no CRITICAL/MAJOR across union      │
                               └───────────────────────────┬────────────────────────────┘
                                                           │ Audited TreatmentPlan + SafetyReport
                                                           ▼
                                ┌────────────────────────────────────────────────────────┐
                                │      Live Transparent Clinician UI (SSE stream)        │
                                │  Events: stage_start, ddx, routing, retrieval, plan,  │
                                │          safety_review, final_result, out_of_scope    │
                                │  Doctor UI (React) ▸ override → /clinical/resynth     │
                                │  Optional: Gmail PDF delivery (deterministic, no LLM) │
                                └────────────────────────────────────────────────────────┘
```

### Stage 2: Symptom-to-ICD-11 DDx Extraction (`agent/clinical_stages.py` + `ddx/search_ddx.py`)
* **Mode A vs Mode B detector.** Symptom-framed visits (Mode A) hit the LLM extractor; task-framed visits (Mode B — post-PCI, antenatal-booking, medication-review, follow-up) bypass the LLM via a deterministic `<procedure marker> for <canonical disease names>` template, eliminating Mode B's notorious cross-rerun jitter.
* **Four-layer determinism stack.** Seed-pinning (`DDX_DETERMINISTIC_SEED=42`) → regex disease→ICD fallback (~60 aliases like NSTEMI/STEMI/AF/T2DM/HFrEF augment but never replace LLM hints) → in-process phrase cache (sha1(model::notes)) → Mode-B rule-based bypass.
* **CC-boost.** `_extract_cc_icd_hints` lifts diagnoses the clinician wrote in CC/HPI/PE text, resolves names to codes via `search_ddx` top-1 (**never trusts LLM-emitted ICD codes** — they hallucinate digit-leading codes), and applies `CC_EXPLICIT_BOOST=0.25` (flat) or `CC_BOOST_WEIGHT=0.15 × confidence` (inferred).
* **LLM contextual reranker** with reasoning tokens, augmented by two prompt rules: **specificity preference** (BA41.1 NSTEMI over BA41 unspecified) and **distinct-disease preference** (collapse 4-char ICD stem clusters to one representative). A deterministic `_collapse_sibling_clusters` post-pass guarantees the rule survives noisy reranks.

### Stage 3: Deterministic Scoped Routing (`agent/routing.py`)
* **D1–D6 ladder.** D1 exact ICD match → D2 sibling → ancestor_d1 → ancestor_d2 → semantic_scope (pgvector against `documents.scope_embedding`, threshold `0.32` — calibrated against `scripts/calibrate_semantic_scope_threshold.py`) → out_of_scope.
* **Sex-incompatibility filter.** Male patients are routed away from Heart-Disease-in-Pregnancy, Diabetes-in-Pregnancy, Cervical-Cancer, CVD-Prevention-Women, Breast-Cancer; exclusions are logged in the trace.
* **D3 exclusion-penalty gate** prevents "other specified" exclusion chunks from self-penalising the correct subtype.
* **Staged-comorbidity short-circuit.** When the clinician already confirmed an ICD for a comorbidity in the intake UI, routing bypasses `search_ddx` entirely (0 ms vs ~4 s vector path). Free-text comorbidities fall through to the vector path with a 0.55 similarity floor and a 4-item merged cap to prevent bare-noun drift (e.g., Depression → Cancer-Pain).

### Stage 4: Scoped Evidence Retrieval (`agent/clinical_stages.stage_4_retrieve`)
* **Targeted query generator** drafts 3–7 domain-specific queries scoped to each routed CPG.
* **Scoped pgvector search** strictly pinned by `document_id_filter` to active CPGs — prevents cross-guideline contamination.
* **Hierarchical content prefetcher** pulls grandparent headers (H3 → H2 → H1) so local abbreviations, levels of evidence, and Malaysian-context callouts ride along with every leaf chunk.
* **Cross-reference resolver** scans hits for inline `§X.Y` anchors to other CPGs and appends the resolved chunks to the evidence pack.

### Stage 4.5: Pre-Synthesis Knowledge-Graph Lookup (`agent/graph_clinical.py` + `agent/graph_navigator.py`)
* **`clinical_graph_lookup`** — candidate-driven from retrieved chunks; emits ClinicalFlags for `(:Drug)-[:CONTRAINDICATED_WITH]->(:Condition)` and `(:Condition)-[:REQUIRES_MONITORING]->(:Parameter)` triples.
* **Drug-class expansion** — both `candidate_drugs` (from chunks) AND `patient_meds` (current regimen — MUST be included, otherwise existing-med teratogen risks silently miss safety review) expand to KG class names so class-level edges like `(ARB)-[:CONTRAINDICATED_WITH]->(Pregnancy)` actually fire.
* **Comorbidity-string aliasing** — raw comorbidity strings like `"Pregnancy 30 weeks (primigravida)"` are expanded to canonical KG forms (`pregnancy`) so set-membership Cypher matches.
* **Graph Navigator PREFER arm** walks `FIRST_LINE_FOR | SECOND_LINE_FOR | RECOMMENDED_FOR` edges keyed by DDx titles + comorbidities; results are merged into the same Stage 5 evidence block so synthesis sees "prefer Y" and "avoid X" together.
* **Routed-chunk scope filter** keeps only edges whose `cpg_chunk_id` belongs to a routed CPG — symmetric across PREFER and referral lookups; eliminates cross-CPG drift.
* **Paediatric-source filter** drops paediatric flags when `patient_age ≥ 18`.

### Stage 5: 8-Section Executable Care Plan Synthesis (`agent/clinical_stages.stage_5_synthesize`)
* **TreatmentPlan synthesizer** assembles patient data, retrieved CPG evidence, prior-visit summary, and KG edges into a Pydantic-validated `TreatmentPlan` structured to render as an **8-section executable plan**:

  | # | Section | Source field |
  |---|---|---|
  | P1 | Clinical Summary | `TreatmentPlan.summary` |
  | P2 | Medications | `recommendations` with `action ∈ {start, stop, change, continue, contraindicated}` |
  | P3 | Procedures & Investigations | `recommendations` (investigation type) |
  | P4 | Monitoring | `monitoring` (time-anchored schedules) |
  | P5 | Lifestyle | `recommendations` (lifestyle type) |
  | P6 | Referrals | `recommendations` (referral type, with urgency) |
  | P7 | Safety Netting / Red Flags | monitoring trip-wires + `SafetyReport` |
  | P8 | Follow-up Plan | `follow_up` |

* **Recommendations stamped** with the *original* Malaysian MoH grading scheme — three incompatible schemes co-exist in the corpus (ESC, USPSTF, SIGN50) and are **never normalised across schemes**.
* **Post-synthesis validator chain (8 layers):** medication dedup (post-LLM then post-KG, 2-tier exact + ≥85% substring), referral dedup with urgency prioritisation (emergency > urgent > routine, token-set Jaccard ≥0.6 with specialty gate), urgency↔severity harmonisation with auto-upgrade, coverage-gap detector (1st-line therapy missing per condition — never fabricates a prescription, only surfaces unresolved), specialist↔medication cross-check (primary-clause trimmed + continuing-token suppressed + pregnancy-context obstetric acceptance), STOP-with-switch splitter (rescues paired START rec from collapsed swap prose), assumption flagger (load-bearing clinical assumptions surfaced for clinician verification), gate-audit per-CPG cap.

### Stage 6: Hybrid Adversarial Safety Critic (`agent/safety_critic.run_safety_critic`)
* **Two graders in parallel** (`asyncio.gather`), flags **merged without dedup**:
  * **LLM clinical-pharmacist critic** — Generator → Evaluator pattern, blind to Stage 5's reasoning chain, audits for:
    1. *Drug allergies* (including complex sulfonamide class cross-reactivity).
    2. *Drug-drug interactions* (e.g., Warfarin + new NSAID bleeding risk).
    3. *Dosing in organ impairment* (e.g., Metformin in Stage 4 CKD).
    4. *Absolute contraindications* (e.g., non-selective beta-blockers in severe asthma).
  * **Neo4j KG plan-verifier** — `_kg_verify_plan` runs structural Cypher against the *final* TreatmentPlan recommendations; catches violations no CPG paragraph happens to mention. `_kg_flag_to_safety` maps KG drug nodes back to recommendation indices via `match_plan_drugs` (Cypher CONTAINS on normalised name).
* **`safe_to_proceed`** is recomputed across the merged union — any `CRITICAL` or `MAJOR` flag blocks sign-off.
* **Both critics fail open** (empty flag list on error); the surface a clinician sees in a pharmacist-vacant clinic must never hide concerns due to infrastructure flakiness.

### Cross-Cutting: Pre-Consultation Prep, Continuity, Delivery, Resilience
* **Pre-consultation prep brief agent** (`generate_prep_brief` → `POST /clinical/prep-brief`) — fires *before* Stage 2 for returning patients only. Consumes the auto-loaded `PriorVisitSummary` + current medications + patient demographics and emits a strict 3-field JSON (`since_last_visit`, `med_flags`, `ask_today`), each capped at 120 chars in telegram-style clinical shorthand. Gives the clinician a 30-second orientation (what changed, what to watch, what to verify) before the consultation even starts — closes the loop with the prior-visit summariser below.
* **Prior-visit summary loop** — at `finalizePlan` (clinician sign-off only — never on every save), the UI calls `POST /clinical/summarise-prior` to generate a lean 5-field `PriorVisitSummary` (visit_date, prior_icd_primary, prior_plan_summary, key_labs_delta, what_changed) with hard character caps + server truncation belt-and-braces. Persisted via `update_prior_visit_summary_bypass`, auto-loaded next visit via `get_latest_prior_visit_summary` and rendered into Stage 4 query-gen and Stage 5 synthesis user content.
* **Deterministic Gmail care-plan delivery** — `agent/delivery.py` + background `delivery_worker.py` poll a `delivery_jobs` table every 5 s, consent-check, fetch the PDF from Supabase storage, validate the subject against a PHI-token blocklist, and SMTP-send via Gmail App Password. No LLM in the loop. Three-attempt cap.
* **Offline resilience (5 layers).** Rotating SSE event log (10 MB × 5), append-only `failed_jobs.jsonl` with `scripts/replay_failed_jobs.py`, `X-Request-ID` correlation across every log line and Supabase row, per-stage `pipeline_timings` JSONB persisted post-`final_result`, and an LLM health probe on `/health` that pings synthesis and safety endpoints with a 2 s timeout.

---

## Implementation

ClearPath represents a complete clinical end-product, designed for visual tablet/desktop dashboards at rural clinics or standalone terminal deployments. The React Doctor UI and the terminal `clinical_cli.py` share an identical SSE contract — every event (`stage_start`, `ddx`, `routing`, `retrieval`, `plan`, `safety_review`, `final_result`, `out_of_scope`) renders in both surfaces:

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
        <li><strong>Patient Queue Pulse:</strong> Prioritises clinical triage by surfacing critical cases and overdue follow-ups dynamically.</li>
        <li><strong>Workflow Analytics:</strong> Real DB-backed tiles (measured Time Saved = Σ <code>clamp(20-min manual baseline − actual plan wall-time, 0, 20)</code> over completed plans, CPG Align %, Citations, Safety Intercepts — no static mocks) refresh on Supabase realtime <code>postgres_changes</code> events.</li>
        <li><strong>4-Step Consultation Wizard:</strong> Input → Diagnosis → CarePlan → Output, with SSE-streamed pipeline trace and one-click clinician override that re-fires Stage 5 synthesis.</li>
        <li><strong>8-Section Plan Renderer:</strong> Action-tagged medication chips, monitoring trip-wires, urgency-coloured referrals, and a one-click PDF export → Gmail delivery handoff.</li>
      </ul>
      <p align="center">
        <a href="frontend/doctor-ui/">Explore Frontend Workspace →</a>
      </p>
    </td>
    <td align="left" valign="top" style="padding: 10px;">
      <ul>
        <li><strong>Intake Console:</strong> Guides clinicians through structured intake parsing (vitals, current medications, allergies, history, staged comorbidities).</li>
        <li><strong>Scope Verification:</strong> Enforces deterministic D1–D6 mapping of primary ICD-11 codes to verified MOH guidelines on the backend.</li>
        <li><strong>Override Harness:</strong> Prompts clinicians to accept AI suggestions or input custom codes, executing real-time re-synthesis via the same SSE contract.</li>
      </ul>
      <p align="center">
        <a href="backend/clinical_cli.py">View clinical_cli.py Code →</a>
      </p>
    </td>
  </tr>
</table>

---

## Decision & Reasoning Matrix

The table below illustrates how a single remote consultation is processed step-by-step through the ClearPath clinical decision engine. The worked example is a real pregnancy + chronic HTN + GDM case used in our reproducibility harness (`scripts/run_eval_case_10.py`):

| Stage | Input Signals / State | AI & Engine Action | Output Artifact / Decision | Reasoning & Grounding |
|---|---|---|---|---|
| **Stage 1: Intake** | 35 F primigravida @ 30 wks • essential HTN on Losartan 50 mg OD • BP 158/104 ×2 • fasting glucose 7.4 / OGTT-2h 11.2 mmol/L • family hx peripartum cardiomyopathy | Parses notes into structured `PatientCase`; derives BMI; auto-loads prior-visit summary if present. | `PatientCase` JSON (Pydantic) | Organises raw clinical signals; ensures BMI-threshold referral triggers have a value to compare against. |
| **Stage 2: DDx** | PatientCase + Mode-A detector (symptom-framed) | Symptom-phrase extractor (seed-pinned, cached) + hypothesis generator + CC-boost name→ICD resolver + regex disease alias scan + parallel pgvector search (3,914 codes, ivfflat probes=100) + LLM contextual rerank + sibling-cluster collapse. | Top-5 DDx incl. JA20.Y (pre-existing HTN in pregnancy) and JA63.Y (diabetes in pregnancy). | Distinct-disease preference rule prevents BA41/BA42 sibling crowding; CC-boost surfaces dx the clinician already wrote. |
| **Stage 3: Routing** | Top DDx + sex='F' + staged comorbidities | D1 exact match → routes to *Hypertension (5th Ed)*, *Diabetes-in-Pregnancy (2017)*, *Heart-Disease-in-Pregnancy (2nd Ed)*; sex filter keeps obstetric CPGs in scope. | 5 scoped CPG documents | Deterministic; staged-comorbidity short-circuit skips ~4 s vector path for already-confirmed ICDs. |
| **Stage 4: Retrieval** | Scoped CPGs + PatientCase + prior-visit summary | 5 targeted queries → scoped pgvector → H3→H2→H1 prefetch → cross-reference resolver. | Evidence pack with §14.2 (HTN-in-Pregnancy), Table 7.6-A (anti-HTN dose ladder), §5.3 (GDM metformin), §5.5 (low-dose aspirin). | `document_id_filter` pinning prevents the AF CPG's secondary-prevention section leaking in. |
| **Stage 4.5: KG inject** | Retrieved chunks + `patient_meds=[Losartan]` + comorbidities | `_query_comorbidity_flags` expands Losartan → {ARB, Angiotensin Receptor Blocker}; expands "Pregnancy 30 weeks (primigravida)" → {pregnancy}; runs Cypher. | ClinicalFlags: `(ARB)-[:CONTRAINDICATED_WITH]->(Pregnancy)`, `(Arb)-[:CONTRAINDICATED_WITH]->(Pregnancy)` | Drug-class + comorbidity aliasing is what makes a class-level KG edge visible against a free-text comorbidity. |
| **Stage 5: Synthesis** | Retrieved chunks + KG edges + prior-visit | LLM synthesis → 8-section plan → 8-layer validator chain → STOP-with-switch splitter pairs `[STOP] Losartan` with `[START] Methyldopa`. | TreatmentPlan: STOP Losartan • START Methyldopa 250 mg TDS [Grade C] • START Labetalol alt • START Metformin 500 mg [§5.3] • START low-dose aspirin [Grade I/A] • obstetrician referral + monitoring + follow-up. | Recommendations stamped with original MoH grading scheme; never cross-normalised. |
| **Stage 6: Critic** | PatientCase + drafted TreatmentPlan | `asyncio.gather`(LLM critic, KG verify); merge without dedup. | SafetyReport: **3 flags** — [CRITICAL/llm] Losartan teratogen, [MAJOR/graph] ARB×Pregnancy, [MAJOR/graph] Arb×Pregnancy. `safe_to_proceed=False`. | LLM catches narrative reasoning; KG catches the structural edge even when the same paragraph wasn't in the LLM's window. Both fire here — the merged view is what the clinician sees. |

---

## Validation & Measured Results

These are **measured pilot results**, not aspirational targets. Evaluation runs over a corpus of **30 Malaysian MoH CPGs** whose ICD-11 routing relationships and per-layer gold sets were curated and clinically validated by expert clinicians. Evidence sources are the CPG corpus + Neo4j knowledge graph only — there is **no UpToDate or AHA/ESC integration**. Numbers below are reproducible via the backend eval harness (`backend/eval/run_*.py`) and the end-to-end case runners (`backend/scripts/run_eval_case_08…12.py`).

### Results against targets

| Layer | Metric | Target | Achieved | Verdict |
|---|---|---|---|---|
| **A1 — DDx** | Hit@5 / MRR | ≥0.90 / ≥0.70 | **0.971 / 0.810** | ✅ Pass |
| **A2 — Routing** | Top-1 | ≥0.85 | **1.000** (44/44) | ✅ Pass |
| **B — Retrieval** | Recall@10 / Hit@10 | ≥0.85 / ≥0.95 | **0.874 / 0.953** | ✅ Pass |
| **B — Retrieval** | nDCG@10 / MRR | ≥0.75 / ≥0.70 | 0.669 / 0.682 | ⚠️ Short (diagnosed) |
| **B — Retrieval** | Precision@5 | ≥0.50 | 0.251 | ⚠️ Short (graded gold dilutes) |
| **C — Re-ranker** | nDCG@10 lift | >0 | **+6.0%** | ✅ Directional |
| **D — Faithfulness** | Mean per-claim grounded | ≥0.90 | 0.864 (849/979 claims) | ⚠️ Short (diagnosed) |
| **Scope refusal** | Orphan refusal | 100% | **11/11** | ✅ Pass |
| **SAF — Safety critic** | Sensitivity / Specificity | >90% / 100% | **92% / 100%** | ✅ Pass |
| **ADV/INJ/LNG** | Adversarial + injection + multilingual | ≥85% | **14/14** | ✅ Pass |
| **SIL/INF** | Fail-loud on silent degradation + infra outage | 6/6 | **6/6** | ✅ Pass |
| **Determinism** | Top-1 stability (dominant dx) | Stable | **10/10** (cases 8, 9) | ✅ Pass |
| **Latency** | End-to-end | <5 min budget | **~2.1 min** (pilot) | ✅ Pass |
| **Coverage** | In-scope backend lines | ≥60% | **64.93%** (355 tests, 174 s) | ✅ Pass |

Read honestly: routing, retrieval recall, scope refusal, safety-critic recall, robustness, determinism, and latency all meet target; DDx meets target on the clinically meaningful lineage metric; **faithfulness and retrieval-ranking fall a measured, stated distance below target** — reported rather than hidden.

### End-to-end latency (pilot, 3 cases)

Measured across HFrEF+T2DM+Obesity (62 M), Pregnancy-HTN+GDM (35 F), and Stable-CAD+ED-on-nitrate (56 M): **mean 127 s · p50 115 s · p95 157 s** — inside the 10-minute consultation window. The two LLM-heavy stages dominate: **Stage 5 synthesis ≈ 43%** and **Stage 4 retrieval ≈ 31%** of wall-time; the two deterministic stages (Stage 3 routing + Stage 4.5 KG lookup) together consume **<1%**, confirming the graph and routing layers add negligible overhead. Stage 5 is the single highest-leverage optimisation target.

### Blinded clinician evaluation

Five practising doctors scored ClearPath against **Qmed AskCPG** and **Gemini NotebookLM** in blinded, randomised order across three cases (8, 10, 11), on a 1–5 scale over 8 clinical-quality aspects + a 6-aspect workflow/UI rubric:

* **ClearPath led every clinical-quality dimension.** Safety **4.93/5** (highest of any aspect), Guideline Fidelity **4.85**, Reasoning Transparency **4.82**. Widest margin was **Uncertainty Handling** (+0.80 over Qmed AskCPG, +0.69 over NotebookLM) — its structured referral injection + explicit unresolved-question surfacing. All three systems reliably caught both Losartan-in-pregnancy and the PDE5i×nitrate contraindication.
* **Workflow:** Reasoning visibility **5/5** and override/feedback **5/5** (ceiling) validated the transparency-and-control thesis; safety surfacing **4/5**. Workflow fit and time-to-answer scored **3+/5** — evaluators judged the default output too verbose and synthesis too slow for live in-consult use, recommending **post-consultation review / teaching** as the near-term deployment context. This aligns with the Stage 5 latency finding above; **UI condensation + response streaming** are the primary improvement levers.

> **Caveat on scope.** These are pilot-scale results (3 end-to-end cases, 5 evaluators). The p95 and clinician scores stabilise only with the planned wider run. They supersede the *aspirational* placeholder figures (87% accuracy, 6.2 CoT depth, 4.3/5 confidence) that still appear in `EVALUATION_FRAMEWORK_README.md` — do not cite those as results.

---
