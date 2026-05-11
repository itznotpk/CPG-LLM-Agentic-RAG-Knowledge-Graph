# clinical_cli.py — Issues & Priority Actions

> Test run 2: 58M chest pain, ACS presentation, CKD Stage 3, T2DM, Penicillin allergy
> Chief complaint: 60-word clinical narrative
> Output reviewed against terminal output, 85.2s total elapsed

---

## Priority Actions (ordered)

---

### P1 — Wrong DDx: narrative chief complaint dilutes ACS signal ⚡ CRITICAL

**Symptom:** DDx returns BD11.0 (HFpEF), BB01.1 (PAH), BD50.3Y — instead of I21.x (ACS/STEMI) or I20.0 (Unstable Angina). All downstream stages (CPG routing, evidence retrieval, medication recommendations) cascade from this wrong ICD.

**Root cause:** `chief_complaint` is the full clinical notes textarea in the Doctor UI (`clinicalNotes` → `case.chief_complaint`). A 60-word narrative contains "dyspnoea", "exertional", "ventricular", "left" — these dilute the ACS signal and vector-match HF/PAH codes more strongly than ACS codes.

The pipeline itself detects this: Summary says "highly suspicious for ACS", unresolved question #3 says "HFpEF-specific treatment guidance was not retrieved". The LLM is reasoning correctly but fighting the wrong CPG context.

**Fix options:**

**Short-term — use concise chief complaint for testing:**
```
Chest pain radiating to left arm and jaw, diaphoresis, nausea, 3 hours, no rest relief
```
This should vector-match I21.x or I20.0 directly. Re-test this before anything else.

**Medium-term — symptom extraction pre-step (Gap C2, new):**
Add a lightweight LLM call in Stage 2 before the vector search that extracts a structured symptom phrase from the free-text clinical notes:

```python
# clinical_stages.py — stage_2_ddx, before search_ddx()
async def _extract_symptom_phrase(notes: str, client: openai.AsyncOpenAI) -> str:
    """Compress clinical notes to a symptom-focused DDx query string."""
    resp = await client.chat.completions.create(
        model=os.getenv("LLM_CHOICE"),
        messages=[{
            "role": "user",
            "content": (
                "Extract the key presenting symptoms as a short phrase for ICD-11 differential diagnosis. "
                "Return only the symptom phrase, no explanation.\n\n"
                f"Clinical notes: {notes}"
            )
        }],
        max_tokens=60,
    )
    return resp.choices[0].message.content.strip()

# Then pass result to search_ddx() instead of raw chief_complaint
query = await _extract_symptom_phrase(case.chief_complaint, client)
ddx_candidates = await search_ddx(query, top_k=10)
```

This keeps the full clinical notes in `patient_context` for Stage 5 synthesis while giving the vector search a clean signal.

---

### P2 — Medication Changes section sparse: no START, no CONTRAINDICATED ⚡ HIGH

**Symptom:** S2 only shows CONTINUE (Aspirin, Lisinopril). Missing: Metformin status (should flag STOP/caution in suspected ACS or acute HF), Atorvastatin CONTINUE, no dual antiplatelet consideration, no NSAID contraindication.

**Root cause:** Stage 3 routed to Heart Failure + PAH CPGs. The ACS CPG was never consulted — no chunks on DAPT, statin loading dose, or Metformin-in-ACS exist in the retrieved evidence. Stage 5 can only synthesise from what Stage 4 retrieved.

**Fix:** Resolves automatically once P1 is fixed (correct DDx → ACS CPG routed → DAPT + statin + contraindication chunks retrieved).

**Independent partial fix — Gap C1 (comorbidity routing):**
Even with correct DDx, `case.comorbidities` (T2DM, CKD Stage 3, Hypertension) are never used to retrieve additional CPGs. Adding comorbidity routing would bring in DM and CKD CPGs for Metformin guidance and renal dose adjustment:

```python
# clinical_workflow.py — after stage_3_route
async def route_comorbidities(
    comorbidities: list[str],
    existing_cpgs: list[CPGDocRef],
    top_k: int = 2,
) -> list[CPGDocRef]:
    additional = []
    for condition in comorbidities:
        ddx = await search_ddx(condition, top_k=1)
        if ddx:
            refs = await route_icd_to_cpgs(ddx[0]["code"], top_k=top_k)
            for ref in refs:
                if ref.cpg_name not in {c.cpg_name for c in existing_cpgs}:
                    additional.append(ref)
    return additional
```

**Effort:** C1 comorbidity routing ~3h, independent of P1.

---

### P3 — Thinking tokens never appear (AI Reasoning block missing) ⚡ MEDIUM

**Symptom:** DDx table shows:
```
AI reasoning for #1: Vector similarity 0.451 | Keyword overlap: left, with
```
The `╔══ AI Reasoning ══` block never prints. This is a fallback from raw similarity data, not actual Gemini thinking output.

**Root cause:** `gemini-2.5-flash-preview-05-20` IS a valid model (released May 2025). The issue is that Google's OpenAI-compatibility shim at `/v1beta/openai/` may not surface thinking tokens in the standard `delta.content` field. Gemini's native thinking tokens may arrive in a non-standard field that the CLI's `thinking_delta` handler isn't reading.

**Fix options:**

**Option A — Inspect delta fields from the shim (fastest to diagnose):**
Add a temporary debug print in `clinical_stages.py` inside the thinking token streaming loop to log the full delta object:
```python
# temporary — remove after diagnosis
logger.debug("thinking delta keys: %s", delta.__dict__)
```
Compare against Google's docs for the OpenAI-compat shim to find the correct field name (`delta.reasoning`, `delta.thinking`, `reasoning_content`, etc.).

**Option B — Switch DDX_RERANK_MODEL to `gemini-2.0-flash` for dev:**
No thinking tokens, but DDx rerank still runs. Faster (no thinking budget consumed). Acceptable for functional testing — just no reasoning trace in the CLI.
```
# .env
DDX_RERANK_MODEL=gemini-2.0-flash
```

**Option C — Use native Gemini Python SDK instead of OpenAI shim for Stage 2:**
`google-generativeai` or `google-genai` SDK exposes thinking tokens natively via `response.candidates[0].content.parts` where `part.thought == True`. This would require a separate client path for Stage 2 only.

**Recommended immediate action:** Use Option B for testing now. Investigate Option A/C as a separate task.

---

### P4 — Referrals section incomplete: no nephrology or DM specialist ⚡ MEDIUM

**Symptom:** Only 1 referral (urgent cardiology). Missing: nephrology (CKD Stage 3 with potential contrast for cath), diabetes/primary care (T2DM management with acute illness).

**Root cause:** Comorbidity CPGs (CKD, DM) never retrieved — same Gap C1 as P2. Stage 5 can only recommend referrals supported by retrieved evidence.

**Fix:** Same C1 comorbidity routing fix as P2. Once DM and CKD CPGs are in scope for Stage 4, Stage 5 will have evidence to support nephrology and DM referral recommendations.

---

### P5 — Total elapsed 85s too slow for interactive testing ⚡ LOW

**Breakdown:**
- Stage 2 DDx: 3.3s — acceptable
- Stage 3 CPG routing: 0.9s — fast
- Stage 4 retrieval: 37s — 5 queries × ~7s/query (NeonDB pgvector, expected)
- Stage 5 synthesis: 44s — MiMo generating full TreatmentPlan JSON

**Fix options:**

**Short-term — reduce Stage 4 query count during dev:**
Add env var `STAGE4_QUERIES_PER_CODE` and default to 3 during dev (instead of 5):
```python
queries_per_code = int(os.getenv("STAGE4_QUERIES_PER_CODE", "5"))
```

**Medium-term — parallel query execution:**
Stage 4 currently runs queries sequentially. Running all 5 concurrently with `asyncio.gather` would cut 37s → ~10s:
```python
results = await asyncio.gather(*[
    vector_search_tool(VectorSearchInput(query=q, document_ids=doc_ids, top_k=5))
    for q in queries
])
```

**Stage 5 model — swap MiMo for Gemini Flash during dev:**
If Google API is unblocked, `gemini-2.0-flash` for Stage 5 synthesis would likely be 10–15s vs 44s.

---

## Resolved Issues (from Test Run 1)

| ID | Issue | Status |
|----|-------|--------|
| U1 | No section separators | ✅ Fixed — DIV lines added |
| U2 | No action group headers in meds | ✅ Fixed — `── START ──` sub-headers |
| U3 | Inline rationale `\|` separator hard to read | ✅ Fixed — rationale on own line |
| U4 | Care plan header box misaligned | ✅ Fixed — `inner:<{width}` padding |
| U5 | DDx table column misalignment | ✅ Fixed — consistent column widths |
| U6 | Pipeline ran 4× (duplicate SSE reads) | ✅ Fixed — `Connection: close` header |

---

## Open Issues Summary

| # | Issue | Type | Impact | Blocked by |
|---|-------|------|--------|------------|
| P1 | Wrong DDx — narrative chief complaint | Pipeline | Critical | Nothing — fix now |
| P2 | Medications section sparse | Pipeline | High | P1 (cascade) + Gap C1 |
| P3 | Thinking tokens missing | CLI/Config | Medium | Investigation needed |
| P4 | Referrals incomplete | Pipeline | Medium | Gap C1 |
| P5 | 85s total elapsed | Performance | Low | Parallel queries (future) |
