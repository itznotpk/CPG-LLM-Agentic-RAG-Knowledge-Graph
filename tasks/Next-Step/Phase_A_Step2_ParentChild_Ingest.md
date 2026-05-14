# Phase A — Step 2: Parent-Child Re-ingest (NeonDB + KG)

> **Position in rollout:** Step 2 of 3. Runs **after** Step 1 (synthesis cap fixes — see `Phase_A_Step1_Synthesis_Fixes_Now.md`) and **before** Step 3 (performance pass — see `Phase_A_Step3_Performance_Pass.md`).
> **Status:** Option A selected — H2 re-chunk with full re-ingest. **Code complete — A-1 through A-10 implemented and verified (2026-05-14). Remaining: A-11 (manual ICD-11 scope) and A-12–A-15 (re-ingest / KG rebuild / smoke test).**
> **Recommendation:** Proceed with H2 re-chunk. Cleanest single-source-of-truth — same H2 UUID serves retrieval and KG citation.
> **Trigger:** Query — "if an answer falls in the middle of a 6k sub-chunk split, does the system know what's before and after?"

---

## 1. Root Problem Summary

**Current state:** Every section markdown file (e.g., `section-3-diagnosis.md`, 1,266 lines, ~51k chars) is stored as **one H1 chunk** in NeonDB with one embedding. The 6k sub-chunking in `graph_builder.py` is ephemeral (KG extraction only) and never stored. This creates three compounding problems:

| # | Problem | Impact |
|---|---------|--------|
| P1 | **Noisy H1 embedding** | One vector covers 5 clinical sub-topics → poor retrieval precision for specific questions |
| P2 | **No shared chunk ID between NeonDB and Neo4j** | KG triples store an integer `chunk_index`; NeonDB stores a UUID `chunk_id` → no clickable citation path |
| P3 | **Context lost at 6k sub-chunk boundaries** | 500-char overlap is too narrow for multi-paragraph clinical recommendations |

---

## 2. Selected Path — H2 Re-chunk with Full Re-ingest

> **Re-embedding is mandatory.** The existing 51k+ H1 vectors were built from incomplete input — `text-embedding-3-small` truncates at ~8,191 tokens (~32k chars), so the late portion of every oversized H1 was never represented in its vector. No retrieval-time trick can fix a vector that was built from incomplete input.

**Decision: Option A / H2 re-chunk.**
- New CPGs are about to be added — the re-ingest pass happens anyway. Cleanest to handle it as one operation.
- Single source of truth: the same H2 UUID is both the embedded vector and the KG citation target.
- The H1 parent row is kept (unembedded) so the synthesis stage can still pull full context.

**Readiness check after Step 1:** Step 1 completion is sufficient to begin Step 2 coding because Stage 5 no longer hard-truncates evidence, has parent-context budgeting, dedupes repeated parents, and refuses oversized prompts. It is **not** sufficient to run re-ingest yet. Re-ingest should only start after the Step 2 schema, markdown alignment guide compliance, chunker, parent-only reference parsing, `cross_ref` metadata parsing, ingestion persistence, H2 retrieval, parent/cross-ref resolver, KG extraction, and ICD-11 scope checks are implemented and dry-run verified.

---

## 3. H2 Re-chunking Architecture

### Architecture

```
markdown/Prevention-Diagnosis-Management-of-IE/section-3-diagnosis.md
│
│  NeonDB — Two levels stored
│
├── H1 PARENT chunk (stored for context, NOT embedded)
│   chunk_id: "a1b2-h1"   content: full 51k chars   embedding: NULL
│   chunk_level: "h1"      parent_chunk_id: NULL
│
├── H2 CHILD chunk — 3.1 Clinical evaluation
│   chunk_id: "c3d4-3.1"  content: ~3,000 chars     embedding: [vector]
│   chunk_level: "h2"      parent_chunk_id: "a1b2-h1"
│
├── H2 CHILD chunk — 3.2 Investigations
│   chunk_id: "e5f6-3.2"  content: ~7,000 chars     embedding: [vector]
│   chunk_level: "h2"      parent_chunk_id: "a1b2-h1"
│
├── H2 CHILD chunk — 3.3 Imaging
│   chunk_id: "g7h8-3.3"  content: ~10,000 chars    embedding: [vector]
│   chunk_level: "h2"      parent_chunk_id: "a1b2-h1"
│
└── H2 CHILD chunk — 3.4 Diagnostic criteria (Duke)
    chunk_id: "i9j0-3.4"  content: ~8,000 chars     embedding: [vector]
    chunk_level: "h2"      parent_chunk_id: "a1b2-h1"

  Neo4j — Triples extracted from H2 child chunks
  └── (:Condition)-[:ASSESSED_BY]->(:DiagnosticTool)
        r.cpg_chunk_id = "g7h8-3.3"  ← same UUID as NeonDB H2 chunk → direct citation
```

### Query Path (Parent-Child Retrieval)

```
User query: "What are the Duke criteria for diagnosing IE?"
│
├─ Step 1: Embed query → cosine search against H2 child embeddings only (chunk_level = 'h2')
│
├─ Step 2: Top-K child hits
│          → "i9j0-3.4" (3.4 Diagnostic criteria) similarity: 0.91  ← precise hit
│          → "c3d4-3.1" (3.1 Clinical evaluation)  similarity: 0.61
│
├─ Step 3: For each child hit, fetch its H1 parent by parent_chunk_id
│          → "a1b2-h1" (full section-3-diagnosis, 51k chars)
│
└─ Step 4: LLM receives:
           [CHILD — citation source]  chunk: "i9j0-3.4" | "Modified Duke criteria include..."
           [PARENT — full context]    chunk: "a1b2-h1"  | (full section 3 for synthesis)
```

### NeonDB Schema Change

Migration file: `sql/migrations/006_chunk_level_and_cleanup.sql`

**Add columns required for parent-child architecture:**

```sql
-- Add chunk level discriminator (h1 = parent, h2 = child, h1_leaf = no H2s present)
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_level TEXT NOT NULL DEFAULT 'h1_leaf';

-- Add child position inside parent for build_parent_context() window slicing
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS start_char INTEGER;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS end_char   INTEGER;

-- Index to restrict retrieval to embedded H2 children only
CREATE INDEX IF NOT EXISTS idx_chunks_level ON chunks (chunk_level);
```

**Drop dead columns — confirmed unused by markdown ingestion pipeline (2026-05-14):**

| Column | Why dropped |
|--------|-------------|
| `is_recommendation` | Never written by markdown ingestion path. Only existed in old PDF/CPG parser path (`cpg_parser.py`) which is no longer used. `clinical_stages.py` has zero reads from this column. |
| `is_table` | Same — written only by PDF parser, never queried from the column. Index `idx_chunks_tables` is never hit. |
| `is_algorithm` | Same — written only by PDF parser, never queried from the column. |
| `structured_content` | Table JSON duplicated inside `metadata->>'structured_content'`. The retrieval path in `db_utils.py` reads only `metadata`. This column is never SELECTed anywhere. |
| `section_hierarchy` | `TEXT[]` column that duplicates `metadata->>'context_path'`. Step 2 expresses hierarchy via `parent_chunk_id` FK — this column becomes redundant. `get_chunk_with_parent_context()` SQL function is updated to remove the reference. |

```sql
-- Drop dedicated boolean/JSONB columns that duplicate metadata and are never queried
ALTER TABLE chunks DROP COLUMN IF EXISTS is_recommendation;
ALTER TABLE chunks DROP COLUMN IF EXISTS is_table;
ALTER TABLE chunks DROP COLUMN IF EXISTS is_algorithm;
ALTER TABLE chunks DROP COLUMN IF EXISTS structured_content;
ALTER TABLE chunks DROP COLUMN IF EXISTS section_hierarchy;

-- Drop indexes that no longer have backing columns
DROP INDEX IF EXISTS idx_chunks_recommendations;
DROP INDEX IF EXISTS idx_chunks_tables;
DROP INDEX IF EXISTS idx_chunks_algorithms;
```

Also update `schema.sql` to reflect final clean state (remove dropped columns, add new ones, update `get_chunk_with_parent_context()` to remove `section_hierarchy` reference and add `chunk_level`).

Also update `ingest.py` INSERT statement to remove the 5 dropped columns and add `chunk_level`, `start_char`, `end_char`, `parent_chunk_id`.

Vector search in [agent/db_utils.py:369-522](../../agent/db_utils.py): filter `WHERE chunk_level = 'h2'` for retrieval; fetch `WHERE chunk_id = $parent_chunk_id` for context.

### Markdown Alignment Inputs

Before re-ingest, align markdown against the current consolidated guide:

- [Markdown_Standardization_And_Cross_Reference_Guide.md](./Markdown_Standardization_And_Cross_Reference_Guide.md): controls standard section filenames, exactly-one-H1-per-file structure, H1/H2/H3/H4 hierarchy, H2 child boundaries, table/figure demotion, parent-only reference block placement, `cross_ref` markers, cross-reference audit rules, and cleanup before ingestion.

The older [CPG-RAG-Standardization-Guide.md](../../Reading%20Docs/CPG-RAG-Standardization-Guide.md) is useful only for legacy evidence-tag and author-time `<!-- METADATA -->` conventions. Its older H3-child chunking and overlap-reattachment model is superseded by this Step 2 plan:

```text
Current Phase A Step 2 retrieval unit:
  H2 chunks only (`chunk_level = 'h2'`)

H3/H4 headings:
  stay inside the owning H2 unless an oversized H2 is internally split;
  even then, persisted retrieval rows remain `chunk_level = 'h2'`

Legacy overlap blocks:
  may still be stripped for Grade/Level/Abbreviation dedupe,
  but shared clinical references should now use `parent_only_reference`
  when they must support synthesis without becoming vector hits
```

There is no conflict inside the consolidated guide:

```text
Parent-child guide:
  structures the current H1 parent and its H2/H3/H4 content

Cross-reference guide:
  links to content outside the current H1 parent

Shared rule:
  if referenced content is already copied into parent_only_reference,
  do not add a cross_ref marker
```

#### Markdown metadata contract

The markdown format now introduces two metadata paths that must be kept distinct:

```text
Author-time document metadata:
  `<!-- METADATA ... -->` blocks are parsed into `documents.metadata`.
  Keep existing category/use_case/patient_input/output style fields here.

Ingestion-time chunk metadata:
  `chunks.metadata` is generated by the chunker and ingestion code.
  Expected fields include doc_title, h2_title, optional h3_title for
  oversized H2 splits, context_path, evidence_grades, evidence_levels,
  cross_refs, and parent_chunk_id on child rows.
```

Do not encode retrieval control fields manually in markdown metadata blocks. `chunk_level`, `start_char`, `end_char`, and `parent_chunk_id` are ingestion outputs. The only manual metadata-like syntax authors should add for Step 2 is:

```text
parent-only context:
  <!-- parent_only_reference_start --> ... <!-- parent_only_reference_end -->

cross-file reference metadata:
  <!-- cross_ref target_file="..." target_heading="..." target_kind="..." -->
```

Use the current repo examples as alignment references before ingestion:

```text
Anaesthesia Medication Safety:
  standard section filenames such as section-0-appendix.md
  one H1 parent per file
  H2 retrievable clinical children
  H3/H4 nested details and table groups
  parent_only_reference blocks for shared TML/CVC examples

Atrial Fibrillation (2012) Section 3:
  one H1 parent
  H2 child sections
  H3/H4 nested clinical details
```

### Chunker Change

**File:** [ingestion/chunker.py:81-318](../../ingestion/chunker.py)

Add `##` (H2) splitting to `MarkdownHeaderTextSplitter`. For each markdown file:
- Require standard `section-{number}-{slug}.md` naming for newly aligned markdown files.
- Require exactly one `# H1` parent per markdown file; remove, demote, or convert duplicate `#` headings before ingestion.
- Pass 1: split at `#` → H1 parent chunk (stored, `embedding=NULL`)
- Pass 2: split at `##` within each H1 → H2 child chunks (stored, embedded)
- Keep `###` numbered subsections such as `3.1.1`, `3.1.2`, and `3.1.3` inside the owning H2 child.
- Demote Table/Figure labels to plain prose unless they sit inside a `parent_only_reference` block; this keeps tables inside the owning H2/H3 text instead of turning them into metadata-bearing headings.
- Fallback: if no H2 headers exist, H1 chunk becomes both parent and leaf (`chunk_level='h1_leaf'`, embedded)
- Cap: H2 chunk > 8,000 chars means split at `###`, but persist each split piece as `chunk_level='h2'` with the same H1 parent. Treat `h3_title` as descriptive metadata only, not as a new retrievable chunk level.

Cleanup before parsing: run `audit_markdown.py` folder-by-folder, remove redundant `---` separators, normalize excessive blank lines, keep table labels directly above tables, validate/sync `cross_ref.target_heading`, confirm exactly one H1 per file, and remove temporary run/log files from the repo.

Heading levels are based on document hierarchy, not visual size:

```text
# Section 3                         H1 parent
## 3.1 Primary Prevention           H2 child
### 3.1.1: Information Required     H3 inside 3.1
Table 7: Prevalence...              plain table label inside 3.1
Table 1A: Points For Men            plain table label inside the same H2/H3 context
```

#### Parent-only shared references

Use this rule for shared or overlap material such as cross-cutting tables, criteria lists, dosing reference tables, and appendix-style content that should support synthesis but should not become an independent vector hit:

```text
Retrievable children = clinically specific H2 sections
Parent context = full H1, including shared/overlap tables
Parent-only references = visible to synthesis, invisible to direct child retrieval
```

Recommended markdown marker:

```md
<!-- parent_only_reference_start -->
### Shared Reference: Modified Duke Criteria

| Criteria | Details |
|---|---|
| Major criteria | ... |
| Minor criteria | ... |
<!-- parent_only_reference_end -->
```

Chunker behavior:
- Keep the marked block inside the H1 parent content.
- Do not emit the marked block as a retrievable H2 child or embed it separately.
- If a nearby H2 child from the same H1 is retrieved, include the parent context so the marked reference is still visible to Stage 5 synthesis.
- Prefer `###` or lower headings inside the marked block. Avoid `##` inside the block unless the parser removes/masks parent-only blocks before H2 splitting.

#### Cross-reference markers

Use `cross_ref` markers only when the referenced content lives outside the current H1 parent. Do not add `cross_ref` if the target table/form/appendix excerpt is already copied into the current H1 using `parent_only_reference`.

Example:

```md
For estimation of global CVD risk, refer to Section 3: Estimation of Global CVD Risk.
<!-- cross_ref target_file="section-3-estimation-of-global-cvd-risk.md" target_heading="Section 3: Estimation of Global CVD Risk" target_kind="h1_section" -->
```

Allowed `target_kind` values:

```text
h1_section
h2_section
algorithm_flowchart
appendix
```

Chunker/ingestion behavior:
- Keep the visible human sentence in the child text.
- Parse the `cross_ref` marker into `cross_refs` metadata on the H2 child chunk where the "refer to..." sentence appears.
- Strip the marker itself from embedding text and normal LLM prompt text.
- Optionally aggregate cross-refs onto the H1 parent for audit/debugging, but retrieval must follow the child metadata.

Retrieval behavior:
- Retrieve the primary H2 child normally.
- Fetch its own H1 parent context.
- If `child.metadata.cross_refs` exists, resolve the target evidence before Stage 5 synthesis.
- For `h1_section`, prefer the best matching H2 under the target H1; use capped/windowed target H1 only when a specific H2 cannot be resolved.
- Do not blindly attach two full H1 parents by default.

### KG Extraction Change

Read H2 child chunks from NeonDB instead of H1:
```sql
SELECT chunk_id, content, metadata FROM chunks
WHERE document_id = $1 AND chunk_level = 'h2'
  AND metadata->>'category' = ANY($category_whitelist)
ORDER BY chunk_index;
```

IE section-3: was 1 H1 → 9 sub-chunks (51k ÷ 6k). Now: 4 H2 → 0–2 sub-chunks each.

### Trade-offs

| Decision | Trade-off |
|----------|-----------|
| Re-ingest NeonDB | Existing H1 chunk_ids change → any hardcoded UUID references break. Acceptable if vector store not in production. |
| H1 not embedded | H1 content unreachable by semantic search; only loadable via parent_chunk_id join. |
| Neo4j re-ingest | Phase D1 `DETACH DELETE` + re-extraction from H2 chunks required. Old `chunk_index` integers abandoned. |

### Implementation Steps After Step 1 Completion

Step 1 must be merged first because Stage 5 now accepts larger evidence packs and has the `build_parent_context()` hook that Step 2 will expand. Step 1 completion is enough to begin Step 2 implementation, but it is not enough to run re-ingest immediately. Re-ingest starts only after A-1 through A-11 are implemented/verified.

Status meaning:

```text
[x]       Done / double-checked
[done]    Already resolved in Step 1
[ready]   Gap confirmed, code not yet written — implement now
[manual]  Needs reviewer or teammate confirmation
[tomorrow] Run during ingestion/rebuild
```

**Codebase audit completed 2026-05-14.** Every gap below is verified against current file state.

Execute Step 2 in this order:

| Status | Step | Action | Files / Area | Current State (audited 2026-05-14) | Exit Gate |
|--------|------|--------|--------------|-------------------------------------|-----------|
| [x] | A-0 | Step 1 prerequisites confirmed: tiered budgets, token counting, whole-chunk formatting, parent dedupe, prompt-size guard, `build_parent_context()` stub present. | `agent/clinical_stages.py:582` | Confirmed — `build_parent_context()` exists at line 582, currently a stub with comment "Step 2 will expand this". All Step 1 guards in place. | Complete. Gates Step 2 coding only, not re-ingest. |
| [x] | A-1 | **Schema migration:** Write `sql/migrations/006_chunk_level_and_cleanup.sql`. Add `chunk_level TEXT NOT NULL DEFAULT 'h1_leaf'`, `start_char INTEGER`, `end_char INTEGER`, index on `chunk_level`. Drop 5 dead columns: `is_recommendation`, `is_table`, `is_algorithm`, `structured_content`, `section_hierarchy` (see §3 NeonDB Schema Change for full SQL and rationale). Update `schema.sql` to reflect clean final state. | `sql/migrations/006_chunk_level_and_cleanup.sql`, `sql/schema.sql` | `chunk_level`, `start_char`, `end_char` all MISSING from schema. Dead columns all present — confirmed never written by markdown ingestion path. `parent_chunk_id` FK already exists (`schema.sql:50`). | Migration runs clean; `\d chunks` shows new columns, dead columns gone. |
| [x] | A-2 | **Chunker H2 splitting:** Update `MarkdownChunker` to emit H1 parent chunk (no embedding) + H2 child chunks (embedded). Add `("##", "h2_title")` to `headers_to_split_on`. Add `chunk_level` field to `DocumentChunk` dataclass. Fallback: if no `##` exists, emit as `h1_leaf` (embedded). Cap: H2 > 8,000 chars splits at `###`, but persisted split pieces still use `chunk_level='h2'`; `h3_title` is descriptive metadata only. | `ingestion/chunker.py:38-55` (DocumentChunk), `ingestion/chunker.py:99-108` (splitter config) | Currently splits on H1 only (`chunker.py:99-103`). `DocumentChunk` has `start_char`/`end_char` but NO `chunk_level` field. H2 splitting does not exist. | Unit parse of IE section-3 shows 1 H1 parent + 4 H2 children; H3/H4 content stays inside owning H2. |
| [x] | A-3 | **Parent-only reference blocks:** Before H2 splitting, detect `<!-- parent_only_reference_start -->` ... `<!-- parent_only_reference_end -->` blocks. Keep them inside H1 parent content; mask/remove them before H2 splitting so they are not emitted as child chunks. | `ingestion/chunker.py` | The existing `_strip_overlap_blocks()` method (`chunker.py:283`) handles a similar pattern — extend it or add parallel method for `parent_only_reference` blocks. No current handling exists for this marker. | Marked shared tables present in H1 parent, absent from H2 child embeddings. |
| [x] | A-4 | **Cross-ref marker parsing:** Parse `<!-- cross_ref target_file="..." target_heading="..." target_kind="..." -->` comments. Store parsed list as `metadata.cross_refs` on the H2 child chunk containing the reference sentence. Strip marker from embedding/prompt text. | `ingestion/chunker.py` | No `cross_ref` parsing exists anywhere. The regex infrastructure in `_strip_overlap_blocks()` can be used as a template. | H2 child has clean content; `metadata.cross_refs` populated when marker present. |
| [ready] | A-4b | **Markdown metadata contract:** Tailor the markdown workflow to the consolidated guide before re-ingest. Run `audit_markdown.py` on each target folder; verify exactly one H1, H2-only retrieval boundaries, Table/Figure demotion, `parent_only_reference` placement, and `cross_ref.target_file/target_heading/target_kind` validity. Confirm author-time `<!-- METADATA -->` fields remain document metadata, while `cross_refs`, evidence tags, `h2_title`, optional `h3_title`, and parent IDs are ingestion-time chunk metadata. | `audit_markdown.py`, `tasks/Next-Step/Markdown_Standardization_And_Cross_Reference_Guide.md`, target `markdown/<CPG>/` folders | Needed because the markdown format now adds metadata-bearing markers. The old `Reading Docs` guide still mentions H3 child chunks and overlap reattachment, which must not override the H2 plan. | Dry-run audit has no R1/R3/R4/R8 blockers; R5 advisory refs are reviewed manually; a sample chunk dry-run shows correct `cross_refs`, evidence metadata, and no Table/Figure headings promoted into retrievable chunks. |
| [x] | A-5 | **Ingestion persistence:** Update `_save_to_postgres` INSERT in `ingest.py` to: (1) remove 5 dropped columns from INSERT list, (2) add `chunk_level`, `start_char`, `end_char`, `parent_chunk_id` to INSERT, (3) store H1 parent with `embedding=NULL`, (4) store H2 children with `parent_chunk_id` pointing to their H1. | `ingestion/ingest.py:888-912` | Current INSERT includes 5 dead columns and is MISSING `chunk_level`, `start_char`, `end_char`, `parent_chunk_id`. `start_char`/`end_char` exist on `DocumentChunk` object but are discarded before DB write. | Re-ingest of one CPG: `SELECT chunk_level, count(*) FROM chunks WHERE document_id=X GROUP BY chunk_level` returns `h1: 1, h2: N`. |
| [x] | A-6 | **Protect scope metadata on re-ingest UPSERT:** Patch the `documents` UPSERT in `ingest.py` to `ON CONFLICT (source) DO UPDATE SET title=EXCLUDED.title, content=EXCLUDED.content, metadata=EXCLUDED.metadata, updated_at=NOW()` — never touch `icd11_scope`, `scope_verified`, `verified_at`, `verified_by`. | `ingestion/ingest.py` (documents UPSERT) | Safety check required before A-13. Current UPSERT behaviour not confirmed safe — must verify and patch before running re-ingest. | Dry-run re-ingest of one verified CPG: `scope_verified` remains TRUE, `icd11_scope` unchanged. |
| [x] | A-7 | **Retrieval filter:** Add `chunk_level: str = 'h2'` parameter to `vector_search()` and `hybrid_search()`. Add `AND c.chunk_level = $N` to WHERE clause in both the filter branch (inline SQL) and update `match_chunks()` / `hybrid_search()` SQL functions in `schema.sql`. | `agent/db_utils.py:369-522`, `sql/schema.sql:98-194` | Neither function has a `chunk_level` parameter or filter. Without this, retrieval returns unembedded H1 parents (which have NULL embedding) and will silently return zero results or crash. | `vector_search()` called with default args returns only `chunk_level='h2'` rows. |
| [x] | A-8 | **Parent context fetch + cross-ref resolution:** Expand `build_parent_context()` from its current stub to: (1) fetch H1 parent from DB using `parent_chunk_id`, (2) apply window slicing if parent > `_PARENT_CHAR_LIMIT` using `child.start_char`/`child.end_char`, (3) resolve `child.metadata.cross_refs` if present. Add `parent_content: Optional[str]` and `chunk_level: Optional[str]` to `ChunkResult` model. | `agent/clinical_stages.py:582-589`, `agent/models.py:59-73`, `agent/tools.py` | `build_parent_context()` at line 582 is explicitly a stub — comment reads "Step 2 will expand this". `ChunkResult` model has no `parent_content`, `chunk_level`, `start_char`, or `end_char` fields. | Stage 5 evidence log shows `[CHILD]` citation + `[PARENT]` context block; cross-ref evidence attaches when `cross_refs` present. |
| [ready] | A-8b | **Cross-ref resolver verification:** Verify that parsed `metadata.cross_refs` is not only stored but actually followed before Stage 5. For each target kind, fetch the target H1/H2 by `target_file` and `target_heading`, attach a capped referenced evidence block, and avoid attaching two full H1 parents by default. Also update `get_chunk_with_context_tool()` if it still expects removed fields such as `section_hierarchy`. | `agent/clinical_stages.py`, `agent/db_utils.py`, `agent/tools.py`, `sql/schema.sql` | Current code should be checked against the new markdown metadata contract because storing `cross_refs` alone is not enough. | Smoke query with a known `cross_ref` shows child evidence, own parent context, and referenced target evidence in the Stage 5 evidence pack; no stale `section_hierarchy` error from the context tool. |
| [x] | A-9 | **KG extraction reads H2 chunks:** Update `build_relationship_graph()` in `graph_builder.py` to query `WHERE chunk_level = 'h2'` instead of all chunks. Keep H2 UUID as `cpg_chunk_id` on each emitted triple. | `ingestion/ingest.py`, `ingestion/graph_builder.py` | Currently reads all chunks (no level filter). After re-ingest, H1 parents will appear in the chunk list and would produce noisy triples covering entire sections. | New triples all have `cpg_chunk_id` resolvable to an H2 row in `chunks`. |
| [x] | A-10 | **KG sub-window context bands:** Rewrite `_split_into_subchunks()` to return windowed dicts with `before`, `focus`, `after`, `focus_start`, `focus_end`, `is_first`, `is_last`. Update triple-extraction prompt to label regions. Stamp `subchunk_focus_start` on each triple. Increase overlap/band from 500 → 2,000 chars (bands replace overlap). | `ingestion/graph_builder.py:534-564` (current: returns `List[str]`, overlap=500) | Current signature: `_split_into_subchunks(self, text, max_chars=6000, overlap=500) -> List[str]`. Returns plain strings, no position info, no context bands. Full rewrite required per §6. | `pytest tests/test_graph_builder_subwindow.py` passes; triple metadata contains `subchunk_focus_start`. |
| [manual] | A-11 | Run ICD-11 scope pipeline for any newly added CPGs, then clinician review and verification. | `classify_cpg_scope.py`, `verify_cpg_scope.py` | Existing 16 CPGs already verified. Required only for new CPGs added before re-ingest. | All documents: `cardinality(icd11_scope) > 0` AND `scope_verified = TRUE`. |
| [tomorrow] | A-12 | Dry-run re-ingest of one small CPG (Erectile-Dysfunction, 6 sections). | CLI | Blocked on A-1 through A-10 plus A-4b and A-8b complete. | `SELECT chunk_level, count(*) FROM chunks WHERE document_id=X GROUP BY chunk_level` shows `h1: N, h2: M`. Retrieval returns H2 hits. Parent context resolves. Sample chunks contain expected evidence metadata and `cross_refs`; marker comments are absent from embedded/prompt text. |
| [tomorrow] | A-12b | **Metadata dry-run gate:** Before full re-ingest, inspect sample rows from the A-12 CPG to confirm markdown-derived metadata shape. | SQL / CLI | Runs immediately after A-12. | Child rows have `chunk_level='h2'`, `metadata.h2_title`, optional descriptive `metadata.h3_title` only for oversized splits, `metadata.evidence_grades/evidence_levels` when tags exist, and `metadata.cross_refs` where markers exist. H1 rows keep parent-only reference content but are not embedded. |
| [tomorrow] | A-13 | Full re-ingest all CPGs with H1/H2 parent-child chunks. | CLI | Blocked on A-12 clean. | Expected H2 count across corpus. No verified scope metadata lost. |
| [tomorrow] | A-14 | Backup Neo4j → wipe old graph → rebuild KG from new H2 chunks. | Cypher, `ingest --graph-only` | Blocked on A-13 complete. Previous backup at `backups/kg_backup_2026-05-12.cypher`. | Typed clinical relations present; `MATCH ()-[r]->() RETURN type(r), count(r)` shows no Graphiti residue. |
| [tomorrow] | A-15 | End-to-end smoke test: Duke criteria IE, cross-ref resolution, citation click-through, parent context inclusion, prompt budget logs. | Clinical pipeline | Blocked on A-14 clean. | Correct answer; H2 citation resolves; referenced evidence attaches; no prompt oversize. |

### 3.1 ICD-11 Scope Wiring for New CPGs

Existing 16 CPGs already have `documents.icd11_scope` populated and `scope_verified = TRUE` (see `tasks/Done/STEP_02_extend_documents.md`). For **new CPG markdown directories** added before this re-ingest, the same pipeline must be run so Stage 3 routing works:

```
markdown/<new-cpg-name>/ ─┐
                          ├─►  ingest.py (creates documents row, icd11_scope = '{}')
                          │
                          ├─►  classify_cpg_scope.py
                          │    └─ groups CPG sections, calls OpenRouter (Gemini Flash),
                          │       upserts icd11_scope codes + scope_rationale,
                          │       sets scope_verified = FALSE, writes
                          │       tasks/cpg_scope_review.md
                          │
                          ├─►  CLINICIAN REVIEW (manual)
                          │    └─ Dr Chin edits tasks/cpg_scope_review.md
                          │       (Approve / Edit / Reject per CPG)
                          │
                          └─►  verify_cpg_scope.py
                               └─ parses review file, flips scope_verified = TRUE,
                                  writes verified_at / verified_by
```

**Validation queries before considering A-11 complete:**

```sql
-- Every CPG document must have at least one ICD-11 code in scope
SELECT title, icd11_scope, scope_verified
FROM documents
WHERE cardinality(icd11_scope) = 0 OR scope_verified = FALSE;
-- Expected: 0 rows.

-- Every code in any documents.icd11_scope must exist in icd11_codes
SELECT DISTINCT unnest(icd11_scope) AS code
FROM documents
WHERE NOT EXISTS (
    SELECT 1 FROM icd11_codes WHERE icd11_codes.code = unnest(documents.icd11_scope)
);
-- Expected: 0 rows. If non-empty, run ddx/ingest_icd11_full.py to backfill missing codes.
```

If any new CPG covers an ICD-11 code not yet in the `icd11_codes` table (e.g. a chapter not previously ingested), run `ddx/ingest_icd11_full.py` to fetch the missing codes from the WHO API **before** verification, so the `icd11_scope` reference is not dangling.

### 3.2 Sequencing inside A-11/A-13

For new CPGs, the order is strict:

1. `ingest.py --skip-graph --skip-classify <new-cpg-dir>` — creates `documents` + H1/H2 chunks with embeddings.
2. `classify_cpg_scope.py --cpg <new-cpg-name>` — adds `icd11_scope`.
3. **Manual review** of `tasks/cpg_scope_review.md`.
4. `verify_cpg_scope.py` — flips `scope_verified = TRUE`.
5. `ingest.py --graph-only <new-cpg-dir>` — runs `graph_builder.py` against the verified H2 chunks (ephemeral sub-windowing per §6).

For **existing CPGs** being re-ingested at H2 level: scope is already verified, so steps 2–4 are skipped — only steps 1 and 5 run. The existing `documents.icd11_scope` values survive because `ingest.py` should `UPSERT` on `documents.source` rather than wiping the row.

> **Safety check before A-13:** confirm `ingest.py` preserves `icd11_scope`, `scope_verified`, `verified_at`, `verified_by` on UPSERT. If it doesn't, the re-ingest will silently un-verify all 16 existing CPGs and Stage 3 routing breaks. Patch `ingest.py` to `ON CONFLICT DO UPDATE SET content = EXCLUDED.content, updated_at = NOW()` only — never touch the scope columns.

---

## 4. KG Sub-chunk Improvements

The following `graph_builder.py` changes apply to the selected H2 re-chunk path:

### Increase overlap 500 → 1,000 chars

**File:** [ingestion/graph_builder.py:535](../../ingestion/graph_builder.py)

```python
def _split_into_subchunks(self, text: str, max_chars: int = 6000, overlap: int = 1000):
```

### Add `subchunk_start_char` to triple metadata

In `_split_into_subchunks()` at lines 534–564, return `(text, start_offset)` tuples:
```python
subchunks.append((chunk, start))   # was: subchunks.append(chunk)
```

In `build_relationship_graph()` at lines 590–598, unpack and store:
```python
for sub_text, sub_start in subchunks:
    triples = await self._extract_triples_with_llm(text=sub_text, ...)
    for t in triples:
        t['subchunk_start_char'] = sub_start
```

Context reconstruction from any stored triple:
```python
# fetch H2 chunk content from NeonDB by cpg_chunk_id
# slice: content[subchunk_start_char : subchunk_start_char + 6000]
```

---

## 5. Verification Checklist

| Check | Expected result |
|-------|-----------------|
| Markdown alignment follows both guides | H2 children preserve H3/H4/table structure; parent-only blocks and `cross_ref` markers follow their separate rules |
| Query "Duke criteria IE" → correct section retrieved | H2 child chunk at rank 1 |
| Neo4j triple → NeonDB chunk (clickable citation) | `cpg_chunk_id` = H2 UUID |
| section-3-diagnosis chunk count in NeonDB | 5 rows (1 H1 + 4 H2) |
| Sub-chunk position tracking | `subchunk_focus_start` in triple |
| KG extraction LLM calls for IE section 3 | 4 H2 chunks × 1–2 sub-chunks |
| **All `documents.icd11_scope` populated + `scope_verified = TRUE`** | Yes — new CPGs pass through §3.1 pipeline |
| Every code in `documents.icd11_scope` exists in `icd11_codes` | No dangling refs |

---

## 6. KG Building — Ephemeral Sub-windowing with Context Bands

**Decision:** Keep H2 as the persisted citation unit. If an H2 child is still oversized (>8k chars), `graph_builder.py` chops it ephemerally into 6k focus windows with context bands on either side. The bands give the LLM enough surrounding text to resolve pronouns, scope conditions, and trailing grade-of-recommendation tags — but only the focus window is treated as an extraction target.

### Concept

```
[BEFORE — context only, do not extract triples from this]
<chars (focus_start - 2000) → focus_start>

[FOCUS — extract triples ONLY from this region]
<chars focus_start → focus_start + 6000>

[AFTER — context only, do not extract triples from this]
<chars (focus_start + 6000) → (focus_start + 8000)>
```

Total payload per LLM call: ~10k chars. Only the middle 6k is the extraction target. Cost impact: ~$1.58 → ~$2.10 across the full corpus — negligible.

### Change shape — `graph_builder.py`

**File:** [graph_builder.py:534-564](../../ingestion/graph_builder.py#L534-L564)

Change `_split_into_subchunks` from returning `[(text, start_offset), ...]` to returning structured windows:

```python
def _split_into_subchunks(
    self,
    text: str,
    focus_size: int = 6000,
    band_size: int = 2000,
    stride: int = 6000,  # non-overlapping focus windows; bands provide the bridge
) -> list[dict]:
    """
    Yields windows of the form:
      {
        "before": str,         # context-only band (may be empty at start)
        "focus":  str,         # extraction target
        "after":  str,         # context-only band (may be empty at end)
        "focus_start": int,    # offset of focus within parent text
        "focus_end":   int,
        "is_first":    bool,
        "is_last":     bool,
      }
    """
    windows = []
    for focus_start in range(0, len(text), stride):
        focus_end = min(focus_start + focus_size, len(text))
        before_start = max(0, focus_start - band_size)
        after_end = min(len(text), focus_end + band_size)
        windows.append({
            "before": text[before_start:focus_start],
            "focus":  text[focus_start:focus_end],
            "after":  text[focus_end:after_end],
            "focus_start": focus_start,
            "focus_end":   focus_end,
            "is_first":    focus_start == 0,
            "is_last":     focus_end == len(text),
        })
        if focus_end == len(text):
            break
    return windows
```

In `_extract_triples_with_llm` (around [graph_builder.py:382](../../ingestion/graph_builder.py#L382)), build the prompt as labeled regions:

```python
before_label = "[BEFORE — none, this is the start of the section]" if window["is_first"] \
               else f"[BEFORE — context only, do not extract triples from this]\n{window['before']}"
after_label  = "[AFTER — none, this is the end of the section]" if window["is_last"] \
               else f"[AFTER — context only, do not extract triples from this]\n{window['after']}"

prompt_body = (
    f"{before_label}\n\n"
    f"[FOCUS — extract triples ONLY from this region]\n{window['focus']}\n\n"
    f"{after_label}"
)
```

### System prompt addition

Add to the triple-extraction system prompt:

```
You will see three regions: [BEFORE], [FOCUS], [AFTER].
Extract triples ONLY from facts stated within [FOCUS].
Use [BEFORE] and [AFTER] solely to resolve references (pronouns,
section scope, grade-of-recommendation tags). Do not emit triples
whose subject AND object both lie outside [FOCUS].
```

### Triple metadata

Each emitted triple gets stamped with:
- `cpg_chunk_id` = H2 chunk UUID (persistent citation)
- `subchunk_focus_start` = `window["focus_start"]` (for debugging / future H3 backfill)

The sub-window itself is **not persisted**. The H2 UUID remains the citation target.

### Implementation steps

| Step | Action | Files | Risk |
|------|--------|-------|------|
| K-1 | Rewrite `_split_into_subchunks` to emit window dicts | `graph_builder.py:534-564` | Low |
| K-2 | Update prompt template with three labeled regions | `graph_builder.py:382` + prompt file | Low |
| K-3 | Add "do not extract from bands" instruction to system prompt | prompt file | Low |
| K-4 | Stamp `subchunk_focus_start` onto each triple | `graph_builder.py:590-598` | Low |
| K-5 | Keep existing triple-dedup pass as safety net | unchanged | Low |

### KG rebuild — when to actually run the commands

The code changes (K-1..K-5) land first as a deploy. The KG itself is then rebuilt during **A-14** in the §3 implementation steps. Strict order:

| Order | Command | Purpose |
|-------|---------|---------|
| 1 | `pytest tests/test_graph_builder_subwindow.py` | Unit-test the new window dicts + prompt template before touching prod Bedrock spend |
| 2 | Backup current graph: `cypher-shell "CALL apoc.export.cypher.all('backups/kg_pre_step2.cypher', {format:'cypher-shell'})"` | Roll-back point. Skip only if previous backup `backups/kg_backup_2026-05-12.cypher` is recent enough |
| 3 | A-13 must be complete — verify `SELECT count(*) FROM chunks WHERE chunk_level = 'h2'` returns expected H2 count | KG build reads H2 rows; running before A-13 would extract from the old polluted H1 rows |
| 4 | `cypher-shell "MATCH (n) DETACH DELETE n"` | Wipe old graph (564 Graphiti edges + 13 old typed triples). Confirmed safe — see Phase_A_Findings.md open question 3 |
| 5 | `python -m ingestion.ingest --graph-only --all-cpgs` (or per-CPG: `--cpg <name>`) | Runs `build_relationship_graph` with new sub-window context bands against H2 chunks |
| 6 | Smoke-check: `MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC` | Expect typed clinical relations (TREATS, INCREASES_RISK_OF, ASSESSED_BY, etc.) — no `MENTIONS` / `RELATES_TO` Graphiti residue |
| 7 | Sample triple → NeonDB resolution: pick one triple, confirm `r.cpg_chunk_id` exists in `chunks` and `chunk_level = 'h2'` | Validates the P2 citation link |

**Per-CPG dry run first.** Before the full `--all-cpgs` run, do one small CPG (Erectile-Dysfunction, 6 filtered chunks, ~$0.013) end-to-end through steps 4–7 to catch prompt-template bugs cheaply. Only proceed to `--all-cpgs` if the dry run looks clean.

**Cost expectation:** ~720 sub-windows × $0.0022 ≈ $1.60 across all CPGs at current size. With context bands (~+3k chars each) the figure rises to ~$2.10. Below the $50 threshold; no re-approval needed.

**Rate-limit safety:** if running A-14 unbatched takes >10 min for the full corpus, apply the `Semaphore(5)` batching from Step 3 §2.6 early. Functional equivalent — just paid down sooner if you need the wall time back.

---

## 7. Retrieval/Synthesis — Window Slicing as Outlier Handler

**Decision:** Most parents (under ~60k chars) are passed to the synthesis LLM in full. Window slicing is a **fallback for outliers** like IE section-3-diagnosis (97k) and section-4-management (131k) that would otherwise blow the evidence budget.

### Logic

```python
def build_parent_context(parent: Chunk, child: Chunk, limit: int = _PARENT_CHAR_LIMIT) -> str:
    if len(parent.content) <= limit:
        return parent.content  # whole parent fits
    # Outlier path: slice a window centered on the child's location inside the parent
    half = limit // 2
    window_start = max(0, child.start_char - half)
    window_end   = min(len(parent.content), child.end_char + half)
    return parent.content[window_start:window_end]
```

For IE section-4 (131k) with a child at chars 15k–60k and `_PARENT_CHAR_LIMIT=60_000`:
- `window_start = max(0, 15000 - 30000) = 0`
- `window_end   = min(131000, 60000 + 30000) = 90000`
- Result: chars 0–90k delivered (tail of 4.1 + all of 4.2 + 4.3) — 4.4 surgical timing is dropped.

### Frequency expectation

| Parent size | Slicing triggered? | % of IE corpus |
|---|---|---|
| ≤ 60k | No — full parent passed | 8 of 10 sections |
| > 60k | Yes — windowed | 2 of 10 sections (3, 4) |

### Implementation steps

| Step | Action | Files | Risk |
|------|--------|-------|------|
| W-1 | Add `build_parent_context()` helper in clinical_stages | `clinical_stages.py` | Low |
| W-2 | Update `_format_evidence` to call helper instead of raw `c.content` | `clinical_stages.py:551-575` | Low |
| W-3 | Log when slicing fires (parent size + child position) for telemetry | `clinical_stages.py` | Low |

Note: this code can be written and merged in Step 1 *before* parent-child ingest exists — it just won't trigger until the H2 re-ingest lands a real `child.start_char` / `parent.content` pair. Until then, treat retrieved chunks as standalone (no parent) and skip the helper.
