# Implementation Plan — Clinician AI Chatbox ("Why did you prescribe this?")

**Status:** Proposed
**Author:** Chua Zhu Heng
**Date:** 2026-06-13

## 1. Goal

Add a docked chat panel on the care-plan view where a clinician can ask *why* a
recommendation was made, request more detail, and probe uncertainty. Every answer
must be grounded in the plan's own citations plus the CPG / knowledge-graph corpus,
and must **refuse and escalate** when it cannot cite a source — never inventing a
clinical rationale.

### Motivation
After a care plan is generated, if the doctor is uncertain about a recommendation
("why this drug?", "what's the evidence?", "what about this comorbidity?") there is
currently nowhere to ask. This feature turns the static plan into something the
clinician can interrogate, with citations.

## 2. Locked-in design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Plan access | By `consultation_id` (load saved plan from Supabase) | Ties chat to a real persisted plan; cleanest payload |
| Answer scope | This plan + full CPG corpus + patient context | Most useful; grounding still enforced |
| Uncertainty behavior | Refuse + escalate | Safest for a clinical decision tool |
| Persistence | Ephemeral (no audit table) | No schema change for v1 |

## 3. Why this is a small feature, not a new system

The hard parts already exist and are reused as-is:

- **`rag_agent`** (`backend/agent/agent.py:51`) — a tool-using agent with vector,
  graph, drug-info, and algorithm-pathway tools already registered.
- **`/chat/stream`** (`backend/agent/api.py:1141`) — a streaming SSE chat endpoint,
  including a Bedrock non-streaming fallback (`api.py:1186`).
- **Per-recommendation provenance** — each `Recommendation` (`backend/agent/models.py:348`)
  already carries `cpg_source`, `rationale`, `evidence_grade`, and
  `contraindications_checked`. This is the grounding material.
- **Consultation load pattern** — `db_pool.acquire()` + `conn.fetchrow(SELECT ... FROM consultations)`
  as used in `backend/agent/delivery.py:181`.

The only new ingredients are: (1) loading the saved plan as grounding context, and
(2) a clinical-explainer system prompt enforcing refuse-and-escalate.

**No DB migration. No new agent. No change to the care-plan generation pipeline.**

## 4. Backend changes

### 4.1 New endpoint `POST /clinical/explain/stream` (`backend/agent/api.py`)

Request body:
```json
{
  "message": "Why did you prescribe sildenafil?",
  "consultation_id": 123,
  "session_id": null,
  "recommendation_index": 2
}
```
- `recommendation_index` (optional) lets the UI say "the Dr clicked rec #2 then asked why."

Behavior:
1. Load the saved plan by id using the established `db_pool.acquire()` + `fetchrow`
   pattern (mirror `delivery.py:181`). Select
   `care_plan_summary, medication_recommendations, interventions, monitoring,
   referrals, lifestyle_goals, cpg_references` from `consultations`.
2. Build a **grounding block** from that row: recommendations with their
   `cpg_source` / `rationale` / `evidence_grade`, plus patient context, formatted as
   a system-context preamble.
3. Run the existing `rag_agent` with the explainer system prompt + grounding block +
   the doctor's question, reusing the **exact SSE streaming machinery** from
   `/chat/stream` (including the Bedrock non-streaming fallback).
4. Ephemeral: do **not** call `add_message` / save turns to Supabase.

### 4.2 New explainer system prompt — `backend/agent/prompts/explain_careplan.txt`

- **Role:** explain *this* care plan to the prescribing clinician.
- **Hard rules:**
  - Answer only from (a) the plan's own rationale/citations in the grounding block,
    or (b) CPG/KG evidence freshly retrieved via tools.
  - If neither grounds the answer → refuse + escalate:
    *"That isn't something I can cite from the guidelines for this plan — I'd suggest
    [specialist referral / primary CPG]."*
  - Always cite the CPG section when making a clinical claim.
  - Never invent a rationale that contradicts the stored one.

### 4.3 Grounding-context formatter

A small helper (in `api.py` or a new `backend/agent/explain.py`) that turns the
consultation row JSONB into the preamble string. Reuses the `Recommendation` /
`TreatmentPlan` field names from `models.py:348`.

## 5. Frontend changes (`frontend/doctor-ui`)

### 5.1 `CarePlanChat` panel component
Docked to the care-plan view, next to `FinalCarePlan` / `CarePlanSection`.
- Reuses the existing SSE-consuming chat pattern.
- "Ask why" affordance per recommendation: clicking a rec opens the panel pre-seeded
  with `recommendation_index` and a starter question.
- Renders streamed tokens + a `sources` footer (the SSE `sources` event the endpoint
  emits) so citations are visible.

### 5.2 API client method (`frontend/doctor-ui/src/lib/clinicalApi.js`)
`explainCarePlan({ message, consultationId, recommendationIndex })` — hits the new
endpoint and yields SSE deltas, mirroring existing stream consumers. (Note:
`clinicalApi.js` already passes `consultation_id` in its request bodies.)

## 6. Testing

- **Backend:** test that the endpoint refuses + escalates on an ungrounded question
  (e.g. a drug not in this plan or any CPG), and that it cites `cpg_source` on a
  grounded "why this rec" question. Mirror existing `backend/tests` style.
- **Manual:** run the app, generate a plan, ask "why did you prescribe X?" and confirm
  the answer cites the stored rationale + CPG section.

## 7. Build order

1. Explainer prompt file (`explain_careplan.txt`).
2. Grounding-context formatter + `/clinical/explain/stream` endpoint.
3. Backend refuse-and-escalate test.
4. Frontend `explainCarePlan` client method.
5. `CarePlanChat` panel + per-recommendation "ask why" hook-in.

## 8. Estimated scope

- Backend: ~half a day (mostly mirroring `/chat/stream`).
- Frontend panel: ~half to one day.
- No risky migrations.

## 9. Open implementation details (resolve during build)

- Whether to emit `recommendation_index` context into the prompt as structured text
  vs. just narrowing retrieval.
- Exact dock location of the panel (match wherever `FinalCarePlan` renders).

## 10. Out of scope / guardrails

- **Not** a general medical chatbot. Scope is strictly *this plan + CPG corpus*.
  Answering ungrounded clinical questions would make it a liability rather than a
  transparency tool.
- No conversation persistence / audit trail in v1 (can be added later as a Supabase
  table if clinical audit is required).
