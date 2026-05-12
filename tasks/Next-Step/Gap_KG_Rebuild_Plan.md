# Knowledge Graph — Rebuild Plan

> **Objective:** Wire the KG into the clinical pipeline AND rebuild the underlying graph data so it actually answers structured clinical questions (drug-drug interactions, allergy cross-reactivity, comorbidity dose adjustment, first-line by ICD).
>
> **Companion docs:**
> - [Gap_KG_Wiring_Problems.md](Gap_KG_Wiring_Problems.md) — the 6 problems this plan solves
> - [../RAG_Pipeline_and_Prompt_Gaps.md](../RAG_Pipeline_and_Prompt_Gaps.md) — Gap R6 (KG wiring) parent gap
>
> **Guiding principle:** *The schema is defined by the queries that read it.* Wire the consumer first against the (broken) current graph to discover what properties edges must carry, THEN re-ingest with confidence. Avoid the trap of re-ingesting twice.

---

## Phase order at a glance

```
Phase A — Pre-flight (4 h)
   ├── A1. Backup current Neo4j
   ├── A2. Investigate chunker root cause (why graph build was skipped)
   └── A3. Cost estimate via 1-CPG dry run

Phase B — Consumer-first wiring (1 day)
   ├── B1. Write 3 clinical Cypher queries against current graph
   ├── B2. Stub clinical_graph_lookup() into Stage 4
   ├── B3. Inject results into Stage 5 prompt as INTERACTION FLAGS block
   └── B4. Discover schema needs from query failures

Phase C — Schema + extraction fixes (1 day)
   ├── C1. Fix chunker issues found in A2
   ├── C2. Add category whitelist to graph_builder
   ├── C3. Promote chunk_index → cpg_chunk_id (UUID)
   ├── C4. Name normalisation (write + read sides)
   ├── C5. Expand relation taxonomy + properties
   └── C6. Add icd11_code via post-ingestion Cypher batch

Phase D — Pilot re-ingestion (0.5 day)
   ├── D1. Clear Neo4j (graph data only, keep schema)
   ├── D2. Re-ingest ONE CPG (HTN — clinically dense)
   └── D3. Validate Cypher returns clean structured rows

Phase E — Fixture validation (0.5 day)
   ├── E1. 3 fixture patient cases through full pipeline
   ├── E2. Verify INTERACTION FLAGS appear with citations in UI
   └── E3. Sign-off gate: do not proceed to F until E passes

Phase F — Full backfill (1 day code-time, ~1 day batch-time)
   ├── F1. Re-ingest remaining CPGs in batches
   ├── F2. Monitor LLM cost + extraction quality
   └── F3. Spot-check 5 random patient cases in UI

Total: ~4 working days code, +1 day batch processing
```

---

## Phase A — Pre-flight (4 h)

### A1. Backup current Neo4j

**Goal:** Recoverable state before any destructive operation.

**Steps:**
1. Confirm Neo4j credentials in `.env` (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`).
2. Export current graph to a Cypher dump:
   ```bash
   # If APOC available:
   cypher-shell -u $NEO4J_USER -p $NEO4J_PASSWORD \
     "CALL apoc.export.cypher.all('kg_backup_$(date +%F).cypher', {format:'cypher-shell'})"

   # If not, use neo4j-admin dump (requires DB stopped):
   neo4j-admin database dump neo4j --to-path=./backups/
   ```
3. Verify backup file exists and is non-empty (>1 KB).
4. Record current node + edge counts as baseline:
   ```cypher
   MATCH (n) RETURN count(n) AS nodes;
   MATCH ()-[r]->() RETURN count(r) AS edges;
   ```

**Exit gate:** Backup file exists; counts logged in this doc under "Phase A artifacts".

---

### A2. Investigate chunker root cause

**Goal:** Understand WHY graph build was skipped during last ingestion. Re-running the same chunker without fixing the cause re-creates the same problem.

**Steps:**
1. Read [ingestion/chunker.py](../../ingestion/chunker.py) end-to-end. Note any `try/except` swallowing errors silently.
2. Read [ingestion/ingest.py](../../ingestion/ingest.py) — find where `build_relationship_graph` is called (or where it's commented out / skipped).
3. Sample 3 chunks from NeonDB across 3 different CPGs:
   ```sql
   SELECT chunk_id, document_id, length(content) AS len, metadata->'category' AS cat
   FROM chunks ORDER BY random() LIMIT 9;
   ```
4. Check for: chunks > 10,000 chars (Graphiti token limit), chunks with empty `metadata['category']`, chunks with missing `<!-- METADATA -->` blocks.
5. Run `_extract_triples_with_llm` manually against ONE problem chunk to reproduce the failure mode. Capture the exception.

**Likely findings (predict before investigating):**
- Oversized chunks blowing Graphiti's 8192 token limit ([graph_builder.py:114](../../ingestion/graph_builder.py#L114) warns about this)
- Bedrock auth/quota errors mid-batch corrupting state
- Chunks missing category metadata, causing Phase B/C category filter to also silently skip them

**Exit gate:** Root cause documented in this MD as "Phase A2 finding: …". Chunker fix scoped (may move to C1).

---

### A3. Cost estimate via 1-CPG dry run

**Goal:** Know the LLM spend before authorising full batch.

**Steps:**
1. Pick one mid-sized CPG (e.g., ED — small enough to be fast, has clear contraindications for validation).
2. Count its chunks:
   ```sql
   SELECT count(*) FROM chunks WHERE document_id = $ED_CPG_DOC_ID;
   ```
3. Apply category filter mentally — count only Treatment/Assessment/Special Populations chunks. Call this `N_filtered`.
4. Estimate: `N_filtered × ~6000 chars/chunk × Bedrock Llama 3.3 70B input cost + ~1000 chars output cost`.
5. Multiply by total CPG count for full-batch estimate.

**Exit gate:** Cost estimate written here. If above $50, get explicit confirmation before Phase F.

---

## Phase B — Consumer-first wiring (1 day)

> **Why this comes BEFORE re-ingestion:** writing the queries against the current graph reveals what properties the edges actually need. Re-ingesting first means guessing the schema; doing it after means knowing.

### B1. Write 3 clinical Cypher queries

**Goal:** Lock in the exact query shapes the clinical pipeline will run.

**File:** new `agent/graph_clinical.py`

**Steps:**
1. Define `clinical_graph_lookup(case: PatientCase, retrieved_drugs: list[str]) -> ClinicalFlags`:
   ```python
   class ClinicalFlag(BaseModel):
       flag_type: Literal["INTERACTION", "ALLERGY_CROSS", "DOSE_ADJUSTMENT"]
       subject: str          # e.g., patient drug
       object: str           # e.g., interacting drug / condition
       severity: str | None  # MAJOR/MODERATE/MINOR if extractable
       evidence: str
       source_document: str
       cpg_chunk_id: str | None
   ```

2. Implement three Cypher queries (run in parallel via `asyncio.gather`):
   - **Drug-drug interactions:**
     ```cypher
     MATCH (d1:Drug)-[r:CONTRAINDICATED_WITH|INTERACTS_WITH]-(d2:Drug)
     WHERE toLower(d1.name) IN $patient_meds_norm
       AND toLower(d2.name) IN $candidate_drugs_norm
     RETURN type(r) AS rel, d1.name AS subj, d2.name AS obj,
            r.evidence AS evidence, r.source_document AS source,
            coalesce(r.severity, 'UNSPECIFIED') AS severity,
            coalesce(r.cpg_chunk_id, toString(r.chunk_index)) AS chunk_id
     ```
   - **Allergy cross-reactivity:**
     ```cypher
     MATCH (a)-[r:CONTRAINDICATED_WITH|CROSS_REACTS_WITH]-(d:Drug)
     WHERE toLower(a.name) IN $allergies_norm
       AND toLower(d.name) IN $candidate_drugs_norm
     RETURN ...
     ```
   - **Comorbidity dose adjustment:**
     ```cypher
     MATCH (d:Drug)-[r:REQUIRES_MONITORING|REQUIRES_DOSE_ADJUSTMENT|CONTRAINDICATED_WITH]->(c:Condition)
     WHERE toLower(c.name) IN $comorbidities_norm
       AND toLower(d.name) IN $candidate_drugs_norm
     RETURN ...
     ```

3. Open Neo4j session via existing pattern ([graph_utils.py:589](../../agent/graph_utils.py#L589)):
   ```python
   async with graph_client.graphiti.driver.session() as session:
       result = await session.run(cypher, params)
       rows = await result.data()
   ```

4. Add a name-normalisation helper (will get reused on write side in C4):
   ```python
   def _norm_name(s: str) -> str:
       s = s.lower().strip()
       s = re.sub(r"\s*\([^)]*\)", "", s)
       s = re.sub(r"\s+\d+\s*mg.*$", "", s)
       return s.strip()
   ```

**Exit gate:** Function callable, returns empty list when no matches (not exception). Unit test against current Neo4j confirms it runs.

---

### B2. Stub clinical_graph_lookup into Stage 4

**File:** [agent/clinical_stages.py](../../agent/clinical_stages.py)

**Steps:**
1. After line 504 (post-`all_chunks.sort`), extract drug names mentioned in retrieved chunks. Cheap heuristic for now: pull `metadata['entities']['medications']` from each chunk and flatten/dedupe. (Better: pass to LLM later, but heuristic is fine for v1.)
2. Call `clinical_graph_lookup(case, candidate_drugs)`:
   ```python
   from .graph_clinical import clinical_graph_lookup
   flags = await clinical_graph_lookup(case, candidate_drugs)
   ```
3. Attach `flags` to the return value of `stage_4_retrieve` (modify return type to `tuple[list[ChunkResult], list[ClinicalFlag]]` OR make it a dataclass — pick one and stay consistent).
4. Emit a `sub_step` event so the UI Pipeline Progress shows it ran:
   ```python
   await emit("sub_step", {
       "stage": 4,
       "detail": f"Graph lookup: {len(flags)} clinical flags",
       "status": "complete",
   })
   ```

**Exit gate:** Pipeline runs without exception. Logs show "Graph lookup: N flags" — N may be 0 with current broken graph; that's expected and informative.

---

### B3. Inject flags into Stage 5 prompt

**File:** [agent/clinical_stages.py](../../agent/clinical_stages.py) `stage_5_synthesize` + [agent/prompts/stage5_synthesis.txt](../../agent/prompts/stage5_synthesis.txt)

**Steps:**
1. In `stage_5_synthesize`, format flags into a structured block prepended to evidence:
   ```python
   def _format_flags(flags: list[ClinicalFlag]) -> str:
       if not flags:
           return "⚠ INTERACTION FLAGS: None detected by knowledge graph."
       lines = ["⚠ INTERACTION FLAGS (graph-verified, MUST be addressed):"]
       for f in flags:
           lines.append(
               f"- {f.flag_type} [{f.severity}]: {f.subject} ↔ {f.object}\n"
               f"    Evidence: \"{f.evidence[:200]}\"\n"
               f"    Source: {f.source_document} (chunk: {f.cpg_chunk_id})"
           )
       return "\n".join(lines)
   ```
2. Prepend `_format_flags(flags)` before `evidence_text` in the user prompt.
3. Update `stage5_synthesis.txt` with a new rule:
   > "If INTERACTION FLAGS are present, EVERY flag MUST be reflected in `recommendations[*].contraindications_checked` or as a STOP/CHANGE recommendation. Do not invent flags not in the list. Do not omit flags from the list."

**Exit gate:** With current (broken) graph, LLM sees "None detected" and proceeds normally. No regression in existing care plans.

---

### B4. Discover schema needs from query failures

**Goal:** Run the wired pipeline against 2-3 fixture cases and observe what's missing.

**Steps:**
1. Pick 2 fixture cases:
   - PAH patient on warfarin (should flag bleeding risk if graph had `INTERACTS_WITH`)
   - HTN patient with sulfa allergy + furosemide candidate (should flag cross-reactivity)
2. Run pipeline. Log:
   - How many edges Cypher matched
   - Which queries returned 0 (and inspect Neo4j manually to see if the data exists in fragmented/wrong form)
3. Document findings in this MD as "Phase B4 schema gaps":
   - Missing properties (e.g., "no severity property anywhere")
   - Missing relation types (e.g., "no CROSS_REACTS_WITH edges exist")
   - Name fragmentation evidence (e.g., "found `Sildenafil`, `sildenafil`, `Sildenafil 50mg` as 3 nodes")

**Exit gate:** Schema gaps documented. Now we know exactly what Phase C must produce.

---

## Phase C — Schema + extraction fixes (1 day)

### C1. Fix chunker root cause (from A2)

Apply the fix scoped in A2. If oversized chunks: enforce a hard upper bound in chunker before they reach graph_builder. If missing category metadata: ensure every chunk gets a default `category: "Reference"` rather than null.

**Exit gate:** Re-run chunker on one CPG, verify all chunks have `category` set and none exceed 8000 chars.

---

### C2. Add category whitelist to graph_builder

**File:** [ingestion/graph_builder.py](../../ingestion/graph_builder.py)

**Steps:**
1. Modify `build_relationship_graph` signature:
   ```python
   async def build_relationship_graph(
       self,
       chunks: List[DocumentChunk],
       document_title: str,
       category_whitelist: Optional[set[str]] = None,
   ) -> Dict[str, Any]:
   ```
2. Default whitelist:
   ```python
   DEFAULT_CATEGORY_WHITELIST = {
       "Treatment", "Supportive Treatment", "Assessment",
       "Diagnosis", "Special Populations", "Prevention",
   }
   ```
3. In the loop, skip chunks whose category is outside the whitelist; log skipped count.

**Exit gate:** Dry-run shows ~50-60% of chunks skipped on a typical CPG.

---

### C3. Promote chunk_index → cpg_chunk_id (UUID)

**File:** [ingestion/graph_builder.py](../../ingestion/graph_builder.py)

**Steps:**
1. Modify `_extract_triples_with_llm` to accept and forward `chunk_id: str` (UUID from NeonDB).
2. Modify `_write_triples_to_neo4j` Cypher:
   ```cypher
   ON CREATE SET
       r.cpg_chunk_id = $cpg_chunk_id,    -- new primary citation key
       r.chunk_index = $chunk_index,       -- keep for backward compat
       ...
   ```
3. Caller (in `ingest.py`) passes the NeonDB chunk UUID — should already be available after the chunk is inserted into Postgres.

**Exit gate:** Test triple extraction on 1 chunk, verify Neo4j edge has `cpg_chunk_id` matching NeonDB.

---

### C4. Name normalisation (write + read symmetric)

**Files:** [ingestion/graph_builder.py](../../ingestion/graph_builder.py) + `agent/graph_clinical.py` (from B1)

**Steps:**
1. Move `_norm_name` helper to a shared module: new `agent/graph_normalise.py`. Both ingestion and query path import from it.
2. In `_write_triples_to_neo4j`, normalise before MERGE:
   ```python
   subject_norm = _norm_name(subject)
   object_norm = _norm_name(obj)

   cypher = f"""
   MERGE (s:{subject_label} {{name_normalised: $subject_norm}})
       ON CREATE SET s.name = $subject_original
   MERGE (o:{obj_label} {{name_normalised: $object_norm}})
       ON CREATE SET o.name = $object_original
   ...
   """
   ```
3. Add Neo4j index for fast lookup:
   ```cypher
   CREATE INDEX drug_norm_name IF NOT EXISTS FOR (d:Drug) ON (d.name_normalised);
   CREATE INDEX cond_norm_name IF NOT EXISTS FOR (c:Condition) ON (c.name_normalised);
   ```
4. Update `clinical_graph_lookup` (B1) to normalise inputs with the same helper.
5. Change `ON MATCH` evidence handling — append instead of preserve-first:
   ```cypher
   ON CREATE SET r.evidence_list = [$evidence], r.cpg_chunk_ids = [$cpg_chunk_id]
   ON MATCH SET
       r.evidence_list = r.evidence_list + $evidence,
       r.cpg_chunk_ids = r.cpg_chunk_ids + $cpg_chunk_id
   ```

**Exit gate:** Ingest a chunk twice with slight name variations ("Sildenafil 50mg" then "sildenafil"); verify Neo4j has 1 node with both evidences in `evidence_list`.

---

### C5. Expand relation taxonomy + properties

**File:** [ingestion/graph_builder.py](../../ingestion/graph_builder.py) `CLINICAL_RELATION_TYPES` + extraction prompt

**Steps:**
1. Add to `CLINICAL_RELATION_TYPES`:
   ```python
   "INTERACTS_WITH",            # supersedes CONTRAINDICATED_WITH for drug-drug
   "CROSS_REACTS_WITH",         # for allergens
   "REQUIRES_DOSE_ADJUSTMENT",  # comorbidity-triggered
   ```
2. Update extraction prompt to ask LLM to extract these as separate edge properties when present in source text:
   - `severity`: MAJOR / MODERATE / MINOR (controlled vocabulary — enforce in prompt)
   - `dosage`: free text dosing instruction
   - `trigger`: e.g., "eGFR<30", "age>65" (when REQUIRES_DOSE_ADJUSTMENT)
   - `frequency`: e.g., "common", "rare" (when CAUSES adverse event)
3. In `_write_triples_to_neo4j`, persist these properties on the edge.
4. Add validation: if LLM returns a `severity` outside the controlled vocabulary, normalise it (e.g., "high" → "MAJOR", "absolute contraindication" → "MAJOR") via a small mapping dict.

**Exit gate:** Manually inspect 5 newly-extracted edges from a Treatment chunk; verify severity/dosage/trigger populated where the source text supports them.

---

### C6. Add icd11_code via post-ingestion Cypher batch

**File:** new `ingestion/enrich_icd_codes.py`

**Steps:**
1. Read the DDx ICD-11 lookup table (`ddx/` data — already used by `search_ddx`).
2. For each (icd_code, condition_name, synonyms) tuple, run:
   ```cypher
   MATCH (c:Condition)
   WHERE c.name_normalised IN $name_variants
   SET c.icd11_code = $icd_code
   ```
3. Run as a one-off script after each ingestion batch.

**Exit gate:** `MATCH (c:Condition) WHERE c.icd11_code IS NOT NULL RETURN count(c)` returns >0; spot-check 3 codes are correctly linked.

---

## Phase D — Pilot re-ingestion (0.5 day)

### D1. Clear Neo4j (graph data only)

**Steps:**
1. Confirm A1 backup exists.
2. Run:
   ```cypher
   MATCH (n) DETACH DELETE n;
   ```
3. Re-create indices (from C4).
4. Verify counts are 0.

---

### D2. Re-ingest ONE CPG

**Steps:**
1. Pick HTN CPG (clinically dense, touches many comorbidities).
2. Run ingestion via updated CLI:
   ```bash
   python -m ingestion.ingest --document <htn_path> --graph-only --categories Treatment,Assessment,Special_Populations
   ```
   (You may need to add the `--graph-only` flag to `ingest.py` — small change to skip chunking/embedding when chunks already in NeonDB.)
3. Run `enrich_icd_codes.py`.
4. Spot-check Neo4j:
   ```cypher
   MATCH (d:Drug)-[r]-(other) RETURN d.name, type(r), other.name LIMIT 20;
   MATCH ()-[r]-() WHERE r.cpg_chunk_id IS NULL RETURN count(r);  -- should be 0
   ```

---

### D3. Validate Cypher returns clean rows

Re-run `clinical_graph_lookup` from B1 against the pilot graph with the fixture cases from B4.

**Exit gate:** All 3 fixture cases return non-empty, structured flags with non-null `cpg_chunk_id`. If any case still returns empty, debug before proceeding.

---

## Phase E — Fixture validation (0.5 day)

### E1. Three fixture patient cases through full pipeline

| Case | Setup | Expected flag |
|---|---|---|
| 1 | HTN, on amlodipine + lisinopril, candidate ramipril | INTERACTION (RAAS double-block) |
| 2 | HTN + CKD eGFR 25, candidate spironolactone | DOSE_ADJUSTMENT (potassium risk) |
| 3 | HTN + sulfa allergy, candidate hydrochlorothiazide | ALLERGY_CROSS (sulfa-derived) |

### E2. Verify in Doctor UI

Run each case end-to-end. Check `CarePlanSection.jsx` rendering — flags should appear in the Care Plan output with citations linking to NeonDB chunks.

### E3. Sign-off gate

**DO NOT proceed to Phase F unless all 3 fixtures pass.** If 1 fails, root-cause it (likely missing relation type or extraction prompt issue) and iterate Phase C5.

---

## Phase F — Full backfill (1 day code, ~1 day batch)

### F1. Re-ingest remaining CPGs

**Steps:**
1. List all CPG documents in NeonDB:
   ```sql
   SELECT id, title FROM documents ORDER BY title;
   ```
2. Process in batches of 3-5 to avoid Bedrock rate limits:
   ```bash
   for cpg in $(cat cpg_list.txt); do
     python -m ingestion.ingest --document "$cpg" --graph-only --categories Treatment,Assessment,Special_Populations
     sleep 60
   done
   ```
3. Run `enrich_icd_codes.py` once at the end.

### F2. Monitor

- Track LLM call count + cost vs. A3 estimate.
- Track extraction errors per CPG; investigate any CPG with >20% chunk failure rate.

### F3. Spot-check

Pick 5 random patient cases (different CPG combinations) — run end-to-end, verify INTERACTION FLAGS appear sensibly in UI.

---

## Rollback plan

If Phase F produces a worse graph than baseline:
1. `MATCH (n) DETACH DELETE n;`
2. Restore from A1 backup: `cypher-shell < kg_backup_<date>.cypher`
3. Revert code changes via `git revert`.
4. Pipeline returns to current (graph-disabled) state — no regression because B2's lookup gracefully returns empty list.

---

## Open questions to resolve before starting

1. **Bedrock budget** — confirm with stakeholder before Phase A3. Hard cap?
2. **Graphiti episodes** — clearing Neo4j wipes Graphiti's episode store too. Acceptable? (Probably yes — episodes weren't being used for clinical lookup anyway.)
3. **`--graph-only` ingestion flag** — does `ingest.py` already support re-running graph build against existing NeonDB chunks without re-chunking? If not, Phase C needs a small CLI patch.
4. **LLM model for extraction** — keep hardcoded Bedrock Llama 3.3 70B, or switch to STAGE*_LLM_* env override pattern? Latter is more consistent with rest of pipeline.
5. **Severity vocabulary** — confirm MAJOR/MODERATE/MINOR is the right axis (vs. say, ABSOLUTE/RELATIVE/CAUTION). Pick now, hard to change later.

---

## Phase A artifacts (fill in as you go)

- A1 backup file: `_______________________`
- A1 baseline counts: nodes `____`, edges `____`
- A2 chunker root cause: `_______________________`
- A3 1-CPG cost: `$____` → estimated full-batch: `$____`

## Phase B4 schema gaps (fill in after wiring discovery)

- Missing properties: `_______________________`
- Missing relation types: `_______________________`
- Name fragmentation examples: `_______________________`
