# Next Step — Ingest Missing Primary Comorbidity CPGs

> **Follow-up to Gap 1 in `Gaps_Closing.md`.**
> Gap 1 code is complete; comorbidity routing now works correctly. This task closes the **data-side** of Gap 1 by ingesting two foundational Malaysian CPGs that are currently missing.
> Also closes the data-side of Gap 2 partially (DM CPG contains SGLT2i + cardioprotection guidance).

---

## Why this matters

Test Run 3 (Diagnostic queries against NeonDB) confirmed:

```sql
-- 0 standalone DM or CKD CPGs ingested:
SELECT id, title FROM documents
WHERE title ILIKE '%diabetes%' OR title ILIKE '%kidney%' OR title ILIKE '%renal%' OR title ILIKE '%nephro%';
-- → 1 row: "SECTION 14.6: HF AND CHRONIC KIDNEY DISEASE" (chunk of HF CPG, not standalone)
```

```
Comorbidity 'Type 2 Diabetes Mellitus' → ICD 5A11 → CPGs: []
Comorbidity 'CKD Stage 3' → skipped (no usable match)
```

A patient with T2DM + CKD therefore receives:
- ❌ No DM-specific medication adjustments (SGLT2i, GLP-1 RA cardioprotection, metformin dose at low eGFR, insulin titration)
- ❌ No CKD-specific guidance (BP target <130/80 in proteinuria, ACEi/ARB renoprotection, statin dose, contrast nephropathy precautions)
- ❌ No nephrology / endocrinology referral evidence base
- ⚠️ Stage 5 synthesis fills the gap from LLM training data → **hallucinated `cpg_source` citations** to documents that don't contain the cited content

Comorbidity routing CANNOT close this gap on its own — it requires the underlying CPGs to exist in `documents` + `chunks`.

---

## Scope

Ingest two primary Malaysian CPGs:

1. **CPG Management of Type 2 Diabetes Mellitus (6th Edition, 2020)**
2. **CPG Management of Chronic Kidney Disease in Adults (2nd Edition, 2018)** — or newer if available

Each must be:
- Parsed by existing `ingestion/cpg_parser.py`
- Chunked by `ingestion/chunker.py` (1200 char chunks, 200 overlap, with metadata categories)
- Embedded by `ingestion/embedder.py` (Bedrock Titan v1, 1536-dim)
- Scope-classified by `ingestion/classify_cpg_scope.py` (must populate `icd11_scope` correctly — see verification below)
- Verified by `ingestion/verify_cpg_scope.py` (manual review + `scope_verified=TRUE`)
- Graph-builder extraction by `ingestion/graph_builder.py` (Treatment/Assessment chunks only, per Gap R6)

---

## Expected `icd11_scope` after classification

| CPG | Primary ICD-11 codes expected in `icd11_scope` |
|-----|-----------------------------------------------|
| T2DM | `5A11` (Type 2 DM), `5A13.Z` (Other specified DM if relevant), `5A1Z` (DM, unspecified) |
| CKD | `GB61.3` (CKD Stage 3), `GB61.4` (Stage 4), `GB61.5` (Stage 5), `GB6Z` (CKD unspecified), `GB61.Z` (CKD, stage unspecified) |

**Verification queries to run after ingestion:**

```sql
-- T2DM CPG should be the only document with 5A11 in primary scope
SELECT id, title, icd11_scope, scope_verified
FROM documents
WHERE '5A11' = ANY(icd11_scope)
ORDER BY title;

-- CKD CPG should have GB61.x family
SELECT id, title, icd11_scope, scope_verified
FROM documents
WHERE icd11_scope && ARRAY['GB61.3', 'GB61.4', 'GB61.5', 'GB6Z']::text[]
ORDER BY title;
```

Both must return exactly one new row each, `scope_verified = TRUE`.

---

## Pipeline validation after ingestion

Re-run the existing CLI smoke test (`python clinical_cli.py` with Test Case 1 — 58M ACS narrative with T2DM, CKD Stage 3, HTN comorbidities).

### Expected log changes

```
Comorbidity 'Type 2 Diabetes Mellitus' → DDx candidates: [('5A11', 'Type 2 diabetes mellitus', 0.80+), ...]
Comorbidity 'Type 2 Diabetes Mellitus' → ICD 5A11 → CPGs: ['Diabetes-Mellitus-T2(6th)'] (match_types=['exact'])

Comorbidity 'CKD Stage 3' → DDx candidates: [('GB61.3', 'Chronic kidney disease, stage 3', 0.65+), ...]
Comorbidity 'CKD Stage 3' → ICD GB61.3 → CPGs: ['Chronic-Kidney-Disease(2nd)'] (match_types=['exact'])
```

Both should clear the 0.55 threshold thanks to clinical synonym expansion (CKD → "chronic kidney disease", T2DM → "type 2 diabetes mellitus").

### Expected care plan changes

| Section | Before ingestion | After ingestion |
|---------|------------------|-----------------|
| S2 START | Furosemide, generic SGLT2i with vague dose | Empagliflozin 10mg OD with CKD eGFR caveat from DM CPG |
| S2 CONTRAINDICATED | (none) | Metformin if eGFR <30, contrast hold protocol |
| S4 Monitoring | Generic K+/eGFR | HbA1c target, ACR for proteinuria, eGFR slope (CKD CPG) |
| S5 Referrals | Cardiology only | Cardiology + Nephrology + DM specialist |
| `cpg_source` citations | "CPG HF §14.6" (loose mention) | "CPG T2DM §X.X" + "CPG CKD §X.X" (primary) |
| `unresolved_questions` | "Metformin in acute setting not addressed", "Exact BP target...", "SGLT2i dosing in CKD..." | Should drop by 3–5 items |

---

## Files to touch

| Action | File |
|---|---|
| **PLACE** | `markdown/Diabetes-Mellitus-T2(6th-Edition)/section-N-...md` (per existing structure) |
| **PLACE** | `markdown/Chronic-Kidney-Disease(2nd-Edition)/section-N-...md` |
| Run | `python -m ingestion.ingest` (existing pipeline — no code changes) |
| Run | `python -m ingestion.classify_cpg_scope` (existing — no code changes) |
| Run | `python -m ingestion.verify_cpg_scope` (existing — manual review step) |
| Run | `python -m ingestion.graph_builder` scoped to new documents |
| Verify | Run SQL queries above |
| Validate | `python clinical_cli.py` with Test Case 1, compare log + care plan |

**No code changes required.** This task is purely data ingestion using existing pipelines.

---

## Out of scope

- ❌ Do NOT modify `route_comorbidities` or the 0.55 threshold (working correctly)
- ❌ Do NOT modify clinical synonym expansion (working correctly)
- ❌ Do NOT add `5A11` or `GB61.x` to existing CPGs' `icd11_scope` arrays as a shortcut — this would mis-route to HF/CVD CPGs and reintroduce hallucination risk
- ❌ Do NOT block on perfect graph-builder coverage — Treatment/Assessment chunks are sufficient for the first pass
- ❌ Do NOT renumber existing Gaps in `Gaps_Closing.md` — Gap 1 retains its number; this is the data-side follow-up

---

## Acceptance criteria

- [ ] T2DM CPG document row exists in `documents` with `'5A11' = ANY(icd11_scope)` and `scope_verified = TRUE`
- [ ] CKD CPG document row exists in `documents` with `icd11_scope && ARRAY['GB61.3', 'GB61.4', 'GB61.5']::text[]` and `scope_verified = TRUE`
- [ ] CLI smoke run: `Comorbidity 'Type 2 Diabetes Mellitus'` log line shows `→ CPGs: ['Diabetes-...']` (non-empty)
- [ ] CLI smoke run: `Comorbidity 'CKD Stage 3'` log line shows `→ ICD GB61.3` (not skipped) AND `→ CPGs: ['Chronic-Kidney-...']`
- [ ] Care plan S2 contains at least one DM-specific recommendation (SGLT2i with CKD-aware dose, or Metformin contraindication)
- [ ] Care plan S5 contains nephrology referral
- [ ] `unresolved_questions` count drops by ≥ 3 items vs Test Run 3 baseline

---

## Next gaps after this one

Once DM + CKD CPGs land, the natural progression is:

1. **Gap 2** (Drug interactions structured lookup) — `Gaps_Closing.md` §Gap 2, ~2 h
2. **Gap 3** (5 domain-templated queries) — already done in prior work but verify against new CPGs
3. **Gap 4** (Severity staging in `PatientCase`) — `Gaps_Closing.md` §Gap 4, ~4 h
4. **Gap 5** (CPG currency / published_year warning) — `Gaps_Closing.md` §Gap 5, ~1.5 h
