# Phase A — Step 2: Parent-Child Re-ingest (NeonDB + KG)

> **Position in rollout:** Step 2 of 3. Runs **after** Step 1 (synthesis cap fixes — see `Phase_A_Step1_Synthesis_Fixes_Now.md`) and **before** Step 3 (performance pass — see `Phase_A_Step3_Performance_Pass.md`).
> **Status:** Option A selected — H2 re-chunk with full re-ingest, **chain model for oversized H2s** (2026-05-14 revision). A-1 through A-10 were implemented against the earlier "oversized H2 stays `chunk_level='h2'`" design; the chain-model decision below supersedes that, so **A-2, A-5, A-7, A-8 drop back to `[ready]` for the `h3` delta**. Remaining: chain-model code revisions, A-11 (manual ICD-11 scope), A-12–A-15 (re-ingest / KG rebuild / smoke test).
> **Recommendation:** Proceed with H2 re-chunk. Normal H2 = embedded retrievable child. An H2 over the 8k cap becomes an **unembedded intermediate** whose `### H3` children are the embedded retrievable rows (`chunk_level='h3'`), chained `H3 → H2 → H1`. Same UUID still serves retrieval and KG citation at whichever level was the hit.
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
│  NeonDB — chain-model storage (H1 → H2 → H3)
│
├── H1 PARENT chunk (stored for context, NOT embedded)
│   chunk_id: "a1b2-h1"   content: full 51k chars   embedding: NULL
│   chunk_level: "h1"      parent_chunk_id: NULL
│
├── H2 CHILD chunk — 3.1 Clinical evaluation     (≤8k → normal embedded child)
│   chunk_id: "c3d4-3.1"  content: ~3,000 chars     embedding: [vector]
│   chunk_level: "h2"      parent_chunk_id: "a1b2-h1"
│
├── H2 CHILD chunk — 3.2 Investigations          (≤8k → normal embedded child)
│   chunk_id: "e5f6-3.2"  content: ~7,000 chars     embedding: [vector]
│   chunk_level: "h2"      parent_chunk_id: "a1b2-h1"
│
├── H2 INTERMEDIATE — 3.3 Imaging                (>8k → cap-split, NOT embedded)
│   chunk_id: "g7h8-3.3"  content: ~10,000 chars    embedding: NULL
│   chunk_level: "h2"      parent_chunk_id: "a1b2-h1"
│   │
│   ├── H3 CHILD — 3.3.1 Transthoracic echo       (embedded retrievable row)
│   │   chunk_id: "k1l2-3.3.1"  content: ~4,000 chars  embedding: [vector]
│   │   chunk_level: "h3"        parent_chunk_id: "g7h8-3.3"
│   │
│   └── H3 CHILD — 3.3.2 Transoesophageal echo    (embedded retrievable row)
│       chunk_id: "m3n4-3.3.2"  content: ~6,000 chars  embedding: [vector]
│       chunk_level: "h3"        parent_chunk_id: "g7h8-3.3"
│
└── H2 CHILD chunk — 3.4 Diagnostic criteria (Duke)  (≤8k → normal embedded child)
    chunk_id: "i9j0-3.4"  content: ~8,000 chars     embedding: [vector]
    chunk_level: "h2"      parent_chunk_id: "a1b2-h1"

  Neo4j — Triples extracted from embedded child chunks (h2 + h3)
  └── (:Condition)-[:ASSESSED_BY]->(:DiagnosticTool)
        r.cpg_chunk_id = "m3n4-3.3.2"  ← same UUID as the embedded child that was the
                                          extraction source → direct citation
```

### Cap-split H2 — the chain model

When an `## H2` exceeds the 8,000-char cap it is **not** embedded as one noisy/truncated vector. Instead:

```text
Normal H2 (≤ 8k chars):
  chunk_level = 'h2', embedded, parent_chunk_id → H1.   Retrievable. Unchanged.

Cap-split H2 (> 8k chars):
  chunk_level = 'h2', embedding = NULL, parent_chunk_id → H1.
  Stored as an unembedded INTERMEDIATE — never a vector hit, but still
  addressable by chunk_id (so cross_refs and the chain walk can reach it).

  Its ### H3 subsections become the embedded retrievable rows:
  chunk_level = 'h3', embedded, parent_chunk_id → the cap-split H2 (NOT H1).
```

Why: an H2 only gets cap-split *because* it was too big to embed coherently (the P1 / 32k-truncation problem). Embedding both the H2 and its H3 children would embed the same text twice and produce redundant top-K hits. So the cap-split H2 drops its vector; only the H3 parts stay embedded.

`parent_chunk_id` is therefore a **chain**, not always a direct link to H1:

```text
normal H2  →  H1                       (one hop)
H3         →  cap-split H2  →  H1       (two hops)
```

Retrieval is still uniform — every embedded row (`h2` or `h3`) is ranked in the same vector pool. The retrieval filter keys on `embedding IS NOT NULL`, **not** `chunk_level = 'h2'`, so it naturally includes `h3` rows and `h1_leaf`, and excludes both `h1` and the unembedded cap-split `h2`.

### Query Path (Parent-Child Retrieval)

```
User query: "What are the Duke criteria for diagnosing IE?"
│
├─ Step 1: Embed query → cosine search against all embedded child rows
│          (embedding IS NOT NULL → covers h2, h3, h1_leaf)
│
├─ Step 2: Top-K child hits
│          → "i9j0-3.4" (3.4 Diagnostic criteria, h2) similarity: 0.91  ← precise hit
│          → "c3d4-3.1" (3.1 Clinical evaluation, h2) similarity: 0.61
│
├─ Step 3: Walk parent_chunk_id up the chain for each hit
│          h2 hit  → fetch H1                       (one hop)
│          h3 hit  → fetch cap-split H2, then H1    (two hops)
│
└─ Step 4: LLM receives:
           [CHILD — citation source]  chunk: "i9j0-3.4" | "Modified Duke criteria include..."
           [PARENT — full context]    chunk: "a1b2-h1"  | (full section 3 for synthesis)


Example — H3 hit ("When should transoesophageal echo be used?"):
│
├─ Top-1: "m3n4-3.3.2" (3.3.2 Transoesophageal echo, h3) similarity: 0.89
│
├─ Chain walk: m3n4 → parent "g7h8-3.3" (cap-split H2) → parent "a1b2-h1"
│
└─ LLM receives three tiers:
   [CHILD — citation source]  "m3n4-3.3.2" | "Transoesophageal echo is recommended when..."
   [SECTION — mid context]    "g7h8-3.3"   | full 3.3 Imaging (passed whole, ≤ limit)
   [PARENT — full context]    "a1b2-h1"    | Section 3 with the 3.3 span sliced out (see §7)
```

### NeonDB Schema Change

Migration file: `sql/migrations/006_chunk_level_and_cleanup.sql`

**Add columns required for parent-child architecture:**

```sql
-- Add chunk level discriminator:
--   h1       = parent, never embedded
--   h2       = child; embedded when ≤8k, NULL embedding when cap-split (intermediate)
--   h3       = child of a cap-split H2; always embedded
--   h1_leaf  = file has no H2s; H1 is both parent and leaf, embedded
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS chunk_level TEXT NOT NULL DEFAULT 'h1_leaf';

-- Add child position for build_parent_context() window slicing.
-- IMPORTANT: start_char/end_char are offsets into the H1 content for EVERY level
-- (including h3), so slicing always works against parent.content.
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS start_char INTEGER;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS end_char   INTEGER;

-- Index supports the retrieval filter and chain walks.
CREATE INDEX IF NOT EXISTS idx_chunks_level ON chunks (chunk_level);
```

**`parent_chunk_id` is a chain, not a flat link.** A normal `h2` and an `h1_leaf` point at their `h1`. An `h3` points at its cap-split `h2`, which in turn points at the `h1`. Resolver code must walk up, not assume the parent is always `h1`. The cap-split `h2` keeps a real `chunk_id` (it is stored, just unembedded) so cross_refs and the chain walk can address it.

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

Vector search in [agent/db_utils.py:369-522](../../agent/db_utils.py): filter `WHERE c.embedding IS NOT NULL` for retrieval (covers `h2`, `h3`, `h1_leaf`; excludes `h1` and the unembedded cap-split `h2`). Do **not** filter on `chunk_level = 'h2'` — that both drops real `h3` hits and lets the NULL-embedding cap-split `h2` leak in. Fetch `WHERE chunk_id = $parent_chunk_id` for context, walking the chain until `chunk_level = 'h1'`.

### Markdown Alignment Inputs

Before re-ingest, align markdown against the current consolidated guide:

- [Markdown_Standardization_And_Cross_Reference_Guide.md](./Markdown_Standardization_And_Cross_Reference_Guide.md): controls standard section filenames, exactly-one-H1-per-file structure, H1/H2/H3/H4 hierarchy, H2 child boundaries, table/figure demotion, parent-only reference block placement, `cross_ref` markers, cross-reference audit rules, and cleanup before ingestion.

The older [CPG-RAG-Standardization-Guide.md](../../Reading%20Docs/CPG-RAG-Standardization-Guide.md) is useful only for legacy evidence-tag and author-time `<!-- METADATA -->` conventions. Its older H3-child chunking and overlap-reattachment model is superseded by this Step 2 plan:

```text
Current Phase A Step 2 retrieval units (chain model):
  embedded child rows = normal H2 (`chunk_level='h2'`)
                      + H3 rows from cap-split H2s (`chunk_level='h3'`)
                      + H1-leaf files (`chunk_level='h1_leaf'`)
  retrieval filter keys on `embedding IS NOT NULL`, not on chunk_level

H3/H4 headings:
  stay inside the owning H2 UNLESS that H2 exceeds the 8k cap;
  then the H2 becomes an unembedded intermediate and its H3 subsections
  are persisted as real `chunk_level='h3'` rows (parent_chunk_id → that H2)

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
  Expected fields include doc_title, h2_title, h3_title (the real heading
  of an `h3` row from a cap-split H2 — descriptive, the retrieval level is
  carried by the `chunk_level` column), context_path, evidence_grades,
  evidence_levels, cross_refs, and parent_chunk_id on child rows.
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
- Pass 2: split at `##` within each H1 → H2 chunks (stored). Measure each H2's char length:
  - **≤ 8,000 chars** → normal child: `chunk_level='h2'`, embedded, `parent_chunk_id` → H1.
  - **> 8,000 chars** → cap-split. The H2 row is still stored but `chunk_level='h2'` with **`embedding=NULL`** (unembedded intermediate), `parent_chunk_id` → H1. Pass 3 splits it at `###` → `chunk_level='h3'` rows, embedded, `parent_chunk_id` → **that H2's chunk_id** (not H1).
- For a normal (non-cap-split) H2, keep `###` numbered subsections such as `3.1.1`, `3.1.2` inside the owning H2 child — no `h3` rows are emitted.
- `start_char` / `end_char` on **every** row (h2 and h3) are offsets into the **H1** content, so `build_parent_context()` can slice against `parent.content` regardless of level.
- Insert order must be H1 → each H2 → that H2's H3s, so the `parent_chunk_id` FK resolves.
- Demote Table/Figure labels to plain prose unless they sit inside a `parent_only_reference` block; this keeps tables inside the owning H2/H3 text instead of turning them into metadata-bearing headings.
- Fallback: if no H2 headers exist, H1 chunk becomes both parent and leaf (`chunk_level='h1_leaf'`, embedded).
- An `### H3` is not further split for retrieval even if large (embedding tolerates up to ~32k chars); KG extraction handles oversize H3s with ephemeral sub-windowing (§6).

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
h3_section          (### H3 — only retrievable when its parent H2 was cap-split at 8k; else resolver falls back to the enclosing H2)
algorithm_flowchart
appendix
```

Chunker/ingestion behavior:
- Keep the visible human sentence in the child text.
- Parse the `cross_ref` marker into `cross_refs` metadata on **whatever chunk row the "refer to..." sentence physically falls in** — usually a normal `h2` or an `h3`, but if the sentence sits in a cap-split H2's preamble it lands on that unembedded `h2` row. Authors do not need to predict cap-splitting; ingestion attaches to the physical row.
- Do **not** place a `cross_ref` marker inside a `parent_only_reference` block — that content is masked out of the chain, so the resolver never reaches it. Markers do not nest. Within-file references (same H1) need no marker at all.
- Strip the marker itself from embedding text and normal LLM prompt text.
- Resolution is **chain-aware** (see A-8b): collect `cross_refs` from the hit child *and* every parent reached on the chain walk, so a marker on an unembedded cap-split `h2` still fires on an `h3` hit.

Retrieval behavior:
- Retrieve the primary embedded child (`h2` or `h3`) normally.
- Walk `parent_chunk_id` up the chain for context:
  - `h2` / `h1_leaf` hit → one hop to H1.
  - `h3` hit → hop to the cap-split H2 (mid context, passed whole — it is ≤ the parent limit), then hop to H1.
- If `child.metadata.cross_refs` exists, resolve the target evidence before Stage 5 synthesis.
- For `h1_section`, prefer the best matching child under the target H1; use capped/windowed target H1 only when a specific child cannot be resolved.
- For `h3_section`, fetch the `h3` row if the target H2 was cap-split and produced one; otherwise fall back to the enclosing H2 child chunk.
- For a cross_ref `h2_section` pointing at a cap-split H2, resolve to that stored (unembedded) H2 row directly — it is addressable by `chunk_id`.
- Do not blindly attach two full H1 parents by default.

### KG Extraction Change

Read **embedded child chunks** from NeonDB instead of H1 — this means normal H2 rows plus H3 rows from cap-split H2s, and excludes both H1 and the unembedded cap-split H2:
```sql
SELECT chunk_id, content, metadata FROM chunks
WHERE document_id = $1 AND embedding IS NOT NULL
  AND metadata->>'category' = ANY($category_whitelist)
ORDER BY chunk_index;
```

`cpg_chunk_id` on each triple is the UUID of whichever embedded child (h2 or h3) was the extraction source — so KG citations always resolve to a retrievable row.

IE section-3: was 1 H1 → 9 sub-chunks (51k ÷ 6k). Now: a mix of normal H2 rows and (for cap-split H2s) their H3 rows, each with 0–2 ephemeral sub-windows.

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

| Status | Step | Action | Files / Area | Current State (audited 2026-05-15) | Exit Gate |
|--------|------|--------|--------------|-------------------------------------|-----------|
| [x] | A-0 | Step 1 prerequisites confirmed: tiered budgets, token counting, whole-chunk formatting, parent dedupe, prompt-size guard, `build_parent_context()` stub present. | `agent/clinical_stages.py:582` | Confirmed — `build_parent_context()` exists at line 582, currently a stub with comment "Step 2 will expand this". All Step 1 guards in place. | Complete. Gates Step 2 coding only, not re-ingest. |
| [x] | A-1 | **Schema migration:** Write `sql/migrations/006_chunk_level_and_cleanup.sql`. Add `chunk_level TEXT NOT NULL DEFAULT 'h1_leaf'`, `start_char INTEGER`, `end_char INTEGER`, index on `chunk_level`. Drop 5 dead columns: `is_recommendation`, `is_table`, `is_algorithm`, `structured_content`, `section_hierarchy` (see §3 NeonDB Schema Change for full SQL and rationale). Update `schema.sql` to reflect clean final state. | `sql/migrations/006_chunk_level_and_cleanup.sql`, `sql/schema.sql` | Done — migration file written, schema.sql updated. 007 migration also added for updated `match_chunks()` / `hybrid_search()` SQL functions keyed on `embedding IS NOT NULL`. | Migration runs clean; `\d chunks` shows new columns, dead columns gone. |
| [x] | A-2 | **Chunker H2/H3 chain splitting:** Cap-split H2 (>8k) stored as unembedded intermediate (`chunk_level='h2'`, `cap_split=True`); its `###` subsections emitted as `chunk_level='h3'` rows, embedded, `parent_chunk_id` → cap-split H2. `cap_split_h2_index` written to H3 metadata so ingest can resolve the UUID. `h3_section` added to `_VALID_TARGET_KINDS`. Stats log updated to show all levels. | `ingestion/chunker.py` | Done (2026-05-15) — dry-run of AF CPG confirms: sections 4, 5, 6, 7, 12 correctly produce cap_split_h2 + h3 rows. Note: cap-split H2 with no `###` headings produces a duplicate H3 child — fix is to add `###` headings in the markdown (team action). | Dry-run shows `h1`, normal `h2`, `cap_split_h2`, `h3` counts as expected; no `h3` row with `parent_chunk_id` pointing at `h1`. |
| [x] | A-3 | **Parent-only reference blocks:** Before H2 splitting, detect `<!-- parent_only_reference_start -->` ... `<!-- parent_only_reference_end -->` blocks. Keep them inside H1 parent content; mask/remove them before H2 splitting so they are not emitted as child chunks. | `ingestion/chunker.py` | Done — `PARENT_ONLY_BLOCK_PATTERN` regex and `_strip_parent_only_blocks()` implemented. | Marked shared tables present in H1 parent, absent from H2 child embeddings. |
| [x] | A-4 | **Cross-ref marker parsing:** Parse `<!-- cross_ref target_file="..." target_heading="..." target_kind="..." -->` comments. Store parsed list as `metadata.cross_refs` on the H2/H3 child chunk. Strip marker from embedding/prompt text. `h3_section` is a valid `target_kind`. | `ingestion/chunker.py` | Done — `CROSS_REF_PATTERN` regex and `_strip_cross_refs()` implemented. `_VALID_TARGET_KINDS` now includes `h3_section`. | H2/H3 child has clean content; `metadata.cross_refs` populated when marker present. |
| [ready] | A-4b | **Markdown metadata contract:** Run `audit_markdown.py` on each target folder; verify exactly one H1, H2-only retrieval boundaries, Table/Figure demotion, `parent_only_reference` placement, and `cross_ref` validity. For cap-split H2 sections, ensure `###` headings exist so no duplicate H3 is produced (e.g. AF section 4.3 needs `###` sub-headings added). | `audit_markdown.py`, target `markdown/<CPG>/` folders | Manual team action required. AF sections 6 and 12 also have Windows console encoding issues (`→`, `₂`) that are cosmetic for dry-run but should be verified clean on actual ingest. | Dry-run audit has no blockers; all cap-split H2s have at least 2 `###` children. |
| [x] | A-5 | **Ingestion persistence (chain):** Three-pass insert: Pass 1 — H1 parents (no embedding). Pass 2 — cap-split H2 intermediates (no embedding, parent → H1). Pass 3 — normal H2 + H3 + h1_leaf (embedded); H3 resolves `parent_chunk_id` from `h2_uuid_by_index[cap_split_h2_index]`. | `ingestion/ingest.py` | Done (2026-05-15) — three-pass logic implemented. | Re-ingest of a CPG with a >8k H2: `SELECT chunk_level, count(*) ... GROUP BY chunk_level` shows `h1`, `h2`, `h3`; cap-split `h2` has `embedding IS NULL`; every `h3.parent_chunk_id` resolves to an `h2` row. |
| [x] | A-6 | **Protect scope metadata on re-ingest UPSERT:** `ON CONFLICT (source) DO UPDATE SET title, content, metadata, updated_at` only — never touch `icd11_scope`, `scope_verified`, `verified_at`, `verified_by`. | `ingestion/ingest.py` | Done — confirmed in code. | Dry-run re-ingest of one verified CPG: `scope_verified` remains TRUE, `icd11_scope` unchanged. |
| [x] | A-7 | **Retrieval filter (embedding-keyed):** `AND c.embedding IS NOT NULL` in both `document_id_filter` branches of `vector_search()` and `hybrid_search()` in `db_utils.py`. Dead `# chunk_level='h2'` comments removed. SQL functions in 007 migration already use `embedding IS NOT NULL`. | `agent/db_utils.py`, `sql/migrations/007_chain_model_retrieval_functions.sql` | Done (2026-05-15). | `vector_search()` never returns `h1` or cap-split `h2` rows. |
| [x] | A-8 | **Parent context fetch + chain walk:** `_prefetch_parent_content()` walks two hops for H3 hits — cap-split H2 → `section_content`, H1 with H2-span replaced by gap marker → `parent_content`. `build_parent_context()` emits 3 tiers (`[CHILD]+[SECTION]+[PARENT]`) for H3 hits, 2 tiers for H2/h1_leaf. `section_content` field added to `ChunkResult` in `models.py`. | `agent/clinical_stages.py`, `agent/models.py` | Done (2026-05-15). | Stage 5 evidence log: `h2` hit → `[CHILD]+[PARENT]`; `h3` hit → `[CHILD]+[SECTION]+[PARENT]` with no duplicated text. |
| [x] | A-8b | **Cross-ref resolver (chain-aware):** `_resolve_cross_refs()` added to `clinical_stages.py`. Collects `cross_refs` from each hit chunk's metadata, deduplicates by `target_file+target_heading`, fetches best matching embedded child from target document (heading match for `h2_section`/`h3_section`; first embedded child for `h1_section`/`appendix`). Resolved chunks appended to evidence list before `_format_evidence`. Skips duplicates already in evidence pack. Called in `stage_5_synthesize` after `_prefetch_parent_content`. | `agent/clinical_stages.py` | Done (2026-05-15). | Smoke query with a known `cross_ref` shows referenced target evidence in Stage 5 pack. |
| [x] | A-9 | **KG extraction reads embedded chunks:** `build_relationship_graph()` filters `chunk_level in ("h2", "h3", "h1_leaf")` — includes H3 rows from cap-split H2s, excludes unembedded H1 and cap-split H2 intermediates. | `ingestion/graph_builder.py` | Done (2026-05-15). | New triples all have `cpg_chunk_id` resolvable to an embedded (`h2`/`h3`) row in `chunks`. |
| [x] | A-10 | **KG sub-window context bands:** `_split_into_subchunks()` returns windowed dicts with `before`, `focus`, `after`, `focus_start`, `focus_end`, `is_first`, `is_last`. Triple-extraction prompt labels regions. `subchunk_focus_start` stamped on each triple. | `ingestion/graph_builder.py` | Done. | Triple metadata contains `subchunk_focus_start`. |
| [manual] | A-11 | Run ICD-11 scope pipeline for any newly added CPGs, then clinician review and verification. | `classify_cpg_scope.py`, `verify_cpg_scope.py` | Existing 16 CPGs already verified. Required only for new CPGs added before re-ingest. | All documents: `cardinality(icd11_scope) > 0` AND `scope_verified = TRUE`. |
| [x] | A-12 | **Live ingest AF CPG (2026-05-16) — COMPLETE.** Migrations 006+007 applied. Chunks wiped (217 deleted). AF re-ingested: 12 sections → 96 chunks (all `h1_leaf`; AF sections fit within cap, no cap-splitting triggered). 0 ingest errors. | CLI | — | Q1–Q8 all PASS: h1_leaf fully embedded, Q4 0 bad parents, Q6 17 chunks with 25 cross_refs, Q7 match_chunks returns only h1_leaf (no h1), Q8 non-AF chunks=0. icd11_codes=3914 preserved, documents=223 (212 pre-existing + 11 new AF sections). |
| [x] | A-12b | **Metadata gate COMPLETE (2026-05-16).** Q1: 96 h1_leaf rows all embedded. Q2: 0 cap-split h2 (none needed). Q3: 0 h3 (none needed). Q4: 0 bad parents. Q5: icd11_scope at schema defaults (new inserts, no drift). Q6: PASS. Q7: PASS. Q8: PASS. | SQL | — | All 8 acceptance queries PASS. |
| [ready] | A-13 | Full re-ingest all CPGs with H1/H2/H3 parent-child chain. | CLI | A-12 clean — UNBLOCKED. | Expected H2/H3 count across corpus. No verified scope metadata lost. |
| [tomorrow] | A-14 | Backup Neo4j → wipe old graph → rebuild KG from new H2/H3 chunks. | Cypher, `ingest --graph-only` | Blocked on A-13 complete. Previous backup at `backups/kg_backup_2026-05-12.cypher`. | Typed clinical relations present; no Graphiti residue. |
| [tomorrow] | A-15 | End-to-end smoke test: clinical query, cross-ref resolution, citation click-through, parent context inclusion, prompt budget logs. | Clinical pipeline | Blocked on A-14 clean. | Correct answer; H2/H3 citation resolves; referenced evidence attaches; no prompt oversize. |

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

1. `ingest.py --skip-graph --skip-classify <new-cpg-dir>` — creates `documents` + the H1/H2/H3 chain (embeddings on the embedded child rows).
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
| Markdown alignment follows the consolidated guide | H2/H3 children preserve table structure; parent-only blocks and `cross_ref` markers follow their separate rules |
| Query "Duke criteria IE" → correct section retrieved | embedded child (`h2` or `h3`) at rank 1 |
| Retrieval filter excludes unembedded rows | no `h1` and no cap-split `h2` ever appears in top-K |
| `h3` hit produces a 3-tier evidence pack | `[CHILD h3]` + `[SECTION h2]` + `[PARENT h1]`, no duplicated text |
| Chain integrity | every `h3.parent_chunk_id` resolves to an `h2` row; every `h2`/`h1_leaf` parent resolves to an `h1` row |
| Neo4j triple → NeonDB chunk (clickable citation) | `cpg_chunk_id` = an embedded child UUID (`h2` or `h3`) |
| Sub-chunk position tracking | `subchunk_focus_start` in triple |
| **All `documents.icd11_scope` populated + `scope_verified = TRUE`** | Yes — new CPGs pass through §3.1 pipeline |
| Every code in `documents.icd11_scope` exists in `icd11_codes` | No dangling refs |

---

## 6. KG Building — Ephemeral Sub-windowing with Context Bands

**Decision:** The persisted citation unit is whichever **embedded child** was the extraction source — a normal `h2` row, or an `h3` row from a cap-split H2. (The cap-split H2 itself is unembedded and is *not* an extraction source; its content is covered by its `h3` rows.) If an embedded child is still oversized (>8k chars — possible for a large `h3` or `h1_leaf`), `graph_builder.py` chops it ephemerally into 6k focus windows with context bands on either side. The bands give the LLM enough surrounding text to resolve pronouns, scope conditions, and trailing grade-of-recommendation tags — but only the focus window is treated as an extraction target.

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
- `cpg_chunk_id` = the embedded child UUID — `h2` or `h3` — that was the extraction source (persistent citation)
- `subchunk_focus_start` = `window["focus_start"]` (for debugging / position recovery)

The sub-window itself is **not persisted**. The embedded child UUID remains the citation target.

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
| 3 | A-13 must be complete — verify `SELECT chunk_level, count(*) FROM chunks WHERE embedding IS NOT NULL GROUP BY chunk_level` returns expected `h2`/`h3` counts | KG build reads embedded child rows; running before A-13 would extract from the old polluted H1 rows |
| 4 | `cypher-shell "MATCH (n) DETACH DELETE n"` | Wipe old graph (564 Graphiti edges + 13 old typed triples). Confirmed safe — see Phase_A_Findings.md open question 3 |
| 5 | `python -m ingestion.ingest --graph-only --all-cpgs` (or per-CPG: `--cpg <name>`) | Runs `build_relationship_graph` with new sub-window context bands against H2 chunks |
| 6 | Smoke-check: `MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC` | Expect typed clinical relations (TREATS, INCREASES_RISK_OF, ASSESSED_BY, etc.) — no `MENTIONS` / `RELATES_TO` Graphiti residue |
| 7 | Sample triple → NeonDB resolution: pick one triple, confirm `r.cpg_chunk_id` exists in `chunks` with `embedding IS NOT NULL` (an `h2` or `h3` row) | Validates the P2 citation link |

**Per-CPG dry run first.** Before the full `--all-cpgs` run, do one small CPG (Erectile-Dysfunction, 6 filtered chunks, ~$0.013) end-to-end through steps 4–7 to catch prompt-template bugs cheaply. Only proceed to `--all-cpgs` if the dry run looks clean.

**Cost expectation:** ~720 sub-windows × $0.0022 ≈ $1.60 across all CPGs at current size. With context bands (~+3k chars each) the figure rises to ~$2.10. Below the $50 threshold; no re-approval needed.

**Rate-limit safety:** if running A-14 unbatched takes >10 min for the full corpus, apply the `Semaphore(5)` batching from Step 3 §2.6 early. Functional equivalent — just paid down sooner if you need the wall time back.

---

## 7. Retrieval/Synthesis — Window Slicing as Outlier Handler

**Decision:** Most parents (under ~60k chars) are passed to the synthesis LLM in full. Window slicing is a **fallback for outliers** like IE section-3-diagnosis (97k) and section-4-management (131k) that would otherwise blow the evidence budget. The chain model adds one more concern: an `h3` hit has both a `[SECTION]` (H2) and a `[PARENT]` (H1) tier, and `h3 ⊂ h2 ⊂ h1` — so the H1 tier must be built to **exclude** the H2 span, otherwise the same text is delivered up to three times.

### Logic

```python
def build_evidence_tiers(child: Chunk, limit: int = _PARENT_CHAR_LIMIT) -> list[Tier]:
    tiers = [Tier("CHILD", child.content, child.chunk_id)]   # the citation source

    if child.chunk_level == "h3":
        h2 = fetch(child.parent_chunk_id)                    # cap-split, unembedded
        h1 = fetch(h2.parent_chunk_id)
        # mid tier: the cap-split H2 passed whole (≤ limit in practice)
        tiers.append(Tier("SECTION", _maybe_window(h2, child, limit), h2.chunk_id))
        # H1 tier: cut the H2 span out so nothing is duplicated
        h1_ctx = (h1.content[:h2.start_char]
                  + "\n\n[… Section " + h2.h2_title + " shown above …]\n\n"
                  + h1.content[h2.end_char:])
        if len(h1_ctx) > limit:                              # only monster H1s
            h1_ctx = _window(h1_ctx, around=h2.start_char, limit=limit)
        tiers.append(Tier("PARENT", h1_ctx, h1.chunk_id))
    else:                                                    # h2 / h1_leaf hit
        h1 = fetch(child.parent_chunk_id)
        tiers.append(Tier("PARENT", _maybe_window(h1, child, limit), h1.chunk_id))

    return tiers


def _maybe_window(parent: Chunk, child: Chunk, limit: int) -> str:
    if len(parent.content) <= limit:
        return parent.content                                # whole parent fits
    half = limit // 2                                        # outlier: slice around child
    start = max(0, child.start_char - half)
    end   = min(len(parent.content), child.end_char + half)
    return parent.content[start:end]
```

- `child.start_char` / `child.end_char` are **H1-relative** for every level (set by the chunker, A-2), so `_maybe_window` and the H1-minus-H2-span cut both operate against the same coordinate space.
- The `[… Section X shown above …]` gap marker is required — without it the H1 slice has a silent discontinuity and the LLM may read 3.2 as flowing straight into 3.4.
- For an `h2` / `h1_leaf` hit nothing changes from the original outlier logic — there is no H2 span to remove.

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
| W-1 | Implement `build_evidence_tiers()` (chain walk + H1-minus-H2-span) in clinical_stages | `clinical_stages.py` | Med |
| W-2 | Update `_format_evidence` to render the returned tiers (`[CHILD]` / `[SECTION]` / `[PARENT]`) instead of raw `c.content` | `clinical_stages.py:551-575` | Low |
| W-3 | Log when slicing fires and when the H1-minus-H2-span cut fires (sizes + child position) for telemetry | `clinical_stages.py` | Low |

Note: the `h2` / `h1_leaf` branch can be written and merged in Step 1 *before* parent-child ingest exists — it just won't trigger until re-ingest lands real `start_char` / `parent_chunk_id` values. The `h3` chain branch only becomes reachable once A-2's cap-split path lands `h3` rows. Until then, treat retrieved chunks as standalone (no parent) and skip the helper.
