# SOP — Per-CPG Ingestion Verification

> **When to run:** every time a single CPG is ingested (the standard workflow — one CPG at a time, not bulk).
> **Purpose:** confirm the CPG landed correctly in both Postgres (vector DB) and Neo4j (KG) without re-auditing the whole corpus.
> **Time:** ~5 minutes per CPG (excluding the ingestion itself).
> **Last updated:** 2026-05-17

---

## Prerequisites

- `venv` activated.
- `.env` has `DATABASE_URL`, `NEO4J_*`, `BEDROCK_MODEL_ID` set.
- The CPG markdown lives under `markdown/<CPG-folder-name>/` (e.g. `markdown/Atrial-Fibrillation(2012)/`). The folder name becomes `metadata->>'cpg_name'` in Postgres.

---

## Step 1 — Capture pre-ingestion baseline

Note current totals so you can diff after. Takes 5 seconds.

```powershell
venv\Scripts\python.exe scratch\kg_verify.py | Select-String -Pattern "TOTAL"
```

Write down: `node_total_before = ___`, `edge_total_before = ___`.

**Why:** if post-ingestion counts didn't move, extraction silently failed. The most common cause is `BEDROCK_MODEL_ID` returning 404 (see [Phase A KG Rebuild Findings](../../memory/project_kg_rebuild_phase_a.md)).

---

## Step 2 — Back up before first ingestion of a session (optional, recommended)

If you've made code changes since your last backup, take a fresh Neo4j dump:

```powershell
# From the Neo4j browser or cypher-shell:
# CALL apoc.export.cypher.all("backups/kg_backup_<YYYY-MM-DD>.cypher", {format:"cypher-shell"});
```

Skip if your last backup in `backups/` is current.

---

## Step 3 — Run the ingestion

Point `--documents` at a folder containing **only** the CPG you want to ingest. The ingester processes every markdown file inside.

```powershell
# Move or symlink only the target CPG folder into a fresh staging dir,
# OR ingest from its own folder directly:
venv\Scripts\python.exe -m ingestion.ingest --documents "markdown\<CPG-folder-name>"
```

**Common flags:**
- `--skip-graph` → vector DB only (faster, for testing chunking)
- `--graph-only` → KG only (use after vector DB is already populated)
- `--clean` → ⚠ wipes existing data; do **not** use for incremental adds
- `--verbose` → log every chunk

**During the run, watch for:**
- `ResourceNotFoundException` or `404` → Bedrock model expired, fix `BEDROCK_MODEL_ID`
- `Triple extraction failed` → LLM call failed; check Bedrock credentials
- `oversized chunk` warnings → chunk-splitting issue, won't fail but truncates extraction
- `MERGE failed` → name normalisation regression; investigate before proceeding

---

## Step 4 — Run the per-CPG verification

```powershell
venv\Scripts\python.exe scratch\verify_cpg_ingest.py --cpg "<CPG-folder-name>"
```

The `--cpg` argument is a substring matched against `metadata->>'cpg_name'`. Use the folder name (e.g. `"Atrial-Fibrillation"`, `"Heart-Failure"`, `"Dyslipidaemia"`).

### What it checks and the pass/fail thresholds

| Check | Threshold | What FAIL means |
|---|---|---|
| **PG-1** Document rows exist | ≥1 | `metadata->>'cpg_name'` wasn't set during ingestion; pipeline regression |
| **PG-2** Total chunks | ≥ 20 (warn-only) | Markdown wasn't parsed correctly, or CPG is unusually small |
| **PG-3** h2/h3 leaf embeddings | 0 nulls; dim = 1536 | Vector search will miss those chunks; embedding pipeline failed mid-batch |
| **PG-4** Child chunks have parents | 0 orphans (warn-only) | Parent-child linkage broken; stage 5 parent prefetch will fail for orphans |
| **PG-5** Category metadata present | At least one Treatment/Assessment | Graph_builder whitelist won't select anything → 0 KG edges next step |
| **PG-6** Vector search smoke test | ≥1 result from cosine similarity | Embeddings exist but may be corrupted (all-zeros, wrong model) — retrieval is broken end-to-end |
| **KG-1** Total edges from this CPG | ≥ 30 (warn at <30, fail at 0) | LLM triple extraction failed silently (most likely Bedrock 404) |
| **KG-2** Severity on safety-critical edges | ≥ 30% | Phase A prompt regression — Stage 5 flag triage will degrade |
| **KG-3** `evidence_list` + `cpg_chunk_ids` on every edge | 100% | Phase A write-side regression in [graph_builder.py:649-658](../../ingestion/graph_builder.py#L649-L658) |
| **KG-4** `cpg_chunk_id` → Postgres cross-DB lookup | 10/10 sampled found | Cross-DB drift; `chunk_id` propagation broke |
| **KG-5** Sample 5 edges printed | Manual eyeball | Edge looks wrong → re-ingest with `--verbose` and check the extraction prompt |
| **KG-6** `name_normalised` on all nodes | 100% (FAIL if any missing) | `clinical_graph_lookup` Cypher queries match on `name_normalised` — missing values = invisible nodes |
| **KG-7** Duplicate node detection | <5% duplication rate | Name normalisation regression — same entity creates multiple nodes, queries miss edges |

### Expected output footer

```
✅ ALL CHECKS PASSED — CPG ingested cleanly
```

…or a list of `FAIL` / `WARN` lines. **Stop and investigate** any `FAIL`. `WARN` is informational unless it repeats across multiple CPGs.

---

## Step 5 — Cumulative health check

Confirm the *whole graph* didn't regress. Should be fast.

```powershell
venv\Scripts\python.exe scratch\kg_verify.py
```

**Compare to baseline (Step 1):**
- Total nodes/edges grew by a sensible amount (typically +30 to +200 edges per CPG)
- 0 missing evidence, 0 orphan nodes
- No duplicate triple patterns flagged

---

## Step 5b — Duplicate node audit

Check that the new CPG didn't re-introduce duplicate nodes (e.g., name normalisation edge case).

```powershell
venv\Scripts\python.exe scratch\kg_dupes.py
```

**What to look for:**
- `CHECK 4` duplication ratio should generally be very low (under 5%).
- **Acceptable duplicates (cross-label):** If you see duplicates with the exact same `name_normalised` but different labels (e.g., "anticoagulation" extracted as both `[Procedure]` and `[Drug]`), this is **normal and harmless**. Neo4j's `MERGE` requires matching labels, so it creates two nodes. Because our `clinical_graph_lookup` pipeline queries *only* on `name_normalised` and ignores the label (`WHERE d.name_normalised IN $candidates`), the read query will flawlessly match both nodes and merge their relationships!
- **Bad duplicates (normalisation failure):** If duplicates appear because of unhandled abbreviations (e.g. a new CPG uses an abbreviation not in `_ABBREV_MAP`), or weird casing/plurals slipped through, you need to update `_normalize_entity_name()` in `graph_builder.py`.
---

## Step 6 — Phase D smoke test (only after a relevant CPG)

If you just ingested a CPG that adds drug-interaction content (cardiology, dyslipidaemia, anaesthesia, HF, etc.), re-run the wiring test to confirm flags fire for a polypharmacy patient:

```powershell
venv\Scripts\python.exe scratch\test_phase_d_af.py
```

Expected: `Gate 1/2/3: PASS`. If a previously-passing test now fails, the new CPG introduced a name-normalisation collision or broke something in `clinical_graph_lookup` — bisect by reverting the new edges in Neo4j.

---

## Step 6b — Clinical graph lookup smoke test

Verify the structured Cypher lookup (`clinical_graph_lookup`) still returns correct results after ingesting a new CPG.

```powershell
venv\Scripts\python.exe scratch\test_graph_clinical.py
```

**What to look for:**
- All 3 query types run without errors (drug interactions, comorbidity flags, allergy cross-reactivity)
- `format_flags_for_prompt()` produces readable output
- If this was previously passing and now returns 0 flags, check:
  - Did the new ingestion wipe existing nodes? (shouldn't with MERGE)
  - Is `name_normalised` populated? (KG-6 check)

---

## Step 7 — Clinical usefulness validation (first CPG of a new disease domain only)

When you ingest the **first CPG for a new disease** (e.g., first Heart Failure CPG, first Dyslipidaemia CPG), run the full clinical validation suite to confirm the graph can answer real questions:

```powershell
# Multi-hop graph queries (drug→condition→risk, cross-section linking)
venv\Scripts\python.exe scratch\kg_usefulness.py

# Clinical scenario walkthrough (contraindications, comorbidities, treatment pathways)
venv\Scripts\python.exe scratch\kg_clinical_tests.py
```

**When to run:** Only after the **first CPG of a new disease domain**. Not needed for every incremental ingestion.

**Expected results:**
- `kg_usefulness.py`: Score ≥4/5
- `kg_clinical_tests.py`: At least 1 contraindication, 1 treatment pathway, and 1 monitoring edge visible

If these fail on a new CPG, the extraction prompt may need domain-specific tuning.

---

## Step 8 — Generate Ingestion Report

Once all checks pass, document the results to maintain an audit trail of the Knowledge Graph's growth.

**Action:** Prompt the AI assistant to summarize the terminal outputs from the previous steps into a Markdown report and save it to the `tasks/Ingestion-Reports/` directory.

**The report must include:**
1. **Document & Chunking Statistics:** Total chunks embedded and category distribution.
2. **Knowledge Graph Extraction:** Total edges created, breakdown by relationship type, and severity coverage percentage.
3. **Entity Normalisation Health:** Validation that `name_normalised` is populated, and confirmation of duplicate ratios (especially separating Safe cross-label duplicates from Bad same-label duplicates).
4. **Spotlight Extractions:** 2-3 examples of high-value clinical triples (like contraindications or required monitoring) extracted from the run.

---

## Recovery — when something fails

### "0 KG edges from this CPG" (KG-1 FAIL)

1. Re-check Bedrock: `venv\Scripts\python.exe scratch\test_bedrock.py`
2. Check ingestion logs for `Triple extraction failed`
3. If Bedrock is OK, re-run **only graph extraction** for that CPG:
   ```powershell
   venv\Scripts\python.exe -m ingestion.ingest --documents "markdown\<CPG-folder>" --graph-only
   ```

### "X chunks have null embeddings" (PG-3 FAIL)

The embedding call failed mid-batch. Find which chunks and re-embed only those:

```sql
SELECT c.id, c.chunk_level
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.metadata->>'cpg_name' ILIKE '%<cpg>%'
  AND c.chunk_level IN ('h2','h3')
  AND c.embedding IS NULL;
```

Then re-ingest with `--skip-graph` so only the vector DB is touched.

### Phase A regression (KG-3 FAIL — missing evidence_list or cpg_chunk_ids)

Some edges were written by an older code path. Either:
- Re-ingest this CPG from scratch (drops & re-extracts), OR
- Patch the affected edges with a one-off Cypher UPDATE, OR
- Restore the most recent Neo4j backup and re-run with current code.

### Catastrophic — graph corrupted

Restore the latest backup:

```powershell
# From cypher-shell:
# :source backups/kg_backup_<YYYY-MM-DD>.cypher
```

Then re-ingest the failed CPG fresh.

---

## Quick reference — one-liner for happy path

```powershell
# 1. ingest, 2. verify per-CPG, 3. cumulative health, 4. duplicates, 5. clinical lookup
venv\Scripts\python.exe -m ingestion.ingest --documents "markdown\<CPG-folder>"
venv\Scripts\python.exe scratch\verify_cpg_ingest.py --cpg "<CPG-folder>"
venv\Scripts\python.exe scratch\kg_verify.py | Select-String -Pattern "TOTAL|ISSUES|PASSED"
venv\Scripts\python.exe scratch\kg_dupes.py | Select-String -Pattern "CHECK 4|CLEAN|WARNING"
venv\Scripts\python.exe scratch\test_graph_clinical.py
```

If all exit with `PASSED` / `ALL CHECKS PASSED` / `CLEAN`, the CPG is in.

---

## Appendix — scripts referenced

| Script | Purpose |
|---|---|
| [scratch/verify_cpg_ingest.py](../../scratch/verify_cpg_ingest.py) | Per-CPG verification (PG-1–6, KG-1–7 — this SOP's main tool) |
| [scratch/kg_verify.py](../../scratch/kg_verify.py) | Whole-graph health check |
| [scratch/kg_dupes.py](../../scratch/kg_dupes.py) | Standalone duplicate node audit (abbreviation splits, case dupes, plurals) |
| [scratch/test_graph_clinical.py](../../scratch/test_graph_clinical.py) | `clinical_graph_lookup` smoke test (structured Cypher queries) |
| [scratch/kg_usefulness.py](../../scratch/kg_usefulness.py) | Multi-hop clinical usefulness test (5 query patterns) |
| [scratch/kg_clinical_tests.py](../../scratch/kg_clinical_tests.py) | Clinical scenario walkthrough (contraindications, comorbidities, treatment pathways) |
| [scratch/audit_phase_a.py](../../scratch/audit_phase_a.py) | Phase A feature audit (severity, evidence_list shape) |
| [scratch/test_phase_d_af.py](../../scratch/test_phase_d_af.py) | Phase D wiring smoke test |
| [scratch/test_bedrock.py](../../scratch/test_bedrock.py) | Bedrock model connectivity sanity check |
| [scratch/check_norm.py](../../scratch/check_norm.py) | Quick `name_normalised` population check |
| [scratch/db_check.py](../../scratch/db_check.py) | Chunk hierarchy per document (diagnostic) |
