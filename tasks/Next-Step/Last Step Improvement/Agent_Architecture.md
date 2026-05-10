# Agent Architecture — Extending the CPG LLM Pipeline

> This document covers architectural additions to the pipeline — new specialised agents
> that run alongside or after the core Stage 2–5 sequential workflow.
>
> **Distinction from Gaps_Closing.md:** The gaps document fixes deficiencies in the
> existing pipeline. This document adds new capabilities on top of a working pipeline.
> Do not start here until Gaps 1–3 in Gaps_Closing.md are closed.

---

## Design principle — why we keep agents minimal

CPG LLM is a **clinical evidence grounding system**, not a general-purpose agent. In a
clinical decision-support tool, more autonomous agents chatting with each other introduces:

- **Compounding hallucination risk** — each agent-to-agent handoff is an opportunity
  to drift further from the grounded CPG evidence
- **Unpredictable reasoning chains** — audit trails become hard to follow; clinicians
  cannot understand *why* a recommendation was made
- **Latency** — a doctor mid-consultation cannot wait 40s for 5 sequential LLM calls

The current architecture is the correct pattern for this domain: a **sequential pipeline**
(`clinical_stages.py`) controlled by one capable LLM, with structured typed outputs at
each stage. Every stage is independently auditable.

The additions below do **not** break this principle. They are:
- Narrow in scope (single responsibility)
- Run in parallel with or after the core pipeline (not injected into stages 2–5)
- Deterministic or near-deterministic where possible (rule-based > LLM-based)

---

## Agent 1 — Clinical Safety Critic

**Priority: HIGH** | **Pattern: Generator → Evaluator**
**Relationship to Gaps_Closing.md:** This extends Gap 2 (drug interaction lookup).
Gap 2 injects interaction flags *into* Stage 5 as a pre-screen.
This agent runs *after* Stage 5 as an independent second opinion — they are complementary, not alternatives.

### What it does

Takes the generated `TreatmentPlan` and the `PatientCase` and plays Devil's Advocate:
it has no knowledge of what Stage 5 decided, and independently checks whether the
recommendations are safe for this specific patient.

```
Stage 5 → TreatmentPlan
                │
                ▼
        Safety Critic Agent
        ┌─────────────────────────────────────────────┐
        │ Input: TreatmentPlan + PatientCase          │
        │                                             │
        │ Checks:                                     │
        │   • Each recommended drug vs. allergies     │
        │   • Each recommended drug vs. current meds  │
        │   • Dosing vs. renal/hepatic function       │
        │   • Red flag conditions vs. comorbidities   │
        │                                             │
        │ Output: SafetyReport                        │
        │   • flags: list[SafetyFlag]                 │
        │   • safe_to_proceed: bool                   │
        │   • modified_recommendations: list | None   │
        └─────────────────────────────────────────────┘
                │
                ▼
        Doctor UI shows SafetyReport alongside TreatmentPlan
```

### Why this matters in clinical AI

The **Generator-Evaluator pattern** is the industry standard for reducing hallucination
in medical AI. A single LLM generating and self-checking is less reliable than two
separate LLMs — the first generates, the second critiques without seeing the reasoning
chain of the first.

In practice: Stage 5 may recommend metoprolol for a patient whose current medications
include verapamil. Both are AV-nodal agents. The Stage 5 LLM may not flag this because
it is focused on producing a coherent treatment plan from CPG evidence. The Safety Critic
has one job: find reasons the plan could harm this patient.

### Implementation

**New file: `agent/safety_critic.py`**

```python
from pydantic import BaseModel
from .models import PatientCase, TreatmentPlan

class SafetyFlag(BaseModel):
    severity: str                   # "CRITICAL" | "MAJOR" | "MODERATE"
    recommendation_index: int       # which recommendation triggered the flag
    flag_type: str                  # "drug_allergy" | "drug_interaction" | "dose" | "contraindication"
    detail: str
    suggested_alternative: str | None = None

class SafetyReport(BaseModel):
    flags: list[SafetyFlag] = []
    safe_to_proceed: bool
    reviewer_notes: str | None = None

async def run_safety_critic(
    case: PatientCase,
    plan: TreatmentPlan,
    emit=None,
) -> SafetyReport:
    """
    Secondary LLM pass: checks TreatmentPlan against PatientCase for
    safety flags. Uses a lean model (Flash) — this is a verification
    pass, not a reasoning pass.
    """
```

**System prompt (safety critic — adversarial framing):**

```
You are a clinical pharmacist performing a medication safety review.
You have NOT seen the reasoning that produced this treatment plan.
Your ONLY job is to find reasons it could harm this specific patient.

For each recommended pharmacological intervention, check:
1. Does it conflict with any listed allergy (including cross-reactivities)?
2. Does it interact dangerously with any current medication?
3. Is the implicit dose appropriate for renal/hepatic function implied by the comorbidities and vitals?
4. Is it contraindicated given any listed comorbidity?

Flag EVERY concern you find. Do not suppress concerns because the plan "looks reasonable overall".
If you find no concerns, return an empty flags array — do not invent concerns.

Return a SafetyReport JSON object. No markdown fences.
```

**In `clinical_workflow.py`:** Run Safety Critic in parallel with final stage:

```python
import asyncio

plan, safety = await asyncio.gather(
    stage_5_synthesize(case, ddx, cpgs, evidence),
    asyncio.sleep(0),   # placeholder — critic needs plan first
)
safety = await run_safety_critic(case, plan, emit=emit)
```

Since the critic needs the plan output, run it immediately after Stage 5 finishes —
target latency <5s with a Flash-class model.

**Frontend:** Show `SafetyReport` as a banner above the care plan:
- 0 flags → green "Safety review passed" chip
- MODERATE flags → amber expandable banner
- MAJOR/CRITICAL flags → red banner that blocks "Approve" button until acknowledged

**Files:** `agent/safety_critic.py`, `agent/models.py` (SafetyFlag + SafetyReport),
`agent/clinical_workflow.py`, `Doctor UI/src/components/sections/CarePlanSection.jsx`
**Effort:** ~4 h
**Test:** Fixture: patient on verapamil, plan recommends metoprolol →
assert `SafetyReport.flags` contains at least one MAJOR flag.

---

## Agent 2 — Graph Navigator (Multi-Morbidity Reasoner)

**Priority: MEDIUM** | **Pattern: Symbolic + Neural hybrid**

### What it does

The Neo4j knowledge graph is currently used as a basic search tool
(`graph_search` in `agent/tools.py`). This agent specialises in
**graph traversal for multi-morbidity patients** — walking entity
relationships to derive hard logical rules that vector search cannot.

```
Patient: DM + CKD Stage 3 + Hypertension
         │
         ▼
  Graph Navigator
  ┌─────────────────────────────────────────────────┐
  │ Walk: CKD Stage 3 → eGFR ~45                   │
  │   → CONTRAINDICATED: Metformin (eGFR < 30 ok,  │
  │                       but hold if AKI risk)     │
  │   → DOSE_REDUCE: SGLT2i (limited efficacy)      │
  │   → AVOID: NSAIDs (nephrotoxic)                 │
  │                                                  │
  │ Walk: DM + HTN → preferred agents               │
  │   → PREFER: ACE inhibitor (renoprotective)      │
  │   → PREFER: SGLT2i (CV + renal benefit)         │
  │                                                  │
  │ Cross-check: ACE inhibitor + CKD → monitor K+   │
  └─────────────────────────────────────────────────┘
         │
         ▼
  GraphConstraints injected into Stage 5 evidence block
```

### Why vector search alone is insufficient for multi-morbidity

Vector search finds semantically similar text. The query
*"diabetes treatment CKD"* finds chunks about diabetes in CKD patients.
But it does not traverse the logical chain:

> CKD Stage 3b (eGFR 32) → metformin should be held if eGFR <30
> AND patient is having a procedure with iodinated contrast
> → HOLD metformin 48h before procedure

This is a **graph traversal problem**, not a semantic similarity problem.
The graph already has entity relationships (drugs → conditions → contraindications)
from the ingestion pipeline. The Graph Navigator makes them queryable per patient.

### Why this approach avoids hallucination

Graph traversal returns **deterministic facts from structured data**, not LLM
generation. The Navigator does not synthesise — it looks up. The LLM in Stage 5
can then cite these constraints as hard rules:

```
[GRAPH RULE] Metformin: hold if eGFR <30 or contrast procedure planned.
Patient eGFR: 32 (borderline). Flag for monitoring.
```

This is categorically more reliable than asking the synthesis LLM to recall
metformin contraindications from training data.

### Implementation

**New file: `agent/graph_navigator.py`**

```python
async def get_graph_constraints(
    case: PatientCase,
    ddx: list[DDxResult],
) -> str:
    """
    Traverse Neo4j for drug constraints specific to this patient's
    comorbidity + medication profile. Returns formatted constraint text
    for injection into Stage 5 evidence.
    """
    constraints = []

    # Query pattern: comorbidity → contraindicated drugs
    # Query pattern: current medication → interactions with CPG drug classes
    # Query pattern: ICD code → monitoring requirements

    return "\n".join(constraints)
```

**In `stage_5_synthesize`:** Prepend graph constraints to evidence block:

```python
graph_constraints = await get_graph_constraints(case, ddx)
if graph_constraints:
    evidence_text = f"GRAPH-DERIVED CONSTRAINTS (hard rules):\n{graph_constraints}\n\n{evidence_text}"
```

**Neo4j schema additions needed:**
- `(:Drug)-[:CONTRAINDICATED_IN {egfr_threshold: 30}]->(:Condition {name: "CKD"})`
- `(:Drug)-[:INTERACTS_WITH {severity: "MAJOR"}]->(:Drug)`
- `(:Condition)-[:REQUIRES_MONITORING]->(:Parameter {name: "K+", frequency: "weekly"})`

**Files:** `agent/graph_navigator.py`, `agent/clinical_stages.py` (`stage_5_synthesize`),
Neo4j schema population scripts
**Effort:** ~6 h (Neo4j schema population is the bulk of the work)
**Dependencies:** Requires Gap 1 (comorbidity routing) to be closed first so comorbidity
entities are consistently structured in the pipeline.

---

## Agent 3 — Medical Scribe

**Priority: LOW (post-pilot)** | **Pattern: Document generator**

### What it does

Once the doctor approves the care plan, this agent takes the approved
`TreatmentPlan` + `PatientCase` + confirmed diagnoses and drafts a
structured clinical note in standard SOAP format, ready for EMR export.

```
Doctor clicks "Sign & Close"
         │
         ▼
  Medical Scribe Agent
  ┌─────────────────────────────────────────┐
  │ Input:                                  │
  │   • PatientCase (S + O)                 │
  │   • Confirmed ICD-11 diagnoses (A)      │
  │   • Approved TreatmentPlan (P)          │
  │   • Doctor name + timestamp             │
  │                                         │
  │ Output: ClinicalNote                    │
  │   • soap_note: str (formatted)          │
  │   • icd_codes: list[str]               │
  │   • prescriptions: list[Prescription]  │
  │   • follow_up_date: date               │
  │   • export_formats: ["PDF", "HL7 FHIR"]│
  └─────────────────────────────────────────┘
```

### Why it closes the loop

CPG LLM currently does the hard work — finding evidence, generating recommendations,
checking safety — but the output is a structured JSON object. The doctor still has to
manually transcribe the approved plan into their EMR.

The Medical Scribe eliminates this step. It is the **lowest hallucination risk** of the
three agents because:
- It transforms structured data (TreatmentPlan JSON) into formatted text
- It does not retrieve, reason, or synthesise new clinical content
- The doctor approved the source data — the scribe only formats it

### SOAP mapping

| SOAP section | Source data |
|---|---|
| **S** — Subjective | `PatientCase.chief_complaint` + `PatientCase.history` |
| **O** — Objective | `PatientCase.vitals` (formatted) + `PatientCase.age`/`sex` |
| **A** — Assessment | Confirmed ICD-11 codes + titles + `TreatmentPlan.confidence` |
| **P** — Plan | `TreatmentPlan.recommendations` (accepted only) + `monitoring` + `red_flags` |

### HL7 FHIR export (future)

The `ClinicalNote` output maps cleanly to FHIR R4 resources:
- `Patient` resource from `PatientCase`
- `Condition` resources from confirmed ICD-11 codes
- `MedicationRequest` resources from pharmacological recommendations
- `CarePlan` resource from the full plan

This is the path to integration with MySejahtera, iHIS, or any FHIR-compliant EMR.

### Implementation

**New file: `agent/medical_scribe.py`**

```python
class ClinicalNote(BaseModel):
    soap_note: str
    icd_codes: list[str]
    encounter_date: str
    clinician_name: str
    follow_up_date: str | None = None
    export_ready: bool = False

async def run_medical_scribe(
    case: PatientCase,
    plan: TreatmentPlan,
    confirmed_diagnoses: list[str],      # ICD codes confirmed by clinician
    clinician_name: str,
) -> ClinicalNote:
```

**Frontend:** `OutputSection.jsx` calls scribe on "Sign & Close"; renders SOAP note in
the document view (already designed in `design_reconstruction.md`). Adds PDF export
and FHIR bundle download buttons.

**Files:** `agent/medical_scribe.py`, `agent/models.py` (ClinicalNote),
`agent/api.py` (POST /clinical/note/generate),
`Doctor UI/src/components/sections/OutputSection.jsx`
**Effort:** ~3 h
**Dependencies:** Step 4 SOAP view in `design_reconstruction.md` should be built first.

---

## Build order

Do not build agents until the core gaps are closed. Agents improve a working pipeline —
they do not fix a broken one.

```
Gaps_Closing.md (Gaps 1–3)       ← must close first
        │
        ▼
Agent 1 — Safety Critic           ← build next; highest safety impact
        │
        ▼
Gap 4 (severity staging)          ← enables Agent 2 to be useful
        │
        ▼
Agent 2 — Graph Navigator         ← requires structured comorbidity data
        │
        ▼
design_reconstruction.md Step 4   ← SOAP view prerequisite
        │
        ▼
Agent 3 — Medical Scribe          ← closes the clinical loop; build last
```

---

## Summary

| Agent | When to build | Effort | Patient safety impact |
|---|---|---|---|
| Safety Critic | After Gaps 1–3 closed | ~4 h | 🔴 Critical |
| Graph Navigator | After Gap 4 + Agent 1 | ~6 h | 🟠 High |
| Medical Scribe | Post-pilot | ~3 h | 🟡 Low (workflow, not safety) |

**If only one agent gets built:** build the Safety Critic. A second LLM independently
verifying the output of the first is the single most impactful safety improvement
available for a clinical AI system.
